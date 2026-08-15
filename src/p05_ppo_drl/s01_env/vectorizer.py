"""Frozen gen9randombattle observation for MaskablePPO.

All features are float32 in [0, 1]. ``OBS_SIZE`` is frozen; changing it
invalidates ``data/models/ppo/<phase>/*.zip`` unless the first layer is expanded
(claim 328 zips load into 346 by copying old columns and zero-init of the new ones).
"""

from __future__ import annotations

import numpy as np
from poke_env.battle.field import Field
from poke_env.battle.pokemon_type import PokemonType
from poke_env.battle.side_condition import STACKABLE_CONDITIONS, SideCondition
from poke_env.battle.status import Status
from poke_env.battle.weather import Weather
from poke_env.data import GenData

from .actions import move_slots, team_slots

_MAX_BASE_POWER = 250.0
_MAX_SPEED = 250.0
_STAB_EFF_CEILING = 8.0  # 2.0 STAB × 4.0 type effectiveness

# Frozen layout (gen9 poke-env enums: 20 types, 7 statuses, 9 weathers, 14 fields, 24 SC).
# Recomputed in StateVectorizer.__init__; tests assert equality with OBS_SIZE.
PREV_OBS_SIZE = 328  # Claim zips (Phase 1–3). First-layer weights are copied on load.
OBS_SIZE = 346  # +6 preview matchup + 1 best-lead + 4 tera move dmg + 1 tera def + 6 hazard cost
OBS_SIZE_318 = 318  # Phase 1 / 1.5 original


