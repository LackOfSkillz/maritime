"""
Tests for the sailing model.

"""

from django.test import override_settings

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest, BaseEvenniaTestCase

from .base import EmptySeaMixin

from ..motion import HelmOrders, MotionLimits
from ..position import EAST, NORTH, SOUTH, WEST, WorldPosition
from ..typeclasses import Vessel
from ..sailing import (
    FULL,
    FURLED,
    REEFED,
    SAIL_PLANS,
    STORM,
    WORKING,
    PolarCurve,
    SailPlan,
    WindVector,
    achievable_speed,
    is_in_irons,
    leeway_angle,
    relative_wind_angle,
    sail_plan,
    steerage_floor,
)

HULL = MotionLimits(max_speed=10.0, acceleration=1.0, turn_rate=6.0)
CURVE = PolarCurve()
# A northerly: blowing from the north, towards the south.
NORTHERLY = WindVector(bearing=NORTH, speed=10.0)


class TestWindVector(BaseEvenniaTestCase):
    """Wind is named for where it comes from."""

    def test_a_northerly_comes_from_the_north(self):
        self.assertEqual(NORTHERLY.bearing, NORTH)

    def test_a_northerly_blows_towards_the_south(self):
        """
        Treating the named bearing as a direction of travel reverses every
        calculation downstream while still producing plausible numbers.

        """
        self.assertEqual(NORTHERLY.blowing_towards, SOUTH)

    def test_bearing_is_normalised(self):
        self.assertEqual(WindVector(bearing=400.0).bearing, 40.0)

    def test_negative_speed_is_refused(self):
        with self.assertRaises(ValueError):
            WindVector(speed=-1.0)

    def test_calm_is_allowed(self):
        self.assertEqual(WindVector(speed=0.0).speed, 0.0)


class TestRelativeWindAngle(BaseEvenniaTestCase):
    """Where the wind lies relative to the vessel."""

    def test_pointing_into_the_wind_is_zero(self):
        self.assertAlmostEqual(relative_wind_angle(NORTH, NORTHERLY), 0.0)

    def test_running_before_it_is_one_eighty(self):
        self.assertAlmostEqual(relative_wind_angle(SOUTH, NORTHERLY), 180.0)

    def test_beam_reach_is_ninety(self):
        self.assertAlmostEqual(relative_wind_angle(EAST, NORTHERLY), 90.0)

    def test_is_unsigned(self):
        """
        A rig does not care which side the wind is on. Port tack at 45 degrees
        sails exactly as starboard.

        """
        self.assertAlmostEqual(
            relative_wind_angle(EAST, NORTHERLY), relative_wind_angle(WEST, NORTHERLY)
        )

    def test_never_exceeds_one_eighty(self):
        for heading in range(0, 360, 13):
            self.assertLessEqual(relative_wind_angle(float(heading), NORTHERLY), 180.0)


class TestInIrons(BaseEvenniaTestCase):
    """Too close to the wind to sail."""

    def test_head_to_wind_is_in_irons(self):
        self.assertTrue(is_in_irons(NORTH, NORTHERLY))

    def test_a_beam_reach_is_not(self):
        self.assertFalse(is_in_irons(EAST, NORTHERLY))

    def test_running_is_not(self):
        self.assertFalse(is_in_irons(SOUTH, NORTHERLY))


