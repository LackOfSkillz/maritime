"""
Tactical geometry: the numbers two ships in company generate about each other.

Everything here is arithmetic on positions, headings and speeds that the simulation already
holds. Nothing decides anything - no weapon fires, no manoeuvre is chosen, nothing is
resolved. These are the quantities a gunner, a helmsman and a captain each read off the same
pair of hulls and use for entirely different purposes:

    range              how far apart they are
    bearing            where she is, from north
    relative bearing   where she is, from your head
    aspect             where *you* are, from *her* head
    relative heading   how their courses differ
    closure            how fast the range is changing

**Aspect is the one that is not symmetric, and it is the one that matters.** Relative
bearing tells a gunner which side to run out; aspect tells a captain what he is looking at -
bow-on and closing, or beam-on and helpless, or stern-on and running. A ship broad on your
beam whose aspect is bow-on is coming for you. The same ship, same bearing, stern-on, is
leaving. Nothing else in this file distinguishes those two situations.

**Range bands are presentation, not physics.** Distance is metres; "long range" is a word.
The bands are configurable because what counts as long depends entirely on what a game arms
its ships with, and a system that hard-coded them would be making a weapons decision inside
a geometry module.

**Pacing is not decided here.** How fast tactical time should run is an open question in the
specification and belongs to the game, so this module says nothing about it and takes no
time argument that would imply it had an opinion.

"""

import math

from .observation import within_arc
from .position import bearing_difference

# Weapon arcs, by the relative bearing each is centred on and how wide it is. A
# broadside gun bears on the beam and has a real spread either side of it; a
# chase gun points where the ship points.
FORWARD = "forward"
STARBOARD_BROADSIDE = "starboard broadside"
PORT_BROADSIDE = "port broadside"
AFT = "aft"
OMNI = "omni"

ARCS = {
    FORWARD: (0.0, 90.0),
    STARBOARD_BROADSIDE: (90.0, 120.0),
    PORT_BROADSIDE: (-90.0, 120.0),
    AFT: (180.0, 90.0),
    OMNI: (0.0, 360.0),
}

# What a range is called, longest first, each with the distance it reaches out
# to. A game arms its ships and then sets these to match; the defaults suit
# smooth-bore guns, where anything past a few cables was optimism.
DEFAULT_RANGE_BANDS = (
    ("extreme", 2000.0),
    ("long", 1000.0),
    ("medium", 500.0),
    ("close", 200.0),
    ("point blank", 60.0),
    ("boarding", 20.0),
)


def relative_heading(own_heading, target_heading):
    """
    How far the two courses differ.

    Args:
        own_heading (float): Your heading, in degrees.
        target_heading (float): Hers, in degrees.

    Returns:
        difference (float): Degrees from -180 to 180, positive if her head is to
            starboard of yours.

    Notes:
        Not where she is - where she is *pointing*. Two ships on the same bearing
        from each other can be running side by side or closing head-on, and only
        this tells them apart.

    """
    return bearing_difference(own_heading, target_heading)


def aspect(position, target_position, target_heading):
    """
    Where you are, seen from her head.

    Args:
        position (WorldPosition): Where you are.
        target_position (WorldPosition): Where she is.
        target_heading (float): Her heading, in degrees.

    Returns:
        angle (float): Degrees from -180 to 180. Zero means you are dead ahead of
            her; 180 means dead astern of her.

    Notes:
        The asymmetric one, and the one that decides what a situation *is*. Also
        called the angle on the bow, and it is what a lookout is really reporting
        when he says a sail is bow-on or shows her quarter.

        A ship broad on your beam whose aspect is bow-on is coming for you. The
        same ship at the same bearing, stern-on, is leaving. No other quantity
        here separates those.

    """
    return bearing_difference(target_heading, target_position.bearing_to(position))


def aspect_name(angle):
    """
    Say an aspect the way it would be reported.

    Args:
        angle (float): Aspect in degrees, from `aspect`.

    Returns:
        name (str): `"bow-on"`, `"starboard bow"`, `"beam-on to starboard"`,
            `"starboard quarter"` or `"stern-on"`.

    """
    side = "starboard" if angle >= 0 else "port"
    magnitude = abs(angle)
    if magnitude < 15.0:
        return "bow-on"
    if magnitude > 165.0:
        return "stern-on"
    if magnitude < 60.0:
        return f"{side} bow"
    if magnitude < 120.0:
        return f"beam-on to {side}"
    return f"{side} quarter"


