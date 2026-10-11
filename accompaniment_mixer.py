"""
Accompaniment Mixer for SongShapes Phase 2
Mix vocal stem + generated bass + generated drums
Apply character effects to each component
"""

import numpy as np
from scipy import signal


class AccompanimentMixer:
    """Mix and balance accompaniment components"""

    def __init__(self, sr=44100):
        self.sr = sr

    def mix_accompaniment(self, vocals, bass, drums, levels=None):
        """
        Mix three audio tracks together with optional level control

        Args:
            vocals: numpy array (mono audio)
            bass: numpy array (mono audio)
            drums: numpy array (mono audio)
            levels: dict with 'vocals', 'bass', 'drums' keys (0-1 scale, default 1.0 each)

        Returns:
            mix: numpy array (mono mix)
        """
        if levels is None:
            levels = {'vocals': 1.0, 'bass': 1.0, 'drums': 1.0}

        # Pad shorter tracks to match longest
        max_len = max(len(vocals), len(bass), len(drums))

        vocals_padded = np.pad(vocals, (0, max_len - len(vocals)), mode='constant')
        bass_padded = np.pad(bass, (0, max_len - len(bass)), mode='constant')
        drums_padded = np.pad(drums, (0, max_len - len(drums)), mode='constant')

        # Apply level scaling
        vocals_level = levels.get('vocals', 1.0)
        bass_level = levels.get('bass', 1.0)
        drums_level = levels.get('drums', 1.0)

        mix = (vocals_padded * vocals_level +
               bass_padded * bass_level +
               drums_padded * drums_level)

        # Normalize to prevent clipping
        max_val = np.max(np.abs(mix))
        if max_val > 0.99:
            mix = mix * (0.99 / max_val)

        return mix

    def apply_3band_eq(self, audio, eq_config):
        """
        Apply 3-band EQ to audio track

        Args:
            audio: numpy array (mono)
            eq_config: dict with 'eq_low', 'eq_mid', 'eq_high' (range -12 to +12 dB)

        Returns:
            filtered: numpy array (filtered audio)
        """
        if not eq_config or all(v == 0 for v in eq_config.values()):
            return audio

        filtered = audio.copy()

        # Low shelf: < 200 Hz
        eq_low = eq_config.get('eq_low', 0)
        if eq_low != 0:
            gain_linear = 10 ** (eq_low / 20)  # Convert dB to linear
            # Simple low-pass boost/cut
            cutoff = 200 / (self.sr / 2)
            cutoff = min(0.99, max(0.01, cutoff))
            b, a = signal.butter(2, cutoff, btype='low')
            low_component = signal.filtfilt(b, a, filtered)
            # Blend based on gain
            filtered = filtered + (low_component - filtered) * (gain_linear - 1)

        # Mid peak: ~1kHz
        eq_mid = eq_config.get('eq_mid', 0)
        if eq_mid != 0:
            gain_linear = 10 ** (eq_mid / 20)
            # Simple band-pass around 1kHz
            low_freq = 500 / (self.sr / 2)
            high_freq = 2000 / (self.sr / 2)
            low_freq = min(0.99, max(0.01, low_freq))
            high_freq = min(0.99, max(low_freq + 0.01, high_freq))
            b, a = signal.butter(2, [low_freq, high_freq], btype='band')
            mid_component = signal.filtfilt(b, a, filtered)
            filtered = filtered + (mid_component - filtered) * (gain_linear - 1)

        # High shelf: > 5kHz
        eq_high = eq_config.get('eq_high', 0)
        if eq_high != 0:
            gain_linear = 10 ** (eq_high / 20)
            # Simple high-pass boost/cut
            cutoff = 5000 / (self.sr / 2)
            cutoff = min(0.99, max(0.01, cutoff))
            b, a = signal.butter(2, cutoff, btype='high')
            high_component = signal.filtfilt(b, a, filtered)
            filtered = filtered + (high_component - filtered) * (gain_linear - 1)

        return filtered

    def apply_compression(self, audio, compression_amount=0.5):
        """
        Apply dynamic range compression

        Args:
            audio: numpy array (mono)
            compression_amount: 0-1 scale (0=no compression, 1=maximum compression)

        Returns:
            compressed: numpy array (compressed audio)
        """
        if compression_amount <= 0:
            return audio

        # Envelope detection with attack/release
        attack_time = 0.005  # 5ms
        release_time = 0.05  # 50ms

        attack_samples = int(attack_time * self.sr)
        release_samples = int(release_time * self.sr)

        # Level detection (envelope follower)
        abs_audio = np.abs(audio)

        envelope = np.zeros_like(audio)
        current_level = 0

        for i in range(len(audio)):
            if abs_audio[i] > current_level:
                # Attack
                alpha = 1.0 - np.exp(-1.0 / attack_samples) if attack_samples > 0 else 1.0
            else:
                # Release
                alpha = 1.0 - np.exp(-1.0 / release_samples) if release_samples > 0 else 1.0

            current_level = alpha * abs_audio[i] + (1 - alpha) * current_level
            envelope[i] = current_level

        # Threshold and ratio
        threshold = np.percentile(envelope, 70)  # Dynamic threshold
        ratio = 4.0 * compression_amount  # Compression ratio (1:1 to 4:1)

        # Gain reduction
        gain_reduction = np.ones_like(envelope)
        above_threshold = envelope > threshold
        gain_reduction[above_threshold] = 1.0 / (1.0 + (ratio - 1.0) * (envelope[above_threshold] / threshold - 1.0))

        # Smooth gain reduction
        gain_reduction = signal.medfilt(gain_reduction, kernel_size=11)

        # Apply gain reduction
        compressed = audio * gain_reduction

        return compressed

    def apply_saturation(self, audio, saturation_amount=0.3):
        """
        Apply soft saturation for warmth and presence

        Args:
            audio: numpy array (mono)
            saturation_amount: 0-1 scale (amount of saturation)

        Returns:
            saturated: numpy array (saturated audio)
        """
        if saturation_amount <= 0:
            return audio

        # Soft clipping via tanh
        # More saturation = drive signal harder into tanh curve
        drive = 1.0 + saturation_amount * 9.0  # Drive from 1 to 10
        saturated = np.tanh(audio * drive) / drive

        # Blend with original
        output = audio + (saturated - audio) * saturation_amount

        return output

    def apply_reverb(self, audio, reverb_amount=0.2):
        """
        Apply simple reverb using Schroeder reverberator

        Args:
            audio: numpy array (mono)
            reverb_amount: 0-1 scale (wet/dry mix)

        Returns:
            reverb_audio: numpy array (with reverb)
        """
        if reverb_amount <= 0:
            return audio

        # Simplified reverb: comb filters
        reverb_delays = [29, 37, 41, 43]  # ms (comb filter delays)
        reverb_decays = [0.84, 0.83, 0.82, 0.81]  # Feedback coefficients

        reverb_output = np.zeros_like(audio)

        for delay_ms, decay in zip(reverb_delays, reverb_decays):
            delay_samples = int(delay_ms * self.sr / 1000)

            if delay_samples < len(audio):
                # Comb filter with feedback
                filtered = np.zeros_like(audio)
                for i in range(len(audio)):
                    if i >= delay_samples:
                        filtered[i] = audio[i] + decay * filtered[i - delay_samples]
                    else:
                        filtered[i] = audio[i]

                reverb_output += filtered

        # Normalize and blend
        reverb_output = reverb_output / len(reverb_delays)

        # Dry/wet mix
        output = audio * (1 - reverb_amount) + reverb_output * reverb_amount

        return output

    def process_stem(self, audio, character_config):
        """
        Apply all character effects to a stem

        Args:
            audio: numpy array (mono audio)
            character_config: dict with 'eq_low', 'eq_mid', 'eq_high', 'compression', 'saturation', 'reverb'

        Returns:
            processed: numpy array (processed audio)
        """
        if not character_config:
            return audio

        processed = audio.copy()

        # Apply EQ
        eq_config = {k: character_config.get(k, 0) for k in ['eq_low', 'eq_mid', 'eq_high']}
        processed = self.apply_3band_eq(processed, eq_config)

        # Apply compression
        compression = character_config.get('compression', 0)
        processed = self.apply_compression(processed, compression)

        # Apply saturation
        saturation = character_config.get('saturation', 0)
        processed = self.apply_saturation(processed, saturation)

        # Apply reverb
        reverb = character_config.get('reverb', 0)
        processed = self.apply_reverb(processed, reverb)

        return processed


