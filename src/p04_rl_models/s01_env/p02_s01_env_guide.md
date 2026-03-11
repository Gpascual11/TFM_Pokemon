# s01_env: RL Environment and Vectorization

This module defines how the Pokémon battle is "seen" and "acted upon" by the Reinforcement Learning agent.

## Components

### `pokemon_env.py`
- Inherits from `poke_env.player.Player`.
- **`embed_battle`**: Converts the incoming game state into numerical data.
- **`action_to_order`**: Maps the agent's chosen index (0-9) back into a valid Pokémon Showdown order.
- **`calc_reward`**: The reward function. It rewards dealing damage and KOing foes, while penalizing being KO'd or stalling needlessly.

### `vectorizer.py`
- A utility class that handles the heavy lifting of state encoding.
- Maps 18+ types, 7 statuses, and stat stages into normalized float ranges [0, 1].

---

## How it works

The environment is wrapped in a **`PokemonMaskedEnvWrapper`**. 
- It provides **Action Masks**: a bitmask where `1` means the action is currently legal and `0` means it is illegal.
- This mask is fed directly into the `MaskablePPO` algorithm from `sb3-contrib`, ensuring the agent never "crashes" the simulator by attempting an impossible move.