class StateVectorizer:
    """Battle → flat float32 vector. Size is ``OBS_SIZE``."""

    NUM_MOVE_SLOTS = 4
    NUM_TEAM_SLOTS = 6

    def __init__(self) -> None:
        self.num_types = len(PokemonType)
        self.num_statuses = len(Status)
        self.num_weathers = len(Weather)
        self.num_fields = len(Field)
        self.num_side_conditions = len(SideCondition)
        self.num_boosts = 7

        active_dims = 1 + self.num_types + self.num_statuses + self.num_boosts
        move_type_bp = self.NUM_MOVE_SLOTS * (self.num_types + 1)
        self.layout = {
            "me_active": active_dims,
            "opp_active": active_dims,
            "move_type_bp": move_type_bp,
            "move_pp": self.NUM_MOVE_SLOTS,
            "stab_eff": self.NUM_MOVE_SLOTS,
            "own_hp": self.NUM_TEAM_SLOTS,
            "own_fainted": self.NUM_TEAM_SLOTS,
            "own_lead": self.NUM_TEAM_SLOTS,
            "opp_hp": self.NUM_TEAM_SLOTS,
            "opp_fainted": self.NUM_TEAM_SLOTS,
            "opp_lead": self.NUM_TEAM_SLOTS,
            "opp_alive_est": 1,
            "weather": self.num_weathers,
            "field": self.num_fields,
            "me_side": self.num_side_conditions,
            "opp_side": self.num_side_conditions,
            "can_tera": 1,
            "me_already_tera": 1,
            "opp_already_tera": 1,
            "me_tera_type": self.num_types,
            "opp_tera_type": self.num_types,
            "faster": 1,
            "my_spe": 1,
            "opp_spe": 1,
            "force_switch": 1,
            "trapped": 1,
            "move_dmg": self.NUM_MOVE_SLOTS,
            "switch_mu": self.NUM_TEAM_SLOTS,
            "preview_mu": self.NUM_TEAM_SLOTS,
            "best_lead": 1,
            "tera_move_dmg": self.NUM_MOVE_SLOTS,
            "tera_def": 1,
            "hazard_cost": self.NUM_TEAM_SLOTS,
        }
        self.obs_size = int(sum(self.layout.values()))
        if self.obs_size != OBS_SIZE:
            raise RuntimeError(
                f"obs_size recomputed as {self.obs_size}, frozen OBS_SIZE={OBS_SIZE}. "
                "Update OBS_SIZE only if you intend to invalidate PPO checkpoints."
            )

    def embed_battle(self, battle) -> np.ndarray:
        me_active = self._embed_active_pokemon(getattr(battle, "active_pokemon", None))
        opp_active = self._embed_active_pokemon(getattr(battle, "opponent_active_pokemon", None))
        me_moves = self._embed_moves(battle)
        me_pp = self._embed_pp(battle)
        stab_eff = self._embed_stab_eff(battle)
        own_hp, own_fainted, own_lead = self._embed_own_team(battle)
        opp_hp, opp_fainted, opp_lead, opp_alive = self._embed_opp_team(battle)
        environment = self._embed_environment(battle)
        me_side = self._embed_side_conditions(getattr(battle, "side_conditions", None) or {})
        opp_side = self._embed_side_conditions(getattr(battle, "opponent_side_conditions", None) or {})
        tera = self._embed_tera(battle)
        speed = self._embed_speed(battle)
        flags = np.array(
            [
                1.0 if getattr(battle, "force_switch", False) else 0.0,
                1.0 if getattr(battle, "trapped", False) else 0.0,
            ],
            dtype=np.float32,
        )
        move_dmg = self._embed_move_damage(battle, as_tera=False)
        switch_mu = self._embed_switch_matchup(battle)
        preview_mu = self._embed_preview_matchup(battle)
        best_lead = self._embed_best_lead(preview_mu, battle)
        tera_move = self._embed_move_damage(battle, as_tera=True)
        tera_def = self._embed_tera_def(battle)
        hazard = self._embed_hazard_cost(battle)
        state = np.concatenate(
            [
                me_active,
                opp_active,
                me_moves,
                me_pp,
                stab_eff,
                own_hp,
                own_fainted,
                own_lead,
                opp_hp,
                opp_fainted,
                opp_lead,
                opp_alive,
                environment,
                me_side,
                opp_side,
                tera,
                speed,
                flags,
                move_dmg,
                switch_mu,
                preview_mu,
                best_lead,
                tera_move,
                tera_def,
                hazard,
            ],
            dtype=np.float32,
        )
        return np.clip(state, 0.0, 1.0)

    def offset(self, name: str) -> slice:
        start = 0
        for key, n in self.layout.items():
            if key == name:
                return slice(start, start + n)
            start += n
        raise KeyError(name)

    def _one_hot_type(self, ptype) -> np.ndarray:
        vec = np.zeros(self.num_types, dtype=np.float32)
        if ptype is None:
            return vec
        idx = int(getattr(ptype, "value", 0)) - 1
        if 0 <= idx < self.num_types:
            vec[idx] = 1.0
        return vec

    def _embed_active_pokemon(self, pokemon) -> np.ndarray:
        size = 1 + self.num_types + self.num_statuses + self.num_boosts
        if pokemon is None:
            return np.zeros(size, dtype=np.float32)
        hp = np.array([float(getattr(pokemon, "current_hp_fraction", 0.0) or 0.0)], dtype=np.float32)
        type_vector = np.zeros(self.num_types, dtype=np.float32)
        for t in getattr(pokemon, "types", None) or []:
            if t is not None:
                idx = int(t.value) - 1
                if 0 <= idx < self.num_types:
                    type_vector[idx] = 1.0
        status_vector = np.zeros(self.num_statuses, dtype=np.float32)
        status = getattr(pokemon, "status", None)
        if status is not None:
            idx = int(status.value) - 1
            if 0 <= idx < self.num_statuses:
                status_vector[idx] = 1.0
        boost_vector = np.zeros(self.num_boosts, dtype=np.float32)
        boosts = getattr(pokemon, "boosts", None) or {}
        for i, stat in enumerate(["atk", "def", "spa", "spd", "spe", "accuracy", "evasion"]):
            boost_vector[i] = (float(boosts.get(stat, 0)) + 6.0) / 12.0
        return np.concatenate([hp, type_vector, status_vector, boost_vector])

    def _embed_moves(self, battle) -> np.ndarray:
        slot_size = self.num_types + 1
        result = np.zeros(self.NUM_MOVE_SLOTS * slot_size, dtype=np.float32)
        for i, move in enumerate(move_slots(battle)):
            if move is None:
                continue
            offset = i * slot_size
            mtype = getattr(move, "type", None)
            if mtype is not None:
                idx = int(mtype.value) - 1
                if 0 <= idx < self.num_types:
                    result[offset + idx] = 1.0
            bp = getattr(move, "base_power", 0) or 0
            result[offset + self.num_types] = min(float(bp) / _MAX_BASE_POWER, 1.0)
        return result

    def _embed_pp(self, battle) -> np.ndarray:
        result = np.zeros(self.NUM_MOVE_SLOTS, dtype=np.float32)
        for i, move in enumerate(move_slots(battle)):
            if move is None:
                continue
            max_pp = float(getattr(move, "max_pp", 0) or 0)
            cur = float(getattr(move, "current_pp", 0) or 0)
            result[i] = 1.0 if max_pp <= 0 else min(max(cur / max_pp, 0.0), 1.0)
        return result

    def _embed_stab_eff(self, battle) -> np.ndarray:
        result = np.zeros(self.NUM_MOVE_SLOTS, dtype=np.float32)
        me = getattr(battle, "active_pokemon", None)
        opp = getattr(battle, "opponent_active_pokemon", None)
        my_types = [t for t in (getattr(me, "types", None) or []) if t is not None]
        for i, move in enumerate(move_slots(battle)):
            if move is None or getattr(move, "type", None) is None:
                continue
            stab = 1.5 if move.type in my_types else 1.0
            if me is not None and getattr(me, "is_terastallized", False):
                tera = getattr(me, "tera_type", None)
                if tera is not None and move.type == tera:
                    # Original-type Tera STAB is 2.0; otherwise 1.5.
                    orig = (getattr(me, "_type_1", None), getattr(me, "_type_2", None))
                    stab = 2.0 if tera in orig else 1.5
            eff = 1.0
            if opp is not None:
                try:
                    eff = float(opp.damage_multiplier(move))
                except Exception:
                    eff = 1.0
            result[i] = min((stab * eff) / _STAB_EFF_CEILING, 1.0)
        return result

    def _embed_own_team(self, battle) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        hp = np.zeros(self.NUM_TEAM_SLOTS, dtype=np.float32)
        fainted = np.zeros(self.NUM_TEAM_SLOTS, dtype=np.float32)
        lead = np.zeros(self.NUM_TEAM_SLOTS, dtype=np.float32)
        active = getattr(battle, "active_pokemon", None)
        for i, mon in enumerate(team_slots(battle)):
            if mon is None:
                continue
            hp[i] = float(getattr(mon, "current_hp_fraction", 0.0) or 0.0)
            fainted[i] = 1.0 if getattr(mon, "fainted", False) else 0.0
            if active is not None and (mon is active or getattr(mon, "species", None) == getattr(active, "species", None)):
                lead[i] = 1.0
        return hp, fainted, lead

    def _embed_opp_team(self, battle) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        hp = np.zeros(self.NUM_TEAM_SLOTS, dtype=np.float32)
        fainted = np.zeros(self.NUM_TEAM_SLOTS, dtype=np.float32)
        lead = np.zeros(self.NUM_TEAM_SLOTS, dtype=np.float32)
        opp_team = getattr(battle, "opponent_team", None) or {}
        opp_active = getattr(battle, "opponent_active_pokemon", None)
        revealed_alive = 0
        mons = list(opp_team.values())[: self.NUM_TEAM_SLOTS]
        for i, mon in enumerate(mons):
            hp[i] = float(getattr(mon, "current_hp_fraction", 0.0) or 0.0)
            is_faint = bool(getattr(mon, "fainted", False))
            fainted[i] = 1.0 if is_faint else 0.0
            if not is_faint:
                revealed_alive += 1
            if opp_active is not None and (mon is opp_active or getattr(mon, "species", None) == getattr(opp_active, "species", None)):
                lead[i] = 1.0
        try:
            ts = int(battle.team_size)
        except Exception:
            ts = 6
        unrevealed = max(0, ts - len(opp_team))
        alive = np.array([(revealed_alive + unrevealed) / 6.0], dtype=np.float32)
        return hp, fainted, lead, alive

    def _embed_environment(self, battle) -> np.ndarray:
        weather_vector = np.zeros(self.num_weathers, dtype=np.float32)
        weather = getattr(battle, "weather", None) or {}
        for w in weather.keys() if hasattr(weather, "keys") else weather:
            idx = int(getattr(w, "value", 0)) - 1
            if 0 <= idx < self.num_weathers:
                weather_vector[idx] = 1.0
        field_vector = np.zeros(self.num_fields, dtype=np.float32)
        fields = getattr(battle, "fields", None) or {}
        for f in fields.keys() if hasattr(fields, "keys") else fields:
            idx = int(getattr(f, "value", 0)) - 1
            if 0 <= idx < self.num_fields:
                field_vector[idx] = 1.0
        return np.concatenate([weather_vector, field_vector])

    def _embed_side_conditions(self, side_conditions: dict) -> np.ndarray:
        vector = np.zeros(self.num_side_conditions, dtype=np.float32)
        for sc, count in (side_conditions or {}).items():
            idx = int(getattr(sc, "value", 0)) - 1
            if 0 <= idx < self.num_side_conditions:
                max_stack = STACKABLE_CONDITIONS.get(sc, 1)
                vector[idx] = min(float(count) / float(max_stack), 1.0)
        return vector

    def _embed_tera(self, battle) -> np.ndarray:
        can = 1.0 if getattr(battle, "can_tera", False) else 0.0
        me = getattr(battle, "active_pokemon", None)
        opp = getattr(battle, "opponent_active_pokemon", None)
        me_done = 1.0 if me is not None and getattr(me, "is_terastallized", False) else 0.0
        opp_done = 1.0 if opp is not None and getattr(opp, "is_terastallized", False) else 0.0
        me_type = self._one_hot_type(getattr(me, "tera_type", None) if me is not None else None)
        opp_type = self._one_hot_type(getattr(opp, "tera_type", None) if opp is not None else None)
        return np.concatenate(
            [np.array([can, me_done, opp_done], dtype=np.float32), me_type, opp_type]
        )

    def _embed_speed(self, battle) -> np.ndarray:
        me = getattr(battle, "active_pokemon", None)
        opp = getattr(battle, "opponent_active_pokemon", None)
        my_spe = _speed_stat(me)
        opp_spe = _speed_stat(opp)
        if my_spe > opp_spe:
            faster = 1.0
        elif my_spe < opp_spe:
            faster = 0.0
        else:
            faster = 0.5
        return np.array(
            [faster, min(my_spe / _MAX_SPEED, 1.0), min(opp_spe / _MAX_SPEED, 1.0)],
            dtype=np.float32,
        )

    def _embed_move_damage(self, battle, *, as_tera: bool = False) -> np.ndarray:
        """Boost-aware damage fraction per move slot. ``as_tera`` uses tera-type STAB."""
        out = np.zeros(self.NUM_MOVE_SLOTS, dtype=np.float32)
        me = getattr(battle, "active_pokemon", None)
        opp = getattr(battle, "opponent_active_pokemon", None)
        if me is None or opp is None:
            return out
        if as_tera:
            if not getattr(battle, "can_tera", False) and not getattr(me, "is_terastallized", False):
                return out
            tera = getattr(me, "tera_type", None)
            my_types = [tera] if tera is not None else [t for t in (getattr(me, "types", None) or []) if t is not None]
        else:
            my_types = [t for t in (getattr(me, "types", None) or []) if t is not None]
        phys = _boosted_stat(me, "atk") / max(_boosted_stat(opp, "def"), 1.0)
        spec = _boosted_stat(me, "spa") / max(_boosted_stat(opp, "spd"), 1.0)
        st = getattr(me, "status", None)
        st_name = str(getattr(st, "name", st) or "").upper()
        if st_name in {"BRN", "BURN"}:
            phys *= 0.5
        try:
            from poke_env.battle import MoveCategory
        except Exception:
            MoveCategory = None
        for i, move in enumerate(move_slots(battle)):
            if move is None or (getattr(move, "base_power", 0) or 0) <= 0:
                continue
            cat = getattr(move, "category", None)
            if MoveCategory is not None and cat == getattr(MoveCategory, "PHYSICAL", None):
                ratio = phys
            elif MoveCategory is not None and cat == getattr(MoveCategory, "SPECIAL", None):
                ratio = spec
            else:
                name = str(cat).upper()
                ratio = phys if "PHYSICAL" in name else spec if "SPECIAL" in name else 0.0
            if ratio <= 0:
                continue
            try:
                eff = float(opp.damage_multiplier(move))
            except Exception:
                eff = 1.0
            mtype = getattr(move, "type", None)
            stab = 1.5 if mtype in my_types else 1.0
            if as_tera and mtype in my_types:
                orig = [t for t in (getattr(me, "types", None) or []) if t is not None]
                if mtype in orig:
                    stab = 2.0
            acc = getattr(move, "accuracy", 1.0)
            acc = float(acc) if isinstance(acc, (int, float)) else 1.0
            hits = float(getattr(move, "expected_hits", 1.0) or 1.0)
            raw = float(move.base_power) * ratio * eff * stab * acc * hits
            out[i] = min(raw / 400.0, 1.0)
        return out

    def _embed_switch_matchup(self, battle) -> np.ndarray:
        """Per team-slot matchup vs the active opponent. Without this, switch slots are HP-only."""
        out = np.zeros(self.NUM_TEAM_SLOTS, dtype=np.float32)
        opp = getattr(battle, "opponent_active_pokemon", None)
        for i, mon in enumerate(team_slots(battle)):
            if mon is None or getattr(mon, "fainted", False):
                continue
            out[i] = _matchup01(mon, opp)
        return out

    def _embed_preview_matchup(self, battle) -> np.ndarray:
        """Average matchup of each own slot vs the revealed opponent team (V12 teampreview)."""
        out = np.zeros(self.NUM_TEAM_SLOTS, dtype=np.float32)
        foes = [
            m
            for m in (getattr(battle, "opponent_team", None) or {}).values()
            if m is not None and not getattr(m, "fainted", False)
        ]
        if not foes:
            opp = getattr(battle, "opponent_active_pokemon", None)
            foes = [opp] if opp is not None else []
        for i, mon in enumerate(team_slots(battle)):
            if mon is None or getattr(mon, "fainted", False) or not foes:
                continue
            out[i] = float(np.mean([_matchup01(mon, opp) for opp in foes]))
        return out

    def _embed_best_lead(self, preview_mu: np.ndarray, battle) -> np.ndarray:
        """1 if the active mon is the best preview matchup among living teammates."""
        active = getattr(battle, "active_pokemon", None)
        if active is None or not np.any(preview_mu > 0):
            return np.array([0.0], dtype=np.float32)
        best = float(np.max(preview_mu))
        for i, mon in enumerate(team_slots(battle)):
            if mon is None or getattr(mon, "fainted", False):
                continue
            if abs(float(preview_mu[i]) - best) > 1e-6:
                continue
            if mon is active or getattr(mon, "species", None) == getattr(active, "species", None):
                return np.array([1.0], dtype=np.float32)
        return np.array([0.0], dtype=np.float32)

    def _embed_tera_def(self, battle) -> np.ndarray:
        """How much tera would reduce the opponent's STAB vs us. 0.5 = no change."""
        me = getattr(battle, "active_pokemon", None)
        opp = getattr(battle, "opponent_active_pokemon", None)
        tera = getattr(me, "tera_type", None) if me is not None else None
        if me is None or opp is None or tera is None:
            return np.array([0.5], dtype=np.float32)
        if not getattr(battle, "can_tera", False) and not getattr(me, "is_terastallized", False):
            return np.array([0.5], dtype=np.float32)
        now = _max_incoming(me.types, opp.types)
        after = _max_incoming([tera], opp.types)
        return np.array([float(np.clip((now - after + 4.0) / 8.0, 0.0, 1.0))], dtype=np.float32)

    def _embed_hazard_cost(self, battle) -> np.ndarray:
        """HP fraction lost on switch-in from our side's rocks/spikes/web."""
        out = np.zeros(self.NUM_TEAM_SLOTS, dtype=np.float32)
        sc = getattr(battle, "side_conditions", None) or {}
        for i, mon in enumerate(team_slots(battle)):
            if mon is None or getattr(mon, "fainted", False):
                continue
            out[i] = min(_hazard_fraction(mon, sc), 1.0)
        return out


