"""
The Aetos coast ashore: a town, six islands, and the people who keep their counters.

This is the worked example of the thing that is otherwise only described - how a walkable
Evennia area sits inside a maritime world without either half having to know much about the
other. Run `build_aetos` as a builder and it makes the lot, once, and again safely.

    Careenage       53 rooms at the head of the harbour, and three piers
    six islands     four rooms each, a pier apiece, and a bar
    eighteen people behind counters, with a hundred-odd things between them

**The seam is one room type.** A `PortRoom` is an ordinary Evennia room that also holds a
`WorldPosition` and a berth. Everything on the landward side of it is rooms and exits like
anywhere else; everything seaward is the maritime coordinate system. Nine rooms in this
world are `PortRoom`s and the other eighty are not, and nothing else had to be taught about
the sea.

**Nothing here is special-cased into the contrib.** The build uses the ordinary public
interface - `PortRoom`, `Berth`, `add_berth`, `create_object` - so a game can write its own
land the same way by reading this file rather than by importing it.

**Idempotent, because a build command nobody dares run twice is a build command nobody
runs.** Every room, exit and person is found before it is made. Running it again on a live
world adds nothing and moves nothing.
"""

from evennia.utils import create
from evennia.utils.search import search_object

from ...client.context import ASHORE_CATEGORY, ASHORE_TAG
from . import islands, people, stock, village

#: What an ordinary land room is.
#:
#: Not a plain `DefaultRoom`. A room ashore has two jobs beyond being a room: it keeps the
#: land map current for anybody standing in it, and it carries the commands that only make
#: sense where there is a counter. Both were written and neither was wired, so `buy` existed
#: in no cmdset and the map redrew only when a sheet happened to arrive - which is to say
#: the shops were unreachable and the map was a photograph.
LAND_ROOM = f"{__package__}.typeclasses.ShoreStreet"

#: What a room with a berth in it is.
#:
#: A `PortRoom` and a shore room both, because it is both. It holds a position and a berth,
#: which is the maritime half; and it is a place somebody stands and walks about in, which is
#: the landward half and is what keeps the land map current under their feet.
#:
#: It was a plain `PortRoom`, and the seam showed: walking onto an island landing drew a map
#: and walking down Careenage's own pier drew "nowhere to map", because the island rooms were
#: shore rooms and the town's quays were not.
QUAY_ROOM = f"{__package__}.typeclasses.IslandLanding"

#: What an exit is, on the same reasoning.
EXIT = "evennia.objects.objects.DefaultExit"


def build(world=None, on_report=None):
    """
    Make the whole coast ashore.

    Args:
        world (MaritimeMapProvider, optional): The ground. Used to site the island piers
            against real water and to keep berths from promising depths they lack. Taken
            from the game's own configuration if omitted.
        on_report (callable, optional): Called with a line of plain text per stage.

    Returns:
        made (dict): `rooms`, `exits` and `people` actually created this run - zero for
            every one of them on a second run, which is the point.

    """
    if world is None:
        from ... import config

        world = config.map_provider()

    tally = {"rooms": 0, "exits": 0, "people": 0}

    _say(on_report, "maritime: building Careenage...")
    made = _place(village.rooms(world), village.paths(), tally)
    _staff_the_village(made, tally)

    marks = {mark.key: mark for mark in world.landmarks_near(_middle(), 200_000.0)}
    for island in islands.ISLANDS:
        mark = marks.get(island["key"])
        if mark is None:
            _say(on_report, f"maritime: no {island['key']} in this world - skipped")
            continue
        _say(on_report, f"maritime: building {island['key']}...")
        here = _place(islands.rooms_for(island, mark, world), islands.paths_for(island), tally)
        bar = here.get(island["bar"])
        if bar is not None:
            _, made_now = islands.stock_the_bar(island, bar)
            tally["people"] += 1 if made_now else 0

    start = starting_room()
    if start is not None:
        _say(
            on_report,
            f"maritime: new players start at {start.key} (#{start.id}). Put that in "
            "settings as START_LOCATION to send them there.",
        )

    _say(
        on_report,
        f"maritime: {tally['rooms']} rooms, {tally['exits']} exits and "
        f"{tally['people']} people made.",
    )
    return tally


