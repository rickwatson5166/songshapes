#!/usr/bin/env python3
"""
Mastercrafter Stage 1 Orchestrator
Coordinate key detection, tempo extraction, harmonic analysis, and style detection
"""

import numpy as np
from mastercrafter_key_detector import KeyDetector
from mastercrafter_tempo_extractor import TempoExtractor
from mastercrafter_harmonic_analyzer import HarmonicAnalyzer
from mastercrafter_style_detector import StyleDetector


class Stage1PerformanceUnderstanding:
    """Complete Stage 1: Performance Understanding"""

    def __init__(self, sr=44100, hop_length=512):
        self.sr = sr
        self.hop_length = hop_length

        self.key_detector = KeyDetector()
        self.tempo_extractor = TempoExtractor(sr=sr, hop_length=hop_length)
        self.harmonic_analyzer = HarmonicAnalyzer(sr=sr, hop_length=hop_length)
        self.style_detector = StyleDetector(sr=sr, hop_length=hop_length)

    def understand_performance(self, performance_blueprint, verbosity=1):
        """
        Analyze complete performance from blueprint.

        Input: Dict from Week 1 PerformanceExtractor with:
            - f0: fundamental frequency curve
            - onset_frames: note onset locations
            - onset_times: note onset in seconds
            - envelope: amplitude envelope
            - rms: RMS energy per frame
            - harmonic_ratio: harmonic vs percussive balance

        Output: Dict with performance understanding:
            - key_info: detected key
            - tempo_info: detected tempo
            - chord_progression: chord sequence
            - style_info: playing style characteristics
        """

        if verbosity >= 1:
            print("\n╔════════════════════════════════════════════════╗")
            print("║  STAGE 1: PERFORMANCE UNDERSTANDING           ║")
            print("╚════════════════════════════════════════════════╝\n")

        # Extract key components from blueprint
        f0_curve = performance_blueprint['f0']
        onset_frames = performance_blueprint['onset_frames']
        envelope = performance_blueprint['envelope']

        # ─────────────────────────────────────────────────
        # Step 1: Detect Key
        # ─────────────────────────────────────────────────
        if verbosity >= 1:
            print("\nStep 1: Key Detection")
            print("─" * 50)

        key_info = self.key_detector.detect_key_verbose(f0_curve, verbosity=verbosity)

        # ─────────────────────────────────────────────────
        # Step 2: Extract Tempo
        # ─────────────────────────────────────────────────
        if verbosity >= 1:
            print("\nStep 2: Tempo Extraction")
            print("─" * 50)

        tempo_info = self.tempo_extractor.extract_tempo_verbose(
            onset_frames,
            sr=self.sr,
            hop_length=self.hop_length,
            verbosity=verbosity
        )

        # ─────────────────────────────────────────────────
        # Step 3: Analyze Harmonies
        # ─────────────────────────────────────────────────
        if verbosity >= 1:
            print("\nStep 3: Harmonic Analysis")
            print("─" * 50)

        harmonies = self.harmonic_analyzer.analyze_harmonies_verbose(
            f0_curve,
            onset_frames,
            key_info=key_info,
            sr=self.sr,
            hop_length=self.hop_length,
            verbosity=verbosity
        )

        # ─────────────────────────────────────────────────
        # Step 4: Detect Style
        # ─────────────────────────────────────────────────
        if verbosity >= 1:
            print("\nStep 4: Style Detection")
            print("─" * 50)

        style_info = self.style_detector.detect_style_verbose(
            f0_curve,
            envelope,
            onset_frames,
            sr=self.sr,
            hop_length=self.hop_length,
            verbosity=verbosity
        )

        # ─────────────────────────────────────────────────
        # Combine Results
        # ─────────────────────────────────────────────────
        performance_understanding = {
            'key': key_info,
            'tempo': tempo_info,
            'chords': harmonies,
            'style': style_info,
            'duration_seconds': len(f0_curve) * self.hop_length / self.sr,
            'num_onsets': len(onset_frames),
            'f0_range_hz': (float(np.min(f0_curve[f0_curve > 0])), float(np.max(f0_curve)))
        }

        if verbosity >= 1:
            print("\n" + "="*50)
            print("STAGE 1 COMPLETE: Performance Understanding")
            print("="*50)
            print(f"\nSummary:")
            print(f"  Duration: {performance_understanding['duration_seconds']:.2f}s")
            print(f"  F0 range: {performance_understanding['f0_range_hz'][0]:.1f} - {performance_understanding['f0_range_hz'][1]:.1f} Hz")
            print(f"  Number of onsets: {performance_understanding['num_onsets']}")
            print(f"\nAnalysis Results:")
            print(f"  Key: {key_info['key']} (confidence: {key_info['confidence']:.1%})")
            print(f"  Tempo: {tempo_info['tempo_bpm']} BPM ({tempo_info['time_signature']})")
            print(f"  Chords: {len(harmonies['chord_progression'])} detected")
            print(f"  Style: {style_info['articulation']}, {style_info['timing']}")

        return performance_understanding


