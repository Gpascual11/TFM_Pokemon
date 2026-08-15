"""Gymnasium SinglesEnv for MaskablePPO on gen9randombattle.

Action space is Discrete(14): 4 moves, 4 moves+Tera, 6 switches.
Masks and orders live in ``actions.py`` so eval players use the same mapping.
"""

from __future__ import annotations

import logging
import weakref

import numpy as np
from gymnasium import spaces
from poke_env.battle.status import Status
from poke_env.environment.single_agent_wrapper import SingleAgentWrapper
from poke_env.environment.singles_env import SinglesEnv
from poke_env.player.player import Player

from ..constants import ACTION_N, BATTLE_FORMAT
from .actions import action_masks as compute_action_masks
from .actions import action_to_order as map_action_to_order
from .actions import order_to_action as map_order_to_action
from .vectorizer import OBS_SIZE, StateVectorizer

original_handle_battle_message = Player._handle_battle_message


async def patched_handle_battle_message(self, split_messages):
    """Drop bulky ``bigerror`` frames that spam logs and can desync training."""
    filtered_messages = [m for m in split_messages if not (len(m) > 1 and m[1] == "bigerror")]
    await original_handle_battle_message(self, filtered_messages)


Player._handle_battle_message = patched_handle_battle_message

_DEBUFF_STATUSES = {Status.BRN, Status.PAR, Status.TOX}
_MAX_HAZARD_WEIGHT = 4.0


def _own_hazard_weight(side_conditions: dict) -> float:
    from poke_env.battle.side_condition import SideCondition

    trackable = {
        SideCondition.STEALTH_ROCK: 1,
        SideCondition.SPIKES: 3,
        SideCondition.TOXIC_SPIKES: 2,
        SideCondition.STICKY_WEB: 1,
    }
    weight = 0.0
    for sc, count in side_conditions.items():
        if sc in trackable:
            weight += count / trackable[sc]
    return min(weight / _MAX_HAZARD_WEIGHT, 1.0)


class PokemonMaskedEnv(SinglesEnv):
    """poke-env ``SinglesEnv`` with frozen obs/action spaces and ``strict=False``."""

    def __init__(self, **kwargs):
        kwargs.setdefault("battle_format", BATTLE_FORMAT)
        kwargs["strict"] = False
        super().__init__(**kwargs)
        self.vectorizer = StateVectorizer()
        self.observation_space_size = self.vectorizer.obs_size
        assert self.observation_space_size == OBS_SIZE
        self.observation_spaces = {
            agent: spaces.Box(low=0.0, high=1.0, shape=(OBS_SIZE,), dtype=np.float32)
            for agent in self.possible_agents
        }
        self.action_spaces = {agent: spaces.Discrete(ACTION_N) for agent in self.possible_agents}
        logging.getLogger("poke_env").setLevel(logging.ERROR)

    @staticmethod
    def action_to_order(action, battle, fake: bool = False, strict: bool = True, **kwargs):
        return map_action_to_order(action, battle, fake=fake, strict=strict)

    @staticmethod
    def order_to_action(order, battle, fake: bool = False, strict: bool = True):
        return map_order_to_action(order, battle, fake=fake, strict=strict)

    def embed_battle(self, battle):
        return self.vectorizer.embed_battle(battle)

    def get_additional_info(self):
        info = super().get_additional_info()
        battle = self.battle1
        payload = {
            "battle_finished": 0,
            "battle_won": 0,
            "turn": 0,
        }
        if battle is not None:
            payload["turn"] = int(getattr(battle, "turn", 0) or 0)
            if getattr(battle, "finished", False):
                payload["battle_finished"] = 1
                payload["battle_won"] = 1 if getattr(battle, "won", False) else 0
        if self.possible_agents:
            info[self.possible_agents[0]] = payload
        return info

    def calc_reward(self, battle) -> float:
        base_reward = self.reward_computing_helper(
            battle,
            fainted_value=2.0,
            hp_value=1.0,
            victory_value=30.0,
        )
        custom_current_value = 0.0
        if battle.active_pokemon is not None and battle.opponent_active_pokemon is not None:
            boost_sum = sum(battle.active_pokemon.boosts.get(stat, 0) for stat in ["atk", "spa", "spe"])
            if boost_sum > 0:
                custom_current_value += boost_sum * 0.3
            neg_boost_sum = sum(
                min(0, battle.active_pokemon.boosts.get(stat, 0)) for stat in ["atk", "def", "spa", "spd", "spe"]
            )
            custom_current_value += neg_boost_sum * 0.1
            opp = battle.opponent_active_pokemon
            if opp is not None and opp.status in _DEBUFF_STATUSES:
                custom_current_value += 0.3
        if battle.opponent_side_conditions:
            custom_current_value += len(battle.opponent_side_conditions) * 0.5
        if battle.side_conditions:
            custom_current_value -= _own_hazard_weight(battle.side_conditions) * 1.0
        if not hasattr(self, "_custom_reward_buffer"):
            self._custom_reward_buffer = weakref.WeakKeyDictionary()
        if battle not in self._custom_reward_buffer:
            self._custom_reward_buffer[battle] = 0.0
        custom_reward_delta = custom_current_value - self._custom_reward_buffer[battle]
        self._custom_reward_buffer[battle] = custom_current_value
        return base_reward + custom_reward_delta - 0.02


class PokemonMaskedEnvWrapper(SingleAgentWrapper):
    """Single-agent Gym wrapper exposing ``action_masks()`` for MaskablePPO."""

    def __init__(self, env: PokemonMaskedEnv, opponent: Player):
        super().__init__(env, opponent)

    def action_masks(self) -> np.ndarray:
        battle = self.env.agent1.battle
        return compute_action_masks(battle)

    def step(self, action: int):
        obs, reward, terminated, truncated, info = super().step(action)
        battle = self.env.agent1.battle
        info.setdefault("battle_finished", 0)
        info.setdefault("battle_won", 0)
        info.setdefault("turn", 0)
        if battle is not None:
            info["turn"] = int(getattr(battle, "turn", 0) or 0)
            if getattr(battle, "finished", False):
                info["battle_finished"] = 1
                info["battle_won"] = 1 if getattr(battle, "won", False) else 0
        return obs, reward, terminated, truncated, info
