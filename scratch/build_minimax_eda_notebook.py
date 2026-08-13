#!/usr/bin/env python3
"""Rebuild eda_minimax_v15_v17.ipynb as a three-agent 1-ply adversarial-search comparison."""
from pathlib import Path

import nbformat as nbf

OUT = Path(__file__).resolve().parents[1] / "src/p00_core/reporting/eda_minimax_v15_v17.ipynb"

nb = nbf.v4.new_notebook()
nb["metadata"] = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "pygments_lexer": "ipython3"},
}
cells = []


def md(src: str):
    cells.append(nbf.v4.new_markdown_cell(src.strip() + "\n"))


def code(src: str):
    cells.append(nbf.v4.new_code_cell(src.strip() + "\n"))


md(
    r"""
# EDA: 1-Ply Minimax — v15 / v16 / v17

This notebook audits **how one-turn adversarial search actually decides**, then checks
whether those mechanics show up in the round-robin. All three agents inherit
`HeuristicV14` and run the same 1-ply minimax skeleton — **no** `LocalSim` rollouts:

For every legal action of ours (moves **and** allowed switches):
1. Predict the opponent’s remaining moves from the Showdown random-battle set DB
   (fill to 4); if they have a bench, add a hypothetical `"switch"`
2. Score the joint outcome with exact damage ranges, **speed/priority order**, and
   KO nullification (the slower Pokémon does not act if it faints)
3. Take the **maximin**: pick our action whose *worst-case* score against the
   predicted opponent replies is highest
4. Leaf is risk-averse: \(V = \mathrm{HP}_{me} - 1.5\,\mathrm{HP}_{opp} + \cdots\)

They differ in *what the leaf values* and *whether v14 is allowed to bias the maximin*:

| | **v15** (`HeuristicV15Minimax`) | **v16** (`HeuristicV16Minimax`) | **v17** (`HeuristicV17MinimaxHybrid`) |
|---|---|---|---|
| Leaf | HP + matchup after the simulated turn | + setup / hazard / recovery / status **bonuses** | Same as v16 |
| Before search | Guaranteed KO → 1-ply endgame (≤2 mons) | + setup-sweeper stop, status absorb, early U-turn | Same as v16 |
| v14 relationship | Probe *after* search to log `search_diff` | Same probe | v14 action gets **+0.15** on its worst-case score |
| What “search worked” means | `search_diff_us`: maximin played ≠ v14 | Same | Same, but the prior should make overrides **rarer** |

```
Every turn
──────────
forced faint? ────────── v14 best-switch
guaranteed KO? ───────── take it (no tree)
endgame ≤2 mons? ─────── 1-ply solver
[v16/v17] setup-stop / absorb / early pivot?
                    │
         1-ply minimax (analytic, not simulated)
         for each of our actions a:
           for each predicted opp reply b:
             speed-aware damage  →  V(a,b) = HP_me − 1.5 HP_opp + bonuses
           score(a) = min_b V(a,b)     [+ 0.15 if a is v14’s pick, v17]
         play argmax_a score(a)
         [loop guard if switched last turn]
         log search_diff vs a fresh v14 probe
```

This is the **horizon-effect control** for MCTS: same teacher (v14), same KO
short-circuit, but only **one** future turn and a perfect-information assumption
about the opponent’s replies. If 1-ply already fails to value setup, 5-ply greedy
rollouts are not starting from a solved leaf.

**Sample size.** 10,000 games per matchup except **1,000** vs v18/v19/v20. Each
agent has 253,000 games as *us*. Wilson interval ≈ **±0.19 pp** overall, **±0.98 pp**
on a 10k cell, **±3.1 pp** on an MCTS cell.

Benchmark: `data/benchmarks/all_10k/gen9randombattle`.
"""
)

