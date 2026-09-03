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
from dataclasses import dataclass, replace

from .damage import canvas_drawing
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

#: Fighting sail: topsails, courses handed. Not a weather plan at all - the others are
#: answers to how hard it is blowing, and this is an answer to what is about to happen.
#:
#: It sits between reefed and working on area, and what makes it a *decision* is that
#: everything it buys is derived from that area rather than granted. Less canvas aloft is
#: less canvas to be shot away, and fewer hands are needed to work it, so they are free to
#: serve the guns. She is slower, harder to dismast, and fires faster - and a captain has to
#: judge whether he still needs the speed.
BATTLE = SailPlan("battle", "fighting sail", 0.5, 20.0)

SAIL_PLANS = (FURLED, STORM, REEFED, BATTLE, WORKING, FULL)

#: The ladder the sailing master climbs, which is *not* every plan she can set.
#:
#: Fighting sail is deliberately absent. It is rated to stand more wind than working
#: sail, so a mate choosing the largest plan the weather allows would reach for it in a
#: fresh breeze and shorten down for action on a quiet passage with nobody in sight -
#: setting a tactical plan for a meteorological reason. Sail area is the wrong axis to
#: sort it on because carrying capacity is not what it is for.
#:
#: A captain can still order it whenever he likes; that is the point of it. He simply
#: never gets it by accident.
WEATHER_PLANS = (FURLED, STORM, REEFED, WORKING, FULL)

#: How much of her rigging is exposed even with every sail handed. Masts, yards and
#: standing rigging are still up there - she cannot make herself immune by furling.
BARE_POLE_EXPOSURE = 0.25

#: What share of her company is aloft under a full press of sail. A third: working a
#: ship hard takes most of the watch on deck, and the rest of the company is below,
#: asleep, or at the guns.
FULL_PRESS_HANDS = 0.35


def rigging_exposed(plan):
    """
    How much of her rigging is there to be shot away.

    Args:
        plan (SailPlan): How much canvas is set.

    Returns:
        exposure (float): Multiplier on rigging damage she takes, 0 to 1.

    Notes:
        Derived from the canvas rather than granted to a plan, which is what stops
        fighting sail being a free upgrade. A ship under bare poles has almost
        nothing aloft for chain to cut; a ship under a full press has everything.

        Never quite nothing, even furled: masts, yards and standing rigging are
        still up there, and a ship cannot make herself immune by handing her sails.

    """
    return BARE_POLE_EXPOSURE + (1.0 - BARE_POLE_EXPOSURE) * max(0.0, min(1.0, plan.area))


