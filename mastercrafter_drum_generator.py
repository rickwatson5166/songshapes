#!/usr/bin/env python3
"""
Mastercrafter Drum Pattern Generator
Generate drum patterns that follow tempo, style, and expression
"""

import numpy as np


class DrumPatternGenerator:
    """Generate drum patterns (kick, snare, hi-hat) following detected style"""

    def __init__(self):
        # MIDI note numbers for drum sounds
        self.drums = {
            'kick': 36,      # C1 (kick drum)
            'snare': 38,     # D1 (snare)
            'hi_hat_closed': 42,  # F#1 (closed hi-hat)
            'hi_hat_open': 46,    # A#1 (open hi-hat)
            'tom_high': 50,  # D2 (high tom)
            'tom_mid': 47,   # B1 (mid tom)
            'tom_low': 45,   # A1 (low tom)
        }

    def generate_drum_pattern(self, chord_progression, chord_timings, tempo_bpm, key_info, style):
        """
        Generate drum pattern following detected style.

        Music Theory Approach:
        1. Generate kick pattern (strong downbeats + syncopation)
        2. Generate snare pattern (backbeat: beats 2 and 4)
        3. Generate hi-hat pattern (timekeeping: eighth or sixteenth notes)
        4. Vary dynamics based on expression level
        5. Apply swing timing if detected
        6. Respect articulation style (punchy vs smooth)

        Args:
            chord_progression: list of chord names ["C major", "F major", ...]
            chord_timings: list of start times for each chord (seconds)
            tempo_bpm: tempo in beats per minute
            key_info: dict with detected key info
            style: dict with detected style (articulation, timing, expression)

        Returns:
            dict with:
                - kick: {notes, timing, dynamics, durations}
                - snare: {notes, timing, dynamics, durations}
                - hi_hat: {notes, timing, dynamics, durations}
                - combined: {notes, timing, dynamics, durations} (all drums mixed)
                - description: text summary
        """

        if len(chord_progression) == 0:
            return {
                'error': 'Empty chord progression'
            }

        # Calculate beat duration
        beat_duration = 60.0 / tempo_bpm  # seconds per beat

        # Determine phrase duration (from first chord to end of last chord)
        phrase_start = chord_timings[0]
        if len(chord_timings) > 1:
            phrase_duration = chord_timings[-1] - chord_timings[0] + beat_duration * 4
        else:
            phrase_duration = beat_duration * 4  # Default: one measure

        phrase_end = phrase_start + phrase_duration

        # Detect style characteristics
        is_staccato = style.get('articulation') == 'staccato'
        has_swing = style.get('timing') in ['swing', 'moderate_swing']
        swing_factor = style.get('swing_factor', 0.0)
        expression = style.get('expression', 0.5)

        # Generate drum parts
        kick_notes, kick_timing, kick_dynamics, kick_durations = self._generate_kick_pattern(
            phrase_start, phrase_end, beat_duration, is_staccato, has_swing, swing_factor, expression
        )

        snare_notes, snare_timing, snare_dynamics, snare_durations = self._generate_snare_pattern(
            phrase_start, phrase_end, beat_duration, is_staccato, expression
        )

        hi_hat_notes, hi_hat_timing, hi_hat_dynamics, hi_hat_durations = self._generate_hihat_pattern(
            phrase_start, phrase_end, beat_duration, has_swing, swing_factor, expression, is_staccato
        )

        # Combine all drums
        all_notes = kick_notes + snare_notes + hi_hat_notes
        all_timing = kick_timing + snare_timing + hi_hat_timing
        all_dynamics = kick_dynamics + snare_dynamics + hi_hat_dynamics
        all_durations = kick_durations + snare_durations + hi_hat_durations

        # Sort by timing
        if len(all_timing) > 0:
            sorted_indices = np.argsort(all_timing)
            all_notes = [all_notes[i] for i in sorted_indices]
            all_timing = [all_timing[i] for i in sorted_indices]
            all_dynamics = [all_dynamics[i] for i in sorted_indices]
            all_durations = [all_durations[i] for i in sorted_indices]

        return {
            'kick': {
                'notes': kick_notes,
                'timing': kick_timing,
                'dynamics': kick_dynamics,
                'durations': kick_durations
            },
            'snare': {
                'notes': snare_notes,
                'timing': snare_timing,
                'dynamics': snare_dynamics,
                'durations': snare_durations
            },
            'hi_hat': {
                'notes': hi_hat_notes,
                'timing': hi_hat_timing,
                'dynamics': hi_hat_dynamics,
                'durations': hi_hat_durations
            },
            'combined': {
                'notes': all_notes,
                'timing': all_timing,
                'dynamics': all_dynamics,
                'durations': all_durations
            },
            'description': f'Drum pattern: {len(kick_notes)} kicks, {len(snare_notes)} snares, {len(hi_hat_notes)} hi-hats'
        }

    def _generate_kick_pattern(self, phrase_start, phrase_end, beat_duration,
                               is_staccato, has_swing, swing_factor, expression):
        """Generate kick drum pattern"""

        kick_notes = []
        kick_timing = []
        kick_dynamics = []
        kick_durations = []

        current_time = phrase_start

        while current_time < phrase_end:
            # Standard kick pattern: 1, 2-and, 3, 4-and (with swing variations)
            beat_positions = [0, 1.5, 2, 3.5]  # As fractions of 4-beat measure

            for beat_pos in beat_positions:
                kick_time = current_time + beat_pos * beat_duration

                if kick_time < phrase_end:
                    # Apply swing timing if present
                    if has_swing and beat_pos in [1.5, 3.5]:  # Offbeats
                        # Swing moves offbeats later in time
                        kick_time += beat_duration * swing_factor * 0.3

                    kick_notes.append(self.drums['kick'])
                    kick_timing.append(kick_time)

                    # Dynamics: kick hits hard on 1 and 3, softer on 2-and and 4-and
                    if beat_pos in [0, 2]:
                        base_dynamics = 0.85
                    else:
                        base_dynamics = 0.65

                    # Add expression variation
                    kick_dynamics.append(base_dynamics + expression * 0.15)

                    # Duration: short percussive hits
                    if is_staccato:
                        kick_durations.append(0.08)  # Very short
                    else:
                        kick_durations.append(0.12)  # Standard kick duration

            current_time += 4 * beat_duration  # One measure

        return kick_notes, kick_timing, kick_dynamics, kick_durations

    def _generate_snare_pattern(self, phrase_start, phrase_end, beat_duration, is_staccato, expression):
        """Generate snare pattern (backbeat on 2 and 4)"""

        snare_notes = []
        snare_timing = []
        snare_dynamics = []
        snare_durations = []

        current_time = phrase_start

        while current_time < phrase_end:
            # Snare on beat 2 and beat 4 (backbeat)
            snare_beat_positions = [1, 3]  # As beat numbers in 4-beat measure

            for beat_num in snare_beat_positions:
                snare_time = current_time + (beat_num - 1) * beat_duration

                if snare_time < phrase_end:
                    snare_notes.append(self.drums['snare'])
                    snare_timing.append(snare_time)

                    # Snare hits hard (backbeat is prominent)
                    base_dynamics = 0.8
                    snare_dynamics.append(base_dynamics + expression * 0.1)

                    # Duration: snare is a percussive hit
                    if is_staccato:
                        snare_durations.append(0.1)
                    else:
                        snare_durations.append(0.15)

            current_time += 4 * beat_duration  # One measure

        return snare_notes, snare_timing, snare_dynamics, snare_durations

    def _generate_hihat_pattern(self, phrase_start, phrase_end, beat_duration,
                               has_swing, swing_factor, expression, is_staccato):
        """Generate hi-hat pattern (timekeeping on eighths or sixteenths)"""

        hi_hat_notes = []
        hi_hat_timing = []
        hi_hat_dynamics = []
        hi_hat_durations = []

        # Determine subdivision: sixteenths if staccato, eighths if legato
        if is_staccato:
            subdivision = 4  # Sixteenth notes (4 per beat)
        else:
            subdivision = 2  # Eighth notes (2 per beat)

        current_time = phrase_start
        measure_beat = 0

        while current_time < phrase_end:
            # Hi-hat on each subdivision
            for i in range(4 * subdivision):  # 4 beats per measure
                hihat_time = current_time + (i / subdivision) * beat_duration

                if hihat_time < phrase_end:
                    # Alternate between closed and open hi-hat
                    # Closed on most hits, open on selected beats for variation
                    on_beat = (i % subdivision) == 0
                    if on_beat and (i // subdivision) % 2 == 1:  # Open on upbeats
                        hihat_note = self.drums['hi_hat_open']
                        base_dynamics = 0.6
                    else:
                        hihat_note = self.drums['hi_hat_closed']
                        base_dynamics = 0.5

                    # Apply swing timing if present
                    if has_swing and (i % subdivision) != 0:  # Apply to sixteenth-note positions
                        hihat_time += beat_duration * swing_factor * 0.2

                    hi_hat_notes.append(hihat_note)
                    hi_hat_timing.append(hihat_time)

                    # Hi-hat dynamics vary for pocket
                    hi_hat_dynamics.append(base_dynamics + np.random.rand() * 0.1 + expression * 0.05)

                    # Hi-hat duration: very short
                    if is_staccato:
                        hi_hat_durations.append(0.06)
                    else:
                        hi_hat_durations.append(0.08)

            current_time += 4 * beat_duration  # One measure

        return hi_hat_notes, hi_hat_timing, hi_hat_dynamics, hi_hat_durations

    def generate_drum_pattern_verbose(self, chord_progression, chord_timings, tempo_bpm, key_info, style, verbosity=1):
        """Generate drum pattern with progress messages"""

        if verbosity >= 1:
            print("[Drum Pattern Generation]")
            print(f"  → Input: {len(chord_progression)} chords, {tempo_bpm} BPM")
            print(f"           Style: {style.get('articulation', 'unknown')}, {style.get('timing', 'unknown')}")

        result = self.generate_drum_pattern(chord_progression, chord_timings, tempo_bpm, key_info, style)

        if 'error' not in result and verbosity >= 1:
            print(f"  ✓ Generated drum pattern:")
            print(f"    Kicks: {len(result['kick']['notes'])} hits")
            print(f"    Snares: {len(result['snare']['notes'])} hits")
            print(f"    Hi-hats: {len(result['hi_hat']['notes'])} hits")
            print(f"    Total: {len(result['combined']['notes'])} drum events")
            if result['combined']['timing']:
                print(f"    Duration: {result['combined']['timing'][0]:.2f}s - {result['combined']['timing'][-1]:.2f}s")

        return result


# ─────────────────────────────────────────────────
# TEST / DEMONSTRATION
# ─────────────────────────────────────────────────

if __name__ == "__main__":

    print("\n╔════════════════════════════════════════════════╗")
    print("║  MASTERCRAFTER DRUM GENERATOR TEST            ║")
    print("╚════════════════════════════════════════════════╝\n")

    # Test 1: Simple progression with legato style
    print("Test 1: Drum pattern at 120 BPM (Legato, Straight)")
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

    generator = DrumPatternGenerator()
    result = generator.generate_drum_pattern_verbose(
        chord_progression, chord_timings, tempo_bpm, key_info, style_legato, verbosity=1
    )

    print(f"\n  Kick pattern:")
    for i, (note, time, dyn, dur) in enumerate(zip(result['kick']['notes'][:8],
                                                     result['kick']['timing'][:8],
                                                     result['kick']['dynamics'][:8],
                                                     result['kick']['durations'][:8])):
        print(f"    {i+1}. Kick @ {time:.2f}s (vel: {dyn:.2f}, dur: {dur:.2f}s)")

    print(f"\n  Snare pattern:")
    for i, (note, time, dyn, dur) in enumerate(zip(result['snare']['notes'][:4],
                                                     result['snare']['timing'][:4],
                                                     result['snare']['dynamics'][:4],
                                                     result['snare']['durations'][:4])):
        print(f"    {i+1}. Snare @ {time:.2f}s (vel: {dyn:.2f}, dur: {dur:.2f}s)")

    print(f"\n  Hi-hat pattern (first 16 events):")
    for i, (note, time, dyn, dur) in enumerate(zip(result['hi_hat']['notes'][:16],
                                                     result['hi_hat']['timing'][:16],
                                                     result['hi_hat']['dynamics'][:16],
                                                     result['hi_hat']['durations'][:16])):
        hat_type = "closed" if note == 42 else "open"
        print(f"    {i+1}. Hi-hat ({hat_type}) @ {time:.3f}s (vel: {dyn:.2f}, dur: {dur:.2f}s)")

    # Test 2: Same progression but staccato style
    print("\n\nTest 2: Drum pattern at 120 BPM (Staccato)")
    print("─" * 50)

    style_staccato = {
        'articulation': 'staccato',
        'timing': 'straight',
        'swing_factor': 0.0,
        'expression': 0.3
    }

    result_staccato = generator.generate_drum_pattern_verbose(
        chord_progression, chord_timings, tempo_bpm, key_info, style_staccato, verbosity=1
    )

    print(f"\n  Pattern summary (Staccato):")
    print(f"    Total drum events: {len(result_staccato['combined']['notes'])}")
    print(f"    Kick hits: {len(result_staccato['kick']['notes'])}")
    print(f"    Snare hits: {len(result_staccato['snare']['notes'])}")
    print(f"    Hi-hat hits: {len(result_staccato['hi_hat']['notes'])}")

    # Test 3: Faster tempo with swing
    print("\n\nTest 3: Drum pattern at 160 BPM with Swing")
    print("─" * 50)

    style_swing = {
        'articulation': 'legato',
        'timing': 'swing',
        'swing_factor': 0.3,
        'expression': 0.6
    }

    result_swing = generator.generate_drum_pattern_verbose(
        chord_progression, chord_timings, 160, key_info, style_swing, verbosity=1
    )

    print(f"\n  Swing characteristics:")
    print(f"    Total drum events: {len(result_swing['combined']['notes'])}")
    print(f"    Swing factor: {style_swing['swing_factor']:.1%}")
    print(f"    Expression: {style_swing['expression']:.1%}")

    print("\n✓ Drum pattern generation working!")
