"""Exact full-hand joint-inference posterior — the package's primary metric.

Computes P(life lost | play) with joint inference over ALL cards in the
acting player's hand: enumerate joint assignments of hand cards consistent
with every card's hint constraints, weight each assignment by the number of
ways to draw it from the hidden pool WITHOUT replacement, and marginalize
to the played card.

Math
----
Hidden pool: for each type t (color, rank), c_t = total copies - copies
visible to the acting player (other hands + discard + fireworks). The
acting player's own hand cards are part of the hidden pool.

For a hand of n cards with per-card allowed sets S_1..S_n (from hint
knowledge, intersected with {t : c_t > 0}), the probability of the joint
type assignment (t_1..t_n) under a uniform random arrangement of the
hidden pool is proportional to  prod_t (c_t)_(k_t)  (falling factorial),
where k_t = multiplicity of t in the assignment.

Marginal of the played card j:
    P(t_j = t)  propto  c_t * W(others | pool with one copy of t removed)
where W = sum over consistent assignments of the OTHER cards of the same
falling-factorial weight.

Key exact simplification: any other card whose allowed set contains every
feasible type ("unconstrained": never touched by a restricting hint)
contributes a factor (N - 1 - k)_(u) that is IDENTICAL across candidates t
and across assignments of the constrained cards, so unconstrained cards
cancel from the marginal. Hence:
  - if NO other hand card is hint-constrained, the joint posterior equals
    the per-card marginal posterior (``posterior.py``) exactly;
  - otherwise only the constrained others (usually 1-3 cards) enter a
    bitmask DP over types.

All weights are exact integers; the only float is the final division.
"""

from __future__ import annotations

from convention_gap.game_engine import ALL_COLORS, ALL_RANKS, CARD_DISTRIBUTION, HanabiState


def _falling(c: int, k: int) -> int:
    p = 1
    for i in range(k):
        p *= c - i
    return p


def _assignment_count_dp(constrained_allowed, pool, decrement_type=None):
    """Number of weighted assignments of the constrained cards.

    constrained_allowed: list of allowed-type frozensets, one per card.
    pool: dict type -> remaining copies.
    decrement_type: if set, that type has one fewer copy available
      (it was assigned to the played card).

    Returns the exact integer  sum_assignments prod_t (c_t)_(k_t).
    """
    m = len(constrained_allowed)
    full = (1 << m) - 1
    dp = [0] * (full + 1)
    dp[0] = 1

    relevant = set()
    for s in constrained_allowed:
        relevant |= s

    for t in sorted(relevant):
        c = pool.get(t, 0) - (1 if t == decrement_type else 0)
        if c <= 0:
            continue
        card_bits = [i for i in range(m) if t in constrained_allowed[i]]
        if not card_bits:
            continue
        ndp = dp[:]  # k_t = 0 case
        for mask in range(full + 1):
            w0 = dp[mask]
            if w0 == 0:
                continue
            avail = [b for b in card_bits if not (mask >> b) & 1]
            na = len(avail)
            # non-empty subsets U of avail with |U| <= c
            for sub in range(1, 1 << na):
                k = bin(sub).count("1")
                if k > c:
                    continue
                bits = 0
                for bi in range(na):
                    if (sub >> bi) & 1:
                        bits |= 1 << avail[bi]
                ndp[mask | bits] += w0 * _falling(c, k)
        dp = ndp

    return dp[full]


