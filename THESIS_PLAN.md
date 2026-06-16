# TFM Pokémon — Thesis Plan & Master Reference

> **Last updated:** June 10, 2026  
> **Format focus:** `gen9randombattle` exclusively  
> **Research question:** *Which AI paradigm gets closest to human-level play in a complex partially-observable stochastic game, using gen9randombattle as the benchmark domain?*

---

## 1. What This Thesis Is (and Is Not)

### What it is
A **paradigm comparison study**: you use Pokémon gen9randombattle as a rich, complex domain to compare five AI decision-making approaches. The contribution is the comparison itself — discovering which paradigm scales best to partially-observable stochastic games.

### What it is NOT
- "Build the best Pokémon bot in the world"
- A claim that your bot beats all humans
- An engineering project to optimize speed

### The performance ladder (conceptual)
```
🎯 Target: Real human players (Showdown ladder)
─────────────────────────────────────────────────
MCTS (Information Set)   ← Phase 4 (to build)
PPO (Reinforcement RL)   ← Phase 3 (to fix + scale)
XGBoost (Imitation IL)   ← Phase 1 (fix data, rerun)
v15 Minimax (Search)     ← Phase 2 (to build)
v14 (best heuristic)     ← DONE ✅ (40.8% vs humans)
...
v1 (Random)              ← DONE ✅
─────────────────────────────────────────────────
```

**The thesis finding IS the ranking.** Even "IL and PPO score below v14" is a publishable result — it says something fundamental about partial observability and sparse rewards.

---

## 2. Current State of the Project

### 2.1 What is DONE ✅

| Component | Status | Location |
|---|---|---|
| Heuristics v1–v14 | Complete | `src/p01_heuristics/agents/internal/` |
| Bot-vs-bot benchmark (v1–v12) | Complete | `data/benchmarks/all_10k/gen9randombattle/` (326 files) |
| Pokechamp baselines (abyssal, max_power, one_step) | Benchmarked | Same folder |
| Online bot v14 | Running, 98 games | `data/testing/logs_v14/battle_history.csv` |
| PPO models (Feb 2026) | Trained but weak | `data/models/models_22_02_26/` |
| v7 minimax (old) | Exists, weak | `src/p03_minmax/agents/internal/v7_minimax.py` |
| IL pipeline structure | Exists, wrong data | `src/p02_imitation_learning/` |
| 8-server parallel infra | Working | `src/p00_core/scripts/` |
| Doubles heuristics v1–v5 | Removed (out of scope) | (Deleted) |

### 2.2 What is BROKEN / NEEDS FIXING ⚠️

