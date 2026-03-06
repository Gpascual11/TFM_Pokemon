"""Unified Factory for Doubles Agents.

Supports internal heuristics and standard poke-env baselines.
"""

from __future__ import annotations
import sys
from pathlib import Path
from typing import Any

# Bootstrap path for imports
_DIR = Path(__file__).parent.resolve()
_SRC = _DIR.parent.parent.parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from ..agents import get_agent_class

class AgentFactory:
    """Creates any 2v2 agent subclasses by name label."""

    @staticmethod
    def available_internal() -> list[str]:
        return ["v1", "v2", "v6"]

    @staticmethod
    def available_baselines() -> list[str]:
        return ["random", "max_power", "abyssal", "one_step", "safe_one_step", "vgc", "simple_heuristic"]

    @staticmethod
    def available_llm() -> list[str]:
        return ["pokechamp", "pokellmon"]

    @staticmethod
    def create(name: str, **kwargs: Any) -> Any:
        """Instantiate the agent identified by *name*."""
        # Special handling for LLM agents which require the pokechamp library
        if name in ["pokechamp", "pokellmon"]:
            # Ensure pokechamp is in path
            root = Path(__file__).parent.parent.parent.parent.parent.resolve()
            pokechamp_path = root / "pokechamp"
            if pokechamp_path.exists() and str(pokechamp_path) not in sys.path:
                sys.path.insert(0, str(pokechamp_path))
            
            from poke_env.player.team_util import get_llm_player
            import argparse
            
            # Extract LLM specific args or use defaults
            temperature = kwargs.pop("temperature", 0.3)
            log_dir = kwargs.pop("log_dir", "./battle_log")
            backend = kwargs.pop("backend", "ollama")
            prompt_algo = kwargs.pop("prompt_algo", "io")
            tag = kwargs.pop("tag", "0")
            battle_format = kwargs.get("battle_format", "gen9randomdoublesbattle")
            
            ns = argparse.Namespace(temperature=temperature, log_dir=log_dir)
            return get_llm_player(
                ns,
                backend=backend,
                prompt_algo=prompt_algo,
                name=name,
                battle_format=battle_format,
                PNUMBER1=tag,
                use_timeout=False,
            )

        cls = get_agent_class(name)
        return cls(**kwargs)

# Alias for backward compatibility
HeuristicFactory = AgentFactory
