# p01_heuristics: Rule-Based Intelligence & Heuristic Design

Welcome to the **Heuristics Module**, the logical core of the Pokémon Showdown AI. This directory houses the rule-based decision engines that power our agents, ranging from simple greedy algorithms to complex, field-aware strategic experts.

These agents serve three primary roles:
1.  **Performance Baselines**: Providing a standard against which Reinforcement Learning models are measured.
2.  **RL Teachers**: The most advanced versions (**V6** for Singles and **V5** for Doubles) act as "expert" teachers to generate trajectories for training Reinforcement Learning models.
3.  **Standalone Competitors**: Highly optimized rulesets capable of competing at high levels in Random Battles.

---

## 1. Directory Architecture

The module is strictly partitioned by battle format to handle the unique complexities of single vs. double battles.

```text
p01_heuristics/
├── s01_singles/          # 1v1 Battle Logic
│   ├── s01_singles.md    # Master framework & Benchmarking overview
│   ├── docs/             # s01_singles_guide.md, CLI, Data Layout, LLM Setup
│   ├── core/             # s01_core.md (Infrastructure)
│   └── evaluation/       # s01_evaluation.md (Performance benchmarking)
├── s02_doubles/          # 2v2 Battle Logic
│   ├── s02_doubles_guide.md # Doubles technical design & strategy guide
│   ├── core/             # s02_core_infrastructure.md
│   └── evaluation/       # Automated doubles benchmarking suite
└── p01_heuristics_overview.md # Unified Master Overview (this file)
```

---

## 2. How it Works: The Decision Pipeline

The heuristics do not "learn" in real-time; instead, they follow a pre-defined mathematical framework to evaluate the game state. Regardless of the battle format, every agent follows a structured **Thinking Loop** that converts raw data into a strategic move.

### 2.1 State Extraction (The Sensory Phase)
The process begins when the Pokémon Showdown server sends a JSON request. The framework parses this raw data into a high-level **Battle Object**. This object provides the agent with a "God's eye view" of the accessible information:
*   **Our Team**: Current HP, status, remaining moves (PP), and active stat boosts.
*   **The Field**: Active Weather (Rain, Sun), Terrain (Grassy, Electric), and Entry Hazards (Spikes, Stealth Rock).
*   **The Opponent**: Known Pokémon, revealed moves, and estimated stat tiers.

### 2.2 Move Scoring (The Logic Phase)
This is the "brain" of the heuristic. Every legal action (every move and every possible switch) is assigned a numeric **Desirability Score**. The final score is a weighted sum of three core metrics:

1.  **Offensive Potential (Damage & Pressure)**: 
    *   The agent calculates an **estimated damage range** for every move using a specialized estimator (`core/common.py`). 
    *   It applies multipliers for **STAB** (Same Type Attack Bonus), **Type Effectiveness** (4x, 2x, 0.5x, etc.), and environmental factors (e.g., Water moves doing 1.5x in Rain).
2.  **Strategic Utility (Status & Field Control)**:
    *   Moves that don't do direct damage (like *Toxic* or *Stealth Rock*) are valued based on their long-term impact. For example, a status move might receive a high score if the opponent isn't already afflicted.
3.  **Survival & Risk Assessment (The Defense Hook)**:
    *   The agent performs a "Danger Check." If the active Pokémon is at low health or faces a faster opponent with a lethal type advantage, the score for **Switching** increases significantly. This is known as "Pivoting."

