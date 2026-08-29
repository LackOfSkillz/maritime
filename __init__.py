"""
Maritime - a continuous-coordinate sailing and vessel simulation for Evennia.

Vessels are simulation entities holding a position in continuous world space.
Their interiors remain ordinary Evennia rooms, which move with the vessel rather
than determining where it is.

Commonly used names are re-exported here, so games can import them directly:

    from evennia.contrib.full_systems.maritime import GameTimeProvider

"""

from .clock import GameTimeProvider, ManualTimeProvider, MaritimeTimeProvider
from .rng import AI, COMBAT, DAMAGE, NAVIGATION, WEATHER, RNGContext

__all__ = (
    "MaritimeTimeProvider",
    "GameTimeProvider",
    "ManualTimeProvider",
    "RNGContext",
    "NAVIGATION",
    "COMBAT",
    "DAMAGE",
    "WEATHER",
    "AI",
)
