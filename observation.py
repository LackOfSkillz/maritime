"""
What a lookout can see.

Detection at sea is a height problem before it is anything else. A hull is hidden by the
curve of the water, not by distance as such, so how far you can see is decided by how high
your eye is - and how far you can see *a particular thing* is decided by how high that
thing is as well. Two ships each with a masthead thirty metres up see each other at nearly
twice the range either could see a swimmer. That is the whole reason a masthead lookout
exists, and it is why height of eye is an argument to almost everything here.

    horizon(h)              how far the water curves away from an eye h metres up
    geographic range        horizon(observer) + horizon(target)
    visibility              what the air will let through, whichever is less

The classical figure, and the one a navigator actually uses, is `2.07 * sqrt(h)` nautical
miles with h in metres. It already includes standard atmospheric refraction, which bends
light down slightly and buys about eight per cent more range than pure geometry - so the
number is empirical rather than derived, and swapping in a "cleaner" 3.57*sqrt(h) in
kilometres would make every range in the game quietly short.

**The world is a plane and this formula is not.** Positions here live in a flat coordinate
space, so a horizon is not something the world's geometry produces - it is imposed. That is
deliberate: the alternative is either a spherical coordinate space, which makes displayed
position disagree with distance sailed, or no horizon at all, which deletes the masthead.
`HORIZON_COEFFICIENT` is therefore a range model carrying a real-world number, not a claim
about the shape of the sea.

**Detection returns confidence, not truth.** A sighting carries a bearing, an estimated
range and how much the observer can tell - a shape on the water, a vessel, a rig they
recognise, a ship they can name. Nothing here reveals what a target *is*; that is the
difference between a lookout and a database query, and it is what makes closing to identify
a decision worth making.

"""

import math
from dataclasses import dataclass

from .position import METRES_PER_NAUTICAL_MILE, bearing_difference
from .vessel import WEATHER_DECKS

# Nautical miles of horizon per square root of a metre of height. Bowditch's
# figure, which folds in standard atmospheric refraction.
HORIZON_COEFFICIENT = 2.07

# Height of eye, in metres, for an observer with nothing better. A person standing
# on a small craft's deck.
DEFAULT_HEIGHT_OF_EYE = 2.0

# How far the air lets you see in clear weather, in metres. Deliberately further
# than any horizon a masthead reaches, so that in fair conditions it is the curve
# of the water that stops you and not the air. A default of the conventional ten
# nautical miles would sit *inside* a thirty-metre masthead's horizon of eleven
# and a third, which would quietly delete the reason to go aloft - the commonest
# way a sensible-looking default breaks the system it belongs to. Weather
# replaces this later, and then a hazy day genuinely is the constraint.
DEFAULT_VISIBILITY = 30.0 * METRES_PER_NAUTICAL_MILE

# What an observer can tell, in increasing order of certainty.
CONTACT = "contact"
VESSEL = "vessel"
CLASSIFIED = "classified"
IDENTIFIED = "identified"

DETECTION_LEVELS = (CONTACT, VESSEL, CLASSIFIED, IDENTIFIED)

# Fractions of the detection limit at which each level becomes available. Right at
# the edge of vision there is something on the water; halfway in you can see her
# rig; close to, you know the ship.
VESSEL_FRACTION = 0.8
CLASSIFIED_FRACTION = 0.5
IDENTIFIED_FRACTION = 0.2

# One point of the compass. Thirty-two to the circle, which is why bearings are
# reported in points rather than degrees when a lookout is calling them.
DEGREES_PER_POINT = 11.25

_POINT_NAMES = ("one", "two", "three")


@dataclass(frozen=True, kw_only=True)
class Sighting:
    """
    One thing seen from one place.

    Attributes:
        target (any): What was seen.
        distance (float): Range in metres.
        bearing (float): True bearing to it, in degrees.
        relative (float): Bearing relative to the observer's head, -180 to 180,
            positive to starboard.
        level (str): How much the observer can tell.

    Notes:
        The observer's own estimate of range is not this number. Turning a true
        distance into what someone would actually judge belongs with navigational
        error, which lands with charts and dead reckoning; until then a caller
        that reports this to a player is reporting more than a lookout knows.

    """

    target: object
    distance: float
    bearing: float
    relative: float
    level: str


