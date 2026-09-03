"""
Who else is out there, and why.

An empty sea is cheap and it is also dull. `strategic` made a background hull affordable -
a record and one division, whatever she has been doing - and this is what fills the sea with
them: merchants on passages that make sense, fishermen working off their own coast, patrols
on their beat, and raiders who go where the money is.

**The traffic is explained rather than scattered.** A merchant's passage is drawn from the
markets: she loads where a thing is cheap and carries it where it is dear, which is the same
sum a player makes and answered from the same data. Nobody authored a shipping lane. The lane
is what the ports are, and a builder who changes what a place exports changes who sails past
it.

**A raider hunts value, not traffic.** `DECISIONS.md` makes that point twice because it is
one decision seen from two sides, and this is the side where it costs something: the danger
on a route is what is being carried along it, so a captain choosing a rich cargo has chosen a
dangerous passage without anybody telling him so. A raider who hunted traffic would spend the
game chasing grain coasters, and choosing a cargo would mean nothing.

**Nothing here materialises anybody.** It says who is out there and where they have got to;
turning one into a real hull is `strategic.materialise`, and *deciding* to is the game's,
because only a game knows whether its players are in a state to be interrupted.

"""

from dataclasses import dataclass, field

from .economy import WORTH
from .results import Result
from .routes import Route, Waypoint
from .strategic import PASSAGE_SPEED, Passage, StrategicVessel

#: What kinds of ship are out there.
MERCHANT = "merchant"
FISHERMAN = "fisherman"
PATROL = "patrol"
RAIDER = "raider"
KINDS = (MERCHANT, FISHERMAN, PATROL, RAIDER)

#: What each makes good, in metres a second.
#:
#: A patrol and a raider are both faster than the trade, which is the whole reason either of
#: them is worth being afraid of - a merchant who could outrun a raider would never meet one.
SPEEDS = {
    MERCHANT: PASSAGE_SPEED,
    FISHERMAN: PASSAGE_SPEED * 0.8,
    PATROL: PASSAGE_SPEED * 1.4,
    RAIDER: PASSAGE_SPEED * 1.5,
}

#: How far off a fisherman works, in metres.
#:
#: Ten miles or so. Far enough to be out of sight of the quay and near enough to be home
#: before dark, which is what an inshore boat actually did.
FISHING_GROUND = 18_000.0

#: How near a background ship has to be to be worth anybody's attention, in metres.
#:
#: Twelve miles - beyond the horizon from a masthead, so a game materialising at this range
#: has her in existence before anybody could have seen her arrive.
WORTH_NOTICING = 22_000.0

NO_MARKETS = "no_markets"
NO_TRADE = "no_trade"
NOWHERE_TO_GO = "nowhere_to_go"


@dataclass(frozen=True)
class Anchorage:
    """
    A place a background ship sails from and to.

    Attributes:
        key (str): What it is called.
        position (WorldPosition): Where it is.
        market (Market): What it sells and what it wants.

    Notes:
        Deliberately not a `Port`. A port is rooms, berths and a quay - a real place a player
        walks about in - and the background world needs none of that. Requiring one would
        mean building a harbour before a merchantman could sail past it.

    """

    key: str
    position: object
    market: object = None


@dataclass(frozen=True, kw_only=True)
class TradeRoute(Result):
    """
    A passage worth making, and what makes it worth making.

    Attributes:
        commodity (str): What she is carrying.
        origin (Anchorage): Where she loaded.
        destination (Anchorage): Where she is bound.
        margin (int): What a tonne gains over the passage, in the smallest coin.

    """

    commodity: str = ""
    origin: Anchorage = None
    destination: Anchorage = None
    margin: int = 0


@dataclass(frozen=True, kw_only=True)
class Encounter(Result):
    """
    Somebody in the offing.

    Attributes:
        handle (int): Her handle in the fleet.
        record (StrategicVessel): Her summary.
        fix (Fix): Where she has got to.
        distance (float): How far off, in metres.

    """

    handle: int = 0
    record: StrategicVessel = None
    fix: object = None
    distance: float = 0.0


