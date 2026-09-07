"""Tests for HanabiData client: parsing, conversion, and validation."""

import json
import textwrap
from pathlib import Path

import pytest

from src.game_engine import (
    ActionType,
    Color,
    HanabiState,
    replay_game,
)
from src.hanabi_data_client import (
    HD_TO_ENGINE_COLOR,
    HD_TO_HL_ACTION,
    HD_NAME_TO_COLOR,
    HanabiDataGameMeta,
    ParsedLog,
    ParsedMove,
    _extract_hand_from_line,
    _extract_played_card,
    _parse_move_fields,
    _undo_changes,
    convert_to_hanab_live_json,
    extract_initial_hands,
    load_games_csv,
    parse_card_from_text,
    parse_hand_from_text,
    parse_log_file,
    remap_card,
    validate_conversion,
)


# ---------------------------------------------------------------------------
# Color mapping tests
# ---------------------------------------------------------------------------

class TestColorMapping:
    def test_hd_to_engine_green(self):
        assert HD_TO_ENGINE_COLOR[0] == int(Color.GREEN)

    def test_hd_to_engine_yellow(self):
        assert HD_TO_ENGINE_COLOR[1] == int(Color.YELLOW)

    def test_hd_to_engine_white_is_purple(self):
        assert HD_TO_ENGINE_COLOR[2] == int(Color.PURPLE)

    def test_hd_to_engine_blue(self):
        assert HD_TO_ENGINE_COLOR[3] == int(Color.BLUE)

    def test_hd_to_engine_red(self):
        assert HD_TO_ENGINE_COLOR[4] == int(Color.RED)

    def test_all_five_colors_mapped(self):
        assert len(HD_TO_ENGINE_COLOR) == 5

    def test_name_to_hd_color(self):
        assert HD_NAME_TO_COLOR["green"] == 0
        assert HD_NAME_TO_COLOR["yellow"] == 1
        assert HD_NAME_TO_COLOR["white"] == 2
        assert HD_NAME_TO_COLOR["blue"] == 3
        assert HD_NAME_TO_COLOR["red"] == 4

    def test_remap_card(self):
        # green 4 in HanabiData → (GREEN=2, 4) in engine
        assert remap_card(0, 4) == (int(Color.GREEN), 4)
        # red 1 → (RED=0, 1)
        assert remap_card(4, 1) == (int(Color.RED), 1)
        # white 5 → (PURPLE=4, 5)
        assert remap_card(2, 5) == (int(Color.PURPLE), 5)


# ---------------------------------------------------------------------------
# Action type mapping tests
# ---------------------------------------------------------------------------

class TestActionMapping:
    def test_color_hint(self):
        assert HD_TO_HL_ACTION[0] == int(ActionType.COLOR_CLUE)

    def test_rank_hint(self):
        assert HD_TO_HL_ACTION[1] == int(ActionType.RANK_CLUE)

    def test_play(self):
        assert HD_TO_HL_ACTION[2] == int(ActionType.PLAY)

    def test_discard(self):
        assert HD_TO_HL_ACTION[3] == int(ActionType.DISCARD)


# ---------------------------------------------------------------------------
# Card and hand parsing tests
# ---------------------------------------------------------------------------

class TestCardParsing:
    def test_parse_card_blue_1(self):
        assert parse_card_from_text("blue 1") == (3, 1)

    def test_parse_card_green_4(self):
        assert parse_card_from_text("green 4") == (0, 4)

    def test_parse_card_white_5(self):
        assert parse_card_from_text("white 5") == (2, 5)

    def test_parse_card_red_3(self):
        assert parse_card_from_text("red 3") == (4, 3)

    def test_parse_card_yellow_2(self):
        assert parse_card_from_text("yellow 2") == (1, 2)

    def test_parse_card_with_extra_whitespace(self):
        assert parse_card_from_text("  blue  1  ") == (3, 1)


class TestHandParsing:
    def test_parse_hand_five_cards(self):
        hand = parse_hand_from_text("green 4, blue 1, blue 2, green 2, red 1")
        assert hand == [(0, 4), (3, 1), (3, 2), (0, 2), (4, 1)]

    def test_parse_hand_four_cards(self):
        hand = parse_hand_from_text("white 5, white 1, blue 1, yellow 1")
        assert hand == [(2, 5), (2, 1), (3, 1), (1, 1)]

    def test_parse_hand_single_card(self):
        hand = parse_hand_from_text("red 5")
        assert hand == [(4, 5)]


