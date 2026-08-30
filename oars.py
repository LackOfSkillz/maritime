"""
Human propulsion: oars, paddles, and the arms behind them.

A sailing vessel is not asked how fast to go - she goes as fast as the wind on that
heading allows. A pulling boat is the opposite: she goes as fast as the people in her are
willing to work, and stops when they stop. That difference is the whole of this module.

    oar plan      how many positions there are, and what a full crew makes of them
    stroke        how hard they are pulling, from resting to not sustainable
    crew          how many of those positions are actually filled

**Speed is the product of all three.** A six-oared gig pulled by two hands is not a
six-oared gig; she is a slow boat with four oars stowed. Making the crew count matter is
the point of counting them, and it is what makes finding a second pair of hands worth
doing before a long pull.

**Nothing here tires.** How long a crew can hold a racing stroke, and what it costs them,
is a statement about how harsh a game is and collides with whatever stamina the host game
already has - see `DECISIONS.md`. What is modelled is the *rate*: `STRETCH_OUT` is faster
than `GIVE_WAY` and a game that wants it to hurt has the seam to make it hurt.

**A pulling boat can stop herself,** which a sailing vessel cannot. Holding water is not
the absence of rowing - it is putting the blades in and leaving them there - so it is a
braking order rather than a speed of zero, and it comes back as sharper deceleration
rather than as a smaller number.

**A boat nobody is driving still goes somewhere.** Sails furled and blades out of the
water is not the same as being moored: the stream carries her, and so does the wind, in
proportion to how much of her stands up out of the water. That is the same windage a
drifting cask has - see `floating` - and it is why a kayak left alone on a pond ends up
against the lee shore rather than where it was let go.

**Paddling and rowing are one model and two vocabularies.** A kayak is a boat with one
position and a double blade; the arithmetic does not care, and the words very much do. The
plan carries which vocabulary applies and the messaging layer reads it, so nobody ends up
telling a lone kayaker to give way together.

"""

import math
from dataclasses import dataclass, replace

# How a crew is spoken to, which is the only thing that separates a paddle from an oar.
ROWED = "rowed"
PADDLED = "paddled"
STYLES = (ROWED, PADDLED)

# What they have been told to do. Named for the orders a coxswain actually gives.
HOLD_WATER = "hold_water"
EASY_OARS = "easy_oars"
PADDLE = "paddle"
GIVE_WAY = "give_way"
STRETCH_OUT = "stretch_out"

STROKES = (HOLD_WATER, EASY_OARS, PADDLE, GIVE_WAY, STRETCH_OUT)

#: What fraction of her rated speed each stroke makes.
#:
#: `EASY_OARS` and `HOLD_WATER` both produce nothing, and they are not the same
#: order. Easy oars means stop pulling and let her run on; hold water means put the
#: blades in and stop her. The difference is in the deceleration, not in the speed.
STROKE_EFFORT = {
    HOLD_WATER: 0.0,
    EASY_OARS: 0.0,
    PADDLE: 0.4,
    GIVE_WAY: 0.75,
    STRETCH_OUT: 1.0,
}

#: How much of her speed a wholly spent crew have lost. Half: they are still pulling,
#: and a boat rowed by exhausted men is slow rather than stopped. The number is what
#: makes a chase a decision - run her people into the ground now and have nothing left
#: when it matters, or hold something back and watch the other fellow open the range.
EXHAUSTION_COST = 0.5

#: How much harder she stops with the blades held against the water. A pulling boat
#: can take her own way off in a couple of lengths, which is the one thing she can do
#: that a ship under sail cannot.
HOLDING_WATER_BRAKING = 4.0


@dataclass(frozen=True)
class OarPlan:
    """
    What a boat is pulled by.

    Attributes:
        positions (int): How many oars or paddles she is fitted for.
        rated_speed (float): Metres per second she makes with every position
            filled and a full working stroke, in still water.
        style (str): `ROWED` or `PADDLED`. Vocabulary only - the arithmetic is
            the same, and the orders are not.
        name (str): What the arrangement is called - "six-oared gig", "double
            blade".

    Notes:
        A rated speed rather than a force and a displacement. Turning strokes
        into newtons and newtons into knots would need a drag model for every
        hull, and every number in it would be invented; a rated speed is one
        figure a builder can look up, argue with, and set.

    """

    positions: int = 2
    rated_speed: float = 1.6
    style: str = ROWED
    name: str = "oars"

    def __post_init__(self):
        """
        Raises:
            ValueError: If she has no positions, a negative rated speed, or a
                style nobody speaks. A boat with no oars is not a pulling boat.

        """
        if self.positions <= 0:
            raise ValueError(f"OarPlan.positions must be positive, got {self.positions!r}.")
        if not math.isfinite(self.rated_speed) or self.rated_speed < 0.0:
            raise ValueError(
                f"OarPlan.rated_speed must be finite and non-negative, got {self.rated_speed!r}."
            )
        if self.style not in STYLES:
            raise ValueError(f"OarPlan.style must be one of {STYLES}, got {self.style!r}.")