def hands_aloft(plan):
    """
    What share of her people are working the canvas.

    Args:
        plan (SailPlan): How much is set.

    Returns:
        share (float): Fraction of the company tied up aloft, 0 to 1.

    Notes:
        The other half of the fighting-sail trade. Hands on sheets and halyards are
        hands that are not at the guns, so shortening down frees a battery - and it
        is why a ship cleared for action carries less canvas than one making a
        passage, quite apart from what a chain shot would do to it.

    """
    return max(0.0, min(1.0, plan.area)) * FULL_PRESS_HANDS


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

    def blanketed(self):
        """
        How much of her wind is being taken by ships to windward.

        Returns:
            lost (float): The fraction of her drive spoiled, 0 to 1.

        Notes:
            The number alone, for callers who only want to know how slow she is.
            `shadow` answers the same question and names the ship responsible.

        """
        return self.shadow().lost

    def shadow(self):
        """
        Whose lee she is lying in, and how deep in it she is.

        Returns:
            blanket (Blanket): The worst shadow on her, and who casts it.

        Notes:
            Gathered from the traffic register within the furthest any hull could
            possibly reach downwind, so a fleet action does not become a comparison
            of every ship against every other. Most of the time the answer is that
            nobody is anywhere near her lee and the whole thing costs one query.

            The vessel comes back beside the number because a captain has to be told
            *who* has the wind of him. A ship that quietly lost a third of her speed
            with nothing said would be an invisible penalty; a ship whose mate
            reports the sails slatting because there is a frigate to windward is a
            situation, and that difference is the whole point of the feature.

        """
        from .traffic import MAX_HULL_LENGTH, traffic

        position = self.maritime_position
        if position is None or self.sail_plan.area <= 0.0:
            return NO_SHADOW

        wind = self.wind_here()
        if wind.speed <= 0.0:
            return NO_SHADOW

        # The broad phase is sized on the longest hull afloat rather than on her own,
        # because the shadow she is looking for belongs to the ship casting it. A
        # cutter searching one cutter's length downwind would never find the
        # three-decker two cables to windward that is taking her wind - which is the
        # case the weather gage is most worth having.
        reach = blanket_reach(max(self.length, MAX_HULL_LENGTH), FULL)

        # The worst single shadow rather than the sum of them, on the same grounds as
        # `blanketing` - this is that rule again, over hulls instead of bare data, and
        # kept here rather than delegated so the ship responsible survives the search.
        worst = NO_SHADOW
        for other in traffic().near(position, reach):
            if other is self or other.maritime_position is None:
                continue
            lost = blanketed_by(
                position, other.maritime_position, other.length, other.sail_plan, wind
            )
            if lost > worst.lost:
                worst = Blanket(vessel=other, lost=lost)
        return worst

    def sailing_speed(self, shadow=None):
        """
        The best speed she can make as she is currently set.

        Args:
            shadow (Blanket, optional): Whose lee she is in, if the caller has
                already asked. Passed in on the simulation tick so a ship does not
                query the register twice in one step - once to find out how fast she
                is going, and again to say why.

        Returns:
            speed (float): Metres per second.

        Notes:
            Replaces the ordered speed when under sail. A sailing vessel is not
            asked how fast to go; she goes as fast as the wind on this heading
            allows, which on some headings is not at all.

        """
        # Rigging shot away means less of the canvas she has set is actually
        # pulling. Applied to the plan rather than to the answer, so a damaged ship
        # is slower at *every* sail plan rather than having her speed quietly
        # rewritten afterwards - and so shooting for the rigging is how you catch a
        # ship rather than how you sink her.
        plan = self.sail_plan
        drawing = canvas_drawing(self.damage)

        # A spar lashed where a mast stood carries sail and does not carry as much, and
        # nothing aboard improves it. Multiplied into the same number, so a jury-rigged ship
        # is slower at every plan rather than capped at one - it is her rig that is worse,
        # not her orders - and it stays that way until a yard sees her.
        from .repairs import canvas_after_jury_rig

        drawing = canvas_after_jury_rig(drawing, getattr(self, "jury_rigged", False))
        if drawing < 1.0:
            plan = replace(plan, area=plan.area * drawing)

        # And a ship to windward takes the wind out of what is left. Applied to the
        # canvas for the same reason - being blanketed is having less air in your
        # sails, not having your speed docked afterwards.
        if shadow is None:
            shadow = self.shadow()
        if shadow.lost > 0.0:
            plan = replace(plan, area=plan.area * (1.0 - shadow.lost))

        return achievable_speed(
            self.heading,
            self.wind_here(),
            plan,
            self.polar_curve,
            self.working_limits,
        )


# Upper wind speed of each Beaufort force, in metres per second. The scale is
# ordinal rather than linear - Beaufort defined it by what a full-rigged ship
# could carry, which is why the bands are uneven and why it suits this system so
# exactly. Force 12 has no upper bound.
BEAUFORT_LIMITS = (0.5, 1.5, 3.3, 5.4, 7.9, 10.7, 13.8, 17.1, 20.7, 24.4, 28.4, 32.6)


def beaufort_force(speed):
    """
    The Beaufort force of a wind speed.

    Args:
        speed (float): Wind speed in metres per second.

    Returns:
        force (int): 0 to 12.

    Notes:
        Arithmetic only. What each force is *called* is prose, and lives with the
        rest of the prose - a game describing a force 7 as "near gale" or as
        "the sky gone the colour of a bruise" is making the same measurement.

    """
    for force, limit in enumerate(BEAUFORT_LIMITS):
        if speed < limit:
            return force
    return len(BEAUFORT_LIMITS)


# --- blanketing -------------------------------------------------------------
#
# A ship under sail takes the wind out of the air behind her. Anybody in that
# shadow - her "blanket" - is sailing in disturbed, slower air, and the closer and
# more directly astern they are the worse it is.
#
# This is why the weather gage was worth dying for, and it is the one thing that
# makes position relative to *other ships* matter rather than only position
# relative to the wind. It also completes the fighting-sail trade: shortening down
# means you blanket your enemy less, so a captain gives something up by clearing
# for action even before a shot is fired.

