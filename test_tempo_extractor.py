#!/usr/bin/env python3
"""
Tests for tempo extraction.

The regression here: extract_tempo takes the most common inter-onset interval
as the beat, but on real music that interval is usually a subdivision. Eighth
notes at 108 BPM cluster near 0.28s, which reads as ~215 BPM. A clamp to
40-200 then absorbed the overflow into a flat "200", so a doubled estimate was
indistinguishable from a measured one.

Octave folding corrects that. What it deliberately does NOT do is resolve the
real ambiguity between 60 BPM in quarter notes and 120 BPM in half notes --
those produce identical onset spacing, so an estimate already in the musical
band is left alone.

Run:  python3 test_tempo_extractor.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

from mastercrafter_tempo_extractor import TempoExtractor

SR = 44100
HOP = 512

PASSED = []
FAILED = []


def check(label, condition, detail=""):
    if condition:
        PASSED.append(label)
        print(f"  pass  {label}")
    else:
        FAILED.append((label, detail))
        print(f"  FAIL  {label}  {detail}")


def onsets_at(bpm, subdivision=1, bars=8, beats_per_bar=4, jitter=0.0, seed=0):
    """
    Frame indices for onsets at `subdivision` events per beat.

    subdivision=1 is quarter notes, 2 eighths, 4 sixteenths.
    """
    beat = 60.0 / bpm
    step = beat / subdivision
    count = int(bars * beats_per_bar * subdivision)
    times = np.arange(count) * step
    if jitter:
        rng = np.random.default_rng(seed)
        times = times + rng.normal(0, jitter * step, times.shape)
        times = np.clip(times, 0, None)
    return (np.sort(times) * SR / HOP).astype(int)


def detect(onset_frames):
    extractor = TempoExtractor(sr=SR, hop_length=HOP)
    return extractor.extract_tempo(onset_frames, sr=SR, hop_length=HOP)


def main():
    print("tempo extractor tests")

    print("\nquarter-note onsets are read directly")
    for bpm in (60, 90, 120, 160):
        result = detect(onsets_at(bpm))
        check(f"{bpm} BPM in quarters reads as {bpm}",
              abs(result["tempo_bpm"] - bpm) <= 5,
              f"got {result['tempo_bpm']}")

    print("\nsubdivisions no longer double the tempo")
    # The actual regression: eighths at 108 used to report 200 (clamped).
    result = detect(onsets_at(108, subdivision=2))
    check("eighths at 108 BPM fold back near 108",
          abs(result["tempo_bpm"] - 108) <= 8,
          f"got {result['tempo_bpm']}")
    check("the fold is recorded, not silent",
          result.get("tempo_octave_factor") == 0.5,
          f"factor was {result.get('tempo_octave_factor')}")
    check("raw estimate is still reported",
          result.get("raw_tempo_bpm", 0) > 180,
          f"raw was {result.get('raw_tempo_bpm')}")

    result = detect(onsets_at(143, subdivision=2))
    check("eighths at 143 BPM fold back near 143",
          abs(result["tempo_bpm"] - 143) <= 8,
          f"got {result['tempo_bpm']}")

    result = detect(onsets_at(120, subdivision=4))
    check("sixteenths at 120 BPM fold into the musical band",
          60 <= result["tempo_bpm"] <= 180,
          f"got {result['tempo_bpm']}")

    print("\nno silent clamping")
    # A flat 200 was the old tell-tale of an absorbed overflow.
    for bpm, sub in ((108, 2), (143, 2), (120, 4), (160, 2)):
        result = detect(onsets_at(bpm, subdivision=sub))
        check(f"{bpm} BPM / {sub}x subdivision does not report a flat 200",
              result["tempo_bpm"] != 200,
              "got exactly 200, the old clamp value")

    print("\nestimates inside the band are left alone")
    # 60 vs 120 cannot be told apart from onset spacing; the extractor should
    # not invent a preference.
    result = detect(onsets_at(60))
    check("60 BPM is not pulled toward 120",
          result["tempo_bpm"] == 60 and result["tempo_octave_factor"] == 1.0,
          f"got {result['tempo_bpm']} factor {result.get('tempo_octave_factor')}")

    result = detect(onsets_at(160))
    check("160 BPM is not halved",
          result["tempo_octave_factor"] == 1.0,
          f"factor was {result.get('tempo_octave_factor')}")

    print("\nhumanized timing still resolves")
    result = detect(onsets_at(120, jitter=0.05))
    check("120 BPM with 5% jitter stays near 120",
          abs(result["tempo_bpm"] - 120) <= 10,
          f"got {result['tempo_bpm']}")

    print("\ndegenerate input")
    result = detect(np.array([0]))
    check("single onset falls back without raising",
          result["tempo_bpm"] == 120 and result["confidence"] == 0.0)
    result = detect(np.array([]))
    check("no onsets falls back without raising",
          result["tempo_bpm"] == 120)

    print("\noctave folding unit behaviour")
    fold = TempoExtractor._fold_tempo_octave
    check("folds 215 down to ~107", abs(fold(215.0)[0] - 107.5) < 0.1)
    check("folds 40 up to 80", abs(fold(40.0)[0] - 80.0) < 0.1)
    check("leaves 120 untouched", fold(120.0) == (120.0, 1.0))
    check("handles zero without raising", fold(0.0)[0] == 120.0)
    check("handles nan without raising", fold(float('nan'))[0] == 120.0)

    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
    if FAILED:
        for label, detail in FAILED:
            print(f"  FAILED: {label} {detail}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
