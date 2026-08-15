# gen9 tournament snapshot (re-run)

Directed 28×28 gauntlet. Taxonomy: v1–v14 heuristic, v15–v17 1-ply minimax,
v18–v20 shallow MCTS (n=1k), v21 hybrid IL, v22 IL (attribute-based move head).


## Bradley-Terry Elo (anchor random = 1000)

| agent            | paradigm   |     Elo |   wins |   games |
|:-----------------|:-----------|--------:|-------:|--------:|
| v12              | Heuristic  | 1812.09 | 348859 |  506000 |
| v13              | Heuristic  | 1801.65 | 342678 |  506000 |
| simple_heuristic | Baseline   | 1754.99 | 313795 |  506000 |
| v14              | Heuristic  | 1754.97 | 313787 |  506000 |
| abyssal          | Baseline   | 1754.67 | 313592 |  506000 |
| v20              | MCTS       | 1741.74 |  33472 |   56000 |
| v11              | Heuristic  | 1733.48 | 299939 |  506000 |
| v9               | Heuristic  | 1729.76 | 297518 |  506000 |
| v21              | IL Hybrid  | 1729.07 | 297070 |  506000 |
| v17              | Minimax    | 1722.16 | 292553 |  506000 |
| v10              | Heuristic  | 1705.51 | 281597 |  506000 |
| v8               | Heuristic  | 1704.07 | 280649 |  506000 |
| v18              | MCTS       | 1696.84 |  30182 |   56000 |
| v7               | Heuristic  | 1695.61 | 275053 |  506000 |
| v16              | Minimax    | 1694.21 | 274125 |  506000 |
| v19              | MCTS       | 1692.54 |  29864 |   56000 |
| v15              | Minimax    | 1690.92 | 271944 |  506000 |
| v5               | Heuristic  | 1630.38 | 231983 |  506000 |
| v4               | Heuristic  | 1627.64 | 230203 |  506000 |
| v6               | Heuristic  | 1624.83 | 228377 |  506000 |
| safe_one_step    | Baseline   | 1622.51 | 226874 |  506000 |
| one_step         | Baseline   | 1622.02 | 226551 |  506000 |
| v3               | Heuristic  | 1621.97 | 226521 |  506000 |
| v2               | Heuristic  | 1621.62 | 226296 |  506000 |
| v1               | Heuristic  | 1618.82 | 224484 |  506000 |
| v22              | IL Pure    | 1529.2  | 169716 |  506000 |
| max_power        | Baseline   | 1382.71 |  99920 |  506000 |
| random           | Baseline   | 1000    |  21398 |  506000 |

## Overall gauntlet WR (as us)

| heuristic        |   games |   wins |   win_rate_% | paradigm   |
|:-----------------|--------:|-------:|-------------:|:-----------|
| v12              |  253000 | 174607 |     69.0146  | Heuristic  |
| v13              |  253000 | 171094 |     67.6261  | Heuristic  |
| v14              |  253000 | 156936 |     62.03    | Heuristic  |
| abyssal          |  253000 | 156855 |     61.998   | Baseline   |
| simple_heuristic |  253000 | 156674 |     61.9265  | Baseline   |
| v20              |   28000 |  16705 |     59.6607  | MCTS       |
| v11              |  253000 | 149934 |     59.2625  | Heuristic  |
| v9               |  253000 | 148919 |     58.8613  | Heuristic  |
| v21              |  253000 | 148530 |     58.7075  | IL Hybrid  |
| v17              |  253000 | 146458 |     57.8885  | Minimax    |
| v10              |  253000 | 140811 |     55.6565  | Heuristic  |
| v8               |  253000 | 140234 |     55.4285  | Heuristic  |
| v16              |  253000 | 137380 |     54.3004  | Minimax    |
| v7               |  253000 | 137243 |     54.2462  | Heuristic  |
| v18              |   28000 |  15126 |     54.0214  | MCTS       |
| v15              |  253000 | 136112 |     53.7992  | Minimax    |
| v19              |   28000 |  14920 |     53.2857  | MCTS       |
| v5               |  253000 | 116035 |     45.8636  | Heuristic  |
| v4               |  253000 | 115125 |     45.504   | Heuristic  |
| v6               |  253000 | 114562 |     45.2814  | Heuristic  |
| one_step         |  253000 | 113264 |     44.7684  | Baseline   |
| v3               |  253000 | 113216 |     44.7494  | Heuristic  |
| safe_one_step    |  253000 | 113153 |     44.7245  | Baseline   |
| v2               |  253000 | 113101 |     44.704   | Heuristic  |
| v1               |  253000 | 111943 |     44.2462  | Heuristic  |
| v22              |  253000 |  84736 |     33.4925  | IL Pure    |
| max_power        |  253000 |  49751 |     19.6644  | Baseline   |
| random           |  253000 |  10638 |      4.20474 | Baseline   |