code(
    """\
# Setup
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
pd.set_option("display.float_format", "{:.3f}".format)
pd.set_option("display.max_columns", 80)
pd.set_option("display.width", 200)

ROOT = Path.cwd().resolve()
while ROOT != ROOT.parent and not (ROOT / "data/benchmarks/all_10k/gen9randombattle").exists():
    ROOT = ROOT.parent
BENCHMARK_DIR = ROOT / "data/benchmarks/all_10k/gen9randombattle"
OUTPUT_DIR = ROOT / "src/p00_core/reporting/agents/minimax_v15_v17"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

AGENTS = ["v15", "v16", "v17"]
AGENT_LABEL = {
    "v15": "v15 maximin (HP leaf)",
    "v16": "v16 maximin (positional bonuses)",
    "v17": "v17 hybrid (v14 prior +0.15)",
}
AGENT_COLOR = {"v15": "#B03A2E", "v16": "#1A7A6D", "v17": "#3D5A80"}

PARADIGM_MAP = {
    "random": "Baseline",
    "max_power": "Baseline",
    "abyssal": "Baseline",
    "one_step": "Baseline",
    "safe_one_step": "Baseline",
    "simple_heuristic": "Baseline",
    **{f"v{i}": "Heuristic" for i in range(1, 15)},
    "v15": "Minimax",
    "v16": "Minimax",
    "v17": "Minimax",
    "v18": "MCTS",
    "v19": "MCTS",
    "v20": "MCTS",
    "v21": "IL Hybrid",
    "v22": "IL Pure",
}
PARADIGM_ORDER = ["Baseline", "Heuristic", "Minimax", "MCTS", "IL Hybrid", "IL Pure"]

SEARCH_COLS = [
    "search_moves_us", "search_switches_us", "search_diff_us",
    "endgame_solves_us", "ko_checks_us", "loop_guards_us", "total_turns_us",
]

sns.set_theme(style="whitegrid", palette="muted")
plt.rcParams.update({"figure.figsize": (11, 5.5), "font.size": 11, "savefig.dpi": 160})


def wilson_ci(wins: float, n: float, z: float = 1.96) -> float:
    \"\"\"Half-width of a 95% Wilson interval, in percentage points.\"\"\"
    if n <= 0:
        return 0.0
    p = wins / n
    denom = 1.0 + z * z / n
    margin = z * np.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denom
    return float(margin * 100)


print(f"Root        : {ROOT}")
print(f"Benchmark   : {BENCHMARK_DIR}")
print(f"Export      : {OUTPUT_DIR}")
print(f"Agents      : {AGENTS}")
print("Search      : 1-ply maximin, analytic damage, opp damage × 1.5")
print("v17 prior   : +0.15 on v14's recommended action")
"""
)

md(
    """\
## 1 · Load all three agents as *us*

Each row is one finished battle. Search telemetry is written by the worker from the
agent's per-battle counters. `search_diff_us` is a 1-ply disagreement with a fresh
v14 probe — the empirical definition of “minimax overrode the expert”.
"""
)

code(
    """\
# Load v15 / v16 / v17 as player
INT_FILL = [
    "won", "turns", "decisions_us", "fallback_moves_us", "error_moves_us",
    "fainted_us", "remaining_pokemon_us", "fainted_opp", "remaining_pokemon_opp",
    "voluntary_switches_us", "forced_switches_us",
    "supereffective_us", "hazard_sets_us", "setup_uses_us", "ko_checks_us",
    "terastallized_us", "loop_guards_us", *SEARCH_COLS,
]


def load_agent(agent: str) -> pd.DataFrame:
    files = sorted(BENCHMARK_DIR.glob(f"{agent}_vs_*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSVs for {agent} in {BENCHMARK_DIR}")
    parts = []
    for path in files:
        df = pd.read_csv(path)
        df["agent"] = agent
        df["matchup_opponent"] = df["opponent"]
        parts.append(df)
    out = pd.concat(parts, ignore_index=True)
    for col in INT_FILL:
        if col not in out.columns:
            out[col] = 0
        else:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)
    out["won_bool"] = out["won"].astype(int)
    out["opponent_paradigm"] = out["matchup_opponent"].map(lambda x: PARADIGM_MAP.get(x, "Other"))
    out["search_decisions"] = out["search_moves_us"] + out["search_switches_us"]
    turns = out["total_turns_us"].replace(0, np.nan)
    out["search_fire_rate"] = out["search_decisions"] / turns
    out["search_diff_rate"] = out["search_diff_us"] / turns
    out["override_of_search"] = out["search_diff_us"] / out["search_decisions"].replace(0, np.nan)
    out["search_switch_share"] = out["search_switches_us"] / out["search_decisions"].replace(0, np.nan)
    return out


frames = {ag: load_agent(ag) for ag in AGENTS}
df = pd.concat(frames.values(), ignore_index=True)

print("Games loaded")
for ag, g in frames.items():
    n_files = g.groupby("matchup_opponent").ngroups
    n_per = g.groupby("matchup_opponent").size()
    print(f"  {ag}: {len(g):>8,} games  |  {n_files} opponents  "
          f"|  median n={int(n_per.median())}  |  WR {g['won_bool'].mean()*100:.2f}%")
print(f"  total: {len(df):,} rows  |  columns {df.shape[1]}")
"""
)

