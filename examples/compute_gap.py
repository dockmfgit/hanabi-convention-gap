"""End-to-end example: replay game logs and compute the convention gap.

Usage:
    python examples/generate_example_games.py   # once, to create inputs
    python examples/compute_gap.py [dir-of-game-jsons]

With no argument, uses the synthetic games in examples/games/. Point it at
a directory of real hanab.live exports (https://hanab.live/export/<id>)
to analyze real games.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from convention_gap import (
    bootstrap_gap_ci,
    cluster_bootstrap_gap_ci,
    convention_gap,
    gap_by_hint_count,
    process_games,
)


def main():
    game_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        Path(__file__).resolve().parent / "games"
    )
    files = sorted(game_dir.glob("*.json"))
    if not files:
        raise SystemExit(
            f"no .json games in {game_dir} — run generate_example_games.py first"
        )

    games = [json.loads(f.read_text()) for f in files]
    records = process_games(games)
    print(f"replayed {len(games)} games -> {len(records)} play actions\n")

    overall = convention_gap(records)
    lo, hi = bootstrap_gap_ci(records, n_boot=2000)
    clo, chi = cluster_bootstrap_gap_ci(records, n_boot=2000)
    mean_marginal = sum(r.posterior_marginal for r in records) / len(records)
    n_affected = sum(
        1 for r in records
        if abs(r.posterior_p_life_loss - r.posterior_marginal) > 1e-12
    )
    print(f"mean posterior P(life loss): {overall['mean_posterior']:.3f}  "
          f"(exact full-hand joint inference)")
    print(f"  [per-card marginal simplification would give "
          f"{mean_marginal:.3f}; joint != marginal on "
          f"{n_affected}/{len(records)} plays]")
    print(f"actual life-loss rate:       {overall['loss_rate']:.3f}")
    print(f"convention gap:              {overall['gap']*100:+.1f} pp")
    print(f"  95% CI (play-level bootstrap): "
          f"[{lo*100:+.1f}, {hi*100:+.1f}] pp")
    print(f"  95% CI (game-cluster bootstrap): "
          f"[{clo*100:+.1f}, {chi*100:+.1f}] pp\n")

    print("gap by hints on the played card:")
    for stratum, g in gap_by_hint_count(records).items():
        if g["n"]:
            print(f"  {stratum:>2} hints: n={g['n']:5d}  "
                  f"posterior={g['mean_posterior']:.3f}  "
                  f"loss={g['loss_rate']:.3f}  gap={g['gap']*100:+.1f} pp")


if __name__ == "__main__":
    main()