# ---------------------------------------------------------------------------
# MOVE line parsing tests
# ---------------------------------------------------------------------------

class TestMoveLineParsing:
    def test_rank_hint(self):
        fields = _parse_move_fields("MOVE: 0 1 None 1 None 1")
        assert fields["player"] == 0
        assert fields["action"] == 1
        assert fields["position"] is None
        assert fields["target"] == 1
        assert fields["color"] is None
        assert fields["rank"] == 1

    def test_play(self):
        fields = _parse_move_fields("MOVE: 1 2 1 1 None None")
        assert fields["player"] == 1
        assert fields["action"] == 2
        assert fields["position"] == 1
        assert fields["target"] == 1
        assert fields["color"] is None
        assert fields["rank"] is None

    def test_color_hint(self):
        fields = _parse_move_fields("MOVE: 0 0 None 1 3 None")
        assert fields["player"] == 0
        assert fields["action"] == 0
        assert fields["position"] is None
        assert fields["target"] == 1
        assert fields["color"] == 3
        assert fields["rank"] is None

    def test_discard(self):
        fields = _parse_move_fields("MOVE: 0 3 0 None None None")
        assert fields["player"] == 0
        assert fields["action"] == 3
        assert fields["position"] == 0
        assert fields["target"] is None
        assert fields["color"] is None
        assert fields["rank"] is None


# ---------------------------------------------------------------------------
# Description line extraction tests
# ---------------------------------------------------------------------------

class TestDescriptionExtraction:
    def test_extract_played_card_success(self):
        card = _extract_played_card("You plays blue 1 successfully! Board is now green 0, yellow 0, white 0, blue 1, red 0")
        assert card == (3, 1)

    def test_extract_played_card_fail(self):
        card = _extract_played_card("You plays green 2 and fails. Board was green 0, yellow 1, white 0, blue 4, red 2")
        assert card == (0, 2)

    def test_extract_discarded_card(self):
        card = _extract_played_card("intentional discards white 2")
        assert card == (2, 2)

    def test_extract_hand_from_has(self):
        hand = _extract_hand_from_line("You has green 4, blue 1, blue 2, green 2, red 1")
        assert hand == [(0, 4), (3, 1), (3, 2), (0, 2), (4, 1)]

    def test_extract_hand_from_now_has(self):
        hand = _extract_hand_from_line("You now has green 4, blue 2, green 2, red 1, red 2")
        assert hand == [(0, 4), (3, 2), (0, 2), (4, 1), (4, 2)]

    def test_extract_hand_ai_player(self):
        hand = _extract_hand_from_line("intentional now has green 3, white 4, green 2, red 5, blue 1")
        assert hand == [(0, 3), (2, 4), (0, 2), (4, 5), (3, 1)]

    def test_extract_hand_no_match(self):
        hand = _extract_hand_from_line("trash is now white 2")
        assert hand is None

    def test_extract_hand_hint_target(self):
        hand = _extract_hand_from_line("intentional has green 3, white 4, green 2, red 5, blue 1")
        assert hand == [(0, 3), (2, 4), (0, 2), (4, 5), (3, 1)]


# ---------------------------------------------------------------------------
# Undo changes (hand reconstruction) tests
# ---------------------------------------------------------------------------

