"""Rule-based Hanabi agents, re-implemented from HOAD/Walton-Rivers et al. (2017).

Each agent is a callable: agent(state, player_id) -> Action.
Agents only use information available to the player (card_knowledge, other
players' hands, fireworks, discard pile) — never their own hand's true identity.

Naming convention: class names (InternalAgent, FlawedAgent) follow the HOAD/
Walton-Rivers codebase. In the manuscript and figure labels, we use the
HanabiData names: "Intentional" (for InternalAgent) and "Full" (for
FlawedAgent). See AGENT_DISPLAY_NAMES in analysis.py for the mapping.
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod

from src.game_engine import (
    Action,
    ActionType,
    CARD_DISTRIBUTION,
    Color,
    HanabiState,
)


# ------------------------------------------------------------------
# Shared utility functions
# ------------------------------------------------------------------

def playability_probability(state: HanabiState, player: int, slot: int) -> float:
    """Fraction of weighted candidate identities that are currently playable."""
    candidates = state.get_candidate_identities(player, slot)
    if not candidates:
        return 0.0
    total = sum(w for _, w in candidates)
    playable = sum(w for (c, r), w in candidates if state.is_playable(c, r))
    return playable / total if total > 0 else 0.0


def is_certainly_playable(state: HanabiState, player: int, slot: int) -> bool:
    """True if ALL candidate identities for this card are playable."""
    candidates = state.get_candidate_identities(player, slot)
    if not candidates:
        return False
    return all(state.is_playable(c, r) for (c, r), _ in candidates)


def highest_score_possible(state: HanabiState, color: int) -> int:
    """Max achievable firework level for a color (limited by discarded cards)."""
    for rank in range(1, 6):
        total = CARD_DISTRIBUTION[rank]
        discarded = sum(1 for c, r in state.discard_pile if c == color and r == rank)
        if discarded >= total:
            return rank - 1
    return 5


def is_card_useless(state: HanabiState, color: int, rank: int) -> bool:
    """Check if a specific card identity is useless (can never be played)."""
    if rank <= state.fireworks[color]:
        return True  # Already played
    if rank > highest_score_possible(state, color):
        return True  # Prerequisite discarded
    return False


def uselessness_probability(state: HanabiState, player: int, slot: int) -> float:
    """Fraction of weighted candidates that are useless."""
    candidates = state.get_candidate_identities(player, slot)
    if not candidates:
        return 1.0
    total = sum(w for _, w in candidates)
    useless = sum(w for (c, r), w in candidates if is_card_useless(state, c, r))
    return useless / total if total > 0 else 1.0


def find_safe_discard(state: HanabiState, player: int) -> int | None:
    """Find a slot the player KNOWS is safe to discard (all candidates useless)."""
    for slot in range(len(state.hands[player])):
        if uselessness_probability(state, player, slot) >= 1.0 - 1e-9:
            return slot
    return None


def next_player(player: int, num_players: int) -> int:
    return (player + 1) % num_players


# ------------------------------------------------------------------
# Base class
# ------------------------------------------------------------------

class Agent(ABC):
    name: str = "base"

    @abstractmethod
    def act(self, state: HanabiState, player: int) -> Action:
        ...

    def __repr__(self):
        return f"{self.__class__.__name__}()"


# ------------------------------------------------------------------
# SimpleAgent
# ------------------------------------------------------------------

class SimpleAgent(Agent):
    """Play known-playable (lowest rank), hint about playable cards, discard oldest."""
    name = "simple"

    def act(self, state: HanabiState, player: int) -> Action:
        hand = state.hands[player]

        # 1. Play lowest-rank certainly-playable card
        playable_slots = [
            (slot, state.card_knowledge[player][slot].possible_ranks)
            for slot in range(len(hand))
            if is_certainly_playable(state, player, slot)
        ]
        if playable_slots:
            # Pick slot whose min possible rank is lowest
            best = min(playable_slots, key=lambda x: min(x[1]))
            return Action(ActionType.PLAY, target=best[0])

        # 2. Give helpful hint (about playable cards, no false positives)
        if state.info_tokens > 0:
            hint = self._find_helpful_hint(state, player)
            if hint:
                return hint

        # 3. Discard oldest
        if state.info_tokens < state.max_info_tokens:
            return Action(ActionType.DISCARD, target=0)

        # Forced: give any hint
        return self._give_any_hint(state, player)

    def _find_helpful_hint(self, state, player):
        best_hint = None
        best_count = 0
        for other in range(state.num_players):
            if other == player:
                continue
            for color in Color:
                newly_playable = self._count_newly_playable(state, other, "color", color)
                if newly_playable > best_count:
                    best_count = newly_playable
                    best_hint = Action(ActionType.COLOR_CLUE, target=other, value=int(color))
            for rank in range(1, 6):
                newly_playable = self._count_newly_playable(state, other, "rank", rank)
                if newly_playable > best_count:
                    best_count = newly_playable
                    best_hint = Action(ActionType.RANK_CLUE, target=other, value=rank)
        return best_hint

    def _count_newly_playable(self, state, target_player, hint_type, hint_value):
        """Count cards that would become certainly-playable after this hint."""
        count = 0
        for slot, card in enumerate(state.hands[target_player]):
            k = state.card_knowledge[target_player][slot]
            # Simulate hint
            new_colors = set(k.possible_colors)
            new_ranks = set(k.possible_ranks)
            if hint_type == "color":
                if card[0] == hint_value:
                    new_colors = {hint_value}
                else:
                    new_colors.discard(hint_value)
            else:
                if card[1] == hint_value:
                    new_ranks = {hint_value}
                else:
                    new_ranks.discard(hint_value)
            # Check if all candidates would be playable
            all_playable = True
            any_candidate = False
            for c in new_colors:
                for r in new_ranks:
                    remaining = CARD_DISTRIBUTION[r] - sum(
                        1 for vc, vr in state.discard_pile if vc == c and vr == r
                    )
                    if remaining > 0:
                        any_candidate = True
                        if not state.is_playable(c, r):
                            all_playable = False
                            break
                if not all_playable:
                    break
            if any_candidate and all_playable and not is_certainly_playable(state, target_player, slot):
                count += 1
        return count

    def _give_any_hint(self, state, player):
        other = next_player(player, state.num_players)
        card = state.hands[other][0]
        return Action(ActionType.COLOR_CLUE, target=other, value=card[0])


# ------------------------------------------------------------------
# IGGIAgent
# ------------------------------------------------------------------

class IGGIAgent(Agent):
    """Conservative: PlayIfCertain -> PlaySafe -> HintUseful -> OsawaDiscard -> DiscardOldest."""
    name = "iggi"

    def act(self, state: HanabiState, player: int) -> Action:
        hand = state.hands[player]

        # 1. PlayIfCertain: both color and rank fully known and playable
        for slot in range(len(hand)):
            k = state.card_knowledge[player][slot]
            if len(k.possible_colors) == 1 and len(k.possible_ranks) == 1:
                c = next(iter(k.possible_colors))
                r = next(iter(k.possible_ranks))
                if state.is_playable(c, r):
                    return Action(ActionType.PLAY, target=slot)

        # 2. PlaySafeCard
        for slot in range(len(hand)):
            if is_certainly_playable(state, player, slot):
                return Action(ActionType.PLAY, target=slot)

        # 3. TellAnyoneAboutUsefulCard (value-first)
        if state.info_tokens > 0:
            hint = self._tell_useful(state, player)
            if hint:
                return hint

        # 4. OsawaDiscard
        safe = find_safe_discard(state, player)
        if safe is not None and state.info_tokens < state.max_info_tokens:
            return Action(ActionType.DISCARD, target=safe)

        # 5. DiscardOldestFirst
        if state.info_tokens < state.max_info_tokens:
            return Action(ActionType.DISCARD, target=0)

        # 6. TellRandomly (fallback when at max info tokens)
        return self._tell_random(state, player)

    def _tell_useful(self, state, player):
        """Hint about an immediately playable card, preferring value hints."""
        for offset in range(1, state.num_players):
            other = (player + offset) % state.num_players
            for slot, card in enumerate(state.hands[other]):
                c, r = card
                if state.is_playable(c, r):
                    k = state.card_knowledge[other][slot]
                    # Prefer value if unknown
                    if len(k.possible_ranks) > 1:
                        return Action(ActionType.RANK_CLUE, target=other, value=r)
                    if len(k.possible_colors) > 1:
                        return Action(ActionType.COLOR_CLUE, target=other, value=c)
                    # Both known — skip
        return None

    def _tell_random(self, state, player):
        other = next_player(player, state.num_players)
        card = random.choice(state.hands[other])
        if random.random() < 0.5:
            return Action(ActionType.COLOR_CLUE, target=other, value=card[0])
        else:
            return Action(ActionType.RANK_CLUE, target=other, value=card[1])


# ------------------------------------------------------------------
# InternalAgent (Osawa)
# ------------------------------------------------------------------

class InternalAgent(Agent):
    """Osawa's internal-state agent: PlaySafe -> OsawaDiscard -> TellPlayable -> TellRandom -> DiscardRandom."""
    name = "internal"

    def act(self, state: HanabiState, player: int) -> Action:
        hand = state.hands[player]

        # 1. PlaySafeCard
        for slot in range(len(hand)):
            if is_certainly_playable(state, player, slot):
                return Action(ActionType.PLAY, target=slot)

        # 2. OsawaDiscard
        safe = find_safe_discard(state, player)
        if safe is not None and state.info_tokens < state.max_info_tokens:
            return Action(ActionType.DISCARD, target=safe)

        # 3. TellPlayableCard (may give redundant hints)
        if state.info_tokens > 0:
            other = next_player(player, state.num_players)
            for slot, card in enumerate(state.hands[other]):
                if state.is_playable(card[0], card[1]):
                    if random.random() < 0.5:
                        return Action(ActionType.COLOR_CLUE, target=other, value=card[0])
                    else:
                        return Action(ActionType.RANK_CLUE, target=other, value=card[1])

        # 4. TellRandomly
        if state.info_tokens > 0:
            other = next_player(player, state.num_players)
            card = random.choice(state.hands[other])
            if random.random() < 0.5:
                return Action(ActionType.COLOR_CLUE, target=other, value=card[0])
            else:
                return Action(ActionType.RANK_CLUE, target=other, value=card[1])

        # 5. DiscardRandomly
        return Action(ActionType.DISCARD, target=random.randrange(len(hand)))


