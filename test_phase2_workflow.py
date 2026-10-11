#!/usr/bin/env python3
"""
End-to-end test for SongShapes Phase 2
Test the complete accompaniment generation pipeline:
1. Extract F0 from vocals
2. Detect chord progression
3. Generate bass + drums patterns
4. Synthesize audio
5. Mix with vocals
6. Apply character effects
"""

import numpy as np
import soundfile as sf
from pathlib import Path
from melody_extractor import MelodyExtractor
from chord_detector import ChordDetector
from accompaniment_generator import AccompanimentGenerator
from drum_synthesizer import DrumSynthesizer
from bass_synthesizer import BassSynthesizer
from accompaniment_mixer import AccompanimentMixer


def create_test_vocals(duration=4, sr=44100):
    """Create synthetic test vocals with melody and vibrato"""
    t = np.linspace(0, duration, int(sr * duration))

    # Melody: C4 → E4 → G4 → C5 (simple ascending progression)
    # Each note is 1 second
    melody = np.zeros_like(t)

    # C4 (261.63 Hz) for 1 second
    mask1 = t < 1
    vibrato1 = 0.02 * np.sin(2 * np.pi * 5 * t[mask1])
    melody[mask1] = 0.4 * np.sin(2 * np.pi * 261.63 * t[mask1] * (1 + vibrato1))

    # E4 (329.63 Hz) for 1 second
    mask2 = (t >= 1) & (t < 2)
    vibrato2 = 0.02 * np.sin(2 * np.pi * 5 * (t[mask2] - 1))
    melody[mask2] = 0.4 * np.sin(2 * np.pi * 329.63 * t[mask2] * (1 + vibrato2))

    # G4 (392.00 Hz) for 1 second
    mask3 = (t >= 2) & (t < 3)
    vibrato3 = 0.02 * np.sin(2 * np.pi * 5 * (t[mask3] - 2))
    melody[mask3] = 0.4 * np.sin(2 * np.pi * 392.00 * t[mask3] * (1 + vibrato3))

    # C5 (523.25 Hz) for 1 second
    mask4 = t >= 3
    vibrato4 = 0.02 * np.sin(2 * np.pi * 5 * (t[mask4] - 3))
    melody[mask4] = 0.4 * np.sin(2 * np.pi * 523.25 * t[mask4] * (1 + vibrato4))

    # Add noise
    melody += 0.01 * np.random.randn(len(melody))

    # Normalize
    melody = melody / (np.max(np.abs(melody)) + 1e-8) * 0.8

    return melody, sr


