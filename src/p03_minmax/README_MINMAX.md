# Adversarial search (1-ply minimax)

Agents: `v15`, `v16`, `v17` in `src/p03_minmax/agents/internal/`.

## Method

All three inherit `HeuristicV14` and, after KO / endgame shortcuts, run **1-ply maximin**: score each of our legal actions against predicted opponent replies this turn, pick the best worst case.

Opponent replies are **revealed** moves (plus a generic `"switch"`). Damage vs opponent HP uses an absolute formula together with poke-env’s percentage HP for foes.

- **v15:** 1-ply + HP-style leaf.
- **v16:** 1-ply; leaf includes more v14-style bonuses (setup / hazards / recovery).
- **v17:** 1-ply with a v14 action prior.

Gauntlet: **10,000** games per directed matchup on gen9randombattle (1,000 vs v18–v20). See the 28-agent matrix.

Canonical write-up: [`../p00_core/reporting/heuristics_and_imitation_thesis_analysis.md`](../p00_core/reporting/heuristics_and_imitation_thesis_analysis.md).
