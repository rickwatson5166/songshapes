#!/usr/bin/env python3
"""
Mastercrafter Performance Extractor
Extract performance blueprint from bad recording using librosa algorithms
"""

import librosa
import numpy as np
from scipy import signal
import warnings
warnings.filterwarnings('ignore')


class PerformanceExtractor:
    """Extract performance blueprint (pitch/timing/dynamics/timbre) from audio"""

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
            voiced_flag: confidence array (True = voiced, False = unvoiced)
        """
        # librosa.yin returns just the f0 array (confidence threshold built in)
        f0 = librosa.yin(
            audio,
            fmin=fmin,
            fmax=fmax,
            sr=self.sr,
            trough_threshold=0.1
        )

        # Create voiced flag based on f0 values (0 = unvoiced)
        voiced_flag = f0 > 0

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
        # RMS energy per frame
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

        # Statistics
        f0_voiced = f0[f0 > 0]
        f0_min = f0_voiced.min() if len(f0_voiced) > 0 else 0
        f0_max = f0_voiced.max() if len(f0_voiced) > 0 else 0

        print(f"\n  ✓ Performance Blueprint Extracted:")
        print(f"    - Pitch range: {f0_min:.1f} - {f0_max:.1f} Hz")
        print(f"    - Onsets detected: {len(onset_times)}")
        print(f"    - Harmonic ratio: {harmonic_ratio:.1%} (instrument character)")
        print(f"    - RMS range: {rms.min():.4f} - {rms.max():.4f}")

        return self.performance


# ─────────────────────────────────────────────────────────
# DEMONSTRATION / TEST
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import soundfile as sf

    print("\n╔════════════════════════════════════════════════╗")
    print("║  MASTERCRAFTER PERFORMANCE EXTRACTOR TEST     ║")
    print("╚════════════════════════════════════════════════╝\n")

    # Create test audio: vocal with hum + hiss
    sr = 44100
    duration = 5.0
    t = np.linspace(0, duration, int(sr * duration))

    # Vocal simulation: modulated sine wave (200Hz with vibrato)
    vocal = np.sin(2 * np.pi * 200 * t) * (0.3 + 0.2 * np.sin(2 * np.pi * 0.5 * t))

    # Add 60Hz hum
    hum = 0.1 * np.sin(2 * np.pi * 60 * t)

    # Add high-frequency hiss
    np.random.seed(42)
    hiss = 0.05 * np.random.randn(len(t))
    hiss = np.convolve(hiss, np.ones(100) / 100, mode='same')  # Smooth

    # Combine into "bad recording"
    bad_recording = vocal + hum + hiss
    bad_recording = bad_recording / np.abs(bad_recording).max() * 0.9

    # Save for inspection
    sf.write('/tmp/test_bad_recording.wav', bad_recording, sr)
    print(f"Created test bad recording: /tmp/test_bad_recording.wav")

    # Extract performance
    print(f"\n")
    extractor = PerformanceExtractor(sr=sr)
    performance = extractor.extract_full_performance(bad_recording, fmin=50, fmax=500)

    print(f"\nExtraction complete! Performance blueprint:")
    print(f"  Keys: {list(performance.keys())}")
    print(f"  F0 shape: {performance['f0'].shape}")
    print(f"  Harmonic shape: {performance['harmonic'].shape}")
    print(f"  Voiced frames: {np.sum(performance['voiced_flag'])} / {len(performance['voiced_flag'])}")
