#!/usr/bin/env python3
"""
SongShapes background workers.

Dockerfile.celery launches this as:
    celery -A celery_tasks worker --loglevel=info --concurrency=2

The three pipeline stages are long-running CPU work (pitch tracking, pattern
generation, synthesis), so they run here instead of blocking a Flask request.
Each task reads its inputs from the job directory and writes its outputs back
there, so nothing large travels through the Redis broker.
"""

import os
import sys
import traceback

# A prefork worker's child processes do not reliably inherit the launch
# directory on sys.path, so the mastercrafter_* modules sitting next to this
# file become unimportable inside a task. Put our own directory on the path
# explicitly rather than depending on how the worker was started.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from celery import Celery, chain

import songshapes_store as store

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

app = Celery("songshapes", broker=REDIS_URL, backend=REDIS_URL)
app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    # Audio synthesis on a long track can run for minutes; give it room but
    # don't let a wedged task hold a worker slot forever.
    task_soft_time_limit=1800,
    task_time_limit=2100,
    worker_max_tasks_per_child=20,  # release memory from numpy/librosa churn
)


class StageError(RuntimeError):
    """A pipeline stage failed in a way worth reporting to the user."""


def _ensure_path():
    """
    Re-assert our directory on sys.path from inside a task.

    A prefork child does not necessarily execute a task with the sys.path its
    parent had at import time, so the mastercrafter_* modules can be missing
    even though this module imported fine. Cheap to call; idempotent.
    """
    if _HERE not in sys.path:
        sys.path.insert(0, _HERE)


def _stage_guard(job_id, stage_name):
    """
    Context manager that records failure on the job record rather than letting
    the traceback vanish into worker logs.
    """

    class _Guard:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            if exc is None:
                return False
            detail = f"{stage_name} failed: {exc}"
            store.fail_job(job_id, detail)
            # Log the full traceback for the operator, keep the job record short.
            print(f"[songshapes] {detail}\n{''.join(traceback.format_tb(tb))}",
                  flush=True)
            return False  # let Celery mark the task failed too

    return _Guard()


# ─────────────────────────────────────────────────
# Stage 1 — performance extraction + understanding
# ─────────────────────────────────────────────────

@app.task(bind=True, name="songshapes.analyze")
def analyze(self, job_id):
    """Extract the performance, then derive key/tempo/chords/style from it."""
    # Imports stay inside the guard: an ImportError here must be recorded on
    # the job, or the UI polls a job that is stuck at "uploaded" with no error.
    with _stage_guard(job_id, "analysis"):
        _ensure_path()
        from mastercrafter_performance_extractor import PerformanceExtractor
        from mastercrafter_stage1_orchestrator import Stage1PerformanceUnderstanding

        store.set_stage(job_id, "analyzing", progress=5)
        audio, sr = store.load_source_audio(job_id)

        extractor = PerformanceExtractor(sr=sr)
        performance = extractor.extract_full_performance(audio, fmin=100, fmax=600)
        store.save_performance(job_id, performance)
        store.set_stage(job_id, "analyzing", progress=55)

        orchestrator = Stage1PerformanceUnderstanding(sr=sr, hop_length=512)
        understanding = orchestrator.understand_performance(performance, verbosity=0)
        store.save_understanding(job_id, understanding)

        store.update_job(
            job_id,
            stage="analyzed",
            progress=100,
            analysis=_analysis_summary(understanding),
        )
    return job_id


def _analysis_summary(understanding):
    """Pull the handful of fields the UI displays, defensively."""

    def dig(*keys, default=None):
        node = understanding
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    expression = dig("style", "expression")
    chords = dig("chords", "chord_progression", default=[]) or []

    return store.to_jsonable({
        "key": dig("key", "key"),
        "tempo_bpm": dig("tempo", "tempo_bpm"),
        "time_signature": dig("tempo", "time_signature"),
        "chords": chords[:8],
        "articulation": dig("style", "articulation"),
        "timing": dig("style", "timing"),
        "expression": (f"{expression:.0%}"
                       if isinstance(expression, (int, float)) else None),
    })


# ─────────────────────────────────────────────────
# Stage 2 — accompaniment generation
# ─────────────────────────────────────────────────

@app.task(bind=True, name="songshapes.generate")
def generate(self, job_id):
    """Generate bass, drum and pad parts from the Stage 1 understanding."""
    with _stage_guard(job_id, "generation"):
        _ensure_path()
        from mastercrafter_stage2_orchestrator import Stage2AccompanimentGeneration

        store.set_stage(job_id, "generating", progress=10)

        understanding = store.load_understanding(job_id)
        if not understanding:
            raise StageError("no analysis on file for this job -- run analyze first")

        orchestrator = Stage2AccompanimentGeneration()
        accompaniment = orchestrator.generate_accompaniment(understanding, verbosity=0)
        store.save_accompaniment(job_id, accompaniment)

        store.update_job(
            job_id,
            stage="generated",
            progress=100,
            accompaniment_summary=_accompaniment_summary(accompaniment),
        )
    return job_id


def _accompaniment_summary(accompaniment):
    def count(*keys):
        node = accompaniment
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return 0
            node = node[key]
        return len(node) if hasattr(node, "__len__") else 0

    return {
        "bass_notes": count("bass", "notes"),
        "drum_events": count("drums", "combined", "notes"),
        "pad_voices": count("pads", "combined", "notes"),
    }


# ─────────────────────────────────────────────────
# Stage 3 — synthesis
# ─────────────────────────────────────────────────

@app.task(bind=True, name="songshapes.synthesize")
def synthesize(self, job_id):
    """Render the accompaniment to audio and write each stem to disk."""
    with _stage_guard(job_id, "synthesis"):
        _ensure_path()
        from mastercrafter_stage3_orchestrator import Stage3AudioSynthesis

        store.set_stage(job_id, "synthesizing", progress=10)

        record = store.load_job(job_id) or {}
        sr = record.get("sr") or 44100
        accompaniment = store.load_accompaniment(job_id)
        if not accompaniment:
            raise StageError("no accompaniment on file -- run generate first")

        synthesizer = Stage3AudioSynthesis(sr=sr)
        result = synthesizer.synthesize_accompaniment(accompaniment, verbosity=0)
        store.set_stage(job_id, "synthesizing", progress=70)

        # Write each track out as its own WAV rather than keeping audio in RAM.
        written = {}
        for track in store.TRACKS:
            audio = (result.get(track) or {}).get("audio")
            if audio is None:
                continue
            store.save_stem(job_id, track, audio, sr)
            written[track] = f"/api/jobs/{job_id}/audio/{track}"

        if not written:
            raise StageError("synthesis produced no audio tracks")

        store.update_job(
            job_id,
            stage="complete",
            progress=100,
            stems=written,
            synthesis={
                "duration": result.get("duration_seconds"),
                "key": result.get("key"),
                "tracks": sorted(written.keys()),
            },
        )
    return job_id


# ─────────────────────────────────────────────────
# Convenience: run all three back to back
# ─────────────────────────────────────────────────

@app.task(name="songshapes.run_pipeline")
def run_pipeline(job_id):
    """Queue analyze -> generate -> synthesize as one chain."""
    workflow = chain(analyze.si(job_id), generate.si(job_id), synthesize.si(job_id))
    return workflow.apply_async().id
