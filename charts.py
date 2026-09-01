"""
Charts: what somebody wrote down about the sea, which is not the same as the sea.

A chart is knowledge. It was made by a person, in a boat, at a moment, and everything about
it is downstream of that: it covers only where they went, it is only as good as their
instruments and their care, and it has been going quietly out of date ever since. The
seabed silts, banks shift, wrecks arrive, and none of that reaches the paper.

    the sea         what `MaritimeMapProvider` says, which is true
    the chart       what somebody recorded, which is not
    the difference  where ships are lost

**A chart is wrong in the same places every time.** That is the whole design. Noise regenerated
on every reading would be unlearnable - a navigator could not come to distrust the northern
approaches, because the northern approaches would be differently wrong each glance. Here the
error is a deterministic function of the chart's seed and the position, so a bad patch is a
*place* on the paper, and a pilot who has sounded it once knows to sound it again.

**Depths are soundings against the datum, not the water in front of you.** A chart records
what the leadsman found relative to chart datum, and applying the state of the tide is the
navigator's job. Reading nine fathoms off the paper at low water is how a ship with a
nine-fathom draught ends up aground on a bank marked deep enough.

**Off the chart is a state, not a failure.** A vessel outside her chart's coverage has no
soundings at all, which is a real and dangerous situation and reads very differently from
having bad ones.

"""

import math
from dataclasses import dataclass

from .bathymetry import UNKNOWN

# How far a chart's soundings can be out, in metres, at the worst quality. A
# chart this bad is a rumour with a compass rose on it, and the number is
# deliberately large enough to ground a ship that trusts it.
MAX_CHART_ERROR = 12.0

# Game seconds after which a chart has aged out of any usefulness. Roughly a
# decade at a four-to-one clock; a survey does not become wrong all at once, and
# this is where the decay finishes rather than where it starts.
CHART_LIFETIME = 10.0 * 365.0 * 24.0 * 3600.0

# How much of a chart's quality age can take away. Even an ancient survey got the
# shape of the coast broadly right, so age degrades a chart towards useless
# rather than to nothing.
AGE_PENALTY = 0.6


@dataclass(frozen=True)
class Chart:
    """
    A surveyed record of one patch of sea.

    Attributes:
        key (str): What the chart is called.
        region (str): Which coordinate space it covers.
        west (float): Western edge, in metres.
        east (float): Eastern edge, in metres.
        south (float): Southern edge, in metres.
        north (float): Northern edge, in metres.
        quality (float): How well it was surveyed, from 0 to 1.
        surveyed_at (float): Game time the survey was made, in seconds.
        seed (int): Fixes where this chart is wrong.
        maker (str): Who made it.

    Notes:
        The bounds are a rectangle because a chart is a sheet of paper. Real
        coverage is ragged, and a game wanting that supplies several charts.

    """

    key: str
    region: str = "default"
    west: float = 0.0
    east: float = 0.0
    south: float = 0.0
    north: float = 0.0
    quality: float = 1.0
    surveyed_at: float = 0.0
    seed: int = 0
    maker: str = "unknown"

    def covers(self, position):
        """
        Whether this chart says anything about a place.

        Args:
            position (WorldPosition): Where to ask.

        Returns:
            covered (bool): True if the place is on the sheet.

        """
        return (
            position.region == self.region
            and self.west <= position.x <= self.east
            and self.south <= position.y <= self.north
        )

    def quality_at(self, game_time):
        """
        How much this chart can be trusted now.

        Args:
            game_time (float): Game time in seconds.

        Returns:
            quality (float): From 0 to 1.

        Notes:
            Decays with age. A survey does not become wrong all at once - the
            coast stays where it was - so age takes only part of the quality
            away, and an ancient chart is a poor guide rather than a blank sheet.

        """
        if CHART_LIFETIME <= 0.0:
            return max(0.0, min(1.0, self.quality))
        age = max(0.0, game_time - self.surveyed_at) / CHART_LIFETIME
        decay = AGE_PENALTY * min(1.0, age)
        return max(0.0, min(1.0, self.quality) * (1.0 - decay))


