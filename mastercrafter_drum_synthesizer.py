#!/usr/bin/env python3
"""
Mastercrafter Drum Synthesizer
Convert drum pattern data to audio waveforms
Synthesize kick, snare, hi-hat sounds from MIDI-like drum events
"""

import numpy as np


class DrumSynthesizer:
    """Synthesize drum sounds from generated drum patterns"""

    def __init__(self, sr=44100):
        self.sr = sr

    def synthesize_kick(self, timing, dynamics, duration_seconds, tempo_bpm=120):
        """
        Synthesize kick drum.

        Physical model:
        - Sub bass (60-100 Hz sine wave) with fast decay
        - Click (high-frequency decay) for attack definition
        - Pitch sweep down (typical kick curve)

        Args:
            timing: list of kick onset times (seconds)
            dynamics: list of velocities (0-1)
            duration_seconds: total duration of audio
            tempo_bpm: tempo for note length calculation

        Returns:
            numpy array of kick audio
        """

        audio = np.zeros(int(duration_seconds * self.sr))

        # Kick parameters
        sub_freq = 80  # Hz - sub bass fundamental
        sub_decay = 0.3  # seconds
        pitch_sweep_rate = 0.3  # How quickly pitch falls
        click_freq = 150  # Hz - click tone
        click_decay = 0.05  # seconds

        for onset_time, velocity in zip(timing, dynamics):
            onset_sample = int(onset_time * self.sr)

            # Sub bass envelope
            sub_samples = int(sub_decay * self.sr)
            envelope = np.exp(-np.arange(sub_samples) / (self.sr * sub_decay))

            # Pitch sweep: start at sub_freq, sweep down
            t_env = np.arange(sub_samples) / self.sr
            freq_curve = sub_freq * np.exp(-pitch_sweep_rate * t_env)
            phase = 2 * np.pi * np.cumsum(freq_curve) / self.sr

            # Sub bass
            sub = 0.7 * velocity * np.sin(phase) * envelope

            # Click (high-frequency attack)
            click_samples = int(click_decay * self.sr)
            click_envelope = np.exp(-np.arange(click_samples) / (self.sr * click_decay))
            click_phase = 2 * np.pi * click_freq * np.arange(click_samples) / self.sr
            click = 0.3 * velocity * np.sin(click_phase) * click_envelope

            # Combine
            total_samples = max(len(sub), len(click))
            kick_sound = np.zeros(total_samples)

            if len(sub) > 0:
                kick_sound[:len(sub)] += sub
            if len(click) > 0:
                kick_sound[:len(click)] += click

            # Add to output
            end_idx = min(onset_sample + len(kick_sound), len(audio))
            add_len = end_idx - onset_sample
            if add_len > 0:
                audio[onset_sample:end_idx] += kick_sound[:add_len]

        return audio

    def synthesize_snare(self, timing, dynamics, duration_seconds, tempo_bpm=120):
        """
        Synthesize snare drum.

        Physical model:
        - Noise burst (broad spectrum)
        - Filtered to emphasize mid-range (2-5 kHz)
        - Fast decay with realistic "snap"

        Args:
            timing: list of snare onset times (seconds)
            dynamics: list of velocities (0-1)
            duration_seconds: total duration of audio
            tempo_bpm: tempo for note length calculation

        Returns:
            numpy array of snare audio
        """

        audio = np.zeros(int(duration_seconds * self.sr))

        # Snare parameters
        snare_decay = 0.15  # seconds - quick decay
        center_freq = 3500  # Hz - snare resonance

        for onset_time, velocity in zip(timing, dynamics):
            onset_sample = int(onset_time * self.sr)
            snare_samples = int(snare_decay * self.sr)

            # Generate noise
            np.random.seed(int(onset_time * 1000) % 2**31)  # Deterministic per note
            noise = np.random.randn(snare_samples)

            # Envelope (fast attack, decay)
            envelope = np.exp(-np.arange(snare_samples) / (self.sr * snare_decay))

            # Simple band-pass filter (emphasize snare resonance)
            # Approximate: noise passes through, with resonance emphasis
            filtered = noise * envelope

            # Add resonance peak at center_freq
            t = np.arange(snare_samples) / self.sr
            resonance = 0.4 * np.sin(2 * np.pi * center_freq * t) * envelope
            snare_sound = 0.6 * velocity * (filtered + resonance)

            # Add to output
            end_idx = min(onset_sample + len(snare_sound), len(audio))
            add_len = end_idx - onset_sample
            if add_len > 0:
                audio[onset_sample:end_idx] += snare_sound[:add_len]

        return audio

    def synthesize_hi_hat(self, timing, dynamics, duration_seconds, is_closed=True, tempo_bpm=120):
        """
        Synthesize hi-hat (closed or open).

        Physical model:
        - Filtered noise (high-frequency emphasis)
        - Closed: short decay (50-100ms), bright
        - Open: longer decay (300-400ms), sustained hiss

        Args:
            timing: list of hi-hat onset times (seconds)
            dynamics: list of velocities (0-1)
            duration_seconds: total duration of audio
            is_closed: True for closed hi-hat, False for open
            tempo_bpm: tempo for note length calculation

        Returns:
            numpy array of hi-hat audio
        """

        audio = np.zeros(int(duration_seconds * self.sr))

        # Hi-hat parameters
        if is_closed:
            decay_time = 0.08  # 80ms closed
            brightness = 0.8  # More high-frequency content
            amplitude = 0.4
        else:
            decay_time = 0.35  # 350ms open
            brightness = 0.6  # Slightly less harsh
            amplitude = 0.3

        for onset_time, velocity in zip(timing, dynamics):
            onset_sample = int(onset_time * self.sr)
            hat_samples = int(decay_time * self.sr)

            # Generate high-frequency noise
            np.random.seed(int(onset_time * 10000) % 2**31)  # Deterministic per note
            noise = np.random.randn(hat_samples)

            # High-pass emphasis: keep bright frequencies
            # Simple approach: multiple noise sources, sum with brightness weighting
            noise_bright = noise * brightness + np.random.randn(hat_samples) * (1 - brightness)

            # Envelope
            envelope = np.exp(-np.arange(hat_samples) / (self.sr * decay_time))

            # Add some shimmer (very high frequency modulation)
            t = np.arange(hat_samples) / self.sr
            shimmer = 0.15 * np.sin(2 * np.pi * 12000 * t) * envelope

            hat_sound = amplitude * velocity * (noise_bright + shimmer) * envelope

            # Add to output
            end_idx = min(onset_sample + len(hat_sound), len(audio))
            add_len = end_idx - onset_sample
            if add_len > 0:
                audio[onset_sample:end_idx] += hat_sound[:add_len]

        return audio

    def synthesize_drum_pattern(self, drum_pattern, duration_seconds, tempo_bpm=120):
        """
        Synthesize complete drum pattern (kick + snare + hi-hat).

        Args:
            drum_pattern: dict from Stage 2 with kick/snare/hi_hat/combined sub-dicts
                Each has: notes (MIDI), timing (seconds), dynamics (0-1), durations
            duration_seconds: total duration to synthesize
            tempo_bpm: tempo in BPM

        Returns:
            dict with:
                - kick_audio: kick drum waveform
                - snare_audio: snare drum waveform
                - hi_hat_audio: hi-hat drum waveform
                - combined_audio: all drums mixed together
                - description: text summary
        """

        # Ensure audio length matches
        duration_samples = int(duration_seconds * self.sr)

        # Extract drum components
        kick_result = drum_pattern.get('kick', {})
        snare_result = drum_pattern.get('snare', {})
        hi_hat_result = drum_pattern.get('hi_hat', {})

        kick_timing = kick_result.get('timing', [])
        kick_dynamics = kick_result.get('dynamics', [])

        snare_timing = snare_result.get('timing', [])
        snare_dynamics = snare_result.get('dynamics', [])

        hi_hat_timing = hi_hat_result.get('timing', [])
        hi_hat_dynamics = hi_hat_result.get('dynamics', [])

        # Synthesize each drum
        kick_audio = self.synthesize_kick(kick_timing, kick_dynamics, duration_seconds, tempo_bpm)
        snare_audio = self.synthesize_snare(snare_timing, snare_dynamics, duration_seconds, tempo_bpm)
        hi_hat_audio = self.synthesize_hi_hat(hi_hat_timing, hi_hat_dynamics, duration_seconds, is_closed=True, tempo_bpm=tempo_bpm)

        # Normalize to duration
        kick_audio = kick_audio[:duration_samples]
        snare_audio = snare_audio[:duration_samples]
        hi_hat_audio = hi_hat_audio[:duration_samples]

        # Mix with level balance: kick > snare > hi-hat
        # Typical level: kick 0.6, snare 0.4, hi-hat 0.3
        combined_audio = (
            0.6 * kick_audio +
            0.4 * snare_audio +
            0.3 * hi_hat_audio
        )

        # Soft normalize to prevent clipping
        max_val = np.abs(combined_audio).max()
        if max_val > 0:
            combined_audio = 0.95 * combined_audio / max_val

        return {
            'kick_audio': kick_audio,
            'snare_audio': snare_audio,
            'hi_hat_audio': hi_hat_audio,
            'combined_audio': combined_audio,
            'sr': self.sr,
            'description': f'Synthesized drums: {len(kick_timing)} kicks, {len(snare_timing)} snares, {len(hi_hat_timing)} hi-hats'
        }