#: A few arrangements, as reference rather than as content. The speeds are what these
#: craft actually do: a racing kayak is quicker than a ship's cutter, which surprises
#: people until they see the two side by side.
OAR_PLANS = {
    "paddle": OarPlan(positions=1, rated_speed=2.2, style=PADDLED, name="a double blade"),
    "canoe": OarPlan(positions=2, rated_speed=1.8, style=PADDLED, name="two paddles"),
    "skiff": OarPlan(positions=2, rated_speed=1.5, style=ROWED, name="a pair of oars"),
    "gig": OarPlan(positions=6, rated_speed=2.0, style=ROWED, name="six oars"),
    "cutter": OarPlan(positions=12, rated_speed=2.3, style=ROWED, name="twelve oars"),
}


def hands_available(plan, crew):
    """
    How much of a boat's power is actually being pulled.

    Args:
        plan (OarPlan): What she is fitted with.
        crew (int): How many positions are filled.

    Returns:
        fraction (float): From 0 to 1.

    Notes:
        Capped at one. A seventh hand in a six-oared gig is a passenger, however
        willing, because there is no seventh oar for them.

    """
    if plan.positions <= 0:
        return 0.0
    return max(0.0, min(1.0, float(crew) / plan.positions))


def rowed_speed(plan, stroke, crew, exhaustion=0.0):
    """
    How fast a boat is being pulled through the water.

    Args:
        plan (OarPlan): What she is fitted with.
        stroke (str): One of `STROKES`.
        crew (int): How many positions are filled.
        exhaustion (float, optional): How spent the people pulling are, 0 to 1.

    Returns:
        speed (float): Metres per second through the water.

    Raises:
        ValueError: If the stroke is not one anybody gives.

    Notes:
        Through the water, like every other speed in this system. What she makes
        over the ground is that plus whatever the water is doing, which is the
        entire point of rowing up a river being harder than rowing down one.

        A spent crew still pull; they pull worse. That is the whole of what
        exhaustion does here - a racing stroke ordered from people who have been
        holding one for an hour is answered, and answered badly. Ordering it is
        still the captain's to do, and living with what it leaves him is the cost.

    """
    if stroke not in STROKE_EFFORT:
        raise ValueError(f"Unknown stroke {stroke!r}. Expected one of {STROKES}.")
    spent = max(0.0, min(1.0, float(exhaustion)))
    fading = 1.0 - spent * EXHAUSTION_COST
    return plan.rated_speed * STROKE_EFFORT[stroke] * hands_available(plan, crew) * fading


def braking_limits(limits, stroke, factor=HOLDING_WATER_BRAKING):
    """
    What she can do about her own way, given the order.

    Args:
        limits (MotionLimits): Her own limits.
        stroke (str): One of `STROKES`.
        factor (float, optional): How much harder held blades stop her.

    Returns:
        limits (MotionLimits): Unchanged, unless she is holding water.

    Notes:
        The whole of the difference between easy oars and hold water. Both order
        no speed; only one of them puts the blades in.

    """
    if stroke != HOLD_WATER:
        return limits
    return replace(limits, acceleration=limits.acceleration * max(1.0, factor))


def reach(plan, stroke, crew, distance, current_along=0.0):
    """
    How long a pull will take.

    Args:
        plan (OarPlan): What she is fitted with.
        stroke (str): One of `STROKES`.
        crew (int): How many positions are filled.
        distance (float): How far, in metres.
        current_along (float, optional): How much of the stream is with her, in
            metres per second. Negative is against.

    Returns:
        seconds (float or None): Game seconds, or None if she will never get
            there - which is a real answer when the stream is faster than she is.

    Notes:
        Exists so that a boat can be asked the question a crew actually asks
        before setting out, and so that "we will never get up this river at that
        stroke" is a thing the game can say before an hour of trying.

    """
    made_good = rowed_speed(plan, stroke, crew) + current_along
    if made_good <= 0.0:
        return None
    return max(0.0, float(distance)) / made_good


#: How much of the wind an ordinary hull catches when she is not sailing, as a
#: fraction of wind speed. Small - a hull is mostly underwater - but not nothing, and
#: over ten minutes on a still pond it is the difference between staying put and
#: fetching up on the lee shore.
HULL_WINDAGE = 0.03


