"""Shared MaskablePPO training loop. Every entrypoint starts Showdown itself."""

from __future__ import annotations

import argparse
import json
import random
import string
import sys
from pathlib import Path

import torch
from poke_env.ps_client.account_configuration import AccountConfiguration
from sb3_contrib import MaskablePPO
from sb3_contrib.common.maskable.policies import MaskableActorCriticPolicy
from stable_baselines3.common.callbacks import CallbackList, CheckpointCallback
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.utils import FloatSchedule
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv

from .._bootstrap import ensure_src_path, repo_root
from ..constants import (
    ACTION_N,
    BATTLE_FORMAT,
    CLAIM_P3_ZIP,
    DEVICE,
    NET_ARCH,
    PHASE_CHECKPOINTS,
    PHASE_EARLY_STOP,
    PLOT_DIR,
    TB_DIR,
    WR_LOG_DIR,
    ensure_model_dirs,
)
from ..s01_env.vectorizer import OBS_SIZE
from .callbacks import WinRateCallback
from .showdown import ensure_showdown, parse_ports

ensure_src_path()


class EnvMaker:
    """Picklable env factory for SubprocVecEnv(spawn)."""

    def __init__(self, rank: int, port: int, opponent: str, root: str):
        self.rank = rank
        self.port = port
        self.opponent = opponent
        self.root = root

    def __call__(self):
        root = Path(self.root)
        src = str(root / "src")
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        if src not in sys.path:
            sys.path.insert(0, src)

        import logging

        logging.getLogger("poke_env").setLevel(logging.ERROR)
        logging.getLogger("websockets").setLevel(logging.ERROR)

        from p05_ppo_drl.s01_env.pokemon_env import PokemonMaskedEnv, PokemonMaskedEnvWrapper
        from p05_ppo_drl.s02_training.opponents import make_opponent
        from p05_ppo_drl.s02_training.showdown import quiet_showdown_client_logs
        from p05_ppo_drl.s02_training.showdown import server_configuration as cfg_for

        quiet_showdown_client_logs()

        tag = "".join(random.choices(string.ascii_lowercase + string.digits, k=5))
        server_config = cfg_for(self.port)
        opponent = make_opponent(self.opponent, port=self.port, rank=self.rank, server_config=server_config, suffix=tag)
        base_env = PokemonMaskedEnv(
            battle_format=BATTLE_FORMAT,
            server_configuration=server_config,
            account_configuration1=AccountConfiguration(f"PPO{self.rank}{tag}", None),
            account_configuration2=AccountConfiguration(f"Body{self.rank}{tag}", None),
        )
        env = PokemonMaskedEnvWrapper(base_env, opponent)
        return Monitor(env, info_keywords=("battle_won", "battle_finished", "turn"))


def require_cuda() -> None:
    if not torch.cuda.is_available():
        raise SystemExit("CUDA is required (device='cuda'). torch.cuda.is_available() is False.")
    name = torch.cuda.get_device_name(0)
    print(f"CUDA device: {name}  torch={torch.__version__}", flush=True)


