# Data layout: `data/1_vs_1/`

This module standardises all Singles (1v1) outputs under `data/1_vs_1/`.

```text
data/1_vs_1/
├── benchmarks/
│   ├── unified/              # engine/benchmark.py outputs: {agent}_vs_{opponent}.csv
│   ├── pokechamp/            # pokechamp-labelled CSVs (if produced)
│   └── pokechamp_parallel/   # pokechamp parallel benchmark outputs (if produced)
├── runs/                     # run_single.py / BattleManager / ProcessLauncher outputs
└── legacy/                   # archived older folder layouts and historical snapshots
```

Notes:
- **Unified benchmark output** is the default path used by `evaluation/engine/benchmark.py`.
- **Legacy folders** are kept for reproducibility; most reporting scripts include fallbacks to older locations.

