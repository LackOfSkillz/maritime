"""
The shape of the example world: one coast, one river, one pond, six islands.

Everything here is terrain and water. The rooms that stand on it are in `world`, and the
craft that cross it are in `craft`. Keeping the three apart is not tidiness - a game
replacing the scenery keeps the geography, and a game replacing the geography keeps the
craft.

    the pond        a still sheet inland, no stream, a breeze across it
    the river       from the pond's outfall to the sea, running hard seaward
    the harbour     at the river mouth, where a canoe becomes a sloop
    six islands     strung eastward, each a fair sail from the last

**The pond and the river are the same water and behave completely differently,** which is
the whole reason both are here. A kayak left alone on the pond fetches up on the lee shore
because the wind is the only thing moving her. A canoe on the river is in a stream that runs
one way, so the same stroke is a different voyage depending on which way she points.

**Terrain is computed, not tabulated.** A `Tile` holds a flat elevation by default, which is
right for a shelf and wrong for a coast; `ExampleTile` overrides `terrain_z_at` and works out
the ground at each point from a handful of authored shapes. That is the seam `Tile` documents,
used the way it was meant to be.

"""

import math

from ..bathymetry import MUD, ROCK, SAND
from ..currents import CurrentVector, MaritimeCurrentProvider
from ..position import WorldPosition
from ..spatial import distance_to_track
from ..tiles import Tile, TiledMapProvider, TileSource

# --- the lie of the land ----------------------------------------------------

#: How wide the example's tiles are. Small enough that a coastline is not one square,
#: large enough that a passage between islands crosses a handful rather than a hundred.
TILE_SIZE = 400.0

#: Elevation of the mainland, and of the deep sea. Everything between is worked out.
MAINLAND_Z = 8.0
DEEP_Z = -40.0

#: Where the mainland stops. West of this is dry, east of it is water - except where
#: the river cuts in and the islands stand up.
COASTLINE_X = 0.0

#: How fast the shelf falls away from the beach, in metres of easting per metre of depth.
SHELF_SLOPE = 60.0

#: The pond: a still sheet, deep enough to paddle and too shallow to sail.
POND_CENTRE = WorldPosition(-4000.0, 2000.0)
POND_RADIUS = 500.0
POND_DEPTH = 3.0

#: The river, as the line it runs along. Each pair is a reach; the last reach ends at
#: the sea. Authored as a polyline rather than a formula because a river bends, and
#: because a builder should be able to move one bend without solving anything.
RIVER = (
    WorldPosition(-4200.0, 1700.0),
    WorldPosition(-3000.0, 1200.0),
    WorldPosition(-1500.0, 500.0),
    WorldPosition(0.0, 0.0),
)

#: How wide the river is, from bank to bank, and how deep between them.
RIVER_HALF_WIDTH = 45.0
RIVER_DEPTH = 4.0

#: How hard it runs. Strong enough that a single paddler cannot get up it, which is the
#: point: the way back is a decision rather than a formality.
RIVER_DRIFT = 0.9

#: The islands, eastward from the river mouth. Each is a name, a centre, and how far
#: the land reaches.
#:
#: Spacing is checked by a test rather than by eye - every leg has to come out between
#: five and ten minutes under working sail. The figure that spaces them is measured
#: rather than assumed: the first layout used a guess of four metres a second and the
#: sloop actually makes 2.2 on this heading, so every island was nearly twice as far
#: out as it should have been and the test passed anyway because it was checking the
#: same guess.
ISLANDS = (
    ("Gullstone", 1575.0, 350.0, 260.0),
    ("Blackrock", 2450.0, -250.0, 240.0),
    ("Thornholm", 3400.0, 400.0, 280.0),
    ("Cradle Isle", 4263.0, -300.0, 250.0),
    ("Farne", 5138.0, 300.0, 230.0),
    ("Outer Skerry", 6000.0, -200.0, 200.0),
)

#: How high an island stands at its middle.
ISLAND_Z = 14.0

#: How far the shoaling foreshore reaches beyond an island's land, as a multiple of
#: its reach. Without it an island is a cliff: twenty-four metres of water one step
#: and dry sand the next, so a lead line would show nothing at all until she struck.
FORESHORE = 2.0

#: How far offshore a harbour lies from its island's centre, as a fraction of the
#: island's reach. On the foreshore rather than out on the shelf, which is why the
#: quays come out at five or six metres rather than twenty-five - a small harbour is
#: shallow, and that is a constraint worth having.
HARBOUR_OFFSET = 1.25


def river_reaches():
    """
    Returns:
        reaches (tuple): `(from, to)` pairs, source to sea.

    """
    return tuple(zip(RIVER[:-1], RIVER[1:]))


def distance_to_river(position):
    """
    How far a point is from the middle of the river.

    Args:
        position (WorldPosition): Where to measure.

    Returns:
        distance (float): Metres to the nearest reach.

    """
    return min(distance_to_track(position, start, end) for start, end in river_reaches())


def river_set_at(position):
    """
    Which way the river runs where it passes closest to a point.

    Args:
        position (WorldPosition): Where to ask.

    Returns:
        bearing (float): The downstream direction, in degrees.

    Notes:
        Per reach rather than one figure for the whole river, so the stream follows
        the bends. A canoe rounding one is set towards the outside of it, which is
        both what happens and the reason a bend is worth respecting.

    """
    start, end = min(
        river_reaches(), key=lambda reach: distance_to_track(position, reach[0], reach[1])
    )
    return start.bearing_to(end)


