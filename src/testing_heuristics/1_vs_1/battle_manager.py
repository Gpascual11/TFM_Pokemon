"""Async battle manager for batched simulation runs.

Orchestrates the ``battle_against`` loop, progress tracking, per-battle
data extraction, and CSV export — all behind a simple ``run()`` call.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any

import pandas as pd

from poke_env import AccountConfiguration, ServerConfiguration
from poke_env.player import RandomPlayer
from poke_env.player.baselines import MaxBasePowerPlayer, SimpleHeuristicsPlayer

from .factory import HeuristicFactory

logger = logging.getLogger(__name__)

OPPONENT_CHOICES = ("random", "self", "max_power", "simple_heuristic")


class BattleManager:
    """Run a batched simulation and export results to CSV.

    Parameters
    ----------
    version : str
        Heuristic version label (e.g. ``v1``, ``v5``).
    server_url : str
        WebSocket URL of the Pokémon Showdown server.
    total_games : int
        Total number of battles to simulate.
    batch_size : int
        Battles per ``battle_against`` call.
    concurrent_battles : int
        ``max_concurrent_battles`` passed to each player.
    data_dir : str | Path
        Directory for CSV output.
    opponent : str
        One of ``random``, ``self``, ``max_power``, ``simple_heuristic``.
    run_id : str | None
        Unique run identifier (auto-generated when ``None``).
    """

    def __init__(
        self,
        version: str,
        server_url: str,
        total_games: int = 10_000,
        batch_size: int = 500,
        concurrent_battles: int = 16,
        data_dir: str | Path = "data",
        opponent: str = "random",
        run_id: str | None = None,
    ) -> None:
        self.version = version
        self.server_url = server_url
        self.total_games = total_games
        self.batch_size = batch_size
        self.concurrent_battles = concurrent_battles
        self.data_dir = Path(data_dir)
        self.opponent = opponent
        self.run_id = run_id or str(uuid.uuid4())[:8]

    def run(self) -> Path:
        """Execute the full simulation (blocking).

        Creates a fresh asyncio event loop, which is safe to call from
        any thread — including ``multiprocessing.Process`` targets.

        Returns
        -------
        Path
            Path to the generated CSV file.
        """
        return asyncio.run(self._run_async())

    async def _run_async(self) -> Path:
        """Async implementation of the batched battle loop."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        csv_path = self.data_dir / f"heuristic_{self.version}_{self.run_id}.csv"

        config = ServerConfiguration(self.server_url, None)
        common_kwargs: dict[str, Any] = {
            "battle_format": "gen9randombattle",
            "server_configuration": config,
            "max_concurrent_battles": self.concurrent_battles,
        }

        # Showdown strips underscores from usernames, causing mismatch
        tag = self.run_id.replace("_", "")
        ver = self.version.replace("_", "")

        player = HeuristicFactory.create(
            self.version,
            account_configuration=AccountConfiguration(f"{ver}A{tag}", None),
            **common_kwargs,
        )
        opponent = self._create_opponent(tag, ver, common_kwargs)

        logger.info(
            "Starting %d games (%s vs %s) on %s | batch=%d concurrent=%d",
            self.total_games, self.version, self.opponent,
            self.server_url, self.batch_size, self.concurrent_battles,
        )

        batches = self.total_games // self.batch_size
        remainder = self.total_games % self.batch_size
        total_batches = batches + (1 if remainder else 0)
        games_done = 0
        total_wins = 0
        label = f"[{self.run_id}]"

        for i in range(total_batches):
            n = self.batch_size if i < batches else remainder
            print(f"{label} Batch {i + 1}/{total_batches} — starting {n} battles…", flush=True)

            await player.battle_against(opponent, n_battles=n)

            rows = self._extract_batch(player, opponent, self.version, self.opponent)
            batch_wins = sum(r["won"] for r in rows) if rows else 0
            total_wins += batch_wins
            games_done += n

            if rows:
                df = pd.DataFrame(rows)
                df.to_csv(csv_path, mode="a", header=not csv_path.exists(), index=False)

            pct = (games_done / self.total_games) * 100
            wr = (total_wins / games_done) * 100 if games_done else 0
            print(f"{label} ✅ {games_done}/{self.total_games} ({pct:.0f}%) | win rate: {wr:.1f}%", flush=True)

            player.reset_battles()
            opponent.reset_battles()

        logger.info("Simulation complete → %s (%d games)", csv_path, self.total_games)
        return csv_path

    def _create_opponent(self, tag: str, ver: str, common_kwargs: dict[str, Any]):
        """Instantiate the opponent player based on ``self.opponent``."""
        opp_name = f"Opp{tag}"
        factories = {
            "self": lambda: HeuristicFactory.create(
                self.version,
                account_configuration=AccountConfiguration(f"{ver}B{tag}", None),
                **common_kwargs,
            ),
            "max_power": lambda: MaxBasePowerPlayer(
                account_configuration=AccountConfiguration(opp_name, None),
                **common_kwargs,
            ),
            "simple_heuristic": lambda: SimpleHeuristicsPlayer(
                account_configuration=AccountConfiguration(opp_name, None),
                **common_kwargs,
            ),
        }
        factory = factories.get(self.opponent)
        if factory:
            return factory()
        return RandomPlayer(
            account_configuration=AccountConfiguration(opp_name, None),
            **common_kwargs,
        )

    @staticmethod
    def _extract_batch(
        player,
        opponent,
        heuristic_version: str,
        opponent_type: str,
    ) -> list[dict]:
        """Extract per-battle analytics from the player's finished battles.

        Returns one dict per battle with fields for the CSV output:
        identifiers, outcome, teams, fainted/remaining counts, HP totals,
        and (optionally) move usage.
        """
        rows: list[dict] = []
        for bid, b in player.battles.items():
            if not b.finished:
                continue

            if b.won:
                winner = player.username
            elif b.lost:
                winner = opponent.username
            else:
                winner = "DRAW"

            row: dict[str, Any] = {
                "battle_id": bid,
                "heuristic": heuristic_version,
                "opponent_type": opponent_type,
                "winner": winner,
                "won": 1 if b.won else 0,
                "turns": b.turn,
            }

            if b.team:
                row["team_us"] = "|".join(sorted({str(m.species) for m in b.team.values()}))
            if b.opponent_team:
                row["team_opp"] = "|".join(sorted({str(m.species) for m in b.opponent_team.values()}))

            if b.team:
                fainted_us = sum(m.fainted for m in b.team.values())
                row["fainted_us"] = fainted_us
                row["remaining_pokemon_us"] = len(b.team) - fainted_us
                row["total_hp_us"] = round(
                    sum(m.current_hp_fraction for m in b.team.values() if not m.fainted), 3,
                )
            if b.opponent_team:
                fainted_opp = sum(m.fainted for m in b.opponent_team.values())
                row["fainted_opp"] = fainted_opp
                row["remaining_pokemon_opp"] = len(b.opponent_team) - fainted_opp
                row["total_hp_opp"] = round(
                    sum(m.current_hp_fraction for m in b.opponent_team.values() if not m.fainted), 3,
                )

            if player.tracks_moves:
                row["moves_used"] = "|".join(sorted(player.get_used_moves(bid)))

            rows.append(row)
        return rows
