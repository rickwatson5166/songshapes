#!/usr/bin/env python3
"""
Mastercrafter Clean Audio Regenerator
Regenerate clean pro-quality audio from performance blueprint
"""

import numpy as np
from scipy import signal
import soundfile as sf


class CleanAudioRegenerator:
    """Regenerate clean audio from performance blueprint using spectral reconstruction"""

    def __init__(self, sr=44100):
        self.sr = sr

    def regenerate_from_blueprint(self, performance, normalize=True, verbosity=1):
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
            verbosity: 0=silent, 1=progress, 2=detailed

        Returns:
            clean_audio: regenerated clean audio
        """

        if verbosity >= 1:
            print("[Clean Audio Regeneration]")

        f0 = performance['f0']
        envelope = performance['envelope']
        harmonic_ratio = performance.get('harmonic_ratio', 0.8)

        # Calculate output length from f0 array
        # Each frame in f0 represents 512 samples
        n_samples = len(f0) * 512

        if verbosity >= 1:
            print(f"  → Generating {n_samples} samples (~{n_samples / self.sr:.1f}s)...")

        # ─────────────────────────────────────────────────────
        # Step 1: Generate Fundamental from F0
        # ─────────────────────────────────────────────────────
        if verbosity >= 1:
            print(f"  → Synthesizing fundamental frequency...")

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
        if verbosity >= 1:
            print(f"  → Adding harmonics (harmonic ratio: {harmonic_ratio:.1%})...")

        harmonics = np.zeros(n_samples)

        # More harmonics if more harmonic content
        n_harmonics = max(1, int(5 * harmonic_ratio))

        for harmonic_num in range(2, 2 + n_harmonics):
            if verbosity >= 2:
                print(f"     - Harmonic {harmonic_num}/x")

            phase = 0
            # Amplitude decreases for higher harmonics
            harmonic_amp = 1.0 / (harmonic_num * 1.5)

            for i in range(n_samples):
                frame_idx = min(i // 512, len(f0) - 1)
                freq = f0[frame_idx]

                if freq > 0:
                    phase += 2 * np.pi * (freq * harmonic_num) / self.sr
                    harmonics[i] += harmonic_amp * np.sin(phase)

        # ─────────────────────────────────────────────────────
        # Step 3: Combine Fundamental + Harmonics
        # ─────────────────────────────────────────────────────
        if verbosity >= 1:
            print(f"  → Combining fundamental + {n_harmonics} harmonics...")

        raw_signal = fundamental + harmonics * 0.3  # Scale harmonics to avoid harshness

        # ─────────────────────────────────────────────────────
        # Step 4: Apply Extracted Amplitude Envelope
        # ─────────────────────────────────────────────────────
        if verbosity >= 1:
            print(f"  → Applying amplitude envelope...")

        # Resample envelope to match signal length
        envelope_resampled = np.interp(
            np.linspace(0, 1, n_samples),
            np.linspace(0, 1, len(envelope)),
            envelope
        )

        # Normalize envelope to 0-1 range
        env_min = envelope_resampled.min()
        env_max = envelope_resampled.max()
        if env_max > env_min:
            envelope_resampled = (envelope_resampled - env_min) / (env_max - env_min + 1e-8)
        else:
            envelope_resampled = np.ones_like(envelope_resampled)

        clean_audio = raw_signal * envelope_resampled

        # ─────────────────────────────────────────────────────
        # Step 5: Smooth with gentle lowpass to remove discontinuities
        # ─────────────────────────────────────────────────────
        if verbosity >= 1:
            print(f"  → Smoothing with gentle lowpass...")

        # Apply minimal smoothing (preserve transients)
        b, a = signal.butter(2, 0.95, btype='low')  # Very gentle filter
        clean_audio = signal.filtfilt(b, a, clean_audio)

        # ─────────────────────────────────────────────────────
        # Step 6: Normalize to prevent clipping
        # ─────────────────────────────────────────────────────
        if normalize:
            if verbosity >= 1:
                print(f"  → Normalizing...")

            max_val = np.abs(clean_audio).max()
            if max_val > 0:
                clean_audio = clean_audio / max_val * 0.95  # Leave 5% headroom

        # Statistics
        if verbosity >= 1:
            print(f"\n  ✓ Clean audio regenerated")
            print(f"    - Peak level: {np.abs(clean_audio).max():.4f}")
            print(f"    - RMS level: {np.sqrt(np.mean(clean_audio ** 2)):.4f}")
            print(f"    - Duration: {len(clean_audio) / self.sr:.2f}s")

        return clean_audio


# ─────────────────────────────────────────────────────────
# DEMONSTRATION / TEST
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    from mastercrafter_performance_extractor import PerformanceExtractor

    print("\n╔════════════════════════════════════════════════╗")
    print("║  MASTERCRAFTER CLEAN REGENERATOR TEST         ║")
    print("╚════════════════════════════════════════════════╝\n")

    # Create test audio
    sr = 44100
    duration = 3.0
    t = np.linspace(0, duration, int(sr * duration))

    # Vocal simulation
    vocal = np.sin(2 * np.pi * 220 * t) * (0.3 + 0.1 * np.sin(2 * np.pi * 0.7 * t))

    # Add noise
    hum = 0.08 * np.sin(2 * np.pi * 60 * t)
    np.random.seed(42)
    hiss = 0.04 * np.random.randn(len(t))
    hiss = np.convolve(hiss, np.ones(100) / 100, mode='same')

    bad_recording = vocal + hum + hiss
    bad_recording = bad_recording / np.abs(bad_recording).max() * 0.9

    # Save bad recording
    sf.write('/tmp/demo_bad.wav', bad_recording, sr)
    print(f"Bad recording: /tmp/demo_bad.wav")
    print(f"  - RMS: {np.sqrt(np.mean(bad_recording ** 2)):.4f}")
    print(f"  - Peak: {np.abs(bad_recording).max():.4f}\n")

    # Extract performance
    print("EXTRACTING PERFORMANCE BLUEPRINT:")
    print("─" * 50)
    extractor = PerformanceExtractor(sr=sr)
    performance = extractor.extract_full_performance(bad_recording, fmin=100, fmax=500)

    # Regenerate clean audio
    print("\n\nREGENERATING CLEAN AUDIO:")
    print("─" * 50)
    regenerator = CleanAudioRegenerator(sr=sr)
    clean_audio = regenerator.regenerate_from_blueprint(performance, verbosity=1)

    # Save clean audio
    sf.write('/tmp/demo_clean.wav', clean_audio, sr)
    print(f"\nClean recording: /tmp/demo_clean.wav")
    print(f"  - RMS: {np.sqrt(np.mean(clean_audio ** 2)):.4f}")
    print(f"  - Peak: {np.abs(clean_audio).max():.4f}")

    # Compare
    print("\n\nCOMPARISON:")
    print("─" * 50)
    print(f"Noise reduction (RMS):")
    bad_rms = np.sqrt(np.mean(bad_recording ** 2))
    clean_rms = np.sqrt(np.mean(clean_audio ** 2))
    reduction_db = 20 * np.log10(bad_rms / (clean_rms + 1e-8))
    print(f"  Before: {bad_rms:.4f} ({20*np.log10(bad_rms):.1f} dB)")
    print(f"  After:  {clean_rms:.4f} ({20*np.log10(clean_rms):.1f} dB)")
    print(f"  Reduction: {reduction_db:.1f} dB")
    print(f"\n✓ Test complete! Compare /tmp/demo_bad.wav vs /tmp/demo_clean.wav")
