"""Replay all three corpora computing marginal AND joint posteriors per play.

Produces ``data/processed/joint_posteriors.csv`` keyed by
(data_source, game_key, turn) with both posterior variants, candidate
counts, and the number of hint-constrained other cards. Also writes
``data/processed/joint_replay_timing.json`` with per-variant timing and
brute-force verification statistics.

Mirrors src/replay.py's action loop exactly (deck-index translation,
GAME_OVER marker handling, posterior computed BEFORE the play is applied).
No usernames are written (seat index only), so the CSV is shippable.

Origin: Phase-1 rebuttal computation A (rebuttal/run_joint_replay.py),
promoted into src/ for v8.

Regenerate from the repo root:  python -m src.joint_replay
Load (with on-demand regeneration): ``load_joint_posteriors()``.
"""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path

from src.game_engine import (
    Action,
    ActionType,
    actions_from_hanab_live,
    state_from_hanab_live,
)
from src.joint_posterior import brute_force_joint_posterior, compute_joint_posterior
from src.posterior import compute_life_loss_posterior

ROOT = Path(__file__).resolve().parent.parent
OUT_CSV = ROOT / "data" / "processed" / "joint_posteriors.csv"
OUT_TIMING = ROOT / "data" / "processed" / "joint_replay_timing.json"

# Brute-force cross-check stride: every Nth play WITH cross-card
# constraints is verified against exhaustive enumeration (prime stride).
BRUTE_CHECK_EVERY = 197


def replay_game_both_posteriors(
    game_json: dict,
    data_source: str,
    game_key_prefix: str = "",
    stats: dict | None = None,
) -> list[tuple]:
    """Replay one game, returning per-play rows with both posterior variants.

    Row format: (data_source, game_key, turn, player_seat,
                 posterior_marginal, posterior_joint,
                 n_cand_marginal, n_cand_joint, n_constrained_others)
    """
    state = state_from_hanab_live(game_json)
    state.deal_initial_hands()
    actions = actions_from_hanab_live(game_json)

    game_id = game_json.get("id", 0)
    game_key = f"{game_key_prefix}:{game_id}" if game_key_prefix else str(game_id)

    rows = []
    for action in actions:
        if state.game_over:
            break
        if action.action_type == ActionType.GAME_OVER:
            break

        if action.action_type in (ActionType.PLAY, ActionType.DISCARD):
            hand_pos = state.find_hand_index_by_deck_index(
                state.current_player, action.target
            )
            translated = Action(action.action_type, target=hand_pos, value=action.value)
        else:
            translated = action

        if action.action_type == ActionType.PLAY:
            player_id = state.current_player
            card_index = translated.target

            t0 = time.perf_counter()
            p_marg, n_cand = compute_life_loss_posterior(state, player_id, card_index)
            t1 = time.perf_counter()
            p_joint, n_cand_joint, n_constrained = compute_joint_posterior(
                state, player_id, card_index
            )
            t2 = time.perf_counter()

            if stats is not None:
                stats["plays"] += 1
                stats["marginal_time"] += t1 - t0
                stats["joint_time"] += t2 - t1
                if (
                    n_constrained > 0
                    and stats["plays"] % BRUTE_CHECK_EVERY == 0
                ):
                    bf = brute_force_joint_posterior(state, player_id, card_index)
                    if bf is not None:
                        d = abs(bf - p_joint)
                        stats["brute_checks"] += 1
                        stats["brute_max_absdiff"] = max(
                            stats["brute_max_absdiff"], d
                        )
                        if d > 1e-12:
                            raise AssertionError(
                                f"brute-force mismatch {d} at {game_key} "
                                f"turn {state.turn}"
                            )

            rows.append(
                (
                    data_source,
                    game_key,
                    state.turn,
                    player_id,
                    f"{p_marg:.12g}",
                    f"{p_joint:.12g}",
                    n_cand,
                    n_cand_joint,
                    n_constrained,
                )
            )

        state.apply_action(translated)

    return rows


def regenerate(verbose: bool = True) -> dict:
    """Replay all three raw corpora and write the joint-posterior CSV."""
    raw = ROOT / "data" / "raw"
    stats = {
        "plays": 0,
        "marginal_time": 0.0,
        "joint_time": 0.0,
        "brute_checks": 0,
        "brute_max_absdiff": 0.0,
    }
    t_start = time.perf_counter()

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "data_source",
                "game_key",
                "turn",
                "player_seat",
                "posterior_marginal",
                "posterior_joint",
                "n_cand_marginal",
                "n_cand_joint",
                "n_constrained_others",
            ]
        )

        for f in sorted((raw / "exports").glob("*.json")):
            game = json.load(open(f))
            try:
                w.writerows(replay_game_both_posteriors(game, "hanab_live", stats=stats))
            except AssertionError:
                raise
            except Exception as e:
                if verbose:
                    print(f"  skip {f.name}: {e}")

        for f in sorted((raw / "hoad").glob("*.json")):
            games = json.load(open(f))
            if not isinstance(games, list):
                games = [games]
            for game in games:
                try:
                    w.writerows(
                        replay_game_both_posteriors(
                            game, "hoad", game_key_prefix=f.stem, stats=stats
                        )
                    )
                except AssertionError:
                    raise
                except Exception as e:
                    if verbose:
                        print(f"  skip {f.stem}:{game.get('id')}: {e}")

        for f in sorted((raw / "hanabi_data" / "converted").glob("*.json")):
            game = json.load(open(f))
            try:
                w.writerows(replay_game_both_posteriors(game, "hanabi_data", stats=stats))
            except AssertionError:
                raise
            except Exception as e:
                if verbose:
                    print(f"  skip {f.name}: {e}")

    stats["wall_clock_s"] = time.perf_counter() - t_start
    OUT_TIMING.write_text(json.dumps(stats, indent=2))
    if verbose:
        n = stats["plays"]
        print(f"joint replay: {n:,} plays, wall {stats['wall_clock_s']:.0f}s, "
              f"marginal {stats['marginal_time'] / n * 1e6:.0f}us/play, "
              f"joint {stats['joint_time'] / n * 1e6:.0f}us/play, "
              f"brute checks {stats['brute_checks']} "
              f"(max diff {stats['brute_max_absdiff']:.1e})")
    return stats


def load_joint_posteriors(regenerate_if_missing: bool = True):
    """Load the joint-posterior CSV as a DataFrame (regenerating if absent)."""
    import pandas as pd

    if not OUT_CSV.exists():
        if not regenerate_if_missing:
            raise FileNotFoundError(OUT_CSV)
        regenerate()
    df = pd.read_csv(OUT_CSV, dtype={"game_key": str})
    df["turn"] = df["turn"].astype(int)
    return df


if __name__ == "__main__":
    regenerate()
