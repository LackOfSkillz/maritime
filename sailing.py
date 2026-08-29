"""
How wind drives a hull.

The point of a sailing model is that speed stops being something you order and becomes
something you negotiate. A vessel does not go where she is pointed at the speed she is
told; she goes as fast as the wind on that heading allows, which on some headings is not
at all.

Four things decide what she can make:

    the angle of the wind      a beam reach is fast, close-hauled is slow, dead into
                               the wind is nothing at all
    how much sail is set       more canvas is more drive, until it is too much
    how hard it blows          light airs will not push a hull whatever you set
    the hull herself           her polar curve, which is data, not code

**Wind is named for where it comes from.** A northerly blows *from* the north. That is
the convention every chart, forecast and sailor uses, and quietly treating it as a
direction of travel reverses every calculation downstream while still producing
plausible-looking numbers - which is the worst kind of wrong.

A polar curve belongs to a hull, not to this module. A square-rigger and a fore-and-aft
rig have genuinely different shapes, and baking one in would make every vessel in every
game sail like the same boat.

"""

import math
from dataclasses import dataclass

from .position import bearing_difference, normalize_bearing

# Angle off the wind, in degrees, at which most rigs stop driving entirely. Inside
# this the sails luff and the vessel is "in irons".
IN_IRONS_ANGLE = 30.0

# Degrees per second of steering a crew can manage with no way on, by backing a
# headsail to shove her bow round.
#
# Without this a vessel that turns too close to the wind is trapped for good:
# she loses drive, losing drive costs her steerage, and with no steerage she
# cannot turn back out again. That trap is authentic - it is what being in irons
# means - but a hull nothing can recover is a broken ship, not a hard one. A crew
# with canvas aloft always has this much authority.
BACKED_SAIL_TURN_RATE = 0.8


@dataclass(frozen=True)
class WindVector:
    """
    Wind at a place and time.

    Attributes:
        bearing (float): Compass bearing the wind blows *from*. A northerly is 0.
        speed (float): Wind speed in metres per second.

    """

    bearing: float = 0.0
    speed: float = 0.0

    def __post_init__(self):
        """Normalise the bearing and refuse an impossible speed."""
        object.__setattr__(self, "bearing", normalize_bearing(float(self.bearing)))
        if not math.isfinite(self.speed) or self.speed < 0.0:
            raise ValueError(f"Wind speed must be finite and non-negative, got {self.speed!r}.")

    @property
    def blowing_towards(self):
        """
        The bearing the wind is pushing towards.

        Returns:
            bearing (float): The reciprocal of where it comes from.

        Notes:
            Provided so that code needing the direction of travel says so
            explicitly, rather than someone deciding `bearing` must have meant
            this and reversing the whole model by accident.

        """
        return normalize_bearing(self.bearing + 180.0)


@dataclass(frozen=True)
class SailPlan:
    """
    How much canvas is set.

    Attributes:
        key (str): Identifier, e.g. `"working"`.
        name (str): What the order is called, e.g. `"working sail"`.
        area (float): Fraction of full sail area, from 0 to 1.
        safe_wind (float): Wind speed in metres per second above which this plan
            is more than the vessel should be carrying.

    """

    key: str
    name: str
    area: float
    safe_wind: float

    def __post_init__(self):
        """Reject a plan that could not be set."""
        if not 0.0 <= self.area <= 1.0:
            raise ValueError(f"Sail area must be a fraction from 0 to 1, got {self.area!r}.")
        if self.safe_wind < 0.0:
            raise ValueError(f"Safe wind cannot be negative, got {self.safe_wind!r}.")


# A serviceable default progression, from bare poles to everything she has. Games
# may define their own; nothing here assumes these particular plans exist.
FURLED = SailPlan("furled", "bare poles", 0.0, 1000.0)
STORM = SailPlan("storm", "storm canvas", 0.15, 30.0)
REEFED = SailPlan("reefed", "reefed sail", 0.45, 18.0)
WORKING = SailPlan("working", "working sail", 0.75, 12.0)
FULL = SailPlan("full", "full sail", 1.0, 8.0)

SAIL_PLANS = (FURLED, STORM, REEFED, WORKING, FULL)


