"""Joint-posterior replay for the LLM-vs-rule-agent corpus (Appendix M/N).

The LLM game-log format differs from hanab.live (see the corpus manifest
``Manuscript/review_round_2026_0724/llm_corpus_manifest_2026-08-17.md``):
colors R,B,G,W,Y = 0-4, hands given directly as card strings, and draws
replace IN PLACE at the same hand index (no slot shift). This module
replays the 1,861-game 2026-04-24 snapshot corpus (a per-condition
seed-prefix of the raw tree), verifies that the recomputed per-card
marginal posteriors match the shipped ``cg_records.json`` exactly on all
19,093 play records, and then computes the exact full-hand joint
posterior for every play, reusing the falling-factorial bitmask DP from
``src.joint_posterior``.

Outputs (data/processed/):
  llm_joint_posteriors.csv   per-play marginal + joint + parse_ok flag
  llm_joint_replay_timing.json  timing, brute-check and verification stats
  llm_fallback_counts.json   per-condition fallback action counts by type

Run from the repo root:  python -m src.llm_joint_replay
"""

from __future__ import annotations

import csv
import json
import os
import time
from collections import Counter
from itertools import product
from pathlib import Path

from src.joint_posterior import _assignment_count_dp, _falling

ROOT = Path(__file__).resolve().parent.parent
# Raw LLM game logs are not shipped in the bundle (they contain full prompts);
# point HANABI_LLM_RAW at a local checkout of the results tree to regenerate.
RAW_LLM = Path(
    os.environ.get("HANABI_LLM_RAW", ROOT / "data" / "raw" / "llm_results")
)
# Shipped per-play records used for the exact marginal-verification gate.
SHIPPED_RECORDS = Path(
    os.environ.get(
        "HANABI_LLM_CG_RECORDS", ROOT / "data" / "processed" / "llm_cg_records.json"
    )
)
OUT_CSV = ROOT / "data" / "processed" / "llm_joint_posteriors.csv"
OUT_TIMING = ROOT / "data" / "processed" / "llm_joint_replay_timing.json"
OUT_FALLBACK = ROOT / "data" / "processed" / "llm_fallback_counts.json"

# 2026-04-24 snapshot inclusion rule: games 1..N per condition.
SNAPSHOT_N = {
    ("GPT54_Mini", "llm_vs_intentional_cot_medium"): 45,
    ("Qwen36_A3B", "llm_vs_iggi_cot"): 8,
    ("Qwen36_A3B", "llm_vs_intentional_cot"): 8,
}
SNAPSHOT_DEFAULT_N = 50
MODELS = ["GPT54", "GPT54_Mini", "Qwen36_A3B"]
# Conditions generated after the snapshot — excluded entirely.
EXCLUDED_CONDITIONS = {
    ("Qwen36_A3B", "llm_vs_flawed_cot"),
    ("Qwen36_A3B", "llm_vs_internal_cot"),
    ("Qwen36_A3B", "llm_vs_outer_cot"),
    ("Qwen36_A3B", "llm_vs_piers_cot"),
}

COLOR_TO_IDX = {"R": 0, "B": 1, "G": 2, "W": 3, "Y": 4}
CARD_DIST = {1: 3, 2: 2, 3: 2, 4: 2, 5: 1}
TOTAL_DECK = sum(CARD_DIST.values()) * 5
MAX_INFO = 8
BRUTE_CHECK_EVERY = 197


def parse_card(s):
    return (COLOR_TO_IDX[s[0]], int(s[1]))


