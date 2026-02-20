"""Minimal debug: run 2 doubles battles and print per-turn move choices."""
import asyncio, os, sys, uuid
_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_DIR)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)
import importlib; importlib.import_module(os.path.basename(_DIR)); __package__ = os.path.basename(_DIR)

from poke_env import AccountConfiguration, ServerConfiguration
from poke_env.player import RandomPlayer
from poke_env.player.battle_order import DoubleBattleOrder, SingleBattleOrder
from poke_env.battle.move import Move
from poke_env.battle.pokemon import Pokemon as PokeClass
from .heuristics.v1 import HeuristicV1Doubles


class DebugV1(HeuristicV1Doubles):
    def choose_doubles_move(self, battle):
        slot0_orders, slot1_orders = battle.valid_orders
        active = battle.active_pokemon
        mon0, mon1 = (active[0] if len(active) > 0 else None), (active[1] if len(active) > 1 else None)
        opps = [o for o in (battle.opponent_active_pokemon or []) if o is not None]
        opp_species = [o.species for o in opps]

        def score0(o):
            return self._score_order(o, mon0, 0, battle) if mon0 else 0.0
        def score1(o):
            return self._score_order(o, mon1, 1, battle) if mon1 else 0.0

        valid_pairs = DoubleBattleOrder.join_orders(slot0_orders, slot1_orders)
        if not valid_pairs:
            result = self.choose_random_doubles_move(battle)
            print(f"  [FALLBACK-NOPAIRS] {battle.turn}")
            return result

        best = max(valid_pairs, key=lambda p: score0(p.first_order) + score1(p.second_order))
        s0 = score0(best.first_order)
        s1 = score1(best.second_order)

        def fmt(o):
            a = o.order
            if isinstance(a, Move):
                return f"move:{a.id}(bp={a.base_power},tgt={o.move_target},tera={o.terastallize})"
            elif isinstance(a, PokeClass):
                return f"switch:{a.species}"
            return f"pass/str:{a}"

        print(f"  T{battle.turn} opps={opp_species} mon0={mon0.species if mon0 else None}({mon0.current_hp_fraction:.0%} HP) mon1={mon1.species if mon1 else None}({mon1.current_hp_fraction:.0%} HP)")
        print(f"    slot0: {fmt(best.first_order)} score={s0:.1f}  slot1: {fmt(best.second_order)} score={s1:.1f}")
        print(f"    msg preview: {best.message[:80]}")
        return best


async def main():
    cfg = ServerConfiguration("ws://127.0.0.1:8000/showdown/websocket", None)
    tag = str(uuid.uuid4())[:4]
    player = DebugV1(battle_format="gen9randomdoublesbattle", server_configuration=cfg,
                     max_concurrent_battles=1,
                     account_configuration=AccountConfiguration(f"DbgV1{tag}", None))
    opp = RandomPlayer(battle_format="gen9randomdoublesbattle", server_configuration=cfg,
                       max_concurrent_battles=1,
                       account_configuration=AccountConfiguration(f"DbgRnd{tag}", None))
    print("=== Running 2 debug battles ===")
    await player.battle_against(opp, n_battles=2)
    print(f"\nResult: {player.n_won_battles}/2 wins")

if __name__ == "__main__":
    asyncio.run(main())
