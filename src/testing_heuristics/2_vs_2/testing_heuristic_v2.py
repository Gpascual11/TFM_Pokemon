import asyncio
import itertools
import os
import uuid
from typing import Dict, Set

import pandas as pd
from tqdm import tqdm

from poke_env import AccountConfiguration, ServerConfiguration
from poke_env.data import GenData
from poke_env.player import DoubleBattleOrder, Player


class TFMExpertDoubles(Player):
    """
    Version 2 doubles heuristic (joint action scoring).

    - Enumerates candidate actions for both slots and scores action pairs.
    - Coordinates KOs, avoids redundant double-targeting, and values spread moves.
    - Uses defensive switching / Protect when threatened.

    For analysis, it also records the moves used per battle.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dm = GenData.from_gen(9)
        self._strict_battle_tracking = False
        # battle_tag -> set of move ids this agent used in that battle
        self._used_moves_by_battle: Dict[str, Set[str]] = {}

    def _record_used_move(self, battle_tag: str, move_id: str) -> None:
        """Register that a move id was used in the given battle."""
        s = self._used_moves_by_battle.setdefault(battle_tag, set())
        s.add(move_id)

    def choose_move(self, battle):
        if battle.force_switch:
            return self._choose_force_switch(battle)

        # Use _choose_joint_best_actions, but intercept chosen moves to log them.
        # The joint selector ultimately goes through _action_to_order, so we
        # do not record here; instead we record when converting actions.
        return self._choose_joint_best_actions(battle)

    def _choose_force_switch(self, battle):
        """Handle forced switches, making sure we never try to switch the same Pokémon twice."""
        orders = []
        selected = set()

        if not battle.force_switch:
            return self.choose_random_move(battle)

        for i, needs_to_switch in enumerate(battle.force_switch):
            if not needs_to_switch:
                continue

            switches = battle.available_switches[i] if i < len(battle.available_switches) else []
            if not switches:
                continue

            # Avoid reusing the same bench Pokémon for multiple slots.
            candidates = [s for s in switches if s not in selected]
            if not candidates:
                continue

            best_sw = self._get_best_switch_from_list(candidates, battle) or candidates[0]
            orders.append(self.create_order(best_sw))
            selected.add(best_sw)

        if len(orders) > 1:
            return DoubleBattleOrder(orders[0], orders[1])
        if len(orders) == 1:
            return orders[0]
        return self.choose_random_move(battle)

    def _choose_joint_best_actions(self, battle):
        opponents = [(idx, p) for idx, p in enumerate(battle.opponent_active_pokemon[:2]) if p and not p.fainted]
        if not opponents:
            return self.choose_random_move(battle)

        actions_by_slot = []
        for slot in range(2):
            actions_by_slot.append(self._enumerate_slot_actions(battle, slot, opponents))

        # If one side has no actions, fallback to random.
        if not actions_by_slot[0] and not actions_by_slot[1]:
            return self.choose_random_move(battle)
        if not actions_by_slot[0]:
            return self._action_to_order(actions_by_slot[1][0])
        if not actions_by_slot[1]:
            return self._action_to_order(actions_by_slot[0][0])

        best_pair = None
        best_pair_score = float("-inf")
        for a0, a1 in itertools.product(actions_by_slot[0], actions_by_slot[1]):
            if self._pair_conflicts(a0, a1):
                continue
            score = self._score_joint_actions(battle, a0, a1, opponents)
            if score > best_pair_score:
                best_pair_score = score
                best_pair = (a0, a1)

        if not best_pair:
            return self.choose_random_move(battle)

        o0 = self._action_to_order(best_pair[0])
        o1 = self._action_to_order(best_pair[1])
        if o0 and o1:
            return DoubleBattleOrder(o0, o1)
        return o0 or o1 or self.choose_random_move(battle)

    def _enumerate_slot_actions(self, battle, slot, opponents):
        actions = []

        me = battle.active_pokemon[slot] if slot < len(battle.active_pokemon) else None
        if not me or me.fainted:
            return actions

        moves = battle.available_moves[slot] if slot < len(battle.available_moves) else []
        switches = battle.available_switches[slot] if slot < len(battle.available_switches) else []

        # Emergency defenses: Protect-like moves if very threatened.
        protect_moves = [m for m in moves if self._is_protect_like(m)]
        weakness = self._active_weakness_multiplier(me, battle)
        hp_frac = self._safe_hp_fraction(me)
        if protect_moves and (hp_frac <= 0.30 or weakness >= 4.0):
            for m in protect_moves[:1]:
                actions.append({"kind": "move", "slot": slot, "move": m, "target": None})

        # Consider switching when low HP and in a bad matchup.
        if switches and (hp_frac <= 0.25 or weakness >= 4.0):
            best_sw = self._get_best_switch_from_list(switches, battle)
            if best_sw:
                actions.append({"kind": "switch", "slot": slot, "switch": best_sw})

        # Offensive move candidates with targets (or no target for spread).
        scored = []
        for m in moves:
            if self._is_protect_like(m):
                continue
            if m.base_power and m.base_power > 1:
                if self._is_spread_move(m):
                    sc = self._score_spread_move(m, me, opponents, battle)
                    scored.append((sc, {"kind": "move", "slot": slot, "move": m, "target": None}))
                else:
                    for opp_idx, opp in opponents:
                        sc = self._score_single_target_move(m, me, opp, battle)
                        scored.append((sc, {"kind": "move", "slot": slot, "move": m, "target": opp_idx + 1}))
            else:
                # Status / support moves
                sc = self._score_status_move(m, me, battle)
                scored.append((sc, {"kind": "move", "slot": slot, "move": m, "target": None}))

        scored.sort(key=lambda x: x[0], reverse=True)
        for _, a in scored[:8]:
            actions.append(a)

        # Keep actions deterministic-ish: most valuable first.
        actions = self._dedupe_actions(actions)
        return actions

    def _action_to_order(self, action):
        if not action:
            return None
        if action["kind"] == "switch":
            return self.create_order(action["switch"])
        if action["kind"] == "move":
            target = action.get("target", None)
            if target is None:
                order = self.create_order(action["move"])
            else:
                order = self.create_order(action["move"], move_target=target)

            # Log the chosen move id for this battle.
            move = action["move"]
            if getattr(move, "id", None):
                # battle reference is the current self.battle set by poke-env
                battle = getattr(self, "battle", None)
                if battle is not None:
                    self._record_used_move(battle.battle_tag, move.id)
            return order
        return None

    def _pair_conflicts(self, a0, a1):
        # Switching into same Pokémon is illegal; avoid it.
        if a0["kind"] == "switch" and a1["kind"] == "switch":
            return self._same_switch(a0["switch"], a1["switch"])
        return False

    def _score_joint_actions(self, battle, a0, a1, opponents):
        base = self._score_action(battle, a0, opponents) + self._score_action(battle, a1, opponents)

        # Coordination bonuses/penalties.
        ko_bonus = 0.0
        focus_penalty = 0.0
        spread_synergy = 0.0

        # Build per-opponent expected damage from each action.
        dmg = {0: [0.0, 0.0], 1: [0.0, 0.0]}
        for ai, a in enumerate([a0, a1]):
            if a["kind"] != "move":
                continue
            m = a["move"]
            me = battle.active_pokemon[a["slot"]]
            if not me:
                continue
            if self._is_spread_move(m):
                for opp_idx, opp in opponents:
                    dmg[opp_idx][ai] = self._estimate_doubles_dmg(m, me, opp, battle)
            else:
                t = a.get("target", None)
                if t in (1, 2):
                    opp_idx = t - 1
                    opp = battle.opponent_active_pokemon[opp_idx]
                    if opp and not opp.fainted:
                        dmg[opp_idx][ai] = self._estimate_doubles_dmg(m, me, opp, battle)

        # Prefer splitting into two KOs when possible.
        for opp_idx, opp in opponents:
            if not opp or opp.fainted:
                continue
            hp = max(1, getattr(opp, "current_hp", 1))
            can_ko0 = dmg[opp_idx][0] >= hp
            can_ko1 = dmg[opp_idx][1] >= hp
            if can_ko0:
                ko_bonus += 250.0
            if can_ko1:
                ko_bonus += 250.0

        # Bonus if each slot threatens a different KO this turn.
        if len(opponents) == 2:
            opp0_hp = max(1, getattr(opponents[0][1], "current_hp", 1))
            opp1_hp = max(1, getattr(opponents[1][1], "current_hp", 1))
            if dmg[0][0] >= opp0_hp and dmg[1][1] >= opp1_hp:
                ko_bonus += 400.0
            if dmg[1][0] >= opp1_hp and dmg[0][1] >= opp0_hp:
                ko_bonus += 400.0

        # If both single-target the same opponent but it's not needed, penalize (over-focus).
        same_target = (
            a0["kind"] == "move"
            and a1["kind"] == "move"
            and (a0.get("target") in (1, 2))
            and (a0.get("target") == a1.get("target"))
            and (not self._is_spread_move(a0["move"]))
            and (not self._is_spread_move(a1["move"]))
        )
        if same_target:
            opp_idx = a0["target"] - 1
            opp = battle.opponent_active_pokemon[opp_idx]
            if opp and not opp.fainted:
                hp = max(1, getattr(opp, "current_hp", 1))
                total = dmg[opp_idx][0] + dmg[opp_idx][1]
                # If one action alone already KOs, focus is usually wasteful.
                if (dmg[opp_idx][0] >= hp) or (dmg[opp_idx][1] >= hp):
                    focus_penalty += 180.0
                # If even both together don't KO, focus is still less valuable than spreading pressure.
                elif total < hp:
                    focus_penalty += 120.0
                else:
                    # Coordinated KO that needs both: small bonus.
                    ko_bonus += 120.0

        # Spread move: reward when it meaningfully damages both.
        spread_used = (
            (a0["kind"] == "move" and self._is_spread_move(a0["move"]))
            or (a1["kind"] == "move" and self._is_spread_move(a1["move"]))
        )
        if spread_used and len(opponents) == 2:
            # Approximate "pressure on both targets"
            opp0_hp = max(1, getattr(opponents[0][1], "current_hp", 1))
            opp1_hp = max(1, getattr(opponents[1][1], "current_hp", 1))
            pressure = min(1.0, (dmg[0][0] + dmg[0][1]) / opp0_hp) + min(1.0, (dmg[1][0] + dmg[1][1]) / opp1_hp)
            spread_synergy += 80.0 * pressure

        return base + ko_bonus + spread_synergy - focus_penalty

    def _score_action(self, battle, action, opponents):
        if action["kind"] == "switch":
            return 70.0 - self._switch_threat_score(action["switch"], battle)

        if action["kind"] != "move":
            return 0.0

        me = battle.active_pokemon[action["slot"]]
        m = action["move"]

        # If status/support: use status scoring.
        if not (m.base_power and m.base_power > 1):
            return self._score_status_move(m, me, battle)

        if self._is_spread_move(m):
            return self._score_spread_move(m, me, opponents, battle)

        t = action.get("target", 1)
        opp_idx = t - 1
        target = battle.opponent_active_pokemon[opp_idx] if opp_idx in (0, 1) else None
        if not target or target.fainted:
            return 0.0
        return self._score_single_target_move(m, me, target, battle)

    def _get_best_switch_from_list(self, switches, battle):
        """Helper to find the best defensive switch from a specific list."""
        if not switches:
            return None
        opponents = [p for p in battle.opponent_active_pokemon if p and not p.fainted]
        if not opponents:
            return switches[0]

        best_teammate = switches[0]
        best_score = float("inf")
        for pokemon in switches:
            score = self._switch_threat_score(pokemon, battle)
            if score < best_score:
                best_score = score
                best_teammate = pokemon
        return best_teammate

    def _estimate_doubles_dmg(self, move, attacker, defender, battle):
        if not move or not attacker or not defender:
            return 0
        if move.base_power <= 1:
            return 0
        if move.category.name == "PHYSICAL":
            atk = (attacker.stats.get("atk") if attacker.stats else None) or attacker.base_stats.get("atk", 1)
            dfe = (defender.stats.get("def") if defender.stats else None) or defender.base_stats.get("def", 1)
        else:
            atk = (attacker.stats.get("spa") if attacker.stats else None) or attacker.base_stats.get("spa", 1)
            dfe = (defender.stats.get("spd") if defender.stats else None) or defender.base_stats.get("spd", 1)

        multiplier = defender.damage_multiplier(move)
        stab = 1.5 if move.type in attacker.types else 1.0
        dfe = max(1, dfe)
        damage = ((0.5 * move.base_power * (atk / dfe) * stab) + 2) * multiplier

        if move.target in ["allAdjacentFoes", "allAdjacent"]:
            damage *= 0.75

        if battle.weather:
            w = str(battle.weather).upper()
            if "SUN" in w:
                if move.type.name == "FIRE":
                    damage *= 1.5
                if move.type.name == "WATER":
                    damage *= 0.5
            elif "RAIN" in w:
                if move.type.name == "WATER":
                    damage *= 1.5
                if move.type.name == "FIRE":
                    damage *= 0.5
        return damage

    def _score_single_target_move(self, move, attacker, defender, battle):
        dmg = self._estimate_doubles_dmg(move, attacker, defender, battle)
        acc = move.accuracy if isinstance(move.accuracy, float) else 1.0
        m_priority = (move.entry.get("priority", 0) if getattr(move, "entry", None) else 0) or 0

        hp = max(1, getattr(defender, "current_hp", 1))
        ko = 1.0 if dmg >= hp else 0.0

        # Prefer hitting threats (opponents that are super-effective vs us)
        threat = self._opponent_threat_multiplier(defender, attacker)

        score = (dmg * acc) + (1000.0 * ko)
        if m_priority > 0:
            score *= 1.35
        score *= (1.0 + 0.15 * max(0.0, threat - 1.0))
        return score

    def _score_spread_move(self, move, attacker, opponents, battle):
        acc = move.accuracy if isinstance(move.accuracy, float) else 1.0
        m_priority = (move.entry.get("priority", 0) if getattr(move, "entry", None) else 0) or 0

        total = 0.0
        ko_bonus = 0.0
        for _, opp in opponents:
            dmg = self._estimate_doubles_dmg(move, attacker, opp, battle)
            total += dmg
            hp = max(1, getattr(opp, "current_hp", 1))
            if dmg >= hp:
                ko_bonus += 650.0

        score = (total * acc) + ko_bonus
        if m_priority > 0:
            score *= 1.2
        return score

    def _score_status_move(self, move, me, battle):
        mid = (getattr(move, "id", None) or getattr(move, "name", "") or "").lower().replace(" ", "")
        priority = (move.entry.get("priority", 0) if getattr(move, "entry", None) else 0) or 0
        hp_frac = self._safe_hp_fraction(me)
        weakness = self._active_weakness_multiplier(me, battle)

        # Generic base value for status (small, so damage usually wins).
        score = 8.0

        # Protect-like: very valuable when threatened / low HP.
        if self._is_protect_like(move):
            score = 40.0
            if hp_frac <= 0.35:
                score += 120.0
            if weakness >= 4.0:
                score += 120.0
            if weakness >= 2.0:
                score += 40.0
            if getattr(battle, "turn", 0) <= 1:
                score += 10.0
            return score

        # Some common doubles support moves.
        if mid in {"fakeout"}:
            score = 120.0
            if getattr(battle, "turn", 0) <= 1:
                score += 120.0
        elif mid in {"tailwind"}:
            score = 85.0
        elif mid in {"trickroom"}:
            score = 65.0
        elif mid in {"helpinghand"}:
            score = 70.0
        elif mid in {"wideguard", "quickguard"}:
            score = 55.0
        elif mid in {"ragepowder", "followme"}:
            score = 60.0
            if weakness >= 2.0:
                score += 20.0
        elif mid in {"willowisp", "thunderwave", "spore", "sleep powder", "sleeppowder"}:
            score = 55.0
        elif mid in {"haze"}:
            score = 35.0
        elif mid in {"recover", "roost", "moonlight", "slackoff", "softboiled"}:
            score = 35.0 + (60.0 if hp_frac <= 0.4 else 0.0)

        if priority > 0:
            score *= 1.15
        return score

    def _is_spread_move(self, move):
        tgt = getattr(move, "target", None)
        return tgt in {"allAdjacentFoes", "allAdjacent"}

    def _is_protect_like(self, move):
        mid = (getattr(move, "id", None) or getattr(move, "name", "") or "").lower().replace(" ", "")
        return mid in {
            "protect",
            "detect",
            "kingsshield",
            "spikyshield",
            "banefulbunker",
            "silktrap",
            "obstruct",
        }

    def _safe_hp_fraction(self, pokemon):
        try:
            frac = getattr(pokemon, "current_hp_fraction", None)
            if frac is None:
                hp = getattr(pokemon, "current_hp", None)
                max_hp = getattr(pokemon, "max_hp", None)
                if hp is None or max_hp in (None, 0):
                    return 1.0
                return max(0.0, min(1.0, hp / max_hp))
            return float(frac)
        except Exception:
            return 1.0

    def _active_weakness_multiplier(self, me, battle):
        opponents = [p for p in battle.opponent_active_pokemon[:2] if p and not p.fainted]
        if not opponents:
            return 1.0
        worst = 1.0
        for opp in opponents:
            for t in getattr(opp, "types", []) or []:
                try:
                    worst = max(worst, me.damage_multiplier(t))
                except Exception:
                    continue
        return worst

    def _opponent_threat_multiplier(self, opponent, me):
        # How threatening opponent is to me based on its STAB types.
        worst = 1.0
        for t in getattr(opponent, "types", []) or []:
            try:
                worst = max(worst, me.damage_multiplier(t))
            except Exception:
                continue
        return worst

    def _switch_threat_score(self, pokemon, battle):
        opponents = [p for p in battle.opponent_active_pokemon[:2] if p and not p.fainted]
        if not opponents:
            return 0.0

        worst = 1.0
        for opp in opponents:
            for t in getattr(opp, "types", []) or []:
                try:
                    worst = max(worst, pokemon.damage_multiplier(t))
                except Exception:
                    continue

        # Penalize very low HP switches.
        hp_pen = 0.0
        hp_frac = self._safe_hp_fraction(pokemon)
        if hp_frac <= 0.25:
            hp_pen = 2.0
        elif hp_frac <= 0.5:
            hp_pen = 0.75

        return worst + hp_pen

    def _same_switch(self, a, b):
        if a is None or b is None:
            return False
        # Prefer stable identifiers when available.
        ida = getattr(a, "species", None) or getattr(a, "name", None) or str(a)
        idb = getattr(b, "species", None) or getattr(b, "name", None) or str(b)
        return ida == idb

    def _dedupe_actions(self, actions):
        seen = set()
        out = []
        for a in actions:
            if a["kind"] == "switch":
                key = ("sw", getattr(a["switch"], "species", None) or getattr(a["switch"], "name", None) or str(a["switch"]))
            else:
                m = a["move"]
                key = ("mv", getattr(m, "id", None) or getattr(m, "name", None) or str(m), a.get("target", None))
            if key in seen:
                continue
            seen.add(key)
            out.append(a)
        return out


async def main():
    """
    Run a large self-play experiment for the v2 doubles heuristic.

    Produces a CSV with:
    - battle outcome and length,
    - team compositions,
    - fainted counts,
    - moves used by v2 in each battle.
    """
    TOTAL_GAMES = 10_000
    BATCH_SIZE = 500
    CONCURRENT_BATTLES = 20

    run_id = str(uuid.uuid4())[:4]
    data_dir = "data"
    csv_path = os.path.join(data_dir, f"tfm_doubles_v2_{run_id}.csv")
    os.makedirs(data_dir, exist_ok=True)

    config = ServerConfiguration("ws://127.0.0.1:8000/showdown/websocket", None)

    player = TFMExpertDoubles(
        battle_format="gen9randomdoublesbattle",
        server_configuration=config,
        max_concurrent_battles=CONCURRENT_BATTLES,
        account_configuration=AccountConfiguration(f"V2_A_{run_id}", None),
    )

    opponent = TFMExpertDoubles(
        battle_format="gen9randomdoublesbattle",
        server_configuration=config,
        max_concurrent_battles=CONCURRENT_BATTLES,
        account_configuration=AccountConfiguration(f"V2_B_{run_id}", None),
    )

    print(f"🚀 Iniciando Simulación Experta v2 (Doubles): {TOTAL_GAMES} partidas")

    with tqdm(total=TOTAL_GAMES, desc="Simulando Batallas v2", unit="game") as pbar:
        batches = TOTAL_GAMES // BATCH_SIZE
        for _ in range(batches):
            await player.battle_against(opponent, n_battles=BATCH_SIZE)
            extracted_data = []
            for bid, b in player.battles.items():
                if not b.finished:
                    continue

                winner_name = (
                    player.username if b.won else (opponent.username if b.lost else "DRAW")
                )

                team_us = "|".join(sorted({str(mon.species) for mon in b.team.values()}))
                team_opp = "|".join(
                    sorted({str(mon.species) for mon in b.opponent_team.values()})
                )

                fainted_us = sum(mon.fainted for mon in b.team.values())
                fainted_opp = sum(mon.fainted for mon in b.opponent_team.values())

                moves_used = "|".join(
                    sorted(player._used_moves_by_battle.get(bid, set()))
                )

                extracted_data.append(
                    {
                        "battle_id": bid,
                        "winner": winner_name,
                        "turns": b.turn,
                        "won": 1 if b.won else 0,
                        "team_us": team_us,
                        "team_opp": team_opp,
                        "fainted_us": fainted_us,
                        "fainted_opp": fainted_opp,
                        "moves_used": moves_used,
                    }
                )

            if extracted_data:
                batch_df = pd.DataFrame(extracted_data)
                batch_df.to_csv(
                    csv_path,
                    mode="a",
                    header=not os.path.exists(csv_path),
                    index=False,
                )

            player.reset_battles()
            opponent.reset_battles()
            pbar.update(BATCH_SIZE)


if __name__ == "__main__":
    asyncio.run(main())