class LLMState:
    """Replay state for the LLM log format (verbatim marginal logic from
    LLM_Hanabi/archive/scripts/convention_gap_llm.py)."""

    def __init__(self, hands_strs):
        self.num_players = len(hands_strs)
        self.hands = [[parse_card(c) for c in h] for h in hands_strs]
        self.knowledge = [
            [
                {"colors": set(range(5)), "ranks": set(range(1, 6))}
                for _ in range(len(self.hands[p]))
            ]
            for p in range(self.num_players)
        ]
        self.fireworks = [0] * 5
        self.discard_pile = []
        self.life_tokens = 3
        self.info_tokens = MAX_INFO
        dealt = sum(len(h) for h in self.hands)
        self.deck_remaining = TOTAL_DECK - dealt

    def is_playable(self, color, rank):
        return self.fireworks[color] == rank - 1

    def visible_counter(self, for_player):
        c = Counter()
        for op in range(self.num_players):
            if op != for_player:
                for card in self.hands[op]:
                    if card is not None:
                        c[card] += 1
        for card in self.discard_pile:
            c[card] += 1
        for color in range(5):
            for r in range(1, self.fireworks[color] + 1):
                c[(color, r)] += 1
        return c

    def candidates(self, player, card_idx):
        k = self.knowledge[player][card_idx]
        visible = self.visible_counter(player)
        out = []
        for color in k["colors"]:
            for rank in k["ranks"]:
                total = CARD_DIST[rank]
                seen = visible.get((color, rank), 0)
                remaining = total - seen
                if remaining > 0:
                    out.append(((color, rank), remaining))
        return out

    def posterior_life_loss(self, player, card_idx):
        cands = self.candidates(player, card_idx)
        if not cands:
            return 0.0, 0
        total_w = sum(r for _, r in cands)
        if total_w == 0:
            return 0.0, 0
        unplay_w = sum(r for (c, rk), r in cands if not self.is_playable(c, rk))
        return unplay_w / total_w, len(cands)

    # ---- joint posterior (same math as src.joint_posterior, adapted to
    #      this state layout: None slots after deck exhaustion are skipped) --
    def _pool_and_allowed(self, player):
        visible = self.visible_counter(player)
        pool = {}
        for color in range(5):
            for rank in range(1, 6):
                c = CARD_DIST[rank] - visible.get((color, rank), 0)
                if c > 0:
                    pool[(color, rank)] = c
        feasible = frozenset(pool)
        allowed = []
        for i, card in enumerate(self.hands[player]):
            if card is None:
                allowed.append(None)  # empty slot: not part of the hand
                continue
            k = self.knowledge[player][i]
            s = frozenset(
                (c, r) for c in k["colors"] for r in k["ranks"]
            ) & feasible
            allowed.append(s)
        return pool, feasible, allowed

    def joint_posterior_life_loss(self, player, card_idx):
        """Returns (p_life_loss, n_cand_joint, n_constrained_others)."""
        pool, feasible, allowed = self._pool_and_allowed(player)
        cand_j = allowed[card_idx]
        if not cand_j:
            return 0.0, 0, 0

        constrained = [
            allowed[i]
            for i in range(len(allowed))
            if i != card_idx and allowed[i] is not None and allowed[i] != feasible
        ]

        if not constrained:
            total = sum(pool[t] for t in cand_j)
            unpl = sum(
                pool[t] for t in cand_j if not self.is_playable(t[0], t[1])
            )
            return (unpl / total if total else 0.0), len(cand_j), 0

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
            if not self.is_playable(t[0], t[1]):
                unplayable += w

        if total == 0:
            total_m = sum(pool[t] for t in cand_j)
            unpl_m = sum(
                pool[t] for t in cand_j if not self.is_playable(t[0], t[1])
            )
            return (
                (unpl_m / total_m if total_m else 0.0),
                len(cand_j),
                len(constrained),
            )
        return unplayable / total, n_cand, len(constrained)

    def brute_force_joint(self, player, card_idx, max_products=2_000_000):
        """Exhaustive reference over ALL (non-empty) hand slots."""
        pool, feasible, allowed = self._pool_and_allowed(player)
        idx_map = [i for i in range(len(allowed)) if allowed[i] is not None]
        sets = [sorted(allowed[i]) for i in idx_map]
        j = idx_map.index(card_idx)
        size = 1
        for s in sets:
            size *= max(len(s), 1)
        if size > max_products:
            return None
        total = 0
        unplayable = 0
        for assign in product(*sets):
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
            if not self.is_playable(t[0], t[1]):
                unplayable += w
        if total == 0:
            cand_j = allowed[card_idx]
            total_m = sum(pool[t] for t in cand_j)
            unpl_m = sum(
                pool[t] for t in cand_j if not self.is_playable(t[0], t[1])
            )
            return unpl_m / total_m if total_m else 0.0
        return unplayable / total

    # ---- actions ----
    def apply_play(self, player, card_idx, drawn):
        card = self.hands[player][card_idx]
        assert card is not None
        color, rank = card
        played_ok = self.is_playable(color, rank)
        if played_ok:
            self.fireworks[color] = rank
            if rank == 5 and self.info_tokens < MAX_INFO:
                self.info_tokens += 1
        else:
            self.life_tokens -= 1
            self.discard_pile.append(card)
        self._replace_card(player, card_idx, drawn)
        return played_ok

    def apply_discard(self, player, card_idx, drawn):
        card = self.hands[player][card_idx]
        assert card is not None
        self.discard_pile.append(card)
        if self.info_tokens < MAX_INFO:
            self.info_tokens += 1
        self._replace_card(player, card_idx, drawn)

    def _replace_card(self, player, card_idx, drawn):
        if drawn:
            self.hands[player][card_idx] = parse_card(drawn)
            self.knowledge[player][card_idx] = {
                "colors": set(range(5)),
                "ranks": set(range(1, 6)),
            }
            self.deck_remaining -= 1
        else:
            self.hands[player][card_idx] = None
            self.knowledge[player][card_idx] = {"colors": set(), "ranks": set()}

    def apply_hint_color(self, hinter, target, color):
        self.info_tokens -= 1
        for i, card in enumerate(self.hands[target]):
            if card is None:
                continue
            if card[0] == color:
                self.knowledge[target][i]["colors"] = {color}
            else:
                self.knowledge[target][i]["colors"].discard(color)

    def apply_hint_rank(self, hinter, target, rank):
        self.info_tokens -= 1
        for i, card in enumerate(self.hands[target]):
            if card is None:
                continue
            if card[1] == rank:
                self.knowledge[target][i]["ranks"] = {rank}
            else:
                self.knowledge[target][i]["ranks"].discard(rank)