# ------------------------------------------------------------------
# OuterAgent (Osawa)
# ------------------------------------------------------------------

class OuterAgent(Agent):
    """Osawa's outer-state agent: tracks others' knowledge, avoids redundant hints."""
    name = "outer"

    def act(self, state: HanabiState, player: int) -> Action:
        hand = state.hands[player]

        # 1. PlaySafeCard
        for slot in range(len(hand)):
            if is_certainly_playable(state, player, slot):
                return Action(ActionType.PLAY, target=slot)

        # 2. OsawaDiscard
        safe = find_safe_discard(state, player)
        if safe is not None and state.info_tokens < state.max_info_tokens:
            return Action(ActionType.DISCARD, target=safe)

        # 3. TellPlayableCardOuter (no redundant hints, value-first)
        if state.info_tokens > 0:
            other = next_player(player, state.num_players)
            for slot, card in enumerate(state.hands[other]):
                if state.is_playable(card[0], card[1]):
                    k = state.card_knowledge[other][slot]
                    if len(k.possible_ranks) > 1:
                        return Action(ActionType.RANK_CLUE, target=other, value=card[1])
                    if len(k.possible_colors) > 1:
                        return Action(ActionType.COLOR_CLUE, target=other, value=card[0])

        # 4. TellUnknown (color-first)
        if state.info_tokens > 0:
            other = next_player(player, state.num_players)
            for slot, card in enumerate(state.hands[other]):
                k = state.card_knowledge[other][slot]
                if len(k.possible_colors) > 1:
                    return Action(ActionType.COLOR_CLUE, target=other, value=card[0])
                if len(k.possible_ranks) > 1:
                    return Action(ActionType.RANK_CLUE, target=other, value=card[1])

        # 5. DiscardRandomly
        return Action(ActionType.DISCARD, target=random.randrange(len(hand)))


