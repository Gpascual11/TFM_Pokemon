"""Heuristic strategy registry for doubles."""

from __future__ import annotations

from .v1 import HeuristicV1Doubles
from .v2 import HeuristicV2Doubles
from .v3 import HeuristicV3Doubles
from .v4 import HeuristicV4Doubles
from .v5 import HeuristicV5Doubles

HEURISTIC_REGISTRY: dict[str, type] = {
    "v1": HeuristicV1Doubles,
    "v2": HeuristicV2Doubles,
    "v3": HeuristicV3Doubles,
    "v4": HeuristicV4Doubles,
    "v5": HeuristicV5Doubles,
}

__all__ = [
    "HeuristicV1Doubles",
    "HeuristicV2Doubles",
    "HeuristicV3Doubles",
    "HeuristicV4Doubles",
    "HeuristicV5Doubles",
    "HEURISTIC_REGISTRY",
]
