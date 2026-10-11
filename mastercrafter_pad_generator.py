#!/usr/bin/env python3
"""
Mastercrafter Pad Generator
Generate sustained chord voicings (pads) that follow chord progression
"""

import numpy as np


class PadGenerator:
    """Generate sustained pad voicings following detected chord progression"""

    def __init__(self):
        self.note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

        # Chord intervals (semitones from root)
        self.chord_intervals = {
            'major': [0, 4, 7],           # Root, Major 3rd, Perfect 5th
            'minor': [0, 3, 7],           # Root, Minor 3rd, Perfect 5th
            'major7': [0, 4, 7, 11],      # Major triad + Major 7th
            'minor7': [0, 3, 7, 10],      # Minor triad + Minor 7th
            'dominant7': [0, 4, 7, 10],   # Major triad + Minor 7th
            'maj9': [0, 4, 7, 11, 14],    # Major 7th + Major 9th
            'min9': [0, 3, 7, 10, 14],    # Minor 7th + Major 9th
        }

    def generate_pad_voicing(self, chord_name, root_midi=60):
        """
        Generate a chord voicing for pad.

        Args:
            chord_name: e.g. "C major", "F minor", "G dominant7"
            root_midi: MIDI note of the root (default: C4 = 60)

        Returns:
            list of MIDI note numbers in the voicing
        """

        # Parse chord
        parts = chord_name.split()
        if len(parts) < 2:
            # Default to major if quality not specified
            chord_quality = 'major'
        else:
            chord_quality = parts[1]

        # Get intervals for this chord quality
        if chord_quality not in self.chord_intervals:
            chord_quality = 'major'  # Default fallback

        intervals = self.chord_intervals[chord_quality]

        # Build voicing: root + intervals, spread across multiple octaves
        voicing = []

        # Pad voicing typically spans 2-3 octaves for richness
        # Low register (root octave)
        for interval in intervals:
            voicing.append(root_midi + interval)

        # Mid register (one octave up, voice leading)
        # Skip the root to avoid doubling
        for interval in intervals[1:]:
            voicing.append(root_midi + 12 + interval)

        # High register (two octaves up, lead voice)
        # Usually just the 3rd or 5th for shimmer
        if len(intervals) > 1:
            voicing.append(root_midi + 24 + intervals[1])  # Major/minor 3rd up top

        return voicing

    def generate_pads(self, chord_progression, chord_timings, tempo_bpm, key_info, style):
        """
        Generate pad sustains following chord progression.

        Music Theory Approach:
        1. Create voicing for each chord (root + intervals across octaves)
        2. Hold each voicing for the duration of the chord
        3. Add slow arpeggiation (play voices in sequence) for movement
        4. Apply gentle envelope (soft attack/release)
        5. Vary expression based on detected expression level

        Args:
            chord_progression: list of chord names ["C major", "F major", ...]
            chord_timings: list of start times for each chord (seconds)
            tempo_bpm: tempo in beats per minute
            key_info: dict with detected key info
            style: dict with detected style (expression, etc.)

        Returns:
            dict with:
                - sustain_notes: notes for sustained pads
                - arpeggio_notes: notes for arpeggiated movement
                - combined_notes: all notes mixed
                - combined_timing: timings
                - combined_dynamics: velocities
                - combined_durations: note lengths
                - description: text summary
        """

        if len(chord_progression) == 0:
            return {'error': 'Empty chord progression'}

        sustain_notes = []
        sustain_timing = []
        sustain_dynamics = []
        sustain_durations = []

        arpeggio_notes = []
        arpeggio_timing = []
        arpeggio_dynamics = []
        arpeggio_durations = []

        # Extract style
        expression = style.get('expression', 0.5)

        # Get key root MIDI (middle C = 60)
        key_root_name = key_info.get('key', 'C').split()[0]
        if key_root_name in self.note_names:
            key_root_semitone = self.note_names.index(key_root_name)
        else:
            key_root_semitone = 0  # Default to C

        # Pad plays in mid-high register (C3-C5)
        pad_base_midi = 48 + key_root_semitone  # C3 adjusted by key

        # Process each chord
        for chord_idx, chord_name in enumerate(chord_progression):
            chord_start = chord_timings[chord_idx]

            # Determine chord duration
            if chord_idx + 1 < len(chord_timings):
                chord_end = chord_timings[chord_idx + 1]
            else:
                # Last chord: assume one measure (4 beats)
                beat_duration = 60.0 / tempo_bpm
                chord_end = chord_start + 4 * beat_duration

            chord_duration = chord_end - chord_start

            # Generate voicing for this chord
            voicing = self.generate_pad_voicing(chord_name, pad_base_midi)

            # ─────────────────────────────────────────────────
            # SUSTAIN NOTES: Hold each voice for chord duration
            # ─────────────────────────────────────────────────
            for voice_idx, midi_note in enumerate(voicing):
                sustain_notes.append(midi_note)
                sustain_timing.append(chord_start)

                # Dynamics: lower voices softer, higher voices brighter
                # Base: pad is subtle (0.4-0.6 range)
                base_dynamic = 0.4 + (voice_idx / len(voicing)) * 0.2
                # Add expression variation
                sustain_dynamics.append(base_dynamic + expression * 0.1)

                # Duration: entire chord
                # Add slight crossfade between chords (overlap)
                fade_overlap = 0.1
                if chord_idx + 1 < len(chord_progression):
                    sustain_duration = chord_duration + fade_overlap
                else:
                    sustain_duration = chord_duration

                sustain_durations.append(sustain_duration)

            # ─────────────────────────────────────────────────
            # ARPEGGIO NOTES: Slow arpeggiation for movement
            # ─────────────────────────────────────────────────
            if chord_duration > 0.5 and len(voicing) > 1:
                # Arpeggiate at half-note speed
                beat_duration = 60.0 / tempo_bpm
                arpeggio_speed = beat_duration * 2  # One arpeggio every 2 beats

                arpeggio_time = chord_start
                voice_idx = 0

                while arpeggio_time < chord_end:
                    # Cycle through voicing notes
                    midi_note = voicing[voice_idx % len(voicing)]

                    arpeggio_notes.append(midi_note)
                    arpeggio_timing.append(arpeggio_time)

                    # Arpeggio notes are quieter than sustain (they're embellishment)
                    arpeggio_dynamics.append(0.3 + expression * 0.1)

                    # Short duration (eighth note)
                    arpeggio_durations.append(beat_duration * 0.5)

                    arpeggio_time += arpeggio_speed
                    voice_idx += 1

        # Combine sustain and arpeggio
        all_notes = sustain_notes + arpeggio_notes
        all_timing = sustain_timing + arpeggio_timing
        all_dynamics = sustain_dynamics + arpeggio_dynamics
        all_durations = sustain_durations + arpeggio_durations

        # Sort by timing
        if len(all_timing) > 0:
            sorted_indices = np.argsort(all_timing)
            all_notes = [all_notes[i] for i in sorted_indices]
            all_timing = [all_timing[i] for i in sorted_indices]
            all_dynamics = [all_dynamics[i] for i in sorted_indices]
            all_durations = [all_durations[i] for i in sorted_indices]

        return {
            'sustain': {
                'notes': sustain_notes,
                'timing': sustain_timing,
                'dynamics': sustain_dynamics,
                'durations': sustain_durations
            },
            'arpeggio': {
                'notes': arpeggio_notes,
                'timing': arpeggio_timing,
                'dynamics': arpeggio_dynamics,
                'durations': arpeggio_durations
            },
            'combined': {
                'notes': all_notes,
                'timing': all_timing,
                'dynamics': all_dynamics,
                'durations': all_durations
            },
            'description': f'Pad voicings: {len(sustain_notes)} sustain notes, {len(arpeggio_notes)} arpeggio notes'
        }

    def generate_pads_verbose(self, chord_progression, chord_timings, tempo_bpm, key_info, style, verbosity=1):
        """Generate pads with progress messages"""

        if verbosity >= 1:
            print("[Pad Generation]")
            print(f"  → Input: {len(chord_progression)} chords in {key_info.get('key', 'unknown')} key")
            print(f"           Tempo: {tempo_bpm} BPM, Expression: {style.get('expression', 0.5):.1%}")

        result = self.generate_pads(chord_progression, chord_timings, tempo_bpm, key_info, style)

        if 'error' not in result and verbosity >= 1:
            print(f"  ✓ Generated pads:")
            print(f"    Sustain voices: {len(result['sustain']['notes'])} notes")
            print(f"    Arpeggio notes: {len(result['arpeggio']['notes'])} notes")
            print(f"    Total: {len(result['combined']['notes'])} notes")
            if result['combined']['timing']:
                print(f"    Duration: {result['combined']['timing'][0]:.2f}s - {result['combined']['timing'][-1] + result['combined']['durations'][-1]:.2f}s")

        return result

    def _midi_to_note_name(self, midi_note):
        """Convert MIDI note number to note name"""
        octave = (midi_note // 12) - 1
        note = self.note_names[midi_note % 12]
        return f"{note}{octave}"


# ─────────────────────────────────────────────────
# TEST / DEMONSTRATION
# ─────────────────────────────────────────────────

if __name__ == "__main__":

    print("\n╔════════════════════════════════════════════════╗")
    print("║  MASTERCRAFTER PAD GENERATOR TEST             ║")
    print("╚════════════════════════════════════════════════╝\n")

    # Test 1: Simple progression with moderate expression
    print("Test 1: Pad voicings for C→F→G→C progression")
    print("─" * 50)

    chord_progression = ["C major", "F major", "G major", "C major"]
    chord_timings = [0.0, 2.0, 4.0, 6.0]
    tempo_bpm = 120

    key_info = {'key': 'C major', 'root_hz': 261.6}
    style = {
        'articulation': 'legato',
        'timing': 'straight',
        'expression': 0.5
    }

    generator = PadGenerator()
    result = generator.generate_pads_verbose(
        chord_progression, chord_timings, tempo_bpm, key_info, style, verbosity=1
    )

    print(f"\n  Sustain notes (one per voice, per chord):")
    for i, (note, time, dyn, dur) in enumerate(zip(result['sustain']['notes'][:12],
                                                     result['sustain']['timing'][:12],
                                                     result['sustain']['dynamics'][:12],
                                                     result['sustain']['durations'][:12])):
        note_name = generator._midi_to_note_name(note)
        print(f"    {i+1}. {note_name:3s} @ {time:.2f}s (vel: {dyn:.2f}, dur: {dur:.2f}s)")

    print(f"\n  Arpeggio notes (embellishment/movement):")
    if result['arpeggio']['notes']:
        for i, (note, time, dyn, dur) in enumerate(zip(result['arpeggio']['notes'][:8],
                                                         result['arpeggio']['timing'][:8],
                                                         result['arpeggio']['dynamics'][:8],
                                                         result['arpeggio']['durations'][:8])):
            note_name = generator._midi_to_note_name(note)
            print(f"    {i+1}. {note_name:3s} @ {time:.2f}s (vel: {dyn:.2f}, dur: {dur:.2f}s)")
    else:
        print("    (no arpeggios generated for this progression)")

    # Test 2: Higher expression
    print("\n\nTest 2: Same progression with high expression (0.8)")
    print("─" * 50)

    style_expressive = {
        'articulation': 'legato',
        'timing': 'straight',
        'expression': 0.8
    }

    result_expressive = generator.generate_pads_verbose(
        chord_progression, chord_timings, tempo_bpm, key_info, style_expressive, verbosity=1
    )

    print(f"\n  Dynamics comparison:")
    print(f"    Low expression (0.5): sustain dynamics {result['sustain']['dynamics'][0]:.2f} - {result['sustain']['dynamics'][-1]:.2f}")
    print(f"    High expression (0.8): sustain dynamics {result_expressive['sustain']['dynamics'][0]:.2f} - {result_expressive['sustain']['dynamics'][-1]:.2f}")

    # Test 3: Different key (F major)
    print("\n\nTest 3: F major chord progression")
    print("─" * 50)

    chord_progression_f = ["F major", "Bb major", "C major", "F major"]
    key_info_f = {'key': 'F major', 'root_hz': 349.2}

    result_f = generator.generate_pads_verbose(
        chord_progression_f, chord_timings, tempo_bpm, key_info_f, style, verbosity=1
    )

    print(f"\n  Voicing notes (first chord only):")
    # Find notes from first chord only (duration indicator)
    first_chord_notes = []
    for i, (note, time) in enumerate(zip(result_f['sustain']['notes'], result_f['sustain']['timing'])):
        if time < chord_timings[1]:  # First chord is from 0.0 to 2.0
            note_name = generator._midi_to_note_name(note)
            first_chord_notes.append((note_name, note))

    print(f"    F major voicing: {' - '.join([n[0] for n in first_chord_notes])}")

    print("\n✓ Pad generation working!")