#: How big a patch of sea one survey error covers, in metres.
#:
#: A survey is wrong about areas rather than about points, so the error has to vary over a
#: stretch of water a navigator could notice crossing. It was two hundred and fifty metres,
#: which is not an area - it is a sounding - and it was small enough to destroy the thing
#: the chart is for.
#:
#: **A vertical error becomes a horizontal one, and how much depends on the slope.** On a
#: gently shelving coast rising a metre in a kilometre, a chart of quality 0.85 is out by
#: under two metres of depth and therefore by *seventeen hundred metres of shoreline*. When
#: that displacement is larger than the patch it varies over, the drawn coastline folds
#: back through itself: it stops being a line that is in the wrong place and becomes a
#: scribble, breaking into fragments and doubling its own length.
#:
#: Measured on generated coast at a ten-kilometre reach, against about 24 km of real shore:
#:
#:      patch      runs drawn      coast drawn
#:        250 m        4              34.6 km      shredded, and 10 km of it is noise
#:      1,000 m        1              24.5 km
#:      3,000 m        1              24.1 km
#:      8,000 m        1              24.5 km
#:
#: Two kilometres. Comfortably past where it stops shredding on the coasts measured, small
#: enough that one part of a bay can still be surveyed better than another, and large
#: enough that what a pilot learns is "this chart puts the point half a mile too far west"
#: - which is a thing he can carry - rather than "this chart is fuzzy", which is not.
ERROR_PATCH = 2000.0


def _error_at_corner(chart, east, north):
    """
    Args:
        chart (Chart): The chart, whose seed makes its errors its own.
        east (int): Patch index, east-west.
        north (int): Patch index, north-south.

    Returns:
        signed (float): In -1..1, the same for ever for this chart and this corner.

    """
    key = chart.seed * 1_000_003 + east * 73_856_093 + north * 19_349_663
    scrambled = (key * 2_654_435_761) % 4_294_967_296
    return scrambled / 2_147_483_648.0 - 1.0


def _sounding_error(chart, position, quality):
    """
    How wrong this chart is at this exact spot.

    Args:
        chart (Chart): The chart.
        position (WorldPosition): Where to ask.
        quality (float): The chart's quality now.

    Returns:
        error (float): Metres, positive or negative.

    Notes:
        A deterministic function of the chart's seed and the place, never a fresh
        random number. Regenerating noise on every reading would make a bad chart
        unlearnable: a navigator could not come to distrust one approach, because
        it would be differently wrong at every glance. This way the error is a
        feature of the paper, and a pilot who has caught it out once knows where
        to sound.

        Varying over a patch of sea rather than between one metre and the next,
        because a survey is wrong about *areas*.

        **Interpolated between patches, not stepped between them.** The first
        version took one value per two-hundred-and-fifty-metre square, which made
        the charted seabed a staircase: on a shelf truly falling a fifth of a metre
        every fifty, the paper showed four-and-a-half-metre cliffs at every patch
        boundary. A lead cast either side of an invisible line disagreed by more
        than the depth of the water changing under it.

        It also made the chart worse the more finely it was drawn. Sampling closer
        together than a patch resolves the *patch edges*, so a coastline traced at
        two hundred metres a sample followed the error grid rather than the shore -
        on a poor chart it ran to two hundred and seventy kilometres where the real
        coast was fifty-five.

        Smoothstepped so the slope matches at the joins as well as the value. A
        merely linear blend has a crease along every patch edge, and a crease in a
        seabed is a ridge that nothing put there.

    """
    east = position.x / ERROR_PATCH
    north = position.y / ERROR_PATCH
    west_of, south_of = int(math.floor(east)), int(math.floor(north))

    across = east - west_of
    up = north - south_of
    across = across * across * (3.0 - 2.0 * across)
    up = up * up * (3.0 - 2.0 * up)

    south_west = _error_at_corner(chart, west_of, south_of)
    south_east = _error_at_corner(chart, west_of + 1, south_of)
    north_west = _error_at_corner(chart, west_of, south_of + 1)
    north_east = _error_at_corner(chart, west_of + 1, south_of + 1)

    southern = south_west + (south_east - south_west) * across
    northern = north_west + (north_east - north_west) * across
    signed = southern + (northern - southern) * up
    return signed * MAX_CHART_ERROR * (1.0 - quality)


