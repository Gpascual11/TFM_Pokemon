# s02_doubles — Unified Doubles Heuristics & Agents Benchmark

This directory provides a state-of-the-art framework for implementing, benchmarking, and analyzing Pokémon Double Battle (2v2) agents. It builds upon the robustness of the Singles framework while introducing advanced logic specifically for the Generation 9 VGC format.

The system is designed to handle the exponential complexity of Doubles (where 2 Pokémon are active per side) by using a **Score-then-Combine** architecture and a high-performance **Master-Worker** execution engine.

---

## 🏗️ Technical Architecture

The module is divided into four core pillars, each designed for maximum modularity and scalability.

### 1. 🧠 Agents & Heuristics (The Thinking Core)

Doubles requires significantly more complex logic than Singles due to move targets, spread moves, and ally synergies. Our agents are categorized into:

#### Internal Heuristics (Evolutionary Path)

- **V1 (Greedy Damage)**: Acts as the base baseline. It calculates the highest damage move for each slot independently. It uses a very simple "choose the target I hit hardest" logic.
- **V2 (Conservative Switcher)**: Extends V1 by introducing a defensive switch-out mechanism. If a Pokémon faces a major type disadvantage (e.g., a Water-type facing 2 Electric-types), it evaluates its teammates and swaps to a safer option. This significantly improves longevity.
- **V6 (Environmental Master)**: Our most advanced rule-based agent. It incorporates weather effects (Sun/Rain), Terrain boosts (Electric/Grassy), and move priority. It values "Extreme Speed" or "Fake Out" more highly in specific turns to snag KOs before the opponent moves.

#### Baselines (Comparative Standards)

- **Abyssal Player**: A port of the famous PokéChamp heuristic. It uses complex matchup estimation and stat tracking.
- **Safe One-Step**: A greedy lookahead player that pre-calculates the best move/target pair for each slot.
- **Random**: The absolute baseline to ensure all other agents are actually "learning" or "thinking".

#### LLM Agents (Generative Strategy)

- **Pokellmon**: Uses Large Language Models to interpret the battle state and select moves using Chain-of-Thought reasoning.
- **Pokechamp LLM**: A variant specialized in double-battle-specific move targets.

### 2. ⚙️ Evaluation Engine (The Performance Driver)

Benchmarking Doubles is computationally expensive. To handle this, we use a custom orchestrator:

- **Master-Worker Pattern**: A central `benchmark.py` script manages the queue of games. It spawns independent `worker.py` subprocesses.
- **Port Concurrency**: The orchestrator can run multiple Pokémon Showdown servers simultaneously on different ports. Each worker is assigned a port, allowing for massive parallelization.
- **Memory Safety**: Pokémon Showdown and some Python libraries are prone to RAM leaks. Our engine automatically terminates workers and restarts servers every X games (default 25) to keep the memory footprint low.
- **Progress Persistence**: Results are written to temporary CSVs throughout the run. If a crash occurs, the system detects the existing `data/benchmarks_doubles_unified/` files and resumes precisely where it left off.

### 3. 🦙 Ollama Integration (Local LLM Serving)

For LLM benchmarking (`benchmark_llm.py`), we rely on **Ollama** for local model serving. This ensures privacy, zero cost per token, and high speed.

#### How to Install Ollama

1. **Linux**: Run `curl -fsSL https://ollama.com/install.sh | sh`
2. **Verify Execution**: Run `ollama list`. You should see your models (e.g., `llama3`, `mistral`).
3. **Pull Model**: Run `ollama pull llama3` (or the model specified in your agent config).

#### Why multiple ports?

While it is impossible to run a single LLM request across multiple ports simultaneously, we use multiple ports to **balance the game server load**. The LLM itself usually runs on a single inference server (Ollama), but the *workers* that wait for the LLM to respond are parallelized. This prevents the game engine from bottlenecking while the LLM "thinks".

### 4. 📊 Analysis & Reporting

- **Heatmaps**: A dedicated script in `evaluation/reporting/heatmaps.py` takes the CSV results and generates a visual grid of Win/Loss rates.
- **Decision Logs**: Every LLM turn is logged into a `.txt` file. These logs contain the input prompt, the "thinking" process, and the final decision, which is crucial for debugging why an LLM made a specific play.

---

## ⚔️ Quick Start Guide

### 1. Prerequisites

Ensure you have the environment set up:

```bash
# Install dependencies
uv sync
# Ensure Showdown is available
# (Usually included in the root /pokemon-showdown directory)
```

### 2. Running a Standard Benchmark

To compare `v1` and `v2` agents over 500 battles using 6 CPU cores:

```bash
uv run src/p01_heuristics/s02_doubles/evaluation/engine/benchmark.py 500 --ports 6
```

*Tip: If the RAM usage is too high, decrease `--ports` to 2 or 3.*

### 3. Running an LLM Matchup

Make sure Ollama is running (`systemctl start ollama` or just run the app).

```bash
uv run src/p01_heuristics/s02_doubles/evaluation/engine/benchmark_llm.py 50
```

This will generate:

- A results CSV.
- Thinking logs for every turn in `results/LLM/`.

---

## 📘 Detailed Logic Breakdown

### The "Score-then-Combine" Pattern

In Doubles, simply choosing the best move for Slot A and the best move for Slot B often leads to illegal moves (e.g., both slots trying to switch to the same benched Pokémon).

Our `BaseHeuristic2v2` uses this logic:

1. **Generate All Pairs**: It uses `DoubleBattleOrder.join_orders` to create a list of all *legal* combinations of actions.
2. **Scoring**: It calls `_score_order` for Slot A and Slot B separately.
3. **Summation**: Total Utility = Score(A) + Score(B).
4. **Selection**: The pair with the highest Total Utility is selected.

### Target Selection Logic

Unlike Singles, every move in Doubles needs a target index:

- `1` or `2`: Target specific opponent slot.
- `0`: Spread move (e.g., Earthquake, Rock Slide).
- `-1` or `-2`: Target ally slot (usually penalized by heuristics).

Our heuristics automatically evaluate the effectiveness of a move against *both* possible targets and pick the one that results in the highest score.

---

## 🛠️ Troubleshooting

### "ModuleNotFoundError: No module named 'poke_env'"

This usually happens if the `pokechamp` fork is not in your path. The benchmark scripts automatically attempt to inject the path:

```python
_POKECHAMP_ROOT = _SRC.parent / "pokechamp"
sys.path.insert(0, str(_POKECHAMP_ROOT))
```

Ensure that the `pokechamp` directory exists alongside your main project directory.

### RAM Crashing

If your system crashes during a benchmark:

1. Reduce the number of `--ports`.
2. Increase the `--games_per_batch` (this reduces the frequency of process overhead).
3. Monitor with `htop` to see if the `node pokemon-showdown` processes are over-consuming.

### Ollama Connection Issues

If `benchmark_llm.py` fails to connect:

- Check `curl http://localhost:11434/api/tags`.
- If it returns an error, Ollama is not running.

---

## ✨ Future Roadmap

- [ ] Integration of "Protean" and "Libero" ability awareness.
- [ ] Support for "Tera" transformations in the heuristic scoring.
- [ ] Dynamic weight adjustment for LLM prompts based on battle stage.

*This framework is a core component of the TFM project aimed at exploring the limits of heuristic vs generative AI in complex strategic environments.*
