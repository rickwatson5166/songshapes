"""
Chord Detector for SongShapes
Infer chord progression from vocals stem using chromagram analysis
Pure scipy/numpy implementation - no external dependencies
"""

import numpy as np
from scipy import signal
from collections import Counter


class ChordDetector:
    """Detect chord progressions from audio using chromagram analysis"""

    def __init__(self, sr=44100, hop_length=512, n_fft=2048):
        """
        Initialize chord detector

        Args:
            sr: Sample rate (Hz)
            hop_length: Samples between frames
            n_fft: FFT size for STFT
        """
        self.sr = sr
        self.hop_length = hop_length
        self.n_fft = n_fft
        self.eps = 1e-8

    def extract_chromagram(self, audio, sr=None):
        """
        Extract chromagram (pitch class energy over time)

        Args:
            audio: numpy array (mono), time-domain signal
            sr: Sample rate

        Returns:
            chromagram: numpy array (12 x n_frames)
                        Energy in each pitch class (C, C#, D, ..., B)
            times: Time of each frame (seconds)
        """
        if sr is None:
            sr = self.sr

        # Convert stereo to mono
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)

        # Compute STFT
        _, _, Sxx = signal.stft(audio, fs=sr, nperseg=self.n_fft,
                                 noverlap=self.n_fft - self.hop_length, window='hann')

        # Magnitude spectrogram
        magnitude = np.abs(Sxx)

        # Compute chromagram: map STFT bins to pitch classes
        chromagram = self._magnitude_to_chromagram(magnitude, sr)

        # Normalize each frame
        chromagram = chromagram / (np.sum(chromagram, axis=0, keepdims=True) + self.eps)

        # Time axis
        n_frames = chromagram.shape[1]
        times = np.arange(n_frames) * self.hop_length / sr

        return chromagram, times

    def _magnitude_to_chromagram(self, magnitude_spectrogram, sr):
        """
        Map magnitude spectrogram to chromagram (12 pitch classes)

        Strategy:
        1. Compute log-frequency for each STFT bin
        2. Map to nearest pitch class (C, C#, D, ..., B)
        3. Sum energy for each pitch class
        """
        n_bins = magnitude_spectrogram.shape[0]
        n_frames = magnitude_spectrogram.shape[1]

        # Frequency of each STFT bin
        frequencies = np.fft.rfftfreq(self.n_fft, 1 / sr)

        # Chromagram (12 pitch classes)
        chromagram = np.zeros((12, n_frames))

        for i, freq in enumerate(frequencies):
            if freq < 20 or freq > 4000:  # Ignore very low and very high frequencies
                continue

            # Convert frequency to cents relative to C0
            # MIDI note = 12 * log2(freq / 16.35) + 0.5
            if freq > 0:
                midi_note = 12 * np.log2(freq / 16.35159783128741)
                pitch_class = int(round(midi_note)) % 12  # 0=C, 1=C#, ..., 11=B

                # Add energy to this pitch class
                chromagram[pitch_class] += magnitude_spectrogram[i]

        return chromagram

    def detect_chords(self, audio, sr=None, key=None, hop_length_frames=None):
        """
        Detect chord progression from audio

        Args:
            audio: numpy array (mono)
            sr: Sample rate
            key: Optional, key center ('C', 'D', etc.) for better detection
            hop_length_frames: How many frames to average per chord detection
                             (larger = fewer, longer chords)

        Returns:
            chords: List of dicts with chord info
            times: Time array for chromagram
        """
        if sr is None:
            sr = self.sr

        # Extract chromagram
        chromagram, times = self.extract_chromagram(audio, sr)

        # Default: ~1 second per chord
        if hop_length_frames is None:
            hop_length_frames = int(sr / self.hop_length)

        # Detect chords by analyzing chromagram in chunks
        chords = []
        for i in range(0, chromagram.shape[1], hop_length_frames):
            chunk_end = min(i + hop_length_frames, chromagram.shape[1])
            chunk = chromagram[:, i:chunk_end]

            # Average chromagram over chunk
            avg_chroma = np.mean(chunk, axis=1)

            # Detect chord from this chromagram
            chord_info = self._detect_chord_from_chromagram(avg_chroma)

            start_time = times[i]
            end_time = times[chunk_end - 1] if chunk_end > 0 else times[-1]
            duration = end_time - start_time

            chord_info['start_time'] = start_time
            chord_info['end_time'] = end_time
            chord_info['duration'] = duration

            chords.append(chord_info)

        # Smooth consecutive identical chords
        chords = self._smooth_chords(chords)

        return chords, times

    def _detect_chord_from_chromagram(self, chromagram_frame):
        """
        Detect chord from a single chromagram frame

        Returns:
            chord_info: dict with 'root', 'quality', 'confidence'
        """
        note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

        # Normalize chromagram
        chroma_norm = chromagram_frame / (np.sum(chromagram_frame) + self.eps)

        # Find root (pitch class with highest energy)
        root_idx = np.argmax(chroma_norm)
        root_note = note_names[root_idx]
        root_energy = chroma_norm[root_idx]

        # Check for common chord patterns
        # Major: root, major 3rd (4 semitones), perfect 5th (7 semitones)
        major_energy = (chroma_norm[root_idx] +
                       chroma_norm[(root_idx + 4) % 12] +
                       chroma_norm[(root_idx + 7) % 12]) / 3

        # Minor: root, minor 3rd (3 semitones), perfect 5th (7 semitones)
        minor_energy = (chroma_norm[root_idx] +
                       chroma_norm[(root_idx + 3) % 12] +
                       chroma_norm[(root_idx + 7) % 12]) / 3

        # Dominant 7th: root, major 3rd, 5th, minor 7th (10 semitones)
        dom7_energy = (chroma_norm[root_idx] +
                      chroma_norm[(root_idx + 4) % 12] +
                      chroma_norm[(root_idx + 7) % 12] +
                      chroma_norm[(root_idx + 10) % 12]) / 4

        # Determine chord quality
        if major_energy > minor_energy and major_energy > dom7_energy:
            quality = "major"
            confidence = major_energy
        elif minor_energy > major_energy and minor_energy > dom7_energy:
            quality = "minor"
            confidence = minor_energy
        elif dom7_energy > major_energy and dom7_energy > minor_energy:
            quality = "dom7"
            confidence = dom7_energy
        else:
            quality = "major"  # Default to major
            confidence = major_energy

        return {
            'root': root_note,
            'quality': quality,
            'confidence': float(confidence)
        }

    def _smooth_chords(self, chords):
        """
        Smooth chord sequence by merging consecutive identical chords
        and removing very short chords
        """
        if len(chords) <= 1:
            return chords

        smoothed = []
        current_chord = chords[0].copy()

        for next_chord in chords[1:]:
            if (next_chord['root'] == current_chord['root'] and
                next_chord['quality'] == current_chord['quality']):
                # Same chord - extend duration
                current_chord['end_time'] = next_chord['end_time']
                current_chord['duration'] = (current_chord['end_time'] -
                                             current_chord['start_time'])
            else:
                # Different chord
                # Keep only if longer than 0.2 seconds
                if current_chord['duration'] > 0.2:
                    smoothed.append(current_chord)
                current_chord = next_chord.copy()

        # Add final chord
        if current_chord['duration'] > 0.2:
            smoothed.append(current_chord)

        return smoothed

    def get_key_center(self, audio, sr=None):
        """
        Estimate key center by analyzing overall chromagram

        Returns:
            key: Root note ('C', 'D', etc.)
            confidence: Confidence score (0-1)
        """
        if sr is None:
            sr = self.sr

        chromagram, _ = self.extract_chromagram(audio, sr)

        # Average chromagram across time
        avg_chroma = np.mean(chromagram, axis=1)

        # Find pitch class with highest energy
        key_idx = np.argmax(avg_chroma)
        note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        key = note_names[key_idx]

        # Confidence: ratio of top pitch class to sum of all
        confidence = avg_chroma[key_idx] / (np.sum(avg_chroma) + self.eps)

        return key, float(confidence)


