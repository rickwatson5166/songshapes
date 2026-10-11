# Mastercrafter Stage 1: Quick Start Guide

## What You Have

A complete **audio restoration engine** that cleans bad recordings (hum, hiss, clicks) while adding tape warmth and analog character.

### The Three Components:
1. **DSP Engine** (`mastercrafter_audio_restoration.py`) — Python, CPU-efficient
2. **Web UI** (`mastercrafter_restoration_ui.html`) — Interactive browser interface
3. **Flask Server** (`mastercrafter_server.py`) — Handles file I/O and processing

---

## Installation

### Requirements
```bash
pip install flask numpy scipy soundfile
```

Optional (for audio analysis):
```bash
pip install librosa matplotlib
```

---

## Usage Option 1: Web Interface (Easiest)

### Start the server:
```bash
cd /home/claude
python3 mastercrafter_server.py
```

### Open browser:
```
http://localhost:5000
```

### Workflow:
1. **Upload** an audio file (WAV, MP3, FLAC, etc.)
2. **Select preset** or adjust controls:
   - Bias (0.3 = warm, 0.8 = bright)
   - HF Driver (0.2 = warm, 0.7 = bright)
   - EQ: Low shelf, Mid gain, High shelf
3. **Toggle noise filtering** (recommended ON)
4. **Click "Process Audio"**
5. **Download** restored file

---

## Usage Option 2: Python Script

### Simple batch processing:
```python
from mastercrafter_audio_restoration import SoundRestorationEngine
import soundfile as sf

# Load your recording
audio, sr = sf.read("my_demo.wav")

# Process with "warm_tape" preset
engine = SoundRestorationEngine(sr=sr, tape_preset="warm_tape")
restored = engine.process(audio, apply_noise_gate=True)

# Save result
sf.write("my_demo_restored.wav", restored, sr)
```

### Advanced: Custom parameters
```python
from mastercrafter_audio_restoration import SoundRestorationEngine
import soundfile as sf

audio, sr = sf.read("my_demo.wav")

# Start with preset
engine = SoundRestorationEngine(sr=sr, tape_preset="warm_tape")

# Override specific controls
engine.hysteresis.bias = 0.5          # Adjust saturation
engine.hysteresis.hf_driver = 0.35    # Adjust response speed
engine.neve_preamp.high_shelf_gain = 6.0  # Add more sheen

# Process
restored = engine.process(audio, apply_noise_gate=True)
sf.write("my_demo_restored.wav", restored, sr)
```

---

## Tape Presets Explained

### Warm Tape (Default)
- **Bias:** 0.3, **HF Driver:** 0.2
- **Use:** Vocals, acoustic guitar, soft vocals
- **Character:** Smooth, musical saturation
- **Reference:** Studer A800 on 456 tape @ 7.5 ips

### Bright Tape
- **Bias:** 0.8, **HF Driver:** 0.7
- **Use:** Drums, electric instruments, punchy sources
- **Character:** Aggressive, distortion-rich
- **Reference:** Studer A800 on 900 formulation @ 30 ips

### Modern Tape
- **Bias:** 0.5, **HF Driver:** 0.6
- **Use:** When you want tape warmth without being vintage
- **Character:** Clean but colorful
- **Reference:** Modern 24-bit tape formulation

### Vintage Tape
- **Bias:** 0.4, **HF Driver:** 0.25
- **Use:** Archival recordings, vintage aesthetic
- **Character:** Deep, warm saturation
- **Reference:** Classic 1970s tape sound

### Neve Sheen
- **Bias:** 0.6, **HF Driver:** 0.55
- **Use:** When you want aggressive presence peak
- **Character:** Extreme 12kHz shelf (+12dB)
- **Reference:** Neve 1073 preamp tone shaper

---

## Control Guide

### Bias (Saturation Softness)
```
0.0 ─────────────── 0.5 ─────────────── 1.0
Soft (warm)         Balanced          Aggressive
```
- **Lower bias = soft saturation** (sounds like pushed/overdriven tape)
- **Higher bias = aggressive saturation** (more harmonic distortion)

