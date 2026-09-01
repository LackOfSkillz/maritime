"""
The marks laid in these waters, and therefore where a ship can be told to go.

    Careenage Roads ---- Aetos Fairway ---- Gannet Roads ---- Kettle ---- Longhope
                                                                              |
                                  Outer Skerry ---- Sandhaven ---- The Brothers

**This is what makes the pond unreachable, and it is not an accident of the terrain.** A
route is planned over marks somebody laid, not over water somebody measured - see
`routes`, which argues the case at length. The pond at the head of the valley is real
water with a real shore, and there is no mark in it and no channel to it, so nothing can
be told to sail there. That is the same sentence as "there is no way in by sea", and it is
a statement this world makes about itself rather than a conclusion an algorithm draws.

It also means the answer cannot be got wrong by a clever search. A pathfinder over the
seabed would eventually find that the pond is water, and would offer a course to it.

**Where each mark lies is measured, not chosen.** Every one is found by walking seaward
from the thing it serves until there is offing enough under it, using the world's own
ground - so the marks move if the coast is ever rebuilt, and `tests/test_approaches.py`
sounds every leg to prove no course laid here crosses a beach.

**Safe-water marks throughout, because that is all this coast has earned.** A cardinal or a
lateral mark is a *claim* - pass north of me, leave me to starboard - and a claim nobody has
surveyed the ground for is worse than no mark at all. These say only "the channel is here",
which is true, and a game that later surveys the Brothers properly can say more.
"""

from ...buoyage import SAFE_WATER
from ...position import WorldPosition
from ...routes import NavigationNetwork, Waypoint
from . import islands, village
from .village import bearing_offset

#: How much water a mark stands in, in metres.
#:
#: Twelve, which is comfortably more than the deepest berth on this coast and more than
#: twice the draft of anything in the shipyard's book. A mark is a place a ship passes at
#: speed and possibly at night, so the water under it wants to be nobody's problem.
OFFING_DEPTH = 12.0

#: How far to walk looking for it, and in what steps.
#:
#: The shore here shelves so gently that six metres of water is most of a kilometre out -
#: which is why the piers are as long as they are - so twelve metres is further again:
#: sounded due west of the Long Pier it is a little under three kilometres.
#:
#: Four kilometres, which is inside `passage.APPROACH_RANGE` on purpose. A mark further from
#: its harbour than that serves no harbour, so a search allowed to run further could only
#: ever return an answer that does not work - and would do it silently.
OFFING_SEARCH_M = 4000.0
OFFING_STEP_M = 50.0

#: How far past the first clear water the mark is actually laid, in metres.
#:
#: **The first point that barely qualifies is the wrong point**, and this coast has taught
#: that three times in an afternoon: a mark laid at the exact edge of an island, a kedge
#: anchor laid at the exact edge of a rock, and a ship hauled to the exact edge of the water
#: that floats her. In every case the next metre of drift undid it.
#:
#: Two hundred and fifty metres, which is a cable and a bit - about what a master would call
#: lying *off* a place rather than close in with it. A roadstead is somewhere a ship rides
#: out a night waiting for the tide, and nobody rides out a night thirty metres from a reef.
OFFING_CLEARANCE = 250.0

#: Which way is seaward, in degrees.
#:
#: West, everywhere on this coast, and the town is the interesting case. Careenage's piers
#: are built out to the *southwest* - that is the shape of her waterfront - and walking that
#: way to find a mark was the first attempt. Sounded, the southwest is a trap: the water
#: deepens to nine metres half a kilometre out and then shoals again over a bank, five
#: metres at a mile and a half and no better at five. Due west it goes on deepening -
#: seven, nine, twelve at three kilometres, fifteen at four.
#:
#: So the fairway out of Careenage runs west and there is foul ground on the quarter, which
#: is a real piece of pilotage this coast now states rather than a constant that happened to
#: work. The figures are in `tests/test_approaches.py`.
SEAWARD_DEG = 270.0