class TestPolarCurve(BaseEvenniaTestCase):
    """The rig's performance by angle."""

    def test_no_drive_head_to_wind(self):
        self.assertEqual(CURVE.efficiency_at(0.0), 0.0)

    def test_best_on_a_beam_reach(self):
        self.assertEqual(CURVE.efficiency_at(90.0), 1.0)

    def test_running_is_slower_than_reaching(self):
        """A square sail runs well, but a beam reach still beats it."""
        self.assertLess(CURVE.efficiency_at(180.0), CURVE.efficiency_at(90.0))

    def test_close_hauled_is_slower_than_reaching(self):
        self.assertLess(CURVE.efficiency_at(45.0), CURVE.efficiency_at(90.0))

    def test_interpolates_between_points(self):
        between = CURVE.efficiency_at(37.5)
        self.assertGreater(between, CURVE.efficiency_at(30.0))
        self.assertLess(between, CURVE.efficiency_at(45.0))

    def test_clamps_beyond_the_ends(self):
        self.assertEqual(CURVE.efficiency_at(200.0), CURVE.efficiency_at(180.0))

    def test_handles_negative_angles(self):
        self.assertEqual(CURVE.efficiency_at(-45.0), CURVE.efficiency_at(45.0))

    def test_a_game_may_supply_its_own(self):
        """A square-rigger runs beautifully and points terribly."""
        square = PolarCurve(points=((0.0, 0.0), (90.0, 0.5), (180.0, 1.0)))
        self.assertGreater(square.efficiency_at(180.0), square.efficiency_at(90.0))

    def test_rejects_unordered_points(self):
        with self.assertRaises(ValueError):
            PolarCurve(points=((90.0, 1.0), (0.0, 0.0)))

    def test_rejects_a_single_point(self):
        with self.assertRaises(ValueError):
            PolarCurve(points=((90.0, 1.0),))

    def test_rejects_impossible_efficiency(self):
        with self.assertRaises(ValueError):
            PolarCurve(points=((0.0, 0.0), (90.0, 1.5)))


class TestSailPlans(BaseEvenniaTestCase):
    """How much canvas is set."""

    def test_bare_poles_carry_no_sail(self):
        self.assertEqual(FURLED.area, 0.0)

    def test_full_sail_is_everything(self):
        self.assertEqual(FULL.area, 1.0)

    def test_plans_increase_in_area(self):
        areas = [plan.area for plan in SAIL_PLANS]
        self.assertEqual(areas, sorted(areas))

    def test_more_canvas_is_safe_in_less_wind(self):
        """The progression exists so a rising wind forces a decision."""
        self.assertLess(FULL.safe_wind, REEFED.safe_wind)
        self.assertLess(REEFED.safe_wind, STORM.safe_wind)

    def test_lookup_by_key(self):
        self.assertIs(sail_plan("reefed"), REEFED)

    def test_unknown_key_returns_none(self):
        self.assertIsNone(sail_plan("spinnaker"))

    def test_rejects_impossible_area(self):
        with self.assertRaises(ValueError):
            SailPlan("odd", "odd", 1.5, 10.0)


class TestAchievableSpeed(BaseEvenniaTestCase):
    """What she can actually make."""

    def speed_on(self, heading, plan=WORKING, wind=NORTHERLY):
        return achievable_speed(heading, wind, plan, CURVE, HULL)

    def test_makes_way_on_a_reach(self):
        self.assertGreater(self.speed_on(EAST), 0.0)

    def test_head_to_wind_makes_nothing(self):
        self.assertEqual(self.speed_on(NORTH), 0.0)

    def test_upwind_is_slower_than_downwind(self):
        """The acceptance criterion for this phase."""
        close_hauled = self.speed_on(45.0)
        running = self.speed_on(SOUTH)
        self.assertLess(close_hauled, running)

    def test_reaching_beats_both(self):
        self.assertGreater(self.speed_on(EAST), self.speed_on(SOUTH))
        self.assertGreater(self.speed_on(EAST), self.speed_on(45.0))

    def test_bare_poles_make_no_way(self):
        self.assertEqual(self.speed_on(EAST, plan=FURLED), 0.0)

    def test_more_sail_is_more_speed(self):
        self.assertGreater(self.speed_on(EAST, plan=FULL), self.speed_on(EAST, plan=REEFED))

    def test_calm_makes_no_way(self):
        self.assertEqual(self.speed_on(EAST, wind=WindVector(NORTH, 0.0)), 0.0)

    def test_light_airs_are_slow(self):
        light = self.speed_on(EAST, wind=WindVector(NORTH, 2.0))
        fresh = self.speed_on(EAST, wind=WindVector(NORTH, 10.0))
        self.assertLess(light, fresh)

    def test_more_wind_stops_helping_at_the_hull_limit(self):
        """Past a point the hull, not the rig, is the limit."""
        fresh = self.speed_on(EAST, wind=WindVector(NORTH, 10.0))
        gale = self.speed_on(EAST, wind=WindVector(NORTH, 40.0))
        self.assertAlmostEqual(fresh, gale)

    def test_never_exceeds_the_hull_ceiling(self):
        for heading in range(0, 360, 7):
            self.assertLessEqual(self.speed_on(float(heading), plan=FULL), HULL.max_speed + 1e-9)


