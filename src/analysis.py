"""Analysis and visualization for Hanabi posterior life-loss data.

Generates calibration curves, risk profiles, and conditional analyses
from PlayRecord data.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output" / "figures"

# Display-name mapping: normalize HOAD and HanabiData agent keys to manuscript names.
# HOAD uses "internal"; HanabiData uses "intentional". Both map to "Intentional".
# HOAD's "flawed" (Walton-Rivers) and HanabiData's "full" (Eger) are DIFFERENT agents.
AGENT_DISPLAY_NAMES = {
    "internal": "Intentional",    # HOAD name "Internal" → unified display name "Intentional"
    "flawed": "Flawed",           # HOAD only (Walton-Rivers 2017) — NOT the same as Full
    "intentional": "Intentional", # HanabiData name; same agent as HOAD's "Internal"
    "full": "Full",               # HanabiData only (Eger 2017) — no HOAD counterpart
    "outer": "Outer",
    "simple": "Simple",
    "iggi": "IGGI",
    "bergh": "VanDenBergh",
    "piers": "Piers",
}


def display_name(key: str) -> str:
    """Return display-friendly agent name for figure labels."""
    return AGENT_DISPLAY_NAMES.get(key, key.title())


def ensure_output_dir(output_dir: Optional[Path] = None) -> Path:
    d = output_dir or OUTPUT_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def add_individual_skill_columns(human_df: pd.DataFrame) -> pd.DataFrame:
    """Add ``individual_skill`` and ``pair_type`` columns to a human-human DataFrame.

    ``individual_skill`` classifies each *player* (not each game) by their
    average final game score across all games in the dataset:
      - beginner:     avg < 15
      - intermediate: 15 <= avg < 22
      - expert:       avg >= 22

    ``pair_type`` is the sorted skill pair for the game, e.g. "expert-intermediate".
    The higher skill level always comes first so that E-I and I-E map to the same label.

    The DataFrame is modified **in-place** and also returned for convenience.
    """
    from collections import defaultdict

    # Per-player average final score (Appendix A: strike-out = 0)
    _gk = "game_key" if "game_key" in human_df.columns else "game_id"
    if "final_score" in human_df.columns:
        game_scores = human_df.groupby(_gk)["final_score"].first().to_dict()
    else:
        # Fallback for legacy CSVs missing final_score
        game_scores = human_df.groupby(_gk)["fireworks_sum"].max().to_dict()
    player_games: dict[str, list[float]] = defaultdict(list)
    for gid, group in human_df.groupby(_gk):
        score = game_scores[gid]
        for p in group["player"].unique():
            player_games[p].append(score)

    player_avgs = {p: sum(s) / len(s) for p, s in player_games.items()}

    def _classify(avg: float) -> str:
        if avg < 15:
            return "beginner"
        elif avg < 22:
            return "intermediate"
        return "expert"

    player_skills = {p: _classify(avg) for p, avg in player_avgs.items()}
    human_df["individual_skill"] = human_df["player"].map(player_skills)

    # Pair type per game (higher skill first for canonical ordering)
    _skill_rank = {"expert": 2, "intermediate": 1, "beginner": 0}
    game_pair: dict = {}
    for gid, group in human_df.groupby(_gk):
        players = group["player"].unique()
        skills = [player_skills[p] for p in players]
        if len(skills) < 2:
            # Only one player has play records; duplicate their skill for pair label
            game_pair[gid] = f"{skills[0]}-{skills[0]}"
        else:
            skills_sorted = sorted(skills, key=lambda s: _skill_rank[s], reverse=True)
            game_pair[gid] = f"{skills_sorted[0]}-{skills_sorted[1]}"

    human_df["pair_type"] = human_df[_gk].map(game_pair)
    # Populate skill_level column from individual_skill so the CSV encodes the
    # single, corrected classification (B3 audit follow-up).
    human_df["skill_level"] = human_df["individual_skill"]
    return human_df


# ------------------------------------------------------------------
# DataFrame construction
# ------------------------------------------------------------------

def build_dataframe(records_dicts: list[dict]) -> pd.DataFrame:
    """Build a DataFrame from flattened PlayRecord dicts."""
    df = pd.DataFrame(records_dicts)

    # Derived columns
    if len(df) > 0:
        df["life_lost"] = (~df["was_playable"]).astype(int)
        df["predicted_safe"] = (df["posterior_p_life_loss"] < 0.5).astype(int)

        # Game phase bins
        df["game_phase"] = pd.cut(
            df["turn"],
            bins=[-1, 15, 35, 200],
            labels=["early", "mid", "late"],
            right=True,
        )

        # Risk bins for calibration
        df["risk_bin"] = pd.cut(
            df["posterior_p_life_loss"],
            bins=np.linspace(0, 1, 11),  # 10 bins
            include_lowest=True,
        )

    return df


# ------------------------------------------------------------------
# 1. Calibration curve
# ------------------------------------------------------------------

def plot_calibration(
    df: pd.DataFrame,
    output_dir: Optional[Path] = None,
    label: str = "",
    ax: Optional[plt.Axes] = None,
) -> plt.Figure:
    """Calibration curve: predicted P(life lost) vs actual life-loss rate."""
    out = ensure_output_dir(output_dir)

    bins = np.linspace(0, 1, 11)
    df = df.copy()
    df["bin"] = pd.cut(df["posterior_p_life_loss"], bins=bins, include_lowest=True)

    grouped = df.groupby("bin", observed=True).agg(
        mean_predicted=("posterior_p_life_loss", "mean"),
        mean_actual=("life_lost", "mean"),
        count=("life_lost", "count"),
    ).dropna()

    own_fig = ax is None
    if own_fig:
        fig, ax = plt.subplots(1, 1, figsize=(7, 6))
    else:
        fig = ax.figure

    suffix = f" ({label})" if label else ""
    ax.plot([0, 1], [0, 1], "k--", alpha=0.4, label="Perfect calibration")
    ax.scatter(
        grouped["mean_predicted"],
        grouped["mean_actual"],
        s=grouped["count"] * 2,
        alpha=0.7,
        zorder=5,
        label=label or "Observed",
    )
    # Error bars (95% CI via binomial)
    for _, row in grouped.iterrows():
        n = row["count"]
        p = row["mean_actual"]
        se = np.sqrt(p * (1 - p) / n) if n > 0 else 0
        ax.errorbar(
            row["mean_predicted"], p,
            yerr=1.96 * se,
            color="steelblue", alpha=0.5, capsize=3,
        )

    ax.set_xlabel("Predicted P(life lost)")
    ax.set_ylabel("Actual life-loss rate")
    ax.set_title(f"Calibration Curve{suffix}")
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, 1.05)
    ax.legend()

    if own_fig:
        fig.tight_layout()
        fig.savefig(out / "calibration_curve.png", dpi=150)
        logger.info("Saved calibration_curve.png")

    return fig


# ------------------------------------------------------------------
# 2. Risk tolerance histogram
# ------------------------------------------------------------------

def plot_risk_histogram(
    df: pd.DataFrame,
    output_dir: Optional[Path] = None,
    label: str = "",
    ax: Optional[plt.Axes] = None,
) -> plt.Figure:
    """Histogram of P(life lost) at the moment of each play."""
    out = ensure_output_dir(output_dir)

    own_fig = ax is None
    if own_fig:
        fig, ax = plt.subplots(1, 1, figsize=(8, 5))
    else:
        fig = ax.figure

    suffix = f" ({label})" if label else ""

    ax.hist(
        df["posterior_p_life_loss"],
        bins=50,
        edgecolor="white",
        alpha=0.7,
        color="steelblue",
    )
    median_p = df["posterior_p_life_loss"].median()
    ax.axvline(median_p, color="red", linestyle="--", label=f"Median = {median_p:.3f}")

    ax.set_xlabel("P(life lost) at play time")
    ax.set_ylabel("Number of plays")
    ax.set_title(f"Risk Tolerance Distribution{suffix}")
    ax.legend()

    if own_fig:
        fig.tight_layout()
        fig.savefig(out / "risk_histogram.png", dpi=150)
        logger.info("Saved risk_histogram.png")

    return fig


# ------------------------------------------------------------------
# 3. Convention effect (predicted vs actual)
# ------------------------------------------------------------------

def plot_convention_effect(
    df: pd.DataFrame,
    output_dir: Optional[Path] = None,
) -> plt.Figure:
    """Bar chart: predicted life-loss rate vs actual, overall and by hint count."""
    out = ensure_output_dir(output_dir)

    predicted = df["posterior_p_life_loss"].mean()
    actual = df["life_lost"].mean()
    gap = predicted - actual

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    # Overall
    ax = axes[0]
    bars = ax.bar(
        ["Predicted\n(literal info)", "Actual\n(outcome)"],
        [predicted, actual],
        color=["#4c72b0", "#dd8452"],
        width=0.5,
    )
    ax.set_ylabel("Life-loss rate")
    ax.set_title(f"Convention Effect (gap = {gap:.3f})")
    ax.set_ylim(0, max(predicted, actual) * 1.3 + 0.01)
    for bar, val in zip(bars, [predicted, actual]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.005,
                f"{val:.3f}", ha="center", fontsize=11)

    # By hint count
    ax = axes[1]
    hint_groups = df.groupby("hints_on_card").agg(
        predicted=("posterior_p_life_loss", "mean"),
        actual=("life_lost", "mean"),
        count=("life_lost", "count"),
    )
    x = np.arange(len(hint_groups))
    w = 0.35
    ax.bar(x - w / 2, hint_groups["predicted"], w, label="Predicted", color="#4c72b0")
    ax.bar(x + w / 2, hint_groups["actual"], w, label="Actual", color="#dd8452")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{h} hint{'s' if h != 1 else ''}\n(n={c})"
                        for h, c in zip(hint_groups.index, hint_groups["count"])])
    ax.set_ylabel("Life-loss rate")
    ax.set_title("Convention Effect by Hint Count")
    ax.legend()

    fig.tight_layout()
    fig.savefig(out / "convention_effect.png", dpi=150)
    logger.info("Saved convention_effect.png")
    return fig


# ------------------------------------------------------------------
# 4. Scatter: P(life lost) vs turn, colored by outcome
# ------------------------------------------------------------------

def plot_risk_vs_turn(
    df: pd.DataFrame,
    output_dir: Optional[Path] = None,
) -> plt.Figure:
    """Scatter plot of P(life lost) vs turn number, colored by outcome."""
    out = ensure_output_dir(output_dir)

    fig, ax = plt.subplots(1, 1, figsize=(10, 5))

    success = df[df["was_playable"]]
    failure = df[~df["was_playable"]]

    ax.scatter(
        success["turn"], success["posterior_p_life_loss"],
        alpha=0.3, s=10, color="green", label=f"Success (n={len(success)})",
    )
    ax.scatter(
        failure["turn"], failure["posterior_p_life_loss"],
        alpha=0.5, s=20, color="red", marker="x", label=f"Failure (n={len(failure)})",
    )
    ax.set_xlabel("Turn number")
    ax.set_ylabel("P(life lost)")
    ax.set_title("Play Risk vs Game Progress")
    ax.legend()

    fig.tight_layout()
    fig.savefig(out / "risk_vs_turn.png", dpi=150)
    logger.info("Saved risk_vs_turn.png")
    return fig


# ------------------------------------------------------------------
# 5. Box plots: P(life lost) by game phase
# ------------------------------------------------------------------

def plot_risk_by_phase(
    df: pd.DataFrame,
    output_dir: Optional[Path] = None,
) -> plt.Figure:
    """Box plots of P(life lost) by game phase."""
    out = ensure_output_dir(output_dir)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    # By game phase
    ax = axes[0]
    phases = ["early", "mid", "late"]
    data = [df[df["game_phase"] == p]["posterior_p_life_loss"].values for p in phases]
    counts = [len(d) for d in data]
    bp = ax.boxplot(data, labels=[f"{p}\n(n={c})" for p, c in zip(phases, counts)],
                    patch_artist=True)
    for patch, color in zip(bp["boxes"], ["#a1c9f4", "#ffb482", "#8de5a1"]):
        patch.set_facecolor(color)
    ax.set_ylabel("P(life lost)")
    ax.set_title("Risk by Game Phase")

    # By life tokens
    ax = axes[1]
    lives = sorted(df["life_tokens"].unique())
    data = [df[df["life_tokens"] == lt]["posterior_p_life_loss"].values for lt in lives]
    counts = [len(d) for d in data]
    bp = ax.boxplot(data, labels=[f"{lt} lives\n(n={c})" for lt, c in zip(lives, counts)],
                    patch_artist=True)
    for patch in bp["boxes"]:
        patch.set_facecolor("#a1c9f4")
    ax.set_ylabel("P(life lost)")
    ax.set_title("Risk by Lives Remaining")

    fig.tight_layout()
    fig.savefig(out / "risk_by_phase.png", dpi=150)
    logger.info("Saved risk_by_phase.png")
    return fig


# ------------------------------------------------------------------
# 6. Agent comparison (Phase 5)
# ------------------------------------------------------------------

def plot_agent_comparison(
    df: pd.DataFrame,
    output_dir: Optional[Path] = None,
) -> plt.Figure:
    """Compare posterior distributions across different agent/partner types."""
    out = ensure_output_dir(output_dir)

    # Group by (subject_type, partner_type)
    groups = df.groupby(["subject_type", "partner_type"]).agg(
        mean_posterior=("posterior_p_life_loss", "mean"),
        median_posterior=("posterior_p_life_loss", "median"),
        actual_loss_rate=("life_lost", "mean"),
        convention_gap=("posterior_p_life_loss", lambda x:
            x.mean() - df.loc[x.index, "life_lost"].mean()),
        n_plays=("life_lost", "count"),
    ).reset_index()

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # Mean posterior by group
    ax = axes[0]
    labels = [f"{display_name(r.subject_type)}\nvs {display_name(r.partner_type)}" for _, r in groups.iterrows()]
    x = np.arange(len(groups))
    ax.bar(x, groups["mean_posterior"], color="#4c72b0", alpha=0.7, label="Predicted risk")
    ax.bar(x, groups["actual_loss_rate"], color="#dd8452", alpha=0.7,
           width=0.4, label="Actual loss rate")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("Rate")
    ax.set_title("Mean Posterior vs Actual Loss Rate")
    ax.legend()

    # Convention gap
    ax = axes[1]
    colors = ["#55a868" if g > 0 else "#c44e52" for g in groups["convention_gap"]]
    ax.barh(x, groups["convention_gap"], color=colors, alpha=0.7)
    ax.set_yticks(x)
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("Convention gap (predicted - actual)")
    ax.set_title("Convention Gap by Agent Pairing")
    ax.axvline(0, color="black", linewidth=0.5)

    fig.tight_layout()
    fig.savefig(out / "agent_comparison.png", dpi=150)
    logger.info("Saved agent_comparison.png")
    return fig


def plot_partner_effect_heatmap(
    df: pd.DataFrame,
    output_dir: Optional[Path] = None,
) -> plt.Figure:
    """Heatmap of mean posterior P(life lost) for each (subject, partner) pair."""
    out = ensure_output_dir(output_dir)

    pivot = df.pivot_table(
        values="posterior_p_life_loss",
        index="subject_type",
        columns="partner_type",
        aggfunc="mean",
    )

    fig, ax = plt.subplots(1, 1, figsize=(10, 8))
    im = ax.imshow(pivot.values, cmap="RdYlGn_r", aspect="auto", vmin=0, vmax=1)

    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([display_name(c) for c in pivot.columns], rotation=45, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([display_name(c) for c in pivot.index])

    # Annotate cells
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            val = pivot.values[i, j]
            if not np.isnan(val):
                ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                        color="white" if val > 0.5 else "black", fontsize=9)

    ax.set_xlabel("Partner Agent")
    ax.set_ylabel("Subject Agent")
    ax.set_title("Mean P(life lost) at Play Time")
    fig.colorbar(im, ax=ax, label="P(life lost)")

    fig.tight_layout()
    fig.savefig(out / "partner_effect_heatmap.png", dpi=150)
    logger.info("Saved partner_effect_heatmap.png")
    return fig


# ------------------------------------------------------------------
# Summary statistics
# ------------------------------------------------------------------

def print_summary(df: pd.DataFrame) -> None:
    """Print key summary statistics."""
    n_games = df["game_key"].nunique()
    n_plays = len(df)
    n_success = df["was_playable"].sum()
    n_fail = n_plays - n_success

    print(f"\n{'='*60}")
    print(f"POSTERIOR ANALYSIS SUMMARY")
    print(f"{'='*60}")
    print(f"Games analyzed:        {n_games}")
    print(f"Play actions:          {n_plays}")
    print(f"  Successful:          {n_success} ({100*n_success/n_plays:.1f}%)")
    print(f"  Failed (life lost):  {n_fail} ({100*n_fail/n_plays:.1f}%)")
    print()
    print(f"Posterior P(life lost):")
    print(f"  Mean:                {df['posterior_p_life_loss'].mean():.4f}")
    print(f"  Median:              {df['posterior_p_life_loss'].median():.4f}")
    print(f"  Std:                 {df['posterior_p_life_loss'].std():.4f}")
    print()
    print(f"Convention effect:")
    predicted = df["posterior_p_life_loss"].mean()
    actual = df["life_lost"].mean()
    print(f"  Predicted loss rate: {predicted:.4f}")
    print(f"  Actual loss rate:    {actual:.4f}")
    print(f"  Gap (pred - actual): {predicted - actual:.4f}")
    print()

    # By hint count
    print("By hint count on played card:")
    for h in sorted(df["hints_on_card"].unique()):
        sub = df[df["hints_on_card"] == h]
        print(f"  {h} hints: n={len(sub):4d}, "
              f"mean_posterior={sub['posterior_p_life_loss'].mean():.3f}, "
              f"actual_loss={sub['life_lost'].mean():.3f}")

    # By data source if mixed
    if df["data_source"].nunique() > 1:
        print("\nBy data source:")
        for src in df["data_source"].unique():
            sub = df[df["data_source"] == src]
            print(f"  {src}: n={len(sub)}, "
                  f"mean_posterior={sub['posterior_p_life_loss'].mean():.3f}, "
                  f"actual_loss={sub['life_lost'].mean():.3f}")

    print(f"{'='*60}\n")


# ------------------------------------------------------------------
# Run all analyses
# ------------------------------------------------------------------

def run_all(
    df: pd.DataFrame,
    output_dir: Optional[Path] = None,
) -> None:
    """Generate all plots and print summary."""
    print_summary(df)
    plot_calibration(df, output_dir)
    plot_risk_histogram(df, output_dir)
    plot_convention_effect(df, output_dir)
    plot_risk_vs_turn(df, output_dir)
    plot_risk_by_phase(df, output_dir)

    # Agent comparison plots only if we have agent data
    if df["data_source"].nunique() > 1 or df["subject_type"].nunique() > 1:
        plot_agent_comparison(df, output_dir)
    if df["partner_type"].nunique() > 1:
        plot_partner_effect_heatmap(df, output_dir)


# ==================================================================
# Cross-Phase Analysis Plots (Phase 7+)
# ==================================================================


def _half_violin(ax, data, center, side, color, width=0.4, alpha=0.5):
    """Draw one half of a KDE violin at x=center. ``side`` in {'left','right'}.

    Scores are bounded to [0, 25]. Used for the split-violin Figure 1a
    (strict scoring on the left half, lenient scoring on the right).
    """
    from scipy.stats import gaussian_kde

    data = np.asarray(data, dtype=float)
    data = data[np.isfinite(data)]
    if len(data) < 2 or np.ptp(data) == 0:
        return
    kde = gaussian_kde(data)
    ys = np.linspace(0, 25, 256)
    dens = kde(ys)
    if dens.max() > 0:
        dens = dens / dens.max() * width
    xs = center - dens if side == "left" else center + dens
    ax.fill_betweenx(ys, center, xs, facecolor=color, alpha=alpha,
                     edgecolor=color, linewidth=0.8, zorder=2)


def lenient_score_stats(
    human_df: pd.DataFrame,
    agent_df: pd.DataFrame,
    human_ai_df: pd.DataFrame,
) -> dict:
    """Strict vs lenient end-of-game score statistics per setting, plus Welch tests.

    Strict = official score (three life losses set the score to 0; HLE / Camp A).
    Lenient = the tableau total at the moment of failure (partial score kept; the
    older human-subject convention, e.g. Eger 2017; Camp B). Both are read per
    game from ``uncensored_end_score``: ``official`` (strict) and ``uncensored``
    (lenient). Used by Figure 1a annotations and Appendix M.
    """
    from scipy.stats import ttest_ind

    dfs = {"Human-Human": human_df, "Human-AI": human_ai_df, "AI-AI": agent_df}
    vals, out = {}, {}
    for name, df in dfs.items():
        u = uncensored_end_score(df)
        strict = u["official"].values.astype(float)
        lenient = u["uncensored"].values.astype(float)
        vals[name] = (strict, lenient)
        out[name] = {
            "n_games": int(len(u)),
            "strict_mean": round(float(strict.mean()), 2),
            "strict_sd": round(float(strict.std(ddof=1)), 2),
            "lenient_mean": round(float(lenient.mean()), 2),
            "lenient_sd": round(float(lenient.std(ddof=1)), 2),
            "zero_frac_pct": round(float(u["struck"].mean()) * 100, 1),
        }

    def _welch(a, b):
        t, p = ttest_ind(a, b, equal_var=False)
        d = (a.mean() - b.mean()) / np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)
        return {"t": round(float(t), 2), "p": float(p), "d": round(float(d), 3)}

    out["tests"] = {
        "lenient_HAI_vs_AA": _welch(vals["Human-AI"][1], vals["AI-AI"][1]),
        "lenient_HH_vs_HAI": _welch(vals["Human-Human"][1], vals["Human-AI"][1]),
        "strict_HAI_vs_AA": _welch(vals["Human-AI"][0], vals["AI-AI"][0]),
    }
    return out


def plot_convention_gap_and_calibration(
    human_df: pd.DataFrame,
    agent_df: pd.DataFrame,
    human_ai_df: pd.DataFrame,
    output_dir: Optional[Path] = None,
) -> plt.Figure:
    """Paper Figure 1: three-panel figure.

    (a) Game score by setting.
    (b) Convention gap by setting (Human-Human, Human-vs-AI, AI-AI).
    (c) Calibration curve (same three sources).
    """
    out = ensure_output_dir(output_dir)

    def _gap(sdf):
        sdf = sdf.copy()
        if "life_lost" not in sdf.columns:
            sdf["life_lost"] = (~sdf["was_playable"]).astype(int)
        return (sdf["posterior_p_life_loss"].mean() - sdf["life_lost"].mean()) * 100

    # Prepare life_lost columns
    hdf = human_df.copy()
    if "life_lost" not in hdf.columns:
        hdf["life_lost"] = (~hdf["was_playable"]).astype(int)
    adf = agent_df.copy()
    if "life_lost" not in adf.columns:
        adf["life_lost"] = (~adf["was_playable"]).astype(int)
    haidf = human_ai_df.copy()
    if "life_lost" not in haidf.columns:
        haidf["life_lost"] = (~haidf["was_playable"]).astype(int)

    # Convention gap values
    gap_hh = _gap(hdf)
    gap_hai = _gap(haidf[haidf["subject_type"] == "human"])
    gap_aa = _gap(adf)

    fig, (ax_score, ax_bar, ax_cal) = plt.subplots(1, 3, figsize=(18, 5.5))
    ax_score.text(-0.1, 1.05, "(a)", transform=ax_score.transAxes,
                  fontsize=14, fontweight="bold", va="bottom")
    ax_bar.text(-0.1, 1.05, "(b)", transform=ax_bar.transAxes,
                fontsize=14, fontweight="bold", va="bottom")
    ax_cal.text(-0.1, 1.05, "(c)", transform=ax_cal.transAxes,
                fontsize=14, fontweight="bold", va="bottom")

    labels = ["Human\n-Human", "Human\n-vs-AI", "AI\n-AI"]
    labels_human_plays = ["Human\n-Human", "Human\n-vs-AI\n(human plays)", "AI\n-AI"]
    bar_colors = ["#c44e52", "#9467bd", "#4c72b0"]

    # --- Panel (a): Game score by setting — split violins (strict vs lenient) ---
    # Left half of each violin = STRICT/official scoring (three life losses set
    # the score to 0; HLE / official rule, Appendix A). Right half = LENIENT
    # scoring (tableau total at the moment of failure, keeping the partial score;
    # the older human-subject convention, e.g. Eger 2017). Both are read per game
    # from uncensored_end_score(): 'official' = strict, 'uncensored' = lenient.
    from matplotlib.patches import Patch

    setting_dfs = [human_df, human_ai_df, agent_df]
    strict_col = "#8a8a8a"  # grey — strict/official (matches Appendix M convention)
    n_games = []
    for i, sdf_full in enumerate(setting_dfs):
        u = uncensored_end_score(sdf_full)
        strict = u["official"].values.astype(float)
        lenient = u["uncensored"].values.astype(float)
        zero_frac = float(u["struck"].mean()) * 100
        n_games.append(len(u))

        _half_violin(ax_score, strict, center=i, side="left",
                     color=strict_col, width=0.42, alpha=0.60)
        _half_violin(ax_score, lenient, center=i, side="right",
                     color=bar_colors[i], width=0.42, alpha=0.45)

        s_mean, l_mean = strict.mean(), lenient.mean()
        # Mean ticks (one per half)
        ax_score.plot([i - 0.42, i], [s_mean, s_mean], color="black", lw=1.3, zorder=5)
        ax_score.plot([i, i + 0.42], [l_mean, l_mean], color="black", lw=1.3, zorder=5)
        # Mean value labels: strict on the left, lenient on the right
        ax_score.text(i - 0.12, s_mean, f"{s_mean:.1f}", ha="right", va="center",
                      fontsize=9.5, fontweight="bold", color="#555555")
        ax_score.text(i + 0.12, l_mean, f"{l_mean:.1f}", ha="left", va="center",
                      fontsize=9.5, fontweight="bold", color=bar_colors[i])
        # Strict zero-fraction annotation below each violin
        ax_score.text(i, -2.0, f"strict 0: {zero_frac:.1f}%", ha="center", va="top",
                      fontsize=8, color="#555555")
        ax_score.text(i, -3.4, f"n={len(u):,}", ha="center", va="top",
                      fontsize=8, color="gray")

    legend_handles = [
        Patch(facecolor=strict_col, alpha=0.60, label="Strict (official / HLE)"),
        Patch(facecolor="#999999", alpha=0.45, label="Lenient (score at failure)"),
    ]
    ax_score.legend(handles=legend_handles, fontsize=8, loc="upper left",
                    framealpha=0.9)

    ax_score.set_xticks(range(3))
    ax_score.set_xticklabels(labels, fontsize=11)
    ax_score.set_ylabel("Final Game Score", fontsize=11)
    ax_score.set_title("Game score by setting", fontsize=13, fontweight="bold")
    ax_score.set_xlim(-0.6, 2.6)
    ax_score.set_ylim(-5, 29)
    ax_score.axhline(25, color="gray", linewidth=0.5, linestyle="--", alpha=0.3)
    ax_score.text(2.5, 25.3, "Perfect score", fontsize=8, color="gray", ha="right")
    ax_score.spines["top"].set_visible(False)
    ax_score.spines["right"].set_visible(False)

    # --- Panel (b): 3-bar convention gap ---
    values = [gap_hh, gap_hai, gap_aa]
    n_vals = [len(hdf), len(haidf[haidf["subject_type"] == "human"]), len(adf)]

    bars = ax_bar.bar(range(3), values, color=bar_colors, width=0.6,
                      edgecolor="white", linewidth=0.5)

    for bar, val, n in zip(bars, values, n_vals):
        y = bar.get_height()
        va = "bottom" if y >= 0 else "top"
        offset = 1.2 if y >= 0 else -1.2
        ax_bar.text(bar.get_x() + bar.get_width() / 2, y + offset,
                    f"{val:+.1f} pp", ha="center", va=va,
                    fontsize=11, fontweight="bold", color=bar.get_facecolor())
        # Sample size below bar
        ax_bar.text(bar.get_x() + bar.get_width() / 2, -3.5,
                    f"n={n:,}", ha="center", va="top",
                    fontsize=8.5, color="gray")

    ax_bar.set_xticks(range(3))
    ax_bar.set_xticklabels(labels_human_plays, fontsize=11)
    ax_bar.set_ylabel("Convention Gap (pp)", fontsize=11)
    ax_bar.set_title("Convention gap by setting", fontsize=13, fontweight="bold")
    ax_bar.axhline(0, color="black", linewidth=0.5)
    ax_bar.spines["top"].set_visible(False)
    ax_bar.spines["right"].set_visible(False)
    ax_bar.set_ylim(-8, 38)

    # --- Panel (c): calibration curve ---
    bins = np.linspace(0, 1, 11)
    sources = [
        ("Human-Human", hdf, "#c44e52", "o"),
        ("Human-vs-AI", haidf[haidf["subject_type"] == "human"], "#9467bd", "D"),
        ("AI-AI", adf, "#4c72b0", "s"),
    ]

    ax_cal.plot([0, 100], [0, 100], "k--", alpha=0.4, label="Perfect calibration")

    for lbl, sdf, color, marker in sources:
        sdf = sdf.copy()
        sdf["bin"] = pd.cut(sdf["posterior_p_life_loss"], bins=bins,
                            include_lowest=True)
        grouped = sdf.groupby("bin", observed=True).agg(
            mean_pred=("posterior_p_life_loss", "mean"),
            mean_actual=("life_lost", "mean"),
            count=("life_lost", "count"),
        ).dropna()
        grouped = grouped[grouped["count"] >= 10]
        ax_cal.scatter(
            grouped["mean_pred"] * 100, grouped["mean_actual"] * 100,
            s=np.clip(grouped["count"], 50, 500),
            alpha=0.75, color=color, marker=marker,
            label=f"{lbl} (n={len(sdf):,})", zorder=5,
            edgecolors="white", linewidths=0.5,
        )

    ax_cal.set_xlabel("Predicted P(life lost) (%)", fontsize=11)
    ax_cal.set_ylabel("Actual life-loss rate (%)", fontsize=11)
    ax_cal.set_title("Calibration by risk level", fontsize=13, fontweight="bold")
    ax_cal.set_xlim(-5, 105)
    ax_cal.set_ylim(-5, 105)
    ax_cal.legend(fontsize=9, loc="upper left")

    fig.tight_layout()
    fig.savefig(out / "figure1_convention_gap_and_calibration.png", dpi=150,
                bbox_inches="tight")
    logger.info("Saved figure1_convention_gap_and_calibration.png")
    return fig


def plot_convention_gap_by_subject(
    human_df: pd.DataFrame,
    agent_df: pd.DataFrame,
    output_dir: Optional[Path] = None,
) -> plt.Figure:
    """Appendix figure: convention gap for each subject type (human + 7 AIs)."""
    out = ensure_output_dir(output_dir)

    def _gap_n(sdf):
        sdf = sdf.copy()
        if "life_lost" not in sdf.columns:
            sdf["life_lost"] = (~sdf["was_playable"]).astype(int)
        gap = (sdf["posterior_p_life_loss"].mean() - sdf["life_lost"].mean()) * 100
        return gap, len(sdf)

    hdf = human_df.copy()
    gap_hh, n_hh = _gap_n(hdf)

    agent_order = ["bergh", "outer", "iggi", "piers", "internal", "simple", "flawed"]
    ai_items = []
    for ak in agent_order:
        sub = agent_df[agent_df["subject_type"] == ak]
        if len(sub) == 0:
            continue
        gap, n = _gap_n(sub)
        ai_items.append((display_name(ak), gap, n))

    labels = [f"Human\n(hanab.live)\n(n={n_hh:,})"] + \
             [f"{name}\n(n={n:,})" for name, _, n in ai_items]
    values = [gap_hh] + [g for _, g, _ in ai_items]
    colors = ["#c44e52"] + ["#4c72b0"] * len(ai_items)

    fig, ax = plt.subplots(figsize=(14, 5))
    x = np.arange(len(labels))
    bars = ax.bar(x, values, color=colors, width=0.7,
                  edgecolor="white", linewidth=0.5)

    for bar, val in zip(bars, values):
        y = bar.get_height()
        va = "bottom" if y >= 0 else "top"
        offset = 0.8 if y >= 0 else -0.8
        ax.text(bar.get_x() + bar.get_width() / 2, y + offset,
                f"{val:+.1f}%", ha="center", va=va,
                fontsize=9, fontweight="bold", color=bar.get_facecolor())

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9, ha="center")
    ax.set_ylabel("Convention Gap (pp)", fontsize=12)
    ax.set_title("Convention Gap by Subject Type: Human vs AI Players",
                 fontsize=14)
    ax.axhline(0, color="black", linewidth=0.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Annotation for AI cluster
    mid_ai = 1 + len(ai_items) / 2
    ax.annotate(
        "AIs play based on\nliteral information only\n(gap ≈ 0)",
        xy=(mid_ai, 0), xytext=(mid_ai, 10),
        fontsize=9, color="#4c72b0",
        arrowprops=dict(arrowstyle="->", color="#4c72b0", lw=1.2),
        ha="center",
    )

    fig.tight_layout()
    fig.savefig(out / "convention_gap_by_subject.png", dpi=150,
                bbox_inches="tight")
    logger.info("Saved convention_gap_by_subject.png")
    return fig


def plot_three_source_calibration(
    human_df: pd.DataFrame,
    agent_df: pd.DataFrame,
    human_ai_df: pd.DataFrame,
    output_dir: Optional[Path] = None,
) -> plt.Figure:
    """Calibration curves for all three data sources on one plot."""
    out = ensure_output_dir(output_dir)

    fig, ax = plt.subplots(figsize=(9, 8))
    ax.plot([0, 100], [0, 100], "k--", alpha=0.4, label="Perfect calibration")

    bins = np.linspace(0, 1, 11)

    sources = [
        ("Human-Human", human_df, "#c44e52", "o"),
        ("Human-AI (human plays)", human_ai_df[human_ai_df["subject_type"] == "human"],
         "#9467bd", "D"),
        ("AI-AI", agent_df, "#4c72b0", "s"),
    ]

    for label, sdf, color, marker in sources:
        sdf = sdf.copy()
        sdf["life_lost"] = (~sdf["was_playable"]).astype(int)
        sdf["bin"] = pd.cut(sdf["posterior_p_life_loss"], bins=bins, include_lowest=True)
        grouped = sdf.groupby("bin", observed=True).agg(
            mean_pred=("posterior_p_life_loss", "mean"),
            mean_actual=("life_lost", "mean"),
            count=("life_lost", "count"),
        ).dropna()
        grouped = grouped[grouped["count"] >= 10]
        ax.scatter(
            grouped["mean_pred"] * 100, grouped["mean_actual"] * 100,
            s=np.clip(grouped["count"], 50, 500),
            alpha=0.75, color=color, marker=marker,
            label=f"{label} (n={len(sdf):,})", zorder=5,
            edgecolors="white", linewidths=0.5,
        )

    ax.set_xlabel("Predicted P(life lost) (%)", fontsize=12)
    ax.set_ylabel("Actual life-loss rate (%)", fontsize=12)
    ax.set_title("Calibration Across All Data Sources", fontsize=14)
    ax.set_xlim(-5, 105)
    ax.set_ylim(-5, 105)
    ax.legend(fontsize=10, loc="upper left")

    # Annotation
    ax.annotate(
        "Convention gap\n(human advantage)",
        xy=(65, 10), xytext=(35, 45),
        fontsize=10, color="#c44e52", fontweight="bold",
        arrowprops=dict(arrowstyle="->", color="#c44e52", lw=1.5),
        ha="center",
    )

    fig.tight_layout()
    fig.savefig(out / "crossphase_calibration.png", dpi=150)
    logger.info("Saved crossphase_calibration.png")
    return fig


def plot_convention_gap_hierarchy(
    human_df: pd.DataFrame,
    agent_df: pd.DataFrame,
    human_ai_df: pd.DataFrame,
    output_dir: Optional[Path] = None,
) -> plt.Figure:
    """Bar chart showing the three cognitive layers of convention gap."""
    out = ensure_output_dir(output_dir)

    # Compute gaps
    def _gap(sdf):
        sdf = sdf.copy()
        sdf["life_lost"] = (~sdf["was_playable"]).astype(int)
        return sdf["posterior_p_life_loss"].mean() - sdf["life_lost"].mean()

    hai = human_ai_df.copy()
    hai["life_lost"] = (~hai["was_playable"]).astype(int)

    gaps = {
        "AI-AI": _gap(agent_df),
        f"Human + {display_name('outer')}": _gap(hai[(hai["subject_type"] == "human") &
                                   (hai["partner_type"] == "outer")]),
        f"Human + {display_name('intentional')}": _gap(hai[(hai["subject_type"] == "human") &
                                         (hai["partner_type"] == "intentional")]),
        f"Human + {display_name('full')}": _gap(hai[(hai["subject_type"] == "human") &
                                  (hai["partner_type"] == "full")]),
        "Human-Human": _gap(human_df),
    }

    fig, ax = plt.subplots(figsize=(10, 6))
    labels = list(gaps.keys())
    values = list(gaps.values())
    colors = ["#4c72b0", "#d4a0a0", "#b07cb0", "#9467bd", "#c44e52"]

    bars = ax.barh(range(len(labels)), values, color=colors, height=0.6,
                   edgecolor="white", linewidth=0.5)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=11)
    ax.set_xlabel("Convention Gap (predicted - actual life-loss rate)", fontsize=12)
    ax.set_title("Three Cognitive Layers of Hanabi Information", fontsize=14)
    ax.axvline(0, color="black", linewidth=0.5)

    for bar, val in zip(bars, values):
        x = bar.get_width()
        offset = 0.005 if x >= 0 else -0.005
        ax.text(x + offset, bar.get_y() + bar.get_height() / 2,
                f"{val:+.3f}", va="center",
                ha="left" if x >= 0 else "right",
                fontsize=11, fontweight="bold")

    # Bracket annotations
    ax.annotate("", xy=(0.32, 4.4), xytext=(0.32, 0.6),
                arrowprops=dict(arrowstyle="<->", color="gray", lw=1.5))
    ax.text(0.33, 2.5, "35x\ndifference", fontsize=10, color="gray",
            va="center")

    fig.tight_layout()
    fig.savefig(out / "crossphase_convention_hierarchy.png", dpi=150)
    logger.info("Saved crossphase_convention_hierarchy.png")
    return fig


def plot_convention_gap_all_settings(
    human_df: pd.DataFrame,
    agent_df: pd.DataFrame,
    human_ai_df: pd.DataFrame,
    output_dir: Optional[Path] = None,
) -> plt.Figure:
    """Paper Figure 1: Convention gap across ALL settings in one wide bar chart.

    Three sections separated by dashed lines:
    - Red: Human-Human by pair type (E-E, E-I, I-I, B-I, B-B)
    - Purple: Human-vs-AI by AI partner (Full, Intentional, Outer)
    - Blue: AI-AI by agent (VanDenBergh, Outer, IGGI, Piers, Intentional, Simple, Full)
    """
    out = ensure_output_dir(output_dir)

    def _gap_n(sdf):
        sdf = sdf.copy()
        if "life_lost" not in sdf.columns:
            sdf["life_lost"] = (~sdf["was_playable"]).astype(int)
        gap = sdf["posterior_p_life_loss"].mean() - sdf["life_lost"].mean()
        return gap, len(sdf)

    # --- Human-Human by pair type ---
    # Ensure individual_skill and pair_type columns exist
    if "pair_type" not in human_df.columns:
        human_df = add_individual_skill_columns(human_df)

    hh_groups = []
    pair_order = [
        ("expert-expert", "Expert\nvs Expert"),
        ("expert-intermediate", "Expert\nvs Interm."),
        ("intermediate-intermediate", "Interm.\nvs Interm."),
        ("intermediate-beginner", "Interm.\nvs Beginner"),
        ("beginner-beginner", "Beginner\nvs Beginner"),
    ]
    for pair_key, pair_label in pair_order:
        sub = human_df[human_df["pair_type"] == pair_key]
        if len(sub) == 0:
            continue
        gap, n = _gap_n(sub)
        hh_groups.append((f"{pair_label}\n(n={n:,})", gap, n))

    # --- Human-vs-AI by partner (human plays only) ---
    hai_human = human_ai_df[human_ai_df["subject_type"] == "human"].copy()
    hai_groups = []
    for ai in ["full", "intentional", "outer"]:
        sub = hai_human[hai_human["partner_type"] == ai]
        gap, n = _gap_n(sub)
        hai_groups.append((f"Human\nvs {display_name(ai)}\n(n={n:,})", gap, n))

    # --- AI-AI by subject agent ---
    aa_groups = []
    agent_order = ["bergh", "outer", "iggi", "piers", "internal", "simple", "flawed"]
    for agent_key in agent_order:
        sub = agent_df[agent_df["subject_type"] == agent_key]
        if len(sub) == 0:
            continue
        gap, n = _gap_n(sub)
        aa_groups.append((f"{display_name(agent_key)}\n(n={n:,})", gap, n))

    # Combine all bars
    labels = [g[0] for g in hh_groups + hai_groups + aa_groups]
    values = [g[1] for g in hh_groups + hai_groups + aa_groups]

    n_hh = len(hh_groups)
    n_hai = len(hai_groups)
    n_aa = len(aa_groups)

    colors = (["#c44e52"] * n_hh +
              ["#9467bd"] * n_hai +
              ["#4c72b0"] * n_aa)

    fig, ax = plt.subplots(figsize=(18, 6))
    x = np.arange(len(labels))
    bars = ax.bar(x, [v * 100 for v in values], color=colors, width=0.7,
                  edgecolor="white", linewidth=0.5)

    # Value labels
    for bar, val in zip(bars, values):
        y = bar.get_height()
        va = "bottom" if y >= 0 else "top"
        offset = 0.8 if y >= 0 else -0.8
        color = bar.get_facecolor()
        ax.text(bar.get_x() + bar.get_width() / 2, y + offset,
                f"{val:+.1%}", ha="center", va=va,
                fontsize=9, fontweight="bold", color=color)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8, ha="center")
    ax.set_ylabel("Convention Gap (pp)", fontsize=12)
    ax.set_title("Convention Gap Across All Settings", fontsize=14)
    ax.axhline(0, color="black", linewidth=0.5)

    # Dashed separator lines
    sep1 = n_hh - 0.5
    sep2 = n_hh + n_hai - 0.5
    for sep in [sep1, sep2]:
        ax.axvline(sep, color="gray", linestyle="--", linewidth=1, alpha=0.5)

    # Source labels below x-axis using axes transform for y
    trans = ax.get_xaxis_transform()
    ax.text((n_hh - 1) / 2, -0.22, "Human-Human\n(hanab.live)",
            ha="center", fontsize=10, color="#c44e52", style="italic",
            transform=trans)
    ax.text(n_hh + (n_hai - 1) / 2, -0.22,
            "Human-vs-AI\n(HanabiData, human plays)",
            ha="center", fontsize=10, color="#9467bd", style="italic",
            transform=trans)
    ax.text(n_hh + n_hai + (n_aa - 1) / 2, -0.22, "AI-AI\n(HOAD)",
            ha="center", fontsize=10, color="#4c72b0", style="italic",
            transform=trans)

    fig.tight_layout()
    fig.subplots_adjust(bottom=0.28)
    fig.savefig(out / "convention_gap_all_settings.png", dpi=150)
    logger.info("Saved convention_gap_all_settings.png")
    return fig


def plot_predicted_vs_actual_all_settings(
    human_df: pd.DataFrame,
    agent_df: pd.DataFrame,
    human_ai_df: pd.DataFrame,
    output_dir: Optional[Path] = None,
) -> plt.Figure:
    """Paired-bar chart: mean predicted P(life loss) and actual life-loss rate.

    Same groupings as :func:`plot_convention_gap_all_settings` (Figure 1).
    The visual gap between the two bars *is* the convention gap.
    """
    out = ensure_output_dir(output_dir)

    def _stats(sdf):
        sdf = sdf.copy()
        if "life_lost" not in sdf.columns:
            sdf["life_lost"] = (~sdf["was_playable"]).astype(int)
        return sdf["posterior_p_life_loss"].mean(), sdf["life_lost"].mean(), len(sdf)

    # --- Human-Human by pair type ---
    if "pair_type" not in human_df.columns:
        human_df = add_individual_skill_columns(human_df)

    hh_groups = []
    pair_order = [
        ("expert-expert", "E-E"),
        ("expert-intermediate", "E-I"),
        ("intermediate-intermediate", "I-I"),
        ("intermediate-beginner", "I-B"),
        ("beginner-beginner", "B-B"),
    ]
    for pair_key, pair_label in pair_order:
        sub = human_df[human_df["pair_type"] == pair_key]
        if len(sub) == 0:
            continue
        pred, actual, n = _stats(sub)
        hh_groups.append((pair_label, pred, actual, n))

    # --- Human-vs-AI by partner (human plays only) ---
    hai_human = human_ai_df[human_ai_df["subject_type"] == "human"].copy()
    hai_groups = []
    for ai in ["full", "intentional", "outer"]:
        sub = hai_human[hai_human["partner_type"] == ai]
        pred, actual, n = _stats(sub)
        hai_groups.append((f"vs {display_name(ai)}", pred, actual, n))

    # --- AI-AI by subject agent ---
    aa_groups = []
    agent_order = ["bergh", "outer", "iggi", "piers", "internal", "simple", "flawed"]
    for agent_key in agent_order:
        sub = agent_df[agent_df["subject_type"] == agent_key]
        if len(sub) == 0:
            continue
        pred, actual, n = _stats(sub)
        aa_groups.append((display_name(agent_key), pred, actual, n))

    all_groups = hh_groups + hai_groups + aa_groups
    labels = [g[0] for g in all_groups]
    preds = [g[1] * 100 for g in all_groups]
    actuals = [g[2] * 100 for g in all_groups]
    ns = [g[3] for g in all_groups]

    n_hh = len(hh_groups)
    n_hai = len(hai_groups)
    n_aa = len(aa_groups)

    fig, ax = plt.subplots(figsize=(18, 7))
    x = np.arange(len(labels))
    width = 0.35

    bars_pred = ax.bar(x - width / 2, preds, width, label="Mean predicted P(life loss)",
                       color="#636363", edgecolor="white", linewidth=0.5)
    # Color actual-loss bars by section
    actual_colors = (["#c44e52"] * n_hh + ["#9467bd"] * n_hai + ["#4c72b0"] * n_aa)
    bars_actual = ax.bar(x + width / 2, actuals, width, label="Actual life-loss rate",
                         color=actual_colors, edgecolor="white", linewidth=0.5)

    # Value labels on predicted bars
    for bar, val in zip(bars_pred, preds):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                f"{val:.1f}", ha="center", va="bottom", fontsize=7.5, color="#636363")

    # Value labels on actual bars
    for bar, val, clr in zip(bars_actual, actuals, actual_colors):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                f"{val:.1f}", ha="center", va="bottom", fontsize=7.5, color=clr,
                fontweight="bold")

    # Convention-gap annotation arrows between bar pairs
    for i, (p, a) in enumerate(zip(preds, actuals)):
        gap_pp = p - a
        if abs(gap_pp) > 2:
            mid_x = x[i]
            ax.annotate("", xy=(mid_x, a + 0.3), xytext=(mid_x, p - 0.3),
                        arrowprops=dict(arrowstyle="<->", color="gray", lw=0.8,
                                        shrinkA=0, shrinkB=0))
            ax.text(mid_x, (p + a) / 2, f"{gap_pp:+.0f}",
                    ha="center", va="center", fontsize=7, color="gray",
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.8))

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9, ha="center")
    ax.set_ylabel("Rate (%)", fontsize=12)
    ax.set_title("Predicted vs Actual Life-Loss Rate Across All Settings", fontsize=14)
    ax.legend(fontsize=10, loc="upper left")

    # Section separators
    sep1 = n_hh - 0.5
    sep2 = n_hh + n_hai - 0.5
    for sep in [sep1, sep2]:
        ax.axvline(sep, color="gray", linestyle="--", linewidth=1, alpha=0.5)

    # Section labels
    trans = ax.get_xaxis_transform()
    ax.text((n_hh - 1) / 2, -0.12, "Human-Human\n(hanab.live)",
            ha="center", fontsize=10, color="#c44e52", style="italic",
            transform=trans)
    ax.text(n_hh + (n_hai - 1) / 2, -0.12,
            "Human-vs-AI\n(HanabiData)",
            ha="center", fontsize=10, color="#9467bd", style="italic",
            transform=trans)
    ax.text(n_hh + n_hai + (n_aa - 1) / 2, -0.12, "AI-AI\n(HOAD)",
            ha="center", fontsize=10, color="#4c72b0", style="italic",
            transform=trans)

    fig.tight_layout()
    fig.subplots_adjust(bottom=0.18)
    fig.savefig(out / "predicted_vs_actual_all_settings.png", dpi=150)
    logger.info("Saved predicted_vs_actual_all_settings.png")
    return fig


def plot_game_scores_all_settings(
    human_df: pd.DataFrame,
    agent_df: pd.DataFrame,
    human_ai_df: pd.DataFrame,
    output_dir: Optional[Path] = None,
) -> plt.Figure:
    """Bar chart of mean final game scores across all 15 settings.

    Same groupings as Figure 1:
    - Human-Human by pair type (E-E, E-I, I-I, I-B, B-B)
    - Human-vs-AI by partner (Full, Intentional, Outer)
    - AI-AI by agent (VanDenBergh, Outer, IGGI, Piers, Intentional, Simple, Full)
    """
    out = ensure_output_dir(output_dir)

    def _score_stats(sdf):
        """Return (mean_score, std_score, n_games) from play records."""
        game_scores = sdf.groupby("game_key")["final_score"].first()
        return game_scores.mean(), game_scores.std(), len(game_scores)

    # --- Human-Human by pair type ---
    if "pair_type" not in human_df.columns:
        human_df = add_individual_skill_columns(human_df)

    hh_groups = []
    pair_order = [
        ("expert-expert", "E-E"),
        ("expert-intermediate", "E-I"),
        ("intermediate-intermediate", "I-I"),
        ("intermediate-beginner", "I-B"),
        ("beginner-beginner", "B-B"),
    ]
    for pair_key, pair_label in pair_order:
        sub = human_df[human_df["pair_type"] == pair_key]
        if len(sub) == 0:
            continue
        mean_s, std_s, n_g = _score_stats(sub)
        hh_groups.append((pair_label, mean_s, std_s, n_g))

    # --- Human-vs-AI by partner (all plays, not just human's) ---
    hai_groups = []
    for ai in ["full", "intentional", "outer"]:
        sub = human_ai_df[human_ai_df["partner_type"] == ai]
        if len(sub) == 0:
            continue
        mean_s, std_s, n_g = _score_stats(sub)
        hai_groups.append((f"vs {display_name(ai)}", mean_s, std_s, n_g))

    # --- AI-AI by agent pair (use subject as grouping key) ---
    # game_id is shared seed across partner types, so group by (partner_type, game_id)
    def _aa_score_stats(sdf):
        game_scores = sdf.groupby("game_key")["final_score"].first()
        return game_scores.mean(), game_scores.std(), len(game_scores)

    aa_groups = []
    agent_order = ["bergh", "outer", "iggi", "piers", "internal", "simple", "flawed"]
    # Unique-game unit: assign each of the 4,900 HOAD games to the first-named
    # agent of its pairing file (verified to move first); 700 games per agent.
    pair = agent_df["game_key"].str.split(":").str[0]
    first_mover = pair.str.split("_vs_").str[0]
    for agent_key in agent_order:
        sub = agent_df[first_mover == agent_key]          # 700 games per agent
        if len(sub) == 0:
            continue
        mean_s, std_s, n_g = _aa_score_stats(sub)
        aa_groups.append((display_name(agent_key), mean_s, std_s, n_g))

    all_groups = hh_groups + hai_groups + aa_groups
    labels = [g[0] for g in all_groups]
    means = [g[1] for g in all_groups]
    stds = [g[2] for g in all_groups]
    n_games = [g[3] for g in all_groups]

    n_hh = len(hh_groups)
    n_hai = len(hai_groups)
    n_aa = len(aa_groups)

    # Bar colors by section
    colors = ["#c44e52"] * n_hh + ["#9467bd"] * n_hai + ["#4c72b0"] * n_aa

    fig, ax = plt.subplots(figsize=(18, 7))
    x = np.arange(len(labels))
    bars = ax.bar(x, means, width=0.6, color=colors, edgecolor="white", linewidth=0.5)

    # Error bars (standard deviation)
    ax.errorbar(x, means, yerr=stds, fmt="none", ecolor="gray", elinewidth=1,
                capsize=3, capthick=1, alpha=0.6)

    # Value labels
    for bar, m, n_g in zip(bars, means, n_games):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                f"{m:.1f}", ha="center", va="bottom", fontsize=9, fontweight="bold")
        ax.text(bar.get_x() + bar.get_width() / 2, -1.2,
                f"n={n_g}", ha="center", va="top", fontsize=7, color="gray")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9, ha="center")
    ax.set_ylabel("Mean Final Game Score", fontsize=12)
    ax.set_ylim(0, 27)
    ax.axhline(25, color="gray", linestyle=":", linewidth=0.8, alpha=0.5)
    ax.text(len(labels) - 0.5, 25.3, "Perfect score = 25", fontsize=8,
            ha="right", color="gray", style="italic")
    ax.set_title("Mean Final Game Score Across All Settings", fontsize=14)

    # Section separators
    sep1 = n_hh - 0.5
    sep2 = n_hh + n_hai - 0.5
    for sep in [sep1, sep2]:
        ax.axvline(sep, color="gray", linestyle="--", linewidth=1, alpha=0.5)

    # Section labels
    trans = ax.get_xaxis_transform()
    ax.text((n_hh - 1) / 2, -0.12, "Human-Human\n(hanab.live)",
            ha="center", fontsize=10, color="#c44e52", style="italic",
            transform=trans)
    ax.text(n_hh + (n_hai - 1) / 2, -0.12,
            "Human-vs-AI\n(HanabiData)",
            ha="center", fontsize=10, color="#9467bd", style="italic",
            transform=trans)
    ax.text(n_hh + n_hai + (n_aa - 1) / 2, -0.12, "AI-AI\n(HOAD)",
            ha="center", fontsize=10, color="#4c72b0", style="italic",
            transform=trans)

    fig.tight_layout()
    fig.subplots_adjust(bottom=0.18)
    fig.savefig(out / "game_scores_all_settings.png", dpi=150)
    logger.info("Saved game_scores_all_settings.png")
    return fig


def plot_trustworthiness_inversion_paper(
    human_ai_df: pd.DataFrame,
    agent_df: pd.DataFrame,
    output_dir: Optional[Path] = None,
) -> plt.Figure:
    """Paper Figure 3: Paired AI-AI (light) + Human-AI (dark) bars.

    Two panels: Player Loss (left) and Partner Loss (right).
    Each agent gets two bars: light=AI-AI, dark=Human-AI.
    The Partner Loss panel shows the inversion annotation.
    """
    out = ensure_output_dir(output_dir)

    hai = human_ai_df.copy()
    if "life_lost" not in hai.columns:
        hai["life_lost"] = (~hai["was_playable"]).astype(int)

    agent_aa = agent_df.copy()
    if "life_lost" not in agent_aa.columns:
        agent_aa["life_lost"] = (~agent_aa["was_playable"]).astype(int)

    # Agents with valid cross-dataset mapping (both Osawa-derived)
    cross_agents = ["outer", "intentional"]
    hai_to_aa = {"outer": "outer", "intentional": "internal"}
    # Full appears only in HanabiData (no HOAD counterpart)
    hai_only_agents = ["full"]
    all_hai_agents = cross_agents + hai_only_agents

    # --- Compute Player Loss (AI's own failure rate) ---
    player_loss_aa = {}
    player_loss_hai = {}
    for a in all_hai_agents:
        # Human-AI: this agent as subject (AI plays)
        sub_hai = hai[hai["subject_type"] == a]
        player_loss_hai[a] = sub_hai["life_lost"].mean() * 100 if len(sub_hai) > 0 else 0
    for a in cross_agents:
        aa_key = hai_to_aa[a]
        sub_aa = agent_aa[agent_aa["subject_type"] == aa_key]
        player_loss_aa[a] = sub_aa["life_lost"].mean() * 100 if len(sub_aa) > 0 else 0

    # --- Compute Partner Loss (partner's failure rate) ---
    partner_loss_aa = {}
    partner_loss_hai = {}
    for a in all_hai_agents:
        sub_hai = hai[(hai["subject_type"] == "human") & (hai["partner_type"] == a)]
        partner_loss_hai[a] = sub_hai["life_lost"].mean() * 100 if len(sub_hai) > 0 else 0
    for a in cross_agents:
        aa_key = hai_to_aa[a]
        sub_aa = agent_aa[(agent_aa["partner_type"] == aa_key) &
                          (agent_aa["subject_type"] != aa_key)]
        partner_loss_aa[a] = sub_aa["life_lost"].mean() * 100 if len(sub_aa) > 0 else 0

    # Colors per agent
    agent_colors_light = {
        "outer": "#a8d5a2", "intentional": "#a8c4e0", "full": "#f0a0a0",
    }
    agent_colors_dark = {
        "outer": "#55a868", "intentional": "#4c72b0", "full": "#c44e52",
    }

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    x_cross = np.arange(len(cross_agents))
    x_all = np.arange(len(all_hai_agents))
    width = 0.35

    # --- Panel 1: Player Loss ---
    ax = axes[0]
    # Cross-dataset agents: paired bars
    aa_vals = [player_loss_aa[a] for a in cross_agents]
    hai_vals_cross = [player_loss_hai[a] for a in cross_agents]
    light_colors = [agent_colors_light[a] for a in cross_agents]
    dark_colors = [agent_colors_dark[a] for a in cross_agents]

    bars_aa = ax.bar(x_cross - width / 2, aa_vals, width, color=light_colors,
                     edgecolor="white", linewidth=0.5, label="AI-AI (HOAD)")
    bars_hai = ax.bar(x_cross + width / 2, hai_vals_cross, width, color=dark_colors,
                      edgecolor="white", linewidth=0.5, label="Human-AI (HanabiData)")

    for bar, val in zip(bars_aa, aa_vals):
        if val > 0.5:
            ax.text(bar.get_x() + bar.get_width() / 2, val + 0.5,
                    f"{val:.1f}%", ha="center", va="bottom", fontsize=9, color="gray")
    for bar, val in zip(bars_hai, hai_vals_cross):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.5,
                f"{val:.2f}%" if val < 1 else f"{val:.1f}%",
                ha="center", va="bottom", fontsize=9, fontweight="bold")

    # HanabiData-only agents: single dark bar
    for j, agent in enumerate(hai_only_agents):
        x_pos = len(cross_agents) + j
        val = player_loss_hai[agent]
        ax.bar(x_pos, val, width, color=agent_colors_dark[agent],
               edgecolor="white", linewidth=0.5, hatch="//", alpha=0.9)
        ax.text(x_pos, val + 0.5, f"{val:.1f}%",
                ha="center", va="bottom", fontsize=9, fontweight="bold")

    ax.set_xticks(x_all)
    ax.set_xticklabels([display_name(a) for a in all_hai_agents], fontsize=11)
    ax.set_ylabel("Agent's Own Life-Loss Rate (%)", fontsize=11)
    ax.set_title("Player Loss", fontsize=13)
    ax.legend(fontsize=10)

    # --- Panel 2: Partner Loss ---
    ax = axes[1]
    aa_vals = [partner_loss_aa[a] for a in cross_agents]
    hai_vals_cross = [partner_loss_hai[a] for a in cross_agents]

    bars_aa = ax.bar(x_cross - width / 2, aa_vals, width,
                     color=[agent_colors_light[a] for a in cross_agents],
                     edgecolor="white", linewidth=0.5, label="AI-AI (HOAD)")
    bars_hai = ax.bar(x_cross + width / 2, hai_vals_cross, width,
                      color=[agent_colors_dark[a] for a in cross_agents],
                      edgecolor="white", linewidth=0.5, label="Human-AI (HanabiData)")

    for bar, val in zip(bars_aa, aa_vals):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.5,
                f"{val:.1f}%", ha="center", va="bottom", fontsize=9, color="gray")
    for bar, val in zip(bars_hai, hai_vals_cross):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 0.5,
                f"{val:.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold")

    # HanabiData-only agents: single dark bar
    for j, agent in enumerate(hai_only_agents):
        x_pos = len(cross_agents) + j
        val = partner_loss_hai[agent]
        ax.bar(x_pos, val, width, color=agent_colors_dark[agent],
               edgecolor="white", linewidth=0.5, hatch="//", alpha=0.9)
        ax.text(x_pos, val + 0.5, f"{val:.1f}%",
                ha="center", va="bottom", fontsize=9, fontweight="bold")

    ax.set_xticks(x_all)
    ax.set_xticklabels([display_name(a) for a in all_hai_agents], fontsize=11)
    ax.set_ylabel("Partner's Life-Loss Rate (%)", fontsize=11)
    ax.set_title("Partner Loss", fontsize=13)
    ax.legend(fontsize=10)

    # Annotation: inversion for cross-dataset agents
    ax.annotate("Rankings reverse\n(Outer ↔ Intentional)",
                xy=(0.35, 0.75), xycoords="axes fraction",
                fontsize=10, color="red", fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                          edgecolor="red", alpha=0.8))

    fig.suptitle("Trustworthiness: AI-AI rankings do not transfer to human partnerships",
                 fontsize=14, y=1.02)
    fig.tight_layout()
    fig.savefig(out / "trustworthiness_inversion_v3.png", dpi=150,
                bbox_inches="tight")
    logger.info("Saved trustworthiness_inversion_v3.png")
    return fig


def plot_trustworthiness_inversion(
    human_ai_df: pd.DataFrame,
    agent_df: pd.DataFrame = None,
    output_dir: Optional[Path] = None,
) -> plt.Figure:
    """Value slopegraph: lines connect AI-AI value to Human-AI value.

    Denominators (AI-AI): Player Loss is over the agent's own plays in all
    1,300 games it participates in; Partner Loss is over the partner's plays
    in the 1,200 non-mirror games (Flawed's partners rarely play: n = 324).

    Y-axis shows actual life-loss rate (%).
    Parallel lines = rankings preserved (Player Loss).
    Crossing lines = rankings inverted (Partner Loss).
    """
    out = ensure_output_dir(output_dir)

    hai = human_ai_df.copy()
    if "life_lost" not in hai.columns:
        hai["life_lost"] = (~hai["was_playable"]).astype(int)

    if agent_df is not None:
        agent_aa = agent_df.copy()
        if "life_lost" not in agent_aa.columns:
            agent_aa["life_lost"] = (~agent_aa["was_playable"]).astype(int)
    else:
        agent_aa = None

    # Agents with valid cross-dataset mapping (both Osawa-derived)
    cross_agents = ["outer", "intentional"]
    hai_to_aa = {"outer": "outer", "intentional": "internal"}
    # Full appears only in HanabiData (no HOAD counterpart)
    hai_only_agents = ["full"]
    agent_colors = {
        "outer": "#55a868", "intentional": "#4c72b0", "full": "#c44e52",
    }
    all_hai_agents = cross_agents + hai_only_agents

    # --- Compute Partner Loss ---
    partner_loss_aa, partner_loss_hai = {}, {}
    for a in all_hai_agents:
        sub_hai = hai[(hai["subject_type"] == "human") & (hai["partner_type"] == a)]
        partner_loss_hai[a] = sub_hai["life_lost"].mean() * 100 if len(sub_hai) > 0 else 0
    for a in cross_agents:
        if agent_aa is not None:
            aa_key = hai_to_aa[a]
            sub_aa = agent_aa[(agent_aa["partner_type"] == aa_key) &
                              (agent_aa["subject_type"] != aa_key)]
            partner_loss_aa[a] = sub_aa["life_lost"].mean() * 100 if len(sub_aa) > 0 else 0
        else:
            partner_loss_aa[a] = 0

    # --- Draw single-panel Partner Loss slopegraph ---
    fig, ax = plt.subplots(1, 1, figsize=(7, 5))

    x_left, x_right = 0, 1

    def _nudge_labels(vals_with_idx, min_gap_pct):
        """Nudge y-offsets to prevent label overlap."""
        sorted_items = sorted(vals_with_idx, key=lambda x: x[0])
        offsets = [0.0] * len(vals_with_idx)
        for k in range(1, len(sorted_items)):
            val_cur, idx_cur = sorted_items[k]
            val_prev, idx_prev = sorted_items[k - 1]
            actual_gap = (val_cur + offsets[idx_cur]) - (val_prev + offsets[idx_prev])
            if actual_gap < min_gap_pct:
                nudge = (min_gap_pct - actual_gap) / 2
                offsets[idx_prev] -= nudge
                offsets[idx_cur] += nudge
        return offsets

    # --- Cross-dataset agents: lines connecting AI-AI to Human-AI ---
    aa_vals = [partner_loss_aa[a] for a in cross_agents]
    hai_vals_cross = [partner_loss_hai[a] for a in cross_agents]

    all_left = [(aa_vals[i], i) for i in range(len(cross_agents))]
    all_right_vals = [partner_loss_hai[a] for a in all_hai_agents]
    all_right = [(all_right_vals[i], i) for i in range(len(all_hai_agents))]

    all_y = aa_vals + all_right_vals
    y_range = max(all_y) - min(min(all_y), 0)
    min_gap = max(y_range * 0.06, 1.5)

    left_offsets = _nudge_labels(all_left, min_gap)
    right_offsets = _nudge_labels(all_right, min_gap)

    for i, agent in enumerate(cross_agents):
        color = agent_colors[agent]

        ax.plot([x_left, x_right], [aa_vals[i], hai_vals_cross[i]],
                color=color, linewidth=3, marker="o", markersize=12,
                markerfacecolor=color, markeredgecolor="white",
                markeredgewidth=2, zorder=3)

        # Left label (AI-AI value)
        fmt_l = f"{aa_vals[i]:.1f}%"
        ax.text(x_left - 0.06, aa_vals[i] + left_offsets[i],
                f"{display_name(agent)}  {fmt_l}",
                ha="right", va="center", fontsize=11, color=color,
                fontweight="bold")

        # Right label (Human-AI value)
        fmt_r = f"{hai_vals_cross[i]:.1f}%"
        ax.text(x_right + 0.06, hai_vals_cross[i] + right_offsets[i],
                f"{fmt_r}  {display_name(agent)}",
                ha="left", va="center", fontsize=11, color=color,
                fontweight="bold")

    # --- HanabiData-only agents: point on right side only ---
    for j, agent in enumerate(hai_only_agents):
        color = agent_colors[agent]
        idx_in_right = len(cross_agents) + j
        hai_val = partner_loss_hai[agent]

        ax.plot(x_right, hai_val,
                marker="D", markersize=12, color=color,
                markerfacecolor=color, markeredgecolor="white",
                markeredgewidth=2, zorder=3)

        # Right label
        fmt_r = f"{hai_val:.1f}%"
        ax.text(x_right + 0.06, hai_val + right_offsets[idx_in_right],
                f"{fmt_r}  {display_name(agent)} (HanabiData only)",
                ha="left", va="center", fontsize=11, color=color,
                fontweight="bold")

    ax.set_xlim(-0.45, 1.55)
    ax.set_xticks([x_left, x_right])
    ax.set_xticklabels(["AI partner plays\nwith AI (HOAD)",
                         "Human partner plays\nwith AI (HanabiData)"],
                        fontsize=12, fontweight="bold")
    ax.set_ylabel("Partner Loss Rate (%)", fontsize=11)
    ax.set_title("Partner Loss: AI-vs-AI rankings do not transfer\n"
                 "to human partnerships",
                 fontsize=13, fontweight="bold", pad=12)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", alpha=0.25, linestyle="--")

    fig.tight_layout()
    fig.savefig(out / "crossphase_trustworthiness_inversion_v3.png", dpi=150,
                bbox_inches="tight")
    logger.info("Saved crossphase_trustworthiness_inversion_v3.png")
    return fig


def plot_hint_count_convention_gap(
    human_df: pd.DataFrame,
    agent_df: pd.DataFrame,
    human_ai_df: pd.DataFrame,
    output_dir: Optional[Path] = None,
) -> plt.Figure:
    """Convention gap by hint count across all three sources."""
    out = ensure_output_dir(output_dir)

    fig, axes = plt.subplots(1, 2, figsize=(15, 6))

    def _hint_gap(sdf, hint_count):
        sdf = sdf.copy()
        sdf["life_lost"] = (~sdf["was_playable"]).astype(int)
        if hint_count == "2+":
            sub = sdf[sdf["hints_on_card"] >= 2]
        else:
            sub = sdf[sdf["hints_on_card"] == hint_count]
        if len(sub) == 0:
            return 0.0, 0
        gap = sub["posterior_p_life_loss"].mean() - sub["life_lost"].mean()
        return gap, len(sub)

    # Panel 1: Convention gap by hint count across sources
    ax = axes[0]
    hint_labels = [0, 1, "2+"]
    source_labels = ["Human-Human", "Human-AI\n(human plays)", "AI-AI"]
    source_dfs = [
        human_df,
        human_ai_df[human_ai_df["subject_type"] == "human"],
        agent_df,
    ]
    source_colors = ["#c44e52", "#9467bd", "#4c72b0"]

    x = np.arange(len(hint_labels))
    width = 0.25
    for i, (label, sdf, color) in enumerate(zip(source_labels, source_dfs, source_colors)):
        gaps = []
        for h in hint_labels:
            g, _ = _hint_gap(sdf, h)
            gaps.append(g)
        ax.bar(x + i * width - width, gaps, width, label=label, color=color,
               edgecolor="white")

    ax.set_xticks(x)
    ax.set_xticklabels(["0 hints", "1 hint", "2+ hints"], fontsize=11)
    ax.set_ylabel("Convention Gap", fontsize=11)
    ax.set_title("Convention Gap by Hint Count", fontsize=13)
    ax.axhline(0, color="black", linewidth=0.5)
    ax.legend(fontsize=9)

    # Panel 2: 1-hint gap by AI partner type
    ax = axes[1]
    hai = human_ai_df.copy()
    hai["life_lost"] = (~hai["was_playable"]).astype(int)
    human_plays = hai[hai["subject_type"] == "human"]

    ai_types = ["full", "intentional", "outer"]
    ai_colors = ["#c44e52", "#4c72b0", "#55a868"]
    gaps_1hint = []
    ns = []
    for ai_type in ai_types:
        sub = human_plays[(human_plays["partner_type"] == ai_type) &
                          (human_plays["hints_on_card"] == 1)]
        if len(sub) > 0:
            gap = sub["posterior_p_life_loss"].mean() - sub["life_lost"].mean()
            gaps_1hint.append(gap)
            ns.append(len(sub))
        else:
            gaps_1hint.append(0)
            ns.append(0)

    # Add human-human baseline
    hh_1hint = human_df[human_df["hints_on_card"] == 1].copy()
    hh_1hint["life_lost"] = (~hh_1hint["was_playable"]).astype(int)
    hh_gap = hh_1hint["posterior_p_life_loss"].mean() - hh_1hint["life_lost"].mean()

    all_labels = ai_types + ["human-human"]
    all_gaps = gaps_1hint + [hh_gap]
    all_colors = ai_colors + ["#dd8452"]

    bars = ax.bar(range(len(all_labels)), all_gaps, color=all_colors,
                  edgecolor="white", width=0.6)
    ax.set_xticks(range(len(all_labels)))
    ax.set_xticklabels([f"vs {display_name(l)}" if l != "human-human" else l for l in all_labels],
                       fontsize=10)
    ax.set_ylabel("Convention Gap (1-hint plays)", fontsize=11)
    ax.set_title("1-Hint Convention Gap by Partner Type", fontsize=13)
    ax.axhline(0, color="black", linewidth=0.5)
    for bar, val in zip(bars, all_gaps):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.005,
                f"{val:+.3f}", ha="center", fontsize=10, fontweight="bold")

    fig.tight_layout()
    fig.savefig(out / "crossphase_hint_convention_gap.png", dpi=150)
    logger.info("Saved crossphase_hint_convention_gap.png")
    return fig


def plot_game_phase_dynamics(
    human_df: pd.DataFrame,
    agent_df: pd.DataFrame,
    human_ai_df: pd.DataFrame,
    output_dir: Optional[Path] = None,
) -> plt.Figure:
    """Convention gap across early/mid/late game for all sources."""
    out = ensure_output_dir(output_dir)

    fig, axes = plt.subplots(1, 2, figsize=(15, 6))

    def _phase_gaps(sdf, phases=("early", "mid", "late")):
        sdf = sdf.copy()
        sdf["life_lost"] = (~sdf["was_playable"]).astype(int)
        sdf["game_phase"] = pd.cut(
            sdf["turn"], bins=[-1, 15, 35, 200],
            labels=["early", "mid", "late"], right=True,
        )
        result = {}
        for phase in phases:
            sub = sdf[sdf["game_phase"] == phase]
            if len(sub) > 0:
                result[phase] = sub["posterior_p_life_loss"].mean() - sub["life_lost"].mean()
            else:
                result[phase] = 0.0
        return result

    # Panel 1: Convention gap by phase across sources
    ax = axes[0]
    phases = ["early", "mid", "late"]
    sources = [
        ("Human-Human", human_df, "#c44e52"),
        ("Human-AI (human)", human_ai_df[human_ai_df["subject_type"] == "human"], "#9467bd"),
        ("AI-AI", agent_df, "#4c72b0"),
    ]

    x = np.arange(len(phases))
    width = 0.25
    for i, (label, sdf, color) in enumerate(sources):
        gaps = _phase_gaps(sdf)
        vals = [gaps[p] for p in phases]
        ax.bar(x + i * width - width, vals, width, label=label, color=color,
               edgecolor="white")

    ax.set_xticks(x)
    ax.set_xticklabels(["Early\n(turns 1-15)", "Mid\n(turns 16-35)",
                        "Late\n(turns 36+)"], fontsize=10)
    ax.set_ylabel("Convention Gap", fontsize=11)
    ax.set_title("Convention Gap by Game Phase", fontsize=13)
    ax.axhline(0, color="black", linewidth=0.5)
    ax.legend(fontsize=9)

    # Panel 2: Phase gaps by AI partner type
    ax = axes[1]
    hai = human_ai_df.copy()
    hai["life_lost"] = (~hai["was_playable"]).astype(int)
    human_plays = hai[hai["subject_type"] == "human"]

    ai_types = ["full", "intentional", "outer"]
    ai_colors = ["#c44e52", "#4c72b0", "#55a868"]

    for i, (ai_type, color) in enumerate(zip(ai_types, ai_colors)):
        sub = human_plays[human_plays["partner_type"] == ai_type]
        gaps = _phase_gaps(sub)
        vals = [gaps[p] for p in phases]
        ax.bar(x + i * width - width, vals, width, label=f"vs {display_name(ai_type)}",
               color=color, edgecolor="white")

    ax.set_xticks(x)
    ax.set_xticklabels(["Early\n(turns 1-15)", "Mid\n(turns 16-35)",
                        "Late\n(turns 36+)"], fontsize=10)
    ax.set_ylabel("Convention Gap", fontsize=11)
    ax.set_title("Human Convention Gap by AI Partner + Phase", fontsize=13)
    ax.axhline(0, color="black", linewidth=0.5)
    ax.legend(fontsize=9)

    fig.tight_layout()
    fig.savefig(out / "crossphase_game_phase.png", dpi=150)
    logger.info("Saved crossphase_game_phase.png")
    return fig


def plot_zero_hint_comparison(
    human_df: pd.DataFrame,
    agent_df: pd.DataFrame,
    human_ai_df: pd.DataFrame,
    output_dir: Optional[Path] = None,
) -> plt.Figure:
    """Zero-hint play success rates across all settings."""
    out = ensure_output_dir(output_dir)

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # Panel 1: 0-hint success rate across settings
    ax = axes[0]
    settings = []

    for label, sdf, color in [
        ("Human-Human", human_df, "#c44e52"),
        (f"Human+{display_name('full')}", human_ai_df[(human_ai_df["subject_type"] == "human") &
                                    (human_ai_df["partner_type"] == "full")], "#9467bd"),
        (f"Human+{display_name('intentional')}", human_ai_df[(human_ai_df["subject_type"] == "human") &
                                           (human_ai_df["partner_type"] == "intentional")],
         "#b07cb0"),
        (f"Human+{display_name('outer')}", human_ai_df[(human_ai_df["subject_type"] == "human") &
                                     (human_ai_df["partner_type"] == "outer")], "#d4a0a0"),
        ("AI-AI", agent_df, "#4c72b0"),
    ]:
        sub = sdf[sdf["hints_on_card"] == 0]
        if len(sub) > 0:
            success = sub["was_playable"].mean() * 100
            n = len(sub)
            settings.append((label, success, n, color))

    labels = [s[0] for s in settings]
    vals = [s[1] for s in settings]
    ns = [s[2] for s in settings]
    colors = [s[3] for s in settings]

    bars = ax.bar(range(len(labels)), vals, color=colors, edgecolor="white",
                  width=0.6)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=9, rotation=15, ha="right")
    ax.set_ylabel("Success Rate (%)", fontsize=11)
    ax.set_title("Zero-Hint Play Success Rate", fontsize=13)
    for bar, val, n in zip(bars, vals, ns):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                f"{val:.1f}%\n(n={n})", ha="center", fontsize=9)
    ax.set_ylim(0, 100)

    # Panel 2: 0-hint success by skill level (human-human only)
    ax = axes[1]
    hh = human_df.copy()
    if "individual_skill" not in hh.columns:
        hh = add_individual_skill_columns(hh)
    hh["life_lost"] = (~hh["was_playable"]).astype(int)
    zero_hint_hh = hh[hh["hints_on_card"] == 0]

    skill_order = ["beginner", "intermediate", "expert"]
    skill_colors = ["#dd8452", "#4c72b0", "#55a868"]
    skill_vals = []
    skill_ns = []
    for skill in skill_order:
        sub = zero_hint_hh[zero_hint_hh["individual_skill"] == skill]
        if len(sub) > 0:
            skill_vals.append(sub["was_playable"].mean() * 100)
            skill_ns.append(len(sub))
        else:
            skill_vals.append(0)
            skill_ns.append(0)

    bars = ax.bar(range(len(skill_order)), skill_vals, color=skill_colors,
                  edgecolor="white", width=0.5)
    ax.set_xticks(range(len(skill_order)))
    ax.set_xticklabels(skill_order, fontsize=11)
    ax.set_ylabel("Success Rate (%)", fontsize=11)
    ax.set_title("Zero-Hint Success by Skill Level (Human-Human)", fontsize=13)
    for bar, val, n in zip(bars, skill_vals, skill_ns):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                f"{val:.0f}%\n(n={n})", ha="center", fontsize=10, fontweight="bold")
    ax.set_ylim(0, 100)

    fig.tight_layout()
    fig.savefig(out / "crossphase_zero_hint.png", dpi=150)
    logger.info("Saved crossphase_zero_hint.png")
    return fig


def plot_ai_partner_comparison(
    human_ai_df: pd.DataFrame,
    output_dir: Optional[Path] = None,
) -> plt.Figure:
    """Comprehensive AI partner comparison: multiple metrics side by side."""
    out = ensure_output_dir(output_dir)

    hai = human_ai_df.copy()
    hai["life_lost"] = (~hai["was_playable"]).astype(int)

    ai_types = ["full", "intentional", "outer"]
    ai_colors = {"full": "#c44e52", "intentional": "#4c72b0", "outer": "#55a868"}

    # Compute metrics
    metrics = {}
    for ai_type in ai_types:
        # AI as player
        ai_plays = hai[hai["subject_type"] == ai_type]
        ai_loss = ai_plays["life_lost"].mean() * 100 if len(ai_plays) > 0 else 0

        # Human plays with this AI
        human_plays = hai[(hai["subject_type"] == "human") &
                          (hai["partner_type"] == ai_type)]
        h_loss = human_plays["life_lost"].mean() * 100 if len(human_plays) > 0 else 0
        h_gap = (human_plays["posterior_p_life_loss"].mean() -
                 human_plays["life_lost"].mean()) if len(human_plays) > 0 else 0

        # 1-hint effectiveness
        h1 = human_plays[human_plays["hints_on_card"] == 1]
        h1_loss = h1["life_lost"].mean() * 100 if len(h1) > 0 else 0

        metrics[ai_type] = {
            "ai_loss": ai_loss,
            "human_loss": h_loss,
            "conv_gap": h_gap,
            "1hint_loss": h1_loss,
        }

    fig, axes = plt.subplots(1, 4, figsize=(18, 5))

    metric_labels = [
        ("ai_loss", "AI Own Loss Rate (%)", "Lower is safer"),
        ("human_loss", "Human Loss Rate (%)", "Lower is better partner"),
        ("conv_gap", "Convention Gap", "Higher means more readable"),
        ("1hint_loss", "1-Hint Loss Rate (%)", "Lower means better hints"),
    ]

    for ax, (metric_key, ylabel, subtitle) in zip(axes, metric_labels):
        vals = [metrics[a][metric_key] for a in ai_types]
        colors = [ai_colors[a] for a in ai_types]
        bars = ax.bar(range(len(ai_types)), vals, color=colors, edgecolor="white",
                      width=0.5)
        ax.set_xticks(range(len(ai_types)))
        ax.set_xticklabels([display_name(a) for a in ai_types], fontsize=11)
        ax.set_ylabel(ylabel, fontsize=10)
        ax.set_title(f"{ylabel}\n({subtitle})", fontsize=10)
        for bar, val in zip(bars, vals):
            fmt = f"{val:.2f}%" if "%" in ylabel else f"{val:+.3f}"
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + max(vals) * 0.02,
                    fmt, ha="center", fontsize=10, fontweight="bold")

    fig.suptitle("AI Agent Comparison: Multi-Dimensional Trustworthiness",
                 fontsize=14, y=1.03)
    fig.tight_layout()
    fig.savefig(out / "crossphase_ai_comparison.png", dpi=150,
                bbox_inches="tight")
    logger.info("Saved crossphase_ai_comparison.png")
    return fig


def plot_skill_vs_ai_partner_gap(
    human_df: pd.DataFrame,
    human_ai_df: pd.DataFrame,
    output_dir: Optional[Path] = None,
) -> plt.Figure:
    """Convention gap: skill levels (human-human) vs AI partner types."""
    out = ensure_output_dir(output_dir)

    fig, ax = plt.subplots(figsize=(11, 6))

    # Skill levels (human-human)
    hh = human_df.copy()
    if "individual_skill" not in hh.columns:
        hh = add_individual_skill_columns(hh)
    hh["life_lost"] = (~hh["was_playable"]).astype(int)
    skill_order = ["beginner", "intermediate", "expert"]
    skill_gaps = []
    skill_ns = []
    for skill in skill_order:
        sub = hh[hh["individual_skill"] == skill]
        if len(sub) > 0:
            gap = sub["posterior_p_life_loss"].mean() - sub["life_lost"].mean()
            skill_gaps.append(gap)
            skill_ns.append(len(sub))

    # AI partner types
    hai = human_ai_df.copy()
    hai["life_lost"] = (~hai["was_playable"]).astype(int)
    human_plays = hai[hai["subject_type"] == "human"]
    ai_order = ["outer", "intentional", "full"]
    ai_gaps = []
    ai_ns = []
    for ai_type in ai_order:
        sub = human_plays[human_plays["partner_type"] == ai_type]
        if len(sub) > 0:
            gap = sub["posterior_p_life_loss"].mean() - sub["life_lost"].mean()
            ai_gaps.append(gap)
            ai_ns.append(len(sub))

    # Combined plot
    all_labels = ([f"Beginner\n(HH, n={skill_ns[0]:,})",
                   f"Intermediate\n(HH, n={skill_ns[1]:,})",
                   f"Expert\n(HH, n={skill_ns[2]:,})"] +
                  [f"vs {display_name('outer')}\n(HAI, n={ai_ns[0]:,})",
                   f"vs {display_name('intentional')}\n(HAI, n={ai_ns[1]:,})",
                   f"vs {display_name('full')}\n(HAI, n={ai_ns[2]:,})"])
    all_gaps = skill_gaps + ai_gaps
    all_colors = (["#dd8452", "#4c72b0", "#55a868"] +
                  ["#a8d8a8", "#8ca8d8", "#d8a8a8"])

    bars = ax.bar(range(len(all_labels)), all_gaps, color=all_colors,
                  edgecolor="white", width=0.65)
    ax.set_xticks(range(len(all_labels)))
    ax.set_xticklabels(all_labels, fontsize=9)
    ax.set_ylabel("Convention Gap", fontsize=12)
    ax.set_title("Convention Gap: Skill Level (Human-Human) vs AI Partner Type",
                 fontsize=13)
    ax.axhline(0, color="black", linewidth=0.5)

    for bar, val in zip(bars, all_gaps):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.005,
                f"{val:+.3f}", ha="center", fontsize=10, fontweight="bold")

    # Separator
    ax.axvline(2.5, color="gray", linestyle="--", linewidth=1, alpha=0.5)
    ax.text(1.0, max(all_gaps) * 1.05, "Human-Human", ha="center",
            fontsize=10, color="gray", fontstyle="italic")
    ax.text(4.0, max(all_gaps) * 1.05, "Human-AI", ha="center",
            fontsize=10, color="gray", fontstyle="italic")

    fig.tight_layout()
    fig.savefig(out / "crossphase_skill_vs_ai_gap.png", dpi=150)
    logger.info("Saved crossphase_skill_vs_ai_gap.png")
    return fig


# ==================================================================
# Deep Mechanism Analysis Plots (Section 18)
# ==================================================================


def plot_hint_playability(*args, **kwargs):
    """DEPRECATED — removed after 2026-07 review.

    The prior implementation called state.apply_action with dicts (wrong API),
    swallowed the resulting exception, and silently produced results computed
    only from the initial state. Use analyze_hint_quality() (backed by
    compute_hint_records) for the correct hint playability metric.
    """
    raise NotImplementedError(
        "plot_hint_playability was removed on 2026-07 (broken apply_action calls). "
        "Use analyze_hint_quality() for hint playability metrics."
    )


def plot_ai_behavioral_profiles(
    human_ai_df: pd.DataFrame,
    output_dir: Optional[Path] = None,
) -> plt.Figure:
    """AI behavioral profiles: action distributions and safety paradox."""
    out = ensure_output_dir(output_dir)

    hai = human_ai_df.copy()
    hai["life_lost"] = (~hai["was_playable"]).astype(int)

    ai_types = ["full", "intentional", "outer"]
    ai_colors = {"full": "#c44e52", "intentional": "#4c72b0", "outer": "#55a868"}

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    # Panel 1: AI play success rate
    ax = axes[0]
    ai_plays = hai[hai["subject_type"] != "human"]
    vals = []
    for ai_type in ai_types:
        sub = ai_plays[ai_plays["subject_type"] == ai_type]
        success = sub["was_playable"].mean() * 100 if len(sub) > 0 else 0
        vals.append(success)
    bars = ax.bar(range(len(ai_types)), vals,
                  color=[ai_colors[a] for a in ai_types], edgecolor="white", width=0.5)
    ai_display = [display_name(a) for a in ai_types]
    ax.set_xticks(range(len(ai_types)))
    ax.set_xticklabels(ai_display, fontsize=12)
    ax.set_ylabel("Play Success Rate (%)", fontsize=11)
    ax.set_title("AI Own Play Success Rate", fontsize=13)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                f"{val:.1f}%", ha="center", fontsize=12, fontweight="bold")
    ax.set_ylim(0, 105)

    # Panel 2: Human play success rate by AI partner
    ax = axes[1]
    human_plays = hai[hai["subject_type"] == "human"]
    vals = []
    for ai_type in ai_types:
        sub = human_plays[human_plays["partner_type"] == ai_type]
        success = sub["was_playable"].mean() * 100 if len(sub) > 0 else 0
        vals.append(success)
    bars = ax.bar(range(len(ai_types)), vals,
                  color=[ai_colors[a] for a in ai_types], edgecolor="white", width=0.5)
    ax.set_xticks(range(len(ai_types)))
    ax.set_xticklabels(ai_display, fontsize=12)
    ax.set_ylabel("Human Play Success Rate (%)", fontsize=11)
    ax.set_title("Human Success When Partnered With AI", fontsize=13)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                f"{val:.1f}%", ha="center", fontsize=12, fontweight="bold")
    ax.set_ylim(0, 105)

    # Panel 3: The safety paradox - stacked bar (computed per game)
    ax = axes[2]
    ai_losses = []
    human_losses = []
    for ai_type in ai_types:
        games = hai[hai["partner_type"] == ai_type]["game_key"].unique()
        n_games = len(games) if len(games) > 0 else 1
        ai_plays = hai[(hai["subject_type"] == ai_type) & (hai["partner_type"] == "human")]
        human_plays_a = hai[(hai["subject_type"] == "human") & (hai["partner_type"] == ai_type)]
        ai_losses.append(ai_plays["life_lost"].sum() / n_games)
        human_losses.append(human_plays_a["life_lost"].sum() / n_games)
    x = np.arange(len(ai_types))
    bars1 = ax.bar(x, ai_losses, 0.5, label="AI life losses/game",
                   color=[ai_colors[a] for a in ai_types], edgecolor="white", alpha=0.6)
    bars2 = ax.bar(x, human_losses, 0.5, bottom=ai_losses,
                   label="Human life losses/game",
                   color=[ai_colors[a] for a in ai_types], edgecolor="white")
    ax.set_xticks(x)
    ax.set_xticklabels(ai_display, fontsize=12)
    ax.set_ylabel("Life Losses per Game", fontsize=11)
    ax.set_title("The Safety Paradox:\nWho Bears the Risk?", fontsize=13)
    ax.legend(fontsize=9, loc="upper left")

    for i, (al, hl) in enumerate(zip(ai_losses, human_losses)):
        total = al + hl
        ax.text(i, total + 0.08, f"Total: {total:.2f}", ha="center",
                fontsize=10, fontweight="bold")

    fig.suptitle("AI Behavioral Profiles and the Safety Paradox", fontsize=15, y=1.03)
    fig.tight_layout()
    fig.savefig(out / "mechanism_behavioral_profiles.png", dpi=150,
                bbox_inches="tight")
    logger.info("Saved mechanism_behavioral_profiles.png")
    return fig


def plot_score_distributions(
    human_ai_df: pd.DataFrame,
    output_dir: Optional[Path] = None,
) -> plt.Figure:
    """Score distributions by AI type."""
    out = ensure_output_dir(output_dir)

    # Get per-game scores from the play records (Appendix A final_score)
    hai = human_ai_df.copy()
    game_scores = hai.groupby(["game_key", "partner_type"]).agg(
        score=("final_score", "first"),
    ).reset_index()

    ai_types = ["outer", "intentional", "full"]
    ai_colors = {"full": "#c44e52", "intentional": "#4c72b0", "outer": "#55a868"}

    fig, axes = plt.subplots(1, 3, figsize=(18, 5), sharey=True)

    for ax, ai_type in zip(axes, ai_types):
        scores = game_scores[game_scores["partner_type"] == ai_type]["score"]
        ax.hist(scores, bins=range(0, 27), color=ai_colors[ai_type],
                edgecolor="white", alpha=0.8, density=True)
        ax.set_xlabel("Final Score", fontsize=11)
        ax.set_title(f"{display_name(ai_type)}\n(mean={scores.mean():.1f}, median={scores.median():.0f})",
                     fontsize=12)
        ax.axvline(scores.mean(), color="black", linestyle="--", linewidth=1.5,
                   label=f"Mean: {scores.mean():.1f}")
        ax.legend(fontsize=9)

    for idx, (ax, label) in enumerate(zip(axes, ["(a)", "(b)", "(c)"])):
        ax.text(-0.05, 1.05, label, transform=ax.transAxes,
                fontsize=14, fontweight="bold", va="bottom")
    axes[0].set_ylabel("Density", fontsize=11)
    fig.suptitle("Score Distributions by AI Partner Type", fontsize=14, y=1.02)
    fig.tight_layout()
    fig.savefig(out / "mechanism_score_distributions.png", dpi=150,
                bbox_inches="tight")
    logger.info("Saved mechanism_score_distributions.png")
    return fig


# ------------------------------------------------------------------
# Censoring diagnostic: uncensored end score
# ------------------------------------------------------------------

_UNC_BINS = [-0.1, 0.5, 5.5, 10.5, 15.5, 20.5, 25.5]
_UNC_LABELS = ["0", "1--5", "6--10", "11--15", "16--20", "21--25"]


def uncensored_end_score(df: pd.DataFrame) -> pd.DataFrame:
    """Per-game 'uncensored end score': the tableau total at the end of play,
    ignoring the three-strike zeroing rule.

    For a game reaching a natural or perfect end this equals the official
    final score; for a struck-out game it is the tableau total at the moment
    of the third strike. The last play record of any game carries the
    pre-play ``fireworks_sum`` snapshot and a ``was_playable`` flag, so
    ``fireworks_sum + was_playable`` recovers the post-last-play tableau
    total uniformly across all endings (the failed third strike adds 0).

    Returns one row per game with columns: game_key, uncensored, official
    (final_score), struck (official == 0).
    """
    d = df.sort_values(["game_key", "turn"])
    last = d.groupby("game_key").tail(1).copy()
    last["uncensored"] = last["fireworks_sum"] + last["was_playable"].astype(int)
    last["official"] = last["final_score"]
    last["struck"] = last["final_score"] == 0
    return last[["game_key", "uncensored", "official", "struck"]].reset_index(drop=True)


def _unc_bin_pct(vals) -> np.ndarray:
    c = pd.cut(vals, bins=_UNC_BINS, labels=_UNC_LABELS)
    return (c.value_counts(normalize=True).reindex(_UNC_LABELS).fillna(0) * 100).values


def plot_uncensored_score_diagnostic(
    human_df: pd.DataFrame,
    agent_df: pd.DataFrame,
    human_ai_df: pd.DataFrame,
    output_dir: Optional[Path] = None,
) -> dict:
    """Censoring diagnostic for the game-score bimodality (Appendix M).

    Produces two figures and returns a dict of per-setting/per-group bin
    percentages and struck-game means for verification.

    Figure A (``uncensored_score_diagnostic.png``): official (zeroed) vs
    uncensored end-score distributions for the three settings.
    Figure B (``uncensored_score_by_group.png``): uncensored distributions by
    group (H-H pair types, H-AI partner types, AI-AI agents).
    """
    out = ensure_output_dir(output_dir)

    hh = human_df.copy()
    if "pair_type" not in hh.columns:
        hh = add_individual_skill_columns(hh)
    settings = [("Human-Human", hh), ("Human-AI", human_ai_df), ("AI-AI", agent_df)]
    colors = {"Human-Human": "#c44e52", "Human-AI": "#9467bd", "AI-AI": "#4c72b0"}

    results = {}

    # ---- Figure A: official vs uncensored, by setting ----
    figA, axesA = plt.subplots(1, 3, figsize=(18, 5), sharey=True)
    x = np.arange(len(_UNC_LABELS))
    w = 0.4
    for ax, (name, df) in zip(axesA, settings):
        u = uncensored_end_score(df)
        off_pct = _unc_bin_pct(u["official"])
        unc_pct = _unc_bin_pct(u["uncensored"])
        struck = u[u["struck"]]
        results[name] = {
            "uncensored_bin_pct": [round(v) for v in unc_pct],
            "official_bin_pct": [round(v) for v in off_pct],
            "n_games": int(len(u)),
            "n_struck": int(len(struck)),
            "struck_uncensored_mean": round(float(struck["uncensored"].mean()), 1) if len(struck) else float("nan"),
        }
        ax.bar(x - w / 2, off_pct, w, label="Official (zeroed)",
               color="#bbbbbb", edgecolor="white")
        ax.bar(x + w / 2, unc_pct, w, label="Uncensored",
               color=colors[name], edgecolor="white")
        ax.set_xticks(x)
        ax.set_xticklabels(_UNC_LABELS, fontsize=9)
        ax.set_xlabel("End score", fontsize=11)
        ax.set_title(name, fontsize=13)
        ax.legend(fontsize=9)
    axesA[0].set_ylabel("% of games", fontsize=11)
    figA.suptitle("Censoring diagnostic: official (zeroed) vs.\\ uncensored end-score distributions",
                  fontsize=14, y=1.02)
    figA.tight_layout()
    figA.savefig(out / "uncensored_score_diagnostic.png", dpi=150, bbox_inches="tight")
    logger.info("Saved uncensored_score_diagnostic.png")

    # ---- Figure B: uncensored by group ----
    figB, axesB = plt.subplots(1, 3, figsize=(18, 5), sharey=True)

    # H-H by pair type
    pair_order = ["expert-expert", "expert-intermediate", "intermediate-intermediate",
                  "intermediate-beginner", "beginner-beginner"]
    pair_lbl = {"expert-expert": "E-E", "expert-intermediate": "E-I",
                "intermediate-intermediate": "I-I", "intermediate-beginner": "I-B",
                "beginner-beginner": "B-B"}
    u_hh = uncensored_end_score(hh)
    ptype_by_game = hh.groupby("game_key")["pair_type"].first()
    u_hh = u_hh.merge(ptype_by_game.rename("pair_type"), on="game_key")
    ax = axesB[0]
    bottom = np.zeros(len(_UNC_LABELS))
    hh_colors = plt.cm.Reds(np.linspace(0.4, 0.9, len(pair_order)))
    for pt, col in zip(pair_order, hh_colors):
        sub = u_hh[u_hh["pair_type"] == pt]
        if len(sub) == 0:
            continue
        pct = _unc_bin_pct(sub["uncensored"]) * len(sub) / len(u_hh)
        ax.bar(x, pct, bottom=bottom, label=pair_lbl[pt], color=col, edgecolor="white", width=0.7)
        bottom += pct
    ax.set_xticks(x); ax.set_xticklabels(_UNC_LABELS, fontsize=9)
    ax.set_title("Human-Human by pair type", fontsize=12); ax.legend(fontsize=8)
    ax.set_ylabel("% of all games in setting", fontsize=11); ax.set_xlabel("Uncensored end score", fontsize=11)

    # H-AI by partner
    ax = axesB[1]
    u_hai = uncensored_end_score(human_ai_df)
    partner_by_game = human_ai_df.groupby("game_key")["partner_type"].first()
    u_hai = u_hai.merge(partner_by_game.rename("partner_type"), on="game_key")
    bottom = np.zeros(len(_UNC_LABELS))
    hai_colors = {"full": "#c44e52", "intentional": "#4c72b0", "outer": "#55a868"}
    for a in ["full", "intentional", "outer"]:
        sub = u_hai[u_hai["partner_type"] == a]
        pct = _unc_bin_pct(sub["uncensored"]) * len(sub) / len(u_hai)
        ax.bar(x, pct, bottom=bottom, label=display_name(a), color=hai_colors[a], edgecolor="white", width=0.7)
        bottom += pct
    ax.set_xticks(x); ax.set_xticklabels(_UNC_LABELS, fontsize=9)
    ax.set_title("Human-AI by partner type", fontsize=12); ax.legend(fontsize=8)
    ax.set_xlabel("Uncensored end score", fontsize=11)

    # AI-AI by subject agent (Flawed highlighted)
    ax = axesB[2]
    u_aa = uncensored_end_score(agent_df)
    subj_by_game = agent_df.groupby("game_key")["subject_type"].first()
    u_aa = u_aa.merge(subj_by_game.rename("subject_type"), on="game_key")
    bottom = np.zeros(len(_UNC_LABELS))
    agent_order = ["iggi", "piers", "bergh", "outer", "simple", "internal", "flawed"]
    for a in agent_order:
        sub = u_aa[u_aa["subject_type"] == a]
        if len(sub) == 0:
            continue
        pct = _unc_bin_pct(sub["uncensored"]) * len(sub) / len(u_aa)
        col = "#000000" if a == "flawed" else plt.cm.Blues(0.3 + 0.5 * agent_order.index(a) / len(agent_order))
        ax.bar(x, pct, bottom=bottom, label=display_name(a) + (" (low mode)" if a == "flawed" else ""),
               color=col, edgecolor="white", width=0.7)
        bottom += pct
    ax.set_xticks(x); ax.set_xticklabels(_UNC_LABELS, fontsize=9)
    ax.set_title("AI-AI by subject agent", fontsize=12); ax.legend(fontsize=8)
    ax.set_xlabel("Uncensored end score", fontsize=11)

    figB.suptitle("Uncensored end-score distributions by group", fontsize=14, y=1.02)
    figB.tight_layout()
    figB.savefig(out / "uncensored_score_by_group.png", dpi=150, bbox_inches="tight")
    logger.info("Saved uncensored_score_by_group.png")

    return results


def plot_crossplay_posterior_heatmap(
    agent_df: pd.DataFrame,
    output_dir: Optional[Path] = None,
) -> plt.Figure:
    """7x7 heatmap of mean P(life lost) at play time for all AI agent pairings."""
    out = ensure_output_dir(output_dir)

    agent_order = ["bergh", "outer", "iggi", "piers", "internal", "simple", "flawed"]
    display_labels = [display_name(a) for a in agent_order]

    matrix = np.full((7, 7), np.nan)
    for i, subj in enumerate(agent_order):
        for j, part in enumerate(agent_order):
            sub = agent_df[(agent_df["subject_type"] == subj) & (agent_df["partner_type"] == part)]
            if len(sub) > 0:
                matrix[i, j] = sub["posterior_p_life_loss"].mean() * 100

    fig, ax = plt.subplots(figsize=(9, 8))
    im = ax.imshow(matrix, cmap="Greys", vmin=0, vmax=50, aspect="auto")

    ax.set_xticks(range(7))
    ax.set_xticklabels(display_labels, fontsize=10, rotation=45, ha="right")
    ax.set_yticks(range(7))
    ax.set_yticklabels(display_labels, fontsize=10)
    ax.set_xlabel("Partner Agent", fontsize=12)
    ax.set_ylabel("Subject Agent", fontsize=12)
    ax.set_title("Mean P(life lost) at Play Time: AI vs AI", fontsize=14)

    for i in range(7):
        for j in range(7):
            if not np.isnan(matrix[i, j]):
                color = "white" if matrix[i, j] > 25 else "black"
                ax.text(j, i, f"{matrix[i, j]:.1f}", ha="center", va="center",
                        fontsize=9, fontweight="bold", color=color)

    cbar = fig.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("Mean P(life lost) (%)", fontsize=11)

    fig.tight_layout()
    fig.savefig(out / "crossplay_posterior_heatmap.png", dpi=150, bbox_inches="tight")
    logger.info("Saved crossplay_posterior_heatmap.png")
    return fig


def plot_crossplay_score_heatmap(
    agent_df: pd.DataFrame,
    output_dir: Optional[Path] = None,
) -> plt.Figure:
    """7x7 heatmap of mean game score for all AI agent pairings."""
    out = ensure_output_dir(output_dir)

    agent_order = ["bergh", "outer", "iggi", "piers", "internal", "simple", "flawed"]
    display_labels = [display_name(a) for a in agent_order]

    # Unordered pairing: cell (a, b) = mean over the 200 games in
    # a_vs_b ∪ b_vs_a (100 on the diagonal), each game counted once; symmetric.
    pair = agent_df["game_key"].str.split(":").str[0]
    matrix = np.full((7, 7), np.nan)
    for i, subj in enumerate(agent_order):
        for j, part in enumerate(agent_order):
            sub = agent_df[pair.isin({f"{subj}_vs_{part}", f"{part}_vs_{subj}"})]
            if len(sub) > 0:
                game_scores = sub.groupby("game_key")["final_score"].first()
                matrix[i, j] = game_scores.mean()

    fig, ax = plt.subplots(figsize=(9, 8))
    im = ax.imshow(matrix, cmap="Greys", vmin=0, vmax=25, aspect="auto")

    ax.set_xticks(range(7))
    ax.set_xticklabels(display_labels, fontsize=10, rotation=45, ha="right")
    ax.set_yticks(range(7))
    ax.set_yticklabels(display_labels, fontsize=10)
    ax.set_xlabel("Partner Agent", fontsize=12)
    ax.set_ylabel("Subject Agent", fontsize=12)
    ax.set_title("Mean Game Score: AI vs AI", fontsize=14)

    for i in range(7):
        for j in range(7):
            if not np.isnan(matrix[i, j]):
                color = "white" if matrix[i, j] > 12.5 else "black"
                ax.text(j, i, f"{matrix[i, j]:.1f}", ha="center", va="center",
                        fontsize=9, fontweight="bold", color=color)

    cbar = fig.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("Mean Game Score", fontsize=11)

    fig.tight_layout()
    fig.savefig(out / "crossplay_score_heatmap.png", dpi=150, bbox_inches="tight")
    logger.info("Saved crossplay_score_heatmap.png")
    return fig


def plot_crossplay_combined(
    agent_df: pd.DataFrame,
    output_dir: Optional[Path] = None,
) -> plt.Figure:
    """Combined two-panel 7x7 heatmap: (a) mean P(life lost), (b) mean game score.

    Produces Figure A6 in the manuscript (``crossplay_combined.png``). Uses the
    same agent order and display labels as the individual panel plots so that
    the combined and individual figures stay in sync.
    """
    out = ensure_output_dir(output_dir)

    agent_order = ["bergh", "outer", "iggi", "piers", "internal", "simple", "flawed"]
    display_labels = [display_name(a) for a in agent_order]

    pair = agent_df["game_key"].str.split(":").str[0]
    posterior_matrix = np.full((7, 7), np.nan)
    score_matrix = np.full((7, 7), np.nan)
    for i, subj in enumerate(agent_order):
        for j, part in enumerate(agent_order):
            # Panel (a): per-play statistic, actor's-perspective selection (unchanged)
            sub = agent_df[(agent_df["subject_type"] == subj) & (agent_df["partner_type"] == part)]
            if len(sub) > 0:
                posterior_matrix[i, j] = sub["posterior_p_life_loss"].mean() * 100
            # Panel (b): game-level unordered pairing — 200 games per cell
            # (100 on the diagonal), each game counted once; symmetric.
            sub_pair = agent_df[pair.isin({f"{subj}_vs_{part}", f"{part}_vs_{subj}"})]
            if len(sub_pair) > 0:
                game_scores = sub_pair.groupby("game_key")["final_score"].first()
                score_matrix[i, j] = game_scores.mean()

    fig, axes = plt.subplots(1, 2, figsize=(18, 8))

    # Panel (a): posterior heatmap
    ax = axes[0]
    im = ax.imshow(posterior_matrix, cmap="Greys", vmin=0, vmax=50, aspect="auto")
    ax.set_xticks(range(7))
    ax.set_xticklabels(display_labels, fontsize=10, rotation=45, ha="right")
    ax.set_yticks(range(7))
    ax.set_yticklabels(display_labels, fontsize=10)
    ax.set_xlabel("Partner Agent", fontsize=12)
    ax.set_ylabel("Subject Agent", fontsize=12)
    ax.set_title("Mean P(life lost) at Play Time: AI vs AI", fontsize=14)
    for i in range(7):
        for j in range(7):
            if not np.isnan(posterior_matrix[i, j]):
                color = "white" if posterior_matrix[i, j] > 25 else "black"
                ax.text(j, i, f"{posterior_matrix[i, j]:.1f}", ha="center", va="center",
                        fontsize=9, fontweight="bold", color=color)
    cbar = fig.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("Mean P(life lost) (%)", fontsize=11)

    # Panel (b): score heatmap
    ax = axes[1]
    im = ax.imshow(score_matrix, cmap="Greys", vmin=0, vmax=25, aspect="auto")
    ax.set_xticks(range(7))
    ax.set_xticklabels(display_labels, fontsize=10, rotation=45, ha="right")
    ax.set_yticks(range(7))
    ax.set_yticklabels(display_labels, fontsize=10)
    ax.set_xlabel("Partner Agent", fontsize=12)
    ax.set_ylabel("Subject Agent", fontsize=12)
    ax.set_title("Mean Game Score: AI vs AI", fontsize=14)
    for i in range(7):
        for j in range(7):
            if not np.isnan(score_matrix[i, j]):
                color = "white" if score_matrix[i, j] > 12.5 else "black"
                ax.text(j, i, f"{score_matrix[i, j]:.1f}", ha="center", va="center",
                        fontsize=9, fontweight="bold", color=color)
    cbar = fig.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("Mean Game Score", fontsize=11)

    # Panel labels (a)/(b) in the top-left of each panel
    fig.text(0.02, 0.97, "(a)", fontsize=20, fontweight="bold", ha="left", va="top")
    fig.text(0.52, 0.97, "(b)", fontsize=20, fontweight="bold", ha="left", va="top")

    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.96))
    fig.savefig(out / "crossplay_combined.png", dpi=150, bbox_inches="tight")
    logger.info("Saved crossplay_combined.png")
    return fig


def plot_causal_chain(
    output_dir: Optional[Path] = None,
    human_ai_df: Optional[pd.DataFrame] = None,
    hint_df: Optional[pd.DataFrame] = None,
) -> plt.Figure:
    """Summary diagram: the causal chain from AI behavior to human outcomes.

    If ``human_ai_df`` and ``hint_df`` are provided, per-AI numbers are computed
    from the data rather than hardcoded.
    """
    out = ensure_output_dir(output_dir)

    fig, ax = plt.subplots(figsize=(16, 10))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 10)
    ax.axis("off")

    # Title
    ax.text(8, 9.5, "Three Modes of Human-AI Failure in Hanabi",
            fontsize=16, ha="center", fontweight="bold")

    def _stats(ai):
        if human_ai_df is None:
            return None
        hai = human_ai_df.copy()
        if "life_lost" not in hai.columns:
            hai["life_lost"] = (~hai["was_playable"]).astype(int)
        human_plays = hai[(hai["subject_type"] == "human") & (hai["partner_type"] == ai)]
        ai_plays = hai[hai["subject_type"] == ai]
        n_games = hai[hai["partner_type"] == ai]["game_key"].nunique()
        n_games = max(1, n_games)
        if "final_score" in hai.columns:
            games_scores = hai[hai["partner_type"] == ai].groupby("game_key")["final_score"].first()
            death_rate = (games_scores == 0).mean() * 100 if len(games_scores) else 0
        else:
            death_rate = float("nan")
        gap = human_plays["posterior_p_life_loss"].mean() - human_plays["life_lost"].mean()
        hf_rate = human_plays["life_lost"].mean() * 100 if len(human_plays) else 0
        hl_per_game = human_plays["life_lost"].sum() / n_games
        ai_l_per_game = ai_plays["life_lost"].sum() / n_games
        # Hint metrics (if hint records supplied)
        if hint_df is not None and "hinter_type" in hint_df.columns:
            ai_hints = hint_df[hint_df["hinter_type"] == ai]
            if len(ai_hints) > 0 and "playable_cards_touched" in ai_hints.columns and "cards_touched" in ai_hints.columns:
                total_touched = ai_hints["cards_touched"].sum()
                if total_touched > 0:
                    playable_pct = ai_hints["playable_cards_touched"].sum() / total_touched * 100
                    not_playable_pct = 100 - playable_pct
                else:
                    playable_pct = float("nan")
                    not_playable_pct = float("nan")
            else:
                playable_pct = float("nan")
                not_playable_pct = float("nan")
        else:
            playable_pct = float("nan")
            not_playable_pct = float("nan")
        return dict(
            gap=gap, hf_rate=hf_rate, hl_per_game=hl_per_game,
            ai_l_per_game=ai_l_per_game, death_rate=death_rate,
            playable_pct=playable_pct, not_playable_pct=not_playable_pct,
        )

    def _fmt_line(template, val, precision=1, suffix=""):
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return template.replace("{}", "n/a")
        return template.replace("{}", f"{val:.{precision}f}{suffix}")

    stats_by_ai = {ai: _stats(ai) for ai in ("outer", "intentional", "full")}

    def _lines_for(ai, tagline_labels):
        s = stats_by_ai.get(ai)
        if s is None:
            # Fallback: hardcoded numbers preserved as a rough reference
            return None
        return [
            tagline_labels[0],
            _fmt_line("{}% of hinted cards NOT playable", s["not_playable_pct"], 0, ""),
            "",
            _fmt_line("Human failure rate: {}%", s["hf_rate"], 1),
            _fmt_line("Human losses/game: {}", s["hl_per_game"], 2),
            _fmt_line("AI losses/game: {}", s["ai_l_per_game"], 2),
            _fmt_line("Death rate: {}%", s["death_rate"], 0),
            _fmt_line("Convention gap: {}", s["gap"], 3),
            "",
            tagline_labels[1],
        ]

    fallback_ai_data = [
        ("outer", "#55a868", [
            "Information-theoretic hints",
            "60% of hinted cards NOT playable",
            "Hint-to-play ratio: 2.71",
            "Never loses lives itself",
            "",
            "Human failure rate: 34.4%",
            "Human losses/game: 2.72",
            "Death rate: 82%",
            "Convention gap: +0.067",
            "",
            '"Brilliant but Incomprehensible"',
        ]),
        ("intentional", "#4c72b0", [
            "Models partner intentions",
            "65% of hinted cards playable",
            "Hint-to-play ratio: 1.32",
            "Plays only when certain (99.9%)",
            "",
            "Human failure rate: 17.6%",
            "Human losses/game: 1.40",
            "Death rate: 26%",
            "Convention gap: +0.208",
            "",
            '"Safe and Readable"',
        ]),
        ("full", "#c44e52", [
            "Aggressive, speculative play",
            "64% of hinted cards playable",
            "Hint-to-play ratio: 1.07",
            "Absorbs 1.34 losses/game itself",
            "",
            "Human failure rate: 14.4%",
            "Human losses/game: 1.00",
            "Death rate: 61%",
            "Convention gap: +0.246",
            "",
            '"Risky but Readable"',
        ]),
    ]

    _tagline_map = {
        "outer": ("Information-theoretic hints", '"Brilliant but Incomprehensible"'),
        "intentional": ("Models partner intentions", '"Safe and Readable"'),
        "full": ("Aggressive, speculative play", '"Risky but Readable"'),
    }
    ai_data = []
    for ai_key, color, fallback_lines in fallback_ai_data:
        lines = _lines_for(ai_key, _tagline_map[ai_key])
        ai_data.append((ai_key, color, lines if lines is not None else fallback_lines))

    for i, (name, color, lines) in enumerate(ai_data):
        x_center = 3 + i * 5
        # Header box
        rect = plt.Rectangle((x_center - 2, 7.8), 4, 1, linewidth=2,
                              edgecolor=color, facecolor=color, alpha=0.2,
                              transform=ax.transData)
        ax.add_patch(rect)
        ax.text(x_center, 8.3, display_name(name).upper(), ha="center", fontsize=14,
                fontweight="bold", color=color)

        # Content
        for j, line in enumerate(lines):
            y = 7.5 - j * 0.6
            weight = "bold" if j >= 9 else "normal"
            color_text = color if j >= 9 else "black"
            fontsize = 11 if j >= 9 else 9
            ax.text(x_center, y, line, ha="center", fontsize=fontsize,
                    fontweight=weight, color=color_text)

    # Arrow annotation at bottom
    ax.annotate("", xy=(13, 1.2), xytext=(3, 1.2),
                arrowprops=dict(arrowstyle="->", color="gray", lw=2))
    ax.text(8, 0.8, "Increasing Human Trustworthiness >>>",
            ha="center", fontsize=12, color="gray", fontstyle="italic")

    fig.tight_layout()
    fig.savefig(out / "mechanism_causal_chain.png", dpi=150, bbox_inches="tight")
    logger.info("Saved mechanism_causal_chain.png")
    return fig


# ==================================================================
# Phase 8: Strengthening Analyses for Publication
# ==================================================================


# ------------------------------------------------------------------
# 8.1 Logistic Regression
# ------------------------------------------------------------------

def logistic_analysis(
    human_df: pd.DataFrame,
    agent_df: pd.DataFrame,
    human_ai_df: pd.DataFrame,
    output_dir: Optional[Path] = None,
) -> dict:
    """Fit logistic regressions predicting life loss from posterior + context.

    Uses statsmodels.Logit (unpenalized MLE) to match Appendix E.
    Coefficients are reported on the unstandardized scale.

    Returns a dict with model results for each dataset.
    """
    import statsmodels.api as sm
    from sklearn.metrics import roc_auc_score, roc_curve

    out = ensure_output_dir(output_dir)

    def _ensure_cols(df):
        df = df.copy()
        if "life_lost" not in df.columns:
            df["life_lost"] = (~df["was_playable"]).astype(int)
        if "game_phase" not in df.columns or df["game_phase"].dtype == "object":
            df["game_phase"] = pd.cut(
                df["turn"], bins=[-1, 15, 35, 200],
                labels=["early", "mid", "late"], right=True,
            )
        return df

    def _fit_models(df, label, has_skill=False, has_partner=False):
        df = _ensure_cols(df)
        y = df["life_lost"].values

        # Features for each model
        # Model 1: posterior only
        X1 = df[["posterior_p_life_loss"]].values

        # Model 2: posterior + context
        phase_dummies = pd.get_dummies(df["game_phase"], prefix="phase", drop_first=True, dtype=float)
        X2_cols = df[["posterior_p_life_loss", "hints_on_card", "life_tokens", "cards_in_deck"]].copy()
        X2_cols = pd.concat([X2_cols, phase_dummies], axis=1)
        X2 = X2_cols.values

        # Model 3: full model
        X3_cols = X2_cols.copy()
        if has_skill and "individual_skill" in df.columns:
            skill_dummies = pd.get_dummies(df["individual_skill"], prefix="skill", drop_first=True, dtype=float)
            X3_cols = pd.concat([X3_cols, skill_dummies], axis=1)
        if has_partner and "partner_type" in df.columns:
            partner_dummies = pd.get_dummies(df["partner_type"], prefix="partner", drop_first=True, dtype=float)
            X3_cols = pd.concat([X3_cols, partner_dummies], axis=1)
        X3 = X3_cols.values

        results = {}
        for model_name, X, feature_names in [
            ("M1_posterior", X1, ["posterior_p_life_loss"]),
            ("M2_context", X2, list(X2_cols.columns)),
            ("M3_full", X3, list(X3_cols.columns)),
        ]:
            # statsmodels.Logit — unpenalized MLE, unstandardized features
            X_sm = sm.add_constant(X, has_constant="add")
            try:
                model = sm.Logit(y, X_sm).fit(disp=False, maxiter=200)
                intercept = float(model.params[0])
                betas = model.params[1:]
                pvalues = {feature_names[i]: float(model.pvalues[i + 1]) for i in range(len(feature_names))}
                y_prob = np.asarray(model.predict(X_sm))
                # McFadden pseudo-R² from the null model
                null_ll = float(sm.Logit(y, np.ones((len(y), 1))).fit(disp=False).llf)
                pseudo_r2 = 1 - float(model.llf) / null_ll if null_ll != 0 else 0
            except Exception as e:
                # Fallback: null model
                logger.warning("statsmodels.Logit failed for %s: %s", model_name, e)
                intercept = 0.0
                betas = np.zeros(len(feature_names))
                pvalues = {n: 1.0 for n in feature_names}
                y_prob = np.full(len(y), y.mean())
                pseudo_r2 = 0.0

            auc = roc_auc_score(y, y_prob)
            coefs = {feature_names[i]: float(betas[i]) for i in range(len(feature_names))}

            results[model_name] = {
                "auc": auc,
                "pseudo_r2": pseudo_r2,
                "coefs": coefs,
                "pvalues": pvalues,
                "intercept": intercept,
                "n": len(y),
                "fpr_tpr": roc_curve(y, y_prob),
            }
        return results

    # Fit on each dataset
    all_results = {}

    # Human-human
    all_results["human"] = _fit_models(human_df, "Human-Human", has_skill=True)

    # Agent-agent
    all_results["agent"] = _fit_models(agent_df, "AI-AI")

    # Human-AI (human plays only)
    hai_human = human_ai_df[human_ai_df["subject_type"] == "human"].copy()
    all_results["human_ai"] = _fit_models(hai_human, "Human-AI", has_partner=True)

    # Print results table
    print("\n=== 8.1 Logistic Regression Results ===\n")
    print(f"{'Dataset':<15} {'Model':<15} {'N':>7} {'AUC':>8} {'Pseudo-R²':>10} {'β(posterior)':>13}")
    print("-" * 70)
    for ds_name, ds_results in all_results.items():
        for model_name, res in ds_results.items():
            beta_post = res["coefs"].get("posterior_p_life_loss", float("nan"))
            print(f"{ds_name:<15} {model_name:<15} {res['n']:>7,} {res['auc']:>8.4f} {res['pseudo_r2']:>10.4f} {beta_post:>13.4f}")

    # Plot ROC curves
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    ds_titles = {"human": "Human-Human", "agent": "AI-AI", "human_ai": "Human-AI (human plays)"}
    model_colors = {"M1_posterior": "#c44e52", "M2_context": "#4c72b0", "M3_full": "#55a868"}
    model_labels = {"M1_posterior": "M1: Posterior only", "M2_context": "M2: + Context", "M3_full": "M3: + Full"}

    for ax, (ds_name, ds_results) in zip(axes, all_results.items()):
        ax.plot([0, 1], [0, 1], "k--", alpha=0.3)
        for model_name, res in ds_results.items():
            fpr, tpr, _ = res["fpr_tpr"]
            ax.plot(fpr, tpr, color=model_colors[model_name], linewidth=2,
                    label=f"{model_labels[model_name]} (AUC={res['auc']:.3f})")
        ax.set_xlabel("False Positive Rate", fontsize=11)
        ax.set_ylabel("True Positive Rate", fontsize=11)
        ax.set_title(f"{ds_titles[ds_name]}\n(n={ds_results['M1_posterior']['n']:,})", fontsize=12)
        ax.legend(fontsize=9, loc="lower right")
        ax.set_xlim(-0.02, 1.02)
        ax.set_ylim(-0.02, 1.02)

    fig.suptitle("ROC Curves: How Well Does the Posterior Predict Life Loss?", fontsize=14, y=1.03)
    fig.tight_layout()
    fig.savefig(out / "phase8_logistic_roc.png", dpi=150, bbox_inches="tight")
    logger.info("Saved phase8_logistic_roc.png")

    # Coefficient comparison plot
    fig, ax = plt.subplots(figsize=(12, 6))
    datasets = ["human", "agent", "human_ai"]
    ds_labels = ["Human-Human", "AI-AI", "Human-AI"]
    models = ["M1_posterior", "M2_context", "M3_full"]
    x = np.arange(len(datasets))
    width = 0.25
    for i, model in enumerate(models):
        betas = [all_results[ds][model]["coefs"].get("posterior_p_life_loss", 0) for ds in datasets]
        ax.bar(x + i * width - width, betas, width, label=model_labels[model],
               color=list(model_colors.values())[i], edgecolor="white")
    ax.set_xticks(x)
    ax.set_xticklabels(ds_labels, fontsize=12)
    ax.set_ylabel("Coefficient on P(life loss)", fontsize=11)
    ax.set_title("Posterior Coefficient Across Datasets and Models", fontsize=13)
    ax.legend(fontsize=10)
    ax.axhline(0, color="black", linewidth=0.5)
    for i, model in enumerate(models):
        for j, ds in enumerate(datasets):
            val = all_results[ds][model]["coefs"].get("posterior_p_life_loss", 0)
            xpos = j + i * width - width
            ax.text(xpos, val + 0.05, f"{val:.2f}", ha="center", fontsize=9, fontweight="bold")

    fig.tight_layout()
    fig.savefig(out / "phase8_logistic_coefficients.png", dpi=150)
    logger.info("Saved phase8_logistic_coefficients.png")

    return all_results


# ------------------------------------------------------------------
# 8.2 Hint-Level Quality Metrics
# ------------------------------------------------------------------

def compute_hint_records(
    game_json: dict,
    data_source: str = "hanab_live",
) -> list[dict]:
    """Replay a game and extract HintRecords for every hint action.

    Returns list of dicts, one per hint action.
    """
    from src.game_engine import (
        ActionType, Action, HanabiState, state_from_hanab_live,
        actions_from_hanab_live, CARD_DISTRIBUTION,
    )
    from src.posterior import compute_life_loss_posterior

    state = state_from_hanab_live(game_json)
    state.deal_initial_hands()
    actions = actions_from_hanab_live(game_json)
    players = game_json.get("players", [])
    game_id = game_json.get("id", 0)

    hint_records = []
    action_list = list(actions)  # for lookahead

    for action_idx, action in enumerate(action_list):
        if state.game_over or action.action_type == ActionType.GAME_OVER:
            break

        # Translate play/discard
        if action.action_type in (ActionType.PLAY, ActionType.DISCARD):
            deck_idx = action.target
            try:
                hand_pos = state.find_hand_index_by_deck_index(state.current_player, deck_idx)
            except ValueError:
                break
            translated = Action(action.action_type, target=hand_pos, value=action.value)
        else:
            translated = action

        # Record hint actions
        if action.action_type in (ActionType.COLOR_CLUE, ActionType.RANK_CLUE):
            hinter = state.current_player
            target_player = action.target
            hint_type = "color" if action.action_type == ActionType.COLOR_CLUE else "rank"
            hint_value = action.value

            # Compute candidates BEFORE hint for each card in target's hand
            candidates_before = 0
            cards_touched = 0
            playable_cards_touched = 0
            for slot_idx, card in enumerate(state.hands[target_player]):
                cands = state.get_candidate_identities(target_player, slot_idx)
                candidates_before += len(cands)

                # Check if hint touches this card
                card_color, card_rank = card
                if hint_type == "color" and card_color == hint_value:
                    cards_touched += 1
                    if state.is_playable(card_color, card_rank):
                        playable_cards_touched += 1
                elif hint_type == "rank" and card_rank == hint_value:
                    cards_touched += 1
                    if state.is_playable(card_color, card_rank):
                        playable_cards_touched += 1

            # Apply hint to get candidates_after
            state.apply_action(translated)

            candidates_after = 0
            for slot_idx in range(len(state.hands[target_player])):
                cands = state.get_candidate_identities(target_player, slot_idx)
                candidates_after += len(cands)

            # Look ahead: what does the target do next?
            next_action_by_target = None
            # computed post hoc by link_hint_to_next_play; see plot_hint_quality
            next_play_success = None
            for future_idx in range(action_idx + 1, len(action_list)):
                future = action_list[future_idx]
                # Count turns to find when target_player acts next
                turns_ahead = future_idx - action_idx
                future_player = (hinter + turns_ahead) % state.num_players
                if future_player == target_player:
                    if future.action_type == ActionType.PLAY:
                        next_action_by_target = "play"
                    elif future.action_type == ActionType.DISCARD:
                        next_action_by_target = "discard"
                    elif future.action_type in (ActionType.COLOR_CLUE, ActionType.RANK_CLUE):
                        next_action_by_target = "hint"
                    break

            hinter_name = players[hinter] if hinter < len(players) else str(hinter)
            target_name = players[target_player] if target_player < len(players) else str(target_player)

            hint_records.append({
                "game_id": game_id,
                "turn": state.turn - 1,  # turn was already incremented
                "hinter": hinter_name,
                "target_player": target_name,
                "hint_type": hint_type,
                "hint_value": hint_value,
                "cards_touched": cards_touched,
                "playable_cards_touched": playable_cards_touched,
                "candidates_before": candidates_before,
                "candidates_after": candidates_after,
                "disambiguation_power": (
                    (candidates_before - candidates_after) / candidates_before
                    if candidates_before > 0 else 0
                ),
                "next_action_by_target": next_action_by_target,
                "data_source": data_source,
            })
            continue  # already applied action

        # Apply non-hint action
        state.apply_action(translated)

    return hint_records


def link_hint_to_next_play(hint_df: pd.DataFrame, play_df: pd.DataFrame) -> pd.Series:
    """For each hint record, the outcome of the play record at (game_id, turn + 1), i.e. the
    target's immediately following action when it was a play. Returns a float Series aligned
    to hint_df.index: 1.0 = that play lost a life, 0.0 = succeeded, NaN = next action was not
    a play (no play record at turn + 1)."""
    key = play_df.drop_duplicates(["game_id", "turn"]).set_index(["game_id", "turn"])["was_playable"]
    assert key.index.is_unique
    nxt = pd.MultiIndex.from_arrays([hint_df["game_id"].values, hint_df["turn"].values + 1])
    y = key.reindex(nxt)
    return pd.Series(np.where(y.isna(), np.nan, 1.0 - y.astype(float)), index=hint_df.index)


def analyze_hint_quality(
    human_df_path: str,
    agent_dir: str,
    hai_dir: str,
    output_dir: Optional[Path] = None,
) -> pd.DataFrame:
    """Compute hint records across all datasets and analyze quality.

    Returns a DataFrame of all hint records.
    """
    import json
    from pathlib import Path as P

    out = ensure_output_dir(output_dir)
    all_hints = []

    # 1. hanab.live games
    print("Processing hanab.live hint records...")
    hl_dir = P(human_df_path)
    hl_files = sorted(hl_dir.glob("*.json"))
    for i, f in enumerate(hl_files):
        try:
            with open(f) as fh:
                game = json.load(fh)
            recs = compute_hint_records(game, data_source="hanab_live")
            for r in recs:
                r["hinter_type"] = "human"
                r["partner_type"] = "human"
            all_hints.extend(recs)
        except Exception:
            pass
    print(f"  hanab.live: {len(all_hints)} hint records from {len(hl_files)} games")

    # 2. HOAD agent games
    n_before = len(all_hints)
    print("Processing HOAD hint records...")
    hoad_dir = P(agent_dir)
    for f in sorted(hoad_dir.glob("*.json")):
        fname = f.stem  # e.g. "simple_vs_iggi"
        try:
            with open(f) as fh:
                games = json.load(fh)
            parts = fname.split("_vs_")
            if len(parts) != 2:
                continue
            subj, part = parts
            for game in games:
                recs = compute_hint_records(game, data_source="hoad")
                for r in recs:
                    # Determine hinter type based on player index
                    r["hinter_type"] = subj if r["hinter"] == game["players"][0] else part
                    r["partner_type"] = part if r["hinter"] == game["players"][0] else subj
                all_hints.extend(recs)
        except Exception:
            pass
    print(f"  HOAD: {len(all_hints) - n_before} hint records")

    # 3. HanabiData human-AI games
    n_before = len(all_hints)
    print("Processing HanabiData hint records...")
    hai_path = P(hai_dir)
    for f in sorted(hai_path.glob("*.json")):
        try:
            with open(f) as fh:
                game = json.load(fh)
            recs = compute_hint_records(game, data_source="hanabi_data")
            ai_type = game.get("metadata", {}).get("ai_type", "unknown")
            for r in recs:
                if r["hinter"] == game["players"][0]:
                    r["hinter_type"] = ai_type
                    r["partner_type"] = "human"
                else:
                    r["hinter_type"] = "human"
                    r["partner_type"] = ai_type
            all_hints.extend(recs)
        except Exception:
            pass
    print(f"  HanabiData: {len(all_hints) - n_before} hint records")

    hint_df = pd.DataFrame(all_hints)
    hint_df.to_csv(
        P(out).parent.parent / "data" / "processed" / "hint_records.csv",
        index=False,
    )
    print(f"\nTotal hint records: {len(hint_df):,}")

    # Analyze and print
    print("\n=== 8.2 Hint Quality Analysis ===\n")

    # Playability rate by source
    print("Playability Rate (% of touched cards that are playable):")
    print(f"{'Source':<25} {'N hints':>8} {'Cards/hint':>10} {'Playable %':>12} {'Disambig.':>10}")
    print("-" * 70)
    for source, sdf in [
        ("Human-Human", hint_df[hint_df["data_source"] == "hanab_live"]),
        ("AI-AI", hint_df[hint_df["data_source"] == "hoad"]),
    ]:
        if len(sdf) == 0:
            continue
        playable_rate = sdf["playable_cards_touched"].sum() / max(sdf["cards_touched"].sum(), 1) * 100
        disambig = sdf["disambiguation_power"].mean()
        cards_per = sdf["cards_touched"].mean()
        print(f"{source:<25} {len(sdf):>8,} {cards_per:>10.2f} {playable_rate:>11.1f}% {disambig:>10.3f}")

    # By AI type (HanabiData)
    hai_hints = hint_df[hint_df["data_source"] == "hanabi_data"]
    ai_hints = hai_hints[hai_hints["hinter_type"] != "human"]
    for ai_type in ["full", "intentional", "outer"]:
        sdf = ai_hints[ai_hints["hinter_type"] == ai_type]
        if len(sdf) == 0:
            continue
        playable_rate = sdf["playable_cards_touched"].sum() / max(sdf["cards_touched"].sum(), 1) * 100
        disambig = sdf["disambiguation_power"].mean()
        cards_per = sdf["cards_touched"].mean()
        print(f"AI: {ai_type:<20} {len(sdf):>8,} {cards_per:>10.2f} {playable_rate:>11.1f}% {disambig:>10.3f}")

    # Play-signal accuracy: observed outcome of the play at (game_id, turn + 1),
    # linked via link_hint_to_next_play (NOT the playable_cards_touched proxy).
    processed_dir = P(out).parent.parent / "data" / "processed"
    hai_play_path = processed_dir / "human_ai_play_records.csv"
    print("\nPlay-Signal Accuracy (hint → linked next-turn play → observed failure):")
    print(f"{'Source':<25} {'Hints':>7} {'→play %':>8} {'linked n':>9} {'observed failure %':>19}")
    print("-" * 74)
    if hai_play_path.exists():
        hai_plays = pd.read_csv(hai_play_path)
        human_plays = hai_plays[hai_plays["subject_type"] == "human"]
        for label, sdf in [
            (f"AI: {display_name('full')}→human", ai_hints[ai_hints["hinter_type"] == "full"]),
            (f"AI: {display_name('intentional')}→human", ai_hints[ai_hints["hinter_type"] == "intentional"]),
            (f"AI: {display_name('outer')}→human", ai_hints[ai_hints["hinter_type"] == "outer"]),
        ]:
            if len(sdf) == 0:
                continue
            play_frac = (sdf["next_action_by_target"] == "play").mean() * 100
            linked = link_hint_to_next_play(sdf, human_plays)
            n_linked = int(linked.notna().sum())
            fail_pct = linked.mean() * 100 if n_linked > 0 else float("nan")
            print(f"{label:<25} {len(sdf):>7,} {play_frac:>7.1f}% {n_linked:>9,} {fail_pct:>18.1f}%")
    else:
        print(f"  (skipped: {hai_play_path} not found)")

    # Plot — only include sources that actually have hint records
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    # Build source list, filtering out empty data
    all_sources = [
        ("AI-AI\n(HOAD)", hint_df[hint_df["data_source"] == "hoad"], "#4c72b0"),
        (f"AI: {display_name('full')}\n→human", ai_hints[ai_hints["hinter_type"] == "full"], "#c44e52"),
        (f"AI: {display_name('intentional')}\n→human", ai_hints[ai_hints["hinter_type"] == "intentional"], "#dd8452"),
        (f"AI: {display_name('outer')}\n→human", ai_hints[ai_hints["hinter_type"] == "outer"], "#55a868"),
    ]
    # Only keep sources with actual data
    sources = [(lbl, sdf, clr) for lbl, sdf, clr in all_sources if len(sdf) > 0]

    labels_src = [s[0] for s in sources]
    colors_src = [s[2] for s in sources]

    # Panel 1: Disambiguation power by source (in %)
    ax = axes[0]
    vals = [s[1]["disambiguation_power"].mean() * 100 for s in sources]
    bars = ax.bar(range(len(labels_src)), vals, color=colors_src, edgecolor="white", width=0.6)
    ax.set_xticks(range(len(labels_src)))
    ax.set_xticklabels(labels_src, fontsize=9)
    ax.set_ylabel("Disambiguation Power (%)", fontsize=11)
    ax.set_title("Hint Disambiguation Power\n(% of candidates eliminated)", fontsize=12)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                f"{val:.1f}%", ha="center", fontsize=10, fontweight="bold")

    # Panel 2: Playability rate
    ax = axes[1]
    vals2 = []
    for _, sdf, _ in sources:
        total_touched = sdf["cards_touched"].sum()
        if total_touched > 0:
            vals2.append(sdf["playable_cards_touched"].sum() / total_touched * 100)
        else:
            vals2.append(0)
    bars = ax.bar(range(len(labels_src)), vals2, color=colors_src, edgecolor="white", width=0.6)
    ax.set_xticks(range(len(labels_src)))
    ax.set_xticklabels(labels_src, fontsize=9)
    ax.set_ylabel("% Touched Cards Playable", fontsize=11)
    ax.set_title("Hint Playability Rate\n(% of touched cards currently playable)", fontsize=12)
    for bar, val in zip(bars, vals2):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                f"{val:.1f}%", ha="center", fontsize=10, fontweight="bold")
    ax.set_ylim(0, 100)

    # Panel 3: Next action after hint
    ax = axes[2]
    action_types = ["play", "discard", "hint"]
    x_pos = np.arange(len(labels_src))
    bottom = np.zeros(len(labels_src))
    action_colors = {"play": "#55a868", "discard": "#dd8452", "hint": "#4c72b0"}
    for act in action_types:
        fracs = []
        for _, sdf, _ in sources:
            fracs.append((sdf["next_action_by_target"] == act).mean() * 100)
        ax.bar(x_pos, fracs, bottom=bottom, width=0.6, label=act.capitalize(),
               color=action_colors[act], edgecolor="white")
        bottom += fracs
    ax.set_xticks(x_pos)
    ax.set_xticklabels(labels_src, fontsize=9)
    ax.set_ylabel("% of Hints", fontsize=11)
    ax.set_title("Target's Next Action After Hint", fontsize=12)
    ax.legend(fontsize=9)
    ax.set_ylim(0, 105)

    fig.suptitle("Hint-Level Quality Metrics", fontsize=14, y=1.03)
    fig.tight_layout()
    fig.savefig(out / "phase8_hint_quality.png", dpi=150, bbox_inches="tight")
    logger.info("Saved phase8_hint_quality.png")

    return hint_df


# ------------------------------------------------------------------
# 8.3 Within-Player Convention Learning
# ------------------------------------------------------------------

def analyze_convention_learning(
    human_df: pd.DataFrame,
    human_ai_df: pd.DataFrame,
    agent_df: Optional[pd.DataFrame] = None,
    output_dir: Optional[Path] = None,
) -> dict:
    """Track how individual players' convention gaps evolve over games.

    Returns dict with learning statistics.
    """
    from scipy import stats as sp_stats

    out = ensure_output_dir(output_dir)
    results = {}

    # --- hanab.live: per-player learning ---
    hh = human_df.copy()
    hh["life_lost"] = (~hh["was_playable"]).astype(int)

    # Per-game convention gap
    game_gaps = hh.groupby(["player", "game_id"]).agg(
        mean_posterior=("posterior_p_life_loss", "mean"),
        loss_rate=("life_lost", "mean"),
        n_plays=("life_lost", "count"),
    ).reset_index()
    game_gaps["gap"] = game_gaps["mean_posterior"] - game_gaps["loss_rate"]

    # Order games chronologically per player (game_id as proxy)
    game_gaps = game_gaps.sort_values(["player", "game_id"])
    game_gaps["game_seq"] = game_gaps.groupby("player").cumcount() + 1

    # Players with 10+ games
    games_per = game_gaps.groupby("player")["game_id"].count()
    eligible = games_per[games_per >= 10].index
    print(f"\n=== 8.3 Convention Learning Analysis ===\n")
    print(f"Players with 10+ games: {len(eligible)}")

    slopes = []
    for player in eligible:
        pg = game_gaps[game_gaps["player"] == player]
        if len(pg) < 10:
            continue
        slope, intercept, r_val, p_val, std_err = sp_stats.linregress(pg["game_seq"], pg["gap"])
        slopes.append({
            "player": player,
            "n_games": len(pg),
            "slope": slope,
            "r_squared": r_val ** 2,
            "p_value": p_val,
            "mean_gap": pg["gap"].mean(),
        })

    slopes_df = pd.DataFrame(slopes)
    results["hanab_live_slopes"] = slopes_df

    positive_frac = (slopes_df["slope"] > 0).mean() * 100
    sig_positive = ((slopes_df["slope"] > 0) & (slopes_df["p_value"] < 0.05)).sum()
    sig_negative = ((slopes_df["slope"] < 0) & (slopes_df["p_value"] < 0.05)).sum()

    print(f"Positive slope (improving): {positive_frac:.1f}% of players")
    print(f"Significant positive (p<0.05): {sig_positive}")
    print(f"Significant negative (p<0.05): {sig_negative}")
    print(f"Mean slope: {slopes_df['slope'].mean():+.4f} per game")
    print(f"Median slope: {slopes_df['slope'].median():+.4f} per game")

    # By individual skill level
    if "individual_skill" not in hh.columns:
        add_individual_skill_columns(hh)
    skill_map = hh.groupby("player")["individual_skill"].first()
    slopes_df["individual_skill"] = slopes_df["player"].map(skill_map)
    print("\nMean learning rate by skill:")
    for skill in ["beginner", "intermediate", "expert"]:
        sub = slopes_df[slopes_df["individual_skill"] == skill]
        if len(sub) > 0:
            print(f"  {skill}: {sub['slope'].mean():+.5f}/game (n={len(sub)})")

    # --- HanabiData: learning with AI partners ---
    # Recover individual participant IDs from mapping file
    hai = human_ai_df[human_ai_df["subject_type"] == "human"].copy()
    hai["life_lost"] = (~hai["was_playable"]).astype(int)

    participant_map_path = Path(__file__).resolve().parent.parent / "data" / "processed" / "hai_game_participant_map.csv"
    if participant_map_path.exists():
        pmap = pd.read_csv(participant_map_path)
        hai = hai.merge(pmap, on="game_id", how="left")
        print(f"\nMapped {hai['participant_id'].notna().sum()}/{len(hai)} HAI records to participants")
    else:
        hai["participant_id"] = "Human"
        print("\nWarning: hai_game_participant_map.csv not found, using pooled 'Human'")

    # Per-game gaps per (participant, partner_type)
    hai_game_gaps = hai.groupby(["participant_id", "partner_type", "game_id"]).agg(
        mean_posterior=("posterior_p_life_loss", "mean"),
        loss_rate=("life_lost", "mean"),
        n_plays=("life_lost", "count"),
    ).reset_index()
    hai_game_gaps["gap"] = hai_game_gaps["mean_posterior"] - hai_game_gaps["loss_rate"]
    hai_game_gaps = hai_game_gaps.sort_values(["participant_id", "partner_type", "game_id"])
    hai_game_gaps["game_seq"] = hai_game_gaps.groupby(
        ["participant_id", "partner_type"]
    ).cumcount() + 1

    # Aggregate stats by AI partner type (pooled across participants)
    print("\nHuman-AI convention learning by AI partner type (pooled):")
    hai_slopes = {}
    for ai_type in ["full", "intentional", "outer"]:
        sub = hai_game_gaps[hai_game_gaps["partner_type"] == ai_type]
        if len(sub) < 10:
            continue
        slope, _, r_val, p_val, _ = sp_stats.linregress(sub["game_seq"], sub["gap"])
        hai_slopes[ai_type] = {"slope": slope, "r2": r_val**2, "p": p_val, "n": len(sub)}
        print(f"  vs {ai_type}: slope={slope:+.6f}/game, R²={r_val**2:.4f}, p={p_val:.4f}, n={len(sub)}")
    results["hai_slopes"] = hai_slopes

    # --- Compute per-(participant, partner_type) learning slopes ---
    min_games_hai = 10  # match the human-human threshold for comparable slope estimates
    hai_trial_games = hai_game_gaps.groupby(["participant_id", "partner_type"])["game_id"].count()
    hai_slope_list = []
    for (pid, ptype), grp in hai_game_gaps.groupby(["participant_id", "partner_type"]):
        if len(grp) < min_games_hai:
            continue
        slope, _, r_val, p_val, _ = sp_stats.linregress(grp["game_seq"], grp["gap"])
        hai_slope_list.append({
            "participant_id": pid,
            "partner_type": ptype,
            "n_games": len(grp),
            "slope": slope,
            "r_squared": r_val ** 2,
            "p_value": p_val,
        })
    hai_slopes_df = pd.DataFrame(hai_slope_list)
    results["hai_slopes_df"] = hai_slopes_df

    if len(hai_slopes_df) > 0:
        hai_pos_frac = (hai_slopes_df["slope"] > 0).mean() * 100
        hai_sig_pos = ((hai_slopes_df["slope"] > 0) & (hai_slopes_df["p_value"] < 0.05)).sum()
        hai_sig_neg = ((hai_slopes_df["slope"] < 0) & (hai_slopes_df["p_value"] < 0.05)).sum()
        print(f"\nHuman-vs-AI learning slopes ({len(hai_slopes_df)} trials with {min_games_hai}+ games):")
        print(f"  Positive slope: {hai_pos_frac:.1f}%")
        print(f"  Significant positive (p<0.05): {hai_sig_pos}")
        print(f"  Significant negative (p<0.05): {hai_sig_neg}")
        print(f"  Mean slope: {hai_slopes_df['slope'].mean():+.6f}")
        print(f"  By AI partner:")
        for ptype in ["full", "intentional", "outer"]:
            sub = hai_slopes_df[hai_slopes_df["partner_type"] == ptype]
            if len(sub) > 0:
                print(f"    vs {ptype}: {len(sub)} trials, mean slope={sub['slope'].mean():+.6f}")

    return results


# ------------------------------------------------------------------
# 8.4 Failure Mode Analysis
# ------------------------------------------------------------------

def classify_failures(df: pd.DataFrame) -> pd.DataFrame:
    """Add failure_category column to a play records DataFrame.

    Categories:
    - blind_play: 0 hints, posterior > 0.5
    - misread_hint: 1+ hints, posterior 0.1-0.5
    - calculated_risk: 1+ hints, posterior 0.01-0.1
    - desperate_play: life_tokens == 1 (any posterior)
    - convention_failure: 1+ hints, posterior > 0.5, but played anyway
    - success: not a failure
    """
    df = df.copy()
    if "life_lost" not in df.columns:
        df["life_lost"] = (~df["was_playable"]).astype(int)

    # Order matters: desperate overrides others
    is_failure = ~df["was_playable"]
    desperate = is_failure & (df["life_tokens"] == 1)
    blind = is_failure & (df["hints_on_card"] == 0) & (df["posterior_p_life_loss"] > 0.5) & ~desperate
    convention_fail = is_failure & (df["hints_on_card"] >= 1) & (df["posterior_p_life_loss"] > 0.5) & ~desperate
    misread = is_failure & (df["hints_on_card"] >= 1) & (df["posterior_p_life_loss"] >= 0.1) & (df["posterior_p_life_loss"] <= 0.5) & ~desperate
    # Table A11: calculated risk = 1+ hints, posterior in [0.01, 0.1)
    calculated = is_failure & (df["hints_on_card"] >= 1) & (df["posterior_p_life_loss"] >= 0.01) & (df["posterior_p_life_loss"] < 0.1) & ~desperate
    # Failures that don't fit any Table A11 bucket (0-hint low-posterior, or 1+ hint posterior<0.01)
    other_fail = is_failure & ~desperate & ~blind & ~convention_fail & ~misread & ~calculated

    df["failure_category"] = "success"
    df.loc[blind, "failure_category"] = "blind_play"
    df.loc[misread, "failure_category"] = "misread_hint"
    df.loc[calculated, "failure_category"] = "calculated_risk"
    df.loc[desperate, "failure_category"] = "desperate_play"
    df.loc[convention_fail, "failure_category"] = "convention_failure"
    df.loc[other_fail, "failure_category"] = "other_failure"

    return df


def analyze_failure_modes(
    human_df: pd.DataFrame,
    agent_df: pd.DataFrame,
    human_ai_df: pd.DataFrame,
    output_dir: Optional[Path] = None,
) -> dict:
    """Classify and analyze failure modes across all datasets."""
    out = ensure_output_dir(output_dir)

    # Classify all datasets
    hh = classify_failures(human_df)
    aa = classify_failures(agent_df)
    hai = classify_failures(human_ai_df)

    results = {}

    print("\n=== 8.4 Failure Mode Analysis ===\n")

    # Failure category distribution
    categories = ["blind_play", "misread_hint", "calculated_risk", "desperate_play", "convention_failure"]

    def _failure_dist(df, label):
        failures = df[df["failure_category"] != "success"]
        if len(failures) == 0:
            return {}
        dist = {}
        print(f"\n{label} (N failures = {len(failures):,}, total plays = {len(df):,}, loss rate = {len(failures)/len(df)*100:.1f}%):")
        for cat in categories:
            n = (failures["failure_category"] == cat).sum()
            pct = n / len(failures) * 100 if len(failures) > 0 else 0
            dist[cat] = {"n": n, "pct": pct}
            print(f"  {cat:<22} {n:>6,}  ({pct:>5.1f}%)")
        return dist

    results["human_human"] = _failure_dist(hh, "Human-Human")
    results["agent_agent"] = _failure_dist(aa, "AI-AI")

    # By AI partner type
    hai_human = hai[hai["subject_type"] == "human"]
    for ai_type in ["full", "intentional", "outer"]:
        sub = hai_human[hai_human["partner_type"] == ai_type]
        results[f"human_vs_{ai_type}"] = _failure_dist(sub, f"Human vs {display_name(ai_type)}")

    # AI failures
    for ai_type in ["full", "intentional", "outer"]:
        sub = hai[hai["subject_type"] == ai_type]
        results[f"ai_{ai_type}"] = _failure_dist(sub, f"AI: {display_name(ai_type)} (own failures)")

    # Game phase distribution of failures
    print("\n\nFailure Distribution by Game Phase:")
    print(f"{'Setting':<25} {'Early %':>8} {'Mid %':>8} {'Late %':>8}")
    print("-" * 55)

    for label, df_sub in [
        ("Human-Human", hh),
        (f"Human vs {display_name('full')}", hai_human[hai_human["partner_type"] == "full"]),
        (f"Human vs {display_name('intentional')}", hai_human[hai_human["partner_type"] == "intentional"]),
        (f"Human vs {display_name('outer')}", hai_human[hai_human["partner_type"] == "outer"]),
    ]:
        df_sub = df_sub.copy()
        if "game_phase" not in df_sub.columns or df_sub["game_phase"].isna().all():
            df_sub["game_phase"] = pd.cut(
                df_sub["turn"], bins=[-1, 15, 35, 200],
                labels=["early", "mid", "late"], right=True,
            )
        failures = df_sub[df_sub["failure_category"] != "success"]
        if len(failures) == 0:
            continue
        phase_dist = failures["game_phase"].value_counts(normalize=True) * 100
        print(f"{label:<25} {phase_dist.get('early', 0):>7.1f}% {phase_dist.get('mid', 0):>7.1f}% {phase_dist.get('late', 0):>7.1f}%")

    # Cascade analysis: convention gap 5 turns before vs after life loss
    print("\nCascade Analysis (convention gap before/after life loss):")
    for label, df_sub in [
        ("Human-Human", hh),
        (f"Human vs {display_name('full')}", hai_human[hai_human["partner_type"] == "full"]),
        (f"Human vs {display_name('intentional')}", hai_human[hai_human["partner_type"] == "intentional"]),
        (f"Human vs {display_name('outer')}", hai_human[hai_human["partner_type"] == "outer"]),
    ]:
        df_sub = df_sub.copy()
        df_sub = df_sub.sort_values(["game_key", "turn"])
        failures = df_sub[df_sub["failure_category"] != "success"]

        gaps_before = []
        gaps_after = []
        for _, fail_row in failures.iterrows():
            game = df_sub[df_sub["game_key"] == fail_row["game_key"]]
            turn = fail_row["turn"]
            before = game[(game["turn"] >= turn - 5) & (game["turn"] < turn)]
            after = game[(game["turn"] > turn) & (game["turn"] <= turn + 5)]
            if len(before) >= 2:
                gaps_before.append(before["posterior_p_life_loss"].mean() - before["life_lost"].mean())
            if len(after) >= 2:
                gaps_after.append(after["posterior_p_life_loss"].mean() - after["life_lost"].mean())

        if gaps_before and gaps_after:
            print(f"  {label}: before={np.mean(gaps_before):+.3f}, after={np.mean(gaps_after):+.3f}, delta={np.mean(gaps_after)-np.mean(gaps_before):+.3f}")

    # Recovery rate: fraction of games reaching 15+ after 1 life loss
    print("\nRecovery Rate (games reaching score 15+ after losing 1+ life):")
    for label, df_sub in [
        ("Human-Human", hh),
        (f"Human vs {display_name('full')}", hai_human[hai_human["partner_type"] == "full"]),
        (f"Human vs {display_name('intentional')}", hai_human[hai_human["partner_type"] == "intentional"]),
        (f"Human vs {display_name('outer')}", hai_human[hai_human["partner_type"] == "outer"]),
    ]:
        # Games with at least 1 failure
        games_with_fail = df_sub[df_sub["failure_category"] != "success"]["game_key"].unique()
        if len(games_with_fail) == 0:
            continue
        # Final score in games with failures
        game_scores = df_sub[df_sub["game_key"].isin(games_with_fail)].groupby("game_key")["final_score"].first()
        recovery = (game_scores >= 15).mean() * 100
        print(f"  {label}: {recovery:.1f}% of {len(games_with_fail)} games with failures reach score 15+")

    # Plot
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    # Panel 1: Failure category distribution
    ax = axes[0]
    cat_colors = {
        "blind_play": "#c44e52", "misread_hint": "#dd8452",
        "calculated_risk": "#55a868", "desperate_play": "#4c72b0",
        "convention_failure": "#9467bd",
    }
    plot_labels = ["Human\n-Human", f"Human\nvs {display_name('full')}", f"Human\nvs {display_name('intentional')}", f"Human\nvs {display_name('outer')}"]
    plot_dfs = [
        hh, hai_human[hai_human["partner_type"] == "full"],
        hai_human[hai_human["partner_type"] == "intentional"],
        hai_human[hai_human["partner_type"] == "outer"],
    ]
    x_pos = np.arange(len(plot_labels))
    bottom = np.zeros(len(plot_labels))
    for cat in categories:
        fracs = []
        for df_sub in plot_dfs:
            failures = df_sub[df_sub["failure_category"] != "success"]
            if len(failures) > 0:
                fracs.append((failures["failure_category"] == cat).mean() * 100)
            else:
                fracs.append(0)
        ax.bar(x_pos, fracs, bottom=bottom, width=0.6, label=cat.replace("_", " ").title(),
               color=cat_colors[cat], edgecolor="white")
        bottom += fracs
    ax.set_xticks(x_pos)
    ax.set_xticklabels(plot_labels, fontsize=9)
    ax.set_ylabel("% of Failures", fontsize=11)
    ax.set_title("Failure Category Distribution", fontsize=12)
    ax.legend(fontsize=8, loc="upper right")

    # Panel 2: Failure rate by game phase
    ax = axes[1]
    phases = ["early", "mid", "late"]
    phase_colors = {"early": "#dd8452", "mid": "#4c72b0", "late": "#55a868"}
    x_pos = np.arange(len(plot_labels))
    width = 0.25
    for i, phase in enumerate(phases):
        vals = []
        for df_sub in plot_dfs:
            df_sub2 = df_sub.copy()
            if "game_phase" not in df_sub2.columns or df_sub2["game_phase"].isna().all():
                df_sub2["game_phase"] = pd.cut(
                    df_sub2["turn"], bins=[-1, 15, 35, 200],
                    labels=["early", "mid", "late"], right=True,
                )
            phase_data = df_sub2[df_sub2["game_phase"] == phase]
            vals.append(phase_data["life_lost"].mean() * 100 if len(phase_data) > 0 else 0)
        ax.bar(x_pos + i * width - width, vals, width, label=phase.capitalize(),
               color=phase_colors[phase], edgecolor="white")
    ax.set_xticks(x_pos)
    ax.set_xticklabels(plot_labels, fontsize=9)
    ax.set_ylabel("Life-Loss Rate (%)", fontsize=11)
    ax.set_title("Failure Rate by Game Phase", fontsize=12)
    ax.legend(fontsize=9)

    # Panel 3: Cascade effect
    ax = axes[2]
    cascade_data = []
    cascade_labels = []
    for label, df_sub in [
        ("HH", hh),
        ("vs full", hai_human[hai_human["partner_type"] == "full"]),
        ("vs intent.", hai_human[hai_human["partner_type"] == "intentional"]),
        ("vs outer", hai_human[hai_human["partner_type"] == "outer"]),
    ]:
        df_sub = df_sub.copy().sort_values(["game_key", "turn"])
        failures = df_sub[df_sub["failure_category"] != "success"]
        gb = []
        ga = []
        for _, fail_row in failures.iterrows():
            game = df_sub[df_sub["game_key"] == fail_row["game_key"]]
            turn = fail_row["turn"]
            before = game[(game["turn"] >= turn - 5) & (game["turn"] < turn)]
            after = game[(game["turn"] > turn) & (game["turn"] <= turn + 5)]
            if len(before) >= 2:
                gb.append(before["posterior_p_life_loss"].mean() - before["life_lost"].mean())
            if len(after) >= 2:
                ga.append(after["posterior_p_life_loss"].mean() - after["life_lost"].mean())
        if gb and ga:
            cascade_data.append((np.mean(gb), np.mean(ga)))
            cascade_labels.append(label)

    if cascade_data:
        x_pos = np.arange(len(cascade_labels))
        w = 0.35
        before_vals = [d[0] for d in cascade_data]
        after_vals = [d[1] for d in cascade_data]
        ax.bar(x_pos - w/2, before_vals, w, label="Before failure", color="#4c72b0", edgecolor="white")
        ax.bar(x_pos + w/2, after_vals, w, label="After failure", color="#c44e52", edgecolor="white")
        ax.set_xticks(x_pos)
        ax.set_xticklabels(cascade_labels, fontsize=10)
        ax.set_ylabel("Convention Gap", fontsize=11)
        ax.set_title("Cascade Effect: Gap Before/After Life Loss", fontsize=12)
        ax.legend(fontsize=10)
        ax.axhline(0, color="black", linewidth=0.5)

    fig.suptitle("Failure Mode Analysis", fontsize=14, y=1.03)
    fig.tight_layout()
    fig.savefig(out / "phase8_failure_modes.png", dpi=150, bbox_inches="tight")
    logger.info("Saved phase8_failure_modes.png")

    return results
