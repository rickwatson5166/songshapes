#!/usr/bin/env python3
"""
Complete Integration Test: Week 1 + Stage 1 + Stage 2
Bad recording → Performance extraction → Performance understanding → Accompaniment generation
"""

import numpy as np
import soundfile as sf
from mastercrafter_performance_extractor import PerformanceExtractor
from mastercrafter_stage1_orchestrator import Stage1PerformanceUnderstanding
from mastercrafter_stage2_orchestrator import Stage2AccompanimentGeneration


def create_test_bad_recording():
    """Create a synthetic bad recording for end-to-end testing"""

    sr = 44100
    duration = 8.0
    t = np.linspace(0, duration, int(sr * duration))

    # Musical phrase: C major scale
    notes = [262, 294, 330, 349, 392, 440, 494, 523]
    frames_per_note = len(t) // len(notes)

    vocal = np.zeros_like(t)

    for note_idx, freq in enumerate(notes):
        start_frame = note_idx * frames_per_note
        end_frame = (note_idx + 1) * frames_per_note if note_idx < len(notes) - 1 else len(t)

        # Create this note with vibrato
        t_note = t[start_frame:end_frame]
        duration_note = t_note[-1] - t_note[0]

        # Frequency with vibrato
        freq_vibrato = freq * (1 + 0.02 * np.sin(2 * np.pi * 5 * (t_note - t_note[0])))
        phase = 2 * np.pi * np.cumsum(freq_vibrato) / sr

        # Amplitude envelope
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

    # Add noise: 60 Hz hum
    hum = 0.15 * np.sin(2 * np.pi * 60 * t)

    # Add high-frequency hiss
    np.random.seed(42)
    hiss = 0.08 * np.random.randn(len(t))
    hiss = np.convolve(hiss, np.ones(200) / 200, mode='same')

    # Add clicks
    clicks = np.zeros_like(t)
    for i in range(3):
        click_idx = int(np.random.rand() * len(t))
        clicks[max(0, click_idx-100):min(len(t), click_idx+100)] += 0.1 * np.hanning(200)

    # Combine
    bad_recording = vocal + hum + hiss + clicks
    bad_recording = bad_recording / np.abs(bad_recording).max() * 0.85

    return bad_recording, sr