def add_common_args(
    parser: argparse.ArgumentParser,
    *,
    default_timesteps: int,
    phase: str,
    default_ent_coef: float = 0.01,
    default_bc_games: int = 0,
    default_envs_per_port: int = 1,
    default_bc_expert: str = "v8",
    default_bc_foe: str | None = None,
) -> None:
    parser.add_argument("--timesteps", type=int, default=default_timesteps)
    parser.add_argument(
        "--ports",
        type=int,
        nargs="*",
        default=None,
        help="Count 1–10 (from 8000) or an explicit consecutive port list. Default: 4 ports 8000–8003.",
    )
    parser.add_argument(
        "--envs-per-port",
        type=int,
        default=default_envs_per_port,
        dest="envs_per_port",
        help="Gym envs (battles) per Showdown server. Default 1. Use 2 with --ports 8 if GPU sits idle.",
    )
    parser.add_argument("--resume", action="store_true", help="Resume this phase's zip if it exists.")
    parser.add_argument("--n-steps", type=int, default=2048, dest="n_steps")
    parser.add_argument("--lr", type=float, default=None, help="Override learning rate.")
    parser.add_argument("--wr-every", type=int, default=10_000, help="Log win rate every N steps.")
    parser.add_argument("--save-every", type=int, default=50_000, help="Checkpoint every N steps (0=off).")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Tiny run: 512 steps, 2 ports, small n_steps. Starts Showdown; not a result.",
    )
    parser.add_argument("--ent-coef", type=float, default=default_ent_coef, dest="ent_coef")
    parser.add_argument("--n-epochs", type=int, default=4, dest="n_epochs")
    parser.add_argument("--gamma", type=float, default=0.99)
    parser.add_argument(
        "--early-stop-wr",
        type=float,
        default=None,
        dest="early_stop_wr",
        help="Stop if rolling train WR ≥ this (default: phase target, none for p3). Not a 1k eval.",
    )
    parser.add_argument("--early-stop-patience", type=int, default=None, dest="early_stop_patience")
    parser.add_argument("--early-stop-min-games", type=int, default=None, dest="early_stop_min_games")
    parser.add_argument("--no-early-stop", action="store_true", dest="no_early_stop")
    parser.add_argument(
        "--bc-games",
        type=int,
        default=default_bc_games,
        dest="bc_games",
        help="Imitation games before PPO (0=off). Teacher is --bc-expert, not the eval opponent unless they match.",
    )
    parser.add_argument(
        "--bc-expert",
        type=str,
        default=default_bc_expert,
        dest="bc_expert",
        help="Heuristic to clone (v8, v14, …). Phase 4 must be v14, never v12.",
    )
    parser.add_argument(
        "--bc-foe",
        type=str,
        default=default_bc_foe or default_bc_expert,
        dest="bc_foe",
        help="Foe during BC collection. Phase 4: v12 so states match eval.",
    )
    parser.add_argument(
        "--bc-lr",
        type=float,
        default=1e-3,
        dest="bc_lr",
        help="Adam lr for BC only. Must not be the PPO 5e-5 or cloning does nothing.",
    )
    parser.add_argument("--bc-epochs", type=int, default=15, dest="bc_epochs")


def _vec_env(ports: list[int], opponent: str, envs_per_port: int = 1):
    root = str(repo_root())
    n = max(int(envs_per_port), 1)
    makers = []
    rank = 0
    for port in ports:
        for _ in range(n):
            makers.append(EnvMaker(rank, port, opponent, root))
            rank += 1
    if len(makers) == 1:
        return DummyVecEnv(makers)
    try:
        return SubprocVecEnv(makers, start_method="spawn")
    except (ConnectionResetError, EOFError, BrokenPipeError) as exc:
        raise RuntimeError(
            "A SubprocVecEnv worker died while creating the env. "
            "The worker traceback is printed above (usually an import error in the opponent)."
        ) from exc