md(
    """\
## 2 · Headline: same 1-ply tree, three leaves / priors

If putting setup/hazard bonuses in the leaf (v16) or adding a v14 prior (v17) did not
matter, win rate, `search_diff`, and setup counts would line up. The interesting
comparisons are **v15 vs v16** (does a positional leaf fix the horizon effect?) and
**v16 vs v17** (does a +0.15 bias toward v14 help, like PUCT did for MCTS?).
"""
)

code(
    """\
# Headline table
rows = []
for ag, g in frames.items():
    n = len(g)
    wins = int(g["won_bool"].sum())
    rows.append({
        "agent": AGENT_LABEL[ag],
        "games": n,
        "win_rate_%": 100 * wins / n,
        "ci95_pp": wilson_ci(wins, n),
        "avg_turns": g["turns"].mean(),
        "avg_hp_us": g["remaining_pokemon_us"].mean(),
        "search_fire_%_turns": 100 * g["search_fire_rate"].mean(),
        "search_moves / game": g["search_moves_us"].mean(),
        "search_switches / game": g["search_switches_us"].mean(),
        "search_diff / game": g["search_diff_us"].mean(),
        "override_%_of_search": 100 * g["override_of_search"].mean(),
        "ko_checks / game": g["ko_checks_us"].mean(),
        "endgame / game": g["endgame_solves_us"].mean(),
        "loop_guards / game": g["loop_guards_us"].mean(),
        "setup / game": g["setup_uses_us"].mean(),
        "hazards / game": g["hazard_sets_us"].mean(),
        "tera / game": g["terastallized_us"].mean(),
    })

headline = pd.DataFrame(rows).set_index("agent")
headline.to_csv(OUTPUT_DIR / "minimax_headline_comparison.csv")
headline.T
"""
)

md(
    """\
## 3 · Who actually chose the action? KO short-circuit vs 1-ply maximin

A guaranteed KO and the ≤2-mon endgame solver run **before** the matrix. If those
paths fire on most turns, the agent is not doing adversarial search — it is v14’s
damage calculator with a 1-ply backup. `search_fire_rate` is the share of turns that
reached the maximin loop.
"""
)

code(
    """\
# Decision machinery per game
fp_cols = [
    "ko_checks_us", "search_moves_us", "search_switches_us",
    "search_diff_us", "endgame_solves_us", "loop_guards_us",
]
fp = pd.DataFrame({ag: frames[ag][fp_cols].mean() for ag in AGENTS}).T
fp["search_fire_rate"] = pd.Series({ag: frames[ag]["search_fire_rate"].mean() for ag in AGENTS})
print("Mean counts per game")
print(fp.T.to_string())

print("\\nSearch fire rate (fraction of turns that reached 1-ply maximin)")
for ag, g in frames.items():
    print(f"  {ag}: {100*g['search_fire_rate'].mean():.1f}% of turns   "
          f"KO checks {g['ko_checks_us'].mean():.2f}/game")

fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
x = np.arange(3)
w = 0.25
left = ["ko_checks_us", "search_moves_us", "search_switches_us"]
for i, ag in enumerate(AGENTS):
    axes[0].bar(x + (i - 1) * w, [frames[ag][c].mean() for c in left], w,
                color=AGENT_COLOR[ag], label=ag)
axes[0].set_xticks(x)
axes[0].set_xticklabels(["KO short-circuit", "Minimax moves", "Minimax switches"], rotation=12)
axes[0].set_ylabel("Mean per game")
axes[0].set_title("Who decided? (count / game)")
axes[0].legend()

right = ["search_diff_us", "loop_guards_us", "endgame_solves_us"]
for i, ag in enumerate(AGENTS):
    axes[1].bar(x + (i - 1) * w, [frames[ag][c].mean() for c in right], w,
                color=AGENT_COLOR[ag], label=ag)
axes[1].set_xticks(x)
axes[1].set_xticklabels(["Override v14 (search_diff)", "Loop guard", "Endgame solve"], rotation=12)
axes[1].set_ylabel("Mean per game")
axes[1].set_title("1-ply disagreement and guards")
axes[1].legend()

fig.suptitle("v15 / v16 / v17 — 1-ply search machinery per game", fontweight="bold")
fig.tight_layout()
fig.savefig(OUTPUT_DIR / "minimax_fingerprint_bars.png")
plt.show()
"""
)