# ─────────────────────────────────────────────────────
# TEST / DEMONSTRATION
# ─────────────────────────────────────────────────────

def create_test_performance_blueprint():
    """Create a synthetic performance blueprint for testing"""

    sr = 44100
    hop_length = 512
    duration = 8.0
    n_frames = int(duration * sr / hop_length)

    # Create F0 curve: C major scale ascending
    f0_curve = np.zeros(n_frames)
    notes = [262, 294, 330, 349, 392, 440, 494, 523]  # C D E F G A B C
    frames_per_note = n_frames // len(notes)

    for note_idx, note_freq in enumerate(notes):
        start_frame = note_idx * frames_per_note
        end_frame = (note_idx + 1) * frames_per_note if note_idx < len(notes) - 1 else n_frames
        f0_curve[start_frame:end_frame] = note_freq

    # Create amplitude envelope (rising volume)
    envelope = np.linspace(0.3, 0.9, n_frames)
    # Add note-like structure
    for i in range(len(notes)):
        start = i * frames_per_note
        end = (i + 1) * frames_per_note if i < len(notes) - 1 else n_frames
        # Add attack/decay to each note
        note_len = end - start
        envelope[start:end] *= np.concatenate([
            np.linspace(0.5, 1.0, note_len // 2),
            np.linspace(1.0, 0.5, note_len - note_len // 2)
        ])

    # Create onset frames (one per note)
    onset_frames = np.array([i * frames_per_note for i in range(len(notes) + 1) if i * frames_per_note < n_frames])

    # Create RMS curve
    rms = np.abs(envelope)

    # Create other required fields
    voiced_flag = f0_curve > 0
    harmonic_ratio = 0.85

    return {
        'f0': f0_curve,
        'voiced_flag': voiced_flag,
        'onset_frames': onset_frames,
        'onset_times': onset_frames * hop_length / sr,
        'rms': rms,
        'envelope': envelope,
        'harmonic_ratio': harmonic_ratio,
        'sr': sr,
        'hop_length': hop_length
    }


if __name__ == "__main__":

    # Create synthetic performance
    print("\n[Creating synthetic performance for testing...]")
    blueprint = create_test_performance_blueprint()

    print(f"Created performance blueprint:")
    print(f"  Duration: {blueprint['f0'].shape[0] * blueprint['hop_length'] / blueprint['sr']:.2f}s")
    print(f"  Onsets: {len(blueprint['onset_frames'])}")
    print(f"  F0 range: {np.min(blueprint['f0'][blueprint['f0'] > 0]):.1f} - {np.max(blueprint['f0']):.1f} Hz")

    # Run Stage 1 orchestrator
    orchestrator = Stage1PerformanceUnderstanding(
        sr=blueprint['sr'],
        hop_length=blueprint['hop_length']
    )

    understanding = orchestrator.understand_performance(blueprint, verbosity=1)

    # Detailed results
    print("\n" + "="*50)
    print("DETAILED RESULTS")
    print("="*50)

    print(f"\nKEY DETECTION:")
    print(f"  Key: {understanding['key']['key']}")
    print(f"  Confidence: {understanding['key']['confidence']:.1%}")
    print(f"  Root: {understanding['key']['root_hz']:.1f} Hz")

    print(f"\nTEMPO EXTRACTION:")
    print(f"  Tempo: {understanding['tempo']['tempo_bpm']} BPM")
    print(f"  Time Signature: {understanding['tempo']['time_signature']}")
    print(f"  Beat Interval: {understanding['tempo']['beat_interval_seconds']:.3f}s")
    print(f"  Confidence: {understanding['tempo']['confidence']:.1%}")

    print(f"\nHARMONIC ANALYSIS:")
    chord_list = ' → '.join(understanding['chords']['chord_progression'])
    print(f"  Chord Progression: {chord_list}")
    print(f"  Number of Chords: {len(understanding['chords']['chord_progression'])}")

    print(f"\nSTYLE DETECTION:")
    print(f"  Articulation: {understanding['style']['articulation']}")
    print(f"  Timing: {understanding['style']['timing']}")
    print(f"  Swing Factor: {understanding['style']['swing_factor']:.1%}")
    print(f"  Expression: {understanding['style']['expression']:.1%}")
    print(f"  Average Dynamics: {understanding['style']['average_dynamics']:.3f}")

    print("\n✓ Stage 1 complete! Ready for Stage 2 (Accompaniment Generation)")
