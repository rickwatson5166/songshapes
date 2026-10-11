#!/usr/bin/env python3
"""
Mastercrafter Style Detector
Detect playing style (legato, staccato, swing, expression level)
"""

import numpy as np


class StyleDetector:
    """Detect playing style characteristics"""

    def __init__(self, sr=44100, hop_length=512):
        self.sr = sr
        self.hop_length = hop_length

    def detect_style(self, f0_curve, envelope, onset_frames, sr=None, hop_length=None):
        """
        Analyze performance characteristics to infer style.

        Detects:
        - Articulation: Legato vs Staccato (overlap vs gaps between notes)
        - Timing: Swing vs Straight (timing variations)
        - Expression: How much dynamics vary throughout performance

        Args:
            f0_curve: array of fundamental frequencies
            envelope: amplitude envelope (RMS per frame)
            onset_frames: array of frame indices where notes start
            sr: sample rate (uses self.sr if not provided)
            hop_length: hop length (uses self.hop_length if not provided)

        Returns:
            dict with:
                - articulation: "legato", "staccato", or "mixed"
                - timing: "straight", "swing", or "moderate_swing"
                - swing_factor: 0-1, degree of swing
                - expression: 0-1, how expressive the dynamics are
                - average_dynamics: mean amplitude level
        """

        if sr is None:
            sr = self.sr
        if hop_length is None:
            hop_length = self.hop_length

        if len(onset_frames) < 2:
            return {
                'articulation': 'unknown',
                'timing': 'unknown',
                'swing_factor': 0.5,
                'expression': 0.5,
                'average_dynamics': 0.0,
                'error': 'Not enough onsets to detect style'
            }

        # ─────────────────────────────────────────────────
        # Detect Legato vs Staccato
        # ─────────────────────────────────────────────────
        gap_count = 0
        overlap_count = 0

        for i in range(len(onset_frames) - 1):
            onset_start = onset_frames[i]
            onset_next = onset_frames[i + 1]

            # Check if there's a significant gap between notes
            # by looking at the envelope (amplitude)
            envelope_region = envelope[onset_start:onset_next]

            if len(envelope_region) > 0:
                env_max = np.max(envelope_region)
                env_min = np.min(envelope_region)

                # If envelope drops to <20% of its max value before next note = gap (staccato)
                if env_min < 0.2 * env_max:
                    gap_count += 1
                else:
                    overlap_count += 1

        total_transitions = gap_count + overlap_count
        if total_transitions > 0:
            gap_ratio = gap_count / total_transitions

            if gap_ratio > 0.6:
                articulation = "staccato"
            elif gap_ratio < 0.4:
                articulation = "legato"
            else:
                articulation = "mixed"
        else:
            articulation = "unknown"

        # ─────────────────────────────────────────────────
        # Detect Swing vs Straight
        # ─────────────────────────────────────────────────
        inter_onset_intervals = np.diff(onset_frames).astype(float)

        if len(inter_onset_intervals) > 1:
            timing_mean = np.mean(inter_onset_intervals)
            timing_std = np.std(inter_onset_intervals)

            # Coefficient of variation
            timing_cv = timing_std / timing_mean if timing_mean > 0 else 0

            # Low CV = straight, high CV = swing
            if timing_cv < 0.08:
                timing = "straight"
                swing_factor = 0.0
            elif timing_cv > 0.15:
                timing = "swing"
                swing_factor = min(1.0, timing_cv)  # Normalize to 0-1
            else:
                timing = "moderate_swing"
                swing_factor = timing_cv
        else:
            timing = "unknown"
            swing_factor = 0.5

        # ─────────────────────────────────────────────────
        # Detect Expression Level
        # ─────────────────────────────────────────────────
        envelope_nonzero = envelope[envelope > 0]

        if len(envelope_nonzero) > 0:
            # Expression = coefficient of variation in dynamics
            mean_envelope = np.mean(envelope_nonzero)
            std_envelope = np.std(envelope_nonzero)
            expression = std_envelope / mean_envelope if mean_envelope > 0 else 0

            # Clip to 0-1 range
            expression = min(1.0, max(0.0, expression))

            average_dynamics = float(mean_envelope)
        else:
            expression = 0.0
            average_dynamics = 0.0

        return {
            'articulation': articulation,
            'timing': timing,
            'swing_factor': float(swing_factor),
            'expression': float(expression),
            'average_dynamics': float(average_dynamics),
            'gap_ratio': float(gap_ratio) if total_transitions > 0 else None,
            'timing_cv': float(timing_cv) if len(inter_onset_intervals) > 1 else None
        }

    def detect_style_verbose(self, f0_curve, envelope, onset_frames, sr=None, hop_length=None, verbosity=1):
        """Detect style with progress messages"""

        if sr is None:
            sr = self.sr
        if hop_length is None:
            hop_length = self.hop_length

        if verbosity >= 1:
            print("[Style Detection]")
            print(f"  → Input: {len(f0_curve)} F0 frames, {len(onset_frames)} onsets")
            print(f"           Envelope range: {envelope.min():.4f} - {envelope.max():.4f}")

        result = self.detect_style(f0_curve, envelope, onset_frames, sr=sr, hop_length=hop_length)

        if 'error' not in result and verbosity >= 1:
            print(f"  ✓ Detected Style:")
            print(f"    - Articulation: {result['articulation']} (gap ratio: {result['gap_ratio']:.1%})")
            print(f"    - Timing: {result['timing']} (swing factor: {result['swing_factor']:.1%})")
            print(f"    - Expression: {result['expression']:.1%}")
            print(f"    - Average dynamics: {result['average_dynamics']:.3f}")

        return result


