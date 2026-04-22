# Data Layout: `data/1_vs_1/`

This module standardizes all Singles (1v1) outputs under `data/1_vs_1/`. The structure is designed to keep raw data and analysis results co-located for better portability and organization.

---

## 1. Benchmarks Architecture

The primary location for long-running experimental data (10k team benchmarks) is `benchmarks/gens_10k_teams/`. Results are partitioned by generation to allow for multi-generation performance sweeps.

```text
data/1_vs_1/benchmarks/gens_10k_teams/
├── gen9randombattle/           # Target folder for Gen 9 runs
│   ├── {agent}_vs_{opponent}.csv  # Raw matchup data (win/loss, turns, fainted, HP, Luck)
│   ├── elo_summary.csv            # Calculated Bradley-Terry Elo ratings
│   ├── 01_win_rate_heatmap.png    # Primary Performance Heatmap
│   ├── 02_agent_ranking.png       # Sorted Win Rate Bar Chart
│   ├── 03_fainted_diff.png        # Combat effectiveness analysis
│   ├── ... (04-11)                # Advanced metrics (Luck, Hazard mgmt, Efficiency)
│   └── latex_tables/              # Academic export files
│       ├── win_rate_matrix.tex
│       └── fainted_diff.tex
├── gen8randombattle/           # Mirrored structure for Gen 8
└── ... (gen1, gen4, gen5, gen6, gen7)
```

---

## 2. Other Directories

*   **`runs/`**: Contains temporary or one-off outputs from `run_single.py` or manual `worker.py` debugging sessions.
*   **`legacy/`**: Archived folder layouts and historical snapshots. These are kept for reproducibility of early-stage project results.

---

## 3. Workflow Integration

All reporting scripts in `s01_singles/evaluation/reporting/` are now "data-aware." They will:
1.  Read the raw CSVs from the specified `--data-dir`.
2.  Generate the analytical plots (`.png`) and Elo ratings.
3.  **Auto-save** all artifacts back into that same directory.

> [!NOTE]
> This ensures that each generation folder is a self-contained unit of analysis, making it easy to zip and share experimental results for publication.
