import sys
from pathlib import Path

# Bootstrap path for poke_env fork
_DIR = Path(__file__).parent.resolve()
_ROOT = _DIR.parent.parent.parent.parent
_POKECHAMP = _ROOT / "pokechamp"

if _POKECHAMP.exists() and str(_POKECHAMP) not in sys.path:
    sys.path.insert(0, str(_POKECHAMP))

from .base import BaseHeuristic2v2
from .factory import AgentFactory, HeuristicFactory
from .common import calculate_base_damage

__all__ = [
    "BaseHeuristic2v2",
    "AgentFactory",
    "HeuristicFactory",
    "calculate_base_damage",
]