### HF Driver (High Frequency Response Speed)
```
0.0 ─────────────── 0.5 ─────────────── 1.0
Slow (warm)         Balanced          Fast (bright)
```
- **Lower HF Driver = tape "lags" behind signal** (warm, smooth)
- **Higher HF Driver = tape responds quickly** (aggressive, distorted)

### EQ Controls (Neve 1073-style)
- **Low Shelf (100 Hz):** Remove tape head bump (-2dB) or add warmth (+2dB)
- **Mid Gain (1 kHz):** Scoop mud (-2dB) or boost presence (+2dB)
- **High Shelf (12 kHz):** Neve's signature presence peak (+3 to +12dB)

### Noise Gate
- ✅ **ON:** Removes 60Hz hum, hiss, clicks (recommended for bad recordings)
- ❌ **OFF:** Pure tape simulation without noise filtering

---

## What It Does (Technical Overview)

### 1. Smart Noise Filtering
- Removes 60Hz power line hum + harmonics (120, 180, 240, 300 Hz)
- Gates high-frequency hiss (8kHz+) without affecting music
- Softens clicks and pops while preserving transients

### 2. Hysteresis Tape Saturation
- Models real tape using magnetic memory (not static waveshaping)
- Same input produces different output based on magnetization history
- Asymmetric clipping (positive and negative swings compress differently)

### 3. Neve 1073-Style Processing
- 10 clipping points throughout the signal chain
- EQ settings alter where/how the saturation stages clip
- Creates harmonic complexity that single-stage compression can't match

---

## Results: What to Expect

### Input vs Output
| Audio Type | Before | After |
|-----------|--------|-------|
| Bedroom vocal demo | Thin, brittle, hissy | Warm, full, clear |
| Analog archive tape | Hum + hiss | Clean, character preserved |
| Field recording | Ambient hum + clicks | Usable, musical |

### Example: "My demo has bad hum and sounds thin"
1. Upload file
2. Select **Warm Tape**
3. Increase **High Shelf** to +6dB (add presence)
4. Leave **Noise Gate ON**
5. Process

Result: Hum removed, thin high-end filled in, adds analog warmth.

---

## Troubleshooting

### "Output sounds too quiet"
- Check **Bias** (lower = softer output)
- Try **Modern Tape** preset (medium bias)
- Increase **Mid Gain** for presence

### "Output is distorted/too aggressive"
- Lower **Bias** to 0.3–0.4
- Lower **HF Driver** to 0.2–0.3
- Try **Warm Tape** or **Vintage Tape** preset

### "Still sounds too similar to input"
- Increase **High Shelf** gain (+6 to +12dB for "sheen")
- Check **Noise Gate** is enabled
- Try **Neve Sheen** preset

### "Processing is slow"
- Check file size (under 500MB recommended)
- For very large files, split into tracks and process separately

---

## File Locations

All code is in `/home/claude/`:
```
mastercrafter_audio_restoration.py  ← Core engine
mastercrafter_restoration_ui.html   ← Web interface
mastercrafter_server.py             ← Flask server
QUICKSTART.md                        ← This file
```

---

## Next: What's Coming

- **Real-time processing** (WebAudio worklet for instant feedback)
- **A/B comparison tool** (hear before/after side-by-side)
- **Stem separation** (process vocals/drums/other separately)
- **Batch processing** (load folder, process many files)
- **VST3/AU plugin** (use in your DAW)
- **Reference library** (compare to professional recordings)

---

## Philosophy

This engine is built around **engineering**, not just cosmetics:

✅ Hysteresis saturation (magnetic memory), not tanh  
✅ Interdependent EQ/compression (Neve architecture), not chained  
✅ Multipoint clipping (10+ stages), not single waveshaper  
✅ Exposed controls (Bias, HF Driver), not hidden behind "warmth" slider  
✅ Matched to reference hardware (Studer, Neve, Akai), not generic  

**As Rick said:** "If we get the engineering right, people will recognize it."

---

## Questions?

See `Mastercrafter_Stage1_AudioRestorationEngine.md` for detailed architecture documentation.
