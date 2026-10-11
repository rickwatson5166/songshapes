# SongShapes: Theory-Trained Audio Regeneration System

**SongShapes** is an AI-powered audio regeneration platform for bedroom musicians, songwriters, and home studio producers. It combines theory-trained stem separation, character effects control, and accompaniment generation into one unified platform.

**Mission**: Democratize studio-quality sound engineering for musicians who can't afford $10k professional studio time.

---

## ✨ Features

### ✅ Phase 1: Audio Regeneration (Complete)

- **Smart Stem Separation**: Harmonic-Percussive Source Separation (HPSS) automatically splits audio into:
  - Vocals (mid-high frequency harmonic)
  - Percussion (drums, rhythm, transients)
  - Bass/Pads (low-frequency harmonic)
  - (Plus raw harmonic and percussive components for advanced use)

- **Per-Stem Character Control**: Adjust sonic character of each stem independently without changing your original performance:
  - **3-Band EQ**: Low (< 200Hz), Mid (1kHz), High (> 5kHz) with ±12dB range
  - **Dynamic Compression**: Attack/release envelopes for controlling dynamics
  - **Saturation**: Soft saturation for warmth and presence
  - **Reverb**: Schroeder reverberator for spatial character
  
- **Regeneration Workflow**: 
  1. Upload any audio (WAV, MP3, FLAC, OGG, M4A up to 100MB)
  2. Automatically separated into 6 stems
  3. Adjust character sliders for each stem in real-time
  4. Regenerate with new settings
  5. Download all stems + master mix

- **No Re-Recording Required**: Your timing, pitch, and dynamics are locked. Only sonic character changes.

### 🔄 Phase 2: Accompaniment Generation (In Progress)

- Melody/lead line → Auto-generate locked bass + drums
- Scenario presets for common bedroom problems:
  - "Bedroom Revival" - Adds warmth and presence
  - "Cassette Restoration" - Vintage tape character
  - "Zoom Call Fix" - Clarity and focus for remote recordings

### 🚀 Phase 3: Advanced Audio Engineering (Planned)

- Advanced denoising and room removal
- Spectral analysis and manipulation
- Acoustic modeling for realistic character changes

---

## 🚀 Quick Start

### System Requirements

- **Python**: 3.8 or higher
- **OS**: macOS (Intel/M1), Linux, Windows (WSL)
- **Hardware**: 
  - 2GB RAM minimum (4GB recommended)
  - 250MB disk space
  - No GPU required
- **Browser**: Modern browser (Chrome, Safari, Firefox)

### Installation

#### 1. Clone the Repository

```bash
git clone https://github.com/rickwatson5166/songshapes.git
cd songshapes
```

#### 2. Create Virtual Environment

```bash
python3 -m venv venv

# Activate (macOS/Linux)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate
```

#### 3. Install Dependencies

```bash
pip3 install -r requirements.txt
```

**Platform Notes:**
- **macOS Intel**: Pure scipy implementation (no librosa compilation issues)
- **macOS M1**: Works with native scipy build
- **Linux**: Standard installation
- **Windows**: Use WSL with Linux setup

#### 4. Run the Server

```bash
python3 app.py 5000
```

The server starts on `http://localhost:5000`

```
🎵 Running on: http://localhost:5000
📁 Temp folder: /tmp
⚙️  Max upload: 100MB
```

#### 5. Open in Browser

Navigate to `http://localhost:5000` and upload an audio file to get started.

---

## 📁 Project Structure

```
songshapes/
├── app.py                           # Flask REST API server (entry point)
├── audio_processor.py               # Core DSP engine
├── templates/
│   └── songshapes.html             # Web UI (served by Flask)
├── requirements.txt                # Python dependencies
├── test_character_workflow.py      # Automated workflow tests
├── .gitignore                       # Git ignore patterns
└── README.md                        # This file
```

### Core Components

| Component | File | Purpose |
|-----------|------|---------|
| **Flask Server** | `app.py` | REST API endpoints, session management, file handling |
| **Audio DSP** | `audio_processor.py` | HPSS stem separation, character effect processors |
| **Web UI** | `templates/songshapes.html` | User interface, interactive sliders, real-time feedback |
| **Tests** | `test_character_workflow.py` | End-to-end workflow validation |

---

## 🎯 How to Use

### Basic Workflow

1. **Upload Audio**
   - Drag and drop any audio file (WAV, MP3, FLAC, OGG, M4A)
   - Max file size: 100MB
   - Supported sample rates: 8kHz - 48kHz

2. **Separate into Stems**
   - Click "Separate into Stems"
   - System generates 6 stem files:
     - `vocals.wav` - Voice/melody
     - `percussion.wav` - Drums and rhythm
     - `bass_pads.wav` - Low-frequency content
     - `harmonic.wav` - All pitched content
     - `percussive.wav` - All transients
     - `master_mix.wav` - Combined result

