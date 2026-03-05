"""Unified Factory for instantiating ANY Pokémon agent by name string.
Supports internal heuristics, poke_env baselines, and Pokechamp LLM agents.
"""

from __future__ import annotations
import sys
from pathlib import Path
from typing import Any

# Ensure we can find the agents relative to this core folder
_DIR = Path(__file__).parent.resolve()
_SRC = _DIR.parent.parent.parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# Pokechamp root for LLM agents
_POKECHAMP_ROOT = _SRC.parent / "pokechamp"
if str(_POKECHAMP_ROOT) not in sys.path:
    sys.path.insert(0, str(_POKECHAMP_ROOT))

from ..agents import get_agent_class
from .base import BaseHeuristic1v1

class AgentFactory:
    """Unified Factory for building any Pokémon agent by its name label.
    
    This factory centralizes the creation of three distinct agent families:
    1. Internal Heuristics (v1-v6): Rule-based experts built locally.
    2. Baselines (abyssal, random, etc.): Standard poke-env agents.
    3. LLM Agents (pokechamp, pokellmon): Model-based agents requiring the Pokechamp library.
    
    It serves as the main dependency injection point for evaluation scripts.
    """

    @staticmethod
    def available_internal() -> list[str]:
        return ["v1", "v2", "v3", "v4", "v5", "v6"]

    @staticmethod
    def available_baselines() -> list[str]:
        return ["random", "max_power", "abyssal", "one_step", "safe_one_step", "simple_heuristic"]

    @staticmethod
    def available_llm() -> list[str]:
        return ["pokechamp", "pokellmon"]

    @staticmethod
    def create(name: str, **kwargs: Any) -> Any:
        """Instantiate the agent identified by *name*.
        
        :param name: Label like 'v5', 'abyssal', or 'pokechamp'.
        :param kwargs: Forwarded to the player constructor.
        """
        # Special handling for LLM agents which require the pokechamp library
        if name in ["pokechamp", "pokellmon"]:
            from poke_env.player.team_util import get_llm_player
            import argparse
            
            # Extract LLM specific args or use defaults
            temperature = kwargs.pop("temperature", 0.3)
            log_dir = kwargs.pop("log_dir", "./battle_log")
            backend = kwargs.pop("backend", "ollama")
            prompt_algo = kwargs.pop("prompt_algo", "io")
            tag = kwargs.pop("tag", "0")
            battle_format = kwargs.get("battle_format", "gen9randombattle")
            
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

        # Standard heuristics/baselines
        cls = get_agent_class(name)
        return cls(**kwargs)

# Alias for backward compatibility
HeuristicFactory = AgentFactory
