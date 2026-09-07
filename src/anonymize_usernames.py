"""Hash hanab.live usernames in the shipped H-H CSV (Phase 4 packaging).

Replaces the raw ``player`` column values with 16-hex identifiers matching the
scheme used in ``hai_game_participant_map.csv``. The username→hash mapping is
written to a *private* file (``data/private/human_player_map.csv``) that is
NOT shipped in the supplementary bundle.

Also hashes:
- ``hinter`` and ``target_player`` columns in ``hint_records.csv``
- Any player references in ``human_play_records.csv``

The 12 verified bot account names are kept unhashed (documented as bot accounts).
Flagged (Bucket B/C) accounts are hashed so their identities are not disclosed.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from src.corpus import VERIFIED_BOTS, is_verified_bot, _load_salt

ROOT = Path(__file__).resolve().parent.parent
PROC = ROOT / "data" / "processed"
PRIVATE = ROOT / "data" / "private"


def _hash(name: str) -> str:
    """16-hex digest keyed by the private salt (see src/corpus.py::_load_salt)."""
    salt = _load_salt()
    h = hashlib.sha256(f"{salt}::{name}".encode("utf-8")).hexdigest()
    return h[:16]


def build_username_map(names: set[str]) -> dict[str, str]:
    """Produce a stable username → 16-hex mapping.

    Verified bot accounts (Tier-1 pattern OR concrete list) keep their names
    unhashed (documented as bots in Appendix~B). Every other name is hashed.
    """
    mapping = {}
    for name in sorted(names):
        if is_verified_bot(name) or name in VERIFIED_BOTS:
            mapping[name] = name
        else:
            mapping[name] = _hash(name)
    return mapping


def main():
    # Collect every username appearing in any CSV
    hh = pd.read_csv(PROC / "human_play_records.csv")
    hints = pd.read_csv(PROC / "hint_records.csv")

    all_names: set[str] = set()
    all_names.update(hh["player"].dropna().unique().tolist())
    for col in ("hinter", "target_player"):
        if col in hints.columns:
            all_names.update(hints[col].dropna().astype(str).unique().tolist())

    # HanabiData "Human" and AI keys should not be re-mapped
    reserved = {"Human", "human", "full", "intentional", "outer",
                "bergh", "flawed", "iggi", "internal", "piers", "simple"}
    to_map = {n for n in all_names if n not in reserved}

    mapping = build_username_map(to_map)
    for r in reserved:
        mapping[r] = r  # identity mapping (keep as-is)

    # Write private mapping (do NOT ship this)
    PRIVATE.mkdir(parents=True, exist_ok=True)
    priv = pd.DataFrame(
        [(k, v) for k, v in sorted(mapping.items()) if v != k],
        columns=["username", "hash"],
    )
    priv.to_csv(PRIVATE / "human_player_map.csv", index=False)
    print(f"Wrote {PRIVATE / 'human_player_map.csv'} ({len(priv)} entries)")

    # Rewrite CSVs with hashed usernames
    hh["player"] = hh["player"].map(mapping).fillna(hh["player"])
    hh.to_csv(PROC / "human_play_records.csv", index=False)
    print(f"Rewrote {PROC / 'human_play_records.csv'}")

    for col in ("hinter", "target_player"):
        if col in hints.columns:
            hints[col] = hints[col].map(mapping).fillna(hints[col])
    hints.to_csv(PROC / "hint_records.csv", index=False)
    print(f"Rewrote {PROC / 'hint_records.csv'}")

    # Sanity check: no raw usernames leak
    leaked = [n for n in to_map if n in hh["player"].unique()]
    if leaked:
        print(f"WARNING: {len(leaked)} unhashed names remain: {leaked[:5]}")
    else:
        print("OK: no unhashed usernames in human_play_records.csv (bots preserved).")


if __name__ == "__main__":
    main()