3. **Adjust Character Effects**
   - For each stem (Vocals, Percussion, Bass/Pads):
     - **EQ Low**: ±12dB (bass boost/cut)
     - **EQ Mid**: ±12dB (presence/dip)
     - **EQ High**: ±12dB (brightness/dull)
     - **Compression**: 0-1 (dynamic control)
     - **Saturation**: 0-1 (warmth/distortion)
     - **Reverb**: 0-0.5 (spaciousness)

4. **Regenerate Stems**
   - Click "Regenerate with Settings"
   - New stems are generated with character effects applied
   - Your original timing and pitch are preserved

5. **Download Results**
   - Download individual stems (individual instruments)
   - Or download master mix (all stems combined)
   - All files in 44.1kHz WAV format

### Advanced: API Access

For programmatic access:

#### Upload Audio

```bash
curl -X POST -F "file=@song.wav" http://localhost:5000/api/upload
```

Response:
```json
{
  "status": "success",
  "session_id": "4bcc66cf",
  "duration": 180.5,
  "sample_rate": 44100
}
```

#### Separate Stems

```bash
curl -X POST http://localhost:5000/api/separate \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "4bcc66cf",
    "character_config": {
      "vocals": {"eq_low": 0, "eq_mid": 0, "eq_high": 0, "compression": 0, "saturation": 0, "reverb": 0},
      "percussion": {"eq_low": 0, "eq_mid": 0, "eq_high": 0, "compression": 0, "saturation": 0, "reverb": 0},
      "bass_pads": {"eq_low": 0, "eq_mid": 0, "eq_high": 0, "compression": 0, "saturation": 0, "reverb": 0}
    }
  }'
```

#### Regenerate with Character

```bash
curl -X POST http://localhost:5000/api/regenerate \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "4bcc66cf",
    "character_config": {
      "vocals": {"eq_low": 2, "eq_mid": 1, "eq_high": 3, "compression": 0.5, "saturation": 0.3, "reverb": 0.2},
      "percussion": {"eq_low": -1, "eq_mid": 0, "eq_high": 2, "compression": 0.7, "saturation": 0.1, "reverb": 0.1},
      "bass_pads": {"eq_low": 2, "eq_mid": -1, "eq_high": 0, "compression": 0.3, "saturation": 0.2, "reverb": 0.3}
    }
  }'
```

#### Download Stem

```bash
curl -O http://localhost:5000/api/download/vocals/4bcc66cf
```

#### Check Health

```bash
curl http://localhost:5000/api/health
```

---

## 🔧 API Reference

### `POST /api/upload`
**Upload and load audio file**

**Request**: Multipart form with `file` field
**Response**:
```json
{
  "status": "success",
  "session_id": "uuid",
  "duration": 180.5,
  "sample_rate": 44100,
  "message": "Audio uploaded successfully"
}
```

### `POST /api/separate`
**Separate audio into stems**

**Request**:
```json
{
  "session_id": "uuid",
  "character_config": { "vocals": {...}, "percussion": {...}, "bass_pads": {...} }
}
```

**Response**:
```json
{
  "status": "success",
  "stems": {
    "vocals": "/path/to/vocals.wav",
    "percussion": "/path/to/percussion.wav",
    "bass_pads": "/path/to/bass_pads.wav",
    "harmonic": "/path/to/harmonic.wav",
    "percussive": "/path/to/percussive.wav",
    "master": "/path/to/master_mix.wav"
  },
  "sr": 44100,
  "duration": 180.5,
  "message": "Successfully separated into 5 stems"
}
```

### `POST /api/regenerate`
**Regenerate stems with character effects**

**Request**:
```json
{
  "session_id": "uuid",
  "character_config": {
    "vocals": {
      "eq_low": -12 to 12,
      "eq_mid": -12 to 12,
      "eq_high": -12 to 12,
      "compression": 0 to 1,
      "saturation": 0 to 1,
      "reverb": 0 to 0.5
    },
    "percussion": {...},
    "bass_pads": {...}
  }
}
```

**Response**: Same as `/api/separate`

### `GET /api/state?session_id=uuid`
**Get current session state**

**Response**:
```json
{
  "status": "loaded|separated|regenerated",
  "message": "Current state message",
  "stems": { "stem_name": "/path" },
  "audio_loaded": true,
  "stems_ready": true
}
```

### `GET /api/download/<stem_name>/<session_id>`
**Download processed stem file**

**Response**: WAV audio file (binary)

### `GET /api/health`
**Health check endpoint**

**Response**:
```json
{
  "status": "ok",
  "service": "SongShapes",
  "version": "0.1.0-alpha",
  "active_sessions": 5
}
```

---

## 🧪 Testing

### Run Full Workflow Test

```bash
python3 test_character_workflow.py
```

This test:
1. Creates synthetic test audio (3 seconds)
2. Uploads to the Flask server
3. Separates into stems
4. Regenerates with character effects
5. Verifies all output files

