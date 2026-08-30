"""
Dead reckoning, and being wrong about where you are.

The engine knows exactly where a ship is. The people aboard her do not, and the whole of
navigation is the gap between those two things.

Dead reckoning is the oldest answer: from a position you trusted, advance by the course you
steered and the distance your log says you ran. It is arithmetic, it needs no instruments
beyond a compass and a log line, and it is *wrong* — because the water was moving and you
did not know it, and because she slipped to leeward of the course you steered.

    DR position     where course and log say you are
    true position   where you are
    the difference  everything the water did that you could not see

**The error is not rolled, it accumulates.** Nothing here generates a random offset. `speed`
in this system is already speed through the water, which is exactly what a log measures, so
advancing a DR by heading and logged speed *is* the real procedure — and it diverges from
the truth by precisely the current and the leeway, both of which the simulation is already
computing for other reasons. Being lost is an emergent consequence of the water moving, not
a mechanic bolted on to make navigation interesting.

That has a consequence worth stating: a ship in slack water with her sails furled and her
engine driving her straight is never lost, and should not be. The sea makes you lost, and a
navigator who knows the set can correct for it.

**A fix is the cure, and taking one has to cost something.** Bring a landmark of known
position within sight and you can say where you are again; the DR resets to the truth and
the uncertainty collapses. Out of sight of land there is nothing to fix on, which is why
the open sea is where dead reckoning matters and why sailors hugged coastlines for
centuries.

**Uncertainty is what the navigator claims, not what they are wrong by.** They cannot know
the second number — if they did they would simply correct it. The circle of uncertainty is
an honest estimate that grows with the distance run since the last fix, and the true error
may be inside it or outside it.

"""

from dataclasses import dataclass, replace

from .currents import CurrentVector
from .position import normalize_bearing

# How much of the distance run a navigator allows for having got wrong, as a
# fraction. Five per cent is the traditional working figure for a careful DR, and
# it is a claim about confidence rather than a measurement of error.
UNCERTAINTY_PER_DISTANCE = 0.05

# The uncertainty of a fresh fix, in metres. Not zero: fixing your position by eye
# off a landmark is good, not perfect, and a navigator who believed a fix exactly
# would never revise it.
FIX_UNCERTAINTY = 50.0


@dataclass(frozen=True)
class DeadReckoning:
    """
    A running estimate of where a ship is.

    Attributes:
        position (WorldPosition): Where course and log say she is.
        run (float): Distance run since the last fix, in metres.
        elapsed (float): Game seconds run since the last fix.
        fixed_at (float): Game time of the last fix, in seconds.

    Notes:
        Carries the distance run rather than a stored uncertainty, because
        uncertainty is derived from it. Storing both invites them to disagree.

        It carries its own elapsed time for the same reason. Working out the set
        she has experienced means dividing by how long she has been running, and
        asking a clock for that answer assumes the reckoning was advanced in step
        with it. Accumulating the same `elapsed` that advanced the position makes
        the pair self-consistent whoever is driving the tick.

    """

    position: object
    run: float = 0.0
    elapsed: float = 0.0
    fixed_at: float = 0.0

    @property
    def uncertainty(self):
        """
        How far out the navigator would admit to being.

        Returns:
            radius (float): Metres.

        """
        return FIX_UNCERTAINTY + UNCERTAINTY_PER_DISTANCE * self.run


def reckon(dr, heading, speed, elapsed):
    """
    Advance a dead reckoning by course steered and distance logged.

    Args:
        dr (DeadReckoning): The current estimate.
        heading (float): The course steered, in degrees.
        speed (float): Speed through the water, in metres per second.
        elapsed (float): Game seconds run.

    Returns:
        dr (DeadReckoning): The advanced estimate.

    Notes:
        Heading and logged speed, and deliberately nothing else. Not the track
        she made good, not the current, not her leeway - a navigator doing this
        by hand has the compass and the log and that is all. Feeding the true
        displacement in here would produce a DR that is always right, which is
        not a dead reckoning, it is a chart plotter.

        There is a third source of error besides the current and the leeway, and
        it is worth naming because the rest of the documentation used to imply
        there were only two. The speed handed in is her speed at the *end* of the
        step, so while she is accelerating the reckoning over-counts - about thirty
        metres for a sloop working up from rest. That is a sampling artefact and a
        realistic one: a navigator reading four knots off the log and multiplying
        by the hour makes exactly the same mistake.

    """
    distance = max(speed, 0.0) * max(elapsed, 0.0)
    if distance <= 0.0:
        return dr
    return replace(
        dr,
        position=dr.position.moved(normalize_bearing(heading), distance),
        run=dr.run + distance,
        elapsed=dr.elapsed + elapsed,
    )


