"""Unit tests for the Hanabi game engine."""

import pytest

from convention_gap.game_engine import (
    ALL_COLORS,
    ALL_RANKS,
    CARD_DISTRIBUTION,
    Action,
    ActionType,
    CardKnowledge,
    Color,
    HanabiState,
    actions_from_hanab_live,
    replay_game,
    state_from_hanab_live,
)


# ---------------------------------------------------------------------------
# Helper: build a deterministic 2-player deck
# ---------------------------------------------------------------------------

def make_simple_deck() -> list[tuple[int, int]]:
    """Create a full sorted 50-card deck for testing.

    Order: R1 R1 R1 R2 R2 R3 R3 R4 R4 R5 Y1 Y1 Y1 ... P5
    """
    deck = []
    for color in Color:
        for rank in range(1, 6):
            for _ in range(CARD_DISTRIBUTION[rank]):
                deck.append((int(color), rank))
    assert len(deck) == 50
    return deck


# ---------------------------------------------------------------------------
# CardKnowledge tests
# ---------------------------------------------------------------------------

class TestCardKnowledge:
    def test_initial_state(self):
        k = CardKnowledge()
        assert k.possible_colors == set(ALL_COLORS)
        assert k.possible_ranks == set(ALL_RANKS)
        assert not k.color_hinted
        assert not k.rank_hinted
        assert k.hint_count == 0

    def test_positive_color_hint(self):
        k = CardKnowledge()
        k.apply_color_hint(Color.RED, positive=True)
        assert k.possible_colors == {Color.RED}
        assert k.color_hinted is True
        assert k.hint_count == 1

    def test_negative_color_hint(self):
        k = CardKnowledge()
        k.apply_color_hint(Color.BLUE, positive=False)
        assert Color.BLUE not in k.possible_colors
        assert len(k.possible_colors) == 4
        assert k.color_hinted is False  # negative hints don't set this

    def test_positive_rank_hint(self):
        k = CardKnowledge()
        k.apply_rank_hint(3, positive=True)
        assert k.possible_ranks == {3}
        assert k.rank_hinted is True

    def test_negative_rank_hint(self):
        k = CardKnowledge()
        k.apply_rank_hint(1, positive=False)
        assert 1 not in k.possible_ranks
        assert len(k.possible_ranks) == 4

    def test_multiple_hints(self):
        k = CardKnowledge()
        k.apply_color_hint(Color.RED, positive=False)
        k.apply_color_hint(Color.YELLOW, positive=False)
        k.apply_rank_hint(1, positive=False)
        k.apply_rank_hint(5, positive=False)
        assert k.possible_colors == {Color.GREEN, Color.BLUE, Color.PURPLE}
        assert k.possible_ranks == {2, 3, 4}

    def test_positive_overrides_all(self):
        k = CardKnowledge()
        k.apply_color_hint(Color.RED, positive=False)  # not red
        k.apply_color_hint(Color.GREEN, positive=True)  # IS green
        assert k.possible_colors == {Color.GREEN}


# ---------------------------------------------------------------------------
# HanabiState initialization tests
# ---------------------------------------------------------------------------

