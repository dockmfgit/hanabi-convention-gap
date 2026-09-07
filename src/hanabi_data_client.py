"""Parse HanabiData text logs (human-vs-AI games) and convert to hanab.live JSON format.

HanabiData (https://github.com/yawgmoth/HanabiData) contains ~2,000 games where
humans played against 3 AI types: intentional, outer, and full.  Each game is a
`.log` file with a specific text format.  This module parses those logs and
converts them to the same JSON format used by hanab_live_client.py, so the
downstream pipeline (replay.py, posterior.py, analysis.py) works unchanged.
"""

from __future__ import annotations

import ast
import csv
import json
import logging
import subprocess
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import pandas as pd

from src.game_engine import (
    Action,
    ActionType,
    Color,
    HanabiState,
)
from src.replay import PlayRecord, replay_and_extract, records_to_dicts

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RAW_DIR = DATA_DIR / "raw" / "hanabi_data"
CONVERTED_DIR = RAW_DIR / "converted"
REPO_DIR = RAW_DIR / "HanabiData"


# ---------------------------------------------------------------------------
# Color / action mappings
# ---------------------------------------------------------------------------

# HanabiData color index → color name
HD_COLOR_NAMES = {0: "green", 1: "yellow", 2: "white", 3: "blue", 4: "red"}

# Color name → HanabiData index
HD_NAME_TO_COLOR = {v: k for k, v in HD_COLOR_NAMES.items()}

# HanabiData color index → engine Color value
HD_TO_ENGINE_COLOR = {
    0: int(Color.GREEN),   # green  → GREEN (2)
    1: int(Color.YELLOW),  # yellow → YELLOW (1)
    2: int(Color.PURPLE),  # white  → PURPLE (4)
    3: int(Color.BLUE),    # blue   → BLUE (3)
    4: int(Color.RED),     # red    → RED (0)
}

