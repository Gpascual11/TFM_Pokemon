# 🤖 Doubles Baselines — Standard Opponents

This directory contains standardized heuristic players used for benchmarking the performance of experimental internal models.

## 📋 Included Agents

### 1. `SafeOneStepDoublesPlayer` (`safe_one_step_doubles.py`)

A robust 1-step lookahead agent that calculates damage proxies for each slot independently. It avoids complex simulation to ensure high throughput during testing.

### 2. `VGCDoublesPlayer` (`vgc_doubles.py`)

A specialized expert agent that builds upon the V6 field-awareness logic. It adds competitive VGC priorities:

- High priority for speed control moves (Tailwind, Icy Wind).
- Preference for spread damage to bypass potential Protect stalls.

### 3. External Baselines (via `poke_env`)

- **Random**: Completely non-deterministic action selection.
- **Max Power**: Always selects the move with the highest base power.
- **Abyssal**: A well-known rule-based baseline.
- **Simple Heuristic**: The standard heuristic provided by the `poke_env` library.
