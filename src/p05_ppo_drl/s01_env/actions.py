"""Discrete(14) action space: 4 moves, 4 moves+Tera, 6 switches.

``action_masks`` and ``action_to_order`` share the same slot mapping.
Switch slots use ``battle.team.values()`` objects (same identity as
``available_switches``), never ``pokemon.name`` vs ``team.keys()``.
Move slots use ``active.moves`` order, except Struggle/recharge which occupy
slot 0 because they are not in the moves dict.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

import numpy as np
from poke_env.player.battle_order import DefaultBattleOrder, SingleBattleOrder
from poke_env.player.player import Player

from ..constants import ACTION_N, MOVE_OFFSET, N_MOVES, N_SWITCHES, SWITCH_OFFSET, TERA_OFFSET

_SPECIAL_MOVE_IDS = {"struggle", "recharge"}


def _as_int(action: Any) -> int:
    return int(np.asarray(action).reshape(-1)[0])


def team_slots(battle) -> list[Any]:
    """Stable 6-slot list of our Pokémon objects (``None`` if missing)."""
    slots: list[Any] = [None] * N_SWITCHES
    if battle is None or getattr(battle, "team", None) is None:
        return slots
    for i, mon in enumerate(list(battle.team.values())[:N_SWITCHES]):
        slots[i] = mon
    return slots


def move_slots(battle) -> list[Any]:
    """Stable 4-slot list of moves aligned with ``action_to_order``.

    Struggle / recharge are not stored on ``pokemon.moves``. They occupy slot 0
    when they are the only available move, matching poke-env SinglesEnv.
    """
    slots: list[Any] = [None] * N_MOVES
    if battle is None:
        return slots
    available = list(getattr(battle, "available_moves", None) or [])
    if len(available) == 1 and getattr(available[0], "id", "") in _SPECIAL_MOVE_IDS:
        slots[0] = available[0]
        return slots
    active = getattr(battle, "active_pokemon", None)
    if active is None:
        return slots
    raw = getattr(active, "moves", None)
    if isinstance(raw, dict):
        moves = list(raw.values())
    elif raw:
        moves = list(raw)
    else:
        moves = []
    for i, move in enumerate(moves[:N_MOVES]):
        slots[i] = move
    return slots


def _same_mon(a, b) -> bool:
    if a is None or b is None:
        return False
    if a is b:
        return True
    return getattr(a, "species", None) == getattr(b, "species", None) and getattr(a, "species", None) is not None


def _in_available_switches(mon, battle) -> bool:
    if mon is None or getattr(mon, "fainted", False):
        return False
    for sw in getattr(battle, "available_switches", None) or []:
        if _same_mon(mon, sw) and not getattr(sw, "fainted", False):
            return True
    return False


def _available_ids(battle) -> set[str]:
    return {m.id for m in (getattr(battle, "available_moves", None) or []) if getattr(m, "id", None)}


def _move_legal(move, battle) -> bool:
    if move is None or battle is None:
        return False
    if getattr(battle, "force_switch", False) or getattr(battle, "_wait", False):
        return False
    if getattr(move, "id", None) not in _available_ids(battle):
        return False
    if getattr(move, "id", "") not in _SPECIAL_MOVE_IDS and int(getattr(move, "current_pp", 1) or 0) <= 0:
        return False
    return True


def _can_tera(battle) -> bool:
    return bool(getattr(battle, "can_tera", False))


def action_masks(battle) -> np.ndarray:
    """Binary mask, length ``ACTION_N``. 1 = legal for ``action_to_order``."""
    mask = np.zeros(ACTION_N, dtype=np.int8)
    if battle is None or getattr(battle, "_wait", False):
        mask[0] = 1
        return mask

    slots = team_slots(battle)
    if getattr(battle, "force_switch", False):
        for i, mon in enumerate(slots):
            if _in_available_switches(mon, battle):
                mask[SWITCH_OFFSET + i] = 1
        if not mask.any():
            _force_switch_fallback(mask, battle, slots)
        return mask

    if not getattr(battle, "trapped", False):
        for i, mon in enumerate(slots):
            if _in_available_switches(mon, battle):
                mask[SWITCH_OFFSET + i] = 1

    moves = move_slots(battle)
    tera = _can_tera(battle)
    for i, move in enumerate(moves):
        if _move_legal(move, battle):
            mask[MOVE_OFFSET + i] = 1
            if tera:
                mask[TERA_OFFSET + i] = 1

    if not mask.any():
        if getattr(battle, "valid_orders", None):
            mask[0] = 1
        else:
            mask[0] = 1
    return mask


def _force_switch_fallback(mask: np.ndarray, battle, slots: Sequence[Any]) -> None:
    """Never enable the fainted active's slot just because it is index 0."""
    for sw in getattr(battle, "available_switches", None) or []:
        if getattr(sw, "fainted", False):
            continue
        for i, mon in enumerate(slots):
            if _same_mon(mon, sw):
                mask[SWITCH_OFFSET + i] = 1
                return
    for i, mon in enumerate(slots):
        if mon is not None and not getattr(mon, "fainted", False):
            mask[SWITCH_OFFSET + i] = 1
            return
    mask[SWITCH_OFFSET] = 1


