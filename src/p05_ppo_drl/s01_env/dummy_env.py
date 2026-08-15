"""Tiny Gym env with the frozen obs/action spaces. No Showdown. For CUDA / untrained init."""

from __future__ import annotations

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from ..constants import ACTION_N
from ..s01_env.vectorizer import OBS_SIZE


class DummyMaskedEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, obs_size: int | None = None):
        super().__init__()
        n = int(obs_size or OBS_SIZE)
        self.observation_space = spaces.Box(0.0, 1.0, shape=(n,), dtype=np.float32)
        self.action_space = spaces.Discrete(ACTION_N)
        self._obs_size = n

    def action_masks(self) -> np.ndarray:
        mask = np.zeros(ACTION_N, dtype=np.int8)
        mask[0] = 1
        return mask

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        return np.zeros(self._obs_size, dtype=np.float32), {}

    def step(self, action):
        return np.zeros(self._obs_size, dtype=np.float32), 0.0, True, False, {}
