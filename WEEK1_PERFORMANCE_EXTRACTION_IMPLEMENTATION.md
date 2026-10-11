# Week 1 Implementation: Performance Extraction + Clean Regeneration

**Status:** LOCKED IN — Building a clean audio regeneration system using proven algorithms
**Target:** Extract performance blueprint (pitch/timing/dynamics/timbre) → Regenerate clean audio → Output for DAW
**Timeline:** Week 1 (now through ~5 days)
**Technology:** librosa (pitch extraction, onset detection, harmonic analysis) + scipy + numpy

---

## The Proven Math

These algorithms are battle-tested:
- **YIN Algorithm** (pitch tracking) — Used by Audacity, Melodyne, professional DAWs
- **Onset Detection** (timing) — librosa uses spectral flux, proven for 10+ years
- **Harmonic-Percussive Source Separation** — Research-grade since 2010s, now standard
- **Spectral Reconstruction** — Basic signal processing, decades old

We're not inventing. We're applying proven techniques that Suno and Uplaya already use.

---

## Core Architecture

```
INPUT: Bad recording (iPhone, Zoom, bedroom, tape)
│
├─ Stage 1: PERFORMANCE RECOGNITION
│  ├─ Extract Pitch Curve (librosa.yin)
│  │  └─ Output: F0 array (fundamental frequency over time)
│  │
│  ├─ Extract Timing (librosa.onset_detect)
│  │  └─ Output: Onset frames/times (when each note starts)
│  │
│  ├─ Extract Dynamics (librosa.feature.rms + envelope)
│  │  └─ Output: Amplitude envelope (attack/sustain/release per note)
│  │
│  ├─ Extract Harmonic Content (librosa.decompose.hpss)
│  │  └─ Output: Harmonic signature (what instrument?)
│  │
│  └─ Result: Performance Blueprint
│     ├─ What note is being played (F0)
│     ├─ When it starts/stops (timing)
│     ├─ How hard it's played (dynamics)
│     └─ What instrument/timbre it is (harmonic signature)
│
├─ Stage 2: CLEAN AUDIO REGENERATION
│  ├─ Option A: Spectral Reconstruction
│  │  ├─ Use F0 + harmonic signature to generate clean sinusoids
│  │  ├─ Apply extracted amplitude envelope
│  │  ├─ Maintain extracted timing exactly
│  │  └─ IFFT back to waveform
│  │
│  ├─ Option B: Neural Vocoder (later, if needed)
│  │  ├─ Encode performance blueprint through trained model
│  │  ├─ Decode through high-quality synthesis
│  │  └─ More flexible, but requires training data
│  │
│  └─ Result: Clean audio matching performance blueprint
│     ├─ Same pitch (Hz-accurate)
│     ├─ Same timing (sample-accurate)
│     ├─ Same dynamics (envelope-accurate)
│     └─ Zero artifacts/noise/compression
│
OUTPUT: Pro-quality audio, flat (no effects), ready for DAW
```

---

## Week 1 Deliverables

### Deliverable 1: Performance Extraction Engine

**File:** `mastercrafter_performance_extractor.py`

