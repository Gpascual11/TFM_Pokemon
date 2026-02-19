"""Heuristic strategy registry for 1-vs-1 singles."""

from __future__ import annotations

from .v1 import HeuristicV1
from .v2 import HeuristicV2
from .v4 import HeuristicV4
from .v5 import HeuristicV5

HEURISTIC_REGISTRY: dict[str, type] = {
    "v1": HeuristicV1,
    "v2": HeuristicV2,
    "v4": HeuristicV4,
    "v5": HeuristicV5,
}

__all__ = [
    "HeuristicV1",
    "HeuristicV2",
    "HeuristicV4",
    "HeuristicV5",
    "HEURISTIC_REGISTRY",
]