Expected output:
```
============================================================
SongShapes Character Control Workflow Test
============================================================
✓ Created test audio: /tmp/test_audio.wav (3s)
[1/4] Uploading audio...
✓ Upload successful
[2/4] Separating into stems...
✓ Separation successful
[3/4] Regenerating with character effects...
✓ Regeneration successful
[4/4] Checking final state...
✓ State retrieved
============================================================
✓ All tests passed! Character control workflow is working.
============================================================
```

---

## 🎵 Audio Engineering Concepts

### HPSS (Harmonic-Percussive Source Separation)

SongShapes uses **Harmonic-Percussive Source Separation** to split audio:

1. **STFT**: Compute Short-Time Fourier Transform
2. **Median Filtering**: 
   - Harmonic mask: Vertical median (stable frequencies over time)
   - Percussive mask: Horizontal median (brief transients)
3. **Wiener Filtering**: Soft mask for smooth separation
4. **Secondary Split**: Harmonic → Vocals (> 400Hz) + Bass/Pads (< 400Hz)

Result: 3 primary stems + 2 raw components + 1 master mix

### Character Processing

Each stem goes through 4 effect stages:

1. **3-Band EQ**: Shelving filters for tonal shape
2. **Dynamic Compression**: Envelope detection with attack/release
3. **Saturation**: Soft tanh clipping for warmth
4. **Reverb**: Schroeder reverberator with comb filters

All effects preserve timing and pitch—only sonic character changes.

---

## 📊 Performance Characteristics

### Timing & Throughput

| Operation | Duration | Notes |
|-----------|----------|-------|
| Upload (50MB file) | 2-5s | Depends on disk speed |
| Separate into stems | 5-10s | Per minute of audio |
| Regenerate with FX | 5-10s | Per minute of audio |
| Download stem (50MB) | 2-5s | Depends on disk speed |

### Memory Usage

- **Loaded audio**: ~1GB per hour
- **STFT computation**: ~500MB per minute
- **Processing**: Minimal additional overhead
- **Total typical**: <2GB for 3-5 minute songs

### Sample Rate Support

- Input: 8kHz - 48kHz (auto-resampled to 44.1kHz)
- Output: 44.1kHz (locked for compatibility)
- Bit depth: 32-bit float (internal), 16-bit WAV (output)

---

## 🐛 Troubleshooting

### Issue: "File type not allowed"

**Cause**: Uploaded file has unsupported extension
**Solution**: Use WAV, MP3, FLAC, OGG, or M4A files

### Issue: "File too large. Maximum 100MB."

**Cause**: Audio file exceeds 100MB limit
**Solution**: Split file, compress, or downsample to lower bit depth

### Issue: Port 5000 already in use

**Cause**: Another process is using port 5000
**Solution**: 
```bash
python3 app.py 5001  # Use different port
```

Or kill the existing process:
```bash
lsof -ti :5000 | xargs kill -9
```

### Issue: "No module named 'soundfile'" or other import errors

**Cause**: Dependencies not installed
**Solution**: Reinstall from requirements.txt
```bash
pip3 install --upgrade -r requirements.txt
```

### Issue: Audio processing is slow

**Cause**: Normalizing, resampling, or large file
**Solution**: 
- Convert to 44.1kHz WAV beforehand
- Reduce file size
- Close other applications to free RAM

### Issue: macOS Intel: Compilation errors during install

**Cause**: System dependencies missing
**Solution**: 
- Already avoided by not using librosa
- If issues persist with scipy, use Homebrew:
  ```bash
  brew install openblas lapack
  pip3 install numpy scipy --no-binary :all:
  ```

---

## 🤝 Contributing

This is Rick Watson's personal research project exploring human-CI collaboration in audio engineering.

**Philosophy**: Option C - both human and AI keep asking together, neither has hierarchy.

**How to help**:
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Make your changes and test with `python3 test_character_workflow.py`
4. Commit with a clear message
5. Push and create a Pull Request

---

## 📜 License

[MIT License](LICENSE) - Use freely for personal and commercial projects.

---

## 🎓 Learning Resources

### Audio Engineering Theory

- **HPSS Techniques**: Fitzgerald, D. (2010). Harmonic/Percussive Source Separation using Median Filtering
- **Audio Compression**: Understanding dynamic range compression and attack/release envelopes
- **Digital Audio**: Theory of sampling, quantization, and spectral analysis

### SongShapes Specific

- **Code walkthrough**: See `audio_processor.py` for DSP implementation
- **API integration**: See `test_character_workflow.py` for usage examples
- **UI customization**: See `templates/songshapes.html` for frontend

---

## 📧 Contact & Support

- **GitHub Issues**: Report bugs and feature requests
- **Author**: Rick Watson
- **Email**: rickwatson5166@gmail.com

---

## 🙏 Acknowledgments

Built on:
- **SciPy**: Scientific Python library for signal processing
- **NumPy**: Numerical computing
- **Flask**: Web framework
- **SoundFile**: Audio I/O

Thank you to the open-source community for enabling projects like this.

---

**Last Updated**: October 11, 2026
**Version**: 0.1.0-alpha
**Status**: Active Development - Character control phase complete, accompaniment generation in progress
