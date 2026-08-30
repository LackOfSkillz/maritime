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
from .currents import CurrentVector, FlatCurrentProvider, MaritimeCurrentProvider
from .messaging import VesselNarrator
from .routes import NavigationNetwork
from .sailing import WindVector
from .weather import FlatWeatherProvider, MaritimeWeatherProvider
from .observation import DEFAULT_VISIBILITY
from .clock import MaritimeTimeProvider
from .rng import RNGContext

# Every setting this contrib reads carries this prefix, so a game's settings file shows
# at a glance which knobs belong to maritime.
SETTING_PREFIX = "MARITIME_"

# Derived, never hardcoded - see the module docstring.
DEFAULT_TIME_PROVIDER = f"{__package__}.clock.GameTimeProvider"
DEFAULT_MAP_PROVIDER = f"{__package__}.bathymetry.FlatSeaMapProvider"
DEFAULT_NARRATOR = f"{__package__}.messaging.VesselNarrator"
DEFAULT_CURRENT_PROVIDER = f"{__package__}.currents.FlatCurrentProvider"


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


def visibility():
    """
    How far the air lets you see, in metres.

    Returns:
        visibility (float): Metres. Defaults to a clear day.

    Notes:
        One global figure, exactly as the wind is one global vector. A weather
        provider replaces both later and no call site changes, which is the only
        reason a constant is acceptable here in the meantime.

    """
    return float(get_setting("VISIBILITY", DEFAULT_VISIBILITY))


def current_provider():
    """
    Build the configured current provider.

    Returns:
        provider (MaritimeCurrentProvider): Where the water is going.

    Raises:
        TypeError: If the configured class is not a current provider.

    Notes:
        With no `MARITIME_CURRENT_PROVIDER` set, returns a flat provider carrying
        `MARITIME_CURRENT_SET` and `MARITIME_CURRENT_DRIFT` - which default to
        slack water, so a game that has never heard of currents is unaffected.
        The two-setting shortcut mirrors the wind exactly, because a game wanting
        one steady stream should not have to write a class to get it.

    """
    path = get_setting("CURRENT_PROVIDER")
    if not path:
        return FlatCurrentProvider(
            CurrentVector(
                set=float(get_setting("CURRENT_SET", 0.0)),
                drift=float(get_setting("CURRENT_DRIFT", 0.0)),
            )
        )
    return load_class(path, expected=MaritimeCurrentProvider)()


def navigation_network():
    """
    Build the game's network of navigational marks.

    Returns:
        network (NavigationNetwork): The marks and the safe water between them.
            Empty if the game has laid none, which simply means no route can be
            plotted rather than that plotting is broken.

    Raises:
        TypeError: If the configured class is not a navigation network.

    Notes:
        Which waters are passable is a game's statement about its own world, so
        the network is authored and loaded rather than derived from the seabed.

    """
    path = get_setting("NAVIGATION_NETWORK")
    if not path:
        return NavigationNetwork()
    return load_class(path, expected=NavigationNetwork)()


def weather_provider():
    """
    Build the configured weather provider.

    Returns:
        provider (MaritimeWeatherProvider): What the sky is doing.

    Raises:
        TypeError: If the configured class is not a weather provider.

    Notes:
        With no `MARITIME_WEATHER_PROVIDER` set, returns a flat provider built
        from the individual wind and visibility settings a game may already have.
        Those settings were the whole of weather before this existed, and a game
        that set them should not have to learn about providers to keep the
        weather it already had.

    """
    path = get_setting("WEATHER_PROVIDER")
    if path:
        return load_class(path, expected=MaritimeWeatherProvider)()
    return FlatWeatherProvider(
        wind=WindVector(
            bearing=float(get_setting("WIND_BEARING", 0.0)),
            speed=float(get_setting("WIND_SPEED", 0.0)),
        ),
        visibility=float(get_setting("VISIBILITY", DEFAULT_VISIBILITY)),
        sea_state=get_setting("SEA_STATE") or None,
    )
