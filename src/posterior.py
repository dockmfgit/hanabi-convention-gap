"""Compute P(life lost | play action, game state) for Hanabi.

The posterior is the "literal information only" model: given the hints
received on a card, the visible cards (other hands, fireworks, discard),
what fraction of the remaining candidate identities are unplayable?
"""

from __future__ import annotations

from src.game_engine import CARD_DISTRIBUTION, HanabiState


def compute_life_loss_posterior(
    state: HanabiState,
    player_id: int,
    card_index: int,
) -> tuple[float, int]:
    """Compute P(life lost) for playing card at card_index.

    Args:
        state: Current game state (before the play action).
        player_id: Who is playing.
        card_index: Hand position of the card being played.

    Returns:
        (p_life_loss, num_candidates) where num_candidates is the number
        of distinct (color, rank) types with remaining copies > 0.
    """
    candidates = state.get_candidate_identities(player_id, card_index)

    if not candidates:
        return 0.0, 0

    total_weight = 0.0
    unplayable_weight = 0.0
    num_candidates = len(candidates)

    for (color, rank), remaining in candidates:
        total_weight += remaining
        if not state.is_playable(color, rank):
            unplayable_weight += remaining

    if total_weight == 0:
        return 0.0, 0

    return unplayable_weight / total_weight, num_candidates
