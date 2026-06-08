import sys
sys.path.insert(0, "/home/sirp/Documents/MUDS/TFM_Pokemon/pokechamp")
sys.path.insert(0, "/home/sirp/Documents/MUDS/TFM_Pokemon/src")

from unittest.mock import MagicMock
from poke_env.environment.pokemon_type import PokemonType
from poke_env.data import GenData
from p01_heuristics.s01_singles.agents.internal.v14 import HeuristicV14

# Initialize GenData
gd = GenData.from_gen(9)

# Create HeuristicV14 instance
agent = HeuristicV14()

# Create Battle Mock
battle = MagicMock()
battle.can_tera = True

# Mock active pokemon (Bruxish)
bruxish = MagicMock()
bruxish.species = "bruxish"
bruxish._species = "bruxish"
bruxish.type_1 = PokemonType.WATER
bruxish.type_2 = PokemonType.PSYCHIC
bruxish.tera_type = "Psychic"
bruxish._terastallized_type = None
bruxish.current_hp_fraction = 199.0 / 254.0
bruxish.level = 85
bruxish._data = gd
bruxish.base_stats = {"atk": 105, "def": 70, "spa": 70, "spd": 70, "spe": 92}
bruxish.boosts = {"atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0}
bruxish.status = None

# mock damage_multiplier on Pokemon
def bruxish_dm(type_or_move):
    t = type_or_move if isinstance(type_or_move, PokemonType) else type_or_move.type
    return t.damage_multiplier(bruxish.type_1, bruxish.type_2, type_chart=gd.type_chart)
bruxish.damage_multiplier = bruxish_dm

battle.active_pokemon = bruxish

# Mock opponent pokemon (Malamar)
malamar = MagicMock()
malamar.species = "malamar"
malamar._species = "malamar"
malamar.type_1 = PokemonType.DARK
malamar.type_2 = PokemonType.PSYCHIC
malamar.types = [PokemonType.DARK, PokemonType.PSYCHIC]
malamar.current_hp_fraction = 1.0
malamar.level = 82
malamar._data = gd
malamar.base_stats = {"atk": 92, "def": 88, "spa": 68, "spd": 75, "spe": 73}
malamar.moves = {}
malamar.boosts = {"atk": 0, "def": 0, "spa": 0, "spd": 0, "spe": 0}
malamar.status = None

def malamar_dm(type_or_move):
    t = type_or_move if isinstance(type_or_move, PokemonType) else type_or_move.type
    return t.damage_multiplier(malamar.type_1, malamar.type_2, type_chart=gd.type_chart)
malamar.damage_multiplier = malamar_dm

battle.opponent_active_pokemon = malamar

# Mock team alive count
mock_team_member = MagicMock()
mock_team_member.fainted = False
battle.team = {"bruxish": bruxish, "other": mock_team_member}

# Mock Move (Wave Crash)
wave_crash = MagicMock()
wave_crash.id = "wavecrash"
wave_crash.base_power = 120
wave_crash.type = PokemonType.WATER

# Run internal estimations to print
active = bruxish
opp_active = malamar
move = wave_crash
gen = 9
sets_db = agent._load_pokemon_sets(gen)
opp_max_dmg = agent._estimate_max_damage(opp_active, active, gen, sets_db)
opp_max_dmg_fraction = opp_max_dmg / 300.0
is_about_to_faint = opp_max_dmg_fraction >= active.current_hp_fraction

print("opp_max_dmg:", opp_max_dmg)
print("opp_max_dmg_fraction:", opp_max_dmg_fraction)
print("current_hp_fraction:", active.current_hp_fraction)
print("is_about_to_faint:", is_about_to_faint)

opp_types = [t for t in opp_active.types if t is not None]
def_scores = []
for t in opp_types:
    mult = active.damage_multiplier(t)
    def_scores.append(mult)
max_def_multiplier = max(def_scores) if def_scores else 1.0

tera_type = PokemonType.PSYCHIC
def_tera_scores = []
for t in opp_types:
    mult = t.damage_multiplier(tera_type, type_chart=gd.type_chart)
    def_tera_scores.append(mult)
max_def_tera_multiplier = max(def_tera_scores) if def_tera_scores else 1.0

print("max_def_multiplier:", max_def_multiplier)
print("max_def_tera_multiplier:", max_def_tera_multiplier)

res = agent._should_terastallize(battle, wave_crash)
print("Result of _should_terastallize:", res)
