"""
The six islands, and what there is to do on one.

Each is the same shape, because the point is the *pattern* rather than the places: a landing
a ship can lie alongside, somewhere to walk, and somewhere to drink. Four rooms is enough to
show every seam and few enough that six of them do not become a chore to sail between.

    the pier        a PortRoom - the one room that stands at real coordinates
    the track       ordinary rooms, which know nothing about the sea
    the bar         a vendor, and the reason a crew wants to come here
    the point       somewhere to look back at the anchorage from

**Written to the house rules, and the rules caught things.** A description holds only what
is permanently true - at any hour, in any weather, forever - so "the light comes through
green and moves about" came out of the track, because at midnight it does not, and a room
that lies every time it is read under different conditions teaches players to skim it.
"Your own ship among them" came out of the point for a different reason: it is not true of
somebody who walked here off a friend's boat.

Buildings are entered by their noun and left by `OUT`, never by a compass direction -
`GO BAR` from the track. North is a direction across open ground; it is not the act of
ducking under a roof. And the bar is named on the *track*, not only inside it, because a
thing you can only discover once you are already there is no invitation at all.

**Every island has a pier, and the pier is not decoration.** The water round these islands
does not reach four metres until a hundred to two hundred and sixty paces off the beach, so
there is nowhere on the sand a trading hull could lie. A pier is precisely the structure that
answers that: it strides out over the shallows to where the water is, and cargo is worked at
its head. Each one's length is *measured* from the ground it stands on rather than described
in general terms, so a pier is as long as it has to be and says so.

**The pier head is the whole lesson.** It is a `PortRoom`: an ordinary Evennia room that also
holds a `WorldPosition` and a berth. Walk in off the sand and it is a room like any other;
look at it from seaward and it is a set of coordinates a hull can be brought alongside. That
one room is where the two coordinate systems meet, and nothing on either side of it has to
know about the other - the rest of the island is plain rooms, and the sea is plain sea.

**Where the landings are is not invented.** Each island's position comes out of the shipped
bundle's own manifest, so a quay stands on the island it belongs to rather than at a
coordinate somebody typed. If the world is ever rebuilt, the quays move with it.

**The cargo is the second lesson.** Every island wants something and has something, so
`discharge` and `stow` at a landing are a trade rather than a demonstration - and a captain
who reads the manifest before sailing does better than one who does not.
"""

from ...cargo import commodity_named
from ...ports import Berth
from ...position import WorldPosition
from . import people
from .stock import BAR_STOCK

#: How much water a landing wants alongside, in metres.
#:
#: Enough for the sort of hull that trades between islands and no more. A quay is a place a
#: ship lies *against the land*; twenty metres under her keel means she is anchored off, not
#: alongside, and the walk ashore is a swim.
LANDING_DEPTH = 4.0

#: How far out to look for it, and in what steps, in metres. Five metres is finer than the
#: inshore soundings are spaced, so nothing is stepped over.
LANDING_SEARCH_M = 2_000.0
LANDING_STEP_M = 5.0


