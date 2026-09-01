"""
The map of the place you are standing in, for when you are not on a ship.

A chart is the wrong instrument ashore. It draws water, and the useful question on land is
not how deep anything is but which way the market is and how to get back to the pier. So
when somebody steps off a gangway the panel keeps its space and changes what it holds: rooms
and the ways between them, with the ship still marked on it.

    rooms      what is walkable from here, out to a short distance
    edges      the exits, one per direction, so a route can be worked out
    markers    what a room is *for*, which is the only reason to draw it in colour

**Walked, not queried.** The map is a breadth-first spread over exits from where the player
stands, bounded. That is deliberate: a game has no zones this contrib knows about, and
inventing one would mean asking every game to declare something it has not got. What a
player can reach in a dozen steps is a definition that needs nothing from anybody.

**Laid out by walking, not by coordinates.** Land rooms have no positions - they are rooms,
joined by exits, and a lane that runs north out of one room and comes back east into another
is perfectly ordinary. So the map is drawn by following compass directions from the player's
own room and putting each room where the walk says it is, which produces a picture that
matches how it felt to walk it. Rooms reached by a door rather than a direction sit beside
their parent, because that is where a door goes.

**Colour is meaning, not decoration.** A dot is only worth colouring if the colour answers a
question a player is actually asking, and ashore there are three: where is my ship, where do
I buy things, and where am I. Everything else stays the same quiet colour so those three
carry.
"""

#: How far to walk before the map stops, in rooms.
#:
#: Far enough to hold a town and stop at its edges. Bounded because an unbounded spread from
#: a well-connected world is a map of the world, and because a payload is sent to a browser.
REACH = 14

#: The most rooms to draw, whatever the reach says. A guard against a game whose town is a
#: thousand rooms of corridor, so a player gets a useful map of nearby rather than a
#: three-second pause and an unreadable one.
MOST_ROOMS = 120

#: Compass directions, and what they do to a position on the map. Two units across for one
#: down, so a row of rooms reads as a row rather than as a diagonal smear.
STEPS = {
    "north": (0, 1),
    "south": (0, -1),
    "east": (1, 0),
    "west": (-1, 0),
    "northeast": (1, 1),
    "northwest": (-1, 1),
    "southeast": (1, -1),
    "southwest": (-1, -1),
    "ne": (1, 1),
    "nw": (-1, 1),
    "se": (1, -1),
    "sw": (-1, -1),
    "n": (0, 1),
    "s": (0, -1),
    "e": (1, 0),
    "w": (-1, 0),
    "up": (0, 1),
    "down": (0, -1),
}

#: What a room is for, in the order it is asked. First match wins, so the more specific
#: markers are listed first.
HERE = "here"
SHIP = "ship"
BERTH = "berth"
TRADE = "trade"
WAY_OUT = "way_out"
PLAIN = "plain"

MARKERS = (HERE, SHIP, BERTH, TRADE, WAY_OUT, PLAIN)


def sheet_for(character, reach=REACH):
    """
    The map of where this character is standing.

    Args:
        character (Object): Whoever is ashore.
        reach (int, optional): How many rooms to walk before stopping.

    Returns:
        sheet (dict): `rooms`, `edges`, `here` and `title`, ready to send.

    Notes:
        Empty for somebody standing nowhere, which is the honest answer and keeps this
        callable without the caller having to check first.

    """
    here = getattr(character, "location", None)
    if here is None:
        return {"rooms": [], "edges": [], "here": None, "title": ""}

    placed, edges = _walk(here, reach)
    return {
        "title": str(getattr(here, "key", "")),
        "here": here.id,
        "rooms": [
            {
                "id": room.id,
                "name": str(getattr(room, "key", "")),
                "x": x,
                "y": y,
                "marker": _marker_for(room, here, placed),
            }
            for room, (x, y) in placed.items()
        ],
        "edges": edges,
    }


def _walk(start, reach):
    """
    Spread out from a room, placing each one where the walk puts it.

    Args:
        start (Object): Where the player is.
        reach (int): How many rooms to follow.

    Returns:
        found (tuple): `(placed, edges)` - a room-to-position map, and the exits between.

    Notes:
        Breadth-first, so the rooms nearest the player are placed first and get the
        positions their directions actually imply. Depth-first would let a long lane wander
        away and claim the square a neighbouring room needed.

        **`reach` counts steps, which is what it says.** It was a room budget of `reach`
        squared, dressed in the name of a distance - so asking for a map two rooms across
        drew five rooms and a caller had no way to limit how far it went. A parameter whose
        name and behaviour disagree is worse than one that is simply wrong, because reading
        the call site tells you the opposite of what happens.

        **A collision keeps the first room there and nudges the second.** Two rooms
        genuinely can want one square - a town is not a grid and its exits do not have to
        be reversible - and the alternative to nudging is drawing them on top of each
        other, which loses one of them entirely.

    """
    placed = {start: (0, 0)}
    taken = {(0, 0)}
    edges = []
    seen_exits = set()
    queue = [(start, 0)]

    while queue and len(placed) < MOST_ROOMS:
        here, steps = queue.pop(0)
        for way in _exits_of(here):
            target = way.destination
            if target is None:
                continue
            name = str(getattr(way, "key", "")).lower()

            # The edge is recorded even when the room beyond it is too far to draw, so a
            # room at the rim can still tell that a way leads off the map.
            pair = (here.id, target.id, name)
            if pair not in seen_exits:
                seen_exits.add(pair)
                edges.append({"from": here.id, "to": target.id, "dir": name})

            if target in placed or len(placed) >= MOST_ROOMS:
                continue
            if steps + 1 > reach:
                continue

            spot = _spot_for(placed[here], name, taken)
            placed[target] = spot
            taken.add(spot)
            queue.append((target, steps + 1))

    return placed, edges