if __name__ == "__main__":

    print("\n╔════════════════════════════════════════════════╗")
    print("║  COMPLETE PIPELINE TEST                       ║")
    print("║  Week 1 + Stage 1 + Stage 2                   ║")
    print("╚════════════════════════════════════════════════╝\n")

    # ─────────────────────────────────────────────────
    # Create test recording
    # ─────────────────────────────────────────────────
    print("[1. CREATING TEST RECORDING]")
    print("─" * 50)
    print("Creating synthetic bad recording (C major scale with noise)...")
    bad_recording, sr = create_test_bad_recording()

    output_file = '/tmp/test_bad_recording_full_pipeline.wav'
    sf.write(output_file, bad_recording, sr)
    print(f"✓ Saved: {output_file}")
    print(f"  Duration: {len(bad_recording) / sr:.2f}s")
    print(f"  Peak level: {np.abs(bad_recording).max():.4f}")
    print(f"  RMS level: {np.sqrt(np.mean(bad_recording ** 2)):.4f}")

    # ─────────────────────────────────────────────────
    # WEEK 1: Performance Extraction
    # ─────────────────────────────────────────────────
    print("\n[2. WEEK 1: PERFORMANCE EXTRACTION]")
    print("─" * 50)

    extractor = PerformanceExtractor(sr=sr)
    performance = extractor.extract_full_performance(bad_recording, fmin=100, fmax=600)

    print(f"✓ Performance Blueprint Extracted:")
    print(f"  F0 range: {np.min(performance['f0'][performance['f0'] > 0]):.1f} - {np.max(performance['f0']):.1f} Hz")
    print(f"  Detected {len(performance['onset_frames'])} note onsets")
    print(f"  Harmonic content: {performance['harmonic_ratio']:.1%}")

    # ─────────────────────────────────────────────────
    # STAGE 1: Performance Understanding
    # ─────────────────────────────────────────────────
    print("\n[3. STAGE 1: PERFORMANCE UNDERSTANDING]")
    print("─" * 50)

    orchestrator_s1 = Stage1PerformanceUnderstanding(sr=sr, hop_length=512)
    understanding = orchestrator_s1.understand_performance(performance, verbosity=0)

    print(f"✓ Performance Understanding Generated:")
    print(f"  Detected Key: {understanding['key']['key']} (confidence: {understanding['key']['confidence']:.1%})")
    print(f"  Detected Tempo: {understanding['tempo']['tempo_bpm']} BPM ({understanding['tempo']['time_signature']})")
    print(f"  Detected {len(understanding['chords']['chord_progression'])} chords")
    print(f"  Detected Style:")
    print(f"    - Articulation: {understanding['style']['articulation']}")
    print(f"    - Timing: {understanding['style']['timing']}")
    print(f"    - Expression: {understanding['style']['expression']:.1%}")

    # ─────────────────────────────────────────────────
    # STAGE 2: Accompaniment Generation
    # ─────────────────────────────────────────────────
    print("\n[4. STAGE 2: ACCOMPANIMENT GENERATION]")
    print("─" * 50)

    orchestrator_s2 = Stage2AccompanimentGeneration()
    accompaniment = orchestrator_s2.generate_accompaniment(understanding, verbosity=0)

    print(f"✓ Accompaniment Generated:")
    print(f"  Bass Line: {len(accompaniment['bass']['notes'])} notes")
    print(f"  Drum Pattern: {len(accompaniment['drums']['combined']['notes'])} events")
    print(f"    - Kicks: {len(accompaniment['drums']['kick']['notes'])}")
    print(f"    - Snares: {len(accompaniment['drums']['snare']['notes'])}")
    print(f"    - Hi-hats: {len(accompaniment['drums']['hi_hat']['notes'])}")
    print(f"  Pad Voicings: {len(accompaniment['pads']['combined']['notes'])} notes")
    print(f"    - Sustains: {len(accompaniment['pads']['sustain']['notes'])}")
    print(f"    - Arpeggios: {len(accompaniment['pads']['arpeggio']['notes'])}")

    # ─────────────────────────────────────────────────
    # FINAL SUMMARY
    # ─────────────────────────────────────────────────
    print("\n" + "="*50)
    print("COMPLETE PIPELINE SUMMARY")
    print("="*50)

    print(f"\n✓ INPUT:")
    print(f"  Bad recording: Synthetic C major scale with 60Hz hum, hiss, clicks")
    print(f"  Duration: {len(bad_recording) / sr:.2f}s")

    print(f"\n✓ WEEK 1 OUTPUT (Performance Blueprint):")
    print(f"  Pitch range: {np.min(performance['f0'][performance['f0'] > 0]):.1f} - {np.max(performance['f0']):.1f} Hz")
    print(f"  Onsets: {len(performance['onset_frames'])}")
    print(f"  Harmonic ratio: {performance['harmonic_ratio']:.1%}")

    print(f"\n✓ STAGE 1 OUTPUT (Performance Understanding):")
    print(f"  Key: {understanding['key']['key']}")
    print(f"  Tempo: {understanding['tempo']['tempo_bpm']} BPM")
    print(f"  Chords: {' → '.join(understanding['chords']['chord_progression'])}")
    print(f"  Style: {understanding['style']['articulation']}, {understanding['style']['timing']}")

    print(f"\n✓ STAGE 2 OUTPUT (Accompaniment):")
    print(f"  Total accompaniment notes: {len(accompaniment['bass']['notes']) + len(accompaniment['drums']['combined']['notes']) + len(accompaniment['pads']['combined']['notes'])}")
    print(f"  Bass: {len(accompaniment['bass']['notes'])} notes")
    print(f"  Drums: {len(accompaniment['drums']['combined']['notes'])} events")
    print(f"  Pads: {len(accompaniment['pads']['combined']['notes'])} notes")

    print(f"\n" + "="*50)
    print("✓✓✓ COMPLETE PIPELINE WORKING ✓✓✓")
    print("="*50)
    print(f"\nBad recording → Performance extraction → Performance understanding → Accompaniment")
    print(f"Ready for Stage 3: Audio Synthesis")
    print(f"\nNext: Build synthesizers to convert accompaniment to audio")
