#!/usr/bin/env python
"""Online Bot Runner for testing Heuristic Agents on the public Pokémon Showdown server."""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# Bootstrap the package path
_THIS_DIR = Path(__file__).parent.resolve()
_EVAL_DIR = _THIS_DIR.parent
_S01_DIR = _EVAL_DIR.parent
_P01_DIR = _S01_DIR.parent
_SRC_DIR = _P01_DIR.parent
_ROOT_DIR = _SRC_DIR.parent

# Always inject pokechamp fork FIRST so its poke_env overrides site-packages
_POKECHAMP = _ROOT_DIR / "pokechamp"
if _POKECHAMP.exists() and str(_POKECHAMP) not in sys.path:
    sys.path.insert(0, str(_POKECHAMP))

if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from poke_env import AccountConfiguration, ServerConfiguration
from p01_heuristics.s01_singles.agents import get_agent_class

# Configuration for official Smogon server
OFFICIAL_SERVER = ServerConfiguration(
    "sim3.psim.us", 
    "https://play.pokemonshowdown.com/action.php"
)


class ChallengeAcceptingPlayer:
    """A wrapper to run any agent in a passive 'online and accept challenges' mode."""

    def __init__(self, agent):
        self.agent = agent

    async def run(self):
        print(f"🤖 Bot '{self.agent.username}' is online and listening for challenges...")
        while True:
            # Sit and wait. poke-env handles challenges in the background 
            # if we use the player's internal listener or run it asynchronously.
            await asyncio.sleep(1)


async def main():
    # Always change to pokechamp root because our poke_env fork expects it for data loading
    if _POKECHAMP.exists():
        os.chdir(str(_POKECHAMP))

    parser = argparse.ArgumentParser(description="Run a Showdown Bot on the official Smogon server.")
    parser.add_argument(
        "--agent", 
        type=str, 
        default="v12", 
        help="Heuristic agent version to run (default: v12)"
    )
    parser.add_argument(
        "--username", 
        type=str, 
        required=True, 
        help="Registered Pokémon Showdown username"
    )
    parser.add_argument(
        "--password", 
        type=str, 
        help="Password for your registered username (can also set SHOWDOWN_PASSWORD env var)"
    )
    parser.add_argument(
        "--mode", 
        type=str, 
        choices=["ladder", "accept"], 
        default="accept",
        help="Run mode: 'ladder' to play public matches, 'accept' to wait and accept friend challenges (default: accept)"
    )
    parser.add_argument(
        "--format", 
        type=str, 
        default="gen9randombattle", 
        help="Showdown battle format (default: gen9randombattle)"
    )
    parser.add_argument(
        "--games", 
        type=int, 
        default=10, 
        help="Number of games to play in ladder mode (default: 10)"
    )
    args = parser.parse_args()

    # Get password from arguments or environment variable
    password = args.password or os.environ.get("SHOWDOWN_PASSWORD")
    if not password:
        print("⚠️  Warning: No password provided. Running unauthenticated (challenges only, cannot register or play ladder).")
    
    # Configure account and server
    account_config = AccountConfiguration(args.username, password)
    
    # Instantiate the agent class dynamically
    try:
        AgentCls = get_agent_class(args.agent)
    except ValueError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    # Ensure logs directory exists
    log_dir = Path("/home/sirp/Documents/MUDS/TFM_Pokemon/data/1_vs_1/logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    # Configure logging to save to a file as well as the console
    logger = logging.getLogger(args.username)
    logger.setLevel(logging.INFO)
    file_handler = logging.FileHandler(log_dir / "online_bot.log")
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(file_handler)

    print(f"Initializing {args.agent} agent...")
    
    # Instantiate player
    agent = AgentCls(
        server_configuration=OFFICIAL_SERVER,
        account_configuration=account_config,
        save_replays=str(log_dir / "replays"),
    )

    if args.mode == "ladder":
        if not password:
            print("❌ Error: You must provide a password to log in and play on the public ladder.")
            sys.exit(1)
        print(f"🚀 Playing {args.games} ladder games in {args.format}...")
        for i in range(args.games):
            print(f"⚔️  Starting battle {i + 1}/{args.games}...")
            try:
                await agent.ladder(args.format)
            except Exception as e:
                print(f"❌ Battle failed: {e}")
        print("✅ Finished playing ladder games.")
        
    elif args.mode == "accept":
        # Sits online and waits for challenges. poke_env will automatically
        # accept and play challenges in the background.
        print(f"🟢 Bot logged in as {args.username}.")
        print("To battle the bot, open Pokémon Showdown, search for your bot's username, and send a challenge.")
        try:
            # We run the agent's internal listener to accept any incoming challenges
            await agent.accept_challenges(opponent=None, n_challenges=9999)
        except KeyboardInterrupt:
            print("\nShutting down bot.")


if __name__ == "__main__":
    # Run the async loop
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user.")
