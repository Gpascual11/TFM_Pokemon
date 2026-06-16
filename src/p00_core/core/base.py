
"""Abstract base class for all 1-vs-1 heuristic strategies.

Implements the Template Method pattern: ``choose_move`` orchestrates the
decision pipeline (pre-hook → select action → fallback), while subclasses
only need to implement ``_select_action``.
"""

from __future__ import annotations

import abc
import datetime
import json
import logging
import os
from pathlib import Path

from poke_env.player import Player

logger = logging.getLogger(__name__)


class BaseHeuristic1v1(Player, abc.ABC):
    """Abstract Foundation for Rule-Based Singles Strategies.

    This class implements the Template Method pattern for move selection.
    Execution Pipeline:
    1. _pre_move_hook(): Check for early returns (e.g. priority KOs).
    2. _select_action(): Main decision logic implementation.
    3. choose_random_move(): Fallback if no specific order is produced.

    It also provides shared utilities for move tracking and basic error handling
    to prevent battle deadlocks.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._used_moves_by_battle: dict[str, set[str]] = {}
        self._fallback_moves_by_battle: dict[str, int] = {}
        self._error_moves_by_battle: dict[str, int] = {}
        self._total_decisions_by_battle: dict[str, int] = {}
        # Strategy tracking (incremented by V7/V8, zero for simpler agents)
        self._hazard_sets_by_battle: dict[str, int] = {}
        self._hazard_removals_by_battle: dict[str, int] = {}
        self._setup_uses_by_battle: dict[str, int] = {}
        self._ko_checks_by_battle: dict[str, int] = {}
        self._matchup_switches_by_battle: dict[str, int] = {}

        # Per-turn decision logging (opt-in via TFM_DECISION_LOG_DIR env var).
        # Off by default so benchmarks stay fast; the online runner sets it so
        # every turn's options + chosen action are recorded for later analysis.
        self._decision_log_dir = os.environ.get("TFM_DECISION_LOG_DIR")

    def reset_battles(self) -> None:
        """Clear both the poke-env battle history and our custom move tracking."""
        super().reset_battles()
        self._used_moves_by_battle.clear()
        self._fallback_moves_by_battle.clear()
        self._error_moves_by_battle.clear()
        self._total_decisions_by_battle.clear()
        self._hazard_sets_by_battle.clear()
        self._hazard_removals_by_battle.clear()
        self._setup_uses_by_battle.clear()
        self._ko_checks_by_battle.clear()
        self._matchup_switches_by_battle.clear()

    def choose_move(self, battle):
        """Orchestrate the three-phase decision pipeline.

        1. ``_pre_move_hook`` — optional early return (e.g. KO moves).
        2. ``_select_action`` — main heuristic logic.
        3. Fallback to ``choose_random_move`` when nothing was selected.

        Wrapped in a try-except to prevent deadlocks on logic errors.
        """
        btag = battle.battle_tag
        self._total_decisions_by_battle[btag] = self._total_decisions_by_battle.get(btag, 0) + 1

        order = None
        source = "fallback"
        try:
            order = self._pre_move_hook(battle)
            if order is not None:
                source = "pre_move_hook"
            else:
                order = self._select_action(battle)
                if order is not None:
                    source = "select_action"
        except Exception as e:
            logger.error(f"Error in {self.__class__.__name__} logic: {e}", exc_info=True)
            self._error_moves_by_battle[btag] = self._error_moves_by_battle.get(btag, 0) + 1
            order = self.choose_random_move(battle)
            source = "error"

        if order is None:
            # No specific order was selected (graceful fallback).
            self._fallback_moves_by_battle[btag] = self._fallback_moves_by_battle.get(btag, 0) + 1
            order = self.choose_random_move(battle)
            source = "fallback"

        if self._decision_log_dir:
            self._log_decision(battle, order, source)
        return order

    @staticmethod
    def _describe_order(order) -> dict:
        """Summarise a BattleOrder into a plain dict (move id or switch target)."""
        info: dict = {"type": "unknown", "id": None, "terastallize": False}
        if order is None:
            return info
        chosen = getattr(order, "order", None)
        info["terastallize"] = bool(getattr(order, "terastallize", False))
        # A move order exposes `.id`; a switch order's `chosen` is a Pokemon.
        if hasattr(chosen, "base_power"):  # Move
            info["type"] = "move"
            info["id"] = getattr(chosen, "id", None)
        elif hasattr(chosen, "species"):  # Pokemon (switch)
            info["type"] = "switch"
            info["id"] = chosen.species.lower()
        return info

    def _log_decision(self, battle, order, source: str) -> None:
        """Append one JSONL record capturing the turn's options and chosen action.

        Written to ``<TFM_DECISION_LOG_DIR>/<battle_id>.jsonl`` (one file per
        battle, appended per turn). Best-effort: never let logging break a game.
        """
        try:
            btag = battle.battle_tag
            me = battle.active_pokemon
            opp = battle.opponent_active_pokemon

            record = {
                "battle_id": btag,
                "turn": battle.turn,
                "ts": datetime.datetime.now().isoformat(timespec="seconds"),
                "source": source,
                "active": me.species.lower() if me else None,
                "active_hp": round(me.current_hp_fraction, 3) if me else None,
                "active_status": (me.status.name if me and me.status else None),
                "active_boosts": ({k: v for k, v in me.boosts.items() if v} if me else {}),
                "opp_active": opp.species.lower() if opp else None,
                "opp_hp": round(opp.current_hp_fraction, 3) if opp else None,
                "opp_status": (opp.status.name if opp and opp.status else None),
                "available_moves": [m.id for m in (battle.available_moves or [])],
                "available_switches": [s.species.lower() for s in (battle.available_switches or [])],
                "force_switch": bool(battle.force_switch),
                "can_tera": bool(getattr(battle, "can_tera", False)),
                "weather": (next(iter(battle.weather), None).name if battle.weather else None),
                "chosen": self._describe_order(order),
            }

            log_dir = Path(self._decision_log_dir)
            log_dir.mkdir(parents=True, exist_ok=True)
            # Sanitise battle tag for use as a filename.
            safe = btag.replace("/", "_").replace("\\", "_").lstrip("-") or "battle"
            with open(log_dir / f"{safe}.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:  # pragma: no cover - logging must never crash play
            logger.debug(f"decision log skipped: {e}")

    def _pre_move_hook(self, battle):
        """Optional hook executed before the main heuristic.

        Return a ``BattleOrder`` to short-circuit, or ``None`` to
        continue to ``_select_action``.  Default: no-op.
        """
        return None

    @abc.abstractmethod
    def _select_action(self, battle):
        """Return a ``BattleOrder`` or ``None`` (triggers random fallback).

        Each heuristic version implements its specific decision logic here.
        """

    @property
    def tracks_moves(self) -> bool:
        """Whether this heuristic records which moves it uses per battle."""
        return False

    def _record_used_move(self, battle_tag: str, move_id: str) -> None:
        """Register *move_id* as used during *battle_tag*."""
        self._used_moves_by_battle.setdefault(battle_tag, set()).add(move_id)

    def get_used_moves(self, battle_tag: str) -> set[str]:
        """Return the set of move ids used in *battle_tag*."""
        return self._used_moves_by_battle.get(battle_tag, set())
