"""
Dredged channels: a world stating that there is water into a harbour, and how much.

Every other way this contrib lets a world describe its ground makes the sea *shallower* - a
hazard, a bank, a rock somebody charted. There was no way to say the opposite, and the
opposite is what a harbour is. A quay is only a quay because somebody keeps a way in to it
open, and on a shelving coast that means a cut through the bar, dredged to a depth and
maintained at it.

Without one, an approach is only as good as the ground happens to be. On the coast this was
written for, six metres of water is most of a kilometre out and the last mile in to the piers
runs over two and three - so a ship ordered alongside would be told, correctly, that there is
no safe water between here and there. The pier is fine. The way to it is not, because nobody
had ever dug one.

    Channel          a cut: from where, to where, how wide, how deep
    Dredged          any map provider, with the channels cut through it
    channels_to()    a cut into every quay in the game, worked out from the quays

**A world does not author these.** Put down a room with berths in it and the engine digs the
way in: it reads what the berths advertise, takes the deepest of them, finds the nearest sea
deep enough, and cuts a channel between the two. A harbour that appears when somebody runs a
build command has an approach the moment it appears, and a harbour whose berths are later
deepened has its channel deepened with them.

That is the whole point of doing it this way. The alternative - a list of cuts written down
beside the world - is a second description of the same harbour, and the two would part
company the first time anybody moved a pier.

**It only ever deepens.** A channel over ground that is already deeper than the dredged
depth changes nothing. That is not an optimisation - a cut that *raised* the seabed would be
a bar built by the dredger, and the arithmetic that would do it is one comparison away from
the arithmetic that does not.

**The sides slope, because a dredger's sides slope.** A vertical wall would be a trench with
cliffs, and a hull half a metre outside it would find three metres of water where a hull half
a metre inside found eight. So the full depth runs across the bottom width and then ramps out
to meet the natural ground over a batter, which is both what a real cut looks like and what
keeps a chart of one legible.

**Nothing else is touched.** Bottom type, hazards, landmarks and geography all come from the
provider underneath, because a dredged channel changes the depth of the water and not what
is charted in it. A rock left standing in a channel is a rock still standing in a channel,
and a world that dredges over its own hazards has said two contradictory things and should
hear about it from the grounding check rather than have one of them silently win.
"""

import math
from dataclasses import dataclass

from .bathymetry import MaritimeMapProvider

#: How far the sides slope out from the bottom width, in metres, unless a channel says.
#:
#: Fifty. A dredged cut is battered rather than walled - the spoil will not stand up
#: vertically under water and nobody would pay to make it - and fifty metres of ramp on a
#: cut ten metres deep is a slope of one in five, which is about what a maintained channel
#: in soft ground actually holds.
BATTER = 50.0


@dataclass(frozen=True)
class Channel:
    """
    One cut, kept open to a depth.

    Attributes:
        key (str): What it is called, for charts and for whoever has to maintain it.
        start (WorldPosition): The seaward end - usually the mark ships come in by.
        end (WorldPosition): The inner end - usually the head of the pier it serves.
        depth (float): Metres of water below the datum, guaranteed the length of it.
        width (float): The width of the flat bottom, in metres.
        batter (float): How far the sides slope out beyond that, in metres.

    Notes:
        A straight cut, and deliberately only that. Real channels bend, and a world that
        needs a bend lays two channels end to end - which is honest, costs nothing, and
        avoids putting a spline solver in the middle of the seabed.

        `depth` is against the *datum*, like every other depth in this contrib, so a channel
        does not get shallower at low water in the arithmetic while getting shallower in
        fact. The tide is applied on top by whoever asks what the water is doing now.

    """

    key: str
    start: object
    end: object
    depth: float
    width: float = 120.0
    batter: float = BATTER

    @property
    def half(self):
        """
        Returns:
            metres (float): Half the flat bottom width.

        """
        return max(0.0, self.width) / 2.0

    def reach(self):
        """
        Returns:
            metres (float): How far from the centre line the cut has any effect at all.

        """
        return self.half + max(0.0, self.batter)

    def cut_at(self, position):
        """
        How deep this channel is kept at a point, if it reaches there.

        Args:
            position (WorldPosition): Where to ask.

        Returns:
            depth (float or None): Metres below datum, or None if the point is outside
                the cut entirely.

        Notes:
            Full depth across the bottom, then ramped linearly out to nothing over the
            batter. Linear rather than smoothed: a dredger cuts a slope, not a curve, and a
            chart of one shows straight contours down the sides.

            Off the ends as well as off the sides, because the distance is measured to the
            *segment*. A cut that carried on past its own ends would dig a trench across
            the harbour and out the other side.

        """
        off = _off_the_line(position, self.start, self.end)
        if off is None or off > self.reach():
            return None
        if off <= self.half or self.batter <= 0.0:
            return self.depth
        return self.depth * (1.0 - (off - self.half) / self.batter)


