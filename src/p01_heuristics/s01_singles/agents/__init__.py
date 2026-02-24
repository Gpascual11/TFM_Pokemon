"""Heuristic strategy registry for 1-vs-1 singles."""

from __future__ import annotations

from .v1 import HeuristicV1
from .v2 import HeuristicV2
from .v3 import HeuristicV3
from .v4 import HeuristicV4
from .v5 import HeuristicV5
from .v6 import HeuristicV6

HEURISTIC_REGISTRY: dict[str, type] = {
    "v1": HeuristicV1,
    "v2": HeuristicV2,
    "v3": HeuristicV3,
    "v4": HeuristicV4,
    "v5": HeuristicV5,
    "v6": HeuristicV6,
}

__all__ = [
    "HeuristicV1",
    "HeuristicV2",
    "HeuristicV3",
    "HeuristicV4",
    "HeuristicV5",
    "HeuristicV6",
    "HEURISTIC_REGISTRY",
]