class TestLeeway(BaseEvenniaTestCase):
    """She does not go quite where she points."""

    def test_none_under_bare_poles(self):
        self.assertEqual(leeway_angle(EAST, NORTHERLY, FURLED, 5.0), 0.0)

    def test_none_in_a_calm(self):
        self.assertEqual(leeway_angle(EAST, WindVector(NORTH, 0.0), WORKING, 5.0), 0.0)

    def test_none_when_stopped(self):
        self.assertEqual(leeway_angle(EAST, NORTHERLY, WORKING, 0.0), 0.0)

    def test_worst_close_hauled(self):
        """
        Worst precisely when a navigator can least afford it, which is why dead
        reckoning goes wrong to windward.

        """
        close = abs(leeway_angle(45.0, NORTHERLY, WORKING, 3.0))
        reaching = abs(leeway_angle(EAST, NORTHERLY, WORKING, 3.0))
        self.assertGreater(close, reaching)

    def test_none_when_running(self):
        self.assertEqual(leeway_angle(SOUTH, NORTHERLY, WORKING, 3.0), 0.0)

    def test_falls_off_as_she_gains_speed(self):
        """A hull moving well grips the water; one barely moving slides."""
        slow = abs(leeway_angle(45.0, NORTHERLY, WORKING, 0.5))
        fast = abs(leeway_angle(45.0, NORTHERLY, WORKING, 8.0))
        self.assertGreater(slow, fast)

    def test_wind_on_the_port_bow_sets_her_to_starboard(self):
        """She is pushed away from the wind, not into it."""
        self.assertGreater(leeway_angle(45.0, NORTHERLY, WORKING, 3.0), 0.0)

    def test_wind_on_the_starboard_bow_sets_her_to_port(self):
        self.assertLess(leeway_angle(315.0, NORTHERLY, WORKING, 3.0), 0.0)


