"""
Being told to make for a port, and whether you can get there from here.

A captain looking at a chart with six harbours on it wants to know two things about each
of them before he wants anything else: can I get there, and will she fit. This answers
both, in one place, so that the chart, the command and the sailing master all agree - and
so that a port drawn as reachable is a port the command will actually accept.

    can_reach(vessel, port)     -> Passage: a route, a berth, or the reason for neither
    make_for(vessel, port)      -> lay the course and hand it to the sailing master
    ports_afloat()              -> every quay a ship could be told to go to

**Reachable means two things, and it needs both.** A course has to exist over the marks
somebody laid - that is the position `routes` argues, and it is what keeps a clever search
from finding its way into a pond by way of water that is technically continuous. And the one
leg that no mark covers, the run in from the last mark to the quay itself, has to have water
on it.

The second half was not there at first, and the pond found the gap. The fairway mark off
Careenage happens to lie a mile from the pond at the head of the valley - close enough to be
"the mark that serves it" by distance alone - so the pond came out reachable, with a course
laid across a hillside. Distance to a mark is not a channel. The leg is sounded, and a leg
with a bank across it does not serve the harbour behind it, whatever the tape measure says.

That is not a pathfinder and must not become one. It is one straight line, the line the ship
will actually sail, checked against the water she actually draws.

**And she has to fit when she gets there.** A course to a berth that will not take her is
a course to a disappointment three days from now, so the berth is checked at the same
moment as the route - by the same `Berth.takes` the `dock` command uses, in the same words.

**The last leg is the berth itself.** The mark serving a harbour stands a mile off it in
water anybody can pass; the berth is at the end of a pier in water that shoals. Making the
berth the final waypoint means the sailing master's own approach - he slows for the last
mark and for no other - is the approach to the quay, which is what it should have been all
along.
"""

#: How far a mark may stand from a port and still be said to serve it, in metres.
#:
#: A roadstead lies off a harbour, not in it - far enough out that a ship can lie there in
#: any weather, close enough that the harbour is the obvious reason it exists.
#:
#: **Distance alone decides nothing**, and this is where that was learned: the fairway mark
#: off Careenage stands a mile from a pond in the hills, which by this measure made it the
#: approach to the pond. The water on the leg is what settles it; this only bounds the
#: search.
APPROACH_RANGE = 5000.0

#: How much water a ship wants under her keel on the run in, in metres.
#:
#: A metre. Not generous - a pilot would want more - but this is the line between "there is
#: a way in" and "there is not", and being ungenerous here means refusing passages that are
#: merely tight rather than impossible. The sailing master takes her in slowly, and the tide
#: is the captain's problem as it always is.
UNDER_KEEL = 1.0

#: How many soundings to take along a leg.
#:
#: Forty-one, evenly spaced, however long the leg is - so a two-hundred-metre run in is
#: sounded every five metres and a five-kilometre one every hundred and twenty. Coarse at the
#: long end and deliberately so: this decides whether a course *can* be laid, the master
#: sounds ahead continuously while he sails it, and the things that actually sink ships here
#: are authored hazards, which are tested exactly rather than sampled.
RUN_IN_SAMPLES = 40

#: Why a port cannot be made for. One of these travels with every refusal, so that a chart
#: and a command give the same answer in the same words.
NO_ROUTE = "no_route"
NO_MARK = "no_mark"
NO_BERTH = "no_berth"
NOT_AFLOAT = "not_afloat"
ALREADY_THERE = "already_there"

WHY = {
    NO_MARK: "no channel is marked into {port}",
    NO_ROUTE: "there is no safe water laid between here and {port}",
    NO_BERTH: "she will not lie at {port}",
    NOT_AFLOAT: "she is not afloat",
    ALREADY_THERE: "she is lying at {port} already",
}


