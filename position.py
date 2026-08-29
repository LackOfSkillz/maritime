"""
Continuous world positions.

A position is three continuous axes and the region they belong to:

    x   east/west, metres
    y   north/south, metres
    z   elevation relative to the sea-level datum, metres

Z is one field for land, sea surface and seabed alike. Underwater terrain is negative,
exposed terrain is positive, and water depth is the difference between the current water
surface and the terrain beneath it. There is no separate depth concept, which is what
makes tides, grounding and shorelines fall out of one model instead of three.

The third axis is present from the start even though surface vessels never leave the
surface. Retrofitting an axis into the authoritative position type would touch distance,
bearing, the spatial indexes, collision and every stored position - the most expensive
change this architecture can absorb, and free to avoid now.

**A region is a coordinate space, not a label.** Two positions in different regions are
not comparable: a lake and an ocean can both have a point at (0, 0) without those points
being anywhere near each other, and no bearing connects them because no water does.
Operations across regions raise rather than returning a meaningless number.

Bearings are compass bearings throughout: 0 degrees is north, 90 is east, increasing
clockwise. That is *not* the convention `math.atan2` uses, and quietly mixing the two is
the classic way to end up sailing at right angles to where you meant.

"""

import math
from dataclasses import dataclass, replace

# Games with a single body of water never need to think about regions.
DEFAULT_REGION = "default"

FULL_CIRCLE = 360.0

# Compass bearings, for readable tests and content.
NORTH = 0.0
EAST = 90.0
SOUTH = 180.0
WEST = 270.0


def normalize_bearing(degrees):
    """
    Wrap a bearing into the range [0, 360).

    Args:
        degrees (float): Any angle in degrees, positive or negative.

    Returns:
        bearing (float): The equivalent bearing in [0, 360).

    Notes:
        Wrapping rather than clamping: 370 degrees is 10, and -90 is 270. Both
        arise naturally from adding a turn to a heading, and clamping would
        silently pin a vessel to due north instead of turning it.

    """
    return degrees % FULL_CIRCLE


def bearing_difference(from_bearing, to_bearing):
    """
    The shortest turn from one bearing to another.

    Args:
        from_bearing (float): Current bearing in degrees.
        to_bearing (float): Desired bearing in degrees.

    Returns:
        difference (float): Signed degrees to turn, in [-180, 180]. Positive turns
            to starboard (clockwise), negative to port.

    Notes:
        Shortest way round, so turning from 350 to 010 is +20 rather than -340.
        Naive subtraction gives the long way and a vessel ordered a few degrees
        across north would swing almost the whole compass to get there.

        Exactly opposite bearings return -180. Both directions are equally short,
        so the choice is arbitrary; picking one keeps the result deterministic,
        which matters for reproducing a manoeuvre from a seed.

    """
    return (to_bearing - from_bearing + 180.0) % FULL_CIRCLE - 180.0