#: How far a ground-truth chart reaches from the origin, in metres.
#:
#: A thousand kilometres past a great circle of the largest planet anybody is going to
#: sail - deliberately absurd, because the number's only job is to be larger than any
#: coordinate a world can produce and a number chosen to be *plausible* would eventually
#: be crossed by somebody's map and cut the world off at a straight line nobody put there.
EVERYWHERE = 1.0e9


def ground_truth(region="default", game_time=0.0):
    """
    A chart of everywhere, with nothing wrong on it.

    Args:
        region (str, optional): Which coordinate space it covers.
        game_time (float, optional): Now, so it never reads as an old survey.

    Returns:
        chart (Chart): Perfect, unbounded, and not a thing anybody can own.

    Notes:
        **Not a chart a game should ever hand to a player.** It exists for the development
        switch that draws the sea as it truly is: quality 1.0 makes `_sounding_error`
        exactly zero rather than merely small, and bounds past any real coordinate make
        `covers` always true, so what comes back is the world rather than a record of it.

        Stamped with the time it is made rather than with zero, because `quality_at` decays
        a survey from the moment it was taken and a chart surveyed at the beginning of time
        would be worthless by the afternoon. There is no error to decay *into* at full
        quality, but a chart whose quality is quietly 0.4 while claiming to be the truth is
        the kind of thing that is discovered a year later.

        Made fresh each time rather than kept as a constant, for that reason and because a
        single shared instance would carry one region for a world that can have several.

    """
    return Chart(
        key="the world itself",
        region=region,
        west=-EVERYWHERE,
        east=EVERYWHERE,
        south=-EVERYWHERE,
        north=EVERYWHERE,
        quality=1.0,
        surveyed_at=game_time,
        seed=0,
        maker="nobody - this is the ground, not a survey of it",
    )


def charted_terrain_z_at(chart, position, game_time, world, seabed=None):
    """
    What the chart says the bottom is, here.

    Args:
        chart (Chart): The chart to read.
        position (WorldPosition): Where to ask.
        game_time (float): Game time in seconds.
        world (MaritimeMapProvider): The real seabed.
        seabed (callable, optional): Something else to ask for the true ground, taking a
            position. Defaults to asking the world directly.

    Returns:
        terrain_z (float or None): Charted ground elevation against the datum, or
            None if the place is off the chart.

    Notes:
        Reads the truth and then spoils it, rather than storing thousands of
        authored soundings. A game gets a chart of any area for free, wrong in
        fixed places, and can still author a provider of its own if it wants a
        specific lie in a specific bay.

        `seabed` exists so a caller sounding thousands of points can hand in a
        remembering reader - see `seabed`, where the measurement is - without
        the rule for what a chart says being written down twice. Reading the
        ground is ninety-eight per cent of the cost here and the lie on top is
        two, so the thing worth caching is the ground, and the thing worth
        keeping in one place is the lie.

    """
    if not chart.covers(position):
        return None
    quality = chart.quality_at(game_time)
    ground = world.terrain_z_at(position) if seabed is None else seabed(position)
    return ground + _sounding_error(chart, position, quality)


def charted_depth_at(chart, position, game_time, world):
    """
    What the chart says the depth is, at the datum.

    Args:
        chart (Chart): The chart to read.
        position (WorldPosition): Where to ask.
        game_time (float): Game time in seconds.
        world (MaritimeMapProvider): The real seabed.

    Returns:
        depth (float or None): Metres of water at chart datum, or None if the
            place is off the chart.

    Notes:
        At the datum, and deliberately not at the present state of the tide.
        Charts record soundings against a fixed reference and applying the tide
        is the navigator's job; a system that quietly did it for them would
        remove the commonest way a careful sailor still goes aground.

    """
    charted = charted_terrain_z_at(chart, position, game_time, world)
    if charted is None:
        return None
    return max(0.0, -charted)


