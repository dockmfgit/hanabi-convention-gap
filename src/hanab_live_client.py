"""Client for fetching and caching Hanabi game data from hanab.live.

Endpoints used:
    - /api/v1/history-full/{player}   — paginated game history for a player
    - /api/v1/variants/{variant_id}   — paginated game list for a variant
    - /export/{game_id}               — full game replay JSON (deck + actions)

All responses are cached locally as JSON files under data/raw/.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Optional

import requests

# Use the OS trust store so corporate proxy CAs (e.g. Netskope) are trusted
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass  # Not needed if standard certs work

logger = logging.getLogger(__name__)

BASE_URL = "https://hanab.live"
API_V1 = f"{BASE_URL}/api/v1"

# "No Variant" is variant ID 0 on hanab.live
NO_VARIANT_ID = 0

# Conservative rate limit: 1 request per second
REQUEST_DELAY = 1.0

# Default data directory (relative to project root)
DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class HanabLiveClient:
    """Fetches and caches game data from hanab.live."""

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        request_delay: float = REQUEST_DELAY,
    ):
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
        self.raw_dir = self.data_dir / "raw"
        self.exports_dir = self.raw_dir / "exports"
        self.history_dir = self.raw_dir / "history"
        self.request_delay = request_delay
        self._last_request_time: float = 0.0

        # Create cache directories
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        self.history_dir.mkdir(parents=True, exist_ok=True)

        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def _rate_limit(self) -> None:
        """Enforce minimum delay between requests."""
        elapsed = time.monotonic() - self._last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)

    def _get(self, url: str) -> dict | list:
        """Make a rate-limited GET request and return parsed JSON."""
        self._rate_limit()
        logger.debug("GET %s", url)
        resp = self.session.get(url, timeout=30)
        self._last_request_time = time.monotonic()
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Game export (deck + actions)
    # ------------------------------------------------------------------

    def get_game_export(self, game_id: int, use_cache: bool = True) -> dict:
        """Fetch the full game replay JSON for a single game.

        Returns the dict with keys: id, players, deck, actions, notes, seed.
        """
        cache_path = self.exports_dir / f"{game_id}.json"

        if use_cache and cache_path.exists():
            with open(cache_path) as f:
                return json.load(f)

        data = self._get(f"{BASE_URL}/export/{game_id}")

        with open(cache_path, "w") as f:
            json.dump(data, f)

        return data

    # ------------------------------------------------------------------
    # Player history
    # ------------------------------------------------------------------

    def get_player_history(
        self,
        player: str,
        use_cache: bool = True,
    ) -> list[dict]:
        """Fetch a player's full game history.

        The history-full endpoint returns ALL games in a single response
        (no pagination). Results are cached per player.

        Returns a list of game summary dicts (not full exports).
        """
        cache_path = self.history_dir / f"player_{player}.json"

        if use_cache and cache_path.exists():
            with open(cache_path) as f:
                return json.load(f)

        data = self._get(f"{API_V1}/history-full/{player}")

        with open(cache_path, "w") as f:
            json.dump(data, f)

        return data

    # ------------------------------------------------------------------
    # Variant-based game listing
    # ------------------------------------------------------------------

    def get_variant_games(
        self,
        variant_id: int = NO_VARIANT_ID,
        page: int = 0,
        size: int = 100,
        num_players: Optional[int] = None,
        use_cache: bool = True,
    ) -> list[dict]:
        """Fetch one page of games for a specific variant.

        The variant endpoint returns rows with: id, num_players, score,
        users, datetime, seed.

        Args:
            variant_id: Variant ID (0 = "No Variant").
            page: 0-indexed page number.
            size: Results per page (max 100).
            num_players: If set, filter by player count.
            use_cache: Use cached response if available.
        """
        suffix = f"_np{num_players}" if num_players else ""
        cache_path = (
            self.raw_dir
            / f"variant_{variant_id}_p{page}_s{size}{suffix}.json"
        )

        if use_cache and cache_path.exists():
            with open(cache_path) as f:
                return json.load(f)

        url = f"{API_V1}/variants/{variant_id}?size={size}&page={page}"
        # Sort by id descending (most recent first)
        url += "&col[0]=1"
        # Filter by num_players if requested
        if num_players is not None:
            url += f"&fcol[1]={num_players}"

        data = self._get(url)

        with open(cache_path, "w") as f:
            json.dump(data, f)

        return data

    # ------------------------------------------------------------------
    # Bulk collection helpers
    # ------------------------------------------------------------------

    def collect_game_ids(
        self,
        variant_id: int = NO_VARIANT_ID,
        num_players: int = 2,
        max_games: int = 5000,
        use_cache: bool = True,
    ) -> list[int]:
        """Collect game IDs from the variant endpoint.

        Paginates through recent games of the specified variant and
        player count, returning up to max_games IDs.
        """
        game_ids = []
        page = 0
        size = 100

        while len(game_ids) < max_games:
            data = self.get_variant_games(
                variant_id=variant_id,
                page=page,
                size=size,
                num_players=num_players,
                use_cache=use_cache,
            )
            rows = data.get("rows", [])
            if not rows:
                break

            for row in rows:
                game_ids.append(row["id"])
                if len(game_ids) >= max_games:
                    break

            logger.info(
                "Collected %d / %d game IDs (page %d)",
                len(game_ids),
                max_games,
                page,
            )
            page += 1

        return game_ids

    def download_game_exports(
        self,
        game_ids: list[int],
        use_cache: bool = True,
        progress_callback=None,
    ) -> list[dict]:
        """Download full game exports for a list of game IDs.

        Args:
            game_ids: List of hanab.live game IDs.
            use_cache: Skip download for already-cached games.
            progress_callback: Optional callable(current, total) for progress.

        Returns:
            List of game export dicts.
        """
        exports = []
        total = len(game_ids)

        for i, gid in enumerate(game_ids):
            try:
                export = self.get_game_export(gid, use_cache=use_cache)
                exports.append(export)
            except requests.HTTPError as e:
                logger.warning("Failed to fetch game %d: %s", gid, e)
            except (requests.ConnectionError, requests.Timeout) as e:
                logger.warning("Network error fetching game %d: %s", gid, e)

            if progress_callback:
                progress_callback(i + 1, total)
            elif (i + 1) % 100 == 0 or i + 1 == total:
                logger.info("Downloaded %d / %d exports", i + 1, total)

        return exports

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    @staticmethod
    def filter_history(
        games: list[dict],
        variant_name: str = "No Variant",
        num_players: Optional[int] = 2,
        min_score: Optional[int] = None,
        completed_only: bool = True,
    ) -> list[dict]:
        """Filter game history records by criteria.

        Args:
            games: List of game summary dicts from history endpoints.
            variant_name: Required variant name (None to skip).
            num_players: Required player count (None to skip).
            min_score: Minimum score threshold (None to skip).
            completed_only: If True, exclude games with endCondition != 1.
        """
        filtered = []
        for g in games:
            opts = g.get("options", {})

            if variant_name and opts.get("variantName") != variant_name:
                continue
            if num_players and opts.get("numPlayers") != num_players:
                continue
            if completed_only and g.get("endCondition") not in (1, 2):
                # 1=normal end, 2=strikeout (ran out of lives — still a completed game)
                continue
            if min_score is not None and g.get("score", 0) < min_score:
                continue

            filtered.append(g)

        return filtered

    @staticmethod
    def is_terminated(export: dict) -> bool:
        """Check if a game was terminated early (players quit).

        Terminated games have a final action with type=4 (GAME_OVER).
        hanab.live records these with score=0.
        """
        actions = export.get("actions", [])
        return bool(actions) and actions[-1].get("type") == 4

    @staticmethod
    def is_no_variant_export(export: dict) -> bool:
        """Check if a game export is a standard 'No Variant' game.

        The export itself doesn't carry variant info, but the seed format
        'p{n}v{variant}s{seed}' encodes it.
        """
        seed = export.get("seed", "")
        # Parse variant from seed: p2v0s609 → variant=0
        try:
            v_start = seed.index("v") + 1
            v_end = seed.index("s", v_start)
            variant_id = int(seed[v_start:v_end])
            return variant_id == NO_VARIANT_ID
        except (ValueError, IndexError):
            return False


# ------------------------------------------------------------------
# Convenience entry point
# ------------------------------------------------------------------


def collect_standard_2p_games(
    max_games: int = 1000,
    data_dir: Optional[Path] = None,
) -> list[dict]:
    """Collect and download standard 2-player 'No Variant' game exports.

    This is the primary data collection function for the analysis pipeline.
    Downloads game IDs from the variant endpoint, then fetches full exports.

    Args:
        max_games: Maximum number of games to collect.
        data_dir: Override default data directory.

    Returns:
        List of game export dicts ready for replay.
    """
    client = HanabLiveClient(data_dir=data_dir)

    logger.info("Collecting up to %d game IDs...", max_games)
    game_ids = client.collect_game_ids(
        variant_id=NO_VARIANT_ID,
        num_players=2,
        max_games=max_games,
    )
    logger.info("Found %d game IDs", len(game_ids))

    logger.info("Downloading game exports...")
    exports = client.download_game_exports(game_ids)
    logger.info("Downloaded %d exports", len(exports))

    return exports


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    # Quick test: collect 10 games
    exports = collect_standard_2p_games(max_games=10)
    for g in exports:
        print(
            f"Game {g['id']}: {len(g['players'])}p, "
            f"{len(g['deck'])} cards, {len(g['actions'])} actions, "
            f"seed={g.get('seed', '?')}"
        )
