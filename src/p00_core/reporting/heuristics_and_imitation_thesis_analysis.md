# Heuristics, search, and imitation learning: thesis analysis

This note is the results-chapter argument for the four paradigms that are fully
measured in `data/benchmarks/all_10k/gen9randombattle`: heuristics **v1–v14**,
1-ply minimax **v15–v17**, Information-Set MCTS **v18–v20**, and imitation
learning **v21–v22**. It is written from the round-robin (10,000 games per matchup;
**1,000** when either side is v18/v19/v20), not from n = 10 validation anecdotes or
the June 2026 thesis plan.

**Research question.** In a partially observable stochastic game (`gen9randombattle`),
which decision paradigm gets closest to the knowledge ceiling of a strong heuristic:
explicit rules, one-turn adversarial search, multi-turn Monte Carlo search, or
cloning expert humans?

**Short answer.** Domain knowledge has a clear ladder with two real jumps and one
inversion; **v12 is the bot-vs-bot ceiling**. Neither 1-ply minimax nor 5-ply MCTS
nor imitation learning beats it. In every learned/search family the same pattern
appears: the **unconstrained** residual (v15/v16, v18/v19, v22) overrides v14 and
loses more; the **hybrid that trusts v14** (v17, v20, v21) is the only variant that
moves the win rate — and it still sits at v9/v11, below v12–v14. Search and cloning
are backups behind a KO short-circuit (~14 checks / game, ~16% of turns), not
replacements for knowledge.

---

## 1. Protocol (what the numbers mean)

| Item | Value |
|---|---|
| Format | Pokémon Showdown `gen9randombattle` |
| Seat | Each agent as **us** vs 28 opponents (directed files `agent_vs_opponent.csv`) |
| Sample | 10,000 games per matchup; **1,000** if either side is v18, v19 or v20 |
| Pool | Heuristics / IL / minimax: **253,000** games (10k × 25 opponents + 1k × 3 MCTS). MCTS agents: **28,000** games (1k × 28). |
| Uncertainty | At n = 10,000 and p ≈ 0.5, a 95% interval is **±0.98 pp**. At n = 1,000 it is **±3.1 pp**. Do not treat a 2 pp MCTS-cell gap as a result. |
| Overall win rate | Weighted mean across the 28-opponent gauntlet. It is **not** a single skill number: `random` and `max_power` inflate everyone. Use it to rank, then read specific matchups. |
| Reciprocal check | Independent files `A_vs_B` and `B_vs_A`. Win rates should sum to ~100%. They do (typically 99.3–100.9). Self-play sits at ~50%. |

Opponents in the gauntlet: six baselines (`random`, `max_power`, `one_step`,
`safe_one_step`, `abyssal`, `simple_heuristic`), heuristics v1–v14, minimax v15–v17,
MCTS v18–v20, IL hybrid v21, IL pure v22.

**How to read overall WR.** Beating `random` at 98% is uninformative. The discriminating
baselines are **Abyssal** and **Simple Heuristic** (Pokechamp-style / local clones of
strong one-step play). The discriminating peers are **v12 / v13 / v14** and **v21**.

Figures and per-agent tables live next to this file:

- Heuristic EDA: `eda_heuristics_v1_v14.ipynb`, `agents/heuristics_v1_v14/`
- Minimax EDA: `eda_minimax_v15_v17.ipynb`, `agents/minimax_v15_v17/`
- MCTS EDA: `eda_mcts_v18_v20.ipynb`, `agents/mcts_v18_v20/`
- IL EDA: `eda_imitation_v21_v22.ipynb`, `agents/il_v21_v22/`

---

## 2. What each paradigm is, academically

### 2.1 Heuristics v1–v14 — explicit knowledge as an ablation ladder

These agents do not learn. At every decision they score legal moves and switches with a
fixed formula and pick the argmax. The series is an **ablation by construction**: each
version adds a capability that a human expert would name (damage math, hazards, Tera,
set prediction, …). That is the point for the thesis. A 14-step ladder lets you say
*which piece of knowledge moved the win rate*, not just that “heuristics work”.

Inheritance is not a single chain. v1→v2→v3→v6 is one family (damage + light switching).
v4/v5 add field and boosts. v7 is a rewrite (hazards, setup, KO, matchup switching).
v8–v14 grow from that strategic core. v14 is v13 plus Yomi profiling, early scouting,
16-step damage rolls, and a 1-ply endgame solver.

### 2.2 Imitation learning v21–v22 — behavioural cloning of expert macro play

Both agents clone **human gen9randombattle** turns (Elo 1800+ replays; ~1.12 million
turns; 1,150 features; GroupShuffleSplit by `battle_id` so turns from the same battle
do not leak into test). The shared head is an XGBoost classifier of **move vs switch**
with calibrated threshold τ = **0.5525** (`xgboost_advanced_threshold.json`).

They diverge after that prediction:

| | **v21 Hybrid** (`HeuristicV21XGBoost`) | **v22 Pure IL** (`HeuristicV22PureIL`) |
|---|---|---|
| Inheritance | Full `HeuristicV14` | `BaseHeuristic1v1` only — **no v14** |
| Before XGB | Guaranteed KO → endgame minimax (≤2 mons) → setup / status absorb | Nothing — XGB is first |
| If switch | Pivot (U-turn / Volt Switch) or v14 `_get_best_switch` | Counterfactual: score every bench mon as if it were active, pick lowest \(p(\text{switch})\) |
| If move | v14 `_score_move` | Second model `xgboost_move_evaluator.json` |
| Overrides | Weak-move tactical switch-back | Loop guard only |

This is a hierarchical policy (macro: stay/switch; micro: which move / which mon).
v21 is the hybrid. v22 is the “pure clone” control that a defence committee will ask
for. Without v22 you cannot claim the hybrid is necessary; without v21 you cannot
claim imitation of *timing* is useful at all.

The older `ml_baseline` (three features, random execution) is **not** in this
round-robin. It belonged to the diagnostic that showed “predict move vs switch and then
pick uniformly” collapses to ~8–16% WR. v22 is the honest pure successor.

### 2.3 1-ply minimax v15–v17 — adversarial search without a simulator