#: The one mark that serves no harbour, and why it is where it is.
#:
#: A straight leg from Careenage to Gannet Isle is 4.5 kilometres of open water with two
#: shoal patches across it - two point seven metres a quarter of a mile off the harbour
#: mark, and three point four halfway. Either would put a laden barque on the bottom, and
#: neither is visible from a chart drawn at the reach a passage is planned at.
#:
#: So the channel goes out and round, and this is the mark it goes round by. The position
#: was found by sounding: every point on a grid was tried as a fairway and this one leaves
#: the most water under both legs - thirteen metres on the run out of the harbour and
#: twenty-two on the run up to Gannet, against minus two on the direct line. Twenty-five
#: metres under the mark itself.
#:
#: Re-derived once already, when the island marks moved seaward: a fairway is a statement
#: about the water between two places, so moving either place makes it a different question
#: and the old answer shoaled to six and a half metres. The test caught it, which is what
#: the test is for.
#:
#: **Authored, and therefore checked.** A hand-placed coordinate goes wrong silently when the
#: ground beneath it changes, so `tests/test_approaches.py` sounds every leg of this network
#: on every run and fails if any of them shoals past what the deepest hull in the shipyard
#: draws.
FAIRWAY = ("Aetos Fairway", -3800.0, 1200.0)


#: The moment every mark on this coast is sited against.
#:
#: **Zero, and fixed, because a buoy is moored.** The walk seaward stops at twelve metres of
#: water, and how deep the water is depends on the tide - so siting the marks against "now"
#: moved them between one build and the next. Careenage Roads was laid at two points a
#: quarter of a kilometre apart within an hour, purely because the tide had fallen and the
#: walk had to go further to find its depth.
#:
#: That is not a small cosmetic wobble. A network is a set of claims about where the safe
#: water runs; if the claims move, a course plotted at high water is a course to somewhere
#: else at low, and the legs `tests/test_approaches.py` sounds are not the legs a ship
#: sails. Zero is chart datum here, which is what a real chart sounds against and for
#: exactly this reason.
DATUM = 0.0


def config_now():
    """
    Returns:
        now (float): The moment the marks are sited against.

    Notes:
        Always `DATUM`, never the clock. Kept as a function rather than inlined because it
        is asked for in three places and because the name is where the reasoning lives.

    """
    return DATUM


def roads_of(name):
    """
    Args:
        name (str): The island or town.

    Returns:
        key (str): What its mark is called.

    Notes:
        "Roads" rather than "buoy" or "approach". A roadstead is the open water off a
        harbour where a ship lies waiting for wind, tide or a berth, which is exactly what
        these are and exactly what a master would call them.

    """
    return f"{name} Roads"


def offing_from(position, world, bearing=SEAWARD_DEG):
    """
    Walk seaward from a place until there is water enough for a mark.

    Args:
        position (WorldPosition): Where to start - a berth, or the head of a pier.
        world (MaritimeMapProvider): The ground.
        bearing (float, optional): Which way seaward is from here, in degrees.

    Returns:
        offing (WorldPosition): Where the mark goes.

    Notes:
        The same walk `islands.landing_position` makes, to a greater depth, and for the
        same reason: a number derived from the ground goes on being right when the ground
        changes, and a number chosen to look plausible does not.

        **Falls back on the deepest clear water it found, not on the far edge of the
        search.**
        Marching to the end of the walk was the first version and it was wrong twice over:
        it put the mark in whatever happened to be there - six metres, or a beach - and it
        put it ten kilometres from the harbour it was supposed to serve, which is further
        than `passage.APPROACH_RANGE` and therefore no use to anybody. The deepest point on
        the walk is the best answer this ground can give, and it is somewhere a ship can
        actually lie.

    """
    from ...grounding import check_hazards

    now = config_now()
    best = None
    deepest = 0.0
    out = 0.0
    while out < OFFING_SEARCH_M:
        out += OFFING_STEP_M
        east, north = bearing_offset(bearing, out)
        here = WorldPosition(position.x + east, position.y + north)

        # **Clear of the rocks, not merely over deep water.** Every mark on this coast was
        # laid inside the island it serves by a version of this that asked only how deep it
        # was: an island is an authored hazard four hundred metres across standing over
        # ground that samples at twenty metres, so the soundings said open sea and the
        # grounding check said aground. A mark a ship cannot lie at is not a mark.
        #
        # Hazards only. Sounding the seabed here as well, with the wanted depth standing in
        # for a draught, made every point on a shallow coast fail - which emptied the
        # fallback below and put the mark back where it started. The depth is what the two
        # tests underneath are for; this is only about the rocks.
        if check_hazards(here, here, OFFING_DEPTH, 0.0, 0.0, world, now) is not None:
            continue

        under = -world.terrain_z_at(here)
        if under >= OFFING_DEPTH:
            return _well_off(position, bearing, out, world, now)
        if best is None or under > deepest:
            best, deepest = here, under
    return best if best is not None else position


