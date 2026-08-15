"""Behavioral cloning of a heuristic teacher into MaskablePPO. No Showdown in unit tests.

Phase 2 cloned V8-vs-V8. Phase 4 clones V14 actions with V12 as the foe so states
match eval. Never label Phase 4 as “BC from V12”.
"""

from __future__ import annotations

import numpy as np
import torch
from poke_env.ps_client.account_configuration import AccountConfiguration

from ..constants import ACTION_N, BATTLE_FORMAT, DEVICE, SWITCH_OFFSET
from ..s01_env.actions import action_masks, order_to_action
from ..s01_env.vectorizer import StateVectorizer
from .opponents import make_eval_player
from .showdown import close_ps_clients, server_configuration

DEFAULT_BC_LR = 1e-3
DEFAULT_BC_EPOCHS = 15


def _recording_expert(server_config, name: str, expert: str):
    from p01_heuristics.agents import get_agent_class

    base = get_agent_class(expert)

    class RecordingExpert(base):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.samples: list[tuple[np.ndarray, np.ndarray, int]] = []
            self._vectorizer = StateVectorizer()

        def choose_move(self, battle):
            order = super().choose_move(battle)
            try:
                obs = self._vectorizer.embed_battle(battle)
                mask = action_masks(battle)
                act = int(order_to_action(order, battle, strict=False))
                if 0 <= act < ACTION_N and int(mask[act]) == 1:
                    self.samples.append((obs, mask.astype(np.int8), act))
            except Exception:
                pass
            return order

    return RecordingExpert(
        battle_format=BATTLE_FORMAT,
        server_configuration=server_config,
        account_configuration=AccountConfiguration(name, None),
        max_concurrent_battles=4,
        start_listening=True,
    )


async def _collect(port: int, games: int, expert: str, foe: str) -> list[tuple[np.ndarray, np.ndarray, int]]:
    cfg = server_configuration(port)
    teacher = _recording_expert(cfg, f"BC{expert}{port}", expert)
    opp = make_eval_player(foe, server_config=cfg, name=f"BCfoe{port}", max_concurrent=4)
    try:
        await teacher.battle_against(opp, n_battles=games)
    finally:
        await close_ps_clients(teacher, opp)
    return teacher.samples


def _actor_params(model):
    return list(model.policy.mlp_extractor.policy_net.parameters()) + list(model.policy.action_net.parameters())


@torch.no_grad()
def bc_agreement(model, obs: torch.Tensor, masks: np.ndarray, acts: torch.Tensor) -> tuple[float, float, float]:
    dist = model.policy.get_distribution(obs, action_masks=masks)
    pred = dist.distribution.probs.argmax(dim=-1)
    agree = float((pred == acts).float().mean())
    switch_lab = float((acts >= SWITCH_OFFSET).float().mean())
    switch_pred = float((pred >= SWITCH_OFFSET).float().mean())
    return agree, switch_lab, switch_pred


def fit_policy_ce(
    model,
    obs: torch.Tensor,
    masks: np.ndarray,
    acts: torch.Tensor,
    *,
    lr: float = DEFAULT_BC_LR,
    epochs: int = DEFAULT_BC_EPOCHS,
    batch_size: int = 256,
    expert_label: str = "expert",
) -> None:
    """Cross-entropy on the actor only. Do not reuse PPO's 5e-5 Adam."""
    model.policy.train()
    opt = torch.optim.Adam(_actor_params(model), lr=lr, eps=1e-5)
    n = int(acts.shape[0])
    idx = np.arange(n)
    agree0, sw_lab, sw_pred0 = bc_agreement(model, obs, masks, acts)
    print(
        f"BC before: agree={agree0:.1%}  {expert_label}_switch={sw_lab:.1%}  "
        f"policy_switch={sw_pred0:.1%}  lr={lr}",
        flush=True,
    )
    for ep in range(epochs):
        np.random.shuffle(idx)
        total = 0.0
        steps = 0
        for start in range(0, n, batch_size):
            sl = idx[start : start + batch_size]
            dist = model.policy.get_distribution(obs[sl], action_masks=masks[sl])
            loss = -dist.log_prob(acts[sl]).mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
            total += float(loss.item())
            steps += 1
        print(f"BC epoch {ep + 1}/{epochs} loss={total / max(steps, 1):.4f}", flush=True)
    agree1, _, sw_pred1 = bc_agreement(model, obs, masks, acts)
    print(
        f"BC after:  agree={agree1:.1%}  {expert_label}_switch={sw_lab:.1%}  policy_switch={sw_pred1:.1%}",
        flush=True,
    )
    if sw_lab > 0.05 and sw_pred1 < 0.5 * sw_lab:
        print(
            f"BC warning: policy still almost never switches. PPO vs the eval foe will stay near the floor.",
            flush=True,
        )


def imitate_heuristic(
    model,
    *,
    port: int,
    games: int,
    expert: str = "v8",
    foe: str | None = None,
    epochs: int = DEFAULT_BC_EPOCHS,
    batch_size: int = 256,
    lr: float = DEFAULT_BC_LR,
) -> int:
    """Clone ``expert`` actions (foe defaults to the same agent). Returns sample count."""
    import asyncio

    if games <= 0:
        return 0
    foe = foe or expert
    print(f"BC from {expert.upper()}: collecting {games} {expert}-vs-{foe} games on port {port}…", flush=True)
    samples = asyncio.run(_collect(port, games, expert, foe))
    if not samples:
        print("BC: no samples — skipping.", flush=True)
        return 0
    obs = torch.as_tensor(np.stack([s[0] for s in samples]), device=DEVICE)
    masks = np.stack([s[1] for s in samples])
    acts = torch.as_tensor(np.array([s[2] for s in samples], dtype=np.int64), device=DEVICE)
    print(f"BC: {len(samples)} decisions, {epochs} epochs, lr={lr} (not PPO lr)", flush=True)
    fit_policy_ce(
        model,
        obs,
        masks,
        acts,
        lr=lr,
        epochs=epochs,
        batch_size=batch_size,
        expert_label=expert.upper(),
    )
    return len(samples)


def imitate_v8(
    model,
    *,
    port: int,
    games: int,
    epochs: int = DEFAULT_BC_EPOCHS,
    batch_size: int = 256,
    lr: float = DEFAULT_BC_LR,
) -> int:
    """Phase 2 helper: clone V8-vs-V8."""
    return imitate_heuristic(
        model,
        port=port,
        games=games,
        expert="v8",
        foe="v8",
        epochs=epochs,
        batch_size=batch_size,
        lr=lr,
    )
