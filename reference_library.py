#!/usr/bin/env python3
"""
SongShapes approved-reference library.

Purpose: let the generators match a style drawn only from recordings whose
use has been explicitly approved, with the rights basis recorded alongside.

Two rules shape this module.

1. Consent is a gate, not a label. An entry is written with approved=False
   and contributes nothing until someone sets an approval with a rights
   basis. `style_target()` only ever reads approved entries, so forgetting to
   approve fails closed.

2. The library stores style, not songs. What goes in a profile is aggregate
   distribution data -- how often you move by a third, how wide your dynamics
   run, whether you sit ahead of or behind the beat. What stays out is
   anything that could rebuild a performance: the pitch contour, onset times,
   the literal chord sequence, the audio. `validate_profile()` enforces that,
   so a future change that starts storing sequences fails a test instead of
   quietly turning a style model into a copy of the recording.

Audio is discarded after extraction unless an entry explicitly opts to retain
it, so masters need not live in the repo.

Layout:
    <data_root>/references/<ref_id>/
        meta.json      provenance, rights basis, approval
        profile.json   non-reconstructive style features
        source.wav     only when retain_audio is set
"""

import hashlib
import os
import time
import uuid

import numpy as np

import songshapes_store as store

REFS_ROOT = os.path.join(store.DATA_ROOT, "references")

# How a reference may be used. Recorded per entry so the basis for each is
# auditable later; "unspecified" cannot be approved.
RIGHTS_BASES = (
    "own-composition-own-recording",     # wrote it, played it, hold the master
    "own-composition-other-performers",  # wrote it, others played on it
    "band-recording-shared-rights",      # band recording, rights shared
    "licensed",                          # written permission on file
    "public-domain",
    "unspecified",
)

# What kind of recording a profile was taken from. This decides which fields
# mean anything: the same extraction run on a finished master and on a solo
# take produce the same field names but not the same trustworthiness.
SOURCE_TYPES = (
    "solo-performance",      # one instrument or voice alone, as played
    "isolated-track",        # a single track lifted from a multitrack
    "separated-stem",        # output of stem separation
    "full-mix-unmastered",   # rough or pre-master mix
    "full-mix-mastered",     # finished, limited master
    "unspecified",
)

_MIXED_SOURCES = ("separated-stem", "full-mix-unmastered", "full-mix-mastered",
                  "unspecified")
_MASTERED_SOURCES = ("full-mix-mastered",)

# Why a field cannot be trusted, by cause. Kept as prose because the reason is
# the useful part -- a bare "unreliable" flag tells a future reader nothing.
_WHY = {
    "mastered": "mastering limits dynamics before analysis, so this measures "
                "the master rather than the performance",
    "mixed": "onsets and envelope come from every instrument at once, so this "
             "describes the mix rather than one player",
    "polyphonic": "pitch tracking cannot follow a single line through "
                  "simultaneous notes, so this is not a melodic measurement",
    "not-measured": "not measured: the extractor hardcodes this value",
}

# Fields whose meaning depends on dynamics surviving to the analyzer.
_DYNAMICS_FIELDS = ("expression", "dynamics")
# Fields that need one player in isolation to mean anything.
_ISOLATION_FIELDS = ("articulation", "gap_ratio", "timing", "swing_factor",
                     "ioi")
# Fields that need a monophonic line.
_MONOPHONIC_FIELDS = ("interval_weights", "pitch_range_semitones")
# Fields the extractor never actually measures.
_CONSTANT_FIELDS = ("time_signature",)