class TestUndoChanges:
    def test_undo_single_discard(self):
        """AI discards pos 0 (white 2), draws blue 1.
        Observed after: [green 3, white 4, green 2, red 5, blue 1]
        Initial should be: [white 2, green 3, white 4, green 2, red 5]
        """
        observed = [(0, 3), (2, 4), (0, 2), (4, 5), (3, 1)]
        changes = [{"position": 0, "card": (2, 2), "draw_index": 0}]
        initial = _undo_changes(observed, changes)
        assert initial == [(2, 2), (0, 3), (2, 4), (0, 2), (4, 5)]

    def test_undo_no_changes(self):
        hand = [(0, 4), (3, 1), (3, 2), (0, 2), (4, 1)]
        assert _undo_changes(hand, []) == hand

    def test_undo_two_changes(self):
        """Two plays: pos 0 card A, then pos 2 card C.
        Original: [A, B, C, D, E]
        After play A from pos 0, draw F: [B, C, D, E, F]
        After play C from pos 2 (in new hand [B,C,D,E,F], pos 2 = D), draw G: [B, C, E, F, G]
        Wait, let me be precise.

        Original: [A, B, C, D, E]
        Play pos 0 (A removed): [B, C, D, E] → draw F → [B, C, D, E, F]
        Play pos 1 (C removed): [B, D, E, F] → draw G → [B, D, E, F, G]
        Observed: [B, D, E, F, G]
        Undo second (pos 1, card C): pop G → [B, D, E, F], insert C at 1 → [B, C, D, E, F]
        Undo first (pos 0, card A): pop F → [B, C, D, E], insert A at 0 → [A, B, C, D, E]
        """
        observed = ["B", "D", "E", "F", "G"]
        changes = [
            {"position": 0, "card": "A", "draw_index": 0},
            {"position": 1, "card": "C", "draw_index": 1},
        ]
        initial = _undo_changes(observed, changes)
        assert initial == ["A", "B", "C", "D", "E"]

    def test_undo_play_from_middle(self):
        """Play from position 3.
        Original: [A, B, C, D, E]
        Play pos 3 (D removed): [A, B, C, E] → draw F → [A, B, C, E, F]
        Undo: pop F → [A, B, C, E], insert D at 3 → [A, B, C, D, E]
        """
        observed = ["A", "B", "C", "E", "F"]
        changes = [{"position": 3, "card": "D", "draw_index": 0}]
        initial = _undo_changes(observed, changes)
        assert initial == ["A", "B", "C", "D", "E"]


# ---------------------------------------------------------------------------
# Log file parsing test (synthetic log)
# ---------------------------------------------------------------------------

SAMPLE_LOG = textwrap.dedent("""\
    Treatment: ('outer', 42)
    [(4, 2), (3, 4), (3, 1), (1, 1), (1, 5), (3, 3), (1, 2), (2, 3), (4, 1), (1, 2), (3, 4), (4, 4), (4, 1), (2, 5), (4, 2), (0, 4), (1, 3), (3, 2), (0, 1), (2, 1), (2, 1), (1, 3), (4, 3), (2, 1), (0, 3), (2, 2), (4, 4), (3, 1), (1, 4), (3, 5), (0, 5), (1, 1), (3, 3), (0, 1), (0, 1), (4, 3), (2, 4), (1, 4), (2, 3), (1, 1)]
    MOVE: 0 1 None 1 None 1
    outer hints You about all their 1 hints remaining: 7
    You has green 4, blue 1, blue 2, green 2, red 1
    MOVE: 1 2 1 1 None None
    You plays blue 1 successfully! Board is now green 0, yellow 0, white 0, blue 1, red 0
    You now has green 4, blue 2, green 2, red 1, red 2
    MOVE: 0 0 None 1 3 None
    outer hints You about all their blue cards hints remaining: 6
    You has green 4, blue 2, green 2, red 1, red 2
    MOVE: 1 2 1 1 None None
    You plays blue 2 successfully! Board is now green 0, yellow 0, white 0, blue 2, red 0
    You now has green 4, green 2, red 1, red 2, blue 4
    MOVE: 0 3 0 None None None
    outer discards white 2
    trash is now white 2
    outer now has green 3, white 4, green 2, red 5, blue 1
    Score 5
""")


class TestLogFileParsing:
    @pytest.fixture
    def parsed(self, tmp_path):
        log_file = tmp_path / "game1234567890abcdef.log"
        log_file.write_text(SAMPLE_LOG)
        return parse_log_file(log_file)

    def test_ai_type(self, parsed):
        assert parsed.ai_type == "outer"

    def test_seed(self, parsed):
        assert parsed.seed == 42

    def test_remaining_deck_length(self, parsed):
        assert len(parsed.remaining_deck) == 40

    def test_remaining_deck_first_card(self, parsed):
        assert parsed.remaining_deck[0] == (4, 2)

    def test_score(self, parsed):
        assert parsed.score == 5

    def test_game_file_id(self, parsed):
        assert parsed.game_file_id == "1234567890abcdef"

    def test_move_count(self, parsed):
        assert len(parsed.moves) == 5

    def test_first_move_is_rank_hint(self, parsed):
        m = parsed.moves[0]
        assert m.player == 0
        assert m.action == 1  # rank hint
        assert m.rank == 1
        assert m.target == 1

    def test_second_move_is_play(self, parsed):
        m = parsed.moves[1]
        assert m.player == 1
        assert m.action == 2  # play
        assert m.position == 1
        assert m.played_card == (3, 1)  # blue 1

    def test_fifth_move_is_discard(self, parsed):
        m = parsed.moves[4]
        assert m.player == 0
        assert m.action == 3  # discard
        assert m.position == 0
        assert m.played_card == (2, 2)  # white 2

    def test_hand_after_hint(self, parsed):
        # First hint shows Human's hand
        assert parsed.moves[0].hand_after == [
            (0, 4), (3, 1), (3, 2), (0, 2), (4, 1)
        ]

    def test_hand_after_play(self, parsed):
        assert parsed.moves[1].hand_after == [
            (0, 4), (3, 2), (0, 2), (4, 1), (4, 2)
        ]

    def test_hand_after_discard(self, parsed):
        assert parsed.moves[4].hand_after == [
            (0, 3), (2, 4), (0, 2), (4, 5), (3, 1)
        ]