# ─────────────────────────────────────────────────
# TEST / DEMONSTRATION
# ─────────────────────────────────────────────────

if __name__ == "__main__":

    import soundfile as sf

    print("\n╔════════════════════════════════════════════════╗")
    print("║  DRUM SYNTHESIZER TEST                        ║")
    print("╚════════════════════════════════════════════════╝\n")

    # Create test drum pattern (C→F→G→C at 120 BPM, 8 seconds)
    beat_interval = 0.5  # 120 BPM = one beat per 0.5 seconds

    # Kick pattern: beats 1, 2-and, 3, 4-and (4 measures = 16 beats = 8 seconds)
    kick_timing = []
    kick_dynamics = []
    for measure in range(4):
        kick_timing.extend([
            measure * 2 + 0 * beat_interval,      # Beat 1
            measure * 2 + 1.5 * beat_interval,    # 2-and
            measure * 2 + 2 * beat_interval,      # Beat 3
            measure * 2 + 3.5 * beat_interval     # 4-and
        ])
        kick_dynamics.extend([0.85, 0.65, 0.85, 0.65])

    # Snare: beats 2 and 4
    snare_timing = []
    snare_dynamics = []
    for measure in range(4):
        snare_timing.extend([
            measure * 2 + 1 * beat_interval,      # Beat 2
            measure * 2 + 3 * beat_interval       # Beat 4
        ])
        snare_dynamics.extend([0.8, 0.8])

    # Hi-hat: eighth notes (8 per measure)
    hi_hat_timing = []
    hi_hat_dynamics = []
    for measure in range(4):
        for beat in range(4):
            for eighth in range(2):
                hi_hat_timing.append(measure * 2 + beat * beat_interval + eighth * beat_interval / 2)
                hi_hat_dynamics.append(0.6 + np.random.rand() * 0.2)  # Humanize

    drum_pattern = {
        'kick': {
            'notes': [36] * len(kick_timing),  # C1 (kick drum)
            'timing': kick_timing,
            'dynamics': kick_dynamics,
            'durations': [0.15] * len(kick_timing)
        },
        'snare': {
            'notes': [38] * len(snare_timing),  # D1 (snare)
            'timing': snare_timing,
            'dynamics': snare_dynamics,
            'durations': [0.15] * len(snare_timing)
        },
        'hi_hat': {
            'notes': [42] * len(hi_hat_timing),  # F#1 (hi-hat)
            'timing': hi_hat_timing,
            'dynamics': hi_hat_dynamics,
            'durations': [0.1] * len(hi_hat_timing)
        }
    }

    # Synthesize
    print("Synthesizing drum pattern...")
    synthesizer = DrumSynthesizer(sr=44100)
    result = synthesizer.synthesize_drum_pattern(drum_pattern, duration_seconds=8.0, tempo_bpm=120)

    print(f"✓ Synthesis complete:")
    print(f"  Kick: {len(kick_timing)} hits synthesized")
    print(f"  Snare: {len(snare_timing)} hits synthesized")
    print(f"  Hi-hat: {len(hi_hat_timing)} hits synthesized")
    print(f"  Combined audio: {len(result['combined_audio'])} samples ({len(result['combined_audio']) / 44100:.2f}s)")
    print(f"  Peak level: {np.abs(result['combined_audio']).max():.3f}")

    # Save
    output_file = '/tmp/test_drum_synthesis.wav'
    sf.write(output_file, result['combined_audio'], result['sr'])
    print(f"\n✓ Saved: {output_file}")
    print("✓ Drum synthesizer working!")
