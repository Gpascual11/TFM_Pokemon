# s02_doubles: 2-vs-2 Heuristic Agents

This directory contains the testing suite for Doubles (2v2) heuristics. It is architected for high-performance parallel execution using `uv`.

## 📂 Content Overview

### `agents/`

- **`internal/`**: Core heuristic versions (v1, v2, v6).
- **`baselines/`**: Standard opponents (Abyssal, Random) and specialized VGC players.

### `evaluation/`

The internal engine for double battles:

- **`engine/benchmark.py`**: High-performance parallel orchestrator.
- **`reporting/heatmaps.py`**: Visual analysis script.

---

## ⚙️ How it Works

Doubles heuristics use a **Score-then-Combine** pattern:

1. **Candidate Selection**: For each active slot, the engine lists all valid actions.
2. **Scoring**: Each action is scored individually (e.g., damage against most vulnerable opponent).
3. **Combination**: `DoubleBattleOrder.join_orders` produces valid pairings, filtering illegal moves (like switching to the same Pokémon twice).
4. **Policy**: The pair with the highest combined score is picked.

---

## 🚀 How to Run

### ⚔️ Automated Doubles Benchmark

The script automatically manages multiple Showdown server ports and calculates a full cross-matchup win-rate matrix.

```bash
uv run python src/p01_heuristics/s02_doubles/evaluation/engine/benchmark.py 1000 --ports 4
```

### 📊 Visual Report

Generate a beautiful heatmap of the results:

```bash
uv run python src/p01_heuristics/s02_doubles/evaluation/reporting/heatmaps.py
```

---

## 🛠️ Technical Features

### Memory safety

- **Isolated Workers**: Each matchup batch runs in a fresh process, preventing memory leaks (especially for LLM threads).
- **Server Cycling**: Automatic server restarts ensure Node.js memory bloat doesn't crash the simulation.

### Competitive Tactics

- **VGC Specialist**: Includes a `vgc` agent that prioritizes speed control (Tailwind, Icy Wind) and spread moves.