if __name__ == '__main__':
    # Test mixer
    print("Testing Accompaniment Mixer")
    print("=" * 60)

    sr = 44100
    duration = 2.0

    # Create test components
    t = np.linspace(0, duration, int(sr * duration))
    vocals = 0.3 * np.sin(2 * np.pi * 440 * t)  # A4
    bass = 0.2 * np.sin(2 * np.pi * 110 * t)   # A2
    drums = 0.15 * np.random.randn(len(t))    # Noise-like

    mixer = AccompanimentMixer(sr)

    # Test basic mixing
    mix = mixer.mix_accompaniment(vocals, bass, drums)
    print(f"✓ Mixed tracks: {len(mix)} samples")
    print(f"  Peak: {np.max(np.abs(mix)):.3f}")

    # Test EQ
    eq_config = {'eq_low': 2, 'eq_mid': 1, 'eq_high': 3}
    eq_vocals = mixer.apply_3band_eq(vocals, eq_config)
    print(f"\n✓ Applied 3-band EQ:")
    print(f"  Original peak: {np.max(np.abs(vocals)):.3f}")
    print(f"  EQ'd peak: {np.max(np.abs(eq_vocals)):.3f}")

    # Test compression
    compressed = mixer.apply_compression(vocals, 0.5)
    print(f"\n✓ Applied compression (0.5):")
    print(f"  Original peak: {np.max(np.abs(vocals)):.3f}")
    print(f"  Compressed peak: {np.max(np.abs(compressed)):.3f}")

    # Test saturation
    saturated = mixer.apply_saturation(vocals, 0.3)
    print(f"\n✓ Applied saturation (0.3):")
    print(f"  Original peak: {np.max(np.abs(vocals)):.3f}")
    print(f"  Saturated peak: {np.max(np.abs(saturated)):.3f}")

    # Test reverb
    reverb_vocals = mixer.apply_reverb(vocals, 0.2)
    print(f"\n✓ Applied reverb (0.2):")
    print(f"  Original RMS: {np.sqrt(np.mean(vocals**2)):.3f}")
    print(f"  Reverb RMS: {np.sqrt(np.mean(reverb_vocals**2)):.3f}")

    # Test full character processing
    character_config = {
        'eq_low': 2,
        'eq_mid': 1,
        'eq_high': 3,
        'compression': 0.5,
        'saturation': 0.3,
        'reverb': 0.2
    }
    processed = mixer.process_stem(vocals, character_config)
    print(f"\n✓ Applied full character processing:")
    print(f"  Original peak: {np.max(np.abs(vocals)):.3f}")
    print(f"  Processed peak: {np.max(np.abs(processed)):.3f}")

    print("=" * 60)