# ---------------------------------------------------------------------------
# Log with predecessor (Old GID)
# ---------------------------------------------------------------------------

SAMPLE_LOG_WITH_PRED = textwrap.dedent("""\
    Old GID: abcdef0123456789
    Treatment: ('intentional', 99)
    [(0, 1), (0, 2), (0, 3), (0, 4), (0, 5)] + [(1, 1)] * 35
    MOVE: 0 1 None 1 None 1
    intentional hints You about all their 1 hints remaining: 7
    You has red 1, red 2, red 3, red 4, red 5
    Score 0
""")


class TestLogWithPredecessor:
    def test_predecessor_parsed(self, tmp_path):
        log_file = tmp_path / "game0000000000000001.log"
        # The deck line won't eval correctly with the "+" syntax,
        # so use a valid Python list
        content = textwrap.dedent("""\
            Old GID: abcdef0123456789
            Treatment: ('intentional', 99)
            [(0, 1), (0, 2), (0, 3), (0, 4), (0, 5), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1)]
            MOVE: 0 1 None 1 None 1
            intentional hints You about all their 1 hints remaining: 7
            You has red 1, red 2, red 3, red 4, red 5
            Score 0
        """)
        log_file.write_text(content)
        parsed = parse_log_file(log_file)
        assert parsed.predecessor_id == "abcdef0123456789"
        assert parsed.ai_type == "intentional"
        assert parsed.seed == 99


# ---------------------------------------------------------------------------
# Initial hand extraction tests
# ---------------------------------------------------------------------------

class TestExtractInitialHands:
    def test_human_hand_from_first_hint(self, tmp_path):
        """Human hand visible from very first hint (no prior changes)."""
        log_file = tmp_path / "game0000000000000002.log"
        log_file.write_text(SAMPLE_LOG)
        parsed = parse_log_file(log_file)
        ai_hand, human_hand = extract_initial_hands(parsed)

        # Human hand from first hint: green 4, blue 1, blue 2, green 2, red 1
        assert human_hand == [(0, 4), (3, 1), (3, 2), (0, 2), (4, 1)]

    def test_ai_hand_reconstructed(self, tmp_path):
        """AI hand reconstructed from post-discard hand."""
        log_file = tmp_path / "game0000000000000003.log"
        log_file.write_text(SAMPLE_LOG)
        parsed = parse_log_file(log_file)
        ai_hand, human_hand = extract_initial_hands(parsed)

        # AI discards white 2 from pos 0, draws blue 1.
        # Post-discard: green 3, white 4, green 2, red 5, blue 1
        # Undo: remove blue 1, insert white 2 at pos 0
        # Initial: white 2, green 3, white 4, green 2, red 5
        assert ai_hand == [(2, 2), (0, 3), (2, 4), (0, 2), (4, 5)]


# ---------------------------------------------------------------------------
# Full conversion test with known game
# ---------------------------------------------------------------------------

