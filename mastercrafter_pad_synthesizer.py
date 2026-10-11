#!/usr/bin/env python3
"""
Mastercrafter Pad Synthesizer
Convert pad voicing data to audio waveforms
Synthesize sustained pad sounds with long envelopes for atmospheric effect
"""

import numpy as np


class PadSynthesizer:
    """Synthesize pad sounds from generated pad voicings"""

    def __init__(self, sr=44100):
        self.sr = sr

    def midi_to_hz(self, midi_note):
        """Convert MIDI note number to frequency in Hz"""
        return 440 * (2 ** ((midi_note - 69) / 12))

    def synthesize_pad_voice(self, frequency, onset_time, duration, velocity, attack=0.2, release=1.0):
        """
        Synthesize a single pad voice.

        Physical model:
        - Pure sine wave (no harmonics for smooth pad character)
        - Slow attack (200-500ms for pad smoothness)
        - Long release (1-2s for sustain character)

        Args:
            frequency: Hz
            onset_time: when voice starts (seconds)
            duration: how long note sustains (seconds)
            velocity: 0-1 amplitude
            attack: attack time (seconds)
            release: release time (seconds)

        Returns:
            tuple: (audio_samples, start_sample_index, end_sample_index)
        """

        total_duration = onset_time + duration + release
        samples = int(duration * self.sr)

        if samples == 0:
            return np.array([]), int(onset_time * self.sr), int(onset_time * self.sr)

        t = np.arange(samples) / self.sr

        # Pure sine wave (pad characteristic)
        waveform = np.sin(2 * np.pi * frequency * t)

        # Envelope: slow attack, sustain, release
        attack_samples = int(attack * self.sr)
        release_samples = int(release * self.sr)

        if attack_samples + release_samples > samples:
            # Short note: just use hanning window
            envelope = np.hanning(samples)
        else:
            sustain_samples = samples - attack_samples

            # Attack (linear for smooth pad)
            attack_env = np.linspace(0, 1, attack_samples)

            # Sustain + decay (exponential)
            sustain_length = sustain_samples - release_samples
            if sustain_length > 0:
                sustain_env = np.ones(sustain_length)
            else:
                sustain_env = np.array([])

            # Release (exponential decay)
            release_env = np.exp(-np.arange(release_samples) / (self.sr * release))

            envelope = np.concatenate([attack_env, sustain_env, release_env[:sustain_samples]])

        # Ensure correct length
        envelope = envelope[:samples]

        # Apply envelope and velocity
        audio = velocity * waveform * envelope

        onset_sample = int(onset_time * self.sr)
        end_sample = onset_sample + len(audio)

        return audio, onset_sample, end_sample

    def synthesize_pad_voicing(self, pad_pattern, duration_seconds, tempo_bpm=120):
        """
        Synthesize complete pad voicings.

        Args:
            pad_pattern: dict from Stage 2 with:
                - combined:
                    - notes: MIDI note numbers
                    - timing: onset times (seconds)
                    - dynamics: velocities (0-1)
                    - durations: note lengths (seconds)
            duration_seconds: total duration to synthesize
            tempo_bpm: tempo in BPM

        Returns:
            dict with:
                - audio: synthesized pad waveform
                - sr: sample rate
                - description: text summary
        """

        duration_samples = int(duration_seconds * self.sr)
        audio = np.zeros(duration_samples)

        # Extract pad pattern
        combined = pad_pattern.get('combined', {})
        notes = combined.get('notes', [])
        timing = combined.get('timing', [])
        dynamics = combined.get('dynamics', [])
        durations = combined.get('durations', [])

        if len(notes) == 0:
            return {
                'audio': audio,
                'sr': self.sr,
                'description': 'Empty pad pattern'
            }

        # Synthesize each voice
        max_end_sample = 0

        for note, onset_time, velocity, duration in zip(notes, timing, dynamics, durations):
            # Convert MIDI to frequency
            frequency = self.midi_to_hz(note)

            # Synthesize voice
            voice_audio, onset_sample, end_sample = self.synthesize_pad_voice(
                frequency,
                onset_time,
                duration,
                velocity,
                attack=0.3,  # Smooth attack for pad
                release=1.0  # Long release for sustain
            )

            # Place in output
            if len(voice_audio) > 0:
                end_idx = min(end_sample, duration_samples)
                add_len = end_idx - onset_sample

                if add_len > 0 and onset_sample >= 0:
                    audio[onset_sample:end_idx] += voice_audio[:add_len]
                    max_end_sample = max(max_end_sample, end_idx)

        # Crop to actual used duration
        if max_end_sample > 0:
            audio = audio[:max_end_sample]

        # Soft normalize to prevent clipping
        max_val = np.abs(audio).max()
        if max_val > 0:
            audio = 0.85 * audio / max_val  # Pads are subtle

        # Ensure correct length
        if len(audio) < duration_samples:
            audio = np.pad(audio, (0, duration_samples - len(audio)))
        else:
            audio = audio[:duration_samples]

        return {
            'audio': audio,
            'sr': self.sr,
            'num_voices': len(notes),
            'note_range': (min(notes), max(notes)) if len(notes) > 0 else (0, 0),
            'description': f'Pad voicing: {len(notes)} voices'
        }


