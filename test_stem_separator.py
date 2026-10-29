#!/usr/bin/env python3
"""
Tests for HPSS stem separation.

Both cases here are regressions for bugs the separator shipped with:

  * `_split_harmonic_by_freq` built a (n_freqs, 1) boolean mask and used it to
    index a (n_freqs, n_frames) array. numpy matches boolean axes by size, so
    this raised IndexError on every input -- the separator could not run at
    all.

  * The band splits ran in an order that high-passed at 80 Hz before carving
    out bass, so the bass stem only ever received 80-200 Hz and everything
    below 80 Hz went to "other". A bass guitar's low E is about 41 Hz, so the
    stem was missing the fundamentals it exists to isolate.

The signal is synthetic and deliberately unambiguous: a low sine well under
80 Hz, a mid chord, and short noise bursts. Each stem should claim its own
component.

Run:  python3 test_stem_separator.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

PASSED = []
FAILED = []

SR = 22050
DURATION = 4.0
BASS_HZ = 55.0           # low A -- below the old 80 Hz cutoff
CHORD_HZ = (440.0, 660.0, 880.0)


def check(label, condition, detail=""):
    if condition:
        PASSED.append(label)
        print(f"  pass  {label}")
    else:
        FAILED.append((label, detail))
        print(f"  FAIL  {label}  {detail}")


def build_mix():
    """A mix whose three components sit in clearly separate places."""
    t = np.linspace(0, DURATION, int(SR * DURATION), endpoint=False)
    rng = np.random.default_rng(0)

    chord = sum(0.3 * np.sin(2 * np.pi * f * t) for f in CHORD_HZ)
    bass = 0.5 * np.sin(2 * np.pi * BASS_HZ * t)

    percussive = np.zeros_like(t)
    for hit in np.arange(0.0, DURATION, 0.5):
        start = int(hit * SR)
        length = min(int(0.02 * SR), len(percussive) - start)
        if length <= 0:
            continue
        burst = rng.normal(0, 1, length) * np.exp(-np.linspace(0, 8, length))
        percussive[start:start + length] += burst

    mix = chord + bass + percussive * 1.5
    return (mix / np.max(np.abs(mix)) * 0.85).astype(np.float32)


def peak_freq(signal):
    if len(signal) == 0:
        return 0.0
    spectrum = np.abs(np.fft.rfft(signal))
    freqs = np.fft.rfftfreq(len(signal), 1 / SR)
    return float(freqs[int(np.argmax(spectrum))])


def rms(signal):
    signal = np.asarray(signal, dtype=float)
    return float(np.sqrt(np.mean(signal ** 2))) if signal.size else 0.0


def main():
    print("stem separator tests")

    try:
        from mastercrafter_capture_station import HPSSStemSeparator
    except ImportError as exc:
        print(f"  cannot import separator: {exc}")
        return 1

    mix = build_mix()
    separator = HPSSStemSeparator(sr=SR, margin=1.0)

    # Regression: this call raised IndexError unconditionally.
    try:
        stems = separator.separate(mix)
    except Exception as exc:
        check("separate() runs without raising", False, f"{type(exc).__name__}: {exc}")
        print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
        return 1

    check("separate() runs without raising", True)

    print("\nstem shape")
    check("returns the four expected stems",
          set(stems) == {"vocals", "drums", "bass", "other"},
          f"got {sorted(stems)}")

    lengths = {len(np.asarray(v)) for v in stems.values()}
    check("all stems share one length", len(lengths) == 1, f"lengths={lengths}")

    print("\nband assignment")
    bass_peak = peak_freq(np.asarray(stems["bass"]))
    check("bass stem peaks near the low fundamental",
          abs(bass_peak - BASS_HZ) < 15.0,
          f"peak was {bass_peak:.1f} Hz, expected ~{BASS_HZ:.0f} Hz")

    # Regression: bass used to arrive at ~0.0002 rms because sub-80 Hz content
    # was routed to "other" before the bass split ran.
    check("bass stem carries real level",
          rms(stems["bass"]) > 0.01,
          f"rms was {rms(stems['bass']):.6f}")

    check("low fundamental is not dumped into 'other'",
          rms(stems["bass"]) > rms(stems["other"]),
          f"bass={rms(stems['bass']):.6f} other={rms(stems['other']):.6f}")

    vocal_peak = peak_freq(np.asarray(stems["vocals"]))
    check("vocal band peaks within the mid chord",
          min(CHORD_HZ) - 50 <= vocal_peak <= max(CHORD_HZ) + 50,
          f"peak was {vocal_peak:.1f} Hz")

    check("percussive stem is high-band broadband",
          peak_freq(np.asarray(stems["drums"])) > 2000.0,
          f"peak was {peak_freq(np.asarray(stems['drums'])):.1f} Hz")

    print("\nenergy sanity")
    check("no stem is entirely silent",
          all(rms(v) > 0 for v in stems.values()))
    check("separation preserves a sane total level",
          rms(sum(np.asarray(v) for v in stems.values())) > 0.01)

    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
    if FAILED:
        for label, detail in FAILED:
            print(f"  FAILED: {label} {detail}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