# A minimal 2-player game for end-to-end testing.
# AI goes first, plays R1 (success), Human plays B1 (success).
MINIMAL_LOG = textwrap.dedent("""\
    Treatment: ('simple', 1)
    [(0, 2), (0, 3), (0, 4), (0, 5), (1, 1), (1, 2), (1, 3), (1, 4), (1, 5), (2, 1), (2, 2), (2, 3), (2, 4), (2, 5), (3, 2), (3, 3), (3, 4), (3, 5), (4, 2), (4, 3), (4, 4), (4, 5), (0, 1), (0, 1), (0, 2), (1, 1), (1, 1), (1, 2), (2, 1), (2, 1), (2, 2), (3, 1), (3, 1), (3, 2), (4, 1), (4, 1), (4, 2), (3, 3), (3, 4), (3, 5)]
    MOVE: 0 0 None 1 4 None
    simple hints You about all their red cards hints remaining: 7
    You has red 1, blue 1, blue 2, blue 3, blue 4
    MOVE: 1 1 None 0 None 1
    You hints simple about all their 1 hints remaining: 6
    simple has green 1, red 3, red 4, red 5, yellow 1
    MOVE: 0 2 0 0 None None
    simple plays green 1 successfully! Board is now green 1, yellow 0, white 0, blue 0, red 0
    simple now has red 3, red 4, red 5, yellow 1, green 2
    MOVE: 1 2 0 1 None None
    You plays red 1 successfully! Board is now green 1, yellow 0, white 0, blue 0, red 1
    You now has blue 1, blue 2, blue 3, blue 4, green 3
    Score 2
""")


class TestConversion:
    @pytest.fixture
    def converted(self, tmp_path):
        log_file = tmp_path / "gameaabbccdd11223344.log"
        log_file.write_text(MINIMAL_LOG)
        parsed = parse_log_file(log_file)
        return convert_to_hanab_live_json(parsed, game_id=999)

    def test_game_id(self, converted):
        assert converted["id"] == 999

    def test_players(self, converted):
        # AI goes first → P0=simple, P1=Human
        assert converted["players"] == ["simple", "Human"]

    def test_deck_length(self, converted):
        assert len(converted["deck"]) == 50

    def test_deck_p0_hand(self, converted):
        """P0 (AI=simple) initial hand: green 1, red 3, red 4, red 5, yellow 1."""
        deck = converted["deck"]
        p0_hand = [(d["suitIndex"], d["rank"]) for d in deck[:5]]
        # green 1 → (GREEN=2, 1), red 3 → (RED=0, 3), red 4 → (RED=0, 4),
        # red 5 → (RED=0, 5), yellow 1 → (YELLOW=1, 1)
        assert p0_hand == [
            (int(Color.GREEN), 1),
            (int(Color.RED), 3),
            (int(Color.RED), 4),
            (int(Color.RED), 5),
            (int(Color.YELLOW), 1),
        ]

    def test_deck_p1_hand(self, converted):
        """P1 (Human) initial hand: red 1, blue 1, blue 2, blue 3, blue 4."""
        deck = converted["deck"]
        p1_hand = [(d["suitIndex"], d["rank"]) for d in deck[5:10]]
        assert p1_hand == [
            (int(Color.RED), 1),
            (int(Color.BLUE), 1),
            (int(Color.BLUE), 2),
            (int(Color.BLUE), 3),
            (int(Color.BLUE), 4),
        ]

    def test_action_count(self, converted):
        assert len(converted["actions"]) == 4

    def test_first_action_is_color_clue(self, converted):
        a = converted["actions"][0]
        assert a["type"] == int(ActionType.COLOR_CLUE)
        assert a["target"] == 1  # targeting Human (player 1 in output)
        assert a["value"] == int(Color.RED)  # red

    def test_second_action_is_rank_clue(self, converted):
        a = converted["actions"][1]
        assert a["type"] == int(ActionType.RANK_CLUE)
        assert a["target"] == 0  # targeting AI (player 0 in output)
        assert a["value"] == 1

    def test_third_action_is_play(self, converted):
        a = converted["actions"][2]
        assert a["type"] == int(ActionType.PLAY)
        # AI plays position 0 → deck index 0
        assert a["target"] == 0

    def test_fourth_action_is_play(self, converted):
        a = converted["actions"][3]
        assert a["type"] == int(ActionType.PLAY)
        # Human plays position 0 → deck index 5
        assert a["target"] == 5

    def test_score(self, converted):
        assert converted["score"] == 2

    def test_metadata(self, converted):
        assert converted["metadata"]["ai_type"] == "simple"
        assert converted["metadata"]["seed"] == 1
        assert converted["metadata"]["data_source"] == "hanabi_data"


