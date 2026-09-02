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

import math

#: How far to walk before the map stops, in rooms.
#:
#: Far enough to hold a town and stop at its edges. Bounded because an unbounded spread from
#: a well-connected world is a map of the world, and because a payload is sent to a browser.
REACH = 14

#: The most rooms to draw, whatever the reach says. A guard against a game whose town is a
#: thousand rooms of corridor, so a player gets a useful map of nearby rather than a
#: three-second pause and an unreadable one.
MOST_ROOMS = 120

#: Compass directions, and what they do to a position on the map.
#:
#: **Up and down are not in here, and used to be.** They were `(0, 1)` and `(0, -1)` - the
#: same as north and south - so on a waterfront with thirteen ups and twelve downs in it,
#: a quarter of the map was drawn as though every ladder were a street running north. Rooms
#: landed on top of each other, the collision search flung them across the sheet to find
#: space, and the result was a cat's cradle of long diagonal lines over a town that is
#: actually a grid.
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
}

#: Exit names that go up or down rather than across.
#:
#: **Followed, but not stepped along.** They were `(0, 1)` and `(0, -1)` - the same as north
#: and south - so a waterfront with thirteen ladders in it drew a quarter of its exits as
#: streets running north, piled rooms on top of each other, and sent the collision search
#: across the sheet looking for space.
#:
#: Not followed at all was the next attempt, and it was worse: a town behind a beach is
#: reached *up* the shore, so refusing to follow them cut Careenage off from its own quay
#: and left a map of twenty-five rooms in a strip. A map cannot tell a hill from a ladder,
#: and guessing wrong in that direction loses the town.
#:
#: So the room beyond is drawn beside its parent, as a door is, and the edge is marked so
#: the drawing can say what it is. That is honest about both cases: neither a ladder nor a
#: slope moves you along the street plan, and both of them get you somewhere real.
VERTICAL = ("up", "down", "u", "d")

#: Where a door goes when it is not a direction, in the order they are tried.
#:
#: `bar`, `chandlery`, `out` - twenty of them on one waterfront, and every one used to go
#: east, because that was the single fallback. Forty doors stacked into one column of cells
#: is most of what the collision search was working around, and it is why a ship reached by
#: a `gangway` sat to starboard of the pier no matter which way the sea was.
#:
#: A door does not move you across a town, it moves you inside something, so it goes in the
#: first free cell beside its parent. Which one hardly matters; that it is *beside* is the
#: whole point.
BESIDE = ((1, 0), (0, -1), (-1, 0), (0, 1), (1, -1), (-1, -1), (1, 1), (-1, 1))

