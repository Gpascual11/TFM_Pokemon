"""Abstract base class for all 1-vs-1 heuristic strategies.

Implements the Template Method pattern: ``choose_move`` orchestrates the
decision pipeline (pre-hook → select action → fallback), while subclasses
only need to implement ``_select_action``.
"""

from __future__ import annotations

import abc
from typing import Dict, Set

from poke_env.player import Player


class BaseHeuristic1v1(Player, abc.ABC):
    """Common base for every singles heuristic version.

    Subclasses must override :meth:`_select_action` to provide their
    decision logic.  Optionally, they can override :meth:`_pre_move_hook`
    for early-return behaviour (e.g. guaranteed KO detection in V5).
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._used_moves_by_battle: Dict[str, Set[str]] = {}

    def choose_move(self, battle):
        """Orchestrate the three-phase decision pipeline.

        1. ``_pre_move_hook`` — optional early return (e.g. KO moves).
        2. ``_select_action`` — main heuristic logic.
        3. Fallback to ``choose_random_move`` when nothing was selected.
        """
        early = self._pre_move_hook(battle)
        if early is not None:
            return early

        order = self._select_action(battle)
        if order is not None:
            return order

        return self.choose_random_move(battle)

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

    def get_used_moves(self, battle_tag: str) -> Set[str]:
        """Return the set of move ids used in *battle_tag*."""
        return self._used_moves_by_battle.get(battle_tag, set())
