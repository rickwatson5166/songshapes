#!/usr/bin/env python3
"""
Mastercrafter Performance Regeneration Pipeline
End-to-end: bad recording → performance extraction → clean regeneration
"""

import soundfile as sf
import numpy as np
import sys
from pathlib import Path

# Import our components
from mastercrafter_performance_extractor import PerformanceExtractor
from mastercrafter_clean_regenerator import CleanAudioRegenerator


class PerformanceRegenerationPipeline:
    """Complete pipeline: bad recording → performance extraction → clean regeneration"""

    def __init__(self, sr=44100):
        self.sr = sr
        self.extractor = PerformanceExtractor(sr=sr)
        self.regenerator = CleanAudioRegenerator(sr=sr)

    def process_file(self, input_path, output_path=None, fmin=50, fmax=2000, verbosity=1):
        """
        Process a bad recording and regenerate clean audio.

        Args:
            input_path: path to bad recording
            output_path: path to save clean audio (if None, auto-generate)
            fmin: min frequency for pitch tracking
            fmax: max frequency for pitch tracking
            verbosity: 0=silent, 1=progress, 2=detailed

        Returns:
            dict with:
                - clean_audio: regenerated clean audio array
                - performance: extracted performance blueprint
                - stats: before/after statistics
                - output_path: where file was saved
        """

        if verbosity >= 1:
            print(f"\n╔════════════════════════════════════════════════╗")
            print(f"║  MASTERCRAFTER PERFORMANCE REGENERATION       ║")
            print(f"╚════════════════════════════════════════════════╝\n")

        # ─────────────────────────────────────────────────────
        # Load bad recording
        # ─────────────────────────────────────────────────────
        if verbosity >= 1:
            print(f"INPUT: {input_path}")

        if not Path(input_path).exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        audio, sr = sf.read(input_path)

        # Convert to mono if stereo
        if len(audio.shape) > 1:
            if verbosity >= 1:
                print(f"  Converting stereo → mono")
            audio = np.mean(audio, axis=1)

        # Resample if needed
        if sr != self.sr:
            if verbosity >= 1:
                print(f"  Resampling {sr} → {self.sr} Hz")
            import librosa
            audio = librosa.resample(audio, orig_sr=sr, target_sr=self.sr)

        if verbosity >= 1:
            print(f"  Duration: {len(audio) / self.sr:.2f}s")
            print(f"  Peak: {np.abs(audio).max():.4f}")
            print(f"  RMS: {np.sqrt(np.mean(audio ** 2)):.4f}\n")

        # Store input stats
        input_rms = np.sqrt(np.mean(audio ** 2))
        input_peak = np.abs(audio).max()

        # ─────────────────────────────────────────────────────
        # Extract performance blueprint
        # ─────────────────────────────────────────────────────
        if verbosity >= 1:
            print("STAGE 1: PERFORMANCE EXTRACTION")
            print("─" * 50)

        performance = self.extractor.extract_full_performance(
            audio,
            fmin=fmin,
            fmax=fmax
        )

        # ─────────────────────────────────────────────────────
        # Regenerate clean audio
        # ─────────────────────────────────────────────────────
        if verbosity >= 1:
            print("\n\nSTAGE 2: CLEAN AUDIO REGENERATION")
            print("─" * 50)
            print()

        clean_audio = self.regenerator.regenerate_from_blueprint(
            performance,
            verbosity=verbosity
        )

        # Store output stats
        output_rms = np.sqrt(np.mean(clean_audio ** 2))
        output_peak = np.abs(clean_audio).max()

        # ─────────────────────────────────────────────────────
        # Save clean audio
        # ─────────────────────────────────────────────────────
        if output_path is None:
            # Auto-generate output path
            input_stem = Path(input_path).stem
            output_path = f"/tmp/{input_stem}_REGENERATED.wav"

        if verbosity >= 1:
            print(f"\n\nOUTPUT: {output_path}")

        sf.write(output_path, clean_audio, self.sr)

        if verbosity >= 1:
            print(f"  Duration: {len(clean_audio) / self.sr:.2f}s")
            print(f"  Peak: {output_peak:.4f}")
            print(f"  RMS: {output_rms:.4f}")

        # ─────────────────────────────────────────────────────
        # Summary Statistics
        # ─────────────────────────────────────────────────────

        noise_reduction_db = 20 * np.log10(input_rms / (output_rms + 1e-8))

        if verbosity >= 1:
            print("\n\nRESULTS")
            print("─" * 50)
            print(f"Noise Reduction:")
            print(f"  Input RMS:  {input_rms:.4f} ({20*np.log10(input_rms):.1f} dB)")
            print(f"  Output RMS: {output_rms:.4f} ({20*np.log10(output_rms):.1f} dB)")
            print(f"  Reduction:  {noise_reduction_db:.1f} dB")
            print(f"\n✓ REGENERATION COMPLETE")

        return {
            'clean_audio': clean_audio,
            'performance': performance,
            'stats': {
                'input_rms': input_rms,
                'output_rms': output_rms,
                'input_peak': input_peak,
                'output_peak': output_peak,
                'noise_reduction_db': noise_reduction_db,
                'duration_seconds': len(clean_audio) / self.sr,
            },
            'output_path': output_path
        }