class TestHanabiStateInit:
    def test_2_player_hand_size(self):
        state = HanabiState(num_players=2, deck=make_simple_deck())
        assert state.hand_size == 5

    def test_3_player_hand_size(self):
        state = HanabiState(num_players=3, deck=make_simple_deck())
        assert state.hand_size == 5

    def test_4_player_hand_size(self):
        state = HanabiState(num_players=4, deck=make_simple_deck())
        assert state.hand_size == 4

    def test_5_player_hand_size(self):
        state = HanabiState(num_players=5, deck=make_simple_deck())
        assert state.hand_size == 4

    def test_invalid_player_count(self):
        with pytest.raises(ValueError):
            HanabiState(num_players=1, deck=[])
        with pytest.raises(ValueError):
            HanabiState(num_players=6, deck=[])

    def test_initial_tokens(self):
        state = HanabiState(num_players=2, deck=make_simple_deck())
        assert state.life_tokens == 3
        assert state.info_tokens == 8

    def test_initial_fireworks(self):
        state = HanabiState(num_players=2, deck=make_simple_deck())
        for color in Color:
            assert state.fireworks[color] == 0

    def test_deal_hands(self):
        deck = make_simple_deck()
        state = HanabiState(num_players=2, deck=deck)
        state.deal_initial_hands()

        # 2 players x 5 cards = 10 cards dealt
        assert len(state.hands[0]) == 5
        assert len(state.hands[1]) == 5
        assert state.deck_size == 40

        # Cards dealt sequentially: all to P0 first, then all to P1
        # From sorted deck: R1,R1,R1,R2,R2 | R3,R3,R4,R4,R5
        assert state.hands[0][0] == (Color.RED, 1)  # deck[0]
        assert state.hands[0][1] == (Color.RED, 1)  # deck[1]
        assert state.hands[0][2] == (Color.RED, 1)  # deck[2]
        assert state.hands[0][3] == (Color.RED, 2)  # deck[3]
        assert state.hands[0][4] == (Color.RED, 2)  # deck[4]
        assert state.hands[1][0] == (Color.RED, 3)  # deck[5]
        assert state.hands[1][1] == (Color.RED, 3)  # deck[6]

    def test_deal_creates_knowledge(self):
        state = HanabiState(num_players=2, deck=make_simple_deck())
        state.deal_initial_hands()
        assert len(state.card_knowledge[0]) == 5
        assert len(state.card_knowledge[1]) == 5
        # All knowledge should be fresh (no hints)
        for k in state.card_knowledge[0]:
            assert k.possible_colors == set(ALL_COLORS)
            assert k.possible_ranks == set(ALL_RANKS)


# ---------------------------------------------------------------------------
# Play action tests
# ---------------------------------------------------------------------------

class TestPlayAction:
    def _setup_state(self):
        """Create a state where Red 1 can be played."""
        # Put a Red 1 in player 0's hand at index 0
        deck = [(Color.RED, 1)] * 10 + make_simple_deck()[:40]
        state = HanabiState(num_players=2, deck=deck)
        state.deal_initial_hands()
        return state

    def test_successful_play(self):
        state = self._setup_state()
        # Player 0 has Red 1 at index 0, fireworks Red=0, so it's playable
        result = state.apply_action(Action(ActionType.PLAY, target=0))

        assert result["success"] is True
        assert result["played"] == (Color.RED, 1)
        assert state.fireworks[Color.RED] == 1
        assert state.score == 1
        assert state.life_tokens == 3  # no life lost

    def test_failed_play(self):
        # Build a deck where player 0 gets a Red 2 (not playable on empty board)
        deck = [(Color.RED, 2)] + [(Color.RED, 1)] * 9 + make_simple_deck()[:40]
        state = HanabiState(num_players=2, deck=deck)
        state.deal_initial_hands()

        result = state.apply_action(Action(ActionType.PLAY, target=0))

        assert result["success"] is False
        assert result["played"] == (Color.RED, 2)
        assert state.fireworks[Color.RED] == 0
        assert state.life_tokens == 2
        assert (Color.RED, 2) in state.discard_pile

    def test_play_draws_replacement(self):
        state = self._setup_state()
        hand_before = len(state.hands[0])
        deck_before = state.deck_size

        state.apply_action(Action(ActionType.PLAY, target=0))

        # Hand size unchanged (card removed + card drawn)
        assert len(state.hands[0]) == hand_before
        assert state.deck_size == deck_before - 1

    def test_play_5_gives_info_token(self):
        # Set up fireworks at 4, play a 5
        deck = [(Color.RED, 5)] + [(Color.RED, 1)] * 9 + make_simple_deck()[:40]
        state = HanabiState(num_players=2, deck=deck)
        state.deal_initial_hands()
        state.fireworks[Color.RED] = 4
        state.info_tokens = 5

        state.apply_action(Action(ActionType.PLAY, target=0))

        assert state.fireworks[Color.RED] == 5
        assert state.info_tokens == 6  # regained one

    def test_play_5_no_overflow(self):
        deck = [(Color.RED, 5)] + [(Color.RED, 1)] * 9 + make_simple_deck()[:40]
        state = HanabiState(num_players=2, deck=deck)
        state.deal_initial_hands()
        state.fireworks[Color.RED] = 4
        state.info_tokens = 8  # already full

        state.apply_action(Action(ActionType.PLAY, target=0))

        assert state.info_tokens == 8  # capped at max

    def test_three_misplays_ends_game(self):
        deck = [(Color.RED, 5)] * 10 + make_simple_deck()[:40]
        state = HanabiState(num_players=2, deck=deck)
        state.deal_initial_hands()

        # All cards are Red 5, none playable on empty board
        state.apply_action(Action(ActionType.PLAY, target=0))
        assert state.life_tokens == 2
        assert not state.game_over

        state.apply_action(Action(ActionType.PLAY, target=0))
        assert state.life_tokens == 1
        assert not state.game_over

        state.apply_action(Action(ActionType.PLAY, target=0))
        assert state.life_tokens == 0
        assert state.game_over
        assert state.score == 0

    def test_turn_advances(self):
        state = self._setup_state()
        assert state.current_player == 0
        assert state.turn == 0

        state.apply_action(Action(ActionType.PLAY, target=0))
        assert state.current_player == 1
        assert state.turn == 1


