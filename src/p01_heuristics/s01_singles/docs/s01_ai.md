# Pokechamp + Heuristics: Setup & Debug Log

This document summarizes the main steps, issues, and fixes while wiring the external `pokechamp` repo into this TFM project and running `pokechamp` / `pokellmon` against your heuristic agents.

---

## 1. Initial integration

- **Goal**: Use the upstream `pokechamp` repo (`~/TFM_Pokemon/pokechamp`) as an external dependency and benchmark its agents (`pokechamp`, `pokellmon`, `random`, `max_power`, `abyssal`, `one_step`) against your own heuristics via `src/p01_heuristics/s01_singles/evaluation/engine/benchmark.py`.
- **Key components in this project**:
- `evaluation/engine/benchmark.py`: Orchestrates matchups, spawns `evaluation/engine/worker.py` subprocesses, merges CSVs, prints a win‑rate matrix.
- `evaluation/engine/worker.py`: Creates two players (agent and opponent), runs `battle_against`, writes per‑battle rows to a temp CSV, then exits.
  - `AgentFactory`: Instantiates internal heuristics, baselines, and pokechamp LLM players by label.

---

## 2. OneStepPlayer instantiation error

**Symptom**

```python
TypeError: OneStepPlayer.__init__() got an unexpected keyword argument 'max_concurrent_battles'
```

**Cause**

- `poke_env.player.player.Player` supports `max_concurrent_battles`, but Pokechamp's `OneStepPlayer` (in `pokechamp/poke_env/player/baselines.py`) has a fixed signature that does **not** accept this kwarg.

**Fix in this project**

- `worker.py` was updated so that bundled baselines (`RandomPlayer`, `MaxBasePowerPlayer`, `AbyssalPlayer`, `OneStepPlayer`) are created with a shared `server_configuration` but **without** `max_concurrent_battles`. Only your heuristics use the concurrency kwarg.

Result: `OneStepPlayer` can be instantiated successfully.

---

## 3. Silent hangs from OneStepPlayer / LocalSim

**Symptom**

- After fixing the constructor, `OneStepPlayer` would hang a process at 100% CPU with no Python traceback.
- Logs showed only warnings like:

```text
[WARN] gen9pokedex.json not found, using empty dict
[WARN] gen9randombattle moves set not found, using empty dict
```

**Root cause (conceptual)**

- `OneStepPlayer.choose_move` uses `LocalSim` and prompt helpers `get_number_turns_faint` / `get_status_num_turns_fnt` from `pokechamp.prompts`, which:
  - Construct many simulated states per candidate move.
  - Call full damage and stat calculations repeatedly.
  - Expect static data JSONs (pokedex, moves sets) to be present.
- With missing JSON data, the cache returns empty dicts and the heavy logic degenerates into very slow / near‑hanging behavior.

**Pragmatic workaround in this project**

- A separate `SafeOneStepPlayer` (in your `src/` tree, not in the upstream repo) was added as a 1‑step lookahead that:
  - Uses only `poke_env` types and `damage_multiplier`.
  - Scores moves by `base_power * STAB * type effectiveness * accuracy`.
  - Never calls `LocalSim` or `pokechamp.prompts`.
- `worker.py` uses `SafeOneStepPlayer` when the CLI agent name is `one_step`.

Result: the `one_step` agent now behaves as a simple rule‑based lookahead without touching `LocalSim`.

---

## 4. Running LLM agents with Gemini

### 4.1. Basic configuration

- Extra dependencies are installed via the `pokechamp` optional extra in `pyproject.toml`:

```bash
cd ~/TFM_Pokemon
uv sync --extra pokechamp
```

- `GeminiPlayer` (`pokechamp/pokechamp/gemini_player.py`):
  - Reads `GEMINI_API_KEY` from the environment when no key is passed.
  - Wraps `google.genai.Client(api_key=...)`.
  - Maps friendly names like `gemini-flash` → `gemini-2.5-flash`.

**Example run with Gemini 2.5 Flash**