def horizon_distance(height_of_eye):
    """
    How far away the water curves out of sight.

    Args:
        height_of_eye (float): Height above the water, in metres.

    Returns:
        distance (float): Distance to the horizon, in metres. Zero for an eye at
            or below the surface - a swimmer sees nothing at any range.

    """
    if height_of_eye <= 0.0:
        return 0.0
    return HORIZON_COEFFICIENT * math.sqrt(height_of_eye) * METRES_PER_NAUTICAL_MILE


def geographic_range(observer_height, target_height):
    """
    How far apart two things can be and still see each other.

    Args:
        observer_height (float): Height of eye, in metres.
        target_height (float): Height of the thing being looked for, in metres.

    Returns:
        distance (float): Maximum range in metres.

    Notes:
        The sum of two horizons, which is what makes this interesting: a tall ship
        is visible from far beyond the observer's own horizon, because her
        masthead is over it looking back. Sailors call the range at which she
        drops below it her dipping distance, and it was a way of fixing position
        long before anything electronic.

    """
    return horizon_distance(observer_height) + horizon_distance(target_height)


def detection_limit(observer_height, target_height, visibility=DEFAULT_VISIBILITY):
    """
    How far this observer can actually see this target.

    Args:
        observer_height (float): Height of eye, in metres.
        target_height (float): Height of the target, in metres.
        visibility (float, optional): What the air allows, in metres.

    Returns:
        limit (float): Range in metres, the lesser of the two constraints.

    Notes:
        Whichever runs out first. In clear air off a masthead the horizon decides;
        in haze or at night the air does, and height stops helping - which is the
        difference between a foggy day being an inconvenience and being the reason
        two ships meet.

    """
    return min(geographic_range(observer_height, target_height), max(visibility, 0.0))


def detection_level(distance, limit):
    """
    How much an observer can tell at this range.

    Args:
        distance (float): Range to the target, in metres.
        limit (float): The furthest this target could be seen at all.

    Returns:
        level (str or None): One of `DETECTION_LEVELS`, or None if it cannot be
            seen at all.

    Notes:
        A ladder rather than a switch. Something on the water at the limit of
        vision, a vessel closer in, her rig recognisable closer still, and her
        name only when you are near enough to read it or know her by sight.
        Closing to identify is then a decision with a cost, which it would not be
        if detection answered yes or no.

    """
    if limit <= 0.0 or distance > limit:
        return None
    fraction = distance / limit
    if fraction <= IDENTIFIED_FRACTION:
        return IDENTIFIED
    if fraction <= CLASSIFIED_FRACTION:
        return CLASSIFIED
    if fraction <= VESSEL_FRACTION:
        return VESSEL
    return CONTACT


def relative_bearing(heading, bearing):
    """
    Where something lies relative to the way you are pointing.

    Args:
        heading (float): The observer's heading, in degrees.
        bearing (float): True bearing to the target, in degrees.

    Returns:
        relative (float): Degrees from -180 to 180, positive to starboard.

    """
    return bearing_difference(heading, bearing)


def bearing_in_points(relative):
    """
    Say a relative bearing the way a lookout calls it.

    Args:
        relative (float): Relative bearing in degrees, positive to starboard.

    Returns:
        call (str): e.g. `"two points off the starboard bow"`, `"dead astern"`.

    Notes:
        Points, not degrees. A lookout calling a sighting is describing where to
        look, and "broad on the port bow" turns a head in the right direction
        faster than a three-figure bearing does. Degrees are for the chart table.

    """
    side = "starboard" if relative >= 0 else "port"
    magnitude = abs(relative)

    if magnitude < DEGREES_PER_POINT / 2.0:
        return "dead ahead"
    if magnitude > 180.0 - DEGREES_PER_POINT / 2.0:
        return "dead astern"
    if magnitude < 3.5 * DEGREES_PER_POINT:
        points = _POINT_NAMES[min(int(magnitude / DEGREES_PER_POINT + 0.5), 3) - 1]
        return f"{points} points off the {side} bow"
    if magnitude < 6.5 * DEGREES_PER_POINT:
        return f"broad on the {side} bow"
    if magnitude < 9.5 * DEGREES_PER_POINT:
        return f"on the {side} beam"
    if magnitude < 12.5 * DEGREES_PER_POINT:
        return f"broad on the {side} quarter"
    return f"fine on the {side} quarter"


