#!/usr/bin/env python3
"""Re-run notebooks that still need a current-data pass.

Writes a self-contained snapshot to src/p00_core/reporting/reruns/ and a
RESULTS.md that explains every artefact.

What is re-run here (needed, not persisted as a current-data snapshot):
  - eda_online_bot.ipynb          live v14 ladder (431 games; CSV path had moved)
  - eda_tournament.ipynb          gen9 28-agent Elo / Tera (taxonomy-correct)
  - the four family EDAs          already computed this morning; re-export into reruns/

Not re-run:
  - analysis.ipynb                legacy v3-vs-v2 helper, not the gauntlet
  - dataset_integrity_verification.ipynb  already scanned the 784-file matrix
"""
from __future__ import annotations

import io
import re
import sys
import traceback
import warnings
from contextlib import redirect_stdout
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import nbformat
import numpy as np
import pandas as pd
import seaborn as sns

warnings.filterwarnings("ignore")

ROOT = Path("/home/sirp/Documents/MUDS/TFM_Pokemon")
REPORTING = ROOT / "src/p00_core/reporting"
RERUNS = REPORTING / "reruns"
BENCHMARK = ROOT / "data/benchmarks/all_10k/gen9randombattle"
LADDER_CSV = ROOT / "data/testing/logs/logs_v14_online/battle_history.csv"

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
PARADIGM_COLOR = {
    "Baseline": "#7f7f7f",
    "Heuristic": "#1f77b4",
    "Minimax": "#d62728",
    "MCTS": "#ff7f0e",
    "IL Hybrid": "#9467bd",
    "IL Pure": "#2ca02c",
}


def wilson_ci(wins: float, n: float, z: float = 1.96) -> float:
    if n <= 0:
        return 0.0
    p = wins / n
    denom = 1.0 + z * z / n
    margin = z * np.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / denom
    return float(margin * 100)


def exec_notebook(nb_path: Path, output_dir: Path, extra_ns: dict | None = None) -> str:
    """Execute code cells in-process. Redirect OUTPUT_DIR and capture stdout."""
    output_dir.mkdir(parents=True, exist_ok=True)
    nb = nbformat.read(nb_path, as_version=4)
    ns = {"__name__": "__main__"}
    if extra_ns:
        ns.update(extra_ns)
    log = io.StringIO()
    fig_i = [0]
    orig_savefig = plt.savefig
    orig_show = plt.show

    def savefig_both(*args, **kwargs):
        orig_savefig(*args, **kwargs)
        # also dump a numbered copy into the snapshot folder
        fig_i[0] += 1
        dest = output_dir / f"fig_{fig_i[0]:02d}.png"
        try:
            orig_savefig(dest, dpi=160, bbox_inches="tight")
        except Exception:
            pass

    def show_and_save(*args, **kwargs):
        fig_i[0] += 1
        dest = output_dir / f"fig_{fig_i[0]:02d}.png"
        try:
            orig_savefig(dest, dpi=160, bbox_inches="tight")
        except Exception:
            pass
        plt.close("all")

    plt.savefig = savefig_both
    plt.show = show_and_save

    with redirect_stdout(log):
        for i, cell in enumerate(nb.cells):
            if cell.cell_type != "code":
                continue
            src = cell.source if isinstance(cell.source, str) else "".join(cell.source)
            src = re.sub(
                r'OUTPUT_DIR = ROOT / "src/p00_core/reporting/agents/[^"]+"',
                f'OUTPUT_DIR = Path(r"{output_dir}")',
                src,
            )
            src = src.replace('plt.savefig(\'live_ladder_evolution.png\')',
                              f'plt.savefig(r"{output_dir / "live_ladder_evolution.png"}")')
            try:
                exec(compile(src, f"{nb_path.name}:cell{i}", "exec"), ns)
            except Exception:
                print(f"\nFAILED {nb_path.name} cell {i}", file=sys.stderr)
                traceback.print_exc()
                plt.savefig = orig_savefig
                plt.show = orig_show
                raise
            if "OUTPUT_DIR" in ns:
                ns["OUTPUT_DIR"] = output_dir
                Path(output_dir).mkdir(parents=True, exist_ok=True)

    plt.savefig = orig_savefig
    plt.show = orig_show
    text = log.getvalue()
    (output_dir / "stdout.log").write_text(text, encoding="utf-8")
    return text