def sail_plan(key):
    """
    Look up a standard sail plan by key.

    Args:
        key (str): The plan's key, e.g. `"reefed"`.

    Returns:
        plan (SailPlan or None): The plan, or None if unknown.

    """
    for plan in SAIL_PLANS:
        if plan.key == key:
            return plan
    return None


@dataclass(frozen=True)
class PolarCurve:
    """
    How well a rig drives at each angle off the wind.

    Attributes:
        points (tuple): `(angle, efficiency)` pairs, angle in degrees from 0
            (head to wind) to 180 (dead downwind), efficiency from 0 to 1.

    Notes:
        Data, deliberately. A square-rigger runs beautifully and points terribly;
        a fore-and-aft rig is the reverse. Baking one curve into the engine would
        make every vessel in every game sail identically.

    """

    points: tuple = (
        (0.0, 0.0),
        (30.0, 0.20),
        (45.0, 0.60),
        (60.0, 0.85),
        (90.0, 1.00),
        (120.0, 0.95),
        (150.0, 0.80),
        (180.0, 0.70),
    )

    def __post_init__(self):
        """Reject a curve that cannot be interpolated."""
        if len(self.points) < 2:
            raise ValueError("A polar curve needs at least two points.")
        angles = [angle for angle, _ in self.points]
        if angles != sorted(angles):
            raise ValueError("Polar curve points must be ordered by angle.")
        for angle, efficiency in self.points:
            if not 0.0 <= angle <= 180.0:
                raise ValueError(f"Polar angle must be 0-180 degrees, got {angle!r}.")
            if not 0.0 <= efficiency <= 1.0:
                raise ValueError(f"Polar efficiency must be 0-1, got {efficiency!r}.")

    def efficiency_at(self, angle):
        """
        How well the rig drives at a given angle off the wind.

        Args:
            angle (float): Degrees off the wind, 0 (head to wind) to 180 (running).

        Returns:
            efficiency (float): Fraction of best performance, 0 to 1.

        Notes:
            Linear interpolation between the given points. Real polars curve
            between them, but the difference is smaller than the uncertainty in
            the numbers a game will actually pick, and a straight line is
            something an author can reason about.

        """
        angle = min(180.0, max(0.0, abs(angle)))
        previous_angle, previous_efficiency = self.points[0]
        for point_angle, point_efficiency in self.points:
            if angle <= point_angle:
                span = point_angle - previous_angle
                if span <= 0.0:
                    return point_efficiency
                position = (angle - previous_angle) / span
                return previous_efficiency + position * (point_efficiency - previous_efficiency)
            previous_angle, previous_efficiency = point_angle, point_efficiency
        return previous_efficiency


def relative_wind_angle(heading, wind):
    """
    How far off the wind a vessel is lying.

    Args:
        heading (float): The vessel's compass heading.
        wind (WindVector): The wind.

    Returns:
        angle (float): Degrees off the wind, 0 to 180. Zero is head to wind;
            180 is running dead before it.

    Notes:
        Unsigned, because a rig does not care which side the wind is on - a
        vessel on port tack at 45 degrees sails exactly as one on starboard.
        Which tack she is on matters for leeway and for describing her, not for
        how hard she is driven.

    """
    return abs(bearing_difference(heading, wind.bearing))


def steerage_floor(wind, plan):
    """
    Steering available with no way on, from backing a sail.

    Args:
        wind (WindVector): The wind.
        plan (SailPlan): How much canvas is set.

    Returns:
        rate (float): Degrees per second the crew can manage regardless of speed.

    Notes:
        Zero under bare poles or in a calm - there is nothing to back and nothing
        to back it against. A vessel caught in irons with her sails furled really
        is helpless, and should be.

    """
    if plan.area <= 0.0 or wind.speed <= 0.0:
        return 0.0
    return BACKED_SAIL_TURN_RATE * plan.area


def is_in_irons(heading, wind):
    """
    Whether the vessel is too close to the wind to sail.

    Args:
        heading (float): The vessel's compass heading.
        wind (WindVector): The wind.

    Returns:
        in_irons (bool): True if she cannot make way on this heading.

    """
    return relative_wind_angle(heading, wind) < IN_IRONS_ANGLE


