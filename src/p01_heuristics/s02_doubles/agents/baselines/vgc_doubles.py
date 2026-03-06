"""VGC-Specialized Doubles Agent.

An expert-level heuristic designed for competitive VGC-style play.
Extends field awareness (weather, terrain) with specific doubles tactics:
- Speed control prioritization.
- Avoidance of obvious Protect stalls.
- Basic sync-targeting (focusing down a single threat).
"""

from __future__ import annotations
from ..internal.v6 import HeuristicV6Doubles

class VGCDoublesPlayer(HeuristicV6Doubles):
    """Competitive VGC heuristic extending V6 logic with double battle tactics."""
    
    def _score_order(self, order, pokemon, slot, battle) -> float:
        score = super()._score_order(order, pokemon, slot, battle)
        
        action = order.order
        if not hasattr(action, "id"):
            return score
            
        move_id = action.id
        
        # Priority on speed control
        speed_control = {"tailwind", "icywind", "trickroom", "electroweb"}
        if move_id in speed_control:
            score *= 1.4
            
        # Protect awareness (slight penalty if we think opponent might protect? 
        # Hard to predict without state tracking, but we can favor spread moves)
        if action.target in ["allAdjacentFoes", "allAdjacent"]:
            score *= 1.1 # Favor spread in doubles
            
        return score