def sight(
    position,
    heading,
    height_of_eye,
    target,
    target_position,
    target_height,
    visibility=DEFAULT_VISIBILITY,
):
    """
    Look at one thing from one place.

    Args:
        position (WorldPosition): Where the observer is.
        heading (float): Which way they are facing, in degrees.
        height_of_eye (float): How high their eye is, in metres.
        target (any): The thing being looked at.
        target_position (WorldPosition): Where it is.
        target_height (float): How high it stands, in metres.
        visibility (float, optional): What the air allows, in metres.

    Returns:
        sighting (Sighting or None): What was seen, or None if it is out of sight
            or in another region.

    Notes:
        Measures across the surface, not through space. An observer looking for a
        hull is asking a surface-horizon question, and counting the metre or two
        of elevation between two floating vessels as *range* would be wrong in the
        one direction that matters - it would make things slightly harder to see
        for being slightly higher.

    """
    if target_position.region != position.region:
        return None

    distance = position.horizontal_distance_to(target_position)
    limit = detection_limit(height_of_eye, target_height, visibility)
    level = detection_level(distance, limit)
    if level is None:
        return None

    bearing = position.bearing_to(target_position)
    return Sighting(
        target=target,
        distance=distance,
        bearing=bearing,
        relative=relative_bearing(heading, bearing),
        level=level,
    )


def scan(position, heading, height_of_eye, candidates, visibility=DEFAULT_VISIBILITY):
    """
    Look at everything within reach, nearest first.

    Args:
        position (WorldPosition): Where the observer is.
        heading (float): Which way they are facing, in degrees.
        height_of_eye (float): How high their eye is, in metres.
        candidates (iterable): `(target, target_position, target_height)` triples.
        visibility (float, optional): What the air allows, in metres.

    Returns:
        sightings (tuple): Everything seen, nearest first.

    Notes:
        Takes triples rather than vessels so that the rules here stay true of
        anything with a position and a height - a headland, a light, a boat, a
        swimmer - and so that this module never needs to know what a vessel is.

    """
    seen = [
        found
        for target, target_position, target_height in candidates
        if (
            found := sight(
                position,
                heading,
                height_of_eye,
                target,
                target_position,
                target_height,
                visibility,
            )
        )
        is not None
    ]
    seen.sort(key=lambda sighting: sighting.distance)
    return tuple(seen)


class Lookout:
    """
    How high a vessel stands, and what can be seen from her.

    """

    def at_object_creation(self):
        """Set up this part of a newly created vessel."""
        super().at_object_creation()
        self.db.air_draft = 12.0

    @property
    def air_draft(self):
        """
        How high she stands above the water.

        Returns:
            air_draft (float): Metres from the waterline to her highest point.

        Notes:
            Her masthead, not her deck. This is what decides how far away someone
            else can see her, and it is the same number that will decide whether
            she fits under a bridge - which is why it is height above the water
            and not height overall.

        """
        return float(self.db.air_draft or 0.0)

    @air_draft.setter
    def air_draft(self, metres):
        """
        Args:
            metres (float): Height above the waterline.

        """
        self.db.air_draft = float(metres)

    @property
    def height_of_eye(self):
        """
        How high this ship's own lookout sees from.

        Returns:
            height (float): Metres above the waterline.

        Notes:
            The highest weather deck she has, because that is where a lookout
            would stand. Building a masthead compartment therefore buys real
            range rather than flavour, and a ship with nothing but a main deck
            sees like a small boat - which she is.

        """
        heights = [room.height_of_eye for room in self.ship_rooms if room.exposure in WEATHER_DECKS]
        return max(heights) if heights else DEFAULT_HEIGHT_OF_EYE

    def contacts(self, height_of_eye=None):
        """
        What can be seen from this hull.

        Args:
            height_of_eye (float, optional): How high the observer's eye is, in
                metres above the waterline. Defaults to her own lookout's.

        Returns:
            sightings (tuple): `Sighting` objects, nearest first.

        Notes:
            Two phases. The register supplies candidates within the furthest
            anything could possibly be seen from this height, and each candidate
            is then tested against its own height - so a low boat and a tall ship
            at the same range get different answers, which is the entire point.

        """
        from . import environment

        position = self.maritime_position
        if position is None:
            return ()
        if height_of_eye is None:
            height_of_eye = self.height_of_eye
        candidates = environment.vessels_within_sight(position, height_of_eye, exclude=self)
        return environment.contacts_from(position, self.heading, height_of_eye, candidates)
