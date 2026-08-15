# Phase 2 vs HeuristicV8 — curriculum notes

Lab notebook. V12 claim is **34.1%** at n=10k. See [RESULTS.md](RESULTS.md). Phase 2 vs V8 is a **1k-game** diagnostic. The claim opponent is **HeuristicV12**.

## Label

**BC warmup + MaskablePPO.** After cloning, V8 is out of the loop: `eval_checkpoint` / `PPOPlayer` is obs → masks → MaskablePPO.

| Piece | How it ran |
|---|---|
| MaskablePPO, CUDA, action masks every step | Default algorithm |
| Extra observation features (matchup, boost-aware damage) | Feature engineering on the 318-d vector |
| Copy Phase 1.5 weights into a wider first layer | Curriculum / transfer |
| **400 games of cloning V8 actions before PPO** | **BC from V8**, then PPO |
| `--hybrid` eval (mix PPO with V12 at decision time) | Ablation, labeled hybrid |

The same two-stage recipe appears in published Showdown RL (clone a heuristic, then PPO). `--hybrid` mixes PPO with V12 **at test time**; BC warmup only initializes weights.

---

## What we already ran (valid numbers)

### Phase 1 — vs RandomPlayer

- Train: ~598k steps, train WR ~93%.
- Diagnostic eval, final `p1_random.zip`, n=1000: **91.8%** (918/1000) ± 1.70 pp.
- Graduated (≥90% at 1k).

### Phase 1.5 — vs MaxBasePowerPlayer

- First train hit a lucky 72% **200-game window** and early-stopped; 1k eval was **64.1%**.
- Resume with `--no-early-stop` to ~898k steps; 1k eval: **70.5%** (705/1000) ± 2.83 pp.
- Graduated on the point estimate (>70%), barely. CI still covers values below 70%.

### Phase 2 — vs HeuristicV8 (ramp)

PPO-only attempts stayed on the MaxBP floor. BC at the PPO learning rate did little. BC with its own 1e-3 Adam cloned switching; 100k PPO then plateaued. 1k eval: **40.6%** (threshold for graduating the ramp was >55%).

| Run | What we thought we were doing | What actually happened | Train WR |
|---|---|---|---|
| 1 | 500k steps, lr 1.5e-4 from MaxBP | `model.learning_rate = …` does **not** update Adam. Optimizer stayed at **2e-4**. Early-stop treated a 38% window spike as “best” and quit at 490k | **30.4%** (17.8k games) |
| 2 | 1M steps, lr 5e-5, 8 ports, Adam reset | LR **was** 5e-5. WR still flat | **~29.3%** at 300k+ steps |
| 3 | 328-d obs + 400-game BC, then PPO | BC reused PPO Adam at **5e-5**. Loss 1.42→0.91 (barely fit). First 10k already 30.5%; `clip_fraction≈0` | **29.4%** at 200k (stopped) |
| 4 | Same, but BC Adam **1e-3**, 15 epochs, then 100k PPO | BC: 8849 decisions, agree **43% → 88%**, V8 switch 23% / policy switch 21%. First 10k **35.5%**. Flat after that | **37.4%** (1621/4331) at ~115k |

Runs 1–3 zips were deleted. Run 4 zip is `data/models/ppo/p2_v8/p2_v8.zip`.

#### Diagnostic eval (the number that counts for this ramp)

```bash
uv run python -m src.p05_ppo_drl.s03_evaluation.eval_checkpoint \
  --model data/models/ppo/p2_v8/p2_v8.zip --opponent v8 --games 1000
```

**pure PPO vs v8, n=1000, p1 only, 4 ports, 46s:** **40.6%** (406/1000) ± 3.04 pp (95% CI half-width). Chunks: 37.6 / 44.0 / 36.8 / 44.0. Mean turns 17.3. JSON: `data/models/ppo/eval/pure_ppo_vs_v8_n1000.json`.

That is a lift over the 29% MaxBP floor and over greedy V1 vs V8 in the gauntlet (37.4%). CI is about 37.6–43.6%. Phase 3 loads this zip (switch-aware BC+PPO).

