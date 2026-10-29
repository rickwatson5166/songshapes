#!/usr/bin/env python3
"""
Tests for the approved-reference library.

These cover the two invariants the library exists to hold:

  * nothing contributes to a style target unless it has been approved with a
    stated rights basis, and
  * a stored profile cannot carry data that would reconstruct the recording.

Both are the sort of property that can regress quietly -- a profile gains a
field, a gate gets loosened for convenience -- so they are asserted rather
than assumed.

Run:  python3 test_reference_library.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Point the store at a scratch directory before importing the library, since
# both read DATA_ROOT at import time.
_TMP = tempfile.mkdtemp(prefix="songshapes_test_")
os.environ["SONGSHAPES_DATA"] = _TMP

import numpy as np
import soundfile as sf

import songshapes_store as store
import reference_library as lib

store.DATA_ROOT = _TMP
store.JOBS_ROOT = os.path.join(_TMP, "jobs")
lib.REFS_ROOT = os.path.join(_TMP, "references")

PASSED = []
FAILED = []


def check(label, condition, detail=""):
    if condition:
        PASSED.append(label)
        print(f"  pass  {label}")
    else:
        FAILED.append((label, detail))
        print(f"  FAIL  {label}  {detail}")


def make_audio(path, notes, note_dur=0.5, sr=22050):
    """Write a short synthetic monophonic phrase."""
    chunks = []
    for freq in notes:
        t = np.linspace(0, note_dur, int(sr * note_dur), endpoint=False)
        env = np.exp(-3.0 * t) * (1 - np.exp(-200 * t))
        sig = np.sin(2 * np.pi * freq * t) + 0.4 * np.sin(2 * np.pi * 2 * freq * t)
        chunks.append((sig * env).astype(np.float32))
    audio = np.concatenate(chunks)
    audio = audio / np.max(np.abs(audio)) * 0.8
    sf.write(path, audio, sr, subtype="PCM_16")
    return path


# ─────────────────────────────────────────────────

def test_profile_validator():
    print("\nnon-reconstruction guard")
    from reference_library import ProfileNotAllowed, validate_profile

    def rejects(payload):
        try:
            validate_profile(payload)
            return False
        except ProfileNotAllowed:
            return True

    check("rejects a pitch contour", rejects({"f0": [100.0, 110.0]}))
    check("rejects onset times", rejects({"t": {"onset_times": [0.1, 0.2]}}))
    check("rejects a literal chord progression",
          rejects({"chord_progression": ["C major", "G major"]}))
    check("rejects an audio buffer", rejects({"audio": [0.0, 0.1]}))
    check("rejects a long sequence", rejects({"x": list(range(_over_limit())) }))
    check("rejects a raw numpy array", rejects({"bins": np.zeros(12)}))
    check("rejects a nested forbidden key",
          rejects({"a": {"b": {"envelope": [1, 2, 3]}}}))

    # A real profile shape must still pass.
    ok = {
        "mode": "minor",
        "tempo_bpm": 96.0,
        "interval_weights": {"bins": [0.04] * 25, "span_semitones": 12},
        "ioi": {"cv": 0.2, "ratio_bins": [0.125] * 8},
        "dynamics": {"mean": 0.1, "std": 0.02, "range": 0.4, "crest": 3.1},
    }
    check("accepts a legitimate profile", validate_profile(ok) is True)


def _over_limit():
    return 33  # one past _MAX_PROFILE_LIST


def test_rights_gate():
    print("\nconsent gate")
    path = make_audio(os.path.join(_TMP, "a.wav"), [220, 262, 330, 294])

    meta = lib.create_reference(path, title="unspecified rights")
    check("new entry is unapproved", meta["approved"] is False)
    check("new entry defaults to no rights basis",
          meta["rights_basis"] == "unspecified")
    check("unapproved entry is not usable", lib.is_usable(meta) is False)

    # Approving with no rights basis must fail.
    try:
        lib.approve(meta["ref_id"], approved_by="Someone")
        check("refuses approval without a rights basis", False,
              "approval succeeded")
    except ValueError:
        check("refuses approval without a rights basis", True)

    # Approving with no approver must fail.
    try:
        lib.approve(meta["ref_id"], approved_by="",
                    rights_basis="own-composition-own-recording")
        check("refuses approval with no approver", False, "approval succeeded")
    except ValueError:
        check("refuses approval with no approver", True)

    # A bogus basis must be rejected outright.
    try:
        lib.create_reference(path, rights_basis="because-i-said-so")
        check("rejects an unknown rights basis", False, "accepted")
    except ValueError:
        check("rejects an unknown rights basis", True)

    approved = lib.approve(meta["ref_id"], approved_by="Rick Watson",
                           rights_basis="own-composition-own-recording")
    check("approves once a basis and approver are given",
          lib.is_usable(approved) is True)

    revoked = lib.revoke(meta["ref_id"], reason="rights unclear")
    check("revocation removes usability", lib.is_usable(revoked) is False)
    check("revoked entry is retained for audit",
          lib.load_reference(meta["ref_id"]) is not None)


def test_style_target_respects_approval():
    print("\nstyle target")
    _clear_refs()

    yes = lib.create_reference(
        make_audio(os.path.join(_TMP, "y.wav"), [220, 262, 330, 294, 220]),
        title="cleared", rights_basis="own-composition-own-recording")
    no = lib.create_reference(
        make_audio(os.path.join(_TMP, "n.wav"), [196, 247, 294, 330]),
        title="on hold")

    empty = lib.style_target()
    check("no approvals yields no style target",
          empty["source_count"] == 0 and empty["profile"] is None)

    lib.approve(yes["ref_id"], approved_by="Rick Watson")
    target = lib.style_target()

    titles = [s["title"] for s in target["sources"]]
    check("approved entry contributes", "cleared" in titles)
    check("unapproved entry does not contribute", "on hold" not in titles)
    check("source count matches approvals", target["source_count"] == 1)
    check("target cites its sources",
          all(s.get("ref_id") and s.get("approved_by")
              for s in target["sources"]))
    check("blended target is itself non-reconstructive",
          lib.validate_profile(target["profile"]) is True)

    # Revoking must drop it back out of the blend.
    lib.revoke(yes["ref_id"])
    check("revoked entry leaves the blend",
          lib.style_target()["source_count"] == 0)
    _ = no


def test_profile_contents():
    print("\nprofile contents")
    _clear_refs()
    meta = lib.create_reference(
        make_audio(os.path.join(_TMP, "p.wav"), [220, 262, 330, 294, 247, 220]),
        title="profile shape", rights_basis="own-composition-own-recording")
    profile = lib.load_reference(meta["ref_id"])["profile"]

    check("records a mode", profile.get("mode") in ("major", "minor", "unknown"))
    check("records a tempo", isinstance(profile.get("tempo_bpm"), float))
    check("scale degrees are 12 normalized bins",
          len(profile["scale_degree_weights"]["bins"]) == 12
          and abs(sum(profile["scale_degree_weights"]["bins"]) - 1.0) < 0.01)
    check("intervals span an octave either way",
          len(profile["interval_weights"]["bins"]) == 25)
    check("records a dynamics summary",
          set(profile["dynamics"]) == {"mean", "std", "range", "crest"})
    check("profile holds no forbidden field",
          lib.validate_profile(profile) is True)

    check("audio is not retained by default",
          not os.path.exists(lib.ref_path(meta["ref_id"], "source.wav")))
    check("source hash is recorded for audit",
          isinstance(meta.get("source_sha256"), str)
          and len(meta["source_sha256"]) == 64)


def _clear_refs():
    import shutil
    if os.path.isdir(lib.REFS_ROOT):
        shutil.rmtree(lib.REFS_ROOT)


def main():
    print("reference library tests")
    print(f"scratch: {_TMP}")

    test_profile_validator()
    test_rights_gate()
    test_style_target_respects_approval()
    test_profile_contents()

    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
    if FAILED:
        for label, detail in FAILED:
            print(f"  FAILED: {label} {detail}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
