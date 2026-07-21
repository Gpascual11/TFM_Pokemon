import os
import sys

# Add src to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from unittest.mock import MagicMock

from p03_minmax.agents.internal.v15_minimax import HeuristicV15Minimax

try:
    from poke_env.environment.move import Move
    from poke_env.environment.move_category import MoveCategory
except ImportError:
    from poke_env.battle import Move, MoveCategory

def test_minimax_trace():
    print("=== Minimax 1-Ply Diagnostic Trace ===")
    
    # Initialize the agent
    agent = HeuristicV15Minimax(start_listening=False)
    
    # Mock active Pokemon
    me = MagicMock()
    me.species = "Iron Valiant"
    me.current_hp = 290
    me.max_hp = 290
    me.current_hp_fraction = 1.0
    me.status = None
    me.boosts = {}
    me.base_stats = {"spe": 364, "atk": 130, "def": 90, "spa": 120, "spd": 90}
    
    opp = MagicMock()
    opp.species = "Chien-Pao"
    opp.current_hp = 281
    opp.max_hp = 281
    opp.current_hp_fraction = 1.0
    opp.status = None
    opp.boosts = {}
    opp.base_stats = {"spe": 405, "atk": 130, "def": 80, "spa": 90, "spd": 80}
    
    # Mock moves using Move spec and MoveCategory
    my_move = MagicMock(spec=Move)
    my_move.id = "closecombat"
    my_move.base_power = 120
    my_move.category = MoveCategory.PHYSICAL
    my_move.type = MagicMock()
    my_move.type.name = "FIGHTING"
    
    opp_move = MagicMock(spec=Move)
    opp_move.id = "iciclecrash"
    opp_move.base_power = 85
    opp_move.category = MoveCategory.PHYSICAL
    opp_move.type = MagicMock()
    opp_move.type.name = "ICE"
    opp_move.entry = {"priority": 0}
    
    # Mock Battle
    battle = MagicMock()
    battle.battle_tag = "test-battle"
    battle.active_pokemon = me
    battle.opponent_active_pokemon = opp
    battle._format = "gen9randombattle"
    battle.side_conditions = {}
    battle.opponent_side_conditions = {}
    battle.opponent_team = {}
    
    # Mock v14 damage calculations (Close Combat KOs Chien-Pao, Icicle Crash does 180 dmg)
    agent._calculate_exact_damage_range = MagicMock(side_effect=lambda move, attacker, defender, b: 
        (281.0, 281.0) if move.id == "closecombat" else (180.0, 180.0)
    )
    
    # Mock speed calculations (Chien-Pao is faster: 405 vs 364)
    agent._get_boosted_speed = MagicMock(side_effect=lambda p, s, f: 
        405 if p.species == "Chien-Pao" else 364
    )
    
    # Mock type immunity checks
    agent._is_ability_immune = MagicMock(return_value=False)
    agent._get_move_priority = MagicMock(return_value=0)
    
    print("\nScenario 1: Iron Valiant (us, slower) vs Chien-Pao (opponent, faster)")
    print("  We have: Close Combat (FIGHTING, BP 120) - Guarantees KO if we hit")
    print("  They have: Icicle Crash (ICE, BP 85) - Deals 180 damage (does not KO)")
    
    # Run evaluation
    score = agent._evaluate_state_score(battle, my_move, opp_move, me, opp, 9, {})
    
    print("\nMinimax Sequential Resolution simulation:")
    print("  1. Opponent is faster, hits first with Icicle Crash (180 damage).")
    print("  2. We survive with 110/290 HP (fraction: 0.379).")
    print("  3. We hit back with Close Combat, KOing Chien-Pao (0 HP, fraction: 0.0).")
    print("\nScore Calculation:")
    print("  Utility = HP_me_after - 1.5 * HP_opp_after")
    print("          = 0.379 - 1.5 * 0.0")
    print(f"          = {score:.3f}")
    
    # Scenario 2
    agent._calculate_exact_damage_range = MagicMock(side_effect=lambda move, attacker, defender, b: 
        (281.0, 281.0) if move.id == "closecombat" else (290.0, 290.0) # Icicle Crash deals 290 (exact KO)
    )
    
    print("\nScenario 2: Opponent's move now KOs us (deals 290 damage)")
    score2 = agent._evaluate_state_score(battle, my_move, opp_move, me, opp, 9, {})
    print("  1. Opponent is faster, KOs us with Icicle Crash.")
    print("  2. We faint (0 HP), nullifying our Close Combat attack.")
    print("  Utility = HP_me_after - 1.5 * HP_opp_after")
    print("          = 0.0 - 1.5 * 1.0 (opponent stays at full HP)")
    print(f"          = {score2:.3f}")

if __name__ == "__main__":
    test_minimax_trace()
