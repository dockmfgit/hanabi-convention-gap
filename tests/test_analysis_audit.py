"""Tests for the 2026-09-07 computational-audit fixes (items 1 and 2).

1. First-mover game assignment for AI-AI per-agent scores: every HOAD game is
   assigned to the first-named agent of its pairing file, giving exactly 700
   games per agent, 4,900 in total, each game exactly once.
2. link_hint_to_next_play: a hint links to the play record at (game_id,
   turn + 1) when one exists, else NaN.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.analysis import link_hint_to_next_play

AGENT_CSV = Path(__file__).resolve().parent.parent / "data" / "processed" / "agent_play_records.csv"


@pytest.mark.skipif(not AGENT_CSV.exists(), reason="agent_play_records.csv not present")
def test_first_mover_selection_700_games_per_agent():
    agent_df = pd.read_csv(AGENT_CSV, usecols=["game_key"])
    pair = agent_df["game_key"].str.split(":").str[0]
    first_mover = pair.str.split("_vs_").str[0]

    games_per_agent = (
        pd.DataFrame({"game_key": agent_df["game_key"], "agent": first_mover})
        .drop_duplicates("game_key")
        .groupby("agent")["game_key"]
        .nunique()
    )
    assert len(games_per_agent) == 7
    assert (games_per_agent == 700).all(), games_per_agent.to_dict()
    assert games_per_agent.sum() == 4900

    # Each game is assigned to exactly one agent (assignment is a function of
    # game_key, so the per-agent game sets partition the 4,900 unique games).
    assert agent_df["game_key"].nunique() == 4900


def test_link_hint_to_next_play_synthetic():
    # 3-turn game: hint at turn 0 -> play at turn 1 (failed); hint at turn 2 -> no play at turn 3
    hint_df = pd.DataFrame({"game_id": [1, 1], "turn": [0, 2]})
    play_df = pd.DataFrame(
        {
            "game_id": [1, 1],
            "turn": [1, 4],
            "was_playable": [False, True],
        }
    )
    linked = link_hint_to_next_play(hint_df, play_df)
    assert list(linked.index) == list(hint_df.index)
    assert linked.iloc[0] == 1.0  # play at turn 1 lost a life
    assert np.isnan(linked.iloc[1])  # no play record at turn 3

    # Successful play links as 0.0
    hint_df2 = pd.DataFrame({"game_id": [1], "turn": [3]})
    assert link_hint_to_next_play(hint_df2, play_df).iloc[0] == 0.0
