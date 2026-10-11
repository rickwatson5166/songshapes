#!/usr/bin/env python3
"""
Mastercrafter Tempo Extractor
Infer musical tempo from onset timing analysis
"""

import numpy as np
from scipy.cluster.hierarchy import fclusterdata


class TempoExtractor:
    """Infer musical tempo from performance timing"""

    def __init__(self, sr=44100, hop_length=512):
        self.sr = sr
        self.hop_length = hop_length

    def extract_tempo(self, onset_frames, sr=None, hop_length=None):
        """
        Estimate tempo by analyzing spacing between note onsets.

        Approach:
        - Convert frame indices to time in seconds
        - Calculate inter-onset intervals (time between each note)
        - Find most common interval using clustering
        - Convert to BPM (beats per minute)
        - Infer time signature (usually 4/4)

        Args:
            onset_frames: array of frame indices where notes start
            sr: sample rate (uses self.sr if not provided)
            hop_length: hop length used in frame calculation (uses self.hop_length if not provided)

        Returns:
            dict with:
                - tempo_bpm: detected tempo in beats per minute
                - time_signature: inferred time signature (e.g., "4/4")
                - beat_interval_seconds: duration of one beat
                - confidence: 0-1 confidence in the estimate
        """

        if sr is None:
            sr = self.sr
        if hop_length is None:
            hop_length = self.hop_length

        if len(onset_frames) < 2:
            return {
                'tempo_bpm': 120,  # Default fallback
                'time_signature': '4/4',
                'beat_interval_seconds': 0.5,
                'confidence': 0.0,
                'error': 'Not enough onsets to estimate tempo'
            }

        # Step 1: Convert frame indices to time in seconds
        onset_times = onset_frames * hop_length / sr

        # Step 2: Calculate intervals between consecutive onsets
        intervals = np.diff(onset_times)

        if len(intervals) < 2:
            return {
                'tempo_bpm': 120,
                'time_signature': '4/4',
                'beat_interval_seconds': 0.5,
                'confidence': 0.0,
                'error': 'Not enough intervals to estimate tempo'
            }

        # Step 3: Find most common interval using hierarchical clustering
        # This handles variations in performance timing (some notes held longer)
        try:
            clusters = fclusterdata(
                intervals.reshape(-1, 1),
                t=0.1,  # Distance threshold for clustering
                criterion='distance',
                method='complete'
            )

            unique_clusters, counts = np.unique(clusters, return_counts=True)
            most_common_cluster = unique_clusters[np.argmax(counts)]
            beat_intervals = intervals[clusters == most_common_cluster]
            beat_interval = np.median(beat_intervals)

        except:
            # Fallback if clustering fails
            beat_interval = np.median(intervals)

        # Step 4: Convert beat interval to BPM
        # BPM = 60 seconds / beat_interval_in_seconds
        if beat_interval > 0:
            tempo_bpm = 60.0 / beat_interval
        else:
            return {
                'tempo_bpm': 120,
                'time_signature': '4/4',
                'beat_interval_seconds': 0.5,
                'confidence': 0.0,
                'error': 'Invalid beat interval'
            }

        # Step 5: Quantize to nearest sensible tempo (round to 5 BPM)
        tempo_bpm_quantized = round(tempo_bpm / 5) * 5

        # Step 6: Clamp to reasonable range (40-200 BPM for most music)
        tempo_bpm_final = np.clip(tempo_bpm_quantized, 40, 200)

        # Step 7: Infer time signature (4/4 is most common)
        # Could be refined by analyzing accent patterns, but 4/4 is safest default
        time_signature = "4/4"

        # Confidence based on interval consistency
        interval_std = np.std(beat_intervals)
        interval_mean = np.mean(beat_intervals)
        coefficient_of_variation = interval_std / interval_mean if interval_mean > 0 else 1.0

        # Lower variation = higher confidence
        confidence = max(0.0, 1.0 - coefficient_of_variation)

        return {
            'tempo_bpm': int(tempo_bpm_final),
            'time_signature': time_signature,
            'beat_interval_seconds': float(beat_interval),
            'confidence': float(confidence),
            'raw_tempo_bpm': float(tempo_bpm),
            'interval_std': float(interval_std),
            'interval_mean': float(interval_mean)
        }

    def extract_tempo_verbose(self, onset_frames, sr=None, hop_length=None, verbosity=1):
        """Extract tempo with progress messages"""

        if sr is None:
            sr = self.sr
        if hop_length is None:
            hop_length = self.hop_length

        if verbosity >= 1:
            print("[Tempo Extraction]")
            print(f"  → Input: {len(onset_frames)} onset frames")

        result = self.extract_tempo(onset_frames, sr=sr, hop_length=hop_length)

        if 'error' not in result and verbosity >= 1:
            print(f"  → Inter-onset intervals: mean={result['interval_mean']:.3f}s, std={result['interval_std']:.3f}s")
            print(f"  ✓ Detected Tempo: {result['tempo_bpm']} BPM ({result['time_signature']})")
            print(f"    Confidence: {result['confidence']:.1%}")

        return result


