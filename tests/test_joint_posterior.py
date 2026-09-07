"""Tests for the full-hand joint-inference posterior (the primary metric)."""

import random

from src.game_engine import (
    CARD_DISTRIBUTION,
    Color,
    HanabiState,
)
from src.joint_posterior import (
    brute_force_joint_posterior,
    compute_joint_posterior,
)
from src.joint_replay import replay_game_both_posteriors
from src.posterior import compute_life_loss_posterior
from src.replay import replay_and_extract


def full_deck():
    return [
        (int(c), r)
        for c in Color
        for r, copies in CARD_DISTRIBUTION.items()
        for _ in range(copies)
    ]


def make_2p_state(deck):
    state = HanabiState(num_players=2, deck=deck)
    state.deal_initial_hands()
    return state


class TestReductionToMarginal:
    def test_unconstrained_hand_equals_marginal(self):
        """With no hint constraints on any OTHER card, joint == marginal."""
        state = make_2p_state(full_deck())
        # Constrain only the played card
        state.card_knowledge[0][0].possible_colors = {Color.RED}

        p_joint, n_j, n_constrained = compute_joint_posterior(state, 0, 0)
        p_marg, n_m = compute_life_loss_posterior(state, 0, 0)

        assert n_constrained == 0
        assert p_joint == p_marg
        assert n_j == n_m

    def test_fully_identified_playable(self):
        """Card known to be Red 1 on empty fireworks → P(loss)=0."""
        state = make_2p_state(full_deck())
        state.card_knowledge[0][0].possible_colors = {Color.RED}
        state.card_knowledge[0][0].possible_ranks = {1}
        p_joint, n_cand, _ = compute_joint_posterior(state, 0, 0)
        assert p_joint == 0.0
        assert n_cand == 1

    def test_fully_identified_unplayable(self):
        state = make_2p_state(full_deck())
        state.card_knowledge[0][0].possible_colors = {Color.RED}
        state.card_knowledge[0][0].possible_ranks = {2}
        p_joint, n_cand, _ = compute_joint_posterior(state, 0, 0)
        assert p_joint == 1.0
        assert n_cand == 1


class TestCrossCardInference:
    def test_known_other_card_removes_copy(self):
        """A hand-computable case where joint != marginal.

        Played card: known Red, rank 1 or 2. Another card in the SAME hand
        is fully identified as Red 1. Under joint inference that identified
        card consumes one hidden R1 copy, lowering the played card's chance
        of being the (playable) R1 and raising P(loss).
        """
        state = make_2p_state(full_deck())
        # Played card (slot 0): Red, rank 1 or 2
        state.card_knowledge[0][0].possible_colors = {Color.RED}
        state.card_knowledge[0][0].possible_ranks = {1, 2}
        # Other card (slot 1): fully identified Red 1
        state.card_knowledge[0][1].possible_colors = {Color.RED}
        state.card_knowledge[0][1].possible_ranks = {1}

        # P0 sees P1's hand = deck[5:10]. With the sorted full deck P0's
        # hand is R1,R1,R1,R2,R2 and P1's is R3,R3,R4,R4,R5 — so from P0's
        # view no R1/R2 copies are visible: pool has R1x3, R2x2.
        p_marg, _ = compute_life_loss_posterior(state, 0, 0)
        assert abs(p_marg - 2 / 5) < 1e-12  # 2 unplayable of 5 copies

        # Joint: slot 1 takes one R1. Played card weights become
        # R1: 3*2=6 ways... normalized: P(R2) = (2*3)/(2*3 + 3*2) = 0.5
        p_joint, _, n_constrained = compute_joint_posterior(state, 0, 0)
        assert n_constrained == 1
        assert abs(p_joint - 0.5) < 1e-12
        assert p_joint > p_marg

    def test_deltas_can_go_both_directions(self):
        """Joint inference can lower P(loss) too: if another card is known
        to be an UNPLAYABLE identity, it soaks up unplayable mass."""
        state = make_2p_state(full_deck())
        # Played card: Red, rank 1 or 2 (R1 playable, R2 not)
        state.card_knowledge[0][0].possible_colors = {Color.RED}
        state.card_knowledge[0][0].possible_ranks = {1, 2}
        # Other card fully identified as R2 (unplayable identity)
        state.card_knowledge[0][1].possible_colors = {Color.RED}
        state.card_knowledge[0][1].possible_ranks = {2}

        p_marg, _ = compute_life_loss_posterior(state, 0, 0)
        p_joint, _, _ = compute_joint_posterior(state, 0, 0)
        # One R2 copy consumed: P(R2) = (1*3)/(1*3 + 3*1) = 0.5 -> here
        # compute directly: weights R1: 3*(2 ways for R2 slot)=... just
        # assert the direction.
        assert p_joint < p_marg


class TestBruteForceAgreement:
    def test_random_states_match_brute_force(self):
        """DP result equals exhaustive enumeration on randomized states."""
        rng = random.Random(7)
        checked = 0
        for trial in range(30):
            deck = full_deck()
            rng.shuffle(deck)
            state = make_2p_state(deck)
            # Constrain hand cards to small candidate sets so the exhaustive
            # enumeration stays tractable (allowed-set product <= ~10k).
            for slot in range(5):
                if rng.random() < 0.85:
                    colors = rng.sample(list(Color), rng.randint(1, 2))
                    state.card_knowledge[0][slot].possible_colors = set(colors)
                if rng.random() < 0.85:
                    ranks = rng.sample(range(1, 6), rng.randint(1, 2))
                    state.card_knowledge[0][slot].possible_ranks = set(ranks)
            # Random board progress
            for c in Color:
                state.fireworks[c] = rng.randint(0, 2)

            p_joint, _, _ = compute_joint_posterior(state, 0, 0)
            p_bf = brute_force_joint_posterior(state, 0, 0)
            if p_bf is not None:
                assert abs(p_joint - p_bf) < 1e-12, f"trial {trial}"
                checked += 1
        assert checked >= 20  # ensure the test actually exercised the DP


class TestJointReplayIntegration:
    def _game(self):
        return {
            "id": 1,
            "players": ["A", "B"],
            "deck": [{"suitIndex": c, "rank": r}
                     for (c, r) in full_deck()],
            "actions": [
                {"type": 2, "target": 1, "value": 0},  # A hints Red to B
                {"type": 0, "target": 5, "value": 0},  # B plays deck[5]
            ],
            "options": {"variant": "No Variant"},
        }

    def test_rows_carry_both_posteriors(self):
        rows = replay_game_both_posteriors(self._game(), "hanab_live")
        assert len(rows) == 1
        (src_name, game_key, turn, seat, p_marg, p_joint,
         n_cm, n_cj, n_constrained) = rows[0]
        assert src_name == "hanab_live"
        assert game_key == "1"
        assert 0.0 <= float(p_marg) <= 1.0
        assert 0.0 <= float(p_joint) <= 1.0
        assert n_constrained >= 0

    def test_marginal_matches_main_pipeline(self):
        """The marginal recorded by joint_replay equals replay.py's posterior."""
        game = self._game()
        rows = replay_game_both_posteriors(game, "hanab_live")
        records, _ = replay_and_extract(game)
        assert len(rows) == len(records) == 1
        assert abs(float(rows[0][4]) - records[0].posterior_p_life_loss) < 1e-12