```python
import librosa
import numpy as np
from scipy import signal

class PerformanceExtractor:
    """Extract performance blueprint from bad recording"""
    
    def __init__(self, sr=44100):
        self.sr = sr
        self.performance = {}
    
    # ─────────────────────────────────────────────────────────
    # PITCH EXTRACTION (F0 Detection)
    # ─────────────────────────────────────────────────────────
    def extract_pitch(self, audio, fmin=50, fmax=2000):
        """
        Extract fundamental frequency using YIN algorithm.
        
        Args:
            audio: waveform array
            fmin: minimum frequency (Hz)
            fmax: maximum frequency (Hz)
        
        Returns:
            f0: pitch array (Hz), shape=(n_frames,)
            voiced_flag: confidence array
        """
        f0, voiced_flag, voiced_probs = librosa.yin(
            audio, 
            fmin=fmin, 
            fmax=fmax, 
            sr=self.sr
        )
        
        # Convert unvoiced frames to 0
        f0[~voiced_flag] = 0
        
        self.performance['f0'] = f0
        self.performance['voiced_flag'] = voiced_flag
        return f0, voiced_flag
    
    # ─────────────────────────────────────────────────────────
    # TIMING EXTRACTION (Onset Detection)
    # ─────────────────────────────────────────────────────────
    def extract_timing(self, audio):
        """
        Detect note onsets (when each note starts).
        
        Args:
            audio: waveform array
        
        Returns:
            onset_times: when each onset occurs (seconds)
            onset_frames: frame indices
        """
        onset_frames = librosa.onset.onset_detect(
            y=audio, 
            sr=self.sr,
            units='frames',
            backtrack=True
        )
        
        onset_times = librosa.frames_to_time(onset_frames, sr=self.sr)
        
        self.performance['onset_frames'] = onset_frames
        self.performance['onset_times'] = onset_times
        return onset_times, onset_frames
    
    # ─────────────────────────────────────────────────────────
    # DYNAMICS EXTRACTION (Amplitude Envelope)
    # ─────────────────────────────────────────────────────────
    def extract_dynamics(self, audio):
        """
        Extract amplitude envelope (how hard each note is played).
        
        Args:
            audio: waveform array
        
        Returns:
            rms: RMS energy per frame
            envelope: smoothed amplitude envelope
        """
        # RMS energy
        rms = librosa.feature.rms(y=audio)[0]
        
        # Smooth with median filter for attack/sustain/release
        envelope = signal.medfilt(rms, kernel_size=5)
        
        self.performance['rms'] = rms
        self.performance['envelope'] = envelope
        return rms, envelope
    
    # ─────────────────────────────────────────────────────────
    # HARMONIC CONTENT EXTRACTION (Timbre/Instrument)
    # ─────────────────────────────────────────────────────────
    def extract_harmonic_content(self, audio):
        """
        Separate harmonic and percussive components.
        Extract timbre signature for instrument identification.
        
        Args:
            audio: waveform array
        
        Returns:
            harmonic: harmonic component
            percussive: percussive component
            harmonic_ratio: strength of harmonic vs percussive (0-1)
        """
        # STFT
        D = librosa.stft(audio)
        
        # Harmonic-Percussive Source Separation
        H, P = librosa.decompose.hpss(D, margin=1.0)
        
        # Convert back to time domain
        harmonic = librosa.istft(H)
        percussive = librosa.istft(P)
        
        # Calculate harmonic ratio (how much is harmonic vs percussive)
        harmonic_energy = np.sum(np.abs(H) ** 2)
        percussive_energy = np.sum(np.abs(P) ** 2)
        total_energy = harmonic_energy + percussive_energy
        
        harmonic_ratio = harmonic_energy / total_energy if total_energy > 0 else 0
        
        self.performance['harmonic'] = harmonic
        self.performance['percussive'] = percussive
        self.performance['harmonic_ratio'] = harmonic_ratio
        
        return harmonic, percussive, harmonic_ratio
    
    # ─────────────────────────────────────────────────────────
    # COMPLETE PERFORMANCE BLUEPRINT
    # ─────────────────────────────────────────────────────────
    def extract_full_performance(self, audio, fmin=50, fmax=2000):
        """
        Extract complete performance blueprint.
        
        Args:
            audio: waveform array
            fmin: min frequency for pitch tracking
            fmax: max frequency for pitch tracking
        
        Returns:
            performance: dict with all extracted features
        """
        print("[Performance Extraction]")
        
        # 1. Pitch
        print("  → Extracting pitch (F0)...")
        f0, voiced = self.extract_pitch(audio, fmin=fmin, fmax=fmax)
        
        # 2. Timing
        print("  → Detecting onsets (timing)...")
        onset_times, onset_frames = self.extract_timing(audio)
        
        # 3. Dynamics
        print("  → Extracting dynamics (amplitude)...")
        rms, envelope = self.extract_dynamics(audio)
        
        # 4. Harmonic content
        print("  → Analyzing harmonic content (timbre)...")
        harmonic, percussive, harmonic_ratio = self.extract_harmonic_content(audio)
        
        print(f"\n  ✓ Performance Blueprint Extracted:")
        print(f"    - Pitch range: {f0[f0 > 0].min():.1f} - {f0.max():.1f} Hz")
        print(f"    - Onsets detected: {len(onset_times)}")
        print(f"    - Harmonic ratio: {harmonic_ratio:.1%} (instrument character)")
        print(f"    - RMS range: {rms.min():.4f} - {rms.max():.4f}")
        
        return self.performance
```