def action_to_order(action, battle, fake: bool = False, strict: bool = True, **kwargs):
    """Map a Discrete(14) index to a ``BattleOrder``. Inverse of ``order_to_action``."""
    try:
        return _action_to_order_inner(action, battle)
    except Exception as exc:
        if strict and not fake:
            raise exc
        return _fallback_order(battle)


def _action_to_order_inner(action, battle):
    if battle is None or getattr(battle, "_wait", False):
        return DefaultBattleOrder()

    idx = _as_int(action)
    if idx < 0:
        return DefaultBattleOrder()

    if getattr(battle, "force_switch", False):
        return _switch_order(idx, battle) or _fallback_order(battle)

    if MOVE_OFFSET <= idx < MOVE_OFFSET + N_MOVES:
        move = move_slots(battle)[idx - MOVE_OFFSET]
        if _move_legal(move, battle):
            return Player.create_order(move)
        return _fallback_order(battle)

    if TERA_OFFSET <= idx < TERA_OFFSET + N_MOVES:
        if not _can_tera(battle):
            return _fallback_order(battle)
        move = move_slots(battle)[idx - TERA_OFFSET]
        if _move_legal(move, battle):
            return Player.create_order(move, terastallize=True)
        return _fallback_order(battle)

    if SWITCH_OFFSET <= idx < SWITCH_OFFSET + N_SWITCHES:
        order = _switch_order(idx, battle)
        if order is not None:
            return order
        return _fallback_order(battle)

    return _fallback_order(battle)


def _switch_order(idx: int, battle) -> Optional[SingleBattleOrder]:
    if SWITCH_OFFSET <= idx < SWITCH_OFFSET + N_SWITCHES:
        slot = idx - SWITCH_OFFSET
        mon = team_slots(battle)[slot]
        if _in_available_switches(mon, battle):
            return Player.create_order(mon)
    return _first_legal_switch(battle)


def _first_legal_switch(battle) -> Optional[SingleBattleOrder]:
    for sw in getattr(battle, "available_switches", None) or []:
        if not getattr(sw, "fainted", False):
            return Player.create_order(sw)
    return None


def _fallback_order(battle):
    if battle is None:
        return DefaultBattleOrder()
    orders = getattr(battle, "valid_orders", None) or []
    if orders:
        return orders[0]
    sw = _first_legal_switch(battle)
    if sw is not None:
        return sw
    available = list(getattr(battle, "available_moves", None) or [])
    if available:
        tera = _can_tera(battle)
        return Player.create_order(available[0], terastallize=tera)
    return DefaultBattleOrder()


def order_to_action(order, battle, fake: bool = False, strict: bool = True) -> np.int64:
    """Inverse of ``action_to_order``. Used so a v12 opponent round-trips Tera."""
    try:
        return _order_to_action_inner(order, battle)
    except Exception as exc:
        if strict and not fake:
            raise exc
        mask = action_masks(battle)
        hits = np.flatnonzero(mask)
        return np.int64(int(hits[0]) if len(hits) else 0)


def _order_to_action_inner(order, battle) -> np.int64:
    if order is None or isinstance(order, DefaultBattleOrder):
        return np.int64(0)
    chosen = getattr(order, "order", None)
    if chosen is None:
        return np.int64(0)

    # Switch: chosen is a Pokemon
    if hasattr(chosen, "species") and not hasattr(chosen, "base_power"):
        for i, mon in enumerate(team_slots(battle)):
            if _same_mon(mon, chosen):
                return np.int64(SWITCH_OFFSET + i)
        return np.int64(SWITCH_OFFSET)

    # Move
    tera = bool(getattr(order, "terastallize", False))
    move_id = getattr(chosen, "id", None)
    for i, move in enumerate(move_slots(battle)):
        if move is not None and getattr(move, "id", None) == move_id:
            return np.int64((TERA_OFFSET if tera else MOVE_OFFSET) + i)
    return np.int64(TERA_OFFSET if tera else MOVE_OFFSET)


def first_legal_action(battle) -> int:
    mask = action_masks(battle)
    hits = np.flatnonzero(mask)
    return int(hits[0]) if len(hits) else 0