class TestConversionValidation:
    def test_replay_matches_score(self, tmp_path):
        """Full round-trip: parse → convert → replay → verify score."""
        log_file = tmp_path / "gameaabbccdd11223344.log"
        log_file.write_text(MINIMAL_LOG)
        parsed = parse_log_file(log_file)
        game_json = convert_to_hanab_live_json(parsed, game_id=999)

        assert validate_conversion(game_json, expected_score=2)

    def test_replay_state_correct(self, tmp_path):
        """Check the replayed game state matches expectations."""
        log_file = tmp_path / "gameaabbccdd11223344.log"
        log_file.write_text(MINIMAL_LOG)
        parsed = parse_log_file(log_file)
        game_json = convert_to_hanab_live_json(parsed, game_id=999)

        state, results = replay_game(game_json)
        # Green 1 and Red 1 played successfully
        assert state.fireworks[int(Color.GREEN)] == 1
        assert state.fireworks[int(Color.RED)] == 1
        assert state.get_score() == 2
        assert state.life_tokens == 3  # no misplays

    def test_validate_wrong_score_returns_false(self, tmp_path):
        log_file = tmp_path / "gameaabbccdd11223344.log"
        log_file.write_text(MINIMAL_LOG)
        parsed = parse_log_file(log_file)
        game_json = convert_to_hanab_live_json(parsed, game_id=999)

        assert not validate_conversion(game_json, expected_score=25)


# ---------------------------------------------------------------------------
# Conversion with failed plays
# ---------------------------------------------------------------------------

FAIL_PLAY_LOG = textwrap.dedent("""\
    Treatment: ('test', 7)
    [(0, 2), (0, 3), (0, 4), (0, 5), (1, 1), (1, 2), (1, 3), (1, 4), (1, 5), (2, 1), (2, 2), (2, 3), (2, 4), (2, 5), (3, 2), (3, 3), (3, 4), (3, 5), (4, 2), (4, 3), (4, 4), (4, 5), (0, 1), (0, 1), (0, 2), (1, 1), (1, 1), (1, 2), (2, 1), (2, 1), (2, 2), (3, 1), (3, 1), (3, 2), (4, 1), (4, 1), (4, 2), (3, 3), (3, 4), (3, 5)]
    MOVE: 0 0 None 1 4 None
    test hints You about all their red cards hints remaining: 7
    You has red 1, blue 3, blue 2, blue 3, blue 4
    MOVE: 1 1 None 0 None 1
    You hints test about all their 1 hints remaining: 6
    test has green 1, red 3, red 4, red 5, yellow 1
    MOVE: 0 0 None 1 3 None
    test hints You about all their blue cards hints remaining: 5
    You has red 1, blue 3, blue 2, blue 3, blue 4
    MOVE: 1 2 1 1 None None
    You plays blue 3 and fails. Board was green 0, yellow 0, white 0, blue 0, red 0
    You now has red 1, blue 2, blue 3, blue 4, green 2
    Score 0
""")


class TestConversionWithFailedPlay:
    def test_failed_play_card_extracted(self, tmp_path):
        log_file = tmp_path / "game0000000000000004.log"
        log_file.write_text(FAIL_PLAY_LOG)
        parsed = parse_log_file(log_file)
        # Fourth move (index 3) is a failed play of blue 3
        assert parsed.moves[3].played_card == (3, 3)

    def test_failed_play_replay(self, tmp_path):
        log_file = tmp_path / "game0000000000000004.log"
        log_file.write_text(FAIL_PLAY_LOG)
        parsed = parse_log_file(log_file)
        game_json = convert_to_hanab_live_json(parsed, game_id=100)

        state, results = replay_game(game_json)
        # One misplay, so life_tokens = 2
        assert state.life_tokens == 2
        # Blue 3 was not playable → failed, score stays 0
        assert state.get_score() == 0


# ---------------------------------------------------------------------------
# Human-goes-first scenario
# ---------------------------------------------------------------------------