def test_phase2_pipeline():
    """Test complete Phase 2 workflow"""
    print("=" * 70)
    print("SongShapes Phase 2: End-to-End Accompaniment Generation Test")
    print("=" * 70)

    sr = 44100
    duration = 4.0

    # [1] Create test vocals
    print("\n[1/6] Creating test vocals...")
    vocals, sr = create_test_vocals(duration, sr)
    print(f"✓ Created test vocals: {len(vocals)} samples ({duration:.1f}s)")

    # [2] Extract melody (F0 contour)
    print("\n[2/6] Extracting melody (F0 contour)...")
    extractor = MelodyExtractor(sr=sr)
    f0_contour, confidence, times = extractor.extract_f0(vocals)
    print(f"✓ Extracted F0 contour: {len(f0_contour)} frames")
    print(f"  Mean F0 (voiced): {np.mean(f0_contour[f0_contour > 0]):.1f} Hz")
    print(f"  Mean confidence: {np.mean(confidence[confidence > 0]):.2f}")

    # Get note sequence (with lower confidence threshold for test audio)
    note_sequence = extractor.get_melody_note_sequence(f0_contour, confidence, times, confidence_threshold=0.15)
    print(f"  Detected {len(note_sequence)} notes from melody")
    for note in note_sequence:
        _, note_name = extractor.hz_to_note(note['f0'])
        print(f"    {note_name}: {note['start_time']:.2f}s - {note['end_time']:.2f}s")

    # [3] Detect chords
    print("\n[3/6] Detecting chord progression...")
    detector = ChordDetector(sr=sr)
    chords, times = detector.detect_chords(vocals)
    print(f"✓ Detected {len(chords)} chords:")
    for i, chord in enumerate(chords):
        print(f"  {i+1}. {chord['root']}{chord['quality'][:3].upper()} "
              f"@ {chord['start_time']:.2f}s - {chord['end_time']:.2f}s "
              f"({chord['confidence']:.2f})")

    # [4] Generate bass + drums
    print("\n[4/6] Generating accompaniment patterns...")
    melody_data = {'f0_contour': f0_contour, 'confidence': confidence}
    acc_gen = AccompanimentGenerator(sr=sr)
    accompaniment = acc_gen.generate(melody_data, chords, tempo_bpm=120, key='C')
    print(f"✓ Generated accompaniment:")
    print(f"  Bass notes: {accompaniment['metadata']['num_bass_notes']}")
    print(f"  Drum events: {accompaniment['metadata']['num_drum_events']}")
    print(f"  Articulation: {accompaniment['metadata']['articulation']}")

    # [5] Synthesize audio
    print("\n[5/6] Synthesizing accompaniment audio...")

    # Synthesize drums
    drum_synth = DrumSynthesizer(sr=sr)
    drums = drum_synth.synthesize_drum_track(accompaniment['drums'], total_duration=duration)
    print(f"✓ Synthesized drums: {len(drums)} samples")

    # Synthesize bass
    bass_synth = BassSynthesizer(sr=sr)
    bass = bass_synth.synthesize_bass_track(accompaniment['bass'], total_duration=duration)
    print(f"✓ Synthesized bass: {len(bass)} samples")

    # [6] Mix components
    print("\n[6/6] Mixing and applying character effects...")
    mixer = AccompanimentMixer(sr=sr)

    # Mix with equal levels
    levels = {'vocals': 1.0, 'bass': 0.7, 'drums': 0.8}
    mix_dry = mixer.mix_accompaniment(vocals, bass, drums, levels)
    print(f"✓ Mixed tracks: {len(mix_dry)} samples")

    # Apply character effects
    character_config = {
        'eq_low': 1,
        'eq_mid': 0,
        'eq_high': 2,
        'compression': 0.3,
        'saturation': 0.2,
        'reverb': 0.15
    }
    mix_processed = mixer.process_stem(mix_dry, character_config)
    print(f"✓ Applied character effects")

    # Normalize final mix
    max_val = np.max(np.abs(mix_processed))
    if max_val > 0.99:
        mix_processed = mix_processed * (0.99 / max_val)

    print("\n" + "=" * 70)
    print("✓ PHASE 2 PIPELINE COMPLETE")
    print("=" * 70)

    # Summary stats
    print(f"\n📊 Final Mix Statistics:")
    print(f"  Duration: {len(mix_processed) / sr:.2f}s")
    print(f"  Peak level: {np.max(np.abs(mix_processed)):.3f}")
    print(f"  RMS level: {np.sqrt(np.mean(mix_processed**2)):.3f}")
    print(f"  Crest factor: {np.max(np.abs(mix_processed)) / np.sqrt(np.mean(mix_processed**2)):.1f}dB")

    print(f"\n🎵 Component Summary:")
    print(f"  Vocals: {len(vocals)} samples, peak {np.max(np.abs(vocals)):.3f}")
    print(f"  Bass: {len(bass)} samples, peak {np.max(np.abs(bass)):.3f}")
    print(f"  Drums: {len(drums)} samples, peak {np.max(np.abs(drums)):.3f}")

    print(f"\n🎼 Musical Content:")
    print(f"  Melody: {len(note_sequence)} notes")
    print(f"  Chords: {len(chords)} changes")
    print(f"  Bass: {accompaniment['metadata']['num_bass_notes']} notes")
    print(f"  Drums: {accompaniment['metadata']['num_drum_events']} events")

    return {
        'mix': mix_processed,
        'vocals': vocals,
        'bass': bass,
        'drums': drums,
        'sr': sr,
        'f0_contour': f0_contour,
        'chords': chords,
        'accompaniment': accompaniment
    }


def save_results(result, output_dir='/tmp/phase2_test'):
    """Save test results to disk"""
    from pathlib import Path
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    print(f"\n💾 Saving results to {output_dir}...")

    # Save individual stems
    sf.write(output_dir / 'vocals.wav', result['vocals'], result['sr'])
    sf.write(output_dir / 'bass.wav', result['bass'], result['sr'])
    sf.write(output_dir / 'drums.wav', result['drums'], result['sr'])
    sf.write(output_dir / 'mix.wav', result['mix'], result['sr'])

    print(f"✓ Saved stems to {output_dir}")
    print(f"  - vocals.wav")
    print(f"  - bass.wav")
    print(f"  - drums.wav")
    print(f"  - mix.wav")

    return output_dir


if __name__ == '__main__':
    try:
        result = test_phase2_pipeline()
        output_dir = save_results(result)
        print(f"\n🎉 Phase 2 test successful! Results in {output_dir}")
        exit(0)
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
