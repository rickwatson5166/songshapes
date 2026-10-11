"""
Accompaniment Generator for SongShapes Phase 2
Generate bass + drums locked to detected melody/chords
Theory-based music generation (no ML, no copyright issues)
"""

import numpy as np
from collections import namedtuple


Note = namedtuple('Note', ['pitch_hz', 'start_time', 'duration', 'velocity', 'note_name'])
DrumEvent = namedtuple('DrumEvent', ['drum_type', 'start_time', 'duration', 'velocity'])


class BassLineGenerator:
    """Generate bass lines following chord progressions"""

    def __init__(self, sr=44100):
        self.sr = sr

    def generate(self, chords, tempo_bpm=120, key='C', articulation='legato'):
        """
        Generate bass line from chord progression

        Args:
            chords: List of {'root': 'C', 'quality': 'major', 'start_time': 0, 'duration': 1}
            tempo_bpm: Tempo in BPM
            key: Key center (not used for MVP, but good for future)
            articulation: 'legato' (smooth) or 'staccato' (punchy)

        Returns:
            bass_notes: List of Note objects
        """
        bass_notes = []
        note_map = {
            'C': 261.63, 'C#': 277.18, 'D': 293.66, 'D#': 311.13, 'E': 329.63,
            'F': 349.23, 'F#': 369.99, 'G': 392.00, 'G#': 415.30, 'A': 440.00,
            'A#': 466.16, 'B': 493.88
        }

        for i, chord in enumerate(chords):
            root = chord['root']
            start_time = chord['start_time']
            duration = chord['duration']

            # Bass note: root note, one octave down from normal
            base_f0 = note_map[root]
            bass_f0 = base_f0 / 2  # One octave down

            # Note duration depends on articulation
            if articulation == 'staccato':
                note_duration = duration * 0.4  # Short punchy notes
                note_velocity = 0.7
            else:
                note_duration = duration * 0.9  # Legato, sustained
                note_velocity = 0.6

            # Add approach note on chord changes (except first chord)
            if i > 0:
                prev_root = chords[i-1]['root']
                prev_f0 = note_map[prev_root] / 2

                # Chromatic approach: semitone below target
                semitone_down = bass_f0 / (2 ** (1/12))  # Down one semitone
                approach_duration = 0.1

                bass_notes.append(Note(
                    pitch_hz=semitone_down,
                    start_time=start_time - approach_duration,
                    duration=approach_duration,
                    velocity=0.5,
                    note_name=f"{root}b2_approach"
                ))

            # Main bass note for this chord
            bass_notes.append(Note(
                pitch_hz=bass_f0,
                start_time=start_time,
                duration=note_duration,
                velocity=note_velocity,
                note_name=f"{root}2"
            ))

            # Add passing tones for staccato (extra rhythmic interest)
            if articulation == 'staccato' and duration > 0.5:
                # Middle of chord, add a passing tone (perfect 5th)
                semitones_up = 7  # Perfect 5th
                passing_f0 = bass_f0 * (2 ** (semitones_up / 12))
                passing_time = start_time + duration * 0.5
                passing_duration = 0.1

                bass_notes.append(Note(
                    pitch_hz=passing_f0,
                    start_time=passing_time,
                    duration=passing_duration,
                    velocity=0.5,
                    note_name=f"{root}5_passing"
                ))

        return bass_notes

    def note_to_midi(self, f0_hz):
        """Convert frequency to MIDI note number"""
        if f0_hz <= 0:
            return 0
        return int(round(69 + 12 * np.log2(f0_hz / 440.0)))


class DrumPatternGenerator:
    """Generate drum patterns (kick, snare, hi-hat) for rock/pop music"""

    def __init__(self, sr=44100):
        self.sr = sr

    def generate(self, chords, tempo_bpm=120, key='C', articulation='legato'):
        """
        Generate drum pattern from chord progression

        Args:
            chords: List of chord dicts with timing
            tempo_bpm: Tempo in BPM
            key: Key center (unused for MVP)
            articulation: 'legato' or 'staccato' affects hi-hat density

        Returns:
            drum_events: List of DrumEvent objects
        """
        # Convert tempo to beat duration
        beat_duration = 60.0 / tempo_bpm

        drum_events = []
        total_time = 0

        # Generate drum pattern for each chord
        for chord in chords:
            chord_start = chord['start_time']
            chord_duration = chord['duration']
            num_beats = int(np.ceil(chord_duration / beat_duration))

            for beat in range(num_beats):
                beat_time = chord_start + beat * beat_duration

                if beat_time >= chord_start + chord_duration:
                    break

                # Kick pattern: beats 1, 2-and, 3, 4-and (standard rock)
                kick_times = [0, 0.5, 1.0, 1.5]  # In beat units
                if (beat % 2 == 0) or ((beat + 1) % 2 == 0):
                    for offset in kick_times:
                        kick_time = beat_time + offset * beat_duration
                        if kick_time < chord_start + chord_duration:
                            # Kick dynamics: louder on main beats
                            velocity = 0.85 if offset in [0, 1.0] else 0.65
                            drum_events.append(DrumEvent(
                                drum_type='kick',
                                start_time=kick_time,
                                duration=0.15,
                                velocity=velocity
                            ))

                # Snare on backbeat (beats 2 and 4)
                if beat % 2 == 1:
                    snare_time = beat_time
                    drum_events.append(DrumEvent(
                        drum_type='snare',
                        start_time=snare_time,
                        duration=0.1,
                        velocity=0.8
                    ))

                # Hi-hat pattern
                hihat_eighth_times = [0, 0.5, 1.0, 1.5]  # Eighth notes
                if articulation == 'staccato':
                    # Sixteenth notes for staccato (busier feel)
                    hihat_times = [0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75]
                else:
                    # Eighth notes for legato (simpler feel)
                    hihat_times = hihat_eighth_times

                for offset in hihat_times:
                    hihat_time = beat_time + offset * beat_duration
                    if hihat_time < chord_start + chord_duration:
                        # Alternate closed/open hi-hat for pocket
                        is_closed = (int(hihat_time * 100) % 2 == 0)  # Pseudo-random
                        # Velocity variation for pocket feel
                        velocity = 0.6 + 0.15 * (is_closed - 0.5)

                        drum_events.append(DrumEvent(
                            drum_type='hihat_closed' if is_closed else 'hihat_open',
                            start_time=hihat_time,
                            duration=0.08,
                            velocity=velocity
                        ))

        return drum_events