1-ply minimax is the classical answer to “the heuristic does not consider the
opponent’s reply.” All three agents inherit `HeuristicV14` and, on turns without a
guaranteed KO, enumerate our legal actions against **predicted** opponent replies
(revealed moves, filled from the Showdown set DB, plus a hypothetical switch). The
score is maximin of a risk-averse leaf \(V = \mathrm{HP}_{me} - 1.5\,\mathrm{HP}_{opp}\).
Speed and priority are resolved analytically; if the faster Pokémon KOs, the slower
action is nullified. There is **no** `LocalSim` rollout — this is exact damage math,
one turn deep.

| | **v15** | **v16** | **v17** |
|---|---|---|---|
| Leaf | HP + matchup after the simulated turn | + setup / hazard / recovery / status bonuses | Same as v16 |
| Before search | KO → 1-ply endgame | + setup-stop, status absorb, early U-turn | Same as v16 |
| v14 bias | Probe after search (`search_diff`) | Same | **+0.15** on v14’s action’s worst-case score |

v16 tests whether decorating the leaf with delayed-payoff bonuses fixes the horizon
effect. v17 is the hierarchical sibling of MCTS v20 / IL v21: keep the expert, let
search only re-rank.

### 2.4 Information-Set MCTS v18–v20 — lookahead under hidden information

1-ply minimax cannot value delayed payoffs that take more than one turn and treats
the opponent’s remaining moves as a known set. IS-MCTS is the standard next step:
sample a plausible hidden state, simulate several turns, average.

All three MCTS agents inherit `HeuristicV14` and share the same budget:

- **100 simulations / turn**, **5-turn** `LocalSim` rollouts, UCB exploration \(C = 1.4\)
- Each simulation **determinizes** the opponent (moves / item / ability from the
  Showdown random-battle set database)
- Root children are legal moves **and** switches; the played action is argmax visits

They differ in leaf evaluation, pre-search overrides, and tree bias:

| | **v18** | **v19** | **v20** |
|---|---|---|---|
| Tree | UCB1 | UCB1 | **PUCT**, v14 prior **0.70** |
| Leaf | Team HP + boosts + status + hazards | + roles, speed-tier OHKO threat | Same as v19 |
| Before search | Guaranteed KO only | KO → endgame → setup-stop → status absorb | Same as v19, and it **takes** the early U-turn |
| Empirical “lookahead worked” | `search_diff_us`: MCTS played ≠ v14 probe | Same | Same, but PUCT should make this **rare** |

The academic contrast is the same shape as IL: v18/v19 are “let search decide”, v20
is the hierarchical hybrid (expert prior + search). Without all three you cannot
separate *leaf quality*, *tactical overrides*, and *prior biasing*.

---

## 3. The heuristic ladder: three regimes, not fourteen equal steps

Gauntlet win rate (253,000 games each):

| Rank | Agent | Overall WR | What was added | vs Abyssal | vs SimpleHeuristic |
|---:|---|---:|---|---:|---:|
| 1 | **v12** | **69.01%** | Tera + teampreview lead + fainted switch-in | **59.91%** | **59.75%** |
| 2 | v13 | 67.63% | Set prediction, stat-aware matchups, conservative Tera, recovery, choice-lock | 55.34% | 56.10% |
| 3 | v14 | 62.03% | Yomi 2, turns 1–3 scouting, 16-step damage, 1-ply endgame | 51.36% | 50.66% |
| 4 | v11 | 59.26% | v9 tight setup + v10 status/sack/pivot | 47.50% | 47.32% |
| 5 | v9 | 58.86% | Hazards / setup **only on free turns** | 46.64% | 47.01% |
| 6 | v10 | 55.66% | Status, sack ≤20% HP, Volt Switch / U-turn | 41.86% | 42.70% |
| 7 | v8 | 55.43% | Items, abilities, screens, Trick Room | 42.30% | 42.80% |
| 8 | v7 | 54.25% | Hazards, setup, KO check, Abyssal-style matchup switch | 40.80% | 40.67% |
| 9–14 | v5 … v1 | 45.86–44.25% | Damage math, weather, boosts, tracking | 32.50–30.64% | 31.99–30.26% |

Self-play for every heuristic is 49.3–50.5%. Reciprocals sum to ~100%. The ranking is
not a recording-seat artefact.

### 3.1 Plateau: v1–v6 (44–46%) — better damage math does not win Random Battles

v1 maximises `base_power × effectiveness × STAB` and never switches. v2–v6 add stats,
burn, move tracking, weather/terrain, boost stages, and a Toxic/outspeed pivot. The
whole cluster is statistically almost flat:

- Overall WR spans **1.61 pp** (v1 44.25 → v5 45.86).
- Head-to-head they sit at ~50% against each other.
- vs Abyssal they remain **30.6–32.5%** — they lose to a competent one-step baseline.

**Thesis sentence.** Once you have type effectiveness, extra damage-formula fidelity
has diminishing returns. Random Battle is won by *position* (who is on the field, when
you Terastallize, whether hazards are up), not by a slightly better expected-HP
estimator.

Behaviour on a five-matchup slice (`abyssal`, `v12`, `v14`, `v21`, `random`) confirms
they play the same game: ~1.04 voluntary switches / game, **zero** Tera, **zero**
logged hazards/setup/KO-checks, ~4.3 engine fallbacks / game. They are greedy attackers
with a weak escape hatch.

### 3.2 First jump: v7 (and v8/v10) — positional play, +9 pp

v7 is the first strategic rewrite: entry hazards, setup on a good matchup, guaranteed-KO
pre-check, and matchup-score switching (the Abyssal formula). Overall WR jumps from
~45.5% (v4–v6) to **54.25%**. vs Abyssal jumps from ~32% to **40.8%**.

v8 (items, abilities, screens, Trick Room) adds only **+1.2 pp** overall. That is a
real but small increment: meta-reading helps, it does not redefine the agent.

v10 (Toxic / Will-O-Wisp / Thunder Wave, sack logic, pivots) is essentially tied with
v8 (55.66 vs 55.43). Status and pivots are useful; they are not the next regime change.

Logged behaviour shifts with v7: voluntary switches rise to ~1.55, `matchup_switches_us`
becomes non-zero (~0.48 / game), fallbacks drop from ~4.4 to ~2.0. The agent is now
*choosing* to switch, not only fainting out.