class TestVesselUnderSail(EmptySeaMixin, BaseEvenniaTest):
    """A hull actually driven by wind."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Test Sloop")
        self.hull.maritime_position = WorldPosition(0.0, 0.0)
        self.hull.motion_limits = MotionLimits(max_speed=10.0, acceleration=2.0, turn_rate=8.0)
        self.hull.orders = HelmOrders(heading=EAST, speed=0.0)
        self.hull.heading = EAST

    def wind(self, bearing=NORTH, speed=10.0):
        """Set the world wind for this test."""
        return override_settings(MARITIME_WIND_BEARING=bearing, MARITIME_WIND_SPEED=speed)

    def test_bare_poles_make_no_way(self):
        with self.wind():
            for _ in range(20):
                self.hull.at_maritime_tick(5.0)
        self.assertEqual(self.hull.speed, 0.0)

    def test_setting_sail_gets_her_moving(self):
        self.hull.sail_plan = WORKING
        with self.wind():
            for _ in range(20):
                self.hull.at_maritime_tick(5.0)
        self.assertGreater(self.hull.speed, 0.0)

    def test_she_will_not_sail_head_to_wind(self):
        """No order can make a vessel sail into the wind."""
        self.hull.heading = NORTH
        self.hull.orders = HelmOrders(heading=NORTH, speed=10.0)
        self.hull.sail_plan = FULL
        with self.wind():
            for _ in range(20):
                self.hull.at_maritime_tick(5.0)
        self.assertEqual(self.hull.speed, 0.0)

    def test_ordered_speed_does_not_override_the_wind(self):
        """
        The point of the phase: speed stops being something you order.

        """
        self.hull.orders = HelmOrders(heading=EAST, speed=10.0)
        self.hull.sail_plan = REEFED
        with self.wind(speed=4.0):
            for _ in range(30):
                self.hull.at_maritime_tick(5.0)
        self.assertLess(self.hull.speed, 10.0)

    def test_a_calm_leaves_her_dead_in_the_water(self):
        self.hull.sail_plan = FULL
        with self.wind(speed=0.0):
            for _ in range(20):
                self.hull.at_maritime_tick(5.0)
        self.assertEqual(self.hull.speed, 0.0)

    def test_leeway_sets_her_off_her_heading(self):
        """
        She points one way and travels another, which is why dead reckoning
        goes wrong to windward.

        """
        self.hull.heading = 45.0
        self.hull.orders = HelmOrders(heading=45.0, speed=0.0)
        self.hull.sail_plan = WORKING
        with self.wind():
            for _ in range(5):
                self.hull.at_maritime_tick(2.0)
        made_good = WorldPosition(0.0, 0.0).bearing_to(self.hull.maritime_position)
        self.assertNotAlmostEqual(made_good, 45.0, places=2)

    def test_her_head_is_still_where_it_was(self):
        """Leeway moves the track, not the heading. Her head really is there."""
        self.hull.heading = 45.0
        self.hull.orders = HelmOrders(heading=45.0, speed=0.0)
        self.hull.sail_plan = WORKING
        with self.wind():
            for _ in range(5):
                self.hull.at_maritime_tick(2.0)
        self.assertAlmostEqual(self.hull.heading, 45.0, places=3)


class TestSteerageFloor(BaseEvenniaTestCase):
    """A crew can back a sail to shove her bow round."""

    def test_nothing_under_bare_poles(self):
        """A vessel caught in irons with sails furled really is helpless."""
        self.assertEqual(steerage_floor(NORTHERLY, FURLED), 0.0)

    def test_nothing_in_a_calm(self):
        self.assertEqual(steerage_floor(WindVector(NORTH, 0.0), WORKING), 0.0)

    def test_available_with_canvas_and_wind(self):
        self.assertGreater(steerage_floor(NORTHERLY, WORKING), 0.0)

    def test_more_canvas_is_more_authority(self):
        self.assertGreater(steerage_floor(NORTHERLY, FULL), steerage_floor(NORTHERLY, STORM))


class TestInIronsRecovery(EmptySeaMixin, BaseEvenniaTest):
    """Being trapped must be hard, not permanent."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Test Sloop")
        self.hull.maritime_position = WorldPosition(0.0, 0.0)
        self.hull.motion_limits = MotionLimits(max_speed=5.0, acceleration=0.12, turn_rate=3.0)

    @override_settings(MARITIME_WIND_BEARING=0.0, MARITIME_WIND_SPEED=9.0)
    def test_she_can_claw_out_of_irons(self):
        """
        A vessel that turns too close to the wind loses drive, and losing drive
        costs her steerage. Without a floor she is trapped for good, which is a
        broken ship rather than a hard one.

        """
        self.hull.heading = 3.0
        self.hull.speed = 0.05
        self.hull.sail_plan = WORKING
        self.hull.orders = HelmOrders(heading=EAST, speed=0.0)
        for _ in range(60):
            self.hull.at_maritime_tick(2.0)
        self.assertGreater(self.hull.heading, 45.0)

    @override_settings(MARITIME_WIND_BEARING=0.0, MARITIME_WIND_SPEED=9.0)
    def test_furled_sails_leave_her_helpless(self):
        """The floor comes from canvas. With none, there is nothing to back."""
        self.hull.heading = 3.0
        self.hull.speed = 0.0
        self.hull.sail_plan = FURLED
        self.hull.orders = HelmOrders(heading=EAST, speed=0.0)
        for _ in range(30):
            self.hull.at_maritime_tick(2.0)
        self.assertAlmostEqual(self.hull.heading, 3.0, places=3)