def _speed_stat(mon) -> float:
    if mon is None:
        return 0.0
    stats = getattr(mon, "stats", None) or {}
    spe = stats.get("spe") if isinstance(stats, dict) else None
    if spe:
        return float(spe)
    base = getattr(mon, "base_stats", None) or {}
    return float(base.get("spe", 0) or 0)


def _boosted_stat(mon, stat: str) -> float:
    base = 100.0
    bs = getattr(mon, "base_stats", None) or {}
    if isinstance(bs, dict):
        base = float(bs.get(stat, 100) or 100)
    boosts = getattr(mon, "boosts", None) or {}
    boost = float(boosts.get(stat, 0) or 0)
    if boost > 0:
        mult = (2.0 + boost) / 2.0
    elif boost < 0:
        mult = 2.0 / (2.0 - boost)
    else:
        mult = 1.0
    return ((2.0 * base + 31.0) + 5.0) * mult


def _matchup01(mon, opponent) -> float:
    """V8-style type/speed/HP matchup mapped to [0, 1]."""
    if mon is None or opponent is None:
        return 0.5
    mon_types = [t for t in (getattr(mon, "types", None) or []) if t is not None]
    opp_types = [t for t in (getattr(opponent, "types", None) or []) if t is not None]
    if not mon_types or not opp_types:
        return 0.5
    score = 0.0
    try:
        score += max(float(opponent.damage_multiplier(t)) for t in mon_types)
        score -= max(float(mon.damage_multiplier(t)) for t in opp_types)
    except Exception:
        return 0.5
    mon_spe = float((getattr(mon, "base_stats", None) or {}).get("spe", 100) or 100)
    opp_spe = float((getattr(opponent, "base_stats", None) or {}).get("spe", 100) or 100)
    if mon_spe > opp_spe:
        score += 0.1
    elif opp_spe > mon_spe:
        score -= 0.1
    score += float(getattr(mon, "current_hp_fraction", 0.0) or 0.0) * 0.4
    score -= float(getattr(opponent, "current_hp_fraction", 0.0) or 0.0) * 0.4
    return float(np.clip((score + 4.0) / 8.0, 0.0, 1.0))