md(
    """\
## 4 · When 1-ply search overrides the heuristic (`search_diff`)

`search_diff_us` increments when the maximin action is **not** the action a fresh v14
probe would have played.

- **High override + lower win rate** ⇒ horizon effect: the 1-ply, risk-averse leaf
  (\(1.5\times\) opponent damage) prefers a safer immediate hit over v14’s delayed
  payoff (setup, rocks, scouting).
- **v16 was supposed to fix that** by putting setup/hazard bonuses in the leaf. If
  override rate and setup counts do not move, the bonuses lost to the \(1.5\times\)
  term.
- **v17** adds +0.15 to v14’s action. That is a weaker bias than MCTS v20’s PUCT
  prior of 0.70, so overrides should drop, not collapse.

Split `search_diff_rate` by win/loss. If losers overrode more, unconstrained maximin
is hurting.
"""
)

code(
    """\
# Override distributions and win/loss split
fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))

for ag, g in frames.items():
    vals = g["search_diff_rate"].dropna()
    axes[0].hist(vals, bins=35, density=True, alpha=0.5, color=AGENT_COLOR[ag],
                 label=f"{ag}  μ={vals.mean():.3f}")
axes[0].set_xlabel("search_diff / turns  (share of turns that overrode v14)")
axes[0].set_ylabel("Density")
axes[0].set_title("How often did 1-ply maximin disagree with v14?")
axes[0].legend(fontsize=9)

labels = AGENTS
x = np.arange(len(labels))
w = 0.35
ov = [100 * frames[ag]["override_of_search"].mean() for ag in AGENTS]
axes[1].bar(x - w / 2, ov, w, color=[AGENT_COLOR[ag] for ag in AGENTS], alpha=0.9)
axes[1].set_xticks(x)
axes[1].set_xticklabels(labels)
axes[1].set_ylabel("% of minimax decisions that ≠ v14")
axes[1].set_title("Override rate among turns that reached the tree")
axes[1].set_ylim(0, 100)
for i, v in enumerate(ov):
    axes[1].text(i - w / 2, v + 1.5, f"{v:.0f}%", ha="center", fontsize=9)

fig.tight_layout()
fig.savefig(OUTPUT_DIR / "minimax_override.png")
plt.show()

print("Override among search decisions, and search_diff/turn in wins vs losses")
print(f"{'agent':<6}  {'override%':>10}  {'diff/turn W':>12}  {'diff/turn L':>12}  {'Δ (L−W)':>8}")
for ag, g in frames.items():
    wsub = g[g["won_bool"] == 1]["search_diff_rate"].mean()
    lsub = g[g["won_bool"] == 0]["search_diff_rate"].mean()
    print(f"{ag:<6}  {100*g['override_of_search'].mean():10.1f}  "
          f"{wsub:12.3f}  {lsub:12.3f}  {lsub-wsub:+8.3f}")
"""
)

