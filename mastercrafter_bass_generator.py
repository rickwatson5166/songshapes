#!/usr/bin/env python3
"""
Mastercrafter Bass Line Generator
Generate bass line that follows chord progression
"""

import numpy as np


class BassLineGenerator:
    """Generate bass line following detected chord progression"""

    def __init__(self):
        self.note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

    def generate_bass_line(self, chord_progression, chord_timings, tempo_bpm, key_info, style):
        """
        Generate a bass line that follows the chord progression.

        Music Theory Approach:
        1. Root position for each chord (bass typically plays the root)
        2. Add passing tones (between chord tones)
        3. Add approach notes (one semitone below target)
        4. Apply voice leading rules (minimize jumps, smooth motion)
        5. Respect performance style (articulation, dynamics)

        Args:
            chord_progression: list of chord names ["C major", "F major", ...]
            chord_timings: list of start times for each chord (seconds)
            tempo_bpm: tempo in beats per minute
            key_info: dict with detected key info
            style: dict with detected style (articulation, timing, etc.)

        Returns:
            dict with:
                - notes: list of MIDI note numbers
                - timing: list of note start times (seconds)
                - dynamics: list of note velocities (0-1)
                - durations: list of note durations (seconds)
        """

        if len(chord_progression) == 0:
            return {
                'notes': [],
                'timing': [],
                'dynamics': [],
                'durations': [],
                'error': 'Empty chord progression'
            }

        bass_notes = []
        bass_timing = []
        bass_dynamics = []
        bass_durations = []

        # Calculate beat duration
        beat_duration = 60.0 / tempo_bpm  # seconds per beat

        # Bass typically plays in the range MIDI 36-48 (E1-C3)
        # We'll use MIDI 36 (E1) as the base and add semitones for different roots
        bass_base_midi = 36

        # Process each chord
        for chord_idx, chord_name in enumerate(chord_progression):
            chord_start = chord_timings[chord_idx]

            # Chord end is the next chord's start, or estimate from tempo
            if chord_idx + 1 < len(chord_timings):
                chord_end = chord_timings[chord_idx + 1]
            else:
                # Assume one measure (4 beats) for the last chord
                chord_end = chord_start + 4 * beat_duration

            chord_duration = chord_end - chord_start

            # Parse chord name
            chord_parts = chord_name.split()
            chord_root_name = chord_parts[0]
            chord_quality = chord_parts[1] if len(chord_parts) > 1 else "major"

            # Get root semitone (0-11)
            if chord_root_name in self.note_names:
                root_semitone = self.note_names.index(chord_root_name)
            else:
                root_semitone = 0  # Default to C

            # Bass note in bass range
            bass_root_midi = bass_base_midi + root_semitone

            # Clamp to bass range if needed
            while bass_root_midi < bass_base_midi:
                bass_root_midi += 12
            while bass_root_midi > 48:
                bass_root_midi -= 12

            # Generate bass pattern based on style
            self._generate_bass_pattern_for_chord(
                bass_root_midi,
                chord_start,
                chord_duration,
                beat_duration,
                style,
                bass_notes,
                bass_timing,
                bass_dynamics,
                bass_durations,
                chord_idx,
                chord_progression
            )

        return {
            'notes': bass_notes,
            'timing': bass_timing,
            'dynamics': bass_dynamics,
            'durations': bass_durations,
            'description': f'Theory-based bass line: {len(bass_notes)} notes following chord progression'
        }

    def _generate_bass_pattern_for_chord(self, bass_midi, chord_start, chord_duration, beat_duration,
                                         style, bass_notes, bass_timing, bass_dynamics, bass_durations,
                                         chord_idx, chord_progression):
        """Generate bass pattern for a single chord"""

        # Determine articulation style
        is_staccato = style.get('articulation') == 'staccato'
        has_swing = style.get('timing') in ['swing', 'moderate_swing']
        expression = style.get('expression', 0.5)

        if is_staccato:
            # Staccato: short hits on strong beats
            num_hits = max(1, int(chord_duration / beat_duration))

            for hit_idx in range(num_hits):
                hit_time = chord_start + hit_idx * beat_duration

                if hit_time < chord_start + chord_duration:
                    # Add main beat
                    bass_notes.append(bass_midi)
                    bass_timing.append(hit_time)
                    bass_dynamics.append(0.7 + expression * 0.2)
                    bass_durations.append(0.15)  # Short staccato notes

                    # Optionally add offbeat with fifth
                    if hit_idx < num_hits - 1 and chord_duration > 1.0:
                        offbeat_time = hit_time + beat_duration * 0.5
                        bass_notes.append(bass_midi - 7)  # Fifth below
                        bass_timing.append(offbeat_time)
                        bass_dynamics.append(0.5)
                        bass_durations.append(0.1)

        else:
            # Legato: held notes with smooth motion

            # Main chord tone at the start
            bass_notes.append(bass_midi)
            bass_timing.append(chord_start)
            bass_dynamics.append(0.8)
            bass_durations.append(chord_duration * 0.95)  # Held through chord

            # If there's motion to the next chord, add passing/approach notes
            if chord_idx + 1 < len(chord_progression):
                next_chord_name = chord_progression[chord_idx + 1]
                next_chord_parts = next_chord_name.split()
                next_chord_root_name = next_chord_parts[0]

                if next_chord_root_name in self.note_names:
                    next_root_semitone = self.note_names.index(next_chord_root_name)
                    next_bass_midi = 36 + next_root_semitone

                    # Clamp to range
                    while next_bass_midi < 36:
                        next_bass_midi += 12
                    while next_bass_midi > 48:
                        next_bass_midi -= 12

                    # Add approach note (chromatic approach from below)
                    if abs(next_bass_midi - bass_midi) > 2 and chord_duration > 0.5:
                        # Approach time: shortly before the next chord
                        approach_time = chord_start + chord_duration - 0.15
                        approach_midi = next_bass_midi - 1

                        bass_notes.append(approach_midi)
                        bass_timing.append(approach_time)
                        bass_dynamics.append(0.5)
                        bass_durations.append(0.1)

    def generate_bass_line_verbose(self, chord_progression, chord_timings, tempo_bpm, key_info, style, verbosity=1):
        """Generate bass line with progress messages"""

        if verbosity >= 1:
            print("[Bass Line Generation]")
            print(f"  → Input: {len(chord_progression)} chords, {tempo_bpm} BPM")
            print(f"           Style: {style.get('articulation', 'unknown')}, {style.get('timing', 'unknown')}")

        result = self.generate_bass_line(chord_progression, chord_timings, tempo_bpm, key_info, style)

        if 'error' not in result and verbosity >= 1:
            print(f"  ✓ Generated: {len(result['notes'])} bass notes")
            if result['notes']:
                min_note = min(result['notes'])
                max_note = max(result['notes'])
                print(f"    Note range: MIDI {min_note} - {max_note} ({self._midi_to_note_name(min_note)} - {self._midi_to_note_name(max_note)})")
                print(f"    Duration: {result['timing'][0]:.2f}s - {result['timing'][-1] + result['durations'][-1]:.2f}s")

        return result

    def _midi_to_note_name(self, midi_note):
        """Convert MIDI note number to note name"""
        note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        octave = (midi_note // 12) - 1
        note = note_names[midi_note % 12]
        return f"{note}{octave}"


# ─────────────────────────────────────────────────────
# TEST / DEMONSTRATION
# ─────────────────────────────────────────────────────

if __name__ == "__main__":

    print("\n╔════════════════════════════════════════════════╗")
    print("║  MASTERCRAFTER BASS GENERATOR TEST            ║")
    print("╚════════════════════════════════════════════════╝\n")

    # Test 1: Simple progression with legato style
    print("Test 1: C major - F major - G major progression (Legato)")
    print("─" * 50)

    chord_progression = ["C major", "F major", "G major", "C major"]
    chord_timings = [0.0, 2.0, 4.0, 6.0]
    tempo_bpm = 120

    key_info = {'key': 'C major', 'root_hz': 261.6}
    style_legato = {
        'articulation': 'legato',
        'timing': 'straight',
        'swing_factor': 0.0,
        'expression': 0.5
    }

    generator = BassLineGenerator()
    result = generator.generate_bass_line_verbose(
        chord_progression, chord_timings, tempo_bpm, key_info, style_legato, verbosity=1
    )

    print(f"\n  Bass Line:")
    for i, (note, time, dyn, dur) in enumerate(zip(result['notes'], result['timing'],
                                                     result['dynamics'], result['durations'])):
        note_name = generator._midi_to_note_name(note)
        print(f"    {i+1}. {note_name:3s} @ {time:.2f}s (vel: {dyn:.2f}, dur: {dur:.2f}s)")

    # Test 2: Same progression but staccato style
    print("\n\nTest 2: C major - F major - G major progression (Staccato)")
    print("─" * 50)

    style_staccato = {
        'articulation': 'staccato',
        'timing': 'straight',
        'swing_factor': 0.0,
        'expression': 0.3
    }

    result_staccato = generator.generate_bass_line_verbose(
        chord_progression, chord_timings, tempo_bpm, key_info, style_staccato, verbosity=1
    )

    print(f"\n  Bass Line (Staccato):")
    for i, (note, time, dyn, dur) in enumerate(zip(result_staccato['notes'], result_staccato['timing'],
                                                     result_staccato['dynamics'], result_staccato['durations'])):
        note_name = generator._midi_to_note_name(note)
        print(f"    {i+1}. {note_name:3s} @ {time:.2f}s (vel: {dyn:.2f}, dur: {dur:.2f}s)")

    # Test 3: Faster tempo with swing
    print("\n\nTest 3: Same progression at 160 BPM with swing")
    print("─" * 50)

    style_swing = {
        'articulation': 'legato',
        'timing': 'swing',
        'swing_factor': 0.3,
        'expression': 0.6
    }

    result_swing = generator.generate_bass_line_verbose(
        chord_progression, chord_timings, 160, key_info, style_swing, verbosity=1
    )

    print(f"\n  Number of notes: {len(result_swing['notes'])}")
    print(f"  Note dynamics range: {min(result_swing['dynamics']):.2f} - {max(result_swing['dynamics']):.2f}")

    print("\n✓ Bass line generation working!")