def unreliable_fields(source_type, monophonic=None):
    """
    Return {field: reason} for fields that cannot be trusted from this kind of
    source.

    Reliability is a property of the recording, not of the code, so it is
    derived here rather than stored -- re-deriving it keeps old entries honest
    when the rules improve.
    """
    source_type = source_type or "unspecified"
    out = {}

    for field in _CONSTANT_FIELDS:
        out[field] = _WHY["not-measured"]

    if source_type in _MASTERED_SOURCES:
        for field in _DYNAMICS_FIELDS:
            out[field] = _WHY["mastered"]

    if source_type in _MIXED_SOURCES:
        for field in _ISOLATION_FIELDS:
            out[field] = _WHY["mixed"]

    # A strummed guitar on its own track is still polyphonic, so isolation
    # alone does not make a pitch line trustworthy -- it has to be stated.
    if monophonic is not True:
        for field in _MONOPHONIC_FIELDS:
            out[field] = _WHY["polyphonic"]

    return out


def reliable_profile(meta, profile):
    """
    Split a profile into what this source can support and what it cannot.

    Returns (trusted, withheld) where withheld maps field -> reason.
    """
    withheld = unreliable_fields(meta.get("source_type"),
                                 meta.get("monophonic"))
    trusted = {k: v for k, v in (profile or {}).items() if k not in withheld}
    return trusted, {k: v for k, v in withheld.items() if k in (profile or {})}

# Keys that must never appear anywhere in a profile. These are the fields that
# would make a profile a reconstruction rather than a description.
_FORBIDDEN_PROFILE_KEYS = {
    "f0", "f0_curve", "voiced_flag", "envelope", "rms_curve",
    "onset_times", "onset_frames", "audio", "harmonic", "percussive",
    "chord_progression", "notes", "pitch_sequence", "waveform", "samples",
}

# No list in a profile may be longer than this. Histograms are small; a
# performance trace is not.
_MAX_PROFILE_LIST = 32

PITCH_CLASSES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


# ─────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────

def refs_root():
    os.makedirs(REFS_ROOT, exist_ok=True)
    return REFS_ROOT


def ref_dir(ref_id, create=False):
    safe = os.path.basename(str(ref_id))
    if not safe or safe in (".", ".."):
        raise ValueError(f"invalid reference id: {ref_id!r}")
    path = os.path.join(refs_root(), safe)
    if create:
        os.makedirs(path, exist_ok=True)
    return path


def ref_path(ref_id, *parts):
    return os.path.join(ref_dir(ref_id), *parts)


# ─────────────────────────────────────────────────
# Profile validation
# ─────────────────────────────────────────────────

class ProfileNotAllowed(ValueError):
    """A profile carried data that could reconstruct the source recording."""


def validate_profile(profile, _path="profile"):
    """
    Raise ProfileNotAllowed if a profile holds reconstructive data.

    Called on every write. The point is that the restriction is checkable
    rather than a matter of intent.
    """
    if isinstance(profile, dict):
        for key, value in profile.items():
            if str(key).lower() in _FORBIDDEN_PROFILE_KEYS:
                raise ProfileNotAllowed(
                    f"{_path}.{key}: '{key}' can reconstruct the recording and "
                    f"must not be stored in a reference profile"
                )
            validate_profile(value, f"{_path}.{key}")
    elif isinstance(profile, (list, tuple)):
        if len(profile) > _MAX_PROFILE_LIST:
            raise ProfileNotAllowed(
                f"{_path}: list of {len(profile)} items exceeds the "
                f"{_MAX_PROFILE_LIST}-item limit; store a summary, not a trace"
            )
        for index, value in enumerate(profile):
            validate_profile(value, f"{_path}[{index}]")
    elif isinstance(profile, np.ndarray):
        raise ProfileNotAllowed(f"{_path}: raw arrays must not be stored")
    return True


# ─────────────────────────────────────────────────
# Feature reduction
# ─────────────────────────────────────────────────

