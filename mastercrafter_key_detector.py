#!/usr/bin/env python3
"""
Mastercrafter Key Detector
Infer musical key from F0 curve using pitch class histogram analysis
"""

import numpy as np


class KeyDetector:
    """Infer musical key from pitch curve"""

    def __init__(self):
        self.note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

        # Major key profile (Krumhansl-Schmuckler)
        self.major_profile = np.array([1.0, 0.0, 0.5, 0.0, 0.8, 0.5, 0.0, 1.0, 0.3, 0.7, 0.3, 0.8])

        # Minor key profile
        self.minor_profile = np.array([1.0, 0.0, 0.5, 0.8, 0.0, 0.5, 0.7, 1.0, 0.3, 0.5, 0.3, 0.7])

    def detect_key(self, f0_curve):
        """
        Analyze pitch distribution to detect key.

        Approach:
        - Remove silence/unvoiced frames (f0 = 0)
        - Normalize all pitches to chromatic scale (12 semitones)
        - Calculate histogram of pitch classes
        - Match against major/minor key signatures

        Args:
            f0_curve: array of fundamental frequencies (Hz) or MIDI notes

        Returns:
            dict with:
                - key: "C major", "A minor", etc.
                - confidence: 0-1 (how certain)
                - root_midi: MIDI note number for root
                - root_hz: Hz frequency for root
        """

        # Remove unvoiced frames (f0 = 0)
        voiced_f0 = f0_curve[f0_curve > 0]

        if len(voiced_f0) == 0:
            return {
                'key': 'Unknown',
                'confidence': 0.0,
                'root_midi': 60,
                'root_hz': 261.6,
                'error': 'No voiced frames in F0 curve'
            }

        # Step 1: Convert Hz to MIDI note numbers
        # MIDI = 12 * log2(f / 440) + 69 (where A4 = 440 Hz = MIDI 69)
        midi_notes = 12 * np.log2(voiced_f0 / 440.0) + 69

        # Step 2: Quantize to chromatic scale (mod 12)
        # This collapses all octaves into 12 pitch classes
        chromatic_pitch_classes = midi_notes % 12

        # Step 3: Build histogram of pitch classes (12 bins, one per semitone)
        histogram, _ = np.histogram(chromatic_pitch_classes, bins=12, range=(0, 12))

        # Normalize histogram to sum = 1
        histogram = histogram / np.sum(histogram)

        # Step 4: Try all 12 possible keys and find best match
        best_match = None
        best_score = -np.inf

        for root in range(12):
            # Rotate histogram so this root becomes position 0
            rotated = np.roll(histogram, -root)

            # Compare rotated histogram against major key profile
            major_score = np.dot(rotated, self.major_profile) / np.linalg.norm(self.major_profile)

            if major_score > best_score:
                best_score = major_score
                best_match = (root, "major")

            # Compare rotated histogram against minor key profile
            minor_score = np.dot(rotated, self.minor_profile) / np.linalg.norm(self.minor_profile)

            if minor_score > best_score:
                best_score = minor_score
                best_match = (root, "minor")

        # Convert root semitone to MIDI and Hz
        root_semitone, quality = best_match
        root_midi = root_semitone + 60  # Middle C = 60
        root_hz = 440 * (2 ** ((root_midi - 69) / 12))

        key_name = f"{self.note_names[root_semitone]} {quality}"

        return {
            'key': key_name,
            'confidence': float(best_score),
            'root_midi': root_midi,
            'root_hz': float(root_hz),
            'histogram': histogram.tolist(),
            'quality': quality
        }

    def detect_key_verbose(self, f0_curve, verbosity=1):
        """Detect key with progress messages"""

        if verbosity >= 1:
            print("[Key Detection]")
            print(f"  → Input: {len(f0_curve)} F0 frames")

        result = self.detect_key(f0_curve)

        if 'error' not in result and verbosity >= 1:
            voiced_count = np.sum(f0_curve > 0)
            print(f"  → Voiced frames: {voiced_count} / {len(f0_curve)}")
            print(f"  ✓ Detected Key: {result['key']} (confidence: {result['confidence']:.1%})")

        return result


# ─────────────────────────────────────────────────────
# TEST / DEMONSTRATION
# ─────────────────────────────────────────────────────

if __name__ == "__main__":

    print("\n╔════════════════════════════════════════════════╗")
    print("║  MASTERCRAFTER KEY DETECTOR TEST              ║")
    print("╚════════════════════════════════════════════════╝\n")

    # Create test F0 curve: C major scale
    # C (262 Hz), D (294 Hz), E (330 Hz), F (349 Hz), G (392 Hz), A (440 Hz), B (494 Hz), C (523 Hz)
    sr = 44100
    duration = 8.0  # 8 seconds, 1 second per note
    t = np.linspace(0, duration, int(sr * duration))

    # Define notes (C major scale)
    notes = [262, 294, 330, 349, 392, 440, 494, 523]

    # Create F0 curve that plays the scale
    f0_curve = np.zeros_like(t)
    frames_per_note = len(t) // len(notes)

    for note_idx, note_freq in enumerate(notes):
        start_frame = note_idx * frames_per_note
        end_frame = (note_idx + 1) * frames_per_note if note_idx < len(notes) - 1 else len(t)
        f0_curve[start_frame:end_frame] = note_freq

    print(f"Created F0 curve: {len(f0_curve)} frames")
    print(f"  Notes: {notes}")
    print(f"  Expected key: C major\n")

    # Test key detection
    detector = KeyDetector()
    result = detector.detect_key_verbose(f0_curve, verbosity=1)

    print(f"\n✓ Detection Complete")
    print(f"  Key: {result['key']}")
    print(f"  Confidence: {result['confidence']:.1%}")
    print(f"  Root MIDI: {result['root_midi']}")
    print(f"  Root Hz: {result['root_hz']:.1f}")

    # Test on a minor key (A minor = A, C, E)
    print("\n" + "="*50)
    print("Test 2: A minor scale")
    print("="*50 + "\n")

    notes_minor = [440, 523, 659, 440, 523, 659, 440, 523]  # A, C, E repeated
    f0_curve_minor = np.zeros_like(t)

    for note_idx, note_freq in enumerate(notes_minor):
        start_frame = note_idx * frames_per_note
        end_frame = (note_idx + 1) * frames_per_note if note_idx < len(notes_minor) - 1 else len(t)
        f0_curve_minor[start_frame:end_frame] = note_freq

    result_minor = detector.detect_key_verbose(f0_curve_minor, verbosity=1)

    print(f"\n✓ Detection Complete")
    print(f"  Key: {result_minor['key']}")
    print(f"  Confidence: {result_minor['confidence']:.1%}")
    print(f"  Root Hz: {result_minor['root_hz']:.1f}")
