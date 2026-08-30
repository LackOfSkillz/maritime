"""
Turning positions into something a person would read.

The domain holds metres on three axes. Nobody aboard a ship talks that way, so this is
where coordinates become a position a navigator would write in the log.

Kept separate from `WorldPosition` deliberately. A fantasy game may reckon in leagues from
a landmark and a sci-fi one will not use latitude at all, so the presentation belongs to
the game rather than to the coordinate type - the same reason speeds become knots in the
command layer rather than in the physics.

The conversion is unusually clean, because a nautical mile *is* one minute of latitude by
definition: 1852 metres, exactly. So northing divided by 1852 gives minutes of latitude
with no fudge factor anywhere.

Longitude uses the same scale rather than narrowing towards the poles. This world is a
plane, not a globe, and applying a cosine correction would make the displayed longitude
disagree with the distance a vessel actually sailed - a worse lie than the simplification
it was meant to fix.

"""

from . import config
from .position import (
    METRES_PER_CABLE,
    METRES_PER_FATHOM,
    METRES_PER_LEAGUE,
    METRES_PER_NAUTICAL_MILE,
    WorldPosition,
)
from .resolver import NoWorldPosition

# Small numbers of cables, said rather than counted.
_CABLE_NAMES = ("", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine")

# One minute of latitude, by definition - and therefore one nautical mile. The
# whole conversion rests on this, so it is defined once, in the spatial layer,
# and named here for what it means when you are reading a position rather than a
# distance.
METRES_PER_MINUTE = METRES_PER_NAUTICAL_MILE

# One knot is one nautical mile in an hour. Defined here, once, because three
# separate modules had each worked it out for themselves - which is fine until one
# of them is corrected and the others are not.
METRES_PER_SECOND_PER_KNOT = METRES_PER_NAUTICAL_MILE / 3600.0
MINUTES_PER_DEGREE = 60.0

# Presentation styles for position. `nautical` is what a player should see; `raw`
# is for staff and for working out why two hulls did or did not touch.
NAUTICAL = "nautical"
RAW = "raw"

STYLES = (NAUTICAL, RAW)

# Schemes for reporting a distance. These are display only - metres are the unit
# everywhere inside the simulation, and always will be.
#
#   leagues   cables, sea miles, then leagues. The age of sail as it was spoken.
#   nautical  cables and sea miles only. Any era's working navigator.
#   metric    metres and kilometres. For a game that is not pretending.
#   raw       metres, for staff.
#
# `leagues` is the default because this is a maritime contrib before it is a
# generic one, and a league is the unit the subject matter actually used. A game
# in another genre changes one setting.
LEAGUES = "leagues"
METRIC = "metric"

DISTANCE_UNITS = (LEAGUES, NAUTICAL, METRIC, RAW)

# Schemes for reporting a depth, kept separate from distance on purpose. A ship
# reckoned her run in leagues and her water in fathoms at the same moment, and
# tying the two together would force one of them to be wrong.
FATHOMS = "fathoms"
METRES = "metres"

DEPTH_UNITS = (FATHOMS, METRES, RAW)


def _degrees_minutes(metres, positive, negative):
    """
    Render a distance from the origin as degrees and decimal minutes.

    Args:
        metres (float): Signed distance from the reference point.
        positive (str): Hemisphere letter when the value is positive.
        negative (str): Hemisphere letter when it is negative.

    Returns:
        text (str): For example `"48°21.4'N"`.

    Notes:
        Degrees and decimal minutes, not degrees-minutes-seconds. It is what
        charts and sights are actually worked in, and it avoids implying a
        precision that dead reckoning does not have.

    """
    hemisphere = positive if metres >= 0 else negative
    total_minutes = abs(metres) / METRES_PER_MINUTE
    degrees = int(total_minutes // MINUTES_PER_DEGREE)
    minutes = total_minutes - degrees * MINUTES_PER_DEGREE
    return f"{degrees}°{minutes:04.1f}'{hemisphere}"


def latitude_of(position):
    """
    The latitude a navigator would write down.

    Args:
        position (WorldPosition): Where the vessel is.

    Returns:
        text (str): For example `"48°21.4'N"`.

    """
    origin = config.get_setting("ORIGIN_NORTHING", 0.0)
    return _degrees_minutes(position.y + float(origin), "N", "S")


def longitude_of(position):
    """
    The longitude a navigator would write down.

    Args:
        position (WorldPosition): Where the vessel is.

    Returns:
        text (str): For example `"4°29.0'W"`.

    """
    origin = config.get_setting("ORIGIN_EASTING", 0.0)
    return _degrees_minutes(position.x + float(origin), "E", "W")


def format_position(position, style=None):
    """
    Render a position for a reader.

    Args:
        position (WorldPosition or NoWorldPositionType): What to render.
        style (str, optional): `NAUTICAL` or `RAW`. Defaults to the game's
            `MARITIME_POSITION_STYLE` setting, or nautical.

    Returns:
        text (str): Something fit to print.

    Raises:
        ValueError: If the style is not recognised. A typo would otherwise fall
            through to a default and quietly show staff coordinates to players.

    """
    if style is None:
        style = config.get_setting("POSITION_STYLE", NAUTICAL)
    if style not in STYLES:
        raise ValueError(f"Unknown position style {style!r}; expected one of {STYLES}.")

    if position is NoWorldPosition or not isinstance(position, WorldPosition):
        return "not at sea"

    if style == RAW:
        return str(position)

    line = f"{latitude_of(position)}  {longitude_of(position)}"
    if position.z < 0.0:
        line = f"{line}, {abs(position.z):.1f} m below the surface"
    return line


def _cables(metres):
    """
    Args:
        metres (float): Distance in metres.

    Returns:
        text (str): The distance in cables, or `"alongside"` under half a cable.

    """
    cables = int(round(metres / METRES_PER_CABLE))
    if cables <= 0:
        return "alongside"
    if cables < len(_CABLE_NAMES):
        return f"{_CABLE_NAMES[cables]} cable{'s' if cables != 1 else ''}"
    return f"{cables} cables"


def format_range(metres, units=None):
    """
    Say a distance the way it would be reported at sea.

    Args:
        metres (float): Distance in metres.
        units (str, optional): One of `DISTANCE_UNITS`. Defaults to the
            configured scheme.

    Returns:
        text (str): e.g. `"two leagues"`, `"4.2 miles"`, `"three cables"`.

    Notes:
        Every scheme falls back to cables at close range, because no scheme has a
        useful word for a tenth of its own unit and every one of them borrowed
        the cable instead. Ranges at sea are estimates, and spelling the small
        ones in words keeps them from reading as though somebody had a
        rangefinder.

    """
    if units is None:
        units = config.get_setting("DISTANCE_UNITS", LEAGUES)

    if units == RAW:
        return f"{metres:.0f} m"

    if units == METRIC:
        if metres < 1000.0:
            return f"{metres:.0f} m"
        return f"{metres / 1000.0:.1f} km"

    if metres < METRES_PER_NAUTICAL_MILE:
        return _cables(metres)

    miles = metres / METRES_PER_NAUTICAL_MILE
    if units == LEAGUES and metres >= METRES_PER_LEAGUE:
        leagues = metres / METRES_PER_LEAGUE
        return f"{leagues:.1f} leagues"
    return f"{miles:.1f} miles"


def format_speed(metres_per_second, units=None):
    """
    Say a speed the way it would be reported.

    Args:
        metres_per_second (float): Speed through the water or over the ground.
        units (str, optional): One of `DISTANCE_UNITS`. Defaults to the
            configured scheme.

    Returns:
        text (str): e.g. `"6.6 knots"`, `"12.2 km/h"`, `"3.40 m/s"`.

    Notes:
        A knot is one nautical mile in an hour, which is why every distance
        scheme except the metric one reports speed in knots - they all measure
        distance in nautical miles underneath, and leagues are only a way of
        saying three of them at once.

        Lives here rather than in the command layer because the messaging layer
        needs it too, and a speed formatted one way for a report and another way
        for a ship's own narration would be a tell.

    """
    if units is None:
        units = config.get_setting("DISTANCE_UNITS", LEAGUES)

    if units == RAW:
        return f"{metres_per_second:.2f} m/s"
    if units == METRIC:
        return f"{metres_per_second * 3.6:.1f} km/h"
    return f"{metres_per_second / METRES_PER_SECOND_PER_KNOT:.1f} knots"


def format_depth(metres, units=None):
    """
    Say a depth the way it would be reported.

    Args:
        metres (float): Depth in metres.
        units (str, optional): One of `DEPTH_UNITS`. Defaults to the configured
            scheme.

    Returns:
        text (str): e.g. `"7.0 fathoms"`, `"12.8 m"`.

    Notes:
        Separate from `format_range` because depth and distance were separate
        questions with separate answers. A ship reckoning her run in leagues
        still sounded in fathoms.

    """
    if units is None:
        units = config.get_setting("DEPTH_UNITS", FATHOMS)
    if units == FATHOMS:
        return f"{metres / METRES_PER_FATHOM:.1f} fathoms"
    return f"{metres:.1f} m"