def build_profile(performance, understanding):
    """
    Reduce a performance blueprint and its Stage 1 understanding to a style
    profile: scalars, categories and small normalized histograms.
    """
    key_info = understanding.get("key") or {}
    tempo_info = understanding.get("tempo") or {}
    style_info = understanding.get("style") or {}
    chord_info = understanding.get("chords") or {}

    key_name = key_info.get("key") or "Unknown"
    mode = "minor" if "minor" in str(key_name).lower() else (
        "major" if "major" in str(key_name).lower() else "unknown")
    root_midi = key_info.get("root_midi")

    f0 = np.asarray(performance.get("f0", []), dtype=float)
    voiced = f0[f0 > 0]
    onsets = np.asarray(performance.get("onset_times", []), dtype=float)
    rms = np.asarray(performance.get("rms", []), dtype=float)

    profile = {
        # ── Tonality: degrees relative to the tonic, not absolute pitches.
        "mode": mode,
        "scale_degree_weights": _scale_degree_weights(voiced, root_midi),

        # ── Melodic motion: how far it tends to move, not where it went.
        "interval_weights": _interval_weights(voiced),
        "pitch_range_semitones": _range_semitones(voiced),

        # ── Rhythm: density and evenness of attacks.
        "tempo_bpm": _as_float(tempo_info.get("tempo_bpm")),
        "time_signature": tempo_info.get("time_signature"),
        "onset_density_per_sec": _onset_density(onsets, understanding),
        "ioi": _ioi_stats(onsets),

        # ── Feel.
        "articulation": style_info.get("articulation"),
        "timing": style_info.get("timing"),
        "expression": _as_float(style_info.get("expression")),
        "swing_factor": _as_float(style_info.get("swing_factor")),
        "gap_ratio": _as_float(style_info.get("gap_ratio")),

        # ── Dynamics.
        "dynamics": _dynamics_stats(rms),

        # ── Harmony: vocabulary and movement, not the progression itself.
        "chord_quality_weights": _chord_quality_weights(chord_info),
        "chord_root_motion_weights": _chord_motion_weights(chord_info, root_midi),

        # ── Timbre.
        "harmonic_ratio": _as_float(performance.get("harmonic_ratio")),
    }

    validate_profile(profile)
    return profile


def _as_float(value, default=None):
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    if out != out or out in (float("inf"), float("-inf")):
        return default
    return out


def _normalize(counts):
    total = float(np.sum(counts))
    if total <= 0:
        return [0.0] * len(counts)
    return [round(float(c) / total, 5) for c in counts]


def _hz_to_midi(hz):
    hz = np.asarray(hz, dtype=float)
    hz = hz[hz > 0]
    if hz.size == 0:
        return np.array([])
    return 12.0 * np.log2(hz / 440.0) + 69.0


def _scale_degree_weights(voiced_f0, root_midi):
    """
    Twelve bins: how much time the performance spends on each scale degree
    relative to the tonic. Transposition-invariant, so it describes a habit
    rather than a particular song.
    """
    midi = _hz_to_midi(voiced_f0)
    if midi.size == 0:
        return {"bins": _normalize(np.zeros(12)), "labels": list(range(12))}

    root = root_midi if isinstance(root_midi, (int, float)) else float(np.min(midi))
    degrees = np.mod(np.round(midi - float(root)).astype(int), 12)
    counts = np.bincount(degrees, minlength=12)[:12]
    return {"bins": _normalize(counts), "labels": list(range(12))}


def _interval_weights(voiced_f0, span=12):
    """
    Distribution of melodic steps in semitones, clamped to +/- an octave.
    Captures whether the line walks or leaps without recording the line.
    """
    midi = _hz_to_midi(voiced_f0)
    if midi.size < 2:
        return {"bins": [0.0] * (2 * span + 1), "span_semitones": span}

    # Collapse repeated frames to note-ish steps so frame rate doesn't dominate.
    quantized = np.round(midi).astype(int)
    changes = quantized[np.insert(np.diff(quantized) != 0, 0, True)]
    if changes.size < 2:
        return {"bins": [0.0] * (2 * span + 1), "span_semitones": span}

    steps = np.clip(np.diff(changes), -span, span)
    counts = np.bincount(steps + span, minlength=2 * span + 1)[:2 * span + 1]
    return {"bins": _normalize(counts), "span_semitones": span}


