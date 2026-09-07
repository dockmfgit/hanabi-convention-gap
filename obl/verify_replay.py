"""Verify exported OBL games replay exactly in the convention_gap engine.

Checks, per game: replayed final score == HLE ground-truth score, and the
game consumed all actions without error.
"""
import json
import sys

sys.path.insert(0, "$OBL_ROOT/hanabi-convention-gap")

from convention_gap import replay_and_extract

path = sys.argv[1]
games = json.load(open(path))

n_bad = 0
for g in games:
    records, state = replay_and_extract(g)
    reason = state.get_game_end_reason(hit_terminate_marker=False)
    cg_score = 0 if reason == "strikeout" else state.get_final_score()
    ok = cg_score == g["hle_score"] and state.game_over
    if not ok:
        n_bad += 1
        print(
            f"MISMATCH game {g['id']}: cg={cg_score} hle={g['hle_score']} "
            f"reason={reason} game_over={state.game_over}"
        )
print(f"{path}: {len(games)} games, {n_bad} mismatches")