def _off_the_line(position, start, end):
    """
    How far a point lies from a segment.

    Args:
        position (WorldPosition): The point.
        start (WorldPosition): One end.
        end (WorldPosition): The other.

    Returns:
        metres (float or None): The distance, or None if the point is in another region.

    Notes:
        Clamped to the segment rather than to the infinite line, which is what makes a
        channel have ends. The degenerate case - a channel whose ends are the same point -
        falls out as the distance to that point, which is a round hole and is a perfectly
        reasonable thing for a world to dig.

    """
    if getattr(position, "region", None) != getattr(start, "region", None):
        return None

    run_x, run_y = end.x - start.x, end.y - start.y
    span = run_x * run_x + run_y * run_y
    if span <= 0.0:
        return math.hypot(position.x - start.x, position.y - start.y)

    along = ((position.x - start.x) * run_x + (position.y - start.y) * run_y) / span
    along = max(0.0, min(1.0, along))
    return math.hypot(
        position.x - (start.x + run_x * along),
        position.y - (start.y + run_y * along),
    )


#: How much deeper than the deepest berth a channel is cut, in metres.
#:
#: Two. A channel exactly as deep as the berth at the end of it is one a ship touches on the
#: way in to a berth she fits, which is the worst possible arrangement: she is stopped a
#: hundred metres short of the place that would have taken her. It also leaves room for the
#: berth to be dredged deeper later without the approach becoming the limit.
CHANNEL_MARGIN = 2.0

#: How wide the flat bottom is, in metres.
#:
#: A hundred and eighty - fifteen times the beam of the largest hull in the shipyard's book,
#: and far wider than a working channel would ever be cut. That is deliberate. This number
#: decides whether somebody steering for a pier by eye, at night, with the set on his beam,
#: stays in the water; a cut that has to be threaded is a cut that will drown a beginner, and
#: a game is not a port authority trying to save on spoil.
CHANNEL_WIDTH = 180.0

#: How far the channel goes on past the first deep water it finds, in metres.
#:
#: Five hundred. The first point deep enough may be a hole with a bar beyond it, and a
#: channel that ended there would put a ship aground on the way *out* - which is the failure
#: nobody tests for, because everyone arrives before they leave. So the seaward end is only
#: accepted once the water has stayed deep enough for this whole run, and the cut is carried
#: out to the far end of it.
SEAWARD_HOLDS = 500.0

#: How far out to look for water deep enough to start a channel from, and in what steps.
#:
#: Ten kilometres. On a shore shelving gently enough to need dredging at all the sea can be a
#: very long way out - this coast wants most of a kilometre for six metres - and a search that
#: gave up early would leave a harbour with no approach and no explanation.
SEAWARD_SEARCH = 10000.0
SEAWARD_STEP = 50.0

#: How many directions to try when looking for the sea.
#:
#: Sixteen, which is the compass a pilot would name them by. Enough that a harbour at the head
#: of a narrow inlet finds the way out; few enough that finding it costs a few hundred
#: soundings once, at load, against a seabed that remembers.
SEAWARD_BEARINGS = 16