def achievable_speed(heading, wind, plan, curve, limits, rated_wind=10.0):
    """
    The best speed a vessel can make as she is currently set.

    Args:
        heading (float): The vessel's compass heading.
        wind (WindVector): The wind.
        plan (SailPlan): How much canvas is set.
        curve (PolarCurve): The rig's performance by angle.
        limits (MotionLimits): The hull's own ceiling.
        rated_wind (float, optional): Wind speed in metres per second at which
            this hull makes her best speed. More wind than this drives her no
            faster - the hull, not the rig, is the limit by then.

    Returns:
        speed (float): Best achievable speed in metres per second.

    Notes:
        Four factors multiply: the hull's ceiling, the rig's efficiency at this
        angle, how much sail is set, and how hard it is blowing. Any one of them
        at zero stops her, which is as it should be - bare poles, no wind, or
        head to wind all mean the same thing to a sailing vessel.

    """
    if plan.area <= 0.0 or wind.speed <= 0.0:
        return 0.0

    angle = relative_wind_angle(heading, wind)
    efficiency = curve.efficiency_at(angle)
    if efficiency <= 0.0:
        return 0.0

    strength = min(1.0, wind.speed / rated_wind) if rated_wind > 0.0 else 1.0
    return limits.max_speed * efficiency * plan.area * strength


def leeway_angle(heading, wind, plan, speed, max_leeway=12.0):
    """
    How far the vessel is being pushed sideways from where she points.

    Args:
        heading (float): The vessel's compass heading.
        wind (WindVector): The wind.
        plan (SailPlan): How much canvas is set.
        speed (float): Her current speed in metres per second.
        max_leeway (float, optional): Worst-case slip angle in degrees.

    Returns:
        leeway (float): Signed degrees. Positive means she is set to starboard of
            her heading, negative to port.

    Notes:
        A sailing vessel does not travel exactly where she points. The wind
        pushes her bodily to leeward, and the effect is worst close-hauled -
        precisely when a navigator can least afford it, which is why dead
        reckoning goes wrong to windward.

        Falls off as she gains speed, because a hull moving well grips the water
        better. A vessel barely moving slides almost sideways.

    """
    if plan.area <= 0.0 or wind.speed <= 0.0 or speed <= 0.0:
        return 0.0

    angle = relative_wind_angle(heading, wind)
    # Strongest close-hauled, nothing when running square before it.
    closeness = max(0.0, 1.0 - angle / 90.0) if angle < 90.0 else 0.0
    grip = 1.0 / (1.0 + speed)
    magnitude = max_leeway * closeness * grip

    # The wind sets her away from itself: to starboard if it is on her port bow.
    to_starboard = bearing_difference(heading, wind.bearing) < 0.0
    return magnitude if to_starboard else -magnitude


class Rigged:
    """
    A vessel's canvas, and what it will do for her.

    """

    def at_object_creation(self):
        """Set up this part of a newly created vessel."""
        super().at_object_creation()
        self.db.sail_plan_key = FURLED.key
        self.db.polar_curve = PolarCurve()

    @property
    def sail_plan(self):
        """
        How much canvas is set.

        Returns:
            plan (SailPlan): The current sail plan. Bare poles by default - a
                vessel does not put to sea with sail already set.

        """
        return sail_plan(self.db.sail_plan_key or FURLED.key) or FURLED

    @sail_plan.setter
    def sail_plan(self, plan):
        """
        Args:
            plan (SailPlan): The plan to set.

        """
        self.db.sail_plan_key = plan.key

    @property
    def polar_curve(self):
        """
        How this rig drives at each angle off the wind.

        Returns:
            curve (PolarCurve): The hull's performance data.

        """
        return self.db.polar_curve or PolarCurve()

    @polar_curve.setter
    def polar_curve(self, curve):
        """
        Args:
            curve (PolarCurve): The rig's polar data.

        """
        self.db.polar_curve = curve

    def sailing_speed(self):
        """
        The best speed she can make as she is currently set.

        Returns:
            speed (float): Metres per second.

        Notes:
            Replaces the ordered speed when under sail. A sailing vessel is not
            asked how fast to go; she goes as fast as the wind on this heading
            allows, which on some headings is not at all.

        """
        return achievable_speed(
            self.heading,
            self.wind_here(),
            self.sail_plan,
            self.polar_curve,
            self.motion_limits,
        )
