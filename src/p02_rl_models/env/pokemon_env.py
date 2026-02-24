"""
Reinforcement Learning Environment for Pokemon Showdown.

This module provides the custom environment, wrappers, and action masking
logic required to train MaskablePPO agents on Pokemon Showdown battles.
"""

import numpy as np
import weakref
import logging
from gymnasium import spaces
from poke_env.environment.singles_env import SinglesEnv
from poke_env.environment.single_agent_wrapper import SingleAgentWrapper
from poke_env.player.player import Player
from poke_env.player.battle_order import DefaultBattleOrder, SingleBattleOrder
from poke_env.battle.status import Status
from .vectorizer import StateVectorizer

# --- Monkey-patch Player._handle_battle_message ---
# This patch intercepts low-level Showdown messages to prevent common
# poke-env failure modes like infinite log spam from 'bigerror' or
# deadlocks from unhandled invalid choice errors.

original_handle_battle_message = Player._handle_battle_message


async def patched_handle_battle_message(self, split_messages):
    """
    Patched message handler to filter noisy server messages.

    Args:
        split_messages: List of message parts from the server.
    """
    # Filter out 'bigerror' messages which flood the logs in long battles
    filtered_messages = [
        m for m in split_messages if not (len(m) > 1 and m[1] == "bigerror")
    ]

    # Execute original poke-env logic
    await original_handle_battle_message(self, filtered_messages)

    # Catch specific edge case errors that can cause client/server desync
    for split_message in filtered_messages[1:]:
        if len(split_message) > 2 and split_message[1] == "error":
            if "[Invalid choice]" in split_message[2]:
                logging.getLogger("poke_env").warning(
                    f"Showdown Error: {split_message[2]}"
                )


Player._handle_battle_message = patched_handle_battle_message
# -------------------------------------------------------------------------------------

# Statuses that represent a meaningful debuff inflicted on the opponent
_DEBUFF_STATUSES = {Status.BRN, Status.PAR, Status.TOX}

# Maximum own-side hazard "weight" for penalty normalization:
# Stealth Rock (1/1) + Spikes (3/3) + Toxic Spikes (2/2) + Sticky Web (1/1) = 4 max
_MAX_HAZARD_WEIGHT = 4.0


def _own_hazard_weight(side_conditions: dict) -> float:
    """
    Computes a normalized [0, 1] danger score for hazards on the agent's own side.

    Args:
        side_conditions: Mapping of SideCondition -> stack count from battle.side_conditions.

    Returns:
        Float in [0, 1] representing hazard pressure on own side.
    """
    from poke_env.battle.side_condition import SideCondition, STACKABLE_CONDITIONS

    _TRACKABLE = {
        SideCondition.STEALTH_ROCK: 1,
        SideCondition.SPIKES: 3,
        SideCondition.TOXIC_SPIKES: 2,
        SideCondition.STICKY_WEB: 1,
    }
    weight = 0.0
    for sc, count in side_conditions.items():
        if sc in _TRACKABLE:
            weight += count / _TRACKABLE[sc]
    return min(weight / _MAX_HAZARD_WEIGHT, 1.0)


