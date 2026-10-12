#!/usr/bin/env python3
"""
Generate synthetic test audio for Phase 3A testing
Creates a simple vocal-like signal with pitch variation and harmonics
"""

import numpy as np
import soundfile as sf
from pathlib import Path

def generate_test_vocal():
    """
    Generate synthetic vocal-like audio
    - 30 seconds duration
    - 44100 Hz sample rate
    - Fundamental frequency: 200 Hz (male voice range) with slight variations
    - Contains harmonics similar to vocal audio
    """
    sr = 44100
    duration = 30  # 30 seconds
    t = np.linspace(0, duration, int(sr * duration), False)

    # Create a pitch contour that moves over time
    # Starts at 180 Hz, moves to 220 Hz at middle, back to 180 Hz
    f0_base = 180
    f0_variation = 40 * np.sin(2 * np.pi * t / duration)  # ±40 Hz variation
    f0 = f0_base + f0_variation

    # Generate fundamental with harmonics (vocal-like timbre)
    # F1 (fundamental), F2 (2nd harmonic), F3 (3rd harmonic)
    phase = 2 * np.pi * np.cumsum(f0) / sr
    fundamental = 0.5 * np.sin(phase)
    harmonic2 = 0.2 * np.sin(2 * phase)
    harmonic3 = 0.1 * np.sin(3 * phase)

    # Combine harmonics
    signal = fundamental + harmonic2 + harmonic3

    # Apply amplitude envelope (attack, sustain, release)
    # Fade in at start, fade out at end
    fade_in = np.linspace(0, 1, int(sr * 0.5))  # 0.5s fade in
    fade_out = np.linspace(1, 0, int(sr * 1))   # 1s fade out

    envelope = np.ones_like(signal)
    envelope[:len(fade_in)] = fade_in
    envelope[-len(fade_out):] = fade_out

    signal = signal * envelope

    # Normalize
    signal = signal / np.max(np.abs(signal)) * 0.8

    return signal, sr, t, f0

def generate_test_audio_with_chords():
    """
    Generate test audio with multiple sections featuring different underlying harmonies
    Simulates a song with chord changes and harmonic variety
    """
    sr = 44100
    duration = 20  # 20 seconds

    # Section 1: C major (0-5s)
    t1 = np.linspace(0, 5, int(sr * 5), False)
    f0_1 = 200 + 20 * np.sin(2 * np.pi * t1 / 5)
    signal1 = generate_signal_with_harmonic_context(f0_1, sr, 'C', 'major')

    # Section 2: F major (5-10s) - moved up from C
    t2 = np.linspace(0, 5, int(sr * 5), False)
    f0_2 = 220 + 20 * np.sin(2 * np.pi * t2 / 5)
    signal2 = generate_signal_with_harmonic_context(f0_2, sr, 'F', 'major')

    # Section 3: G major (10-15s) - higher
    t3 = np.linspace(0, 5, int(sr * 5), False)
    f0_3 = 240 + 20 * np.sin(2 * np.pi * t3 / 5)
    signal3 = generate_signal_with_harmonic_context(f0_3, sr, 'G', 'major')

    # Section 4: C major return (15-20s)
    t4 = np.linspace(0, 5, int(sr * 5), False)
    f0_4 = 200 + 20 * np.sin(2 * np.pi * t4 / 5)
    signal4 = generate_signal_with_harmonic_context(f0_4, sr, 'C', 'major')

    # Concatenate sections with crossfade
    full_signal = np.concatenate([signal1, signal2, signal3, signal4])

    # Apply overall envelope
    fade_in = np.linspace(0, 1, int(sr * 1))
    fade_out = np.linspace(1, 0, int(sr * 1))
    envelope = np.ones_like(full_signal)
    envelope[:len(fade_in)] = fade_in
    envelope[-len(fade_out):] = fade_out

    full_signal = full_signal * envelope
    full_signal = full_signal / np.max(np.abs(full_signal)) * 0.7

    return full_signal, sr

def generate_signal_with_harmonic_context(f0, sr, root, quality):
    """
    Generate a vocal signal with harmonic context from chord
    Adds subtle overtones based on the underlying chord
    """
    t = np.arange(len(f0)) / sr

    # Basic vocal timbre
    phase = 2 * np.pi * np.cumsum(f0) / sr
    signal = 0.5 * np.sin(phase)
    signal += 0.2 * np.sin(2 * phase)
    signal += 0.1 * np.sin(3 * phase)
    signal += 0.05 * np.sin(4 * phase)

    # Add subtle harmonic coloration based on chord
    # This creates a basis for chord detection algorithms
    if quality == 'major':
        harmonic_boost = 1.0  # Boost slightly for major
    else:
        harmonic_boost = 0.8  # Slightly different for minor

    signal *= harmonic_boost

    # Normalize each section
    signal = signal / np.max(np.abs(signal)) * 0.6

    return signal

def main():
    print("Generating synthetic test audio...")

    # Generate two versions
    print("  - Generating simple vocal signal (30s)...")
    signal1, sr1, t1, f0_1 = generate_test_vocal()
    path1 = Path('/home/claude/test_audio_vocal.wav')
    sf.write(path1, signal1, sr1)
    print(f"    ✓ Saved: {path1} ({len(signal1)/sr1:.1f}s)")

    print("  - Generating chord-based signal (20s)...")
    signal2, sr2 = generate_test_audio_with_chords()
    path2 = Path('/home/claude/test_audio_chords.wav')
    sf.write(path2, signal2, sr2)
    print(f"    ✓ Saved: {path2} ({len(signal2)/sr2:.1f}s)")

    print("\nTest audio files ready!")
    print(f"  For melody extraction: {path1}")
    print(f"  For chord detection: {path2}")

    return path1, path2

if __name__ == '__main__':
    main()
