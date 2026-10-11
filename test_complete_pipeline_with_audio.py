#!/usr/bin/env python3
"""
Complete End-to-End Integration Test: Week 1 + Stage 1 + Stage 2 + Stage 3
Bad recording → Performance extraction → Understanding → Accompaniment → Audio synthesis → Mixed output
"""

import numpy as np
import soundfile as sf
from mastercrafter_performance_extractor import PerformanceExtractor
from mastercrafter_stage1_orchestrator import Stage1PerformanceUnderstanding
from mastercrafter_stage2_orchestrator import Stage2AccompanimentGeneration
from mastercrafter_stage3_orchestrator import Stage3AudioSynthesis


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
    print("║  COMPLETE PIPELINE TEST (All Stages)          ║")
    print("║  Week 1 + Stage 1 + Stage 2 + Stage 3         ║")
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
    print(f"  Detected Tempo: {understanding['tempo']['tempo_bpm']} BPM")
    print(f"  Detected {len(understanding['chords']['chord_progression'])} chords")
    print(f"  Style: {understanding['style']['articulation']}, {understanding['style']['timing']}")

    # ─────────────────────────────────────────────────
    # STAGE 2: Accompaniment Generation
    # ─────────────────────────────────────────────────
    print("\n[4. STAGE 2: ACCOMPANIMENT GENERATION]")
    print("─" * 50)

    orchestrator_s2 = Stage2AccompanimentGeneration()
    accompaniment = orchestrator_s2.generate_accompaniment(understanding, verbosity=0)

    print(f"✓ Accompaniment Generated:")
    print(f"  Bass: {len(accompaniment['bass']['notes'])} notes")
    print(f"  Drums: {len(accompaniment['drums']['combined']['notes'])} events")
    print(f"  Pads: {len(accompaniment['pads']['combined']['notes'])} voices")

    # ─────────────────────────────────────────────────
    # STAGE 3: Audio Synthesis
    # ─────────────────────────────────────────────────
    print("\n[5. STAGE 3: AUDIO SYNTHESIS]")
    print("─" * 50)

    synthesizer = Stage3AudioSynthesis(sr=sr)
    synthesis_result = synthesizer.synthesize_accompaniment(accompaniment, verbosity=0)

    print(f"✓ Audio Synthesized:")
    print(f"  Duration: {synthesis_result['duration_seconds']:.2f}s")
    print(f"  Sample rate: {synthesis_result['sr']} Hz")
    print(f"  Mixed audio peak: {np.abs(synthesis_result['mixed']['audio']).max():.3f}")

    # ─────────────────────────────────────────────────
    # Create mixed output (original + accompaniment)
    # ─────────────────────────────────────────────────
    print("\n[6. CREATING MIXED OUTPUT]")
    print("─" * 50)

    original_audio = bad_recording
    accompaniment_audio = synthesis_result['mixed']['audio']

    # Match lengths (pad original to accompaniment length)
    if len(original_audio) < len(accompaniment_audio):
        original_audio = np.pad(original_audio, (0, len(accompaniment_audio) - len(original_audio)))
    elif len(original_audio) > len(accompaniment_audio):
        accompaniment_audio = np.pad(accompaniment_audio, (0, len(original_audio) - len(accompaniment_audio)))

    # Normalize levels
    original_level = np.abs(original_audio).max()
    accompaniment_level = np.abs(accompaniment_audio).max()

    if original_level > 0:
        original_audio = original_audio / original_level

    if accompaniment_level > 0:
        accompaniment_audio = accompaniment_audio / accompaniment_level

    # Mix: 50/50 blend
    mixed_final = 0.5 * original_audio + 0.5 * accompaniment_audio

    # Final normalize
    max_val = np.abs(mixed_final).max()
    if max_val > 0:
        mixed_final = 0.95 * mixed_final / max_val

    print(f"✓ Mixed original + accompaniment")
    print(f"  Original level: {original_level:.3f}")
    print(f"  Accompaniment level: {accompaniment_level:.3f}")
    print(f"  Mix peak: {np.abs(mixed_final).max():.3f}")

    # Save mixed output
    mixed_output_file = '/tmp/complete_pipeline_final_mix.wav'
    sf.write(mixed_output_file, mixed_final, sr)
    print(f"✓ Saved mixed output: {mixed_output_file}")

    # Save individual stems
    print("\n[7. EXPORTING STEMS]")
    print("─" * 50)

    stems = synthesizer.export_stems(synthesis_result, output_dir='/tmp')
    print(f"✓ Stems exported:")
    for stem_type, filepath in stems.items():
        print(f"  {stem_type}: {filepath}")

    # ─────────────────────────────────────────────────
    # FINAL SUMMARY
    # ─────────────────────────────────────────────────
    print("\n" + "="*50)
    print("COMPLETE PIPELINE SUMMARY")
    print("="*50)

    print(f"\n✓ INPUT:")
    print(f"  Bad recording: Synthetic C major scale with noise")
    print(f"  Duration: {len(bad_recording) / sr:.2f}s")

    print(f"\n✓ WEEK 1 OUTPUT (Performance Blueprint):")
    print(f"  Pitch range: {np.min(performance['f0'][performance['f0'] > 0]):.1f} - {np.max(performance['f0']):.1f} Hz")
    print(f"  Onsets: {len(performance['onset_frames'])}")

    print(f"\n✓ STAGE 1 OUTPUT (Performance Understanding):")
    print(f"  Key: {understanding['key']['key']}")
    print(f"  Tempo: {understanding['tempo']['tempo_bpm']} BPM")
    print(f"  Chords: {' → '.join(understanding['chords']['chord_progression'])}")

    print(f"\n✓ STAGE 2 OUTPUT (Accompaniment Data):")
    print(f"  Total notes: {len(accompaniment['bass']['notes']) + len(accompaniment['drums']['combined']['notes']) + len(accompaniment['pads']['combined']['notes'])}")

    print(f"\n✓ STAGE 3 OUTPUT (Audio Synthesis):")
    print(f"  Synthesized duration: {synthesis_result['duration_seconds']:.2f}s")
    print(f"  Drums + Bass + Pads mixed")

    print(f"\n✓ FINAL OUTPUT (Mixed):")
    print(f"  Original + Accompaniment blended")
    print(f"  Saved: {mixed_output_file}")
    print(f"  Stems saved: drums, bass, pads")

    print(f"\n" + "="*50)
    print("✓✓✓ COMPLETE PIPELINE WORKING ✓✓✓")
    print("="*50)
    print(f"\nWeek 1 → Stage 1 → Stage 2 → Stage 3 → Mixed Audio")
    print(f"\n✓ System ready for:")
    print(f"  - Web UI implementation")
    print(f"  - Track-by-track regeneration workflow")
    print(f"  - Stem export for user customization")