class PokemonMaskedEnv(SinglesEnv):
    """
    Custom Singles environment with built-in state vectorization.

    Inherits from SinglesEnv to provide a seamless interface with poke-env
    while overriding the state and action mapping for RL compatibility.
    """

    def __init__(self, **kwargs):
        """
        Initializes the environment with a custom state vectorizer and action space.

        Args:
            **kwargs: Arguments passed to the parent SinglesEnv constructor.
        """
        if "battle_format" not in kwargs:
            kwargs["battle_format"] = "gen9randombattle"

        # Disable strict mode to prevent ValueError crashes on minor server/client desyncs
        kwargs["strict"] = False
        super().__init__(**kwargs)

        self.vectorizer = StateVectorizer()

        # Use the pre-computed size from the vectorizer (single source of truth)
        self.observation_space_size = self.vectorizer.obs_size

        # Define the observation space as a flat 1D Box [0.0, 1.0]
        self.observation_spaces = {
            agent: spaces.Box(
                low=0.0,
                high=1.0,
                shape=(self.observation_space_size,),
                dtype=np.float32,
            )
            for agent in self.possible_agents
        }

        # 10 actions: 4 attack slots + 6 switch slots
        self.action_spaces = {
            agent: spaces.Discrete(10) for agent in self.possible_agents
        }

        # Suppress noisy poke-env warnings during training
        logging.getLogger("poke_env").setLevel(logging.ERROR)

    def action_to_order(self, action: int, battle, **kwargs):
        """
        Maps the neural network's integer action back into a valid BattleOrder.

        This mapping is stable and fixed to ensure it matches the action_masks exactly.
        Logic priority: Wait state > Forced Switch > Normal Move > Normal Switch.

        Args:
            action: Integer from 0 to 9.
            battle: The current Battle object.

        Returns:
            A SingleBattleOrder or DefaultBattleOrder.
        """
        # Case 1: Wait state (opponent is choosing)
        if battle._wait:
            return DefaultBattleOrder()

        # Case 2: Force switch (current active Pokemon just fainted)
        if battle.force_switch:
            team = list(battle.team.values())
            switch_idx = action - 4
            if 0 <= switch_idx < len(team):
                pokemon = team[switch_idx]
                if pokemon in battle.available_switches:
                    return SingleBattleOrder(pokemon)
            # Fallback: pick first legal switch
            if battle.available_switches:
                return SingleBattleOrder(battle.available_switches[0])
            return DefaultBattleOrder()

        # Case 3: Normal turn - Attack (actions 0-3)
        if action < 4:
            try:
                moves = list(battle.active_pokemon.moves.values())
                if action < len(moves):
                    move = moves[action]
                    if move in battle.available_moves:
                        return SingleBattleOrder(move)
            except Exception:
                pass

        # Case 4: Normal turn - Switch (actions 4-9)
        if action >= 4:
            try:
                team = list(battle.team.values())
                team_idx = action - 4
                if team_idx < len(team):
                    pokemon = team[team_idx]
                    if pokemon in battle.available_switches:
                        return SingleBattleOrder(pokemon)
            except Exception:
                pass

        # Final Fallback: Return any legal order to prevent a server hang
        if battle.valid_orders:
            return battle.valid_orders[0]
        return DefaultBattleOrder()

    def embed_battle(self, battle):
        """Overrides parent method to use the custom StateVectorizer."""
        return self.vectorizer.embed_battle(battle)

    def calc_reward(self, battle) -> float:
        """
        Calculates a dense reward signal for the current battle state.

        Combines sparse victory rewards with dense turn-by-turn signals
        reflecting HP damage, stat boosts, hazards, and status conditions.

        Args:
            battle: Current Battle state.

        Returns:
            Float representing the reward for this transition.
        """
        # 1. Base Sparse Reward (HP changes and Victory/Defeat)
        base_reward = self.reward_computing_helper(
            battle,
            fainted_value=2.0,
            hp_value=1.0,
            victory_value=30.0,
        )

        custom_current_value = 0.0

        if (
            battle.active_pokemon is not None
            and battle.opponent_active_pokemon is not None
        ):
            # 2. Offensive Boost Reward (Swords Dance, Nasty Plot, etc.)
            boost_sum = sum(
                battle.active_pokemon.boosts.get(stat, 0)
                for stat in ["atk", "spa", "spe"]
            )
            if boost_sum > 0:
                custom_current_value += boost_sum * 0.3

            # 3. Negative Boost Penalty (Intimidate, sticky web speed drop, etc.)
            neg_boost_sum = sum(
                min(0, battle.active_pokemon.boosts.get(stat, 0))
                for stat in ["atk", "def", "spa", "spd", "spe"]
            )
            # neg_boost_sum is <= 0; scale so -6 per stat → -0.6 max penalty
            custom_current_value += neg_boost_sum * 0.1

            # 4. Status Infliction Reward (Burn, Paralysis, Toxic on opponent)
            opp = battle.opponent_active_pokemon
            if opp is not None and opp.status in _DEBUFF_STATUSES:
                custom_current_value += 0.3

        # 5. Opponent Hazard Reward (Stealth Rock / Spikes on their side)
        if battle.opponent_side_conditions:
            custom_current_value += len(battle.opponent_side_conditions) * 0.5

        # 6. Own Hazard Penalty (hazards on our side hurt us)
        if battle.side_conditions:
            hazard_score = _own_hazard_weight(battle.side_conditions)
            custom_current_value -= hazard_score * 1.0

        # Initialize reward buffer if needed
        if not hasattr(self, "_custom_reward_buffer"):
            self._custom_reward_buffer = weakref.WeakKeyDictionary()

        if battle not in self._custom_reward_buffer:
            self._custom_reward_buffer[battle] = 0.0

        # Delta-based update prevents double-rewarding static boards
        custom_reward_delta = custom_current_value - self._custom_reward_buffer[battle]
        self._custom_reward_buffer[battle] = custom_current_value

        # 7. Stall Penalty — reduced from -0.05 to -0.02 to allow tactical switching
        action_penalty = -0.02

        return base_reward + custom_reward_delta + action_penalty


