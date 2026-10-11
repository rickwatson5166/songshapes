#!/usr/bin/env python3
"""
Mastercrafter Stage 2 Orchestrator
Coordinate bass, drums, and pad generation for complete accompaniment
"""

from mastercrafter_bass_generator import BassLineGenerator
from mastercrafter_drum_generator import DrumPatternGenerator
from mastercrafter_pad_generator import PadGenerator


class Stage2AccompanimentGeneration:
    """Complete Stage 2: Generate accompaniment (bass, drums, pads)"""

    def __init__(self):
        self.bass_generator = BassLineGenerator()
        self.drum_generator = DrumPatternGenerator()
        self.pad_generator = PadGenerator()

    def generate_accompaniment(self, performance_understanding, verbosity=1):
        """
        Generate complete accompaniment from performance understanding.

        Input: Dict from Stage 1 with:
            - key: detected key information
            - tempo: detected tempo information
            - chords: chord progression
            - style: detected style characteristics

        Output: Dict with complete accompaniment:
            - bass: bass line notes
            - drums: drum patterns (kick, snare, hi-hat)
            - pads: pad voicings
            - combined: all notes mixed
            - description: text summary
        """

        if verbosity >= 1:
            print("\n╔════════════════════════════════════════════════╗")
            print("║  STAGE 2: ACCOMPANIMENT GENERATION            ║")
            print("╚════════════════════════════════════════════════╝\n")

        # Extract components from performance understanding
        key_info = performance_understanding['key']
        tempo_info = performance_understanding['tempo']
        chord_info = performance_understanding['chords']
        style_info = performance_understanding['style']

        chord_progression = chord_info['chord_progression']
        chord_timings = chord_info['chord_timings']
        tempo_bpm = tempo_info['tempo_bpm']

        # ─────────────────────────────────────────────────
        # Step 1: Generate Bass Line
        # ─────────────────────────────────────────────────
        if verbosity >= 1:
            print("Step 1: Bass Line Generation")
            print("─" * 50)

        bass_result = self.bass_generator.generate_bass_line_verbose(
            chord_progression,
            chord_timings,
            tempo_bpm,
            key_info,
            style_info,
            verbosity=verbosity
        )

        # ─────────────────────────────────────────────────
        # Step 2: Generate Drum Pattern
        # ─────────────────────────────────────────────────
        if verbosity >= 1:
            print("\nStep 2: Drum Pattern Generation")
            print("─" * 50)

        drum_result = self.drum_generator.generate_drum_pattern_verbose(
            chord_progression,
            chord_timings,
            tempo_bpm,
            key_info,
            style_info,
            verbosity=verbosity
        )

        # ─────────────────────────────────────────────────
        # Step 3: Generate Pads
        # ─────────────────────────────────────────────────
        if verbosity >= 1:
            print("\nStep 3: Pad Generation")
            print("─" * 50)

        pad_result = self.pad_generator.generate_pads_verbose(
            chord_progression,
            chord_timings,
            tempo_bpm,
            key_info,
            style_info,
            verbosity=verbosity
        )

        # ─────────────────────────────────────────────────
        # Combine all accompaniment elements
        # ─────────────────────────────────────────────────

        accompaniment = {
            'bass': bass_result,
            'drums': drum_result,
            'pads': pad_result,
            'key': key_info,
            'tempo': tempo_info,
            'chords': chord_info,
            'style': style_info,
            'description': f'Complete accompaniment: {len(bass_result["notes"])} bass notes, {len(drum_result["combined"]["notes"])} drum events, {len(pad_result["combined"]["notes"])} pad notes'
        }

        if verbosity >= 1:
            print("\n" + "="*50)
            print("STAGE 2 COMPLETE: Accompaniment Generation")
            print("="*50)
            print(f"\nSummary:")
            print(f"  Bass Line: {len(bass_result['notes'])} notes")
            print(f"  Drum Pattern: {len(drum_result['combined']['notes'])} events")
            print(f"    - Kicks: {len(drum_result['kick']['notes'])}")
            print(f"    - Snares: {len(drum_result['snare']['notes'])}")
            print(f"    - Hi-hats: {len(drum_result['hi_hat']['notes'])}")
            print(f"  Pad Voicings: {len(pad_result['combined']['notes'])} notes")
            print(f"    - Sustains: {len(pad_result['sustain']['notes'])}")
            print(f"    - Arpeggios: {len(pad_result['arpeggio']['notes'])}")
            print(f"\nStyle Applied:")
            print(f"  Articulation: {style_info['articulation']}")
            print(f"  Timing: {style_info['timing']}")
            print(f"  Expression: {style_info['expression']:.1%}")
            print(f"  Swing Factor: {style_info['swing_factor']:.1%}")

        return accompaniment

    def get_accompaniment_summary(self, accompaniment):
        """Generate a text summary of the accompaniment"""

        summary = f"""
╔════════════════════════════════════════════════╗
║  ACCOMPANIMENT SUMMARY                        ║
╚════════════════════════════════════════════════╝

PERFORMANCE CONTEXT:
  Key: {accompaniment['key']['key']} (confidence: {accompaniment['key']['confidence']:.1%})
  Tempo: {accompaniment['tempo']['tempo_bpm']} BPM ({accompaniment['tempo']['time_signature']})
  Chords: {' → '.join(accompaniment['chords']['chord_progression'])}

ACCOMPANIMENT ELEMENTS:

Bass Line:
  Total notes: {len(accompaniment['bass']['notes'])}
  Range: {self.bass_generator._midi_to_note_name(min(accompaniment['bass']['notes']))} - {self.bass_generator._midi_to_note_name(max(accompaniment['bass']['notes']))}
  Style: {accompaniment['style']['articulation']} articulation
  Description: {accompaniment['bass']['description']}

Drum Pattern:
  Total drum events: {len(accompaniment['drums']['combined']['notes'])}
  Kick hits: {len(accompaniment['drums']['kick']['notes'])}
  Snare hits: {len(accompaniment['drums']['snare']['notes'])}
  Hi-hat hits: {len(accompaniment['drums']['hi_hat']['notes'])}
  Timing: {accompaniment['style']['timing']}

Pad Voicings:
  Total notes: {len(accompaniment['pads']['combined']['notes'])}
  Sustain voices: {len(accompaniment['pads']['sustain']['notes'])}
  Arpeggio notes: {len(accompaniment['pads']['arpeggio']['notes'])}
  Expression: {accompaniment['style']['expression']:.1%}

TOTAL ACCOMPANIMENT NOTES: {len(accompaniment['bass']['notes']) + len(accompaniment['drums']['combined']['notes']) + len(accompaniment['pads']['combined']['notes'])}

Ready for Stage 3: Audio Synthesis
"""
        return summary


