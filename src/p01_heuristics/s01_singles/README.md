# s01_singles — 1-vs-1 Heuristic Agents & Pokechamp Benchmarks

This directory contains the Singles (1v1) heuristic agents and two independent
benchmark pipelines: one for testing the agents against each other, and one
for comparing them against LLM-based agents from the Pokechamp repository.

---

## Directory Structure

```
s01_singles/
├── README.md                  ← This file
├── agents/                    ← Heuristic implementations (v1–v6), SHARED
├── core/                      ← BattleManager, Factory, ProcessLauncher, SHARED
├── heuristics/                ← Internal benchmark: v1–v6 round-robin
│   ├── README.md
│   ├── benchmark.py
│   ├── run.py
│   ├── generate_report.py
│   └── results/
└── pokechamp/                 ← Cross-repo benchmark: Pokechamp vs heuristics
    ├── README.md
    ├── pokechamp_benchmark.py
    ├── _pokechamp_worker.py
    ├── generate_pokechamp_report.py
    ├── generate_pokechamp_full_report.py
    └── results/
```

---

## `agents/` — Heuristic Implementations

| File | Description |
|------|-------------|
| `v1.py` | Max-damage greedy selector |
| `v2.py` | Adds type-advantage weighting |
| `v3.py` | Adds threat detection and switching |
| `v4.py` | Multi-factor scoring (damage, STAB, accuracy) |
| `v5.py` | Speed-tiering and field-state awareness |
| `v6.py` | Most advanced, full team view |

---

## `core/` — Shared Infrastructure

| File | Description |
|------|-------------|
| `base.py` | Abstract base class all heuristics inherit from |
| `factory.py` | Creates heuristic instances by name string |
| `battle_manager.py` | Connects to Showdown, runs batches, writes CSV |
| `process_launcher.py` | Distributes battles across multiple ports |
| `common.py` | Shared utilities and constants |

---

## How It Works

Each turn, the heuristics:
1. **Estimate damage** — `Attack / Defense × Power × Type multipliers`
2. **Check threats** — low HP or 4× weakness triggers a switch search
3. **KO first** — priority moves that can KO are picked immediately

---

## See Also

- [`heuristics/README.md`](heuristics/README.md) — internal round-robin benchmark
- [`pokechamp/README.md`](pokechamp/README.md) — Pokechamp vs heuristics benchmark