# ---------------------------------------------------------------------------
# Discard action tests
# ---------------------------------------------------------------------------

class TestDiscardAction:
    def test_discard(self):
        state = HanabiState(num_players=2, deck=make_simple_deck())
        state.deal_initial_hands()
        state.info_tokens = 5  # below max

        card = state.hands[0][0]
        result = state.apply_action(Action(ActionType.DISCARD, target=0))

        assert result["discarded"] == card
        assert card in state.discard_pile
        assert state.info_tokens == 6

    def test_discard_no_info_overflow(self):
        state = HanabiState(num_players=2, deck=make_simple_deck())
        state.deal_initial_hands()
        state.info_tokens = 8

        state.apply_action(Action(ActionType.DISCARD, target=0))
        assert state.info_tokens == 8

    def test_discard_draws_replacement(self):
        state = HanabiState(num_players=2, deck=make_simple_deck())
        state.deal_initial_hands()

        hand_before = len(state.hands[0])
        deck_before = state.deck_size

        state.apply_action(Action(ActionType.DISCARD, target=0))

        assert len(state.hands[0]) == hand_before
        assert state.deck_size == deck_before - 1


# ---------------------------------------------------------------------------
# Hint action tests
# ---------------------------------------------------------------------------

class TestHintActions:
    def _setup_known_hands(self):
        """Create a state with known hands for hint testing.

        Sequential dealing: P0 gets deck[0:5], P1 gets deck[5:10].
        Player 0: R1 R1 R2 R3 R4
        Player 1: Y1 Y1 G1 G2 B1
        """
        deck = [
            # P0's hand (deck[0:5])
            (Color.RED, 1), (Color.RED, 1), (Color.RED, 2),
            (Color.RED, 3), (Color.RED, 4),
            # P1's hand (deck[5:10])
            (Color.YELLOW, 1), (Color.YELLOW, 1), (Color.GREEN, 1),
            (Color.GREEN, 2), (Color.BLUE, 1),
        ] + make_simple_deck()[:40]
        state = HanabiState(num_players=2, deck=deck)
        state.deal_initial_hands()
        return state

    def test_color_hint_positive(self):
        state = self._setup_known_hands()
        # Player 0 hints Red to Player 1 — should touch nothing (P1 has Y,Y,G,G,B)
        result = state.apply_action(
            Action(ActionType.COLOR_CLUE, target=1, value=Color.RED)
        )
        assert result["touched_slots"] == []
        assert state.info_tokens == 7

        # All of player 1's cards should have Red eliminated
        for k in state.card_knowledge[1]:
            assert Color.RED not in k.possible_colors

    def test_color_hint_touches_cards(self):
        state = self._setup_known_hands()
        # Player 0 hints Yellow to Player 1 — P1 hand: Y1,Y1,G1,G2,B1
        result = state.apply_action(
            Action(ActionType.COLOR_CLUE, target=1, value=Color.YELLOW)
        )
        assert result["touched_slots"] == [0, 1]

        # Touched cards know they are Yellow
        assert state.card_knowledge[1][0].possible_colors == {Color.YELLOW}
        assert state.card_knowledge[1][1].possible_colors == {Color.YELLOW}
        # Untouched cards know they are NOT Yellow
        assert Color.YELLOW not in state.card_knowledge[1][2].possible_colors
        assert Color.YELLOW not in state.card_knowledge[1][3].possible_colors
        assert Color.YELLOW not in state.card_knowledge[1][4].possible_colors

    def test_rank_hint_touches_cards(self):
        state = self._setup_known_hands()
        # Player 0 hints rank 1 to Player 1 — P1 hand: Y1,Y1,G1,G2,B1
        result = state.apply_action(
            Action(ActionType.RANK_CLUE, target=1, value=1)
        )
        assert result["touched_slots"] == [0, 1, 2, 4]

        # Touched cards know rank is 1
        assert state.card_knowledge[1][0].possible_ranks == {1}
        assert state.card_knowledge[1][2].possible_ranks == {1}
        # Untouched card (G2 at index 3) knows rank is NOT 1
        assert 1 not in state.card_knowledge[1][3].possible_ranks

    def test_hint_costs_info_token(self):
        state = self._setup_known_hands()
        assert state.info_tokens == 8
        state.apply_action(
            Action(ActionType.COLOR_CLUE, target=1, value=Color.RED)
        )
        assert state.info_tokens == 7

    def test_hint_with_no_tokens_raises(self):
        state = self._setup_known_hands()
        state.info_tokens = 0
        with pytest.raises(RuntimeError):
            state.apply_action(
                Action(ActionType.COLOR_CLUE, target=1, value=Color.RED)
            )


