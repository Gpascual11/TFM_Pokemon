def get_heuristic_class(version: str) -> type:
    """Lazy-load and return the heuristic class for the given version."""
    if version == "v1":
        from .v1 import HeuristicV1
        return HeuristicV1
    if version == "v2":
        from .v2 import HeuristicV2
        return HeuristicV2
    if version == "v3":
        from .v3 import HeuristicV3
        return HeuristicV3
    if version == "v4":
        from .v4 import HeuristicV4
        return HeuristicV4
    if version == "v5":
        from .v5 import HeuristicV5
        return HeuristicV5
    if version == "v6":
        from .v6 import HeuristicV6
        return HeuristicV6
    raise ValueError(f"Unknown heuristic version: {version}")

__all__ = [
    "get_heuristic_class",
]
