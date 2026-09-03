"""
The ships that are somewhere else.

A world with two hundred sail in it cannot afford two hundred room trees, two hundred
tick handlers and two hundred sets of attributes, and does not need them: nobody is
looking at a hundred and ninety of them. Law 4 says a distant vessel is a lightweight
record rather than an Evennia object, and Law 5 says she advances by arithmetic rather
than by simulation. This is both of those.

**Analytical, not stepped.** A vessel nobody has watched for an hour has not sailed three
thousand one-second steps - she has sailed an hour, and where that puts her is a division.
The cost of a strategic vessel is therefore the same whether she was last touched a second
ago or a week ago, which is the property that makes a background world affordable at all.

**Strategic is not dormant, and conflating them is a bug waiting to happen.** A record is a
*summary*. It rehydrates an NPC trader perfectly, because nothing about that trader is
individual - she is a hull, a route and a speed. It cannot rehydrate a chest somebody left
in the cabin, a room somebody renamed, or the fact that a player is asleep in the hold. A
vessel carrying anything individual leaves the simulation registry instead and keeps her
rooms, and this module refuses to summarise her rather than quietly losing what she had.

**Materialisation preserves identity.** The record carries the key and the dimensions she
had, and the hull that comes back is the hull that went away. A vessel does not become a
different vessel because the way she was stored changed.

"""

from dataclasses import dataclass, field, replace

from .position import WorldPosition
from .results import Result
from .routes import Route

#: What a strategic hull is assumed to make when nothing says otherwise.
#:
#: Four knots, near enough - a working speed for a merchantman on a passage, neither
#: becalmed nor flying. A record with no speed at all would sit still for ever, which is a
#: world that looks broken rather than quiet.
PASSAGE_SPEED = 2.0

NOT_A_HULL = "not_a_hull"
OCCUPIED = "occupied"
ALREADY_STRATEGIC = "already_strategic"
NO_SUCH_RECORD = "no_such_record"
NO_ROUTE = "no_route"


@dataclass(frozen=True)
class Passage:
    """
    A route, a speed, and the moment she started.

    Attributes:
        route (Route): The marks she is going by.
        speed (float): What she makes good, in metres a second.
        departed (float): Game time she left the first mark.

    Notes:
        Three numbers and a frozen route, which is the whole reason this is affordable. The
        alternative - a position updated on a tick - costs a write per vessel per tick and
        gets *less* accurate, because it accumulates the error of every step it took.

    """

    route: Route
    speed: float = PASSAGE_SPEED
    departed: float = 0.0

    @property
    def distance(self):
        """
        Returns:
            distance (float): The whole passage, in metres.

        """
        return self.route.distance

    def run_by(self, now):
        """
        How far she has sailed.

        Args:
            now (float): Game time in seconds.

        Returns:
            run (float): Metres.

        """
        return max(0.0, (float(now) - self.departed)) * max(0.0, self.speed)


@dataclass(frozen=True)
class Fix:
    """
    Where a strategic vessel is, worked out rather than remembered.

    Attributes:
        position (WorldPosition): Where she is now.
        heading (float): What she is steering, in degrees.
        leg (int): How many marks she has left astern.
        arrived (bool): Whether she has run out of route.

    """

    position: WorldPosition
    heading: float = 0.0
    leg: int = 0
    arrived: bool = False


@dataclass(frozen=True)
class StrategicVessel:
    """
    A ship reduced to what a summary can carry.

    Attributes:
        key (str): What she is called.
        length (float): Metres.
        beam (float): Metres.
        passage (Passage): Where she is going and how fast.
        cargo (tuple): What she is carrying, as `(commodity key, tonnes)` pairs.
        owner_key (str): Whose she is, by name rather than by reference.

    Notes:
        Deliberately not a subset of a `Vessel`. Everything here is a plain value, so a
        record survives a reload, pickles into an attribute, and can be compared with
        another record - none of which is true of an object graph. The moment something
        needs a reference to a live object, it is no longer a thing a summary can hold, and
        the vessel belongs in the dormant state instead.

    """

    key: str
    length: float = 20.0
    beam: float = 6.0
    passage: Passage = None
    cargo: tuple = field(default_factory=tuple)
    owner_key: str = ""


def along(passage, now):
    """
    Where a passage has got to.

    Args:
        passage (Passage): The route, speed and departure.
        now (float): Game time in seconds.

    Returns:
        fix (Fix): Her position, heading and progress.

    Notes:
        **One walk of the legs, no matter how long she has been sailing.** The elapsed time
        buys a distance, and the distance is spent along the route until it runs out. A ship
        untouched for a week costs exactly what one untouched for a second costs, which is
        the property Law 5 is protecting.

        A route with one mark is a ship sitting on it. That is not an error - it is a vessel
        at anchor described in the same terms as one on passage, so nothing downstream needs
        two cases.

    """
    marks = passage.route.waypoints if passage and passage.route else ()
    if not marks:
        return Fix(position=None, arrived=True)
    if len(marks) == 1:
        return Fix(position=marks[0].position, arrived=True)

    left = passage.run_by(now)
    for index, (first, second) in enumerate(zip(marks, marks[1:])):
        leg = first.position.horizontal_distance_to(second.position)
        heading = first.position.bearing_to(second.position)
        if left < leg:
            return Fix(position=first.position.moved(heading, left), heading=heading, leg=index)
        left -= leg

    last, before = marks[-1], marks[-2]
    return Fix(
        position=last.position,
        heading=before.position.bearing_to(last.position),
        leg=len(marks) - 1,
        arrived=True,
    )


