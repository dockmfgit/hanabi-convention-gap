"""Convention gap for inter-level pairings, split by acting player.

For each OBLi x OBLj pairing: verify replay, mean score, and the gap
computed over (a) all plays, (b) only OBLi's plays, (c) only OBLj's plays.
"""
import json
import os
import sys

sys.path.insert(0, "$OBL_ROOT/hanabi-convention-gap")

from convention_gap import (
    process_games,
    convention_gap,
    cluster_bootstrap_gap_ci,
    replay_and_extract,
)

SP = "/tmp/claude-1002/-home-makotof-research-Hanabi-offbelief-learning/2f15f1ab-92f8-42b0-8e7d-65de0f3c304a/scratchpad"

out = []
for i in range(1, 6):
    for j in range(i + 1, 6):
        name = f"OBL{i}xOBL{j}"
        games = json.load(open(os.path.join(SP, "games", f"interlevel_{name}.json")))

        n_bad = 0
        for g in games:
            _, state = replay_and_extract(g)
            reason = state.get_game_end_reason(hit_terminate_marker=False)
            cg = 0 if reason == "strikeout" else state.get_final_score()
            if cg != g["hle_score"] or not (state.game_over or reason == "perfect"):
                n_bad += 1
        assert n_bad == 0, f"{name}: {n_bad} replay mismatches"
        score = sum(g["hle_score"] for g in games) / len(games)

        # subject_type=None -> each record's subject_type = acting player's name
        records = process_games(
            games, data_source="obl_interlevel",
            subject_type=None, partner_type=None, game_key_prefix=name,
        )
        row = {"pair": name, "i": i, "j": j, "score": score, "n_games": len(games)}
        for label, recs in [
            ("all", records),
            (f"OBL{i}", [r for r in records if r.subject_type == f"OBL{i}"]),
            (f"OBL{j}", [r for r in records if r.subject_type == f"OBL{j}"]),
        ]:
            agg = convention_gap(recs)
            lo, hi = cluster_bootstrap_gap_ci(recs)
            key = "all" if label == "all" else ("low" if label == f"OBL{i}" else "high")
            row[key] = {**agg, "ci95": [lo, hi], "player": label}
        out.append(row)
        print(
            f"{name}: score={score:.2f}  "
            f"gap_all={row['all']['gap']*100:+.2f}  "
            f"gap_{'OBL%d'%i}={row['low']['gap']*100:+.2f} "
            f"[{row['low']['ci95'][0]*100:+.2f},{row['low']['ci95'][1]*100:+.2f}]  "
            f"gap_{'OBL%d'%j}={row['high']['gap']*100:+.2f} "
            f"[{row['high']['ci95'][0]*100:+.2f},{row['high']['ci95'][1]*100:+.2f}]",
            flush=True,
        )

with open(f"{SP}/gap_interlevel.json", "w") as f:
    json.dump(out, f, indent=2)
print("wrote gap_interlevel.json")
