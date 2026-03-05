# PyTorch: CPU vs GPU setup

This project is used on two machines: one with **PyTorch CPU** and one with **PyTorch GPU** (CUDA). The same `pyproject.toml` works on both; you only change the index when running `uv`.

## What we changed

- **Before:** `pyproject.toml` had a fixed PyTorch CPU index and `[tool.uv.sources]` so `torch` always came from the CPU wheel.
- **After:** Those were removed. PyTorch is chosen at install time by passing the right `--index-url` to `uv lock` and `uv sync`.

So:
- **Other computer (CPU):** use the `cpu` index.
- **This computer (GPU):** use the `cu124` index (CUDA 12.4; driver reports CUDA 13.0, which is backward compatible).

## Commands by machine

### GPU machine (this one – CUDA)

From the project root:

```bash
# 1. Regenerate lock file for GPU (once, or after changing dependencies)
uv lock --index-url https://download.pytorch.org/whl/cu124 --extra-index-url https://pypi.org/simple

# 2. Install/sync everything (base + all extras + dev)
uv sync --all-extras --group dev --index-url https://download.pytorch.org/whl/cu124 --extra-index-url https://pypi.org/simple
```

Result: `torch` (and `torchaudio`, `torchvision` from the `gpu` extra) are installed from the CUDA 12.4 wheel, plus NVIDIA CUDA libraries (cublas, cudnn, etc.) and Triton.

### CPU machine (the other one)

From the project root:

```bash
uv lock --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple
uv sync --all-extras --group dev --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple
```

## What the GPU install adds

When you run the GPU `uv sync`, you get in particular:

- **torch** – PyTorch built for CUDA 12.4 (replaces the `+cpu` build).
- **triton** – GPU compiler used by PyTorch.
- **NVIDIA CUDA libraries** – e.g. `nvidia-cublas-cu12`, `nvidia-cudnn-cu12`, `nvidia-cuda-runtime-cu12`, etc.

So “perfect” in your case means: lock and sync completed, and you now have a GPU-enabled PyTorch environment on this machine.

## Lock file and two machines

Each machine uses a different PyTorch wheel (CPU vs CUDA), so `uv.lock` will differ:

- You can **not commit** `uv.lock` and run `uv lock` + `uv sync` with the appropriate index on each machine, or  
- You **commit** `uv.lock` from one machine and on the other run `uv lock` with that machine’s index, then `uv sync`, so the lock is updated for that environment.

## Optional: grpcio yanked warning

If you see a warning like:

```text
warning: `grpcio==1.78.1` is yanked (reason: "...")
```

that comes from a dependency of one of the project packages (e.g. TensorBoard), not from our PyTorch choice. It’s safe to ignore unless you use gcloud serverless; you can update dependencies later if a fix is released.

## Quick reference

| Machine | Index URL |
|--------|------------|
| CPU    | `https://download.pytorch.org/whl/cpu` |
| GPU    | `https://download.pytorch.org/whl/cu124` |

Always add: `--extra-index-url https://pypi.org/simple` so the rest of the dependencies resolve from PyPI.