def seaward_from(position, world, wanted, reach=SEAWARD_SEARCH, step=SEAWARD_STEP):
    """
    The nearest water of a given depth, in whatever direction that turns out to be.

    Args:
        position (WorldPosition): Where to start - a berth.
        world (MaritimeMapProvider): The undredged ground.
        wanted (float): How much water to look for, in metres below datum.
        reach (float, optional): How far to look.
        step (float, optional): How finely.

    Returns:
        found (WorldPosition or None): Where the sea is, or None if it is not within reach.

    Notes:
        **Which way is seaward is not something a game should have to say.** A quay knows
        where it is and the ground knows where the water is; between them that is enough.
        Asking a world to declare a bearing for every harbour it builds is asking it to write
        down something it can be wrong about, and to write it again every time somebody moves
        a pier.

        Nearest across all sixteen bearings rather than the first bearing that works, so a
        harbour with sea on two sides gets the shorter cut - which is the one a dredger would
        have made.

    """
    from .position import WorldPosition

    def at(radians, out):
        """
        Args:
            radians (float): The bearing, in radians.
            out (float): How far along it, in metres.

        Returns:
            position (WorldPosition): The point there.

        """
        return WorldPosition(
            position.x + math.sin(radians) * out,
            position.y + math.cos(radians) * out,
            getattr(position, "z", 0.0),
            position.region,
        )

    best, nearest = None, float("inf")
    for point in range(SEAWARD_BEARINGS):
        radians = math.radians(360.0 * point / SEAWARD_BEARINGS)
        out = step
        held = 0.0
        while out <= reach and out < nearest:
            if -world.terrain_z_at(at(radians, out)) >= wanted:
                held += step
                if held >= SEAWARD_HOLDS:
                    # Out to the far end of the deep run, not back to where it began. The
                    # channel has to cover the whole of it or a ship leaving would drop off
                    # the end of the cut and onto the bar it was dug to avoid.
                    best, nearest = at(radians, out), out
                    break
            else:
                held = 0.0
            out += step
    return best


def channels_to(ports, world, margin=CHANNEL_MARGIN, width=CHANNEL_WIDTH):
    """
    A cut into every quay, deep enough for anything that can lie at it.

    Args:
        ports (iterable): `PortRoom` objects with berths and positions.
        world (MaritimeMapProvider): The *undredged* ground.
        margin (float, optional): How much deeper than the deepest berth to cut.
        width (float, optional): The flat bottom width, in metres.

    Returns:
        channels (list): One `Channel` per quay that could be reached from the sea.

    Notes:
        **Asked of the undredged ground, which it has to be.** Looking for deep water on a
        world that already has these cuts in it finds the cut, and the channel is then dug
        from the harbour end of itself to the harbour.

        The depth comes from the berths rather than from a setting: a quay that advertises
        six metres is a quay a six-metre ship will try to use, so the approach has to keep
        the promise the berth already made. A quay whose berths have silted to nothing gets a
        channel to match, which is the right answer and reads as one.

        A harbour with no sea within reach gets no channel and no exception. A room somebody
        put in the middle of a continent is a room somebody put in the middle of a continent,
        and digging a ten-kilometre trench to it would be the engine deciding it knew better.

    """
    made = []
    for port in ports:
        here = getattr(port, "maritime_position", None)
        berths = tuple(getattr(port, "berths", ()) or ())
        if here is None or not berths:
            continue

        deepest = max(berths, key=lambda berth: berth.max_draft or 0.0)
        wanted = (deepest.max_draft or 0.0) + margin
        if wanted <= 0.0:
            continue

        sea = seaward_from(deepest.position, world, wanted)
        if sea is None:
            continue

        made.append(
            Channel(
                key=f"{port.key} Approach",
                start=sea,
                end=deepest.position,
                depth=wanted,
                width=width,
            )
        )
    return made


