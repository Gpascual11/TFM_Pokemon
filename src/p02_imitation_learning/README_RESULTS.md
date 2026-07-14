# Imitation Learning Paradigm — Evaluation & Results

This document summarizes the evaluation of the Imitation Learning agents trained on `gen9randombattle` expert replays (Elo 1800+).

## 1. Experimental Setup

* **Dataset:** 1,116,343 expert turns extracted from Gen 9 Random Battle matches.
* **Models:**
  * **`ml_baseline`:** XGBoost model predicting action type (Move vs. Switch) based on basic features. Picks specific actions randomly.
  * **`ml_advanced`:** XGBoost model predicting action type using 1,150 features. Executes specific actions using the championship-level heuristic (`v14`).
* **Evaluation Metric:** Head-to-head win rate (WR%) over 1,000 games per matchup.

---

## 2. Matchup Win Rates (1,000 Games)

| Agent (Imitation) | Opponent (Heuristic/Baseline) | Win Rate (WR%) | Games Played | Speed (Sec/Game) |
|---|---|---|---|---|
| **`ml_baseline`** | `v1` (Random Moves) | 16.6% | 1,000 / 1,000 | 0.03 |
| **`ml_baseline`** | `abyssal` | 9.7% | 1,000 / 1,000 | 0.02 |
| **`ml_baseline`** | `v8` | 10.4% | 1,000 / 1,000 | 0.02 |
| **`ml_baseline`** | `v12` | 8.3% | 1,000 / 1,000 | 0.02 |
| **`ml_baseline`** | `v14` (Championship Heuristic) | 7.6% | 1,000 / 1,000 | 0.02 |
| **`ml_advanced`** | `v1` (Random Moves) | **66.6%** | 1,000 / 1,000 | 0.04 |
| **`ml_advanced`** | `abyssal` | **44.5%** | 1,000 / 1,000 | 0.04 |
| **`ml_advanced`** | `v8` | **53.6%** | 1,000 / 1,000 | 0.04 |
| **`ml_advanced`** | `v12` | **38.9%** | 1,000 / 1,000 | 0.04 |
| **`ml_advanced`** | `v14` (Championship Heuristic) | **43.7%** | 1,000 / 1,000 | 0.05 |

---

## 3. Thesis Key Insights & Discussion

1. **Action Categorization vs. Action Selection:**
   * The extremely low performance of `ml_baseline` (~8% - 16% win rate) proves that predicting *when* to switch or attack is insufficient if the actual attacks/switches chosen are random.
2. **Success of the Hybrid Agent (`ml_advanced`):**
   * By combining the human action-type policy (stay vs. switch predicted by XGBoost) with high-level heuristic execution (`v14`), `ml_advanced` becomes highly competitive.
   * It achieves a **43.7% win rate against the championship heuristic `v14`** and **53.6% against `v8`**. This suggests that the XGBoost imitation policy makes highly rational, human-like decisions regarding active matchups and switching boundaries.

### 3.1 Methodological Justification: Why a Hybrid Model is Academically Sound
A potential critique during a thesis defense is that a "pure" imitation learning agent should predict specific moves and switches directly, rather than using a heuristic delegate. However, in the context of competitive Pokémon Showdown, a hybrid approach is the mathematically and practically correct design:
* **The Action Semantics Problem**: A pure model predicting action slots (0-9) is theoretically flawed because slot indices have no universal meaning (e.g., action 0 is "Stealth Rock" on one Pokémon, but "Hydro Pump" on another). Without a complex transformer/attention mechanism matching options to state vectors, slot classification is noise.
* **Exposure Bias and Compounding Errors**: In behavioral cloning, if an agent makes a single suboptimal decision, it moves into a state-space region not covered by the training dataset. This leads to rapid strategic degradation. Using the `v14` expert engine to guide the execution of the selected action type keeps the agent in a highly structured, valid state trajectory.
* **Hierarchical Policy Design**: This hybrid structure is formally defined as a hierarchical policy: a high-level policy (XGBoost) makes the macro decision (Stay vs. Switch transition boundary), and a low-level policy (`v14`) handles micro-tactical execution. This is a robust and widely used design in AI literature.

---

## 4. Technical Hyperparameters & Model Architecture

### A. Data Preprocessing & Features
* **Total Samples:** 1,116,343 turns (GroupShuffleSplit with 80% train, 20% test, grouped by `battle_id` to prevent intra-battle data leakage).
* **Feature Dimensions:** 1,150 features.
* **Key Features Include:**
  * **Continuous States:** Turn number, Player 1 HP fraction, Player 2 HP fraction.
  * **Flags:** Stealth Rock active on side (P1/P2), Terastallization used (P1/P2).
  * **Categorical:** One-hot encoded species identity for both the active and opponent active Pokémon (mapping various paradox and regional formats to match the Hugging Face schema).

### B. Class Imbalance Handling
* **Move Turns (Class 0):** 663,764 samples
* **Switch Turns (Class 1):** 230,320 samples
* **Imbalance Ratio:** `scale_pos_weight` = **2.882** (calculated as `n_move / n_switch` to adjust gradient weights for the minority Switch class).

### C. XGBoost Hyperparameters
The model was trained with the following configuration:
* `n_estimators = 200`
* `max_depth = 6`
* `learning_rate = 0.1`
* `scale_pos_weight = 2.882`
* `eval_metric = "logloss"`
* `n_jobs = -1` (utilizes all CPU cores)

### D. MLAdvancedAgent Decision Flow
To prevent common imitation learning pitfalls, `MLAdvancedAgent` wraps the classifier with heuristic guards:
1. **Guaranteed KO Guard:** Before querying the XGBoost model, the agent computes exact damage ranges. If there is a guaranteed move to knock out the opponent's active Pokémon (considering speed ordering), it executes the KO immediately.
2. **Action Classification:** If no KO is present, it queries XGBoost. If the probability of switching exceeds **0.65** (tuned to prevent reckless staying), the agent decides to Switch; otherwise, it Attacks.
3. **Infinite Switch Loop Guard:** If the model selects a Switch action, but the agent switched on the *previous* turn, the choice is overridden to Attack to prevent infinite back-and-forth switching.
4. **Execution Delegation:** If a Switch is selected, it uses `v14`'s switch scoring to pick the best teammate. If an Attack is selected, it uses `v14`'s move scoring to choose the best move.