### 3.3 Second jump: v9 / v11 — stop wasting tempo, +4 pp

v9 keeps v7’s core but fires hazards and setup **only on free turns** (outspeed and
resist opponent STAB). That single constraint is worth more than v8’s entire item
table: **58.86%** overall, **46.64%** vs Abyssal.

v11 hybridises v9 + v10 and barely moves the needle (**59.26%**, +0.4 pp vs v9). Once
tempo-safe setup exists, grafting status/sack/pivot on top is nearly redundant in this
gauntlet.

Logged behaviour: v9/v11 are the first agents with real `setup_uses_us` (~1.6 / game)
and `hazard_sets_us` (~0.16). v7/v8/v10 log those counters at 0 in this schema — either
the code paths did not increment the counters, or they almost never took the action.
Do not over-interpret a zero in v7 as “v7 never sets rocks”; interpret the **v9 jump
in the counter** as “v9’s free-turn gate made setup frequent enough to measure”.

### 3.4 Third jump: v12 — Gen 9 actually played as Gen 9, +10 pp

v12 adds three things that are native to this format:

1. **Terastallization** scored offensively and defensively.
2. **Teampreview lead** (best average matchup against the known six).
3. **Matchup-based fainted switch-in** (no more slot-0 replacement).

Overall WR **69.01%**. First heuristic in the project to beat **both** Abyssal and
Simple Heuristic at scale: **59.91% / 59.75%** (n = 10,000, CI ±0.96). vs `one_step` /
`safe_one_step` it jumps from ~65% (v9/v11) to **~76.5%**.

Tera usage on the five-matchup slice is **0.95 / game** — it Terastallizes almost every
battle. Fallbacks collapse to **0.02 / game**. Remaining HP on our side, gauntlet-wide,
is **1.84** mons versus **1.44** for v11. This is not a cosmetic patch. It is the
format-specific skill that v1–v11 were missing.

**Thesis sentence.** In gen9randombattle, Terastallization plus principled switch-ins
is a larger rule than item awareness, status, or a more accurate damage formula. Any
later paradigm that cannot Tera and cannot choose leads is competing with one hand
tied.

---

## 4. The inversion: later is not better (v12 ≥ v13 > v14)

This is the result that must not be smoothed over. The genealogy says v14 ⊃ v13 ⊃ v12.
The round-robin says the opposite.

### 4.1 Head-to-head (10,000 independent games each way)

| | WR (row vs column) | Reciprocal | Sum |
|---|---:|---:|---:|
| v12 vs v13 | 50.65% | 48.85% | 99.50 |
| v12 vs v14 | 56.01% | 44.74% | 100.75 |
| v13 vs v14 | 57.71% | 41.60% | 99.31 |

v12 vs v13 is a **coin flip** (gap 1.8 pp, each CI ±0.98; consistent with a tiny v12
edge or with equality). v14 loses clearly to both.

The old v13 write-up claimed **90% vs v12 in 10 games**. That anecdote is false at
n = 10,000. Cite the 10k number; mention the n = 10 figure only as a cautionary
example of why the benchmark exists.

### 4.2 Where v13 still wins

v13 is not a strictly dominated agent. It is the **best heuristic against search and
against the IL hybrid**:

| Opponent class | v12 | v13 | v14 |
|---|---:|---:|---:|
| Minimax (v15, gauntlet cell) | 63.96% | **67.59%** | 60.07% |
| Minimax v17 | 60.37% | **64.12%** | 56.70% |
| MCTS v18 (n = 1,000) | 66.10% | **67.70%** | 59.80% |
| v21 Hybrid IL | 59.12% | **62.46%** | 54.74% |
| Baselines as a block | **76.91%** | 74.36% | 71.06% |
| Other heuristics as a block | **67.01%** | 64.71% | 58.58% |

v13 also finishes games with more HP left (gauntlet `avg_hp_us` **2.01** vs 1.84 / 1.49)
and plays longer (19.1 turns vs 17.9 / 18.5). It is a more attritional, prediction-heavy
player.

### 4.3 Why v13 does not beat v12 overall

v13 Terastallizes **conservatively** (0.19 Tera / game on the slice vs v12’s 0.95).
It voluntary-switches **4.0 / game** vs v12’s 1.5, and `matchup_switches_us` jumps to
**3.0**. Set prediction and recovery buy HP against search agents; against other
heuristics the extra switches leak tempo. v12’s greedy Tera + simpler switch-in is the
better exploit of *static, non-bluffing* bots.

### 4.4 Why v14 loses in bot-vs-bot (and why that is not a failure)

v14 was built to beat **humans**: Yomi 2 (predictive vs conservative opponent), turns
1–3 scouting (Protect / U-turn / Knock Off), defensive Tera bait, 16-step damage rolls,
1-ply endgame when ≤2 mons remain.

Against a heuristic, those extras are often **over-respect**:

- Scouting spends early turns that v12 spends attacking.
- Yomi profiling of a deterministic bot is fitting noise.
- `ko_checks_us` explodes to **~15 / game** (the 16-step calculator fires constantly)
  while `setup_uses_us` drops to 0.22 — v14 is KO-hunting instead of building.
- vs Abyssal it is only **51.36%**, statistically a coin flip with a strong baseline.
  v12 is **59.91%**.

Online, the current v14 ladder log is **431 games, 39.44% ± 4.6 pp**, Elo **1085 → 1038**
(peak 1263). The June 2026 snapshot (98 games / 40.8% / Elo ~1151) is a prefix of the
same log, taken near a local Elo high — do not cite it as the final sample. That is
still the right *human* baseline. Do **not** use the bot-vs-bot ranking to claim v12
would beat humans more than v14. Do **not** use the ladder sample to claim v14 is the
best bot.
They answer different questions. The thesis should say that out loud.

**Thesis sentence.** Adding human-modelling machinery to a heuristic can *lower*
bot-vs-bot win rate. That is evidence that the extra rules are specialised, not that
the agent is broken. The evaluation protocol must stay split: round-robin for paradigm
comparison, ladder for the human-level claim.

---

## 5. Imitation learning: the same expert, two execution models, two different agents

### 5.1 Headline (full 253,000-game gauntlet)

