#!/usr/bin/env python3
"""
SongShapes HTTP API.

docker-compose launches this as `python3 app.py 5000`.

Unlike mastercrafter_web_ui.py, this process does no audio work itself. It
accepts an upload, hands the job to Celery, and reports status. The heavy
stages run in the worker container; both sides meet at the job directory on
the shared volume.

Routes
    GET  /                             the existing UI template
    GET  /api/health                   liveness + broker reachability
    POST /api/upload                   store audio, create a job
    POST /api/jobs/<id>/analyze        queue Stage 1
    POST /api/jobs/<id>/generate       queue Stage 2
    POST /api/jobs/<id>/synthesize     queue Stage 3
    POST /api/jobs/<id>/run            queue all three
    GET  /api/jobs/<id>                job status
    GET  /api/jobs                     recent jobs
    GET  /api/jobs/<id>/audio/<track>  stream a rendered stem
    POST /api/jobs/<id>/lock/<track>   lock / unlock a track
    GET  /api/jobs/<id>/stems          list downloadable stems
    DELETE /api/jobs/<id>              remove a job and its files
"""

import os
import sys
import tempfile

from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.utils import secure_filename

import songshapes_store as store

ALLOWED_EXTENSIONS = (".wav", ".mp3", ".flac", ".ogg", ".aiff", ".aif", ".m4a")
MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # room for a full-length multitrack bounce

app = Flask(__name__, template_folder="templates")
app.secret_key = os.environ.get("SONGSHAPES_SECRET", "songshapes-dev-secret")
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES


def _tasks():
    """
    Import the Celery module lazily.

    Flask should still start and serve /api/health when Redis is unreachable,
    so the import cost and any broker error stay inside the request that needs
    a worker.
    """
    import celery_tasks
    return celery_tasks


def _queue(task, job_id, stage_label):
    """Send one stage to the worker and record the task id on the job."""
    record = store.load_job(job_id)
    if record is None:
        return jsonify({"status": "error", "message": "no such job"}), 404
    try:
        async_result = task.delay(job_id)
    except Exception as exc:  # broker down, etc.
        return jsonify({
            "status": "error",
            "message": f"could not reach the task queue: {exc}",
        }), 503

    task_ids = dict(record.get("task_ids") or {})
    task_ids[stage_label] = async_result.id
    store.update_job(job_id, task_ids=task_ids, error=None)

    return jsonify({
        "status": "queued",
        "job_id": job_id,
        "stage": stage_label,
        "task_id": async_result.id,
    }), 202


# ─────────────────────────────────────────────────
# UI + health
# ─────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/health")
def health():
    """Report whether the broker is reachable, without failing the request."""
    broker = {"configured": os.environ.get("REDIS_URL", "redis://localhost:6379/0")}
    try:
        from celery_tasks import app as celery_app
        conn = celery_app.connection()
        conn.ensure_connection(max_retries=0, timeout=2)
        conn.release()
        broker["reachable"] = True
    except Exception as exc:
        broker["reachable"] = False
        broker["error"] = str(exc)[:200]

    return jsonify({
        "status": "ok",
        "data_root": store.DATA_ROOT,
        "broker": broker,
    })


# ─────────────────────────────────────────────────
# Upload
# ─────────────────────────────────────────────────

@app.route("/api/upload", methods=["POST"])
def upload():
    """
    Accept an audio file and create a job for it.

    Accepts the field name "file" (used by the current UI) or "audio".
    Pass run=1 to queue the whole pipeline immediately.
    """
    upload_file = request.files.get("file") or request.files.get("audio")
    if upload_file is None or upload_file.filename == "":
        return jsonify({"status": "error", "message": "no audio file provided"}), 400

    filename = secure_filename(upload_file.filename)
    if not filename.lower().endswith(ALLOWED_EXTENSIONS):
        return jsonify({
            "status": "error",
            "message": f"unsupported format; accepted: {', '.join(ALLOWED_EXTENSIONS)}",
        }), 400

    record = store.create_job(source_name=filename)
    job_id = record["job_id"]

    # Stage the upload outside the job dir, then let the store normalize it in.
    tmp_path = os.path.join(tempfile.gettempdir(), f"{job_id}_{filename}")
    upload_file.save(tmp_path)
    try:
        sr, duration = store.save_source_audio(job_id, tmp_path)
    except Exception as exc:
        store.fail_job(job_id, f"could not read audio: {exc}")
        return jsonify({
            "status": "error",
            "job_id": job_id,
            "message": f"could not read that audio file: {exc}",
        }), 400
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    response = {
        "status": "success",
        "job_id": job_id,
        "source_name": filename,
        "sample_rate": sr,
        "duration": duration,
    }

    if request.args.get("run") or (request.form.get("run") in ("1", "true")):
        try:
            async_result = _tasks().run_pipeline.delay(job_id)
            response["pipeline_task_id"] = async_result.id
            response["status"] = "queued"
        except Exception as exc:
            response["warning"] = f"uploaded, but could not queue work: {exc}"

    return jsonify(response), 201


