"""Cluster-robust statistics for convention-gap inference.

Utilities promoted from the Phase-1 rebuttal scripts (rebuttal/run_analyses.py)
into src/ for v8:

- ``cluster_bootstrap_gap_ci``: percentile bootstrap CI for the convention
  gap (mean posterior - loss rate), resampling plays, games, or
  players/participants with replacement.
- ``cluster_robust_se_mean``: CR0 sandwich standard error of a sample mean
  under cluster correlation.
- ``clustered_diff_z``: two-sample z for a difference in means with
  cluster-robust SEs on each side.
- ``paired_stats``: within-participant paired contrast summary (mean,
  t-based CI, sign counts, sign-test p, Wilcoxon p).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as st

DEFAULT_N_BOOT = 10_000
DEFAULT_SEED = 42


def cluster_bootstrap_gap_ci(
    df: pd.DataFrame,
    cluster_col: str | None,
    n_boot: int = DEFAULT_N_BOOT,
    seed: int = DEFAULT_SEED,
    post_col: str = "posterior_p_life_loss",
    loss_col: str = "life_lost",
) -> np.ndarray:
    """95% percentile bootstrap CI for (mean posterior - loss rate).

    ``cluster_col=None`` resamples individual plays (play-level bootstrap);
    otherwise whole clusters (games or players) are resampled with
    replacement, which accounts for within-cluster correlation. Vectorized
    via per-cluster sums.
    """
    rng = np.random.default_rng(seed)
    if cluster_col is None:
        post = df[post_col].to_numpy(float)
        lost = df[loss_col].to_numpy(float)
        n = len(df)
        gaps = np.empty(n_boot)
        for b in range(n_boot):
            idx = rng.integers(0, n, n)
            gaps[b] = post[idx].mean() - lost[idx].mean()
        return np.percentile(gaps, [2.5, 97.5])

    g = df.groupby(cluster_col).agg(
        sp=(post_col, "sum"), sl=(loss_col, "sum"), n=(post_col, "size")
    )
    sp, sl, n = g["sp"].to_numpy(), g["sl"].to_numpy(), g["n"].to_numpy(float)
    n_c = len(g)
    gaps = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, n_c, n_c)
        gaps[b] = (sp[idx].sum() - sl[idx].sum()) / n[idx].sum()
    return np.percentile(gaps, [2.5, 97.5])


def cluster_robust_se_mean(x: np.ndarray, clusters: np.ndarray) -> float:
    """CR0 cluster-robust standard error of the sample mean of ``x``."""
    m = x.mean()
    resid = pd.Series(x - m).groupby(pd.Series(clusters)).sum()
    return float(np.sqrt((resid.to_numpy() ** 2).sum()) / len(x))


def clustered_diff_z(
    a: pd.DataFrame,
    b: pd.DataFrame,
    value_col: str,
    cluster_col: str,
) -> tuple[float, float]:
    """Two-sample z-test for mean(a) - mean(b) with CR0 clustered SEs.

    Returns (z, two_sided_p).
    """
    m1 = a[value_col].mean()
    m2 = b[value_col].mean()
    se1 = cluster_robust_se_mean(a[value_col].to_numpy(float), a[cluster_col].to_numpy())
    se2 = cluster_robust_se_mean(b[value_col].to_numpy(float), b[cluster_col].to_numpy())
    z = (m1 - m2) / np.sqrt(se1**2 + se2**2)
    p = float(st.norm.sf(abs(z)) * 2)
    return float(z), p


def paired_stats(diffs: np.ndarray) -> dict:
    """Summary of a within-participant paired contrast.

    Returns dict with mean, 95% t-based CI, sign counts, two-sided
    sign-test p, and Wilcoxon signed-rank p.
    """
    diffs = np.asarray(diffs, dtype=float)
    n = len(diffs)
    mean = diffs.mean()
    se = diffs.std(ddof=1) / np.sqrt(n)
    tcrit = st.t.ppf(0.975, n - 1)
    npos = int((diffs > 0).sum())
    nneg = int((diffs < 0).sum())
    sign_p = (
        st.binomtest(npos, npos + nneg, 0.5).pvalue if npos + nneg else float("nan")
    )
    try:
        wil_p = (
            st.wilcoxon(diffs[diffs != 0]).pvalue
            if (diffs != 0).any()
            else float("nan")
        )
    except ValueError:
        wil_p = float("nan")
    return {
        "n": n,
        "mean": float(mean),
        "ci": (float(mean - tcrit * se), float(mean + tcrit * se)),
        "n_pos": npos,
        "n_neg": nneg,
        "sign_p": float(sign_p),
        "wilcoxon_p": float(wil_p),
    }