| | v21 Hybrid | v22 Pure IL |
|---|---:|---:|
| Win rate | **58.71%** ± 0.19 | **33.49%** ± 0.18 |
| Avg turns | 18.20 | 20.07 |
| Remaining mons (us) | 1.33 | 0.70 |
| Voluntary switches / game | 1.98 | 3.72 |
| XGB fire rate (% of turns) | **15.2%** | **79.9%** |
| Among XGB decisions, % SWITCH | 35.5% | 15.2% |
| Mean \(p(\text{switch})\) | 0.080 | 0.351 |
| KO guards / game | 13.85 | **0** |
| Endgame solves / game | 0.032 | **0** |
| Loop guards / game (% of games) | 0.38 (33%) | 1.92 (**97%**) |
| Tera / game (slice) | 0.41 | **0.99** |
| Fallbacks / game | 0 | 0.011 |

v21 beats v22 in **28 / 28** matchups (mean **+25.2 pp**). Direct H2H: v21 vs v22
**71.74%**, v22 vs v21 **29.07%** (sum 1.008). Self-play 49.92% / 49.58%.

v22 purity checks are exact: `ko_guards`, `endgame_solves`, `ko_checks`, `search_*`
are 0 in 100% of games. The two stacks are not the same policy with a different label.

### 5.2 Where they sit on the heuristic ladder

Inserting IL, 1-ply minimax, and MCTS into the overall ranking (MCTS overall is 28k
equally weighted opponents; heuristic / IL / minimax overall is 253k and slightly
underweights the three MCTS cells — directionally the same ladder):

```
v12  69.0
v13  67.6
v14  62.0
v20  59.7   ← PUCT MCTS (28k)
v11  59.3
v9   58.9
v21  58.7   ← hybrid IL
v17  57.9   ← 1-ply + v14 prior +0.15
v10  55.7
v8   55.4
v16  54.3   ← 1-ply positional leaf (≈ v15)
v7   54.3
v18  54.0   ← UCB1 MCTS
v15  53.8   ← 1-ply HP leaf
v19  53.3
…
v1   44.3
v22  33.5   ← pure IL
```

Specific matchups that matter:

| | vs v12 | vs v13 | vs v14 | vs Abyssal | vs SimpleH |
|---|---:|---:|---:|---:|---:|
| v21 | 41.28 | 38.39 | 45.43 | 46.98 | 47.76 |
| v17 | 40.94 | 35.10 | 43.61 | 46.79 | 46.75 |
| v22 | 19.80 | 22.03 | 25.81 | 22.90 | 21.73 |
| v20 (n=1k) | 42.7 | 39.1 | 47.0 | 49.0 | 49.2 |

v14 vs v21 is **54.74%** (reciprocal 45.43, sum 100.17). Grafting a human switch-timing
model **onto v14 does not beat v14**. It plays like a slightly worse v14: overall WR
58.7 vs v14’s 62.0; vs Abyssal 47.0 vs 51.4.

v22 loses even to **v1** (v1 vs v22 = 65.72%). Pure cloning is not “a weak expert”; it
is below greedy `bp × type × STAB`.

### 5.3 Why v21 is mostly still a heuristic

Only **15% of v21’s turns** ever reach the XGBoost head. The other 85% are consumed by
v14’s guaranteed-KO path (`ko_guards_us` ≈ 14 / game — the same order of magnitude as
v14’s `ko_checks_us`). Mean \(p(\text{switch})\) on the turns that do reach the model
is 0.08, far below τ = 0.5525, so the macro head almost always says *stay*, and v14
picks the move.

So the honest description of v21 in this benchmark is:

> A v14 agent that, on the minority of turns without a KO, asks a human-clone whether
> to switch, then still uses v14 to execute.

That is why v21 clusters with v9/v11 rather than with v12–v14 (it Terastallizes like
v14, not like v12) and why it cannot beat its teacher. The imitation layer is a
**switch-timing prior**, not a new tactical engine.

This is still a legitimate IL result. It shows that expert *when-to-switch* is a
learnable signal (v21 is far above v22 and far above `ml_baseline`). It also shows
that this signal is **weaker than v14’s own matchup tables** in bot-vs-bot play.

### 5.4 Why v22 fails — three structural reasons, not “XGBoost is bad”

1. **Action semantics.** A Showdown action slot is not a stable class. Slot 0 is
   Stealth Rock on one lead and Hydro Pump on the next. The macro model therefore
   predicts only {move, switch}. The second model scores *candidate attributes*
   (power, STAB, effectiveness, status, priority), not named moves. That is a lossy
   substitute for v14’s damage calculator. Super-effective hits stay similar
   (v21 4.47 vs v22 4.16 / game); win rate does not, because KO order and switch-ins
   dominate.

2. **Exposure bias / compounding error.** Behavioural cloning is trained on expert
   states. One bad switch puts v22 on a bench the expert never occupied; the
   counterfactual macro then scores that alien state, and the loop guard fires in
   **97% of games** (1.92 times / game vs 0.38 for v21). The policy is fighting its
   own distribution shift for the rest of the match. Games run longer (20.1 vs 18.2
   turns) and end with **0.70** mons left vs 1.33.

3. **Missing hard constraints.** Experts almost never skip a guaranteed KO. v21
   encodes that as a guard *before* the clone is queried. v22 cannot. Combined with
   Tera on **0.99 / game** (unconstrained, unlike v13’s 0.19), it spends the once-per-
   battle resource like a script, not like a player.

**Thesis sentence.** Imitation learning in this domain is limited by *what is cloned*
(macro stay/switch) and by *who executes* (heuristic vs second XGB), not by a lack of
expert data. 1.1 million in-format turns are enough to learn a switch prior. They are
not enough to replace damage math, KO logic, and Tera discipline.

### 5.5 The hybrid is academically the right design — empirically it is not enough

A committee objection: “a true IL agent should pick the move, not call v14.” The
rebuttal is in the table: that agent is v22, and it is dominated. Hierarchical
cloning (macro from data, micro from a solver) is standard in imperfect-information
control. The contribution is the **measurement**: the hierarchy recovers a v9-level
player and does not recover v12. The missing piece is format-specific knowledge
(Tera, preview, KO), which the 1,150-feature macro never had to output.

---

## 6. 1-ply minimax: the opponent’s reply, one turn deep

