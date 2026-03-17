"""Async Battle Manager for batched 2v2 heuristic simulations.

Handles the execution of multiple doubles battles, collecting performance
metrics for up to 4 Pokémon per side and exporting results to CSV format.
"""

from __future__ import annotations

import asyncio
import gc
import logging
import uuid
from pathlib import Path
from typing import Any

import pandas as pd

from poke_env import AccountConfiguration, ServerConfiguration
from poke_env.player import RandomPlayer
from poke_env.player.baselines import MaxBasePowerPlayer

from .factory import HeuristicFactory
from ..agents.baselines.simple_doubles_baseline import SimpleHeuristicsDoublesPlayer

logger = logging.getLogger(__name__)

OPPONENT_CHOICES = ("random", "self", "max_power", "simple_heuristic")


class BattleManager:
    """Orchestrate a batched doubles simulation and export results to CSV.

    :param version: Heuristic version label, e.g. ``v1`` or ``v6``.
    :param server_url: WebSocket URL of the Pokémon Showdown server.
    :param total_games: Total battles to simulate.
    :param batch_size: Battles per ``battle_against`` call.
    :param concurrent_battles: ``max_concurrent_battles`` passed to each player.
    :param data_dir: Directory for CSV output.
    :param opponent: ``random``, ``self``, ``max_power``, ``simple_heuristic``, or a heuristic version.
    :param run_id: Unique run identifier; auto-generated when ``None``.
    """

    def __init__(
        self,
        version: str,
        server_url: str,
        total_games: int = 10_000,
        batch_size: int = 250,  # Reduced default for memory safety
        concurrent_battles: int = 16,
        data_dir: str | Path = "data",
        opponent: str = "random",
        run_id: str | None = None,
        battle_format: str = "gen9randomdoublesbattle",
    ) -> None:
        self.version = version
        self.server_url = server_url
        self.total_games = total_games
        self.batch_size = batch_size
        self.concurrent_battles = concurrent_battles
        self.data_dir = Path(data_dir)
        self.opponent = opponent
        self.run_id = run_id or str(uuid.uuid4())[:8]
        self.battle_format = battle_format

    def run(self) -> Path:
        """Execute the full simulation (blocking)."""
        return asyncio.run(self._run_async())

    async def _run_async(self) -> Path:
        """Async implementation of the batched battle loop."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        csv_path = (
            self.data_dir
            / f"{self.version}_vs_{self.opponent}_{self.run_id}.csv"
        )

        config = ServerConfiguration(self.server_url, "https://play.pokemonsoftshowdown.com/action.php")
        common_kwargs: dict[str, Any] = {
            "battle_format": self.battle_format,
            "server_configuration": config,
            "max_concurrent_battles": self.concurrent_battles,
            "strict_battle_tracking": False,
        }

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
            self.total_games,
            self.version,
            self.opponent,
            self.server_url,
            self.batch_size,
            self.concurrent_battles,
        )

        batches = self.total_games // self.batch_size
        remainder = self.total_games % self.batch_size
        total_batches = batches + (1 if remainder else 0)
        games_done = 0
        total_wins = 0
        label = f"[{self.run_id}]"

        for i in range(total_batches):
            n = self.batch_size if i < batches else remainder
            print(
                f"{label} Batch {i + 1}/{total_batches} — starting {n} battles…",
                flush=True,
            )

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
            print(
                f"{label} ✅ {games_done}/{self.total_games} ({pct:.0f}%) | win rate: {wr:.1f}%",
                flush=True,
            )

            player.reset_battles()
            opponent.reset_battles()

        logger.info("Simulation complete → %s (%d games)", csv_path, self.total_games)

        # Explicit cleanup to help the GC
        player.reset_battles()
        opponent.reset_battles()
        del player
        del opponent
        gc.collect()

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
            "simple_heuristic": lambda: SimpleHeuristicsDoublesPlayer(
                account_configuration=AccountConfiguration(opp_name, None),
                **common_kwargs,
            ),
        }
        factory = factories.get(self.opponent)
        if factory:
            return factory()
        if self.opponent in HeuristicFactory.available_versions():
            return HeuristicFactory.create(
                self.opponent,
                account_configuration=AccountConfiguration(
                    f"{self.opponent.replace('_', '')}B{tag}", None
                ),
                **common_kwargs,
            )
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
        """Extract per-battle analytics from the player's finished battles."""
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
                row["team_us"] = "|".join(
                    sorted({str(m.species) for m in b.team.values()})
                )
            if b.opponent_team:
                row["team_opp"] = "|".join(
                    sorted({str(m.species) for m in b.opponent_team.values()})
                )

            if b.team:
                fainted_us = sum(m.fainted for m in b.team.values())
                row["fainted_us"] = fainted_us
                row["remaining_pokemon_us"] = len(b.team) - fainted_us
                row["total_hp_us"] = round(
                    sum(
                        m.current_hp_fraction for m in b.team.values() if not m.fainted
                    ),
                    3,
                )
            if b.opponent_team:
                fainted_opp = sum(m.fainted for m in b.opponent_team.values())
                row["fainted_opp"] = fainted_opp
                row["remaining_pokemon_opp"] = len(b.opponent_team) - fainted_opp
                row["total_hp_opp"] = round(
                    sum(
                        m.current_hp_fraction
                        for m in b.opponent_team.values()
                        if not m.fainted
                    ),
                    3,
                )

            if player.tracks_moves:
                row["moves_used"] = "|".join(sorted(player.get_used_moves(bid)))

            rows.append(row)
        return rows
