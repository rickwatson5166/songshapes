# SongShapes

A sophisticated platform for audio regeneration and accompaniment generation. Track-by-track workflow with three-stage processing: performance extraction, accompaniment generation, and audio synthesis.

## Quick Start

### Install Dependencies
```bash
pip3 install numpy scipy librosa soundfile flask werkzeug
```

### Run the Web UI
```bash
python3 mastercrafter_web_ui.py
```

Then visit http://localhost:5000 in your browser.

## Features

- **Performance Extraction**: Analyzes uploaded audio to detect pitch, onsets, dynamics
- **Accompaniment Generation**: Generates bass, drums, and pad tracks with style matching
- **Audio Synthesis**: Synthesizes final stereo mix with stem export
- **Web Interface**: Intuitive track-by-track workflow with drag-and-drop upload

## Architecture

- Stage 1: Performance extraction and musical analysis
- Stage 2: Accompaniment generation (bass, drums, pads)
- Stage 3: Audio synthesis and stem export

