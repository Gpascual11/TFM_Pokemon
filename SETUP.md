# Clean Setup Guide for New Computer

This guide helps you set up the TFM project from scratch on a new machine.

## Quick Start

```bash
# 1. Install uv (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Clone the repository
git clone <your-repo-url>
cd TFM

# 3. Install Python 3.12 via uv
uv python install 3.12

# 4. Sync dependencies (uv will use Python 3.12 automatically)
uv sync

# 5. Verify Python version
uv run python --version  # Should show Python 3.12.x
```

## Python Version

This project requires **Python 3.12** (specified in `pyproject.toml` and `.python-version`).

- Python 3.12 is required for CUDA compatibility with PyTorch
- The `.python-version` file ensures `uv` and `pyenv` use the correct version
- `uv sync` will automatically use Python 3.12 if available

## RL Training (CPU or GPU)

To run RL scripts (e.g. PPO vs heuristic in `src/rl/`), install the optional **rl** dependencies:

```bash
uv sync --extra rl
```

This installs: `gymnasium`, `stable-baselines3`, `torch`, `torchvision`, `torchaudio` (CPU builds from PyPI). You can then run:

```bash
uv run python src/rl/train_ppo_doubles_vs_heuristic.py
```

### Using the GPU (CUDA)

On a machine with an NVIDIA GPU and CUDA installed:

1. **Install CUDA Toolkit** (if not already installed):
   - CUDA 11.8 or 12.1 recommended
   - Follow NVIDIA's installation guide for your OS

2. **Sync base + RL deps**, then **replace PyTorch with CUDA builds**:
   ```bash
   uv sync --extra rl
   uv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
   ```
   Use `cu118` instead of `cu121` for CUDA 11.8.

3. **Verify CUDA**:
   ```bash
   uv run python -c "import torch; print('cuda:', torch.cuda.is_available())"
   ```

After that, run the same RL scripts with `uv run`; they will use the GPU automatically.

## Project Structure

- `pyproject.toml`: Project metadata and dependencies (Python 3.12 required)
- `.python-version`: Python version pin for uv/pyenv
- `uv.lock`: Locked dependency versions (regenerated with `uv sync`)

## Troubleshooting

- **Python version mismatch**: Run `uv python install 3.12` then `uv sync`
- **uv not found**: Install via `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **CUDA not detected**: Ensure CUDA toolkit is installed and PyTorch CUDA build matches your CUDA version
