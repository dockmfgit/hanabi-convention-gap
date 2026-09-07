"""Convention-gap computation over extracted PlayRecords.

The convention gap of a group of play actions is

    gap = mean(posterior P(life loss)) - mean(actual life-loss rate)

where the posterior is the exact "literal information only" Bayesian
estimate computed at each play (see ``posterior.py``). A positive gap
means the group succeeds more often than the literal hint content
predicts — evidence that partners extract extra information through
conventions, intent inference, or other implicit channels. A gap near
zero means outcomes are fully explained by literal information.

All functions are pure standard-library Python and accept a list of
``PlayRecord`` objects (from ``replay.replay_and_extract`` /
``replay.process_games``).
"""

from __future__ import annotations

import random
from typing import Sequence

from convention_gap.replay import PlayRecord


def convention_gap(records: Sequence[PlayRecord]) -> dict:
    """Compute the convention gap for a set of play records.

    Returns a dict with:
        n               number of play actions
        mean_posterior  mean predicted P(life loss)
        loss_rate       fraction of plays that actually failed
        gap             mean_posterior - loss_rate
    """
    n = len(records)
    if n == 0:
        return {"n": 0, "mean_posterior": None, "loss_rate": None, "gap": None}
    mean_post = sum(r.posterior_p_life_loss for r in records) / n
    loss_rate = sum(0 if r.was_playable else 1 for r in records) / n
    return {
        "n": n,
        "mean_posterior": mean_post,
        "loss_rate": loss_rate,
        "gap": mean_post - loss_rate,
    }


def bootstrap_gap_ci(
    records: Sequence[PlayRecord],
    n_boot: int = 10_000,
    alpha: float = 0.05,
    seed: int = 42,
) -> tuple[float, float]:
    """Percentile bootstrap confidence interval for the convention gap.

    Resamples play records with replacement (play-level bootstrap).
    Returns (lower, upper) at the 1 - alpha level.
    """
    n = len(records)
    if n == 0:
        raise ValueError("no records")
    post = [r.posterior_p_life_loss for r in records]
    lost = [0.0 if r.was_playable else 1.0 for r in records]
    rng = random.Random(seed)
    gaps = []
    for _ in range(n_boot):
        sp = sl = 0.0
        for _ in range(n):
            i = rng.randrange(n)
            sp += post[i]
            sl += lost[i]
        gaps.append((sp - sl) / n)
    gaps.sort()
    lo = gaps[int((alpha / 2) * n_boot)]
    hi = gaps[min(int((1 - alpha / 2) * n_boot), n_boot - 1)]
    return lo, hi


def cluster_bootstrap_gap_ci(
    records: Sequence[PlayRecord],
    n_boot: int = 10_000,
    alpha: float = 0.05,
    seed: int = 42,
) -> tuple[float, float]:
    """Game-level cluster bootstrap CI for the convention gap.

    Resamples whole games (clusters keyed by ``PlayRecord.game_key``) with
    replacement, which accounts for within-game correlation of plays.
    """
    by_game: dict[str, list[tuple[float, float]]] = {}
    for r in records:
        by_game.setdefault(str(r.game_key), []).append(
            (r.posterior_p_life_loss, 0.0 if r.was_playable else 1.0)
        )
    games = [
        (sum(p for p, _ in plays), sum(l for _, l in plays), len(plays))
        for plays in by_game.values()
    ]
    n_g = len(games)
    if n_g == 0:
        raise ValueError("no records")
    rng = random.Random(seed)
    gaps = []
    for _ in range(n_boot):
        sp = sl = nn = 0.0
        for _ in range(n_g):
            gp, gl, gn = games[rng.randrange(n_g)]
            sp += gp
            sl += gl
            nn += gn
        gaps.append((sp - sl) / nn)
    gaps.sort()
    lo = gaps[int((alpha / 2) * n_boot)]
    hi = gaps[min(int((1 - alpha / 2) * n_boot), n_boot - 1)]
    return lo, hi


def gap_by_hint_count(records: Sequence[PlayRecord]) -> dict:
    """Convention gap stratified by the number of hint actions that touched
    the played card: strata '0', '1', and '2+'.

    The gap concentrates in the 0- and 1-hint strata for human play — the
    plays where literal information is weakest and conventions matter most.
    """
    strata = {"0": [], "1": [], "2+": []}
    for r in records:
        if r.hints_on_card == 0:
            strata["0"].append(r)
        elif r.hints_on_card == 1:
            strata["1"].append(r)
        else:
            strata["2+"].append(r)
    return {k: convention_gap(v) for k, v in strata.items()}
