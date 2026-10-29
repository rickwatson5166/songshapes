# SongShapes

A sophisticated platform for audio regeneration and accompaniment generation. Track-by-track workflow with three-stage processing: performance extraction, accompaniment generation, and audio synthesis.

## Quick Start

### Option A — async stack (Redis + Celery + Flask)

Audio work runs in a background worker, so a long track doesn't block the
request. This is what `docker-compose.yml` brings up:

```bash
docker compose up --build
```

Then visit http://localhost:5000.

To run the same stack without Docker:

```bash
pip3 install -r requirements.txt
redis-server --port 6379 --daemonize yes

export REDIS_URL=redis://localhost:6379/0
export SONGSHAPES_DATA=./data

celery -A celery_tasks worker --loglevel=info --concurrency=2 &
python3 app.py 5000
```

### Option B — single-process UI

The original synchronous server, no Redis required:

```bash
pip3 install -r requirements.txt
python3 mastercrafter_web_ui.py
```

## API

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | liveness, plus whether the broker is reachable |
| `POST` | `/api/upload` | store audio, create a job (`?run=1` queues all stages) |
| `POST` | `/api/jobs/<id>/analyze` | queue Stage 1 |
| `POST` | `/api/jobs/<id>/generate` | queue Stage 2 |
| `POST` | `/api/jobs/<id>/synthesize` | queue Stage 3 |
| `POST` | `/api/jobs/<id>/run` | queue all three as a chain |
| `GET` | `/api/jobs/<id>` | job status, analysis results, stem URLs |
| `GET` | `/api/jobs` | recent jobs |
| `GET` | `/api/jobs/<id>/audio/<track>` | stream `drums`/`bass`/`pads`/`mixed`/`source` |
| `GET` | `/api/jobs/<id>/stems` | download links for rendered stems |
| `POST` | `/api/jobs/<id>/lock/<track>` | lock / unlock a track |
| `DELETE` | `/api/jobs/<id>` | delete a job and its files |

Example:

```bash
curl -F "file=@take.wav" "http://localhost:5000/api/upload?run=1"
curl http://localhost:5000/api/jobs/<job_id>
```

## Job storage

Flask and the Celery worker are separate processes, so job state lives on
disk rather than in memory (`songshapes_store.py`). Each job gets a directory
under `$SONGSHAPES_DATA/jobs/<job_id>/`:

```
job.json              status, progress, analysis results
source.wav            normalized mono source audio
performance.npz       extracted performance arrays
understanding.json    Stage 1 output
accompaniment.json    Stage 2 output
stems/*.wav           drums, bass, pads, mixed
```

Under Docker both containers mount the same volume, so they share it.

## Features

- **Performance Extraction**: Analyzes uploaded audio to detect pitch, onsets, dynamics
- **Accompaniment Generation**: Generates bass, drums, and pad tracks with style matching
- **Audio Synthesis**: Synthesizes final stereo mix with stem export
- **Web Interface**: Intuitive track-by-track workflow with drag-and-drop upload

## Architecture

- Stage 1: Performance extraction and musical analysis
- Stage 2: Accompaniment generation (bass, drums, pads)
- Stage 3: Audio synthesis and stem export