#: Each island: its name in the world's manifest, what its bar is called, who keeps it, and
#: what the island trades. The names come from the survey; the rest is the settlement on it.
#:
#: **Every commodity here is one the game actually carries**, and a test says so. The first
#: draft asked for hardwood, fish, cloth and copper, none of which are in the stowage table -
#: so four islands would have looked perfectly configured and traded in nothing at all, which
#: is a failure nobody notices until a player tries to sell something.
#:
#: They also form a closed round: salt to Gannet, her timber to the Skerry, his wine to
#: Sandhaven, and her salt back to the beginning. A captain who reads the manifests can run
#: the chain and come home laden, which is a better lesson about cargo than any amount of
#: documentation.
ISLANDS = (
    {
        "key": "Gannet Isle",
        "landfall": "the first of the chain, and the one every ship calls at",
        "bar": "The Long Reach",
        "keeper": "Massi",
        "keeper_desc": (
            "A broad woman with forearms like cable, who has run this bar since before "
            "anybody now drinking in it was born. She does not hurry."
        ),
        "greeting": "Massi looks up. 'Tie her off proper and come in out of the sun.'",
        "wants": "salt",
        "offers": "timber",
    },
    {
        "key": "Kettle Rock",
        "landfall": "small, steep, and louder than it looks",
        "bar": "The Kettle",
        "keeper": "Odo",
        "keeper_desc": (
            "Thin, sunburnt, and permanently amused by something he has not shared. He "
            "pours with one eye on the weather."
        ),
        "greeting": "Odo raises a cup he is already drinking from. 'Sit anywhere.'",
        "wants": "iron",
        "offers": "hides",
    },
    {
        "key": "Longhope",
        "landfall": "the biggest of them, with room for more than one ship",
        "bar": "The Fair Wind",
        "keeper": "Tibb",
        "keeper_desc": (
            "A very old man in a very clean shirt, who remembers every ship that has ever "
            "lain at the quay and most of what they were carrying."
        ),
        "greeting": "'Another one,' says Tibb, not unkindly. 'Sit down before you fall.'",
        "wants": "grain",
        "offers": "sugar",
    },
    {
        "key": "The Brothers",
        "landfall": "two humps of rock that only look like one island from seaward",
        "bar": "Between the Brothers",
        "keeper": "Nesh",
        "keeper_desc": (
            "Quiet, watchful, and about sixteen. He took over when his mother died and "
            "has not yet worked out that he is allowed to raise the prices."
        ),
        "greeting": "The boy nods at you and reaches for a cup without being asked.",
        "wants": "wool",
        "offers": "tobacco",
    },
    {
        "key": "Sandhaven",
        "landfall": "low, sandy, and the only good beach in the chain",
        "bar": "The Turtle",
        "keeper": "Ilena",
        "keeper_desc": (
            "Sharp-eyed and quick with change, running the bar and half the island's "
            "trade out of the same three feet of counter."
        ),
        "greeting": "'You'll be wanting water,' says Ilena. 'Everybody wants water first.'",
        "wants": "wine",
        "offers": "salt",
    },
    {
        "key": "Outer Skerry",
        "landfall": "the last of them, and the one ships leave for the outward passage",
        "bar": "The Last House",
        "keeper": "Garrow",
        "keeper_desc": (
            "A wrecked-looking man who was a bosun for thirty years and has the hands to "
            "prove it. He will tell you about the passage out if you let him."
        ),
        "greeting": "'Outward bound?' says Garrow. 'Everyone here is outward bound.'",
        "wants": "timber",
        "offers": "wine",
    },
)


def landing_position(landmark, world):
    """
    Where a ship lies to work an island.

    Args:
        landmark (Landmark): The island, from the world's own manifest.
        world (MaritimeMapProvider): The ground, asked where the water starts.

    Returns:
        position (WorldPosition): The berth, just off the beach.

    Notes:
        **Found by walking out from the island until the water is deep enough**, rather than
        by taking a fraction of its reach. A fraction is a guess about the shape of a
        foreshore, and it was wrong: one and a third of the reach put every quay in
        twenty-one metres, which is a ship anchored well offshore rather than one lying
        against a quay, and the walk ashore would have been a swim.

        Walking finds the right spot on an island of any size and any steepness, and keeps
        finding it if the world is ever rebuilt. That is the difference between a number
        that happens to work and one that is derived.

        Seaward is west on this coast, which is the side a ship comes from.

    """
    step = LANDING_STEP_M
    out = 0.0
    while out < LANDING_SEARCH_M:
        out += step
        here = WorldPosition(landmark.x - out, landmark.y)
        if -world.terrain_z_at(here) >= LANDING_DEPTH:
            return here
    # Nothing deep enough anywhere near it - hand back the far edge rather than a point on
    # the beach, so a badly placed island gives an unusable berth instead of a dry one.
    return WorldPosition(landmark.x - LANDING_SEARCH_M, landmark.y)


def pier_length(landmark, world):
    """
    How far a pier has to reach before there is water enough at the end of it.

    Args:
        landmark (Landmark): The island.
        world (MaritimeMapProvider): The ground.

    Returns:
        metres (float): From the waterline to the berth.

    Notes:
        Measured, so a pier is as long as the shoal it crosses. Describing every island's
        pier as "long" would be writing round the fact that they differ by a factor of two
        and a half - Outer Skerry is steep-to and wants a hundred paces, while Longhope
        shelves so gently it wants two hundred and sixty.

    """
    berth = landing_position(landmark, world)
    shore = landmark.x
    step = LANDING_STEP_M
    while shore > berth.x:
        if world.terrain_z_at(WorldPosition(shore, landmark.y)) < 0.0:
            break
        shore -= step
    return max(0.0, shore - berth.x)


