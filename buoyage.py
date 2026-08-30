"""
What a mark *means*, and whether the water has been marked at all.

A buoy with a name and a position tells a navigator nothing. Real buoyage works because
every mark carries a meaning that says where the safe water is relative to itself, and that
meaning is the entire reason a helmsman knows which side to leave it on.

    safe water        mid-channel; pass either side. "The channel begins here."
    port hand         the channel's left edge, proceeding with the direction of buoyage
    starboard hand    its right edge
    cardinal          north, east, south or west: "the safe water is on this side of me"
    isolated danger   moored on the thing itself, with navigable water all round
    special           not navigational at all - a mooring, a cable, a spoil ground

**Direction of buoyage is a convention, not a fact**, and it belongs to the world. Lateral
marks only mean anything once somebody says which way is "in", so a game states it and this
module reads it rather than assuming that everybody enters harbour heading north.

**Two invariants live here**, and they are the reason this module exists at all rather than
being three constants in `routes`:

    every berth        reachable from open water by way of marks
    every charted danger   carries a mark

Both are questions a world can *ask itself*, in a test, and that is the point. A rule like
"every approach is buoyed" holds on the day it is written and quietly stops holding the
first time somebody adds an island. A paragraph in the documentation will not catch that; a
failing test will.

**"Charted" is load-bearing.** An unmarked rock in surveyed water is somebody's negligence;
an unmarked rock in unsurveyed water is just the sea. Keeping that distinction is what makes
a chart worth having and standing into unknown water worth fearing - so the invariant is
that *charted* dangers carry marks, never that all dangers do.

"""

import math
from dataclasses import dataclass

#: What a mark is, and therefore what it means.
SAFE_WATER = "safe water"
PORT_HAND = "port hand"
STARBOARD_HAND = "starboard hand"
NORTH_CARDINAL = "north cardinal"
EAST_CARDINAL = "east cardinal"
SOUTH_CARDINAL = "south cardinal"
WEST_CARDINAL = "west cardinal"
ISOLATED_DANGER = "isolated danger"
SPECIAL = "special"

KINDS = (
    SAFE_WATER,
    PORT_HAND,
    STARBOARD_HAND,
    NORTH_CARDINAL,
    EAST_CARDINAL,
    SOUTH_CARDINAL,
    WEST_CARDINAL,
    ISOLATED_DANGER,
    SPECIAL,
)

#: What a mark is put there to warn you about. A safe-water mark says "here is the
#: channel"; these say "here is the trouble", which is what the danger invariant counts.
DANGER_KINDS = (
    NORTH_CARDINAL,
    EAST_CARDINAL,
    SOUTH_CARDINAL,
    WEST_CARDINAL,
    ISOLATED_DANGER,
)

#: Which way the safe water lies from a cardinal mark, as a bearing. That is the whole
#: content of a cardinal: it is not "there is a rock here", it is "go round me this way".
SAFE_QUADRANT = {
    NORTH_CARDINAL: 0.0,
    EAST_CARDINAL: 90.0,
    SOUTH_CARDINAL: 180.0,
    WEST_CARDINAL: 270.0,
}

#: Which hand to leave a lateral mark on, proceeding *with* the direction of buoyage.
#: Reversed when leaving, which `leave_to` handles rather than each caller remembering.
PORT = "port"
STARBOARD = "starboard"
EITHER = "either"

LATERAL_SIDE = {
    PORT_HAND: PORT,
    STARBOARD_HAND: STARBOARD,
}

#: How much sea-room to give a mark that stands for a danger, as a multiple of the
#: danger's own radius. Two: close enough to be a passage, wide enough that being set
#: down on it by a current is not immediately fatal.
BERTH_FACTOR = 2.0

#: And a floor on that, in metres, for a danger charted as a point with no size worth
#: speaking of. A rock the size of a cart still wants a cable's room.
MINIMUM_BERTH = 100.0