# ------------------------------------------------------------------
# PiersAgent
# ------------------------------------------------------------------

class PiersAgent(Agent):
    """Adaptive: safe -> 60% probable -> hail-mary endgame plays."""
    name = "piers"

    def act(self, state: HanabiState, player: int) -> Action:
        hand = state.hands[player]

        # 1. Hail-mary endgame: if lives > 1 and deck empty, play anything
        if state.life_tokens > 1 and state.deck_size == 0:
            best_slot, best_prob = self._best_play(state, player, threshold=0.0)
            if best_slot is not None:
                return Action(ActionType.PLAY, target=best_slot)

        # 2. PlaySafeCard
        for slot in range(len(hand)):
            if is_certainly_playable(state, player, slot):
                return Action(ActionType.PLAY, target=slot)

        # 3. PlayProbablySafe (60%) if lives > 1
        if state.life_tokens > 1:
            best_slot, best_prob = self._best_play(state, player, threshold=0.6)
            if best_slot is not None:
                return Action(ActionType.PLAY, target=best_slot)

        # 4. TellAnyoneAboutUsefulCard
        if state.info_tokens > 0:
            hint = IGGIAgent._tell_useful(self, state, player)
            if hint:
                return hint

        # 5. TellDispensable when tokens < 4
        if state.info_tokens > 0 and state.info_tokens < 4:
            hint = self._tell_dispensable(state, player)
            if hint:
                return hint

        # 6. OsawaDiscard
        safe = find_safe_discard(state, player)
        if safe is not None and state.info_tokens < state.max_info_tokens:
            return Action(ActionType.DISCARD, target=safe)

        # 7. DiscardOldestFirst
        if state.info_tokens < state.max_info_tokens:
            return Action(ActionType.DISCARD, target=0)

        # 8. TellRandomly
        if state.info_tokens > 0:
            return IGGIAgent._tell_random(self, state, player)

        # 9. DiscardRandomly
        return Action(ActionType.DISCARD, target=random.randrange(len(hand)))

    def _best_play(self, state, player, threshold):
        best_slot = None
        best_prob = threshold
        for slot in range(len(state.hands[player])):
            p = playability_probability(state, player, slot)
            if p >= best_prob:
                best_prob = p
                best_slot = slot
        return best_slot, best_prob

    def _tell_dispensable(self, state, player):
        """Tell a partner about a card they can safely discard."""
        for offset in range(1, state.num_players):
            other = (player + offset) % state.num_players
            for slot, card in enumerate(state.hands[other]):
                if is_card_useless(state, card[0], card[1]):
                    k = state.card_knowledge[other][slot]
                    if len(k.possible_ranks) > 1:
                        return Action(ActionType.RANK_CLUE, target=other, value=card[1])
                    if len(k.possible_colors) > 1:
                        return Action(ActionType.COLOR_CLUE, target=other, value=card[0])
        return None


