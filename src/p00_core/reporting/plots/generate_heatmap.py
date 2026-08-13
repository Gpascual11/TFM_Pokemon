"""Win-rate heatmap from a directory of directed matchup CSVs.

Default axis order is v1–v22, then baselines. Labels are prefixed
(H) heuristic, (MM) minimax, (MCT) MCTS, (IL) imitation, (B) baseline.
v18/v19/v20 cells are 1,000 games; every other cell is 10,000.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_DIR = Path(__file__).parent.resolve()
_ROOT = _DIR.parents[3]
_SRC = _ROOT / "src"
for p in (_ROOT, _SRC):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from p00_core.reporting.plots.styling import RD_YL_GN_PREMIUM, apply_premium_style, finalize_plot

SKIP_FILES = {"elo_summary.csv", "matchup_performance.csv"}
USECOLS = {"heuristic", "pokechamp_agent", "agent", "opponent", "opponent_type", "won"}

VERSION_ORDER = [f"v{i}" for i in range(1, 23)] + [
    "abyssal",
    "simple_heuristic",
    "one_step",
    "safe_one_step",
    "max_power",
    "random",
]


def _version_num(name: str) -> int | None:
    if name.startswith("v") and name[1:].isdigit():
        return int(name[1:])
    return None


def display_label(name: str) -> str:
    """Prefix used on the heatmap axes."""
    n = _version_num(name)
    if n is not None:
        if 1 <= n <= 14:
            return f"(H) {name}"
        if 15 <= n <= 17:
            return f"(MM) {name}"
        if 18 <= n <= 20:
            return f"(MCT) {name}"
        if n in (21, 22):
            return f"(IL) {name}"
        return name
    return f"(B) {name}"


def _is_matchup_csv(path: Path) -> bool:
    if path.suffix != ".csv":
        return False
    if path.name in SKIP_FILES or path.name.startswith("_tmp"):
        return False
    return True


def _agent_col(df: pd.DataFrame) -> str | None:
    for c in ("agent", "heuristic", "pokechamp_agent"):
        if c in df.columns:
            return c
    return None


def load_matchup_winrates(data_dir: Path) -> pd.DataFrame:
    """One row per directed file: agent, opponent, win rate, n."""
    files = sorted(p for p in data_dir.glob("*.csv") if _is_matchup_csv(p))
    if not files:
        raise FileNotFoundError(f"No CSV files in {data_dir}")

    rows = []
    skipped = 0
    for path in files:
        try:
            df = pd.read_csv(path, usecols=lambda c: c in USECOLS)
        except Exception as exc:
            print(f"Error reading {path.name}: {exc}")
            skipped += 1
            continue
        agent_col = _agent_col(df)
        opp_col = "opponent" if "opponent" in df.columns else (
            "opponent_type" if "opponent_type" in df.columns else None
        )
        if agent_col is None or opp_col is None or "won" not in df.columns:
            skipped += 1
            continue
        if df.empty:
            skipped += 1
            continue
        agent = str(df[agent_col].iloc[0])
        opponent = str(df[opp_col].iloc[0])
        rows.append(
            {
                "agent": agent,
                "opponent": opponent,
                "win_rate": float(df["won"].mean()),
                "n": int(len(df)),
            }
        )

    if not rows:
        raise ValueError("No valid matchup CSVs to process.")
    print(f"Loaded {len(rows)} matchups from {data_dir} ({skipped} files skipped)")
    return pd.DataFrame(rows)


def _axis_order(stats: pd.DataFrame, mode: str) -> list[str]:
    agents = set(stats["agent"]).union(stats["opponent"])
    if mode == "winrate":
        overall = stats.groupby("agent")["win_rate"].mean().sort_values(ascending=False)
        leftover = [a for a in agents if a not in overall.index]
        return list(overall.index) + sorted(leftover)
    rank = {name: i for i, name in enumerate(VERSION_ORDER)}
    return sorted(agents, key=lambda a: (rank.get(a, 10_000), a))


def generate_heatmap(
    data_dir: Path,
    output_path: Path,
    title: str = "Pairwise win rate",
    filter_agents: list[str] | None = None,
    filter_opponents: list[str] | None = None,
    order: str = "version",
) -> pd.DataFrame:
    apply_premium_style()
    stats = load_matchup_winrates(data_dir)

    if filter_agents:
        stats = stats[stats["agent"].isin(filter_agents)]
    if filter_opponents:
        stats = stats[stats["opponent"].isin(filter_opponents)]
    if stats.empty:
        print("Filtering resulted in an empty matrix.")
        return stats

    names = _axis_order(stats, order)
    if filter_agents or filter_opponents:
        allow = set(filter_agents or names) | set(filter_opponents or names)
        names = [a for a in names if a in allow]

    matrix = (
        stats.pivot(index="agent", columns="opponent", values="win_rate")
        .reindex(index=names, columns=names)
        * 100
    )
    labeled = matrix.copy()
    labeled.index = [display_label(a) for a in labeled.index]
    labeled.columns = [display_label(a) for a in labeled.columns]
    n_agents = len(names)
    side = max(12.0, 0.42 * n_agents + 4.0)
    annot_size = 8 if n_agents <= 14 else (6 if n_agents <= 22 else 5)

    fig, ax = plt.subplots(figsize=(side, side * 0.88))
    sns.heatmap(
        labeled,
        annot=True,
        fmt=".1f",
        cmap=RD_YL_GN_PREMIUM,
        vmin=0,
        vmax=100,
        center=50,
        linewidths=0.4,
        linecolor="#eee",
        square=True,
        ax=ax,
        cbar_kws={"label": "Win rate %", "shrink": 0.65},
        annot_kws={"size": annot_size},
    )
    ax.set_xlabel("Opponent")
    ax.set_ylabel("Player (us)")
    ax.set_title(title)
    plt.xticks(rotation=45, ha="right")
    plt.yticks(rotation=0)
    finalize_plot(fig)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=220)
    plt.close(fig)

    csv_path = output_path.with_suffix(".csv")
    matrix.round(2).to_csv(csv_path)
    print(f"Heatmap saved to {output_path}")
    print(f"Matrix CSV saved to {csv_path}")
    print(f"Shape {matrix.shape[0]}×{matrix.shape[1]}; "
          f"NaNs={int(matrix.isna().sum().sum())}")
    return matrix


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a win-rate heatmap from CSV results.")
    parser.add_argument("--data-dir", type=str, required=True, help="Path to CSV files")
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output PNG path. Defaults to heatmap.png next to the data.",
    )
    parser.add_argument("--title", type=str, default="Pairwise win rate", help="Plot title")
    parser.add_argument("--agents", nargs="+", help="Only include these agents as rows")
    parser.add_argument("--opponents", nargs="+", help="Only include these opponents as columns")
    parser.add_argument(
        "--order",
        choices=("version", "winrate"),
        default="version",
        help="Axis order: v1–v22 then baselines (default), or overall win rate.",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    output_path = Path(args.output) if args.output else data_dir / "heatmap.png"
    generate_heatmap(
        data_dir,
        output_path,
        args.title,
        filter_agents=args.agents,
        filter_opponents=args.opponents,
        order=args.order,
    )


if __name__ == "__main__":
    main()
