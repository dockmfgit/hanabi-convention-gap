"""Run agent-vs-agent Hanabi games and export as hanab.live-compatible JSON.

Since HLE compilation is unavailable (archived, C++ build issues), this module
runs games using our pure-Python game engine with the HOAD agents re-implemented
in src/agents.py.  The output JSON format matches hanab.live game exports, so
the downstream pipeline (replay.py, posterior.py, analysis.py) works unchanged.
"""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Optional

from src.agents import Agent, get_agent, AGENTS
from src.game_engine import (
    Action,
    ActionType,
    CARD_DISTRIBUTION,
    Color,
    HanabiState,
)

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "hoad"


def _generate_random_deck(num_colors: int = 5, num_ranks: int = 5) -> list[tuple[int, int]]:
    """Generate a shuffled standard Hanabi deck."""
    deck = []
    for color in range(num_colors):
        for rank in range(1, num_ranks + 1):
            copies = CARD_DISTRIBUTION[rank]
            deck.extend([(color, rank)] * copies)
    random.shuffle(deck)
    return deck


def _deck_to_json(deck: list[tuple[int, int]]) -> list[dict]:
    """Convert deck to hanab.live JSON format."""
    return [{"suitIndex": c, "rank": r} for c, r in deck]


def run_single_game(
    agents: list[Agent],
    deck: Optional[list[tuple[int, int]]] = None,
    num_players: int = 2,
) -> dict:
    """Run a single game with the given agents and return a hanab.live-style JSON.

    Args:
        agents: List of Agent instances, one per player.
        deck: Optional predetermined deck order. Random if None.
        num_players: Number of players (must match len(agents)).

    Returns:
        A dict matching hanab.live game export format.
    """
    if len(agents) != num_players:
        raise ValueError(f"Need {num_players} agents, got {len(agents)}")

    if deck is None:
        deck = _generate_random_deck()

    state = HanabiState(num_players=num_players, deck=deck)
    state.deal_initial_hands()

    actions_log: list[dict] = []
    max_turns = 500  # safety limit

    for _ in range(max_turns):
        if state.game_over:
            break

        player = state.current_player
        agent = agents[player]
        action = agent.act(state, player)

        # Convert hand-position target to deck-index for play/discard
        # (matches hanab.live's encoding)
        if action.action_type in (ActionType.PLAY, ActionType.DISCARD):
            hand_pos = action.target
            deck_idx = state.hand_deck_indices[player][hand_pos]
            actions_log.append({
                "type": int(action.action_type),
                "target": deck_idx,
                "value": action.value,
            })
        else:
            actions_log.append({
                "type": int(action.action_type),
                "target": action.target,
                "value": action.value,
            })

        state.apply_action(action)

    game_json = {
        "players": [a.name for a in agents],
        "deck": _deck_to_json(deck),
        "actions": actions_log,
        "options": {
            "variant": "No Variant",
            "numPlayers": num_players,
        },
        "score": state.get_score(),
    }

    return game_json


def generate_agent_games(
    subject_agent: str,
    partner_agent: str,
    num_games: int = 1000,
    num_players: int = 2,
    seed: Optional[int] = None,
) -> list[dict]:
    """Run games between two agents and export as hanab.live-format JSON logs.

    Args:
        subject_agent: Agent key for player 0 (the one we analyze).
        partner_agent: Agent key for player 1.
        num_games: Number of games to generate.
        num_players: Number of players (2 for standard analysis).
        seed: Optional random seed for reproducibility.

    Returns:
        List of game JSON dicts in hanab.live export format.
    """
    if seed is not None:
        random.seed(seed)

    agent_0 = get_agent(subject_agent)
    agent_1 = get_agent(partner_agent)
    agents = [agent_0, agent_1]

    # For >2 players, fill remaining slots with partner agent
    for _ in range(num_players - 2):
        agents.append(get_agent(partner_agent))

    games = []
    for i in range(num_games):
        game_json = run_single_game(agents, num_players=num_players)
        game_json["id"] = i
        games.append(game_json)

    scores = [g["score"] for g in games]
    mean_score = sum(scores) / len(scores) if scores else 0
    logger.info(
        "%s vs %s: %d games, mean score = %.1f",
        subject_agent, partner_agent, num_games, mean_score,
    )

    return games


def save_agent_games(
    games: list[dict],
    subject_agent: str,
    partner_agent: str,
    output_dir: Optional[Path] = None,
) -> Path:
    """Save agent game logs to disk as JSON.

    Returns:
        Path to the saved file.
    """
    out = output_dir or DATA_DIR
    out.mkdir(parents=True, exist_ok=True)
    filename = f"{subject_agent}_vs_{partner_agent}.json"
    path = out / filename
    with open(path, "w") as f:
        json.dump(games, f)
    logger.info("Saved %d games to %s", len(games), path)
    return path


def load_agent_games(
    subject_agent: str,
    partner_agent: str,
    data_dir: Optional[Path] = None,
) -> list[dict]:
    """Load previously saved agent game logs."""
    d = data_dir or DATA_DIR
    path = d / f"{subject_agent}_vs_{partner_agent}.json"
    with open(path) as f:
        return json.load(f)


def generate_cross_play_matrix(
    agent_names: Optional[list[str]] = None,
    num_games: int = 100,
    seed: int = 42,
    save: bool = True,
) -> dict[tuple[str, str], list[dict]]:
    """Generate games for all (subject, partner) agent pairings.

    Returns:
        Dict mapping (subject, partner) to list of game JSONs.
    """
    if agent_names is None:
        agent_names = list(AGENTS.keys())

    all_games: dict[tuple[str, str], list[dict]] = {}

    total_pairs = len(agent_names) ** 2
    completed = 0

    for subject in agent_names:
        for partner in agent_names:
            pair_seed = seed + hash((subject, partner)) % (2**31)
            games = generate_agent_games(
                subject, partner,
                num_games=num_games,
                seed=pair_seed,
            )
            all_games[(subject, partner)] = games
            if save:
                save_agent_games(games, subject, partner)
            completed += 1
            logger.info("Progress: %d/%d pairs", completed, total_pairs)

    return all_games


def score_summary(games: list[dict]) -> dict:
    """Quick score summary for a batch of games."""
    scores = [g["score"] for g in games]
    return {
        "n_games": len(scores),
        "mean": sum(scores) / len(scores) if scores else 0,
        "min": min(scores) if scores else 0,
        "max": max(scores) if scores else 0,
        "perfect": sum(1 for s in scores if s == 25),
    }
