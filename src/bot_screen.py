"""Unnamed-bot screen for hanab.live H-H corpus (B4 follow-up).

For every non-verified account in `human_play_records.csv`, fetch its full game
history via hanab.live's public API and compute:
- total games on hanab.live
- median / min inter-game completion gap (seconds)
- fraction of consecutive games with gap < 120 s
- fraction of consecutive games with gap < 60 s

Flags: median inter-game gap < 120 s OR total games > 5,000.

Cache API responses to `data/raw/hanab_live_history/{user}.json` so repeat runs
are idempotent.

Usage:  python -m src.bot_screen
"""

from __future__ import annotations

import json
import logging
import ssl
import time
import urllib.request
from pathlib import Path

import pandas as pd

# hanab.live uses a corporate Netskope-friendly cert; truststore was needed
# once at import time in this project (see CLAUDE.md).
try:
    import truststore  # noqa: F401
    truststore.inject_into_ssl()
except Exception:
    pass

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "data" / "raw" / "hanab_live_history"
OUT_DIR = ROOT / "output"
API_BASE = "https://hanab.live/api/v1/history"  # paginated; use ?size=100 for a sample

VERIFIED_BOTS = [
    "will-bot1", "will-bot2", "jabot1", "jabot4",
    "clanker1", "clanker2", "clanker4", "clanker5", "clanker6",
    "Inybot", "rand-bot1", "mac-bot-test",
]

REQUEST_SLEEP = 1.0
FLAG_MEDIAN_GAP_SECS = 120
FLAG_TOTAL_GAMES = 5000
FLAG_MIN_GAP_SECS = 30  # any run with min gap < 30s is deeply suspicious


def _load_or_fetch(user: str) -> dict | None:
    """Fetch a paginated sample of the user's game history + the total row count.

    hanab.live's /api/v1/history/{user} returns {total_rows, rows: [...]} where
    each row has id, num_players, score, variant, users, datetime, seed. We
    request size=100 (the maximum I've seen accepted) to get inter-game timing.
    """
    path = CACHE_DIR / f"{user}.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    url = f"{API_BASE}/{user}?size=100&page=0"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = json.load(resp)
    except Exception as e:
        logger.warning("Fetch failed for %s: %s", user, e)
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f)
    time.sleep(REQUEST_SLEEP)
    return data


def _parse_datetime(dt: str):
    """Parse hanab.live datetime, e.g. '2026-07-02 - 06:01:50 UTC'."""
    if not dt:
        return None
    # hanab.live format has ' - ' between date and time; pandas accepts it after removing.
    cleaned = dt.replace(" - ", " ").replace(" UTC", "")
    try:
        return pd.to_datetime(cleaned, utc=True).value / 1e9
    except Exception:
        return None


def _gaps(rows: list) -> list[float]:
    """Return sorted inter-completion gaps in seconds."""
    if not rows:
        return []
    ts = []
    for r in rows:
        v = _parse_datetime(r.get("datetime"))
        if v is not None:
            ts.append(v)
    ts.sort()
    gaps = [ts[i + 1] - ts[i] for i in range(len(ts) - 1)]
    return gaps


def screen(players: list[str], progress_every: int = 20) -> pd.DataFrame:
    rows = []
    for i, user in enumerate(players):
        data = _load_or_fetch(user)
        if data is None or not isinstance(data, dict):
            rows.append(dict(
                player=user, total_games=None, sample_size=0, median_gap=None,
                min_gap=None, frac_under_2min=None, frac_under_1min=None,
                fetch_ok=False,
            ))
            continue
        total = int(data.get("total_rows", 0))
        recs = data.get("rows") or []
        gaps = _gaps(recs)
        if gaps:
            gs = pd.Series(gaps)
            median_gap = float(gs.median())
            min_gap = float(gs.min())
            frac_under_2min = float((gs < 120).mean())
            frac_under_1min = float((gs < 60).mean())
        else:
            median_gap = min_gap = frac_under_2min = frac_under_1min = None
        rows.append(dict(
            player=user, total_games=total, sample_size=len(recs),
            median_gap=median_gap, min_gap=min_gap,
            frac_under_2min=frac_under_2min, frac_under_1min=frac_under_1min,
            fetch_ok=True,
        ))
        if (i + 1) % progress_every == 0:
            print(f"  screened {i + 1}/{len(players)}")
    return pd.DataFrame(rows)


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    hh = pd.read_csv(ROOT / "data" / "processed" / "human_play_records.csv")
    all_players = sorted(hh["player"].unique())
    non_verified = [p for p in all_players if p not in VERIFIED_BOTS]
    print(f"Total unique players: {len(all_players)}")
    print(f"Verified bots present: {sum(1 for p in all_players if p in VERIFIED_BOTS)}")
    print(f"Non-verified to screen: {len(non_verified)}")
    print()

    df = screen(non_verified)

    # Flag suspicious accounts
    def _flag(row):
        reasons = []
        if row.total_games is not None and row.total_games > FLAG_TOTAL_GAMES:
            reasons.append(f"vol>{FLAG_TOTAL_GAMES}")
        if row.median_gap is not None and row.median_gap < FLAG_MEDIAN_GAP_SECS:
            reasons.append(f"med<{FLAG_MEDIAN_GAP_SECS}s")
        if row.min_gap is not None and row.min_gap < FLAG_MIN_GAP_SECS:
            reasons.append(f"min<{FLAG_MIN_GAP_SECS}s")
        if row.total_games is None:
            reasons.append("no_data")
        return ";".join(reasons)

    df["flag"] = df.apply(_flag, axis=1)
    # Sort: flagged first (by reason length desc), then by median_gap asc
    df["_flag_len"] = df["flag"].map(len)
    df.sort_values(
        ["_flag_len", "total_games"],
        ascending=[False, False],
        na_position="last", inplace=True,
    )
    df = df.drop(columns=["_flag_len"])

    df.to_csv(OUT_DIR / "bot_screen_results.csv", index=False)
    print(f"Wrote {OUT_DIR / 'bot_screen_results.csv'}")

    flagged = df[df["flag"] != ""]
    print()
    print(f"FLAGGED: {len(flagged)} / {len(df)}")
    if len(flagged):
        print(flagged.to_string(index=False))


if __name__ == "__main__":
    main()
