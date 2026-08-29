"""
Maritime - a continuous-coordinate sailing and vessel simulation for Evennia.

Vessels are simulation entities holding a position in continuous world space.
Their interiors remain ordinary Evennia rooms, which move with the vessel rather
than determining where it is.

Commonly used names are re-exported here, so games can import them directly:

    from evennia.contrib.full_systems.maritime import GameTimeProvider

"""

from . import config  # noqa: F401
from .bathymetry import (
    DATUM,
    FlatSeaMapProvider,
    FlatTideProvider,
    MaritimeMapProvider,
    MaritimeTideProvider,
)
from .clock import GameTimeProvider, ManualTimeProvider, MaritimeTimeProvider
from .events import Delivery, Event, EventBus
from .position import DEFAULT_REGION, WorldPosition, normalize_bearing
from .results import (
    INVALID_TARGET,
    NOT_PERMITTED,
    PRECONDITION_FAILED,
    UNSUPPORTED,
    Result,
)
from .rng import AI, COMBAT, DAMAGE, NAVIGATION, WEATHER, RNGContext

__all__ = (
    # configuration
    "config",
    # time
    "MaritimeTimeProvider",
    "GameTimeProvider",
    "ManualTimeProvider",
    # randomness
    "RNGContext",
    "NAVIGATION",
    "COMBAT",
    "DAMAGE",
    "WEATHER",
    "AI",
    # space
    "WorldPosition",
    "DATUM",
    "MaritimeMapProvider",
    "FlatSeaMapProvider",
    "MaritimeTideProvider",
    "FlatTideProvider",
    "normalize_bearing",
    "DEFAULT_REGION",
    # events
    "Event",
    "EventBus",
    "Delivery",
    # results
    "Result",
    "NOT_PERMITTED",
    "PRECONDITION_FAILED",
    "INVALID_TARGET",
    "UNSUPPORTED",
)