# ─────────────────────────────────────────────────
# TEST / DEMONSTRATION
# ─────────────────────────────────────────────────

if __name__ == "__main__":

    import soundfile as sf

    print("\n╔════════════════════════════════════════════════╗")
    print("║  PAD SYNTHESIZER TEST                         ║")
    print("╚════════════════════════════════════════════════╝\n")

    # Create test pad pattern
    # C major voicing: C3(48), E3(52), G3(55), E4(64), G4(67), E5(76)
    # Held through 8-second phrase (2 seconds per chord)

    pad_pattern = {
        'sustain': {
            'notes': [48, 52, 55, 64, 67, 76] * 4,  # 6 voices x 4 chords
            'timing': [],
            'dynamics': [],
            'durations': []
        },
        'arpeggio': {
            'notes': [],
            'timing': [],
            'dynamics': [],
            'durations': []
        },
        'combined': {
            'notes': [],
            'timing': [],
            'dynamics': [],
            'durations': []
        }
    }

    # Fill timing for each chord change (every 2 seconds)
    chord_starts = [0.0, 2.0, 4.0, 6.0]
    chord_duration = 2.0

    sustain_notes = []
    sustain_timing = []
    sustain_dynamics = []
    sustain_durations = []

    voices = [48, 52, 55, 64, 67, 76]  # C3, E3, G3, E4, G4, E5

    for chord_idx, chord_start in enumerate(chord_starts):
        for voice_idx, midi_note in enumerate(voices):
            sustain_notes.append(midi_note)
            sustain_timing.append(chord_start)

            # Dynamics: lower voices softer, higher brighter
            base_dyn = 0.4 + (voice_idx / len(voices)) * 0.2
            sustain_dynamics.append(base_dyn)

            # Duration: chord duration (with slight overlap)
            sustain_durations.append(chord_duration + 0.1)

    pad_pattern['combined']['notes'] = sustain_notes
    pad_pattern['combined']['timing'] = sustain_timing
    pad_pattern['combined']['dynamics'] = sustain_dynamics
    pad_pattern['combined']['durations'] = sustain_durations

    print("Synthesizing pad voicing...")
    synthesizer = PadSynthesizer(sr=44100)
    result = synthesizer.synthesize_pad_voicing(pad_pattern, duration_seconds=8.0, tempo_bpm=120)

    print(f"✓ Synthesis complete:")
    print(f"  Voices: {result['num_voices']}")
    print(f"  Note range: MIDI {result['note_range'][0]} - {result['note_range'][1]}")
    print(f"  Audio: {len(result['audio'])} samples ({len(result['audio']) / result['sr']:.2f}s)")
    print(f"  Peak level: {np.abs(result['audio']).max():.3f}")

    # Save
    output_file = '/tmp/test_pad_synthesis.wav'
    sf.write(output_file, result['audio'], result['sr'])
    print(f"\n✓ Saved: {output_file}")
    print("✓ Pad synthesizer working!")
