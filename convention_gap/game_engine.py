"""Pure Python Hanabi game state tracker.

Replays games from hanab.live JSON format, tracking full state including
per-card knowledge from hints. Designed for posterior analysis, not for
playing — we have perfect information about the deck order.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional


# Standard Hanabi color mapping (matches hanab.live suitIndex)
class Color(IntEnum):
    RED = 0
    YELLOW = 1
    GREEN = 2
    BLUE = 3
    PURPLE = 4


COLOR_NAMES = {
    Color.RED: "Red",
    Color.YELLOW: "Yellow",
    Color.GREEN: "Green",
    Color.BLUE: "Blue",
    Color.PURPLE: "Purple",
}

ALL_COLORS = frozenset(Color)
ALL_RANKS = frozenset(range(1, 6))

# Number of copies per rank in a standard Hanabi deck
CARD_DISTRIBUTION = {1: 3, 2: 2, 3: 2, 4: 2, 5: 1}


# Action types from hanab.live JSON
class ActionType(IntEnum):
    PLAY = 0
    DISCARD = 1
    COLOR_CLUE = 2
    RANK_CLUE = 3
    GAME_OVER = 4  # End-of-game marker (not a real gameplay action)


@dataclass
class Action:
    action_type: ActionType
    target: int
    value: int = 0


Card = tuple[int, int]  # (color: int, rank: int)


@dataclass
class CardKnowledge:
    """What a player knows about one card in their hand from hints."""

    possible_colors: set[int] = field(default_factory=lambda: set(ALL_COLORS))
    possible_ranks: set[int] = field(default_factory=lambda: set(ALL_RANKS))
    color_hinted: bool = False
    rank_hinted: bool = False
    hint_action_count: int = 0  # incremented on each hint action that MATCHES this card

    def apply_color_hint(self, color: int, positive: bool) -> None:
        if positive:
            self.possible_colors = {color}
            self.color_hinted = True
            self.hint_action_count += 1
        else:
            self.possible_colors.discard(color)

    def apply_rank_hint(self, rank: int, positive: bool) -> None:
        if positive:
            self.possible_ranks = {rank}
            self.rank_hinted = True
            self.hint_action_count += 1
        else:
            self.possible_ranks.discard(rank)

    @property
    def hint_count(self) -> int:
        """Count of hint actions that touched this card (matches Appendix A8)."""
        return self.hint_action_count

    @property
    def hint_types(self) -> int:
        """Number of hint types (color and/or rank) that have touched this card (0-2)."""
        return int(self.color_hinted) + int(self.rank_hinted)


class HanabiState:
    """Tracks the full state of a Hanabi game.

    Designed for replaying games from hanab.live JSON data. The deck order
    is known (from the JSON), but we track what each player *could* know
    from hints for posterior computation.
    """

    def __init__(self, num_players: int, deck: list[Card]):
        if num_players < 2 or num_players > 5:
            raise ValueError(f"num_players must be 2-5, got {num_players}")

        self.num_players = num_players
        self.hand_size = 5 if num_players <= 3 else 4
        self.num_colors = 5
        self.num_ranks = 5
        self.max_life_tokens = 3
        self.max_info_tokens = 8

        # The deck is a list of (color, rank) tuples, dealt from index 0
        self.deck: list[Card] = list(deck)
        self.deck_index: int = 0  # Next card to draw

        self.hands: list[list[Card]] = [[] for _ in range(num_players)]
        self.hand_deck_indices: list[list[int]] = [
            [] for _ in range(num_players)
        ]  # Tracks which deck index each card in hand came from
        self.card_knowledge: list[list[CardKnowledge]] = [
            [] for _ in range(num_players)
        ]

        self.fireworks: dict[int, int] = {c: 0 for c in Color}
        self.discard_pile: list[Card] = []
        self.life_tokens: int = self.max_life_tokens
        self.info_tokens: int = self.max_info_tokens
        self.current_player: int = 0
        self.turn: int = 0
        self.score: int = 0

        # End-game tracking: once deck empties, each player gets one more turn
        self.final_turns_remaining: Optional[int] = None
        self.game_over: bool = False

    def deal_initial_hands(self) -> None:
        """Deal cards from the deck to all players.

        hanab.live deals sequentially: all cards to player 0, then all to
        player 1, etc. (not round-robin).
        """
        for player in range(self.num_players):
            for _ in range(self.hand_size):
                self._draw_card(player)

    def _draw_card(self, player: int) -> Optional[Card]:
        """Draw the next card from the deck into a player's hand."""
        if self.deck_index >= len(self.deck):
            return None
        card = self.deck[self.deck_index]
        self.hand_deck_indices[player].append(self.deck_index)
        self.deck_index += 1
        self.hands[player].append(card)
        self.card_knowledge[player].append(CardKnowledge())
        return card

    @property
    def deck_size(self) -> int:
        return len(self.deck) - self.deck_index

    def is_playable(self, color: int, rank: int) -> bool:
        """Check if a card can be legally played on the fireworks."""
        return self.fireworks[color] == rank - 1

    def find_hand_index_by_deck_index(
        self, player: int, deck_idx: int
    ) -> int:
        """Find the hand position of a card given its original deck index."""
        return self.hand_deck_indices[player].index(deck_idx)

    def apply_action(self, action: Action) -> dict:
        """Apply an action and advance the game state.

        Returns a dict with information about what happened:
        - For play: {'played': card, 'success': bool}
        - For discard: {'discarded': card}
        - For hints: {'hint_type': 'color'|'rank', 'target': player, 'value': int,
                       'touched_slots': list[int]}
        """
        if self.game_over:
            raise RuntimeError("Game is already over")

        # Snapshot whether end-game countdown was already active before this action
        countdown_active_before = self.final_turns_remaining is not None

        result = {}

        if action.action_type == ActionType.PLAY:
            result = self._apply_play(action.target)
        elif action.action_type == ActionType.DISCARD:
            result = self._apply_discard(action.target)
        elif action.action_type == ActionType.COLOR_CLUE:
            result = self._apply_color_clue(action.target, action.value)
        elif action.action_type == ActionType.RANK_CLUE:
            result = self._apply_rank_clue(action.target, action.value)
        else:
            raise ValueError(f"Unknown action type: {action.action_type}")

        # Advance turn
        self.turn += 1
        self.current_player = (self.current_player + 1) % self.num_players

        # Decrement end-game countdown (only if it was active before this action —
        # the turn that empties the deck doesn't count against the countdown)
        if countdown_active_before and self.final_turns_remaining is not None:
            self.final_turns_remaining -= 1
            if self.final_turns_remaining <= 0:
                self.game_over = True

        return result

    def _draw_and_check_endgame(self) -> None:
        """Draw a replacement card if possible; start end-game countdown
        when the deck becomes empty."""
        if self.deck_size > 0:
            self._draw_card(self.current_player)
        if self.deck_size == 0 and self.final_turns_remaining is None:
            self.final_turns_remaining = self.num_players

    def _apply_play(self, card_index: int) -> dict:
        card = self.hands[self.current_player][card_index]
        color, rank = card

        # Remove card and its knowledge
        self.hands[self.current_player].pop(card_index)
        self.hand_deck_indices[self.current_player].pop(card_index)
        self.card_knowledge[self.current_player].pop(card_index)

        if self.is_playable(color, rank):
            self.fireworks[color] = rank
            self.score += 1
            # Playing a 5 gives back an info token
            if rank == 5 and self.info_tokens < self.max_info_tokens:
                self.info_tokens += 1
            success = True
        else:
            # Misplay — card goes to discard, lose a life
            self.discard_pile.append(card)
            self.life_tokens -= 1
            if self.life_tokens <= 0:
                self.game_over = True
                self.score = 0
            success = False

        # Draw replacement
        self._draw_and_check_endgame()

        return {"played": card, "success": success}

    def _apply_discard(self, card_index: int) -> dict:
        card = self.hands[self.current_player][card_index]

        # Remove card and its knowledge
        self.hands[self.current_player].pop(card_index)
        self.hand_deck_indices[self.current_player].pop(card_index)
        self.card_knowledge[self.current_player].pop(card_index)

        self.discard_pile.append(card)

        # Regain an info token
        if self.info_tokens < self.max_info_tokens:
            self.info_tokens += 1

        # Draw replacement
        self._draw_and_check_endgame()

        return {"discarded": card}

    def _apply_color_clue(self, target_player: int, color: int) -> dict:
        if self.info_tokens <= 0:
            raise RuntimeError("No info tokens available for hint")

        self.info_tokens -= 1
        touched_slots = []

        for i, card in enumerate(self.hands[target_player]):
            card_color, _ = card
            positive = card_color == color
            self.card_knowledge[target_player][i].apply_color_hint(color, positive)
            if positive:
                touched_slots.append(i)

        return {
            "hint_type": "color",
            "target": target_player,
            "value": color,
            "touched_slots": touched_slots,
        }

    def _apply_rank_clue(self, target_player: int, rank: int) -> dict:
        if self.info_tokens <= 0:
            raise RuntimeError("No info tokens available for hint")

        self.info_tokens -= 1
        touched_slots = []

        for i, card in enumerate(self.hands[target_player]):
            _, card_rank = card
            positive = card_rank == rank
            self.card_knowledge[target_player][i].apply_rank_hint(rank, positive)
            if positive:
                touched_slots.append(i)

        return {
            "hint_type": "rank",
            "target": target_player,
            "value": rank,
            "touched_slots": touched_slots,
        }

    def get_candidate_identities(
        self, player_id: int, card_index: int
    ) -> list[tuple[Card, int]]:
        """Get possible card identities and their weights for a card.

        Returns a list of ((color, rank), remaining_count) tuples.
        Only includes identities with remaining_count > 0.
        """
        knowledge = self.card_knowledge[player_id][card_index]

        # Count all cards visible to this player
        visible = self._count_visible_cards(player_id)

        candidates = []
        for color in knowledge.possible_colors:
            for rank in knowledge.possible_ranks:
                total = CARD_DISTRIBUTION[rank]
                seen = visible.get((color, rank), 0)
                remaining = total - seen
                if remaining > 0:
                    candidates.append(((color, rank), remaining))

        return candidates

    def _count_visible_cards(self, player_id: int) -> dict[Card, int]:
        """Count all cards visible to a given player.

        Visible = other players' hands + discard pile + fireworks.
        """
        counts: dict[Card, int] = {}

        # Other players' hands
        for p in range(self.num_players):
            if p != player_id:
                for card in self.hands[p]:
                    counts[card] = counts.get(card, 0) + 1

        # Discard pile
        for card in self.discard_pile:
            counts[card] = counts.get(card, 0) + 1

        # Fireworks (played cards)
        for color in Color:
            for rank in range(1, self.fireworks[color] + 1):
                card = (color, rank)
                counts[card] = counts.get(card, 0) + 1

        return counts

    def get_score(self) -> int:
        """Return the sum of fireworks (pre-Appendix-A rule).

        Kept for backward compatibility with hanabi_data_client.validate_conversion,
        which compares against the raw fireworks-sum recorded in HanabiData logs.
        For the canonical, Appendix-A-compliant end-of-game score, use
        get_final_score() instead.
        """
        return sum(self.fireworks.values())

    def get_final_score(self) -> int:
        """Canonical end-of-game score per Appendix A.

        Three life losses end the game with score 0; otherwise sum of fireworks.
        """
        if self.life_tokens <= 0:
            return 0
        return sum(self.fireworks.values())

    def get_game_end_reason(self, hit_terminate_marker: bool = False) -> str:
        """Classify how the game ended, based on the current (final) state.

        Should be called after all recorded actions have been replayed.

        - ``strikeout``: three life losses (score 0 per Appendix A).
        - ``perfect``: all fireworks completed (score 25).
        - ``natural``: the deck was exhausted (``game_over`` set by the
          end-game countdown, or simply ``deck_size == 0``), with a
          non-perfect, non-strikeout score. hanab.live ends the final round
          as soon as no further points are possible, so a completed
          natural game's log can stop with one or two final turns unrecorded;
          reaching an empty deck is therefore sufficient to call it natural.
        - ``truncated``: the game did NOT complete. Either the action log
          carried an explicit hanab.live end-of-game marker signalling an
          abnormal end (``hit_terminate_marker`` — timeout / terminated /
          idle-timeout; verified to carry recorded score 0), or the log
          simply ran out with cards still in the deck and no terminal state
          reached. These are NOT completed games.

        Validation: on HOAD agent-vs-agent games (played to completion by this
        same engine) this returns 0 truncated; on hanab.live it separates
        completed games (whose recorded scores match the replayed score) from
        terminated games (recorded score 0).
        """
        if hit_terminate_marker:
            # An explicit abnormal-end marker (hanab.live end conditions
            # 3=timeout, 4=terminated, 6=idle-timeout) always means the game
            # did not complete, regardless of board state.
            return "truncated"
        if self.life_tokens <= 0:
            return "strikeout"
        if sum(self.fireworks.values()) == 25:
            return "perfect"
        if self.game_over or self.deck_size == 0:
            return "natural"
        return "truncated"

    def __repr__(self) -> str:
        fw = {COLOR_NAMES[c]: r for c, r in self.fireworks.items() if r > 0}
        return (
            f"HanabiState(turn={self.turn}, score={self.score}, "
            f"lives={self.life_tokens}, info={self.info_tokens}, "
            f"deck={self.deck_size}, fireworks={fw})"
        )