---

### Phase 3 — vs HeuristicV12 (the experiment)

“Coin flip” means **P(win the game) ≈ 50%**, not “moves are random.” V12 vs V12 in the gauntlet is **50.1%**. V8 vs V12 is **32.9%**. Greedy V1 vs V12 is **23.3%**.

| Run | Settings | What happened | Train WR |
|---|---|---|---|
| A | From p2 zip, lr **5e-5**, 8 envs, `ent_coef` 0.01 | `clip_fraction` ~2%. Cumulative never rose 1 pp. Early-stop at 320k (patience 30) | **32.0%** (3880/12115), best 33.4% |
| B (stopped) | From p2 zip, lr **1.5e-4**, 8 ports × 2 envs, `ent_coef` 0.02, `--no-early-stop` | `clip_fraction` ~6%, ~1114 fps. Still on the V8-vs-V12 floor | **32.7%** at 414k (3094/9458), window 35% |

Zip A: `data/models/ppo/p3_v12/p3_v12_lr5e5_flat.zip` (8 envs, lr 5e-5). Zip B: `data/models/ppo/p3_v12/p3_v12_lr15e4_400k.zip` (16 envs, lr 1.5e-4). `p3_v12_stale_160k_interrupt.zip` is a 160k interrupt of the **hotter** run (same hparams as B). Train CSV/plot `p3_v12` on disk is **zip B**.

#### Diagnostic eval of zip A (n=1k; not a claim)

```bash
uv run python -m src.p05_ppo_drl.s03_evaluation.eval_checkpoint \
  --model data/models/ppo/p3_v12/p3_v12_lr5e5_flat.zip --opponent random --games 1000

uv run python -m src.p05_ppo_drl.s03_evaluation.eval_checkpoint \
  --model data/models/ppo/p3_v12/p3_v12_lr5e5_flat.zip --opponent v12 --games 1000 --both-seats
```

| Matchup | Result | Read as |
|---|---|---|
| vs Random | **98.3%** (983/1000) ± 0.80 pp | Sanity: net is not broken |
| vs V12 (zip A) | **36.0%** (360/1000) ± 2.98 pp | Best diagnostic. CI ~33–39%. V8 gauntlet vs V12 is 32.9% |
| vs V12 (zip B) | **32.6%** (326/1000) ± 2.91 pp | Hotter PPO was worse. JSON now on disk is this run (overwrote zip A’s file) |

Need ≳53% at 1k to even suspect a beat. Neither zip has it. **n=10k went on zip A.**

#### Claim eval (the only “PPO vs V12” number)

```bash
uv run python -m src.p05_ppo_drl.s03_evaluation.eval_checkpoint \
  --model data/models/ppo/p3_v12/p3_v12_lr5e5_flat.zip --opponent v12 --games 10000 --both-seats --ports 8
```

**pure PPO vs v12, n=10000, both seats, 8 ports, 450s:** **34.1%** (3405/10000) ± 0.93 pp (95% CI half-width). Mean turns 17.2. JSON: `data/models/ppo/eval/pure_ppo_vs_v12_n10000.json`.

CI about **33.2–35.0%**. p1 1709/5000 = 34.2%; p2 1696/5000 = 33.9% (no seat bias).

How to write it:

| Reading | Fits this number? |
|---|---|
| ≥51% edge vs V12 | No |
| 50±1 coin flip (same skill as V12) | No |
| ~45% knowledge-ceiling loss | No — this is lower |
| V8’s gauntlet matchup vs V12 (**32.9%**) | **Yes.** BC+PPO plays like V8 against V12 |
| Broken net / Showdown bug | No (98.3% vs Random at 1k) |

BC+PPO vs V12 lands in the V8-vs-V12 band (gauntlet **32.9%**). Sanity vs Random at 1k is **98.3%**. Optional footnote: `--hybrid` ablation, labeled hybrid.

---

## Observation at 318-d

