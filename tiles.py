"""
The seabed, authored a square at a time.

A map provider that answers point queries is enough to sail over, and it is what this
contrib has had since phase 1. What it cannot do is answer the other question a hull
actually asks:

    what is on this stretch of bottom, between here and where I am going?

Answering that by searching every hazard in the world, for every vessel, on every tick, is
an O(n x m) sweep that looks fine with one ship and a reef and stops being fine with a
fleet and a coastline. So the world is tiled. A tile is a square of authored seabed - a
base elevation, what the ground is made of, and whatever discrete things are on it - and a
vessel loads only the tiles her track crosses.

**Tiles do not change what a depth query means.** `TiledMapProvider` is an ordinary
`MaritimeMapProvider`; every existing caller of `terrain_z_at` gets the same kind of answer
from the same interface. What is new is `hazards_touching`, and that is additive: the base
provider answers it with nothing, so grounding can ask unconditionally.

**A hazard is exact where sampling is not.** A hull is tested at seven points on her
outline, so something small enough fits between them - a limitation the sweep has always
been honest about. An authored hazard has a position and a radius, and it is measured
against the whole corridor she swept rather than against her sample points, so a rock
inside the water she displaces cannot be missed at all.

How small is small enough was measured rather than argued: two metres of rock, four metres
off the centreline of a six-metre beam, sits in the gap and is invisible to all five
hundred and sixty-seven points a sampled pass looks at.

**Unauthored water is not a hole in the world.** A tile that nobody has drawn falls through
to a base provider, which by default is deep open sea. A game maps its coastline and its
approaches and leaves the ocean alone, which is also how real charts work: the detail is
where the danger is.

**Tiles are loaded on demand and can be let go.** A world of ten thousand tiles keeps
resident only the ones being sailed over.

"""

from dataclasses import dataclass, field

from .bathymetry import DATUM, MaritimeMapProvider, ROCK, SAND
from .spatial import cell_bounds, cell_of, cells_touching, distance_to_track

# How wide a tile is, in metres. A kilometre is a compromise with two sides: small
# enough that a track rarely crosses more than four of them, and large enough that
# authoring a coastline is not a second career.
DEFAULT_TILE_SIZE = 1000.0

# Elevation of the sea floor where no tile has been authored. Deep enough that
# nothing grounds on it, so an unmapped ocean is open water rather than a hazard
# nobody drew.
UNMAPPED_TERRAIN_Z = DATUM - 200.0


@dataclass(frozen=True)
class Hazard:
    """
    A discrete thing on the bottom.

    Attributes:
        key (str): What it is called - `"the Whaleback"`, `"wreck of the Marigold"`.
        x (float): Easting of its centre, in metres.
        y (float): Northing of its centre, in metres.
        radius (float): How far it extends, in metres.
        top_z (float): Elevation of its shallowest point, relative to datum.
            Negative is submerged; positive dries at low water.
        bottom (str): What it is made of, which decides what it does to a hull.
        region (str): Which coordinate space it belongs to.

    Notes:
        A circle rather than an outline. A reef is not round, but the useful
        questions - is she standing into danger, did she pass close enough to
        touch - are answered by a radius, and an outline would be a great deal
        more authoring for an answer that is still approximate at the edges.

        `top_z` rather than a depth, because the whole system measures elevation
        against one datum and a hazard quoted as a depth would silently be a
        depth at some unstated state of tide.

    """

    key: str
    x: float
    y: float
    radius: float
    top_z: float
    bottom: str = ROCK
    region: str = "default"

    def __post_init__(self):
        """
        Raises:
            ValueError: If it has no name, or no extent. A hazard of zero radius
                is a point that nothing can ever be near, which is a hazard that
                does not work rather than a very small one.

        """
        if not self.key:
            raise ValueError("Hazard.key cannot be empty.")
        if self.radius <= 0.0:
            raise ValueError(f"Hazard.radius must be positive, got {self.radius!r}.")

    def covers(self, position):
        """
        Whether a point is over this hazard.

        Args:
            position (WorldPosition): Where to test.

        Returns:
            over (bool): True if the point is within its radius.

        """
        if position.region != self.region:
            return False
        return (position.x - self.x) ** 2 + (position.y - self.y) ** 2 <= self.radius**2

    def near_track(self, before, after, margin=0.0):
        """
        Whether a hull sweeping this track would touch it.

        Args:
            before (WorldPosition): Where the track starts.
            after (WorldPosition): Where it ends.
            margin (float, optional): How far either side of the track counts -
                half her beam.

        Returns:
            touched (bool): True if the corridor reaches it.

        Notes:
            The whole corridor, not the sample points. This is the exactness that
            tiles buy: a rock inside the water she displaces is caught whether or
            not any of her seven outline points happened to land on it.

        """
        if before.region != self.region:
            return False
        centre = before.__class__(x=self.x, y=self.y, z=0.0, region=self.region)
        return distance_to_track(centre, before, after) <= self.radius + max(0.0, margin)