def run_online_bot(out: Path) -> dict:
    """Full v14 ladder pass. Does not rely on the notebook's single savefig."""
    out.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid")
    df = pd.read_csv(LADDER_CSV)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    n = len(df)
    wins = int(df["won"].sum())
    wr = 100 * wins / n
    ci = wilson_ci(wins, n)
    active = df[df["turns"] >= 10].copy()
    n_act = len(active)
    w_act = int(active["won"].sum())
    wr_act = 100 * w_act / n_act if n_act else 0
    ci_act = wilson_ci(w_act, n_act)

    rated = df[pd.to_numeric(df.get("rating_us"), errors="coerce").notna()].copy()
    rated["rating_us"] = pd.to_numeric(rated["rating_us"], errors="coerce")
    rated["rating_opp"] = pd.to_numeric(rated.get("rating_opp"), errors="coerce")
    elo_start = float(rated["rating_us"].iloc[0]) if len(rated) else None
    elo_end = float(rated["rating_us"].iloc[-1]) if len(rated) else None
    elo_max = float(rated["rating_us"].max()) if len(rated) else None
    elo_min = float(rated["rating_us"].min()) if len(rated) else None

    df["cum_wins"] = df["won"].cumsum()
    df["cum_games"] = np.arange(1, n + 1)
    df["running_wr"] = df["cum_wins"] / df["cum_games"]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    axes[0].plot(df["cum_games"], 100 * df["running_wr"], color="#1A7A6D", lw=2)
    axes[0].axhline(wr, color="#c0392b", ls="--", label=f"final {wr:.1f}%")
    axes[0].set_xlabel("Game number")
    axes[0].set_ylabel("Win rate (%)")
    axes[0].set_title("v14 ladder — running win rate")
    axes[0].legend()
    if len(rated):
        axes[1].plot(range(1, len(rated) + 1), rated["rating_us"], color="#E76F51", lw=2, label="v14 Elo")
        if rated["rating_opp"].notna().any():
            axes[1].plot(range(1, len(rated) + 1), rated["rating_opp"], color="#3D5A80",
                         alpha=0.35, label="opponent Elo")
        axes[1].set_ylabel("Elo")
        axes[1].set_xlabel("Rated game")
        axes[1].set_title("v14 ladder — Elo")
        axes[1].legend()
    fig.tight_layout()
    fig.savefig(out / "ladder_wr_elo.png", dpi=160)
    plt.close()

    # Wins vs losses: strategy / health
    def by_outcome(frame, cols):
        g = frame.groupby("won")[cols].mean()
        g.index = g.index.map({0: "loss", 1: "win"})
        return g

    health_cols = [c for c in ["fainted_us", "fainted_opp", "hp_perc_us", "hp_perc_opp", "turns"] if c in active.columns]
    switch_cols = [c for c in ["voluntary_switches_us", "forced_switches_us",
                               "voluntary_switches_opp", "matchup_switches_us"] if c in active.columns]
    strat_cols = [c for c in ["hazard_sets_us", "setup_uses_us", "ko_checks_us",
                              "terastallized_us", "fallback_moves_us"] if c in active.columns]
    rng_cols = [c for c in ["crit_us", "crit_opp", "miss_us", "miss_opp",
                            "supereffective_us", "supereffective_opp"] if c in active.columns]

    health = by_outcome(active, health_cols) if health_cols else pd.DataFrame()
    switches = by_outcome(active, switch_cols) if switch_cols else pd.DataFrame()
    strat = by_outcome(active, strat_cols) if strat_cols else pd.DataFrame()
    rng = by_outcome(active, rng_cols) if rng_cols else pd.DataFrame()

    for name, table in [("health", health), ("switches", switches), ("strategy", strat), ("rng", rng)]:
        if not table.empty:
            table.to_csv(out / f"ladder_{name}_by_outcome.csv")

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.4))
    for ax, table, title in [
        (axes[0], health, "Health / length"),
        (axes[1], switches, "Switching"),
        (axes[2], strat, "v14 tactics"),
    ]:
        if table.empty:
            ax.set_visible(False)
            continue
        table.T.plot(kind="bar", ax=ax, color=["#9B2226", "#2A9D8F"], rot=25, legend=True)
        ax.set_title(title)
        ax.set_ylabel("Mean per game")
    fig.tight_layout()
    fig.savefig(out / "ladder_win_vs_loss.png", dpi=160)
    plt.close()

    tera_wr = None
    if "terastallized_us" in active.columns:
        tera = pd.crosstab(active["terastallized_us"] > 0, active.get("terastallized_opp", 0) > 0,
                           values=active["won"], aggfunc=["mean", "count"])
        tera.to_csv(out / "ladder_tera_crosstab.csv")
        tera_wr = float(active.loc[active["terastallized_us"] > 0, "won"].mean() * 100) if (active["terastallized_us"] > 0).any() else None
        tera_n = int((active["terastallized_us"] > 0).sum())
    else:
        tera_n = 0

    headline = pd.DataFrame([{
        "games_raw": n,
        "wins_raw": wins,
        "win_rate_%": wr,
        "ci95_pp": ci,
        "games_turns_ge10": n_act,
        "win_rate_turns_ge10_%": wr_act,
        "ci95_turns_ge10_pp": ci_act,
        "short_games_turns_lt10": n - n_act,
        "elo_start": elo_start,
        "elo_end": elo_end,
        "elo_min": elo_min,
        "elo_max": elo_max,
        "mean_turns_active": float(active["turns"].mean()) if n_act else None,
        "tera_games": tera_n,
        "tera_wr_%": tera_wr,
        "fallback_us_total": int(df["fallback_moves_us"].sum()) if "fallback_moves_us" in df.columns else 0,
        "error_us_total": int(df["error_moves_us"].sum()) if "error_moves_us" in df.columns else 0,
        "ko_checks_mean": float(active["ko_checks_us"].mean()) if "ko_checks_us" in active.columns else None,
        "setup_mean": float(active["setup_uses_us"].mean()) if "setup_uses_us" in active.columns else None,
        "vol_switches_mean": float(active["voluntary_switches_us"].mean()) if "voluntary_switches_us" in active.columns else None,
        "first_timestamp": str(df["timestamp"].min()),
        "last_timestamp": str(df["timestamp"].max()),
        "csv": str(LADDER_CSV),
    }])
    headline.to_csv(out / "ladder_headline.csv", index=False)

    md = [
        "# v14 live ladder (re-run)",
        "",
        f"Source: `{LADDER_CSV.relative_to(ROOT)}`.",
        f"**{n} games**, {wins} wins → **{wr:.2f}% ± {ci:.1f} pp** (Wilson 95%).",
        f"Games with ≥10 turns: **{n_act}**, WR **{wr_act:.2f}%** (the raw number includes {n-n_act} short games, mostly opponent forfeits that inflate WR).",
        "",
        f"Elo: {elo_start:.0f} → {elo_end:.0f} (min {elo_min:.0f}, max {elo_max:.0f})." if elo_start is not None else "Elo: not recorded.",
        "",
        "This is **not** comparable to the 253k bot-vs-bot overall WR. Humans bluff; v14 was built for that and still sits below 50% on the public ladder.",
        "",
        "## Headline",
        "",
        headline.to_markdown(index=False),
        "",
        "## Win vs loss (active games)",
        "",
        "### Health",
        health.to_markdown() if not health.empty else "(none)",
        "",
        "### Switching",
        switches.to_markdown() if not switches.empty else "(none)",
        "",
        "### Tactics",
        strat.to_markdown() if not strat.empty else "(none)",
        "",
        "### RNG",
        rng.to_markdown() if not rng.empty else "(none)",
        "",
        "## Figures",
        "",
        "- `ladder_wr_elo.png`",
        "- `ladder_win_vs_loss.png`",
    ]
    (out / "ladder_report.md").write_text("\n".join(md), encoding="utf-8")
    return headline.iloc[0].to_dict()