class Passage:
    """
    What came of asking whether a ship can be told to go somewhere.

    Attributes:
        port (PortRoom): The quay asked about.
        route (Route or None): The course, if one could be laid.
        berth (Berth or None): Where she would lie.
        why (str or None): One of the reasons above, or None if she can go.

    Notes:
        A small object rather than a tuple, because three callers want three different
        parts of it - the chart wants only whether, the command wants the reason, and the
        order wants the route and the berth - and a tuple that three callers unpack
        differently is three chances to unpack it wrong.

    """

    __slots__ = ("port", "route", "berth", "why")

    def __init__(self, port, route=None, berth=None, why=None):
        self.port = port
        self.route = route
        self.berth = berth
        self.why = why

    def __bool__(self):
        """
        Returns:
            can (bool): Whether she can be told to go.

        """
        return self.why is None

    @property
    def said(self):
        """
        Returns:
            sentence (str): Why not, in words, or an empty string if she can go.

        """
        if self.why is None:
            return ""
        name = getattr(self.port, "key", "there")
        return WHY.get(self.why, "she cannot go there").format(port=name)

    def __repr__(self):
        return f"<Passage {getattr(self.port, 'key', None)!r} why={self.why!r}>"


def ports_afloat():
    """
    Every quay a ship could be told to go to.

    Returns:
        ports (list): `PortRoom`s with a position and at least one berth, by name.

    Notes:
        Both conditions matter. A `PortRoom` with no position is not on the water yet - it
        is a room somebody has started and not finished - and one with no berths is a
        quayside with nowhere to lie, which is a viewing platform.

    """
    from .rooms import PortRoom

    found = [
        port
        for port in PortRoom.objects.all_family()
        if port.maritime_position is not None and port.berths
    ]
    found.sort(key=lambda port: port.key.lower())
    return found


def water_along(first, second, draft, world=None, length=0.0, beam=0.0, now=None):
    """
    Whether a straight leg has water on it for a hull of this draught.

    Args:
        first (WorldPosition): One end.
        second (WorldPosition): The other.
        draft (float): How deep she sits, in metres.
        world (MaritimeMapProvider, optional): The ground. Taken from the game's own
            configuration if omitted.
        length (float, optional): Her length, for the hazard corridor.
        beam (float, optional): Her beam, likewise.
        now (float, optional): Game time, because the tide decides this.

    Returns:
        clear (bool): Whether she could sail it.

    Notes:
        **Two questions, asked the two different ways they should be.**

        The authored hazards are asked *exactly*, through `check_hazards`, which tests the
        corridor against each one rather than sampling for it. That is the half that matters
        most and the half that was missing: on the coast this was built against, the islands
        are hazards twelve metres high standing over terrain that samples at minus twenty, so
        a leg straight through an island read as sixty feet of clear water. Three separate
        bugs came out of that in one afternoon.

        The ground is *sampled*, at a bounded number of soundings. Handing the whole leg to
        `check_swept_grounding` fixed the hazards and cost sixty times as much: with no hull
        length to go on it steps every two metres, so a five-kilometre leg became two and a
        half thousand soundings where forty-one had done - on a function called fourteen
        times for every chart drawn. The test suite went from twenty-eight minutes to over an
        hour before anybody noticed.

        Sampling can miss a bank narrower than the gap between soundings. That is a real
        limit and an acceptable one: a bar narrow enough to slip between these is narrow
        enough that a ship crossing it at right angles is over it before she touches, and the
        things that genuinely sink ships here are authored, which is why those are exact.

        True when there is no world to sound. A game with no map provider has no ground,
        every position in it is open water by definition, and refusing every passage because
        nothing could be measured would be the wrong failure.

    """
    if world is None:
        from . import config

        world = config.map_provider()
    if world is None:
        return True
    if now is None:
        from . import config

        now = config.time_provider().now()

    from .grounding import check_hazards

    wanted = float(draft) + UNDER_KEEL

    # The hazards, exactly and cheaply - a walk over the few a world has authored near the
    # corridor, not a walk along the corridor.
    struck = check_hazards(first, second, wanted, 0.0, beam, world, now)
    if struck is not None:
        return False

    # And the ground, sampled.
    for step in range(RUN_IN_SAMPLES + 1):
        along = step / float(RUN_IN_SAMPLES)
        where = first.__class__(
            first.x + (second.x - first.x) * along,
            first.y + (second.y - first.y) * along,
            getattr(first, "z", 0.0),
            first.region,
        )
        if world.sea_surface_z_at(where, now) - world.terrain_z_at(where) < wanted:
            return False
    return True