### 2.3 Coordination: Cross-Slot Synergy (Doubles Only)
In 2-vs-2 battles, scoring a single move is not enough. The engine must evaluate **pairs of actions** (Slot 0 + Slot 1). It uses a "Score-then-Combine" approach:
*   **Focus Fire**: If both Pokémon attacking the same target results in a guaranteed Knock-Out (KO), that pair of moves receives a massive synergy bonus.
*   **Protect & Support**: The engine rewards combinations where one Pokémon uses *Protect* while the other attacks, or where one sets up *Tailwind* to help the other sweep.
*   **Efficiency**: It penalizes "Overkill" (e.g., Slot 0 KOs the target, so Slot 1's move on that same target would be wasted).

### 2.4 Action Selection (The Execution Phase)
Once all valid actions (or action pairs) have been scored:
1.  **Ranking**: The engine sorts the orders from highest to lowest score.
2.  **Validation**: It performs a final check to ensure the move is still legal (e.g., not disabled by *Taunt*).
3.  **Submission**: The highest-scoring order is formatted into a Showdown-compatible string and sent back to the server.
4.  **Fallback**: If a logic error occurs or no move scores above a threshold, the system defaults to a **Random Legal Move** to ensure the battle never deadlocks.

---

## 3. The RL Teachers: Expert Heuristics

While the folder contains many versions, the following are designated as the "Teachers" for higher-level AI training:

### Singles: V6 (The Champion)
The definitive heuristic for 1v1. It is the most robust teacher due to its:
*   **Priority Awareness**: Knows when to use moves like *Extreme Speed* to finish low-HP targets.
*   **Defensive Stability**: Uses the "V3 Pivot" logic to escape bad matchups and Toxic counters.
*   **Field Scaling**: Perfect awareness of Sun/Rain and Electric/Grassy terrains.

### Doubles: V5 (Apex Heuristic)
The primary teacher for 2v2 coordination. Key teaching behaviors include:
*   **Focus Fire**: Coordinating both active Pokémon to target a single high-threat opponent.
*   **Predictive KOs**: Calculating if one Pokémon can secure a KO so the other can target a different slot.
*   **Environmental Control**: Managing Weather and Terrain specifically for doubles synergy.

---

## 4. Execution Guide

We use `uv` for high-performance execution. The system is designed for **Subprocess Isolation**, meaning it spawns independent processes to prevent memory leaks during massive simulation runs.

### Running a Benchmark
To test agents against each other and generate performance data:

**For Singles (1v1), eg. 1000 games:**
```bash
uv run python src/p01_heuristics/s01_singles/evaluation/engine/benchmark.py 1000 --ports 4
```

**For Doubles (2v2), eg. 1000 games:**
```bash
uv run python src/p01_heuristics/s02_doubles/evaluation/engine/benchmark.py 1000 --ports 4
```

### Generating Analytics Reports
The reporting tools automatically save outputs (plots, Elo rankings, LaTeX tables) into the source data folder by default for better organization.

**For Singles (1v1):**
```bash
# Full Scientific Report (Heatmaps, Scatter plots, LaTeX tables)
uv run python src/p01_heuristics/s01_singles/evaluation/reporting/plots/generate_full_report.py --data-dir data/1_vs_1/benchmarks/gens_10k_teams/gen9randombattle

# Calculate Elo Ratings (MLE Bradley-Terry)
uv run python src/p01_heuristics/s01_singles/evaluation/reporting/elo/elo_ranking.py --data-dir data/1_vs_1/benchmarks/gens_10k_teams/gen9randombattle
```

**For Doubles (2v2):**
```bash
# 1. Generate/Update the Summary CSV from raw results
uv run python src/p01_heuristics/s02_doubles/evaluation/engine/summarize_results.py --data-dir data/2_vs_2/benchmarks/gens_10k_teams/gen9randomdoublesbattle

# 2. Generate Visual Performance Report
uv run python src/p01_heuristics/s02_doubles/evaluation/reporting/generate_report.py --csv data/2_vs_2/benchmarks/gens_10k_teams/gen9randomdoublesbattle/benchmark_summary.csv
```

---

## 5. Data Persistence: Where it Saves

All benchmark results and logs are stored outside the `src` directory to keep the codebase clean and the experimental data portable.

*   **Primary Data Store**: All raw results are stored in the `data/` directory at the project root, partitioned by format and generation:
    *   **Singles (1v1)**: `data/1_vs_1/benchmarks/gens_10k_teams/genXrandombattle/`
    *   **Doubles (2v2)**: `data/2_vs_2/benchmarks/gens_10k_teams/genXrandomdoublesbattle/`
*   **Analytics Artifacts**: Look for `01_win_rate_heatmap.png`, `elo_summary.csv`, and the `latex_tables/` directory **within the same specific folder** as the raw CSV data.
*   **Thinking Logs (LLMs)**: For agents that use LLM reasoning, full "Chain of Thought" logs are saved in `src/p01_heuristics/s01_singles/evaluation/results/LLM/`.

---

## 6. Key Features

*   **Parallelism**: Built-in support for multiple Showdown server instances running on different ports.
*   **Resilience**: The benchmark engine includes a **Resume & Complete** feature—if a run crashes, it will automatically skip already completed games.
*   **Granular Metrics**: We track more than just winrates. Our logs include:
    *   **Luck Metrics**: Critical hits, misses, and RNG variance.
    *   **Strategic Metrics**: Voluntary switches, hazard damage, and team HP percentage.
    *   **Performance Metrics**: Seconds-per-game (SPG) for every matchup.

---

> [!TIP]
> For deep-dives into specific formats, please refer to the internal READMEs:
> - **Singles**: [s01_singles/s01_singles.md](file:///home/sirp/Documents/MUDS/TFM_Pokemon/src/p01_heuristics/s01_singles/s01_singles.md)
> - **Doubles**: [s02_doubles/s02_doubles_guide.md](file:///home/sirp/Documents/MUDS/TFM_Pokemon/src/p01_heuristics/s02_doubles/s02_doubles_guide.md)

