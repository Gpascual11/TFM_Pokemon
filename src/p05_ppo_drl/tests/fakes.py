"""Shared fake battles for mask / vectorizer unit tests. No Showdown."""

from __future__ import annotations

from types import SimpleNamespace

from poke_env.battle.move import Move
from poke_env.battle.pokemon import Pokemon
from poke_env.battle.status import Status
from poke_env.player.battle_order import SingleBattleOrder


def make_mon(species: str, *, fainted: bool = False) -> Pokemon:
    mon = Pokemon(gen=9, species=species)
    mon._max_hp = 100
    if fainted:
        mon._status = Status.FNT
        mon._current_hp = 0
    else:
        mon._current_hp = 100
        mon._status = None
    return mon


def add_moves(mon: Pokemon, move_ids: list[str]) -> list[Move]:
    for mid in move_ids:
        mon._moves[mid] = Move(mid, gen=9)
    return list(mon._moves.values())


def make_battle(
    *,
    team: list[Pokemon],
    active_idx: int = 0,
    available_move_ids: list[str] | None = None,
    available_switch_indices: list[int] | None = None,
    force_switch: bool = False,
    can_tera: bool = False,
    wait: bool = False,
    trapped: bool = False,
    opponent: Pokemon | None = None,
    opponent_team: list[Pokemon] | None = None,
    side_conditions: dict | None = None,
) -> SimpleNamespace:
    team_dict = {f"p1: {m.species}": m for m in team}
    active = team[active_idx] if team else None
    if available_switch_indices is None:
        switches = [m for i, m in enumerate(team) if i != active_idx and not m.fainted]
    else:
        switches = [team[i] for i in available_switch_indices]
    if available_move_ids is None:
        moves = list(active.moves.values()) if active is not None else []
    else:
        special = {"struggle", "recharge"}
        moves = []
        for mid in available_move_ids:
            if mid in special:
                moves.append(Move(mid, gen=9))
            elif active is not None and mid in active.moves:
                moves.append(active.moves[mid])
            else:
                moves.append(Move(mid, gen=9))
    opp = opponent or make_mon("charizard")
    opp_team_list = opponent_team if opponent_team is not None else [opp]
    opp_team = {f"p2: {m.species}{i}": m for i, m in enumerate(opp_team_list)}
    battle = SimpleNamespace(
        _wait=wait,
        force_switch=force_switch,
        can_tera=can_tera,
        trapped=trapped,
        team=team_dict,
        available_switches=switches,
        available_moves=moves,
        active_pokemon=active,
        opponent_active_pokemon=opp,
        opponent_team=opp_team,
        side_conditions=side_conditions or {},
        opponent_side_conditions={},
        weather={},
        fields={},
        valid_orders=[],
        player_username="p1",
        battle_tag="test",
        team_size=6,
        finished=False,
        won=False,
        lost=False,
        turn=1,
    )
    if force_switch:
        battle.valid_orders = [SingleBattleOrder(s) for s in switches]
    else:
        battle.valid_orders = [SingleBattleOrder(m) for m in moves]
        if can_tera:
            battle.valid_orders += [SingleBattleOrder(m, terastallize=True) for m in moves]
        battle.valid_orders += [SingleBattleOrder(s) for s in switches]
    return battle
