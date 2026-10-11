#!/usr/bin/env python3
"""
Mastercrafter Harmonic Analyzer
Infer chord progressions from F0 curve and timing
"""

import numpy as np


class HarmonicAnalyzer:
    """Infer chord progressions from performance"""

    def __init__(self, sr=44100, hop_length=512):
        self.sr = sr
        self.hop_length = hop_length
        self.note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

    def analyze_harmonies(self, f0_curve, onset_frames, key_info=None, sr=None, hop_length=None):
        """
        Break performance into chunks and infer chords for each.

        Approach:
        - Divide performance into chunks (one per beat/onset)
        - For each chunk, find dominant pitch classes
        - Match against known chord shapes (triads, sevenths, etc.)
        - Build chord progression sequence

        Args:
            f0_curve: array of fundamental frequencies
            onset_frames: array of frame indices where notes start
            key_info: dict with detected key (optional, for context)
            sr: sample rate (uses self.sr if not provided)
            hop_length: hop length (uses self.hop_length if not provided)

        Returns:
            dict with:
                - chord_progression: list of chord names ["C major", "F major", ...]
                - chord_timings: list of start times for each chord
                - chord_confidences: confidence for each chord detection
        """

        if sr is None:
            sr = self.sr
        if hop_length is None:
            hop_length = self.hop_length

        if len(onset_frames) < 2:
            return {
                'chord_progression': ['Unknown'],
                'chord_timings': [0.0],
                'chord_confidences': [0.0],
                'error': 'Not enough onsets to analyze harmonies'
            }

        # Step 1: Segment into chunks based on onsets
        # Each chunk spans from one onset to the next
        chords = []
        chord_times = []
        chord_confidences = []

        for onset_idx in range(len(onset_frames)):
            onset_start = onset_frames[onset_idx]

            # Next onset or end of song
            if onset_idx + 1 < len(onset_frames):
                onset_end = onset_frames[onset_idx + 1]
            else:
                onset_end = len(f0_curve)

            # Extract F0 chunk for this beat
            beat_chunk = f0_curve[onset_start:onset_end]
            beat_time = onset_start * hop_length / sr

            # Infer chord for this chunk
            chord, confidence = self._infer_chord_from_f0(beat_chunk)

            chords.append(chord)
            chord_times.append(beat_time)
            chord_confidences.append(confidence)

        # Step 2: Simplify by merging consecutive identical chords
        simplified_chords = []
        simplified_times = []
        simplified_confidences = []

        for i, chord in enumerate(chords):
            if chord != (simplified_chords[-1] if simplified_chords else None):
                simplified_chords.append(chord)
                simplified_times.append(chord_times[i])
                simplified_confidences.append(chord_confidences[i])

        return {
            'chord_progression': simplified_chords,
            'chord_timings': simplified_times,
            'chord_confidences': simplified_confidences,
            'raw_chords': chords,
            'raw_chord_times': chord_times
        }

    def _infer_chord_from_f0(self, f0_chunk):
        """
        Infer chord from an F0 chunk (one beat/note region).

        Returns:
            (chord_name, confidence) tuple
        """

        # Remove unvoiced frames
        voiced = f0_chunk[f0_chunk > 0]

        if len(voiced) == 0:
            return ("silence", 0.0)

        # Convert to MIDI and then to pitch classes (0-11)
        midi_notes = 12 * np.log2(voiced / 440.0) + 69
        chromatic = (midi_notes % 12).astype(int)

        # Find pitch class distribution
        pitch_classes, counts = np.unique(chromatic, return_counts=True)

        # Get root (most common pitch class)
        root_idx = np.argmax(counts)
        root = pitch_classes[root_idx]
        root_count = counts[root_idx]

        # Detect chord quality by looking for characteristic intervals
        # Major chord: root + 4 semitones (major third) + 7 semitones (perfect fifth)
        # Minor chord: root + 3 semitones (minor third) + 7 semitones (perfect fifth)

        major_third = (root + 4) % 12
        minor_third = (root + 3) % 12
        perfect_fifth = (root + 7) % 12

        has_major_third = major_third in pitch_classes
        has_minor_third = minor_third in pitch_classes
        has_fifth = perfect_fifth in pitch_classes

        # Determine quality
        if has_major_third and has_fifth:
            quality = "major"
            confidence = 0.9
        elif has_minor_third and has_fifth:
            quality = "minor"
            confidence = 0.9
        elif has_major_third:
            quality = "major"
            confidence = 0.6
        elif has_minor_third:
            quality = "minor"
            confidence = 0.6
        else:
            # No clear third, default to major
            quality = "major"
            confidence = 0.3

        # Confidence also depends on how concentrated the energy is in the root
        total_count = np.sum(counts)
        root_ratio = root_count / total_count if total_count > 0 else 0
        confidence = min(1.0, confidence * root_ratio)

        chord_name = f"{self.note_names[root]} {quality}"

        return (chord_name, float(confidence))

    def analyze_harmonies_verbose(self, f0_curve, onset_frames, key_info=None, sr=None, hop_length=None, verbosity=1):
        """Analyze with progress messages"""

        if sr is None:
            sr = self.sr
        if hop_length is None:
            hop_length = self.hop_length

        if verbosity >= 1:
            print("[Harmonic Analysis]")
            print(f"  → Input: {len(f0_curve)} F0 frames, {len(onset_frames)} onsets")

        result = self.analyze_harmonies(f0_curve, onset_frames, key_info=key_info, sr=sr, hop_length=hop_length)

        if 'error' not in result and verbosity >= 1:
            mean_confidence = np.mean(result['chord_confidences']) if result['chord_confidences'] else 0
            progression_str = ' → '.join(result['chord_progression'][:8])
            if len(result['chord_progression']) > 8:
                progression_str += ' → ...'

            print(f"  → Chords detected: {len(result['chord_progression'])}")
            print(f"    {progression_str}")
            print(f"  ✓ Mean confidence: {mean_confidence:.1%}")

        return result


