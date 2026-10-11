"""
SongShapes Audio Processor
Stem separation, character regeneration, and accompaniment generation
Built with numpy/scipy (no librosa dependency)
"""

import numpy as np
from scipy import signal
from scipy.fftpack import fft, ifft
import soundfile as sf
from pathlib import Path
import json
import os


class StemSeparator:
    """Harmonic-Percussive Source Separation (HPSS) for stem splitting"""

    def __init__(self, sr=44100):
        self.sr = sr
        self.eps = 1e-8

    def separate(self, audio, margin=2.0, power=2.0):
        """
        Separate audio into harmonic and percussive components using HPSS.

        Args:
            audio: numpy array (mono or stereo)
            margin: margin in STFT bins (higher = more separation)
            power: exponent for STFT magnitude

        Returns:
            harmonic: harmonic component (voiced/pitched sounds)
            percussive: percussive component (drums/rhythm)
        """
        # Handle stereo by processing each channel
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)

        # Compute STFT
        f, t, Sxx = signal.stft(audio, fs=self.sr, window='hann')
        magnitude = np.abs(Sxx)
        phase = np.angle(Sxx)

        # Apply median filters to separate harmonic and percussive
        # Harmonic: contains stable frequency components (vertical structure)
        # Percussive: contains brief impulses (horizontal structure)

        margin_bins = int(margin)

        # Harmonic is vertical (stable over time)
        harmonic_mask = signal.medfilt2d(magnitude, kernel_size=(2*margin_bins+1, 1))

        # Percussive is horizontal (brief in time)
        percussive_mask = signal.medfilt2d(magnitude, kernel_size=(1, 2*margin_bins+1))

        # Normalize masks
        harmonic_mask = harmonic_mask ** power
        percussive_mask = percussive_mask ** power

        # Wiener filtering: soft mask based on relative magnitude
        harmonic_mask = harmonic_mask / (harmonic_mask + percussive_mask + self.eps)
        percussive_mask = percussive_mask / (harmonic_mask + percussive_mask + self.eps)

        # Apply masks and reconstruct
        harmonic_mag = magnitude * harmonic_mask
        percussive_mag = magnitude * percussive_mask

        # Inverse STFT
        _, harmonic = signal.istft(harmonic_mag * np.exp(1j * phase), fs=self.sr, window='hann')
        _, percussive = signal.istft(percussive_mag * np.exp(1j * phase), fs=self.sr, window='hann')

        # Normalize output
        harmonic = self._normalize(harmonic)
        percussive = self._normalize(percussive)

        return harmonic, percussive

    def separate_harmonic_by_frequency(self, harmonic, low_freq=80, mid_freq=400):
        """
        Further split harmonic component by frequency:
        - Vocals (mid-high): 400 Hz - 4 kHz
        - Bass/Pads (low): < 400 Hz

        Args:
            harmonic: harmonic component from HPSS
            low_freq: lower bound for vocal range (Hz)
            mid_freq: upper bound for bass range (Hz)

        Returns:
            vocals: vocal-range harmonic
            bass_pads: low-frequency harmonic
        """
        # Design filters
        nyquist = self.sr / 2

        # Bass/Pads: low-pass < mid_freq
        bass_cutoff = mid_freq / nyquist
        bass_cutoff = np.clip(bass_cutoff, 0.01, 0.99)
        b_bass, a_bass = signal.butter(4, bass_cutoff, btype='low')
        bass_pads = signal.filtfilt(b_bass, a_bass, harmonic)

        # Vocals: band-pass mid_freq to nyquist (everything else from harmonic)
        vocals = harmonic - bass_pads

        return self._normalize(vocals), self._normalize(bass_pads)

    def _normalize(self, signal_array, target_peak=0.95):
        """Normalize signal to peak amplitude"""
        peak = np.max(np.abs(signal_array))
        if peak > 0:
            return signal_array * (target_peak / peak)
        return signal_array


