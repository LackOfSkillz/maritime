"""
The rooms of the example world, and the command that builds them.

**Land is ordinary rooms with ordinary exits.** An island is a little graph you walk
around exactly as you would walk around anywhere else in an Evennia game; the maritime
system knows nothing about it and does not need to. What joins the two is one room per
waterfront - a `PortRoom` - which is an ordinary room that also happens to stand at a
world position and offer a berth.

That is the whole of the join, and it is Law 7: a physical relationship creates a
traversal. Bring a boat alongside and a gangway is rigged as two real exits between her
deck and the quay. Walk across it. Let go the lines and it is deleted. Nobody is
teleported, and neither side had to learn about the other.

    Pond Shore  --  Water Meadow  --  River Head
                                          |
                                    (row down the river)
                                          |
                    Stone Quay  --  Harbour Town  --  Ferry Steps

    Stone Quay  ==  six islands, eastward, each a fair sail from the last

The gap in the middle is deliberate. There is no path from the river head to the harbour:
the river *is* the road, and rowing down it is how you get there. Rowing back up it is a
different afternoon, which is the lesson.

"""

from evennia.utils import create
from evennia.utils.search import search_object

from ..ports import Berth
from ..position import WorldPosition
from ..rooms import PortRoom, ShipRoom
from ..typeclasses import Vessel
from ..vessel import BELOW_WATERLINE, INTERIOR, OPEN
from .craft import CRAFT, outfit
from .geography import ISLANDS, POND_CENTRE, RIVER, harbour_position

#: Where the sloop's quay stands, out on the shelf where there is water enough for her.
STONE_QUAY = WorldPosition(400.0, 0.0)

#: Where the canoe lands, in the last reach of the river above the bar.
FERRY_STEPS = WorldPosition(-200.0, 67.0)

#: Where the kayak is launched, inside the pond and clear of the bank.
POND_LANDING = WorldPosition(POND_CENTRE.x, POND_CENTRE.y - 450.0)

#: The mainland, as rooms. Each is a key, a description, whether it is a waterfront,
#: and where that waterfront stands.
MAINLAND = (
    {
        "key": "Pond Shore",
        "desc": (
            "A shelf of trodden grass runs down to a wide, still sheet of water. There "
            "is not a ripple on it that the wind did not put there. A kayak lies pulled "
            "up on the turf with its blade beside it."
        ),
        "berth": Berth(
            key="the turf landing",
            position=POND_LANDING,
            heading=0.0,
            max_length=8.0,
            max_beam=2.0,
            max_draft=1.5,
        ),
    },
    {
        "key": "The Water Meadow",
        "desc": (
            "Wet grass between the pond and the river, cut through by the channel that "
            "joins them. Cattle have been here. East, the ground falls away towards the "
            "sound of running water."
        ),
    },
    {
        "key": "River Head",
        "desc": (
            "The river starts in earnest here, narrow and quick between cut banks. A "
            "canoe is drawn up on the shingle. Downstream it bends away south-east and "
            "is gone; there is no path beside it."
        ),
        "berth": Berth(
            key="the shingle",
            position=RIVER[0],
            heading=115.0,
            max_length=8.0,
            max_beam=2.0,
            max_draft=1.5,
        ),
    },
    {
        "key": "Ferry Steps",
        "desc": (
            "Stone steps down to the last reach of the river, where the water goes "
            "brown and slow and starts to smell of the sea. The town is up the hill."
        ),
        "berth": Berth(
            key="the ferry steps",
            position=FERRY_STEPS,
            heading=125.0,
            max_length=12.0,
            max_beam=3.0,
            max_draft=2.0,
        ),
    },
    {
        "key": "Harbour Town",
        "desc": (
            "A single street of tarred houses between the river and the sea, with a "
            "chandler at one end and a public house at the other. Everyone here can "
            "tell you the weather and nobody agrees about it."
        ),
    },
    {
        "key": "Stone Quay",
        "desc": (
            "A short stone quay standing out into deep water, bollards worn smooth and "
            "a tide-line of weed a foot below the coping. Eastward the sea runs away "
            "flat, and the islands are out there somewhere."
        ),
        "berth": Berth(
            key="stone quay",
            position=STONE_QUAY,
            heading=0.0,
            max_length=30.0,
            max_beam=9.0,
            max_draft=6.0,
        ),
    },
)

#: Which mainland rooms are walkable from which, and in which direction. The river
#: head and the ferry steps are pointedly not among them.
MAINLAND_PATHS = (
    ("Pond Shore", "The Water Meadow", "east", "west"),
    ("The Water Meadow", "River Head", "east", "west"),
    ("Ferry Steps", "Harbour Town", "up", "down"),
    ("Harbour Town", "Stone Quay", "east", "west"),
)

#: What each island's three rooms are called and look like. The same shape everywhere,
#: because an example that made every island different would be teaching scenery rather
#: than structure.
ISLAND_ROOMS = (
    (
        "{name} Quay",
        "A stub of stone quay with a ring bolt and a boat's worth of shelter. The "
        "island rises behind it.",
    ),
    (
        "{name} Track",
        "A path worn between rocks and sea thrift, climbing away from the water.",
    ),
    (
        "{name} Head",
        "The high point of the island, all wind and horizon. From here you can count "
        "the other islands strung out east and west.",
    ),
)


