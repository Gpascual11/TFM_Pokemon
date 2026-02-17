# TFM: Pokémon Battle AI Research Environment

This project focuses on developing and benchmarking Heuristic and Reinforcement Learning agents for Pokémon Showdown. The environment uses a local Node.js server for high-speed, parallel battle simulations.

## Prerequisites

* **Node.js** (v18+ recommended)
* **Python** (3.10+ recommended)
* **uv** (High-performance Python package manager)

---

## Installation & Setup

### 1. Clone the Game Engine

We use the official Pokémon Showdown server as the local engine.

```bash
git clone https://github.com/smogon/pokemon-showdown.git
cd pokemon-showdown
npm install

```

### 2. Configure the High-Performance Server

To utilize the 22 threads of the **Intel Core Ultra 7 155H**, we modified `config/config.js` (copied from `config-example.js`).

**Key modifications in `config.js`:**

* Set `exports.workerprocesses = 14;` (Increases battle simulation workers).
* Adjusted `exports.subprocesses` for networking and simulation:
* `network: 4`
* `simulator: 14`


* Set `exports.loginserver = null;` to allow offline/local bot authentication.

### 3. Setup Python Environment

We use `uv` for lightning-fast dependency management and environment isolation.

```bash
cd .. # Back to your TFM root
uv init
uv add poke-env pandas tqdm tabulate

```

---

## Project Structure

* `pokemon-showdown/`: The Node.js game engine.
* `data/`: CSV exports of battle results.
* `src/testing/`:
* `test_heuristic_v3.py`: Main script for mass simulations (10k+ games).
* `test_env.py`: Simple connectivity test.



---

## Running Simulations

### Step 1: Start the Engine

Always start the Node.js server first. The `--no-security` flag is used for local high-speed bot communication.

```bash
cd pokemon-showdown
node pokemon-showdown start --no-security

```

### Step 2: Execute the AI Agents

Run the research scripts using `uv`.

```bash
# To run a 10,000 game simulation with CSV export
uv run src/testing/test_heuristic_v3.py

```

---

## Methodology (TFM Context)

The project treats Pokémon battles as a **Partially Observable Markov Decision Process (POMDP)**.

### Heuristic Logic

Our current agent (`TFMResearchAgent`) utilizes:

1. **Physical/Special Split**: Dynamically calculates damage based on  vs  ratios.
2. **Status Awareness**: Accounts for **Burn** (Attack reduction) and **Paralysis** (Speed reduction).
3. **Strategic Switching**: Implements logic for **Toxic resetting** and defensive retreats based on speed tiers.

### Data Collection

Simulations are run in batches of 500 games with **20 concurrent threads**, logging:

* `battle_id`
* `winner`
* `turns`
* `won` (Boolean)

---

## Troubleshooting

* **"Name Taken" Error**: Restart the Node.js server to clear "zombie" bot sessions.
* **Memory Issues**: Ensure `player.reset_battles()` is called in Python after every batch to clear RAM.