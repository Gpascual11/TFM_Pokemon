# RL Data Analysis Summary — Doubles Heuristics (run 460184)

## Dataset Overview

- **Total battles**: 2,000 (v1 vs v2, both sides logged)
- **Total turn rows**: 213,493 (state-action pairs)
- **Mean battle length**: 17.62 turns (median: 17, std: 5.80)

## Battle Outcomes

### Overall Win Distribution
- **"us" wins**: 1,017 (50.85%)
- **"opp" wins**: 983 (49.15%)

The data is nearly balanced, indicating both heuristics are competitive against each other.

### Heuristic Performance Comparison

| Heuristic | Wins | Total Battles | Win Rate | Mean Turns |
|-----------|------|---------------|----------|------------|
| **v1** | 496 | 1,000 | 49.60% | 17.70 |
| **v2** | 521 | 1,000 | 52.10% | 17.54 |

**Key findings:**
- **v2 has a slight edge**: 2.5% higher win rate (52.10% vs 49.60%)
- **v2 finishes slightly faster**: Mean 17.54 turns vs 17.70 turns
- The difference is small but consistent, suggesting v2's joint-action coordination provides a measurable advantage

## Action Distribution

### Overall Actions
- **Move decisions**: 54,142 (25.4%)
- **Switch decisions**: 159,351 (74.6%)

**Observation**: Switches dominate (~3:1 ratio), which is expected in doubles format where:
- Forced switches occur frequently
- Defensive switching is common
- Both slots may switch in the same turn

### Heuristic Action Patterns
- **v1**: 103,776 turn rows
- **v2**: 109,717 turn rows

v2 generates slightly more turn rows, possibly due to:
- More complex decision-making
- Different coordination patterns
- Slightly longer battles on average

## Move Usage Analysis

### Top 10 Most Used Moves

| Move | Count | Percentage of Move Decisions |
|------|-------|-------------------------------|
| **protect** | 2,870 | 5.3% |
| **knockoff** | 2,378 | 4.4% |
| **closecombat** | 1,423 | 2.6% |
| **thunderbolt** | 1,373 | 2.5% |
| **highhorsepower** | 1,369 | 2.5% |
| **psychic** | 1,263 | 2.3% |
| **bodypress** | 1,160 | 2.1% |
| **thunderwave** | 1,007 | 1.9% |
| **earthpower** | 972 | 1.8% |
| **shadowball** | 944 | 1.7% |

**Insights:**
- **Protect** is the most common move (5.3%), reflecting its defensive value in doubles
- **Knock Off** is second, showing item disruption is highly valued
- High-damage moves (Close Combat, Thunderbolt, High Horsepower) are common
- Status moves (Thunder Wave) appear in top 10, showing status control is important

## Damage and Type Effectiveness

### Estimated Damage Statistics
- **Mean estimated damage**: 122.85 HP
- **Median estimated damage**: 93.18 HP
- **Distribution**: Right-skewed (mean > median), indicating some very high-damage moves

### Type Multiplier Distribution

| Multiplier | Count | Interpretation |
|------------|-------|----------------|
| **1.00** (neutral) | 29,963 | 55.4% |
| **0.50** (resisted) | 10,509 | 19.4% |
| **2.00** (super effective) | 7,131 | 13.2% |
| **0.00** (immune) | 2,258 | 4.2% |
| **0.25** (double resisted) | 1,088 | 2.0% |
| **4.00** (double super effective) | 488 | 0.9% |

**Mean type multiplier**: 1.01 (essentially neutral on average)

**Key observations:**
- **55% of moves are neutral** (1.0x), showing heuristics don't always prioritize type advantage
- **13% are super effective** (2.0x), indicating type targeting when available
- **19% are resisted** (0.5x), showing some moves are used despite type disadvantage (possibly for coverage or status)
- **4% are immune** (0.0x), likely status moves or mis-targeted attacks

## State Feature Distributions

### Turn Distribution
- Mean: ~17.6 turns per battle
- Range: Battles typically last 10-30 turns
- Standard deviation: 5.80 turns

### Remaining Pokémon
- Both sides start with 6 Pokémon
- Distribution shows gradual reduction as battles progress
- Data captures mid-battle states effectively

### HP Fractions
- Active Pokémon HP fractions range from 0.0 (fainted) to 1.0 (full HP)
- Distribution captures various battle states
- Low HP states trigger defensive switches (Protect, switching)

