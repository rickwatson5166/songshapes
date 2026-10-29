#!/usr/bin/env python3
"""
SongShapes job store.

The original web UI kept all job state -- including raw numpy audio arrays --
in a module-level dict. That works for a single Flask process but is invisible
to a Celery worker, which runs in a separate process (and, under
docker-compose, a separate container).

This module moves job state to disk so Flask and Celery can share it:

    <data_root>/jobs/<job_id>/
        job.json              status record (stage, progress, errors, metadata)
        source.wav            normalized mono source audio
        performance.npz       Stage 1 input: extracted performance arrays
        understanding.json    Stage 1 output
        accompaniment.json    Stage 2 output
        stems/*.wav           Stage 3 output

Numpy types are not JSON-serializable, so everything written as JSON passes
through `to_jsonable()` first.
"""

import io
import json
import os
import shutil
import time
import uuid

import numpy as np
import soundfile as sf

# ─────────────────────────────────────────────────
# Layout
# ─────────────────────────────────────────────────

DATA_ROOT = os.environ.get("SONGSHAPES_DATA", "/app/data")
JOBS_ROOT = os.path.join(DATA_ROOT, "jobs")

STAGE_ORDER = ["uploaded", "analyzing", "analyzed",
               "generating", "generated",
               "synthesizing", "complete"]

TRACKS = ["drums", "bass", "pads", "mixed"]


def jobs_root():
    os.makedirs(JOBS_ROOT, exist_ok=True)
    return JOBS_ROOT


def job_dir(job_id, create=False):
    """Resolve a job directory, refusing anything that escapes JOBS_ROOT."""
    safe = os.path.basename(str(job_id))
    if not safe or safe in (".", ".."):
        raise ValueError(f"invalid job id: {job_id!r}")
    path = os.path.join(jobs_root(), safe)
    if create:
        os.makedirs(os.path.join(path, "stems"), exist_ok=True)
    return path


def job_path(job_id, *parts):
    return os.path.join(job_dir(job_id), *parts)


def new_job_id():
    return uuid.uuid4().hex


# ─────────────────────────────────────────────────
# JSON with numpy support
# ─────────────────────────────────────────────────

def to_jsonable(obj, _array_limit=100_000):
    """
    Recursively convert numpy types to plain Python so json can encode them.

    Large arrays (audio buffers) are replaced with a descriptor rather than
    inlined -- audio belongs in a WAV file, not in a status document.
    """
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        value = float(obj)
        # NaN/Inf are not valid JSON
        if value != value or value in (float("inf"), float("-inf")):
            return None
        return value
    if isinstance(obj, np.ndarray):
        if obj.size > _array_limit:
            return {"__array__": True, "shape": list(obj.shape),
                    "dtype": str(obj.dtype), "elided": True}
        return to_jsonable(obj.tolist(), _array_limit)
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v, _array_limit) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_jsonable(v, _array_limit) for v in obj]
    # Unknown object: describe it instead of crashing the job.
    return {"__repr__": repr(obj)[:200], "__type__": type(obj).__name__}


def write_json(path, payload):
    tmp = f"{path}.tmp"
    with open(tmp, "w") as fh:
        json.dump(to_jsonable(payload), fh, indent=2)
    os.replace(tmp, path)  # atomic: a reader never sees a half-written file


def read_json(path, default=None):
    if not os.path.exists(path):
        return default
    try:
        with open(path) as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return default


# ─────────────────────────────────────────────────
# Job records
# ─────────────────────────────────────────────────

def create_job(job_id=None, source_name=None):
    job_id = job_id or new_job_id()
    job_dir(job_id, create=True)
    record = {
        "job_id": job_id,
        "stage": "uploaded",
        "progress": 0,
        "error": None,
        "source_name": source_name,
        "created_at": time.time(),
        "updated_at": time.time(),
        "sr": None,
        "duration_seconds": None,
        "locked_tracks": [],
        "task_ids": {},
        "analysis": None,
        "accompaniment_summary": None,
        "stems": {},
    }
    write_json(job_path(job_id, "job.json"), record)
    return record


def load_job(job_id):
    return read_json(job_path(job_id, "job.json"))


def update_job(job_id, **fields):
    """Read-modify-write a job record. Unknown keys are allowed."""
    record = load_job(job_id)
    if record is None:
        raise KeyError(f"no such job: {job_id}")
    record.update(fields)
    record["updated_at"] = time.time()
    write_json(job_path(job_id, "job.json"), record)
    return record


