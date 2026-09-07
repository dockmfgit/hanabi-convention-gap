"""Tests for cluster-robust statistics (src/cluster_stats.py)."""

import numpy as np
import pandas as pd
from scipy import stats as st

from src.cluster_stats import (
    cluster_bootstrap_gap_ci,
    cluster_robust_se_mean,
    clustered_diff_z,
    paired_stats,
)


def make_df(n_games=50, plays_per_game=10, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for g in range(n_games):
        game_effect = rng.normal(0, 0.1)
        for _ in range(plays_per_game):
            post = float(np.clip(0.3 + game_effect + rng.normal(0, 0.1), 0, 1))
            lost = int(rng.random() < 0.1)
            rows.append({"game_key": f"g{g}", "posterior_p_life_loss": post,
                         "life_lost": lost})
    return pd.DataFrame(rows)


class TestClusterBootstrap:
    def test_play_level_ci_covers_point_estimate(self):
        df = make_df()
        gap = df["posterior_p_life_loss"].mean() - df["life_lost"].mean()
        lo, hi = cluster_bootstrap_gap_ci(df, None, n_boot=500)
        assert lo < gap < hi

    def test_cluster_ci_covers_point_estimate(self):
        df = make_df()
        gap = df["posterior_p_life_loss"].mean() - df["life_lost"].mean()
        lo, hi = cluster_bootstrap_gap_ci(df, "game_key", n_boot=500)
        assert lo < gap < hi

    def test_cluster_ci_at_least_as_wide_with_cluster_correlation(self):
        """With strong within-game correlation, the game-cluster CI should be
        wider than the play-level CI."""
        rng = np.random.default_rng(1)
        rows = []
        for g in range(40):
            game_post = rng.uniform(0.1, 0.9)  # whole game shares one value
            for _ in range(20):
                rows.append({"game_key": f"g{g}",
                             "posterior_p_life_loss": game_post,
                             "life_lost": 0})
        df = pd.DataFrame(rows)
        lo_p, hi_p = cluster_bootstrap_gap_ci(df, None, n_boot=800)
        lo_c, hi_c = cluster_bootstrap_gap_ci(df, "game_key", n_boot=800)
        assert (hi_c - lo_c) > (hi_p - lo_p)

    def test_reproducible_with_seed(self):
        df = make_df()
        a = cluster_bootstrap_gap_ci(df, "game_key", n_boot=200, seed=7)
        b = cluster_bootstrap_gap_ci(df, "game_key", n_boot=200, seed=7)
        assert np.allclose(a, b)


class TestClusterRobustSE:
    def test_reduces_to_iid_se_with_singleton_clusters(self):
        rng = np.random.default_rng(2)
        x = rng.normal(0, 1, 500)
        clusters = np.arange(500)  # each obs its own cluster
        se_cr = cluster_robust_se_mean(x, clusters)
        se_iid = x.std(ddof=0) / np.sqrt(len(x))
        assert abs(se_cr - se_iid) / se_iid < 1e-10

    def test_inflates_with_perfect_within_cluster_correlation(self):
        rng = np.random.default_rng(3)
        vals = rng.normal(0, 1, 50)
        x = np.repeat(vals, 10)          # 10 identical obs per cluster
        clusters = np.repeat(np.arange(50), 10)
        se_cr = cluster_robust_se_mean(x, clusters)
        se_iid = x.std(ddof=0) / np.sqrt(len(x))
        # Perfect correlation in clusters of 10 → SE inflates ~sqrt(10)
        assert se_cr > 2.5 * se_iid


class TestClusteredDiffZ:
    def test_matches_welch_with_singleton_clusters(self):
        rng = np.random.default_rng(4)
        a = pd.DataFrame({"v": rng.normal(0.2, 1, 400), "c": np.arange(400)})
        b = pd.DataFrame({"v": rng.normal(0.0, 1, 300), "c": np.arange(300)})
        z, p = clustered_diff_z(a, b, "v", "c")
        t_w, _ = st.ttest_ind(a["v"], b["v"], equal_var=False)
        # With singleton clusters CR0 ~ i.i.d.; z should be close to Welch t
        assert abs(z - t_w) < 0.05


class TestPairedStats:
    def test_known_answer(self):
        diffs = np.array([1.0, 2.0, 3.0, -1.0, 2.0])
        r = paired_stats(diffs)
        assert r["n"] == 5
        assert abs(r["mean"] - 1.4) < 1e-12
        assert r["n_pos"] == 4 and r["n_neg"] == 1
        assert 0 <= r["sign_p"] <= 1
        assert 0 <= r["wilcoxon_p"] <= 1

    def test_all_positive_sign_test(self):
        diffs = np.ones(22)  # mirrors the 22/0 Full-Outer split
        r = paired_stats(diffs)
        assert r["n_pos"] == 22 and r["n_neg"] == 0
        # two-sided sign test with 22/0: p = 2 * 0.5^22
        assert abs(r["sign_p"] - 2 * 0.5**22) < 1e-12