## Implications for RL Training

### 1. **State Space**
- **28 features per turn** (state + action + outcome)
- Rich representation including:
  - Active species/types (both slots)
  - HP fractions
  - Weather/terrain
  - Remaining team size
  - Turn number

### 2. **Action Space**
- **361 unique move IDs** observed
- **Move vs Switch** binary decision
- **Target selection** (1 or 2 for moves)
- Action space is manageable for RL

### 3. **Reward Signals**
- **Battle outcome** (win/loss/draw) available
- **Estimated damage** can serve as dense reward signal
- **Type multiplier** indicates decision quality
- **Turn count** can be used for efficiency rewards

### 4. **Training Data Quality**
- **213K+ state-action pairs** from 2,000 battles
- Balanced win distribution (good for learning)
- Both heuristics represented equally
- Rich damage/type information for auxiliary tasks

### 5. **Key Patterns to Learn**
- **Protect usage**: Critical defensive move (5.3% of moves)
- **Type targeting**: 13% super-effective moves show type awareness
- **Switching frequency**: 74.6% switches indicate defensive play is common
- **Damage optimization**: Mean 122.85 damage suggests heuristics prioritize high-damage moves

## Recommendations for RL Training

1. **Use estimated damage as auxiliary reward**: The damage estimates correlate with move quality
2. **Type multiplier as feature**: Include type multiplier in state representation
3. **Balance move vs switch**: Model should learn when to attack vs switch (currently 25% vs 75%)
4. **Protect as special action**: High frequency suggests it's a key defensive tool
5. **Learn from both heuristics**: v1 and v2 provide complementary strategies
6. **Dense rewards**: Use turn-level damage estimates + battle outcome for better learning signal

## Additional Insights

### Win Rate by Battle Length

| Battle Length | Win Rate (%) | Count |
|---------------|--------------|-------|
| <10 turns | 48.67% | 113 |
| 10-15 turns | 47.98% | 694 |
| 15-20 turns | 51.47% | 715 |
| 20-25 turns | 52.61% | 306 |
| 25+ turns | 58.14% | 172 |

**Finding**: Longer battles favor "us" (the heuristic making decisions). This suggests:
- Better heuristics can outlast opponents in extended battles
- Endgame positioning and resource management matter
- v2's coordination may shine in longer, more complex scenarios

### Damage by Type Multiplier

| Type Multiplier | Mean Damage | Count |
|----------------|-------------|-------|
| 0.00 (immune) | 0.00 | 2,258 |
| 0.25 (double resisted) | 30.36 | 1,088 |
| 0.50 (resisted) | 59.96 | 10,509 |
| 1.00 (neutral) | 117.73 | 29,963 |
| 2.00 (super effective) | 265.19 | 7,131 |
| 4.00 (double super) | 485.95 | 488 |

**Key insight**: Type effectiveness dramatically impacts damage:
- **Super effective moves (2.0x) deal 2.25x more damage** than neutral (265 vs 118)
- **Double super effective (4.0x) deals 4.1x more** (486 vs 118)
- This validates that type targeting is crucial for high damage output

### Switch Frequency by Turn

| Turn | Switch Frequency (%) |
|------|---------------------|
| 1 | 26.7% |
| 2-5 | ~35% |
| 6 | 58.1% |
| 7 | 34.1% |
| 8 | 49.3% |
| 9 | 76.4% |
| 10 | 79.1% |

**Patterns observed**:
- **Early turns (1-5)**: Lower switch rate (~27-35%), heuristics prefer attacking
- **Mid-game (6-8)**: Variable switch rate, likely responding to threats/KOs
- **Late game (9+)**: Very high switch rate (76-79%), frequent forced switches as Pokémon faint

This pattern suggests:
- Early game is more aggressive (establishing position)
- Mid-game involves tactical switching
- Late game is dominated by forced switches and defensive play

## Next Steps

1. **Expand dataset**: Run more games (10K+) for better coverage
2. **Feature engineering**: Create derived features (e.g., "threat level", "type advantage score")
3. **Action encoding**: Map move IDs to categorical or embedding space
4. **Reward shaping**: Design reward function using damage + type multiplier + outcome
5. **Baseline comparison**: Train RL agent and compare against v1/v2 win rates
6. **Temporal patterns**: Model turn-dependent behavior (early aggression vs late defense)
7. **Type effectiveness learning**: Use type multiplier as auxiliary task to improve type awareness
