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
import re
from dataclasses import dataclass

from .position import COMPASS_POINTS, METRES_PER_NAUTICAL_MILE, bearing_difference
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
        seen = environment.contacts_from(position, self.heading, height_of_eye, candidates)
        return self._noticed(seen, height_of_eye)

    def _noticed(self, seen, height_of_eye):
        """
        What the lookout actually picks out of what is theoretically in sight.

        Args:
            seen (tuple): Everything the geometry allows.
            height_of_eye (float): How high his eye is.

        Returns:
            noticed (tuple): What he reports.

        Notes:
            **The horizon is geometry and the lookout is attention, and they are not the
            same thing.** A poor lookout cannot see further than the curve of the earth
            allows, and shortening his horizon to model him would be saying he can - so
            what a bad one loses is the faint stuff at the edge of vision, the topsail on
            the skyline he has not picked out yet. He sees what is near perfectly well.

            This is the second consequence `competence_at` finally buys. A game that points
            `MARITIME_COMPETENCE_POLICY` at its own skills now gets a sharp-eyed lookout who
            reports a stranger before a dull one does, which is what a lookout is for.

        """
        from .stations import LOOKOUT

        sharpness = self.competence_at(LOOKOUT)
        if sharpness >= 1.0:
            return seen
        return tuple(
            sighting
            for sighting in seen
            if sighting.distance
            <= sharpness
            * geographic_range(height_of_eye, getattr(sighting.target, "air_draft", 0.0))
        )


# The four quarters of the horizon, as seen from a ship, by the relative bearing
# each is centred on. A quarter is ninety degrees because that is what the words
# mean: everything forward of the beam is "fore".
QUARTER_ARC = 90.0
RELATIVE_ARCS = {
    "fore": 0.0,
    "starboard": 90.0,
    "aft": 180.0,
    "port": -90.0,
}

# Compass directions are narrower, because there are more of them. An eighth of
# the horizon each, so "north" does not swallow north-east.
POINT_ARC = 45.0


def within_arc(bearing, centre, width=QUARTER_ARC):
    """
    Whether a bearing falls inside an arc.

    Args:
        bearing (float): The bearing in question, in degrees.
        centre (float): The middle of the arc, in degrees.
        width (float, optional): How wide the arc is, in degrees.

    Returns:
        inside (bool): True if it falls within.

    Notes:
        Works on true and relative bearings alike, because both are just angles -
        the caller decides which it is passing by which one it takes from a
        sighting. That is the whole reason `Sighting` carries both.

    """
    return abs(bearing_difference(centre, bearing)) <= width / 2.0


def in_arc(sightings, centre, width=QUARTER_ARC, relative=True):
    """
    The sightings that lie in one direction.

    Args:
        sightings (iterable): `Sighting` objects.
        centre (float): The middle of the arc, in degrees.
        width (float, optional): How wide the arc is, in degrees.
        relative (bool, optional): True to measure from the ship's head, False to
            measure from north.

    Returns:
        found (tuple): Those within the arc, in the order given.

    Notes:
        Looking to starboard and looking east are the same question asked from
        two different reference frames, and a ship that comes round changes the
        answer to one of them and not the other. Keeping both is why a lookout
        can be told to watch the port bow and a navigator to watch the headland.

    """
    return tuple(
        sighting
        for sighting in sightings
        if within_arc(sighting.relative if relative else sighting.bearing, centre, width)
    )


#: The four cardinal points, which abbreviate to a single letter each. The rest
#: are built from them: "east-northeast" is e + ne.
_CARDINALS = ("north", "east", "south", "west")

#: Every word that names a direction, mapped to `(name, centre, width, relative)`.
#: Ship-relative directions turn with her and compass directions do not, which is
#: the difference between telling a lookout to watch the port bow and telling him
#: to watch the headland.
#:
#: Keys are normalised - no spaces, hyphens or case - so "south east",
#: "south-east" and "southeast" all arrive as one word, and the abbreviations are
#: here because "se" is what people type.
LOOKOUT_DIRECTIONS = {}


def normalise_direction(text):
    """
    Reduce a typed direction to one comparable form.

    Args:
        text (str): What was typed.

    Returns:
        word (str): Lowercased, with spaces, hyphens and underscores removed.

    Notes:
        A player who has to work out whether this system wants "south east",
        "south-east" or "southeast" has been handed a puzzle instead of a
        compass.

    """
    return re.sub(r"[\s_-]+", "", (text or "").strip().lower())


def _abbreviate(name):
    """
    Args:
        name (str): A compass point, e.g. `"east-northeast"`.

    Returns:
        short (str): Its abbreviation, e.g. `"ene"`.

    """
    return "".join(part[0] if part in _CARDINALS else part[0] + part[5] for part in name.split("-"))


def _register(word, name, centre, width, relative):
    """
    Args:
        word (str): What a player might type.
        name (str): The canonical name reported back.
        centre (float): Middle of the arc, in degrees.
        width (float): How wide the arc is.
        relative (bool): Whether it turns with the ship.

    """
    LOOKOUT_DIRECTIONS[normalise_direction(word)] = (name, centre, width, relative)


for _name, _centre in RELATIVE_ARCS.items():
    _register(_name, _name, _centre, QUARTER_ARC, True)

for _alias, _of in (
    ("ahead", "fore"),
    ("forward", "fore"),
    ("bow", "fore"),
    ("bows", "fore"),
    ("astern", "aft"),
    ("stern", "aft"),
    ("abaft", "aft"),
    ("behind", "aft"),
    ("larboard", "port"),
    ("stbd", "starboard"),
    ("stb", "starboard"),
):
    _register(_alias, *LOOKOUT_DIRECTIONS[normalise_direction(_of)])

for _index, _point in enumerate(COMPASS_POINTS):
    _bearing = _index * 22.5
    _register(_point, _point, _bearing, POINT_ARC, False)
    _register(_abbreviate(_point), _point, _bearing, POINT_ARC, False)
    _register(_point.replace("-", " "), _point, _bearing, POINT_ARC, False)


def direction_named(text):
    """
    Resolve a word into an arc to look along.

    Args:
        text (str): What was typed - a quarter, a compass point, an
            abbreviation, or any spacing of one.

    Returns:
        found (tuple or None): `(name, centre, width, relative)`, or None if the
            word names no direction.

    Notes:
        Returns the canonical name, so "astern", "stern" and "abaft" all report
        as "aft" and a watch set with one word is not a different watch from the
        same one set with another.

    """
    return LOOKOUT_DIRECTIONS.get(normalise_direction(text))
