#!/usr/bin/env python
"""Backwards-compatible shim.

This file used to live in `evaluation/engine/`. It now lives in
`evaluation/debug/debug_runner.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the top-level `src/` is importable so `p01_heuristics` resolves.
_DIR = Path(__file__).parent.resolve()
_SRC = _DIR.parent.parent.parent.parent  # src/
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from p01_heuristics.s01_singles.evaluation.debug.debug_runner import main


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

