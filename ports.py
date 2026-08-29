"""
Berths, and what has to be true before a ship can lie in one.

A port is where the sea stops being the only way to get anywhere. It is also the one place
in this system where maritime space and ordinary room space have to meet, and Law 7 decides
how: a physical relationship creates a traversal. Lines go ashore, a gangway comes down, and
that gangway is a real exit between a real deck and a real quay. Nobody is teleported, and
when the lines are let go the exit goes with them.

**A berth has dimensions, and that is the point of having berths at all.** A quay is a
length of stone with a depth of water alongside it. A ship longer than the berth cannot lie
in it, and one drawing more than the water there will sit on the bottom at low tide - which
is a real decision a shipowner makes when they add cargo capacity and gain draft. Without
sizes, a berth is a teleport pad with a nautical name.

    berth        where she lies, how she lies, and what will fit
    approach     close enough, slow enough, and shallow enough for her
    made fast    lines ashore; she is held, and not going anywhere
    gangway      the exit, which exists only while she is made fast

**Way must be off her.** Coming alongside at five knots is not docking, it is a collision
with paperwork. The threshold is deliberately slow - walking pace - because the last part of
an approach was warped, poled or towed, and a ship that can slam into a quay at cruising
speed and call it mooring makes the whole approach meaningless.

"""

from dataclasses import dataclass

from .position import bearing_difference, normalize_bearing
from .results import Result

# Reasons a ship cannot lie in a berth. Each says which precondition failed, so a
# caller can tell her what to do about it rather than only that she cannot.
TOO_FAR = "too_far"
TOO_FAST = "too_fast"
BADLY_ALIGNED = "badly_aligned"
TOO_LONG = "too_long"
TOO_BEAMY = "too_beamy"
TOO_DEEP = "too_deep"
OCCUPIED = "occupied"

# How close she must be for lines to reach the shore, in metres. Generous: the
# last of an approach was warped or poled in, and this is the range at which that
# becomes possible rather than the range at which she is already alongside.
APPROACH_RANGE = 100.0

# Speed at or below which she can be brought alongside, in metres per second.
# Walking pace. Anything faster arriving at a stone quay is a collision.
ALONGSIDE_SPEED = 0.5

# How far off the line of the quay she may lie, in degrees. A ship comes alongside
# roughly parallel, either way round - port side to or starboard side to - so both
# the berth's heading and its reciprocal are acceptable.
ALIGNMENT_TOLERANCE = 45.0


@dataclass(frozen=True)
class Berth:
    """
    A place at a quay where one ship can lie.

    Attributes:
        key (str): Identifier, unique within its port.
        position (WorldPosition): Where the vessel lies when made fast.
        heading (float): The line of the quay, in degrees. She lies along it.
        max_length (float): Longest vessel that fits, in metres.
        max_beam (float): Widest vessel that fits, in metres.
        max_draft (float): Deepest vessel the water there will take, in metres.

    Notes:
        Dimensions are the reason berths exist rather than dock-anywhere. A hull
        that has been fitted out until she draws another half metre may no longer
        fit her home berth, which is the tradeoff made physical.

    """

    key: str
    position: object
    heading: float = 0.0
    max_length: float = 0.0
    max_beam: float = 0.0
    max_draft: float = 0.0

    def __post_init__(self):
        object.__setattr__(self, "heading", normalize_bearing(self.heading))

    def takes(self, length, beam, draft):
        """
        Whether a hull of these dimensions fits.

        Args:
            length (float): Vessel length in metres.
            beam (float): Vessel beam in metres.
            draft (float): How deep she sits, in metres.

        Returns:
            reason (str or None): The dimension that does not fit, or None if she
                does.

        Notes:
            A dimension of zero means unmeasured rather than tiny, and is treated
            as no limit. A game that has not filled in its berth sizes gets a
            working port rather than one that refuses every ship.

        """
        if self.max_length and length > self.max_length:
            return TOO_LONG
        if self.max_beam and beam > self.max_beam:
            return TOO_BEAMY
        if self.max_draft and draft > self.max_draft:
            return TOO_DEEP
        return None


@dataclass(frozen=True, kw_only=True)
class DockingResult(Result):
    """
    What came of trying to bring a ship alongside.

    Attributes:
        berth (Berth or None): The berth in question.
        distance (float): How far off she was, in metres.
        side (str): Which side she lies to the quay, `"port"` or `"starboard"`.

    """

    berth: object = None
    distance: float = 0.0
    side: str = ""


def alongside_side(heading, berth_heading):
    """
    Which side of her is to the quay.

    Args:
        heading (float): Her heading, in degrees.
        berth_heading (float): The line of the quay, in degrees.

    Returns:
        side (str): `"port"` or `"starboard"`.

    Notes:
        Lying head-on along the quay puts the quay on one hand; lying the other
        way round puts it on the other. Which is why a ship is described as
        berthing port side to or starboard side to, and why it matters when
        deciding which rail the gangway goes over.

    """
    return "port" if abs(bearing_difference(berth_heading, heading)) < 90.0 else "starboard"


