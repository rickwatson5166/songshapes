"""
Melody Extractor for SongShapes
Extract F0 (fundamental frequency) from vocals stem using autocorrelation
No librosa dependency - pure scipy/numpy implementation for Intel Mac compatibility
"""

import numpy as np
from scipy import signal
from scipy.signal import windows
import soundfile as sf
from pathlib import Path


class MelodyExtractor:
    """Extract F0 contour from audio using autocorrelation-based pitch detection"""

    def __init__(self, sr=44100, hop_length=512, fmin=50, fmax=400):
        """
        Initialize melody extractor

        Args:
            sr: Sample rate (Hz)
            hop_length: Samples between frames
            fmin: Minimum frequency to detect (Hz) - lower bound for vocals
            fmax: Maximum frequency to detect (Hz) - upper bound for vocals
        """
        self.sr = sr
        self.hop_length = hop_length
        self.fmin = fmin
        self.fmax = fmax
        self.eps = 1e-8

    def extract_f0(self, audio, sr=None):
        """
        Extract F0 (fundamental frequency) contour from audio

        Args:
            audio: numpy array (mono), time-domain signal
            sr: Sample rate (if different from self.sr)

        Returns:
            f0_contour: numpy array (Hz values per frame)
            confidence: numpy array (0-1, confidence per frame)
            times: numpy array (seconds, time of each frame)
        """
        if sr is None:
            sr = self.sr

        # Convert stereo to mono if needed
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)

        # Pre-emphasis to boost high frequencies (helps with F0 detection)
        pre_emphasis = 0.97
        audio = np.append(audio[0], audio[1:] - pre_emphasis * audio[:-1])

        # Frame the audio
        n_frames = 1 + (len(audio) - self.hop_length) // self.hop_length
        frames = np.zeros((n_frames, self.hop_length))

        for i in range(n_frames):
            start = i * self.hop_length
            end = start + self.hop_length
            frame = audio[start:end]
            if len(frame) < self.hop_length:
                frame = np.pad(frame, (0, self.hop_length - len(frame)))
            frames[i] = frame

        # Apply Hann window to each frame
        window = windows.hann(self.hop_length)
        frames *= window

        # Detect F0 for each frame using autocorrelation
        f0_contour = np.zeros(n_frames)
        confidence = np.zeros(n_frames)

        for i in range(n_frames):
            frame = frames[i]
            f0, conf = self._detect_f0_frame(frame, sr)
            f0_contour[i] = f0
            confidence[i] = conf

        # Post-process: median filter to smooth and remove octave errors
        f0_contour = self._post_process_f0(f0_contour, confidence)

        # Time axis
        times = np.arange(n_frames) * self.hop_length / sr

        return f0_contour, confidence, times

    def _detect_f0_frame(self, frame, sr):
        """
        Detect F0 for a single frame using autocorrelation

        Returns:
            f0: Detected frequency (Hz), or 0 if unvoiced
            confidence: Confidence score (0-1)
        """
        # Compute autocorrelation
        acf = self._autocorrelation(frame)

        # Search for peak in the autocorrelation function
        # Convert frequency bounds to lag indices
        lag_min = int(sr / self.fmax)
        lag_max = int(sr / self.fmin)

        if lag_min >= len(acf) or lag_max >= len(acf):
            return 0, 0

        # Find the peak in the valid lag range
        search_acf = acf[lag_min:lag_max]

        if len(search_acf) == 0 or np.max(search_acf) < self.eps:
            return 0, 0

        peak_lag = np.argmax(search_acf) + lag_min
        peak_value = search_acf[np.argmax(search_acf)]

        # Convert lag to frequency
        f0 = sr / peak_lag if peak_lag > 0 else 0

        # Compute confidence as normalized peak height
        # Voiced frames have higher autocorrelation values
        confidence = min(1.0, max(0, peak_value))

        # Threshold confidence (very low peaks = unvoiced)
        if confidence < 0.1:
            f0 = 0
            confidence = 0

        return f0, confidence

    def _autocorrelation(self, frame):
        """Compute autocorrelation function using FFT (efficient)"""
        # Zero-pad for FFT
        padded_length = 2 * len(frame)
        padded = np.zeros(padded_length)
        padded[:len(frame)] = frame

        # FFT
        fft_frame = np.fft.rfft(padded)

        # Power spectrum (absolute value squared)
        power_spectrum = np.abs(fft_frame) ** 2

        # IFFT to get autocorrelation
        acf = np.fft.irfft(power_spectrum)

        # Normalize by first value
        if acf[0] > self.eps:
            acf /= acf[0]

        return acf[:len(frame)]

    def _post_process_f0(self, f0_contour, confidence, median_window=5):
        """
        Post-process F0 contour:
        - Remove unvoiced frames (confidence < threshold)
        - Median filter to smooth
        - Interpolate short gaps
        """
        # Remove very low confidence frames
        f0_processed = f0_contour.copy()
        voicing_threshold = 0.1
        f0_processed[confidence < voicing_threshold] = 0

        # Median filter for smoothing (only on voiced frames)
        if median_window > 1:
            voiced_mask = f0_processed > 0
            if np.any(voiced_mask):
                # Apply median filter
                f0_filtered = signal.medfilt(f0_processed, kernel_size=median_window)
                # Keep original for unvoiced, use filtered for voiced
                f0_processed[voiced_mask] = f0_filtered[voiced_mask]

        # Interpolate short gaps (< 3 frames)
        f0_processed = self._interpolate_gaps(f0_processed, max_gap=3)

        return f0_processed

    def _interpolate_gaps(self, f0_contour, max_gap=3):
        """Interpolate short gaps in F0 contour"""
        f0_out = f0_contour.copy()

        i = 0
        while i < len(f0_out):
            if f0_out[i] == 0:
                # Find the gap length
                gap_start = i
                gap_length = 0
                while i < len(f0_out) and f0_out[i] == 0:
                    gap_length += 1
                    i += 1

                # If gap is small enough and bounded, interpolate
                if gap_length <= max_gap and gap_start > 0 and i < len(f0_out):
                    if f0_out[gap_start - 1] > 0 and f0_out[i] > 0:
                        # Linear interpolation
                        prev_f0 = f0_out[gap_start - 1]
                        next_f0 = f0_out[i]
                        for j in range(gap_length):
                            alpha = (j + 1) / (gap_length + 1)
                            f0_out[gap_start + j] = (1 - alpha) * prev_f0 + alpha * next_f0
            else:
                i += 1

        return f0_out

    def get_melody_note_sequence(self, f0_contour, confidence, times, confidence_threshold=0.3):
        """
        Convert F0 contour to note sequence

        Returns:
            notes: List of dicts with 'pitch', 'start_time', 'duration', 'confidence'
        """
        notes = []
        note_start = None
        note_f0_values = []
        note_confidences = []
        note_start_idx = None

        for i, (f0, conf, t) in enumerate(zip(f0_contour, confidence, times)):
            if f0 > 0 and conf > confidence_threshold:
                # Voiced frame
                if note_start is None:
                    note_start = t
                    note_start_idx = i
                note_f0_values.append(f0)
                note_confidences.append(conf)
            else:
                # Unvoiced frame - end current note if any
                if note_start is not None and len(note_f0_values) > 0:
                    duration = t - note_start
                    avg_f0 = np.median(note_f0_values)  # Use median to avoid glitches
                    avg_confidence = np.mean(note_confidences)

                    notes.append({
                        "f0": avg_f0,
                        "pitch_hz": avg_f0,
                        "start_time": note_start,
                        "end_time": t,
                        "duration": duration,
                        "confidence": avg_confidence,
                        "vibrato_detected": self._detect_vibrato(note_f0_values)
                    })

                note_start = None
                note_f0_values = []
                note_confidences = []
                note_start_idx = None

        # Handle final note if it extends to end
        if note_start is not None and len(note_f0_values) > 0:
            duration = times[-1] - note_start
            avg_f0 = np.median(note_f0_values)
            avg_confidence = np.mean(note_confidences)

            notes.append({
                "f0": avg_f0,
                "pitch_hz": avg_f0,
                "start_time": note_start,
                "end_time": times[-1],
                "duration": duration,
                "confidence": avg_confidence,
                "vibrato_detected": self._detect_vibrato(note_f0_values)
            })

        return notes

    def _detect_vibrato(self, f0_values):
        """Detect if a note has vibrato (frequency oscillation)"""
        if len(f0_values) < 3:
            return False

        # Compute standard deviation of F0 values
        f0_std = np.std(f0_values)

        # Vibrato typically causes 1-2% frequency variation
        f0_mean = np.mean(f0_values)
        vibrato_threshold = f0_mean * 0.02  # 2% variation

        return f0_std > vibrato_threshold

    def hz_to_note(self, f0_hz):
        """Convert frequency (Hz) to MIDI note number and note name"""
        if f0_hz <= 0:
            return None, "silence"

        # A4 = 440 Hz = MIDI note 69
        midi_note = 69 + 12 * np.log2(f0_hz / 440.0)
        midi_note_rounded = int(round(midi_note))

        # Note names
        note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        octave = (midi_note_rounded // 12) - 1
        note_name = note_names[midi_note_rounded % 12]

        return midi_note_rounded, f"{note_name}{octave}"


if __name__ == '__main__':
    # Test with synthetic audio
    print("Testing Melody Extractor")
    print("=" * 60)

    sr = 44100

    # Create test audio: 2 seconds of A4 (440 Hz) with vibrato
    t = np.linspace(0, 2, 2 * sr)
    vibrato = 0.05 * np.sin(2 * np.pi * 5 * t)  # 5 Hz vibrato
    audio = 0.3 * np.sin(2 * np.pi * 440 * t * (1 + vibrato))

    # Add some noise
    audio += 0.01 * np.random.randn(len(audio))

    # Extract melody
    extractor = MelodyExtractor(sr=sr)
    f0_contour, confidence, times = extractor.extract_f0(audio, sr)

    # Get note sequence
    notes = extractor.get_melody_note_sequence(f0_contour, confidence, times)

    print(f"✓ Extracted {len(notes)} notes from test audio")
    for i, note in enumerate(notes):
        midi_note, note_name = extractor.hz_to_note(note['f0'])
        print(f"  Note {i+1}: {note_name} ({note['f0']:.1f} Hz) "
              f"@ {note['start_time']:.2f}s, duration {note['duration']:.2f}s, "
              f"confidence {note['confidence']:.2f}")

    print(f"\n✓ Mean F0: {np.mean(f0_contour[f0_contour > 0]):.1f} Hz")
    print(f"✓ Mean Confidence: {np.mean(confidence[confidence > 0]):.2f}")
    print(f"✓ Voicing Ratio: {np.sum(f0_contour > 0) / len(f0_contour) * 100:.1f}%")
    print("=" * 60)