def snapshot_files():
    """Yield (model, condition, path) for the 1,861 corpus games in the
    original iteration order (sorted dirs, lexicographically sorted files)."""
    for model_dir in sorted(d for d in RAW_LLM.iterdir() if d.is_dir()):
        model = model_dir.name
        if model not in MODELS:
            continue
        for group_dir in sorted(d for d in model_dir.iterdir() if d.is_dir()):
            cond = group_dir.name
            if not cond.startswith("llm_vs_"):
                continue
            if (model, cond) in EXCLUDED_CONDITIONS:
                continue
            n = SNAPSHOT_N.get((model, cond), SNAPSHOT_DEFAULT_N)
            for gf in sorted(group_dir.glob("game_*.json")):
                num = int(gf.stem.split("_")[1])
                if num <= n:
                    yield model, cond, gf


def replay_corpus(verbose=True):
    stats = {
        "plays": 0,
        "marginal_time": 0.0,
        "joint_time": 0.0,
        "brute_checks": 0,
        "brute_max_absdiff": 0.0,
        "games": 0,
        "score_mismatches": 0,
    }
    fallback_counts = {}
    rows = []
    t_start = time.perf_counter()

    for model, cond, gf in snapshot_files():
        with open(gf) as f:
            g = json.load(f)
        num_players = g.get("num_players", 2)
        hands = [g[f"player{p}_hand"] for p in range(num_players)]
        state = LLMState(hands)
        strategies = list(g["strategy"])
        while len(strategies) < num_players:
            strategies.append(strategies[-1])
        roles = ["llm" if s == "evolve_agent" else "rule" for s in strategies]
        stats["games"] += 1

        fb = fallback_counts.setdefault(
            f"{model}/{cond}",
            {"PLAY": 0, "DISCARD": 0, "HINT_COLOR": 0, "HINT_RANK": 0,
             "llm_actions": 0, "llm_parse_ok": 0},
        )

        for turn, a in enumerate(g["actions"]):
            p = a["player"]
            t = a["type"]
            parse_ok = a.get("_parse_ok")
            if roles[p] == "llm":
                fb["llm_actions"] += 1
                if parse_ok:
                    fb["llm_parse_ok"] += 1
                elif parse_ok is not None and not parse_ok:
                    fb[t] += 1

            if t == "PLAY":
                t0 = time.perf_counter()
                p_marg, n_cand = state.posterior_life_loss(p, a["card_index"])
                t1 = time.perf_counter()
                p_joint, n_cand_j, n_constr = state.joint_posterior_life_loss(
                    p, a["card_index"]
                )
                t2 = time.perf_counter()
                stats["plays"] += 1
                stats["marginal_time"] += t1 - t0
                stats["joint_time"] += t2 - t1
                if n_constr > 0 and stats["plays"] % BRUTE_CHECK_EVERY == 0:
                    bf = state.brute_force_joint(p, a["card_index"])
                    if bf is not None:
                        d = abs(bf - p_joint)
                        stats["brute_checks"] += 1
                        stats["brute_max_absdiff"] = max(
                            stats["brute_max_absdiff"], d
                        )
                        if d > 1e-12:
                            raise AssertionError(
                                f"brute-force mismatch {d} at "
                                f"{model}/{cond}/{gf.name} turn {turn}"
                            )
                actual_ok = state.apply_play(p, a["card_index"], a.get("draw"))
                rows.append(
                    {
                        "model": model,
                        "group": cond,
                        "game_file": gf.name,
                        "turn": turn,
                        "actor_role": roles[p],
                        "actor_player": p,
                        "posterior_marginal": p_marg,
                        "posterior_joint": p_joint,
                        "n_cand_marginal": n_cand,
                        "n_cand_joint": n_cand_j,
                        "n_constrained_others": n_constr,
                        "actual_fail": not actual_ok,
                        "parse_ok": parse_ok,
                    }
                )
            elif t == "DISCARD":
                state.apply_discard(p, a["card_index"], a.get("draw"))
            elif t == "HINT_COLOR":
                state.apply_hint_color(p, a["target"], a["color"])
            elif t == "HINT_RANK":
                state.apply_hint_rank(p, a["target"], a["rank"])
            else:
                raise ValueError(f"Unknown action type: {t}")

        final_score = 0 if state.life_tokens <= 0 else sum(state.fireworks)
        rec = g.get("results", {})
        if "score" in rec and rec["score"] != final_score:
            stats["score_mismatches"] += 1

    stats["wall_clock_s"] = time.perf_counter() - t_start
    return rows, stats, fallback_counts