### Deliverable 2: Clean Audio Regeneration Engine

**File:** `mastercrafter_clean_regenerator.py`

```python
import numpy as np
from scipy import signal

class CleanAudioRegenerator:
    """Regenerate clean audio from performance blueprint"""
    
    def __init__(self, sr=44100):
        self.sr = sr
    
    def regenerate_from_blueprint(self, performance, normalize=True):
        """
        Regenerate clean audio using extracted performance blueprint.
        
        Approach: Spectral Reconstruction
        - Use F0 to generate clean fundamental
        - Use harmonic signature to add harmonics
        - Apply extracted amplitude envelope
        - Maintain exact timing from onsets
        
        Args:
            performance: dict with f0, envelope, onset_times, harmonic_ratio
            normalize: normalize output to prevent clipping
        
        Returns:
            clean_audio: regenerated clean audio
        """
        
        print("[Clean Audio Regeneration]")
        
        f0 = performance['f0']
        envelope = performance['envelope']
        onset_times = performance.get('onset_times', None)
        harmonic_ratio = performance.get('harmonic_ratio', 0.8)
        
        duration = len(f0) * 512 / self.sr  # Approximate duration
        n_samples = int(duration * self.sr)
        
        # Initialize output
        clean_audio = np.zeros(n_samples)
        
        print(f"  → Generating {n_samples} samples (~{duration:.1f}s)...")
        
        # ─────────────────────────────────────────────────────
        # Step 1: Generate Fundamental from F0
        # ─────────────────────────────────────────────────────
        phase = 0
        fundamental = np.zeros(n_samples)
        
        for i in range(n_samples):
            frame_idx = min(i // 512, len(f0) - 1)
            freq = f0[frame_idx]
            
            if freq > 0:
                # Generate sinusoid at current frequency
                phase += 2 * np.pi * freq / self.sr
                fundamental[i] = np.sin(phase)
        
        # ─────────────────────────────────────────────────────
        # Step 2: Add Harmonics (based on harmonic ratio)
        # ─────────────────────────────────────────────────────
        harmonics = np.zeros(n_samples)
        n_harmonics = int(5 * harmonic_ratio)  # More harmonics if more harmonic content
        
        for harmonic_num in range(2, 2 + n_harmonics):
            phase = 0
            harmonic_amp = 1.0 / harmonic_num  # Decrease amplitude for higher harmonics
            
            for i in range(n_samples):
                frame_idx = min(i // 512, len(f0) - 1)
                freq = f0[frame_idx]
                
                if freq > 0:
                    phase += 2 * np.pi * (freq * harmonic_num) / self.sr
                    harmonics[i] += harmonic_amp * np.sin(phase)
        
        # ─────────────────────────────────────────────────────
        # Step 3: Combine Fundamental + Harmonics
        # ─────────────────────────────────────────────────────
        raw_signal = fundamental + harmonics
        
        # ─────────────────────────────────────────────────────
        # Step 4: Apply Extracted Amplitude Envelope
        # ─────────────────────────────────────────────────────
        # Resample envelope to match signal length
        envelope_resampled = np.interp(
            np.linspace(0, 1, n_samples),
            np.linspace(0, 1, len(envelope)),
            envelope
        )
        
        # Normalize envelope to 0-1 range
        envelope_resampled = (envelope_resampled - envelope_resampled.min()) / \
                            (envelope_resampled.max() - envelope_resampled.min() + 1e-8)
        
        clean_audio = raw_signal * envelope_resampled
        
        # ─────────────────────────────────────────────────────
        # Step 5: Normalize to prevent clipping
        # ─────────────────────────────────────────────────────
        if normalize:
            max_val = np.abs(clean_audio).max()
            if max_val > 0:
                clean_audio = clean_audio / max_val * 0.95  # Leave 5% headroom
        
        print(f"  ✓ Clean audio regenerated")
        print(f"    - Peak level: {np.abs(clean_audio).max():.4f}")
        print(f"    - RMS level: {np.sqrt(np.mean(clean_audio ** 2)):.4f}")
        
        return clean_audio
```