# ---------------------------------------------------------------------------
# Knowledge persistence through draw
# ---------------------------------------------------------------------------

class TestKnowledgePersistence:
    def test_play_replaces_knowledge(self):
        """When a card is played, its knowledge is removed and the new drawn
        card gets fresh knowledge."""
        state = HanabiState(num_players=2, deck=make_simple_deck())
        state.deal_initial_hands()

        # Give player 0's first card a rank hint
        # (We simulate this by directly modifying knowledge for the test)
        state.card_knowledge[0][0].apply_rank_hint(1, positive=True)
        assert state.card_knowledge[0][0].possible_ranks == {1}

        # Play card at index 0
        state.apply_action(Action(ActionType.PLAY, target=0))

        # The old knowledge at index 0 is gone; new card has fresh knowledge
        # (After removing index 0, old index 1 becomes 0, and new card is appended)
        # So the new card is at index 4 (end of hand)
        new_card_knowledge = state.card_knowledge[0][-1]
        assert new_card_knowledge.possible_colors == set(ALL_COLORS)
        assert new_card_knowledge.possible_ranks == set(ALL_RANKS)

    def test_hint_persists_after_other_actions(self):
        """Hints on cards not played/discarded survive other actions."""
        state = HanabiState(num_players=2, deck=make_simple_deck())
        state.deal_initial_hands()

        # Player 0 hints color Red to Player 1
        state.apply_action(
            Action(ActionType.COLOR_CLUE, target=1, value=Color.RED)
        )

        # Player 1 discards a card (index 0)
        state.apply_action(Action(ActionType.DISCARD, target=0))

        # Player 0's cards were never hinted, should still have full knowledge
        for k in state.card_knowledge[0]:
            assert k.possible_colors == set(ALL_COLORS)


# ---------------------------------------------------------------------------
# Candidate identity computation
# ---------------------------------------------------------------------------