# ------------------------------------------------------------------
# VanDenBerghAgent
# ------------------------------------------------------------------

class VanDenBerghAgent(Agent):
    """GA-evolved agent: probability-based play/discard, max-information hints."""
    name = "bergh"

    def __init__(self, play_threshold=0.6):
        self.play_threshold = play_threshold

    def act(self, state: HanabiState, player: int) -> Action:
        hand = state.hands[player]

        # 1. Play: probability >= threshold (or safe-only if lives == 1)
        if state.life_tokens > 1:
            best_slot, _ = self._best_play(state, player, self.play_threshold)
            if best_slot is not None:
                return Action(ActionType.PLAY, target=best_slot)
        else:
            for slot in range(len(hand)):
                if is_certainly_playable(state, player, slot):
                    return Action(ActionType.PLAY, target=slot)

        # 2. DiscardCertainlyUseless (threshold 1.0)
        safe = find_safe_discard(state, player)
        if safe is not None and state.info_tokens < state.max_info_tokens:
            return Action(ActionType.DISCARD, target=safe)

        # 3. TellAnyoneAboutUsefulCard
        if state.info_tokens > 0:
            hint = IGGIAgent._tell_useful(self, state, player)
            if hint:
                return hint

        # 4. TellMostInformation (new=true)
        if state.info_tokens > 0:
            hint = self._tell_most_info(state, player)
            if hint:
                return hint

        # 5. DiscardMostProbablyUseless (threshold 0.0)
        if state.info_tokens < state.max_info_tokens:
            best_slot = None
            best_useless = -1.0
            for slot in range(len(hand)):
                u = uselessness_probability(state, player, slot)
                if u > best_useless:
                    best_useless = u
                    best_slot = slot
            if best_slot is not None:
                return Action(ActionType.DISCARD, target=best_slot)

        # Fallback
        return Action(ActionType.DISCARD, target=0)

    def _best_play(self, state, player, threshold):
        best_slot = None
        best_prob = threshold
        for slot in range(len(state.hands[player])):
            p = playability_probability(state, player, slot)
            if p >= best_prob:
                best_prob = p
                best_slot = slot
        return best_slot, best_prob

    def _tell_most_info(self, state, player):
        """Give the hint that conveys the most NEW information."""
        best_hint = None
        best_new_info = 0
        for other in range(state.num_players):
            if other == player:
                continue
            for color in Color:
                new_info = sum(
                    1 for slot in range(len(state.hands[other]))
                    if len(state.card_knowledge[other][slot].possible_colors) > 1
                    and (state.hands[other][slot][0] == color
                         or color in state.card_knowledge[other][slot].possible_colors)
                )
                if new_info > best_new_info:
                    best_new_info = new_info
                    best_hint = Action(ActionType.COLOR_CLUE, target=other, value=int(color))
            for rank in range(1, 6):
                new_info = sum(
                    1 for slot in range(len(state.hands[other]))
                    if len(state.card_knowledge[other][slot].possible_ranks) > 1
                    and (state.hands[other][slot][1] == rank
                         or rank in state.card_knowledge[other][slot].possible_ranks)
                )
                if new_info > best_new_info:
                    best_new_info = new_info
                    best_hint = Action(ActionType.RANK_CLUE, target=other, value=rank)
        return best_hint


