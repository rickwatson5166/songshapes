"""
Drum Synthesizer for SongShapes Phase 2
Generate kick, snare, and hi-hat sounds from drum events
Pure scipy/numpy implementation - no dependencies beyond what Phase 1 needs
"""

import numpy as np
from scipy import signal


class DrumSynthesizer:
    """Synthesize drum sounds from DrumEvent objects"""

    def __init__(self, sr=44100):
        self.sr = sr

    def synthesize_drum(self, drum_event):
        """
        Synthesize a single drum sound

        Args:
            drum_event: DrumEvent namedtuple with drum_type, start_time, duration, velocity

        Returns:
            audio: numpy array of audio samples
            start_sample: Starting sample index for this drum sound
        """
        drum_type = drum_event.drum_type
        duration = drum_event.duration
        velocity = drum_event.velocity

        if drum_type == 'kick':
            audio = self._synthesize_kick(duration, velocity)
        elif drum_type == 'snare':
            audio = self._synthesize_snare(duration, velocity)
        elif drum_type == 'hihat_closed':
            audio = self._synthesize_hihat_closed(duration, velocity)
        elif drum_type == 'hihat_open':
            audio = self._synthesize_hihat_open(duration, velocity)
        else:
            audio = np.zeros(int(duration * self.sr))

        start_sample = int(drum_event.start_time * self.sr)
        return audio, start_sample

    def _synthesize_kick(self, duration, velocity):
        """
        Synthesize kick drum: sine wave sweep down + exponential decay

        Classic 808-style kick: starts at ~150Hz, sweeps to ~50Hz, decays over duration
        """
        n_samples = int(duration * self.sr)
        t = np.arange(n_samples) / self.sr

        # Frequency envelope: 150Hz down to 50Hz over attack (0.1s), then hold
        attack_time = min(0.1, duration * 0.3)
        attack_samples = int(attack_time * self.sr)

        # Frequency sweep down
        f_start = 150
        f_end = 50
        freq = np.ones_like(t) * f_end
        freq[:attack_samples] = f_start - (f_start - f_end) * (np.arange(attack_samples) / attack_samples)

        # Phase accumulation for smooth frequency sweep
        phase = 2 * np.pi * np.cumsum(freq) / self.sr

        # Sine wave
        kick = np.sin(phase)

        # Amplitude envelope: quick attack, exponential decay
        env = np.ones_like(t)
        # Decay from end of attack
        decay_start = attack_samples
        decay_samples = n_samples - decay_start
        if decay_samples > 0:
            decay_rate = 8.0  # Decay constant
            env[decay_start:] = np.exp(-decay_rate * np.arange(decay_samples) / self.sr)

        # Apply envelope and velocity
        kick = kick * env * velocity

        return kick

    def _synthesize_snare(self, duration, velocity):
        """
        Synthesize snare drum: filtered white noise with envelope

        High-pass filtered noise with quick attack and medium decay
        """
        n_samples = int(duration * self.sr)
        t = np.arange(n_samples) / self.sr

        # White noise
        noise = np.random.randn(n_samples)

        # High-pass filter: remove low frequencies (snare is bright)
        # Design a simple high-pass filter
        cutoff_freq = 2000  # Hz
        normalized_cutoff = cutoff_freq / (self.sr / 2)
        # Clamp to valid range
        normalized_cutoff = min(0.99, max(0.01, normalized_cutoff))
        b, a = signal.butter(4, normalized_cutoff, btype='high')
        noise_filtered = signal.filtfilt(b, a, noise)

        # Amplitude envelope: quick attack, medium decay
        attack_time = 0.01  # 10ms attack
        attack_samples = int(attack_time * self.sr)

        env = np.ones_like(t)
        # Exponential decay from start
        decay_rate = 5.0  # Decay constant
        env = np.exp(-decay_rate * t)

        # Sharp attack (linear ramp in first 10ms)
        if attack_samples > 0:
            env[:attack_samples] = np.linspace(0, 1, attack_samples)

        # Apply envelope and velocity
        snare = noise_filtered * env * velocity

        return snare

    def _synthesize_hihat_closed(self, duration, velocity):
        """
        Synthesize closed hi-hat: bright noise burst with quick decay

        Very bright, quick decay (20-30ms typical)
        """
        n_samples = int(duration * self.sr)
        t = np.arange(n_samples) / self.sr

        # White noise
        noise = np.random.randn(n_samples)

        # High-pass filter: very bright (remove everything below 5kHz)
        cutoff_freq = 5000  # Hz
        normalized_cutoff = cutoff_freq / (self.sr / 2)
        normalized_cutoff = min(0.99, max(0.01, normalized_cutoff))
        b, a = signal.butter(6, normalized_cutoff, btype='high')
        noise_filtered = signal.filtfilt(b, a, noise)

        # Amplitude envelope: very fast decay
        decay_rate = 20.0  # Fast decay
        env = np.exp(-decay_rate * t)

        # Apply envelope and velocity
        hihat = noise_filtered * env * velocity * 0.7  # Quieter than other drums

        return hihat

    def _synthesize_hihat_open(self, duration, velocity):
        """
        Synthesize open hi-hat: longer decay than closed, more sustain

        Similar spectral content to closed but decays slower (ring/sustain)
        """
        n_samples = int(duration * self.sr)
        t = np.arange(n_samples) / self.sr

        # White noise
        noise = np.random.randn(n_samples)

        # High-pass filter: bright (remove below 3kHz)
        cutoff_freq = 3000  # Hz
        normalized_cutoff = cutoff_freq / (self.sr / 2)
        normalized_cutoff = min(0.99, max(0.01, normalized_cutoff))
        b, a = signal.butter(5, normalized_cutoff, btype='high')
        noise_filtered = signal.filtfilt(b, a, noise)

        # Amplitude envelope: slower decay for open sound
        decay_rate = 8.0  # Slower decay
        env = np.exp(-decay_rate * t)

        # Apply envelope and velocity
        hihat = noise_filtered * env * velocity * 0.7

        return hihat

    def synthesize_drum_track(self, drum_events, total_duration=None):
        """
        Synthesize all drum events into a single track

        Args:
            drum_events: List of DrumEvent objects
            total_duration: Total duration in seconds (auto-calculated if None)

        Returns:
            drum_track: numpy array (mono audio) containing all synthesized drums
        """
        if not drum_events:
            if total_duration is None:
                total_duration = 1.0
            return np.zeros(int(total_duration * self.sr))

        # Calculate total duration
        if total_duration is None:
            max_end_time = max(e.start_time + e.duration for e in drum_events)
            total_duration = max_end_time + 0.1  # Add small buffer

        n_samples = int(total_duration * self.sr)
        drum_track = np.zeros(n_samples)

        # Synthesize each drum event
        for drum_event in drum_events:
            audio, start_sample = self.synthesize_drum(drum_event)
            end_sample = start_sample + len(audio)

            # Clip to track length
            if start_sample < n_samples:
                end_sample = min(end_sample, n_samples)
                audio = audio[:end_sample - start_sample]
                drum_track[start_sample:end_sample] += audio

        # Normalize to prevent clipping
        max_val = np.max(np.abs(drum_track))
        if max_val > 0.99:
            drum_track = drum_track * (0.99 / max_val)

        return drum_track


