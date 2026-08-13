# Executive EDA Report: Heuristic Agent `v7`

## 1. Executive Summary
- **Target Agent**: `v7`
- **Total Battles Evaluated**: 253,000 games across 28 matchups
- **Overall Win Rate**: 54.25%
- **Best Matchup**: `random` (97.61% ± 0.30%)
- **Worst Matchup**: `v12` (31.97% ± 0.91%)

---

## 2. Performance Breakdown by Opponent Paradigm
| Opponent Paradigm | Total Games | Win Rate (%) | Avg Turns | Avg HP Margin | Avg Vol. Switches (Us vs Opp) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline** | 60,000.0 | 64.37% | 18.52 | 1.31 | 1.49 vs 2.61 |
| **Heuristic (Basic)** | 60,000.0 | 60.51% | 17.29 | 0.83 | 1.36 vs 1.12 |
| **Heuristic (Strategic)** | 30,000.0 | 48.12% | 17.50 | 0.33 | 1.47 vs 1.55 |
| **Heuristic (Tactical)** | 20,000.0 | 47.23% | 17.45 | 0.31 | 1.47 vs 1.51 |
| **Heuristic (Tera)** | 10,000.0 | 31.97% | 17.60 | -0.18 | 1.54 vs 1.47 |
| **Heuristic (Advanced)** | 10,000.0 | 33.76% | 18.85 | -1.16 | 1.63 vs 3.61 |
| **Heuristic (Prediction)** | 10,000.0 | 42.01% | 18.22 | -0.49 | 1.53 vs 2.27 |
| **Minimax Search** | 20,000.0 | 50.72% | 18.59 | -0.10 | 1.51 vs 2.22 |
| **MCTS Search** | 11,000.0 | 46.17% | 18.33 | -0.29 | 1.53 vs 2.24 |
| **Imitation Learning** | 12,000.0 | 44.92% | 17.97 | -0.29 | 1.51 vs 2.16 |
| **Pure Imitation** | 10,000.0 | 70.49% | 19.38 | 1.11 | 1.47 vs 3.89 |

---

## 3. Matchup Summary Table (with 95% Confidence Intervals)
| Opponent | Paradigm | Games | Win Rate (%) | 95% CI (±%) | Avg Turns | Avg HP Us | Avg HP Opp | Sample Warning |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `random` | Baseline | 10,000 | 97.61% | ±0.30% | 23.64 | 3.85 | 0.03 | ✅ N=10k |
| `max_power` | Baseline | 10,000 | 85.69% | ±0.69% | 17.97 | 2.26 | 0.14 | ✅ N=10k |
| `v22` | Pure Imitation | 10,000 | 70.49% | ±0.89% | 19.38 | 1.64 | 0.53 | ✅ N=10k |
| `v2` | Heuristic (Basic) | 10,000 | 61.47% | ±0.95% | 17.33 | 1.24 | 0.39 | ✅ N=10k |
| `v6` | Heuristic (Basic) | 10,000 | 61.31% | ±0.95% | 17.30 | 1.24 | 0.39 | ✅ N=10k |
| `v1` | Heuristic (Basic) | 10,000 | 61.09% | ±0.96% | 17.30 | 1.24 | 0.39 | ✅ N=10k |
| `one_step` | Baseline | 10,000 | 60.91% | ±0.96% | 17.16 | 1.24 | 0.39 | ✅ N=10k |
| `safe_one_step` | Baseline | 10,000 | 60.51% | ±0.96% | 17.10 | 1.21 | 0.40 | ✅ N=10k |
| `v3` | Heuristic (Basic) | 10,000 | 60.46% | ±0.96% | 17.25 | 1.23 | 0.40 | ✅ N=10k |
| `v4` | Heuristic (Basic) | 10,000 | 59.72% | ±0.96% | 17.28 | 1.19 | 0.41 | ✅ N=10k |
| `v5` | Heuristic (Basic) | 10,000 | 59.01% | ±0.96% | 17.26 | 1.20 | 0.41 | ✅ N=10k |
| `v15` | Minimax Search | 10,000 | 51.07% | ±0.98% | 18.56 | 0.95 | 1.04 | ✅ N=10k |
| `v16` | Minimax Search | 10,000 | 50.37% | ±0.98% | 18.62 | 0.93 | 1.05 | ✅ N=10k |
| `v7` | Heuristic (Strategic) | 10,000 | 50.24% | ±0.98% | 17.48 | 0.95 | 0.58 | ✅ N=10k |
| `v18` | MCTS Search | 1,000 | 50.10% | ±3.10% | 17.85 | 0.95 | 1.00 | ⚠️ N=1k (high variance) |
| `v8` | Heuristic (Strategic) | 10,000 | 48.84% | ±0.98% | 17.44 | 0.92 | 0.59 | ✅ N=10k |
| `v10` | Heuristic (Tactical) | 10,000 | 48.36% | ±0.98% | 17.32 | 0.91 | 0.59 | ✅ N=10k |
| `v19` | Imitation Learning | 1,000 | 48.00% | ±3.10% | 18.22 | 0.92 | 1.02 | ⚠️ N=1k (high variance) |
| `v11` | Heuristic (Tactical) | 10,000 | 46.09% | ±0.98% | 17.59 | 0.91 | 0.61 | ✅ N=10k |
| `v17` | MCTS Search | 10,000 | 45.78% | ±0.98% | 18.38 | 0.85 | 1.16 | ✅ N=10k |
| `v9` | Heuristic (Strategic) | 10,000 | 45.29% | ±0.98% | 17.57 | 0.92 | 0.63 | ✅ N=10k |
| `v21` | Imitation Learning | 10,000 | 44.83% | ±0.97% | 17.92 | 0.81 | 1.11 | ✅ N=10k |
| `v20` | Imitation Learning | 1,000 | 42.70% | ±3.07% | 18.22 | 0.80 | 1.21 | ⚠️ N=1k (high variance) |
| `v14` | Heuristic (Prediction) | 10,000 | 42.01% | ±0.97% | 18.22 | 0.76 | 1.25 | ✅ N=10k |
| `abyssal` | Baseline | 10,000 | 40.80% | ±0.96% | 17.57 | 0.81 | 0.68 | ✅ N=10k |
| `simple_heuristic` | Baseline | 10,000 | 40.67% | ±0.96% | 17.65 | 0.83 | 0.68 | ✅ N=10k |
| `v13` | Heuristic (Advanced) | 10,000 | 33.76% | ±0.93% | 18.85 | 0.67 | 1.82 | ✅ N=10k |
| `v12` | Heuristic (Tera) | 10,000 | 31.97% | ±0.91% | 17.60 | 0.60 | 0.78 | ✅ N=10k |

---

## 4. Key Analytical Insights
1. **Search Horizon Impact**: Performance against Minimax (v15-v16) and MCTS (v17-v18) reveals how static rule evaluation holds up against tree search lookahead.
2. **Imitation Learning Counterplay**: Evaluation against XGBoost hybrid (v21) and Pure IL (v22) highlights strengths and vulnerabilities against data-driven policy models.
3. **Statistical Integrity**: All win rates are reported with 95% confidence bounds. Matchups with 1,000 games are flagged for elevated variance.
