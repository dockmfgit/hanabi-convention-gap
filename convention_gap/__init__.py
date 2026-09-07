"""Convention gap for Hanabi: an exact literal-information baseline for
measuring implicit communication in cooperative play.

The per-play posterior is the exact full-hand joint-inference posterior:
joint enumeration over all hint-consistent assignments of the acting
player's hand, weighted without replacement, marginalized to the played
card (``joint_posterior.py``). A per-card marginal simplification is also
provided for reference (``posterior.py``).

Pipeline:  game JSON (hanab.live export format)
             -> replay.replay_and_extract   (replay + per-play posterior)
             -> gap.convention_gap          (aggregate metric)
"""

from convention_gap.game_engine import (
    Action,
    ActionType,
    CardKnowledge,
    Color,
    HanabiState,
    actions_from_hanab_live,
    replay_game,
    state_from_hanab_live,
)
from convention_gap.joint_posterior import (
    brute_force_joint_posterior,
    compute_joint_posterior,
)
from convention_gap.posterior import compute_life_loss_posterior
from convention_gap.replay import (
    PlayRecord,
    process_games,
    records_to_dicts,
    replay_and_extract,
)
from convention_gap.gap import (
    bootstrap_gap_ci,
    cluster_bootstrap_gap_ci,
    convention_gap,
    gap_by_hint_count,
)

__version__ = "1.1.0"

__all__ = [
    "Action",
    "ActionType",
    "CardKnowledge",
    "Color",
    "HanabiState",
    "PlayRecord",
    "actions_from_hanab_live",
    "bootstrap_gap_ci",
    "brute_force_joint_posterior",
    "cluster_bootstrap_gap_ci",
    "compute_joint_posterior",
    "compute_life_loss_posterior",
    "convention_gap",
    "gap_by_hint_count",
    "process_games",
    "records_to_dicts",
    "replay_and_extract",
    "replay_game",
    "state_from_hanab_live",
]
