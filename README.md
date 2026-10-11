# SongShapes: Theory-Trained Audio Regeneration System

**SongShapes** is an AI-powered audio regeneration platform designed for bedroom musicians, songwriters, and home studio producers. It separates your audio into stems, regenerates each track's sonic character while preserving your original performance (timing, pitch, dynamics), and lets you optionally generate accompaniment from a melody or lead.

**Mission**: Democratize studio-quality sound for musicians who can't afford $10k professional studio time.

---

## ✨ What SongShapes Does

### Phase 1.5: Audio Regeneration + Accompaniment (Current Development)

- **Upload single audio** → Auto-separate into stems (Vocal, Drums, Bass, Other) → Regenerate
- **Upload pre-separated stems** (.zip with 4-24 tracks) → Character control panel → Regenerate with locked performance
- **Accompaniment generation**: Songwriter plays melody/guitar → AI generates bass + drums locked to timing/pitch
- **Scenario presets**: "Bedroom Revival," "Cassette Restoration," "Zoom Call Fix" for bedroom musician problems
- **Constraint-locked output**: Your timing, pitch, and dynamics stay intact. Only the sonic character changes.

### Phase 2: Advanced Features (Planned)

- Room removal & denoising
- Advanced sound synthesis
- Acoustic modeling
- Pro-quality audio effects

---

## 🚀 Quick Start

### Requirements

- Python 3.8+
- macOS Intel / Linux / Windows with WSL
- ~250MB disk space

### Installation (macOS Intel / M1)

```bash
# Clone the repository
git clone https://github.com/rickwatson5166/songshapes.git
cd songshapes

# Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip3 install -r requirements.txt
```

**Note on macOS Intel**: If you encounter issues with librosa/llvmlite installation, the Flask server runs without it. Audio processing features will be integrated in Phase 2.

### Run the Server

```bash
python3 mastercrafter_web_ui_working.py
```

Open your browser to **http://localhost:5000**

You should see the SongShapes interface with:
- Upload panel (drag-and-drop)
- Workflow stages (Upload → Analyze → Drums → Bass → Pads → Export)
- Processing status

---

## 📁 Project Structure

```
songshapes/
├── mastercrafter_web_ui_working.py    # Working Flask server (entry point)
├── mastercrafter_restoration_ui.html  # Frontend interface (served by Flask)
├── templates/
│   └── index.html                     # SongShapes UI (web interface)
├── mastercrafter_*.py                 # Audio processing modules (integrated next)
├── requirements.txt                   # Python dependencies
└── README.md                          # This file
```

### Core Files

| File | Purpose |
|------|---------|
| `mastercrafter_web_ui_working.py` | Flask server—runs UI and API endpoints |
| `templates/index.html` | Web frontend—drag-drop upload, workflow display |
| `mastercrafter_audio_restoration.py` | Audio loading & format handling (planned integration) |
| `mastercrafter_performance_extractor.py` | Extract timing/pitch from audio (planned integration) |
| `mastercrafter_drum_generator.py` | Drum synthesis (planned integration) |
| `mastercrafter_bass_generator.py` | Bass synthesis (planned integration) |
| `mastercrafter_pad_generator.py` | Harmonic pad generation (planned integration) |

---

## 🎯 Current State

**Status**: MVP Phase 1.5 in active development

✅ **Working**
- Flask server running on localhost:5000
- Web UI frontend with professional styling
- Audio upload interface (ready for file handling)
- Project structure in place
- Processing pipeline framework

🔄 **In Progress**
- Audio processing backend integration
- Stem separation (auto or from .zip)
- Accompaniment generation
- Character control per stem

📋 **Planned (Phase 2)**
- Room removal & denoising
- Advanced acoustic modeling
- CVSS attestation (Constraint-Verified Stem Standard)
- Character preset library

---

## 🛠️ API Endpoints

The Flask server provides these endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Serve main UI |
| `/api/upload` | POST | Handle audio file upload |
| `/api/state` | GET | Get processing state for session |

