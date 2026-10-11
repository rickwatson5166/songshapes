"""
Bass Synthesizer for SongShapes Phase 2
Generate bass notes with harmonics from Note objects
Pure scipy/numpy implementation
"""

import numpy as np
from scipy import signal


class BassSynthesizer:
    """Synthesize bass notes with harmonic content"""

    def __init__(self, sr=44100):
        self.sr = sr

    def synthesize_note(self, note):
        """
        Synthesize a single bass note

        Args:
            note: Note namedtuple with pitch_hz, start_time, duration, velocity, note_name

        Returns:
            audio: numpy array of audio samples
            start_sample: Starting sample index for this note
        """
        pitch_hz = note.pitch_hz
        duration = note.duration
        velocity = note.velocity

        # Skip silence
        if pitch_hz <= 0:
            return np.zeros(int(duration * self.sr)), int(note.start_time * self.sr)

        audio = self._synthesize_bass_note(pitch_hz, duration, velocity, note.note_name)
        start_sample = int(note.start_time * self.sr)
        return audio, start_sample

    def _synthesize_bass_note(self, pitch_hz, duration, velocity, note_name=None):
        """
        Synthesize bass note with harmonic content

        Strategy:
        - Fundamental + 2nd harmonic (one octave up) + 3rd harmonic (one octave + fifth)
        - Envelope: attack (10-20ms), sustain, release
        - Articulation affects: attack time and sustain level
        """
        n_samples = int(duration * self.sr)
        t = np.arange(n_samples) / self.sr

        # Check for approach notes (marked by 'b' for flat in note_name)
        is_approach = note_name and 'approach' in note_name

        # Fundamental
        fundamental = np.sin(2 * np.pi * pitch_hz * t)

        # Add harmonics for richer bass
        # 2nd harmonic: one octave up (2x frequency), lower amplitude
        harmonic2 = 0.5 * np.sin(2 * np.pi * pitch_hz * 2 * t)

        # 3rd harmonic: octave + perfect fifth (3x frequency), even lower amplitude
        harmonic3 = 0.25 * np.sin(2 * np.pi * pitch_hz * 3 * t)

        # Mix harmonics
        bass = fundamental + harmonic2 + harmonic3

        # Normalize to prevent clipping
        bass = bass / np.max(np.abs(bass) + 1e-8) * 0.9

        # Amplitude envelope
        if is_approach:
            # Approach notes are very short and punchy
            attack_time = 0.02  # 20ms
            release_time = 0.05  # 50ms
        else:
            # Regular notes have smoother envelope
            attack_time = min(0.05, duration * 0.1)  # 50ms attack
            release_time = min(0.1, duration * 0.2)  # 100ms release

        attack_samples = int(attack_time * self.sr)
        release_samples = int(release_time * self.sr)
        sustain_samples = max(0, n_samples - attack_samples - release_samples)

        # Build envelope: attack, sustain, release
        env = np.ones(n_samples)

        # Attack: linear ramp from 0 to 1
        if attack_samples > 0:
            env[:attack_samples] = np.linspace(0, 1, attack_samples)

        # Release: exponential decay at end
        if release_samples > 0:
            sustain_end = attack_samples + sustain_samples
            env[sustain_end:] = np.exp(-8.0 * np.arange(release_samples) / self.sr)

        # Apply envelope and velocity
        bass = bass * env * velocity

        return bass

    def synthesize_bass_track(self, bass_notes, total_duration=None):
        """
        Synthesize all bass notes into a single track

        Args:
            bass_notes: List of Note objects
            total_duration: Total duration in seconds (auto-calculated if None)

        Returns:
            bass_track: numpy array (mono audio) containing all synthesized bass
        """
        if not bass_notes:
            if total_duration is None:
                total_duration = 1.0
            return np.zeros(int(total_duration * self.sr))

        # Calculate total duration
        if total_duration is None:
            max_end_time = max(n.start_time + n.duration for n in bass_notes)
            total_duration = max_end_time + 0.1  # Add small buffer

        n_samples = int(total_duration * self.sr)
        bass_track = np.zeros(n_samples)

        # Synthesize each note
        for note in bass_notes:
            audio, start_sample = self.synthesize_note(note)
            end_sample = start_sample + len(audio)

            # Clip to track length
            if start_sample < n_samples:
                end_sample = min(end_sample, n_samples)
                audio = audio[:end_sample - start_sample]
                bass_track[start_sample:end_sample] += audio

        # Normalize to prevent clipping
        max_val = np.max(np.abs(bass_track))
        if max_val > 0.99:
            bass_track = bass_track * (0.99 / max_val)

        return bass_track


if __name__ == '__main__':
    # Test bass synthesis
    print("Testing Bass Synthesizer")
    print("=" * 60)

    from accompaniment_generator import Note

    # Create test bass line (C major scale)
    bass_notes = [
        Note(261.63 / 2, 0.0, 0.9, 0.6, "C2"),      # C2, 0.9s, legato
        Note(293.66 / 2, 1.0, 0.9, 0.6, "D2"),      # D2
        Note(329.63 / 2, 2.0, 0.9, 0.6, "E2"),      # E2
        Note(392.00 / 2, 3.0, 0.9, 0.6, "G2"),      # G2
    ]

    # Synthesize
    synth = BassSynthesizer(sr=44100)
    bass_track = synth.synthesize_bass_track(bass_notes, total_duration=5.0)

    print(f"✓ Synthesized {len(bass_notes)} bass notes")
    print(f"✓ Bass track duration: {len(bass_track) / 44100:.2f}s")
    print(f"✓ Peak amplitude: {np.max(np.abs(bass_track)):.3f}")
    print(f"✓ RMS level: {np.sqrt(np.mean(bass_track**2)):.3f}")

    # Show individual note synthesis
    print(f"\n✓ Individual note synthesis:")
    for note in bass_notes:
        audio, _ = synth.synthesize_note(note)
        print(f"  {note.note_name} ({note.pitch_hz:.1f}Hz): {len(audio)} samples, "
              f"peak {np.max(np.abs(audio)):.3f}")

    print("=" * 60)
