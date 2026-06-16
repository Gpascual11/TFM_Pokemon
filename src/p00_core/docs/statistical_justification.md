# Statistical Justification: 10,000 Games Per Matchup

## Why 10,000 Games?

Each battle in Pokémon random battles has a **binary outcome** (win or lose). The precision of our win rate estimate depends only on the number of games played, not on the size of the Pokémon pool or the complexity of the generation.

### Confidence Interval Formula

For a proportion (win rate) `p` estimated from `n` games:

```
95% CI = p ± 1.96 × sqrt(p × (1-p) / n)
```

At **n = 10,000** games with the worst-case variance (p = 0.5):

```
CI = ± 1.96 × sqrt(0.25 / 10000) = ± 0.98%
```

This means any observed win rate is accurate to within **±1 percentage point** at 95% confidence.

---

## Detectable Differences

| Difference to detect | Minimum games needed | 10k sufficient? |
|---------------------|---------------------|-----------------|
| 1% (e.g., 50% vs 51%) | 19,600 | No |
| 2% (e.g., 50% vs 52%) | 4,900 | Yes |
| 3% (e.g., 50% vs 53%) | 2,178 | Yes |
| 5% (e.g., 50% vs 55%) | 784 | Yes |
| 10%+ (e.g., 30% vs 50%) | 196 | Yes |

For our research, the relevant comparisons are:
- **V7/V8 vs baselines**: Expected gaps of 10-20% → easily detectable at 1,000 games.
- **Between heuristic versions** (e.g., V4 vs V5): Expected gaps of 3-10% → detectable at 5,000 games.
- **V1 vs V2 vs V3** (~1% differences): Confirms they are statistically equivalent, which is itself a valid finding.

---

## Why Pool Size Doesn't Affect Sample Requirements

### Intuition vs Reality

It seems logical that Gen 1 (151 Pokémon) would need fewer games than Gen 9 (1,025 Pokémon) because there's "less randomness." However:

| Generation | Pokémon Pool | Possible Teams C(n,6) |
|-----------|-------------|----------------------|
| Gen 1 | 151 | ~14.9 billion |
| Gen 5 | 649 | ~1.2 × 10^13 |
| Gen 9 | 1,025 | ~1.6 × 10^15 |

Even Gen 1's team space (14.9 billion combinations) is astronomically larger than our 10,000 sample size. We never come close to "covering" the space in any generation.

### The Mathematical Argument

The variance of a win rate estimate is:

```
Var(p̂) = p(1-p) / n
```

This formula contains:
- `p` — the true win rate (bounded between 0 and 1)
- `n` — the number of games played

It does **not** contain:
- Number of Pokémon in the pool
- Number of possible moves, items, or abilities
- Complexity of the generation's mechanics

The per-game outcome is always binary (1 or 0), so the variance is always bounded by 0.25 regardless of how the game's internal randomness works.

---

## Practical Validation

### Sources of Variance in Random Battles

1. **Team composition luck** — which Pokémon each player receives
2. **In-battle RNG** — critical hits, misses, secondary effects (30% burn, 10% flinch)
3. **Speed ties** — 50/50 coin flip when speeds are equal
4. **Damage rolls** — ±15% random multiplier on every attack

All of these average out over large samples. The key insight: we don't need to model these individually. The binary outcome (win/lose) captures their net effect, and the Central Limit Theorem guarantees convergence.

### Empirical Confirmation

From our existing 10k-game benchmarks:
- Matchups with large true differences (e.g., any agent vs `random` at ~95% WR) show virtually zero variance between runs.
- Matchups near 50% (e.g., V1 vs V3) show observed differences of 0.5-1.5%, consistent with the theoretical ±0.98% noise floor.

---

## Comparison With Other Sample Sizes

| Games per matchup | 95% CI width | Detects differences ≥ | Total compute (14 agents × 14 opp × 9 gens) |
|---|---|---|---|
| 1,000 | ± 3.10% | 6% | 1.76M games |
| 2,000 | ± 2.19% | 4.4% | 3.53M games |
| 5,000 | ± 1.39% | 2.8% | 8.82M games |
| **10,000** | **± 0.98%** | **2.0%** | **17.64M games** |
| 20,000 | ± 0.69% | 1.4% | 35.28M games |

**10,000 games** is the sweet spot: it detects all meaningful differences (≥2%) while remaining computationally feasible with our parallel benchmark infrastructure.

---

## Diagnostic vs Benchmark: Choosing Sample Size

During development, we use tiered sample sizes depending on the goal:

### Phase 1: Smoke Test (100 games per matchup)

- **Purpose**: Verify code correctness — no crashes, new features fire, win rate isn't catastrophically broken.
- **CI width**: ±10% at 95% confidence.
- **What it CAN tell you**: Agent doesn't crash; win rate is roughly in expected range (e.g., >40% vs Tier 2).
- **What it CANNOT tell you**: Whether a 6% improvement is real or noise.
- **When to use**: After creating a new agent version. Quick feedback loop (~5 min runtime).

### Phase 2: Validation (1,000 games per matchup)

- **Purpose**: Confirm win rate trends with moderate confidence.
- **CI width**: ±3.1% at 95% confidence.
- **Detects**: Differences ≥6% reliably.
- **When to use**: After smoke test passes. Confirms the agent's new features help (or at least don't hurt). Sufficient to compare against Tier 1 (Abyssal, SimpleHeuristic) where expected gaps are 5-15%.

### Phase 3: Full Benchmark (10,000 games per matchup)

- **Purpose**: Definitive statistical measurement for thesis results.
- **CI width**: ±0.98% at 95% confidence.
- **Detects**: Differences ≥2% reliably.
- **When to use**: Final evaluation of all agents across all generations for publication.

### Why 100 Games Is Not Enough for Conclusions

Random battles introduce high per-game variance from team composition. Example:

```
True win rate: 50%
100 games observed: 55%
95% CI: [45%, 65%]
```

The observed 55% is statistically indistinguishable from 45%. At 1,000 games:

```
True win rate: 50%
1000 games observed: 53%
95% CI: [49.9%, 56.1%]
```

Now a 53% result is distinguishable from 47% — meaningful for detecting improvements.

---

## Conclusion

- **10,000 games per matchup** provides ±0.98% precision at 95% confidence.
- **Same sample size across all generations** ensures uniform methodology and comparable results.
- **No adjustment needed** for pool size, mechanics complexity, or generation-specific factors.
- The only scenario where 10k is insufficient is distinguishing agents within ~1% of each other (e.g., V1 vs V2), but those agents being equivalent is itself a valid research finding.
- **For development**: Use 100 games (smoke test) → 1,000 games (validation) → 10,000 games (final benchmark) as a progression.
