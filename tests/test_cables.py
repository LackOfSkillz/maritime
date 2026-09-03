"""
Tests for springing on a cable, and for cutting it.

"""

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest

from ..cables import (
    ANCHOR_ABOARD,
    NOT_ANCHORED,
    NOT_SPRUNG,
    RIGGING_A_SPARE,
    hauled_round,
    spring_rate,
)
from ..motion import MotionLimits
from ..position import WorldPosition
from ..rooms import ShipRoom
from ..typeclasses import Vessel
from ..vessel import OPEN
from ..ballistics import ANCHORED_STEADINESS, MAX_SEA_PENALTY, sea_accuracy
from ..weather import CALM, ROUGH
from .base import EmptySeaMixin


class TestHowFastSheComesRound(BaseEvenniaTest):
    """The arithmetic, with no ship attached."""

    def test_a_longer_hull_comes_round_more_slowly(self):
        self.assertLess(spring_rate(60.0), spring_rate(30.0))

    def test_a_boat_comes_round_faster_than_a_ship(self):
        self.assertGreater(spring_rate(8.0), spring_rate(40.0))

    def test_a_length_of_zero_does_not_divide_by_it(self):
        self.assertGreater(spring_rate(0.0), 0.0)

    def test_she_takes_the_short_way_round(self):
        """
        A spring hauls a point on the cable towards you. There is no long way about, and
        a ship warped in a circle round her own anchor is nobody's idea of a tactic.

        """
        self.assertAlmostEqual(hauled_round(350.0, 10.0, 600.0, 30.0), 10.0, places=3)

    def test_and_the_short_way_is_the_other_way_too(self):
        self.assertAlmostEqual(hauled_round(10.0, 350.0, 600.0, 30.0), 350.0, places=3)

    def test_she_does_not_overshoot(self):
        far_too_long = 100000.0
        self.assertAlmostEqual(hauled_round(0.0, 90.0, far_too_long, 30.0), 90.0, places=3)

    def test_a_short_spell_only_gets_her_part_way(self):
        after = hauled_round(0.0, 90.0, 60.0, 30.0)
        self.assertGreater(after, 0.0)
        self.assertLess(after, 90.0)

    def test_it_is_slow_enough_to_be_a_decision(self):
        """
        Ninety degrees in a quarter of an hour for a middling ship. If it were quick it
        would be a button rather than something you do before anybody arrives.

        """
        after_five_minutes = hauled_round(0.0, 90.0, 300.0, 30.0)
        self.assertLess(after_five_minutes, 45.0)

    def test_no_time_moves_her_not_at_all(self):
        self.assertAlmostEqual(hauled_round(42.0, 90.0, 0.0, 30.0), 42.0, places=3)


class CableTestCase(EmptySeaMixin, BaseEvenniaTest):
    """A hull with an anchor."""

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


class TestRiggingASpring(CableTestCase):
    """Ordering it, and taking it off."""

    def test_a_ship_under_way_has_nothing_to_spring_on(self):
        result = self.hull.spring(90.0)
        self.assertFalse(result)
        self.assertEqual(result.code, NOT_ANCHORED)

    def test_at_anchor_she_can_be_sprung(self):
        self.hull.anchored = True
        self.assertTrue(self.hull.spring(90.0))
        self.assertAlmostEqual(self.hull.sprung_to, 90.0)

    def test_she_starts_with_no_spring_rigged(self):
        self.assertIsNone(self.hull.sprung_to)

    def test_it_says_how_long_it_will_take(self):
        self.hull.anchored = True
        result = self.hull.spring(90.0)
        self.assertAlmostEqual(result.remaining, 90.0)
        self.assertGreater(result.seconds_more, 600.0)

    def test_a_bearing_is_normalised(self):
        self.hull.anchored = True
        self.hull.spring(450.0)
        self.assertAlmostEqual(self.hull.sprung_to, 90.0)

    def test_the_spring_can_be_cast_off(self):
        self.hull.anchored = True
        self.hull.spring(90.0)
        self.assertTrue(self.hull.unrig_spring())
        self.assertIsNone(self.hull.sprung_to)

    def test_casting_off_one_she_has_not_got(self):
        self.assertFalse(self.hull.unrig_spring())