#: How high a mark stands above the water, in metres, when nobody has said. A buoy is a
#: low thing - which is the whole reason landfall was made on a light or a steeple and
#: never on a can, and why the horizon arithmetic has to apply to marks as much as to hulls.
BUOY_HEIGHT = 3.0

#: How near a mark has to be to a danger to count as marking it, in metres. A cardinal is
#: laid off the thing it guards rather than on it, so this is generous by design; an
#: isolated danger mark sits on top of its rock and passes easily.
MARKING_RANGE = 400.0


@dataclass(frozen=True)
class Buoyage:
    """
    A world's statement about how its marks are to be read.

    Attributes:
        direction (float): The bearing that counts as "proceeding inward" - the
            direction of buoyage. Lateral marks are meaningless without it.

    Notes:
        One number, and it has to be authored. Whether a port-hand mark is left to
        port depends entirely on which way you are going, and no algorithm can work
        out which way a harbour considers "in".

    """

    direction: float = 0.0


def leave_to(kind, heading, buoyage=None):
    """
    Which hand to leave a mark on.

    Args:
        kind (str): One of `KINDS`.
        heading (float): The vessel's heading, in degrees.
        buoyage (Buoyage, optional): The world's direction of buoyage. Without one,
            lateral marks cannot be read and come back as `EITHER`.

    Returns:
        side (str): `PORT`, `STARBOARD` or `EITHER`.

    Notes:
        Reverses when outbound, which is the part everybody gets wrong. A port-hand
        mark is left to port going in and to starboard coming out - it marks the same
        edge of the same channel either way, and it is the vessel that turned round.

    """
    side = LATERAL_SIDE.get(kind)
    if side is None or buoyage is None:
        return EITHER
    if _inbound(heading, buoyage.direction):
        return side
    return STARBOARD if side is PORT else PORT


def safe_water_from(kind):
    """
    Args:
        kind (str): One of `KINDS`.

    Returns:
        bearing (float or None): The bearing from the mark towards safe water, or
            None if the mark does not say.

    """
    return SAFE_QUADRANT.get(kind)


def marks_danger(kind):
    """
    Args:
        kind (str): One of `KINDS`.

    Returns:
        warns (bool): True if this mark is there to warn of something.

    """
    return kind in DANGER_KINDS


def berth_for(radius, factor=BERTH_FACTOR, floor=MINIMUM_BERTH):
    """
    How much sea-room to give a danger.

    Args:
        radius (float): How far the danger extends, in metres.
        factor (float, optional): Multiple of its own size to keep off.
        floor (float, optional): The least room to give anything, in metres.

    Returns:
        berth (float): Metres of clearance.

    Notes:
        "Berth" is not a borrowed word here - it is the sea-room sense, the one in
        *give it a wide berth*. The clearance a helmsman holds off a danger already
        had a name, so it did not need a new one.

    """
    return max(floor, radius * factor)


def unmarked_dangers(hazards, marks, charts, reach=MARKING_RANGE):
    """
    Which charted dangers nobody has marked.

    Args:
        hazards (iterable): Things on the bottom, each with `x`, `y` and `key`.
        marks (iterable): Marks, each with a `position` and a `kind`.
        charts (iterable): The charts this world has. A danger counts as charted if
            any of them covers it.
        reach (float, optional): How near a mark must be to count as marking it.

    Returns:
        unmarked (tuple): The hazards that are charted and unwarned, in the order
            given.

    Notes:
        Half of the buoyage invariant, and the half with teeth. A builder who adds a
        reef inside surveyed water and forgets the buoy should get a red test rather
        than a drowned player, and this is the function that turns that from a
        resolution into a fact.

        Only marks that *warn* count. A safe-water mark a mile away says "the channel
        is here"; it does not say "and there is a rock over there".

    """
    warning = [mark for mark in marks if marks_danger(getattr(mark, "kind", SPECIAL))]
    charts = tuple(charts)

    missed = []
    for hazard in hazards:
        spot = _place(hazard)
        if not any(chart.covers(spot) for chart in charts):
            # Unsurveyed water. Not negligence - just the sea.
            continue
        if any(mark.position.horizontal_distance_to(spot) <= reach for mark in warning):
            continue
        missed.append(hazard)
    return tuple(missed)