@dataclass(frozen=True)
class Tile:
    """
    One square of authored seabed.

    Attributes:
        cell (tuple): `(region, x_index, y_index)`, from `spatial.cell_of`.
        terrain_z (float): Base elevation of the ground across this square.
        bottom (str): What that ground is made of.
        hazards (tuple): Discrete things standing on it.

    Notes:
        A flat base and a list of things standing proud of it, rather than a grid
        of soundings. A sounding grid is the obvious model and the wrong one for
        authoring: it makes a builder fill in a hundred numbers that are all the
        same to describe one shelf, and it still cannot say "there is a rock here
        that dries at low water" without inventing a resolution fine enough to
        hold it.

        A game wanting a real slope subclasses this and overrides `terrain_z_at`,
        which is one method and the same seam the map provider itself offers.

    """

    cell: tuple
    terrain_z: float = UNMAPPED_TERRAIN_Z
    bottom: str = SAND
    hazards: tuple = field(default_factory=tuple)

    def bounds(self, size=DEFAULT_TILE_SIZE):
        """
        Args:
            size (float, optional): Tile width in metres.

        Returns:
            bounds (tuple): `(west, south, east, north)`.

        """
        return cell_bounds(self.cell, size)

    def terrain_z_at(self, position):
        """
        Ground elevation at a point on this tile.

        Args:
            position (WorldPosition): Where to sample.

        Returns:
            terrain_z (float): The shallowest ground here.

        Notes:
            The shallowest of the base and anything standing on it, because that
            is what a keel meets. Taking the base alone would let a hull sail
            through a rock that the tile explicitly says is there.

        """
        highest = self.terrain_z
        for hazard in self.hazards:
            if hazard.covers(position) and hazard.top_z > highest:
                highest = hazard.top_z
        return highest

    def bottom_type_at(self, position):
        """
        What the ground is made of at a point.

        Args:
            position (WorldPosition): Where to sample.

        Returns:
            bottom (str): The hazard's material if one covers the point, else the
                tile's own.

        Notes:
            A hazard's material wins, and that matters more than it looks:
            touching sand is an inconvenience and touching rock holes her, so a
            reef head standing on a sandy shelf has to answer for itself.

        """
        for hazard in self.hazards:
            if hazard.covers(position):
                return hazard.bottom
        return self.bottom

    def hazards_near_track(self, before, after, margin=0.0):
        """
        Args:
            before (WorldPosition): Where the track starts.
            after (WorldPosition): Where it ends.
            margin (float, optional): Half her beam.

        Returns:
            hazards (tuple): Those the corridor reaches.

        """
        return tuple(hazard for hazard in self.hazards if hazard.near_track(before, after, margin))