```bash
export GEMINI_API_KEY="YOUR_GEMINI_KEY"

# Terminal A: Showdown server
cd ~/TFM_Pokemon
bash src/p05_scripts/p05_launch_custom_servers.sh 1

# Terminal B: benchmark
cd ~/TFM_Pokemon
uv run python src/p01_heuristics/s01_singles/evaluation/engine/benchmark.py 1 \
  --agents pokechamp pokellmon \
  --opponents random \
  --ports 1 \
  --concurrency 1 \
  --start-port 8000 \
  --player_backend gemini-2.5-flash \
  --player_prompt_algo io
```

### 4.2. Gemini‑specific errors

- **404 NotFound**: using `--player_backend gemini` caused the model name "gemini" to be sent, which the API doesn’t know. Fix: use valid IDs like `gemini-2.5-flash` or `gemini-1.5-pro`.
- **`ValueError: No API key was provided`**: occurred when worker subprocesses didn’t inherit `GEMINI_API_KEY`. Fix: export the key in the same shell that runs `uv run ...`.
- **429 TooManyRequests**: free tier rate limit reached (seen in Gemini console). Workarounds: run one LLM agent at a time, reduce games, or switch to a local backend.

---

## 5. Switching to local Ollama (no API keys)

### 5.1. Install and move models to the larger NVMe

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Put models on /mnt/data instead of home
sudo mkdir -p /mnt/data/ollama-models
sudo chown "$USER":"$USER" /mnt/data/ollama-models

# Systemd override
sudo systemctl edit ollama
# Add:
# [Service]
# Environment="OLLAMA_MODELS=/mnt/data/ollama-models"

sudo systemctl daemon-reload
sudo systemctl restart ollama
systemctl show ollama -p Environment | grep OLLAMA_MODELS

# Pull a model (example)
ollama pull qwen3:8b
```

### 5.2. Use Ollama backend in the benchmark

```bash
# Terminal A: Showdown server
cd ~/TFM_Pokemon
bash src/p05_scripts/p05_launch_custom_servers.sh 1

# Terminal B: LLM benchmark with local Qwen 3 8B
cd ~/TFM_Pokemon
uv run python src/p01_heuristics/s01_singles/evaluation/engine/benchmark.py 1 \
  --agents pokechamp pokellmon \
  --opponents random \
  --ports 1 \
  --concurrency 1 \
  --start-port 8000 \
  --player_backend ollama/qwen3:8b \
  --player_prompt_algo io \
  --battle-format gen9randombattle
```

Notes:
- CPU‑only 8B models are slow; a single LLM battle can take several minutes.
- Smaller models (e.g. `ollama/qwen3:4b`) or a GPU make this much faster.

---

## 6. Debug helper: `debug_runner.py`

To see live progress for single games without the full benchmark, this project includes `src/p01_heuristics/s01_singles/evaluation/debug/debug_runner.py` (with `evaluation/engine/debug_runner.py` kept as a backwards-compatible shim).

**Behavior**

- Uses the same bootstrap and backend as `worker.py` / `benchmark.py`.
- Runs three battles in sequence:
  1. `pokellmon` vs `random`.
  2. `pokechamp` vs `random`.
  3. `pokellmon` vs `pokechamp`.
- Prints turn progress while a game is running, e.g.:

```text
=== pokellmon (backend=ollama/qwen3:8b) vs random — format=gen9randombattle ===
    [pokellmon vs random] turn=0
    [pokellmon vs random] turn=1
    ...
    Finished battle battle-gen9randombattle-XXXXX: turns=23, won=True, duration=185.2s
```

**How to run**

```bash
# Terminal A
cd ~/TFM_Pokemon
bash src/p05_scripts/p05_launch_custom_servers.sh 1

# Terminal B
cd ~/TFM_Pokemon
uv run python src/p01_heuristics/s01_singles/evaluation/debug/debug_runner.py
```

---

## 7. CPU vs GPU expectation

- On CPU, 8B models (Gemini via API or local Ollama) + heavyweight prompts mean **minutes per game** are normal.
- A mid‑range NVIDIA GPU (8–12GB VRAM) typically reduces per‑turn latency by an order of magnitude or more, bringing games down to tens of seconds to a couple of minutes even with the same logic.
