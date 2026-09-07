"""Sweep hanab.live raw exports' per-player notes for bot version signatures.

will-hanabi-bot (and its convention-framework variants) auto-annotate their
per-game notes with a version tag of the form:

    [INFO: v1.11.1, HGroup3]
    [INFO: v0.7.2 (scala-bot)]

A human player never authors that string, so its presence in an account's own
notes is definitive bot evidence — stronger than the volume/timing heuristics
used by the primary bot screen (src/bot_screen.py). This module scans every
export, reports which accounts carry the signature, and flags those not already
on the exclusion list as new suspects.

Usage:  python -m src.notes_bot_sweep
"""

from __future__ import annotations

import glob
import json
import re
from collections import defaultdict
from pathlib import Path

from src.corpus import (
    FLAGGED_B_BOT_PARTNER,
    FLAGGED_C_IDENTICAL_PAIR,
    FLAGGED_D_NOTES_SIGNATURE,
    _hash_username,
    is_verified_bot,
)

ROOT = Path(__file__).resolve().parent.parent
EXPORTS_DIR = ROOT / "data" / "raw" / "exports"

# Primary signature: an [INFO: v<semver>...] tag authored in the account's notes.
SIGNATURE = re.compile(r"\[INFO:\s*v[\d.]+")

_EXCLUDED_HASHES = (
    set(FLAGGED_B_BOT_PARTNER)
    | set(FLAGGED_C_IDENTICAL_PAIR)
    | set(FLAGGED_D_NOTES_SIGNATURE)
)


def _is_excluded(user: str) -> bool:
    return is_verified_bot(user) or _hash_username(user) in _EXCLUDED_HASHES


def sweep(exports_dir: Path | None = None) -> dict:
    """Return {player: {"games": [...], "example": str}} for signature hits."""
    exports_dir = exports_dir or EXPORTS_DIR
    hits: dict[str, dict] = defaultdict(lambda: {"games": [], "example": ""})
    for f in sorted(glob.glob(str(exports_dir / "*.json"))):
        with open(f) as fh:
            g = json.load(fh)
        players = g.get("players", [])
        notes = g.get("notes")
        if not notes:
            continue
        for pi, pnotes in enumerate(notes):
            if pi >= len(players):
                continue
            if not isinstance(pnotes, list):
                continue
            joined = " ".join(x for x in pnotes if isinstance(x, str) and x)
            m = SIGNATURE.search(joined)
            if m:
                user = players[pi]
                hits[user]["games"].append(g.get("id"))
                if not hits[user]["example"]:
                    hits[user]["example"] = joined[m.start(): m.start() + 40]
    return dict(hits)


def main():
    hits = sweep()
    print(f"Accounts with bot version signature in notes: {len(hits)}")
    print(f"{'player':<20} {'#games':>6}  {'excluded?':<10} example")
    for user in sorted(hits, key=lambda u: -len(hits[u]["games"])):
        print(f"{user:<20} {len(hits[user]['games']):>6}  "
              f"{str(_is_excluded(user)):<10} {hits[user]['example']}")

    new = [u for u in hits if not _is_excluded(u)]
    print(f"\nNEW suspects (signature present, not yet excluded): {len(new)}")
    for u in sorted(new, key=lambda u: -len(hits[u]["games"])):
        print(f"  {u}: {len(hits[u]['games'])} games, e.g. {hits[u]['games'][:5]}")
    if not new:
        print("  (none — all signature accounts already on the exclusion list)")


if __name__ == "__main__":
    main()