class TileSource:
    """
    Where tiles come from.

    Notes:
        A game implements `tile_for` and the provider calls it once per tile, on
        first use. That is the seam that lets a world be authored in Python, read
        from files, generated from a seed, or pulled from a database, without the
        provider knowing which.

    """

    def tile_for(self, cell, size):
        """
        Build or fetch one tile.

        Args:
            cell (tuple): `(region, x_index, y_index)`.
            size (float): Tile width in metres.

        Returns:
            tile (Tile or None): The tile, or None if nobody has drawn that
                square - which is open water, not an error.

        """
        raise NotImplementedError("A tile source must implement tile_for().")


class DictTileSource(TileSource):
    """
    Tiles from a mapping, authored up front.

    Notes:
        The straightforward case, and enough for a game whose interesting water
        is a coastline and a few approaches. Anything larger wants a source that
        builds on demand, which is why `tile_for` is an interface rather than
        this class being the only option.

    """

    def __init__(self, tiles=()):
        """
        Args:
            tiles (iterable): `Tile` objects. Keyed by their own `cell`, so a
                tile cannot be filed under a square it does not describe.

        Raises:
            ValueError: If two tiles claim the same square. Silently keeping one
                of them would make the map depend on iteration order.

        """
        self._tiles = {}
        for tile in tiles:
            if tile.cell in self._tiles:
                raise ValueError(f"Two tiles both claim {tile.cell!r}.")
            self._tiles[tile.cell] = tile

    def tile_for(self, cell, size):
        """
        Args:
            cell (tuple): The square wanted.
            size (float): Ignored; these tiles were authored at a fixed scale.

        Returns:
            tile (Tile or None): The tile, or None for unmapped water.

        """
        return self._tiles.get(cell)

    def __len__(self):
        return len(self._tiles)

    def __repr__(self):
        return f"<DictTileSource: {len(self._tiles)} tiles>"