def run_tournament_gen9(out: Path) -> pd.DataFrame:
    out.mkdir(parents=True, exist_ok=True)
    files = sorted(BENCHMARK.glob("*.csv"))
    files = [f for f in files if not f.name.startswith("_") and "elo" not in f.name and "matchup" not in f.name]
    cols = ["heuristic", "opponent", "won", "turns", "terastallized_us"]
    chunks = []
    for path in files:
        df = pd.read_csv(path, usecols=lambda c: c in cols)
        g = df.groupby(["heuristic", "opponent"], as_index=False).agg(
            games=("won", "size"), wins=("won", "sum"),
            turns=("turns", "sum"), tera=("terastallized_us", "sum"),
        )
        chunks.append(g)
    agg = pd.concat(chunks, ignore_index=True)
    agg = agg.groupby(["heuristic", "opponent"], as_index=False).sum()
    agg["win_rate"] = agg["wins"] / agg["games"]
    agg["paradigm"] = agg["heuristic"].map(lambda x: PARADIGM_MAP.get(x, "Other"))
    agg.to_csv(out / "gen9_matchup_summary.csv", index=False)

    # Bradley-Terry
    agents = sorted(set(agg["heuristic"]).union(set(agg["opponent"])))
    idx = {a: i for i, a in enumerate(agents)}
    n_a = len(agents)
    W = np.zeros((n_a, n_a))
    N = np.zeros((n_a, n_a))
    for _, row in agg.iterrows():
        u, o = idx[row["heuristic"]], idx[row["opponent"]]
        W[u, o] += row["wins"]
        N[u, o] += row["games"]
        W[o, u] += row["games"] - row["wins"]
        N[o, u] += row["games"]
    pi = np.ones(n_a)
    for _ in range(400):
        pi_old = pi.copy()
        for i in range(n_a):
            denom = 0.0
            for j in range(n_a):
                if N[i, j] > 0:
                    denom += N[i, j] / (pi[i] + pi[j])
            if denom > 0:
                pi[i] = np.sum(W[i, :]) / denom
        pi /= np.mean(pi)
        if np.max(np.abs(pi - pi_old)) < 1e-6:
            break
    elo = 400 * np.log10(np.clip(pi, 1e-12, None))
    if "random" in idx:
        elo += 1000 - elo[idx["random"]]
    elo_df = pd.DataFrame({
        "agent": agents,
        "paradigm": [PARADIGM_MAP.get(a, "Other") for a in agents],
        "Elo": elo,
        "wins": W.sum(axis=1),
        "games": N.sum(axis=1),
    }).sort_values("Elo", ascending=False)
    elo_df.to_csv(out / "gen9_bradley_terry_elo.csv", index=False)

    fig, ax = plt.subplots(figsize=(12, 6.2))
    colors = [PARADIGM_COLOR.get(p, "#333") for p in elo_df["paradigm"]]
    ax.bar(range(len(elo_df)), elo_df["Elo"], color=colors)
    ax.set_xticks(range(len(elo_df)))
    ax.set_xticklabels(elo_df["agent"], rotation=90)
    ax.set_ylabel("Bradley-Terry Elo (random = 1000)")
    ax.set_title("gen9randombattle gauntlet — Bradley-Terry Elo\nMCTS v18–v20 cells are n=1k; everyone else n=10k")
    handles = [plt.Rectangle((0, 0), 1, 1, color=PARADIGM_COLOR[p], label=p) for p in PARADIGM_ORDER]
    ax.legend(handles=handles, ncol=3, fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "gen9_elo_bars.png", dpi=160)
    plt.close()

    # overall WR as us
    overall = agg.groupby("heuristic", as_index=False).agg(games=("games", "sum"), wins=("wins", "sum"))
    overall["win_rate_%"] = 100 * overall["wins"] / overall["games"]
    overall["paradigm"] = overall["heuristic"].map(lambda x: PARADIGM_MAP.get(x, "Other"))
    overall = overall.sort_values("win_rate_%", ascending=False)
    overall.to_csv(out / "gen9_overall_wr.csv", index=False)

    md = [
        "# gen9 tournament snapshot (re-run)",
        "",
        "Directed 28×28 gauntlet. Taxonomy: v1–v14 heuristic, v15–v17 1-ply minimax,",
        "v18–v20 IS-MCTS (n=1k), v21 hybrid IL, v22 pure IL.",
        "",
        "## Bradley-Terry Elo (anchor random = 1000)",
        "",
        elo_df.to_markdown(index=False),
        "",
        "## Overall gauntlet WR (as us)",
        "",
        overall.to_markdown(index=False),
    ]
    (out / "tournament_report.md").write_text("\n".join(md), encoding="utf-8")
    return elo_df