The minimax question is whether **considering the opponent’s best reply this turn**
beats the one-ply expert that already sits inside every search agent. Same telemetry
as MCTS: `search_fire_rate`, `search_diff_us`, win/loss splits of that disagreement.
The difference is there is no simulator — only exact damage ranges and a maximin
over predicted replies.

Figures: `agents/minimax_v15_v17/minimax_fingerprint_bars.png`, `minimax_override.png`,
`minimax_future_proxies.png`, `minimax_key_matchups.png`.

### 6.1 Headline (253,000 games each)

| | v15 HP leaf | v16 positional bonuses | v17 v14 prior +0.15 |
|---|---:|---:|---:|
| Win rate | 53.80% ± 0.19 | 54.30% ± 0.19 | **57.89%** ± 0.19 |
| Search fire (% of turns) | 17.6 | 17.6 | 16.3 |
| Override of search decisions | **66.5%** | **67.3%** | **36.6%** |
| search_diff / turn (wins / losses) | 0.098 / **0.133** | 0.099 / **0.135** | 0.054 / 0.076 |
| KO checks / game | 14.33 | 14.33 | 14.49 |
| Setup / hazards / Tera | 0.21 / 0.05 / 0.40 | 0.21 / 0.04 / 0.39 | 0.21 / 0.04 / 0.38 |
| Remaining mons (us) | 1.28 | 1.29 | **1.39** |

H2H at n = 10,000 (CI ±0.98 pp):

| | WR | Reciprocal | Sum |
|---|---:|---:|---:|
| v15 vs v16 | 49.28% | 51.14% | 1.004 |
| v15 vs v17 | 45.34% | 54.71% | 1.001 |
| v16 vs v17 | 45.68% | 54.30% | 1.000 |

Self-play 49.92 / 49.97 / 50.12%. Reciprocals are clean.

### 6.2 Search barely runs — again

~14 KO checks / game vs ~4.5 maximin decisions. The matrix is consulted on **16–18%
of turns**. Honest description:

> A v14 KO-first player that, on the residual turns, maximin-scores one analytic turn
> against predicted opponent replies.

Same structural fact as v21 (XGB) and v18–v20 (MCTS).

### 6.3 Decorating the 1-ply leaf does not fix the horizon (v16 ≈ v15)

v16 was the “put setup and rocks in the evaluator” agent. Overall WR **+0.50 pp**
(detectable at 253k, irrelevant in practice). H2H is a coin flip. Setup uses **0.213
vs 0.207**; hazards **0.044 vs 0.049**. The leaf bonuses (0.25–0.35) lose to the
**\(1.5\times\) opponent-damage** term: in a risk-averse 1-ply world, attacking still
beats dancing.

Override rate stays **67%**. Losers still override more than winners (+0.036
search_diff/turn). v16 did not change *when* search disagrees with v14, only the
algebra of the leaf.

**Thesis sentence.** Horizon effect at 1-ply is not a missing bonus in the formula.
It is the maximin objective plus a one-turn horizon. You cannot recover v9’s
free-turn setup by adding +0.3 to Dragon Dance inside a leaf that also multiplies
incoming damage by 1.5.

### 6.4 The +0.15 prior (v17) is the only 1-ply upgrade that matters

v17 adds 0.15 to v14’s action after the maximin. Override rate halves (**67% → 37%**).
Overall WR jumps **+4.1 pp** vs v15. H2H 54.7% / 54.3% vs v15/v16 at n = 10k. Remaining
HP 1.39. Largest gains vs the agents unconstrained maximin was mishandling: **+10.7 pp
vs v20** (n = 1k), **+5.5 vs v9**, **+5.1 vs Abyssal**.

The bias is *weaker* than MCTS v20’s PUCT prior of 0.70 (override 19%), so v17 still
disagrees with v14 on more than a third of search turns and sits **below** v20 / v21
on the ladder (57.9 vs 59.7 / 58.7). Directionally it is the same hybrid.

### 6.5 1-ply vs the knowledge ceiling (n = 10,000 except MCTS cells)

| Opponent | v15 | v16 | v17 |
|---|---:|---:|---:|
| v12 | 36.04 | 35.92 | **40.94** |
| v13 | 32.82 | 33.50 | 35.10 |
| v14 (teacher) | 39.43 | 39.56 | **43.61** |
| Abyssal | 41.72 | 41.86 | **46.79** |
| Simple Heuristic | 41.23 | 40.65 | 46.75 |
| MCTS v18 (n=1k) | 49.3 | 51.8 | 52.9 |
| MCTS v20 (n=1k) | 39.7 | 44.6 | **50.4** |
| IL v21 | 43.65 | 44.75 | 47.50 |
| IL v22 | 69.67 | 70.22 | 71.27 |

v17 vs v14 is **43.6%** — 1-ply search **loses to its teacher** at 10k games, not a
coin flip. v17 vs v12 is **40.9%**. vs Abyssal **46.8%**, still short of v12’s 59.9%.
v17 vs v20 is **50.4%** at n = 1k: the two hybrids that trust v14 are interchangeable
within noise. Unconstrained 1-ply (v15) **loses** to 5-ply PUCT (39.7% vs v20).

**Thesis sentence.** Looking one turn ahead with perfect-information maximin does not
beat v14, and putting delayed-payoff bonuses in that leaf does not make it value the
future. The only 1-ply agent that moves is the one that is told to stay close to v14.

---

## 7. MCTS: five-turn lookahead is a backup, and unconstrained search hurts

The MCTS question for the thesis is not “did we implement UCT?” It is whether
**looking 5 turns into sampled futures** beats the one-ply expert that already sits
inside every MCTS agent. Telemetry answers that directly: `search_fire_rate` (did the
tree run?), `search_diff_us` (did it play something v14 would not?), and win/loss
splits of that disagreement.

Figures: `agents/mcts_v18_v20/mcts_fingerprint_bars.png`, `mcts_override.png`,
`mcts_future_proxies.png`, `mcts_key_matchups.png`.

### 7.1 Headline (28,000 games each, n = 1,000 per opponent)

