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

## Approved reference library

Style matching draws only on recordings whose use has been explicitly
approved, with the basis for that approval recorded alongside.

Two properties are enforced in code rather than left to intent, and both are
covered by `test_reference_library.py`:

**Consent is a gate.** An ingested recording is unapproved and contributes
nothing until someone approves it *and* states a rights basis. Approval
without a basis, or without a named approver, is refused. Forgetting to
approve fails closed.

**The library stores style, not songs.** A profile holds aggregate
distributions — scale-degree emphasis, melodic interval spread, inter-onset
evenness, dynamics range, chord-quality vocabulary, chord root-motion
weights. It does not hold the pitch contour, the onset times, the literal
chord progression, or the audio. `validate_profile()` rejects those on every
write, so a change that starts storing sequences fails a test instead of
quietly turning a style model into a copy of the recording.

Audio is discarded after extraction unless `--retain-audio` is passed, so
masters need not live in the repo.

```bash
# Your own songs and recordings, cleared as you go
python3 reference_ingest.py ./my_songs \
    --rights own-composition-own-recording \
    --writer "Your Name" --performer "Your Name" \
    --approve-as "Your Name"

# Old band recordings: ingest now, decide later
python3 reference_ingest.py ./band_tapes \
    --band "Band Name" --rights band-recording-shared-rights \
    --notes "check with the other players first"

python3 reference_ingest.py --list            # approval state of every entry
python3 reference_ingest.py --approve <id> --approve-as "Your Name"
python3 reference_ingest.py --revoke <id>     # withdraw; entry kept for audit
python3 reference_ingest.py --style-target    # what generators would match
```

Recognized rights bases: `own-composition-own-recording`,
`own-composition-other-performers`, `band-recording-shared-rights`,
`licensed`, `public-domain`.

`style_target()` names the references each blend came from, so a generated
part's lineage can be traced back to the recordings that informed it.

Layout, under `$SONGSHAPES_DATA/references/<ref_id>/`:

```
meta.json      provenance, rights basis, approval, source hash
profile.json   non-reconstructive style features
source.wav     only when --retain-audio was passed
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

