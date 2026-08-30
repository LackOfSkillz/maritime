"""
Weather: the wind, what you can see through, and the state of the sea.

Until now the wind was one setting and the visibility another, read separately wherever
somebody needed them. That works while both are constants and stops working the moment they
are not, because weather is not a set of independent numbers - a gale brings a high sea and
takes your visibility with it, and a system that lets those drift apart will cheerfully
produce a flat calm you cannot see across.

So they arrive together, from one provider, sampled at a place and a moment:

    wind          where it blows from, and how hard
    visibility    how far the air lets you see
    sea state     what the water is doing, which the wind mostly decides

**Sea state follows the wind, but not instantly.** Waves need fetch and time to build, and
they keep running after the wind drops - which is why a provider supplies the sea rather
than having it derived on the spot from the current gust. `sea_state_for` gives the sea a
steady wind would eventually raise, and that is the sensible default; a game modelling
swell, fetch or a dying gale overrides it and nothing above notices.

**One clock, as everywhere else.** Weather is sampled at a game time, so a front that
arrives at dawn arrives at dawn for every vessel, and a scheduled ferry meets the same gale
her captain was warned about.

"""

from dataclasses import dataclass

from .sailing import WindVector, beaufort_force

# The sea, by the WMO scale, from a mirror to something no one wants to see. The
# names are what a mariner would say; the numbers behind them are significant
# wave heights in metres.
CALM = "calm"
RIPPLED = "rippled"
SMOOTH = "smooth"
SLIGHT = "slight"
MODERATE = "moderate"
ROUGH = "rough"
VERY_ROUGH = "very rough"
HIGH = "high"
VERY_HIGH = "very high"
PHENOMENAL = "phenomenal"

SEA_STATES = (
    CALM,
    RIPPLED,
    SMOOTH,
    SLIGHT,
    MODERATE,
    ROUGH,
    VERY_ROUGH,
    HIGH,
    VERY_HIGH,
    PHENOMENAL,
)

# Significant wave height at the top of each state, in metres. Phenomenal has no
# top, which is rather the point of the name.
WAVE_HEIGHTS = (0.0, 0.1, 0.5, 1.25, 2.5, 4.0, 6.0, 9.0, 14.0)

# The sea a steady wind of each Beaufort force will eventually raise, given room
# and time. Indexed by force, so force 0 is a mirror and force 12 is phenomenal.
SEA_FOR_FORCE = (0, 1, 2, 3, 3, 4, 5, 5, 6, 7, 8, 8, 9)

# How much of a vessel's speed a heavy sea takes, by sea state. A hull punching
# into steep water loses way; the numbers are gentle because this is drag on a
# ship, not a wall, and anything harsher would make bad weather unplayable rather
# than dangerous.
SEA_DRAG = (0.0, 0.0, 0.0, 0.02, 0.05, 0.10, 0.18, 0.28, 0.40, 0.55)


@dataclass(frozen=True)
class Weather:
    """
    What the sky and the sea are doing at one place and moment.

    Attributes:
        wind (WindVector): Where it blows from, and how hard.
        visibility (float): How far the air lets you see, in metres.
        sea_state (str): One of `SEA_STATES`.

    Notes:
        One object rather than three lookups, because these are not independent.
        A gale with unlimited visibility and a glassy sea is not weather, it is
        three settings that were never introduced to each other.

    """

    wind: object = None
    visibility: float = 0.0
    sea_state: str = CALM

    @property
    def wave_height(self):
        """
        Returns:
            height (float): Significant wave height in metres - the top of this
                state's band, or the bottom of `PHENOMENAL`, which has no top.

        """
        index = SEA_STATES.index(self.sea_state)
        if index >= len(WAVE_HEIGHTS):
            return WAVE_HEIGHTS[-1]
        return WAVE_HEIGHTS[index]


def sea_state_for(wind_speed):
    """
    The sea a steady wind would eventually raise.

    Args:
        wind_speed (float): Wind speed in metres per second.

    Returns:
        state (str): One of `SEA_STATES`.

    Notes:
        Eventually, and given room. Waves need fetch and time to build and go on
        running after the wind drops, so this is the sea a wind *tends* towards
        rather than the sea that is there. A game wanting a dying gale's leftover
        swell, or a sheltered bay that never builds one, supplies its own
        provider and this is not consulted.

    """
    return SEA_STATES[SEA_FOR_FORCE[beaufort_force(wind_speed)]]


def sea_drag(sea_state):
    """
    How much of her speed a sea takes.

    Args:
        sea_state (str): One of `SEA_STATES`.

    Returns:
        fraction (float): How much speed is lost, from 0 to 1.

    Notes:
        Deliberately gentle. A hull punching into steep water loses way, but a
        penalty harsh enough to feel dramatic makes heavy weather unplayable
        rather than dangerous - and the danger is supposed to come from the
        grounding, the flooding and the lee shore, not from an arithmetic wall.

    """
    if sea_state not in SEA_STATES:
        return 0.0
    return SEA_DRAG[SEA_STATES.index(sea_state)]


class MaritimeWeatherProvider:
    """
    What the sky is doing, wherever and whenever you ask.

    Notes:
        The seam the whole system reads weather through. Wind, visibility and the
        sea arrive together because they are not independent, and they arrive
        sampled at a time because weather moves - a front that reaches the coast
        at dawn should reach it at dawn for everybody.

    """

    def weather_at(self, position, game_time):
        """
        The weather at a place and a moment.

        Args:
            position (WorldPosition): Where to sample.
            game_time (float): Game time in seconds.

        Returns:
            weather (Weather): Wind, visibility and sea state.

        """
        raise NotImplementedError("A weather provider must say what the sky is doing.")


class FlatWeatherProvider(MaritimeWeatherProvider):
    """
    One weather everywhere, unchanging.

    Notes:
        The counterpart of the flat sea and the steady current: enough to make
        the mechanism real, and obviously not a forecast. Its sea state follows
        its wind by default, so a game that sets a gale gets a gale's sea without
        having to know this module exists.

    """

    def __init__(self, wind=None, visibility=0.0, sea_state=None):
        """
        Args:
            wind (WindVector, optional): The wind everywhere.
            visibility (float, optional): How far you can see, in metres.
            sea_state (str, optional): The sea. Defaults to whatever the wind
                would raise.

        """
        self.wind = wind or WindVector()
        self.visibility = visibility
        self.sea_state = sea_state or sea_state_for(self.wind.speed)

    def weather_at(self, position, game_time):
        """
        Args:
            position (WorldPosition): Ignored.
            game_time (float): Ignored.

        Returns:
            weather (Weather): The one weather.

        """
        return Weather(wind=self.wind, visibility=self.visibility, sea_state=self.sea_state)