| | v18 UCB1, HP leaf | v19 UCB1, positional leaf | v20 PUCT, v14 prior 0.70 |
|---|---:|---:|---:|
| Win rate | 54.02% ± 0.58 | 53.29% ± 0.58 | **59.66%** ± 0.57 |
| Search fire (% of turns) | 18.1 | 17.6 | 15.5 |
| MCTS moves / switches per game | 3.76 / 0.61 | 3.40 / 0.87 | 2.60 / 1.07 |
| Override of search decisions | **71.3%** | **71.1%** | **18.7%** |
| search_diff / turn (wins) | 0.109 | 0.104 | 0.029 |
| search_diff / turn (losses) | **0.152** | **0.152** | 0.038 |
| KO checks / game | 14.16 | 14.19 | 14.54 |
| Setup / hazards / Tera | 0.22 / 0.05 / 0.41 | 0.22 / 0.05 / 0.39 | 0.20 / 0.04 / 0.39 |
| Remaining mons (us) | 1.21 | 1.22 | **1.40** |

v20 beats v18 in **28 / 28** matchups (mean **+5.64 pp**). Direct H2H (n = 1,000):

| | WR | Reciprocal | Sum |
|---|---:|---:|---:|
| v18 vs v19 | 49.3% | 51.4% | 1.007 |
| v18 vs v20 | 43.6% | 56.6% | 1.002 |
| v19 vs v20 | 41.2% | 56.6% | 0.978 |

v18 vs v19 is a coin flip: **a richer 5-turn leaf did not help**. v20 vs both is a
clear ~7–15 pp gap (each CI ±3.1, still significant). Self-play 52.3 / 49.5 / 49.9%.

`endgame_solves_us` on v18 (~0.03 / game) is mostly a side-effect of the post-search
v14 probe (v18 never calls the endgame solver). On v19/v20 the solver really runs
before the tree.

### 7.2 Search barely runs — the KO short-circuit is the policy

~14 guaranteed-KO checks per game, vs ~3–4 MCTS decisions. The tree is consulted on
**16–18% of turns**. The honest description of all three agents is:

> A v14 KO-first player that, on the residual turns, runs 100 × 5-ply IS-MCTS.

That is the same structural fact as v15–v17 (1-ply on 16–18% of turns) and v21 (XGB
on 15%). Any claim that “MCTS plays by looking into the future” has to be restricted
to that residual. The 100-sim budget never gets a chance to value a Dragon Dance on a
turn where a KO exists, which is most mid-game turns.

### 7.3 Horizon effect, measured: overriding v14 correlates with losing

`search_diff_us` is the empirical definition of lookahead doing something. Among turns
that reached the tree:

- **v18/v19 override v14 on 71%** of those decisions. The 5-ply tree is not confirming
  the expert; it is replacing it.
- Losers override more than winners (**0.152 vs 0.109** search_diff per turn). The
  extra disagreement is not “finding a better line”; it is associated with defeat.
- That is the **horizon effect** in the replay, not in the algorithm comment.
  A 5-turn greedy rollout with an HP-like leaf prefers immediate damage and will skip
  v14’s delayed-payoff rules (sweeper preservation, hazard turns, scouting).

v19 was supposed to fix this with a positional leaf (roles, OHKO threat). Override
rate stays **71.1%** and overall WR is **0.7 pp worse** than v18. The leaf upgrade is
not the binding constraint. The binding constraint is **100 noisy simulations through
a greedy rollout in a huge hidden-information tree**.

### 7.4 PUCT works by disagreeing less, not by seeing further

v20 puts prior 0.70 on the v14 action (PUCT). Override rate collapses to **18.7%**.
Overall WR jumps to **59.7%**, remaining HP to 1.40, and it is the only MCTS agent
that is even in the conversation with v9/v11/v21.

Largest PUCT gains vs v18 are exactly against the knowledge-heavy and search agents
the unconstrained tree was mishandling: **+11.1 pp vs v17, +10.5 vs v13, +9.8 vs v15,
+8.7 vs v12**. Against `random` the gap is 0.3 pp — there was nothing to fix.

**Thesis sentence.** With this budget, the useful search agent is not “MCTS instead of
v14”. It is “v14, with 100 simulations allowed to re-rank that prior.” That is the
same hierarchical moral as v21 (clone the macro, keep the solver). Unguided UCT is
the v22 of this paradigm: theoretically purer, empirically worse.

### 7.5 Five greedy rollout turns do not buy the future

The reason to search 5 plies is delayed payoff. The replay does not show it:

| | Setup / game | Hazards / game | Tera / game |
|---|---:|---:|---:|
| v12 (knowledge ceiling) | ~1.73 | ~0.18 | ~0.95 |
| v14 (teacher) | ~0.22 | ~0.03 | ~0.31 |
| v15 / v16 / v17 (1-ply) | 0.21 / 0.21 / 0.21 | 0.05 / 0.04 / 0.04 | 0.40 / 0.39 / 0.38 |
| v18 / v19 / v20 (5-ply) | 0.22 / 0.22 / 0.20 | 0.05 / 0.05 / 0.04 | 0.41 / 0.39 / 0.39 |

Setup and hazards stay at **v14 levels**, not v12. Tera is v14-like, not v12. The
horizon problem that motivated MCTS over 1-ply minimax is **not solved** by 5 greedy
LocalSim steps. A rollout policy that scores setup at 80 only when HP > 75% and
hazards at 70 only on turns ≤ 3 is still a shallow heuristic, just executed inside
the tree.

v20’s higher `search_switches` share (36% of search decisions vs 14% for v18) with
*lower* `search_diff` means PUCT is steering visits toward **v14’s switch**, not
inventing new long-horizon switches.

### 7.6 Lookahead vs the knowledge ceiling

All cells n = 1,000, CI ~±3 pp:

| Opponent | v18 | v19 | v20 |
|---|---:|---:|---:|
| v12 | 34.0 | 33.1 | **42.7** |
| v13 | 28.6 | 34.1 | 39.1 |
| v14 (teacher) | 40.0 | 41.7 | **47.0** |
| Abyssal | 42.2 | 38.7 | **49.0** |
| Simple Heuristic | 42.0 | 40.1 | 49.2 |
| Minimax v15 | 49.3 | 51.6 | **59.1** |
| Minimax v17 | 44.7 | 45.3 | 55.8 |
| IL v21 | 44.1 | 46.5 | 49.6 |
| IL v22 | 71.1 | 66.9 | 73.0 |

