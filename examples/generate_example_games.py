"""Generate synthetic example games in hanab.live export format.

Plays 2-player games with a simple scripted policy (using the engine's
perfect deck knowledge, so every action is legal) and records them in the
same JSON format as a hanab.live game export. This gives the example
pipeline real, replayable inputs without shipping any real players' data.

Policy per turn (in order):
  1. If any card in the current player's hand is playable, play it.
  2. Else, if info tokens remain, hint the partner's first card's rank.
  3. Else, discard the oldest card.

Run:  python examples/generate_example_games.py
Writes examples/games/game_<n>.json
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from convention_gap.game_engine import (
    ALL_COLORS,
    CARD_DISTRIBUTION,
    Action,
    ActionType,
    HanabiState,
)

OUT_DIR = Path(__file__).resolve().parent / "games"


def full_deck() -> list[tuple[int, int]]:
    return [
        (color, rank)
        for color in sorted(ALL_COLORS)
        for rank, copies in CARD_DISTRIBUTION.items()
        for _ in range(copies)
    ]


def scripted_action(state: HanabiState) -> Action:
    """Choose a legal action for the current player (perfect-info policy)."""
    p = state.current_player
    for i, (color, rank) in enumerate(state.hands[p]):
        if state.is_playable(color, rank):
            return Action(ActionType.PLAY, target=i)
    partner = 1 - p
    if state.info_tokens > 0 and state.hands[partner]:
        _, rank = state.hands[partner][0]
        return Action(ActionType.RANK_CLUE, target=partner, value=rank)
    return Action(ActionType.DISCARD, target=0)


def play_one_game(game_id: int, seed: int) -> dict:
    rng = random.Random(seed)
    deck = full_deck()
    rng.shuffle(deck)

    state = HanabiState(num_players=2, deck=deck)
    state.deal_initial_hands()

    actions_json = []
    while not state.game_over:
        action = scripted_action(state)
        # Record in hanab.live format: play/discard targets are DECK indices
        if action.action_type in (ActionType.PLAY, ActionType.DISCARD):
            deck_idx = state.hand_deck_indices[state.current_player][action.target]
            actions_json.append(
                {"type": int(action.action_type), "target": deck_idx, "value": 0}
            )
        else:
            actions_json.append(
                {
                    "type": int(action.action_type),
                    "target": action.target,
                    "value": action.value,
                }
            )
        state.apply_action(action)

    return {
        "id": game_id,
        "players": ["Player0", "Player1"],
        "deck": [{"suitIndex": c, "rank": r} for c, r in deck],
        "actions": actions_json,
        "options": {"variant": "No Variant", "numPlayers": 2},
    }


def main():
    OUT_DIR.mkdir(exist_ok=True)
    for i in range(20):
        game = play_one_game(game_id=i + 1, seed=1000 + i)
        path = OUT_DIR / f"game_{i + 1:02d}.json"
        path.write_text(json.dumps(game))
    print(f"wrote 20 games to {OUT_DIR}/")


if __name__ == "__main__":
    main()
