"""
Tests for one hull dragging another.

Two claims. **A tow is placed, not steered** - she has no helm of her own on the line, and
she rides astern rather than inside the tug. And **a tow is not free**: the cost is felt in
the speed the tick actually steers her by, which is what makes bringing a prize in a decision
rather than a formality.

"""

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest

from ..cargo import commodity_named
from ..motion import MotionLimits
from ..position import WorldPosition
from ..rooms import ShipRoom
from ..towing import (
    ALREADY_TOWED,
    ALREADY_TOWING,
    HERSELF,
    MOST_SHE_WILL_TAKE,
    NOT_A_HULL,
    NOT_TOWING,
    SCOPE,
    TOO_HEAVY,
    all_up_weight,
    burden_of,
    towing_speed,
)
from ..typeclasses import Vessel
from ..vessel import BELOW_WATERLINE, OPEN, VesselCapacity

HERE = WorldPosition(0.0, 0.0)


class TestWhatATowCosts(BaseEvenniaTest):
    """Not proportional, and deliberately."""

    def test_nothing_on_the_line_costs_nothing(self):
        self.assertAlmostEqual(towing_speed(6.0, burden=0.0), 6.0)

    def test_something_on_it_costs(self):
        self.assertLess(towing_speed(6.0, burden=1.0), 6.0)

    def test_a_heavier_tow_costs_more(self):
        self.assertLess(towing_speed(6.0, burden=2.0), towing_speed(6.0, burden=1.0))

    def test_but_twice_the_tow_is_not_half_the_speed(self):
        """
        A hull already moving takes little to keep moving. Halving her speed for every
        hull's weight added would make a tow impossible rather than expensive.

        """
        one = towing_speed(6.0, burden=1.0)
        two = towing_speed(6.0, burden=2.0)
        self.assertGreater(two, one / 2.0)

    def test_a_tug_towing_her_own_weight_is_plainly_working(self):
        self.assertLess(towing_speed(6.0, burden=1.0), 6.0 * 0.75)


class TowTestCase(BaseEvenniaTest):
    """Two hulls, one of which may end up on the end of a line."""

    def setUp(self):
        super().setUp()
        self.tug = self.a_hull("Kestrel", displacement=200_000.0)
        self.prize = self.a_hull("Marigold", displacement=150_000.0)

    def a_hull(self, key, displacement):
        hull = create.create_object(Vessel, key=key)
        hull.length, hull.beam = 24.0, 7.0
        hull.light_draft = 2.0
        hull.motion_limits = MotionLimits(max_speed=6.0, acceleration=0.5, turn_rate=5.0)
        hull.capacity = VesselCapacity(
            displacement=displacement, internal_volume=300.0, stability_moment=100_000.0
        )
        hull.maritime_position = HERE
        hull.heading = 0.0
        hold = create.create_object(ShipRoom, key=f"{key} Hold")
        hold.vessel = hull
        hold.deck_level = -1
        hold.exposure = BELOW_WATERLINE
        hold.hold_capacity = 200.0
        deck = create.create_object(ShipRoom, key=f"{key} Deck")
        deck.vessel = hull
        deck.exposure = OPEN
        return hull


class TestWhatSheWeighs(TowTestCase):
    """Her manifest counts, which is what makes a tow interesting."""

    def test_an_empty_hull_weighs_what_she_displaces(self):
        self.assertAlmostEqual(all_up_weight(self.prize), 150_000.0)

    def test_cargo_makes_her_heavier(self):
        salt = commodity_named("salt")
        if salt is None:
            self.skipTest("the shipped commodities do not include salt")
        light = all_up_weight(self.prize)
        self.prize.load(salt, 50.0)
        self.assertGreater(all_up_weight(self.prize), light)

    def test_and_a_worse_tow(self):
        """
        The way to make a prize towable is to start throwing cargo over the side, which is
        a decision and a bitter one.

        """
        salt = commodity_named("salt")
        if salt is None:
            self.skipTest("the shipped commodities do not include salt")
        light = burden_of(self.tug, self.prize)
        self.prize.load(salt, 50.0)
        self.assertGreater(burden_of(self.tug, self.prize), light)

    def test_a_tug_with_no_displacement_can_drag_nothing(self):
        weightless = self.a_hull("Ghost", displacement=0.0)
        self.assertEqual(burden_of(weightless, self.prize), float("inf"))


class TestGettingALineAboard(TowTestCase):
    """What she will take, and what she will not."""

    def test_a_new_hull_tows_nothing(self):
        self.assertIsNone(self.tug.tow)
        self.assertIsNone(self.tug.tug)

    def test_she_can_take_one_in_tow(self):
        self.assertTrue(self.tug.take_in_tow(self.prize))

    def test_and_both_ends_know_about_it(self):
        self.tug.take_in_tow(self.prize)
        self.assertIs(self.tug.tow, self.prize)
        self.assertIs(self.prize.tug, self.tug)
        self.assertTrue(self.prize.under_tow)

    def test_she_cannot_tow_herself(self):
        self.assertEqual(self.tug.take_in_tow(self.tug).code, HERSELF)

    def test_nor_something_that_is_not_a_hull(self):
        cask = create.create_object("evennia.objects.objects.DefaultObject", key="a cask")
        self.assertEqual(self.tug.take_in_tow(cask).code, NOT_A_HULL)

    def test_nor_two_at_once(self):
        another = self.a_hull("Swift", displacement=100_000.0)
        self.tug.take_in_tow(self.prize)
        self.assertEqual(self.tug.take_in_tow(another).code, ALREADY_TOWING)

    def test_nor_one_somebody_else_already_has(self):
        another = self.a_hull("Swift", displacement=100_000.0)
        self.tug.take_in_tow(self.prize)
        self.assertEqual(another.take_in_tow(self.prize).code, ALREADY_TOWED)

    def test_nor_one_she_cannot_hold(self):
        """
        Past the limit she has the power to move it and not the power to stop it or turn
        it, which is the thing that actually kills a tow.

        """
        heavy = self.a_hull("Leviathan", displacement=200_000.0 * MOST_SHE_WILL_TAKE * 2)
        result = self.tug.take_in_tow(heavy)
        self.assertEqual(result.code, TOO_HEAVY)
        self.assertGreater(result.burden, MOST_SHE_WILL_TAKE)

    def test_a_refused_tow_leaves_neither_end_marked(self):
        heavy = self.a_hull("Leviathan", displacement=200_000.0 * MOST_SHE_WILL_TAKE * 2)
        self.tug.take_in_tow(heavy)
        self.assertIsNone(self.tug.tow)
        self.assertIsNone(heavy.tug)