# ─────────────────────────────────────────────────
# Stage triggers
# ─────────────────────────────────────────────────

@app.route("/api/jobs/<job_id>/analyze", methods=["POST"])
def analyze(job_id):
    return _queue(_tasks().analyze, job_id, "analyze")


@app.route("/api/jobs/<job_id>/generate", methods=["POST"])
def generate(job_id):
    return _queue(_tasks().generate, job_id, "generate")


@app.route("/api/jobs/<job_id>/synthesize", methods=["POST"])
def synthesize(job_id):
    return _queue(_tasks().synthesize, job_id, "synthesize")


@app.route("/api/jobs/<job_id>/run", methods=["POST"])
def run_all(job_id):
    return _queue(_tasks().run_pipeline, job_id, "pipeline")


# ─────────────────────────────────────────────────
# Status
# ─────────────────────────────────────────────────

@app.route("/api/jobs/<job_id>")
def job_status(job_id):
    record = store.load_job(job_id)
    if record is None:
        return jsonify({"status": "error", "message": "no such job"}), 404
    return jsonify(record)


@app.route("/api/jobs")
def job_list():
    limit = request.args.get("limit", default=50, type=int)
    return jsonify({"jobs": store.list_jobs(limit=max(1, min(limit, 200)))})


@app.route("/api/jobs/<job_id>", methods=["DELETE"])
def job_delete(job_id):
    removed = store.delete_job(job_id)
    if not removed:
        return jsonify({"status": "error", "message": "no such job"}), 404
    return jsonify({"status": "deleted", "job_id": job_id})


# ─────────────────────────────────────────────────
# Audio
# ─────────────────────────────────────────────────

@app.route("/api/jobs/<job_id>/audio/<track>")
def job_audio(job_id, track):
    if track == "source":
        path = store.job_path(job_id, "source.wav")
        path = path if os.path.exists(path) else None
    else:
        path = store.stem_path(job_id, track)

    if path is None:
        return jsonify({
            "status": "error",
            "message": f"no rendered audio for track '{track}' yet",
        }), 404

    download = request.args.get("download") in ("1", "true")
    return send_file(path, mimetype="audio/wav", as_attachment=download,
                     download_name=f"{job_id}_{track}.wav")


@app.route("/api/jobs/<job_id>/stems")
def job_stems(job_id):
    record = store.load_job(job_id)
    if record is None:
        return jsonify({"status": "error", "message": "no such job"}), 404

    stems = {}
    for track in store.TRACKS:
        if store.stem_path(job_id, track):
            stems[track] = f"/api/jobs/{job_id}/audio/{track}?download=1"
    return jsonify({"job_id": job_id, "stems": stems})


# ─────────────────────────────────────────────────
# Track locking
# ─────────────────────────────────────────────────

@app.route("/api/jobs/<job_id>/lock/<track>", methods=["POST"])
def lock_track(job_id, track):
    return _set_lock(job_id, track, locked=True)


@app.route("/api/jobs/<job_id>/unlock/<track>", methods=["POST"])
def unlock_track(job_id, track):
    return _set_lock(job_id, track, locked=False)


def _set_lock(job_id, track, locked):
    record = store.load_job(job_id)
    if record is None:
        return jsonify({"status": "error", "message": "no such job"}), 404

    locked_tracks = list(record.get("locked_tracks") or [])
    if locked and track not in locked_tracks:
        locked_tracks.append(track)
    elif not locked and track in locked_tracks:
        locked_tracks.remove(track)

    store.update_job(job_id, locked_tracks=locked_tracks)
    return jsonify({"status": "success", "locked_tracks": locked_tracks})


# ─────────────────────────────────────────────────

@app.errorhandler(413)
def too_large(_err):
    return jsonify({
        "status": "error",
        "message": f"file exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)}MB limit",
    }), 413


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    debug = os.environ.get("FLASK_ENV") == "development"
    print(f"[songshapes] API on http://0.0.0.0:{port}  data={store.DATA_ROOT}")
    app.run(host="0.0.0.0", port=port, debug=debug)
