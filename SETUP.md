# Setup Guide — TFM Pokémon

Complete installation guide to get all thesis components ready: heuristics, imitation learning, adversarial search (minimax + MCTS), and reinforcement learning (PPO).

> For what to actually run and in what order, see [`THESIS_PLAN.md`](THESIS_PLAN.md).

---

## Prerequisites

| Tool | Required version | Purpose |
|---|---|---|
| **Python** | 3.12.x (exact) | Main runtime — 3.13 not supported |
| **uv** | latest | Package manager + virtualenv |
| **Node.js** | v18+ (v24 on this machine) | Pokemon Showdown server |
| **npm** | 11.x | Showdown server dependencies |
| **Git** | any | Repository management |
| **CUDA** | 12.x (optional) | GPU-accelerated PPO training |

---

## Step 1 — Clone the repository

```bash
git clone <your-repo-url>
cd TFM_Pokemon
```

Two subdirectories are **not** pip packages but must exist at the project root:

| Directory | Purpose | If missing |
|---|---|---|
| `pokechamp/` | LLM agents + LocalSim simulator (for MCTS) | `git clone https://github.com/showlab/pokechamp.git pokechamp` |
| `pokemon-showdown/` | Local battle simulator server | `git clone https://github.com/smogon/pokemon-showdown.git pokemon-showdown` |

---

## Step 2 — Python environment

```bash
# Install uv if not present
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Python 3.12
uv python install 3.12

# Install base dependencies (required for everything)
uv sync

# Verify
uv run python --version   # must show Python 3.12.x
```

After any change to `pyproject.toml`, re-run `uv sync` to regenerate the lockfile.

---

## Step 3 — Dependency groups (install only what you need)

The project separates heavy ML dependencies into optional extras so you don't need PyTorch just to run heuristics.

### Base install (always required)
`uv sync` installs:
- `poke-env==0.11.0` — battle environment (PINNED, see §5)
- `xgboost` — imitation learning classifier
- `scikit-learn`, `numpy`, `pandas`, `polars` — data processing
- `datasets` — Hugging Face replay downloader
- `orjson` — fast JSON (required by pokechamp LocalSim)
- `matplotlib`, `seaborn`, `tqdm`, `tabulate` — analysis and reporting

This is sufficient for: **heuristics v1–v14, benchmarks, imitation learning, reporting**.

### RL training (PPO) — CPU
```bash
uv sync --extra rl
```
Adds: `gymnasium`, `stable-baselines3`, `sb3-contrib`, `torch` (CPU build), `tensorboard`

### RL training (PPO) — GPU (RTX 2080 / CUDA 12.8)
```bash
uv sync --extra gpu --index https://download.pytorch.org/whl/cu128
```
Adds: same as above but with CUDA-enabled PyTorch.

Other CUDA versions:
```bash
uv sync --extra gpu --index https://download.pytorch.org/whl/cu124   # CUDA 12.4
uv sync --extra gpu --index https://download.pytorch.org/whl/cu121   # CUDA 12.1
uv sync --extra rl  --index https://download.pytorch.org/whl/cpu     # CPU only
```

After switching PyTorch index, regenerate the lockfile:
```bash
uv lock --index https://download.pytorch.org/whl/cu128
uv sync --extra gpu
```

Verify GPU is detected:
```bash
uv run python -c "import torch; print('CUDA:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0))"
# Expected on this machine: CUDA: True | GPU: NVIDIA GeForce RTX 2080
```

### pokechamp LLM agents (abyssal, pokellmon, pokechamp-minimax)
```bash
uv sync --extra pokechamp
```
Adds: `openai`, `anthropic`, `google-genai`, `ollama`, `transformers`, `websockets`, `rich`, etc.

> **Note:** MCTS does NOT need this extra. MCTS uses `LocalSim` from `pokechamp/poke_env/` loaded via sys.path — no pip install required.

---

## Step 4 — Pokemon Showdown server

All bot-vs-bot benchmarks run against local Showdown server instances.

### Build the server
```bash
cd pokemon-showdown
npm install
node build
cd ..
```

Tested versions on this machine: Showdown `0.11.10`, Node.js `v24.15.0`, npm `11.12.1`

### Configure for offline use
Create `pokemon-showdown/config/config.js` from the example and set:
```js
// Minimum required: disable online authentication
exports.loginserver = null;

// Recommended for this machine (Ryzen 7 5700X3D, 16 threads, 32 GB RAM)
exports.workerprocesses = 10;
exports.subprocesses = {
  network: 2,
  simulator: 10,
};
```

### Launch servers for benchmarking
```bash
# Start 8 servers on ports 8000–8007
bash src/p00_core/scripts/launch_custom_servers.sh 8
```

This is the configuration used for all benchmark results in this thesis (200 concurrent games, ~50k games/hour).