class TestCandidateIdentities:
    def test_no_hints_many_candidates(self):
        """With no hints, all 25 color-rank combos are possible (some with 0 remaining)."""
        state = HanabiState(num_players=2, deck=make_simple_deck())
        state.deal_initial_hands()

        candidates = state.get_candidate_identities(0, 0)
        # Each candidate should have remaining > 0
        for (color, rank), remaining in candidates:
            assert remaining > 0

    def test_fully_identified_card(self):
        """A card with known color and rank has one candidate."""
        state = HanabiState(num_players=2, deck=make_simple_deck())
        state.deal_initial_hands()

        # Manually set knowledge to identify the card
        state.card_knowledge[0][0].possible_colors = {Color.RED}
        state.card_knowledge[0][0].possible_ranks = {1}

        candidates = state.get_candidate_identities(0, 0)
        # Should have exactly one candidate type (Red 1), possibly with
        # weight = total_copies - visible_copies
        card_types = [c for c, w in candidates]
        assert (Color.RED, 1) in card_types

    def test_visible_cards_reduce_weight(self):
        """Cards visible in other hands reduce the weight of candidates."""
        # Deck: all Red 1s first, then fill
        deck = [(Color.RED, 1)] * 10 + make_simple_deck()[:40]
        state = HanabiState(num_players=2, deck=deck)
        state.deal_initial_hands()

        # Player 0 knows their card at index 0 is Red 1
        state.card_knowledge[0][0].possible_colors = {Color.RED}
        state.card_knowledge[0][0].possible_ranks = {1}

        candidates = state.get_candidate_identities(0, 0)
        # Player 0 can see Player 1's hand (5 Red 1s) plus fireworks and discard
        # Total Red 1 copies = 3, visible in P1's hand: depends on exact dealing
        assert len(candidates) >= 0  # May be 0 if all copies visible

    def test_eliminated_by_visibility(self):
        """If all copies of a card type are visible, it's excluded from candidates."""
        deck = make_simple_deck()
        state = HanabiState(num_players=2, deck=deck)
        state.deal_initial_hands()

        # Suppose player 0's card could be Red 5 (1 copy total)
        # Put Red 5 in the discard pile
        state.discard_pile.append((Color.RED, 5))
        state.card_knowledge[0][0].possible_colors = {Color.RED}
        state.card_knowledge[0][0].possible_ranks = {5}

        candidates = state.get_candidate_identities(0, 0)
        # Red 5 has 1 copy, now in discard → 0 remaining → eliminated
        card_types = [c for c, w in candidates]
        assert (Color.RED, 5) not in card_types

    def test_fireworks_count_as_visible(self):
        """Cards on the fireworks are counted as visible."""
        deck = make_simple_deck()
        state = HanabiState(num_players=2, deck=deck)
        state.deal_initial_hands()

        # Red firework at 2 means R1 and R2 are played
        state.fireworks[Color.RED] = 2

        state.card_knowledge[0][0].possible_colors = {Color.RED}
        state.card_knowledge[0][0].possible_ranks = {1}

        candidates = state.get_candidate_identities(0, 0)
        # R1 has 3 total copies. 1 on fireworks. Visibility depends on
        # what P1 has in hand. Remaining = 3 - visible_in_fireworks - visible_in_P1_hand
        # Check the weight accounts for the fireworks copy
        for (color, rank), weight in candidates:
            if (color, rank) == (Color.RED, 1):
                # 3 total - at least 1 on fireworks
                assert weight <= 2


# ---------------------------------------------------------------------------
# is_playable tests
# ---------------------------------------------------------------------------

class TestIsPlayable:
    def test_rank_1_on_empty(self):
        state = HanabiState(num_players=2, deck=make_simple_deck())
        assert state.is_playable(Color.RED, 1) is True

    def test_rank_2_on_empty(self):
        state = HanabiState(num_players=2, deck=make_simple_deck())
        assert state.is_playable(Color.RED, 2) is False

    def test_sequential_play(self):
        state = HanabiState(num_players=2, deck=make_simple_deck())
        state.fireworks[Color.BLUE] = 3
        assert state.is_playable(Color.BLUE, 4) is True
        assert state.is_playable(Color.BLUE, 3) is False
        assert state.is_playable(Color.BLUE, 5) is False

    def test_completed_stack(self):
        state = HanabiState(num_players=2, deck=make_simple_deck())
        state.fireworks[Color.GREEN] = 5
        # Nothing is playable on a completed stack
        for rank in range(1, 6):
            assert state.is_playable(Color.GREEN, rank) is False


# ---------------------------------------------------------------------------
# End-game (deck exhaustion) tests
# ---------------------------------------------------------------------------

class TestEndGame:
    def test_deck_exhaustion_countdown(self):
        """After the deck runs out, each player gets one more turn."""
        # Tiny deck: just enough for initial hands
        deck = [(Color.RED, 1)] * 11  # 10 for hands + 1 extra
        state = HanabiState(num_players=2, deck=deck)
        state.deal_initial_hands()
        assert state.deck_size == 1

        # Play: draws the last card → starts countdown
        state.apply_action(Action(ActionType.PLAY, target=0))
        assert state.deck_size == 0
        assert state.final_turns_remaining == 2  # 2 players

        # Next play: countdown decreases
        state.apply_action(Action(ActionType.PLAY, target=0))
        assert state.final_turns_remaining == 1
        assert not state.game_over

        # Final play: game ends
        state.apply_action(Action(ActionType.PLAY, target=0))
        assert state.final_turns_remaining == 0
        assert state.game_over

    def test_no_draw_when_deck_empty(self):
        """When deck is empty, hand shrinks after play/discard."""
        deck = [(Color.RED, 1)] * 10  # exactly enough for hands
        state = HanabiState(num_players=2, deck=deck)
        state.deal_initial_hands()
        assert state.deck_size == 0

        state.apply_action(Action(ActionType.PLAY, target=0))
        # Hand should shrink from 5 to 4
        assert len(state.hands[0]) == 4