def _range_semitones(voiced_f0):
    midi = _hz_to_midi(voiced_f0)
    if midi.size == 0:
        return None
    return round(float(np.max(midi) - np.min(midi)), 2)


def _onset_density(onsets, understanding):
    duration = _as_float(understanding.get("duration_seconds"))
    if not duration or duration <= 0 or onsets.size == 0:
        return None
    return round(float(onsets.size) / duration, 4)


def _ioi_stats(onsets, bins=8):
    """
    Inter-onset intervals, summarized. Ratios to the median keep this about
    evenness of attack rather than absolute timing.
    """
    if onsets.size < 3:
        return {"count": int(max(onsets.size - 1, 0)), "mean": None,
                "std": None, "cv": None, "ratio_bins": [0.0] * bins}

    iois = np.diff(np.sort(onsets))
    iois = iois[iois > 0]
    if iois.size == 0:
        return {"count": 0, "mean": None, "std": None, "cv": None,
                "ratio_bins": [0.0] * bins}

    mean = float(np.mean(iois))
    std = float(np.std(iois))
    median = float(np.median(iois)) or mean

    # Bucket each interval against the median: short, even, long, held.
    ratios = iois / median if median else iois
    counts, _ = np.histogram(np.clip(ratios, 0, 4), bins=bins, range=(0, 4))
    return {
        "count": int(iois.size),
        "mean": round(mean, 4),
        "std": round(std, 4),
        "cv": round(std / mean, 4) if mean else None,
        "ratio_bins": _normalize(counts),
    }


def _dynamics_stats(rms):
    if rms.size == 0:
        return {"mean": None, "std": None, "range": None, "crest": None}
    mean = float(np.mean(rms))
    peak = float(np.max(rms))
    return {
        "mean": round(mean, 6),
        "std": round(float(np.std(rms)), 6),
        "range": round(peak - float(np.min(rms)), 6),
        "crest": round(peak / mean, 4) if mean > 0 else None,
    }


def _chord_quality_weights(chord_info):
    """How often each chord quality appears -- vocabulary, not sequence."""
    progression = chord_info.get("chord_progression") or []
    counts = {}
    for chord in progression:
        name = str(chord)
        quality = name.split(" ", 1)[1] if " " in name else "unknown"
        counts[quality] = counts.get(quality, 0) + 1
    total = sum(counts.values())
    if not total:
        return {}
    return {q: round(c / total, 5) for q, c in sorted(counts.items())}


def _chord_motion_weights(chord_info, root_midi):
    """
    Distribution of root movement between consecutive chords, in semitones
    (0-11). A transition table is style; the ordered progression is the song,
    so only the aggregate is kept.
    """
    progression = chord_info.get("chord_progression") or []
    roots = []
    for chord in progression:
        name = str(chord).split(" ", 1)[0]
        if name in PITCH_CLASSES:
            roots.append(PITCH_CLASSES.index(name))
    if len(roots) < 2:
        return {"bins": [0.0] * 12}
    moves = np.mod(np.diff(np.asarray(roots)), 12)
    counts = np.bincount(moves, minlength=12)[:12]
    return {"bins": _normalize(counts)}


# ─────────────────────────────────────────────────
# Entries
# ─────────────────────────────────────────────────