if __name__ == '__main__':
    # Test drum synthesis
    print("Testing Drum Synthesizer")
    print("=" * 60)

    from accompaniment_generator import DrumEvent

    # Create test drum pattern
    drum_events = [
        DrumEvent('kick', 0.0, 0.15, 0.85),
        DrumEvent('hihat_closed', 0.1, 0.08, 0.65),
        DrumEvent('hihat_closed', 0.35, 0.08, 0.65),
        DrumEvent('snare', 0.5, 0.1, 0.8),
        DrumEvent('kick', 0.5, 0.15, 0.65),
        DrumEvent('hihat_closed', 0.6, 0.08, 0.65),
        DrumEvent('hihat_open', 0.85, 0.15, 0.6),
    ]

    # Synthesize
    synth = DrumSynthesizer(sr=44100)
    drum_track = synth.synthesize_drum_track(drum_events, total_duration=2.0)

    print(f"✓ Synthesized {len(drum_events)} drum events")
    print(f"✓ Drum track duration: {len(drum_track) / 44100:.2f}s")
    print(f"✓ Peak amplitude: {np.max(np.abs(drum_track)):.3f}")
    print(f"✓ RMS level: {np.sqrt(np.mean(drum_track**2)):.3f}")

    # Show individual drum types
    print(f"\n✓ Individual drum synthesis:")
    kick = synth._synthesize_kick(0.15, 0.85)
    print(f"  Kick (150→50Hz): {len(kick)} samples, peak {np.max(np.abs(kick)):.3f}")

    snare = synth._synthesize_snare(0.1, 0.8)
    print(f"  Snare (filtered noise): {len(snare)} samples, peak {np.max(np.abs(snare)):.3f}")

    hihat_c = synth._synthesize_hihat_closed(0.08, 0.65)
    print(f"  Hi-hat closed: {len(hihat_c)} samples, peak {np.max(np.abs(hihat_c)):.3f}")

    hihat_o = synth._synthesize_hihat_open(0.15, 0.6)
    print(f"  Hi-hat open: {len(hihat_o)} samples, peak {np.max(np.abs(hihat_o)):.3f}")

    print("=" * 60)