# HanabiData action → hanab.live ActionType
HD_TO_HL_ACTION = {
    0: int(ActionType.COLOR_CLUE),  # color_hint → COLOR_CLUE (2)
    1: int(ActionType.RANK_CLUE),   # rank_hint  → RANK_CLUE (3)
    2: int(ActionType.PLAY),        # play       → PLAY (0)
    3: int(ActionType.DISCARD),     # discard    → DISCARD (1)
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class HanabiDataGameMeta:
    """Metadata for a single game from games.csv."""
    participant_id: str
    ai_type: str
    deck_seed: int
    score: int
    timestamp: float
    is_first_game: bool  # first game in participant's sequence


@dataclass
class ParsedMove:
    """A single parsed move from a HanabiData log."""
    player: int           # 0=AI, 1=Human in HanabiData
    action: int           # 0=color_hint, 1=rank_hint, 2=play, 3=discard
    position: Optional[int]   # hand position for play/discard
    target: Optional[int]     # target player for hints
    color: Optional[int]      # HanabiData color index for color hints
    rank: Optional[int]       # rank for rank hints
    # Extracted from descriptive lines
    played_card: Optional[tuple[int, int]] = None  # (hd_color, rank) for play/discard
    hand_after: Optional[list[tuple[int, int]]] = None  # hand state shown after move


@dataclass
class ParsedLog:
    """Fully parsed HanabiData log file."""
    ai_type: str
    seed: int
    remaining_deck: list[tuple[int, int]]  # (hd_color, rank) tuples
    moves: list[ParsedMove]
    score: int
    game_file_id: str = ""
    predecessor_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Step 1: Download/clone repository
# ---------------------------------------------------------------------------

def download_hanabi_data(repo_dir: Optional[Path] = None) -> Path:
    """Clone or update the HanabiData repository.

    Returns:
        Path to the cloned repo directory.
    """
    repo = repo_dir or REPO_DIR
    repo.parent.mkdir(parents=True, exist_ok=True)

    if (repo / ".git").exists():
        logger.info("HanabiData repo already exists, pulling updates...")
        subprocess.run(["git", "pull"], cwd=repo, check=True, capture_output=True)
    else:
        logger.info("Cloning HanabiData repository...")
        subprocess.run(
            ["git", "clone", "https://github.com/yawgmoth/HanabiData.git", str(repo)],
            check=True,
            capture_output=True,
        )
    return repo


# ---------------------------------------------------------------------------
# Step 2: Parse games.csv metadata
# ---------------------------------------------------------------------------

def load_games_csv(repo_dir: Optional[Path] = None) -> list[HanabiDataGameMeta]:
    """Parse games.csv from the HanabiData repository.

    Returns:
        List of HanabiDataGameMeta records.
    """
    repo = repo_dir or REPO_DIR
    csv_path = repo / "games.csv"

    records = []
    with open(csv_path, newline="") as f:
        reader = csv.reader(f, skipinitialspace=True)
        header = next(reader)  # id, ai, deck, score, time, first
        for row in reader:
            if len(row) < 6:
                continue
            try:
                records.append(HanabiDataGameMeta(
                    participant_id=row[0].strip(),
                    ai_type=row[1].strip(),
                    deck_seed=int(row[2].strip()),
                    score=int(row[3].strip()),
                    timestamp=float(row[4].strip()),
                    is_first_game=(row[5].strip().lower() == "yes"),
                ))
            except (ValueError, IndexError) as e:
                logger.warning("Skipping invalid CSV row %s: %s", row, e)

    logger.info("Loaded %d game records from games.csv", len(records))
    return records


# ---------------------------------------------------------------------------
# Step 3: Log file parsing
# ---------------------------------------------------------------------------

def parse_card_from_text(text: str) -> tuple[int, int]:
    """Parse a card like 'blue 3' into (hd_color, rank).

    Returns:
        (HanabiData color index, rank)
    """
    parts = text.strip().split()
    color_name = parts[0].lower()
    rank = int(parts[1])
    return (HD_NAME_TO_COLOR[color_name], rank)


def parse_hand_from_text(text: str) -> list[tuple[int, int]]:
    """Parse a hand like 'green 4, blue 1, blue 2, green 2, red 1'.

    Returns:
        List of (hd_color, rank) tuples.
    """
    cards = []
    for card_text in text.split(","):
        card_text = card_text.strip()
        if card_text:
            cards.append(parse_card_from_text(card_text))
    return cards


def _parse_move_fields(line: str) -> dict:
    """Parse 'MOVE: <player> <action> <pos> <target> <color> <rank>' fields."""
    parts = line[len("MOVE:"):].split()
    return {
        "player": int(parts[0]),
        "action": int(parts[1]),
        "position": int(parts[2]) if parts[2] != "None" else None,
        "target": int(parts[3]) if parts[3] != "None" else None,
        "color": int(parts[4]) if parts[4] != "None" else None,
        "rank": int(parts[5]) if parts[5] != "None" else None,
    }


def _extract_played_card(desc_line: str) -> Optional[tuple[int, int]]:
    """Extract card identity from a play/discard description line.

    Handles:
      'You plays blue 1 successfully! ...'
      'You plays green 2 and fails. ...'
      'intentional discards white 2'
    """
    # Find 'plays' or 'discards' keyword
    for keyword in ("plays ", "discards "):
        idx = desc_line.find(keyword)
        if idx >= 0:
            after = desc_line[idx + len(keyword):]
            # Take the first two tokens: color name + rank
            tokens = after.split()
            if len(tokens) >= 2:
                try:
                    color_name = tokens[0].lower()
                    rank = int(tokens[1])
                    return (HD_NAME_TO_COLOR[color_name], rank)
                except (KeyError, ValueError):
                    pass
    return None


def _extract_hand_from_line(line: str) -> Optional[list[tuple[int, int]]]:
    """Extract hand from a line like '<name> [now ]has <cards>'.

    Returns None if the line doesn't contain a hand.
    """
    # Match "has " preceded by player name
    for marker in (" now has ", " has "):
        idx = line.find(marker)
        if idx >= 0:
            hand_text = line[idx + len(marker):]
            try:
                return parse_hand_from_text(hand_text)
            except (KeyError, ValueError):
                pass
    return None


def parse_log_file(log_path: Path) -> ParsedLog:
    """Parse a single HanabiData .log file.

    Returns:
        ParsedLog with all moves and metadata.
    """
    lines = log_path.read_text().strip().splitlines()

    ai_type = ""
    seed = 0
    remaining_deck: list[tuple[int, int]] = []
    moves: list[ParsedMove] = []
    score = 0
    predecessor_id = None

    # Extract game file ID from filename: game<16hex>.log
    filename = log_path.stem  # e.g. "gamebcbbc9bc2cd7369f"
    game_file_id = filename[4:] if filename.startswith("game") else filename

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if line.startswith("Old GID:"):
            predecessor_id = line.split()[-1].strip()
            i += 1
            continue

        if line.startswith("Treatment:"):
            # Parse "Treatment: ('intentional', 3)"
            treatment_str = line[len("Treatment:"):].strip()
            treatment = ast.literal_eval(treatment_str)
            ai_type = treatment[0]
            seed = treatment[1]
            i += 1
            continue

        if line.startswith("[") and not line.startswith("MOVE"):
            # Remaining deck line: Python list of tuples
            remaining_deck = ast.literal_eval(line)
            i += 1
            continue

        if line.startswith("Score"):
            score = int(line.split()[-1])
            i += 1
            continue

        if line.startswith("MOVE:"):
            fields = _parse_move_fields(line)
            move = ParsedMove(
                player=fields["player"],
                action=fields["action"],
                position=fields["position"],
                target=fields["target"],
                color=fields["color"],
                rank=fields["rank"],
            )

            # Parse subsequent descriptive lines
            i += 1
            desc_lines = []
            while i < len(lines) and not lines[i].strip().startswith("MOVE:") \
                    and not lines[i].strip().startswith("Score"):
                desc_lines.append(lines[i].strip())
                i += 1

            # Extract played/discarded card
            if move.action in (2, 3):  # play or discard
                for dl in desc_lines:
                    card = _extract_played_card(dl)
                    if card is not None:
                        move.played_card = card
                        break

            # Extract hand state
            for dl in desc_lines:
                hand = _extract_hand_from_line(dl)
                if hand is not None:
                    # For hints, this is the target's hand
                    # For play/discard, this is the acting player's new hand
                    move.hand_after = hand
                    break

            moves.append(move)
            continue

        i += 1

    return ParsedLog(
        ai_type=ai_type,
        seed=seed,
        remaining_deck=remaining_deck,
        moves=moves,
        score=score,
        game_file_id=game_file_id,
        predecessor_id=predecessor_id,
    )


# ---------------------------------------------------------------------------
# Step 4: Extract initial hands
# ---------------------------------------------------------------------------

def extract_initial_hands(
    parsed: ParsedLog,
) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """Reconstruct both players' initial hands from descriptive text.

    Player 0 = AI, Player 1 = Human in HanabiData.

    Returns:
        (ai_hand, human_hand) each as list of (hd_color, rank).
    """
    # Track card changes per player before their hand is first visible
    player_changes: dict[int, list[dict]] = {0: [], 1: []}
    player_initial_hand: dict[int, Optional[list]] = {0: None, 1: None}

    draw_counter = 0  # next index into remaining_deck

    for move in parsed.moves:
        player = move.player
        action = move.action

        if action in (2, 3):  # play or discard
            # Record this change FIRST so undo includes it
            player_changes[player].append({
                "position": move.position,
                "card": move.played_card,
                "draw_index": draw_counter,
            })
            draw_counter += 1

            # Check if this move reveals the player's hand (post-action)
            if move.hand_after is not None and player_initial_hand[player] is None:
                # Reconstruct initial hand by undoing ALL changes including this one
                player_initial_hand[player] = _undo_changes(
                    move.hand_after, player_changes[player]
                )

        elif action in (0, 1):  # hint
            # Hint shows the TARGET player's hand (unchanged)
            target = move.target
            if move.hand_after is not None and player_initial_hand[target] is None:
                if not player_changes[target]:
                    # No changes yet → this IS the initial hand
                    player_initial_hand[target] = list(move.hand_after)
                else:
                    # Target had changes → reconstruct
                    player_initial_hand[target] = _undo_changes(
                        move.hand_after, player_changes[target]
                    )

        # Stop once both hands are found
        if player_initial_hand[0] is not None and player_initial_hand[1] is not None:
            break

    # Fallback: deduce missing hand from the standard deck
    # If we know one hand + the remaining deck, the other hand is the complement
    if player_initial_hand[0] is None or player_initial_hand[1] is None:
        known_hand_idx = 0 if player_initial_hand[0] is not None else 1
        unknown_idx = 1 - known_hand_idx

        if player_initial_hand[known_hand_idx] is not None:
            deduced = _deduce_hand(
                player_initial_hand[known_hand_idx],
                parsed.remaining_deck,
            )
            if deduced is not None:
                player_initial_hand[unknown_idx] = deduced
                logger.debug(
                    "Deduced player %d hand for game %s",
                    unknown_idx, parsed.game_file_id,
                )

    if player_initial_hand[0] is None or player_initial_hand[1] is None:
        raise ValueError(
            f"Could not determine initial hands for game {parsed.game_file_id}: "
            f"AI={player_initial_hand[0] is not None}, "
            f"Human={player_initial_hand[1] is not None}"
        )

    return player_initial_hand[0], player_initial_hand[1]


def _undo_changes(
    observed_hand: list[tuple[int, int]],
    changes: list[dict],
) -> list[tuple[int, int]]:
    """Reconstruct the initial hand by undoing play/discard operations.

    Each change removed a card from `position` and appended a drawn card.
    We reverse them: remove the last card (drawn), insert back the played card.
    """
    hand = list(observed_hand)
    for change in reversed(changes):
        if len(hand) > 0:
            hand.pop()  # remove drawn card (appended at end)
        hand.insert(change["position"], change["card"])
    return hand


def _deduce_hand(
    known_hand: list[tuple[int, int]],
    remaining_deck: list[tuple[int, int]],
) -> Optional[list[tuple[int, int]]]:
    """Deduce the missing player's hand from the standard deck.

    Given one player's hand and the 40-card remaining deck, the other
    player's hand is the complement.  The order is arbitrary since this
    player never played/discarded (so hand position doesn't matter).
    """
    from collections import Counter
    from src.game_engine import CARD_DISTRIBUTION

    # Build standard deck counts
    full_deck: Counter = Counter()
    for color in range(5):
        for rank in range(1, 6):
            full_deck[(color, rank)] = CARD_DISTRIBUTION[rank]

    # Subtract known cards
    accounted: Counter = Counter()
    for card in known_hand:
        accounted[card] += 1
    for card in remaining_deck:
        accounted[card] += 1

    # The remainder is the unknown hand
    diff = full_deck - accounted
    hand = []
    for card, count in diff.items():
        hand.extend([card] * count)

    if len(hand) != 5:
        return None

    return hand


# ---------------------------------------------------------------------------
# Step 5 & 6: Convert to hanab.live JSON
# ---------------------------------------------------------------------------

def remap_card(hd_color: int, rank: int) -> tuple[int, int]:
    """Convert a HanabiData card to engine format."""
    return (HD_TO_ENGINE_COLOR[hd_color], rank)


def convert_to_hanab_live_json(
    parsed: ParsedLog,
    game_id: Optional[int] = None,
) -> dict:
    """Convert a parsed HanabiData log to hanab.live-compatible JSON.

    Determines who goes first from the MOVE lines and maps players
    accordingly: output player 0 is whoever moves first.

    Returns:
        Dict matching hanab.live game export format.
    """
    if not parsed.moves:
        raise ValueError(f"No moves in game {parsed.game_file_id}")

    # Determine who goes first
    first_mover = parsed.moves[0].player  # 0=AI or 1=Human in HanabiData

    # Extract initial hands (in HanabiData player order: 0=AI, 1=Human)
    ai_hand, human_hand = extract_initial_hands(parsed)

    # Map HanabiData players to output players
    # Output player 0 goes first, player 1 goes second
    if first_mover == 0:
        # AI goes first → output P0=AI, P1=Human
        hd_to_out = {0: 0, 1: 1}
        p0_hand = ai_hand
        p1_hand = human_hand
        player_names = [parsed.ai_type, "Human"]
    else:
        # Human goes first → output P0=Human, P1=AI
        hd_to_out = {0: 1, 1: 0}
        p0_hand = human_hand
        p1_hand = ai_hand
        player_names = ["Human", parsed.ai_type]

    # Build full 50-card deck in engine format
    engine_p0 = [remap_card(c, r) for c, r in p0_hand]
    engine_p1 = [remap_card(c, r) for c, r in p1_hand]
    engine_remaining = [remap_card(c, r) for c, r in parsed.remaining_deck]
    full_deck = engine_p0 + engine_p1 + engine_remaining

    # Create HanabiState to track hand_deck_indices for play/discard conversion
    state = HanabiState(num_players=2, deck=full_deck)
    state.deal_initial_hands()

    # Convert actions
    actions_json = []
    for move in parsed.moves:
        out_player = hd_to_out[move.player]

        if move.action == 0:  # HanabiData color_hint → COLOR_CLUE
            out_target = hd_to_out[move.target]
            engine_color = HD_TO_ENGINE_COLOR[move.color]
            actions_json.append({
                "type": int(ActionType.COLOR_CLUE),
                "target": out_target,
                "value": engine_color,
            })
            # Apply to state for tracking
            action = Action(ActionType.COLOR_CLUE, target=out_target, value=engine_color)
            state.apply_action(action)

        elif move.action == 1:  # HanabiData rank_hint → RANK_CLUE
            out_target = hd_to_out[move.target]
            actions_json.append({
                "type": int(ActionType.RANK_CLUE),
                "target": out_target,
                "value": move.rank,
            })
            action = Action(ActionType.RANK_CLUE, target=out_target, value=move.rank)
            state.apply_action(action)

        elif move.action in (2, 3):  # play or discard
            hand_pos = move.position
            deck_idx = state.hand_deck_indices[out_player][hand_pos]

            hl_type = ActionType.PLAY if move.action == 2 else ActionType.DISCARD
            actions_json.append({
                "type": int(hl_type),
                "target": deck_idx,
                "value": 0,
            })
            action = Action(hl_type, target=hand_pos, value=0)
            if state.game_over:
                break
            state.apply_action(action)

        if state.game_over:
            break

    # Compute game ID from hex string
    if game_id is None:
        try:
            game_id = int(parsed.game_file_id[:8], 16)
        except ValueError:
            game_id = 0

    return {
        "id": game_id,
        "players": player_names,
        "deck": [{"suitIndex": c, "rank": r} for c, r in full_deck],
        "actions": actions_json,
        "options": {"variant": "No Variant", "numPlayers": 2},
        "score": parsed.score,
        "metadata": {
            "ai_type": parsed.ai_type,
            "seed": parsed.seed,
            "data_source": "hanabi_data",
            "game_file_id": parsed.game_file_id,
        },
    }


# ---------------------------------------------------------------------------
# Step 7: Validate conversions
# ---------------------------------------------------------------------------

def validate_conversion(game_json: dict, expected_score: int) -> bool:
    """Replay a converted game and check the score matches.

    Returns True if the replayed score matches the expected score.
    """
    from src.game_engine import replay_game
    try:
        state, _ = replay_game(game_json)
        actual_score = state.get_score()
        if actual_score != expected_score:
            logger.warning(
                "Score mismatch for game %s: replay=%d, expected=%d",
                game_json.get("id", "?"), actual_score, expected_score,
            )
            return False
        return True
    except Exception as e:
        logger.warning(
            "Replay failed for game %s: %s", game_json.get("id", "?"), e
        )
        return False


# ---------------------------------------------------------------------------
# Step 8: Run through existing pipeline
# ---------------------------------------------------------------------------

def process_hanabi_data_games(
    repo_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    validate: bool = True,
) -> list[PlayRecord]:
    """Process all HanabiData games through the full pipeline.

    1. Parse log files
    2. Convert to hanab.live JSON
    3. Validate conversions
    4. Extract PlayRecords via replay_and_extract
    5. Re-tag records based on player identity

    Returns:
        List of PlayRecords with correct subject_type/partner_type tags.
    """
    repo = repo_dir or REPO_DIR
    log_dir = repo / "log"
    out = output_dir or CONVERTED_DIR
    out.mkdir(parents=True, exist_ok=True)

    log_files = sorted(log_dir.glob("game*.log"))
    logger.info("Found %d log files in %s", len(log_files), log_dir)

    all_records: list[PlayRecord] = []
    success_count = 0
    fail_count = 0

    for log_path in log_files:
        try:
            parsed = parse_log_file(log_path)
            game_json = convert_to_hanab_live_json(parsed)

            # Validate
            if validate and not validate_conversion(game_json, parsed.score):
                fail_count += 1
                continue

            # Save converted JSON
            json_path = out / f"{parsed.game_file_id}.json"
            with open(json_path, "w") as f:
                json.dump(game_json, f)

            # Extract play records
            records, _ = replay_and_extract(
                game_json,
                data_source="hanabi_data",
                subject_type="mixed",  # re-tag below
                partner_type="mixed",
            )

            # Re-tag records based on player identity
            players = game_json["players"]
            ai_type = parsed.ai_type
            for record in records:
                if record.player == "Human":
                    record.subject_type = "human"
                    record.partner_type = ai_type
                else:
                    record.subject_type = ai_type
                    record.partner_type = "human"
                record.data_source = "hanabi_data"

            all_records.extend(records)
            success_count += 1

        except Exception as e:
            logger.warning("Failed to process %s: %s", log_path.name, e)
            fail_count += 1

    logger.info(
        "Processed %d games successfully, %d failed", success_count, fail_count
    )
    return all_records


def save_play_records(
    records: list[PlayRecord],
    output_path: Optional[Path] = None,
) -> Path:
    """Save PlayRecords to CSV."""
    path = output_path or DATA_DIR / "processed" / "human_ai_play_records.csv"
    path.parent.mkdir(parents=True, exist_ok=True)

    dicts = records_to_dicts(records)
    df = pd.DataFrame(dicts)
    df.to_csv(path, index=False)
    logger.info("Saved %d play records to %s", len(records), path)
    return path


# ---------------------------------------------------------------------------
# Step 9: Trustworthiness metrics
# ---------------------------------------------------------------------------

def compute_trustworthiness_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Compute trustworthiness metrics per AI type.

    Computes metrics both 'as player' (AI's own plays) and 'as partner'
    (human plays when partnered with this AI).

    Returns:
        DataFrame with one row per AI type.
    """
    results = []

    for ai_type in df[df["subject_type"] != "human"]["subject_type"].unique():
        # --- As player (AI's own plays) ---
        ai_plays = df[df["subject_type"] == ai_type]
        ai_n = len(ai_plays)
        if ai_n > 0:
            ai_loss_rate = ai_plays["life_lost"].mean()
            ai_mean_posterior = ai_plays["posterior_p_life_loss"].mean()
            ai_frac_p0 = (ai_plays["posterior_p_life_loss"] == 0).mean()
            ai_frac_high = (ai_plays["posterior_p_life_loss"] > 0.5).mean()
            ai_conv_gap = ai_mean_posterior - ai_loss_rate
        else:
            ai_loss_rate = ai_mean_posterior = ai_frac_p0 = ai_frac_high = ai_conv_gap = 0

        # --- As partner (human plays with this AI) ---
        human_plays = df[
            (df["subject_type"] == "human") & (df["partner_type"] == ai_type)
        ]
        h_n = len(human_plays)
        if h_n > 0:
            h_loss_rate = human_plays["life_lost"].mean()
            h_mean_posterior = human_plays["posterior_p_life_loss"].mean()
            h_frac_p0 = (human_plays["posterior_p_life_loss"] == 0).mean()
            h_conv_gap = h_mean_posterior - h_loss_rate
        else:
            h_loss_rate = h_mean_posterior = h_frac_p0 = h_conv_gap = 0

        results.append({
            "ai_type": ai_type,
            # As player
            "ai_n_plays": ai_n,
            "ai_loss_rate": ai_loss_rate,
            "ai_mean_posterior": ai_mean_posterior,
            "ai_frac_p0": ai_frac_p0,
            "ai_frac_high_risk": ai_frac_high,
            "ai_convention_gap": ai_conv_gap,
            # As partner
            "human_n_plays": h_n,
            "human_loss_rate": h_loss_rate,
            "human_mean_posterior": h_mean_posterior,
            "human_frac_p0": h_frac_p0,
            "human_convention_gap": h_conv_gap,
        })

    return pd.DataFrame(results)


# ---------------------------------------------------------------------------
# Step 10: Compare with agent-vs-agent rankings
# ---------------------------------------------------------------------------

def compare_with_agent_rankings(
    human_ai_df: pd.DataFrame,
    agent_df: Optional[pd.DataFrame] = None,
    agent_csv_path: Optional[Path] = None,
) -> pd.DataFrame:
    """Compare human-vs-agent and agent-vs-agent trustworthiness rankings.

    Maps HanabiData AI names to HOAD agent names:
      intentional ≈ internal, outer ≈ outer, full ≈ flawed

    Returns:
        DataFrame with side-by-side rankings.
    """
    if agent_df is None and agent_csv_path is not None:
        agent_df = pd.read_csv(agent_csv_path)
    elif agent_df is None:
        default_path = DATA_DIR / "processed" / "agent_play_records.csv"
        if default_path.exists():
            agent_df = pd.read_csv(default_path)
        else:
            logger.warning("No agent data available for comparison")
            return pd.DataFrame()

    # Name mapping: HanabiData → HOAD
    hd_to_hoad = {
        "intentional": "internal",
        "outer": "outer",
        "full": "flawed",
    }

    # Human-vs-AI metrics
    h_metrics = compute_trustworthiness_metrics(human_ai_df)

    # Agent-vs-agent metrics (subset to matching agents)
    hoad_names = set(hd_to_hoad.values())
    agent_subset = agent_df[
        (agent_df["subject_type"].isin(hoad_names)) &
        (agent_df["partner_type"].isin(hoad_names))
    ]

    if len(agent_subset) == 0:
        logger.warning("No matching agent data found for comparison")
        return h_metrics

    # Compute agent-vs-agent loss rate per subject type
    agent_metrics = []
    for agent_name in hoad_names:
        plays = agent_subset[agent_subset["subject_type"] == agent_name]
        if len(plays) > 0:
            agent_metrics.append({
                "hoad_name": agent_name,
                "agent_loss_rate": plays["life_lost"].mean() if "life_lost" in plays.columns else (1 - plays["was_playable"]).mean(),
                "agent_mean_posterior": plays["posterior_p_life_loss"].mean(),
            })

    agent_metrics_df = pd.DataFrame(agent_metrics)

    # Merge
    h_metrics["hoad_name"] = h_metrics["ai_type"].map(hd_to_hoad)
    comparison = h_metrics.merge(agent_metrics_df, on="hoad_name", how="left")

    # Rank by loss rate (lower is better)
    comparison["human_ai_rank"] = comparison["ai_loss_rate"].rank()
    if "agent_loss_rate" in comparison.columns:
        comparison["agent_agent_rank"] = comparison["agent_loss_rate"].rank()

    return comparison


# ---------------------------------------------------------------------------
# Convenience entry points
# ---------------------------------------------------------------------------

def run_full_pipeline(
    clone: bool = True,
    validate: bool = True,
) -> pd.DataFrame:
    """Run the complete HanabiData pipeline end-to-end.

    1. Clone/update repository
    2. Parse and convert all games
    3. Extract play records
    4. Save to CSV
    5. Compute trustworthiness metrics

    Returns:
        DataFrame of all play records.
    """
    if clone:
        download_hanabi_data()

    records = process_hanabi_data_games(validate=validate)
    if not records:
        logger.warning("No records extracted")
        return pd.DataFrame()

    save_play_records(records)

    from src.analysis import build_dataframe
    dicts = records_to_dicts(records)
    df = build_dataframe(dicts)

    metrics = compute_trustworthiness_metrics(df)
    print("\n=== Trustworthiness Metrics (Human-vs-AI) ===")
    print(metrics.to_string(index=False))

    comparison = compare_with_agent_rankings(df)
    if len(comparison) > 0:
        print("\n=== Agent-vs-Agent vs Human-vs-Agent Comparison ===")
        print(comparison.to_string(index=False))

    return df


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    run_full_pipeline()