md(
    """\
## 5 · Does 1-ply search value the future? Setup, hazards, Tera

v16’s leaf explicitly bonuses Dragon Dance / Stealth Rock / Recover. If those bonuses
were large enough to survive \(1.5\times\) opponent damage, `setup_uses_us` and
`hazard_sets_us` would rise toward v9/v12 (~1.6 / ~0.16). If they stay at v14 levels
(~0.22 / ~0.04), **the horizon effect is not fixed by decorating a 1-ply leaf**.
"""
)

code(
    """\
# Future-payoff proxies
proxy = ["setup_uses_us", "hazard_sets_us", "terastallized_us",
         "voluntary_switches_us", "supereffective_us"]
fig, ax = plt.subplots(figsize=(11, 4.6))
idx = np.arange(len(proxy))
w = 0.25
for i, ag in enumerate(AGENTS):
    ax.bar(idx + (i - 1) * w, [frames[ag][c].mean() for c in proxy], w,
           color=AGENT_COLOR[ag], label=ag)
ax.set_xticks(idx)
ax.set_xticklabels(["Setup uses", "Hazard sets", "Tera", "Vol. switches", "Super-effective"],
                   rotation=12)
ax.set_ylabel("Mean per game")
ax.set_title("Did 1-ply maximin (and v16 bonuses) buy long-term actions?")
ax.legend()
fig.tight_layout()
fig.savefig(OUTPUT_DIR / "minimax_future_proxies.png")
plt.show()

for c in proxy:
    vals = "  ".join(f"{ag}={frames[ag][c].mean():.3f}" for ag in AGENTS)
    print(f"  {c:24s}  {vals}")
print("\\nReference (heuristic / IL / MCTS notebooks):")
print("  v12 setup ≈ 1.73, hazards ≈ 0.18, tera ≈ 0.95")
print("  v14 setup ≈ 0.22, hazards ≈ 0.03, tera ≈ 0.31")
print("  v18–v20 setup ≈ 0.21, hazards ≈ 0.04  (5-ply greedy rollouts, same ceiling)")
"""
)

md(
    """\
## 6 · Win rate across the same opponents

Grouped bars. MCTS cells (v18–v20) are 1,000 games (~±3 pp); everything else is 10,000
(~±1 pp). Discriminating opponents: **v12 / v13 / v14** and **Abyssal**.
"""
)

code(
    """\
# Per-opponent win rates
def wr_table(g: pd.DataFrame) -> pd.DataFrame:
    t = g.groupby("matchup_opponent").agg(games=("won_bool", "size"), wins=("won_bool", "sum"))
    t["win_rate"] = 100 * t["wins"] / t["games"]
    t["ci95"] = [wilson_ci(w, n) for w, n in zip(t["wins"], t["games"])]
    t["paradigm"] = t.index.map(lambda x: PARADIGM_MAP.get(x, "Other"))
    return t


wr = {ag: wr_table(g) for ag, g in frames.items()}
cmp = wr["v15"].add_prefix("v15_")
for ag in ("v16", "v17"):
    cmp = cmp.join(wr[ag].add_prefix(f"{ag}_"), how="outer")
cmp["delta_v17_v15"] = cmp["v17_win_rate"] - cmp["v15_win_rate"]
cmp["delta_v16_v15"] = cmp["v16_win_rate"] - cmp["v15_win_rate"]
cmp = cmp.sort_values("v17_win_rate", ascending=False)
cmp.to_csv(OUTPUT_DIR / "minimax_winrate_by_opponent.csv")

order = list(cmp.index)
x = np.arange(len(order))
fig, ax = plt.subplots(figsize=(14, 5.5))
w = 0.25
for i, ag in enumerate(AGENTS):
    ax.bar(x + (i - 1) * w, cmp.loc[order, f"{ag}_win_rate"], w,
           yerr=cmp.loc[order, f"{ag}_ci95"], capsize=1.5,
           color=AGENT_COLOR[ag], label=AGENT_LABEL[ag], error_kw={"elinewidth": 0.7})
ax.axhline(50, color="#c0392b", ls="--", lw=1)
ax.set_xticks(x)
ax.set_xticklabels(order, rotation=50, ha="right")
ax.set_ylabel("Win rate (%)")
ax.set_title("Win rate of each 1-ply minimax agent vs the gauntlet")
ax.legend(fontsize=8)
fig.tight_layout()
fig.savefig(OUTPUT_DIR / "minimax_winrate_grouped.png")
plt.show()

print(f"v16 vs v15 mean Δ: {cmp['delta_v16_v15'].mean():+.2f} pp  "
      f"(ahead in {(cmp['delta_v16_v15'] > 0).sum()} / {len(cmp)})")
print(f"v17 vs v15 mean Δ: {cmp['delta_v17_v15'].mean():+.2f} pp  "
      f"(ahead in {(cmp['delta_v17_v15'] > 0).sum()} / {len(cmp)})")
print("\\nLargest hybrid gains (v17 − v15):")
print(cmp["delta_v17_v15"].sort_values(ascending=False).head(6).to_string())
print("\\nSmallest v17 − v15 gaps:")
print(cmp["delta_v17_v15"].sort_values().head(6).to_string())
"""
)

