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
# Team for gen9ou
TEAM = """
Dragapult @ Choice Specs  
Ability: Infiltrator  
Tera Type: Ghost  
EVs: 252 SpA / 4 SpD / 252 Spe  
Timid Nature  
- Draco Meteor  
- Shadow Ball  
- Flamethrower  
- U-turn  

Kingambit @ Leftovers  
Ability: Supreme Overlord  
Tera Type: Flying  
EVs: 252 Atk / 4 SpD / 252 Spe  
Adamant Nature  
- Kowtow Cleave  
- Swords Dance  
- Sucker Punch  
- Iron Head  

Great Tusk @ Leftovers  
Ability: Protosynthesis  
Tera Type: Steel  
EVs: 252 Atk / 4 SpD / 252 Spe  
Jolly Nature  
- Headlong Rush  
- Close Combat  
- Ice Spinner  
- Rapid Spin  

Iron Valiant @ Booster Energy  
Ability: Quark Drive  
Tera Type: Fairy  
EVs: 252 SpA / 4 SpD / 252 Spe  
Timid Nature  
- Moonblast  
- Psyshock  
- Aura Sphere  
- Calm Mind  

Gholdengo @ Air Balloon  
Ability: Good as Gold  
Tera Type: Steel  
EVs: 252 SpA / 4 SpD / 252 Spe  
Timid Nature  
- Shadow Ball  
- Make It Rain  
- Nasty Plot  
- Recover  

Cinderace @ Heavy-Duty Boots  
Ability: Libero  
Tera Type: Fire  
EVs: 252 Atk / 4 SpD / 252 Spe  
Jolly Nature  
- Pyro Ball  
- Gunk Shot  
- High Jump Kick  
- Court Change
"""

from p01_heuristics.s01_singles.core.factory import AgentFactory

async def debug_battle():
    server_config = ServerConfiguration("localhost:8000", None)
    BATTLE_FORMAT = "gen9ou"
    tag = str(random.randint(0, 9999))
    
    player = AgentFactory.create(
        "ml_advanced",
        account_configuration=AccountConfiguration(f"Player{tag}", None),
        server_configuration=server_config,
        battle_format=BATTLE_FORMAT,
        max_concurrent_battles=1,
        team=TEAM
    )
    
    opponent = AgentFactory.create(
        "v3",
        account_configuration=AccountConfiguration(f"Opponent{tag}", None),
        server_configuration=server_config,
        battle_format=BATTLE_FORMAT,
        max_concurrent_battles=1,
        team=TEAM
    )
    
    print(f"Starting battle in {BATTLE_FORMAT} as Player{tag} vs Opponent{tag}...")
    try:
        task = asyncio.create_task(player.battle_against(opponent, n_battles=1))
        
        while not task.done():
            await asyncio.sleep(5)
            if player.battles:
                battle = list(player.battles.values())[0]
                print(f"Turn {battle.turn}... (Player HP: {battle.active_pokemon.current_hp_fraction if battle.active_pokemon else 'N/A'})")
            else:
                print("Waiting for battle to start...")
        
        await task
        print("Battle task finished.")
    except Exception as e:
        print(f"Battle failed: {e}")

if __name__ == "__main__":
    print("Main entry point reached. Starting asyncio...")
    try:
        asyncio.run(debug_battle())
    except Exception as e:
        print(f"EXCEPTION AT ROOT: {e}")
    print("Script finished.")
