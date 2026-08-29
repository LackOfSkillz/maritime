"""
Currents: the difference between where you point and where you go.

A vessel's engine or her sails move her through the water. The water itself is also moving.
What an observer ashore sees is the sum of the two, and almost every interesting thing about
navigation lives in that gap:

    heading            where her head is pointing
    speed through water  what the log line measures, and what the sails produce
    set and drift      where the water is going, and how fast
    course made good   where she is actually going
    speed made good    how fast she is actually getting there

Without a current those pairs are the same number twice and navigation is arithmetic. With
one, a passage takes a different time depending on when you sailed, a safe heading can put
you on a lee shore, and a navigator has something to do.

**Set and drift, and the opposite convention from wind.** A current is named for where it
goes; wind is named for where it comes from. A northerly wind blows *from* the north, a
north-setting current flows *towards* it. That is not a quirk to be tidied away - it is what
sailors say, and quietly normalising one of them to match the other is how a bearing ends up
reversed somewhere deep in a passage calculation.

    set     the compass bearing the water flows towards
    drift   how fast it flows, in metres per second

**Speed is through the water, not over the ground.** A chip log measures the water going
past the hull, so a vessel carried three knots sideways by a current still logs whatever her
sails are making. Keeping `speed` as speed through water and deriving the over-ground figures
means the current never has to be subtracted back out of anything.

"""

import math
from dataclasses import dataclass

from .position import normalize_bearing


@dataclass(frozen=True)
class CurrentVector:
    """
    Water on the move.

    Attributes:
        set (float): Compass bearing the water flows *towards*, in degrees.
        drift (float): How fast it flows, in metres per second.

    Notes:
        Named the way a current is named. See the module docstring for why this
        is the reverse of `WindVector`, and why that difference is kept.

    """

    set: float = 0.0
    drift: float = 0.0

    def __post_init__(self):
        """
        Raises:
            ValueError: If the drift is negative. A current running backwards is a
                current with the opposite set, and allowing both spellings means
                two representations of one state.

        """
        if self.drift < 0.0:
            raise ValueError(f"Drift cannot be negative, got {self.drift!r}. Reverse the set.")
        object.__setattr__(self, "set", normalize_bearing(self.set))

    @property
    def running(self):
        """
        Returns:
            running (bool): True if the water is actually moving.

        """
        return self.drift > 0.0

    def components(self):
        """
        Returns:
            components (tuple): `(east, north)` metres per second.

        """
        radians = math.radians(self.set)
        return self.drift * math.sin(radians), self.drift * math.cos(radians)

    def __str__(self):
        if not self.running:
            return "slack water"
        return f"setting {self.set:.0f}° at {self.drift:.2f} m/s"


#: No water movement at all. Slack water, or a game that has not asked for any.
STILL = CurrentVector()

# Speed below which a vessel is treated as going nowhere, in metres per second.
# A hull stemming the tide exactly cancels to a residual of about 1e-16 rather
# than to zero, and asking atan2 for the direction of that residual returns a
# confident, meaningless bearing - a ship reported as making good due south while
# sitting motionless. A nanometre a second is not a course.
STOPPED = 1e-9


class MaritimeCurrentProvider:
    """
    Where the water is going, and how fast.

    Notes:
        A provider rather than a field on the map, because a current is a
        function of time as well as place - a tidal stream reverses twice a day
        and an ocean current does not. Games that want neither can ignore this
        entirely and get slack water.

    """

    def current_at(self, position, game_time):
        """
        The current at a place and a moment.

        Args:
            position (WorldPosition): Where to sample.
            game_time (float): Game time in seconds.

        Returns:
            current (CurrentVector): Set and drift.

        """
        raise NotImplementedError("A current provider must say where the water is going.")


class FlatCurrentProvider(MaritimeCurrentProvider):
    """
    One current everywhere, unchanging.

    Notes:
        The counterpart of the flat sea and the single global wind: enough to
        make the mechanism real and prove the seam, and obviously not a weather
        model. A game supplies its own provider for tidal streams.

    """

    def __init__(self, current=STILL):
        """
        Args:
            current (CurrentVector, optional): The current everywhere.

        """
        self.current = current

    def current_at(self, position, game_time):
        """
        Args:
            position (WorldPosition): Ignored.
            game_time (float): Ignored.

        Returns:
            current (CurrentVector): The one current.

        """
        return self.current


def drift_offset(current, seconds):
    """
    How far the water carries something in a stretch of time.

    Args:
        current (CurrentVector): Set and drift.
        seconds (float): Elapsed game seconds.

    Returns:
        offset (tuple): `(east, north)` displacement in metres.

    Notes:
        Applies to anything floating, not only to vessels. A swimmer, a barrel
        and a wreck are all carried at the same rate, which is why this takes a
        current and a duration rather than a vessel.

    """
    east, north = current.components()
    return east * seconds, north * seconds


def carried(position, current, seconds):
    """
    Where the water has taken something.

    Args:
        position (WorldPosition): Where it was.
        current (CurrentVector): Set and drift.
        seconds (float): Elapsed game seconds.

    Returns:
        position (WorldPosition): Where it is now.

    """
    if not current.running or seconds == 0.0:
        return position
    east, north = drift_offset(current, seconds)
    return position.offset(east, north)


def made_good(heading, speed, current):
    """
    Where she is actually going, and how fast.

    Args:
        heading (float): Where her head is pointing, in degrees.
        speed (float): Speed through the water, in metres per second.
        current (CurrentVector): Set and drift.

    Returns:
        track (tuple): `(course_made_good, speed_made_good)` in degrees and
            metres per second.

    Notes:
        The vector sum, and the reason a heading is not a destination. A vessel
        making five knots with two knots of current on the beam is not going
        where she is pointing and is going faster than she is sailing.

    """
    if not current.running:
        return normalize_bearing(heading), speed

    radians = math.radians(heading)
    east = speed * math.sin(radians)
    north = speed * math.cos(radians)
    current_east, current_north = current.components()
    east += current_east
    north += current_north

    made = math.hypot(east, north)
    if made < STOPPED:
        # Exactly stemmed: sailing into the current at its own rate. She is
        # pointing somewhere and going nowhere, which is a real situation and not
        # an error, so the heading is kept rather than invented.
        return normalize_bearing(heading), 0.0
    return normalize_bearing(math.degrees(math.atan2(east, north))), made


def course_to_steer(track, speed, current):
    """
    What to steer to make good the course you want.

    Args:
        track (float): The course you want to make good, in degrees.
        speed (float): Speed through the water, in metres per second.
        current (CurrentVector): Set and drift.

    Returns:
        heading (float or None): The heading to steer, or None if no heading
            makes that track good.

    Notes:
        The navigator's triangle, and the whole practical point of knowing the
        set and drift: you do not steer where you are going, you steer to
        counteract what the water is doing to you.

        It genuinely has no answer sometimes. A current stronger than the vessel
        can carry her across her intended track faster than she can crab back
        into it, and a boat that cannot outrun the stream cannot make good a
        course into it. Returning None says so rather than returning a heading
        that quietly does not work.

    """
    if speed <= 0.0:
        return None
    if not current.running:
        return normalize_bearing(track)

    relative = math.radians(normalize_bearing(current.set - track))
    across = current.drift * math.sin(relative)

    ratio = -across / speed
    if abs(ratio) > 1.0:
        return None

    correction = math.asin(ratio)
    along = speed * math.cos(correction) + current.drift * math.cos(relative)
    if along <= 0.0:
        return None

    return normalize_bearing(track + math.degrees(correction))