def can_dock(position, speed, heading, length, beam, draft, berth, occupied=False):
    """
    Test a ship against a berth.

    Args:
        position (WorldPosition): Where she is.
        speed (float): Her speed through the water, in metres per second.
        heading (float): Her heading, in degrees.
        length (float): Her length, in metres.
        beam (float): Her beam, in metres.
        draft (float): How deep she sits, in metres.
        berth (Berth): The berth she is trying for.
        occupied (bool, optional): Whether somebody else is already lying there.

    Returns:
        result (DockingResult): Successful if she can be made fast, and failed
            with the specific reason if she cannot.

    Notes:
        Checked in the order a ship would discover them: whether the berth is
        free at all, then whether she fits it, then whether she is near enough,
        slow enough and lying the right way. There is no point telling a captain
        his approach is too fast for a berth his ship was never going to fit.

    """
    distance = position.horizontal_distance_to(berth.position)

    if occupied:
        return DockingResult.failed(OCCUPIED, berth=berth, distance=distance)

    misfit = berth.takes(length, beam, draft)
    if misfit:
        return DockingResult.failed(misfit, berth=berth, distance=distance)

    if distance > APPROACH_RANGE:
        return DockingResult.failed(TOO_FAR, berth=berth, distance=distance)

    if speed > ALONGSIDE_SPEED:
        return DockingResult.failed(TOO_FAST, berth=berth, distance=distance)

    off_line = abs(bearing_difference(berth.heading, heading))
    if min(off_line, 180.0 - off_line) > ALIGNMENT_TOLERANCE:
        return DockingResult.failed(BADLY_ALIGNED, berth=berth, distance=distance)

    return DockingResult.ok(
        berth=berth,
        distance=distance,
        side=alongside_side(heading, berth.heading),
    )


def nearest_berth(position, berths):
    """
    The berth closest to a position.

    Args:
        position (WorldPosition): Where she is.
        berths (iterable): `Berth` objects.

    Returns:
        berth (Berth or None): The nearest, or None if there are none in the same
            region.

    Notes:
        Nearest, not best. Whether she can actually lie there is `can_dock`'s
        question, and answering "no, and here is why" about the berth she is
        obviously trying for beats silently selecting a different one across the
        harbour.

    """
    candidates = [berth for berth in berths if berth.position.region == position.region]
    if not candidates:
        return None
    return min(candidates, key=lambda berth: position.horizontal_distance_to(berth.position))


class Berthing:
    """
    A vessel's dimensions, and whether she is lying at a quay.

    Notes:
        Length and beam are here because berth fitting is what first needed them.
        They will be wanted again by hull footprints and swept grounding, and
        they will still be one number each.

    """

    def at_object_creation(self):
        """Set up this part of a newly created vessel."""
        super().at_object_creation()
        self.db.length = 0.0
        self.db.beam = 0.0
        self.db.docked_at = None
        self.db.berth_key = None
        self.db.gangway = []

    @property
    def length(self):
        """
        How long she is.

        Returns:
            length (float): Metres.

        Notes:
            Berth fitting today, hull footprint and swept grounding later. The
            same number answers both, which is why it lives on the hull rather
            than in the port code that first needed it.

        """
        return float(self.db.length or 0.0)

    @length.setter
    def length(self, metres):
        """
        Args:
            metres (float): Her length.

        """
        self.db.length = float(metres)

    @property
    def beam(self):
        """
        How wide she is.

        Returns:
            beam (float): Metres.

        """
        return float(self.db.beam or 0.0)

    @beam.setter
    def beam(self, metres):
        """
        Args:
            metres (float): Her beam.

        """
        self.db.beam = float(metres)

    @property
    def docked_at(self):
        """
        The quay she is lying at.

        Returns:
            port (PortRoom or None): Her berth's port, or None if she is at sea.

        """
        return self.db.docked_at

    @property
    def berth_key(self):
        """
        Which berth she is lying in.

        Returns:
            key (str or None): The berth's identifier, or None if she is at sea.

        """
        return self.db.berth_key

    @property
    def docked(self):
        """
        Whether she is made fast to a quay.

        Returns:
            docked (bool): True if her lines are ashore.

        """
        return self.db.docked_at is not None

    def make_fast(self, port, berth, gangway=()):
        """
        Record her as lying in a berth.

        Args:
            port (PortRoom): The quay.
            berth (Berth): The berth she is in.
            gangway (iterable, optional): The exits rigged to her.

        Returns:
            vessel (Vessel): This hull, for chaining.

        Notes:
            Persists immediately rather than waiting for a checkpoint. Docking is
            a critical transition: a ship that reloads having lost the fact that
            she is made fast comes back adrift at a quay with a gangway to
            nowhere.

        """
        self.db.docked_at = port
        self.db.berth_key = berth.key
        self.db.gangway = list(gangway)
        self.ndb.speed = 0.0
        self.maritime_position = berth.position
        self.heading = berth.heading
        self.start_reckoning()
        self.checkpoint()
        port.moor(self)
        return self

    def let_go(self):
        """
        Record her as cast off, and take the gangway away.

        Returns:
            removed (int): How many gangway exits were removed.

        """
        from .rooms import unrig_gangway

        port = self.db.docked_at
        removed = unrig_gangway(self.db.gangway)
        if port:
            port.cast_off(self)
        self.db.docked_at = None
        self.db.berth_key = None
        self.db.gangway = []
        self.checkpoint()
        return removed
