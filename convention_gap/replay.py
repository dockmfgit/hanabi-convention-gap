"""Replay games and extract PlayRecords at each play action.

This is the bridge between raw game logs and the posterior analysis.
It replays each game action-by-action, and at every play action it
snapshots the state and computes the posterior before applying the play.

The primary posterior (``posterior_p_life_loss``) is the exact full-hand
joint-inference posterior (see ``joint_posterior.py``). The per-card
marginal simplification is also recorded (``posterior_marginal``) for
comparison; the two coincide whenever no other card in the acting
player's hand carries hint constraints.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from typing import Optional

from convention_gap.game_engine import (
    Action,
    ActionType,
    HanabiState,
    actions_from_hanab_live,
    state_from_hanab_live,
)
from convention_gap.joint_posterior import compute_joint_posterior
from convention_gap.posterior import compute_life_loss_posterior

logger = logging.getLogger(__name__)


@dataclass
class PlayRecord:
    """Record of a single play action with posterior analysis."""

    game_id: int
    game_key: str               # globally unique per game (pairing:game_id for HOAD, else game_id)
    turn: int
    player: str
    card_index: int
    actual_card: tuple  # (color, rank)
    was_playable: bool
    posterior_p_life_loss: float        # exact full-hand joint posterior
    posterior_marginal: float           # per-card simplification (reference)
    num_constrained_others: int         # other hand cards with hint constraints
    num_candidates: int
    fireworks_state: dict  # snapshot
    life_tokens: int
    info_tokens: int
    hints_on_card: int          # count of hint ACTIONS that touched this card (Appendix A8)
    hint_types_on_card: int     # 0/1/2 — count of hint types (legacy metric, kept for comparison)
    cards_in_deck: int
    final_score: int            # end-of-game score (0 if life_tokens==0 at end, else sum(fireworks))
    game_end_reason: str        # strikeout / perfect / natural / truncated (see HanabiState.get_game_end_reason)
    # Cross-source metadata
    data_source: str = "hanab_live"
    subject_type: str = "human"
    partner_type: str = "human"
    skill_level: str = ""


def replay_and_extract(
    game_json: dict,
    data_source: str = "hanab_live",
    subject_type: Optional[str] = "human",
    partner_type: Optional[str] = "human",
    skill_level: str = "",
    game_key_prefix: str = "",
) -> tuple[list[PlayRecord], HanabiState]:
    """Replay a game and extract PlayRecords for every play action.

    At each play action, BEFORE applying it, we compute the posterior
    from the acting player's perspective. Then we apply the action to
    see whether it succeeded.

    subject_type / partner_type: if None, derive per-record from the
    acting player's identity (game_json["players"][player_id]). If a
    string, all records get that constant value.

    Returns:
        (play_records, final_state)
    """
    state = state_from_hanab_live(game_json)
    state.deal_initial_hands()
    actions = actions_from_hanab_live(game_json)

    game_id = game_json.get("id", 0)
    players = game_json.get("players", [])
    # Compose globally unique game key. HOAD callers pass game_key_prefix=<pairing>;
    # hanab.live and HanabiData games already have unique game_ids.
    game_key = f"{game_key_prefix}:{game_id}" if game_key_prefix else str(game_id)

    records: list[PlayRecord] = []
    hit_terminate_marker = False

    for action in actions:
        if state.game_over:
            break
        if action.action_type == ActionType.GAME_OVER:
            # hanab.live appends a GAME_OVER marker only for abnormal ends
            # (timeout / terminated / idle-timeout). Normal, perfect, and
            # strikeout completions carry no such marker.
            hit_terminate_marker = True
            break

        # Translate deck index → hand position for play/discard
        if action.action_type in (ActionType.PLAY, ActionType.DISCARD):
            deck_idx = action.target
            hand_pos = state.find_hand_index_by_deck_index(
                state.current_player, deck_idx
            )
            translated = Action(action.action_type, target=hand_pos, value=action.value)
        else:
            translated = action

        # If this is a play action, compute posterior BEFORE applying
        if action.action_type == ActionType.PLAY:
            player_id = state.current_player
            card_index = translated.target

            # Compute both posterior variants BEFORE the play is applied.
            # The joint posterior is the primary metric; the marginal is
            # kept as a reference column.
            p_marginal, _ = compute_life_loss_posterior(
                state, player_id, card_index
            )
            p_loss, n_candidates, n_constrained = compute_joint_posterior(
                state, player_id, card_index
            )

            # Get card knowledge for hint counts
            knowledge = state.card_knowledge[player_id][card_index]

            # The actual card (ground truth)
            actual_card = state.hands[player_id][card_index]
            was_playable = state.is_playable(actual_card[0], actual_card[1])

            # Snapshot fireworks
            fw_snapshot = dict(state.fireworks)

            # Per-record actor/partner derivation
            player_name = (
                players[player_id] if player_id < len(players) else str(player_id)
            )
            if subject_type is None:
                actor_type = player_name
            else:
                actor_type = subject_type
            if partner_type is None:
                if len(players) == 2:
                    partner_val = players[1 - player_id]
                else:
                    partner_val = ",".join(
                        p for i, p in enumerate(players) if i != player_id
                    )
            else:
                partner_val = partner_type

            record = PlayRecord(
                game_id=game_id,
                game_key=game_key,
                turn=state.turn,
                player=player_name,
                card_index=card_index,
                actual_card=actual_card,
                was_playable=was_playable,
                posterior_p_life_loss=p_loss,
                posterior_marginal=p_marginal,
                num_constrained_others=n_constrained,
                num_candidates=n_candidates,
                fireworks_state=fw_snapshot,
                life_tokens=state.life_tokens,
                info_tokens=state.info_tokens,
                hints_on_card=knowledge.hint_count,
                hint_types_on_card=knowledge.hint_types,
                cards_in_deck=state.deck_size,
                final_score=0,  # backfilled after game finishes
                game_end_reason="",  # backfilled after game finishes
                data_source=data_source,
                subject_type=actor_type,
                partner_type=partner_val,
                skill_level=skill_level,
            )
            records.append(record)

        # Apply the action
        state.apply_action(translated)

    # Backfill final_score (Appendix A: strike-out → 0, else sum of fireworks)
    # and the game-end reason (strikeout / perfect / natural / truncated).
    end_reason = state.get_game_end_reason(hit_terminate_marker=hit_terminate_marker)
    # Truncated (abnormally ended) games are scored 0 on hanab.live; mirror that
    # so downstream code that keys on final_score stays consistent even though
    # truncated games are excluded from the completed-game corpus.
    if end_reason == "truncated":
        final_score = 0
    else:
        final_score = state.get_final_score()
    for r in records:
        r.final_score = final_score
        r.game_end_reason = end_reason

    return records, state


def process_games(
    game_jsons: list[dict],
    data_source: str = "hanab_live",
    subject_type: Optional[str] = "human",
    partner_type: Optional[str] = "human",
    skill_level: str = "",
    return_skipped: bool = False,
    game_key_prefix: str = "",
):
    """Process multiple games and return all PlayRecords.

    Skips games that fail to replay (logs a warning).
    If return_skipped is True, returns (all_records, skipped_ids).
    """
    all_records: list[PlayRecord] = []
    skipped_ids: list = []

    for game_json in game_jsons:
        game_id = game_json.get("id", "?")
        try:
            records, _ = replay_and_extract(
                game_json,
                data_source=data_source,
                subject_type=subject_type,
                partner_type=partner_type,
                skill_level=skill_level,
                game_key_prefix=game_key_prefix,
            )
            all_records.extend(records)
        except Exception as e:
            logger.warning("Failed to process game %s: %s", game_id, e)
            skipped_ids.append(game_id)

    if skipped_ids:
        logger.info(
            "process_games: skipped %d/%d games (see warnings)",
            len(skipped_ids), len(game_jsons),
        )

    if return_skipped:
        return all_records, skipped_ids
    return all_records


def records_to_dicts(records: list[PlayRecord]) -> list[dict]:
    """Convert PlayRecords to plain dicts (for DataFrame construction)."""
    rows = []
    for r in records:
        d = asdict(r)
        # Flatten actual_card tuple
        d["actual_color"] = r.actual_card[0]
        d["actual_rank"] = r.actual_card[1]
        del d["actual_card"]
        # Flatten fireworks
        del d["fireworks_state"]
        d["fireworks_sum"] = sum(r.fireworks_state.values())
        rows.append(d)
    return rows