def unreachable_berths(network, berths, seaward):
    """
    Which berths cannot be reached from open water by way of marks.

    Args:
        network (NavigationNetwork): The world's marks and the safe water between them.
        berths (iterable): Keys of the marks that stand at a berth or landing.
        seaward (iterable): Keys of the marks a vessel arriving from open water would
            make first.

    Returns:
        unreachable (tuple): Berth keys with no marked approach, in the order given.

    Notes:
        The other half of the invariant. Gary's rule is that every dock and every
        landfall has at least one safe approach that is marked; this is that rule
        written down in a form that can fail.

        A berth reachable from *any* seaward mark passes. One good approach is what
        was asked for - a harbour with a single buoyed channel and a great deal of
        foul ground round it is a real harbour, not a broken one.

    """
    seaward = tuple(seaward)
    stranded = []
    for berth in berths:
        if not any(network.plan(entry, berth) for entry in seaward):
            stranded.append(berth)
    return tuple(stranded)


def _place(hazard):
    """
    Args:
        hazard (Hazard): Something on the bottom.

    Returns:
        position (WorldPosition): Where it is.

    Notes:
        Hazards carry loose coordinates rather than a position, because they are
        authored in a table. This is the one place that has to care.

    """
    from .position import WorldPosition

    return WorldPosition(hazard.x, hazard.y, region=getattr(hazard, "region", "default"))


def _inbound(heading, direction, tolerance=90.0):
    """
    Args:
        heading (float): Where the vessel is heading, in degrees.
        direction (float): The direction of buoyage.
        tolerance (float, optional): How far off it still counts as inward.

    Returns:
        inbound (bool): True if she is proceeding with the direction of buoyage.

    Notes:
        A quadrant either side, so a vessel working up a winding channel is still
        "going in" while she tacks. The alternative - requiring her head to be within
        a few degrees of the direction of buoyage - would have a beating vessel swap
        which side of the channel she believed in on every tack.

    """
    from .position import normalize_bearing

    difference = abs(normalize_bearing(heading - direction))
    if difference > 180.0:
        difference = 360.0 - difference
    return difference <= tolerance


#: How far ahead a helmsman looks for marked danger, in metres. A mile and a half: far
#: enough that an alteration is a gentle one, near enough that he is not steering round
#: something he will pass nowhere near.
LOOK_AHEAD = 2500.0


@dataclass(frozen=True)
class Clearance:
    """
    What a helmsman decided about a marked danger.

    Attributes:
        heading (float): The course to steer, in degrees.
        mark (object or None): The mark that forced the alteration, if any.
        altered (float): How far off the ordered course he came, in degrees.
        watching (object or None): The nearest danger ahead she is keeping clear
            of, whether or not this particular tick called for a turn.

    Notes:
        `mark` and `watching` are different questions and both are needed. Steering
        to clear something settles at exactly the berth, so the alteration switches
        off and on as she runs down past it - which makes `mark` a poor thing to
        narrate from, because it flickers. `watching` holds steady from raising the
        danger to passing it, which is what somebody on deck would actually say.

    """

    heading: float
    mark: object = None
    altered: float = 0.0
    watching: object = None