class TestAnchoring(EmptySeaMixin, BaseEvenniaTest):
    """Bringing up and getting under way."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Test Sloop")
        self.hull.maritime_position = WorldPosition(0.0, 0.0)
        self.hull.motion_limits = MotionLimits(max_speed=5.0, acceleration=0.5, turn_rate=3.0)
        self.hull.heading = EAST
        self.hull.sail_plan = WORKING

    def test_starts_unanchored(self):
        self.assertFalse(self.hull.anchored)

    @override_settings(MARITIME_WIND_BEARING=0.0, MARITIME_WIND_SPEED=9.0)
    def test_an_anchored_vessel_does_not_sail(self):
        self.hull.anchored = True
        for _ in range(20):
            self.hull.at_maritime_tick(5.0)
        self.assertEqual(self.hull.maritime_position, WorldPosition(0.0, 0.0))

    @override_settings(MARITIME_WIND_BEARING=0.0, MARITIME_WIND_SPEED=9.0)
    def test_anchoring_takes_the_way_off_her(self):
        self.hull.speed = 3.0
        self.hull.anchored = True
        self.hull.at_maritime_tick(5.0)
        self.assertEqual(self.hull.speed, 0.0)

    @override_settings(MARITIME_WIND_BEARING=0.0, MARITIME_WIND_SPEED=9.0)
    def test_weighing_lets_her_sail_again(self):
        self.hull.anchored = True
        self.hull.at_maritime_tick(5.0)
        self.hull.anchored = False
        for _ in range(20):
            self.hull.at_maritime_tick(5.0)
        self.assertNotEqual(self.hull.maritime_position, WorldPosition(0.0, 0.0))


class TestInIronsFromADeadStop(EmptySeaMixin, BaseEvenniaTest):
    """
    Coming round with no way on at all.

    The case a live vertical slice found and the unit tests had missed. Backing a
    headsail turns a ship that is stopped dead - that is the entire manoeuvre -
    but the recovery was first written as a raised turn *rate*, and turn rate is
    scaled by speed because it models a rudder. Multiplied by zero speed it gave
    zero turn, so a hull that came to rest head to wind was stuck there for good.
    Docking at a north-facing berth in a northerly did exactly that.

    """

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Test Sloop")
        self.hull.maritime_position = WorldPosition(0.0, 0.0)
        self.hull.motion_limits = MotionLimits(max_speed=5.0, acceleration=0.12, turn_rate=3.0)
        self.hull.heading = NORTH
        self.hull.speed = 0.0
        self.hull.sail_plan = FULL
        self.hull.orders = HelmOrders(heading=115.0, speed=0.0)

    def test_she_makes_no_way_head_to_wind(self):
        """The trap itself, which is correct and should stay."""
        with override_settings(MARITIME_WIND_BEARING=0.0, MARITIME_WIND_SPEED=9.0):
            self.assertAlmostEqual(self.hull.sailing_speed(), 0.0)

    def test_she_can_still_come_round(self):
        with override_settings(
            MARITIME_WIND_BEARING=0.0,
            MARITIME_WIND_SPEED=9.0,
            MARITIME_DEFAULT_DEPTH=100.0,
        ):
            for _ in range(10):
                self.hull.at_maritime_tick(5.0)
        self.assertGreater(self.hull.heading, 20.0)

    def test_and_then_she_sails(self):
        """Off the wind, drawing again, and away - the recovery completed."""
        with override_settings(
            MARITIME_WIND_BEARING=0.0,
            MARITIME_WIND_SPEED=9.0,
            MARITIME_DEFAULT_DEPTH=100.0,
        ):
            for _ in range(40):
                self.hull.at_maritime_tick(5.0)
        self.assertGreater(self.hull.speed, 1.0)

    def test_with_no_canvas_she_stays_helpless(self):
        """
        Nothing to back. A ship with her sails furled and no way on genuinely
        cannot steer, and that must remain true or the trap is not a trap.

        """
        self.hull.sail_plan = FURLED
        with override_settings(
            MARITIME_WIND_BEARING=0.0,
            MARITIME_WIND_SPEED=9.0,
            MARITIME_DEFAULT_DEPTH=100.0,
        ):
            for _ in range(10):
                self.hull.at_maritime_tick(5.0)
        self.assertAlmostEqual(self.hull.heading, NORTH)