def _sha256(path, chunk=1 << 20):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def create_reference(audio_path, title=None, performers=None, writers=None,
                     band=None, year=None, rights_basis="unspecified",
                     rights_notes=None, notes=None, retain_audio=False,
                     ref_id=None, source_type="unspecified", monophonic=None):
    """
    Register a reference and extract its profile.

    The entry is unapproved on creation regardless of rights_basis -- approval
    is a separate, deliberate act (see `approve`).

    source_type and monophonic decide which profile fields are meaningful;
    see `unreliable_fields`. Both default to the cautious reading, so an entry
    added without them contributes only what any source can support.
    """
    if rights_basis not in RIGHTS_BASES:
        raise ValueError(
            f"unknown rights_basis {rights_basis!r}; expected one of "
            f"{', '.join(RIGHTS_BASES)}"
        )
    if source_type not in SOURCE_TYPES:
        raise ValueError(
            f"unknown source_type {source_type!r}; expected one of "
            f"{', '.join(SOURCE_TYPES)}"
        )
    if not os.path.exists(audio_path):
        raise FileNotFoundError(audio_path)

    ref_id = ref_id or uuid.uuid4().hex[:12]
    ref_dir(ref_id, create=True)

    source_name = os.path.basename(audio_path)
    meta = {
        "ref_id": ref_id,
        "title": title or os.path.splitext(source_name)[0],
        "source_filename": source_name,
        "source_sha256": _sha256(audio_path),  # audit trail without the audio
        "performers": list(performers or []),
        "writers": list(writers or []),
        "band": band,
        "year": year,
        "rights_basis": rights_basis,
        "rights_notes": rights_notes,
        "notes": notes,
        "source_type": source_type,
        "monophonic": monophonic,
        "approved": False,
        "approved_by": None,
        "approved_at": None,
        "retain_audio": bool(retain_audio),
        "created_at": time.time(),
        "sr": None,
        "duration_seconds": None,
    }
    store.write_json(ref_path(ref_id, "meta.json"), meta)

    profile, sr, duration = extract_profile(audio_path)
    store.write_json(ref_path(ref_id, "profile.json"), profile)

    meta["sr"] = sr
    meta["duration_seconds"] = duration
    store.write_json(ref_path(ref_id, "meta.json"), meta)

    if retain_audio:
        import shutil
        shutil.copy2(audio_path, ref_path(ref_id, "source.wav"))

    return meta


def extract_profile(audio_path):
    """Run the analysis chain on a file and reduce it to a style profile."""
    import soundfile as sf
    from mastercrafter_performance_extractor import PerformanceExtractor
    from mastercrafter_stage1_orchestrator import Stage1PerformanceUnderstanding

    audio, sr = sf.read(audio_path, always_2d=False)
    if audio.ndim > 1:
        audio = np.mean(audio, axis=1)
    audio = np.asarray(audio, dtype=np.float32)
    duration = float(len(audio) / sr) if sr else 0.0

    extractor = PerformanceExtractor(sr=sr)
    performance = extractor.extract_full_performance(audio, fmin=60, fmax=1200)

    understanding = Stage1PerformanceUnderstanding(
        sr=sr, hop_length=512).understand_performance(performance, verbosity=0)

    return build_profile(performance, understanding), int(sr), duration


def load_reference(ref_id):
    meta = store.read_json(ref_path(ref_id, "meta.json"))
    if meta is None:
        return None
    meta["profile"] = store.read_json(ref_path(ref_id, "profile.json"))
    return meta


def list_references(approved_only=False):
    root = refs_root()
    out = []
    for name in sorted(os.listdir(root)):
        meta = store.read_json(os.path.join(root, name, "meta.json"))
        if not meta:
            continue
        if approved_only and not is_usable(meta):
            continue
        out.append(meta)
    out.sort(key=lambda m: m.get("created_at", 0), reverse=True)
    return out


def is_usable(meta):
    """
    True only for an entry cleared for use: approved, attributed, and with a
    rights basis that is actually stated.
    """
    return bool(
        meta
        and meta.get("approved") is True
        and meta.get("approved_by")
        and meta.get("rights_basis")
        and meta["rights_basis"] != "unspecified"
    )