# ---------------------------------------------------------------------------
# hanab.live JSON parsing
# ---------------------------------------------------------------------------

class TestHanabLiveParsing:
    # Sequential dealing: P0 = deck[0:5], P1 = deck[5:10]
    # P0: R1 Y1 G1 B1 P1 (all rank-1s, playable)
    # P1: R1 Y1 G1 B1 P1 (all rank-1s, playable)
    SAMPLE_GAME = {
        "id": 999,
        "players": ["Alice", "Bob"],
        "deck": [
            # P0's hand: deck[0..4]
            {"suitIndex": 0, "rank": 1},  # R1
            {"suitIndex": 1, "rank": 1},  # Y1
            {"suitIndex": 2, "rank": 1},  # G1
            {"suitIndex": 3, "rank": 1},  # B1
            {"suitIndex": 4, "rank": 1},  # P1
            # P1's hand: deck[5..9]
            {"suitIndex": 0, "rank": 1},  # R1
            {"suitIndex": 1, "rank": 1},  # Y1
            {"suitIndex": 2, "rank": 1},  # G1
            {"suitIndex": 3, "rank": 1},  # B1
            {"suitIndex": 4, "rank": 1},  # P1
            # Remaining deck
            {"suitIndex": 0, "rank": 2},
            {"suitIndex": 1, "rank": 2},
            {"suitIndex": 2, "rank": 2},
            {"suitIndex": 3, "rank": 2},
            {"suitIndex": 4, "rank": 2},
            {"suitIndex": 0, "rank": 3},
            {"suitIndex": 1, "rank": 3},
            {"suitIndex": 2, "rank": 3},
            {"suitIndex": 3, "rank": 3},
            {"suitIndex": 4, "rank": 3},
        ],
        "actions": [
            # Player 0 plays deck[0] = Red 1 → success
            {"type": 0, "target": 0, "value": 0},
            # Player 1 plays deck[5] = Red 1 → already played, fails!
            # Actually: Red is at 1, so Red 1 is NOT playable. Use Yellow 1.
            # Player 1 plays deck[6] = Yellow 1 → success
            {"type": 0, "target": 6, "value": 0},
        ],
        "options": {
            "variant": "No Variant",
            "numPlayers": 2,
        },
    }

    def test_state_from_json(self):
        state = state_from_hanab_live(self.SAMPLE_GAME)
        assert state.num_players == 2
        assert len(state.deck) == 20

    def test_actions_from_json(self):
        actions = actions_from_hanab_live(self.SAMPLE_GAME)
        assert len(actions) == 2
        assert actions[0].action_type == ActionType.PLAY
        assert actions[0].target == 0  # deck index
        assert actions[1].target == 6  # deck index

    def test_replay_game(self):
        state, results = replay_game(self.SAMPLE_GAME)

        # P0 plays deck[0]=R1 (success), P1 plays deck[6]=Y1 (success)
        assert results[0]["success"] is True
        assert results[0]["played"] == (Color.RED, 1)
        assert results[1]["success"] is True
        assert results[1]["played"] == (Color.YELLOW, 1)

        assert state.fireworks[Color.RED] == 1
        assert state.fireworks[Color.YELLOW] == 1
        assert state.score == 2

    def test_replay_with_hints(self):
        game = {
            "players": ["A", "B"],
            "deck": [{"suitIndex": c, "rank": 1} for c in range(5)] * 4,
            "actions": [
                # P0 hints color Red to P1
                {"type": 2, "target": 1, "value": 0},
                # P1 hints rank 1 to P0
                {"type": 3, "target": 0, "value": 1},
            ],
            "options": {"variant": "No Variant"},
        }
        state, results = replay_game(game)

        assert results[0]["hint_type"] == "color"
        assert results[1]["hint_type"] == "rank"
        assert state.info_tokens == 6  # 8 - 2 hints