# ─────────────────────────────────────────────────────
# TEST / DEMONSTRATION
# ─────────────────────────────────────────────────────

if __name__ == "__main__":

    print("\n╔════════════════════════════════════════════════╗")
    print("║  MASTERCRAFTER TEMPO EXTRACTOR TEST           ║")
    print("╚════════════════════════════════════════════════╝\n")

    sr = 44100
    hop_length = 512

    # Test 1: Regular 120 BPM pattern (0.5 second intervals between notes)
    print("Test 1: Regular 120 BPM (quarter-note onsets)")
    print("─" * 50)

    tempo_bpm = 120
    beat_interval = 60.0 / tempo_bpm  # seconds

    # Create regular onsets at 0.5s intervals (120 BPM quarter notes)
    onset_times = np.arange(0, 8, beat_interval)
    onset_frames = (onset_times * sr / hop_length).astype(int)

    print(f"  Beat interval: {beat_interval:.3f}s")
    print(f"  Expected tempo: {tempo_bpm} BPM")
    print(f"  Onset frames: {onset_frames[:5]} ... (total: {len(onset_frames)})\n")

    extractor = TempoExtractor(sr=sr, hop_length=hop_length)
    result = extractor.extract_tempo_verbose(onset_frames, verbosity=1)

    print(f"  ✓ Detected: {result['tempo_bpm']} BPM")
    print()

    # Test 2: Varied timing (slightly humanized)
    print("\nTest 2: Humanized timing (±5% variation)")
    print("─" * 50)

    onset_times_varied = []
    for i, t in enumerate(onset_times):
        # Add ±5% timing variation
        variation = np.random.randn() * 0.05 * beat_interval
        onset_times_varied.append(t + variation)

    onset_times_varied = np.array(onset_times_varied)
    onset_frames_varied = (onset_times_varied * sr / hop_length).astype(int)

    print(f"  Timing variation: ±5% of beat interval")
    print(f"  Expected tempo: ~{tempo_bpm} BPM\n")

    result_varied = extractor.extract_tempo_verbose(onset_frames_varied, verbosity=1)

    print(f"  ✓ Detected: {result_varied['tempo_bpm']} BPM")
    print()

    # Test 3: Slow tempo (60 BPM)
    print("\nTest 3: Slow tempo (60 BPM)")
    print("─" * 50)

    tempo_bpm_slow = 60
    beat_interval_slow = 60.0 / tempo_bpm_slow
    onset_times_slow = np.arange(0, 8, beat_interval_slow)
    onset_frames_slow = (onset_times_slow * sr / hop_length).astype(int)

    print(f"  Beat interval: {beat_interval_slow:.3f}s")
    print(f"  Expected tempo: {tempo_bpm_slow} BPM\n")

    result_slow = extractor.extract_tempo_verbose(onset_frames_slow, verbosity=1)

    print(f"  ✓ Detected: {result_slow['tempo_bpm']} BPM")
    print()

    # Test 4: Fast tempo (160 BPM)
    print("\nTest 4: Fast tempo (160 BPM)")
    print("─" * 50)

    tempo_bpm_fast = 160
    beat_interval_fast = 60.0 / tempo_bpm_fast
    onset_times_fast = np.arange(0, 8, beat_interval_fast)
    onset_frames_fast = (onset_times_fast * sr / hop_length).astype(int)

    print(f"  Beat interval: {beat_interval_fast:.3f}s")
    print(f"  Expected tempo: {tempo_bpm_fast} BPM\n")

    result_fast = extractor.extract_tempo_verbose(onset_frames_fast, verbosity=1)

    print(f"  ✓ Detected: {result_fast['tempo_bpm']} BPM")
