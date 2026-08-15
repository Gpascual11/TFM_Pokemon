"""Frozen obs_size and [0, 1] features."""

from __future__ import annotations

import unittest

import numpy as np
from poke_env.battle.pokemon_type import PokemonType
from poke_env.battle.side_condition import SideCondition

from src.p05_ppo_drl.s01_env.vectorizer import OBS_SIZE, PREV_OBS_SIZE, StateVectorizer
from src.p05_ppo_drl.tests.fakes import add_moves, make_battle, make_mon


class TestVectorizer(unittest.TestCase):
    def test_obs_size_frozen(self):
        v = StateVectorizer()
        self.assertEqual(v.obs_size, OBS_SIZE)
        self.assertEqual(OBS_SIZE, 346)
        self.assertEqual(PREV_OBS_SIZE, 328)

    def test_embed_in_unit_interval(self):
        me = make_mon("pikachu")
        add_moves(me, ["thunderbolt", "volttackle", "irontail", "agility"])
        opp = make_mon("charizard")
        battle = make_battle(team=[me, make_mon("dragonite")], opponent=opp, can_tera=True)
        vec = StateVectorizer().embed_battle(battle)
        self.assertEqual(vec.shape, (OBS_SIZE,))
        self.assertEqual(vec.dtype, np.float32)
        self.assertTrue(np.all(vec >= 0.0))
        self.assertTrue(np.all(vec <= 1.0))
        self.assertGreater(float(vec.sum()), 0.0)

    def test_switch_matchup_ranks_better_type(self):
        """Swampert vs Charizard should outrank a Charizard mirror on switch_mu."""
        v = StateVectorizer()
        foe = make_mon("charizard")
        vec = v.embed_battle(make_battle(team=[make_mon("swampert"), make_mon("charizard")], opponent=foe))
        mu = vec[v.offset("switch_mu")]
        self.assertGreater(float(mu[0]), float(mu[1]))

    def test_hazard_cost_ranks_rock_weak(self):
        """Stealth Rock: Charizard (4×) costs more HP than Swampert (0.5×)."""
        v = StateVectorizer()
        rocks = {SideCondition.STEALTH_ROCK: 1}
        vec = v.embed_battle(
            make_battle(
                team=[make_mon("charizard"), make_mon("swampert")],
                opponent=make_mon("tyranitar"),
                side_conditions=rocks,
            )
        )
        cost = vec[v.offset("hazard_cost")]
        self.assertGreater(float(cost[0]), float(cost[1]))
        self.assertAlmostEqual(float(cost[0]), 0.5, places=2)
        self.assertAlmostEqual(float(cost[1]), 0.0625, places=3)

    def test_preview_matchup_uses_revealed_team(self):
        v = StateVectorizer()
        swampert = make_mon("swampert")
        charizard = make_mon("charizard")
        vec = v.embed_battle(
            make_battle(
                team=[swampert, charizard],
                opponent=charizard,
                opponent_team=[make_mon("charizard"), make_mon("tyranitar")],
            )
        )
        preview = vec[v.offset("preview_mu")]
        self.assertGreater(float(preview[0]), float(preview[1]))

    def test_tera_move_dmg_nonzero_when_can_tera(self):
        me = make_mon("pikachu")
        add_moves(me, ["thunderbolt", "volttackle", "irontail", "agility"])
        me._terastallized_type = PokemonType.ELECTRIC
        battle = make_battle(team=[me], opponent=make_mon("gyarados"), can_tera=True)
        v = StateVectorizer()
        vec = v.embed_battle(battle)
        tera_dmg = vec[v.offset("tera_move_dmg")]
        move_dmg = vec[v.offset("move_dmg")]
        self.assertGreater(float(tera_dmg[0]), 0.0)
        self.assertGreaterEqual(float(tera_dmg[0]), float(move_dmg[0]))


if __name__ == "__main__":
    unittest.main()