def take_fix(position, now):
    """
    Start a fresh dead reckoning from a known position.

    Args:
        position (WorldPosition): Where she actually is.
        now (float): Game time in seconds.

    Returns:
        dr (DeadReckoning): A new estimate, with the run reset.

    """
    return DeadReckoning(position=position, run=0.0, elapsed=0.0, fixed_at=now)


def error_of(dr, position):
    """
    How far out the dead reckoning actually is.

    Args:
        dr (DeadReckoning): The estimate.
        position (WorldPosition): Where she really is.

    Returns:
        error (float): Metres between the two.

    Notes:
        Not for showing a player. This is the number a navigator cannot have -
        knowing it would mean being able to correct it - and it exists for tests,
        for staff tools, and for deciding whether a fix was worth taking.

    """
    return dr.position.horizontal_distance_to(position)


def set_and_drift(dr, position):
    """
    Work out the current from the difference between DR and a fix.

    Args:
        dr (DeadReckoning): Where course and log said she was.
        position (WorldPosition): Where the fix says she is.

    Returns:
        current (CurrentVector): The set and drift she has experienced.

    Notes:
        Real practice, and the reason a navigator takes fixes rather than only
        trusting them. The vector from the DR position to the fix, divided by the
        time, *is* the current that has been setting her - averaged over the
        whole run, including any leeway, which is why it is called the current
        experienced rather than the current.

        Knowing it is what lets the next leg be steered to counteract it. This is
        the input `course_to_steer` was written for, and the loop closes: sail,
        fix, learn the set, allow for it, sail better.

    """
    if dr.elapsed <= 0.0:
        return CurrentVector()
    displaced = dr.position.horizontal_distance_to(position)
    if displaced <= 0.0:
        return CurrentVector()
    return CurrentVector(
        set=dr.position.bearing_to(position),
        drift=displaced / dr.elapsed,
    )


class Navigator:
    """
    A vessel's running estimate of where she is.

    Notes:
        The Evennia-side face of this module. It lives here rather than with the
        typeclass so that everything about dead reckoning - the arithmetic and
        the state it runs on - is in one file, and it needs nothing from Evennia
        to do it.

    """

    def at_object_creation(self):
        """Set up this part of a newly created vessel."""
        super().at_object_creation()
        self.db.dead_reckoning = None

    @property
    def dead_reckoning(self):
        """
        Where course and log say she is.

        Returns:
            dr (DeadReckoning or None): Her running estimate, or None if she has
                never been launched or fixed.

        """
        return self.db.dead_reckoning

    @dead_reckoning.setter
    def dead_reckoning(self, dr):
        """
        Args:
            dr (DeadReckoning): The new estimate.

        """
        self.db.dead_reckoning = dr

    @property
    def reckoned_position(self):
        """
        The position the people aboard believe they are at.

        Returns:
            position (WorldPosition or None): Her DR position, falling back to
                the truth only if she has never had a reckoning started.

        Notes:
            What a player should be shown. The fallback is not a shortcut: a
            vessel that has never run anywhere has nothing to be wrong about, and
            her berth is as good a fix as any.

        """
        dr = self.dead_reckoning
        return dr.position if dr else self.maritime_position

    def start_reckoning(self):
        """
        Begin a dead reckoning from where she is now.

        Returns:
            dr (DeadReckoning or None): The new estimate, or None if she is not
                afloat.

        Notes:
            Called when she is put somewhere known - launched, warped into a
            berth, moved by staff. Those are all fixes in the navigational sense:
            somebody knows exactly where she is, so there is nothing yet to be
            wrong about.

        """
        from . import config

        position = self.maritime_position
        if position is None:
            return None
        self.dead_reckoning = take_fix(position, config.time_provider().now())
        return self.dead_reckoning

    def fix_position(self, now=None):
        """
        Reset the reckoning to where she actually is.

        Args:
            now (float, optional): Game time. Defaults to the current time.

        Returns:
            experienced (CurrentVector): The set and drift the old reckoning had
                missed, which is what a navigator learns by fixing.

        Notes:
            Returns the lesson rather than nothing, because that is the point of
            taking a fix at sea: the difference between where you thought you
            were and where you are, divided by the time, is the water that has
            been setting you - and the next leg can be steered to allow for it.

        """
        from . import config

        position = self.maritime_position
        if position is None:
            return CurrentVector()
        if now is None:
            now = config.time_provider().now()

        dr = self.dead_reckoning
        experienced = CurrentVector()
        if dr:
            experienced = set_and_drift(dr, position)
        self.dead_reckoning = take_fix(position, now)
        return experienced