def routes_worth_sailing(anchorages, worth=None):
    """
    Every passage the markets make worth making.

    Args:
        anchorages (iterable): `Anchorage` objects with markets on them.
        worth (dict, optional): The standing worths.

    Returns:
        routes (tuple): `TradeRoute` objects, richest first.

    Notes:
        **Nobody authored a shipping lane.** A lane is what the ports are: somewhere with a
        surplus, somewhere with a shortage, and a commodity both of them have an opinion
        about. Change what a place exports and the traffic past it changes, which is what a
        builder would expect and what a table of authored routes would not do.

    """
    from .economy import price_at

    table = WORTH if worth is None else worth
    places = [one for one in anchorages if one.market is not None]

    found = []
    for origin in places:
        for commodity in origin.market.exports:
            if commodity not in table:
                continue
            loaded = price_at(origin.market, commodity, 1.0, table).smallest
            for destination in places:
                if destination is origin:
                    continue
                landed = price_at(destination.market, commodity, 1.0, table).smallest
                if landed <= loaded:
                    continue
                found.append(
                    TradeRoute(
                        success=True,
                        commodity=commodity,
                        origin=origin,
                        destination=destination,
                        margin=landed - loaded,
                    )
                )
    return tuple(sorted(found, key=lambda route: -route.margin))


def a_merchant_on(route, name, departed=0.0, speed=None, tonnes=40.0):
    """
    A trader making one of those passages.

    Args:
        route (TradeRoute): The passage she is making.
        name (str): What she is called.
        departed (float, optional): When she sailed.
        speed (float, optional): What she makes good.
        tonnes (float, optional): How much she is carrying.

    Returns:
        record (StrategicVessel): Her summary.

    """
    marks = (
        Waypoint(key=route.origin.key, position=route.origin.position),
        Waypoint(key=route.destination.key, position=route.destination.position),
    )
    return StrategicVessel(
        key=name,
        passage=Passage(
            route=Route(waypoints=marks),
            speed=SPEEDS[MERCHANT] if speed is None else speed,
            departed=departed,
        ),
        cargo=((route.commodity, float(tonnes)),),
    )


def a_fisherman_off(anchorage, name, departed=0.0, out=FISHING_GROUND):
    """
    A boat working her own coast.

    Args:
        anchorage (Anchorage): Where she belongs.
        name (str): What she is called.
        departed (float, optional): When she went out.
        out (float, optional): How far off she works, in metres.

    Returns:
        record (StrategicVessel): Her summary.

    Notes:
        Out and home, which is why her route closes on itself. She is the traffic that makes
        a coast feel inhabited rather than the traffic anybody is going to fight, and she
        costs the same as any other record: three numbers and a route.

    """
    home = Waypoint(key=anchorage.key, position=anchorage.position)
    ground = Waypoint(key=f"off {anchorage.key}", position=anchorage.position.moved(180.0, out))
    return StrategicVessel(
        key=name,
        length=9.0,
        beam=3.0,
        passage=Passage(
            route=Route(waypoints=(home, ground, home)),
            speed=SPEEDS[FISHERMAN],
            departed=departed,
        ),
    )


def a_patrol_between(anchorages, name, departed=0.0):
    """
    A ship working a beat up and down a coast.

    Args:
        anchorages (iterable): The places she calls at, in order.
        name (str): What she is called.
        departed (float, optional): When she sailed.

    Returns:
        record (StrategicVessel or None): Her summary, or None if there is no beat.

    Notes:
        Her route closes, because a beat that did not would be a ship leaving the station
        she was put there to keep.

    """
    places = list(anchorages)
    if len(places) < 2:
        return None

    marks = [Waypoint(key=one.key, position=one.position) for one in places]
    marks.append(marks[0])
    return StrategicVessel(
        key=name,
        passage=Passage(
            route=Route(waypoints=tuple(marks)), speed=SPEEDS[PATROL], departed=departed
        ),
    )


def richest_route(routes):
    """
    Args:
        routes (iterable): `TradeRoute` objects.

    Returns:
        route (TradeRoute or None): The one carrying the most value.

    """
    best = None
    for route in routes:
        if best is None or route.margin > best.margin:
            best = route
    return best


def a_raider_on(route, name, departed=0.0):
    """
    Somebody waiting on the richest passage there is.

    Args:
        route (TradeRoute): The passage she is hunting.
        name (str): What she is called.
        departed (float, optional): When she took up the station.

    Returns:
        record (StrategicVessel): Her summary.

    Notes:
        **She hunts the route, not the ships on it.** Which is the whole of the design: the
        danger on a passage is what is being carried along it, so a captain who loads
        tobacco has chosen a dangerous voyage without anybody telling him he has. A raider
        who hunted traffic instead would spend the game chasing grain coasters, and choosing
        a cargo would mean nothing.

        She works the passage rather than sitting on one end of it, because a raider parked
        on a harbour mouth is a blockade and a blockade is a different thing.

    """
    marks = (
        Waypoint(key=route.origin.key, position=route.origin.position),
        Waypoint(key=route.destination.key, position=route.destination.position),
        Waypoint(key=route.origin.key, position=route.origin.position),
    )
    return StrategicVessel(
        key=name,
        passage=Passage(route=Route(waypoints=marks), speed=SPEEDS[RAIDER], departed=departed),
    )


