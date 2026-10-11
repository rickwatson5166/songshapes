#!/usr/bin/env python3
"""
Integration test: Week 1 (Performance Extraction) → Stage 1 (Performance Understanding)
Tests the complete pipeline from bad recording to performance analysis
"""

import numpy as np
import soundfile as sf
from mastercrafter_performance_extractor import PerformanceExtractor
from mastercrafter_stage1_orchestrator import Stage1PerformanceUnderstanding


def create_test_bad_recording():
    """Create a synthetic bad recording for end-to-end testing"""

    sr = 44100
    duration = 8.0
    t = np.linspace(0, duration, int(sr * duration))

    # Create a musical phrase: C major scale with some character
    # Frequencies: C (262 Hz), D (294 Hz), E (330 Hz), F (349 Hz), G (392 Hz), A (440 Hz), B (494 Hz), C (523 Hz)
    notes = [262, 294, 330, 349, 392, 440, 494, 523]
    frames_per_note = len(t) // len(notes)

    vocal = np.zeros_like(t)

    for note_idx, freq in enumerate(notes):
        start_frame = note_idx * frames_per_note
        end_frame = (note_idx + 1) * frames_per_note if note_idx < len(notes) - 1 else len(t)

        # Create this note with vibrato
        t_note = t[start_frame:end_frame]
        duration_note = t_note[-1] - t_note[0]

        # Frequency with vibrato (slight pitch wobble)
        freq_vibrato = freq * (1 + 0.02 * np.sin(2 * np.pi * 5 * (t_note - t_note[0])))
        phase = 2 * np.pi * np.cumsum(freq_vibrato) / sr

        # Amplitude envelope (attack/sustain/release)
        attack_time = 0.1
        release_time = 0.1

        if duration_note > attack_time + release_time:
            attack = np.linspace(0, 1, int(attack_time * sr))
            sustain = np.ones(int((duration_note - attack_time - release_time) * sr))
            release = np.linspace(1, 0, int(release_time * sr))
            envelope_note = np.concatenate([attack, sustain, release])
        else:
            envelope_note = np.hanning(len(t_note))

        note_len = min(len(np.sin(phase)), len(envelope_note))
        vocal[start_frame:start_frame + note_len] = np.sin(phase)[:note_len] * envelope_note[:note_len]

    # Add noise: 60 Hz hum (typical mains interference)
    hum = 0.15 * np.sin(2 * np.pi * 60 * t)

    # Add high-frequency hiss (microphone noise)
    np.random.seed(42)
    hiss = 0.08 * np.random.randn(len(t))
    # Smooth hiss to make it more realistic
    hiss = np.convolve(hiss, np.ones(200) / 200, mode='same')

    # Add some clicks (recording artifacts)
    clicks = np.zeros_like(t)
    for i in range(3):
        click_idx = int(np.random.rand() * len(t))
        clicks[max(0, click_idx-100):min(len(t), click_idx+100)] += 0.1 * np.hanning(200)

    # Combine into "bad recording"
    bad_recording = vocal + hum + hiss + clicks
    bad_recording = bad_recording / np.abs(bad_recording).max() * 0.85

    return bad_recording, sr


if __name__ == "__main__":

    print("\n╔════════════════════════════════════════════════╗")
    print("║  WEEK 1 + STAGE 1 INTEGRATION TEST            ║")
    print("╚════════════════════════════════════════════════╝\n")

    # ─────────────────────────────────────────────────
    # Create test recording
    # ─────────────────────────────────────────────────
    print("[Creating synthetic bad recording...]")
    bad_recording, sr = create_test_bad_recording()

    # Save for reference
    output_file = '/tmp/test_bad_recording_stage1_test.wav'
    sf.write(output_file, bad_recording, sr)
    print(f"Saved: {output_file}")

    print(f"\nBad Recording Stats:")
    print(f"  Duration: {len(bad_recording) / sr:.2f}s")
    print(f"  Peak level: {np.abs(bad_recording).max():.4f}")
    print(f"  RMS level: {np.sqrt(np.mean(bad_recording ** 2)):.4f} ({20*np.log10(np.sqrt(np.mean(bad_recording ** 2))):.1f} dB)")

    # ─────────────────────────────────────────────────
    # WEEK 1: Performance Extraction
    # ─────────────────────────────────────────────────
    print("\n" + "="*50)
    print("WEEK 1: PERFORMANCE EXTRACTION")
    print("="*50)

    extractor = PerformanceExtractor(sr=sr)
    performance = extractor.extract_full_performance(bad_recording, fmin=100, fmax=600)

    print(f"\n✓ Performance Blueprint Extracted:")
    print(f"  Keys: {list(performance.keys())}")
    print(f"  F0 shape: {performance['f0'].shape}")
    print(f"  Onsets: {len(performance['onset_frames'])}")
    print(f"  Harmonic ratio: {performance['harmonic_ratio']:.1%}")

    # ─────────────────────────────────────────────────
    # STAGE 1: Performance Understanding
    # ─────────────────────────────────────────────────
    print("\n" + "="*50)
    print("STAGE 1: PERFORMANCE UNDERSTANDING")
    print("="*50)

    orchestrator = Stage1PerformanceUnderstanding(sr=sr, hop_length=512)
    understanding = orchestrator.understand_performance(performance, verbosity=1)

    # ─────────────────────────────────────────────────
    # FINAL SUMMARY
    # ─────────────────────────────────────────────────
    print("\n" + "="*50)
    print("COMPLETE PIPELINE RESULTS")
    print("="*50)

    print(f"\nInput Recording:")
    print(f"  Quality: Bad (hum + hiss + clicks)")
    print(f"  Format: Synthetic vocal + noise")

    print(f"\nWeek 1 Output (Performance Blueprint):")
    print(f"  Pitch range: {np.min(performance['f0'][performance['f0'] > 0]):.1f} - {np.max(performance['f0']):.1f} Hz")
    print(f"  Detected {len(performance['onset_frames'])} note onsets")
    print(f"  Harmonic content: {performance['harmonic_ratio']:.1%}")

    print(f"\nStage 1 Output (Performance Understanding):")
    print(f"  Detected Key: {understanding['key']['key']} (confidence: {understanding['key']['confidence']:.1%})")
    print(f"  Detected Tempo: {understanding['tempo']['tempo_bpm']} BPM ({understanding['tempo']['time_signature']})")
    print(f"  Detected Chord Progression:")
    for i, (chord, time) in enumerate(zip(understanding['chords']['chord_progression'],
                                           understanding['chords']['chord_timings'])):
        print(f"    {i+1}. {chord:12s} @ {time:.2f}s")

    print(f"  Detected Style:")
    print(f"    - Articulation: {understanding['style']['articulation']}")
    print(f"    - Timing: {understanding['style']['timing']}")
    print(f"    - Expression: {understanding['style']['expression']:.1%}")
    print(f"    - Swing factor: {understanding['style']['swing_factor']:.1%}")

    print(f"\n✓ COMPLETE PIPELINE WORKING!")
    print(f"  Bad recording → Performance extraction → Performance understanding")
    print(f"  Ready for Stage 2: Accompaniment Generation")