#: What `approach_for` has already worked out, keyed by port and draught.
#:
#: Which mark serves a quay is a fact about the coast: it depends on where the quay is,
#: where the marks are, and how deep the ship is - and on nothing at all about where she
#: happens to be floating. A chart drawn every two seconds was re-testing the same legs for
#: the same fourteen harbours for ever, at six hundred milliseconds a sheet on a reactor
#: that has one thread.
#:
#: Cleared by `forget_approaches`, which a game calls if it moves a quay or re-lays its
#: marks. Not time-limited: nothing in here changes unless somebody rebuilds the world, and
#: an expiry would trade a real cost paid constantly for a staleness window nobody could
#: predict.
_SERVED_BY = {}


def forget_approaches():
    """
    Drop what has been worked out about which mark serves which quay.

    Notes:
        For a game that moves a quay, re-lays its marks or rebuilds its ground at runtime,
        and for tests. See `_SERVED_BY`.

    """
    _SERVED_BY.clear()


def approach_for(port, network=None, draft=0.0, world=None):
    """
    The mark that serves this port - the one with water between it and the quay.

    Args:
        port (PortRoom): The quay.
        network (NavigationNetwork, optional): The marks. Taken from the game's own
            configuration if omitted.
        draft (float, optional): What the ship draws, so the run in is judged against her
            rather than against nothing.
        world (MaritimeMapProvider, optional): The ground.

    Returns:
        mark (Waypoint or None): The nearest mark within `APPROACH_RANGE` she could
            actually run in from, or None if no channel is marked into this port.

    Notes:
        Nearest *that works*, rather than nearest. Tying a port to its mark by a naming
        convention would hold until somebody renamed a harbour; taking simply the closest
        made a pond in the hills the customer of a fairway buoy a mile away across a ridge.
        Sorted by distance and taking the first with water on the leg is both - the obvious
        mark when there is one, and nothing at all when the nearest is nearest only as the
        crow flies.

    """
    if network is None:
        from . import config

        network = config.navigation_network()
    if network is None:
        return None

    here = port.maritime_position
    if here is None:
        return None

    # Rounded, because a draught is a float that wanders in the last decimal as a hull is
    # loaded, and a cache keyed on it exactly would never hit twice. A tenth of a metre is
    # far finer than the difference between one channel and another.
    #
    # **Not keyed on the network.** `id(network)` was in here, which is worse than useless:
    # CPython reuses an id the moment the object it belonged to is collected, so two
    # different networks can share one and the second would be handed the first one's
    # answers. A game that changes its marks calls `forget_approaches`, which is what that
    # function is for and is a promise a caller can actually keep.
    remembered = (port.id, round(float(draft), 1))
    if remembered in _SERVED_BY:
        return _SERVED_BY[remembered]

    near = [
        mark
        for mark in network.marks()
        if mark.position.region == here.region
        and here.horizontal_distance_to(mark.position) <= APPROACH_RANGE
    ]
    near.sort(key=lambda mark: here.horizontal_distance_to(mark.position))

    found = None
    for mark in near:
        if water_along(mark.position, here, draft, world):
            found = mark
            break
    _SERVED_BY[remembered] = found
    return found