def closure(position, heading, speed, target_position, target_heading, target_speed):
    """
    How fast the range between two vessels is changing.

    Args:
        position (WorldPosition): Where you are.
        heading (float): Your heading, in degrees.
        speed (float): Your speed over the ground, in metres per second.
        target_position (WorldPosition): Where she is.
        target_heading (float): Her heading, in degrees.
        target_speed (float): Her speed over the ground, in metres per second.

    Returns:
        rate (float): Metres per second. Positive is closing, negative opening.

    Notes:
        The component of relative velocity along the line between them, which is
        the only part of it that changes the range - two ships steaming abreast
        at twenty knots have an enormous relative motion and a closure of zero.

        Speeds over the ground rather than through the water, because it is the
        gap that matters and the water carries both of them.

    """
    line = math.radians(position.bearing_to(target_position))
    own = math.radians(heading)
    hers = math.radians(target_heading)

    # Velocity of each along the line joining them, positive towards her.
    own_along = speed * math.cos(own - line)
    her_along = target_speed * math.cos(hers - line)
    return own_along - her_along


def time_to_close(distance, rate):
    """
    How long until they meet, at this rate.

    Args:
        distance (float): Range now, in metres.
        rate (float): Closure in metres per second.

    Returns:
        seconds (float or None): Game seconds until the range is nothing, or None
            if they are not closing.

    Notes:
        None when the range is opening or steady, because "never" is the honest
        answer and infinity is not a number anybody can put in a report. A
        constant rate is assumed, which is wrong the moment either of them alters
        course - it is a captain's estimate, not a prophecy.

    """
    if rate <= 0.0 or distance <= 0.0:
        return None
    return distance / rate


def range_band(distance, bands=DEFAULT_RANGE_BANDS):
    """
    What to call a range.

    Args:
        distance (float): Range in metres.
        bands (iterable, optional): `(name, reach)` pairs, longest first.

    Returns:
        name (str): What the range is called, or `"out of range"` beyond the
            longest band.

    Notes:
        Presentation, not physics. Distance is metres; "long range" is a word,
        and what counts as long depends entirely on what a game arms its ships
        with. Hard-coding these would be making a weapons decision inside a
        geometry module.

    """
    found = "out of range"
    for name, reach in bands:
        if distance <= reach:
            found = name
    return found


def bears(relative, arc, arcs=ARCS):
    """
    Whether something on this relative bearing is in a given arc.

    Args:
        relative (float): Relative bearing to the target, in degrees.
        arc (str): One of `ARCS`.
        arcs (dict, optional): The arcs available.

    Returns:
        bearing (bool): True if a weapon on that arc could be brought to bear.

    Notes:
        Geometry only. Whether a gun is loaded, run out, crewed or in one piece
        is somebody else's question - this says only that the target is in the
        direction the arc faces, which is the part that manoeuvring can change.

        An omni mount needs no special case: a three-hundred-and-sixty degree arc
        reaches half a circle either side of its centre, which is every bearing
        there is. There was a shortcut here for it until mutation testing pointed
        out that deleting the shortcut changed nothing, which is the definition
        of dead code.

    """
    if arc not in arcs:
        return False
    centre, width = arcs[arc]
    return within_arc(relative, centre, width)


def arcs_bearing(relative, arcs=ARCS):
    """
    Every arc that could be brought to bear.

    Args:
        relative (float): Relative bearing to the target, in degrees.
        arcs (dict, optional): The arcs available.

    Returns:
        found (tuple): The names of the arcs bearing, in the order given.

    Notes:
        More than one can bear at once - a target fine on the bow is in the
        forward arc and the edge of a broadside both - and that overlap is the
        whole of manoeuvring for position.

    """
    return tuple(name for name in arcs if bears(relative, name, arcs))


def crossing_the_t(own_relative, target_aspect):
    """
    Whether you have crossed her T.

    Args:
        own_relative (float): Her relative bearing from you, in degrees.
        target_aspect (float): Your aspect from her, from `aspect`.

    Returns:
        crossed (bool): True if she lies on your beam while you lie on her bow.

    Notes:
        The classic position: your broadside bears on her and only her chase guns
        answer. It falls straight out of holding both quantities - she is abeam
        of you and you are ahead of her - and it is the clearest possible
        demonstration that bearing and aspect are different questions.

    """
    return abs(abs(own_relative) - 90.0) <= 45.0 and abs(target_aspect) <= 45.0