| Issue | Root Cause | Fix |
|---|---|---|
| **IL gives 2% winrate** | Trained on gen9ou replays, tested on gen9randombattle | Retrain on gen9randombattle replays |
| **PPO fails phase 1** (can't beat RandomPlayer) | Almost certainly a bug (sparse reward, bad mask, or missing state info) | Debug before scaling |
| **v13/v14 not in benchmark matrix** | Never ran the full benchmark after v12 | Run `benchmark.py` for v13/v14 |
| **No MCTS agent** | Not built yet | Phase 4 |
| **No v15 minimax** | Not built yet | Phase 2 |

### 2.3 Online bot v14 results (as of June 10, 2026)
- **98 games played** on Showdown ladder (`gen9randombattle`)  
- **40 wins / 58 losses** → **40.8% win rate**  
- **Elo progression:** Started ~1085, ended ~1151  
- **Interpretation:** Below the average ladder player (~1200+), but consistently winning ~40% against real humans. This is a meaningful baseline — a naive bot wins ~0-5%.

### 2.4 Benchmark matrix coverage

The 326 existing files cover: `v1–v12` × `abyssal`, `max_power`, `one_step`, `safe_one_step`, `simple_heuristic`, `random`, and all cross-matchups.

**Missing from benchmark (must run):**
- `v13` vs all agents
- `v14` vs all agents  
- `v15` (to build) vs all agents
- `MCTS` (to build) vs all agents
- `XGBoost-IL-randombattle` (after fix) vs all agents
- `PPO` (after fix) vs all agents
- `pokechamp-minimax` vs all agents
- `pokellmon-cot` vs all agents (optional, needs API key)

---

## 3. Infrastructure

### 3.1 Compute setup
- **Servers:** 8 local Pokemon Showdown instances (ports 8000+), launched via `src/p00_core/scripts/launch_custom_servers.sh`
- **Concurrency:** 25 games per server × 8 servers = **200 concurrent battles**
- **Throughput:** ~2.5 million games in 50 hours ≈ **50,000 games/hour**
- **For benchmarks:** 10k games takes ~12 minutes with this setup
- **GPU:** RTX 2080 — used for PPO training, NOT needed for heuristics/minimax/MCTS

### 3.2 Python environment
```bash
# Always run with:
uv run python <script>

# Python version: 3.12
# Virtual env managed by uv
# Key packages: poke-env 0.11.0, stable-baselines3, xgboost, torch
```

### 3.3 Pokechamp integration
- `pokechamp/` directory is the pokechamp repository (cloned locally)
- It has its OWN `poke_env/` fork (older, adds `local_simulation.py`)
- Some scripts inject `pokechamp/` into sys.path to get `LocalSim`:
  ```python
  sys.path.insert(0, str(_POKECHAMP))  # gets LocalSim from pokechamp fork
  ```
- **When this injection is active:** Python uses pokechamp's poke_env fork  
- **When NOT active:** Uses standard poke-env 0.11.0 from PyPI  
- **This does NOT affect game outcomes** — the Showdown server controls all mechanics

### 3.4 poke-env version situation — DO NOT CHANGE
| Version | Where | What it adds |
|---|---|---|
| **0.11.0 (PyPI)** | `.venv/` — main install | Standard API, `battle/`, `calc/` dirs |
| **pokechamp fork (~0.9)** | `pokechamp/poke_env/` | Adds `local_simulation.py` + `team_util.py` |
| **0.15 (latest)** | NOT installed | Breaking API changes, don't upgrade mid-thesis |

**Do not upgrade to 0.15.** Your 2.5M games ran on 0.11.0. The core API (`Battle`, `Move`, `Pokemon`, `GenData`) is identical in both active versions for the objects your agents use.

---

## 4. Phase-by-Phase Roadmap

---

### Phase 1 — Fix Imitation Learning (~1 week)
**Path:** `src/p02_imitation_learning/`

#### What it is
XGBoost classifier trained to imitate human move choices. Given the current battle state as features, predict which move a 1800+ Elo player would pick.

#### Why it failed
The existing model was trained on **gen9ou** expert replays and tested on **gen9randombattle**. These formats have different Pokémon pools, item sets, damage ranges, and meta strategies. The 2% winrate is not a failure of imitation learning — it's a data mismatch. This is fixed by changing one argument.

#### Exact fix
```bash
# Step 1: Download gen9randombattle replays (NOT gen9ou)
uv run python src/p02_imitation_learning/s01_download/download_dataset.py \
    --gamemode gen9randombattle \
    --min-elo 1800 \
    --start 2025-01 \
    --end 2026-04

# Step 2: Extract features from new replays
uv run python src/p02_imitation_learning/s03_training/extract_ml_features.py \
    --format gen9randombattle

# Step 3: Train XGBoost
uv run python src/p02_imitation_learning/s03_training/train_ml_baseline.py \
    --format gen9randombattle

# Step 4: Benchmark the trained model
# Integrate MLBaselineAgent into the existing benchmark runner
```

#### Key implementation files
- `src/p02_imitation_learning/s01_download/download_dataset.py` — change `--gamemode` arg
- `src/p02_imitation_learning/s03_training/extract_ml_features.py` — feature extraction
- `src/p02_imitation_learning/s04_agent/ml_baseline.py` — the agent wrapper
- `src/p02_imitation_learning/s04_agent/ml_advanced.py` — advanced features version

#### What to expect
- Target win rate: 40–55% vs v12/v13 after fixing the data
- Randombattle IL has a lower ceiling than OU IL — even 1800+ Elo players improvise because they don't know their own team at preview. The "ground truth label" is noisier.
- If win rate stays near random even after fix → feature vector is missing critical info. Check it includes: HP fractions for both sides, type matchup score for the active matchup, remaining Pokémon count, active status conditions, speed comparison.

#### Academic framing
"Can imitation learning from human experts, without any game knowledge encoded manually, compete with hand-crafted expert heuristics in a hidden-information stochastic game?"

---

### Phase 2 — Build v15 Minimax (~2 weeks)
**Path:** `src/p03_minmax/agents/internal/v15_minimax.py`

#### What it is
A 1-ply adversarial game tree search. For each possible move, estimate: "If I pick this move and the opponent plays optimally, what is the worst-case outcome?" Pick the move with the best worst-case (maximin).

#### Why not just use pokechamp's minimax?
The pokechamp `pokechamp` bot uses a minimax with LocalSim but with a weak evaluator (simple damage subtraction). v14 has a far superior evaluator with exact damage rolls, speed ordering, status effects, setup detection, etc. v15 wraps v14's evaluator in a proper game tree.

#### Why not improve v7_minimax?
`src/p03_minmax/agents/internal/v7_minimax.py` exists but uses a primitive evaluator. Build v15 fresh, inheriting from v14, rather than extending v7.

#### Core architecture
```python
# src/p03_minmax/agents/internal/v15_minimax.py

class MinimaxV15(HeuristicV14):
    """
    1-ply minimax using v14's evaluator + Showdown DB for opponent move prediction.
    Extends HeuristicV14 to reuse _score_move, _calculate_exact_damage_range,
    _load_pokemon_sets, _estimate_matchup_score, etc.
    """
    
    def _select_action(self, battle):
        best_move = None
        best_minimax_score = float('-inf')
        
        for my_action in self._get_all_actions(battle):
            # Predict what moves the opponent might use (Showdown DB for unknown)
            opp_actions = self._predict_opponent_actions(battle)
            
            worst_case = float('+inf')
            for opp_action in opp_actions:
                # Evaluate this (my_action, opp_action) pair using v14's evaluator
                score = self._evaluate_action_pair(battle, my_action, opp_action)
                worst_case = min(worst_case, score)  # opponent minimizes
            
            if worst_case > best_minimax_score:
                best_minimax_score = worst_case
                best_move = my_action
        
        return best_move
```

#### Key improvements over v7 minimax

1. **v14 evaluator** — not just `my_damage - opp_damage`. Uses STAB, speed ordering, status bonuses, ability immunities, terastallization value.

2. **Showdown DB for unknown opponent moves** — call `self._load_pokemon_sets(gen)` to get probable movesets for Pokémon whose moves haven't been revealed yet. Don't assume the opponent only has the moves you've seen.

3. **Speed-aware damage resolution** — if opponent is faster, they move first. The exchange is sequential (they deal damage to your HP, then you deal damage to their reduced HP). This matters for KO decisions.

4. **Switch as a minimax option** — include `battle.available_switches` in `my_action`. Evaluate opponent's best switch-in by matchup score, not a flat penalty.

5. **Speed-ordered resolution example:**
   ```python
   def _evaluate_action_pair(self, battle, my_action, opp_action):
       me, opp = battle.active_pokemon, battle.opponent_active_pokemon
       if my_speed > opp_speed:
           # I move first: evaluate after I hit them, then they hit me
           score = my_damage_to_opp - opp_damage_to_me_after_hp_reduction
       else:
           # They move first: evaluate after they hit me, then I hit them
           score = my_damage_to_opp_after_hp_reduction - opp_damage_to_me
   ```

#### Benchmark target
Run v15 vs all v1–v14 + pokechamp minimax (external reference).  
Expected: v15 should beat v14 (~55%+) and match or beat pokechamp's minimax.

#### Academic framing
"Does explicit adversarial game tree search improve over pure heuristic play? How does it compare against a published minimax implementation (pokechamp)?"

---

### Phase 3 — Fix and Scale PPO (~2–3 weeks)
**Path:** `src/p05_ppo_drl/`

#### What it is
Reinforcement Learning. The agent plays millions of games and learns from win/loss signals without any human knowledge — it discovers strategy from scratch.

#### Current state
- 4 trained checkpoints exist: `ppo_pokemon_baseline.zip`, `ppo_pokemon_phase1_5.zip`, `ppo_pokemon_phase2.zip`, `ppo_pokemon_phase3.zip` (from Feb 2026)
- These were reportedly underperforming — couldn't reliably beat RandomPlayer in phase 1

#### Critical: debug before scaling
Running more training on a broken agent wastes weeks. Run this diagnostic FIRST:

```bash
# Phase 1 diagnostic: 500k steps vs RandomPlayer, log win rate every 50k
uv run python src/p05_ppo_drl/s02_training/train_p1_base.py \
    --timesteps 500000 \
    --eval-interval 50000 \
    --log-winrate
```

Plot win rate curve. Diagnosis:
- **Flat at ~50%** → There's a bug. Find it before running more.
- **Rising slowly** → Just needs more steps. Your 200-env setup will fix this.
- **Oscillating** → Learning rate too high or environment reset bug.

#### Most likely bugs (check in order)

**A. Sparse reward (most common)**
```python
# BAD (current): Only reward at game end
reward = +1.0 if won else -1.0

# GOOD: Shape the reward
def compute_reward(self, battle, prev_battle):
    hp_dealt = prev_opp_hp_fraction - battle.opponent_active_pokemon.current_hp_fraction
    hp_lost = prev_my_hp_fraction - battle.active_pokemon.current_hp_fraction
    fainted_bonus = 0.3 * (opp_fainted - prev_opp_fainted)
    win_bonus = 1.0 if battle.won else (-1.0 if battle.lost else 0.0)
    return 0.01 * hp_dealt - 0.005 * hp_lost + fainted_bonus + win_bonus
```
File to check: `src/p05_ppo_drl/s01_env/pokemon_env.py`

**B. State vector missing critical info**
The vectorizer must include at minimum:
- My active Pokémon: HP fraction, current status, boosts, types
- Opponent active Pokémon: HP fraction, known status, known types
- My team: remaining count, HP fractions of alive Pokémon
- Opponent team: estimated remaining count
- Type matchup: effectiveness of my best move vs opponent
- Speed comparison: am I faster?

File to check: `src/p05_ppo_drl/s01_env/vectorizer.py`

**C. Action masking bug**
If illegal actions (switches to fainted Pokémon, moves with 0 PP) aren't masked to `-inf` before softmax, the agent wastes learning cycles on impossible actions.

**D. Server disconnects mid-episode**
If the Showdown server drops, the episode truncates abnormally. Check for unusual episode length distributions in logs.

#### Curriculum after phase 1 is fixed
```
Phase 1: vs RandomPlayer         → target 90%+ WR, then graduate
Phase 2: vs v8 (simple heuristic) → target 70%+ WR, then graduate
Phase 3: vs v12 (strong heuristic) → target 55%+ WR, then graduate
Phase 4: self-play                → let Elo converge
```

#### Training with your parallel infrastructure
Your 200 concurrent environments dramatically reduce wall-clock time:
```python
# In train_p1_base.py, confirm parallel envs are set correctly:
n_envs = 200  # 8 servers × 25 concurrent each
```

#### Academic framing
"Can reinforcement learning, without any domain knowledge, discover competitive battle strategies in a high-dimensional partially-observable game? What are the practical limits of sparse-reward RL in this domain?"

---

### Phase 4 — Build MCTS (~2–3 weeks)
**Path:** `src/p03_minmax/s02_mcts/agents/internal/v16_mcts.py`

#### What it is
Monte Carlo Tree Search with Information Set sampling. Instead of exhaustive search (minimax), it uses stochastic simulations to estimate the value of moves. It's the algorithm core to AlphaGo/AlphaZero.

#### Why it's better suited to Pokémon than minimax

Pokémon is **partially observable** — you don't know the opponent's full team or their unrevealed moves. Minimax pretends you know everything (it evaluates against "all opponent moves" but only the revealed ones). MCTS naturally handles this:

```
Information Set MCTS:
  For each simulation:
    1. Sample a plausible opponent team from Showdown DB
       (based on revealed Pokémon, probable sets for unrevealed ones)
    2. Run a rollout using that sampled state
    3. Aggregate results across simulations
  
  Result: probability distribution over moves, naturally accounting
  for opponent uncertainty. This is the correct algorithm for Pokémon.
```

This is the **key academic contribution** of MCTS in your thesis: explicitly handling hidden information through Information Set sampling, vs. minimax's deterministic assumptions.

#### The critical shortcut: LocalSim already exists

`pokechamp/poke_env/player/local_simulation.py` is a **1,759-line local battle simulator** with `LocalSim.step(action1, action2)`. This is exactly what MCTS needs for rollouts — you DON'T need to build a simulator.

```python
# Import from pokechamp's fork (requires sys.path injection):
from poke_env.player.local_simulation import LocalSim
```

**Why LocalSim matters:** MCTS needs to simulate many game positions from the current state WITHOUT using the Showdown server (too slow for 200 rollouts per turn). LocalSim runs in Python, in-process, instantly.

#### Core MCTS implementation
```python
# src/p03_minmax/s02_mcts/agents/internal/v16_mcts.py

import math
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class MCTSNode:
    action: object = None
    parent: 'MCTSNode' = None
    children: list = field(default_factory=list)
    visits: int = 0
    value: float = 0.0
    
    def ucb_score(self, exploration_c=1.4):
        if self.visits == 0:
            return float('inf')
        exploitation = self.value / self.visits
        exploration = exploration_c * math.sqrt(math.log(self.parent.visits) / self.visits)
        return exploitation + exploration


class MCTSV16(HeuristicV14):
    """
    Information Set MCTS using LocalSim for rollouts.
    Inherits v14's Showdown DB loading and evaluator for rollout policy.
    """
    N_SIMULATIONS = 200  # per turn
    ROLLOUT_DEPTH = 5    # turns ahead per rollout
    EXPLORATION_C = 1.4  # UCT constant
    
    def _select_action(self, battle):
        root = MCTSNode()
        actions = self._get_all_actions(battle)
        
        # Initialize child nodes for each possible action
        for action in actions:
            root.children.append(MCTSNode(action=action, parent=root))
        
        for _ in range(self.N_SIMULATIONS):
            # 1. Selection: pick child with best UCB score
            node = max(root.children, key=lambda n: n.ucb_score(self.EXPLORATION_C))
            
            # 2. Sample opponent team from Showdown DB (Information Set)
            gen = self._get_gen(battle)
            sets_db = self._load_pokemon_sets(gen)
            opp_team = self._sample_opponent_state(battle, sets_db)
            
            # 3. Rollout: simulate ROLLOUT_DEPTH turns using v14 policy
            result = self._rollout(battle, node.action, opp_team)
            
            # 4. Backpropagate
            node.visits += 1
            node.value += result
            root.visits += 1
        
        # Return action with most visits (robust child)
        return max(root.children, key=lambda n: n.visits).action
    
    def _rollout(self, battle, initial_action, opp_team):
        """Simulate ROLLOUT_DEPTH turns using LocalSim + v14 heuristic as policy."""
        sim = LocalSim(battle, opp_team)
        sim.step(initial_action, self._predict_opp_best_response(battle, initial_action))
        
        for _ in range(self.ROLLOUT_DEPTH - 1):
            if sim.is_done:
                break
            my_action = self._select_action_heuristic(sim.battle)  # v14 policy
            opp_action = self._predict_opp_best_response(sim.battle, my_action)
            sim.step(my_action, opp_action)
        
        return sim.get_hp_diff()  # normalized value: positive = winning
    
    def _sample_opponent_state(self, battle, sets_db):
        """Sample probable opponent moves for unrevealed Pokémon from Showdown DB."""
        opp_team = {}
        for mon in battle.opponent_team.values():
            if len(mon.moves) < 4:  # moves not fully revealed
                probable_moves = sets_db.get(mon.species, {}).get('moves', [])
                opp_team[mon.species] = {
                    'known_moves': list(mon.moves.keys()),
                    'probable_moves': probable_moves
                }
        return opp_team
```

#### Why MCTS is feasible with your setup
- **LocalSim runs in Python** — no server needed for rollouts
- **200 simulations per turn at 10 seconds** = very achievable with CPU parallelism
- **Your parallel benchmark infrastructure** remains intact for evaluation (LocalSim is only used DURING a turn's decision, not between games)

#### The MCTS thesis contribution  
*"Standard minimax assumes full knowledge of opponent state; we implement Information Set MCTS that samples probable opponent configurations from the Pokémon Showdown sets database, making the search probabilistically correct under hidden information — a natural fit for Pokémon's imperfect-information structure."*

#### Benchmark target
Run v16 MCTS vs v15 minimax, v14, and pokechamp's minimax.  
Expected: MCTS should beat v15 minimax because it handles hidden info better, especially in early turns when the opponent team is largely unknown.

---

### Phase 5 — External Pokechamp Benchmarks (~1 week)
**Path:** Extend `src/p00_core/engine/benchmark.py`

#### What it is
Running the published pokechamp agents against your implementations as external reference points.

#### Available pokechamp bots (already installed)
| Agent | What it is | Thesis use |
|---|---|---|
| `abyssal` | Pokechamp's rule-based baseline | **Already benchmarked** ✅ |
| `max_power` | Always picks highest base power | **Already benchmarked** ✅ |
| `one_step` | 1-step lookahead | **Already benchmarked** ✅ |
| `pokechamp` | Minimax with LocalSim (weak evaluator) | **Must add** — compare to your v15 |
| `pokellmon` (cot) | LLM with chain-of-thought prompting | **Must add** — LLM paradigm benchmark |
| `pokellmon` (minimax) | LLM guides the minimax tree | Optional — hybrid paradigm |

#### Why this matters academically
You're not just comparing your own agents against each other — you're placing your implementations in the context of **published literature**. "Our MCTS beats pokechamp's minimax by X%" is externally validated.

#### Notes on pokellmon
- Requires an API key (GPT/Claude/Ollama)
- Run locally against your agents (not online) — much faster and reproducible
- Use `ollama` locally if you don't want cloud API costs (Mistral/Llama)
- 1000 games is sufficient for pokellmon benchmarking (LLM call latency limits throughput)

---

### Phase 6 — Complete v13/v14 Benchmark Matrix (~2 days)

The existing benchmark matrix only covers v1–v12. You need v13 and v14 in the matrix before the final comparison.

```bash
# Add v13 and v14 to the benchmark matrix
uv run python src/p00_core/engine/benchmark.py \
    --agents v13,v14 \
    --opponents all \
    --format gen9randombattle \
    --games 10000 \
    --servers 8
```

---

### Phase 7 — Final Unified Benchmark (~1 week)

#### The comparison table you're building

```
All agents, head-to-head, 10k games each (gen9randombattle):

Agents in the matrix:
  Rule-based:        v1, v4, v8, v12, v13, v14  (representative subset)
  Search:            v15 (minimax), v16 (MCTS), pokechamp (external)
  Imitation:         XGBoost-IL (gen9randombattle trained)
  RL:                PPO (after fix)
  LLM:               pokellmon-cot (external)
  Baselines:         random, max_power, abyssal (already done)
```

With your setup, this runs in a few hours.

---

### Phase 8 — Human Validation (ongoing)

**The v14 online bot is ALREADY running.** Let it continue.

When MCTS (v16) is built, run 100 online games with it too. Compare:
- v14 online: 40.8% WR, Elo ~1151 (current)
- v16 MCTS online: target 50%+

**Don't run all agents online** — only your top 1–2. Bot-vs-bot is your rigorous benchmark; online is ecological validation.

---

## 5. Key Technical Decisions (and Why)

### 5.1 Format: gen9randombattle ONLY

**Decision:** All experiments in gen9randombattle exclusively.  
**Why:**
- Your benchmark framework, Showdown sets DB, and all v1-v14 heuristics are calibrated for randombattle
- gen9ou would require team-building logic your agents don't have
- VGC (doubles) needs a completely separate action space, IL pipeline, and RL environment
- One format = clean, rigorous, apples-to-apples comparison

**What NOT to add:**
- ❌ gen9ou with fixed teams (heuristics calibrated wrong, comparisons unclear)
- ❌ VGC (doubles) — 2+ months of infrastructure for marginal thesis value
- ❌ Different generation benchmarks (nice-to-have, not thesis-critical)

### 5.2 Online games: validation only, not primary benchmark

**Decision:** Use bot-vs-bot (10k games) as primary; online as validation.  
**Why:**
- 100 online games per agent × 6 agents = 50-100 hours of calendar time waiting for matchmaking
- Online is noisy (varies by opponent skill, not reproducible)
- Bot-vs-bot is fast (12 min), reproducible, and statistically rigorous

**What to do:** Keep v14 running. Run MCTS online when built. Only these two agents need online validation.

### 5.3 MCTS: Information Set, not full game MCTS

**Decision:** Sample from Showdown DB, shallow rollouts (5 turns), no full game simulation.  
**Why:**
- Full game MCTS would need to simulate 20–30 turns per rollout × 200 simulations = too slow even with LocalSim
- 5-turn rollouts with v14 heuristic evaluation capture the critical early-game decisions
- Information Set sampling (sampling opponent state from Showdown DB) is the academically correct approach for hidden-information games

### 5.4 PPO: debug first, scale after

**Decision:** Don't run more training until phase 1 bug is identified.  
**Why:**
- A broken agent trained for 10M more steps is still broken
- The 200-parallel-env setup means once the bug is fixed, training is very fast
- The models from Feb 2026 exist as baseline comparisons even if they're weak

### 5.5 LocalSim: from pokechamp fork, not standard poke-env

**Decision:** Use `pokechamp/poke_env/player/local_simulation.py` for MCTS rollouts.  
**Why:**
- Standard poke-env 0.11.0 does NOT have LocalSim (`ModuleNotFoundError`)
- Pokechamp's fork adds LocalSim as its main contribution to poke-env
- For MCTS scripts, inject pokechamp's path: `sys.path.insert(0, "pokechamp/")`
- For heuristic scripts (v1-v14), no injection needed — they don't use LocalSim

---

## 6. Marc Acadèmic i Explicació dels Paradigmes (Academic Framing)

En aquesta tesi comparem sis paradigmes diferents de presa de decisions en Intel·ligència Artificial aplicats a Pokémon Showdown (`gen9randombattle`). A continuació es detallen des d'una perspectiva acadèmica i tècnica en català:

### 1. Heurístiques basades en regles (Heuristics v1–v14)
* **Què és:** Sistemes experts programats a mà que codifiquen el coneixement del joc directament en regles de decisió lògiques (estructures `if-then-else`).
* **Com funciona:** Avalua l'estat actual del combat calculant danys exactes, taules de tipus, velocitats, efectes d'estat i utilitat de canvis basant-se en regles fixes decidides per un expert humà.
* **Paper a la tesi:** Representa el sostre de rendiment de la programació explícita (coneixement de domini pur). Serveix com a línia base forta i com a avaluador per a altres algorismes de cerca.

### 2. Cerca Adversarial (Minimax v15) — *Cerca basada en Heurística*
* **Què és:** Un algorisme de cerca en arbre de joc que assumeix que l'oponent jugarà de manera racional per minimitzar els nostres guanys (principi maximin).
* **Com funciona (Dependència d'Heurístiques):** Com que l'arbre del Pokémon és gegant i probabilístic, no es pot cercar fins al final de la partida. Per tant, Minimax fa una cerca de profunditat limitada (1-ply o 2-ply) i **utilitza la nostra millor heurística (v14) com a funció d'avaluació en els nodes fulla** per estimar qui està guanyant la partida en aquell punt intermedi.
* **Paper a la tesi:** Comprova si afegir previsió de les respostes de l'oponent millora les decisions en comparació amb només reaccionar heurísticament a l'estat actual.

### 3. Cerca en Arbre Monte Carlo (MCTS v16) — *Cerca basada en Heurística i Mostreig*
* **Què és:** Un algorisme de cerca probabilístic que simula partides futures (rollouts) de manera repetida per trobar el moviment amb millor taxa d'èxit.
* **Com funciona (Dependència d'Heurístiques):** Per ser eficient en un entorn d'informació oculta (on no sabem l'equip de l'oponent), l'MCTS utilitza un *Information Set* (mostreja equips possibles de l'oponent basant-se en la base de dades de Showdown). A més, **depèn d'una política heurística** (la heurística v14) tant per triar els moviments durant les simulacions ràpides com per avaluar l'estat de la partida al final de la simulació de profunditat limitada (per exemple, 5 torns).
* **Paper a la tesi:** És l'algorisme teòricament més correcte per a jocs estocàstics d'informació imperfecta com el Pokémon, ja que gestiona directament la incertesa de l'oponent.

### 4. Aprenentatge per Imitació (Imitation Learning via XGBoost) — *Basat en Dataset Estàtic*
* **Què és:** Un enfocament d'aprenentatge supervisat on un model aprèn a triar moviments imitant el comportament d'experts humans de molt alt nivell.
* **Com funciona:** S'entrena un classificador (com XGBoost) utilitzant un **dataset estàtic de partides ja jugades (Showdown Replays de jugadors amb Elo 1800+)**. El model aprèn a correlacionar el vector de característiques (features) de l'estat del joc amb la decisió que va prendre l'humà, sense cap coneixement previ de les regles del joc.
* **Diferència clau:** Treballa exclusivament de manera "offline" amb un conjunt de dades històric tancat (com faria un aprenentatge supervisat clàssic).

### 5. Aprenentatge per Reforç Profund (PPO / DRL) — *Basat en Interacció Activa*
* **Què és:** Un model d'aprenentatge on l'agent aprèn de manera autònoma a través del mètode d'assaig i error, optimitzant una funció de recompensa (win/loss, dany fet, etc.).
* **Com funciona:** L'agent juga milions de partides contra ell mateix o contra oponents de referència de manera en línia. **A diferència d'Imitation Learning, no utilitza un dataset estàtic de partides preexistents; en comptes d'això, PPO genera les seves pròpies partides mitjançant la interacció contínua amb l'entorn** (Pokemon Showdown).
* **Paper a la tesi:** Avalua si una intel·ligència artificial pot descobrir estratègies guanyadores i contrarestar estils de joc humans o heurístics sense haver vist mai com juguen els humans, superant les limitacions de biaix que té l'aprenentatge per imitació.

### 6. Agents Basats en LLM (pokellmon)
* **Què és:** L'ús de Models de Llenguatge Grans (com GPT, Claude, o Llama) com a nucli de raonament estratègic.
* **Com funciona:** Es tradueix l'estat del joc i el ventall de moviments disponibles a un format textual (prompt). L'agent utilitza la tècnica de Chain-of-Thought (CoT, cadena de pensament) en llenguatge natural per analitzar el combat ("Estic davant d'un Pokémon de tipus Foc, el meu millor moviment és de tipus Aigua...") abans de triar l'acció definitiva.
* **Paper a la tesi:** Representa el paradigma més recent d'IA general aplicada a tasques de lògica i estratègica complexes d'informació parcial.

---

## 7. Suggested Timeline (3 months)

```
Month 1 — Fix existing + build minimax
  Week 1:   Fix IL data (gen9randombattle), run pipeline, evaluate
  Week 2:   Build v15 minimax, debug + benchmark vs v1-v14
  Week 3:   Run full v13/v14 benchmark matrix (2 days), debug PPO phase 1
  Week 4:   PPO diagnostic + fix, first training run with parallel envs

Month 2 — Build MCTS + scale everything  
  Week 1:   Build v16 MCTS tree (LocalSim is done, ~150 lines UCT)
  Week 2:   MCTS evaluation + tuning (n_simulations, rollout depth, c parameter)
  Week 3:   PPO phase 2-3 training, pokechamp external benchmarks
  Week 4:   pokellmon benchmark (optional), begin writing results chapter

Month 3 — Write
  Week 1:   Final unified benchmark (all paradigms, 10k games each, ~2 hours)
  Week 2:   Results analysis, figures, tables
  Week 3:   Thesis writing (methods + results chapters)
  Week 4:   Polish, conclusions, abstract, defense prep
```

---

## 8. What NOT To Do

| Don't | Why |
|---|---|
| ❌ Upgrade to poke-env 0.15 | Breaking API changes, 2.5M games ran on 0.11.0, no thesis benefit |
| ❌ Add gen9ou experiments | Heuristics not calibrated for OU, comparisons scientifically unclear |
| ❌ Add VGC (doubles) | New action space, new IL pipeline, new RL env = 2 months of infrastructure |
| ❌ Run all agents online vs humans | Too slow (50-100 hours), too noisy; use bot-vs-bot as primary benchmark |
| ❌ Scale PPO before debugging phase 1 | Scaling a broken agent wastes weeks |
| ❌ Implement full game MCTS (20+ turn rollouts) | Too slow even with LocalSim; 5-turn shallow rollouts are sufficient |
| ❌ Build a custom battle simulator | LocalSim already exists in pokechamp — 1,759 lines, use it |
| ❌ Try to beat all humans | That's not the thesis; paradigm comparison is the thesis |

---

## 9. File Reference

### New files to create
```
src/p03_minmax/
  agents/internal/
    v15_minimax.py            ← Phase 2: 1-ply minimax with v14 evaluator
src/p04_mcts/
  agents/internal/
    v16_mcts.py             ← Phase 4: Information Set MCTS with LocalSim
  evaluation/
    benchmark_mcts.py       ← MCTS-specific benchmark runner
```

### Key existing files to understand before each phase
```
Phase 1 (IL fix):
  src/p02_imitation_learning/s01_download/download_dataset.py   ← change --gamemode
  src/p02_imitation_learning/s03_training/extract_ml_features.py
  src/p02_imitation_learning/s04_agent/ml_baseline.py

Phase 2 (v15 minimax):
  src/p03_minmax/agents/internal/v7_minimax.py  ← reference only
  src/p01_heuristics/agents/internal/v14.py     ← inherit from this
  src/p00_core/core/base.py               ← base class

Phase 3 (PPO fix):
  src/p05_ppo_drl/s01_env/pokemon_env.py     ← check reward + masking
  src/p05_ppo_drl/s01_env/vectorizer.py      ← check state vector
  src/p05_ppo_drl/s02_training/train.py      ← main training script

Phase 4 (MCTS):
  pokechamp/poke_env/player/local_simulation.py  ← LocalSim.step() is here
  src/p01_heuristics/agents/internal/v14.py  ← inherit evaluator
```

### Running benchmarks
```bash
# Standard bot-vs-bot benchmark
uv run python src/p00_core/engine/benchmark.py \
    --agents v14,v15 \
    --opponents v1,v8,v12,v13,v14,abyssal \
    --format gen9randombattle \
    --games 10000 \
    --servers 8 \
    --concurrency 25

# Online bot
uv run python src/p00_core/online_bot/run_online_bot.py \
    --agent v14 --mode ladder --username SirPThesis --password ***REDACTED*** \
    --games 100 --concurrency 3
```

---

## 10. The Thesis Contribution Statement

> *"We conduct the first systematic paradigm comparison of AI decision-making approaches in a complex partially-observable stochastic game (gen9randombattle), evaluating five paradigms — rule-based heuristics, adversarial search, Information Set MCTS, imitation learning, and reinforcement learning — under a unified evaluation framework of 10,000 games per matchup. We find that [X], demonstrating that [Y], with implications for AI in imperfect-information multi-agent environments."*

Fill in X and Y from your actual results. All outcomes are valid findings.