v20 vs v14 is **47.0%** — a coin flip with its own teacher. v20 vs v12 is **42.7%** —
clearly below the knowledge ceiling. v20 vs Abyssal is **49.0%**, back to the coin
flip that v12 had already left (59.9% at n = 10k). Search beats 1-ply minimax once
PUCT is on (59.1% vs v15) and crushes pure IL, which is the same pattern as every
competent heuristic.

Paradigm blocks: v20 is 69.9% vs baselines, 56.7% vs heuristics, 57.4% vs minimax.
v18/v19 are ~50% vs heuristics and *below* 50% vs minimax. Unconstrained 5-ply search
does not even beat 1-ply search.

**Thesis sentence.** IS-MCTS with 100 × 5-turn greedy rollouts does not surpass v12
or v14. It surpasses *unguided* search of the same family, and only when the tree is
told to trust the heuristic.

---

## 8. Cross-cutting facts the thesis should use

### 8.1 Abyssal is the external ruler

Until v12, **no** internal heuristic beat Abyssal. v7–v11 sit at 41–48%. v12 is the
regime change (59.9%). v14 is back to a coin flip (51.4%). v21 is below (47.0%).
v20 PUCT is a coin flip at n = 1k (**49.0% ± 3.1**). v17 is **46.79%** at n = 10k.
v18 is 42.2%, v15 is 41.7%, v22 is crushed (22.9%). If the thesis needs one number
for “did we surpass the published rule baseline?”, it remains **v12 vs Abyssal,
59.91% ± 0.96, n = 10,000**.

### 8.2 The same hierarchical moral appears three times

v21 (IL), v17 (1-ply), and v20 (MCTS) are the same architecture in different clothes:
**keep v14’s KO/tactics, add a residual module** (XGB switch prior / +0.15 maximin
bias / PUCT-biased tree). All three residual modules fire on ~15–18% of turns. The
pure-er siblings (v22, v15/v16, v18/v19) override the expert more and win less. The
thesis can say this once and point at three figures (`il_fingerprint_bars.png`,
`minimax_override.png`, `mcts_override.png`).

The control to beat for any later paradigm (deeper MCTS, PPO, LLM) remains **v12/v13**,
not v14, not v17, not v20, not v21.

### 8.3 Switching volume is not skill

| Agent | Vol. switches / game | Overall WR |
|---|---:|---:|
| v12 | 1.46 (slice) | 69.0% |
| v18 | 1.61 | 54.0% |
| v15 | 2.00 | 53.8% |
| v16 | 1.96 | 54.3% |
| v17 | 2.07 | 57.9% |
| v21 | 1.98 | 58.7% |
| v20 | 2.09 | 59.7% |
| v14 | 2.20 (slice) | 62.0% |
| v22 | 3.72 | 33.5% |
| v13 | 4.02 (slice) | 67.6% |

v13 switches like v22 and wins like v12. v22 switches a lot because it is lost, not
because it is “more positional”. Always pair switch counts with win rate and with
*who initiated* the switch (`matchup_switches` vs `search_switches` vs loop guard vs faint).

### 8.4 Tera policy is a fingerprint

| Agent | Tera / game |
|---|---:|
| v1–v7 | ~0 (slice) |
| v13 | 0.19 (slice) |
| v14 | 0.31 (slice) |
| v20 / v19 / v18 | 0.39 / 0.39 / 0.41 |
| v15 / v16 / v17 | 0.40 / 0.39 / 0.38 |
| v21 | 0.41 (slice) |
| v12 | **0.95** (slice) |
| v22 | **0.99** (slice) |

v12 and v22 both Tera almost every game and sit at opposite ends of the ranking. Tera
*availability* is necessary (v1–v11). Tera *discipline* is not the same as Tera
*frequency*. v13’s conservative gate is part of why it trades overall WR for better
search matchups.

---

## 9. What to claim in the thesis (and what not to)

### Claims that are supported

1. **Heuristic knowledge has a non-linear return.** Damage-formula refinements (v1–v6)
   are a plateau. Positional play (v7) and tempo-safe setup (v9) are discrete jumps.
   Format mechanics (Tera + preview + switch-in, v12) are the largest jump.

2. **The knowledge ceiling in bot-vs-bot is v12, not v14.** v12 ≥ v13 ≫ v14 against
   the gauntlet. Extra human-modelling rules can hurt against deterministic bots.

3. **Imitation of expert macro-timing is real but weaker than v12–v14 tactics.**
   v21 ≈ v9/v11, loses to its teacher v14, and only queries XGBoost on 15% of turns.

4. **Pure behavioural cloning is insufficient** for this POSG with the representation
   used here. v22 is below v1. The failure is exposure bias plus missing KO/Tera/switch
   execution, demonstrated by telemetry (loop guards in 97% of games, zero KO guards,
   Tera every game).

5. **The hybrid vs pure contrast is the IL contribution.** Same data, same macro
   model, same threshold; execution stack changes the agent from “mid heuristic” to
   “worse than random-move greedy”. That isolates *execution*, not data quality
   (the gen9ou mismatch that produced 2% WR is already fixed).

6. **1-ply minimax does not beat its teacher.** Search fires on ~17% of turns.
   Unconstrained maximin (v15/v16) overrides v14 on **67%** of those turns; losers
   override more. Putting setup/hazard bonuses in the leaf (**v16**) changes overall
   WR by +0.5 pp and does **not** raise setup uses (0.21, v14-like). The +0.15 v14
   prior (**v17**) is the only 1-ply upgrade that matters (+4.1 pp, override 37%).
   v17 vs v14 is **43.6%** at n = 10k; vs v12 **40.9%**.

7. **Five-turn IS-MCTS does not beat the knowledge ceiling either.** Same KO backup
   (16–18% search). Unconstrained UCB1 overrides v14 on 71%; a richer leaf (v19) does
   not help. PUCT with a v14 prior (v20) is the only 5-ply variant that moves WR
   (+5.6 pp vs v18) — by *disagreeing less*. v20 vs v12 is 42.7%; vs v14 is 47.0%
   (n = 1,000). Setup/hazards stay at v14 levels. v17 vs v20 is 50.4% (n = 1k): the
   two hybrids that trust v14 are interchangeable.