#: How far downwind a ship's blanket reaches, as a multiple of her own length,
#: under a full press. Eight: a few ship-lengths of genuinely disturbed air, which
#: is close enough to the real thing to sail by and small enough that it is a
#: manoeuvring problem rather than a map-wide one.
BLANKET_REACH = 8.0

#: How wide the shadow is, in degrees either side of dead downwind of her.
BLANKET_ARC = 25.0

#: How much drive is lost by a ship directly in another's lee, close under her
#: stern. Not all of it - the air is disturbed rather than absent, and a ship that
#: stopped dead would make the weather gage an execution rather than an advantage.
BLANKET_WORST = 0.55

#: What a hull blankets with every sail handed. Small but not nothing: a bare hull
#: is still something standing up out of the water.
BARE_HULL_BLANKET = 0.15


@dataclass(frozen=True)
class Blanket:
    """
    A shadow on her sails, and the ship casting it.

    Attributes:
        vessel (Vessel or None): Who has the wind of her, or None if nobody has.
        lost (float): The fraction of her drive taken out, 0 to 1.

    """

    vessel: object = None
    lost: float = 0.0


#: Clear air. A shared instance because the overwhelmingly common answer to "is
#: anybody stealing my wind" is no, and it is worth not allocating to say so.
NO_SHADOW = Blanket()


def blanket_reach(length, plan):
    """
    How far downwind this ship spoils the air.

    Args:
        length (float): Her length overall, in metres.
        plan (SailPlan): How much canvas she has set.

    Returns:
        metres (float): How far her blanket extends.

    Notes:
        Scaled by canvas, which is what ties this to fighting sail. A ship that has
        shortened down for action stops spoiling her enemy's wind, and gives up an
        advantage she may not have known she had.

    """
    canvas = BARE_HULL_BLANKET + (1.0 - BARE_HULL_BLANKET) * max(0.0, min(1.0, plan.area))
    return max(0.0, length) * BLANKET_REACH * canvas


def blanketed_by(position, other_position, other_length, other_plan, wind, arc=BLANKET_ARC):
    """
    How much wind one ship takes out of another's sails.

    Args:
        position (WorldPosition): Where the sheltered vessel is.
        other_position (WorldPosition): Where the vessel to windward is.
        other_length (float): Her length overall, in metres.
        other_plan (SailPlan): What she has set.
        wind (WindVector): The true wind.
        arc (float, optional): Half-width of the shadow, in degrees.

    Returns:
        lost (float): The fraction of drive taken out, 0 to 1.

    Notes:
        Two things have to be true: you are downwind of her, and you are close
        enough. Both taper, so the edge of a blanket is a gradient rather than a
        wall - a ship does not fall out of another's lee like stepping through a
        doorway.

    """
    if wind.speed <= 0.0:
        return 0.0

    reach = blanket_reach(other_length, other_plan)
    if reach <= 0.0:
        return 0.0

    range_to = other_position.horizontal_distance_to(position)
    if range_to <= 0.0 or range_to > reach:
        return 0.0

    # Where she lies from the ship to windward, against where the wind is going.
    # Dead in line with the wind is the deepest part of her shadow.
    off = abs(bearing_difference(wind.blowing_towards, other_position.bearing_to(position)))
    if off >= arc:
        return 0.0

    across = math.cos(math.radians(off * 90.0 / arc)) ** 2
    along = 1.0 - (range_to / reach)
    return BLANKET_WORST * across * along


def blanketing(position, plan, wind, others, arc=BLANKET_ARC):
    """
    How much of the wind is being taken out of her by everybody to windward.

    Args:
        position (WorldPosition): Where she is.
        plan (SailPlan): What she has set. A ship with nothing set has nothing
            to steal from.
        wind (WindVector): The true wind.
        others (iterable): `(position, length, plan)` for every other vessel that
            could be shadowing her.
        arc (float, optional): Half-width of a shadow, in degrees.

    Returns:
        lost (float): The fraction of her drive taken out, 0 to 1.

    Notes:
        The worst single shadow rather than the sum of them. Lying behind two ships
        is not twice as calm as lying behind one - the air is already spoiled, and
        adding shadows would let a squadron becalm a ship entirely, which is not a
        thing that happens.

    """
    if plan.area <= 0.0 or wind.speed <= 0.0:
        return 0.0
    return max(
        (blanketed_by(position, where, length, hers, wind, arc) for where, length, hers in others),
        default=0.0,
    )