#: How many cells a street runs before the next street cell.
#:
#: Two, so that every room on a street has a free ring around it for its doors. At one, a
#: shop and the street outside it competed for the same square: the first door placed took
#: the cell the next street cell wanted, and half a waterfront could not be drawn at all.
#:
#: It is also the truth about the place. A row of buildings stands *between* two streets,
#: which is exactly the gap this opens up, and putting the chandlery in it rather than on
#: the road is a better picture as well as a possible one.
STREET = 2

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
        sheet (dict): `rooms`, `edges`, `here` and `title`, ready to send. A room also says
            whether it has `stairs` - a way off this level, drawn as a mark rather than
            followed.

    Notes:
        Empty for somebody standing nowhere, which is the honest answer and keeps this
        callable without the caller having to check first.

    """
    here = getattr(character, "location", None)
    if here is None:
        return {"rooms": [], "edges": [], "here": None, "title": ""}

    anchor = _anchor_for(here, reach)
    placed, edges, stairs = _walk(anchor, reach)
    if here not in placed:
        # She is inside the component but past the room budget, so the sheet cannot show
        # her. Better to draw the place she is standing in than a place she is not.
        placed, edges, stairs = _walk(here, reach)

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
                "stairs": room in stairs,
            }
            for room, (x, y) in placed.items()
        ],
        "edges": [edge for edge in edges if edge["from"] in {room.id for room in placed}],
    }


def _anchor_for(here, reach):
    """
    The room this map is laid out from, whoever happens to be standing on it.

    Args:
        here (Object): Where the player is.
        reach (int): How far the map extends, in rooms.

    Returns:
        anchor (Object): The room to walk from.

    Notes:
        **A map that is drawn from the player's own room is a different map every time the
        player moves.** Walking east redrew the whole town from a new origin: streets
        landed in different cells, doors picked different gaps, and the picture visibly
        reshaped itself under somebody who had taken one step. A map is meant to be the
        thing that stays still while you move across it.

        So the layout is anchored on the lowest-numbered room of the group the player is
        in, which is a fact about the place rather than about the player. Stand anywhere in
        Careenage and Careenage is drawn identically; only the marker moves. It is the same
        thing a game with authored room coordinates gets for free, worked out instead of
        stored - because a contrib cannot ask every game to have laid its rooms out on a
        grid first.

        The lowest dbref, specifically, because it is stable, cheap and needs nothing
        declared. It is usually the oldest room in the area, which is as good an origin as
        any and better than most.

    """
    seen = {here}
    edge = [here]
    for _ in range(reach):
        following = []
        for room in edge:
            for way in _exits_of(room):
                target = way.destination
                if target is not None and target not in seen:
                    seen.add(target)
                    following.append(target)
        if not following or len(seen) >= MOST_ROOMS:
            break
        edge = following

    # **Ashore, and not aboard.** A ship reachable over a gangway has a dbref like anything
    # else, and hers was the lowest - so a whole town was laid out relative to her deck,
    # which put the harbour inland of everything and would have moved the entire map the
    # moment she sailed. An anchor has to be a thing that stays: a vessel is a visitor.
    ashore = [room for room in seen if not _afloat(room)]
    return min(ashore or list(seen), key=lambda room: room.id)


def _afloat(room):
    """
    Args:
        room (Object): A room.

    Returns:
        aboard (bool): Whether it is part of a vessel.

    """
    from ..vessel import vessel_in

    return vessel_in(room) is not None


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
    stairs = set()
    queue = [(start, 0)]

    while queue and len(placed) < MOST_ROOMS:
        here, steps = queue.pop(0)
        for way in _exits_of(here):
            target = way.destination
            if target is None:
                continue
            name = str(getattr(way, "key", "")).lower()

            climbs = name in VERTICAL
            if climbs:
                stairs.add(here)

            # The edge is recorded even when the room beyond it is too far to draw, so a
            # room at the rim can still tell that a way leads off the map.
            pair = (here.id, target.id, name)
            if pair not in seen_exits:
                seen_exits.add(pair)
                edges.append({"from": here.id, "to": target.id, "dir": name, "climbs": climbs})

            if target in placed or len(placed) >= MOST_ROOMS:
                continue
            if steps + 1 > reach:
                continue

            spot = _anchored_spot(target, placed, taken, here)
            if spot is None:
                spot = _spot_for(placed[here], name, taken, here, target)
            if spot is None:
                # Nowhere beside its parent, so it is not drawn. A room placed six cells
                # away to find space is a room joined to the map by a line across half the
                # town, which is worse than a room that is simply not on it.
                continue
            placed[target] = spot
            taken.add(spot)
            queue.append((target, steps + 1))

    _rehouse(placed, edges)
    return placed, edges, stairs


def _joinable(first, second, taken):
    """
    Whether a line drawn between two cells would be drawn at all.

    Args:
        first (tuple): One room's cell.
        second (tuple): The other's.
        taken (set): Every cell holding a room.

    Returns:
        joinable (bool): True if the client would draw this line.

    Notes:
        The same two questions the client asks before it draws: is this one move, and is
        there anything standing in it. Asked here so the layout can see what the picture
        will look like before anybody has to look at it.

    """
    across = second[0] - first[0]
    down = second[1] - first[1]
    if max(abs(across), abs(down)) > STREET:
        return False
    return _clear_between(first, second, taken)


def _rehouse(placed, edges):
    """
    Move any room that has ended up with no line to anywhere.

    Args:
        placed (dict): Room to cell, changed in place.
        edges (list): The exits between them.

    Notes:
        Placement puts each room beside the room it opens off, but a room placed later can
        land in the gap between two earlier ones and cut the road that joined them. The room
        beyond is then on the map with nothing drawn to it - a dot in a field, which a player
        can see, click, and walk to, and which looks like a mistake.

        Rather than hold every gap open against that - which costs rooms their place, since
        a held cell is one nothing else may use - the few rooms it actually happens to are
        moved afterwards, to a free cell beside a room they really do open off.

    """
    cells = {room.id: spot for room, spot in placed.items()}
    rooms = {room.id: room for room in placed}
    taken = set(cells.values())

    neighbours = {}
    for edge in edges:
        neighbours.setdefault(edge["from"], set()).add(edge["to"])
        neighbours.setdefault(edge["to"], set()).add(edge["from"])

    for room_id, spot in list(cells.items()):
        near = [other for other in neighbours.get(room_id, ()) if other in cells]
        if any(_joinable(spot, cells[other], taken) for other in near):
            continue
        for other in near:
            moved = _free_beside(cells[other], taken)
            if moved is None:
                continue
            taken.discard(spot)
            taken.add(moved)
            cells[room_id] = moved
            placed[rooms[room_id]] = moved
            break


def _free_beside(origin, taken):
    """
    Args:
        origin (tuple): The cell to sit beside.
        taken (set): Every cell holding a room.

    Returns:
        spot (tuple or None): A free cell one move from `origin`, or None if there is none.

    """
    for scale in (STREET, 1):
        for way in BESIDE:
            spot = (origin[0] + way[0] * scale, origin[1] + way[1] * scale)
            if spot not in taken and _clear_between(origin, spot, taken):
                return spot
    return None


def _anchored_spot(target, placed, taken, parent=None):
    """
    Where a room that knows its own position belongs, relative to the others that do.

    Args:
        target (Object): The room being placed.
        placed (dict): Rooms already on the map, and their cells.
        taken (set): Cells already used.
        parent (Object, optional): The room it was reached from.

    Returns:
        spot (tuple or None): Its cell, or None if there is nothing to anchor it to.

    Notes:
        **A few rooms on a land map know where they really are, and they should be drawn
        there.** A quay carries a `WorldPosition`; a street never will. Walked from the
        street plan alone, three piers on one waterfront came out in a line running south
        in the order the Strand happens to visit them - and the middle one, which is north
        and east of the first in the world, was drawn six cells south of it. A map that
        puts the harbour on the wrong side of the town is worse than one that admits it is
        a diagram.

        So a positioned room is placed by its true bearing from the nearest *other*
        positioned room already on the sheet, and the streets hang off them as they fall.
        The first one anchors the sheet and everything else is measured from it, which is
        what a chart datum is for.

        Rounded to the eight points and one street's stride, because this is still a
        diagram: the piers come out in the right relation to each other, not to scale.

    """
    # Asked first, because a ship's compartment carries no position of its own - she is
    # placed by where her *berth* is - so the gate below would turn her away.
    # A vessel lying at a quay is in the same place as the quay, so there is no bearing
    # between them to take - and a gangway is a noun, so she was going wherever the first
    # free cell happened to be, which was east. East of the pier is where the town is.
    seaward = _seaward_spot(target, placed, taken, parent)
    if seaward is not None:
        return seaward

    here = getattr(target, "maritime_position", None)
    if here is None:
        return None

    nearest = None
    span = None
    for room, cell in placed.items():
        other = getattr(room, "maritime_position", None)
        if other is None or getattr(other, "region", None) != getattr(here, "region", None):
            continue
        away = other.horizontal_distance_to(here)
        if away <= 0.0:
            continue
        if span is None or away < span:
            nearest, span = (other, cell), away

    if nearest is None:
        return None

    other, cell = nearest
    step = _step_between(other, here)
    if step is None:
        return None
    for out in range(1, 5):
        spot = (cell[0] + step[0] * STREET * out, cell[1] + step[1] * STREET * out)
        if spot not in taken:
            return spot
    return None


def _seaward_step(port, draft=0.0):
    """
    Which way the open water lies from a quay.

    Args:
        port (PortRoom): The quay.
        draft (float, optional): What is being taken in, so the mark that serves her is
            the one she could actually use.

    Returns:
        step (tuple or None): A compass step towards the sea, or None if this quay has no
            marked approach.

    Notes:
        **Taken from the mark that serves the harbour, which is seaward by construction.**
        A roadstead lies off a quay in open water; the bearing to it is the way out. That
        needs nothing authored and guesses nothing, and it is the same answer `passage`
        gives when it plans a course in - so the map and the passage agree about which way
        the sea is, which they must.

    """
    quay = getattr(port, "maritime_position", None)
    if quay is None:
        return None

    from .. import passage

    mark = passage.approach_for(port, draft=draft)
    if mark is None:
        return None
    return _step_between(quay, mark.position)


def _seaward_spot(target, placed, taken, parent=None):
    """
    Where something on the water side of a town belongs: on the water side of the map.

    Args:
        target (Object): The room being placed.
        placed (dict): Rooms already on the map, and their cells.
        taken (set): Cells already used.
        parent (Object, optional): The room it was reached from.

    Returns:
        spot (tuple or None): Its cell, or None if this is not a quay or a ship at one.

    Notes:
        Two cases, and the same answer to both.

        **A quay reached from a street.** A pier is joined to the road by a noun - `pier`,
        `hard`, `steps` - because a pier is a structure you walk out onto rather than a
        direction you travel, which is right. It also means nothing in the exit says which
        way the sea is, so a waterfront went into the first free cell, which was east: a
        harbour whose ocean lies west drew its shipping inland, and the map came out a
        mirror of the coast.

        **A vessel lying at that quay.** She and the berth share a position, so there is no
        bearing between them to take at all, and the gangway is a noun for the same good
        reason. She goes on the water side of the quay, which is where she is.

    """
    from ..vessel import vessel_in

    vessel = vessel_in(target)
    if vessel is not None:
        port = getattr(vessel, "docked_at", None)
        if port is None or port not in placed:
            return None
        step = _seaward_step(port, getattr(vessel, "draft", 0.0))
        return _out_from(placed[port], step, taken)

    # A quay: seaward of whatever it hangs off.
    if not getattr(target, "berths", None) or parent is None or parent not in placed:
        return None
    step = _seaward_step(target)
    return _out_from(placed[parent], step, taken)


def _out_from(cell, step, taken, reach=3):
    """
    Args:
        cell (tuple): Where to start.
        step (tuple or None): Which way to go.
        taken (set): Cells already used.
        reach (int, optional): How far to look.

    Returns:
        spot (tuple or None): The first free cell that way, or None.

    """
    if step is None:
        return None
    for out in range(1, reach + 1):
        spot = (cell[0] + step[0] * out, cell[1] + step[1] * out)
        if spot not in taken:
            return spot
    return None


def _spot_for(origin, direction, taken, here=None, target=None):
    """
    Args:
        origin (tuple): Where the room we came from sits.
        direction (str): What the exit was called.
        taken (set): Squares already used.
        here (Object, optional): The room we came from, for its position if it has one.
        target (Object, optional): The room being placed, likewise.

    Returns:
        spot (tuple or None): Where to put the new room, or None if there is nowhere
            beside its parent.

    Notes:
        **A door goes beside its parent, not east of it.** An exit whose name is not a
        direction - `bar`, `chandlery`, `out`, `gangway` - used to be given `(1, 0)`, so
        every door in a town went into the same column and the collision search spent the
        rest of the map working around them. It also meant a vessel reached by a gangway
        was drawn to the east of her berth whatever the coast was doing, which is how a
        harbour ended up with its sea on the wrong side.

        **Anything that knows where it really is, is placed where it really is.** A quay
        and a ship both carry a world position, so the bearing between them is a fact
        rather than a guess, and using it puts the ship seaward of the pier because that is
        where she is. Streets have no positions and never will; they fall back to the exit
        name, which is the only thing anybody knows about them.

        **Never more than one cell from its parent.** Searching outward until something was
        free is what drew the long diagonals: a room five cells adrift is joined to the map
        by a line across half the town, and a line that long stops meaning "you can walk
        this way" and starts meaning nothing at all. If there is no room beside it, it does
        not go on the sheet.

    """
    step = _bearing_step(here, target)
    if step is None:
        step = STEPS.get(direction)

    if direction in VERTICAL:
        # Up and down go nowhere on a street plan. Beside its parent, like a door.
        step = None

    # **NEXT DOOR, OR NOWHERE.**
    #
    # A town has no bridges and no subways, so every line on the map has to be a move a
    # player could make in one go. That is a rule about *placement*, not about drawing:
    # a room put three streets from the room it opens off cannot be joined to it by
    # anything honest, and hiding the line afterwards only leaves the room floating.
    #
    # So a room goes in the cell its exit points at; failing that, in the nearest cell to
    # that one which is still a single move from its parent; and failing that, not on the
    # map at all. Looking further along the street was the previous rule and it is what put
    # rooms two and three strides out with four- and six-cell lines back to their parents.
    if step is not None and direction in STEPS:
        wanted = (origin[0] + step[0] * STREET, origin[1] + step[1] * STREET)
        if wanted not in taken and _clear_between(origin, wanted, taken):
            return wanted
        return _nearest_free(origin, step, taken)

    if step is not None:
        spot = (origin[0] + step[0], origin[1] + step[1])
        if spot not in taken:
            return spot

    # A door, which opens into the gap the lattice leaves between two streets.
    for beside in BESIDE:
        spot = (origin[0] + beside[0], origin[1] + beside[1])
        if spot not in taken:
            return spot
    return None


def _nearest_free(origin, step, taken):
    """
    The free cell one move from here that lies nearest the way the exit points.

    Args:
        origin (tuple): The parent's cell.
        step (tuple): The compass step the exit wanted.
        taken (set): Cells already used.

    Returns:
        spot (tuple or None): A cell one move away, or None if every one is taken.

    Notes:
        One move means one street's stride on the lattice, or one cell into the gap between
        streets - the two distances anything on this map is ever drawn at. Tried in order of
        how far round they are from the direction actually asked for, so a lane that cannot
        run north runs north-east before it runs south, and the picture stays as close to
        the truth as the grid allows.

    """
    wanted = math.atan2(step[0], step[1])

    def turned(candidate):
        angle = math.atan2(candidate[0], candidate[1])
        return abs((angle - wanted + math.pi) % (2.0 * math.pi) - math.pi)

    for scale in (STREET, 1):
        for way in sorted(BESIDE, key=turned):
            spot = (origin[0] + way[0] * scale, origin[1] + way[1] * scale)
            if spot not in taken and _clear_between(origin, spot, taken):
                return spot
    return None


def _clear_between(origin, spot, taken):
    """
    Whether the line from one cell to another has nothing standing in it.

    Args:
        origin (tuple): The parent's cell.
        spot (tuple): Where the room would go.
        taken (set): Cells already used.

    Returns:
        clear (bool): True if a line between them would cross no other room.

    Notes:
        A cell two strides away is one move on this lattice, but only if the cell between
        them is empty - otherwise the line runs straight through somebody's front room,
        which on a street plan is a road through a building. The drawing refuses to draw
        such a line, so a room placed there ends up on the map joined to nothing; asking
        here means it is never placed there at all.

        Only the midpoint, because nothing further than two strides is ever offered.

    """
    across = spot[0] - origin[0]
    down = spot[1] - origin[1]
    if abs(across) < 2 and abs(down) < 2:
        return True
    return (origin[0] + across // 2, origin[1] + down // 2) not in taken


def _step_between(first, second):
    """
    Args:
        first (WorldPosition): Where to measure from.
        second (WorldPosition): Where to measure to.

    Returns:
        step (tuple or None): The compass step the bearing falls in, or None if they are
            in the same place.

    Notes:
        Rounded to the eight points, because the map has eight neighbours. A bearing is
        only being used to pick a cell.

    """
    east = second.x - first.x
    north = second.y - first.y
    if not east and not north:
        return None

    bearing = (math.degrees(math.atan2(east, north)) + 360.0) % 360.0
    point = int((bearing + 22.5) // 45) % 8
    return ((0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (-1, 1))[point]


def _bearing_step(here, target):
    """
    Args:
        here (Object or None): The room we came from.
        target (Object or None): The room being placed.

    Returns:
        step (tuple or None): The compass step the true bearing between them falls in, or
            None if either of them is not on the water.

    Notes:
        Only for rooms that hold a `WorldPosition` - which on land means quays, and afloat
        means ships. Two rooms that both know where they are can be drawn in their true
        relation to each other, and a map that draws a pier and the vessel lying at it in
        the wrong relative direction is worse than one that admits it is a diagram.

        Rounded to the eight points, because the map has eight neighbours. A bearing is
        only being used to pick a cell.

    """
    if here is None or target is None:
        return None
    first = getattr(here, "maritime_position", None)
    second = getattr(target, "maritime_position", None)
    if first is None or second is None:
        return None
    if getattr(first, "region", None) != getattr(second, "region", None):
        return None
    return _step_between(first, second)


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
    "VERTICAL",
    "BESIDE",
    "STREET",
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