def charted_bottom_at(chart, position, game_time, world):
    """
    What the chart says the ground is made of.

    Args:
        chart (Chart): The chart to read.
        position (WorldPosition): Where to ask.
        game_time (float): Game time in seconds.
        world (MaritimeMapProvider): The real seabed.

    Returns:
        bottom (str): A bottom type, or `UNKNOWN` off the chart or on a poor one.

    Notes:
        Bottom type survives age and poor survey better than depths do - the
        nature of the ground changes far more slowly than its level - but a bad
        chart still does not know, and says so rather than guessing.

    """
    if not chart.covers(position):
        return UNKNOWN
    if chart.quality_at(game_time) < 0.4:
        return UNKNOWN
    return world.bottom_type_at(position)


def discrepancy(chart, position, game_time, world):
    """
    How wrong the chart is here, in metres.

    Args:
        chart (Chart): The chart.
        position (WorldPosition): Where to ask.
        game_time (float): Game time in seconds.
        world (MaritimeMapProvider): The real seabed.

    Returns:
        error (float or None): Charted ground less true ground. Positive means
            the chart shows deeper water than there is, which is the direction
            that sinks ships. None off the chart.

    Notes:
        Not for showing a player - it is the number nobody aboard can have. It
        exists for tests, for staff tools, and for a game deciding whether a
        chart is worth what a dealer is asking for it.

    """
    charted = charted_terrain_z_at(chart, position, game_time, world)
    if charted is None:
        return None
    return charted - world.terrain_z_at(position)


def best_chart_for(charts, position):
    """
    The most trustworthy chart covering a place.

    Args:
        charts (iterable): `Chart` objects.
        position (WorldPosition): Where to ask.

    Returns:
        chart (Chart or None): The best one covering it, or None if the place is
            off every sheet aboard.

    Notes:
        Best rather than first, because a ship carries several and a navigator
        reaches for the good one. Ties go to the more recent survey.

    """
    covering = [chart for chart in charts if chart.covers(position)]
    if not covering:
        return None
    return max(covering, key=lambda chart: (chart.quality, chart.surveyed_at))


class Charted:
    """
    The charts a vessel carries, and what they say about where she is.

    Notes:
        The Evennia-side face of `charts`. A ship's charts are hers - bought,
        inherited, stolen or drawn - so they live on the hull rather than in the
        world, and two vessels in the same water can honestly disagree about what
        is under them.

    """

    def at_object_creation(self):
        """Set up this part of a newly created vessel."""
        super().at_object_creation()
        self.db.charts = []

    @property
    def charts(self):
        """
        Returns:
            charts (tuple): Every chart aboard.

        """
        return tuple(self.db.charts or ())

    def add_chart(self, chart):
        """
        Put a chart aboard.

        Args:
            chart (Chart): The chart.

        Returns:
            vessel (Vessel): This hull, for chaining.

        Raises:
            ValueError: If a chart of that name is already aboard.

        Notes:
            Reads the whole list, appends and writes it back once. Mutating the
            stored list in place would commit on every touch - see Law 10.

        """
        aboard = list(self.db.charts or ())
        if any(other.key == chart.key for other in aboard):
            raise ValueError(f"She already carries a chart called {chart.key!r}.")
        aboard.append(chart)
        self.db.charts = aboard
        return self

    def chart_here(self):
        """
        The best chart covering where she is.

        Returns:
            chart (Chart or None): The chart to read, or None if she is off every
                sheet aboard - which is a real and dangerous state rather than an
                error.

        """
        position = self.maritime_position
        if position is None:
            return None
        return best_chart_for(self.charts, position)

    def charted_depth(self):
        """
        What the chart says the water is, at the datum.

        Returns:
            depth (float or None): Metres at chart datum, or None off the chart.

        Notes:
            At the datum, not at the present tide. Applying the state of the tide
            is the navigator's job, and doing it for them here would remove the
            commonest way a careful sailor still goes aground.

        """
        from . import config

        position = self.maritime_position
        chart = self.chart_here()
        if chart is None or position is None:
            return None
        return charted_depth_at(chart, position, config.time_provider().now(), self.map_here())
