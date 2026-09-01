"""
How a scenario is sailed: the harness the voyages share.

Split out of `test_scenarios` when that file passed the thousand-line ceiling. The seam is
a real one rather than a convenient place to cut: this is *how to sail a scenario* - a
sloop, a stretch of time, and a few authored seabeds - and the other file is *the voyages
themselves*. They change for different reasons, which is the test that a seam is real.

The original header follows, because it is the argument for the suite existing at all.

---

The scenario suite: named voyages, run end to end.

Every other test file here checks a piece. These check a *passage* - set sail, stand on,
and see where she ends up - because a system can pass every unit test it has and still be
unable to get a ship from one place to another. The names are the design's own, from
section 20 of the architecture, so that "which of these actually run?" has an answer that
is not somebody's memory.

Each scenario is a voyage rather than an assertion about a function. They tick real time
through real typeclasses and read the result off the ship, which makes them slower than the
rest of the suite and worth every second: three separate bugs this contrib has shipped
would have been caught here rather than by somebody sailing about in the testbed.

Not built, and why:

    flooding, fire, collision            damage, phase 17
    strategic-advance, materialize       phase 11
    passenger-*, service-partial         phases 21 and 23

Those are Gary's, and a scenario that pretended to exercise them would be worse than a gap.

"""

from django.test import override_settings
from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest

from ..bathymetry import ROCK, SAND, MaritimeMapProvider
from ..motion import MotionLimits
from ..position import WorldPosition
from ..rooms import ShipRoom
from ..sailing import FURLED, PolarCurve
from ..traffic import traffic
from ..typeclasses import Vessel
from ..vessel import OPEN, VesselCapacity
from .base import EmptySeaMixin

#: A steady working breeze from the south, so an easterly course is a beam reach.
BREEZE = {"MARITIME_WIND_BEARING": 180.0, "MARITIME_WIND_SPEED": 8.0}

#: A gale from the same quarter. Same direction on purpose - the only thing that
#: changes between `sailing-basic` and `storm-delay` is how hard it is blowing.
GALE = {"MARITIME_WIND_BEARING": 180.0, "MARITIME_WIND_SPEED": 22.0}


class Shoal(MaritimeMapProvider):
    """Deep water with a sandbank in it, east of x=2000."""

    def terrain_z_at(self, position):
        return -1.0 if position.x >= 2000.0 else -30.0

    def bottom_type_at(self, position):
        return SAND


class Reef(Shoal):
    """The same bank, made of rock."""

    def bottom_type_at(self, position):
        return ROCK


class Ledge(MaritimeMapProvider):
    """
    A rock ledge with open water round its southern end.

    Notes:
        The channel is the point. Standing straight east runs onto it; going south
        round the end does not, and that is what makes a chart worth having.

    """

    def terrain_z_at(self, position):
        on_it = 2000.0 <= position.x <= 2600.0 and abs(position.y) <= 800.0
        return -1.2 if on_it else -30.0

    def bottom_type_at(self, position):
        return ROCK


class ScenarioTestCase(EmptySeaMixin, BaseEvenniaTest):
    """
    A sloop, and a way to sail her.

    Notes:
        Weather is a class attribute rather than an `override_settings`
        decorator, and that is not a style choice. `EmptySeaMixin` enables its
        own flat, still, windless sea inside `setUp`, which runs *after* a class
        decorator has been applied - so a scenario asking for a working breeze by
        decorator got a dead calm and every ship in it sat still. Enabling it
        here, after the empty sea, is the only ordering that works.

    """

    #: What the sky is doing. Applied after the empty sea so it wins.
    weather = {}

    def setUp(self):
        super().setUp()
        if self.weather:
            sky = override_settings(**self.weather)
            sky.enable()
            self.addCleanup(sky.disable)

    def a_sloop(self, key="Kittiwake", position=None, sails=True):
        """
        Returns:
            vessel (Vessel): A working sloop with a deck and a masthead.

        """
        hull = create.create_object(Vessel, key=key)
        hull.length, hull.beam = 18.0, 5.4
        hull.light_draft = 2.2
        hull.air_draft = 20.0
        hull.capacity = VesselCapacity(displacement=40000.0, internal_volume=90.0)
        hull.motion_limits = MotionLimits(max_speed=6.0, acceleration=0.5, turn_rate=6.0)
        hull.maritime_position = position or WorldPosition(0.0, 0.0)
        if sails:
            hull.polar_curve = PolarCurve()
            hull.sail_plan = FURLED

        deck = create.create_object(ShipRoom, key=f"{key} Deck")
        deck.vessel = hull
        deck.exposure = OPEN
        deck.height_of_eye = 2.0

        top = create.create_object(ShipRoom, key=f"{key} Masthead")
        top.vessel = hull
        top.exposure = OPEN
        top.deck_level = 3
        top.height_of_eye = 18.0

        traffic().note(hull, hull.maritime_position)
        return hull

    def sail(self, vessel, seconds, step=15.0):
        """
        Advance a vessel through a stretch of time, a tick at a time.

        Args:
            vessel (Vessel): The hull.
            seconds (float): How long to sail.
            step (float, optional): Tick length.

        Returns:
            ticks (int): How many ticks ran before she stopped or the time ran out.

        Notes:
            Stops early if she goes aground, because a scenario that kept ticking a
            stranded ship would be measuring nothing.

        """
        ticks = 0
        for _ in range(int(seconds / step)):
            vessel.at_maritime_tick(step)
            ticks += 1
            if vessel.aground:
                break
        return ticks