class Oared:
    """
    The Evennia-side face of this module.

    Notes:
        Mixed into `Vessel` alongside `Rigged`, and a hull may honestly have both:
        a cutter carries a lug sail and twelve oars, and which one is driving her
        depends on the wind. Sail wins when there is wind and canvas set, because
        nobody rows a boat that is sailing.

    """

    def at_object_creation(self):
        """Set up this part of a newly created vessel."""
        super().at_object_creation()
        self.db.oar_plan = None
        self.db.stroke = EASY_OARS

    @property
    def oar_plan(self):
        """
        Returns:
            plan (OarPlan or None): What she is fitted with, or None if she has
                no oars at all.

        """
        return self.db.oar_plan

    @oar_plan.setter
    def oar_plan(self, plan):
        """
        Args:
            plan (OarPlan or None): Her arrangement, or None to unship the lot.

        Raises:
            TypeError: If given anything else.

        """
        if plan is not None and not isinstance(plan, OarPlan):
            raise TypeError(f"Expected an OarPlan or None, got {type(plan).__name__}.")
        self.db.oar_plan = plan

    @property
    def stroke(self):
        """
        Returns:
            stroke (str): What they have been told to pull.

        """
        return self.db.stroke or EASY_OARS

    @stroke.setter
    def stroke(self, stroke):
        """
        Args:
            stroke (str): One of `STROKES`.

        Raises:
            ValueError: If it is not an order anybody gives.

        """
        if stroke not in STROKES:
            raise ValueError(f"Unknown stroke {stroke!r}. Expected one of {STROKES}.")
        if self.db.stroke != stroke:
            self.db.stroke = stroke

    @property
    def under_oars(self):
        """
        Returns:
            pulling (bool): Whether oars are what is driving her at this moment.

        Notes:
            False the instant she has sail set and wind to fill it. Nobody rows a
            boat that is sailing, and a hull that did both would be getting her
            speed twice.

        """
        if self.oar_plan is None:
            return False
        if self.sail_plan.area > 0.0 and self.wind_here().speed > 0.0:
            return False
        return True

    @property
    def rowing_crew(self):
        """
        Returns:
            crew (int): How many positions are filled.

        Notes:
            Her ship's company if she has one, and otherwise everybody aboard -
            capped either way by the number of oars, since a boat with six looms
            cannot be pulled by seven people.

            The two cases are both real and neither replaces the other. A galley's
            two hundred oarsmen are a number on the hull, because two hundred
            Evennia objects to be counted every tick would be absurd. A gig pulled
            by whoever happened to climb into her is exactly the people standing in
            her, and counting heads is the only way to know.

        """
        plan = self.oar_plan
        if plan is None:
            return 0
        company = self.company
        if company is not None:
            return min(company.fit, plan.positions)
        aboard = sum(1 for room in self.ship_rooms for obj in room.contents if not obj.destination)
        return min(aboard, plan.positions)

    @property
    def windage(self):
        """
        Returns:
            windage (float): The fraction of wind speed she catches when she is
                not sailing.

        """
        stored = self.db.windage
        return HULL_WINDAGE if stored is None else float(stored)

    @windage.setter
    def windage(self, fraction):
        """
        Args:
            fraction (float): How much of the wind she catches, from 0 to 1.

        Raises:
            ValueError: If outside that range. Above 1 she would outrun the wind
                pushing her, which is not a fast boat but a broken one.

        """
        fraction = float(fraction)
        if not 0.0 <= fraction <= 1.0:
            raise ValueError(f"Windage must be between 0 and 1, got {fraction!r}.")
        if self.db.windage != fraction:
            self.db.windage = fraction

    def blown_from(self, position, elapsed):
        """
        Where the wind has pushed her, with no sail set.

        Args:
            position (WorldPosition): Where she is.
            elapsed (float): Game seconds.

        Returns:
            position (WorldPosition): Where the wind leaves her.

        Notes:
            Only when she is not sailing. Under canvas the wind is already
            driving her and `leeway_angle` says how much of that goes sideways;
            adding this on top would be counting the same air twice.

            The same arithmetic a drifting cask gets, because it is the same
            thing happening. A hull is mostly underwater and catches little, but
            "little" is not "none", and a boat left alone on a pond proves it
            within the quarter hour.

            A calm, a hull that catches nothing and a tick of no length are all
            handled by `drift` itself. Guarding for them again here would be a
            second copy of a rule that is already written down, and a branch no
            test could tell from its absence.

        """
        from .floating import drift
        from .currents import CurrentVector

        return drift(position, CurrentVector(), self.wind_here(), self.windage, elapsed)

    def rowing_speed(self):
        """
        Returns:
            speed (float): What the people in her are making, in metres per second
                through the water.

        """
        plan = self.oar_plan
        if plan is None:
            return 0.0
        return rowed_speed(plan, self.stroke, self.rowing_crew, self.exhaustion)

    def pull_for(self, distance):
        """
        How long this pull will take at the current stroke.

        Args:
            distance (float): How far, in metres.

        Returns:
            seconds (float or None): Game seconds, or None if she will not get
                there at all.

        Notes:
            Allows for the stream she is in, which is why rowing up a river and
            down it are different questions with different answers.

        """
        plan = self.oar_plan
        if plan is None:
            return None
        current = self.current_here()
        along = 0.0
        if current.running:
            from .position import bearing_difference

            angle = bearing_difference(self.heading, current.set)
            along = current.drift * math.cos(math.radians(angle))
        return reach(plan, self.stroke, self.rowing_crew, distance, along)