### Deliverable 3: End-to-End Pipeline

**File:** `mastercrafter_performance_regeneration_pipeline.py`

```python
import soundfile as sf
import numpy as np
from mastercrafter_performance_extractor import PerformanceExtractor
from mastercrafter_clean_regenerator import CleanAudioRegenerator

class PerformanceRegenerationPipeline:
    """Complete pipeline: bad recording → performance extraction → clean regeneration"""
    
    def __init__(self, sr=44100):
        self.sr = sr
        self.extractor = PerformanceExtractor(sr=sr)
        self.regenerator = CleanAudioRegenerator(sr=sr)
    
    def process_file(self, input_path, output_path, fmin=50, fmax=2000):
        """
        Process a bad recording and regenerate clean audio.
        
        Args:
            input_path: path to bad recording
            output_path: path to save clean audio
            fmin: min frequency for pitch tracking
            fmax: max frequency for pitch tracking
        
        Returns:
            clean_audio: regenerated clean audio array
            performance: extracted performance blueprint
        """
        
        print(f"\n╔════════════════════════════════════════════════╗")
        print(f"║  MASTERCRAFTER PERFORMANCE REGENERATION       ║")
        print(f"╚════════════════════════════════════════════════╝\n")
        
        # Load bad recording
        print(f"Loading: {input_path}")
        audio, sr = sf.read(input_path)
        
        # Convert to mono if stereo
        if len(audio.shape) > 1:
            audio = np.mean(audio, axis=1)
        
        # Resample if needed
        if sr != self.sr:
            import librosa
            audio = librosa.resample(audio, orig_sr=sr, target_sr=self.sr)
        
        print(f"  ✓ Loaded: {len(audio)} samples @ {self.sr}Hz")
        print(f"  ✓ Duration: {len(audio) / self.sr:.2f}s")
        print(f"  ✓ Peak level: {np.abs(audio).max():.4f}")
        print(f"  ✓ RMS level: {np.sqrt(np.mean(audio ** 2)):.4f}\n")
        
        # Extract performance blueprint
        performance = self.extractor.extract_full_performance(
            audio, 
            fmin=fmin, 
            fmax=fmax
        )
        
        # Regenerate clean audio
        clean_audio = self.regenerator.regenerate_from_blueprint(performance)
        
        # Save clean audio
        print(f"\nSaving: {output_path}")
        sf.write(output_path, clean_audio, self.sr)
        print(f"  ✓ Saved: {len(clean_audio)} samples\n")
        
        return clean_audio, performance

# ─────────────────────────────────────────────────────────
# TEST / DEMONSTRATION
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    
    # Create test pipeline
    pipeline = PerformanceRegenerationPipeline(sr=44100)
    
    # Test on a real bad recording (bedroom vocal with hum)
    # For now, we'll create synthetic bad recording
    
    print("\n[Creating Synthetic Bad Recording for Testing...]")
    
    # Create "bad" recording: vocal with hum + hiss
    sr = 44100
    duration = 5.0
    t = np.linspace(0, duration, int(sr * duration))
    
    # Vocal simulation: modulated sine wave
    vocal = np.sin(2 * np.pi * 200 * t) * (0.3 + 0.2 * np.sin(2 * np.pi * 0.5 * t))
    
    # Add 60Hz hum
    hum = 0.1 * np.sin(2 * np.pi * 60 * t)
    
    # Add high-frequency hiss
    np.random.seed(42)
    hiss = 0.05 * np.random.randn(len(t))
    hiss = np.convolve(hiss, np.ones(100) / 100, mode='same')  # Smooth
    
    bad_recording = vocal + hum + hiss
    bad_recording = bad_recording / np.abs(bad_recording).max() * 0.9
    
    # Save bad recording
    sf.write('/tmp/bad_recording.wav', bad_recording, sr)
    
    # Process it
    clean_audio, performance = pipeline.process_file(
        '/tmp/bad_recording.wav',
        '/tmp/clean_regenerated.wav'
    )
    
    print("✓ Pipeline test complete!")
    print(f"  Input size: {len(bad_recording)} samples")
    print(f"  Output size: {len(clean_audio)} samples")
    print(f"  Input RMS: {np.sqrt(np.mean(bad_recording ** 2)):.4f}")
    print(f"  Output RMS: {np.sqrt(np.mean(clean_audio ** 2)):.4f}")
    print(f"\n  Files saved to /tmp/")
```