def _well_off(position, bearing, found, world, now):
    """
    Take the mark a little further out than the first place that would do.

    Args:
        position (WorldPosition): Where the walk started.
        bearing (float): Which way seaward is.
        found (float): How far out the first acceptable point was, in metres.
        world (MaritimeMapProvider): The ground.
        now (float): Game time.

    Returns:
        where (WorldPosition): The mark.

    Notes:
        See `OFFING_CLEARANCE`. Every step of the extra distance is checked too, so pushing
        a mark further out can never push it onto something else - which would be a very
        stupid way to fix this.

        Gives back the best it managed rather than refusing. On a coast with a bank outside
        the harbour there may be no clear water two hundred and fifty metres further out,
        and a mark close in is worth having; a mark nowhere is not.

    """
    from ...grounding import check_hazards

    best = None
    out = found
    while out <= found + OFFING_CLEARANCE:
        east, north = bearing_offset(bearing, out)
        here = WorldPosition(position.x + east, position.y + north)
        if check_hazards(here, here, OFFING_DEPTH, 0.0, 0.0, world, now) is not None:
            break
        if -world.terrain_z_at(here) < OFFING_DEPTH:
            break
        best = here
        out += OFFING_STEP_M
    return best if best is not None else position


def marks_for(world):
    """
    Every mark on this coast, and where it lies.

    Args:
        world (MaritimeMapProvider): The ground.

    Returns:
        laid (list): `(key, WorldPosition)` pairs, the town first and then the chain in
            order from south to north.

    Notes:
        The town's mark is taken from the head of her longest pier rather than from the
        waterfront, because the waterfront is a street and the pier is where the water
        begins. Walking from the wrong end would find the same offing eventually and would
        do it by crossing eight hundred metres of somebody's quay.

    """
    head = village.pier_position(village.PIERS[0])
    laid = [
        (roads_of("Careenage"), offing_from(head, world)),
        (FAIRWAY[0], WorldPosition(FAIRWAY[1], FAIRWAY[2])),
    ]

    middle = WorldPosition(0.0, 6000.0)
    found = {mark.key: mark for mark in world.landmarks_near(middle, 200_000.0)}
    for island in islands.ISLANDS:
        landmark = found.get(island["key"])
        if landmark is None:
            continue
        landing = islands.landing_position(landmark, world)
        laid.append((roads_of(island["key"]), offing_from(landing, world)))
    return laid


def channels():
    """
    Which marks have safe water between them.

    Returns:
        links (tuple): `(from, to)` pairs.

    Notes:
        A chain, and a dog-leg out of the harbour to reach it. That is the shape of the
        trade here: the islands run north from the harbour's latitude in a line, and a ship
        works up them one at a time. It is also the shape of the water - the legs run down
        the seaward side of the chain, clear of every island's foul ground, and the way out
        of Careenage goes west round two shoals before it turns north. See `FAIRWAY`.

        **Careenage reaches only Gannet, and only by way of the fairway**, so a ship bound
        for Sandhaven goes by way of all of them. That is what a chain of islands *is*, and
        it is what makes the middle of it worth calling at.

    """
    chain = ["Gannet Isle", "Kettle Rock", "Longhope", "The Brothers", "Sandhaven", "Outer Skerry"]
    links = [
        (roads_of("Careenage"), FAIRWAY[0]),
        (FAIRWAY[0], roads_of("Gannet Isle")),
    ]
    links.extend(
        (roads_of(chain[step]), roads_of(chain[step + 1])) for step in range(len(chain) - 1)
    )
    return tuple(links)


class AetosApproaches(NavigationNetwork):
    """
    The marks of this coast, laid against the shipped ground at load.

    Notes:
        Set as `MARITIME_NAVIGATION_NETWORK` and Evennia builds it once when the setting is
        first read. The walk seaward is a few hundred soundings against a cached seabed,
        which is cheap once and would not be cheap per tick - which is why this is a network
        built at load rather than a search run per course.

    """

    def __init__(self, world=None):
        """
        Args:
            world (MaritimeMapProvider, optional): The ground. Taken from the game's own
                configuration if omitted, which is how Evennia will build it.

        """
        super().__init__()
        if world is None:
            from ... import config

            world = config.map_provider()
        if world is None:
            return

        for key, position in marks_for(world):
            self.add(Waypoint(key, position, SAFE_WATER))
        laid = {mark.key for mark in self.marks()}
        for first, second in channels():
            if first in laid and second in laid:
                self.link(first, second)


__all__ = (
    "OFFING_DEPTH",
    "OFFING_SEARCH_M",
    "OFFING_STEP_M",
    "DATUM",
    "OFFING_CLEARANCE",
    "SEAWARD_DEG",
    "FAIRWAY",
    "roads_of",
    "offing_from",
    "marks_for",
    "channels",
    "AetosApproaches",
)