def set_stage(job_id, stage, progress=None, error=None):
    fields = {"stage": stage}
    if progress is not None:
        fields["progress"] = progress
    if error is not None:
        fields["error"] = error
    return update_job(job_id, **fields)


def fail_job(job_id, message):
    return update_job(job_id, stage="failed", error=str(message)[:2000])


def list_jobs(limit=50):
    root = jobs_root()
    records = []
    for name in os.listdir(root):
        record = read_json(os.path.join(root, name, "job.json"))
        if record:
            records.append(record)
    records.sort(key=lambda r: r.get("created_at", 0), reverse=True)
    return records[:limit]


def delete_job(job_id):
    path = job_dir(job_id)
    if os.path.isdir(path):
        shutil.rmtree(path)
        return True
    return False


# ─────────────────────────────────────────────────
# Audio
# ─────────────────────────────────────────────────

def save_source_audio(job_id, upload_path):
    """
    Load an uploaded file, downmix to mono, and store it as the canonical
    source.wav for the job. Returns (sr, duration_seconds).
    """
    audio, sr = sf.read(upload_path, always_2d=False)
    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)
    audio = np.asarray(audio, dtype=np.float32)

    sf.write(job_path(job_id, "source.wav"), audio, sr, subtype="FLOAT")
    duration = float(len(audio) / sr) if sr else 0.0
    update_job(job_id, sr=int(sr), duration_seconds=duration)
    return int(sr), duration


def load_source_audio(job_id):
    audio, sr = sf.read(job_path(job_id, "source.wav"), always_2d=False)
    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)
    return np.asarray(audio, dtype=np.float32), int(sr)


def save_stem(job_id, name, audio, sr):
    """Write one synthesized track to stems/<name>.wav as 16-bit PCM."""
    audio = np.asarray(audio, dtype=np.float32)
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak > 1.0:  # guard against clipping on export
        audio = audio / peak
    path = job_path(job_id, "stems", f"{name}.wav")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sf.write(path, audio, sr, subtype="PCM_16")
    return path


def stem_path(job_id, name):
    safe = os.path.basename(str(name))
    path = job_path(job_id, "stems", f"{safe}.wav")
    return path if os.path.exists(path) else None


def audio_bytes(path):
    with open(path, "rb") as fh:
        return io.BytesIO(fh.read())


# ─────────────────────────────────────────────────
# Stage artifacts
# ─────────────────────────────────────────────────

def save_performance(job_id, performance):
    """
    Stage 1 input. The performance blueprint mixes arrays with scalars, so
    arrays go to .npz and everything else to JSON alongside it.
    """
    arrays, scalars = {}, {}
    _split_arrays(performance, arrays, scalars)
    np.savez_compressed(job_path(job_id, "performance.npz"), **arrays)
    write_json(job_path(job_id, "performance_meta.json"), scalars)


def load_performance(job_id):
    npz_path = job_path(job_id, "performance.npz")
    scalars = read_json(job_path(job_id, "performance_meta.json"), {}) or {}
    if not os.path.exists(npz_path):
        return scalars
    with np.load(npz_path, allow_pickle=False) as data:
        arrays = {key: data[key] for key in data.files}
    return _merge_arrays(scalars, arrays)


def _split_arrays(obj, arrays, scalars, prefix=""):
    """Walk a nested dict, routing ndarrays to `arrays` under a flat key."""
    if isinstance(obj, dict):
        out = {}
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, np.ndarray):
                arrays[path] = value
                out[key] = {"__ref__": path}
            elif isinstance(value, dict):
                nested = {}
                _split_arrays(value, arrays, nested, path)
                out[key] = nested
            else:
                out[key] = to_jsonable(value)
        scalars.update(out)
        return scalars
    scalars.update(to_jsonable(obj) if isinstance(obj, dict) else {})
    return scalars


def _merge_arrays(scalars, arrays):
    if isinstance(scalars, dict):
        if set(scalars.keys()) == {"__ref__"}:
            return arrays.get(scalars["__ref__"])
        return {k: _merge_arrays(v, arrays) for k, v in scalars.items()}
    return scalars


def save_understanding(job_id, understanding):
    write_json(job_path(job_id, "understanding.json"), understanding)


def load_understanding(job_id):
    return read_json(job_path(job_id, "understanding.json"))


def save_accompaniment(job_id, accompaniment):
    write_json(job_path(job_id, "accompaniment.json"), accompaniment)


def load_accompaniment(job_id):
    return read_json(job_path(job_id, "accompaniment.json"))
