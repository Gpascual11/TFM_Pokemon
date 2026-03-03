#!/usr/bin/env python
"""Cross-repository Pokémon AI benchmark: Pokechamp agents vs internal heuristics.

Orchestrates a full tournament between selected Pokechamp agents and all
internal opponents (heuristics v1–v6 plus poke_env baselines).  Each
mini-batch of battles is delegated to a **subprocess worker**
(``_pokechamp_worker.py``) so that, upon exit, the OS reclaims all memory
used by pokechamp's ``POKE_LOOP`` background thread.

Outputs
-------
- Per-matchup CSVs in ``data/benchmarks_pokechamp/``.
- Aggregated summary CSV.
- Win-rate matrix printed to the terminal.

See Also
--------
_pokechamp_worker : The subprocess that actually executes battles.
POKECHAMP_BENCHMARK.md : Full development notes and usage guide.
"""

import argparse
import gc
import json
import logging
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd
from tabulate import tabulate

# ---------------------------------------------------------------------------
# Package bootstrap
# ---------------------------------------------------------------------------
# Pokechamp's bundled ``poke_env`` fork must be importable *first* so that
# both Pokechamp agents and internal heuristics share the same
# ``poke_env.player.Player`` base class (required by ``battle_against``).
_DIR = Path(__file__).parent.resolve()
_SRC = _DIR.parent.parent
_POKECHAMP_ROOT = _SRC.parent / "pokechamp"
if str(_POKECHAMP_ROOT) not in sys.path:
    sys.path.insert(0, str(_POKECHAMP_ROOT))

if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

__package__ = "p01_heuristics.s01_singles"

from common import prompt_algos  # noqa: E402, F821  # type: ignore[import-untyped]

from .core.factory import HeuristicFactory  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
POKECHAMP_AGENTS: list[str] = [
    "pokechamp",
    "pokellmon",
    "abyssal",
    "max_power",
    "one_step",
    "random",
]
"""All available Pokechamp agent identifiers."""

LLM_AGENTS: set[str] = {"pokechamp", "pokellmon"}
"""Agents that require an LLM backend; all others are rule-based."""