---

## Step 5 — Critical: poke-env version architecture

> [!IMPORTANT]
> This project has two co-existing poke-env versions. You must understand this before running anything.

### The two versions

| Version | Location | What it has | Used for |
|---|---|---|---|
| **`poke-env 0.11.0`** (PyPI) | `.venv/` | Standard API, `battle/`, `calc/` dirs | All heuristics v1–v14, benchmarks, online bot, IL |
| **pokechamp fork (~0.9-era)** | `pokechamp/poke_env/` | Adds `LocalSim` + `team_util` | MCTS rollouts, pokechamp agents |

### Why poke-env is pinned to `0.11.x`

All 2.5M+ benchmark games were run on `poke-env 0.11.0`. Version 0.15+ has breaking API changes that would break all v1–v14 heuristics. The `pyproject.toml` hard-pins `poke-env>=0.11.0,<0.12.0`.

**Never run:** `uv add poke-env@latest` or `uv upgrade poke-env`

### LocalSim (pokechamp fork) — only for MCTS

`pokechamp/poke_env/player/local_simulation.py` is a 1,759-line local battle simulator that does not exist in standard poke-env 0.11.0. It is the rollout engine for MCTS. Scripts that need it inject the pokechamp path at runtime:

```python
sys.path.insert(0, str(Path(__file__).resolve().parents[N] / "pokechamp"))
from poke_env.player.local_simulation import LocalSim
```

Heuristics v1–v14 and the benchmark engine do **not** need this — they run on clean poke-env 0.11.0.

### Does this affect benchmark results?

No. Game mechanics (damage, type effectiveness, win/loss) are determined by the **Showdown server**, not by the poke-env client version. Both versions expose identical core objects (`Battle`, `Move`, `Pokemon`, `GenData`). The version difference only adds/removes `LocalSim`.

---

## Step 6 — pokechamp setup (for LLM benchmarks)

```bash
# Install pokechamp extras
uv sync --extra pokechamp

# Set up API keys (needed for pokellmon LLM agents)
cp pokechamp/passwords.json.example pokechamp/passwords.json
# Edit passwords.json: add openai_key, anthropic_key, etc. as needed

# For free local LLM inference (no API cost):
# Install ollama from https://ollama.ai
ollama pull mistral   # or llama3, gemma3, etc.
```

pokechamp's `abyssal` and minimax bots work without any API keys.

---

## Step 7 — Verify the full setup

```bash
# 1. Check Python + core packages
uv run python -c "import poke_env, xgboost, sklearn, pandas; print('Core OK')"

# 2. Check LocalSim (pokechamp fork)
cd pokechamp && uv run python -c "from poke_env.player.local_simulation import LocalSim; print('LocalSim OK')" && cd ..

# 3. Check GPU (if installed with --extra gpu)
uv run python -c "import torch; print('CUDA:', torch.cuda.is_available())"

# 4. Check Showdown server is running (after launching servers)
curl -s http://localhost:8000 | head -3
```

---

## Installed versions (this machine — June 2026)

| Package | Version | Notes |
|---|---|---|
| Python | 3.12.x | Required exact major.minor |
| **poke-env** | **0.11.0** | **PINNED — do not upgrade** |
| pokemon-showdown | 0.11.10 | Already built |
| Node.js | v24.15.0 | |
| npm | 11.12.1 | |
| torch | 2.10.0+cu128 | RTX 2080, CUDA 12.8 |
| stable-baselines3 | 2.7.1 | |
| gymnasium | 1.2.3 | |
| xgboost | 3.2.0 | |
| scikit-learn | 1.8.0 | |
| pandas | 3.0.0 | |
| numpy | 2.4.2 | |
| pokechamp poke_env fork | ~0.9-era | LocalSim for MCTS only |

---

## Troubleshooting

**`ModuleNotFoundError: poke_env.player.local_simulation`**  
LocalSim is only in pokechamp's fork. In MCTS scripts, inject the path:
```python
sys.path.insert(0, str(Path(__file__).parents[N] / "pokechamp"))
```

**poke-env upgraded past 0.11.x after `uv sync`**  
```bash
uv add "poke-env==0.11.0" && uv sync
```

**CUDA not detected**  
```bash
uv sync --extra gpu --index https://download.pytorch.org/whl/cu128
uv run python -c "import torch; print(torch.version.cuda)"
```

**Showdown server won't start**  
```bash
cd pokemon-showdown && node build && cd ..
node --version   # must be v18+
lsof -i :8000    # check if port is in use
```

**Python version mismatch**  
```bash
uv python install 3.12 && uv sync
```

**pokechamp agent imports fail**  
```bash
uv sync --extra pokechamp
ls pokechamp/pokechamp/  # must show gpt_player.py etc.
```
