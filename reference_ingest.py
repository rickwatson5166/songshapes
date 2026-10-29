#!/usr/bin/env python3
"""
Ingest approved reference recordings into the style library.

Point it at one file or a whole folder. For each recording it extracts a style
profile, records where the recording came from and on what basis it may be
used, and then -- unless told to keep it -- leaves the audio where it was.

Nothing ingested is used for anything until it is approved. Ingest and
approval are separate steps on purpose: ingesting is bookkeeping, approving is
a decision.

Examples
--------
Your own songs, your own recordings, cleared as you go:

    python3 reference_ingest.py ./my_songs \\
        --rights own-composition-own-recording \\
        --writer "Rick Watson" --performer "Rick Watson" \\
        --approve-as "Rick Watson"

An old band's recordings -- ingest now, decide later:

    python3 reference_ingest.py ./band_tapes \\
        --band "The Old Band" --rights band-recording-shared-rights \\
        --notes "check with the other players before approving"

Review and approve one at a time:

    python3 reference_ingest.py --list
    python3 reference_ingest.py --approve <ref_id> --approve-as "Rick Watson"

See what the generators would actually match against:

    python3 reference_ingest.py --style-target
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import reference_library as lib

AUDIO_EXTENSIONS = (".wav", ".mp3", ".flac", ".ogg", ".aiff", ".aif", ".m4a")


def collect_audio(target):
    """Return a sorted list of audio files from a file or directory path."""
    if os.path.isfile(target):
        return [target]
    if os.path.isdir(target):
        found = []
        for root, _dirs, files in os.walk(target):
            for name in sorted(files):
                if name.lower().endswith(AUDIO_EXTENSIONS) and not name.startswith("."):
                    found.append(os.path.join(root, name))
        return sorted(found)
    raise FileNotFoundError(target)


def ingest(paths, args):
    results, failures = [], []

    for index, path in enumerate(paths, start=1):
        name = os.path.basename(path)
        print(f"[{index}/{len(paths)}] {name}")
        try:
            meta = lib.create_reference(
                path,
                title=args.title if len(paths) == 1 else None,
                performers=args.performer,
                writers=args.writer,
                band=args.band,
                year=args.year,
                rights_basis=args.rights,
                rights_notes=args.rights_notes,
                notes=args.notes,
                retain_audio=args.retain_audio,
            )
        except Exception as exc:
            print(f"    failed: {exc}")
            failures.append((name, str(exc)))
            continue

        ref_id = meta["ref_id"]

        if args.approve_as:
            try:
                meta = lib.approve(ref_id, approved_by=args.approve_as)
                state = f"approved by {meta['approved_by']}"
            except ValueError as exc:
                state = f"ingested, NOT approved ({exc})"
        else:
            state = "ingested, awaiting approval"

        profile = lib.load_reference(ref_id)["profile"]
        print(f"    {ref_id}  {meta['title']}")
        print(f"    {profile.get('mode')}, {profile.get('tempo_bpm')} bpm, "
              f"{profile.get('articulation')}, {profile.get('timing')}")
        print(f"    {state}")
        results.append(meta)

    return results, failures


def cmd_list():
    entries = lib.list_references()
    if not entries:
        print("No references ingested yet.")
        return
    usable = sum(1 for m in entries if lib.is_usable(m))
    print(f"{len(entries)} reference(s), {usable} cleared for use\n")
    for meta in entries:
        mark = "USE " if lib.is_usable(meta) else "HOLD"
        basis = meta.get("rights_basis")
        who = meta.get("approved_by") or "-"
        print(f"  [{mark}] {meta['ref_id']}  {meta.get('title')}")
        print(f"         rights={basis}  approved_by={who}")
        if meta.get("rights_notes"):
            print(f"         note: {meta['rights_notes']}")


def cmd_style_target():
    target = lib.style_target()
    if not target["source_count"]:
        print("No approved references. Generators fall back to defaults.")
        return
    print(f"Style target built from {target['source_count']} approved "
          f"reference(s):\n")
    for source in target["sources"]:
        print(f"  - {source['title']}  ({source['rights_basis']}, "
              f"approved by {source['approved_by']})")
    print()
    print(json.dumps(target["profile"], indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Ingest approved reference recordings for style matching.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("target", nargs="?",
                        help="audio file or folder of audio files")

    parser.add_argument("--title", help="title (single file only)")
    parser.add_argument("--performer", action="append", default=[],
                        help="who played on it; repeatable")
    parser.add_argument("--writer", action="append", default=[],
                        help="who wrote it; repeatable")
    parser.add_argument("--band", help="band name")
    parser.add_argument("--year", help="year recorded")

    parser.add_argument("--rights", default="unspecified",
                        choices=lib.RIGHTS_BASES,
                        help="basis on which this may be used")
    parser.add_argument("--rights-notes", help="free-text note on the rights")
    parser.add_argument("--notes", help="any other note")

    parser.add_argument("--approve-as", metavar="NAME",
                        help="approve on ingest, recorded as this name; "
                             "ignored unless --rights is set")
    parser.add_argument("--retain-audio", action="store_true",
                        help="keep a copy of the audio (off by default: the "
                             "profile is what the system needs)")

    parser.add_argument("--list", action="store_true",
                        help="list references and their approval state")
    parser.add_argument("--approve", metavar="REF_ID",
                        help="approve an already-ingested reference")
    parser.add_argument("--revoke", metavar="REF_ID",
                        help="withdraw approval")
    parser.add_argument("--style-target", action="store_true",
                        help="show the blended target from approved entries")

    args = parser.parse_args(argv)

    if args.list:
        cmd_list()
        return 0

    if args.style_target:
        cmd_style_target()
        return 0

    if args.approve:
        try:
            meta = lib.approve(args.approve, approved_by=args.approve_as,
                               rights_basis=(args.rights
                                             if args.rights != "unspecified"
                                             else None),
                               rights_notes=args.rights_notes)
        except (ValueError, KeyError) as exc:
            print(f"could not approve: {exc}", file=sys.stderr)
            return 1
        print(f"approved {meta['ref_id']} ({meta['title']}) "
              f"by {meta['approved_by']}")
        return 0

    if args.revoke:
        meta = lib.revoke(args.revoke, reason=args.notes)
        print(f"approval withdrawn for {meta['ref_id']} ({meta['title']})")
        return 0

    if not args.target:
        parser.print_help()
        return 1

    if args.approve_as and args.rights == "unspecified":
        print("refusing to approve without --rights; ingesting on hold "
              "instead.\n", file=sys.stderr)
        args.approve_as = None

    paths = collect_audio(args.target)
    if not paths:
        print(f"no audio files found in {args.target}")
        return 1

    print(f"Ingesting {len(paths)} file(s)\n")
    results, failures = ingest(paths, args)

    print(f"\n{len(results)} ingested, {len(failures)} failed")
    usable = sum(1 for m in lib.list_references() if lib.is_usable(m))
    print(f"{usable} reference(s) now cleared for use")
    if failures:
        print("\nFailed:")
        for name, error in failures:
            print(f"  {name}: {error}")
    return 0 if results else 1


if __name__ == "__main__":
    sys.exit(main())
