# Executive EDA Report: Heuristic Agent `v8`

## 1. Executive Summary
- **Target Agent**: `v8`
- **Total Battles Evaluated**: 253,000 games across 28 matchups
- **Overall Win Rate**: 55.43%
- **Best Matchup**: `random` (97.67% ± 0.30%)
- **Worst Matchup**: `v12` (32.86% ± 0.92%)

---

## 2. Performance Breakdown by Opponent Paradigm
| Opponent Paradigm | Total Games | Win Rate (%) | Avg Turns | Avg HP Margin | Avg Vol. Switches (Us vs Opp) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline** | 60,000.0 | 65.55% | 18.43 | 1.36 | 1.51 vs 2.61 |
| **Heuristic (Basic)** | 60,000.0 | 61.69% | 17.20 | 0.87 | 1.38 vs 1.12 |
| **Heuristic (Strategic)** | 30,000.0 | 49.44% | 17.44 | 0.37 | 1.48 vs 1.55 |
| **Heuristic (Tactical)** | 20,000.0 | 48.40% | 17.48 | 0.35 | 1.50 vs 1.50 |
| **Heuristic (Tera)** | 10,000.0 | 32.86% | 17.60 | -0.16 | 1.55 vs 1.47 |
| **Heuristic (Advanced)** | 10,000.0 | 34.20% | 18.72 | -1.11 | 1.64 vs 3.60 |
| **Heuristic (Prediction)** | 10,000.0 | 43.31% | 18.19 | -0.42 | 1.56 vs 2.31 |
| **Minimax Search** | 20,000.0 | 51.65% | 18.55 | -0.05 | 1.51 vs 2.20 |
| **MCTS Search** | 11,000.0 | 47.78% | 18.38 | -0.21 | 1.53 vs 2.24 |
| **Imitation Learning** | 12,000.0 | 46.92% | 17.89 | -0.19 | 1.52 vs 2.16 |
| **Pure Imitation** | 10,000.0 | 71.23% | 19.30 | 1.15 | 1.50 vs 3.87 |

---

## 3. Matchup Summary Table (with 95% Confidence Intervals)
| Opponent | Paradigm | Games | Win Rate (%) | 95% CI (±%) | Avg Turns | Avg HP Us | Avg HP Opp | Sample Warning |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `random` | Baseline | 10,000 | 97.67% | ±0.30% | 23.47 | 3.87 | 0.03 | ✅ N=10k |
| `max_power` | Baseline | 10,000 | 87.01% | ±0.66% | 17.75 | 2.32 | 0.13 | ✅ N=10k |
| `v22` | Pure Imitation | 10,000 | 71.23% | ±0.89% | 19.30 | 1.66 | 0.50 | ✅ N=10k |
| `v6` | Heuristic (Basic) | 10,000 | 62.23% | ±0.95% | 17.16 | 1.27 | 0.38 | ✅ N=10k |
| `v2` | Heuristic (Basic) | 10,000 | 62.14% | ±0.95% | 17.18 | 1.26 | 0.38 | ✅ N=10k |
| `safe_one_step` | Baseline | 10,000 | 62.09% | ±0.95% | 16.98 | 1.25 | 0.38 | ✅ N=10k |
| `v1` | Heuristic (Basic) | 10,000 | 61.82% | ±0.95% | 17.27 | 1.26 | 0.38 | ✅ N=10k |
| `v3` | Heuristic (Basic) | 10,000 | 61.59% | ±0.95% | 17.31 | 1.25 | 0.39 | ✅ N=10k |
| `one_step` | Baseline | 10,000 | 61.44% | ±0.95% | 17.04 | 1.24 | 0.39 | ✅ N=10k |
| `v5` | Heuristic (Basic) | 10,000 | 61.39% | ±0.95% | 17.11 | 1.24 | 0.39 | ✅ N=10k |
| `v4` | Heuristic (Basic) | 10,000 | 60.97% | ±0.96% | 17.16 | 1.24 | 0.39 | ✅ N=10k |
| `v19` | Imitation Learning | 1,000 | 52.50% | ±3.10% | 18.16 | 0.99 | 0.96 | ⚠️ N=1k (high variance) |
| `v16` | Minimax Search | 10,000 | 51.94% | ±0.98% | 18.64 | 0.98 | 1.00 | ✅ N=10k |
| `v7` | Heuristic (Strategic) | 10,000 | 51.61% | ±0.98% | 17.36 | 0.98 | 0.56 | ✅ N=10k |
| `v15` | Minimax Search | 10,000 | 51.36% | ±0.98% | 18.46 | 0.96 | 1.02 | ✅ N=10k |
| `v10` | Heuristic (Tactical) | 10,000 | 50.81% | ±0.98% | 17.40 | 0.94 | 0.55 | ✅ N=10k |
| `v18` | MCTS Search | 1,000 | 50.20% | ±3.10% | 18.00 | 0.94 | 0.94 | ⚠️ N=1k (high variance) |
| `v8` | Heuristic (Strategic) | 10,000 | 49.92% | ±0.98% | 17.44 | 0.94 | 0.59 | ✅ N=10k |
| `v17` | MCTS Search | 10,000 | 47.54% | ±0.98% | 18.42 | 0.87 | 1.10 | ✅ N=10k |
| `v9` | Heuristic (Strategic) | 10,000 | 46.80% | ±0.98% | 17.53 | 0.94 | 0.61 | ✅ N=10k |
| `v21` | Imitation Learning | 10,000 | 46.61% | ±0.98% | 17.84 | 0.86 | 1.05 | ✅ N=10k |
| `v11` | Heuristic (Tactical) | 10,000 | 45.99% | ±0.98% | 17.55 | 0.91 | 0.61 | ✅ N=10k |
| `v20` | Imitation Learning | 1,000 | 44.40% | ±3.08% | 18.05 | 0.82 | 1.17 | ⚠️ N=1k (high variance) |
| `v14` | Heuristic (Prediction) | 10,000 | 43.31% | ±0.97% | 18.19 | 0.79 | 1.21 | ✅ N=10k |
| `simple_heuristic` | Baseline | 10,000 | 42.80% | ±0.97% | 17.55 | 0.88 | 0.65 | ✅ N=10k |
| `abyssal` | Baseline | 10,000 | 42.30% | ±0.97% | 17.76 | 0.84 | 0.66 | ✅ N=10k |
| `v13` | Heuristic (Advanced) | 10,000 | 34.20% | ±0.93% | 18.72 | 0.69 | 1.80 | ✅ N=10k |
| `v12` | Heuristic (Tera) | 10,000 | 32.86% | ±0.92% | 17.60 | 0.61 | 0.77 | ✅ N=10k |

---

## 4. Key Analytical Insights
1. **Search Horizon Impact**: Performance against Minimax (v15-v16) and MCTS (v17-v18) reveals how static rule evaluation holds up against tree search lookahead.
2. **Imitation Learning Counterplay**: Evaluation against XGBoost hybrid (v21) and Pure IL (v22) highlights strengths and vulnerabilities against data-driven policy models.
3. **Statistical Integrity**: All win rates are reported with 95% confidence bounds. Matchups with 1,000 games are flagged for elevated variance.