class TestWorkingTheSpring(CableTestCase):
    """Hauling, over time."""

    def setUp(self):
        super().setUp()
        self.hull.anchored = True

    def test_without_a_spring_there_is_nothing_to_work(self):
        result = self.hull.work_spring(600.0)
        self.assertFalse(result)
        self.assertEqual(result.code, NOT_SPRUNG)

    def test_hauling_brings_her_head_round(self):
        self.hull.spring(90.0)
        self.hull.work_spring(300.0)
        self.assertGreater(self.hull.heading, 0.0)

    def test_and_does_not_move_her(self):
        """
        The one place a ship changes heading without changing position. If a spring moved
        her she would be dragging her own anchor, which is the failure it exists to avoid.

        """
        where = self.hull.maritime_position
        self.hull.spring(90.0)
        self.hull.work_spring(600.0)
        self.assertAlmostEqual(self.hull.maritime_position.x, where.x, places=6)
        self.assertAlmostEqual(self.hull.maritime_position.y, where.y, places=6)

    def test_and_gives_her_no_way(self):
        self.hull.spring(90.0)
        self.hull.work_spring(600.0)
        self.assertAlmostEqual(self.hull.speed, 0.0)

    def test_enough_hauling_gets_her_all_the_way_round(self):
        self.hull.spring(90.0)
        for _ in range(20):
            self.hull.work_spring(300.0)
        self.assertAlmostEqual(self.hull.heading, 90.0, places=3)

    def test_and_then_the_spring_comes_off_by_itself(self):
        """Otherwise the hands go on walking the capstan for ever, half a degree at a time."""
        self.hull.spring(90.0)
        for _ in range(20):
            self.hull.work_spring(300.0)
        self.assertIsNone(self.hull.sprung_to)

    def test_weighing_while_sprung_leaves_nothing_to_haul_on(self):
        self.hull.spring(90.0)
        self.hull.anchored = False
        result = self.hull.work_spring(300.0)
        self.assertFalse(result)
        self.assertEqual(result.code, NOT_ANCHORED)


class TestCuttingTheCable(CableTestCase):
    """The decision with a consequence that outlives the fight."""

    def test_a_ship_not_anchored_has_nothing_to_cut(self):
        result = self.hull.cut_cable()
        self.assertFalse(result)
        self.assertEqual(result.code, NOT_ANCHORED)

    def test_cutting_frees_her_at_once(self):
        self.hull.anchored = True
        self.assertTrue(self.hull.cut_cable())
        self.assertFalse(self.hull.anchored)

    def test_and_the_anchor_is_gone(self):
        self.hull.anchored = True
        self.hull.cut_cable()
        self.assertFalse(self.hull.has_anchor)

    def test_and_the_spring_goes_with_it(self):
        """There is nothing left to spring on."""
        self.hull.anchored = True
        self.hull.spring(90.0)
        self.hull.cut_cable()
        self.assertIsNone(self.hull.sprung_to)

    def test_she_starts_with_an_anchor(self):
        self.assertTrue(self.hull.has_anchor)

    def test_a_spare_can_be_rigged(self):
        self.hull.anchored = True
        self.hull.cut_cable()
        result = self.hull.rig_a_spare()
        self.assertTrue(result)
        self.assertAlmostEqual(result.seconds_more, RIGGING_A_SPARE)

    def test_but_not_while_she_already_has_one(self):
        result = self.hull.rig_a_spare()
        self.assertFalse(result)
        self.assertEqual(result.code, ANCHOR_ABOARD)

    def test_rigging_one_is_most_of_a_day(self):
        """The consequence is the point. A ship that cut at noon is not anchoring by dark."""
        self.assertGreater(RIGGING_A_SPARE, 4.0 * 3600.0)

    def test_she_has_no_anchor_until_the_work_is_done(self):
        """
        The clock has to be the same one on both sides. Starting the work at an injected
        time and asking the live clock whether it is finished is how a six-hour job
        reports itself done the moment it is begun.

        """
        self.hull.anchored = True
        self.hull.cut_cable()
        self.hull.rig_a_spare()
        self.assertFalse(self.hull.has_anchor)

    def test_and_has_one_again_once_it_is(self):
        self.hull.anchored = True
        self.hull.cut_cable()
        self.hull.rig_a_spare()
        self.hull.db.anchor_ready_at = 1.0
        self.assertTrue(self.hull.has_anchor)


class TestAnAnchoredShipShootsBetter(BaseEvenniaTest):
    """The return on having laid her where her broadside bears."""

    def test_a_steady_platform_loses_less_to_the_sea(self):
        self.assertGreater(sea_accuracy(ROUGH, steady=True), sea_accuracy(ROUGH))

    def test_but_not_all_of_it_back(self):
        """She still rises to a swell. A cable is not dry land."""
        self.assertLess(sea_accuracy(ROUGH, steady=True), 1.0)

    def test_a_cable_cannot_make_a_calm_calmer(self):
        """
        Nothing to recover, so nothing is paid out. A model that rewarded anchoring in a
        flat calm would be rewarding it for nothing.

        """
        self.assertAlmostEqual(sea_accuracy(CALM, steady=True), sea_accuracy(CALM))

    def test_it_takes_out_the_stated_fraction_of_the_penalty(self):
        loss = 1.0 - sea_accuracy(ROUGH)
        steady_loss = 1.0 - sea_accuracy(ROUGH, steady=True)
        self.assertAlmostEqual(steady_loss, loss * (1.0 - ANCHORED_STEADINESS))

    def test_the_worst_sea_is_still_the_worst_sea(self):
        self.assertGreater(1.0 - sea_accuracy("phenomenal"), MAX_SEA_PENALTY / 2.0)