# ─────────────────────────────────────────────────────────
# TEST / DEMONSTRATION
# ─────────────────────────────────────────────────────────

def create_test_recording():
    """Create a synthetic bad recording for testing"""

    sr = 44100
    duration = 5.0
    t = np.linspace(0, duration, int(sr * duration))

    # Vocal simulation: modulated sine (200-300 Hz range)
    freq_mod = 200 + 50 * np.sin(2 * np.pi * 0.3 * t)
    phase = np.cumsum(2 * np.pi * freq_mod / sr)
    vocal = 0.3 * np.sin(phase) * (0.5 + 0.3 * np.sin(2 * np.pi * 0.5 * t))

    # Add 60Hz hum
    hum = 0.15 * np.sin(2 * np.pi * 60 * t)

    # Add high-frequency hiss
    np.random.seed(42)
    hiss = 0.08 * np.random.randn(len(t))
    hiss = np.convolve(hiss, np.ones(200) / 200, mode='same')  # Smooth into realistic hiss

    # Add some clicks
    clicks = np.zeros_like(t)
    for i in range(5):
        idx = int(np.random.rand() * len(t))
        clicks[max(0, idx-10):min(len(t), idx+10)] += 0.05

    # Combine into "bad recording"
    bad = vocal + hum + hiss + clicks
    bad = bad / np.abs(bad).max() * 0.85

    return bad, sr


if __name__ == "__main__":

    # ─────────────────────────────────────────────────────
    # Create and save test recording
    # ─────────────────────────────────────────────────────
    print("\n[Creating synthetic bad recording for testing...]")
    bad_recording, sr = create_test_recording()
    test_input = '/tmp/test_bad_recording.wav'
    sf.write(test_input, bad_recording, sr)
    print(f"Saved: {test_input}")

    # ─────────────────────────────────────────────────────
    # Run pipeline
    # ─────────────────────────────────────────────────────
    pipeline = PerformanceRegenerationPipeline(sr=sr)
    results = pipeline.process_file(
        test_input,
        output_path='/tmp/test_clean_regenerated.wav',
        fmin=100,
        fmax=500,
        verbosity=1
    )

    # ─────────────────────────────────────────────────────
    # Show results
    # ─────────────────────────────────────────────────────
    print("\n\n" + "=" * 50)
    print("REGENERATION SUCCESS")
    print("=" * 50)
    print(f"\nTest files saved to /tmp/")
    print(f"  Input:  test_bad_recording.wav")
    print(f"  Output: test_clean_regenerated.wav")
    print(f"\nNoise reduction achieved: {results['stats']['noise_reduction_db']:.1f} dB")
    print(f"\nYou can now compare the audio files to validate the regeneration.")