@dataclass(frozen=True)
class WorldPosition:
    """
    A point in continuous world space.

    Frozen: a position is a reading, and code that could edit one in place would
    change it for everything else holding the same object.

    Attributes:
        x (float): East/west metres. East is positive.
        y (float): North/south metres. North is positive.
        z (float): Elevation in metres relative to the sea-level datum. Negative is
            below datum - the seabed, a diver, a settled wreck.
        region (str): The coordinate space this point belongs to. Positions in
            different regions are not comparable.

    """

    x: float
    y: float
    z: float = 0.0
    region: str = DEFAULT_REGION

    def __post_init__(self):
        """
        Reject non-finite coordinates.

        A NaN or infinity entering a position propagates silently through every
        distance and bearing that touches it, and the first visible symptom is
        usually a vessel that has stopped moving for no apparent reason. Far
        cheaper to refuse it here, where the bad value was introduced.

        """
        for name in ("x", "y", "z"):
            value = getattr(self, name)
            if not math.isfinite(value):
                raise ValueError(f"WorldPosition.{name} must be finite, got {value!r}.")

    def _require_same_region(self, other):
        """
        Raise if `other` is in a different coordinate space.

        Args:
            other (WorldPosition): The position being compared against.

        Raises:
            ValueError: If the regions differ.

        """
        if self.region != other.region:
            raise ValueError(
                f"Cannot relate positions in different regions "
                f"({self.region!r} and {other.region!r}); they are separate "
                f"coordinate spaces."
            )

    def horizontal_distance_to(self, other):
        """
        Distance ignoring elevation, in metres.

        Args:
            other (WorldPosition): The other position.

        Returns:
            distance (float): Distance across the surface plane.

        Raises:
            ValueError: If the positions are in different regions.

        Notes:
            This is the navigational distance - how far a vessel must travel. A
            diver forty metres below a hull is nearly zero metres away by this
            measure, which is correct for navigation and wrong for proximity. Use
            `distance_to` when depth separation matters.

        """
        self._require_same_region(other)
        return math.hypot(other.x - self.x, other.y - self.y)

    def distance_to(self, other):
        """
        True distance through space, in metres.

        Args:
            other (WorldPosition): The other position.

        Returns:
            distance (float): Distance including elevation difference.

        Raises:
            ValueError: If the positions are in different regions.

        Notes:
            Use this where depth separates things that look adjacent from above -
            collision, boarding, a diver beneath a hull.

        """
        self._require_same_region(other)
        return math.dist((self.x, self.y, self.z), (other.x, other.y, other.z))

    def bearing_to(self, other):
        """
        Compass bearing from this position to another, in degrees.

        Args:
            other (WorldPosition): The position to bear towards.

        Returns:
            bearing (float): Compass bearing in [0, 360). North is 0, east is 90.

        Raises:
            ValueError: If the positions are in different regions.

        Notes:
            Returns 0.0 when the two positions share a horizontal location, since
            no direction is meaningful. Elevation is ignored: a bearing is a
            heading to steer, and a vessel cannot steer downwards.

            Note the argument order - `atan2(dx, dy)`, not the usual `(dy, dx)`.
            Compass bearings measure clockwise from north, where mathematical
            angles measure anticlockwise from east.

        """
        self._require_same_region(other)
        delta_x = other.x - self.x
        delta_y = other.y - self.y
        if delta_x == 0.0 and delta_y == 0.0:
            return 0.0
        return normalize_bearing(math.degrees(math.atan2(delta_x, delta_y)))

    def offset(self, dx=0.0, dy=0.0, dz=0.0):
        """
        A new position shifted by the given amounts.

        Args:
            dx (float, optional): Eastward metres.
            dy (float, optional): Northward metres.
            dz (float, optional): Upward metres.

        Returns:
            position (WorldPosition): A new position; this one is unchanged.

        """
        return replace(self, x=self.x + dx, y=self.y + dy, z=self.z + dz)

    def with_z(self, z):
        """
        A copy of this position at a different elevation.

        Args:
            z (float): The new elevation, in metres relative to datum.

        Returns:
            position (WorldPosition): A new position at the same x and y.

        Notes:
            The common way to move between the surface, a hull's keel and the
            seabed beneath a given point, all of which share x and y.

        """
        return replace(self, z=z)

    def moved(self, bearing, distance):
        """
        A new position reached by travelling along a compass bearing.

        Args:
            bearing (float): Compass bearing in degrees. North is 0, east is 90.
            distance (float): Distance to travel, in metres.

        Returns:
            position (WorldPosition): The resulting position, at the same
                elevation.

        Notes:
            Travel is horizontal. Elevation is set by the water surface and the
            terrain, not by a heading.

        """
        radians = math.radians(normalize_bearing(bearing))
        return self.offset(dx=distance * math.sin(radians), dy=distance * math.cos(radians))

    def __str__(self):
        """
        A readable form, to millimetres.

        Notes:
            Three decimals, not because navigation needs them but because
            collision, grappling and boarding do - and this is the view a
            developer reads when working out why two hulls did or did not touch.
            Coordinates are stored as full 64-bit floats regardless; this only
            decides how much of that is shown.

            A player-facing report should round further. That is the messaging
            layer's decision, not this one's.

        """
        return f"({self.x:.3f}, {self.y:.3f}, {self.z:.3f}) in {self.region}"
