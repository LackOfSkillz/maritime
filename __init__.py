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
from .cmdsets import HelmCmdSet
from .commands import CmdAllStop, CmdHelm, CmdPosition, CmdSpeed
from .formatting import NAUTICAL, RAW, format_position
from .messaging import (
    AT_SPEED,
    COMING_ROUND,
    HULL_HOLED,
    RUN_AGROUND,
    SHOALING,
    STEADY,
    WAY_OFF,
    VesselNarrator,
    compass_point,
    spell_bearing,
)
from .grounding import (
    AGROUND,
    HOLED,
    TOUCHED,
    GroundingResult,
    check_grounding,
    is_shoaling,
    keel_clearance,
    refloats_on_tide,
)
from .motion import HelmOrders, MotionLimits, MotionState, advance
from .position import (
    DEFAULT_REGION,
    WorldPosition,
    bearing_difference,
    normalize_bearing,
)
from .resolver import (
    NoWorldPosition,
    get_world_position,
    has_world_position,
    resolve_chain,
)
from .vessel import (
    BELOW_WATERLINE,
    EXPOSURES,
    INTERIOR,
    MAIN_DECK,
    OPEN,
    SEMI_EXPOSED,
    DeckLevel,
    DeckPlan,
    VesselCapacity,
    VesselTemplate,
)
from .scheduler import FairQueue
from .sailing import (
    FULL,
    FURLED,
    REEFED,
    SAIL_PLANS,
    STORM,
    WORKING,
    PolarCurve,
    SailPlan,
    WindVector,
    achievable_speed,
    leeway_angle,
    relative_wind_angle,
    sail_plan,
)
from .scripts import MaritimeDriver
from .simulation import (
    ACTIVE,
    DORMANT,
    STRATEGIC,
    TACTICAL,
    TIERS,
    TIER_INTERVALS,
    MaritimeSimulationService,
)
from .spatial import ContactIndex, ProximityIndex, SpatialIndex
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
    "get_world_position",
    "has_world_position",
    "resolve_chain",
    "NoWorldPosition",
    "SpatialIndex",
    "ContactIndex",
    "ProximityIndex",
    # simulation
    "MaritimeDriver",
    "MaritimeSimulationService",
    "FairQueue",
    "TIERS",
    "TIER_INTERVALS",
    "DORMANT",
    "STRATEGIC",
    "ACTIVE",
    "TACTICAL",
    # vessels
    "VesselTemplate",
    "VesselCapacity",
    "DeckPlan",
    "DeckLevel",
    "MAIN_DECK",
    "EXPOSURES",
    "OPEN",
    "SEMI_EXPOSED",
    "INTERIOR",
    "BELOW_WATERLINE",
    "normalize_bearing",
    "bearing_difference",
    # commands
    "HelmCmdSet",
    "CmdHelm",
    "CmdSpeed",
    "CmdAllStop",
    "CmdPosition",
    # presentation
    "format_position",
    "NAUTICAL",
    "RAW",
    "VesselNarrator",
    "compass_point",
    "spell_bearing",
    "COMING_ROUND",
    "STEADY",
    "AT_SPEED",
    "WAY_OFF",
    "RUN_AGROUND",
    "HULL_HOLED",
    "SHOALING",
    # sailing
    "WindVector",
    "PolarCurve",
    "SailPlan",
    "SAIL_PLANS",
    "FURLED",
    "STORM",
    "REEFED",
    "WORKING",
    "FULL",
    "sail_plan",
    "relative_wind_angle",
    "achievable_speed",
    "leeway_angle",
    # grounding
    "keel_clearance",
    "check_grounding",
    "is_shoaling",
    "refloats_on_tide",
    "GroundingResult",
    "TOUCHED",
    "AGROUND",
    "HOLED",
    # motion
    "MotionState",
    "MotionLimits",
    "HelmOrders",
    "advance",
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
