"""Run OBL agents per-step in Python, export games to hanab.live JSON.

Adapted from off-belief-learning/pyhanabi/tools/run_game.py (game loop)
and tools/game_exporter.py (export), with two changes for the
hanabi-convention-gap input format:
  - deck comes from env.deck_history() (already in deal order, so no
    reversal) and uses {"suitIndex": int, "rank": int} keys;
  - games carry ids/players metadata.

Usage:
  python export_obl_games.py --weight1 W [--weight2 W2] --num_game N \
      --seed_base S --out_dir DIR --prefix NAME
"""
import argparse
import json
import os
import sys
import time

PYHANABI = "$OBL_ROOT/off-belief-learning/pyhanabi"
sys.path.insert(0, PYHANABI)
os.chdir(PYHANABI)  # utils.load_agent reads train.log via relative paths

import set_path

set_path.append_sys_path()

import torch  # noqa: E402
import rela  # noqa: E402,F401  (must precede hanalearn: registers base types)
import hanalearn  # noqa: E402
import r2d2  # noqa: E402
import utils  # noqa: E402

COLOR_LETTERS = "abcde"


def load(weight):
    agent, cfg = utils.load_agent(
        weight, {"vdn": False, "device": "cuda:0", "boltzmann_act": False}
    )
    agent.train(False)
    assert cfg["sad"] == 0 and cfg["hide_action"] == 0, (weight, cfg)
    return agent


@torch.no_grad()
def run_game(agents, seed):
    """One 2-player game, greedy actions. Returns (score, moves, deck_strs)."""
    params = {
        "players": str(len(agents)),
        "seed": str(seed),
        "bomb": "0",
        "random_start_player": "0",
    }
    game = hanalearn.HanabiEnv(params, -1, False)
    game.reset()

    hids = [agent.get_h0(1) for agent in agents]
    for h in hids:
        for k, v in h.items():
            h[k] = v.cuda().unsqueeze(0)

    moves = []
    while not game.terminated():
        actions = []
        new_hids = []
        for i, (agent, hid) in enumerate(zip(agents, hids)):
            obs = hanalearn.observe(game.get_hle_state(), i, False)
            priv_s = obs["priv_s"].cuda().unsqueeze(0)
            publ_s = obs["publ_s"].cuda().unsqueeze(0)
            legal_move = obs["legal_move"].cuda().unsqueeze(0)
            action, new_hid = agent.greedy_act(priv_s, publ_s, legal_move, hid)
            actions.append(action.item())
            new_hids.append(new_hid)
        hids = new_hids
        cur_player = game.get_current_player()
        move = game.get_move(actions[cur_player])
        moves.append((cur_player, move))
        game.step(move)

    deck_strs = game.deck_history()  # deal order, e.g. "3a" = rank 3, color a
    return game.get_score(), moves, deck_strs


def export_game(game_id, players, score, moves, deck_strs):
    deck = [
        {"suitIndex": COLOR_LETTERS.index(s[-1]), "rank": int(s[:-1])}
        for s in deck_strs
    ]
    assert len(deck) == 50

    # Hands as deck indices, deal order: p0 gets 0-4, p1 gets 5-9.
    hands = {0: list(range(5)), 1: list(range(5, 10))}
    deck_cursor = 10
    actions = []
    for player, move in moves:
        mt = move.move_type()
        if mt == hanalearn.MoveType.Play or mt == hanalearn.MoveType.Discard:
            atype = 0 if mt == hanalearn.MoveType.Play else 1
            actions.append({"type": atype, "target": hands[player][move.card_index()]})
            del hands[player][move.card_index()]
            if deck_cursor < len(deck):
                hands[player].append(deck_cursor)
                deck_cursor += 1
        elif mt == hanalearn.MoveType.RevealColor:
            actions.append({"type": 2, "target": 1 - player, "value": move.color()})
        elif mt == hanalearn.MoveType.RevealRank:
            actions.append({"type": 3, "target": 1 - player, "value": move.rank() + 1})
        else:
            raise RuntimeError(f"unexpected move type {mt}")

    return {
        "id": game_id,
        "players": players,
        "deck": deck,
        "actions": actions,
        "options": {"variant": "No Variant", "numPlayers": 2},
        "hle_score": score,  # extra field: ground-truth score for verification
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--weight1", required=True)
    parser.add_argument("--weight2", default=None)
    parser.add_argument("--num_game", type=int, default=10)
    parser.add_argument("--seed_base", type=int, default=90000)
    parser.add_argument("--out_dir", required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--name1", default=None, help="player-0 label in the export")
    parser.add_argument("--name2", default=None, help="player-1 label in the export")
    args = parser.parse_args()

    a1 = load(args.weight1)
    a2 = load(args.weight2) if args.weight2 else a1
    agents = [a1, a2]
    names = [
        args.name1 or os.path.basename(os.path.dirname(args.weight1)),
        args.name2 or os.path.basename(os.path.dirname(args.weight2 or args.weight1)),
    ]

    os.makedirs(args.out_dir, exist_ok=True)
    t0 = time.time()
    scores = []
    games = []
    for g in range(args.num_game):
        score, moves, deck_strs = run_game(agents, args.seed_base + g)
        games.append(export_game(args.seed_base + g, names, score, moves, deck_strs))
        scores.append(score)
        if (g + 1) % 50 == 0:
            el = time.time() - t0
            print(
                f"[{args.prefix}] {g+1}/{args.num_game} games, "
                f"mean score {sum(scores)/len(scores):.3f}, "
                f"{el:.1f}s ({el/(g+1):.2f}s/game)",
                flush=True,
            )

    out = os.path.join(args.out_dir, f"{args.prefix}.json")
    with open(out, "w") as f:
        json.dump(games, f)
    print(
        f"[{args.prefix}] DONE {args.num_game} games, "
        f"mean score {sum(scores)/len(scores):.3f}, wrote {out}",
        flush=True,
    )


if __name__ == "__main__":
    main()