HeuristicV8 is mid-pack in the **28-agent gauntlet** (~55% overall). In this curriculum it **punishes greedy attackers**: score damage with boosts, and **switch** when the type matchup is bad. In the 10k gauntlet, greedy **V1 scores 37.4% vs V8**. Phases 1–1.5 taught PPO to beat Random and MaxBP — click high STAB×power on the lead. **29% PPO vs V8** is that matchup.

The 318-d observation made it **almost impossible to learn who to switch to**:

- Active types, four move types, HP, fainted flags, lead one-hots: present.
- **Bench types / per-slot matchup vs the current foe: absent.**
- In `gen9randombattle` the six team slots are a new random team every game. Slot index is not a stable identity.
- So the net can learn “switch when the lead is losing,” but the six switch actions look like HP-only noise. Random switches lose; the policy stops switching; V8 farms the lead.

More PPO steps on that observation cannot invent bench types. The second run proved it: correct LR, still a flat 29%.

Fixes that landed:

1. Loaded checkpoints now apply the new learning rate and `ent_coef`.
2. Early-stop used a noisy 200-game window; later runs used cumulative WR.

---

## Ramp that shipped

Observation **318 → 328**, BC at **1e-3** (run 4), then PPO vs V8. That ramp is **40.6% at 1k vs V8**. Phase 3 from that zip is the experiment.

The experiment number is **34.1% ± 0.93 pp vs V12 at n=10k** (zip A). Phase 3 starts from `p2_v8.zip`.

## Phase 4 — BC from V14 + 346-d obs

Appended obs (matchup / tera / hazard → 346) **and** BC from V14 (foe V12), then PPO vs V12. Label **BC from V14**.

- Loaded zip A, expanded 328→346.
- BC: 400 games V14-vs-V12. After: agree **79.7%**, V14_switch 26.3%, policy_switch 24.6%.
- First 10k train WR **34.1%**.
- PPO (lr 1.5e-4, 8×2 envs) sat at **33.5%** (4203/12554) through ~340k (`clip_fraction` ~6%). Snapshot: `data/models/ppo/p4_v14/p4_v14_aborted_300k.zip`.
- Same V8-vs-V12 floor. V14 vs V12 (44.7%) is in-battle skill. Claim remains zip A.

## Files

| Path | Role |
|---|---|
| `s01_env/vectorizer.py` | Code `OBS_SIZE=346`; claim zips are 328 (`PREV_OBS_SIZE`) |
| `s02_training/bc.py` | Heuristic action cloning (`imitate_heuristic`) |
| `s02_training/loop.py` | LR apply, obs expand, BC hook, cumulative early-stop |
| `s02_training/train_p2_v8.py` | Phase 2 entry (`bc_games=400`, V8) |
| `s02_training/train_p4_v14.py` | Phase 4 entry |
| `data/models/ppo/p2_v8/p2_v8.zip` | Run 4 BC+PPO (40.6% vs V8 at 1k) |
| `data/models/ppo/p3_v12/p3_v12_lr5e5_flat.zip` | **Claim zip A** |
| `data/models/ppo/p3_v12/p3_v12_lr15e4_400k.zip` | Phase 3 run B (32.6% at 1k) |
| `data/models/ppo/p3_v12/p3_v12_stale_160k_interrupt.zip` | 160k interrupt of the hotter run |
| `data/models/ppo/p4_v14/p4_v14_aborted_300k.zip` | Phase 4 snapshot |
| `data/models/ppo/eval/pure_ppo_vs_v8_n1000.json` | V8 diagnostic |
| `data/models/ppo/eval/pure_ppo_vs_v12_n10000.json` | **Claim:** 34.1% vs V12 at n=10k |
| `data/models/ppo/eval/pure_ppo_vs_v12_n1000.json` | Zip B 32.6% (overwrote zip A’s 36.0%) |
| `data/models/ppo/wr_logs/p3_v12.csv` / `plots/p3_v12/` | Zip B train |
| [RESULTS.md](RESULTS.md) | Thesis table |
| [RUN.md](RUN.md) | Reproduce claim eval |