class AccompanimentGenerator:
    """High-level orchestrator for bass + drums accompaniment"""

    def __init__(self, sr=44100):
        self.sr = sr
        self.bass_gen = BassLineGenerator(sr)
        self.drum_gen = DrumPatternGenerator(sr)

    def generate(self, melody_data, chords, tempo_bpm=120, key='C'):
        """
        Generate complete accompaniment (bass + drums)

        Args:
            melody_data: {'f0_contour': array, 'confidence': array, ...}
            chords: List of detected chords with timing
            tempo_bpm: Tempo in BPM
            key: Key center

        Returns:
            accompaniment: {
                'bass': list of Note objects,
                'drums': list of DrumEvent objects,
                'metadata': {...}
            }
        """
        # Detect articulation style from melody
        articulation = self._detect_articulation(melody_data)

        # Generate bass
        bass_notes = self.bass_gen.generate(
            chords=chords,
            tempo_bpm=tempo_bpm,
            key=key,
            articulation=articulation
        )

        # Generate drums
        drum_events = self.drum_gen.generate(
            chords=chords,
            tempo_bpm=tempo_bpm,
            key=key,
            articulation=articulation
        )

        return {
            'bass': bass_notes,
            'drums': drum_events,
            'metadata': {
                'tempo_bpm': tempo_bpm,
                'key': key,
                'articulation': articulation,
                'num_bass_notes': len(bass_notes),
                'num_drum_events': len(drum_events)
            }
        }

    def _detect_articulation(self, melody_data):
        """
        Detect if melody is legato (smooth) or staccato (punchy)

        Strategy: Analyze F0 contour for gaps between notes
        """
        f0_contour = melody_data.get('f0_contour', np.array([]))

        if len(f0_contour) == 0:
            return 'legato'  # Default

        # Compute gaps: when F0 drops to 0
        voiced_mask = f0_contour > 0
        gaps = []
        gap_start = None

        for i in range(len(voiced_mask)):
            if not voiced_mask[i] and gap_start is None:
                gap_start = i
            elif voiced_mask[i] and gap_start is not None:
                gap_length = i - gap_start
                gaps.append(gap_length)
                gap_start = None

        if len(gaps) == 0:
            return 'legato'

        # Average gap length
        avg_gap = np.mean(gaps)

        # If gaps are small, it's legato; if gaps are large, it's staccato
        # Threshold: ~0.1 second at 44.1kHz with hop_length=512
        gap_threshold = 8  # frames

        return 'staccato' if avg_gap > gap_threshold else 'legato'


if __name__ == '__main__':
    # Test accompaniment generation
    print("Testing Accompaniment Generator")
    print("=" * 60)

    # Create test chord progression
    chords = [
        {'root': 'C', 'quality': 'major', 'start_time': 0.0, 'duration': 1.0},
        {'root': 'F', 'quality': 'major', 'start_time': 1.0, 'duration': 1.0},
        {'root': 'G', 'quality': 'major', 'start_time': 2.0, 'duration': 1.0},
        {'root': 'C', 'quality': 'major', 'start_time': 3.0, 'duration': 1.0}
    ]

    # Mock melody data
    melody_data = {
        'f0_contour': np.random.randn(100),
        'confidence': np.random.rand(100)
    }

    # Generate accompaniment
    gen = AccompanimentGenerator()
    accompaniment = gen.generate(
        melody_data=melody_data,
        chords=chords,
        tempo_bpm=120,
        key='C'
    )

    print(f"✓ Generated accompaniment:")
    print(f"  Bass: {accompaniment['metadata']['num_bass_notes']} notes")
    print(f"  Drums: {accompaniment['metadata']['num_drum_events']} events")
    print(f"  Articulation: {accompaniment['metadata']['articulation']}")
    print(f"  Tempo: {accompaniment['metadata']['tempo_bpm']} BPM")

    print(f"\n✓ Bass notes:")
    for note in accompaniment['bass'][:5]:
        print(f"  {note.note_name}: {note.pitch_hz:.1f}Hz @ {note.start_time:.2f}s, "
              f"duration {note.duration:.2f}s, velocity {note.velocity:.2f}")

    print(f"\n✓ Drum events (first 10):")
    for event in accompaniment['drums'][:10]:
        print(f"  {event.drum_type}: {event.start_time:.2f}s, velocity {event.velocity:.2f}")

    print("=" * 60)