**Example**:
```bash
# Check current processing state
curl http://localhost:5000/api/state?session_id=default
```

---

## 🎵 How to Use

1. **Open UI**: Navigate to http://localhost:5000
2. **Upload Audio**:
   - Drag-drop a single audio file, OR
   - Upload a .zip containing pre-separated stems
3. **Analyze**: System detects audio format and initializes processing
4. **Regenerate** (when audio processing is integrated):
   - Adjust character sliders per stem
   - Lock tracks you want unchanged
   - Generate accompaniment (optional)
5. **Export**: Download regenerated stems + master mix

---

## 🔧 Troubleshooting

### `ModuleNotFoundError: No module named 'soundfile'`

```bash
pip3 install soundfile
```

### Server won't start on port 5000

```bash
# Check if port is in use
lsof -i :5000

# Kill process on that port (macOS/Linux)
kill -9 <PID>

# Or use a different port
python3 mastercrafter_web_ui_working.py --port 5001
```

### Browser shows blank page

- Check browser console (F12) for errors
- Verify Flask server is running: `curl http://localhost:5000`
- Try clearing browser cache

### Audio file won't upload

- Supported formats: WAV, MP3, FLAC (16-24 bit, 44.1-48 kHz)
- Max file size: 60MB
- Check file is not corrupted: `file <audio.wav>`

---

## 📚 Documentation

For deeper understanding of the theory and design:

- **[Mastercrafter Project](https://github.com/rickwatson5166)**: Full IP portfolio and patent library
- **[Audio Engineering Curriculum](./docs/audio-engineering/)**: Theory foundation (signal processing, psychoacoustics, spectral analysis)
- **[SongShapes Theory](./docs/songshapes-theory.md)**: Constraint-preserving regeneration, user-adaptive learning

---

## 🎯 Project Philosophy

SongShapes follows three core principles:

1. **Performance is Sacred**: Your timing, pitch, and dynamics never change. Only sonic character transforms.
2. **No AI Literacy Required**: Interface uses production/mastering workflows musicians already understand.
3. **Bedroom Musician Focus**: Solves real problems (bad room acoustics, degraded tape, need for accompaniment) without overthinking AI.

---

## 🚦 Development Roadmap

### Week 1-2 (Current)
- ✅ Web UI running locally
- 🔄 Audio file handling
- 🔄 Stem separation (auto or from .zip)
- 🔄 Single-track regeneration skeleton

### Week 3-4 (Next)
- Multi-track character control panel
- Accompaniment generation (melody → drums + bass)
- Scenario presets ("Bedroom Revival," "Cassette Restoration")
- First test with real bedroom musicians

### Week 5-6
- Room removal & denoising
- Advanced synthesis backend
- CVSS attestation (constraint verification)
- Performance optimization

---

## 🤝 Contributing

This is an active research and development project. If you'd like to contribute:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit changes: `git commit -m 'Add your feature'`
4. Push to branch: `git push origin feature/your-feature`
5. Open a Pull Request

---

## 📄 License

SongShapes is part of the Mastercrafter patent portfolio. See LICENSE.md for details.

---

## 📧 Contact

**Creator**: Rick Watson  
**GitHub**: [@rickwatson5166](https://github.com/rickwatson5166)  
**Project Lead**: Mastercrafter (privacy-tech + audio-tech IP portfolio)

---

## 🙏 Acknowledgments

- Theory foundation: Music theory, signal processing, psychoacoustics research
- Development platform: Claude AI
- Tested on: macOS Intel (Mac mini 2018)

---

## 🎬 Next Steps

1. **Run the server** locally and explore the UI
2. **Share feedback** on UX/workflow
3. **Submit audio files** for testing (once processing is integrated)
4. **Join the conversation** about bedroom musician pain points

**The goal**: By month 2, SongShapes should fix real recordings and generate accompaniment. By month 3, it should sound as good as a professional studio.

Let's build this together.

---

**Last updated**: October 11, 2026  
**Status**: Active Development (Phase 1.5 MVP)