def departure_from(here, network, draft=0.0, world=None):
    """
    The mark she can actually get to from where she is.

    Args:
        here (WorldPosition): Where she lies.
        network (NavigationNetwork): The marks.
        draft (float, optional): What she draws.
        world (MaritimeMapProvider, optional): The ground.

    Returns:
        mark (Waypoint or None): The nearest mark with water on the leg to it, or None if
            she is somewhere no marked channel can be joined from.

    Notes:
        **The other end of the same problem `approach_for` solves, and it was missed.** The
        legs *between* marks are a world's own statement about where the water runs and are
        checked when they are laid. The leg from wherever a ship happens to be floating to
        the first of them is nobody's statement about anything - she could be anywhere - so
        it has to be sounded like the run in.

        Found the hard way. A vessel lying east of an island chain was given a course whose
        first mark was west of it; the sailing master steered the direct line at six metres
        a second and put her on a spit two hundred metres away, on a course the game itself
        had planned. Every leg of the network was clear. The leg onto it was not.

    """
    near = [mark for mark in network.marks() if mark.position.region == here.region]
    near.sort(key=lambda mark: here.horizontal_distance_to(mark.position))
    for mark in near:
        if water_along(here, mark.position, draft, world):
            return mark
    return None


def berth_at(port, vessel):
    """
    Where she would lie, if she can lie there at all.

    Args:
        port (PortRoom): The quay.
        vessel (Vessel): The hull.

    Returns:
        berth (Berth or None): A free berth that takes her.

    Notes:
        Free *and* big enough, asked in that order and against the same `Berth.takes` the
        `dock` command uses. A berth held by somebody else is not a berth, however well she
        would have fitted it.

    """
    for berth in port.berths:
        if port.occupant_of(berth) is not None:
            continue
        if berth.takes(vessel.length, vessel.beam, vessel.draft) is None:
            return berth
    return None


def can_reach(vessel, port, network=None, start=None):
    """
    Whether this ship can be told to make for this port.

    Args:
        vessel (Vessel): The hull.
        port (PortRoom): The quay.
        network (NavigationNetwork, optional): The marks.
        start (Waypoint, optional): The mark she would leave from, when the caller has
            already worked it out. It depends only on where *she* is, so a chart asking
            about fourteen harbours should find it once rather than fourteen times.

    Returns:
        passage (Passage): The course and the berth, or the reason for neither.

    Notes:
        Asked in the order that gives the most useful *answer*, not the cheapest one. With
        the berth checked first, the pond reported "she will not lie there" - true, and
        misleading in the same breath, because it says a bigger quay would fix it and
        nothing would. No channel marked in is what is actually wrong, so it is asked
        first. Nothing here is expensive at this scale.

    """
    from .routes import Waypoint

    here = vessel.maritime_position
    if here is None:
        return Passage(port, why=NOT_AFLOAT)
    if vessel.docked_at == port:
        return Passage(port, why=ALREADY_THERE)

    if network is None:
        from . import config

        network = config.navigation_network()
    if network is None:
        return Passage(port, why=NO_MARK)

    destination = approach_for(port, network, vessel.draft)
    if destination is None:
        return Passage(port, why=NO_MARK)

    berth = berth_at(port, vessel)
    if berth is None:
        return Passage(port, why=NO_BERTH)

    if start is None:
        start = departure_from(here, network, vessel.draft)
    if start is None:
        return Passage(port, why=NO_ROUTE)

    route = network.plan(start.key, destination.key)
    if not route:
        return Passage(port, why=NO_ROUTE)

    # The berth is the last leg, so the master's own final approach - he slows for the last
    # mark and for no other - is the approach to the quay. Given its own kind, so a chart
    # drawing the course does not put a buoy symbol on the end of a pier.
    alongside = Waypoint(berth.key, berth.position, kind=destination.kind)
    return Passage(port, route=route.extended(alongside), berth=berth)