def danger_on(route, worth=None):
    """
    How much a passage is worth robbing.

    Args:
        route (TradeRoute): The passage.
        worth (dict, optional): The standing worths.

    Returns:
        danger (int): What a tonne of what she carries is worth, in the smallest coin.

    Notes:
        The number a game ranks its raiders by, and the number a player is implicitly
        choosing when he picks a cargo. Reported rather than acted on: whether a raider
        actually appears is a game's decision about pacing, and this contrib does not get to
        interrupt somebody's evening.

    """
    table = WORTH if worth is None else worth
    return table.get(route.commodity, 0)


@dataclass(frozen=True, kw_only=True)
class PopulationResult(Result):
    """
    What was put out there.

    Attributes:
        put_out (dict): Kind to the handles entered.
        lanes (tuple): The trade routes the markets made.

    """

    put_out: dict = field(default_factory=dict)
    lanes: tuple = field(default_factory=tuple)


def populate(fleet, anchorages, merchants=6, fishermen=4, patrols=1, raiders=1, worth=None):
    """
    Fill the background world.

    Args:
        fleet (Fleet): The register to put them in.
        anchorages (iterable): The places they sail from and to.
        merchants (int, optional): How many traders.
        fishermen (int, optional): How many inshore boats.
        patrols (int, optional): How many patrols.
        raiders (int, optional): How many raiders.
        worth (dict, optional): The standing worths.

    Returns:
        result (Result): What was put out there, by kind.

    Notes:
        Every one of them is a record and a route, so a hundred of them cost what one costs
        to advance - which is the property `strategic` exists to protect and the reason this
        can afford to put a sea full of ships in front of somebody.

        Departures are staggered by index rather than rolled, so the same world built twice
        is the same world. A background fleet that shuffled itself on every restart would
        make a bug in it impossible to reproduce.

    """
    places = list(anchorages)
    if not places:
        return PopulationResult(success=False, code=NO_MARKETS)

    lanes = routes_worth_sailing(places, worth)
    if not lanes and merchants:
        return PopulationResult(success=False, code=NO_TRADE)

    put_out = {kind: [] for kind in KINDS}

    for number in range(max(0, int(merchants))):
        lane = lanes[number % len(lanes)]
        record = a_merchant_on(lane, f"{lane.commodity} trader {number + 1}", number * 900.0)
        put_out[MERCHANT].append(fleet.enter(record))

    for number in range(max(0, int(fishermen))):
        home = places[number % len(places)]
        record = a_fisherman_off(home, f"{home.key} boat {number + 1}", number * 600.0)
        put_out[FISHERMAN].append(fleet.enter(record))

    for number in range(max(0, int(patrols))):
        record = a_patrol_between(places, f"patrol {number + 1}", number * 1800.0)
        if record is not None:
            put_out[PATROL].append(fleet.enter(record))

    richest = richest_route(lanes)
    if richest is not None:
        for number in range(max(0, int(raiders))):
            record = a_raider_on(richest, f"raider {number + 1}", number * 2400.0)
            put_out[RAIDER].append(fleet.enter(record))

    return PopulationResult(
        success=True,
        put_out={kind: tuple(handles) for kind, handles in put_out.items()},
        lanes=lanes,
    )


def encounters(fleet, position, now, within=WORTH_NOTICING):
    """
    Who is near enough to matter.

    Args:
        fleet (Fleet): The background world.
        position (WorldPosition): Where to look from.
        now (float): Game time in seconds.
        within (float, optional): How far to look, in metres.

    Returns:
        near (tuple): `Encounter` objects, nearest first.

    Notes:
        **Nothing is materialised here.** This says who is out there and where they have got
        to; turning one into a real hull is `strategic.materialise`, and deciding to is the
        game's, because only a game knows whether its players are in a state to be
        interrupted by a strange sail.

        One pass over the fleet, which is what `Fleet.fixes` costs however long any of them
        has been left alone.

    """
    if position is None:
        return ()

    found = []
    for handle, fix in fleet.fixes(now).items():
        if fix.position is None:
            continue
        off = position.horizontal_distance_to(fix.position)
        if off > within:
            continue
        found.append(
            Encounter(
                success=True,
                handle=handle,
                record=fleet.get(handle),
                fix=fix,
                distance=off,
            )
        )
    return tuple(sorted(found, key=lambda seen: seen.distance))
