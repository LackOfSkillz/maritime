"""
Terrain elevation, tides, and the water depth derived from them.

There is no depth map. There is one terrain elevation field that happens to cross zero:

    Z +40     cliff
    Z  +1     beach
    Z   0     datum
    Z  -3     shoal
    Z  -20    coastal shelf
    Z -3000   ocean floor

Water depth is the difference between the current water surface and the terrain beneath
it, so it is *computed*, never stored. That is what makes tides a real system rather than
decoration: sea level is a datum, not a constant, and moving the surface changes every
depth in the world without touching any terrain.

    High water:  surface +1.5, seabed -3.0  ->  4.5 m of water
    Low water:   surface -0.8, seabed -3.0  ->  2.2 m of water

Because the two share a model, the shoreline is simply where terrain crosses the current
surface - and it moves with the tide on its own.

**Depth queries take a game time.** A depth without a time is a question about the datum,
not about the water actually present, and the difference is the one that runs a vessel
aground. The argument is required rather than defaulted so the mistake cannot be made
quietly.

"""

from .position import WorldPosition

# Sea level. Depths are measured against this, and tides move the surface around it.
DATUM = 0.0

# What the seabed is made of. This decides what happens when a hull finds it: mud
# and sand hold a vessel and often give her back on the next tide, while reef and
# rock hole her. Games may add their own.
MUD = "mud"
SAND = "sand"
GRAVEL = "gravel"
WEED = "weed"
REEF = "reef"
ROCK = "rock"
UNKNOWN = "unknown"

BOTTOM_TYPES = (MUD, SAND, GRAVEL, WEED, REEF, ROCK, UNKNOWN)

# Bottoms that take a hull rather than hold it. Touching these at speed is a
# different event from grounding on sand.
FOUL_GROUND = (REEF, ROCK)


class MaritimeTideProvider:
    """
    Supplies the elevation of the water surface over time.

    Separated from the map because tides are a *temporal* model over an unchanging
    seabed. A game can supply harmonic tides, a story-driven flood, or none at all,
    without touching its terrain.

    """

    def surface_z_at(self, position, game_time):
        """
        Elevation of the water surface at a point and time.

        Args:
            position (WorldPosition): Where to sample.
            game_time (float): Game time in seconds, from the run's time provider.

        Returns:
            surface_z (float): Water surface elevation in metres, relative to datum.

        """
        raise NotImplementedError("A tide provider must implement surface_z_at().")


class FlatTideProvider(MaritimeTideProvider):
    """
    A motionless sea surface.

    The default, and the right choice for a game that does not want tides: the
    surface sits at the datum and never moves, so depth is simply the negated
    terrain elevation.

    """

    def __init__(self, surface_z=DATUM):
        """
        Args:
            surface_z (float, optional): The fixed surface elevation. Useful for a
                lake or a flooded region sitting above or below the world datum.

        """
        self.surface_z = float(surface_z)

    def surface_z_at(self, position, game_time):
        """
        The fixed surface elevation, whatever the position or time.

        Args:
            position (WorldPosition): Ignored.
            game_time (float): Ignored.

        Returns:
            surface_z (float): The constant surface elevation.

        """
        return self.surface_z