def _n_steps_and_batch(timesteps: int, n_envs: int, n_steps: int) -> tuple[int, int]:
    n_steps = max(16, min(n_steps, max(timesteps // max(n_envs, 1), 16)))
    rollout = n_steps * n_envs
    # Larger minibatches when many envs: a bit more GPU work on the update, still divides the rollout.
    cap = 512 if n_envs >= 8 else 256
    batch = min(cap, rollout)
    while batch > 8 and rollout % batch != 0:
        batch -= 1
    return n_steps, batch


def apply_loaded_hparams(model, *, lr: float, ent_coef: float, reset_optimizer: bool) -> None:
    """``model.learning_rate = x`` does not update ``lr_schedule`` or Adam. Fix that."""
    model.learning_rate = lr
    model.lr_schedule = FloatSchedule(lr)
    model.ent_coef = ent_coef
    if reset_optimizer:
        model.policy.optimizer = torch.optim.Adam(model.policy.parameters(), lr=lr, eps=1e-5)
        print(f"Applied curriculum hparams lr={lr} ent_coef={ent_coef} (Adam reset)", flush=True)
    else:
        for group in model.policy.optimizer.param_groups:
            group["lr"] = lr
        print(f"Applied resume hparams lr={lr} ent_coef={ent_coef}", flush=True)


def expand_obs_layer(model, new_obs: int) -> None:
    """Copy old first-layer weights and zero-init appended observation columns."""
    import gymnasium as gym
    import numpy as np

    old_space = model.observation_space
    old_n = int(old_space.shape[0])
    if old_n == new_obs:
        return
    if old_n > new_obs:
        raise SystemExit(f"Cannot shrink policy obs {old_n} → {new_obs}")
    for net_name in ("policy_net", "value_net"):
        net = getattr(model.policy.mlp_extractor, net_name)
        old = net[0]
        new_lin = torch.nn.Linear(
            new_obs, old.out_features, device=old.weight.device, dtype=old.weight.dtype
        )
        with torch.no_grad():
            new_lin.weight.zero_()
            new_lin.bias.copy_(old.bias)
            new_lin.weight[:, :old_n].copy_(old.weight)
        net[0] = new_lin
    box = gym.spaces.Box(0.0, 1.0, shape=(new_obs,), dtype=np.float32)
    model.observation_space = box
    model.policy.observation_space = box
    print(f"Expanded first layer {old_n} → {new_obs} (new cols zero-init)", flush=True)


def _attach_env(model, vec_env) -> None:
    """``set_env`` requires matching ``n_envs``. p15 was 4 ports; p2 defaults to 8."""
    model.n_envs = int(vec_env.num_envs)
    buf_cls = model.rollout_buffer_class
    kwargs = getattr(model, "rollout_buffer_kwargs", None) or {}
    if buf_cls is not None:
        model.rollout_buffer = buf_cls(
            model.n_steps,
            model.observation_space,
            model.action_space,
            model.device,
            gamma=model.gamma,
            gae_lambda=model.gae_lambda,
            n_envs=model.n_envs,
            **kwargs,
        )
    model.set_env(vec_env)


def _load_maskable(path: Path, vec_env, *, device: str, tb: str):
    model = MaskablePPO.load(str(path.with_suffix("")), device=device, tensorboard_log=tb)
    old_n = int(model.observation_space.shape[0])
    if old_n != OBS_SIZE:
        expand_obs_layer(model, OBS_SIZE)
    _attach_env(model, vec_env)
    return model


def train_phase(
    *,
    phase: str,
    opponent: str,
    default_timesteps: int,
    default_lr: float,
    load_from: Path | None,
    argv: list[str] | None = None,
    default_ent_coef: float = 0.01,
    default_port_count: int | None = None,
    default_envs_per_port: int = 1,
    bc_games: int = 0,
    bc_expert: str = "v8",
    bc_foe: str | None = None,
) -> None:
    parser = argparse.ArgumentParser(description=f"Train MaskablePPO phase {phase} vs {opponent}.")
    add_common_args(
        parser,
        default_timesteps=default_timesteps,
        phase=phase,
        default_ent_coef=default_ent_coef,
        default_bc_games=bc_games,
        default_envs_per_port=default_envs_per_port,
        default_bc_expert=bc_expert,
        default_bc_foe=bc_foe,
    )
    args = parser.parse_args(argv)

    if args.smoke:
        args.timesteps = min(args.timesteps, 512)
        args.ports = [2]
        args.n_steps = 64
        args.wr_every = 64
        args.save_every = 0
        args.no_early_stop = True
        args.bc_games = 0
        print("SMOKE: 512 steps, 2 Showdown ports. Not a result.", flush=True)
    elif args.ports is None and default_port_count is not None:
        args.ports = [default_port_count]

    ports = parse_ports(args.ports)
    save_path = PHASE_CHECKPOINTS[phase]
    if save_path.resolve() == CLAIM_P3_ZIP.resolve():
        raise SystemExit(f"Refusing to overwrite the Phase 3 claim zip: {CLAIM_P3_ZIP}")
    if load_from is not None and load_from.resolve() == CLAIM_P3_ZIP.resolve():
        print(
            f"Loading claim zip {CLAIM_P3_ZIP.name} (328-d, 34.1% n=10k). "
            f"Will expand to obs_size={OBS_SIZE} and save to {save_path} — not the claim file.",
            flush=True,
        )
    ensure_model_dirs()
    require_cuda()

    envs_per_port = max(int(args.envs_per_port), 1)
    n_envs = len(ports) * envs_per_port
    print(
        f"Phase {phase} vs {opponent} | ports={ports} | envs={n_envs} "
        f"({envs_per_port}/port) | steps={args.timesteps:,} | "
        f"obs_size={OBS_SIZE} action_n={ACTION_N} device={DEVICE}"
        + (
            f" | BC from {str(args.bc_expert).upper()} vs {args.bc_foe} ({int(args.bc_games)} games)"
            if int(args.bc_games) > 0
            else ""
        ),
        flush=True,
    )
    print("Changing obs_size or action_n invalidates every zip under data/models/ppo/<phase>/.", flush=True)
    print(
        "GPU util stays low on purpose: Showdown + websockets are the bottleneck, "
        "not the 346→256→256 net. 5–15% on an RTX 2080 is expected. "
        "More battles (next run): --ports 8 --envs-per-port 2",
        flush=True,
    )

    session = ensure_showdown(ports, restart=True)
    vec_env = None
    try:
        vec_env = _vec_env(ports, opponent, envs_per_port)
        n_steps, batch = _n_steps_and_batch(args.timesteps, n_envs, args.n_steps)
        lr = args.lr if args.lr is not None else default_lr
        tb = str(TB_DIR)
        resume = args.resume
        model = None
        if load_from is not None and not load_from.exists():
            for fallback in (PHASE_CHECKPOINTS.get("p15"), PHASE_CHECKPOINTS.get("p1")):
                if fallback is not None and fallback.exists() and fallback != save_path:
                    print(f"{load_from} missing — falling back to {fallback}", flush=True)
                    load_from = fallback
                    break
        if resume and save_path.exists():
            print(f"Resuming {save_path}", flush=True)
            model = _load_maskable(save_path, vec_env, device=DEVICE, tb=tb)
            apply_loaded_hparams(model, lr=lr, ent_coef=args.ent_coef, reset_optimizer=False)
        elif load_from is not None and load_from.exists() and not resume:
            print(f"Loading curriculum weights from {load_from}", flush=True)
            model = _load_maskable(load_from, vec_env, device=DEVICE, tb=tb)
            apply_loaded_hparams(model, lr=lr, ent_coef=args.ent_coef, reset_optimizer=True)
        elif resume and load_from is not None and load_from.exists():
            print(f"Phase zip missing; loading {load_from}", flush=True)
            model = _load_maskable(load_from, vec_env, device=DEVICE, tb=tb)
            apply_loaded_hparams(model, lr=lr, ent_coef=args.ent_coef, reset_optimizer=True)

        if model is None:
            print(f"Fresh MaskablePPO lr={lr} n_steps={n_steps} batch={batch}", flush=True)
            model = MaskablePPO(
                MaskableActorCriticPolicy,
                vec_env,
                verbose=1,
                learning_rate=lr,
                gamma=args.gamma,
                ent_coef=args.ent_coef,
                n_steps=n_steps,
                batch_size=batch,
                n_epochs=args.n_epochs,
                policy_kwargs=dict(net_arch=NET_ARCH),
                tensorboard_log=tb,
                device=DEVICE,
            )
        else:
            # Loaded models keep their n_steps; shrink only for smoke.
            if args.smoke:
                model.n_steps = n_steps
                model.batch_size = batch
            prog = getattr(model, "_current_progress_remaining", 1.0)
            print(
                f"Active lr={float(model.lr_schedule(prog))} "
                f"opt_lr={model.policy.optimizer.param_groups[0]['lr']} ent_coef={model.ent_coef}",
                flush=True,
            )

        param_dev = next(model.policy.parameters()).device
        if param_dev.type != "cuda":
            raise SystemExit(f"Policy is on {param_dev}, expected cuda.")

        if int(args.bc_games) > 0:
            from .bc import imitate_heuristic

            expert = str(args.bc_expert).lower()
            foe = str(args.bc_foe).lower()
            if phase == "p4" and expert == "v12":
                raise SystemExit("Phase 4 must say BC from V14 (or V11), not V12.")
            imitate_heuristic(
                model,
                port=ports[0],
                games=int(args.bc_games),
                expert=expert,
                foe=foe,
                lr=float(args.bc_lr),
                epochs=int(args.bc_epochs),
            )
            apply_loaded_hparams(model, lr=lr, ent_coef=args.ent_coef, reset_optimizer=True)

        stop_cfg = PHASE_EARLY_STOP.get(phase, {})
        target_wr = args.early_stop_wr if args.early_stop_wr is not None else stop_cfg.get("target_wr")
        patience = args.early_stop_patience if args.early_stop_patience is not None else int(stop_cfg.get("patience") or 20)
        min_games = (
            args.early_stop_min_games
            if args.early_stop_min_games is not None
            else int(stop_cfg.get("min_games") or 300)
        )
        run_tag = f"{phase}_{opponent}" + ("_smoke" if args.smoke else "")
        plot_dir = PLOT_DIR / run_tag
        csv_path = WR_LOG_DIR / f"{run_tag}.csv"
        if not resume and csv_path.exists():
            csv_path.unlink()
        plot_dir.mkdir(parents=True, exist_ok=True)
        hparams = {
            "phase": phase,
            "opponent": opponent,
            "timesteps": args.timesteps,
            "ports": ports,
            "envs_per_port": envs_per_port,
            "n_envs": n_envs,
            "lr": lr,
            "n_steps": n_steps,
            "batch_size": batch,
            "n_epochs": args.n_epochs,
            "gamma": args.gamma,
            "ent_coef": args.ent_coef,
            "net_arch": NET_ARCH,
            "obs_size": OBS_SIZE,
            "action_n": ACTION_N,
            "device": DEVICE,
            "early_stop_wr": target_wr,
            "early_stop_patience": patience,
            "early_stop_min_games": min_games,
            "early_stop_enabled": not args.no_early_stop,
            "bc_games": int(args.bc_games),
            "bc_expert": str(args.bc_expert),
            "bc_foe": str(args.bc_foe),
            "note": "These are standard PPO starting values, not a tuned optimum. Graduation is 1k/10k eval, not train WR.",
        }
        (plot_dir / "hparams.json").write_text(json.dumps(hparams, indent=2), encoding="utf-8")
        print(
            f"hparams lr={lr} n_steps={n_steps} batch={batch} n_epochs={args.n_epochs} "
            f"early_stop_wr={target_wr} min_games={min_games} patience={patience} "
            f"plots={plot_dir}",
            flush=True,
        )

        wr_cb = WinRateCallback(
            every_steps=args.wr_every,
            opponent_name=opponent,
            csv_path=csv_path,
            plot_dir=plot_dir,
            title=f"Phase {phase} vs {opponent} (train WR, not a 1k/10k result)",
            target_wr=target_wr,
            min_games=min_games,
            patience=patience,
            enable_early_stop=not args.no_early_stop,
        )
        callbacks = [wr_cb]
        if args.save_every > 0:
            ckpt_dir = save_path.parent / "ckpts"
            ckpt_dir.mkdir(parents=True, exist_ok=True)
            callbacks.append(
                CheckpointCallback(
                    save_freq=max(args.save_every // max(n_envs, 1), 1),
                    save_path=str(ckpt_dir),
                    name_prefix=save_path.stem,
                    save_replay_buffer=False,
                    save_vecnormalize=False,
                )
            )

        try:
            model.learn(
                total_timesteps=args.timesteps,
                callback=CallbackList(callbacks),
                reset_num_timesteps=not (args.resume and save_path.exists()),
                tb_log_name=f"{phase}_{opponent}",
                use_masking=True,
            )
        except KeyboardInterrupt:
            print("Interrupted — saving current weights.", flush=True)
        except (TimeoutError, EOFError) as exc:
            raise SystemExit(
                "Showdown challenge timed out (Agent is not challenging / worker EOF). "
                "Usually a leftover server after eval. Train now kills and restarts "
                "its ports; rerun the same command."
            ) from exc
        status = {
            "games": wr_cb.games,
            "wins": wr_cb.wins,
            "wr_cumulative": (wr_cb.wins / wr_cb.games) if wr_cb.games else None,
            "stop_reason": wr_cb.stop_reason,
            "timesteps_done": int(model.num_timesteps),
        }
        (plot_dir / "status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
        if wr_cb.stop_reason:
            print(f"Stopped because: {wr_cb.stop_reason}", flush=True)
        print(f"Plots: {plot_dir / 'winrate.png'}", flush=True)
        if args.smoke:
            print("SMOKE: not writing a curriculum checkpoint.", flush=True)
        else:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            model.save(str(save_path.with_suffix("")))
            print(f"Saved {save_path}", flush=True)
    finally:
        if vec_env is not None:
            try:
                vec_env.close()
            except Exception:
                pass
        session.stop()