class TestSlippingIt(TowTestCase):
    """Slipped in a hurry, so nothing is conditional on anything."""

    def test_a_ship_towing_nothing_has_nothing_to_slip(self):
        self.assertEqual(self.tug.slip_the_tow().code, NOT_TOWING)

    def test_a_tow_can_be_let_go(self):
        self.tug.take_in_tow(self.prize)
        self.assertTrue(self.tug.slip_the_tow())

    def test_and_both_ends_are_clear_afterwards(self):
        self.tug.take_in_tow(self.prize)
        self.tug.slip_the_tow()
        self.assertIsNone(self.tug.tow)
        self.assertIsNone(self.prize.tug)

    def test_she_can_take_another_afterwards(self):
        self.tug.take_in_tow(self.prize)
        self.tug.slip_the_tow()
        self.assertTrue(self.tug.take_in_tow(self.prize))


class TestTheTowIsNotFree(TowTestCase):
    """The cost is felt in the speed the tick steers her by."""

    def test_a_clear_ship_makes_her_own_speed(self):
        self.assertAlmostEqual(self.tug.working_limits.max_speed, self.tug.motion_limits.max_speed)

    def test_one_with_a_tow_makes_less(self):
        clear = self.tug.working_limits.max_speed
        self.tug.take_in_tow(self.prize)
        self.assertLess(self.tug.working_limits.max_speed, clear)

    def test_and_slipping_it_gives_her_speed_back(self):
        clear = self.tug.working_limits.max_speed
        self.tug.take_in_tow(self.prize)
        self.tug.slip_the_tow()
        self.assertAlmostEqual(self.tug.working_limits.max_speed, clear)

    def test_a_heavier_prize_costs_more(self):
        light = self.a_hull("Wren", displacement=40_000.0)
        self.tug.take_in_tow(light)
        with_light = self.tug.working_limits.max_speed
        self.tug.slip_the_tow()
        self.tug.take_in_tow(self.prize)
        self.assertLess(self.tug.working_limits.max_speed, with_light)

    def test_she_is_not_charged_for_the_tow_twice(self):
        """
        `working_limits` drags the tow itself, so the result reported when the line goes
        aboard has to be that number rather than the same sum done again.

        """
        result = self.tug.take_in_tow(self.prize)
        self.assertAlmostEqual(result.speed, self.tug.working_limits.max_speed)


class TestDraggingHer(TowTestCase):
    """Placed, not steered - and astern, not inside the tug."""

    def test_a_ship_towing_nothing_drags_nothing(self):
        self.assertFalse(self.tug.drag_the_tow())

    def test_a_tow_is_moved_with_the_tug(self):
        self.tug.take_in_tow(self.prize)
        self.tug.maritime_position = WorldPosition(1000.0, 0.0)
        self.tug.heading = 90.0
        self.tug.drag_the_tow()
        self.assertNotEqual(self.prize.maritime_position, HERE)

    def test_and_rides_astern_of_her_rather_than_inside_her(self):
        """
        A tow set at the tug's own position would be through her. Astern on the reciprocal
        of her heading is where a tow actually rides.

        """
        self.tug.take_in_tow(self.prize)
        self.tug.heading = 90.0
        self.tug.drag_the_tow()
        gap = self.tug.maritime_position.horizontal_distance_to(self.prize.maritime_position)
        self.assertAlmostEqual(gap, self.tug.length * SCOPE, places=3)

    def test_she_lies_the_way_the_tug_is_pointing(self):
        self.tug.take_in_tow(self.prize)
        self.tug.heading = 123.0
        self.tug.drag_the_tow()
        self.assertAlmostEqual(self.prize.heading, 123.0, places=3)

    def test_and_makes_the_tug_speed(self):
        self.tug.take_in_tow(self.prize)
        self.tug.speed = 3.0
        self.tug.drag_the_tow()
        self.assertAlmostEqual(self.prize.speed, 3.0, places=3)

    def test_the_tow_is_astern_whichever_way_the_tug_heads(self):
        self.tug.take_in_tow(self.prize)
        for heading in (0.0, 90.0, 180.0, 270.0):
            self.tug.heading = heading
            self.tug.drag_the_tow()
            astern = self.tug.maritime_position.bearing_to(self.prize.maritime_position)
            self.assertAlmostEqual(astern, (heading + 180.0) % 360.0, places=2)

    def test_a_tug_nowhere_drags_nothing(self):
        self.tug.take_in_tow(self.prize)
        self.tug.maritime_position = None
        self.assertFalse(self.tug.drag_the_tow())