_WORKER_SCRIPT: str = str(_DIR / "_pokechamp_worker.py")
"""Absolute path to the subprocess worker invoked for each mini-batch."""

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Server helpers
# ---------------------------------------------------------------------------
def restart_servers(n_ports: int) -> None:
    """Kill running Showdown servers and launch *n_ports* fresh instances.

    Calls ``p03_launch_custom_servers.sh`` and waits 15 s for startup.
    """
    print("\n♻️  RESTARTING SHOWDOWN SERVERS (Clearing Node.js RAM)...")
    try:
        subprocess.run(["pkill", "-f", "pokemon-showdown"], check=False)
        time.sleep(2)
        subprocess.Popen(
            ["bash", "src/p03_scripts/p03_launch_custom_servers.sh", str(n_ports)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print("⏳ Waiting 15 seconds for servers to initialize...")
        time.sleep(15)
    except Exception as e:
        print(f"❌ Failed to restart servers: {e}")


def _check_port(host: str, port: int, timeout: float = 2.0) -> bool:
    """Return ``True`` if a TCP connection to *host*:*port* succeeds."""
    import socket

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Battle runner (subprocess-isolated)
# ---------------------------------------------------------------------------
def run_matchup(
    pokechamp_agent: str,
    opponent_name: str,
    total_games: int,
    ports: list[int],
    battle_format: str,
    backend: str,
    prompt_algo: str,
    temperature: float,
    log_dir: str,
    data_dir: Path,
    batch_size: int = 50,
) -> dict:
    """Execute a full matchup between one Pokechamp agent and one opponent.

    The total number of games is split into mini-batches of *batch_size*.
    Each batch is run in a **separate Python process** via
    ``_pokechamp_worker.py``, which writes its results to a temporary CSV
    and then exits — guaranteeing OS-level memory reclamation.

    After all batches complete, the temporary CSVs are merged into a
    single per-matchup CSV and aggregated metrics are returned.

    Parameters
    ----------
    pokechamp_agent : str
        Identifier of the Pokechamp agent (e.g. ``"random"``, ``"abyssal"``).
    opponent_name : str
        Identifier of the opponent (e.g. ``"v1"``, ``"max_power"``).
    total_games : int
        Total battles to play in this matchup.
    ports : list[int]
        Available server ports (currently only ``ports[0]`` is used).
    battle_format : str
        Pokémon Showdown battle format.
    backend : str
        LLM backend string (only used by LLM agents).
    prompt_algo : str
        Prompt algorithm (only used by LLM agents).
    temperature : float
        LLM sampling temperature.
    log_dir : str
        Directory for pokechamp battle logs.
    data_dir : Path
        Directory where per-matchup CSVs are written.
    batch_size : int
        Number of games per subprocess worker (default 50).

    Returns
    -------
    dict
        Aggregated metrics: ``win_rate``, ``avg_turns``, ``avg_fainted_opp``,
        ``avg_hp_remaining``, ``total_games``.
    """
    print(f"\n⚔️  MATCHUP: {pokechamp_agent} vs {opponent_name} ({total_games} games)...")

    port = ports[0]
    data_dir = data_dir.resolve()

    n_full = total_games // batch_size
    remainder = total_games % batch_size
    batch_counts = [batch_size] * n_full
    if remainder:
        batch_counts.append(remainder)

    temp_csvs: list[Path] = []
    games_done = 0

    for i, n in enumerate(batch_counts):
        tmp_csv = data_dir / f"_tmp_{pokechamp_agent}_vs_{opponent_name}_b{i}.csv"
        temp_csvs.append(tmp_csv)

        cmd = [
            sys.executable,
            _WORKER_SCRIPT,
            "--pc-agent",
            pokechamp_agent,
            "--opponent",
            opponent_name,
            "--n-battles",
            str(n),
            "--port",
            str(port),
            "--format",
            battle_format,
            "--backend",
            backend,
            "--prompt-algo",
            prompt_algo,
            "--temperature",
            str(temperature),
            "--log-dir",
            log_dir,
            "--out",
            str(tmp_csv),
        ]

        print(f"    Batch {i + 1}/{len(batch_counts)} — {n} battles…", flush=True)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)
        except subprocess.TimeoutExpired:
            print("    ⏰ Batch timed out after 1200s — skipping (server may be stuck)")
            continue

        if result.returncode != 0:
            print(f"    ❌ Worker failed (exit {result.returncode})")
            err_lines = (result.stderr or "").strip().splitlines()
            for line in err_lines[-5:]:
                print(f"       {line}")
            continue

        for line in result.stdout.strip().splitlines():
            if line.startswith("WORKER_OK:"):
                batch_done = int(line.split(":")[1])
                games_done += batch_done
                pct = (games_done / total_games) * 100
                print(f"    ✅ {games_done}/{total_games} ({pct:.0f}%)", flush=True)
                break

    # Merge temporary CSVs into the final per-matchup file.
    frames: list[pd.DataFrame] = []
    for tmp in temp_csvs:
        if tmp.exists():
            try:
                frames.append(pd.read_csv(tmp))
            except Exception:
                pass
            tmp.unlink()

    if frames:
        merged = pd.concat(frames, ignore_index=True)
        csv_path = data_dir / f"pokechamp_{pokechamp_agent}_vs_{opponent_name}.csv"
        merged.to_csv(csv_path, index=False)

        n_total = len(merged)
        wins = int(merged["won"].sum())
        metrics = {
            "win_rate": (wins / n_total * 100) if n_total else 0.0,
            "avg_turns": float(merged["turns"].mean()) if n_total else 0.0,
            "avg_fainted_opp": float(merged["fainted_opp"].mean()) if "fainted_opp" in merged.columns else 0.0,
            "avg_hp_remaining": float(merged["total_hp_us"].mean()) if "total_hp_us" in merged.columns else 0.0,
            "total_games": n_total,
        }
    else:
        metrics = {
            "win_rate": 0.0,
            "avg_turns": 0.0,
            "avg_fainted_opp": 0.0,
            "avg_hp_remaining": 0.0,
            "total_games": 0,
        }

    return metrics


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    """Parse arguments and run the full Pokechamp-vs-heuristics benchmark."""
    parser = argparse.ArgumentParser(
        description="Cross-repo benchmark: Pokechamp agents vs internal heuristics (v1–v6) + baselines.",
    )
    parser.add_argument("total_games", type=int, help="Number of games per matchup pair.")
    parser.add_argument(
        "-p",
        "--ports",
        type=int,
        nargs="+",
        default=[8000],
        help="Server ports (e.g. 8000 8001) or a single number < 100 for auto-expansion.",
    )
    parser.add_argument(
        "--pokechamp-agents",
        type=str,
        nargs="+",
        default=POKECHAMP_AGENTS,
        choices=POKECHAMP_AGENTS,
        help="Which Pokechamp agents to benchmark (default: all 6).",
    )
    parser.add_argument(
        "--player_backend",
        type=str,
        default="ollama/gemma3:4b",
        help="LLM backend for LLM-based agents. Ignored for rule-based agents.",
    )
    parser.add_argument(
        "--player_prompt_algo",
        type=str,
        default="io",
        choices=prompt_algos,
        help="Prompt algorithm for LLM-based agents.",
    )
    parser.add_argument(
        "--battle-format",
        type=str,
        default="gen9randombattle",
        choices=["gen9randombattle", "gen9ou", "gen8randombattle", "gen8ou"],
        help="Battle format.",
    )
    parser.add_argument("--temperature", type=float, default=0.3, help="LLM temperature.")
    parser.add_argument("--resume", action="store_true", help="Resume from previous checkpoint.")
    parser.add_argument(
        "--restart-every",
        type=int,
        default=1,
        help=(
            "Restart the Showdown server every N matchups to flush Node.js memory "
            "(default: 1). Set to 0 to never restart."
        ),
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/benchmarks_pokechamp",
        help="Directory for per-matchup battle CSVs.",
    )
    parser.add_argument(
        "--output-csv",
        type=str,
        default="src/p01_heuristics/s01_singles/results/pokechamp_benchmark_summary.csv",
        help="Path for the summary CSV.",
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default="./battle_log/pokechamp_benchmark",
        help="Directory for pokechamp battle logs.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Games per subprocess batch (lower = less RAM, more overhead).",
    )
    args = parser.parse_args()

    # --- Configuration ---
    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_file = data_dir / "checkpoint_pokechamp.json"

    if len(args.ports) == 1 and args.ports[0] < 100:
        n_ports = args.ports[0]
        args.ports = [8000 + i for i in range(n_ports)]
    ports_list = args.ports

    logging.basicConfig(level=logging.WARNING)
    logging.getLogger("p01_heuristics").setLevel(logging.INFO)
    logging.getLogger("poke_env").setLevel(logging.ERROR)

    # --- Build the matchup matrix ---
    pokechamp_agents = args.pokechamp_agents
    heuristics = sorted(HeuristicFactory.available_versions())
    baselines = ["random", "max_power", "simple_heuristic"]
    opponents = heuristics + baselines

    # --- Load / initialise checkpoint ---
    checkpoint_data: dict[str, dict] = {}
    if args.resume and checkpoint_file.exists():
        print(f"🔄 Resuming from checkpoint: {checkpoint_file}")
        with open(checkpoint_file) as f:
            checkpoint_data = json.load(f)

    print("🚀 Starting Cross-Repo Pokechamp Benchmark")
    print(f"🔹 Pokechamp agents: {pokechamp_agents}")
    print(f"🔹 Opponents: {opponents}")
    print(f"🔹 Data Directory: {data_dir}")
    print(f"📈 Total Matchups: {len(pokechamp_agents) * len(opponents)}")
    print(f"📡 Serving on {len(ports_list)} port(s): {ports_list}")

    # Always start with a fresh Showdown server so any state from previous runs
    # (accumulated room-battle.js workers) is cleared before the first matchup.
    if args.restart_every > 0:
        restart_servers(len(ports_list))

    # --- Execute matchups ---
    matchup_count = 0
    for pc_agent in pokechamp_agents:
        for opp in opponents:
            match_key = f"{pc_agent}_vs_{opp}"

            if args.resume:
                if match_key in checkpoint_data:
                    print(f"⏩ Skipping {match_key} (found in checkpoint)")
                    continue

                csv_path = data_dir / f"pokechamp_{pc_agent}_vs_{opp}.csv"
                if csv_path.exists():
                    try:
                        df_check = pd.read_csv(csv_path)
                        if len(df_check) >= args.total_games:
                            checkpoint_data[match_key] = {
                                "win_rate": (df_check["won"].sum() / len(df_check)) * 100,
                                "avg_turns": df_check["turns"].mean(),
                                "avg_fainted_opp": df_check["fainted_opp"].mean()
                                if "fainted_opp" in df_check.columns
                                else 0.0,
                                "avg_hp_remaining": df_check["total_hp_us"].mean()
                                if "total_hp_us" in df_check.columns
                                else 0.0,
                                "total_games": int(len(df_check)),
                            }
                            print(f"⏩ Skipping {match_key} (CSV already complete)")
                            continue
                    except Exception:
                        pass

            # Restart the Showdown server every N matchups to prevent Node.js memory
            # accumulation — each battle spawns a room-battle.js worker that is never
            # freed, so after ~150–200 games the server stalls.
            should_restart = args.restart_every > 0 and matchup_count > 0 and matchup_count % args.restart_every == 0
            if should_restart:
                restart_servers(len(ports_list))

            port = ports_list[0]
            if not _check_port("127.0.0.1", port):
                print(f"⚠️  Server on port {port} is NOT reachable. Waiting 10s extra...")
                time.sleep(10)
                if not _check_port("127.0.0.1", port):
                    print(f"❌ Server on port {port} still unreachable. Skipping matchup.")
                    continue

            metrics = run_matchup(
                pokechamp_agent=pc_agent,
                opponent_name=opp,
                total_games=args.total_games,
                ports=ports_list,
                battle_format=args.battle_format,
                backend=args.player_backend,
                prompt_algo=args.player_prompt_algo,
                temperature=args.temperature,
                log_dir=args.log_dir,
                data_dir=data_dir,
                batch_size=args.batch_size,
            )
            checkpoint_data[match_key] = metrics
            matchup_count += 1

            with open(checkpoint_file, "w") as f:
                json.dump(checkpoint_data, f, indent=4)

            gc.collect()
            time.sleep(2)

    # --- Summary CSV ---
    results_list = []
    for match_key, m in checkpoint_data.items():
        pc_agent, opp = match_key.split("_vs_")
        results_list.append(
            {
                "pokechamp_agent": pc_agent,
                "opponent": opp,
                "win_rate": round(m["win_rate"], 2),
                "avg_turns": round(m["avg_turns"], 2),
                "avg_fainted_opp": round(m["avg_fainted_opp"], 2),
                "avg_hp_remaining": round(m["avg_hp_remaining"], 4),
                "total_games": m["total_games"],
            }
        )

    output_csv = Path(args.output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(results_list).to_csv(output_csv, index=False)
    print(f"\n✅ MASTER SUMMARY SAVED TO: {output_csv}")

    # --- Win-rate matrix ---
    table_rows = []
    for pc_agent in pokechamp_agents:
        row = [pc_agent]
        for opp in opponents:
            m = checkpoint_data.get(f"{pc_agent}_vs_{opp}", {})
            wr = m.get("win_rate", 0.0)
            row.append(f"{wr:.1f}%")
        table_rows.append(row)

    headers = ["Pokechamp \\ Opponent"] + opponents
    print("\n" + "=" * 100)
    print("🏆 WIN RATE MATRIX (%): Pokechamp Agent (row) wins against Opponent (col)")
    print("=" * 100)
    print(tabulate(table_rows, headers=headers, tablefmt="grid"))
    print("=" * 100)


if __name__ == "__main__":
    main()
