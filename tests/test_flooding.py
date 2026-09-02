"""
Tests for making water.

The point of the whole item is that sinking is a process you fight rather than a threshold
you cross, so most of these are about the fight and only one is about the ending.

"""

import math

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest

from ..crew import ABLE
from ..damage import HULL
from ..flooding import (
    FOTHERING_RELIEF,
    FOTHERING_TIME,
    FOUNDERS_AT,
    Foundered,
    leak_rate,
    pump_rate,
    time_to_founder,
)
from ..events import bus
from ..motion import MotionLimits
from ..position import WorldPosition
from ..rooms import ShipRoom
from ..typeclasses import Vessel
from ..vessel import OPEN
from .base import EmptySeaMixin


class TestTheArithmetic(BaseEvenniaTest):
    """The pure functions, with no ship attached."""

    def test_a_tight_hull_makes_no_water(self):
        self.assertAlmostEqual(leak_rate(0.0, 0.0), 0.0)

    def test_a_worse_hull_leaks_worse(self):
        self.assertGreater(leak_rate(0.8, 0.0), leak_rate(0.4, 0.0))

    def test_and_disproportionately_so(self):
        """
        Squared, so a scraped hull weeps and an opened one floods. A linear leak would
        have every damaged ship slowly sinking, which makes the model a nuisance rather
        than a crisis.

        """
        self.assertGreater(leak_rate(0.8, 0.0), 2.0 * leak_rate(0.4, 0.0))

    def test_way_through_the_water_forces_more_in(self):
        self.assertGreater(leak_rate(0.7, 8.0), leak_rate(0.7, 0.0))

    def test_going_astern_forces_it_just_the_same(self):
        self.assertAlmostEqual(leak_rate(0.7, -8.0), leak_rate(0.7, 8.0))

    def test_a_fothered_sail_holds_most_of_it_back(self):
        loose = leak_rate(0.7, 0.0)
        fothered = leak_rate(0.7, 0.0, fothered=True)
        self.assertAlmostEqual(fothered, loose * (1.0 - FOTHERING_RELIEF))

    def test_nobody_on_the_pumps_shifts_nothing(self):
        self.assertAlmostEqual(pump_rate(0), 0.0)

    def test_more_hands_shift_more(self):
        self.assertGreater(pump_rate(25), pump_rate(10))

    def test_but_past_the_pumps_they_are_queueing(self):
        self.assertAlmostEqual(pump_rate(25), pump_rate(2500))

    def test_holding_it_means_she_has_for_ever(self):
        self.assertEqual(time_to_founder(0.5, 0.01, 0.02), math.inf)

    def test_gaining_means_she_has_a_number(self):
        self.assertLess(time_to_founder(0.5, 0.02, 0.01), math.inf)

    def test_and_the_fuller_she_is_the_less_of_it(self):
        self.assertLess(
            time_to_founder(0.9, 0.02, 0.0),
            time_to_founder(0.1, 0.02, 0.0),
        )


class TestTheDecision(BaseEvenniaTest):
    """Pumps beat a holed ship that has stopped, and lose to the same ship running."""

    def test_stopped_she_can_be_held(self):
        self.assertGreater(pump_rate(25), leak_rate(0.7, 0.0))

    def test_running_she_cannot(self):
        self.assertLess(pump_rate(25), leak_rate(0.7, 8.0))

    def test_which_is_the_whole_item(self):
        """
        One comparison, two answers, and the only difference is a decision the captain
        made. If both came out the same way there would be nothing here.

        """
        self.assertNotEqual(
            pump_rate(25) > leak_rate(0.7, 0.0),
            pump_rate(25) > leak_rate(0.7, 8.0),
        )