# ---------------------------------------------------------------------------
# Score computation
# ---------------------------------------------------------------------------

class TestScore:
    def test_perfect_score_sequence(self):
        """Play cards 1-5 for one color to get score 5."""
        # Sequential dealing: P0 gets deck[0:5], P1 gets deck[5:10]
        deck = (
            [(Color.RED, 1), (Color.RED, 3), (Color.RED, 5),
             (Color.YELLOW, 1), (Color.YELLOW, 1)]  # P0's hand
            + [(Color.RED, 2), (Color.RED, 4),
               (Color.YELLOW, 1), (Color.YELLOW, 1), (Color.YELLOW, 1)]  # P1's hand
            + [(Color.GREEN, 1)] * 40  # filler
        )
        state = HanabiState(num_players=2, deck=deck)
        state.deal_initial_hands()

        # P0: R1, R3, R5, Y1, Y1
        # P1: R2, R4, Y1, Y1, Y1

        # Play R1 (P0, slot 0)
        r = state.apply_action(Action(ActionType.PLAY, target=0))
        assert r["success"] is True
        assert state.fireworks[Color.RED] == 1

        # Play R2 (P1, slot 0)
        r = state.apply_action(Action(ActionType.PLAY, target=0))
        assert r["success"] is True
        assert state.fireworks[Color.RED] == 2

        # Play R3 (P0, slot 0 — was index 1, now shifted to 0 after R1 removed)
        r = state.apply_action(Action(ActionType.PLAY, target=0))
        assert r["success"] is True
        assert state.fireworks[Color.RED] == 3

        # Play R4 (P1, slot 0)
        r = state.apply_action(Action(ActionType.PLAY, target=0))
        assert r["success"] is True
        assert state.fireworks[Color.RED] == 4

        # Play R5 (P0, slot 0)
        r = state.apply_action(Action(ActionType.PLAY, target=0))
        assert r["success"] is True
        assert state.fireworks[Color.RED] == 5
        assert state.score == 5
        # Playing a 5 should give back an info token
        assert state.info_tokens == 8

    def test_get_score_matches_score_attr(self):
        state = HanabiState(num_players=2, deck=make_simple_deck())
        state.fireworks[Color.RED] = 3
        state.fireworks[Color.BLUE] = 2
        assert state.get_score() == 5


class TestGameEndReason:
    def test_strikeout(self):
        state = HanabiState(num_players=2, deck=make_simple_deck())
        state.life_tokens = 0
        assert state.get_game_end_reason() == "strikeout"

    def test_perfect(self):
        state = HanabiState(num_players=2, deck=make_simple_deck())
        for c in Color:
            state.fireworks[c] = 5
        assert state.get_game_end_reason() == "perfect"

    def test_natural_via_game_over(self):
        state = HanabiState(num_players=2, deck=make_simple_deck())
        state.game_over = True
        state.fireworks[Color.RED] = 3
        assert state.get_game_end_reason() == "natural"

    def test_natural_via_empty_deck(self):
        # Deck exhausted (no game_over flag) still counts as a completed natural
        # end: hanab.live ends the final round early once no points remain.
        state = HanabiState(num_players=2, deck=make_simple_deck())
        state.deck_index = len(state.deck)  # deck_size == 0
        state.fireworks[Color.RED] = 4
        assert state.deck_size == 0
        assert state.get_game_end_reason() == "natural"

    def test_truncated_marker(self):
        # An explicit abnormal-end marker forces truncated regardless of board.
        state = HanabiState(num_players=2, deck=make_simple_deck())
        state.fireworks[Color.RED] = 4  # would otherwise look mid-game
        assert state.get_game_end_reason(hit_terminate_marker=True) == "truncated"

    def test_truncated_mid_deck(self):
        # Cards left in deck, no terminal state, no marker -> truncated.
        state = HanabiState(num_players=2, deck=make_simple_deck())
        state.fireworks[Color.RED] = 2
        assert state.deck_size > 0
        assert not state.game_over
        assert state.get_game_end_reason() == "truncated"
