"""Eval MaskablePPO vs Random (sanity) and HeuristicV12 (the claim opponent).

Sample sizes: 100 = smoke (±10 pp), 1k = diagnostic (±3.1 pp), 10k = publishable (±0.98 pp).
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import random
import string
import time
from pathlib import Path

import numpy as np
from poke_env.ps_client.account_configuration import AccountConfiguration
from sb3_contrib import MaskablePPO
from sb3_contrib.common.maskable.policies import MaskableActorCriticPolicy
from stable_baselines3.common.vec_env import DummyVecEnv

from .._bootstrap import ensure_src_path
from ..constants import BATTLE_FORMAT, DEVICE, EVAL_DIR, NET_ARCH, ensure_model_dirs
from ..s01_env.dummy_env import DummyMaskedEnv
from ..s01_env.vectorizer import StateVectorizer
from ..s02_training.loop import require_cuda
from ..s02_training.opponents import make_eval_player
from ..s02_training.showdown import close_ps_clients, ensure_showdown, parse_ports, quiet_showdown_client_logs, server_configuration
from .ppo_player import HybridPPOv12Player, PPOPlayer

ensure_src_path()


def _tag(n: int = 4) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def load_or_fresh_model(model_path: Path | None, untrained: bool) -> MaskablePPO:
    dummy = DummyVecEnv([DummyMaskedEnv])
    if untrained or model_path is None:
        print("Untrained MaskablePPO (smoke, not a result).", flush=True)
        model = MaskablePPO(
            MaskableActorCriticPolicy,
            dummy,
            verbose=0,
            n_steps=32,
            batch_size=32,
            policy_kwargs=dict(net_arch=NET_ARCH),
            device=DEVICE,
        )
        return model
    if not model_path.exists():
        alt = model_path.with_suffix(".zip")
        if alt.exists():
            model_path = alt
        else:
            raise FileNotFoundError(f"Checkpoint not found: {model_path}")
    print(f"Loading {model_path}", flush=True)
    from ..s01_env.vectorizer import OBS_SIZE
    from ..s02_training.loop import expand_obs_layer

    model = MaskablePPO.load(str(model_path.with_suffix("")), device=DEVICE)
    old_n = int(model.observation_space.shape[0])
    if old_n != OBS_SIZE:
        expand_obs_layer(model, OBS_SIZE)
    return model


async def _play(
    model: MaskablePPO,
    opponent: str,
    port: int,
    games: int,
    *,
    hybrid: bool,
    alpha: float,
    as_challenger: bool,
    concurrent: int,
) -> dict:
    cfg = server_configuration(port)
    tag = _tag()
    vectorizer = StateVectorizer()
    player_cls = HybridPPOv12Player if hybrid else PPOPlayer
    extra = {"alpha": alpha} if hybrid else {}
    ppo = player_cls(
        model,
        vectorizer=vectorizer,
        **extra,
        server_configuration=cfg,
        account_configuration=AccountConfiguration(f"Eppo{tag}", None),
        max_concurrent_battles=concurrent,
        battle_format=BATTLE_FORMAT,
    )
    opp = make_eval_player(
        opponent,
        server_config=cfg,
        name=f"Eopp{tag}",
        max_concurrent=concurrent,
    )
    try:
        if as_challenger:
            await ppo.battle_against(opp, n_battles=games)
            wins = ppo.n_won_battles
            turns = [b.turn for b in ppo.battles.values()]
        else:
            await opp.battle_against(ppo, n_battles=games)
            wins = games - opp.n_won_battles
            turns = [b.turn for b in opp.battles.values()]
        return {
            "games": games,
            "wins": int(wins),
            "wr": wins / games if games else 0.0,
            "avg_turns": float(np.mean(turns)) if turns else 0.0,
            "seat": "p1" if as_challenger else "p2",
            "port": port,
        }
    finally:
        await close_ps_clients(ppo, opp)


def _ci95(p: float, n: int) -> float:
    if n <= 0:
        return 0.0
    return 1.96 * float(np.sqrt(p * (1.0 - p) / n))


def run_eval(args: argparse.Namespace) -> dict:
    require_cuda()
    quiet_showdown_client_logs()
    ensure_model_dirs()
    ports = parse_ports(args.ports)
    session = ensure_showdown(ports)
    model_path = Path(args.model) if args.model else None
    try:
        model = load_or_fresh_model(model_path, args.untrained)
        if next(model.policy.parameters()).device.type != "cuda":
            raise SystemExit("Eval model is not on CUDA.")
        games = args.games
        if args.both_seats:
            per_seat = games // 2
            leftover = games - 2 * per_seat
            jobs = [(True, per_seat + leftover), (False, per_seat)]
        else:
            jobs = [(True, games)]
        # Round-robin ports
        chunks: list[tuple[int, bool, int]] = []
        port_i = 0
        for as_p1, n in jobs:
            if n <= 0:
                continue
            remaining = n
            n_ports = len(ports)
            base = remaining // n_ports
            rem = remaining % n_ports
            for j, port in enumerate(ports):
                take = base + (1 if j < rem else 0)
                if take:
                    chunks.append((port, as_p1, take))
            port_i += 1
        print(
            f"Eval {'hybrid PPO+v12' if args.hybrid else 'pure PPO'} vs {args.opponent} "
            f"n={games} ports={ports} both_seats={args.both_seats}",
            flush=True,
        )
        if games <= 100:
            print("n=100 is smoke (±10 pp), never a result.", flush=True)
        elif games <= 1000:
            print("n=1k is diagnostic (±3.1 pp). ≳53% vs v12 to even suspect a beat.", flush=True)
        else:
            print("n=10k is the only number that may be called 'PPO vs v12' (±0.98 pp).", flush=True)

        t0 = time.time()
        results = []
        for port, as_p1, n in chunks:
            if n <= 0:
                continue
            print(f"  port {port} seat={'p1' if as_p1 else 'p2'} games={n}", flush=True)
            results.append(
                asyncio.run(
                    _play(
                        model,
                        args.opponent,
                        port,
                        n,
                        hybrid=args.hybrid,
                        alpha=args.alpha,
                        as_challenger=as_p1,
                        concurrent=args.concurrent,
                    )
                )
            )
        elapsed = time.time() - t0
        wins = sum(r["wins"] for r in results)
        n_tot = sum(r["games"] for r in results)
        wr = wins / n_tot if n_tot else 0.0
        half = _ci95(wr, n_tot)
        summary = {
            "agent": "hybrid_ppo_v12" if args.hybrid else "pure_ppo",
            "alpha": args.alpha if args.hybrid else 1.0,
            "opponent": args.opponent,
            "games": n_tot,
            "wins": wins,
            "win_rate": wr,
            "ci95_half_pp": half * 100,
            "avg_turns": float(np.mean([r["avg_turns"] for r in results if r["games"]])) if results else 0.0,
            "seconds": elapsed,
            "untrained": bool(args.untrained),
            "model": str(model_path) if model_path else None,
            "chunks": results,
            "note": (
                "smoke not a result"
                if n_tot <= 100
                else ("diagnostic" if n_tot <= 1000 else "publishable vs v12 only at n=10k")
            ),
        }
        print(
            f"RESULT {summary['agent']} vs {args.opponent}: {wr:.1%} "
            f"({wins}/{n_tot})  ±{half*100:.2f} pp (95% CI half-width)  {elapsed:.0f}s",
            flush=True,
        )
        EVAL_DIR.mkdir(parents=True, exist_ok=True)
        stem = f"{summary['agent']}_vs_{args.opponent}_n{n_tot}"
        json_path = EVAL_DIR / f"{stem}.json"
        csv_path = EVAL_DIR / f"{stem}.csv"
        json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        with csv_path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["agent", "opponent", "games", "wins", "win_rate", "ci95_half_pp", "note"])
            w.writeheader()
            w.writerow({k: summary[k] for k in w.fieldnames})
        print(f"Wrote {json_path}", flush=True)
        return summary
    finally:
        session.stop()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Eval PPO vs random (sanity) or v12 (claim).")
    p.add_argument("--model", type=str, default=None, help="Path to zip (suffix optional).")
    p.add_argument("--untrained", action="store_true", help="Fresh weights. Smoke, not a result.")
    p.add_argument("--opponent", type=str, default="v12", help="random | maxbp | v8 | v12 | ...")
    p.add_argument("--games", type=int, default=1000)
    p.add_argument("--ports", type=int, nargs="*", default=None)
    p.add_argument("--both-seats", action="store_true", dest="both_seats")
    p.add_argument("--hybrid", action="store_true", help="Ablation: blend PPO with HeuristicV12.")
    p.add_argument("--alpha", type=float, default=0.5, help="PPO weight for --hybrid (rest is v12).")
    p.add_argument("--concurrent", type=int, default=4, help="max_concurrent_battles per player.")
    return p


def main(argv=None) -> None:
    args = build_parser().parse_args(argv)
    if not args.untrained and not args.model:
        raise SystemExit("Pass --model path.zip or --untrained.")
    run_eval(args)


if __name__ == "__main__":
    main()