def approve(ref_id, approved_by, rights_basis=None, rights_notes=None):
    """Record approval. Refuses to approve without a stated rights basis."""
    meta = store.read_json(ref_path(ref_id, "meta.json"))
    if meta is None:
        raise KeyError(f"no such reference: {ref_id}")

    if rights_basis is not None:
        if rights_basis not in RIGHTS_BASES:
            raise ValueError(f"unknown rights_basis {rights_basis!r}")
        meta["rights_basis"] = rights_basis
    if rights_notes is not None:
        meta["rights_notes"] = rights_notes

    if not meta.get("rights_basis") or meta["rights_basis"] == "unspecified":
        raise ValueError(
            "cannot approve a reference with no rights basis -- set "
            "rights_basis to one of: " + ", ".join(RIGHTS_BASES[:-1])
        )
    if not approved_by:
        raise ValueError("approval requires approved_by")

    meta.update({"approved": True, "approved_by": approved_by,
                 "approved_at": time.time()})
    store.write_json(ref_path(ref_id, "meta.json"), meta)
    return meta


def set_source(ref_id, source_type, monophonic=None):
    """
    Reclassify what kind of recording an entry came from.

    Separate from approval: deciding a file is a mastered mix rather than a
    solo take changes which fields mean anything, but says nothing about
    whether its use was cleared.
    """
    if source_type not in SOURCE_TYPES:
        raise ValueError(
            f"unknown source_type {source_type!r}; expected one of "
            f"{', '.join(SOURCE_TYPES)}"
        )
    meta = store.read_json(ref_path(ref_id, "meta.json"))
    if meta is None:
        raise KeyError(f"no such reference: {ref_id}")
    meta["source_type"] = source_type
    meta["monophonic"] = monophonic
    store.write_json(ref_path(ref_id, "meta.json"), meta)
    return meta


def revoke(ref_id, reason=None):
    """
    Withdraw approval. The entry stays for the audit trail but stops
    contributing to any style target.
    """
    meta = store.read_json(ref_path(ref_id, "meta.json"))
    if meta is None:
        raise KeyError(f"no such reference: {ref_id}")
    meta.update({"approved": False, "approved_at": None,
                 "revoked_at": time.time(), "revoked_reason": reason})
    store.write_json(ref_path(ref_id, "meta.json"), meta)
    return meta


def delete_reference(ref_id):
    import shutil
    path = ref_dir(ref_id)
    if os.path.isdir(path):
        shutil.rmtree(path)
        return True
    return False


# ─────────────────────────────────────────────────
# Aggregation
# ─────────────────────────────────────────────────