def build():
    """
    Build the example world, or return it if it is already there.

    Returns:
        built (dict): `{"mainland": {...}, "islands": {...}, "craft": {...}}`.

    Notes:
        Idempotent. Everything is found by key first and only created if missing, so
        a half-finished attempt can be re-run without leaving two of anything.

        Returns what it made and says nothing. The command is what talks - which the
        domain-purity check insisted on and which is better anyway, since a caller
        that wanted the rooms had to go and find them again otherwise.

    """
    mainland = {spec["key"]: _room(spec) for spec in MAINLAND}
    _link(mainland, MAINLAND_PATHS)

    islands = {}
    for island in ISLANDS:
        islands[island[0]] = _island(island)

    craft = {
        "kayak": _launch("kayak", mainland["Pond Shore"]),
        "canoe": _launch("canoe", mainland["River Head"]),
        "sloop": _launch("sloop", mainland["Stone Quay"]),
    }

    return {"mainland": mainland, "islands": islands, "craft": craft}


def _room(spec):
    """
    Find or make one room.

    Args:
        spec (dict): One entry from `MAINLAND`, or an equivalent.

    Returns:
        room (Object): The room, a `PortRoom` if it has a berth.

    """
    wanted = PortRoom if spec.get("berth") else "evennia.objects.objects.DefaultRoom"
    existing = [found for found in search_object(spec["key"]) if found.destination is None]
    if existing:
        return existing[0]

    room = create.create_object(wanted, key=spec["key"])
    room.db.desc = spec["desc"]
    if spec.get("berth"):
        room.maritime_position = spec["berth"].position
        room.add_berth(spec["berth"])
    return room


def _link(rooms, paths):
    """
    Cut the exits between rooms.

    Args:
        rooms (dict): Key to room.
        paths (iterable): `(from, to, out, back)` tuples.

    Notes:
        Ordinary exits both ways. A gangway is made the same way when a boat comes
        alongside, which is the point of Law 7 - there is no second kind of
        traversal to learn.

    """
    for start, end, out, back in paths:
        _exit(rooms[start], rooms[end], out)
        _exit(rooms[end], rooms[start], back)


def _exit(source, destination, key):
    """
    Args:
        source (Object): Where it leads from.
        destination (Object): Where it leads to.
        key (str): What it is called.

    Returns:
        exit (Object): The exit, made or found.

    """
    for found in source.contents:
        if found.destination == destination and found.key == key:
            return found
    return create.create_object(
        "evennia.objects.objects.DefaultExit",
        key=key,
        location=source,
        destination=destination,
    )


def _island(island):
    """
    Build one island: a quay, a track and a summit.

    Args:
        island (tuple): `(name, x, y, reach)`.

    Returns:
        rooms (dict): Key to room, quay first.

    """
    name = island[0]
    keys = [shape[0].format(name=name) for shape in ISLAND_ROOMS]
    quay_spec = {
        "key": keys[0],
        "desc": ISLAND_ROOMS[0][1].format(name=name),
        "berth": Berth(
            key=f"{name.lower()} quay",
            position=harbour_position(island),
            heading=0.0,
            max_length=30.0,
            max_beam=9.0,
            max_draft=4.5,
        ),
    }
    rooms = {keys[0]: _room(quay_spec)}
    for key, (_shape, desc) in zip(keys[1:], ISLAND_ROOMS[1:]):
        rooms[key] = _room({"key": key, "desc": desc.format(name=name)})

    _link(rooms, ((keys[0], keys[1], "up", "down"), (keys[1], keys[2], "up", "down")))
    return rooms


def _launch(which, quay):
    """
    Build one boat and lay her alongside.

    Args:
        which (str): A key from `CRAFT`.
        quay (PortRoom): Where she starts.

    Returns:
        vessel (Vessel): The boat, made fast.

    """
    spec = CRAFT[which]
    afloat = [found for found in search_object(spec["key"]) if isinstance(found, Vessel)]
    if afloat:
        return afloat[0]

    vessel = outfit(create.create_object(Vessel, key=spec["key"]), spec)
    vessel.maritime_position = quay.berths[0].position

    decks = spec.get("decks")
    if decks:
        exposures = {"interior": INTERIOR, "below_waterline": BELOW_WATERLINE}
        for key, level, exposure, height, hold, desc in decks:
            room = create.create_object(ShipRoom, key=key)
            room.vessel = vessel
            room.deck_level = level
            room.exposure = exposures.get(exposure, exposure)
            room.db.desc = desc
            if height:
                room.height_of_eye = height
            if hold:
                room.hold_capacity = hold
    else:
        room = create.create_object(ShipRoom, key=spec["compartment"])
        room.vessel = vessel
        room.exposure = OPEN
        room.db.desc = spec["compartment_desc"]
        room.height_of_eye = 1.0

    vessel.make_fast(quay, quay.berths[0])
    return vessel
