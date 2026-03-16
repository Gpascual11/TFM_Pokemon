# ⚔️ EVALUATION: Testing, Benchmarking & Analysis

The `evaluation` directory is the lab where we prove that our agents are getting smarter. It handles everything from battle execution to data visualization.

---

For a complete CLI reference (including all flags and `uv` commands), see `../docs/CLI_REFERENCE.md`.  
For where outputs are written, see `../docs/DATA_LAYOUT.md`.

## 🏎️ 1. The Benchmark Engine (`engine/`)

We provide two main ways to run experiments.

### 💂 The Parallel Orchestrator (`benchmark.py`)

This is the **High-Level Entry Point**. It is designed for large tournaments (e.g., 10 agents vs 10 opponents, 1000 games each).

- **Matchup Matrix**: It generates a list of every possible agent/opponent pair.
- **Dynamic Port Scaling**: It distributes work to workers as ports become available.
- **CSV Merging**: It takes the results from every parallel worker and merges them into a clean, final dataset.
- **Resume Feature**: Automatically detects existing files to finish interrupted runs.

### 🛡️ The Subprocess Worker (`worker.py`)

This is the **Low-Level Executor**. Each worker handles one specific port and one specific matchup at a time.

- **RAM Safety**: It implements massive memory-cleanup (chunking, clearing battle history, and calling the Garbage Collector).
- **Independence**: A worker does not care about other workers; it only cares about its assigned port and target game count.

---

## 📊 2. Reporting & Visualization (`reporting/`)

Data is only useful if it can be understood.

### `heatmaps.py` — The Win Rate Matrix

This script scans the `data/1_vs_1/benchmarks/unified/` folder (legacy: `data/1_vs_1/benchmarks_unified/` or `data/benchmarks_unified/`) and generates a high-resolution heatmap.

- **X-axis**: Opponents
- **Y-axis**: Our Agents
- **Color**: Darker/Warmer colors indicate higher win rates.
- **Command**: `uv run python src/p01_heuristics/s01_singles/evaluation/reporting/heatmaps.py`

---

## 📁 3. Results Management (`results/`)

This directory is organized into several key areas:

- **`LLM/`**: Contains the reasoning logs (`thinking_*.txt`) for model-based agents.
- **`heatmaps/`**: Stores the generated PNG visualizations.
- **`matchups/`**: Older JSON-based results for specific single-run debugs.

---

## 🛠️ 4. How to run an Evaluation (Step-by-Step)

1. **Prep the Servers**: Ensure you have enough Pokémon Showdown servers available. The system can handle up to 16+ parallel ports if your hardware allows.
2. **Start the Benchmark**:

    ```bash
    # Run 100 battles for all pairs of v4,v5,v6 against abyssal
    uv run python src/p01_heuristics/s01_singles/evaluation/engine/benchmark.py 100 \
        --agents v4 v5 v6 \
        --opponents abyssal \
        --ports 4
    ```

3. **Monitor Progress**: The benchmark will show you in real-time which "Batch" is running on which "Port".
4. **Analyze**: Run the heatmap script to see which version performs best.

## 🚀 5. Optimization History (March 2026 Updates)

We recently implemented several critical fixes that transformed the benchmark's scalability, especially for older generations like Gen 5.

### **The Challenges We Solved**
1.  **IndexError in Identifier Parsing**: Fixed a crash in `abstract_battle.py` when handling short identifiers in Gen 5 battle messages.
2.  **The JSON Parsing Bottleneck**: Previously, every Pokémon object (12 per battle) re-opened and parsed the `sets_1500.json` file (2.6MB). In large runs, this was parsing gigabytes of JSON data repeatedly, leading to:
    *   **RAM Spikes**: Peak memory usage was reaching **31GB+** with only 4 parallel ports.
    *   **CPU Overhead**: The CPU was wasting time on I/O and parsing instead of game logic.
    *   **Timeouts**: Slow simulation caused many battles to exceed the 5-minute timeout window.

### **The Optimization: Global Sets Cache**
We implemented a **class-level cache** in `pokemon.py`. Now, the sets data is loaded and parsed **exactly once per worker process**.

### **Impact**
*   **Memory Drop**: RAM usage fell from **31GB (4 ports)** to **13GB (8 ports)**.
*   **Speedup**: Gen 5 battles now finish in seconds rather than minutes.
*   **Higher Throughput**: The system now runs at **100% CPU utilization** (doing actual battle logic) while keeping the RAM "chill."
*   **Tested Stability**: Validated with 1000-game runs using **8 Ports and 25 Concurrency** with zero crashes.

---

## ⚡ Performance Tips

- **CPU Utilization**: The benchmark is now highly efficient. You can easily push to **8-16 parallel ports** depending on your core count.
- **RAM Scaling**: Thanks to the global sets cache, RAM scales much more linearly. Each additional port only adds a small constant overhead.
- **Concurrency Settings**: We recommend **25 concurrency** per port for rule-based heuristics to keep the throughput high.
- **Data Integrity**: These optimizations only affect infrastructure (how files are read); the battle logic, agent decisions, and research validity remain 100% "real" and identical to official `poke-env` rules.