def _spot_for(origin, direction, taken):
    """
    Args:
        origin (tuple): Where the room we came from sits.
        direction (str): What the exit was called.
        taken (set): Squares already used.

    Returns:
        spot (tuple): Where to put the new room.

    Notes:
        An exit whose name is not a direction - `bar`, `chandlery`, `out` - puts its room
        beside its parent rather than nowhere. That is what a door does: it does not move
        you across the town, it moves you inside something, and drawing it adjacent says so
        without needing a second kind of map.

    """
    step = STEPS.get(direction)
    if step is None:
        step = (1, 0)
    spot = (origin[0] + step[0], origin[1] + step[1])
    if spot not in taken:
        return spot

    # Nudged outward in a ring until something is free. Rare, and better than two rooms
    # drawn on the same square.
    for ring in range(1, 6):
        for dx in range(-ring, ring + 1):
            for dy in range(-ring, ring + 1):
                candidate = (spot[0] + dx, spot[1] + dy)
                if candidate not in taken:
                    return candidate
    return spot


def _exits_of(room):
    """
    Args:
        room (Object): A room.

    Returns:
        exits (list): Its exits, in a stable order.

    Notes:
        Sorted by name so a map drawn twice is the same map. Left to the database's own
        order, a room's exits can come back differently between calls and the whole
        picture shuffles under the player for no reason they can see.

    """
    found = [thing for thing in room.contents if getattr(thing, "destination", None)]
    found.sort(key=lambda way: str(getattr(way, "key", "")))
    return found


def _marker_for(room, here, placed):
    """
    What this room is for.

    Args:
        room (Object): The room being drawn.
        here (Object): Where the player is.
        placed (dict): Every room on this map, so the edge of it can be recognised.

    Returns:
        marker (str): One of `MARKERS`.

    Notes:
        Three questions and no more. Ashore, a player wants to know where they are, where
        their ship is, and where things are sold; a map that colours eleven kinds of room
        answers none of them, because nothing stands out when everything does.

    """
    if room == here:
        return HERE
    if _holds_a_vessel(room):
        return SHIP
    if getattr(room, "berths", None):
        return BERTH
    if _sells_anything(room):
        return TRADE
    if _leaves_the_map(room, placed):
        return WAY_OUT
    return PLAIN


def _holds_a_vessel(room):
    """
    Args:
        room (Object): A room.

    Returns:
        aboard (bool): Whether this room is part of a ship.

    """
    from ..vessel import vessel_in

    return vessel_in(room) is not None


def _sells_anything(room):
    """
    Args:
        room (Object): A room.

    Returns:
        trades (bool): Whether somebody in it has something for sale.

    Notes:
        Duck-typed rather than tied to any vendor class, so a game with its own shopkeepers
        gets its own shops marked without telling this module anything.

        **Both the property and the attribute**, which is the difference between duck-typing
        and duck-typing one duck. The example's own vendor exposes `stock` as a property, so
        checking only that worked perfectly for the example and silently marked nothing at
        all for a game that kept its stock on an ordinary attribute - which is most of the
        ways somebody would write it.

    """
    for thing in room.contents:
        if getattr(thing, "destination", None):
            continue
        if getattr(thing, "stock", None):
            return True
        holder = getattr(thing, "db", None)
        if holder is not None and getattr(holder, "stock", None):
            return True
    return False


def _leaves_the_map(room, placed):
    """
    Args:
        room (Object): A room.
        placed (dict): Every room on this map.

    Returns:
        onward (bool): Whether a way leads off the edge of the drawing.

    Notes:
        Marked so the edge of the drawing does not read as the edge of the world. A player
        who can see that a road continues will follow it; one looking at a map that simply
        stops will assume there is nothing out there.

        **It means what it says, which the first version did not.** That counted a room's
        exits and called anything with more than two a way out - so every junction in the
        town was flagged, twenty-six of them, and the marker meant "this room is busy"
        rather than "the road goes on". A marker that fires everywhere is a marker nobody
        reads. The question is whether an exit leads somewhere *not on this map*, and
        answering it needs the map, which is why it is passed in.

    """
    for way in _exits_of(room):
        target = way.destination
        if target is not None and target not in placed:
            return True
    return False


__all__ = (
    "REACH",
    "MOST_ROOMS",
    "MARKERS",
    "HERE",
    "SHIP",
    "BERTH",
    "TRADE",
    "WAY_OUT",
    "PLAIN",
    "sheet_for",
)