8. **The hierarchical moral is the same in IL, 1-ply, and 5-ply.** Residual modules
   that trust v14 (v21, v17, v20) beat residual modules that replace it (v22, v15/v16,
   v18/v19). Pure search and pure cloning both fail in this domain at the budgets
   tested.

### Claims to avoid

- “v14 is the best heuristic.” It is the best *designed for humans*; it is third in
  the round-robin.
- “v13 crushes v12.” False at n = 10,000.
- “v21 is an IL agent that plays like humans.” It is a KO-first v14 with a human
  switch prior on the residual turns.
- “IL failed.” Hybrid IL is a competent v9-level player from static data. Pure IL
  failed. Those are different sentences.
- “Minimax looks at the opponent’s reply, therefore it is safer than v14.” It loses
  to v14 at 10k games. The 1.5× damage term plus a 1-turn horizon is not safety; it
  is myopia.
- “v16 values setup because the leaf has a setup bonus.” Setup counts refute that.
- “MCTS looks 5 turns ahead, therefore it values setup.” Same refutation.
- “v20 / v17 is a strong search agent.” Each is a strong *v14-biased search*. Unguided
  search is a mid heuristic.
- Using overall WR as a proxy for human Elo. `random` is in the average. Report
  vs Abyssal, vs v12, and ladder separately. Do not mix 28k MCTS overall WR with 253k
  heuristic/minimax/IL overall WR without noting the sample.

### Suggested results-chapter spine

1. Protocol and why 10k / 1k games (this §1).
2. Heuristic ladder and the three jumps (§3), figure: overall WR by version.
3. Inversion v12/v13/v14 and the bot-vs-human split (§4).
4. 1-ply minimax (§6): maximin diagram, override 67% vs 37%, v16 leaf failure,
   `minimax_override.png`.
5. 5-ply MCTS (§7): `mcts_override.png`, 71% vs 19%, PUCT vs UCB1, 1-ply vs 5-ply.
6. IL (§5): `il_fingerprint_bars.png`, hybrid vs pure.
7. Cross-paradigm ranking vs v12 / Abyssal / teacher v14 (§8.1).
8. Discussion: in this POSG, knowledge beats cloning and beats shallow lookahead;
   the hybrids that *keep* the knowledge (v21, v17, v20) are the only
   learned/search agents that are even competitive; pointer to deeper search / PPO.

---

## 10. Caveats

- **Gauntlet-weighted overall WR** includes easy opponents. Rankings are robust
  (v12 is first on Abyssal, on heuristics, and overall) but the absolute 69% is not a
  “true skill”.
- **MCTS overall WR is 28k games, all n = 1,000.** Heuristic / IL / minimax overall is
  253k with MCTS opponents underweighted. Compare **matchup cells**, not the two
  overall percentages, when ranking v20 against v17. Per-cell gaps under ~3 pp
  involving v18–v20 are noise.
- **Strategy counters are schema-incomplete.** `hazard_sets_us` / `setup_uses_us` are
  0 for v7/v8/v10 and for both IL agents; they are non-zero for v9/v11/v12/v13/v14
  and for minimax/MCTS (at v14-like levels). Use them only where they fire.
- **Telemetry slice** in §3–§4 (switches, Tera, KO checks for heuristics) is five
  matchups, not the full 28. IL, minimax, and MCTS numbers in §5–§7 are the full
  gauntlet.
- **v18 `endgame_solves_us`** is contaminated by the post-search v14 probe. Do not
  cite it as “v18 runs the endgame solver”. v15–v17 do call the solver before search.
- **No human IL labels on Tera/KO.** The clone never had to imitate “when to Tera” as
  a first-class head.
- **LocalSim ≠ Showdown.** Rollout noise is a plausible contributor to v18/v19
  override-and-lose. 1-ply minimax does **not** use LocalSim, so v15/v16’s
  override-and-lose cannot be blamed on simulator mismatch — it is the maximin
  objective itself.
- **v14 ladder evidence is a pilot** (431 games, 39.44% ± 4.6 pp, Elo 1085 → 1038).
  Treat it as ecological validation against humans, not as a parallel of the 10k matrix.

---

## 11. Numbers cheat-sheet

```
Overall WR
  heuristics/IL/minimax 253k; MCTS 28k (all MCTS cells n=1k)
  v12 69.01   v13 67.63   v14 62.03   v20 59.66
  v11 59.26   v9  58.86   v21 58.71   v17 57.89
  v10 55.66   v8  55.43   v16 54.30   v7  54.25
  v18 54.02   v15 53.80   v19 53.29   v22 33.49

vs Abyssal
  v12 59.91 (10k)   v13 55.34   v14 51.36   v20 49.0 (1k)
  v21 46.98         v17 46.79   v16 41.86   v15 41.72
  v18 42.2 (1k)     v1  30.64   v22 22.90

vs v12
  v13 48.85 (10k)   v14 44.74   v20 42.7 (1k)   v21 41.28
  v17 40.94         v15 36.04   v18 34.0 (1k)   v22 19.80

vs v14 (teacher)
  v12 56.01   v13 57.71   v20 47.0 (1k)   v21 45.43
  v17 43.61   v16 39.56   v15 39.43   v18 40.0 (1k)

H2H
  v12 vs v13  50.65 / 48.85
  v12 vs v14  56.01 / 44.74
  v14 vs v21  54.74 / 45.43
  v21 vs v22  71.74 / 29.07
  v15 vs v16  49.28 / 51.14
  v17 vs v15  54.71 / 45.34
  v20 vs v18  56.6 / 43.6     (1k)
  v17 vs v20  50.4            (1k, as us)
  v20 vs v17  55.8            (1k, as us; CI ±3.1)

IL internals
  XGB fire    v21 15% of turns    v22 80%
  override    n/a (macro stay/switch)

Minimax internals (analytic 1-ply, opp dmg × 1.5)
  search fire      v15 18%   v16 18%   v17 16%
  override of tree v15 67%   v16 67%   v17 37%
  setup/game       ~0.21 (v14-like; v16 bonuses did not raise it)

MCTS internals (100 sims × 5-turn LocalSim)
  search fire      v18 18%   v19 18%   v20 16%
  override of tree v18 71%   v19 71%   v20 19%
  setup/game       ~0.22 (v14-like)
```