HUMAN_FIRST_LOG = textwrap.dedent("""\
    Treatment: ('outer', 55)
    [(0, 2), (0, 3), (0, 4), (0, 5), (1, 1), (1, 2), (1, 3), (1, 4), (1, 5), (2, 1), (2, 2), (2, 3), (2, 4), (2, 5), (3, 2), (3, 3), (3, 4), (3, 5), (4, 2), (4, 3), (4, 4), (4, 5), (0, 1), (0, 1), (0, 2), (1, 1), (1, 1), (1, 2), (2, 1), (2, 1), (2, 2), (3, 1), (3, 1), (3, 2), (4, 1), (4, 1), (4, 2), (3, 3), (3, 4), (3, 5)]
    MOVE: 1 1 None 0 None 1
    You hints outer about all their 1 hints remaining: 7
    outer has green 1, red 3, red 4, red 5, yellow 1
    MOVE: 0 0 None 1 4 None
    outer hints You about all their red cards hints remaining: 6
    You has red 1, blue 1, blue 2, blue 3, blue 4
    MOVE: 1 2 0 1 None None
    You plays red 1 successfully! Board is now green 0, yellow 0, white 0, blue 0, red 1
    You now has blue 1, blue 2, blue 3, blue 4, green 2
    Score 1
""")


class TestHumanFirstConversion:
    @pytest.fixture
    def converted(self, tmp_path):
        log_file = tmp_path / "game0000000000000005.log"
        log_file.write_text(HUMAN_FIRST_LOG)
        parsed = parse_log_file(log_file)
        return convert_to_hanab_live_json(parsed, game_id=555)

    def test_human_is_player_0(self, converted):
        """When human goes first, they become output player 0."""
        assert converted["players"][0] == "Human"
        assert converted["players"][1] == "outer"

    def test_deck_p0_is_human_hand(self, converted):
        """P0 hand in deck should be Human's initial hand."""
        deck = converted["deck"]
        p0_hand = [(d["suitIndex"], d["rank"]) for d in deck[:5]]
        # Human initial: red 1, blue 1, blue 2, blue 3, blue 4
        assert p0_hand == [
            (int(Color.RED), 1),
            (int(Color.BLUE), 1),
            (int(Color.BLUE), 2),
            (int(Color.BLUE), 3),
            (int(Color.BLUE), 4),
        ]

    def test_deck_p1_is_ai_hand(self, converted):
        """P1 hand in deck should be AI's initial hand."""
        deck = converted["deck"]
        p1_hand = [(d["suitIndex"], d["rank"]) for d in deck[5:10]]
        # AI initial: green 1, red 3, red 4, red 5, yellow 1
        assert p1_hand == [
            (int(Color.GREEN), 1),
            (int(Color.RED), 3),
            (int(Color.RED), 4),
            (int(Color.RED), 5),
            (int(Color.YELLOW), 1),
        ]

    def test_first_action_targets_ai(self, converted):
        """Human hints AI → output P0 hints P1."""
        a = converted["actions"][0]
        assert a["type"] == int(ActionType.RANK_CLUE)
        assert a["target"] == 1  # AI is output player 1

    def test_second_action_targets_human(self, converted):
        """AI hints Human → output P1 hints P0."""
        a = converted["actions"][1]
        assert a["type"] == int(ActionType.COLOR_CLUE)
        assert a["target"] == 0  # Human is output player 0

    def test_replay_score(self, converted):
        assert validate_conversion(converted, expected_score=1)


# ---------------------------------------------------------------------------
# games.csv parsing test
# ---------------------------------------------------------------------------

class TestGamesCsvParsing:
    def test_parse_csv(self, tmp_path):
        csv_content = textwrap.dedent("""\
            id, ai, deck, score, time, first
            bcbbc9bc2cd7369f, intentional, 3, 18, 1490488725.0, yes
            19dbddedf07994e2, full, 9813, 5, 1489965568.0, no
        """)
        csv_path = tmp_path / "HanabiData" / "games.csv"
        csv_path.parent.mkdir(parents=True)
        csv_path.write_text(csv_content)

        records = load_games_csv(tmp_path / "HanabiData")
        assert len(records) == 2

        assert records[0].participant_id == "bcbbc9bc2cd7369f"
        assert records[0].ai_type == "intentional"
        assert records[0].deck_seed == 3
        assert records[0].score == 18
        assert records[0].is_first_game is True

        assert records[1].participant_id == "19dbddedf07994e2"
        assert records[1].ai_type == "full"
        assert records[1].deck_seed == 9813
        assert records[1].score == 5
        assert records[1].is_first_game is False


# ---------------------------------------------------------------------------
# Integration: Play records extraction
# ---------------------------------------------------------------------------