def keep_clear(position, heading, marks, look_ahead=LOOK_AHEAD, berth=MINIMUM_BERTH):
    """
    Alter course, if she needs to, to give marked dangers their berth.

    Args:
        position (WorldPosition): Where she is.
        heading (float): The course she was going to steer, in degrees.
        marks (iterable): Marks in sight, each with `position` and `kind`.
        look_ahead (float, optional): How far ahead to look, in metres.
        berth (float, optional): How much sea-room to keep, in metres.

    Returns:
        clearance (Clearance): The course to steer and what forced it.

    Notes:
        **Only marks that warn are avoided.** A helmsman does not steer round a
        fairway buoy; that is what a fairway buoy is *for*.

        **The mark decides which way to go round**, which is the entire reason kinds
        carry meaning. A cardinal says where the safe water lies, so he goes that
        side even when the other side is a shorter alteration. An isolated danger
        mark says nothing about sides - deep water all round is what it means - so he
        goes whichever way costs less.

        **Nothing behind her matters.** A danger abaft the beam has been passed, and
        a helmsman who kept altering for it would sail in circles.

        This *recommends*; it does not seize the helm. What the caller does with the
        answer decides whether the player was helped or overruled, and only one of
        those is acceptable.

    """
    from .position import normalize_bearing

    worst = None
    nearest = None
    nearest_range = None
    for mark in marks:
        if not marks_danger(getattr(mark, "kind", SPECIAL)):
            continue

        range_to = position.horizontal_distance_to(mark.position)
        if range_to <= 0.0 or range_to > look_ahead:
            continue

        bearing = position.bearing_to(mark.position)
        relative = _relative(normalize_bearing(bearing - heading))
        if abs(relative) >= 90.0:
            # Abaft the beam. She is past it.
            continue

        # Ahead, close enough to matter, and something that warns: she is watching
        # it from here until she is past it, turning or not.
        if nearest_range is None or range_to < nearest_range:
            nearest, nearest_range = mark, range_to

        across = abs(range_to * math.sin(math.radians(relative)))
        if across >= berth:
            continue

        wanted = _clearing_heading(position, mark, bearing, range_to, relative, berth)
        altered = abs(_relative(normalize_bearing(wanted - heading)))
        if worst is None or altered > worst.altered:
            worst = Clearance(heading=wanted, mark=mark, altered=altered)

    if worst is not None:
        return Clearance(
            heading=worst.heading, mark=worst.mark, altered=worst.altered, watching=nearest
        )
    return Clearance(heading=heading, watching=nearest)


def _clearing_heading(position, mark, bearing, range_to, relative, berth):
    """
    Args:
        position (WorldPosition): Where she is.
        mark (object): The mark to clear.
        bearing (float): True bearing to it.
        range_to (float): Range to it, in metres.
        relative (float): Its bearing relative to her head, -180 to 180.
        berth (float): Sea-room wanted, in metres.

    Returns:
        heading (float): A course that clears it by the berth.

    Notes:
        The offset is the angle the berth subtends at this range, so the alteration
        shrinks as she opens the distance and grows as she closes it - which is how
        a helmsman actually behaves, and why an early alteration is a small one.

    """
    from .position import normalize_bearing

    offset = math.degrees(math.asin(min(1.0, berth / range_to)))

    safe = safe_water_from(getattr(mark, "kind", SPECIAL))
    if safe is None:
        # An isolated danger: deep water all round, so go the cheaper way and turn
        # away from the side it already lies on.
        leave_to_port = relative <= 0.0
    else:
        # A cardinal names the side the safe water is on, and she has to end up on
        # that side of it whatever that costs - the whole point of the mark is that
        # the cheaper-looking way round is the one with the rock in it.
        #
        # `towards` is where the safe water lies as seen along the line of sight to
        # the mark. Clockwise of it means passing to the right of the mark, which
        # leaves the mark on her port hand.
        towards = _relative(normalize_bearing(safe - bearing))
        leave_to_port = towards > 0.0

    return normalize_bearing(bearing + offset if leave_to_port else bearing - offset)


def _relative(bearing):
    """
    Args:
        bearing (float): A bearing difference, 0 to 360.

    Returns:
        relative (float): The same angle as -180 to 180, positive to starboard.

    """
    return bearing - 360.0 if bearing > 180.0 else bearing