class Dredged(MaritimeMapProvider):
    """
    Another world's ground, with channels cut through it.

    Notes:
        A decorator rather than a base class, so a game keeps whatever provider it already
        had - generated, baked, hand-written - and says separately where it has dug. The two
        are different kinds of statement and a game will change them at different times.

        Everything except the depth is delegated untouched. See the module docstring: a
        channel is a statement about water, not about what is charted in it.

    """

    def __init__(self, ground, channels=(), tide_provider=None):
        """
        Args:
            ground (MaritimeMapProvider): The world underneath.
            channels (iterable, optional): `Channel` objects. Left empty, the cuts are
                worked out from the quays in the game the first time the ground is asked
                about - see `rebuild`.
            tide_provider (MaritimeTideProvider, optional): Passed to the base.

        """
        super().__init__(tide_provider=tide_provider)
        self.ground = ground
        self.channels = tuple(channels)
        self._surveyed = bool(channels)

    def rebuild(self):
        """
        Work out the cuts again, from the quays that exist now.

        Returns:
            channels (tuple): What was dug.

        Notes:
            Done lazily, the first time anybody asks about the ground, because a provider is
            built while Django is still starting and the quays are rows in a table that is
            not readable yet.

            **Lazily until it works, not lazily once.** The first version marked itself done
            before trying, so the survey that ran during startup failed on an unreadable
            table, cached no channels and never looked again - and every harbour in the game
            reported no way in, silently, with the reason swallowed by the same `except` that
            was there to make startup survivable. A retry costs one query on a world with no
            quays; not retrying costs the entire feature.

            The failure is logged rather than passed over. Something that can leave a coast
            with no approaches should not be able to do it without saying so.

            Call it again after building a harbour. A game that adds quays at runtime and
            never says so gets an approach to them on the next reload, which is honest but
            slow to notice; a build command should say so at once.

        """
        try:
            from .passage import ports_afloat

            self.channels = tuple(channels_to(ports_afloat(), self.ground))
        except Exception:  # noqa: BLE001 - no database yet, or none at all
            try:
                from evennia.utils import logger

                logger.log_trace("maritime: could not survey the quays for dredging")
            except Exception:  # noqa: BLE001 - no logger either, this early
                pass
            return self.channels
        self._surveyed = True
        return self.channels

    def terrain_z_at(self, position):
        """
        Args:
            position (WorldPosition): Where to sample.

        Returns:
            terrain_z (float): Elevation of the bottom, in metres against the datum.

        Notes:
            The deepest answer wins - the natural ground, or the deepest channel reaching
            this point. Deepest rather than last, so two channels crossing at a harbour
            entrance leave the depth of the deeper of them rather than of whichever happened
            to be declared second.

            **Only downwards.** `min` against the natural ground, so a cut over water that
            is already deeper than the dredged depth does nothing at all. A channel is
            maintained *to* a depth; it is not a promise that the sea is no deeper.

        """
        if not self._surveyed:
            self.rebuild()

        ground = self.ground.terrain_z_at(position)
        for channel in self.channels:
            cut = channel.cut_at(position)
            if cut is not None:
                ground = min(ground, -abs(cut))
        return ground

    def bottom_type_at(self, position):
        """
        Args:
            position (WorldPosition): Where to sample.

        Returns:
            bottom (str): What is down there.

        """
        return self.ground.bottom_type_at(position)

    def hazards_touching(self, before, after, width=0.0):
        """
        Args:
            before (WorldPosition): Start of the track.
            after (WorldPosition): End of it.
            width (float, optional): How wide a corridor to test.

        Returns:
            hazards (tuple): Whatever the world underneath answers.

        """
        return self.ground.hazards_touching(before, after, width=width)

    def landmarks_near(self, position, reach):
        """
        Args:
            position (WorldPosition): Where to look from.
            reach (float): How far, in metres.

        Returns:
            landmarks (tuple): Whatever the world underneath answers.

        """
        return self.ground.landmarks_near(position, reach)

    def charted_dangers(self, position, reach):
        """
        Args:
            position (WorldPosition): Where to look from.
            reach (float): How far, in metres.

        Returns:
            dangers (tuple): Whatever the world underneath answers.

        """
        return self.ground.charted_dangers(position, reach)

    def geographic_at(self, position):
        """
        Args:
            position (WorldPosition): Where to ask.

        Returns:
            geography (object): Whatever the world underneath answers.

        """
        return self.ground.geographic_at(position)

    def __repr__(self):
        return f"<Dredged {self.ground!r} +{len(self.channels)} channels>"


__all__ = (
    "BATTER",
    "CHANNEL_MARGIN",
    "CHANNEL_WIDTH",
    "SEAWARD_HOLDS",
    "SEAWARD_SEARCH",
    "SEAWARD_STEP",
    "SEAWARD_BEARINGS",
    "Channel",
    "Dredged",
    "seaward_from",
    "channels_to",
)