def is_individual(vessel):
    """
    Whether this hull is carrying anything a summary would lose.

    Args:
        vessel (object): The hull.

    Returns:
        individual (bool): True if she must go dormant rather than strategic.

    Notes:
        **The guard that makes the two states safe to have.** A record can rebuild an NPC
        trader because there is nothing about her that is hers. It cannot rebuild a chest in
        the cabin or a player asleep in the hold, and the failure mode of getting this wrong
        is not a crash - it is a chest that is silently gone, which nobody notices until the
        person who put it there comes back.

        Anything in her compartments counts, not just people. A game that has let a player
        leave a coil of rope on deck has let them leave something, and this contrib is not
        the thing that decides it was not worth keeping.

    """
    for room in getattr(vessel, "ship_rooms", ()):
        for thing in room.contents:
            if getattr(thing, "destination", None) is None:
                return True
    return False


@dataclass(frozen=True, kw_only=True)
class SummaryResult(Result):
    """
    What became of an attempt to summarise a hull.

    Attributes:
        record (StrategicVessel): The summary, if one could be made.

    """

    record: StrategicVessel = None


def summarise(vessel, passage=None):
    """
    Reduce a hull to a record.

    Args:
        vessel (object): The hull.
        passage (Passage, optional): Where she is going. Taken from her route if not given.

    Returns:
        result (Result): The record, or why she cannot be one.

    Notes:
        Refuses rather than truncates. A summary that quietly dropped what it could not
        carry would work perfectly in every test written against NPC traders and lose a
        player's belongings the first time one was used on a ship somebody lived on.

    """
    if not hasattr(vessel, "ship_rooms"):
        return SummaryResult(success=False, code=NOT_A_HULL)
    if is_individual(vessel):
        return SummaryResult(success=False, code=OCCUPIED)

    if passage is None:
        route = getattr(vessel, "route", None)
        if route is None:
            return SummaryResult(success=False, code=NO_ROUTE)
        passage = Passage(route=route, speed=max(0.0, float(getattr(vessel, "speed", 0.0))))

    owner = getattr(vessel, "owner", None)
    return SummaryResult(
        success=True,
        record=StrategicVessel(
            key=vessel.key,
            length=float(vessel.length),
            beam=float(vessel.beam),
            passage=passage,
            cargo=tuple(
                (parcel.commodity.key, parcel.tonnes)
                for hold in getattr(vessel, "holds", ())
                for parcel in hold.stowed
            ),
            owner_key=owner.key if owner is not None else "",
        ),
    )


def materialise(record, now, typeclass=None):
    """
    Build a real hull from a record.

    Args:
        record (StrategicVessel): The summary.
        now (float): Game time in seconds.
        typeclass (class, optional): What to build. The shipped `Vessel` by default.

    Returns:
        vessel (object): The hull, at the position her passage puts her at.

    Notes:
        **Identity is preserved.** She comes back with the name and the dimensions she went
        away with, at the place the arithmetic says she got to - not at the place she left,
        and not as a fresh ship that happens to look like her.

    """
    from evennia.utils import create

    from .motion import MotionLimits
    from .typeclasses import Vessel

    hull = create.create_object(typeclass or Vessel, key=record.key)
    hull.length, hull.beam = record.length, record.beam
    hull.motion_limits = MotionLimits(max_speed=6.0, acceleration=0.5, turn_rate=5.0)

    fix = along(record.passage, now)
    hull.maritime_position = fix.position
    hull.heading = fix.heading
    if record.passage is not None and record.passage.route is not None:
        hull.route = record.passage.route
    return hull


class Fleet:
    """
    Every ship that is somewhere else.

    Notes:
        A dict and nothing more, deliberately. The expensive part of a background world was
        never the bookkeeping - it was giving each vessel a tick, and `along` is what
        removed that. Adding an index here would be optimising the part that is already
        free.

    """

    def __init__(self):
        self._records = {}
        self._next = 1

    def enter(self, record):
        """
        Put a ship into the background.

        Args:
            record (StrategicVessel): The summary.

        Returns:
            handle (int): How to refer to her.

        """
        handle = self._next
        self._next += 1
        self._records[handle] = record
        return handle

    def leave(self, handle):
        """
        Take a ship out of the background.

        Args:
            handle (int): Which one.

        Returns:
            record (StrategicVessel or None): Her summary, if she was in it.

        """
        return self._records.pop(handle, None)

    def get(self, handle):
        """
        Args:
            handle (int): Which one.

        Returns:
            record (StrategicVessel or None): Her summary.

        """
        return self._records.get(handle)

    def __len__(self):
        return len(self._records)

    def records(self):
        """
        Returns:
            records (tuple): Every summary, as `(handle, record)` pairs.

        """
        return tuple(self._records.items())

    def fixes(self, now):
        """
        Where they all are.

        Args:
            now (float): Game time in seconds.

        Returns:
            fixes (dict): Handle to `Fix`.

        Notes:
            The whole background world in one pass, and the pass does not care how long it
            has been since the last one. This is the method the benchmarks measure.

        """
        return {handle: along(record.passage, now) for handle, record in self._records.items()}

    def arrived(self, now):
        """
        Which of them have run out of route.

        Args:
            now (float): Game time in seconds.

        Returns:
            arrived (tuple): Handles.

        """
        return tuple(handle for handle, fix in self.fixes(now).items() if fix.arrived)

    def rerouted(self, handle, passage):
        """
        Send a ship somewhere else.

        Args:
            handle (int): Which one.
            passage (Passage): Her new passage.

        Returns:
            record (StrategicVessel or None): Her updated summary.

        """
        record = self._records.get(handle)
        if record is None:
            return None
        self._records[handle] = replace(record, passage=passage)
        return self._records[handle]

    def clear(self):
        """Empty the background world."""
        self._records.clear()


_FLEET = Fleet()


def fleet():
    """
    Returns:
        fleet (Fleet): The process-wide background world.

    """
    return _FLEET