class TiledMapProvider(MaritimeMapProvider):
    """
    A seabed assembled from authored tiles, over an unmapped ocean.

    Notes:
        An ordinary map provider. Nothing that already asks for terrain or a depth
        changes, and a game swaps this in through `MARITIME_MAP_PROVIDER` like any
        other.

    """

    def __init__(self, source=None, base=None, tile_size=DEFAULT_TILE_SIZE, tide_provider=None):
        """
        Args:
            source (TileSource, optional): Where tiles come from. An empty source
                is a legitimate world - all open sea.
            base (MaritimeMapProvider, optional): What answers for water no tile
                covers. Defaults to deep, featureless sea.
            tile_size (float, optional): Tile width in metres.
            tide_provider (MaritimeTideProvider, optional): Supplies the surface.

        Raises:
            ValueError: If `tile_size` is not positive.

        """
        super().__init__(tide_provider=tide_provider)
        if tile_size <= 0.0:
            raise ValueError(f"tile_size must be positive, got {tile_size!r}.")
        self.source = source or DictTileSource()
        self.base = base
        self.tile_size = float(tile_size)
        self._resident = {}
        self.loads = 0

    # --- tiles ---------------------------------------------------------------

    def tile(self, cell):
        """
        The tile for one square, loading it if this is its first use.

        Args:
            cell (tuple): `(region, x_index, y_index)`.

        Returns:
            tile (Tile or None): The tile, or None for unmapped water.

        Notes:
            Caches the miss as well as the hit. Open ocean is the commonest answer
            there is, and a cache that only remembered tiles would ask the source
            about the same empty square on every tick of a long passage.

        """
        if cell in self._resident:
            return self._resident[cell]
        self.loads += 1
        tile = self.source.tile_for(cell, self.tile_size)
        self._resident[cell] = tile
        return tile

    def tile_at(self, position):
        """
        Args:
            position (WorldPosition): Where to look.

        Returns:
            tile (Tile or None): The tile under that point.

        """
        return self.tile(cell_of(position, self.tile_size))

    def tiles_touching(self, before, after, width=0.0):
        """
        Every tile a track crosses.

        Args:
            before (WorldPosition): Where the track starts.
            after (WorldPosition): Where it ends.
            width (float, optional): How wide the moving thing is, in metres.

        Returns:
            tiles (tuple): The authored tiles along it. Unmapped squares are left
                out rather than returned as None, since a caller wanting the
                hazards on a track has no use for the squares that have none.

        """
        found = []
        for cell in cells_touching(before, after, self.tile_size, margin=width / 2.0):
            tile = self.tile(cell)
            if tile is not None:
                found.append(tile)
        return tuple(found)

    def resident(self):
        """
        Returns:
            count (int): How many squares are currently held in memory, mapped
                and unmapped together.

        """
        return len(self._resident)

    def release(self):
        """
        Let go of every loaded tile.

        Returns:
            released (int): How many squares were dropped.

        Notes:
            For a long-running server that has sailed across a large world, and
            for a test that wants to prove a tile really is loaded on demand
            rather than at startup.

        """
        count = len(self._resident)
        self._resident.clear()
        return count

    # --- the map provider interface -----------------------------------------

    def terrain_z_at(self, position):
        """
        Ground elevation at a point.

        Args:
            position (WorldPosition): Where to sample.

        Returns:
            terrain_z (float): Elevation relative to datum.

        """
        tile = self.tile_at(position)
        if tile is not None:
            return tile.terrain_z_at(position)
        if self.base is not None:
            return self.base.terrain_z_at(position)
        return UNMAPPED_TERRAIN_Z

    def bottom_type_at(self, position):
        """
        What the ground is made of at a point.

        Args:
            position (WorldPosition): Where to sample.

        Returns:
            bottom (str): The bottom type.

        """
        tile = self.tile_at(position)
        if tile is not None:
            return tile.bottom_type_at(position)
        if self.base is not None:
            return self.base.bottom_type_at(position)
        return SAND

    def hazards_touching(self, before, after, width=0.0):
        """
        Every authored hazard a hull would sweep through.

        Args:
            before (WorldPosition): Where she started the step.
            after (WorldPosition): Where she is proposing to end it.
            width (float, optional): Her beam, in metres.

        Returns:
            hazards (tuple): What she would touch, shallowest first.

        Notes:
            Shallowest first so that a caller taking the first entry gets the
            worst one. Two rocks in the same corridor are not equally bad news,
            and the one that dries at low water is the one that stops her.

        """
        margin = max(0.0, width) / 2.0
        found = []
        for tile in self.tiles_touching(before, after, width):
            found.extend(tile.hazards_near_track(before, after, margin))
        return tuple(sorted(found, key=lambda hazard: -hazard.top_z))

    def charted_dangers(self, position, reach):
        """
        Every authored hazard inside the square a sheet covers.

        Args:
            position (WorldPosition): Where the sheet is centred.
            reach (float): How far it extends from there, in metres.

        Returns:
            dangers (tuple): What the survey recorded, shallowest first.

        Notes:
            A square rather than a circle, because that is the shape of the sheet
            and a rock just off the corner of the paper is still on the paper.

            Walks the tiles the box covers rather than every tile aboard. A chart
            is a few kilometres across and a world may be ten thousand tiles; the
            ones outside the sheet cannot contribute to it, and loading them to
            find that out would put the cost of a world into the cost of a chart.

        """
        reach = abs(reach)
        _, west, south = cell_of(position.offset(-reach, -reach), self.tile_size)
        _, east, north = cell_of(position.offset(reach, reach), self.tile_size)

        found = []
        for column in range(west, east + 1):
            for row in range(south, north + 1):
                tile = self.tile((position.region, column, row))
                if tile is None:
                    continue
                for hazard in tile.hazards:
                    if hazard.region != position.region:
                        continue
                    if abs(hazard.x - position.x) > reach:
                        continue
                    if abs(hazard.y - position.y) > reach:
                        continue
                    found.append(hazard)
        return tuple(sorted(found, key=lambda hazard: -hazard.top_z))

    def __repr__(self):
        return (
            f"<TiledMapProvider: {self.tile_size:.0f} m tiles, "
            f"{self.resident()} resident, {self.loads} loaded>"
        )