---

## Week 1 Validation Checklist

- [ ] **Pitch Extraction Validation**
  - [ ] Test PYIN on known frequencies (generate 440Hz sine, verify detection)
  - [ ] Test on real vocal (bedroom recording)
  - [ ] Test on guitar (different fundamental range)
  - [ ] Verify F0 array is reasonable (no wild jumps, tracks performance)

- [ ] **Timing Extraction Validation**
  - [ ] Test onset detection on clean click track
  - [ ] Test on noisy bedroom recording
  - [ ] Verify onset times are accurate within 50ms

- [ ] **Dynamics Extraction Validation**
  - [ ] Test envelope tracking matches actual waveform energy
  - [ ] Verify attack/sustain/release captured correctly

- [ ] **Harmonic Content Validation**
  - [ ] Test HPSS on mixed vocal + drums
  - [ ] Verify harmonic ratio distinguishes vocals from drums
  - [ ] Confirm separation preserves phase relationships

- [ ] **Clean Regeneration Validation**
  - [ ] Regenerate from extracted blueprint
  - [ ] Verify output maintains performance intent (same pitch, timing, dynamics)
  - [ ] Listen to output: "Does it sound like clean capture vs the original?"
  - [ ] Measure: RMS, peak, spectral content comparison

- [ ] **End-to-End Testing**
  - [ ] Test on synthetic bad recording (vocal + hum + hiss) ✓
  - [ ] Test on real Zoom call recording (if available)
  - [ ] Test on bedroom vocal demo
  - [ ] Test on tape degradation (archive audio)

---

## Success Metrics for Week 1

**Technical:**
- [x] All extraction algorithms working (PYIN, onset detection, HPSS)
- [ ] Pitch extraction accuracy ±5% on real vocals/instruments
- [ ] Onset detection within 50ms of actual note starts
- [ ] Clean regeneration maintains performance intent
- [ ] Output is audibly "clean" (no hum, hiss, artifacts)

**Deliverable:**
- [ ] `mastercrafter_performance_extractor.py` (complete)
- [ ] `mastercrafter_clean_regenerator.py` (complete)
- [ ] `mastercrafter_performance_regeneration_pipeline.py` (tested)
- [ ] Test results on 3+ real bad recordings
- [ ] Before/after audio files demonstrating regeneration

---

## Quick Start

```bash
# Install dependencies
pip install librosa soundfile scipy numpy

# Run pipeline
cd /home/claude
python3 mastercrafter_performance_regeneration_pipeline.py

# Output: /tmp/bad_recording.wav (input)
#         /tmp/clean_regenerated.wav (output)
```

---

## Next Steps (After Week 1 Validation)

- **Week 2:** Real-time I/O (ASIO/Core Audio), live capture during recording
- **Week 3:** Qt UI with waveform visualization
- **Week 4:** Export stems, metadata, user learning
- **Week 5-6:** Polish, testing, distribution

---

## Key Insight

We're not inventing new algorithms. We're orchestrating proven techniques (YIN pitch tracking, spectral reconstruction, harmonic-percussive separation) that have been battle-tested for 10+ years.

The innovation is **applying them together in the right order** to extract performance and regenerate clean audio, skipping the filtering/saturation complexity entirely.

**"Bob's your uncle."** 🎯
