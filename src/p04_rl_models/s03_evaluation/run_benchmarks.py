"""Benchmark Suite for PPO and Hybrid Ensemble.

Evaluates the trained PPO model and a hybrid Ensemble agent (PPO + Heuristics)
against a gauntlet of opponents to measure relative performance.
"""

import asyncio
import os
import numpy as np
import torch
from tabulate import tabulate
import random
import string
from poke_env.player import RandomPlayer, MaxBasePowerPlayer, SimpleHeuristicsPlayer
from poke_env.ps_client.server_configuration import LocalhostServerConfiguration
from poke_env.ps_client.account_configuration import AccountConfiguration
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.monitor import Monitor
from sb3_contrib import MaskablePPO

from ..s01_env.pokemon_env import PokemonMaskedEnv, PokemonMaskedEnvWrapper


class EnsemblePlayer(SimpleHeuristicsPlayer):
    """
    Hybrid agent that combines PPO neural network logits with heuristic scores.

    Uses soft-voting (weighted summation of probability distributions) to
    leverage high-level PPO strategy and low-level heuristic tactics.
    """

    def __init__(self, model, alpha=0.5, **kwargs):
        """
        Initializes the Ensemble Player.

        Args:
            model: Trained MaskablePPO model.
            alpha: Weight for the PPO model (1-alpha is for the heuristic).
            **kwargs: Arguments for the parent Player class.
        """
        super().__init__(**kwargs)
        self.model = model
        self.alpha = alpha

    def choose_move(self, battle):
        """
        Blends PPO and Heuristic distributions to choose the optimal move.

        Args:
            battle: The current Battle object.

        Returns:
            The chosen BattleOrder.
        """
        if battle.force_switch or battle._wait:
            return super().choose_move(battle)

        # The environment is wrapped: DummyVecEnv -> Monitor -> PokemonMaskedEnvWrapper -> PokemonMaskedEnv
        wrapper_env = self.model.env.envs[0].env
        base_env = wrapper_env.env

        # 1. Get PPO Action Probabilities
        obs = base_env.embed_battle(battle)
        obs_tensor = torch.as_tensor(obs).unsqueeze(0).to(self.model.device)

        with torch.no_grad():
            distribution = self.model.policy.get_distribution(obs_tensor)
            ppo_probs = distribution.distribution.probs[0].cpu().numpy()

        # 2. Get Heuristic Utilities
        # Action space is 10: 0-3 for moves, 4-9 for switches
        heuristic_scores = np.zeros(10)

        if battle.active_pokemon:
            # First, evaluate attack moves
            if battle.opponent_active_pokemon:
                for i, move in enumerate(battle.available_moves):
                    if i < 4:
                        # Value of attacking: damage multiplier
                        score = battle.opponent_active_pokemon.damage_multiplier(move)
                        heuristic_scores[i] = score
            else:
                # If opponent has no active pokemon (fainted?), any move is fine
                for i in range(min(4, len(battle.available_moves))):
                    heuristic_scores[i] = 1.0

            # Second, evaluate switches (give a neutral baseline score so switches aren't zeroed out)
            # A score of 1.0 means "switching is an ok option, let PPO decide if it's best"
            available_switch_names = [p.name for p in battle.available_switches]
            team_names = list(battle.team.keys())
            for i, p_name in enumerate(team_names):
                if i < 6 and p_name in available_switch_names:
                    heuristic_scores[4 + i] = 1.0

            # Normalize heuristic scores so they sum to 1.0
            if np.sum(heuristic_scores) > 0:
                heuristic_scores /= np.sum(heuristic_scores)

        # 3. Combine Distributions via Soft-Voting
        combined_logits = (self.alpha * ppo_probs) + (
            (1 - self.alpha) * heuristic_scores
        )

        # Apply action mask from the PPO environment
        action_mask = wrapper_env.action_masks()
        combined_logits *= action_mask

        # Select highest weighted action
        if np.sum(combined_logits) > 0:
            action = np.argmax(combined_logits)
        else:
            # Fallback to pure PPO if heuristic zeroes everything out
            action, _ = self.model.predict(
                obs, action_masks=action_mask, deterministic=True
            )

        # Map integer action back to order
        return base_env.action_to_order(action, battle)


async def run_benchmark(player, opponent, n_battles=100):
    """
    Runs a series of battles between two players and returns the win rate.

    Args:
        player: The agent being evaluated.
        opponent: The baseline opponent.
        n_battles: Number of games to play.

    Returns:
        Float win percentage.
    """
    await player.battle_against(opponent, n_battles=n_battles)
    winrate = (player.n_won_battles / n_battles) * 100
    player.reset_battles()
    opponent.reset_battles()
    return winrate