def make_for(vessel, port, network=None):
    """
    Lay the course and give the sailing master his standing order.

    Args:
        vessel (Vessel): The hull.
        port (PortRoom): Where she is bound.
        network (NavigationNetwork, optional): The marks.

    Returns:
        passage (Passage): What was ordered, or why it was not.

    Notes:
        **Two things, and the second is what makes it more than `plot` and `follow`.** The
        course is the ordinary thing any captain could lay by hand. The standing order to
        take her alongside at the end of it is the part he cannot: `follow`'s own help says
        the master will make no judgement beyond steering, carrying sail and taking the way
        off her, and that anything more is a standing order. This is that order, given
        explicitly, which is why it is recorded on the hull and not inferred from the fact
        that her last waypoint happens to be a berth.

        Nothing is changed at all if she cannot go. A half-given order - a course laid and
        no master to sail it, or a master told to dock somewhere she has no course to - is
        worse than none.

    """
    passage = can_reach(vessel, port, network)
    if not passage:
        return passage

    here = vessel.maritime_position

    vessel.route = passage.route
    # Marks she is already at do not have to be sailed to. A ship lying on the very mark
    # her course starts from was being told to make for it, which sent her away from it and
    # then back - a lap of a buoy she was moored to. `advance` is the same function the
    # sailing master uses every tick; asking it once at the start means the order is given
    # from where she actually is.
    vessel.route_index = passage.route.advance(here, 0)
    vessel.db.alongside_at = port
    vessel.under_con = True
    return passage


def belay_alongside(vessel):
    """
    Cancel the standing order to go alongside, leaving any course alone.

    Args:
        vessel (Vessel): The hull.

    Returns:
        had_one (bool): Whether there was an order to cancel.

    Notes:
        Separate from taking back the con, because they are separate decisions. A captain
        who takes the helm off his master in a squall has not changed his mind about where
        he is going, and finding the standing order quietly gone when he hands her back
        would be a surprise at the worst moment.

    """
    had_one = vessel.db.alongside_at is not None
    vessel.db.alongside_at = None
    return had_one


def take_her_alongside(vessel):
    """
    Carry out the standing order, now that the passage is made.

    Args:
        vessel (Vessel): The hull.

    Returns:
        berthed (Berth or None): Where she was laid, or None if she was not.

    Notes:
        **The physical checks and not the seamanship ones.** `can_dock` asks four things: is
        she close enough, slow enough, lying along the quay, and does she fit. The first
        three are a judgement on somebody's approach, and this *is* the approach - the
        master has brought her the last mile and taken the way off her, and refusing him for
        lying across a berth he is warping into would be marking his homework. The fourth is
        the water and the timber, which do not care who is steering, so it is still asked.

        Clears the order whatever happens. An order that survived being carried out would
        berth her again every time she was ever told to follow a course.

    """
    from .rooms import rig_gangway
    from .vessel import WEATHER_DECKS

    port = vessel.db.alongside_at
    vessel.db.alongside_at = None
    if port is None or not getattr(port, "berths", None):
        return None
    if vessel.docked:
        return None

    berth = berth_at(port, vessel)
    if berth is None:
        return None

    decks = [room for room in vessel.ship_rooms if room.exposure in WEATHER_DECKS]
    gangway = ()
    if decks:
        gangway = rig_gangway(min(decks, key=lambda room: room.height_of_eye), port)
    vessel.make_fast(port, berth, gangway)
    return berth


__all__ = (
    "APPROACH_RANGE",
    "UNDER_KEEL",
    "RUN_IN_SAMPLES",
    "water_along",
    "departure_from",
    "NO_ROUTE",
    "NO_MARK",
    "NO_BERTH",
    "NOT_AFLOAT",
    "ALREADY_THERE",
    "WHY",
    "Passage",
    "ports_afloat",
    "approach_for",
    "forget_approaches",
    "berth_at",
    "can_reach",
    "make_for",
    "belay_alongside",
    "take_her_alongside",
)
