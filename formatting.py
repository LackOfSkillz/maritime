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
from .position import METRES_PER_NAUTICAL_MILE, WorldPosition
from .resolver import NoWorldPosition

# Small numbers of cables, said rather than counted.
_CABLE_NAMES = ("", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine")

# One minute of latitude, by definition - and therefore one nautical mile. The
# whole conversion rests on this, so it is defined once, in the spatial layer,
# and named here for what it means when you are reading a position rather than a
# distance.
METRES_PER_MINUTE = METRES_PER_NAUTICAL_MILE
MINUTES_PER_DEGREE = 60.0

# Presentation styles. `nautical` is what a player should see; `raw` is for staff
# and for working out why two hulls did or did not touch.
NAUTICAL = "nautical"
RAW = "raw"

STYLES = (NAUTICAL, RAW)


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


def format_range(metres, style=None):
    """
    Say a distance the way it would be reported at sea.

    Args:
        metres (float): Distance in metres.
        style (str, optional): `NAUTICAL` or `RAW`. Defaults to the configured
            style.

    Returns:
        text (str): e.g. `"4.2 miles"`, `"three cables"`, `"1830 m"`.

    Notes:
        Cables under a mile, miles above it. A cable is a tenth of a nautical
        mile and about a ship's-length unit of thought - close enough that
        "three cables" is a decision and "555 metres" is a measurement. Ranges
        at sea are estimates, and spelling the small ones in words keeps them
        from reading as though somebody had a rangefinder.

    """
    if style is None:
        style = config.get_setting("POSITION_STYLE", NAUTICAL)
    if style == RAW:
        return f"{metres:.0f} m"

    miles = metres / METRES_PER_NAUTICAL_MILE
    if miles >= 1.0:
        return f"{miles:.1f} miles"

    cables = int(round(miles * 10.0))
    if cables <= 0:
        return "alongside"
    if cables < len(_CABLE_NAMES):
        return f"{_CABLE_NAMES[cables]} cable{'s' if cables != 1 else ''}"
    return f"{cables} cables"
