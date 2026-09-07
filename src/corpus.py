"""H-H corpus definition and bot-exclusion utilities (B2/B4 audit follow-up).

The H-H corpus is defined as: all successfully replayed 2-player "No Variant"
hanab.live games EXCLUDING every game involving a verified or flagged bot
account (see BOT_EXCLUSION_LIST below).

Load the corpus via ``load_hh_corpus()``; it applies the exclusion.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

import pandas as pd

# Tier-1 verified bot families. Every hanab.live account whose name matches
# any pattern below is treated as a bot for game-level exclusion. The families
# themselves were identified via the will-hanabi-bot README and per-account
# hanab.live history verification.
VERIFIED_BOT_PATTERNS = [
    r"will-bot\d+",   # will-hanabi-bot family
    r"jabot\d+",      # jabot family
    r"clanker\d+",    # clanker family
    r"Inybot\d*",     # Inybot (and any numbered siblings)
    r"rand-bot\d+",   # rand-bot family
    r"mac-bot.*",     # mac-bot-test etc.
]

_VERIFIED_RE = re.compile("|".join(f"^({p})$" for p in VERIFIED_BOT_PATTERNS))


def is_verified_bot(name: str) -> bool:
    """True iff ``name`` matches any Tier-1 verified-bot pattern."""
    if not isinstance(name, str):
        return False
    return _VERIFIED_RE.match(name) is not None


# Concrete verified bot names encountered so far (used as a stable identity
# whitelist by anonymize_usernames.py so bot names are preserved unhashed).
# Any real hanab.live account matching VERIFIED_BOT_PATTERNS is also a bot;
# this list is not exhaustive by design.
VERIFIED_BOTS = [
    "will-bot1", "will-bot2", "will-bot4",
    "jabot1", "jabot4",
    "clanker1", "clanker2", "clanker4", "clanker5", "clanker6",
    "Inybot", "rand-bot1", "mac-bot-test",
]

# Account-level exclusions from the unnamed-bot screen (src/bot_screen.py,
# 2026-07-02 sweep). Policy revision 2026-07-02 (post-user-review):
# only accounts with POSITIVE bot evidence are excluded at the account level.
# Volume-only or timing-only signals (Buckets A and D from the screen) are
# NOT enough on their own — they qualify only via B or C evidence.
#
# NOTE: We keep the flagged accounts as HASHED identifiers so this bundle
# does not publicly label real (possibly-human) hanab.live users as bots.
# The username-to-hash correspondence is in the private map
# ``data/private/human_player_map.csv`` (not shipped).
#
# B — plays ≥90% of corpus games with a verified bot ("bot-partner" evidence)
FLAGGED_B_BOT_PARTNER = [
    "ea0285b3f4909ecc",   # B1
    "3498e8a285617330",   # B2
    "2fc31451841f63e0",   # B3
    "7a27464fc158175e",   # B4
    "620fe77ea74f2ae0",   # B5
    "c25e9d15b0cd34fb",   # B6
    "1a6fd92d07206382",   # B7
    "fad90fa836963df0",   # B8
    "e446b6c7fcd8e39e",   # B9  (100% co-play with verified bots, extreme signature)
    "0fffb9fa1baf7288",   # B10 (low-volume, 100% co-play with verified bots)
    "5f9055bffd4b2668",   # B11 (low-volume, 100% co-play with verified bots)
]
# C — members of identical-stats pairs (byte-identical inter-game timing with
# another account, evidence of coordinated automation). Both members of every
# pair where at least one member has >1,000 total games are included.
FLAGGED_C_IDENTICAL_PAIR = [
    "ee915ff623ed43b2", "27797c996dc95a07",   # C-pair 1 (350s/57s, ~6.4k games each)
    "5f310280a62f161b", "f58c03ce961214e0",   # C-pair 2 (192s/115s, ~7-8k)
    "062b9984c9aae6b1", "692cc0b824b50b80",   # C-pair 3 (406s/232s)
    "556ba9a4c709f44e", "93a43163e81bacb5",   # C-pair 4 (227s/17s)
    "f97203edb723d45f", "7509ccb6f3f01757",   # C-pair 5 (1279s/14s)
    "40cd4089bda19f0a", "11e9982607e4ebde",   # C-pair 6 (509s/174s)
    "b34535560f78fd9f", "34cf4908d4b94a9a",   # C-pair 7 (484s/80s)
    "309f9df73e2a3e27", "4fa552eadf6915b9",   # C-pair 8 (100s/27s, ~29k each)
]

# D — bot version signature in the account's own per-game notes (2026-07-03
# notes sweep, src/notes_bot_sweep.py). will-hanabi-bot auto-annotates its
# notes with "[INFO: v<version>, <convention framework>]"; a human never
# authors that string. One account carries the signature in all of its games
# and plays exclusively with one partner, so both are excluded (the partner
# qualifies as a 100%-bot-partner). Hashed to avoid publicly labelling the accounts.
FLAGGED_D_NOTES_SIGNATURE = [
    "a08ee96386551922",   # notes-signature account — [INFO: v1.11.1, HGroup1] in all 8 games
    "eb2b956a115dee2c",   # exclusive partner of the notes-signature account
]

BOT_EXCLUSION_LIST: list[str] = sorted(set(
    VERIFIED_BOTS                # Tier-1 (bot names, kept unhashed by design)
    + FLAGGED_B_BOT_PARTNER      # Tier-2 (hashed)
    + FLAGGED_C_IDENTICAL_PAIR   # Tier-2 (hashed)
    + FLAGGED_D_NOTES_SIGNATURE  # Tier-2 (hashed)
))


def _load_salt() -> str:
    """Load the hash salt.

    Priority: HANABI_HASH_SALT env var, then a private file at
    ``data/private/hash_salt.txt`` (kept out of the bundle via .gitignore).
    Falls back to a fixed test-only value ONLY when neither is present, so
    corpus.py works out-of-the-box for pre-anonymized shipped CSVs but does
    not leak any real salt in the bundle.
    """
    v = os.environ.get("HANABI_HASH_SALT")
    if v:
        return v
    p = Path(__file__).resolve().parent.parent / "data" / "private" / "hash_salt.txt"
    if p.exists():
        return p.read_text().strip()
    return "PUBLIC-TEST-SALT-DO-NOT-USE"


_HASH_SALT_CACHE: str | None = None


def _hash_username(name: str) -> str:
    """16-hex digest of a username using the private salt."""
    global _HASH_SALT_CACHE
    if _HASH_SALT_CACHE is None:
        _HASH_SALT_CACHE = _load_salt()
    return hashlib.sha256(f"{_HASH_SALT_CACHE}::{name}".encode("utf-8")).hexdigest()[:16]


def _tier2_mask(players: pd.Series) -> pd.Series:
    """True where the player is one of the Tier-2 B+C accounts (matched by
    hash). Works on both hashed and raw-username CSVs: rows whose value is
    already a hash match directly; raw usernames are hashed on the fly and
    checked against the same set.

    The FLAGGED_* lists are shipped as hashes so raw usernames of suspected
    (possibly-human) accounts never appear in the bundle.
    """
    exclusion_hashes = (
        set(FLAGGED_B_BOT_PARTNER)
        | set(FLAGGED_C_IDENTICAL_PAIR)
        | set(FLAGGED_D_NOTES_SIGNATURE)
    )
    already_hash = players.isin(exclusion_hashes)
    # Raw-username fallback: hash each non-hashed value and re-check.
    is_hex = players.astype(str).str.match(r"^[0-9a-f]{16}$", na=False)
    raw = players[~is_hex]
    if len(raw):
        raw_hashes = raw.astype(str).map(_hash_username)
        raw_match = raw_hashes.isin(exclusion_hashes)
        raw_match = raw_match.reindex(players.index, fill_value=False)
    else:
        raw_match = pd.Series(False, index=players.index)
    return already_hash | raw_match


def _expand_matchers(accounts: list[str]) -> set[str]:  # pragma: no cover
    """Deprecated helper (pre-punchlist). Retained for backward compatibility
    with any external callers; superseded by _tier2_mask()."""
    return set(accounts) | {_hash_username(a) for a in accounts}


def _tier1_mask(players: pd.Series) -> pd.Series:
    """True where the player is a Tier-1 verified-bot family member OR a
    16-hex hash of one (post-anonymization). Matching by both the raw
    pattern and the pre-computed hash means the same corpus filter works
    on the raw and shipped CSVs."""
    raw = players.astype(str).map(is_verified_bot)
    hashed = {_hash_username(n) for n in VERIFIED_BOTS}
    return raw | players.isin(hashed)


def filter_bot_games(df: pd.DataFrame) -> pd.DataFrame:
    """Apply the two-tier bot exclusion (policy 2026-07-02, punchlist rev):

    1. Game-level for VERIFIED bot FAMILIES (by name pattern OR their
       hashed identifiers): drop every play record from any game in which
       a verified-bot account MADE A PLAY. NB: this frame is a play-record
       table, so a verified bot that only clued or discarded is not visible
       here and its game is retained (one such game, 1762152). Documented
       in REPRODUCING.md and Appendix B; excluding those games as well
       would give 424 games / 9,011 plays.
    2. Account-level for B+C flagged accounts: drop only those accounts'
       own play records.

    Works for both raw-username and hashed-username CSVs.
    """
    # Tier 1: game-level for verified-bot families
    bad_games = set(df.loc[_tier1_mask(df["player"]), "game_key"].unique())
    df = df[~df["game_key"].isin(bad_games)].copy()

    # Tier 2: account-level for B+C suspects — match hash or raw username
    df = df[~_tier2_mask(df["player"])].copy()
    return df


def filter_truncated_games(df: pd.DataFrame) -> pd.DataFrame:
    """Drop games that did not complete (``game_end_reason == 'truncated'``).

    Truncated games are hanab.live games that ended abnormally (timeout,
    terminated, or idle-timeout — recorded score 0) or whose log stopped
    mid-game without reaching a terminal state. Excluding them makes the
    corpus consistent with the paper's ``completed games`` claim. Applies
    only if the ``game_end_reason`` column is present (older CSVs lack it).
    """
    if "game_end_reason" not in df.columns:
        return df
    return df[df["game_end_reason"] != "truncated"].copy()


def load_hh_corpus(
    csv_path: str | Path | None = None,
    apply_bot_exclusion: bool = True,
    exclude_truncated: bool = True,
) -> pd.DataFrame:
    """Load the H-H corpus with the two-tier bot exclusion and the
    completed-games filter applied by default.

    The v6 canonical corpus definition. Use this everywhere instead of
    reading the raw CSV.
    """
    if csv_path is None:
        csv_path = Path(__file__).resolve().parent.parent / "data" / "processed" / "human_play_records.csv"
    df = pd.read_csv(csv_path)
    if exclude_truncated:
        df = filter_truncated_games(df)
    if apply_bot_exclusion:
        df = filter_bot_games(df)
    return df