# ─────────────────────────────────────────────────────
# TEST / DEMONSTRATION
# ─────────────────────────────────────────────────────

if __name__ == "__main__":

    print("\n╔════════════════════════════════════════════════╗")
    print("║  MASTERCRAFTER HARMONIC ANALYZER TEST         ║")
    print("╚════════════════════════════════════════════════╝\n")

    sr = 44100
    hop_length = 512

    # Test 1: C major chord (C-E-G)
    print("Test 1: C major chord")
    print("─" * 50)

    # Create F0 curve with C (262 Hz), E (330 Hz), G (392 Hz) mixed
    duration = 1.0
    n_frames = int(duration * sr / hop_length)
    f0_curve = np.zeros(n_frames)

    # Simulate playing C-E-G together (chord)
    frequencies = [262, 330, 392]  # C, E, G
    for freq in frequencies:
        f0_curve += freq * np.ones(n_frames) / len(frequencies)

    # One onset at the beginning
    onset_frames = np.array([0])

    print(f"  Frequencies: {frequencies} Hz (C, E, G)")
    print(f"  Expected chord: C major\n")

    analyzer = HarmonicAnalyzer(sr=sr, hop_length=hop_length)
    result = analyzer.analyze_harmonies_verbose(f0_curve, onset_frames, verbosity=1)

    print(f"  ✓ Detected: {result['chord_progression'][0]}")
    print()

    # Test 2: Progression (C major → F major → G major → C major)
    print("\nTest 2: C major → F major → G major → C major")
    print("─" * 50)

    duration = 4.0
    n_frames = int(duration * sr / hop_length)
    f0_curve = np.zeros(n_frames)

    # Define chord progressions
    progressions = [
        ([262, 330, 392], 0.0),      # C major (C-E-G)
        ([349, 440, 523], 1.0),      # F major (F-A-C)
        ([392, 494, 659], 2.0),      # G major (G-B-D)
        ([262, 330, 392], 3.0),      # C major
    ]

    onset_frames = np.array([])
    frame_times = np.arange(n_frames) * hop_length / sr

    for frequencies, start_time in progressions:
        start_frame = int(start_time * sr / hop_length)
        end_frame = int((start_time + 0.9) * sr / hop_length)  # 0.9 seconds per chord

        if end_frame > n_frames:
            end_frame = n_frames

        # Mix the frequencies
        for freq in frequencies:
            f0_curve[start_frame:end_frame] += freq / len(frequencies)

        onset_frames = np.append(onset_frames, start_frame)

    onset_frames = onset_frames.astype(int)

    print(f"  Progressions: C major → F major → G major → C major")
    print(f"  Onset frames: {onset_frames}\n")

    result = analyzer.analyze_harmonies_verbose(f0_curve, onset_frames, verbosity=1)

    print(f"\n  ✓ Detected progression:")
    for i, (chord, time, conf) in enumerate(zip(result['chord_progression'],
                                                   result['chord_timings'],
                                                   result['chord_confidences'])):
        print(f"    {i+1}. {chord:12s} @ {time:.2f}s (confidence: {conf:.1%})")

    # Test 3: A minor chord (A-C-E)
    print("\n\nTest 3: A minor chord")
    print("─" * 50)

    duration = 1.0
    n_frames = int(duration * sr / hop_length)
    f0_curve = np.zeros(n_frames)

    frequencies = [440, 523, 659]  # A, C, E
    for freq in frequencies:
        f0_curve += freq * np.ones(n_frames) / len(frequencies)

    onset_frames = np.array([0])

    print(f"  Frequencies: {frequencies} Hz (A, C, E)")
    print(f"  Expected chord: A minor\n")

    result = analyzer.analyze_harmonies_verbose(f0_curve, onset_frames, verbosity=1)

    print(f"  ✓ Detected: {result['chord_progression'][0]}")