# ─────────────────────────────────────────────────
# TEST / DEMONSTRATION
# ─────────────────────────────────────────────────

def create_test_performance_understanding():
    """Create a synthetic performance understanding for testing"""

    import numpy as np

    # Simulate Stage 1 output
    performance_understanding = {
        'key': {
            'key': 'C major',
            'confidence': 0.85,
            'root_hz': 261.6
        },
        'tempo': {
            'tempo_bpm': 120,
            'time_signature': '4/4',
            'beat_interval_seconds': 0.5,
            'confidence': 0.98
        },
        'chords': {
            'chord_progression': ['C major', 'F major', 'G major', 'C major'],
            'chord_timings': [0.0, 2.0, 4.0, 6.0],
            'confidence': 0.75
        },
        'style': {
            'articulation': 'legato',
            'timing': 'straight',
            'swing_factor': 0.0,
            'expression': 0.6,
            'average_dynamics': 0.7
        },
        'duration_seconds': 8.0,
        'num_onsets': 32,
        'f0_range_hz': (262.0, 523.0)
    }

    return performance_understanding


if __name__ == "__main__":

    print("\n╔════════════════════════════════════════════════╗")
    print("║  STAGE 2 ORCHESTRATOR INTEGRATION TEST       ║")
    print("╚════════════════════════════════════════════════╝\n")

    # Create test performance understanding
    print("[Creating synthetic performance understanding...]")
    performance_understanding = create_test_performance_understanding()

    print(f"Performance Understanding:")
    print(f"  Key: {performance_understanding['key']['key']}")
    print(f"  Tempo: {performance_understanding['tempo']['tempo_bpm']} BPM")
    print(f"  Chords: {' → '.join(performance_understanding['chords']['chord_progression'])}")
    print(f"  Style: {performance_understanding['style']['articulation']}, Expression: {performance_understanding['style']['expression']:.1%}")

    # Run Stage 2 orchestrator
    orchestrator = Stage2AccompanimentGeneration()
    accompaniment = orchestrator.generate_accompaniment(performance_understanding, verbosity=1)

    # Print detailed summary
    summary = orchestrator.get_accompaniment_summary(accompaniment)
    print(summary)

    print("\n✓ Stage 2 complete! Ready for Stage 3 (Audio Synthesis)")