_TYPE_CHART = None


def _type_chart() -> dict:
    global _TYPE_CHART
    if _TYPE_CHART is None:
        _TYPE_CHART = GenData.from_gen(9).type_chart
    return _TYPE_CHART


def _combined_eff(atk_type, def_types) -> float:
    if atk_type is None:
        return 1.0
    row = _type_chart().get(str(getattr(atk_type, "name", atk_type)).upper(), {})
    m = 1.0
    for dt in def_types or []:
        if dt is None:
            continue
        m *= float(row.get(str(getattr(dt, "name", dt)).upper(), 1.0))
    return m


def _max_incoming(def_types, opp_types) -> float:
    best = 0.0
    for ot in opp_types or []:
        if ot is None:
            continue
        best = max(best, _combined_eff(ot, def_types))
    return best


def _grounded(mon) -> bool:
    types = [t for t in (getattr(mon, "types", None) or []) if t is not None]
    if any(str(getattr(t, "name", t)).upper() == "FLYING" for t in types):
        return False
    ability = str(getattr(mon, "ability", "") or getattr(mon, "item", "") or "").lower()
    if "levitate" in ability or ability == "airballoon":
        return False
    return True


def _hazard_fraction(mon, side_conditions: dict) -> float:
    dmg = 0.0
    grounded = _grounded(mon)
    for sc, count in (side_conditions or {}).items():
        name = str(getattr(sc, "name", sc)).upper()
        n = int(count or 0)
        if n <= 0:
            continue
        if name in {"STEALTH_ROCK", "STEALTHROCK"}:
            try:
                eff = float(mon.damage_multiplier(PokemonType.ROCK))
            except Exception:
                eff = _combined_eff(PokemonType.ROCK, getattr(mon, "types", None))
            dmg += 0.125 * eff
        elif name == "SPIKES" and grounded:
            dmg += {1: 0.125, 2: 1.0 / 6.0, 3: 0.25}.get(min(n, 3), 0.25)
        elif name in {"STICKY_WEB", "STICKYWEB"} and grounded:
            dmg += 0.08
    return float(dmg)


if __name__ == "__main__":
    v = StateVectorizer()
    print(f"Observation size: {v.obs_size}")
    for k, n in v.layout.items():
        print(f"  {k:18s} {n}")