class TestPlayRecordExtraction:
    def test_records_have_correct_tags(self, tmp_path):
        """Play records should be tagged with correct subject/partner types."""
        log_file = tmp_path / "gameaabbccdd11223344.log"
        log_file.write_text(MINIMAL_LOG)
        parsed = parse_log_file(log_file)
        game_json = convert_to_hanab_live_json(parsed, game_id=999)

        from src.replay import replay_and_extract
        records, state = replay_and_extract(
            game_json,
            data_source="hanabi_data",
            subject_type="mixed",
            partner_type="mixed",
        )

        # Re-tag records (mimicking process_hanabi_data_games logic)
        ai_type = parsed.ai_type
        for record in records:
            if record.player == "Human":
                record.subject_type = "human"
                record.partner_type = ai_type
            else:
                record.subject_type = ai_type
                record.partner_type = "human"

        # We expect 2 play actions: AI plays green 1, Human plays red 1
        assert len(records) == 2

        # AI's play
        ai_rec = [r for r in records if r.subject_type == "simple"][0]
        assert ai_rec.partner_type == "human"
        assert ai_rec.data_source == "hanabi_data"

        # Human's play
        h_rec = [r for r in records if r.subject_type == "human"][0]
        assert h_rec.partner_type == "simple"

    def test_posterior_values_valid(self, tmp_path):
        log_file = tmp_path / "gameaabbccdd11223344.log"
        log_file.write_text(MINIMAL_LOG)
        parsed = parse_log_file(log_file)
        game_json = convert_to_hanab_live_json(parsed, game_id=999)

        from src.replay import replay_and_extract
        records, _ = replay_and_extract(game_json, data_source="hanabi_data")

        for r in records:
            assert 0.0 <= r.posterior_p_life_loss <= 1.0
            assert r.num_candidates > 0


# ---------------------------------------------------------------------------
# Edge case: discard-only AI (no play before hand visible)
# ---------------------------------------------------------------------------

DISCARD_ONLY_LOG = textwrap.dedent("""\
    Treatment: ('careful', 10)
    [(0, 2), (0, 3), (0, 4), (0, 5), (1, 1), (1, 2), (1, 3), (1, 4), (1, 5), (2, 1), (2, 2), (2, 3), (2, 4), (2, 5), (3, 2), (3, 3), (3, 4), (3, 5), (4, 2), (4, 3), (4, 4), (4, 5), (0, 1), (0, 1), (0, 2), (1, 1), (1, 1), (1, 2), (2, 1), (2, 1), (2, 2), (3, 1), (3, 1), (3, 2), (4, 1), (4, 1), (4, 2), (3, 3), (3, 4), (3, 5)]
    MOVE: 0 3 0 None None None
    careful discards green 1
    trash is now green 1
    careful now has red 3, red 4, red 5, yellow 1, green 2
    MOVE: 1 1 None 0 None 1
    You hints careful about all their 1 hints remaining: 7
    careful has red 3, red 4, red 5, yellow 1, green 2
    MOVE: 0 0 None 1 4 None
    careful hints You about all their red cards hints remaining: 6
    You has red 1, blue 1, blue 2, blue 3, blue 4
    Score 0
""")


class TestDiscardBeforeHandVisible:
    def test_ai_hand_reconstructed_from_discard(self, tmp_path):
        """AI discards before any hint reveals their hand.
        AI discards green 1 (pos 0), draws green 2.
        Post-discard: red 3, red 4, red 5, yellow 1, green 2
        Initial: green 1, red 3, red 4, red 5, yellow 1
        """
        log_file = tmp_path / "game0000000000000006.log"
        log_file.write_text(DISCARD_ONLY_LOG)
        parsed = parse_log_file(log_file)
        ai_hand, human_hand = extract_initial_hands(parsed)

        # AI initial: green 1, red 3, red 4, red 5, yellow 1
        assert ai_hand == [(0, 1), (4, 3), (4, 4), (4, 5), (1, 1)]

        # Human initial: red 1, blue 1, blue 2, blue 3, blue 4
        assert human_hand == [(4, 1), (3, 1), (3, 2), (3, 3), (3, 4)]

    def test_conversion_validates(self, tmp_path):
        log_file = tmp_path / "game0000000000000006.log"
        log_file.write_text(DISCARD_ONLY_LOG)
        parsed = parse_log_file(log_file)
        game_json = convert_to_hanab_live_json(parsed, game_id=600)
        assert validate_conversion(game_json, expected_score=0)
