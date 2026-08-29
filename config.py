"""
Settings resolution for the maritime contrib.

A game overrides maritime behaviour from its own `settings.py`, never by editing
contrib source. Settings are individual `MARITIME_`-prefixed names, matching how every
other Evennia contrib reads configuration:

    ```python
    # in mygame/server/conf/settings.py
    MARITIME_TIME_PROVIDER = "world.maritime_integration.MyTimeProvider"
    MARITIME_RNG_SEED = 729922
    ```

Only settings backing something that exists are defined here. Configuration for systems
not yet built would be a promise this contrib cannot keep.

Swappable pieces are given as dotted paths and resolved through Evennia's own
`class_from_module`, so a game can substitute an implementation without subclassing
anything of ours.

Defaults are derived from `__package__` rather than written out in full. A hardcoded
`evennia.contrib.full_systems.maritime...` default would resolve only when the contrib
sits in the Evennia tree, and would break the moment someone dropped it into their game
under a different path.

"""

from django.conf import settings

from evennia.utils.utils import class_from_module

from .bathymetry import FlatSeaMapProvider, MaritimeMapProvider
from .messaging import VesselNarrator
from .clock import MaritimeTimeProvider
from .rng import RNGContext

# Every setting this contrib reads carries this prefix, so a game's settings file shows
# at a glance which knobs belong to maritime.
SETTING_PREFIX = "MARITIME_"

# Derived, never hardcoded - see the module docstring.
DEFAULT_TIME_PROVIDER = f"{__package__}.clock.GameTimeProvider"
DEFAULT_MAP_PROVIDER = f"{__package__}.bathymetry.FlatSeaMapProvider"
DEFAULT_NARRATOR = f"{__package__}.messaging.VesselNarrator"


def get_setting(name, default=None):
    """
    Read a maritime setting from the game's Django settings.

    Args:
        name (str): Setting name without the `MARITIME_` prefix, e.g.
            `"TIME_PROVIDER"`.
        default (any, optional): Returned when the game has not set it.

    Returns:
        value (any): The configured value, or `default`.

    """
    return getattr(settings, f"{SETTING_PREFIX}{name}", default)


def load_class(path, expected=None):
    """
    Resolve a dotted path to a class.

    Args:
        path (str): Full Python path, e.g. `"world.maritime.MyProvider"`.
        expected (type, optional): Base class the result must inherit from.

    Returns:
        cls (type): The resolved class, uninstantiated.

    Raises:
        ImportError: If the path cannot be imported. Evennia's loader raises this
            with the paths it tried, which is what a misconfigured game needs to
            see.
        TypeError: If `expected` is given and the class does not subclass it.

    Notes:
        The type check exists so a misconfiguration fails at load with a message
        naming both the class and what it should have been, rather than surfacing
        much later as a missing attribute deep inside the simulation.

    """
    cls = class_from_module(path)
    if expected is not None and not (isinstance(cls, type) and issubclass(cls, expected)):
        raise TypeError(
            f"{path} is not a {expected.__name__}. Check the "
            f"{SETTING_PREFIX}-prefixed setting that points at it."
        )
    return cls


def time_provider():
    """
    Build the configured time provider.

    Returns:
        provider (MaritimeTimeProvider): A new provider instance. Defaults to one
            reading the host game's own clock, so maritime inherits whatever
            `TIME_FACTOR` the game runs at.

    Notes:
        Returns a new instance per call rather than a shared one. Providers hold no
        state worth sharing, and a cached instance would outlive a settings change
        during development, which is the sort of staleness that wastes an afternoon.

    """
    provider_class = load_class(
        get_setting("TIME_PROVIDER", DEFAULT_TIME_PROVIDER),
        expected=MaritimeTimeProvider,
    )
    return provider_class()


def rng_seed():
    """
    The configured master seed for random streams.

    Returns:
        seed (int or None): The seed a game pinned via `MARITIME_RNG_SEED`, or
            `None` to let each run generate its own.

    Notes:
        Pinning a seed makes a whole server run reproducible, which is useful for
        a reproduction case and unhelpful in live play - the same storm every
        restart. Left unset by default for that reason.

    """
    seed = get_setting("RNG_SEED")
    return None if seed is None else int(seed)


def rng_context():
    """
    Build an RNG context from the configured seed.

    Returns:
        context (RNGContext): A new context. Unseeded unless the game pinned
            `MARITIME_RNG_SEED`, in which case every context built here replays
            the same streams.

    """
    return RNGContext(seed=rng_seed())


def map_provider():
    """
    Build the configured map provider.

    Returns:
        provider (MaritimeMapProvider): The world's terrain. Defaults to a
            featureless sea deep enough that nothing grounds, so a game gets
            vessels sailing before it needs bathymetry.

    Raises:
        TypeError: If the configured class is not a map provider.

    """
    path = get_setting("MAP_PROVIDER")
    if not path:
        return FlatSeaMapProvider(depth=float(get_setting("DEFAULT_DEPTH", 200.0)))
    return load_class(path, expected=MaritimeMapProvider)()


def narrator_class():
    """
    The class that speaks for vessels.

    Returns:
        cls (type): A `VesselNarrator` subclass, uninstantiated.

    Raises:
        TypeError: If the configured class is not a narrator.

    Notes:
        Returned uninstantiated because a narrator is bound to one vessel. This
        is the seam a game uses to replace the prose of the whole system without
        touching the simulation that produces it.

    """
    return load_class(get_setting("NARRATOR", DEFAULT_NARRATOR), expected=VesselNarrator)