def starting_room():
    """
    Where a new character should be put down.

    Returns:
        room (Object or None): The room, or None if the world has not been built.

    Notes:
        Inland and upstream on purpose. The town is what a player arrives at rather than
        what they start in, so the creek landing is the door: a boat comes down the water
        and the place is discovered from it rather than handed over.

        Evennia wants `START_LOCATION` as a dbref in settings and cannot be told one by a
        build command, so this returns the room and the build prints it. A number nobody
        reports is a number nobody sets.

    """
    for found in search_object(village.STARTING_ROOM):
        if found.destination is None:
            return found
    return None


def _middle():
    """
    Returns:
        position (WorldPosition): The origin, for asking a world what is near.

    """
    from ...position import WorldPosition

    return WorldPosition(0.0, 0.0)


def _place(specs, paths, tally):
    """
    Make a set of rooms and join them.

    Args:
        specs (iterable): Room specifications.
        paths (iterable): `(from, to, out, back)` joins.
        tally (dict): Counters to add to.

    Returns:
        rooms (dict): Room key to object.

    """
    rooms = {}
    for spec in specs:
        room, fresh = _room(spec)
        rooms[spec["key"]] = room
        tally["rooms"] += 1 if fresh else 0

    for start, end, out, back in paths:
        if start not in rooms or end not in rooms:
            continue
        tally["exits"] += 1 if _exit(rooms[start], rooms[end], out) else 0
        tally["exits"] += 1 if _exit(rooms[end], rooms[start], back) else 0
    return rooms


def _room(spec):
    """
    Args:
        spec (dict): `key`, `desc`, and optionally `berth`.

    Returns:
        found (tuple): `(room, made_now)`.

    Notes:
        A room with a berth is a `PortRoom` and stands at real coordinates; everything else
        is an ordinary room that has never heard of the sea.

        **Every room here is tagged as maritime land**, which is what lets a game choose to
        keep the panel up ashore. The tag says "this place belongs to the coast" and nothing
        more; whether that means anything is `MARITIME_ASHORE_PANEL`'s business, and off by
        default. Tagging is the world describing itself, which is safe; deciding what an
        interface does about it is the game's, which is why the two are separate.

    """
    wanted = spec.get("typeclass") or (QUAY_ROOM if spec.get("berth") else LAND_ROOM)
    for found in search_object(spec["key"]):
        if found.destination is None:
            return (found, False)

    room = create.create_object(wanted, key=spec["key"])
    room.db.desc = spec["desc"]
    room.tags.add(ASHORE_TAG, category=ASHORE_CATEGORY)
    if spec.get("landmark"):
        room.db.landmark = spec["landmark"]
        room.db.landmark_height = spec.get("landmark_height", 0.0)
    if spec.get("berth"):
        room.maritime_position = spec["berth"].position
        room.add_berth(spec["berth"])
    return (room, True)


def _exit(source, destination, key):
    """
    Args:
        source (Object): Where it leads from.
        destination (Object): Where it leads to.
        key (str): What it is called.

    Returns:
        made (Object or None): The exit if it was made now, or None if it was already there.

    """
    for found in source.contents:
        if found.destination == destination and found.key == key:
            return None
    return create.create_object(EXIT, key=key, location=source, destination=destination)


def _staff_the_village(rooms, tally):
    """
    Put somebody behind every counter that has one.

    Args:
        rooms (dict): Room key to object.
        tally (dict): Counters to add to.

    Notes:
        Driven off the room's own name, so adding a shop means adding a room and a line in
        `stock` and nothing else. A room nobody keeps simply has nobody in it, which is the
        right answer for a bond store.

    """
    for key, room in rooms.items():
        spec = stock.village_vendor_for(key)
        if spec is None:
            continue
        _, made_now = people.make(
            key=spec["key"],
            description=spec["desc"],
            stock=spec["stock"],
            greeting=spec["greeting"],
            home=room,
        )
        tally["people"] += 1 if made_now else 0


def _say(on_report, line):
    """
    Args:
        on_report (callable or None): Where to say it.
        line (str): What to say.

    """
    if on_report is not None:
        on_report(line)


__all__ = (
    "LAND_ROOM",
    "QUAY_ROOM",
    "EXIT",
    "build",
    "starting_room",
    "islands",
    "people",
    "stock",
    "village",
)
