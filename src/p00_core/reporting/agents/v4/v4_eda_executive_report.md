# Executive EDA Report: Heuristic Agent `v4`

## 1. Executive Summary
- **Target Agent**: `v4`
- **Total Battles Evaluated**: 253,000 games across 28 matchups
- **Overall Win Rate**: 45.50%
- **Best Matchup**: `random` (97.29% ± 0.32%)
- **Worst Matchup**: `v12` (24.44% ± 0.84%)

---

## 2. Performance Breakdown by Opponent Paradigm
| Opponent Paradigm | Total Games | Win Rate (%) | Avg Turns | Avg HP Margin | Avg Vol. Switches (Us vs Opp) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline** | 60,000.0 | 57.10% | 18.84 | 0.96 | 1.04 vs 2.67 |
| **Heuristic (Basic)** | 60,000.0 | 50.87% | 17.47 | 0.43 | 1.02 vs 1.11 |
| **Heuristic (Strategic)** | 30,000.0 | 38.05% | 17.29 | -0.05 | 1.02 vs 1.46 |
| **Heuristic (Tactical)** | 20,000.0 | 37.14% | 17.21 | -0.06 | 1.02 vs 1.40 |
| **Heuristic (Tera)** | 10,000.0 | 24.44% | 17.10 | -0.43 | 1.02 vs 1.37 |
| **Heuristic (Advanced)** | 10,000.0 | 26.82% | 17.92 | -1.62 | 1.02 vs 3.14 |
| **Heuristic (Prediction)** | 10,000.0 | 33.17% | 17.79 | -0.98 | 1.01 vs 2.12 |
| **Minimax Search** | 20,000.0 | 40.38% | 18.40 | -0.65 | 1.02 vs 2.23 |
| **MCTS Search** | 11,000.0 | 36.75% | 18.15 | -0.84 | 1.01 vs 2.23 |
| **Imitation Learning** | 12,000.0 | 35.97% | 17.56 | -0.78 | 1.01 vs 2.10 |
| **Pure Imitation** | 10,000.0 | 66.23% | 19.65 | 0.79 | 1.03 vs 3.94 |

---

## 3. Matchup Summary Table (with 95% Confidence Intervals)
| Opponent | Paradigm | Games | Win Rate (%) | 95% CI (±%) | Avg Turns | Avg HP Us | Avg HP Opp | Sample Warning |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `random` | Baseline | 10,000 | 97.29% | ±0.32% | 25.13 | 3.57 | 0.03 | ✅ N=10k |
| `max_power` | Baseline | 10,000 | 80.87% | ±0.77% | 18.64 | 1.92 | 0.19 | ✅ N=10k |
| `v22` | Pure Imitation | 10,000 | 66.23% | ±0.93% | 19.65 | 1.41 | 0.62 | ✅ N=10k |
| `v1` | Heuristic (Basic) | 10,000 | 51.97% | ±0.98% | 17.52 | 0.95 | 0.47 | ✅ N=10k |
| `v3` | Heuristic (Basic) | 10,000 | 51.37% | ±0.98% | 17.39 | 0.94 | 0.49 | ✅ N=10k |
| `safe_one_step` | Baseline | 10,000 | 51.33% | ±0.98% | 17.35 | 0.93 | 0.49 | ✅ N=10k |
| `v6` | Heuristic (Basic) | 10,000 | 51.32% | ±0.98% | 17.40 | 0.94 | 0.49 | ✅ N=10k |
| `v2` | Heuristic (Basic) | 10,000 | 50.73% | ±0.98% | 17.46 | 0.92 | 0.50 | ✅ N=10k |
| `one_step` | Baseline | 10,000 | 50.28% | ±0.98% | 17.26 | 0.91 | 0.49 | ✅ N=10k |
| `v4` | Heuristic (Basic) | 10,000 | 50.14% | ±0.98% | 17.59 | 0.90 | 0.50 | ✅ N=10k |
| `v5` | Heuristic (Basic) | 10,000 | 49.66% | ±0.98% | 17.46 | 0.88 | 0.51 | ✅ N=10k |
| `v15` | Minimax Search | 10,000 | 40.42% | ±0.96% | 18.28 | 0.68 | 1.32 | ✅ N=10k |
| `v16` | Minimax Search | 10,000 | 40.34% | ±0.96% | 18.52 | 0.67 | 1.34 | ✅ N=10k |
| `v7` | Heuristic (Strategic) | 10,000 | 39.72% | ±0.96% | 17.29 | 0.68 | 0.69 | ✅ N=10k |
| `v19` | Imitation Learning | 1,000 | 39.40% | ±3.03% | 18.02 | 0.70 | 1.28 | ⚠️ N=1k (high variance) |
| `v8` | Heuristic (Strategic) | 10,000 | 39.35% | ±0.96% | 17.32 | 0.66 | 0.69 | ✅ N=10k |
| `v10` | Heuristic (Tactical) | 10,000 | 38.69% | ±0.95% | 17.14 | 0.66 | 0.70 | ✅ N=10k |
| `v18` | MCTS Search | 1,000 | 38.30% | ±3.01% | 17.93 | 0.63 | 1.32 | ⚠️ N=1k (high variance) |
| `v17` | MCTS Search | 10,000 | 36.59% | ±0.94% | 18.17 | 0.59 | 1.45 | ✅ N=10k |
| `v21` | Imitation Learning | 10,000 | 35.96% | ±0.94% | 17.54 | 0.60 | 1.37 | ✅ N=10k |
| `v11` | Heuristic (Tactical) | 10,000 | 35.59% | ±0.94% | 17.28 | 0.65 | 0.73 | ✅ N=10k |
| `v9` | Heuristic (Strategic) | 10,000 | 35.08% | ±0.94% | 17.27 | 0.64 | 0.75 | ✅ N=10k |
| `v14` | Heuristic (Prediction) | 10,000 | 33.17% | ±0.92% | 17.79 | 0.53 | 1.51 | ✅ N=10k |
| `v20` | Imitation Learning | 1,000 | 32.60% | ±2.91% | 17.26 | 0.52 | 1.53 | ⚠️ N=1k (high variance) |
| `simple_heuristic` | Baseline | 10,000 | 31.53% | ±0.91% | 17.39 | 0.58 | 0.77 | ✅ N=10k |
| `abyssal` | Baseline | 10,000 | 31.33% | ±0.91% | 17.28 | 0.57 | 0.78 | ✅ N=10k |
| `v13` | Heuristic (Advanced) | 10,000 | 26.82% | ±0.87% | 17.92 | 0.50 | 2.12 | ✅ N=10k |
| `v12` | Heuristic (Tera) | 10,000 | 24.44% | ±0.84% | 17.10 | 0.42 | 0.86 | ✅ N=10k |

---

## 4. Key Analytical Insights
1. **Search Horizon Impact**: Performance against Minimax (v15-v16) and MCTS (v17-v18) reveals how static rule evaluation holds up against tree search lookahead.
2. **Imitation Learning Counterplay**: Evaluation against XGBoost hybrid (v21) and Pure IL (v22) highlights strengths and vulnerabilities against data-driven policy models.
3. **Statistical Integrity**: All win rates are reported with 95% confidence bounds. Matchups with 1,000 games are flagged for elevated variance.