class MaritimeMapProvider:
    """
    Answers questions about the world's terrain.

    A game supplies its own by implementing `terrain_z_at`. Everything else here is
    derived from that plus the tide provider, so a game cannot accidentally produce
    a depth inconsistent with its own seabed.

    """

    def __init__(self, tide_provider=None):
        """
        Args:
            tide_provider (MaritimeTideProvider, optional): Supplies the water
                surface. Defaults to a motionless surface at the datum.

        """
        self.tides = tide_provider or FlatTideProvider()

    def terrain_z_at(self, position):
        """
        Ground elevation at a point, ignoring any water above it.

        Args:
            position (WorldPosition): Where to sample. Only x, y and region are
                used; the position's own z is irrelevant to what the ground does.

        Returns:
            terrain_z (float): Elevation in metres relative to datum. Negative is
                below datum - seabed, shoal, reef. Positive is dry land.

        """
        raise NotImplementedError("A map provider must implement terrain_z_at().")

    def bottom_type_at(self, position):
        """
        What the seabed is made of at a point.

        Args:
            position (WorldPosition): Where to sample.

        Returns:
            bottom (str): One of the bottom types.

        Notes:
            Sand by default, because it is the forgiving answer and a map that
            has not been surveyed should not silently be strewn with reefs. A
            game supplies real ground by overriding this.

        """
        return SAND

    def hazards_touching(self, before, after, width=0.0):
        """
        Discrete hazards a hull would sweep through on this track.

        Args:
            before (WorldPosition): Where the step started.
            after (WorldPosition): Where it would end.
            width (float, optional): Her beam, in metres.

        Returns:
            hazards (tuple): What she would touch, shallowest first.

        Notes:
            Nothing, unless a provider authors real hazards - see `tiles`. It is
            on the base class rather than duck-typed so that grounding can ask
            every provider unconditionally instead of guessing whether this one
            answers.

            The point of asking at all: a hull is sampled at seven points on
            her outline, and something small enough fits between them. A hazard
            with a position and a radius is measured against the whole corridor
            she swept and cannot.

        """
        return ()

    def geographic_at(self, position):
        """
        Where in the world a position is, in degrees.

        Args:
            position (WorldPosition): Where to ask.

        Returns:
            place (tuple or None): `(latitude, longitude)`, or None for a world with no
                geography to report.

        Notes:
            Nothing, unless a game's world is somewhere. A flat seabed defined by an
            arithmetic ramp has no latitude and should not invent one; a generated planet
            has a real answer and can give it.

            What it buys is the graticule - the meridians and parallels a chart is ruled
            with. They are worth having for their own sake, and they are also the only
            honest way a flat sheet can show that the world is round: meridians converge,
            and at a wide enough view a navigator can see them doing it.

            It leaks nothing. A navigator knows his latitude by observation and his
            longitude by reckoning; that is the job.

        """
        return None

    def charted_dangers(self, position, reach):
        """
        Discrete hazards near enough to belong on a chart, drawn as symbols.

        Args:
            position (WorldPosition): Where the sheet is centred.
            reach (float): How far the sheet extends from there, in metres.

        Returns:
            dangers (tuple): What a survey would have recorded, shallowest first.

        Notes:
            Nothing, unless a provider authors real hazards - the same terms as
            `hazards_touching`, and on the base class for the same reason: the
            chart asks every provider unconditionally rather than guessing which
            ones answer.

            **The other half of a hazard, and the half that was missing.** A rock
            that grounding knows about and the chart does not is worse than a rock
            drawn nowhere at all, because the captain has looked at the paper, seen
            open water, and is entitled to believe it.

            It has to be a symbol rather than a sounding. A chart samples the
            seabed on a grid, and something narrower than that grid is not smoothed
            away - it is *missed*, and missed differently depending on where the
            grid happens to fall relative to it, so it would appear and vanish as
            she sailed. Which is why real charts give an isolated danger its own
            mark instead of trusting a contour to imply one.

            Charted, not sighted. This is what the survey recorded, so it stays on
            the paper in fog and at night exactly as the coastline does. A game
            that wants a rock to be a discovery should not answer with it here
            until somebody has discovered it.

        """
        return ()

    def sea_surface_z_at(self, position, game_time):
        """
        Elevation of the water surface at a point and time.

        Args:
            position (WorldPosition): Where to sample.
            game_time (float): Game time in seconds.

        Returns:
            surface_z (float): Water surface elevation in metres.

        """
        return self.tides.surface_z_at(position, game_time)

    def water_depth_at(self, position, game_time):
        """
        How much water stands over the terrain at a point and time.

        Args:
            position (WorldPosition): Where to sample.
            game_time (float): Game time in seconds. Required - a depth without a
                time is a question about the datum rather than the water actually
                present, and that difference is what runs a vessel aground.

        Returns:
            depth (float): Metres of water. Zero where the terrain stands above
                the surface.

        Notes:
            Derived from the surface and the terrain, never stored. Do not override:
            a subclass supplying its own depth could contradict its own seabed, and
            grounding trusts these two to agree.

            Clamped at zero rather than going negative. Dry land has no water, and a
            negative depth would read as "water below the seabed" to anything
            comparing against a draft. How far above water the ground stands is
            still available from `terrain_z_at`.

        """
        above_ground = self.sea_surface_z_at(position, game_time) - self.terrain_z_at(position)
        return max(0.0, above_ground)

    def is_submerged_at(self, position, game_time):
        """
        Whether there is any water over the terrain here.

        Args:
            position (WorldPosition): Where to sample.
            game_time (float): Game time in seconds.

        Returns:
            submerged (bool): True where water stands over the ground.

        Notes:
            The shoreline test. Because terrain and surface share one model, the
            line this traces moves with the tide without any terrain changing.

        """
        return self.water_depth_at(position, game_time) > 0.0

    def surface_position(self, position, game_time):
        """
        The same horizontal point, at the water surface.

        Args:
            position (WorldPosition): Point to project.
            game_time (float): Game time in seconds.

        Returns:
            position (WorldPosition): A position at the surface elevation.

        Notes:
            Where a floating thing belongs: a vessel, a swimmer, drifting wreckage.

        """
        return position.with_z(self.sea_surface_z_at(position, game_time))

    def seabed_position(self, position, game_time=None):
        """
        The same horizontal point, on the ground.

        Args:
            position (WorldPosition): Point to project.
            game_time (float, optional): Unused. Accepted so this reads
                symmetrically with `surface_position` at call sites.

        Returns:
            position (WorldPosition): A position at the terrain elevation.

        Notes:
            Where a sinking thing comes to rest. Terrain does not move with time,
            which is why the time argument is optional here and required for depth.

        """
        return position.with_z(self.terrain_z_at(position))


class FlatSeaMapProvider(MaritimeMapProvider):
    """
    A featureless sea of uniform depth.

    Not a toy: it is the sane default for a game that wants vessels before it wants
    bathymetry, and it is what most tests should use, since a constant seabed makes
    a failing depth assertion unambiguous.

    """

    def __init__(self, depth=100.0, tide_provider=None):
        """
        Args:
            depth (float, optional): Metres of water everywhere, measured from the
                datum. Stored internally as a terrain elevation, since terrain is
                what this model considers real.
            tide_provider (MaritimeTideProvider, optional): Supplies the surface.

        Raises:
            ValueError: If depth is negative. A negative depth is land, which this
                provider does not model - use a real map for that.

        """
        super().__init__(tide_provider=tide_provider)
        if depth < 0.0:
            raise ValueError(f"Depth cannot be negative, got {depth!r}. Use a map with terrain.")
        self._terrain_z = DATUM - float(depth)

    def terrain_z_at(self, position):
        """
        The same seabed elevation everywhere.

        Args:
            position (WorldPosition): Ignored.

        Returns:
            terrain_z (float): The uniform seabed elevation.

        """
        return self._terrain_z


__all__ = (
    "DATUM",
    "BOTTOM_TYPES",
    "FOUL_GROUND",
    "MUD",
    "SAND",
    "GRAVEL",
    "WEED",
    "REEF",
    "ROCK",
    "UNKNOWN",
    "MaritimeTideProvider",
    "FlatTideProvider",
    "MaritimeMapProvider",
    "FlatSeaMapProvider",
    "WorldPosition",
)