# ------------------------------------------------------------------
# FlawedAgent
# ------------------------------------------------------------------

class FlawedAgent(Agent):
    """Deliberately imperfect: low play threshold, random hints."""
    name = "flawed"

    def act(self, state: HanabiState, player: int) -> Action:
        hand = state.hands[player]

        # 1. PlaySafeCard
        for slot in range(len(hand)):
            if is_certainly_playable(state, player, slot):
                return Action(ActionType.PLAY, target=slot)

        # 2. PlayProbablySafe (25%)
        best_slot = None
        best_prob = 0.25
        for slot in range(len(hand)):
            p = playability_probability(state, player, slot)
            if p >= best_prob:
                best_prob = p
                best_slot = slot
        if best_slot is not None:
            return Action(ActionType.PLAY, target=best_slot)

        # 3. TellRandomly
        if state.info_tokens > 0:
            other = next_player(player, state.num_players)
            card = random.choice(state.hands[other])
            if random.random() < 0.5:
                return Action(ActionType.COLOR_CLUE, target=other, value=card[0])
            else:
                return Action(ActionType.RANK_CLUE, target=other, value=card[1])

        # 4. OsawaDiscard
        safe = find_safe_discard(state, player)
        if safe is not None and state.info_tokens < state.max_info_tokens:
            return Action(ActionType.DISCARD, target=safe)

        # 5. DiscardOldestFirst
        if state.info_tokens < state.max_info_tokens:
            return Action(ActionType.DISCARD, target=0)

        # Fallback
        return Action(ActionType.DISCARD, target=random.randrange(len(hand)))


# ------------------------------------------------------------------
# Agent registry
# ------------------------------------------------------------------

AGENTS = {
    "simple": SimpleAgent,
    "iggi": IGGIAgent,
    "internal": InternalAgent,
    "outer": OuterAgent,
    "piers": PiersAgent,
    "bergh": VanDenBerghAgent,
    "flawed": FlawedAgent,
}


def get_agent(name: str) -> Agent:
    cls = AGENTS.get(name.lower())
    if cls is None:
        raise ValueError(f"Unknown agent: {name}. Available: {list(AGENTS.keys())}")
    return cls()