async def main():
    """Main benchmark execution script."""
    print("--- Baseline 1 Comprehensive Evaluation ---")

    server_config = LocalhostServerConfiguration

    # Generate unique names to prevent Showdown collisions
    def get_unique_name(prefix):
        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
        return f"{prefix}_{suffix}"

    def make_eval_env():
        # 1. Base Env
        base_env = PokemonMaskedEnv(
            server_configuration=server_config,
            account_configuration1=AccountConfiguration(
                get_unique_name("EvalPPO"), None
            ),
        )
        # 2. Wrapper (PPO needs this for action_masks)
        # We use a dummy RandomPlayer as the opponent for the wrapper
        dummy_opponent = RandomPlayer(
            server_configuration=server_config,
            account_configuration=AccountConfiguration(
                get_unique_name("EvalDummy"), None
            ),
        )
        env = PokemonMaskedEnvWrapper(base_env, dummy_opponent)
        # 3. Monitor (SB3 standard)
        return Monitor(env)

    # We wrap in DummyVecEnv to match the training structure exactly
    ppo_env_vec = DummyVecEnv([make_eval_env])

    # Load the best available model
    script_dir = os.path.dirname(os.path.abspath(__file__))
    phase3_path = os.path.join(script_dir, "ppo_pokemon_phase3")
    phase2_path = os.path.join(script_dir, "ppo_pokemon_phase2")
    phase1_5_path = os.path.join(script_dir, "ppo_pokemon_phase1_5")
    baseline_path = os.path.join(script_dir, "ppo_pokemon_baseline")

    if os.path.exists(phase3_path + ".zip"):
        model = MaskablePPO.load(phase3_path, env=ppo_env_vec)
        print("Loaded Phase 3 Weights.")
    elif os.path.exists(phase2_path + ".zip"):
        model = MaskablePPO.load(phase2_path, env=ppo_env_vec)
        print("Loaded Phase 2 Weights.")
    elif os.path.exists(phase1_5_path + ".zip"):
        model = MaskablePPO.load(phase1_5_path, env=ppo_env_vec)
        print("Loaded Phase 1.5 Weights.")
    else:
        model = MaskablePPO.load(baseline_path, env=ppo_env_vec)
        print("Loaded Phase 1 Weights.")

    # Initialize Players with unique names
    # For "Pure PPO", we use EnsemblePlayer with alpha=1.0 (100% PPO weights)
    ppo_player = EnsemblePlayer(
        model=model,
        alpha=1.0,
        server_configuration=server_config,
        account_configuration=AccountConfiguration(
            get_unique_name("EvalPPO_Pure"), None
        ),
    )

    ensemble_player = EnsemblePlayer(
        model=model,
        alpha=0.5,  # Mixed probabilities
        server_configuration=server_config,
        account_configuration=AccountConfiguration(get_unique_name("EvalEns"), None),
    )

    import sys

    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
    from p01_heuristics.s01_singles.agents import (
        HeuristicV1,
        HeuristicV2,
        HeuristicV3,
        HeuristicV4,
        HeuristicV5,
        HeuristicV6,
    )

    opponents = [
        (
            "Random",
            RandomPlayer(
                server_configuration=server_config,
                account_configuration=AccountConfiguration(
                    get_unique_name("OppRand"), None
                ),
            ),
        ),
        (
            "MaxBP",
            MaxBasePowerPlayer(
                server_configuration=server_config,
                account_configuration=AccountConfiguration(
                    get_unique_name("OppMaxBP"), None
                ),
            ),
        ),
        (
            "poke-env-Heur",
            SimpleHeuristicsPlayer(
                server_configuration=server_config,
                account_configuration=AccountConfiguration(
                    get_unique_name("OppHeur"), None
                ),
            ),
        ),
        (
            "Custom-V1",
            HeuristicV1(
                server_configuration=server_config,
                account_configuration=AccountConfiguration(
                    get_unique_name("OppV1"), None
                ),
            ),
        ),
        (
            "Custom-V2",
            HeuristicV2(
                server_configuration=server_config,
                account_configuration=AccountConfiguration(
                    get_unique_name("OppV2"), None
                ),
            ),
        ),
        (
            "Custom-V3",
            HeuristicV3(
                server_configuration=server_config,
                account_configuration=AccountConfiguration(
                    get_unique_name("OppV3"), None
                ),
            ),
        ),
        (
            "Custom-V4",
            HeuristicV4(
                server_configuration=server_config,
                account_configuration=AccountConfiguration(
                    get_unique_name("OppV4"), None
                ),
            ),
        ),
        (
            "Custom-V5",
            HeuristicV5(
                server_configuration=server_config,
                account_configuration=AccountConfiguration(
                    get_unique_name("OppV5"), None
                ),
            ),
        ),
        (
            "Custom-V6",
            HeuristicV6(
                server_configuration=server_config,
                account_configuration=AccountConfiguration(
                    get_unique_name("OppV6"), None
                ),
            ),
        ),
    ]

    results = []
    for opp_name, opp_player in opponents:
        print(f"Benchmarking vs {opp_name}...")

        ppo_winrate = await run_benchmark(ppo_player, opp_player, n_battles=100)
        ensemble_winrate = await run_benchmark(
            ensemble_player, opp_player, n_battles=100
        )

        results.append([opp_name, f"{ppo_winrate:.1f}%", f"{ensemble_winrate:.1f}%"])

    # Final Output Table
    print(
        "\n"
        + tabulate(
            results, headers=["Opponent", "Pure PPO", "Ensemble"], tablefmt="grid"
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
