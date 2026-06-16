# p01_heuristics: Rule-Based Intelligence & Heuristic Design

Welcome to the **Heuristics Module**, the logical core of the Pokémon Showdown AI. This directory houses the rule-based decision engines that power our agents, ranging from simple greedy algorithms to complex, field-aware strategic experts.

These agents serve three primary roles:
1.  **Performance Baselines**: Providing a standard against which Reinforcement Learning models are measured.
2.  **RL Teachers**: The most advanced versions (e.g. **V14** / **V6**) act as "expert" teachers to generate trajectories for training Reinforcement Learning models.
3.  **Standalone Competitors**: Highly optimized rulesets capable of competing at high levels in Random Battles.

---

## 1. Directory Architecture

The heuristics framework is organized as follows:

```text
p01_heuristics/
├── agents/               # Heuristic Agent implementations (V1 to V14)
│   ├── baselines/        # Standard baseline players (random, max power, simple heuristic)
│   └── internal/         # Custom rule-based expert heuristics (v1.py to v14.py)
├── p01_heuristics_overview.md # Unified Master Overview (this file)
└── heuristics.md         # Heuristics framework guide
```

All evaluation, benchmarking, and core utilities are stored in the shared `p00_core` directory:
*   `src/p00_core/core/`: Common battle management, factories, base class, and process launcher.
*   `src/p00_core/engine/`: Benchmarking and simulation execution scripts.
*   `src/p00_core/docs/`: Comprehensive guides and reference logs.

---

## 2. How it Works: The Decision Pipeline

The heuristics do not "learn" in real-time; instead, they follow a pre-defined mathematical framework to evaluate the game state. Every agent follows a structured **Thinking Loop** that converts raw data into a strategic move.

### 2.1 State Extraction (The Sensory Phase)
The process begins when the Pokémon Showdown server sends a JSON request. The framework parses this raw data into a high-level **Battle Object**. This object provides the agent with a "God's eye view" of the accessible information:
*   **Our Team**: Current HP, status, remaining moves (PP), and active stat boosts.
*   **The Field**: Active Weather (Rain, Sun), Terrain (Grassy, Electric), and Entry Hazards (Spikes, Stealth Rock).
*   **The Opponent**: Known Pokémon, revealed moves, and estimated stat tiers.

### 2.2 Move Scoring (The Logic Phase)
This is the "brain" of the heuristic. Every legal action (every move and every possible switch) is assigned a numeric **Desirability Score**. The final score is a weighted sum of three core metrics:

1.  **Offensive Potential (Damage & Pressure)**: 
    *   The agent calculates an **estimated damage range** for every move using a specialized estimator (`p00_core/core/common.py`). 
    *   It applies multipliers for **STAB** (Same Type Attack Bonus), **Type Effectiveness** (4x, 2x, 0.5x, etc.), and environmental factors (e.g., Water moves doing 1.5x in Rain).
2.  **Strategic Utility (Status & Field Control)**:
    *   Moves that don't do direct damage (like *Toxic* or *Stealth Rock*) are valued based on their long-term impact. For example, a status move might receive a high score if the opponent isn't already afflicted.
3.  **Survival & Risk Assessment (The Defense Hook)**:
    *   The agent performs a "Danger Check." If the active Pokémon is at low health or faces a faster opponent with a lethal type advantage, the score for **Switching** increases significantly. This is known as "Pivoting."

### 2.3 Action Selection (The Execution Phase)
Once all valid actions have been scored:
1.  **Ranking**: The engine sorts the orders from highest to lowest score.
2.  **Validation**: It performs a final check to ensure the move is still legal (e.g., not disabled by *Taunt*).
3.  **Submission**: The highest-scoring order is formatted into a Showdown-compatible string and sent back to the server.
4.  **Fallback**: If a logic error occurs or no move scores above a threshold, the system defaults to a **Random Legal Move** to ensure the battle never deadlocks.

---

## 3. The RL Teachers: Expert Heuristics

The definitive heuristic versions are designated as the "Teachers" for higher-level AI training:

### Heuristic V6 (The Baseline Teacher)
Key behaviors:
*   **Priority Awareness**: Knows when to use moves like *Extreme Speed* to finish low-HP targets.
*   **Defensive Stability**: Uses the pivot logic to escape bad matchups and Toxic counters.
*   **Field Scaling**: Perfect awareness of Sun/Rain and Electric/Grassy terrains.

### Heuristic V14 (The Apex Teacher)
The most advanced heuristic developed, incorporating:
*   **Yomi Layer 2 Opponent Profiling**: Predicts opponent switches and counters setup/pivots.
*   **Dynamic Hazard Management**: Accurately values spikes/rocks setting and removal.
*   **Advanced Game State Simulation**: Tracks active boosts and defensive values dynamically.

---

## 4. Execution Guide

We use `uv` for high-performance execution. The system is designed for **Subprocess Isolation**, meaning it spawns independent processes to prevent memory leaks during massive simulation runs.

### Running a Benchmark
To test agents against each other and generate performance data:

**Run a Benchmark, eg. 1000 games:**
```bash
uv run python src/p00_core/engine/benchmark.py 1000 --ports 4
```

### Generating Analytics Reports
The reporting tools automatically save outputs (plots, Elo rankings, LaTeX tables) into the source data folder by default for better organization.

```bash
# Full Scientific Report (Heatmaps, Scatter plots, LaTeX tables)
uv run python src/p00_core/reporting/plots/generate_full_report.py --data-dir data/benchmarks/all_10k/gen9randombattle

# Calculate Elo Ratings (MLE Bradley-Terry)
uv run python src/p00_core/reporting/elo/elo_ranking.py --data-dir data/benchmarks/all_10k/gen9randombattle
```

---

## 5. Data Persistence: Where it Saves

All benchmark results and logs are stored outside the `src` directory to keep the codebase clean and the experimental data portable.

*   **Primary Data Store**: All raw results are stored in the `data/` directory at the project root:
    *   `data/benchmarks/all_10k/gen9randombattle/`
*   **Analytics Artifacts**: Look for `01_win_rate_heatmap.png`, `elo_summary.csv`, and the `latex_tables/` directory **within the same specific folder** as the raw CSV data.
*   **Thinking Logs (LLMs)**: For agents that use LLM reasoning, full "Chain of Thought" logs are saved in `src/p00_core/results/LLM/`.

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
> For deep-dives into specific heuristics implementation, please refer to:
> - **Heuristics Framework Guide**: [heuristics.md](file:///home/sirp/Documents/MUDS/TFM_Pokemon/src/p01_heuristics/heuristics.md)
> - **Heuristics Guide Document**: [heuristics_guide.md](file:///home/sirp/Documents/MUDS/TFM_Pokemon/src/p01_heuristics/docs/heuristics_guide.md)
