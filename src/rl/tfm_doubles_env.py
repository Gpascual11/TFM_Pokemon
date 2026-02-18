from __future__ import annotations

import numpy as np
from gymnasium.spaces import Box

from poke_env.battle.double_battle import DoubleBattle
from poke_env.environment.doubles_env import DoublesEnv


class TFMDoublesEnv(DoublesEnv):
    """
    A minimal Gen9 Random Doubles RL environment.

    This extends poke-env's DoublesEnv by defining:
    - observation space (Box)
    - embed_battle (state embedding)
    - calc_reward (dense, symmetric reward)
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Observation vector:
        # For each of our 2 active mons:
        #  - 4 moves base power (scaled /100, -1 for missing)
        #  - 4 moves max dmg multiplier vs either opponent active (default 1)
        #  - 1 self hp fraction
        # Opponent actives:
        #  - 2 hp fractions
        # Teams:
        #  - fainted fraction (us, opp)
        # Misc:
        #  - turn fraction (min(turn, 50)/50)
        #
        # Total = 2 * (4 + 4 + 1) + 2 + 2 + 1 = 23
        self._obs_len = 23

        low = np.array([-1.0] * 16 + [0.0] * 7, dtype=np.float32)
        high = np.array([3.0] * 4 + [4.0] * 4 + [1.0] + [3.0] * 4 + [4.0] * 4 + [1.0] + [1.0] * 2 + [1.0] * 2 + [1.0], dtype=np.float32)

        assert low.shape == (self._obs_len,)
        assert high.shape == (self._obs_len,)

        self.observation_spaces = {
            agent: Box(low=low, high=high, dtype=np.float32) for agent in self.possible_agents
        }

    def calc_reward(self, battle: DoubleBattle) -> float:
        # Dense reward based on relative team HP, KOs, and victory.
        return float(
            self.reward_computing_helper(
                battle,
                fainted_value=2.0,
                hp_value=1.0,
                victory_value=30.0,
            )
        )

    def embed_battle(self, battle: DoubleBattle) -> np.ndarray:
        # Move features for each of our 2 active mons
        moves_base_power = -np.ones((2, 4), dtype=np.float32)
        moves_dmg_multiplier = np.ones((2, 4), dtype=np.float32)
        self_hp = np.ones(2, dtype=np.float32)

        opp_actives = [m for m in (battle.opponent_active_pokemon[:2] or []) if m and not m.fainted]

        for pos in range(2):
            active = battle.active_pokemon[pos] if battle.active_pokemon and pos < len(battle.active_pokemon) else None
            if not active or active.fainted:
                self_hp[pos] = 0.0
                continue

            # HP fraction
            hp_frac = getattr(active, "current_hp_fraction", None)
            if hp_frac is None:
                chp = getattr(active, "current_hp", None)
                mhp = getattr(active, "max_hp", None)
                if chp is not None and mhp:
                    hp_frac = chp / mhp
                else:
                    hp_frac = 1.0
            self_hp[pos] = float(np.clip(hp_frac, 0.0, 1.0))

            # Available moves at this position
            available = []
            if battle.available_moves and pos < len(battle.available_moves) and battle.available_moves[pos]:
                available = list(battle.available_moves[pos])[:4]

            for i, move in enumerate(available):
                moves_base_power[pos, i] = float((move.base_power or 0) / 100.0)
                if move.type and opp_actives:
                    best = 1.0
                    for opp in opp_actives:
                        best = max(
                            best,
                            move.type.damage_multiplier(getattr(opp, "type_1", None), getattr(opp, "type_2", None)),
                        )
                    moves_dmg_multiplier[pos, i] = float(best)

        # Opponent active hp fractions
        opp_hp = np.zeros(2, dtype=np.float32)
        for j in range(2):
            opp = battle.opponent_active_pokemon[j] if battle.opponent_active_pokemon and j < len(battle.opponent_active_pokemon) else None
            if not opp or opp.fainted:
                opp_hp[j] = 0.0
                continue
            hp_frac = getattr(opp, "current_hp_fraction", None)
            if hp_frac is None:
                chp = getattr(opp, "current_hp", None)
                mhp = getattr(opp, "max_hp", None)
                if chp is not None and mhp:
                    hp_frac = chp / mhp
                else:
                    hp_frac = 1.0
            opp_hp[j] = float(np.clip(hp_frac, 0.0, 1.0))

        fainted_us = len([m for m in battle.team.values() if m.fainted]) / 6.0
        fainted_opp = len([m for m in battle.opponent_team.values() if m.fainted]) / 6.0

        turn_frac = min(float(getattr(battle, "turn", 0) or 0), 50.0) / 50.0

        obs = np.concatenate(
            [
                moves_base_power.flatten(),
                moves_dmg_multiplier.flatten(),
                self_hp,
                opp_hp,
                np.array([fainted_us, fainted_opp, turn_frac], dtype=np.float32),
            ]
        ).astype(np.float32)

        # Defensive sanity check (helps catch poke-env changes)
        if obs.shape != (self._obs_len,):
            raise ValueError(f"Observation has shape {obs.shape}, expected ({self._obs_len},)")
        return obs