class FloodingTestCase(EmptySeaMixin, BaseEvenniaTest):
    """A hull that can be opened."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Kestrel")
        self.hull.length, self.hull.beam = 30.0, 8.5
        self.hull.motion_limits = MotionLimits(max_speed=6.0, acceleration=0.5, turn_rate=5.0)
        self.hull.maritime_position = WorldPosition(0.0, 0.0)
        self.hull.heading = 0.0
        deck = create.create_object(ShipRoom, key="Kestrel Deck")
        deck.vessel = self.hull
        deck.exposure = OPEN

    def hole_her(self, fraction=0.8):
        """Open her hull to the sea."""
        self.hull.take_damage(HULL, self.hull.damage.of(HULL) * 0.0)
        self.hull.damage = self.hull.damage.hurt(HULL, fraction)


class TestMakingWater(FloodingTestCase):
    """Filling, and being pumped."""

    def test_she_starts_tight_and_dry(self):
        self.assertAlmostEqual(self.hull.water, 0.0)
        self.assertFalse(self.hull.making_water)

    def test_a_sound_hull_does_not_fill(self):
        self.assertIsNone(self.hull.work_water(600.0))

    def test_an_opened_hull_fills(self):
        self.hole_her()
        self.hull.work_water(600.0)
        self.assertGreater(self.hull.water, 0.0)

    def test_the_pumps_take_it_out_again(self):
        self.hole_her()
        self.hull.work_water(600.0)
        rising = self.hull.water

        self.hull.man_pumps(25)
        self.hull.ndb.speed = 0.0
        self.hull.work_water(600.0)
        self.assertLess(self.hull.water, rising)

    def test_water_left_in_her_stays_there_when_the_leak_stops(self):
        """
        A ship with her hull mended is not dry. Somebody still has to pump her out, which
        is why this runs even when nothing is coming in.

        """
        self.hole_her()
        self.hull.work_water(600.0)
        had = self.hull.water

        self.hull.damage = self.hull.damage.mended(HULL, 1.0)
        self.hull.work_water(600.0)
        self.assertAlmostEqual(self.hull.water, had)

    def test_and_the_pumps_will_clear_it(self):
        self.hole_her()
        self.hull.work_water(600.0)
        self.hull.damage = self.hull.damage.mended(HULL, 1.0)
        self.hull.man_pumps(25)
        for _ in range(20):
            self.hull.work_water(600.0)
        self.assertAlmostEqual(self.hull.water, 0.0)

    def test_the_report_says_how_long_she_has(self):
        self.hole_her()
        self.hull.ndb.speed = 0.0
        report = self.hull.water_report()
        self.assertTrue(report.gaining)
        self.assertGreater(report.inflow, 0.0)


class TestSlowingHerSlowsTheLeak(FloodingTestCase):
    """The dilemma, on a real hull."""

    def test_running_lets_more_in(self):
        self.hole_her()
        self.hull.ndb.speed = 0.0
        quiet = self.hull.leak()
        self.hull.ndb.speed = 8.0
        running = self.hull.leak()
        self.assertGreater(running, quiet)

    def test_the_pumps_hold_her_stopped_and_lose_her_running(self):
        self.hole_her(0.7)
        self.hull.man_pumps(25)

        self.hull.ndb.speed = 0.0
        self.assertFalse(self.hull.water_report().gaining)

        self.hull.ndb.speed = 8.0
        self.assertTrue(self.hull.water_report().gaining)


class TestFothering(FloodingTestCase):
    """A sail under the hull, which is slow and does not mend her."""

    def test_it_takes_a_quarter_of_an_hour(self):
        self.hole_her()
        self.hull.fother(now=0.0)
        self.assertFalse(self.hull.fothered)

    def test_and_then_it_is_under_her(self):
        self.hole_her()
        self.hull.fother(now=0.0)
        self.hull.fother(now=FOTHERING_TIME + 1.0)
        self.assertTrue(self.hull.fothered)

    def test_and_the_leak_eases(self):
        self.hole_her()
        self.hull.ndb.speed = 0.0
        before = self.hull.leak()
        self.hull.fother(now=0.0)
        self.hull.fother(now=FOTHERING_TIME + 1.0)
        self.assertLess(self.hull.leak(), before)

    def test_but_it_does_not_mend_her(self):
        """She is still holed. It buys the chance to make port, and nothing else."""
        self.hole_her()
        self.hull.fother(now=0.0)
        self.hull.fother(now=FOTHERING_TIME + 1.0)
        self.assertGreater(self.hull.damage.of(HULL), 0.0)
        self.assertGreater(self.hull.leak(), 0.0)

    def test_it_cannot_be_done_twice(self):
        self.hole_her()
        self.hull.fother(now=0.0)
        self.hull.fother(now=FOTHERING_TIME + 1.0)
        self.assertFalse(self.hull.fother(now=FOTHERING_TIME + 2.0))


class TestFoundering(FloodingTestCase):
    """The ending, which is the one thing that is not a fight."""

    def setUp(self):
        super().setUp()
        self.heard = []
        bus().subscribe(Foundered, self.heard.append)

    def fill_her(self):
        """Leave her leaking, unpumped, until she goes."""
        self.hole_her(1.0)
        self.hull.ndb.speed = 0.0
        for _ in range(60):
            result = self.hull.work_water(120.0)
            if result and result.foundered:
                return result
        return None

    def test_an_unfought_leak_sinks_her(self):
        self.assertIsNotNone(self.fill_her())

    def test_she_stops_floating(self):
        self.fill_her()
        self.assertFalse(self.hull.afloat)

    def test_and_has_somewhere_to_go(self):
        """
        Not a boolean. A foundered ship is still a place, going down through a water
        column, and collapsing that into 'gone' would delete every wreck before anybody
        could dive on it.

        """
        self.fill_her()
        self.assertGreater(self.hull.buoyancy.sink_rate, 0.0)

    def test_it_is_announced(self):
        self.fill_her()
        self.assertEqual(len(self.heard), 1)

    def test_and_says_how_many_were_aboard(self):
        """What becomes of them is the game's. This is what it needs to decide."""
        self.hull.man(120, ABLE)
        self.fill_her()
        self.assertGreater(self.heard[0].aboard, 0)

    def test_the_water_does_not_go_past_full(self):
        self.fill_her()
        self.assertAlmostEqual(self.hull.water, FOUNDERS_AT)

    def test_pumping_her_hard_enough_saves_her(self):
        """The whole point. Same hull, same hole - somebody went to the pumps."""
        self.hole_her(0.7)
        self.hull.ndb.speed = 0.0
        self.hull.man_pumps(25)
        for _ in range(60):
            self.hull.work_water(120.0)
        self.assertTrue(self.hull.afloat)
