# RL next steps (Gen9 Random Doubles)

This folder contains a minimal, runnable RL pipeline using `poke-env` + Gymnasium + Stable-Baselines3.

## 0) Python version (important)

Deep-learning libraries (PyTorch / TensorFlow) generally **do not support Python 3.14 yet**.
This project is pinned to **Python 3.12** for RL.

The repo includes a `.python-version` set to `3.12` and `pyproject.toml` updated accordingly.

## 1) Create / sync the environment

From the repo root:

```bash
uv python install 3.12
uv sync
```

## 2) (Optional) GPU PyTorch on your RTX 2080

If you want GPU training, install a CUDA-enabled PyTorch wheel.
For example (CUDA 12.1 wheels):

```bash
uv pip install --index-url https://download.pytorch.org/whl/cu121 torch torchvision torchaudio
```

Check:

```bash
uv run python -c "import torch; print(torch.__version__); print('cuda:', torch.cuda.is_available())"
```

If `cuda: False`, you likely need to update NVIDIA drivers / CUDA compatibility on your system.

## 3) Start local Pokémon Showdown

Your existing scripts already assume a local server at:

`ws://127.0.0.1:8000/showdown/websocket`

Make sure it is running before training.

## 4) Train PPO vs your heuristic v2 (doubles)

```bash
uv run python src/rl/train_ppo_doubles_vs_heuristic.py
```

This will:
- run `gen9randomdoublesbattle`
- train PPO against your `TFMExpertDoubles` heuristic (`testing_heuristic_v2.py`)
- save the model in `models/`
- write logs into `runs/`

## Files

- `tfm_doubles_env.py`: observation + reward for doubles
- `train_ppo_doubles_vs_heuristic.py`: PPO training loop