def verify_against_shipped(rows):
    """Exact-match check of recomputed marginals vs the shipped records."""
    shipped = json.load(open(SHIPPED_RECORDS))
    if len(shipped) != len(rows):
        raise AssertionError(
            f"record count mismatch: recomputed {len(rows)} vs shipped {len(shipped)}"
        )
    for i, (r, s) in enumerate(zip(rows, shipped)):
        if (
            r["model"] != s["model"]
            or r["group"] != s["group"]
            or r["turn"] != s["turn"]
            or r["actor_role"] != s["actor_role"]
        ):
            raise AssertionError(f"record identity mismatch at index {i}")
        if r["posterior_marginal"] != s["posterior"]:
            raise AssertionError(
                f"marginal posterior mismatch at index {i}: "
                f"{r['posterior_marginal']!r} vs shipped {s['posterior']!r}"
            )
        if r["actual_fail"] != s["actual_fail"] or r["n_cand_marginal"] != s["num_candidates"]:
            raise AssertionError(f"outcome/candidate mismatch at index {i}")
    return len(rows)


def regenerate(verbose=True):
    rows, stats, fallback_counts = replay_corpus(verbose=verbose)
    n_verified = verify_against_shipped(rows)
    stats["verified_against_shipped"] = n_verified

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys())
    with open(OUT_CSV, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            r = dict(r)
            r["posterior_marginal"] = f"{r['posterior_marginal']:.12g}"
            r["posterior_joint"] = f"{r['posterior_joint']:.12g}"
            w.writerow(r)
    OUT_TIMING.write_text(json.dumps(stats, indent=2))
    OUT_FALLBACK.write_text(json.dumps(fallback_counts, indent=2))

    if verbose:
        n = stats["plays"]
        print(
            f"LLM joint replay: {stats['games']} games, {n:,} plays, "
            f"score mismatches {stats['score_mismatches']}, "
            f"marginal verified vs shipped on {n_verified:,} records"
        )
        print(
            f"timing: marginal {stats['marginal_time'] / n * 1e6:.0f}us/play, "
            f"joint {stats['joint_time'] / n * 1e6:.0f}us/play, "
            f"wall {stats['wall_clock_s']:.0f}s; brute checks "
            f"{stats['brute_checks']} (max diff {stats['brute_max_absdiff']:.1e})"
        )
    return rows, stats, fallback_counts


if __name__ == "__main__":
    regenerate()
