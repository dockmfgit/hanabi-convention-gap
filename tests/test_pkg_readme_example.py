"""Known-answer test for the README's worked example (corrected 2026-09-07).

Card hinted "not blue" + "rank 2"; one R2 visible in the partner's hand,
both Y2s discarded; fireworks red at 1, green at 0, purple at 0. The hidden
pool holds R2x1, G2x2, P2x2 and only R2 is playable, so P = 4/5 = 0.8.
If another hand card is separately hinted "red" + "rank 2" it must be the
last hidden R2; joint inference assigns that copy there and the played
card's P rises to 1.0, while the per-card marginal still reports 0.8.
"""

from convention_gap.game_engine import CardKnowledge, Color, HanabiState
from convention_gap.joint_posterior import compute_joint_posterior
from convention_gap.posterior import compute_life_loss_posterior


def _build_state(second_card_hinted_red2: bool) -> HanabiState:
    st = HanabiState(num_players=2, deck=[(Color.BLUE, 1)] * 20)
    st.hands[0] = [(Color.GREEN, 2), (Color.RED, 2)]
    st.card_knowledge[0] = [CardKnowledge(), CardKnowledge()]
    # Played card hinted "not blue" and "rank 2"
    st.card_knowledge[0][0].possible_colors = {
        Color.RED, Color.YELLOW, Color.GREEN, Color.PURPLE
    }
    st.card_knowledge[0][0].possible_ranks = {2}
    if second_card_hinted_red2:
        st.card_knowledge[0][1].possible_colors = {Color.RED}
        st.card_knowledge[0][1].possible_ranks = {2}
    st.hands[1] = [
        (Color.RED, 2), (Color.BLUE, 1), (Color.BLUE, 3),
        (Color.BLUE, 4), (Color.BLUE, 5),
    ]
    st.card_knowledge[1] = [CardKnowledge() for _ in range(5)]
    st.discard_pile = [(Color.YELLOW, 2), (Color.YELLOW, 2)]
    st.fireworks = {
        Color.RED: 1, Color.YELLOW: 0, Color.GREEN: 0,
        Color.BLUE: 0, Color.PURPLE: 0,
    }
    return st


def test_readme_worked_example_per_card_and_joint():
    st = _build_state(second_card_hinted_red2=False)
    p_marg, n_cand = compute_life_loss_posterior(st, 0, 0)
    p_joint, _, n_constrained = compute_joint_posterior(st, 0, 0)
    assert n_cand == 3  # R2, G2, P2 (Y2 eliminated: both copies discarded)
    assert abs(p_marg - 0.8) < 1e-12
    assert n_constrained == 0  # joint reduces exactly to the per-card value
    assert abs(p_joint - 0.8) < 1e-12


def test_readme_worked_example_joint_reassigns_last_r2():
    st = _build_state(second_card_hinted_red2=True)
    p_marg, _ = compute_life_loss_posterior(st, 0, 0)
    p_joint, _, n_constrained = compute_joint_posterior(st, 0, 0)
    assert abs(p_marg - 0.8) < 1e-12  # the marginal misses the cross-card constraint
    assert n_constrained == 1
    assert abs(p_joint - 1.0) < 1e-12
