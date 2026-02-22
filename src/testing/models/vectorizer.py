"""
State vectorization for Pokemon Showdown.

Converts complex Battle objects from poke-env into flattened 1D numpy arrays
suitable for consumption by neural network policies.
"""

import numpy as np
from poke_env.battle import Battle
from poke_env.battle.pokemon_type import PokemonType
from poke_env.battle.status import Status
from poke_env.battle.weather import Weather
from poke_env.battle.field import Field
from poke_env.battle.side_condition import SideCondition, STACKABLE_CONDITIONS

# Maximum base power used for normalization (higher than standard so Sheer Cold etc. are clipped)
_MAX_BASE_POWER = 250.0

# Only hazard-type side conditions worth tracking as danger signals
_HAZARD_CONDITIONS = {
    SideCondition.STEALTH_ROCK: 1,
    SideCondition.SPIKES: 3,
    SideCondition.TOXIC_SPIKES: 2,
    SideCondition.STICKY_WEB: 1,
}


class StateVectorizer:
    """
    Handles the transformation of game states into numerical tensors.

    The resulting vector is fixed-size and normalized where possible to
    assist in neural network training stability.

    Observation layout (all float32, values in [0,1]):
    ┌──────────────────────────────────────────────────────┬────────┐
    │ Component                                            │  Dims  │
    ├──────────────────────────────────────────────────────┼────────┤
    │ Own active Pokémon (HP, types, status, boosts)       │  1+T+S+7│
    │ Opp active Pokémon (HP, types, status, boosts)       │  1+T+S+7│
    │ Own active moves (4 × [18 types + 1 BP])             │   76   │
    │ Own bench HP fractions (6 slots)                     │    6   │
    │ Opp bench HP + estimated alive (6 + 1)               │    7   │
    │ Environment (weather + field conditions)             │  W+F   │
    │ Own side conditions (24 dims)                        │   SC   │
    │ Opp side conditions (24 dims)                        │   SC   │
    └──────────────────────────────────────────────────────┴────────┘
    Total: 2*(1+T+S+7) + 76 + 6 + 7 + W + F + 2*SC
    """

    NUM_MOVE_SLOTS = 4

    def __init__(self):
        """Initializes the vectorizer with fixed sizes for all categorical game elements."""
        self.num_types = len(PokemonType)
        self.num_statuses = len(Status)
        self.num_weathers = len(Weather)
        self.num_fields = len(Field)
        self.num_side_conditions = len(SideCondition)

        # 7 stats: atk, def, spa, spd, spe, accuracy, evasion
        self.num_boosts = 7

        # 4 move slots × (num_types + 1 BP) = e.g. 4 × 19 = 76
        self.move_dims = self.NUM_MOVE_SLOTS * (self.num_types + 1)

        # Pre-compute total size for rl_env.py to use
        active_dims = 1 + self.num_types + self.num_statuses + self.num_boosts
        self.obs_size = (
            2 * active_dims
            + self.move_dims
            + 6
            + 7
            + self.num_weathers
            + self.num_fields
            + 2 * self.num_side_conditions
        )

    def embed_battle(self, battle: Battle) -> np.ndarray:
        """
        Flattens the entire battle state into a 1D tensor.

        Args:
            battle: The current Battle object from poke-env.

        Returns:
            A 1D float32 numpy array representing the global game state.
        """
        me_active = self._embed_active_pokemon(battle.active_pokemon)
        opp_active = self._embed_active_pokemon(battle.opponent_active_pokemon)

        me_moves = self._embed_moves(battle.active_pokemon)

        me_bench = self._embed_team(battle.team)
        opp_bench = self._embed_opponent_team(battle.opponent_team, battle.team_size)

        environment = self._embed_environment(battle)

        me_side = self._embed_side_conditions(battle.side_conditions)
        opp_side = self._embed_side_conditions(battle.opponent_side_conditions)

        state_vector = np.concatenate([
            me_active,
            opp_active,
            me_moves,
            me_bench,
            opp_bench,
            environment,
            me_side,
            opp_side,
        ], dtype=np.float32)

        return state_vector

    def _embed_active_pokemon(self, pokemon) -> np.ndarray:
        """
        Extracts and normalizes features for a single active Pokemon.

        Args:
            pokemon: The active Pokemon object or None.

        Returns:
            A sub-vector with normalized HP, types, status, and boosts.
        """
        if pokemon is None:
            size = 1 + self.num_types + self.num_statuses + self.num_boosts
            return np.zeros(size, dtype=np.float32)

        # HP: Normalized [0, 1]
        hp = np.array([pokemon.current_hp_fraction], dtype=np.float32)

        # Types: Multi-hot encoding
        type_vector = np.zeros(self.num_types, dtype=np.float32)
        for t in pokemon.types:
            if t is not None:
                type_vector[t.value - 1] = 1.0

        # Status: One-hot encoding
        status_vector = np.zeros(self.num_statuses, dtype=np.float32)
        if pokemon.status is not None:
            status_vector[pokemon.status.value - 1] = 1.0

        # Stat Boosts: Normalized [-6, 6] → [0, 1]
        boost_vector = np.zeros(self.num_boosts, dtype=np.float32)
        boost_keys = ['atk', 'def', 'spa', 'spd', 'spe', 'accuracy', 'evasion']
        for i, stat in enumerate(boost_keys):
            raw_boost = pokemon.boosts.get(stat, 0)
            boost_vector[i] = (raw_boost + 6.0) / 12.0

        return np.concatenate([hp, type_vector, status_vector, boost_vector])

    def _embed_moves(self, pokemon) -> np.ndarray:
        """
        Encodes the type and base power for each of the active Pokémon's 4 move slots.

        Args:
            pokemon: The active Pokemon object or None.

        Returns:
            A vector of shape (NUM_MOVE_SLOTS * (num_types + 1),).
            Each slot contains: [type_multi_hot (18), base_power_norm (1)].
            Empty slots are zero-padded.
        """
        result = np.zeros(self.move_dims, dtype=np.float32)
        if pokemon is None:
            return result

        moves = list(pokemon.moves.values())
        slot_size = self.num_types + 1  # type dims + 1 BP dim

        for i in range(min(self.NUM_MOVE_SLOTS, len(moves))):
            move = moves[i]
            offset = i * slot_size

            # Move type (multi-hot, but a move has exactly 1 type)
            if move.type is not None:
                result[offset + move.type.value - 1] = 1.0

            # Base power normalized by ceiling value
            bp = move.base_power if move.base_power is not None else 0
            result[offset + self.num_types] = min(bp / _MAX_BASE_POWER, 1.0)

        return result

    def _embed_team(self, team: dict) -> np.ndarray:
        """
        Extracts current HP fractions for all team members.

        Args:
            team: The dictionary of player team members.

        Returns:
            A vector of 6 HP values.
        """
        team_hps = np.zeros(6, dtype=np.float32)
        for i, (_, mon) in enumerate(list(team.items())[:6]):
            team_hps[i] = mon.current_hp_fraction
        return team_hps

    def _embed_opponent_team(self, opp_team: dict, opp_team_size: int) -> np.ndarray:
        """
        Estimates the HP fractions and total alive count of the opponent team.

        Args:
            opp_team: Dictionary of revealed opponent team members.
            opp_team_size: Total number of Pokemon on the opponent team.

        Returns:
            A vector of 6 known HPs + 1 total alive estimate (normalized).
        """
        team_info = np.zeros(7, dtype=np.float32)
        revealed_alive = 0

        for i, (_, mon) in enumerate(list(opp_team.items())[:6]):
            team_info[i] = mon.current_hp_fraction
            if not mon.fainted:
                revealed_alive += 1

        # Unrevealed Pokémon are assumed alive
        unrevealed = max(0, opp_team_size - len(opp_team))
        team_info[6] = (revealed_alive + unrevealed) / 6.0

        return team_info

    def _embed_environment(self, battle: Battle) -> np.ndarray:
        """
        Encodes weather and terrain conditions using multi-hot encoding.

        Args:
            battle: Current Battle object.

        Returns:
            A concatenated vector of weather and field conditions.
        """
        weather_vector = np.zeros(self.num_weathers, dtype=np.float32)
        if battle.weather:
            for w in battle.weather.keys():
                weather_vector[w.value - 1] = 1.0

        field_vector = np.zeros(self.num_fields, dtype=np.float32)
        if battle.fields:
            for f in battle.fields.keys():
                field_vector[f.value - 1] = 1.0

        return np.concatenate([weather_vector, field_vector])

    def _embed_side_conditions(self, side_conditions: dict) -> np.ndarray:
        """
        Encodes all side conditions for one side of the field.

        For non-stackable conditions the value is binary (0 or 1).
        For stackable conditions (Spikes ×3, Toxic Spikes ×2) the value is
        normalized by the maximum stack count so it stays in [0, 1].

        Args:
            side_conditions: Mapping of SideCondition → stack count.

        Returns:
            A vector of shape (num_side_conditions,).
        """
        vector = np.zeros(self.num_side_conditions, dtype=np.float32)
        for sc, count in side_conditions.items():
            idx = sc.value - 1
            max_stack = STACKABLE_CONDITIONS.get(sc, 1)
            vector[idx] = min(count / max_stack, 1.0)
        return vector


if __name__ == "__main__":
    # Quick sanity-check: instantiate and verify obs_size is consistent
    v = StateVectorizer()
    print(f"Observation size: {v.obs_size}")
    print(f"  active dims:      2 × {1 + v.num_types + v.num_statuses + v.num_boosts}")
    print(f"  move dims:        {v.move_dims}  (4 × {v.num_types + 1})")
    print(f"  bench dims:       6 + 7")
    print(f"  env dims:         {v.num_weathers} + {v.num_fields}")
    print(f"  side cond dims:   2 × {v.num_side_conditions}")