def compute_joint_posterior(
    state: HanabiState, player_id: int, card_index: int
) -> tuple[float, int, int]:
    """Joint-inference P(life lost) for playing card at card_index.

    Returns (p_life_loss, num_joint_candidates, num_constrained_others):
      num_joint_candidates: candidate types of the played card with
        nonzero joint weight;
      num_constrained_others: other hand cards whose hint knowledge
        actually constrains them (0 -> joint == marginal exactly).
    """
    knowledge = state.card_knowledge[player_id]
    hand_n = len(state.hands[player_id])
    visible = state._count_visible_cards(player_id)

    pool = {}
    for color in ALL_COLORS:
        for rank in ALL_RANKS:
            c = CARD_DISTRIBUTION[rank] - visible.get((color, rank), 0)
            if c > 0:
                pool[(int(color), int(rank))] = c
    feasible = frozenset(pool)

    allowed = []
    for i in range(hand_n):
        k = knowledge[i]
        s = frozenset(
            (int(c), int(r))
            for c in k.possible_colors
            for r in k.possible_ranks
        ) & feasible
        allowed.append(s)

    j = card_index
    cand_j = allowed[j]
    if not cand_j:
        return 0.0, 0, 0

    constrained = [
        allowed[i] for i in range(hand_n) if i != j and allowed[i] != feasible
    ]

    if not constrained:
        # exact reduction: joint marginal == per-card marginal
        total = 0
        unplayable = 0
        for t in cand_j:
            w = pool[t]
            total += w
            if not state.is_playable(t[0], t[1]):
                unplayable += w
        return (unplayable / total if total else 0.0), len(cand_j), 0

    relevant = set()
    for s in constrained:
        relevant |= s

    w_base = _assignment_count_dp(constrained, pool)

    total = 0
    unplayable = 0
    n_cand = 0
    for t in cand_j:
        if t in relevant:
            w_others = _assignment_count_dp(constrained, pool, decrement_type=t)
        else:
            w_others = w_base
        w = pool[t] * w_others
        if w <= 0:
            continue
        n_cand += 1
        total += w
        if not state.is_playable(t[0], t[1]):
            unplayable += w

    if total == 0:
        # Degenerate (inconsistent constraints); fall back to marginal.
        total_m = sum(pool[t] for t in cand_j)
        unpl_m = sum(
            pool[t] for t in cand_j if not state.is_playable(t[0], t[1])
        )
        return (unpl_m / total_m if total_m else 0.0), len(cand_j), len(constrained)

    return unplayable / total, n_cand, len(constrained)


def brute_force_joint_posterior(
    state: HanabiState, player_id: int, card_index: int, max_products: int = 2_000_000
):
    """Exhaustive-enumeration reference implementation (for verification).

    Enumerates the full product of allowed sets over ALL hand cards
    (including unconstrained ones) with falling-factorial weights.
    Returns None if the product space exceeds max_products.
    """
    from collections import Counter
    from itertools import product

    knowledge = state.card_knowledge[player_id]
    hand_n = len(state.hands[player_id])
    visible = state._count_visible_cards(player_id)

    pool = {}
    for color in ALL_COLORS:
        for rank in ALL_RANKS:
            c = CARD_DISTRIBUTION[rank] - visible.get((color, rank), 0)
            if c > 0:
                pool[(int(color), int(rank))] = c
    feasible = frozenset(pool)

    allowed = []
    for i in range(hand_n):
        k = knowledge[i]
        s = frozenset(
            (int(c), int(r))
            for c in k.possible_colors
            for r in k.possible_ranks
        ) & feasible
        allowed.append(sorted(s))

    size = 1
    for s in allowed:
        size *= max(len(s), 1)
    if size > max_products:
        return None

    total = 0
    unplayable = 0
    j = card_index
    for assign in product(*allowed):
        cnt = Counter(assign)
        w = 1
        for t, k in cnt.items():
            w *= _falling(pool[t], k)
            if w == 0:
                break
        if w <= 0:
            continue
        total += w
        t = assign[j]
        if not state.is_playable(t[0], t[1]):
            unplayable += w

    if total == 0:
        # Degenerate (inconsistent constraints): mirror the marginal
        # fallback used by compute_joint_posterior.
        total_m = sum(pool[t] for t in allowed[j])
        unpl_m = sum(
            pool[t] for t in allowed[j] if not state.is_playable(t[0], t[1])
        )
        return unpl_m / total_m if total_m else 0.0
    return unplayable / total
