"""PPO as a poke-env Player. Always uses action_to_order (never SimpleHeuristics)."""

from __future__ import annotations

import numpy as np
import torch
from poke_env.player.battle_order import DefaultBattleOrder
from poke_env.player.player import Player

from .._bootstrap import ensure_src_path
from ..constants import ACTION_N, BATTLE_FORMAT
from ..s01_env.actions import action_masks, action_to_order, order_to_action
from ..s01_env.vectorizer import StateVectorizer

ensure_src_path()


def _predict_action(model, obs: np.ndarray, mask: np.ndarray) -> int:
    """MaskablePPO.predict does not forward action_masks — use the policy."""
    masks = np.asarray(mask, dtype=np.int8)
    if masks.ndim == 1:
        pass
    action, _ = model.policy.predict(obs, deterministic=True, action_masks=masks)
    return int(np.asarray(action).reshape(-1)[0])


class PPOPlayer(Player):
    """Pure MaskablePPO. Default eval agent."""

    def __init__(self, model, vectorizer: StateVectorizer | None = None, **kwargs):
        kwargs.setdefault("battle_format", BATTLE_FORMAT)
        super().__init__(**kwargs)
        self.model = model
        self.vectorizer = vectorizer or StateVectorizer()

    def choose_move(self, battle):
        if getattr(battle, "_wait", False):
            return DefaultBattleOrder()
        obs = self.vectorizer.embed_battle(battle)
        mask = action_masks(battle)
        action = _predict_action(self.model, obs, mask)
        return action_to_order(action, battle, strict=False)


class HybridPPOv12Player(Player):
    """Ablation: mix MaskablePPO with HeuristicV12. Not poke-env SimpleHeuristics."""

    def __init__(self, model, alpha: float = 0.5, vectorizer: StateVectorizer | None = None, **kwargs):
        kwargs.setdefault("battle_format", BATTLE_FORMAT)
        super().__init__(**kwargs)
        self.model = model
        self.alpha = float(alpha)
        self.vectorizer = vectorizer or StateVectorizer()
        from p01_heuristics.agents import get_agent_class

        self._v12 = get_agent_class("v12")(
            battle_format=BATTLE_FORMAT,
            start_listening=False,
        )

    def teampreview(self, battle) -> str:
        return self._v12.teampreview(battle)

    def choose_move(self, battle):
        if getattr(battle, "_wait", False):
            return DefaultBattleOrder()
        obs = self.vectorizer.embed_battle(battle)
        mask = action_masks(battle)
        obs_t = torch.as_tensor(obs, device=self.model.device).unsqueeze(0)
        with torch.no_grad():
            dist = self.model.policy.get_distribution(obs_t, action_masks=mask.reshape(1, -1))
            ppo_probs = dist.distribution.probs[0].detach().cpu().numpy()
        v12_order = self._v12.choose_move(battle)
        v12_idx = int(order_to_action(v12_order, battle, strict=False))
        heur = np.zeros(ACTION_N, dtype=np.float64)
        if 0 <= v12_idx < ACTION_N:
            heur[v12_idx] = 1.0
        combined = self.alpha * ppo_probs + (1.0 - self.alpha) * heur
        combined = combined * mask.astype(np.float64)
        if combined.sum() <= 0:
            combined = mask.astype(np.float64)
        action = int(np.argmax(combined))
        return action_to_order(action, battle, strict=False)