def nearest_island(position):
    """
    The island a point is closest to, and how far off it lies.

    Args:
        position (WorldPosition): Where to ask.

    Returns:
        found (tuple): `(island, offshore)`, where `offshore` is metres from its
            centre. `(None, inf)` if there are no islands at all.

    """
    best, best_range = None, math.inf
    for island in ISLANDS:
        _name, x, y, _reach = island
        offshore = math.hypot(position.x - x, position.y - y)
        if offshore < best_range:
            best, best_range = island, offshore
    return best, best_range


def island_at(position):
    """
    The island a point stands on, if any.

    Args:
        position (WorldPosition): Where to ask.

    Returns:
        island (tuple or None): `(name, x, y, reach)`, or None if it is in the
            water - foreshore included.

    """
    island, offshore = nearest_island(position)
    if island is None:
        return None
    return island if offshore <= island[3] else None


def harbour_position(island):
    """
    Where an island's quay stands.

    Args:
        island (tuple): `(name, x, y, reach)`.

    Returns:
        position (WorldPosition): On the water, on the landward side.

    Notes:
        On the side facing the mainland, so that a passage from the west arrives at
        the quay rather than having to go round. That is a courtesy to a player
        learning to sail, not a claim about how harbours are sited.

    """
    _name, x, y, reach = island
    return WorldPosition(x - reach * HARBOUR_OFFSET, y)


class ExampleTile(Tile):
    """
    A square of this world, with the ground worked out at each point.

    Notes:
        `Tile` holds one elevation for its whole square, which is right for a shelf
        and wrong for a coast. Overriding `terrain_z_at` is the seam `Tile`
        documents for exactly this, and it means a shoreline can cross a tile
        diagonally without anybody authoring a finer grid.

    """

    def terrain_z_at(self, position):
        """
        Ground elevation at a point.

        Args:
            position (WorldPosition): Where to sample.

        Returns:
            terrain_z (float): Metres relative to datum.

        Notes:
            Ordered from the smallest feature to the largest, because the small
            ones are cut *into* the big ones. The river is a channel through the
            mainland and the pond is a hollow in it, so both have to be tested
            before the land they sit in.

        """
        if distance_to_river(position) <= RIVER_HALF_WIDTH:
            return -RIVER_DEPTH

        if position.horizontal_distance_to(POND_CENTRE) <= POND_RADIUS:
            return -POND_DEPTH

        if position.x < COASTLINE_X:
            return MAINLAND_Z

        shelf = max(DEEP_Z, -position.x / SHELF_SLOPE)

        island, offshore = nearest_island(position)
        if island is not None:
            _name, _x, _y, reach = island
            if offshore <= reach:
                # A beach at the water's edge rising to a hill in the middle, so
                # a hull grounds gently on the way in rather than hitting a wall.
                return ISLAND_Z * (1.0 - offshore / reach) ** 2
            if offshore <= reach * FORESHORE:
                # Shoaling water off the beach, from nothing at the tideline to
                # the full depth of the shelf a beach-width out. Without this an
                # island is a cliff, and a lead line would show twenty-four
                # metres right up to the moment she struck.
                return shelf * ((offshore - reach) / (reach * (FORESHORE - 1.0)))

        return shelf

    def bottom_type_at(self, position):
        """
        Args:
            position (WorldPosition): Where to sample.

        Returns:
            bottom (str): What the ground is made of.

        Notes:
            Rock around the islands and mud in the river, because what she strikes
            decides whether she comes off again. Grounding on the mud of a river
            bend is an afternoon; grounding on Outer Skerry is not.

        """
        if distance_to_river(position) <= RIVER_HALF_WIDTH:
            return MUD
        island, offshore = nearest_island(position)
        if island is not None and offshore <= island[3] * FORESHORE:
            return ROCK
        return SAND


class ExampleTiles(TileSource):
    """
    Builds a square of the example world on demand.

    Notes:
        Generated rather than tabulated. This world is twelve kilometres by six,
        which is nine hundred tiles at four hundred metres - a table nobody would
        want to read and nobody would want to edit. Building them as they are
        sailed over is also the honest demonstration of what a tile source is for.

    """

    def tile_for(self, cell, size):
        """
        Args:
            cell (tuple): `(region, x_index, y_index)`.
            size (float): Tile width in metres.

        Returns:
            tile (ExampleTile): This world's square. Never None - every square of
                this world is authored, even the empty ones, because the shelf
                falls away with easting and that is a real statement about depth.

        """
        return ExampleTile(cell=cell)


class ExampleSeabed(TiledMapProvider):
    """The ground under the example world."""

    def __init__(self, tide_provider=None):
        super().__init__(source=ExampleTiles(), tile_size=TILE_SIZE, tide_provider=tide_provider)


class ExampleCurrents(MaritimeCurrentProvider):
    """
    The stream, which is all river and no tide.

    Notes:
        Slack everywhere except between the banks. The pond has no current at all -
        Gary asked for a still sheet, and it is the control against which the
        river means anything. A boat that behaved the same on both would be
        demonstrating nothing.

    """

    def current_at(self, position, game_time):
        """
        Args:
            position (WorldPosition): Where to ask.
            game_time (float): Ignored. This river does not turn with the tide,
                which is a simplification and a deliberate one - one moving thing
                at a time is what a demonstration is for.

        Returns:
            current (CurrentVector): Set and drift.

        """
        if distance_to_river(position) > RIVER_HALF_WIDTH:
            return CurrentVector()
        return CurrentVector(set=river_set_at(position), drift=RIVER_DRIFT)