def style_target(ref_ids=None):
    """
    Blend approved profiles into one style target for the generators.

    Unapproved entries are excluded, so an un-approved upload contributes
    nothing. The result names its sources so a generated part's lineage can be
    traced back to the recordings that informed it.
    """
    entries = []
    for meta in list_references(approved_only=True):
        if ref_ids and meta["ref_id"] not in ref_ids:
            continue
        full = load_reference(meta["ref_id"])
        if full and full.get("profile"):
            entries.append(full)

    if not entries:
        return {
            "sources": [],
            "source_count": 0,
            "profile": None,
            "note": "no approved references; generators should fall back to "
                    "their built-in defaults",
        }

    blended, withheld, contributors = {}, {}, {}

    def put(field, builder):
        """
        Blend `field` across only those sources that can support it.

        Averaging a field over sources where it is a known artifact would
        launder the artifact into the target -- three mastered mixes all
        reporting "legato" because their envelopes never drop is not evidence
        of legato playing. When no source supports a field it is withheld with
        the reason, which is more useful to a generator than a confident
        wrong number.
        """
        supporting = [e["profile"] for e in entries
                      if field not in unreliable_fields(e.get("source_type"),
                                                        e.get("monophonic"))]
        if not supporting:
            for entry in entries:
                reason = unreliable_fields(
                    entry.get("source_type"), entry.get("monophonic")
                ).get(field)
                if reason:
                    withheld[field] = reason
                    break
            return
        value = builder(supporting)
        if value is not None:
            blended[field] = value
            contributors[field] = len(supporting)

    put("mode", lambda ps: _modal([p.get("mode") for p in ps]))
    put("time_signature", lambda ps: _modal([p.get("time_signature") for p in ps]))
    put("articulation", lambda ps: _modal([p.get("articulation") for p in ps]))
    put("timing", lambda ps: _modal([p.get("timing") for p in ps]))
    put("tempo_bpm", lambda ps: _mean([p.get("tempo_bpm") for p in ps]))
    put("expression", lambda ps: _mean([p.get("expression") for p in ps]))
    put("swing_factor", lambda ps: _mean([p.get("swing_factor") for p in ps]))
    put("gap_ratio", lambda ps: _mean([p.get("gap_ratio") for p in ps]))
    put("harmonic_ratio", lambda ps: _mean([p.get("harmonic_ratio") for p in ps]))
    put("onset_density_per_sec",
        lambda ps: _mean([p.get("onset_density_per_sec") for p in ps]))
    put("pitch_range_semitones",
        lambda ps: _mean([p.get("pitch_range_semitones") for p in ps]))
    put("scale_degree_weights", lambda ps: {
        "bins": _mean_bins(ps, "scale_degree_weights", 12),
        "labels": list(range(12)),
    })
    put("interval_weights", lambda ps: {
        "bins": _mean_bins(ps, "interval_weights", 25),
        "span_semitones": 12,
    })
    put("chord_root_motion_weights", lambda ps: {
        "bins": _mean_bins(ps, "chord_root_motion_weights", 12),
    })
    put("chord_quality_weights",
        lambda ps: _mean_dicts([p.get("chord_quality_weights") for p in ps]))
    put("ioi", lambda ps: {
        "cv": _mean([(p.get("ioi") or {}).get("cv") for p in ps]),
        "ratio_bins": _mean_bins(ps, "ioi", 8, key="ratio_bins"),
    })
    put("dynamics", lambda ps: {
        field: _mean([(p.get("dynamics") or {}).get(field) for p in ps])
        for field in ("mean", "std", "range", "crest")
    })

    validate_profile(blended)
    return {
        "sources": [
            {"ref_id": e["ref_id"], "title": e.get("title"),
             "rights_basis": e.get("rights_basis"),
             "approved_by": e.get("approved_by"),
             "source_type": e.get("source_type"),
             "monophonic": e.get("monophonic")}
            for e in entries
        ],
        "source_count": len(entries),
        "profile": blended,
        # Fields no approved source can support, and why. A generator should
        # fall back to its own defaults for these rather than guessing.
        "withheld": withheld,
        # How many sources backed each blended field.
        "blended_from": contributors,
    }


def _mean(values):
    clean = [float(v) for v in values if isinstance(v, (int, float))]
    return round(sum(clean) / len(clean), 5) if clean else None


def _modal(values):
    clean = [v for v in values if v]
    if not clean:
        return None
    counts = {}
    for value in clean:
        counts[value] = counts.get(value, 0) + 1
    return max(counts.items(), key=lambda kv: kv[1])[0]


def _mean_bins(profiles, field, length, key="bins"):
    stacked = []
    for profile in profiles:
        node = profile.get(field) or {}
        bins = node.get(key)
        if isinstance(bins, list) and len(bins) == length:
            stacked.append([float(b) for b in bins])
    if not stacked:
        return [0.0] * length
    return [round(v, 5) for v in np.mean(np.asarray(stacked), axis=0).tolist()]


def _mean_dicts(dicts):
    clean = [d for d in dicts if isinstance(d, dict) and d]
    if not clean:
        return {}
    keys = sorted({k for d in clean for k in d})
    return {k: round(float(np.mean([d.get(k, 0.0) for d in clean])), 5)
            for k in keys}