def state_from_hanab_live(game_json: dict) -> HanabiState:
    """Create a HanabiState from a hanab.live game export JSON.

    Expects the format:
    {
        "players": [...],
        "deck": [{"suitIndex": int, "rank": int}, ...],
        "actions": [{"type": int, "target": int, "value": int}, ...],
        "options": {"variant": str, "numPlayers": int}
    }
    """
    num_players = len(game_json["players"])
    deck = [(card["suitIndex"], card["rank"]) for card in game_json["deck"]]
    return HanabiState(num_players=num_players, deck=deck)


def actions_from_hanab_live(game_json: dict) -> list[Action]:
    """Parse actions from a hanab.live game export JSON."""
    actions = []
    for a in game_json["actions"]:
        action = Action(
            action_type=ActionType(a["type"]),
            target=a["target"],
            value=a.get("value", 0),
        )
        actions.append(action)
    return actions


def replay_game(game_json: dict) -> tuple[HanabiState, list[dict]]:
    """Fully replay a hanab.live game, returning the final state and action results.

    hanab.live encodes play/discard targets as **deck indices** (0-49),
    not hand positions. This function translates them to hand positions
    before applying each action.

    Returns:
        (final_state, action_results) where action_results[i] is the dict
        returned by apply_action for the i-th action.
    """
    state = state_from_hanab_live(game_json)
    state.deal_initial_hands()
    actions = actions_from_hanab_live(game_json)

    results = []
    for action in actions:
        if state.game_over:
            break
        if action.action_type == ActionType.GAME_OVER:
            break

        # Translate deck index → hand position for play/discard
        if action.action_type in (ActionType.PLAY, ActionType.DISCARD):
            deck_idx = action.target
            hand_pos = state.find_hand_index_by_deck_index(
                state.current_player, deck_idx
            )
            action = Action(action.action_type, target=hand_pos, value=action.value)

        result = state.apply_action(action)
        results.append(result)

    return state, results