class PokemonMaskedEnvWrapper(SingleAgentWrapper):
    """
    Gym wrapper that generates action masks for MaskablePPO.

    Ensures that the agent only attempts actions which are legal in the
    current Showdown battle state.
    """

    def __init__(self, env: PokemonMaskedEnv, opponent: Player):
        super().__init__(env, opponent)

    def action_masks(self) -> np.ndarray:
        """
        Generates binary action mask corresponding to 0-9 action space.

        The mask is kept in strict alignment with action_to_order:
          - Slots 0-3: move slots ordered by battle.active_pokemon.moves (dict iteration order)
          - Slots 4-9: team slots ordered by battle.team (dict iteration order)

        Returns:
            A binary numpy array (1 = valid, 0 = invalid).
        """
        battle = self.env.agent1.battle
        mask = np.zeros(self.action_space.n, dtype=np.int8)

        # No active battle or waiting for opponent
        if battle is None or battle._wait:
            mask[0] = 1  # Safety pass
            return mask

        # Forced Switch Logic
        if battle.force_switch:
            available_switch_names = [p.name for p in battle.available_switches]
            team_names = list(battle.team.keys())
            for i, p_name in enumerate(team_names):
                if i < 6 and p_name in available_switch_names:
                    mask[4 + i] = 1  # Slots 4-9 are switches

            if not mask.any():
                mask[4] = 1  # Absolute safety fallback
            return mask

        # Normal Turn: Move masking (0-3)
        available_move_ids = [m.id for m in battle.available_moves]
        move_ids = (
            list(battle.active_pokemon.moves.keys()) if battle.active_pokemon else []
        )
        for i, m_id in enumerate(move_ids):
            if i < 4 and m_id in available_move_ids:
                mask[i] = 1

        # Normal Turn: Switch masking (4-9)
        available_switch_names = [p.name for p in battle.available_switches]
        team_names = list(battle.team.keys())
        for i, p_name in enumerate(team_names):
            if i < 6 and p_name in available_switch_names:
                mask[4 + i] = 1

        # Safety catch for zero-valid-action turns
        if not mask.any() and battle.valid_orders:
            mask[0] = 1

        return mask


class GauntletEnvWrapper(PokemonMaskedEnvWrapper):
    """
    Phase 3 "Gauntlet" Environment Wrapper.

    This wrapper inherits action masking and the 238-dimensional observation space
    from `PokemonMaskedEnvWrapper`, but it introduces aggressive reward shaping
    specifically designed to combat Cathedral Forgetting and Heuristic Deadlocking.

    Design Goals:
    1. Eradicate Stalling: The base wrapper penalized -0.02 per turn. This wrapper
       increases that to -0.1 per turn, heavily punishing infinite switching loops.
    2. Over-value Knockouts: Instead of the default +30 for a win, this wrapper
       boosts the victory reward to +100, ensuring the RL agent prioritizes actual
       match conclusions over farming in-game status conditions.
    """

    def step(self, action: int):
        """
        Executes a single environment step, intercepting the reward vector.
        """
        obs, reward, terminated, truncated, info = super().step(action)

        # 1. Aggressive Stall Penalty: -0.1 per action taken
        reward -= 0.1

        # 2. Victory/Defeat Multiplier Calculation
        # The base poke-env architecture assigns +30 for a win and -30 for a loss.
        # We intercept this base calculation at the end of the battle.
        battle = self.env.agent1.battle
        if battle.finished:
            if battle.won:
                # Base is +30. We add +70 to reach the +100 target reward for Phase 3.
                reward += 70.0
            elif battle.lost:
                # Base is -30. We subtract 70 to reach a steep -100 penalty for losing.
                reward -= 70.0
            elif battle.lost:
                reward -= 70.0  # -30 (base) - 70 = -100 Total

        return obs, reward, terminated, truncated, info
