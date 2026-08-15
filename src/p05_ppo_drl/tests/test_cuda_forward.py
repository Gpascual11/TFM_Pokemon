"""One CUDA forward pass of MaskablePPO. No Showdown."""

from __future__ import annotations

import unittest

import numpy as np
import torch
from sb3_contrib import MaskablePPO
from sb3_contrib.common.maskable.policies import MaskableActorCriticPolicy
from stable_baselines3.common.vec_env import DummyVecEnv

from src.p05_ppo_drl.constants import ACTION_N, DEVICE, NET_ARCH
from src.p05_ppo_drl.s01_env.dummy_env import DummyMaskedEnv
from src.p05_ppo_drl.s01_env.vectorizer import OBS_SIZE


class TestCudaForward(unittest.TestCase):
    def test_maskable_ppo_cuda_forward(self):
        self.assertTrue(torch.cuda.is_available(), "CUDA required")
        env = DummyVecEnv([DummyMaskedEnv])
        model = MaskablePPO(
            MaskableActorCriticPolicy,
            env,
            verbose=0,
            n_steps=8,
            batch_size=8,
            policy_kwargs=dict(net_arch=NET_ARCH),
            device=DEVICE,
        )
        device = next(model.policy.parameters()).device
        self.assertEqual(device.type, "cuda", device)
        obs = np.zeros((1, OBS_SIZE), dtype=np.float32)
        mask = np.zeros((1, ACTION_N), dtype=np.int8)
        mask[0, 0] = 1
        action, _ = model.policy.predict(obs, deterministic=True, action_masks=mask)
        self.assertEqual(int(np.asarray(action).reshape(-1)[0]), 0)
        print(f"CUDA forward OK device={torch.cuda.get_device_name(0)} action={action}")

    def test_apply_loaded_hparams_updates_optimizer(self):
        self.assertTrue(torch.cuda.is_available(), "CUDA required")
        env = DummyVecEnv([DummyMaskedEnv])
        model = MaskablePPO(
            MaskableActorCriticPolicy,
            env,
            verbose=0,
            n_steps=8,
            batch_size=8,
            learning_rate=3e-4,
            ent_coef=0.01,
            policy_kwargs=dict(net_arch=NET_ARCH),
            device=DEVICE,
        )
        model.learning_rate = 5e-5
        self.assertGreater(model.policy.optimizer.param_groups[0]["lr"], 1e-4)
        from src.p05_ppo_drl.s02_training.loop import apply_loaded_hparams

        apply_loaded_hparams(model, lr=5e-5, ent_coef=0.02, reset_optimizer=True)
        self.assertAlmostEqual(model.policy.optimizer.param_groups[0]["lr"], 5e-5)
        self.assertAlmostEqual(float(model.lr_schedule(1.0)), 5e-5)
        self.assertAlmostEqual(model.ent_coef, 0.02)

    def test_expand_obs_layer_318_to_current(self):
        self.assertTrue(torch.cuda.is_available(), "CUDA required")
        from src.p05_ppo_drl.s01_env.vectorizer import PREV_OBS_SIZE
        from src.p05_ppo_drl.s02_training.loop import expand_obs_layer

        env = DummyVecEnv([lambda: DummyMaskedEnv(obs_size=PREV_OBS_SIZE)])
        model = MaskablePPO(
            MaskableActorCriticPolicy,
            env,
            verbose=0,
            n_steps=8,
            batch_size=8,
            policy_kwargs=dict(net_arch=NET_ARCH),
            device=DEVICE,
        )
        self.assertEqual(model.policy.mlp_extractor.policy_net[0].in_features, PREV_OBS_SIZE)
        expand_obs_layer(model, OBS_SIZE)
        self.assertEqual(model.policy.mlp_extractor.policy_net[0].in_features, OBS_SIZE)
        obs = np.zeros((1, OBS_SIZE), dtype=np.float32)
        mask = np.zeros((1, ACTION_N), dtype=np.int8)
        mask[0, 0] = 1
        action, _ = model.policy.predict(obs, deterministic=True, action_masks=mask)
        self.assertEqual(int(np.asarray(action).reshape(-1)[0]), 0)

    def test_attach_env_changes_n_envs(self):
        self.assertTrue(torch.cuda.is_available(), "CUDA required")
        from src.p05_ppo_drl.s02_training.loop import _attach_env

        env1 = DummyVecEnv([DummyMaskedEnv])
        model = MaskablePPO(
            MaskableActorCriticPolicy,
            env1,
            verbose=0,
            n_steps=8,
            batch_size=8,
            policy_kwargs=dict(net_arch=NET_ARCH),
            device=DEVICE,
        )
        self.assertEqual(model.n_envs, 1)
        env2 = DummyVecEnv([DummyMaskedEnv, DummyMaskedEnv])
        _attach_env(model, env2)
        self.assertEqual(model.n_envs, 2)
        self.assertEqual(model.env.num_envs, 2)

    def test_fit_policy_ce_uses_bc_lr_not_ppo(self):
        self.assertTrue(torch.cuda.is_available(), "CUDA required")
        from src.p05_ppo_drl.constants import SWITCH_OFFSET
        from src.p05_ppo_drl.s02_training.bc import bc_agreement, fit_policy_ce

        env = DummyVecEnv([DummyMaskedEnv])
        model = MaskablePPO(
            MaskableActorCriticPolicy,
            env,
            verbose=0,
            n_steps=8,
            batch_size=8,
            learning_rate=5e-5,
            policy_kwargs=dict(net_arch=NET_ARCH),
            device=DEVICE,
        )
        n = 512
        obs = torch.as_tensor(np.random.rand(n, OBS_SIZE).astype(np.float32), device=DEVICE)
        masks = np.ones((n, ACTION_N), dtype=np.int8)
        acts = torch.full((n,), SWITCH_OFFSET, dtype=torch.long, device=DEVICE)
        agree0, _, sw0 = bc_agreement(model, obs, masks, acts)
        fit_policy_ce(model, obs, masks, acts, lr=1e-3, epochs=20, batch_size=128)
        agree1, _, sw1 = bc_agreement(model, obs, masks, acts)
        self.assertGreater(agree1, 0.8, f"before={agree0:.2%} after={agree1:.2%}")
        self.assertGreater(sw1, 0.8, f"policy_switch before={sw0:.2%} after={sw1:.2%}")
        self.assertAlmostEqual(model.policy.optimizer.param_groups[0]["lr"], 5e-5)


if __name__ == "__main__":
    unittest.main()
