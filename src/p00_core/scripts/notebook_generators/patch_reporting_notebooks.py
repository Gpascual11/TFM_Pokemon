#!/usr/bin/env python3
"""Patch reporting notebooks: correct taxonomy, drop stray cells, update ladder sample size."""
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[4] / "src/p00_core/reporting"


def load(name: str):
    path = ROOT / name
    nb = nbf.read(path, as_version=4)
    return path, nb


def save(path, nb):
    nbf.write(nb, path)
    print(f"patched {path.name} ({len(nb.cells)} cells)")


def set_md(cell, text: str):
    cell["source"] = text.strip() + "\n"


def replace_in_source(cell, old: str, new: str) -> bool:
    src = cell.source if isinstance(cell.source, str) else "".join(cell.source)
    if old not in src:
        return False
    cell.source = src.replace(old, new)
    return True


# ── online bot ──────────────────────────────────────────────────────────────
path, nb = load("eda_online_bot.ipynb")
set_md(
    nb.cells[0],
    """\
# Heuristic V14 Live Ladder EDA

This notebook audits **live Showdown ladder games** played by `HeuristicV14`
(`SirPThesis`) on `gen9randombattle`. It is **not** the bot-vs-bot gauntlet.

The log currently has **431 battles** (`data/testing/logs_v14/battle_history.csv`).
Treat this as a human-side pilot, not as a parallel of the 10k matrix. Bot-vs-bot
ranking (v12 ≥ v13 > v14) answers a different question.

**Taxonomy reminder.** v14 is a heuristic. Search is v15–v17 (1-ply) and v18–v20
(MCTS). IL is v21 (hybrid) / v22 (pure). This file only contains v14 vs humans.
""",
)
for cell in nb.cells:
    replace_in_source(
        cell,
        "We visualize the running win rate and the Elo rating adjustments over the course of the 100 matches.",
        "Running win rate and Elo over the recorded ladder session (n is `len(df)`, currently 431).",
    )
save(path, nb)

# ── analysis.ipynb ──────────────────────────────────────────────────────────
path, nb = load("analysis.ipynb")
set_md(
    nb.cells[0],
    """\
# 1-vs-1 Heuristic Simulation Analysis (single-file helper)

This notebook plots **one** simulation CSV (currently a legacy `v3 vs v2` file).
It is **not** the 10k gauntlet and it is **not** the results chapter.

Gauntlet EDAs with the correct taxonomy:

| Family | Notebook |
|---|---|
| Heuristics v1–v14 | `eda_heuristics_v1_v14.ipynb` |
| 1-ply minimax v15–v17 | `eda_minimax_v15_v17.ipynb` |
| Shallow MCTS v18–v20 | `eda_mcts_v18_v20.ipynb` |
| IL v21–v22 | `eda_imitation_v21_v22.ipynb` |

**Taxonomy:** v1–v14 heuristic · v15–v17 minimax · v18–v20 MCTS · v21 hybrid IL · v22 pure IL.
Do not label v17 as MCTS or v19–v20 as imitation.
""",
)
save(path, nb)

# ── tournament ──────────────────────────────────────────────────────────────
path, nb = load("eda_tournament.ipynb")
set_md(
    nb.cells[0],
    """\
# Tournament EDA & schema validator

Streaming aggregation across `data/benchmarks/all_10k` (all generations). This
notebook ranks **every** recorded agent, not only heuristics.

**Taxonomy (gen9randombattle, 28 agents):**

| IDs | Paradigm |
|---|---|
| `random`, `max_power`, `one_step`, `safe_one_step`, `abyssal`, `simple_heuristic` | Baselines |
| **v1–v14** | Heuristics (ablation ladder) |
| **v15–v17** | 1-ply minimax (analytic maximin; no LocalSim) |
| **v18–v20** | Information-Set MCTS (**1,000** games per matchup, not 10k) |
| **v21** | IL hybrid (XGB + v14) |
| **v22** | IL pure (two XGBs, no v14) |

Older executive reports under `agents/v1/` … `v14/` mislabel v17 as MCTS and v19–v20
as IL. Ignore those labels. Family EDAs live next to this file.

Bradley-Terry Elo here mixes 10k and 1k cells: MCTS ratings are noisier. For the
thesis ranking use matchup cells from the family notebooks, not this Elo plot alone.
""",
)
# config cell: add taxonomy print
cfg = "".join(nb.cells[2].source) if not isinstance(nb.cells[2].source, str) else nb.cells[2].source
if "PARADIGM_MAP" not in cfg:
    nb.cells[2].source = cfg.rstrip() + """

PARADIGM_MAP = {
    "random": "Baseline", "max_power": "Baseline", "abyssal": "Baseline",
    "one_step": "Baseline", "safe_one_step": "Baseline", "simple_heuristic": "Baseline",
    **{f"v{i}": "Heuristic" for i in range(1, 15)},
    "v15": "Minimax", "v16": "Minimax", "v17": "Minimax",
    "v18": "MCTS", "v19": "MCTS", "v20": "MCTS",
    "v21": "IL Hybrid", "v22": "IL Pure",
}
print("Taxonomy: v1–v14 heuristic | v15–v17 minimax | v18–v20 MCTS (n=1k) | v21 hybrid IL | v22 pure IL")
"""
replace_in_source(
    nb.cells[10],
    "Plotting pairwise win rates per generation to visually assess agent counters and hierarchy.",
    "Pairwise win rates. Row/column labels are agent IDs — v15–v17 are minimax, v18–v20 MCTS, v21–v22 IL.",
)
replace_in_source(
    nb.cells[11],
    'plt.title(f"Pairwise Win Rate Heatmap - {format_name}\\n(Rows: Player Heuristic, Columns: Opponent Agent)", fontsize=14, fontweight=\'bold\', pad=15)',
    'plt.title(f"Pairwise Win Rate Heatmap - {format_name}\\n(Rows: player, columns: opponent; v15–v17 minimax, v18–v20 MCTS, v21–v22 IL)", fontsize=13, fontweight=\'bold\', pad=15)',
)
replace_in_source(nb.cells[11], 'plt.ylabel("Player Agent (Us)")', 'plt.ylabel("Player")')
replace_in_source(
    nb.cells[14],
    'plt.title("Bradley-Terry Elo Strength of Heuristic Agents (Anchor: random = 1000)", fontsize=15, fontweight=\'bold\', pad=15)',
    'plt.title("Bradley-Terry Elo (all paradigms; anchor random = 1000)\\nMCTS v18–v20 cells are n=1k — noisier than 10k agents", fontsize=14, fontweight=\'bold\', pad=15)',
)
replace_in_source(
    nb.cells[15],
    "Let's trace which heuristic agents Terastallize the most, and how Terastallization rate correlates with average Elo.",
    "Tera rate vs Elo for **all gen9 agents**. v12 Teras almost every game; v13 is conservative; v22 Teras like v12 and still loses. Frequency is not skill.",
)
save(path, nb)

