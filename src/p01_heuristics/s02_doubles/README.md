# s02_doubles — Unified Doubles Heuristics & Agents Benchmark

This directory provides a unified framework for implementing and analyzing Pokémon Double Battle (2v2) agents. It follows the same architecture as the Singles module, providing a consistent experience across different formats.

---

## 📂 Directory Structure

```text
s02_doubles/
├── agents/              # 🧠 AGENT IMPLEMENTATIONS
│   ├── internal/        # Your v1, v2, v6 custom doubles heuristics
│   └── baselines/       # Standard players (Abyssal, SafeOneStep, VGCSpecialist)
│
├── core/                # ⚙️ SHARED INFRASTRUCTURE
│   ├── factory.py       # Unified AgentFactory: creates any doubles agent by label
│   ├── base.py          # Abstract Base Class (Score-then-Combine pattern)
│   └── common.py        # Shared math & damage utilities
│
├── evaluation/          # ⚔️ TESTING LAB
│   ├── engine/          # High-performance runners
│   │   ├── benchmark.py # Parallel orchestrator (doubles optimized)
│   │   └── worker.py    # Isolated subprocess worker
│   ├── reporting/       # Data analysis & visualization
│   │   └── heatmaps.py  # Generates cross-matchup win-rate matrices
│   └── results/         # Output artifacts (PNGs/CSVs)
│
└── README.md            # You are here
```

---

## ⚔️ Running Benchmarks

Run 100 doubles battles per matchup across 4 CPU workers:

```bash
uv run python src/p01_heuristics/s02_doubles/evaluation/engine/benchmark.py 100 --ports 4
```

### Specific Matchup

Test your VGC agent against the Abyssal baseline:

```bash
uv run python src/p01_heuristics/s02_doubles/evaluation/engine/benchmark.py 50 --agents vgc --opponents abyssal
```

---

## 📊 Generating Reports

Once the data is collected in `data/benchmarks_doubles_unified/`, generate the heatmap:

```bash
uv run python src/p01_heuristics/s02_doubles/evaluation/reporting/heatmaps.py
```

---

## ✨ Key Features

- **Score-then-Combine**: The Doubles core uses a sophisticated pattern to evaluate both active Pokémon slots and join their orders legally and optimally.
- **VGC Specialist**: Includes a high-tier heuristic (`vgc`) that prioritizes speed control and spread damage.
- **Unified Interface**: Use the same `AgentFactory` pattern as Singles to switch between rule-based and baseline opponents seamlessly.
