# Pokechamp Benchmark — Development Notes & Usage Guide

## What is Pokechamp?

[**PokéChamp**](https://github.com/sethkarten/pokechamp) is an expert-level Pokémon battle AI from the paper *"PokéChamp: an Expert-level Minimax Language Agent"* (ICML '25). It combines LLM reasoning with minimax search to play competitive Pokémon battles on [Pokémon Showdown](https://pokemonshowdown.com).

The repo bundles its own fork of `poke_env` (the Python library for interacting with Showdown) and provides several agent types:

| Agent | Type | Description |
|-------|------|-------------|
| `pokechamp` | LLM | Full minimax + LLM agent (the paper's main contribution) |
| `pokellmon` | LLM | Alternative LLM-based agent |
| `abyssal` | Rule-based | Heuristic baseline using type effectiveness and team analysis |
| `max_power` | Rule-based | Always picks the highest base power move |
| `one_step` | Rule-based | One-step lookahead heuristic |
| `random` | Rule-based | Picks moves uniformly at random |

---

## Local LLM Setup (Ollama)

To run the LLM agents (`pokechamp`, `pokellmon`) locally without relying on expensive APIs, we use **Ollama**.

### 1. Installation
Install Ollama on Linux using the official script:
```sh
curl -fsSL https://ollama.com/install.sh | sh
```

### 2. Model Selection: Qwen 3 (8B)
We chose **Qwen 3 (8B)** as our primary local backend for several reasons:
- **Optimization (RTX 2080):** At ~6GB-8GB VRAM usage, the entire 8B model fits into the 8GB VRAM of an RTX 2080, ensuring fast inference.
- **Reasoning:** Qwen 3 (released in 2025) significantly improved over Qwen 2.5 in instruction following and "Chain of Thought" reasoning, which is critical for parsing the complex battle state in Pokémon.
- **Efficiency:** Larger models (13B-14B+) trigger memory swapping on 8GB cards, making each battle turn take minutes instead of seconds.

Pull the model before running benchmarks:
```sh
ollama pull qwen3:8b
```

### 3. Monitoring Performance
When running LLM battles, you can monitor your GPU health:
```sh
watch -n 1 nvidia-smi
```
*Expected for RTX 2080:* ~6.5GB VRAM usage, ~90% GPU load, and ~60-70°C temperature. This is normal behavior during the AI's "thinking" phase.

---

### Cloning the repo

The pokechamp repo must be cloned **inside** the project root as a sibling directory:

```sh
cd ~/TFM
git clone git@github.com:sethkarten/pokechamp.git
```

Expected directory structure:
```
TFM/
├── pokechamp/           ← cloned repo (bundled poke_env fork)
├── src/
│   └── p01_heuristics/
│       └── s01_singles/
│           ├── benchmark.py
│           ├── _worker.py
│           └── POKECHAMP_BENCHMARK.md
└── pyproject.toml
```

---

## Overview

The **`benchmark.py`** script runs a 1-vs-1 tournament between **Pokechamp AI agents** and **internal heuristic opponents** (v1–v6 plus `poke_env` baselines). It produces per-matchup CSVs, a master summary CSV, and a human-readable win-rate matrix.

### Architecture

```
benchmark.py (orchestrator)
  └── spawns → _worker.py (subprocess per batch)
                 ├── Creates players
                 ├── Runs N battles
                 ├── Writes temp CSV
                 └── Exits → OS reclaims ALL memory
```

Each mini-batch runs in a **separate Python process**. When the worker exits, the OS reclaims all memory. This is the only reliable way to prevent pokechamp's `POKE_LOOP` background thread from leaking memory.

### Tournament Matrix

| **Rows (Players)** | **Columns (Opponents)** |
|---------------------|--------------------------|
| `pokechamp` (LLM)   | `v1` through `v6` (user heuristics) |
| `pokellmon` (LLM)    | `random` (baseline) |
| `abyssal` (rule-based) | `max_power` (baseline) |
| `max_power` (rule-based) | `simple_heuristic` (baseline → mapped to `AbyssalPlayer`) |
| `one_step` (rule-based) | |
| `random` (rule-based) | |

---

## Errors Encountered & Solutions

### Phase 1: Getting it to connect

#### 1. `ModuleNotFoundError: No module named 'torch'`

**Cause:** Pokechamp's bundled `poke_env` has an eager import chain:
```
poke_env.player.baselines → local_simulation → pokechamp.llama_player → torch, transformers
```
Even importing `poke_env` for simple baseline players triggers `torch` and `transformers` imports.

**Solution:** Added both packages to `pyproject.toml` under the `pokechamp` optional dependency group. `torch` resolves to CPU-only via the existing `[tool.uv.sources]` pointing to the `pytorch-cpu` index.

---

#### 2. `ImportError: cannot import name 'SimpleHeuristicsPlayer'`

**Cause:** Pokechamp's **bundled fork** of `poke_env` does not include `SimpleHeuristicsPlayer`. Both players must share the same `Player` base class for `battle_against()` to work.

**Solution:** Replaced with `AbyssalPlayer` from pokechamp's baselines — both are rule-based heuristic opponents. The `simple_heuristic` name is preserved in the CLI/output.

---

#### 3. WebSocket Connection Timeout (`TimeoutError`)

**Cause:** Pokechamp's `ps_client.py` builds URLs by **prepending** `ws://` and **appending** `/showdown/websocket`. Passing a full URL caused double-prefixing. Using `127.0.0.1` instead of `localhost` triggered the online (TLS) URL path.

**Solution:** Pass just `"localhost:PORT"` as `server_url`:
```python
server_config = ServerConfiguration(f"localhost:{port}", None)
```

---

#### 4. Both Players Must Share the Same `ServerConfiguration`

**Cause:** `get_llm_player()` defaults to `LocalhostServerConfiguration` (with an auth URL to `play.pokemonshowdown.com`). Different `ServerConfiguration` between players caused connection failures.

**Solution:** Rule-based agents (`random`, `max_power`, `abyssal`, `one_step`) are instantiated directly with the shared `ServerConfiguration`. Only LLM agents use `get_llm_player`.

---

#### 5. `FileNotFoundError: 'poke_env/data/static/gen9/ou/sets_1500.json'`

**Cause:** Pokechamp uses **relative paths** for data files. They only resolve from the pokechamp repo root.

**Solution:** Worker subprocess calls `os.chdir(_POKECHAMP_ROOT)` before running battles. Output CSV paths are resolved to absolute before passing to the worker.

---

#### 6. `Your name must be 18 characters or shorter`

**Cause:** Showdown enforces 18-char usernames. `"Oppsimpleheuristic14260"` (23 chars) was too long.

**Solution:** `_SHORT_NAMES` abbreviation map: `simple_heuristic` → `SH`, `max_power` → `MP`, etc. Usernames are now like `OpSH802`, `PCRD5640`.

---

#### 7. `OneStepPlayer` hang (no traceback, 100% CPU)

**Cause:** `OneStepPlayer` uses `LocalSim` and `pokechamp.prompts.get_number_turns_faint` / `get_status_num_turns_fnt`, which rely on cached data (e.g. `gen9pokedex.json`, `gen9randombattle` moves set). When those files are missing, the cache returns empty dicts; the sim/prompt path can then block or spin (e.g. in damage/stat lookups or opponent-move enumeration) with no Python exception.

**Solution:** The benchmark uses **`SafeOneStepPlayer`** instead of pokechamp's `OneStepPlayer` for the `one_step` agent. `SafeOneStepPlayer` (see `safe_one_step_player.py`) does a 1-step lookahead using only `poke_env`: it scores moves by `base_power * STAB * type effectiveness * accuracy` and picks the best damaging move, with no LocalSim or prompts. No extra ML/data dependencies.

---

### Phase 2: Fixing RAM crashes at scale

#### 8. RAM explosion after ~50 battles (in-process approach)

**Cause:** Pokechamp's `POKE_LOOP` background thread retains references to player objects even after `del` + `gc.collect()`. With 1000+ games in a single process, battle state accumulates unboundedly.

**First attempt (failed):** Recreate players every 50 games within the same process. Failed because `POKE_LOOP` never releases references.

**Final solution:** **Subprocess isolation** — each mini-batch runs in a completely separate Python process (`_worker.py`). When the worker process exits, the OS reclaims *everything*. The orchestrator merges partial CSVs afterwards.

```
Batch 1: spawn worker → 50 battles → write CSV → exit (RAM freed)
Batch 2: spawn worker → 50 battles → write CSV → exit (RAM freed)
...
Merge all CSVs → final result
```

---

## Files

| File | Purpose |
|------|---------|
| [`benchmark.py`](benchmark.py) | Main orchestrator — spawns workers, merges CSVs, produces summary |
| [`_worker.py`](_worker.py) | Subprocess worker — runs N battles, writes CSV, exits |
| [`pyproject.toml`](../../../pyproject.toml) | Added `torch`, `transformers` to `pokechamp` dep group |
#### 9. Showdown server hangs after ~150–200 games

**Cause:** Each Pokémon Showdown battle spawns a `room-battle.js` Node.js worker process that **never gets freed**. After 3 matchups of 50 games each (~150 battles), the server's Node.js heap fills up. CPU drops to near zero, RAM keeps climbing, and all new battle requests stall.

**Symptom:** v1, v2, v3 complete fine; v4 (the 4th matchup) hangs indefinitely at batch start.

**Solution:** Replaced `--no-restart` with `--restart-every N` (default 3). The script now automatically kills and restarts the Showdown server every N completed matchups, flushing all accumulated worker processes.

```python
should_restart = (
    args.restart_every > 0
    and matchup_count > 0
    and matchup_count % args.restart_every == 0
)
if should_restart:
    restart_servers(len(ports_list))
```

---

#### 10. `HeuristicV4` — `GenData.from_gen(9)` dead code (bonus fix)

**Cause:** `v4.__init__` called `GenData.from_gen(9)` and stored the result in `self.dm`, but **`self.dm` was never referenced anywhere** in the class — pure dead code from an earlier draft. Loading it consumed ~7 GB of RAM on every v4 player instantiation.

**Solution:** Removed the `GenData` import and the `__init__` method entirely from v4.

---


---

## Usage

### Prerequisites

1. **Install dependencies:**
   ```sh
   uv sync --extra pokechamp
   ```

2. **Start the Pokémon Showdown server** (in a separate terminal):
   ```sh
   bash src/p03_scripts/p03_launch_custom_servers.sh 1
   ```
   Wait until you see `📡 Port 8000: READY`.

### Running the Benchmark

#### 100 games, all rule-based agents (recommended first run)

```sh
uv run python src/p01_heuristics/s01_singles/pokechamp/benchmark.py 100 \
  -p 8000 \
  --pokechamp-agents random max_power abyssal one_step
```

#### 1000 games (RAM-safe with subprocess batching)

```sh
uv run python src/p01_heuristics/s01_singles/pokechamp/benchmark.py 1000 \
  -p 8000 \
  --pokechamp-agents random max_power abyssal one_step \
  --batch-size 50 --restart-every 3
```

#### Resume an interrupted run

```sh
uv run python src/p01_heuristics/s01_singles/pokechamp/benchmark.py 1000 \
  -p 8000 --resume
```

#### Fresh start (clear old data first)

```sh
rm -rf data/benchmarks_pokechamp_v4/
uv run python src/p01_heuristics/s01_singles/pokechamp/benchmark.py 100 \
  -p 8000 \
  --pokechamp-agents random max_power abyssal one_step
```

### CLI Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `total_games` | *(required)* | Number of games per matchup |
| `-p / --ports` | `8000` | Server port(s) |
| `--pokechamp-agents` | all 6 | Which pokechamp agents to benchmark |
| `--batch-size` | `50` | Games per subprocess batch (lower = less RAM, more overhead) |
| `--player_backend` | `ollama/qwen3:8b` | LLM backend (only for `pokechamp`/`pokellmon`) |
| `--player_prompt_algo` | `io` | Prompt algorithm for LLM agents |
| `--battle-format` | `gen9randombattle` | Battle format |
| `--temperature` | `0.3` | LLM temperature |
| `--resume` | `false` | Skip completed matchups (uses checkpoint + CSVs) |
| `--restart-every` | `3` | Restart Showdown server every N matchups (0 = never restart) |
| `--data-dir` | `data/benchmarks_pokechamp` | Directory for per-matchup CSVs |
| `--output-csv` | `results/pokechamp_benchmark_summary.csv` | Master summary CSV path |
| `--log-dir` | `./battle_log/pokechamp_benchmark` | Pokechamp battle log directory |

### Output

1. **Per-matchup CSVs** in `data/benchmarks_pokechamp/` — one file per agent-vs-opponent pair
2. **Master summary CSV** at `results/pokechamp_benchmark_summary.csv`
3. **Win-rate matrix** printed to terminal
4. **Checkpoint file** (`checkpoint_pokechamp.json`) for resuming interrupted runs

### Tips

- **Start small** (e.g., `5` games) to validate your setup before large benchmarks.
- **`--restart-every 3`** (the default) restarts the Showdown server every 3 matchups. Lower it to 1 if you still see hangs; set to 0 to disable entirely.
- **Batch size trade-off:** batch size 50 = safe RAM, batch size 100 = faster but more RAM per batch.
- **LLM agents** (`pokechamp`, `pokellmon`) require the Ollama service to be running and the model (`qwen3:8b`) to be pulled.
- **Use `--resume`** to safely re-run after crashes — completed matchups are skipped.
- **Light Debugging:** Use `benchmark_light.py` to test a single matchup with live turn monitoring if the full benchmark feels too slow.