# ── dataset integrity ───────────────────────────────────────────────────────
path, nb = load("dataset_integrity_verification.ipynb")
# Drop the two stray cells that duplicate §13 at the top (markdown + code-as-markdown).
src0 = "".join(nb.cells[0].source) if not isinstance(nb.cells[0].source, str) else nb.cells[0].source
if src0.startswith("## 13 · Fainted"):
    del nb.cells[0]
    src0 = "".join(nb.cells[0].source) if not isinstance(nb.cells[0].source, str) else nb.cells[0].source
    if "over6_violations" in src0[:80]:
        del nb.cells[0]
    print("  removed stray §13 cells at top of integrity notebook")

title = nbf.v4.new_markdown_cell(
    """\
# Dataset integrity verification

Checks the 28×28 `gen9randombattle` gauntlet (784 CSVs). This notebook does **not**
interpret skill; it only asks whether the files are complete, parseable, and internally
consistent.

**Taxonomy**

| IDs | Paradigm | Games / matchup |
|---|---|---|
| v1–v14 | Heuristic ladder | 10,000 (1,000 if the opponent is v18/v19/v20) |
| v15–v17 | 1-ply minimax | same |
| v18–v20 | shallow MCTS | **1,000** whenever either side is v18/v19/v20 |
| v21 / v22 | IL hybrid / IL pure | 10,000 (1,000 vs MCTS) |
| six baselines | `random`, `max_power`, `one_step`, `safe_one_step`, `abyssal`, `simple_heuristic` | same as heuristics |

Do not label v17 as MCTS or v19–v20 as imitation.

## 1 · Setup
""".strip()
    + "\n"
)
nb.cells.insert(0, title)

setup = nb.cells[1]  # imports, was cell 0 after deletion
src = setup.source if isinstance(setup.source, str) else "".join(setup.source)
old_agents = '''ALL_AGENTS = [
    "v1","v2","v3","v4","v5","v6","v7","v8","v9","v10","v11","v12","v13","v14",
    "v15","v16","v17","v18","v19","v20","v21","v22",
    "random","max_power","abyssal","one_step","safe_one_step","simple_heuristic"
]'''
new_agents = '''# Taxonomy: v1–v14 heuristic, v15–v17 1-ply minimax, v18–v20 shallow MCTS (n=1k),
# v21 IL hybrid, v22 IL pure, then six baselines.
ALL_AGENTS = [
    "v1","v2","v3","v4","v5","v6","v7","v8","v9","v10","v11","v12","v13","v14",  # heuristic
    "v15","v16","v17",  # 1-ply minimax
    "v18","v19","v20",  # shallow MCTS (n=1k)
    "v21","v22",        # IL hybrid / pure
    "random","max_power","abyssal","one_step","safe_one_step","simple_heuristic",
]'''
if old_agents in src:
    setup.source = src.replace(old_agents, new_agents)
else:
    print("  WARN: ALL_AGENTS block not found exactly")

if "Taxonomy    :" not in (setup.source if isinstance(setup.source, str) else "".join(setup.source)):
    s = setup.source if isinstance(setup.source, str) else "".join(setup.source)
    setup.source = s.rstrip() + '\nprint("Taxonomy           : v1–v14 heuristic | v15–v17 minimax | v18–v20 MCTS | v21–v22 IL")\n'

for cell in nb.cells:
    replace_in_source(
        cell,
        'ax.set_ylabel("Heuristic (Player)", fontsize=12, labelpad=10)',
        'ax.set_ylabel("Player", fontsize=12, labelpad=10)',
    )
    replace_in_source(
        cell,
        'ax.set_title("Tournament Coverage Matrix (28×28)", fontsize=14, fontweight="bold", pad=15)',
        'ax.set_title("Tournament coverage (28×28)\\nv1–v14 heuristic · v15–v17 minimax · v18–v20 MCTS · v21–v22 IL", fontsize=13, fontweight="bold", pad=15)',
    )
save(path, nb)

print("done")