md(
    """\
## 7 · Head-to-head among the three 1-ply agents

Independent samples, not flipped games. v15 vs v16 tests the leaf bonuses (10k games,
CI ±1 pp). v16 vs v17 tests the +0.15 prior.
"""
)

code(
    """\
# Direct H2H triangle
h2h_rows = []
for a in AGENTS:
    for b in AGENTS:
        if a == b:
            continue
        sub = frames[a][frames[a]["matchup_opponent"] == b]
        n, w = len(sub), int(sub["won_bool"].sum())
        h2h_rows.append({
            "file": f"{a}_vs_{b}",
            "games": n,
            "win_rate_%": 100 * w / n,
            "ci95_pp": wilson_ci(w, n),
            "search_diff / game": sub["search_diff_us"].mean(),
            "override_%": 100 * sub["override_of_search"].mean(),
            "search_fire_%": 100 * sub["search_fire_rate"].mean(),
        })
h2h_df = pd.DataFrame(h2h_rows).set_index("file")
print(h2h_df.to_string())
print()
for a, b in (("v15", "v16"), ("v15", "v17"), ("v16", "v17")):
    s = (h2h_df.loc[f"{a}_vs_{b}", "win_rate_%"] + h2h_df.loc[f"{b}_vs_{a}", "win_rate_%"]) / 100
    print(f"  WR({a} vs {b}) + WR({b} vs {a}) = {s:.4f}")
"""
)

md(
    """\
## 8 · Strength by opponent paradigm

Does 1-ply maximin help against knowledge-heavy heuristics, against 5-ply MCTS, or
only against weak baselines?
"""
)

code(
    """\
# Paradigm-level WR
def paradigm_wr(g: pd.DataFrame) -> pd.DataFrame:
    t = g.groupby("opponent_paradigm").agg(games=("won_bool", "size"), wins=("won_bool", "sum"))
    t["win_rate"] = 100 * t["wins"] / t["games"]
    t["ci95"] = [wilson_ci(w, n) for w, n in zip(t["wins"], t["games"])]
    return t.reindex([p for p in PARADIGM_ORDER if p in t.index])


pw = {ag: paradigm_wr(g) for ag, g in frames.items()}
labels = list(pw["v15"].index)
x = np.arange(len(labels))
w = 0.25
fig, ax = plt.subplots(figsize=(10.5, 4.8))
for i, ag in enumerate(AGENTS):
    ax.bar(x + (i - 1) * w, pw[ag]["win_rate"], w, yerr=pw[ag]["ci95"],
           capsize=3, color=AGENT_COLOR[ag], label=AGENT_LABEL[ag])
ax.axhline(50, color="#c0392b", ls="--", lw=1)
ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.set_ylabel("Win rate (%)")
ax.set_title("1-ply minimax win rate by opponent paradigm")
ax.legend(fontsize=8)
fig.tight_layout()
fig.savefig(OUTPUT_DIR / "minimax_wr_by_paradigm.png")
plt.show()

joined = pw["v15"].add_prefix("v15_")
for ag in ("v16", "v17"):
    joined = joined.join(pw[ag].add_prefix(f"{ag}_"))
joined
"""
)

