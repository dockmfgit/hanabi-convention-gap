"""Regenerate all three processed CSV datasets from raw game logs.

This is a rebuild entrypoint used after fixing engine/replay bugs
(subject_type per-actor, final_score, hints_on_card action counter, ...).

Reads:
  data/raw/exports/*.json         (hanab.live 2-player No Variant games)
  data/raw/hoad/*.json            (HOAD agent-vs-agent bundles: list per file)
  data/raw/hanabi_data/converted/*.json  (converted HanabiData human-AI games)

Writes:
  data/processed/human_play_records.csv
  data/processed/agent_play_records.csv
  data/processed/human_ai_play_records.csv
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from pathlib import Path

import pandas as pd

from src.replay import process_games, records_to_dicts

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "data" / "processed"


def _load_json(path: Path):
    with open(path) as f:
        return json.load(f)


def regenerate_human() -> tuple[pd.DataFrame, list]:
    """hanab.live human-human 2-player No Variant games."""
    files = sorted((RAW_DIR / "exports").glob("*.json"))
    games = [_load_json(f) for f in files]
    records, skipped = process_games(
        games,
        data_source="hanab_live",
        subject_type="human",
        partner_type="human",
        return_skipped=True,
    )
    df = pd.DataFrame(records_to_dicts(records))
    return df, skipped


def regenerate_agent() -> tuple[pd.DataFrame, list]:
    """HOAD agent-vs-agent games.

    Uses per-actor subject_type/partner_type derivation
    (`subject_type=None, partner_type=None` -> derive from players[]).
    """
    files = sorted((RAW_DIR / "hoad").glob("*.json"))
    all_records = []
    all_skipped = []
    for f in files:
        games = _load_json(f)
        # HOAD files are lists of games
        if not isinstance(games, list):
            games = [games]
        records, skipped = process_games(
            games,
            data_source="hoad",
            subject_type=None,     # derive from players[player_id]
            partner_type=None,     # derive from other seat
            return_skipped=True,
            game_key_prefix=f.stem,  # e.g. "simple_vs_iggi" — makes game_key globally unique
        )
        all_records.extend(records)
        all_skipped.extend([(f.stem, gid) for gid in skipped])
    df = pd.DataFrame(records_to_dicts(all_records))
    return df, all_skipped


def regenerate_human_ai() -> tuple[pd.DataFrame, list]:
    """HanabiData converted human-AI games.

    subject_type is stamped from the acting player: for the human seat
    (player == "Human"), we set subject_type='human' and partner_type=ai_type;
    for the AI seat, subject_type=ai_type and partner_type='human'.
    """
    files = sorted((RAW_DIR / "hanabi_data" / "converted").glob("*.json"))
    all_records = []
    all_skipped = []
    for f in files:
        game_json = _load_json(f)
        ai_type = game_json.get("metadata", {}).get("ai_type", "unknown")
        try:
            from src.replay import replay_and_extract
            records, _ = replay_and_extract(
                game_json,
                data_source="hanabi_data",
                subject_type=None,      # derive from players[]
                partner_type=None,      # derive from other seat
            )
            # Re-tag: player "Human" is the human, other is ai_type
            for r in records:
                if r.player == "Human":
                    r.subject_type = "human"
                    r.partner_type = ai_type
                else:
                    r.subject_type = ai_type
                    r.partner_type = "human"
            all_records.extend(records)
        except Exception as e:
            logger.warning("skipped %s: %s", f.name, e)
            all_skipped.append(f.name)
    df = pd.DataFrame(records_to_dicts(all_records))
    return df, all_skipped


def regenerate_hints() -> pd.DataFrame:
    """Regenerate hint_records.csv from the same raw sources."""
    from src.analysis import compute_hint_records

    all_hints = []

    # hanab.live
    hl_files = sorted((RAW_DIR / "exports").glob("*.json"))
    for f in hl_files:
        try:
            game = _load_json(f)
            recs = compute_hint_records(game, data_source="hanab_live")
            for r in recs:
                r["hinter_type"] = "human"
                r["partner_type"] = "human"
            all_hints.extend(recs)
        except Exception:
            pass

    # HOAD (per-actor tagging via players[])
    hoad_files = sorted((RAW_DIR / "hoad").glob("*.json"))
    for f in hoad_files:
        fname = f.stem
        parts = fname.split("_vs_")
        if len(parts) != 2:
            continue
        subj, part = parts
        try:
            games = _load_json(f)
            if not isinstance(games, list):
                games = [games]
            for game in games:
                recs = compute_hint_records(game, data_source="hoad")
                for r in recs:
                    r["hinter_type"] = subj if r["hinter"] == game["players"][0] else part
                    r["partner_type"] = part if r["hinter"] == game["players"][0] else subj
                all_hints.extend(recs)
        except Exception:
            pass

    # HanabiData
    hd_files = sorted((RAW_DIR / "hanabi_data" / "converted").glob("*.json"))
    for f in hd_files:
        try:
            game = _load_json(f)
            recs = compute_hint_records(game, data_source="hanabi_data")
            ai_type = game.get("metadata", {}).get("ai_type", "unknown")
            for r in recs:
                if r["hinter"] == game["players"][0]:
                    r["hinter_type"] = ai_type
                    r["partner_type"] = "human"
                else:
                    r["hinter_type"] = "human"
                    r["partner_type"] = ai_type
            all_hints.extend(recs)
        except Exception:
            pass

    return pd.DataFrame(all_hints)


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=== Regenerating human_play_records.csv ===")
    hh, sk_hh = regenerate_human()
    print(f"  human-human: {len(hh):,} records, skipped {len(sk_hh)} games")
    print(f"  subject_type counts: {Counter(hh['subject_type'])}")
    print(f"  final_score dist: min={hh['final_score'].min()}, max={hh['final_score'].max()}, mean={hh['final_score'].mean():.2f}")
    print(f"  hints_on_card max: {hh['hints_on_card'].max()}, hint_types_on_card max: {hh['hint_types_on_card'].max()}")
    print(f"  game_end_reason: {Counter(hh.groupby('game_key')['game_end_reason'].first())}")
    # B3 + completed-games: classify skill over COMPLETED games only (truncated
    # games are excluded from the corpus, so a player's skill is their average
    # score across the games that actually count), then map back onto every row.
    from src.analysis import add_individual_skill_columns
    completed = hh[hh["game_end_reason"] != "truncated"].copy()
    completed = add_individual_skill_columns(completed)
    skill_by_player = completed.groupby("player")["individual_skill"].first()
    pair_by_game = completed.groupby("game_key")["pair_type"].first()
    hh["individual_skill"] = hh["player"].map(skill_by_player)
    hh["skill_level"] = hh["individual_skill"]
    hh["pair_type"] = hh["game_key"].map(pair_by_game)
    print(f"  skill_level populated (completed-game basis): "
          f"{hh['skill_level'].notna().sum():,} / {len(hh):,}")
    hh.to_csv(OUT_DIR / "human_play_records.csv", index=False)

    print("\n=== Regenerating agent_play_records.csv ===")
    aa, sk_aa = regenerate_agent()
    print(f"  agent-agent: {len(aa):,} records, skipped {len(sk_aa)} games")
    print(f"  subject_type counts: {Counter(aa['subject_type'])}")
    print(f"  final_score dist: min={aa['final_score'].min()}, max={aa['final_score'].max()}, mean={aa['final_score'].mean():.2f}")
    print(f"  hints_on_card max: {aa['hints_on_card'].max()}, hint_types_on_card max: {aa['hint_types_on_card'].max()}")
    aa.to_csv(OUT_DIR / "agent_play_records.csv", index=False)

    print("\n=== Regenerating human_ai_play_records.csv ===")
    hai, sk_hai = regenerate_human_ai()
    print(f"  human-AI: {len(hai):,} records, skipped {len(sk_hai)} games")
    print(f"  subject_type counts: {Counter(hai['subject_type'])}")
    print(f"  final_score dist: min={hai['final_score'].min()}, max={hai['final_score'].max()}, mean={hai['final_score'].mean():.2f}")
    print(f"  hints_on_card max: {hai['hints_on_card'].max()}, hint_types_on_card max: {hai['hint_types_on_card'].max()}")
    hai.to_csv(OUT_DIR / "human_ai_play_records.csv", index=False)

    print("\n=== Regenerating hint_records.csv ===")
    ht = regenerate_hints()
    print(f"  hint records: {len(ht):,}, from {ht.groupby(['data_source','game_id']).ngroups} games")
    print(f"  by data_source: {Counter(ht['data_source'])}")
    ht.to_csv(OUT_DIR / "hint_records.csv", index=False)

    # Anonymize hanab.live usernames in the shipped CSVs (P4 punchlist).
    # The pipeline MUST end here — no consumer should see raw usernames.
    print("\n=== Anonymizing usernames ===")
    from src.anonymize_usernames import main as anonymize_main
    anonymize_main()


if __name__ == "__main__":
    main()