def _pier_desc(island, metres):
    """
    Args:
        island (dict): One entry from `ISLANDS`.
        metres (float): How far the pier reaches over the water.

    Returns:
        desc (str): What standing on the pier head is like.

    """
    strides = int(round(metres / 0.8 / 10.0)) * 10
    return (
        f"Some {strides} strides of blackened timber, striding out from the beach on legs "
        "of driftwood and coral rubble to where the water is deep enough to float a laden "
        "hull. The planks are worn pale in two tracks by generations of barrels being "
        "rolled up and down them. At the head there is room to work cargo, a pair of "
        "bollards, and a ladder going down into green water."
    )


def rooms_for(island, landmark, world):
    """
    The four rooms of one island.

    Args:
        island (dict): One entry from `ISLANDS`.
        landmark (Landmark): Where it is, from the manifest.
        world (MaritimeMapProvider): The ground, for siting the quay.

    Returns:
        specs (list): Room specifications, the landing first.

    """
    name = island["key"]
    where = landing_position(landmark, world)
    return [
        {
            "key": f"{name} Pier",
            "desc": _pier_desc(island, pier_length(landmark, world)),
            # The pier is where a landing happens, so it is the room that records one.
            #
            # Named relative to this package rather than spelled out, so the contrib still
            # works when it is installed somewhere other than where it was written - which
            # is the ordinary case for a contrib and the whole point of the rule.
            "typeclass": f"{__package__}.typeclasses.IslandLanding",
            "landmark": name,
            "landmark_height": landmark.height,
            "berth": Berth(
                key=f"{name.lower().replace(' ', '_')}_quay",
                position=where,
                heading=0.0,
                max_length=40.0,
                max_beam=12.0,
                max_draft=LANDING_DEPTH,
            ),
        },
        {
            "key": f"{name} Track",
            "desc": (
                "The track runs up off the beach under trees that meet overhead. It is "
                "sand underfoot for the first part and then bare rock, polished by "
                "generations of bare feet going up and rather less steadily back down. "
                f"A roof of palm thatch stands off to one side, which is {island['bar']}."
            ),
        },
        {
            "key": island["bar"],
            "desc": (
                "A roof of palm thatch on four posts, open on every side. The counter is "
                "a single slab of hardwood, scarred with the names of ships and deepest "
                "where elbows have rested on it for forty years. Bottles stand in a rack "
                "behind it, and a water barrel in the corner is what most people want "
                "first."
            ),
        },
        {
            "key": f"{name} Point",
            "desc": (
                "The high end of the island, where the trees give out and the rock goes "
                "bare. The whole anchorage lies below, near enough to pick out a hull by "
                "her rig, and past it the next island in the chain stands up out of the "
                "water. A cairn of ballast stones has been built here, added to by every "
                "crew that has ever climbed up with nothing better to do."
            ),
        },
    ]


def paths_for(island):
    """
    Args:
        island (dict): One entry from `ISLANDS`.

    Returns:
        paths (tuple): `(from, to, out, back)` for this island's exits.

    """
    name = island["key"]
    return (
        (f"{name} Pier", f"{name} Track", "shore", "pier"),
        (f"{name} Track", island["bar"], "bar", "out"),
        (f"{name} Track", f"{name} Point", "point", "track"),
    )


def stock_the_bar(island, room):
    """
    Put a keeper behind the counter.

    Args:
        island (dict): One entry from `ISLANDS`.
        room (Object): The bar.

    Returns:
        found (tuple): `(keeper, made_now)`.

    """
    return people.make(
        key=island["keeper"],
        description=island["keeper_desc"],
        stock=BAR_STOCK,
        greeting=island["greeting"],
        home=room,
    )


def trade_at(island):
    """
    What an island will buy and what it sells.

    Args:
        island (dict): One entry from `ISLANDS`.

    Returns:
        trade (tuple): `(wants, offers)` as `Commodity` records, or Nones if this game's
            stowage table does not carry them.

    Notes:
        Looked up in the game's own commodity table rather than invented here, so an island
        never asks for a cargo the ship cannot legally carry. A game with its own table gets
        islands that trade in its goods without anything here changing.

    """
    return (commodity_named(island["wants"]), commodity_named(island["offers"]))


__all__ = (
    "LANDING_DEPTH",
    "LANDING_SEARCH_M",
    "LANDING_STEP_M",
    "ISLANDS",
    "landing_position",
    "pier_length",
    "rooms_for",
    "paths_for",
    "stock_the_bar",
    "trade_at",
)