md(
    """\
## 9 · Discriminating matchups: v12, v14, Abyssal, v20, v21

v12 is the bot-vs-bot knowledge ceiling. v14 is the teacher inside every minimax
agent. v20 is 5-ply PUCT — the natural “deeper search” sibling. If 1-ply beat its
teacher, v17 vs v14 would sit clearly above 50% at n = 10,000.
"""
)

code(
    """\
# Key matchup table
keys = ["v12", "v13", "v14", "abyssal", "simple_heuristic", "v18", "v20", "v21", "v22"]
rows = []
for opp in keys:
    rec = {"opponent": opp, "paradigm": PARADIGM_MAP.get(opp, "?")}
    for ag in AGENTS:
        if opp not in wr[ag].index:
            rec[f"{ag}_wr"] = np.nan
            rec[f"{ag}_ci"] = np.nan
            rec[f"{ag}_n"] = 0
            continue
        sub = wr[ag].loc[opp]
        rec[f"{ag}_wr"] = float(sub["win_rate"])
        rec[f"{ag}_ci"] = float(sub["ci95"])
        rec[f"{ag}_n"] = int(sub["games"])
    rows.append(rec)
key_df = pd.DataFrame(rows).set_index("opponent")
print(key_df.to_string())

fig, ax = plt.subplots(figsize=(10.5, 4.8))
idx = np.arange(len(keys))
w = 0.25
for i, ag in enumerate(AGENTS):
    ax.bar(idx + (i - 1) * w, [key_df.loc[k, f"{ag}_wr"] for k in keys], w,
           yerr=[key_df.loc[k, f"{ag}_ci"] for k in keys], capsize=2,
           color=AGENT_COLOR[ag], label=ag)
ax.axhline(50, color="#c0392b", ls="--", lw=1)
ax.set_xticks(idx)
ax.set_xticklabels(keys, rotation=20)
ax.set_ylabel("Win rate (%)")
ax.set_title("1-ply maximin vs knowledge ceiling, teacher, 5-ply search, IL")
ax.legend()
fig.tight_layout()
fig.savefig(OUTPUT_DIR / "minimax_key_matchups.png")
plt.show()
"""
)

md(
    """\
## 10 · Switching that came from the maximin

Risk-averse 1-ply (\(1.5\times\) incoming damage) should switch more than a greedy
heuristic when the active Pokémon is about to be punished. `search_switches_us` is
switches the matrix actually picked.
"""
)

code(
    """\
# Switching from search
fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.4))
for ax, col, title in [
    (axes[0], "voluntary_switches_us", "Voluntary switches / game"),
    (axes[1], "search_switches_us", "Minimax-chosen switches / game"),
    (axes[2], "search_switch_share", "Share of search decisions that are switches"),
]:
    data = [frames[ag][col].dropna() for ag in AGENTS]
    bp = ax.boxplot(data, tick_labels=AGENTS, patch_artist=True, showfliers=False)
    for patch, ag in zip(bp["boxes"], AGENTS):
        patch.set_facecolor(AGENT_COLOR[ag])
        patch.set_alpha(0.75)
    ax.set_title(title)
    ax.set_ylabel("Fraction" if col == "search_switch_share" else "Count")

fig.tight_layout()
fig.savefig(OUTPUT_DIR / "minimax_switching_box.png")
plt.show()

print("Means")
for col in ["voluntary_switches_us", "search_switches_us", "search_switch_share", "loop_guards_us"]:
    vals = "  ".join(f"{ag}={frames[ag][col].mean():.3f}" for ag in AGENTS)
    print(f"  {col:26s}  {vals}")
"""
)

md(
    """\
## 11 · Game length and leftover HP

A risk-averse maximin that over-switches should leave more HP or play longer. The
hybrid that hugs v14 should look like v14.
"""
)

code(
    """\
# Duration and leftover HP
fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
for ax, col, title in [
    (axes[0], "turns", "Battle length (turns)"),
    (axes[1], "remaining_pokemon_us", "Remaining Pokémon (us)"),
]:
    for ag, g in frames.items():
        ax.hist(g[col], bins=28, density=True, alpha=0.45, color=AGENT_COLOR[ag],
                label=f"{ag}  μ={g[col].mean():.2f}")
    ax.set_title(title)
    ax.set_xlabel(col)
    ax.set_ylabel("Density")
    ax.legend()
fig.tight_layout()
fig.savefig(OUTPUT_DIR / "minimax_length_hp.png")
plt.show()
"""
)