class CharacterProcessor:
    """Apply character effects to audio stems"""

    def __init__(self, sr=44100):
        self.sr = sr

    def apply_eq(self, audio, low_gain=0.0, mid_gain=0.0, high_gain=0.0):
        """
        Apply 3-band EQ to audio.

        Args:
            audio: input signal
            low_gain: gain in dB for bass (< 200 Hz)
            mid_gain: gain in dB for mids (200-2kHz)
            high_gain: gain in dB for treble (> 2kHz)

        Returns:
            eq_audio: EQ'd signal
        """
        output = audio.copy()

        # Low shelf (< 200 Hz)
        if low_gain != 0:
            freq = 100
            Q = 0.707
            output = self._shelf_filter(output, freq, low_gain, Q, 'low')

        # Mid peak (1 kHz)
        if mid_gain != 0:
            freq = 1000
            Q = 1.0
            output = self._peaking_filter(output, freq, mid_gain, Q)

        # High shelf (> 5 kHz)
        if high_gain != 0:
            freq = 5000
            Q = 0.707
            output = self._shelf_filter(output, freq, high_gain, Q, 'high')

        return output

    def apply_compression(self, audio, threshold=-20, ratio=4.0, attack_ms=10, release_ms=100):
        """
        Apply dynamic range compression.

        Args:
            audio: input signal
            threshold: threshold in dB
            ratio: compression ratio
            attack_ms: attack time in ms
            release_ms: release time in ms

        Returns:
            compressed: compressed signal
        """
        # Convert dB threshold to linear
        threshold_linear = 10 ** (threshold / 20.0)

        # Attack/release in samples
        attack_samples = int(self.sr * attack_ms / 1000.0)
        release_samples = int(self.sr * release_ms / 1000.0)

        # Compute envelope
        envelope = np.abs(audio)

        # Apply attack/release
        for i in range(1, len(envelope)):
            if envelope[i] > envelope[i-1]:
                # Attack
                envelope[i] = envelope[i-1] + (envelope[i] - envelope[i-1]) / max(attack_samples, 1)
            else:
                # Release
                envelope[i] = envelope[i-1] - (envelope[i-1] - envelope[i]) / max(release_samples, 1)

        # Compute gain reduction
        gain = np.ones_like(envelope)
        mask = envelope > threshold_linear
        gain[mask] = threshold_linear + (envelope[mask] - threshold_linear) / ratio
        gain[mask] = gain[mask] / (envelope[mask] + 1e-8)

        # Smooth gain changes
        gain = signal.savgol_filter(gain, window_length=min(51, len(gain)//2*2+1), polyorder=3)

        return audio * gain

    def apply_saturation(self, audio, drive=0.0):
        """
        Apply soft saturation (tape-like warmth).

        Args:
            audio: input signal
            drive: drive amount (0-1, where 1 is full saturation)

        Returns:
            saturated: saturated signal
        """
        if drive <= 0:
            return audio

        # Soft clipping function
        drive_amount = 1.0 + drive * 10.0  # Scale to 1-11
        driven = audio * drive_amount

        # Soft clip with tanh
        saturated = np.tanh(driven)

        # Blend with original based on drive
        return audio * (1 - drive) + saturated * drive

    def apply_reverb(self, audio, room_size=0.5, wet_level=0.3):
        """
        Apply simple reverb using delays (Schroeder reverberator).

        Args:
            audio: input signal
            room_size: room size parameter (0-1)
            wet_level: wet/dry mix (0-1)

        Returns:
            reverb_audio: reverb'd signal
        """
        # Delay times (in samples) for comb filters
        delay_times = np.array([1116, 1188, 1277, 1356]) * self.sr // 44100
        delay_times = np.maximum(delay_times, 1)  # Ensure >= 1

        # Initialize delay buffers
        delays = [np.zeros(dt) for dt in delay_times]
        output = np.zeros_like(audio)

        # Process
        for i, sample in enumerate(audio):
            # Comb filter processing
            comb_out = 0
            for j, delay_buffer in enumerate(delays):
                # Read from delay
                delay_sample = delay_buffer[0]

                # Feedback
                feedback = delay_sample * room_size

                # Write input + feedback to delay
                delay_buffer[0] = sample + feedback

                # Shift delay line
                delays[j] = np.roll(delay_buffer, 1)

                # Accumulate
                comb_out += delay_sample

            # Wet/dry mix
            output[i] = audio[i] * (1 - wet_level) + (comb_out * wet_level / len(delay_times))

        return output

    def _shelf_filter(self, audio, freq, gain_db, Q, shelf_type):
        """Design and apply shelf filter with gain"""
        nyquist = self.sr / 2
        normalized_freq = freq / nyquist
        normalized_freq = np.clip(normalized_freq, 0.01, 0.99)

        # Simple approach: create filter and scale output
        if shelf_type == 'low':
            # Low shelf filter
            b, a = signal.butter(2, normalized_freq, btype='low')
        else:
            # High shelf filter
            b, a = signal.butter(2, normalized_freq, btype='high')

        filtered = signal.filtfilt(b, a, audio)

        # Apply gain scaling
        gain_linear = 10 ** (gain_db / 20.0)
        return audio * (1 - 0.5) + filtered * 0.5 * gain_linear

    def _peaking_filter(self, audio, freq, gain_db, Q):
        """Design and apply peaking EQ filter with gain"""
        nyquist = self.sr / 2
        normalized_freq = freq / nyquist
        normalized_freq = np.clip(normalized_freq, 0.01, 0.99)

        # Create a notch filter (which acts as a peaking filter in reverse)
        b, a = signal.iirnotch(normalized_freq, Q)
        filtered = signal.filtfilt(b, a, audio)

        # Invert for peak and apply gain
        gain_linear = 10 ** (gain_db / 20.0)
        return audio * (1 - 0.3) + filtered * 0.3 * gain_linear


class AudioProcessor:
    """Main processor: orchestrates stem separation and character effects"""

    def __init__(self, sr=44100):
        self.sr = sr
        self.separator = StemSeparator(sr)
        self.character = CharacterProcessor(sr)

    def load_audio(self, filepath):
        """Load audio file and return (audio, sr)"""
        audio, sr = sf.read(filepath)
        if sr != self.sr:
            # Resample if needed (simplified)
            ratio = self.sr / sr
            audio = signal.resample(audio, int(len(audio) * ratio))
        return audio, self.sr

    def save_audio(self, audio, filepath, sr=None):
        """Save audio file"""
        if sr is None:
            sr = self.sr
        # Ensure audio is in valid range
        audio = np.clip(audio, -1.0, 1.0)
        sf.write(filepath, audio, sr)

    def process_full_pipeline(self, input_path, output_dir, character_config=None):
        """
        Full pipeline: load → separate → apply character → save stems

        Args:
            input_path: path to input audio
            output_dir: directory to save stems
            character_config: dict with per-stem character settings

        Returns:
            results: dict with paths and metadata
        """
        # Load
        audio, sr = self.load_audio(input_path)

        # Separate
        harmonic, percussive = self.separator.separate(audio)
        vocals, bass_pads = self.separator.separate_harmonic_by_frequency(harmonic)

        # Create output directory
        os.makedirs(output_dir, exist_ok=True)

        # Default character config
        if character_config is None:
            character_config = {
                'vocals': {'eq_low': 0, 'eq_mid': 2, 'eq_high': 1, 'compression': 0},
                'percussion': {'eq_low': 1, 'eq_mid': 0, 'eq_high': 2, 'compression': 0.5},
                'bass_pads': {'eq_low': 1, 'eq_mid': -1, 'eq_high': 0, 'compression': 0.3}
            }

        # Apply character effects
        vocals_processed = self.character.apply_eq(
            vocals,
            low_gain=character_config.get('vocals', {}).get('eq_low', 0),
            mid_gain=character_config.get('vocals', {}).get('eq_mid', 0),
            high_gain=character_config.get('vocals', {}).get('eq_high', 0)
        )

        percussion_processed = self.character.apply_eq(
            percussive,
            low_gain=character_config.get('percussion', {}).get('eq_low', 0),
            mid_gain=character_config.get('percussion', {}).get('eq_mid', 0),
            high_gain=character_config.get('percussion', {}).get('eq_high', 0)
        )

        bass_pads_processed = self.character.apply_eq(
            bass_pads,
            low_gain=character_config.get('bass_pads', {}).get('eq_low', 0),
            mid_gain=character_config.get('bass_pads', {}).get('eq_mid', 0),
            high_gain=character_config.get('bass_pads', {}).get('eq_high', 0)
        )

        # Save stems
        stems = {
            'vocals': vocals_processed,
            'percussion': percussion_processed,
            'bass_pads': bass_pads_processed,
            'harmonic': harmonic,
            'percussive': percussive
        }

        saved_paths = {}
        for stem_name, stem_audio in stems.items():
            output_path = os.path.join(output_dir, f"{stem_name}.wav")
            self.save_audio(stem_audio, output_path, sr)
            saved_paths[stem_name] = output_path

        # Master mix
        master = (vocals_processed + percussion_processed + bass_pads_processed) / 3
        master_path = os.path.join(output_dir, "master_mix.wav")
        self.save_audio(master, master_path, sr)
        saved_paths['master'] = master_path

        return {
            'status': 'success',
            'stems': saved_paths,
            'sr': sr,
            'duration': len(audio) / sr,
            'message': f'Successfully separated into {len(stems)} stems'
        }


if __name__ == '__main__':
    # Test
    processor = AudioProcessor()
    print("✓ Audio processor ready")
    print("  - Stem separator (HPSS)")
    print("  - Character processor (EQ, compression, saturation, reverb)")
    print("  - Full pipeline integration")
