"""action_masks ↔ action_to_order lockstep. No Showdown."""

from __future__ import annotations

import unittest

from poke_env.player.battle_order import DefaultBattleOrder, SingleBattleOrder

from src.p05_ppo_drl.constants import ACTION_N, MOVE_OFFSET, N_MOVES, SWITCH_OFFSET, TERA_OFFSET
from src.p05_ppo_drl.s01_env.actions import action_masks, action_to_order, order_to_action
from src.p05_ppo_drl.tests.fakes import add_moves, make_battle, make_mon


def _lockstep(battle) -> None:
    mask = action_masks(battle)
    assert mask.shape == (ACTION_N,)
    hits = [i for i, v in enumerate(mask) if v]
    assert hits, "mask must have at least one legal action"
    for i, bit in enumerate(mask):
        order = action_to_order(i, battle, strict=False)
        if bit:
            assert not isinstance(order, DefaultBattleOrder), f"legal slot {i} mapped to default"
            back = int(order_to_action(order, battle, strict=False))
            # Struggle occupies slot 0 even if order_to_action uses move id.
            if i < SWITCH_OFFSET:
                assert 0 <= back < SWITCH_OFFSET
            else:
                assert back == i or mask[back], f"switch slot {i} round-trip {back}"
        else:
            # Illegal actions may fallback; they must not target a fainted active switch slot 0
            # when that mon is fainted. Checked in dedicated tests.
            assert order is not None


