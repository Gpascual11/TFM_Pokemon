"""Put ``src/`` on ``sys.path`` so ``p01_heuristics`` / ``p00_core`` import."""

from __future__ import annotations

import sys
from pathlib import Path


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd()


def ensure_src_path() -> Path:
    src = repo_root() / "src"
    src_s = str(src)
    if src_s not in sys.path:
        sys.path.insert(0, src_s)
    return src
