"""Multi-process launcher for parallelizing 2v2 simulations.

Distributes battles across multiple Showdown server ports, using independent
process workers to maximize throughput on multi-core systems.
"""

from __future__ import annotations

import logging
import multiprocessing
import os
import signal
import socket
import sys
import uuid
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

_mp_ctx = multiprocessing.get_context("spawn")


def _check_port(host: str, port: int, timeout: float = 2.0) -> bool:
    """Return ``True`` if a TCP connection to *host*:*port* succeeds."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (ConnectionRefusedError, OSError, TimeoutError):
        return False


def _worker(
    version: str,
    port: int,
    games: int,
    batch_size: int,
    concurrent_battles: int,
    data_dir: str,
    opponent: str,
    run_id: str,
    battle_format: str = "gen9randomdoublesbattle",
    worker_index: int = 0,
) -> None:
    """Entry point for each child process."""
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
    sys.stderr.reconfigure(line_buffering=True)  # type: ignore[attr-defined]

    logging.basicConfig(
        level=logging.WARNING,
        format=f"[port:{port}] %(levelname)s %(message)s",
        force=True,
    )

    # Bootstrap package path
    _this_dir = os.path.dirname(os.path.abspath(__file__))  # core
    _doubles_dir = os.path.dirname(_this_dir)  # s02_doubles
    _heuristics_dir = os.path.dirname(_doubles_dir)  # p01_heuristics
    _src_dir = os.path.dirname(_heuristics_dir)  # src

    if _src_dir not in sys.path:
        sys.path.insert(0, _src_dir)

    import importlib

    _pkg_full = "p01_heuristics.s02_doubles.core"
    BattleManager = importlib.import_module(f"{_pkg_full}.battle_manager").BattleManager

    if not _check_port("127.0.0.1", port):
        logger.error(
            "Cannot connect to Showdown server on port %d! "
            "Start it with: node pokemon-showdown start --port %d --no-security",
            port,
            port,
        )
        print(
            f"\n❌ [Process {worker_index}] FAILED: port {port} is not reachable.\n",
            flush=True,
        )
        sys.exit(1)

    # print(f"✅ [Port {port}] Connected", flush=True)

    mgr = BattleManager(
        version=version,
        server_url=f"ws://127.0.0.1:{port}/showdown/websocket",
        total_games=games,
        batch_size=batch_size,
        concurrent_battles=concurrent_battles,
        data_dir=data_dir,
        opponent=opponent,
        run_id=f"{run_id}_p{port}",
        battle_format=battle_format,
    )

    try:
        mgr.run()
        print(f"      [{version} vs {opponent}] Port {port}: Completed batch.", flush=True)
    except Exception as exc:
        print(
            f"\n❌ [Process {worker_index}] CRASHED on port {port}: {exc}", flush=True
        )
        logger.exception("Process on port %d crashed", port)
        raise


class ProcessLauncher:
    """Distribute a 2v2 simulation across multiple Showdown servers.

    Parameters
    ----------
    version : str
        Heuristic version label.
    ports : Sequence[int]
        Server ports — one child process per port.
    total_games : int
        Total battles (divided evenly across processes).
    batch_size : int
        Battles per batch inside each process.
    concurrent_battles : int
        ``max_concurrent_battles`` per process.
    data_dir : str | Path
        Output directory for per-process and merged CSVs.
    opponent : str
        Opponent type (``random``, ``self``, ``max_power``, ``simple_heuristic``).
    """

    def __init__(
        self,
        version: str,
        ports: Sequence[int],
        total_games: int = 10_000,
        batch_size: int = 500,
        concurrent_battles: int = 16,
        data_dir: str | Path = "data",
        opponent: str = "random",
        battle_format: str = "gen9randomdoublesbattle",
    ) -> None:
        self.version = version
        self.ports = list(ports)
        self.total_games = total_games
        self.batch_size = batch_size
        self.concurrent_battles = concurrent_battles
        self.data_dir = Path(data_dir)
        self.opponent = opponent
        self.battle_format = battle_format
        self.run_id = str(uuid.uuid4())[:8]

    def launch(self) -> Path:
        """Spawn workers, wait for completion, and merge results."""
        self._preflight_check()
        processes = self._spawn_workers()
        self._wait_for_completion(processes)
        merged_path = self._merge_results()
        logger.info("Merged results → %s", merged_path)
        return merged_path

    def _preflight_check(self) -> None:
        """Verify all Showdown servers are reachable before spawning."""
        # Quiet check
        all_ok = True
        for port in self.ports:
            if not _check_port("127.0.0.1", port):
                print(f"   Port {port}: ❌ UNREACHABLE")
                all_ok = False

        if not all_ok:
            print(
                "\n⚠️  Some servers are not reachable! Start them with:\n"
                "   node pokemon-showdown start --port <PORT> --no-security\n"
            )
            raise RuntimeError(
                f"Cannot launch: not all Showdown servers are reachable. "
                f"Checked ports: {self.ports}"
            )
        if not all_ok:
            pass # Already printed individual port errors

    def _spawn_workers(self) -> list:
        """Create and start one child process per port."""
        n = len(self.ports)
        base, extra = divmod(self.total_games, n)
        games_per_port = [base + (1 if i < extra else 0) for i in range(n)]

        processes = []
        for idx, (port, games) in enumerate(zip(self.ports, games_per_port, strict=True)):
            if games == 0:
                continue
            p = _mp_ctx.Process(
                target=_worker,
                kwargs={
                    "version": self.version,
                    "port": port,
                    "games": games,
                    "batch_size": self.batch_size,
                    "concurrent_battles": self.concurrent_battles,
                    "data_dir": str(self.data_dir),
                    "opponent": self.opponent,
                    "run_id": self.run_id,
                    "battle_format": self.battle_format,
                    "worker_index": idx,
                },
                daemon=False,
            )
            processes.append(p)

        logger.info(
            "Launching %d processes for %d total games (%s)",
            len(processes),
            self.total_games,
            self.version,
        )
        for p in processes:
            p.start()
        return processes

    def _wait_for_completion(self, processes: list) -> None:
        """Wait for all workers, handling SIGINT gracefully."""
        original_handler = signal.getsignal(signal.SIGINT)

        def _shutdown(signum, frame):
            logger.warning("SIGINT received — terminating child processes…")
            for proc in processes:
                if proc.is_alive():
                    proc.terminate()
            sys.exit(1)

        signal.signal(signal.SIGINT, _shutdown)

        for p in processes:
            p.join()

        signal.signal(signal.SIGINT, original_handler)

        failed = [p for p in processes if p.exitcode != 0]
        if failed:
            logger.error(
                "%d/%d processes exited with errors", len(failed), len(processes)
            )
            print(
                f"\n⚠️  {len(failed)}/{len(processes)} processes failed! Check logs above."
            )

    def _merge_results(self) -> Path:
        """Concatenate all per-process CSVs into one merged file."""
        pattern = f"{self.version}_vs_{self.opponent}_{self.run_id}_p*.csv"
        part_files = sorted(self.data_dir.glob(pattern))

        merged_path = self.data_dir / f"{self.version}_vs_{self.opponent}.csv"

        if not part_files:
            logger.warning("No per-process CSVs found matching '%s'", pattern)
            return merged_path

        # Load new results
        frames = [pd.read_csv(f) for f in part_files]
        
        # If the file already exists, load the history so we append instead of overwrite
        if merged_path.exists():
            try:
                history_df = pd.read_csv(merged_path)
                frames.insert(0, history_df)
            except Exception as e:
                logger.warning("Could not read existing history in %s: %s. Starting fresh.", merged_path, e)

        merged = pd.concat(frames, ignore_index=True)
        merged.to_csv(merged_path, index=False)

        for f in part_files:
            try:
                f.unlink()
            except OSError as e:
                logger.warning("Could not delete partial file %s: %s", f, e)

        logger.info(
            "Merged %d partial files (%d rows) → %s",
            len(frames),
            len(merged),
            merged_path,
        )
        return merged_path