def main():
    RERUNS.mkdir(parents=True, exist_ok=True)
    print(f"Snapshot folder: {RERUNS}")

    print("\n=== 1/6  v14 live ladder ===")
    ladder = run_online_bot(RERUNS / "online_bot")
    print(f"  {int(ladder['games_raw'])} games  WR {ladder['win_rate_%']:.2f}%  Elo {ladder['elo_start']:.0f}→{ladder['elo_end']:.0f}")
    print("  also executing eda_online_bot.ipynb cells…")
    exec_notebook(REPORTING / "eda_online_bot.ipynb", RERUNS / "online_bot" / "notebook_exec")

    families = [
        ("heuristics", "eda_heuristics_v1_v14.ipynb"),
        ("minimax", "eda_minimax_v15_v17.ipynb"),
        ("mcts", "eda_mcts_v18_v20.ipynb"),
        ("il", "eda_imitation_v21_v22.ipynb"),
    ]
    for i, (name, nb) in enumerate(families, start=2):
        print(f"\n=== {i}/6  {nb} → reruns/{name} ===")
        exec_notebook(REPORTING / nb, RERUNS / name)

    print("\n=== 6/6  gen9 tournament Elo ===")
    elo_df = run_tournament_gen9(RERUNS / "tournament_gen9")
    print(elo_df.head(8).to_string(index=False))

    # ── RESULTS.md ──────────────────────────────────────────────────────────
    heur = pd.read_csv(RERUNS / "heuristics" / "heur_headline_comparison.csv")
    mm = pd.read_csv(RERUNS / "minimax" / "minimax_headline_comparison.csv")
    mcts = pd.read_csv(RERUNS / "mcts" / "mcts_headline_comparison.csv")
    il = pd.read_csv(RERUNS / "il" / "il_headline_comparison.csv")
    overall = pd.read_csv(RERUNS / "tournament_gen9" / "gen9_overall_wr.csv")

    def wr_line(df, name_col, wr_col="win_rate_%"):
        parts = []
        for _, r in df.iterrows():
            label = r[name_col] if name_col in r else r.iloc[0]
            parts.append(f"{label} {r[wr_col]:.2f}%")
        return "; ".join(parts)

    results = f"""# Current-data re-run — results

This folder is a **separate snapshot** of every notebook that still needed a pass
on the current files. It does **not** replace `agents/il_v21_v22/`, `agents/minimax_v15_v17/`,
`agents/mcts_v18_v20/`, or `agents/heuristics_v1_v14/` (those already held this morning’s
gauntlet figures). It also does **not** replace the stale `agents/v1/` … `v14/` executive
reports — those still mislabel v17 as MCTS and v19–v20 as IL. Do not cite them.

Date of this snapshot: 2026-08-13.
Gauntlet: `data/benchmarks/all_10k/gen9randombattle` (10k games / matchup; **1k** if either
side is v18/v19/v20).
Ladder: `data/testing/logs/logs_v14_online/battle_history.csv`.

Taxonomy used everywhere below:

| IDs | Paradigm |
|---|---|
| v1–v14 | Heuristic ladder |
| v15–v17 | 1-ply minimax (analytic, no LocalSim) |
| v18–v20 | IS-MCTS (n = 1,000) |
| v21 | IL hybrid (XGB + v14) |
| v22 | IL pure (two XGBs, no v14) |

---

## 1. What was re-run, and why

| Notebook | Why it needed a current-data pass | This snapshot |
|---|---|---|
| `eda_online_bot.ipynb` | CSV had moved; markdown still talked about 100 games; only one figure was saved to CWD | `reruns/online_bot/` |
| `eda_heuristics_v1_v14.ipynb` | Rebuilt as a 14-agent ladder; `.ipynb` had empty outputs | `reruns/heuristics/` |
| `eda_minimax_v15_v17.ipynb` | Same: analysis existed, notebook outputs empty | `reruns/minimax/` |
| `eda_mcts_v18_v20.ipynb` | Same | `reruns/mcts/` |
| `eda_imitation_v21_v22.ipynb` | Same | `reruns/il/` |
| gen9 tournament Elo (from `eda_tournament.ipynb` logic) | Old embedded plots; titles said “heuristic” for v15–v22 | `reruns/tournament_gen9/` |

Not re-run: `analysis.ipynb` (legacy v3 vs v2 file) and `dataset_integrity_verification.ipynb`
(already verified the 784-file matrix).

---

## 2. v14 vs humans (the notebook that was actually stale)

**{int(ladder['games_raw'])} live `gen9randombattle` games**, username `SirPThesis`.

| | Value |
|---|---|
| Raw win rate | **{ladder['win_rate_%']:.2f}% ± {ladder['ci95_pp']:.1f} pp** ({int(ladder['wins_raw'])}/{int(ladder['games_raw'])}) |
| Turns ≥ 10 only | **{ladder['win_rate_turns_ge10_%']:.2f}%** (n = {int(ladder['games_turns_ge10'])}) |
| Short games (turns < 10) | {int(ladder['short_games_turns_lt10'])} — mostly opponent forfeits; they **inflate** the raw WR |
| Elo | {ladder['elo_start']:.0f} → **{ladder['elo_end']:.0f}** (range {ladder['elo_min']:.0f}–{ladder['elo_max']:.0f}) |
| Errors | {int(ladder['error_us_total'])} (should be 0) |
| Fallbacks | {int(ladder['fallback_us_total'])} total |
| Window | {ladder['first_timestamp']} → {ladder['last_timestamp']} |

The June 2026 thesis-plan figure (98 games, 40.8%, Elo ~1151) is a **prefix** of this log,
not a different experiment. With 431 games the point estimate is **{ladder['win_rate_%']:.1f}%**,
still a below-average public-ladder player, still a meaningful human baseline.

**How to use this number.** Bot-vs-bot said v14 is third (62% gauntlet, 51% vs Abyssal)
and v12 is first (69% / 60%). The ladder does **not** let you invert that ranking.
v14 was built to scout and profile humans; this sample only says that design is not
yet 50% vs the public ladder. It does not say v12 would do better online.

Figures: `online_bot/ladder_wr_elo.png`, `online_bot/ladder_win_vs_loss.png`.
Tables: `online_bot/ladder_headline.csv` and `*_by_outcome.csv`.

---

## 3. Heuristic ladder (v1–v14)

Gauntlet-weighted overall WR, 253,000 games each:

{heur.to_markdown(index=False)}

Three jumps, then an inversion:

- Plateau v1–v6 ≈ 44–46%. Extra damage math does not win Random Battles.
- v7 ≈ 54% (+9 pp): hazards, KO, matchup switching.
- v9 / v11 ≈ 59%: setup only on free turns.
- **v12 = 69.0%**: Tera + preview + fainted switch-in. First internal agent to beat Abyssal (59.9%).
- **v12 ≥ v13 > v14** (69.0 / 67.6 / 62.0). Genealogy said the opposite. H2H at 10k:
  v12 vs v13 is a coin flip (50.7 / 48.9); v14 loses to both.

`setup_uses_us` / `hazard_sets_us` are 0 for v7/v8/v10 — schema gap, not “they never set rocks”.

---

## 4. 1-ply minimax (v15–v17)

{mm.to_markdown(index=False)}

Search fires on ~16–18% of turns (KO short-circuit is the rest). Unconstrained maximin
(v15/v16) overrides v14 on **~67%** of those turns; v16’s setup/hazard leaf bonuses do
not raise setup uses (~0.21, v14-like). The +0.15 v14 prior (**v17**) is the only 1-ply
upgrade that moves WR. v17 still loses to v14 (43.6%) and to v12 (40.9%) at n = 10k.

---

## 5. IS-MCTS (v18–v20)

All cells n = 1,000. Do not mix this 28k overall WR with the 253k heuristic/minimax/IL overall.

{mcts.to_markdown(index=False)}

Same KO backup (~16–18% search). UCB1 (v18/v19) overrides v14 on **~71%** of tree
decisions; losers override more (horizon effect). A richer leaf (v19) does nothing.
PUCT with a v14 prior (**v20**) is the only 5-ply upgrade — by disagreeing less (~19%
override), not by seeing further. Setup/hazards stay v14-like. v20 vs v12 is 42.7%;
vs v14 is 47.0%.

---

## 6. Imitation learning (v21–v22)

{il.to_markdown(index=False)}

Same XGBoost macro, same τ = 0.5525. v21 keeps v14’s KO/endgame and only asks XGB on
**15%** of turns (WR 58.7%, ≈ v9/v11). v22 is the clone with no v14: XGB on 80% of
turns, zero KO guards, loop guards in 97% of games, WR **33.5%** (below v1). v21 beats
v22 28/28 matchups. Hybrid IL is a competent mid-heuristic; pure cloning is not.

---

## 7. Cross-paradigm ranking (gen9, as us)

Bradley-Terry Elo (anchor `random` = 1000) and gauntlet WR live in
`tournament_gen9/`. Top of the Elo list should be v12 / v13 / v14, then the hybrids
that keep v14 (v20, v21, v17). Unconstrained search and pure IL sit with the mid/low
heuristics.

Overall WR as *us* (MCTS rows are 28k equally weighted opponents; others 253k with
MCTS underweighted — compare matchup cells, not these two overalls, when ranking v20
against v11):

{overall.head(16).to_markdown(index=False)}

The hierarchical moral is the same three times: the residual that **trusts v14**
(v17, v20, v21) is the only variant that moves; the residual that **replaces v14**
(v15/v16, v18/v19, v22) overrides more and wins less. None of them beat v12.

---

## 8. Folder map

```
reruns/
  RESULTS.md                          ← this file
  online_bot/                         ← live ladder
  heuristics/                         ← v1–v14 comparative ladder
  minimax/                            ← v15–v17
  mcts/                               ← v18–v20
  il/                                 ← v21–v22
  tournament_gen9/                    ← Elo + overall WR
```

Deep thesis write-up (argument, not just tables):
`src/p00_core/reporting/heuristics_and_imitation_thesis_analysis.md`.
"""

    (RERUNS / "RESULTS.md").write_text(results, encoding="utf-8")
    print(f"\nWrote {RERUNS / 'RESULTS.md'}")
    print("done")


if __name__ == "__main__":
    main()