# ─────────────────────────────────────────────────────
# TEST / DEMONSTRATION
# ─────────────────────────────────────────────────────

if __name__ == "__main__":

    print("\n╔════════════════════════════════════════════════╗")
    print("║  MASTERCRAFTER STYLE DETECTOR TEST            ║")
    print("╚════════════════════════════════════════════════╝\n")

    sr = 44100
    hop_length = 512

    # Test 1: Legato style (no gaps between notes)
    print("Test 1: Legato style (overlapping notes)")
    print("─" * 50)

    duration = 2.0
    n_frames = int(duration * sr / hop_length)
    f0_curve = np.zeros(n_frames)
    envelope = np.zeros(n_frames)

    # Create legato notes: sustained envelope, no gaps
    note_durations = [0.5, 0.5, 0.5, 0.5]  # seconds
    onset_frames_legato = []

    current_frame = 0
    for note_dur in note_durations:
        onset_frames_legato.append(current_frame)

        note_frames = int(note_dur * sr / hop_length)

        # Frequency stays constant during note
        f0_curve[current_frame:current_frame + note_frames] = 440

        # Envelope: smooth decay but doesn't go to zero
        attack = np.linspace(0.0, 1.0, int(0.05 * sr / hop_length))
        sustain = 0.9 * np.ones(int((note_dur - 0.1) * sr / hop_length))
        release = np.linspace(0.9, 0.7, int(0.05 * sr / hop_length))

        note_envelope = np.concatenate([attack, sustain, release])
        if len(note_envelope) < note_frames:
            note_envelope = np.pad(note_envelope, (0, note_frames - len(note_envelope)), constant_values=0.7)
        else:
            note_envelope = note_envelope[:note_frames]

        envelope[current_frame:current_frame + note_frames] = note_envelope
        current_frame += note_frames

    onset_frames_legato = np.array(onset_frames_legato)

    print(f"  Note durations: {note_durations}")
    print(f"  Expected style: legato (no gaps)\n")

    detector = StyleDetector(sr=sr, hop_length=hop_length)
    result = detector.detect_style_verbose(f0_curve, envelope, onset_frames_legato, verbosity=1)
    print()

    # Test 2: Staccato style (gaps between notes)
    print("\nTest 2: Staccato style (short notes with gaps)")
    print("─" * 50)

    duration = 2.0
    n_frames = int(duration * sr / hop_length)
    f0_curve = np.zeros(n_frames)
    envelope = np.zeros(n_frames)

    # Create staccato notes: short envelopes that drop to zero
    onset_frames_staccato = []
    current_frame = 0

    for i in range(4):
        onset_frames_staccato.append(current_frame)

        # Short note (0.15s)
        note_frames = int(0.15 * sr / hop_length)
        gap_frames = int(0.35 * sr / hop_length)

        # Frequency
        f0_curve[current_frame:current_frame + note_frames] = 440

        # Envelope: quick attack/decay to zero
        note_envelope = np.hanning(note_frames * 2)[:note_frames]
        envelope[current_frame:current_frame + note_frames] = note_envelope

        current_frame += note_frames + gap_frames

    onset_frames_staccato = np.array(onset_frames_staccato)

    print(f"  Note duration: 0.15s, gap: 0.35s")
    print(f"  Expected style: staccato (clear gaps)\n")

    result = detector.detect_style_verbose(f0_curve, envelope, onset_frames_staccato, verbosity=1)
    print()

    # Test 3: Straight timing
    print("\nTest 3: Straight timing (regular rhythm)")
    print("─" * 50)

    # Regular onset spacing (0.5s intervals = 120 BPM)
    duration = 2.0
    n_frames = int(duration * sr / hop_length)

    onset_frames_straight = np.array([0, int(0.5 * sr / hop_length),
                                      int(1.0 * sr / hop_length),
                                      int(1.5 * sr / hop_length)])

    print(f"  Onset spacing: perfectly regular (0.5s intervals)")
    print(f"  Expected timing: straight\n")

    result = detector.detect_style_verbose(f0_curve, envelope, onset_frames_straight, verbosity=1)
    print()

    # Test 4: Swing timing
    print("\nTest 4: Swing timing (humanized rhythm)")
    print("─" * 50)

    # Add variation to onset spacing
    onset_frames_swing_raw = np.array([0, int(0.5 * sr / hop_length),
                                       int(1.0 * sr / hop_length),
                                       int(1.5 * sr / hop_length)])

    # Add ±10% timing variation
    variations = np.array([0, 0.1, -0.1, 0.08]) * int(0.5 * sr / hop_length)
    onset_frames_swing = (onset_frames_swing_raw + variations).astype(int)

    print(f"  Onset spacing: regular ±10% variation")
    print(f"  Expected timing: swing\n")

    result = detector.detect_style_verbose(f0_curve, envelope, onset_frames_swing, verbosity=1)
