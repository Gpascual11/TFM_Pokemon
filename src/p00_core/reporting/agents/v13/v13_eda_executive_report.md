# Executive EDA Report: Heuristic Agent `v13`

## 1. Executive Summary
- **Target Agent**: `v13`
- **Total Battles Evaluated**: 253,000 games across 28 matchups
- **Overall Win Rate**: 67.63%
- **Best Matchup**: `random` (98.18% ± 0.26%)
- **Worst Matchup**: `v12` (48.85% ± 0.98%)

---

## 2. Performance Breakdown by Opponent Paradigm
| Opponent Paradigm | Total Games | Win Rate (%) | Avg Turns | Avg HP Margin | Avg Vol. Switches (Us vs Opp) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline** | 60,000.0 | 74.36% | 19.05 | 2.26 | 3.77 vs 2.67 |
| **Heuristic (Basic)** | 60,000.0 | 72.90% | 17.97 | 1.84 | 3.07 vs 1.13 |
| **Heuristic (Strategic)** | 30,000.0 | 63.26% | 18.79 | 1.32 | 3.53 vs 1.77 |
| **Heuristic (Tactical)** | 20,000.0 | 61.39% | 18.95 | 1.27 | 3.78 vs 1.73 |
| **Heuristic (Tera)** | 10,000.0 | 48.85% | 19.10 | 0.72 | 4.00 vs 1.68 |
| **Heuristic (Advanced)** | 10,000.0 | 49.33% | 22.28 | 0.47 | 4.98 vs 5.18 |
| **Heuristic (Prediction)** | 10,000.0 | 57.71% | 20.28 | 0.88 | 3.77 vs 2.50 |
| **Minimax Search** | 20,000.0 | 67.20% | 19.73 | 1.13 | 3.45 vs 1.85 |
| **MCTS Search** | 11,000.0 | 64.45% | 19.94 | 0.96 | 3.59 vs 2.02 |
| **Imitation Learning** | 12,000.0 | 62.76% | 19.61 | 0.84 | 3.63 vs 2.19 |
| **Pure Imitation** | 10,000.0 | 78.31% | 20.14 | 2.06 | 3.40 vs 3.74 |

---

## 3. Matchup Summary Table (with 95% Confidence Intervals)
| Opponent | Paradigm | Games | Win Rate (%) | 95% CI (±%) | Avg Turns | Avg HP Us | Avg HP Opp | Sample Warning |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `random` | Baseline | 10,000 | 98.18% | ±0.26% | 22.33 | 4.42 | 0.02 | ✅ N=10k |
| `max_power` | Baseline | 10,000 | 91.11% | ±0.56% | 17.78 | 3.32 | 0.09 | ✅ N=10k |
| `v22` | Pure Imitation | 10,000 | 78.31% | ±0.81% | 20.14 | 2.48 | 0.42 | ✅ N=10k |
| `v3` | Heuristic (Basic) | 10,000 | 73.16% | ±0.87% | 17.90 | 2.12 | 0.27 | ✅ N=10k |
| `v2` | Heuristic (Basic) | 10,000 | 73.14% | ±0.87% | 18.00 | 2.11 | 0.27 | ✅ N=10k |
| `v6` | Heuristic (Basic) | 10,000 | 73.04% | ±0.87% | 17.90 | 2.12 | 0.27 | ✅ N=10k |
| `v1` | Heuristic (Basic) | 10,000 | 72.98% | ±0.87% | 18.15 | 2.15 | 0.27 | ✅ N=10k |
| `v4` | Heuristic (Basic) | 10,000 | 72.87% | ±0.87% | 17.93 | 2.11 | 0.28 | ✅ N=10k |
| `one_step` | Baseline | 10,000 | 72.87% | ±0.87% | 17.99 | 2.13 | 0.27 | ✅ N=10k |
| `safe_one_step` | Baseline | 10,000 | 72.55% | ±0.87% | 17.93 | 2.12 | 0.28 | ✅ N=10k |
| `v5` | Heuristic (Basic) | 10,000 | 72.23% | ±0.88% | 17.93 | 2.10 | 0.28 | ✅ N=10k |
| `v18` | MCTS Search | 1,000 | 67.70% | ±2.90% | 19.30 | 1.90 | 0.71 | ⚠️ N=1k (high variance) |
| `v15` | Minimax Search | 10,000 | 67.59% | ±0.92% | 19.52 | 1.88 | 0.71 | ✅ N=10k |
| `v19` | Imitation Learning | 1,000 | 67.10% | ±2.91% | 19.54 | 1.86 | 0.70 | ⚠️ N=1k (high variance) |
| `v16` | Minimax Search | 10,000 | 66.81% | ±0.92% | 19.94 | 1.80 | 0.71 | ✅ N=10k |
| `v7` | Heuristic (Strategic) | 10,000 | 66.49% | ±0.93% | 18.80 | 1.84 | 0.40 | ✅ N=10k |
| `v10` | Heuristic (Tactical) | 10,000 | 66.06% | ±0.93% | 18.86 | 1.80 | 0.40 | ✅ N=10k |
| `v8` | Heuristic (Strategic) | 10,000 | 65.42% | ±0.93% | 18.82 | 1.76 | 0.41 | ✅ N=10k |
| `v17` | MCTS Search | 10,000 | 64.12% | ±0.94% | 20.01 | 1.71 | 0.78 | ✅ N=10k |
| `v21` | Imitation Learning | 10,000 | 62.46% | ±0.95% | 19.58 | 1.60 | 0.79 | ✅ N=10k |
| `v20` | Imitation Learning | 1,000 | 61.40% | ±3.02% | 20.00 | 1.63 | 0.85 | ⚠️ N=1k (high variance) |
| `v9` | Heuristic (Strategic) | 10,000 | 57.87% | ±0.97% | 18.74 | 1.68 | 0.51 | ✅ N=10k |
| `v14` | Heuristic (Prediction) | 10,000 | 57.71% | ±0.97% | 20.28 | 1.48 | 0.60 | ✅ N=10k |
| `v11` | Heuristic (Tactical) | 10,000 | 56.73% | ±0.97% | 19.04 | 1.65 | 0.51 | ✅ N=10k |
| `simple_heuristic` | Baseline | 10,000 | 56.10% | ±0.97% | 19.12 | 1.66 | 0.52 | ✅ N=10k |
| `abyssal` | Baseline | 10,000 | 55.34% | ±0.97% | 19.13 | 1.62 | 0.53 | ✅ N=10k |
| `v13` | Heuristic (Advanced) | 10,000 | 49.33% | ±0.98% | 22.28 | 1.43 | 0.96 | ✅ N=10k |
| `v12` | Heuristic (Tera) | 10,000 | 48.85% | ±0.98% | 19.10 | 1.34 | 0.62 | ✅ N=10k |

---

## 4. Key Analytical Insights
1. **Search Horizon Impact**: Performance against Minimax (v15-v16) and MCTS (v17-v18) reveals how static rule evaluation holds up against tree search lookahead.
2. **Imitation Learning Counterplay**: Evaluation against XGBoost hybrid (v21) and Pure IL (v22) highlights strengths and vulnerabilities against data-driven policy models.
3. **Statistical Integrity**: All win rates are reported with 95% confidence bounds. Matchups with 1,000 games are flagged for elevated variance.
