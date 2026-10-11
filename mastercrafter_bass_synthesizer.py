#!/usr/bin/env python3
"""
Mastercrafter Bass Synthesizer
Convert bass line data to audio waveforms
Synthesize bass with fundamental + harmonics, envelope following detected articulation
"""

import numpy as np


class BassSynthesizer:
    """Synthesize bass sounds from generated bass lines"""

    def __init__(self, sr=44100):
        self.sr = sr

    def midi_to_hz(self, midi_note):
        """Convert MIDI note number to frequency in Hz"""
        return 440 * (2 ** ((midi_note - 69) / 12))

    def synthesize_bass_note(self, frequency, duration, velocity, articulation='legato', attack=0.05, release=0.1):
        """
        Synthesize a single bass note.

        Physical model:
        - Fundamental sine wave
        - 2nd harmonic (octave, softer)
        - 3rd harmonic (fifth, softer still)
        - Envelope shaped by articulation

        Args:
            frequency: Hz
            duration: seconds
            velocity: 0-1 amplitude
            articulation: 'legato' (smooth) or 'staccato' (punchy)
            attack: attack time (seconds)
            release: release time (seconds)

        Returns:
            numpy array of audio samples
        """

        samples = int(duration * self.sr)
        t = np.arange(samples) / self.sr

        # Build harmonic content
        # Fundamental (80% of energy)
        fundamental = 0.8 * np.sin(2 * np.pi * frequency * t)

        # 2nd harmonic: octave up, 50% amplitude
        harmonic2 = 0.4 * np.sin(2 * np.pi * (frequency * 2) * t)

        # 3rd harmonic: perfect 5th (1.5x frequency), 30% amplitude
        harmonic3 = 0.2 * np.sin(2 * np.pi * (frequency * 1.5) * t)

        # Combine harmonics
        waveform = fundamental + harmonic2 + harmonic3

        # Normalize
        waveform = waveform / np.abs(waveform).max()

        # Create envelope
        if articulation == 'legato':
            # Smooth, held envelope
            attack_samples = int(attack * self.sr)
            release_samples = int(release * self.sr)
            sustain_samples = samples - attack_samples - release_samples

            if sustain_samples > 0:
                attack_env = np.linspace(0, 1, attack_samples)
                sustain_env = np.ones(sustain_samples)
                release_env = np.linspace(1, 0, release_samples)
                envelope = np.concatenate([attack_env, sustain_env, release_env])
            else:
                # Short note: use hanning window
                envelope = np.hanning(samples)

        elif articulation == 'staccato':
            # Quick attack, fast decay
            attack_samples = int(0.02 * self.sr)  # 20ms
            decay_samples = samples - attack_samples

            attack_env = np.linspace(0, 1, attack_samples)
            decay_env = np.exp(-np.arange(decay_samples) / (self.sr * 0.15))  # 150ms decay

            envelope = np.concatenate([attack_env, decay_env[:decay_samples]])
        else:
            # Default: gentle envelope
            envelope = np.hanning(samples)

        # Ensure envelope length matches
        envelope = envelope[:samples]

        # Apply envelope and velocity
        audio = velocity * waveform * envelope

        return audio

    def synthesize_bass_line(self, bass_pattern, duration_seconds, tempo_bpm=120):
        """
        Synthesize bass line from generated bass pattern.

        Args:
            bass_pattern: dict from Stage 2 with:
                - notes: MIDI note numbers
                - timing: onset times (seconds)
                - dynamics: velocities (0-1)
                - durations: note lengths (seconds)
            duration_seconds: total duration to synthesize
            tempo_bpm: tempo in BPM

        Returns:
            dict with:
                - audio: synthesized bass waveform
                - sr: sample rate
                - description: text summary
        """

        duration_samples = int(duration_seconds * self.sr)
        audio = np.zeros(duration_samples)

        # Extract bass pattern
        notes = bass_pattern.get('notes', [])
        timing = bass_pattern.get('timing', [])
        dynamics = bass_pattern.get('dynamics', [])
        durations = bass_pattern.get('durations', [])

        if len(notes) == 0:
            return {
                'audio': audio,
                'sr': self.sr,
                'description': 'Empty bass pattern'
            }

        # Determine articulation from average note duration
        avg_duration = np.mean(durations) if len(durations) > 0 else 0.5
        articulation = 'legato' if avg_duration > 0.3 else 'staccato'

        # Synthesize each note
        for note, onset_time, velocity, duration in zip(notes, timing, dynamics, durations):
            # Convert MIDI to frequency
            frequency = self.midi_to_hz(note)

            # Synthesize note
            note_audio = self.synthesize_bass_note(
                frequency,
                duration,
                velocity,
                articulation=articulation,
                attack=0.05,
                release=0.1
            )

            # Place in output
            onset_sample = int(onset_time * self.sr)
            end_sample = min(onset_sample + len(note_audio), duration_samples)
            add_len = end_sample - onset_sample

            if add_len > 0:
                audio[onset_sample:end_sample] += note_audio[:add_len]

        # Soft normalize to prevent clipping
        max_val = np.abs(audio).max()
        if max_val > 0:
            audio = 0.95 * audio / max_val

        return {
            'audio': audio,
            'sr': self.sr,
            'num_notes': len(notes),
            'note_range': (min(notes), max(notes)) if len(notes) > 0 else (0, 0),
            'articulation': articulation,
            'description': f'Bass line: {len(notes)} notes, {articulation} articulation'
        }


# ─────────────────────────────────────────────────
# TEST / DEMONSTRATION
# ─────────────────────────────────────────────────

if __name__ == "__main__":

    import soundfile as sf

    print("\n╔════════════════════════════════════════════════╗")
    print("║  BASS SYNTHESIZER TEST                        ║")
    print("╚════════════════════════════════════════════════╝\n")

    # Create test bass pattern (following C→F→G→C chord progression)
    # 120 BPM = 0.5 seconds per beat, 2 seconds per chord

    # MIDI notes (C major scale bass)
    # C3 = 36, F3 = 41, G3 = 43

    bass_pattern = {
        'notes': [36, 36, 41, 41, 43, 43],  # C, C, F, F, G, G
        'timing': [0.0, 1.0, 2.0, 3.0, 4.0, 5.0],  # One per beat
        'dynamics': [0.7, 0.6, 0.7, 0.6, 0.7, 0.6],  # Slight variation
        'durations': [0.9, 0.9, 0.9, 0.9, 0.9, 0.9]  # Legato notes
    }

    print("Synthesizing bass line...")
    synthesizer = BassSynthesizer(sr=44100)
    result = synthesizer.synthesize_bass_line(bass_pattern, duration_seconds=8.0, tempo_bpm=120)

    print(f"✓ Synthesis complete:")
    print(f"  Notes: {result['num_notes']}")
    print(f"  Note range: MIDI {result['note_range'][0]} - {result['note_range'][1]}")
    print(f"  Articulation: {result['articulation']}")
    print(f"  Audio: {len(result['audio'])} samples ({len(result['audio']) / result['sr']:.2f}s)")
    print(f"  Peak level: {np.abs(result['audio']).max():.3f}")

    # Save
    output_file = '/tmp/test_bass_synthesis.wav'
    sf.write(output_file, result['audio'], result['sr'])
    print(f"\n✓ Saved: {output_file}")
    print("✓ Bass synthesizer working!")
