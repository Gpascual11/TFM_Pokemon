# s01_singles — Unified Heuristics & Agents Benchmark

This directory provides a unified framework for implementing, executing, and analyzing Pokémon Single Battle (1v1) agents. It consolidates custom heuristics, standard baselines, and LLM-based researchers into a single workflow.

---

## 📂 Directory Structure

```text
s01_singles/
├── agents/              # 🧠 AGENT IMPLEMENTATIONS
│   ├── internal/        # Your v1–v6 custom heuristics
│   ├── baselines/       # Standard rule-based players (Abyssal, SafeOneStep, etc.)
│   └── llm/             # Connectors for LLM-based agents (Pokechamp, Pokellmon)
│
├── core/                # ⚙️ SHARED INFRASTRUCTURE
│   ├── factory.py       # Unified AgentFactory: creates any agent by string name
│   ├── base.py          # Abstract Base Class for all heuristic players
│   └── battle_manager.py # Showdown connection & results management
│
├── evaluation/          # ⚔️ TESTING LAB
│   ├── engine/          # High-performance runners
│   │   ├── benchmark.py # Parallel orchestrator (use this for large tests)
│   │   └── worker.py    # Isolated subprocess worker
│   ├── reporting/       # Data analysis & visualization
│   │   └── heatmaps.py  # Generates cross-matchup performance matrices
│   └── results/         # Output artifacts (PNGs/CSVs)
│
└── README.md            # You are here
```

---

## ⚔️ Running Benchmarks

The benchmark engine is unified. You can run any agent against any other agent using the same command.

### Large Parallel Batch
To run 100 battles per matchup across 4 CPU workers:
```bash
uv run python evaluation/engine/benchmark.py 100 --ports 4
```

### Specific Matchup
To test `v6` against `abyssal`:
```bash
uv run python evaluation/engine/benchmark.py 50 --agents v1 --opponents abyssal
```

---

## 📊 Generating Reports
Once the data is collected in `data/benchmarks_unified/`, generate the heatmap:
```bash
uv run python evaluation/reporting/heatmaps.py
```

---

## ✨ Key Benefits
- **Unified Factory**: Use `AgentFactory.create("v6")` or `AgentFactory.create("abyssal")` interchangeably.
- **Memory Safety**: Subprocess workers ensure background threads and memory leaks don't accumulate.
- **Scalability**: Add new agents to `agents/` and they are immediately available to the benchmark engine.
