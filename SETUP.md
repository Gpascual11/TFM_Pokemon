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

### Step 2: Run a training phase
All scripts support `--timesteps` and `--ports`.

> [!IMPORTANT]
> **Always** run scripts as modules using `python -m` from the project root. This ensures relative imports work correctly.

```bash
# Example: Using uv to run Phase 1
uv run python -m src.p02_rl_models.s02_training.train_p1_base --timesteps 1000000 --ports 8000 8001 8002 8003
```

## RL Training (GPU Setup)

To use your GPU on a new computer, you need to sync the dependencies with the `gpu` extra and use the correct PyTorch index.

1. **Sync with GPU extras**:
   ```bash
   uv sync --all-extras
   ```

2. **(Optional) Re-install PyTorch for your specific CUDA version**:
   If your GPU is not detected, you may need to point `uv` to the NVIDIA wheels:
   ```bash
   # For CUDA 12.4+ (Standard for most modern GPUs)
   uv lock --index-url https://download.pytorch.org/whl/cu124 --extra-index-url https://pypi.org/simple
   uv sync --all-extras --index-url https://download.pytorch.org/whl/cu124 --extra-index-url https://pypi.org/simple
   ```

3. **Verify CUDA availability**:
   ```bash
   uv run python -c "import torch; print('CUDA available:', torch.cuda.is_available()); print('GPU:', torch.get_device_name(0) if torch.cuda.is_available() else 'None')"
   ```

After verification, run your training scripts with `uv run python -m ...`.

## Project Structure

- `pyproject.toml`: Project metadata and dependencies (Python 3.12 required)
- `.python-version`: Python version pin for uv/pyenv
- `uv.lock`: Locked dependency versions (regenerated with `uv sync`)

## Troubleshooting

- **Python version mismatch**: Run `uv python install 3.12` then `uv sync`
- **uv not found**: Install via `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **CUDA not detected**: Ensure CUDA toolkit is installed and PyTorch CUDA build matches your CUDA version