if __name__ == '__main__':
    # Test with synthetic audio
    print("Testing Chord Detector")
    print("=" * 60)

    sr = 44100

    # Create test audio: C major chord (C, E, G)
    t = np.linspace(0, 2, 2 * sr)
    c_note = 0.3 * np.sin(2 * np.pi * 261.63 * t)  # C4
    e_note = 0.3 * np.sin(2 * np.pi * 329.63 * t)  # E4
    g_note = 0.3 * np.sin(2 * np.pi * 392.00 * t)  # G4
    audio = c_note + e_note + g_note

    # Add transition to F major at 1 second
    f_mask = t > 1
    f_note = 0.3 * np.sin(2 * np.pi * 349.23 * t)  # F4
    a_note = 0.3 * np.sin(2 * np.pi * 440.00 * t)  # A4
    # Replace second half with F major
    audio[f_mask] = f_note[f_mask] + a_note[f_mask] + g_note[f_mask]

    # Normalize
    audio = audio / (np.max(np.abs(audio)) + 1e-8)
    audio *= 0.8

    # Detect chords
    detector = ChordDetector(sr=sr)

    # Get key center
    key, key_conf = detector.get_key_center(audio, sr)
    print(f"✓ Detected key center: {key} (confidence: {key_conf:.2f})")

    # Detect chords
    chords, times = detector.detect_chords(audio, sr)

    print(f"\n✓ Detected {len(chords)} chords:")
    for i, chord in enumerate(chords):
        print(f"  Chord {i+1}: {chord['root']}{chord['quality'][:3]} "
              f"@ {chord['start_time']:.2f}s - {chord['end_time']:.2f}s "
              f"(confidence: {chord['confidence']:.2f})")

    print("=" * 60)