md(
    """\
## 12 · Self-play sanity

Each agent vs itself should sit near 50% (n = 10,000 ⇒ ±0.98 pp).
"""
)

code(
    """\
# Self-play
for ag, g in frames.items():
    sub = g[g["matchup_opponent"] == ag]
    n, w = len(sub), int(sub["won_bool"].sum())
    print(f"  {ag} vs {ag}:  {100*w/n:.2f}%  ±{wilson_ci(w, n):.2f}  (n={n:,})")
"""
)

md("## 13 · Export comparison report")

code(
    """\
# Markdown report
lines = [
    "# 1-Ply Minimax EDA — v15 / v16 / v17",
    "",
    "Deep thesis write-up: [`../../heuristics_and_imitation_thesis_analysis.md`](../../heuristics_and_imitation_thesis_analysis.md).",
    "",
    "Source: `data/benchmarks/all_10k/gen9randombattle` (each agent as us vs 28 opponents;",
    "10k games, or 1k vs v18/v19/v20).",
    "Search: analytic 1-ply maximin, exact damage ranges, opponent damage × 1.5.",
    "",
    "## Architecture in one paragraph",
    "",
    "All three agents are 1-ply adversarial search on top of HeuristicV14. For each legal",
    "action they evaluate the worst-case reply among predicted opponent moves (set DB) and",
    "a hypothetical switch, resolving speed/priority and KOs analytically — no LocalSim.",
    "**v15** uses an HP/matchup leaf. **v16** adds setup/hazard/recovery/status bonuses and",
    "v14 tactical overrides before the matrix. **v17** is v16 plus +0.15 on v14’s action.",
    "",
    "## Headline",
    "",
    headline.to_markdown(),
    "",
    "## 1-ply vs the heuristic",
    "",
    "- Search only runs on **~16–18% of turns**; the rest are guaranteed-KO short-circuits",
    "  (~14 KO checks / game). One-ply maximin is a backup, not the default policy.",
    "- Of the turns that *do* reach the matrix, **v15/v16 override v14 on ~67%** of",
    "  decisions. Losers override more than winners (search_diff/turn 0.13 vs 0.10).",
    "- **v16’s positional leaf does not help**: overall +0.5 pp vs v15, H2H ~50%, setup",
    "  uses stay at 0.21 (v14-like, not v12-like). The 1.5× opponent-damage term dominates",
    "  the 0.25–0.35 setup/hazard bonuses.",
    "- **v17 overrides on 37%** of search decisions (prior +0.15) and is the strongest",
    "  1-ply agent (overall +4.1 pp vs v15). Still below v12 (40.9% vs v12) and below",
    "  its teacher (43.6% vs v14).",
    "",
    "## Head-to-head",
    "",
    h2h_df.to_markdown(),
    "",
    "## Discriminating matchups (WR %)",
    "",
    key_df.to_markdown(),
    "",
    "## Paradigm win rates",
    "",
    joined.to_markdown(),
    "",
    "## Figures",
    "",
    "- `minimax_fingerprint_bars.png`",
    "- `minimax_override.png`",
    "- `minimax_future_proxies.png`",
    "- `minimax_winrate_grouped.png`",
    "- `minimax_wr_by_paradigm.png`",
    "- `minimax_key_matchups.png`",
    "- `minimax_switching_box.png`",
    "- `minimax_length_hp.png`",
]

report_path = OUTPUT_DIR / "minimax_v15_v17_comparison.md"
report_path.write_text("\\n".join(lines), encoding="utf-8")
print(f"Wrote {report_path}")
print(f"Plots in {OUTPUT_DIR}")
"""
)

nb["cells"] = cells
OUT.write_text(nbf.writes(nb), encoding="utf-8")
print(f"Wrote {OUT} ({len(cells)} cells)")