class TestActionMasks(unittest.TestCase):
    def test_forced_switch_skips_fainted_active(self):
        fainted = make_mon("pikachu", fainted=True)
        alive_a = make_mon("dragonite")
        alive_b = make_mon("garchomp")
        battle = make_battle(
            team=[fainted, alive_a, alive_b],
            active_idx=0,
            force_switch=True,
            available_move_ids=[],
            available_switch_indices=[1, 2],
        )
        mask = action_masks(battle)
        self.assertEqual(int(mask[SWITCH_OFFSET + 0]), 0)
        self.assertEqual(int(mask[SWITCH_OFFSET + 1]), 1)
        self.assertEqual(int(mask[SWITCH_OFFSET + 2]), 1)
        for i in range(N_MOVES * 2):
            self.assertEqual(int(mask[i]), 0)
        order = action_to_order(SWITCH_OFFSET + 1, battle, strict=False)
        self.assertIsInstance(order, SingleBattleOrder)
        self.assertEqual(order.order.species, alive_a.species)
        _lockstep(battle)

    def test_forced_switch_fallback_is_not_fainted_slot_zero(self):
        """Old bug: mask[4]=1 could be the fainted active (now switch offset 8)."""
        fainted = make_mon("pikachu", fainted=True)
        bench = make_mon("dragonite")
        battle = make_battle(
            team=[fainted, bench],
            active_idx=0,
            force_switch=True,
            available_move_ids=[],
            available_switch_indices=[1],
        )
        # Even if available_switches were empty, fallback must not pick fainted slot 0.
        battle.available_switches = []
        mask = action_masks(battle)
        self.assertEqual(int(mask[SWITCH_OFFSET + 0]), 0)
        self.assertEqual(int(mask[SWITCH_OFFSET + 1]), 1)

    def test_zero_pp_is_masked_out(self):
        me = make_mon("pikachu")
        opp = make_mon("blissey")
        moves = add_moves(me, ["thunderbolt", "volttackle", "irontail", "agility"])
        moves[0]._current_pp = 0
        battle = make_battle(
            team=[me, make_mon("dragonite")],
            available_move_ids=["volttackle", "irontail", "agility"],
            opponent=opp,
        )
        mask = action_masks(battle)
        self.assertEqual(int(mask[MOVE_OFFSET + 0]), 0)
        self.assertEqual(int(mask[MOVE_OFFSET + 1]), 1)
        order = action_to_order(MOVE_OFFSET + 0, battle, strict=False)
        # Fallback must not be the 0 PP move.
        if isinstance(order, SingleBattleOrder) and hasattr(order.order, "id"):
            self.assertNotEqual(order.order.id, "thunderbolt")
        _lockstep(battle)

    def test_choice_lock_only_locked_move(self):
        me = make_mon("gengar")
        add_moves(me, ["shadowball", "sludgebomb", "focusblast", "thunderbolt"])
        battle = make_battle(
            team=[me, make_mon("dragonite")],
            available_move_ids=["shadowball"],
        )
        mask = action_masks(battle)
        self.assertEqual(int(mask[MOVE_OFFSET + 0]), 1)
        self.assertEqual(int(mask[MOVE_OFFSET + 1]), 0)
        self.assertEqual(int(mask[MOVE_OFFSET + 2]), 0)
        self.assertEqual(int(mask[MOVE_OFFSET + 3]), 0)
        order = action_to_order(MOVE_OFFSET + 0, battle, strict=False)
        self.assertEqual(order.order.id, "shadowball")
        _lockstep(battle)

    def test_can_tera_true_enables_tera_slots(self):
        me = make_mon("pikachu")
        add_moves(me, ["thunderbolt", "volttackle", "irontail", "agility"])
        battle = make_battle(team=[me, make_mon("dragonite")], can_tera=True)
        mask = action_masks(battle)
        self.assertEqual(int(mask[TERA_OFFSET + 0]), 1)
        order = action_to_order(TERA_OFFSET + 0, battle, strict=False)
        self.assertTrue(getattr(order, "terastallize", False))
        back = int(order_to_action(order, battle, strict=False))
        self.assertEqual(back, TERA_OFFSET + 0)
        _lockstep(battle)

    def test_can_tera_false_disables_tera_slots(self):
        me = make_mon("pikachu")
        add_moves(me, ["thunderbolt", "volttackle", "irontail", "agility"])
        battle = make_battle(team=[me, make_mon("dragonite")], can_tera=False)
        mask = action_masks(battle)
        for i in range(N_MOVES):
            self.assertEqual(int(mask[TERA_OFFSET + i]), 0)
        order = action_to_order(TERA_OFFSET + 0, battle, strict=False)
        self.assertFalse(getattr(order, "terastallize", False))

    def test_struggle_uses_slot_zero_not_moves_dict(self):
        me = make_mon("pikachu")
        add_moves(me, ["thunderbolt", "volttackle", "irontail", "agility"])
        for mv in me.moves.values():
            mv._current_pp = 0
        battle = make_battle(
            team=[me, make_mon("dragonite")],
            available_move_ids=["struggle"],
        )
        mask = action_masks(battle)
        self.assertEqual(int(mask[MOVE_OFFSET + 0]), 1)
        order = action_to_order(MOVE_OFFSET + 0, battle, strict=False)
        self.assertEqual(order.order.id, "struggle")

    def test_name_vs_team_keys_does_not_break_switches(self):
        """team.keys() are 'p1: species'; pokemon.name is a display string."""
        me = make_mon("pikachu")
        add_moves(me, ["thunderbolt"])
        bench = make_mon("dragonite")
        battle = make_battle(team=[me, bench], available_switch_indices=[1])
        self.assertIn("p1:", next(iter(battle.team.keys())))
        mask = action_masks(battle)
        self.assertEqual(int(mask[SWITCH_OFFSET + 1]), 1)
        order = action_to_order(SWITCH_OFFSET + 1, battle, strict=False)
        self.assertEqual(order.order.species, bench.species)

    def test_wait_is_default(self):
        me = make_mon("pikachu")
        add_moves(me, ["thunderbolt"])
        battle = make_battle(team=[me], wait=True)
        mask = action_masks(battle)
        self.assertEqual(int(mask[0]), 1)
        self.assertEqual(int(mask.sum()), 1)
        self.assertIsInstance(action_to_order(0, battle, strict=False), DefaultBattleOrder)


if __name__ == "__main__":
    unittest.main()
