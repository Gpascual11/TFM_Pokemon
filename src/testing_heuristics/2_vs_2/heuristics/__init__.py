"""Heuristic strategy registry for 2-vs-2 doubles."""

from __future__ import annotations

from .v1 import HeuristicV1Doubles
from .v2 import HeuristicV2Doubles
from .v6 import HeuristicV6Doubles

HEURISTIC_REGISTRY: dict[str, type] = {
    "v1": HeuristicV1Doubles,
    "v2": HeuristicV2Doubles,
    "v6": HeuristicV6Doubles,
}

__all__ = [
    "HeuristicV1Doubles",
    "HeuristicV2Doubles",
    "HeuristicV6Doubles",
    "HEURISTIC_REGISTRY",
]
