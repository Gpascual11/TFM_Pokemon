import asyncio
import os
import sys
import random

# Define absolute paths
PROJECT_ROOT = "/home/gerardpf/TFM"
SRC_PATH = os.path.join(PROJECT_ROOT, "src")
POKECHAMP_PATH = os.path.join(PROJECT_ROOT, "pokechamp")

# Insert paths to sys.path
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if POKECHAMP_PATH not in sys.path:
    sys.path.insert(0, POKECHAMP_PATH)

# Change working directory to pokechamp for its internal data loading
if os.path.exists(POKECHAMP_PATH):
    os.chdir(POKECHAMP_PATH)

from poke_env import AccountConfiguration, ServerConfiguration
from p01_heuristics.s01_singles.core.factory import AgentFactory

async def debug_battle():
    server_config = ServerConfiguration("localhost:8000", None)
    BATTLE_FORMAT = "gen9randombattle"
    tag = str(random.randint(0, 9999))
    
    player = AgentFactory.create(
        "ml_advanced",
        account_configuration=AccountConfiguration(f"Player{tag}", None),
        server_configuration=server_config,
        battle_format=BATTLE_FORMAT,
        max_concurrent_battles=1
    )
    
    opponent = AgentFactory.create(
        "random",
        account_configuration=AccountConfiguration(f"Opponent{tag}", None),
        server_configuration=server_config,
        battle_format=BATTLE_FORMAT,
        max_concurrent_battles=1
    )
    
    print(f"Starting battle in {BATTLE_FORMAT} as Player{tag} vs Opponent{tag}...")
    try:
        # Use battle_against but with more info
        task = asyncio.create_task(player.battle_against(opponent, n_battles=1))
        
        while not task.done():
            await asyncio.sleep(5)
            if player.battles:
                battle = list(player.battles.values())[0]
                print(f"Turn {battle.turn}...")
            else:
                print("Waiting for battle to start...")
        
        await task
        print("Battle task finished.")
        
        if player.battles:
            battle = list(player.battles.values())[0]
            print(f"Winner: {'Player' if battle.won else 'Opponent'}")
    except Exception as e:
        print(f"Battle failed: {e}")

if __name__ == "__main__":
    print("Main entry point reached. Starting asyncio...")
    try:
        asyncio.run(debug_battle())
    except Exception as e:
        print(f"EXCEPTION AT ROOT: {e}")
    print("Script finished.")
