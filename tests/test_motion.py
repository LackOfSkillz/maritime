"""
Tests for vessel motion.

"""

from evennia.utils.test_resources import BaseEvenniaTestCase

from ..motion import (
    HelmOrders,
    MotionLimits,
    MotionState,
    advance,
    turn_rate_at_speed,
)
from ..position import EAST, NORTH, SOUTH, WEST, WorldPosition, bearing_difference


def at_origin(heading=NORTH, speed=0.0):
    """A vessel at the origin, for tests that only care about what changes."""
    return MotionState(position=WorldPosition(0.0, 0.0), heading=heading, speed=speed)


BRISK = MotionLimits(max_speed=10.0, acceleration=1.0, turn_rate=6.0)


class TestBearingDifference(BaseEvenniaTestCase):
    """Shortest turn between two bearings."""

    def test_straight_ahead_is_zero(self):
        self.assertEqual(bearing_difference(72.0, 72.0), 0.0)

    def test_starboard_is_positive(self):
        self.assertEqual(bearing_difference(0.0, 90.0), 90.0)

    def test_port_is_negative(self):
        self.assertEqual(bearing_difference(90.0, 0.0), -90.0)

    def test_takes_the_short_way_across_north(self):
        """
        Naive subtraction gives -340 and swings the vessel almost all the way
        round the compass to make a twenty-degree alteration.

        """
        self.assertEqual(bearing_difference(350.0, 10.0), 20.0)

    def test_short_way_the_other_direction(self):
        self.assertEqual(bearing_difference(10.0, 350.0), -20.0)

    def test_never_exceeds_half_a_circle(self):
        for start in range(0, 360, 17):
            for end in range(0, 360, 23):
                self.assertLessEqual(abs(bearing_difference(float(start), float(end))), 180.0)

    def test_opposite_is_deterministic(self):
        """Both ways are equally short; picking one keeps a manoeuvre reproducible."""
        self.assertEqual(bearing_difference(0.0, 180.0), bearing_difference(0.0, 180.0))


class TestMotionLimits(BaseEvenniaTestCase):
    """Hull capabilities."""

    def test_rejects_negative_max_speed(self):
        with self.assertRaises(ValueError):
            MotionLimits(max_speed=-1.0)

    def test_rejects_non_finite_turn_rate(self):
        with self.assertRaises(ValueError):
            MotionLimits(turn_rate=float("inf"))

    def test_zero_is_allowed(self):
        """A hulk under tow has no power of its own."""
        self.assertEqual(MotionLimits(max_speed=0.0).max_speed, 0.0)


class TestHelmOrders(BaseEvenniaTestCase):
    """What the vessel is told to do."""

    def test_normalises_the_heading(self):
        self.assertEqual(HelmOrders(heading=400.0).heading, 40.0)

    def test_normalises_a_negative_heading(self):
        self.assertEqual(HelmOrders(heading=-90.0).heading, 270.0)

    def test_refuses_negative_speed(self):
        """Order a reciprocal heading instead; ships do not drive backwards."""
        with self.assertRaises(ValueError):
            HelmOrders(speed=-1.0)


class TestAcceleration(BaseEvenniaTestCase):
    """Gathering and losing way."""

    def test_does_not_reach_ordered_speed_instantly(self):
        """The acceptance criterion for this phase: gradual, not immediate."""
        result = advance(at_origin(), HelmOrders(speed=10.0), BRISK, elapsed=1.0)
        self.assertLess(result.speed, 10.0)
        self.assertGreater(result.speed, 0.0)

    def test_accelerates_at_the_stated_rate(self):
        result = advance(at_origin(), HelmOrders(speed=10.0), BRISK, elapsed=3.0)
        self.assertAlmostEqual(result.speed, 3.0)

    def test_reaches_ordered_speed_eventually(self):
        result = advance(at_origin(), HelmOrders(speed=6.0), BRISK, elapsed=60.0)
        self.assertAlmostEqual(result.speed, 6.0)

    def test_does_not_overshoot(self):
        result = advance(at_origin(), HelmOrders(speed=2.0), BRISK, elapsed=60.0)
        self.assertAlmostEqual(result.speed, 2.0)

    def test_slows_when_ordered_slower(self):
        result = advance(at_origin(speed=10.0), HelmOrders(speed=0.0), BRISK, elapsed=4.0)
        self.assertAlmostEqual(result.speed, 6.0)

    def test_stops_without_going_astern(self):
        result = advance(at_origin(speed=5.0), HelmOrders(speed=0.0), BRISK, elapsed=60.0)
        self.assertEqual(result.speed, 0.0)

    def test_cannot_exceed_the_hull_limit(self):
        """An order beyond the hull's capability is capped, not obeyed."""
        result = advance(at_origin(), HelmOrders(speed=1000.0), BRISK, elapsed=600.0)
        self.assertAlmostEqual(result.speed, BRISK.max_speed)


class TestTurning(BaseEvenniaTestCase):
    """Coming round."""

    def test_does_not_turn_instantly(self):
        state = at_origin(heading=NORTH, speed=10.0)
        result = advance(state, HelmOrders(heading=EAST, speed=10.0), BRISK, elapsed=1.0)
        self.assertGreater(result.heading, NORTH)
        self.assertLess(result.heading, EAST)

    def test_turns_at_the_stated_rate_at_full_speed(self):
        state = at_origin(heading=NORTH, speed=10.0)
        result = advance(state, HelmOrders(heading=EAST, speed=10.0), BRISK, elapsed=5.0)
        self.assertAlmostEqual(result.heading, 30.0, places=4)

    def test_settles_on_the_ordered_heading(self):
        state = at_origin(heading=NORTH, speed=10.0)
        result = advance(state, HelmOrders(heading=EAST, speed=10.0), BRISK, elapsed=120.0)
        self.assertAlmostEqual(result.heading, EAST, places=4)

    def test_does_not_overshoot_the_order(self):
        state = at_origin(heading=NORTH, speed=10.0)
        result = advance(state, HelmOrders(heading=10.0, speed=10.0), BRISK, elapsed=120.0)
        self.assertAlmostEqual(result.heading, 10.0, places=4)

    def test_turns_the_short_way_across_north(self):
        state = at_origin(heading=350.0, speed=10.0)
        result = advance(state, HelmOrders(heading=10.0, speed=10.0), BRISK, elapsed=1.0)
        self.assertTrue(result.heading > 350.0 or result.heading < 10.0)

    def test_turns_to_port_when_that_is_shorter(self):
        state = at_origin(heading=EAST, speed=10.0)
        result = advance(state, HelmOrders(heading=NORTH, speed=10.0), BRISK, elapsed=1.0)
        self.assertLess(result.heading, EAST)


class TestSteerageWay(BaseEvenniaTestCase):
    """A rudder needs water flowing past it."""

    def test_no_steering_when_stopped(self):
        self.assertEqual(turn_rate_at_speed(BRISK, 0.0), 0.0)

    def test_full_rate_at_full_speed(self):
        self.assertAlmostEqual(turn_rate_at_speed(BRISK, BRISK.max_speed), BRISK.turn_rate)

    def test_half_rate_at_half_speed(self):
        self.assertAlmostEqual(turn_rate_at_speed(BRISK, 5.0), 3.0)

    def test_does_not_exceed_full_rate(self):
        self.assertAlmostEqual(turn_rate_at_speed(BRISK, 1000.0), BRISK.turn_rate)

    def test_a_stopped_vessel_cannot_come_round(self):
        """
        Losing way is a real problem, not an inconvenience. A becalmed ship
        cannot simply spin to face a threat.

        """
        state = at_origin(heading=NORTH, speed=0.0)
        result = advance(state, HelmOrders(heading=SOUTH, speed=0.0), BRISK, elapsed=60.0)
        self.assertEqual(result.heading, NORTH)

    def test_a_hull_with_no_power_cannot_steer(self):
        dead = MotionLimits(max_speed=0.0, acceleration=0.0, turn_rate=6.0)
        self.assertEqual(turn_rate_at_speed(dead, 5.0), 0.0)


class TestPositionChanges(BaseEvenniaTestCase):
    """Actually going somewhere."""

    def test_a_stopped_vessel_does_not_move(self):
        result = advance(at_origin(), HelmOrders(speed=0.0), BRISK, elapsed=100.0)
        self.assertEqual(result.position, WorldPosition(0.0, 0.0))

    def test_moves_north_when_heading_north(self):
        state = at_origin(heading=NORTH, speed=5.0)
        result = advance(state, HelmOrders(heading=NORTH, speed=5.0), BRISK, elapsed=10.0)
        self.assertAlmostEqual(result.position.y, 50.0)
        self.assertAlmostEqual(result.position.x, 0.0)

    def test_moves_east_when_heading_east(self):
        state = at_origin(heading=EAST, speed=5.0)
        result = advance(state, HelmOrders(heading=EAST, speed=5.0), BRISK, elapsed=10.0)
        self.assertAlmostEqual(result.position.x, 50.0)

    def test_moves_west_when_heading_west(self):
        state = at_origin(heading=WEST, speed=5.0)
        result = advance(state, HelmOrders(heading=WEST, speed=5.0), BRISK, elapsed=10.0)
        self.assertAlmostEqual(result.position.x, -50.0)

    def test_position_is_continuous_not_stepped(self):
        """Position is a float track, never a grid square."""
        state = at_origin(heading=41.0, speed=3.3)
        result = advance(state, HelmOrders(heading=41.0, speed=3.3), BRISK, elapsed=7.0)
        self.assertNotEqual(result.position.x, round(result.position.x))

    def test_elevation_is_untouched(self):
        """Surface vessels do not steer vertically."""
        state = MotionState(position=WorldPosition(0.0, 0.0, 0.0), heading=NORTH, speed=5.0)
        result = advance(state, HelmOrders(heading=NORTH, speed=5.0), BRISK, elapsed=10.0)
        self.assertEqual(result.position.z, 0.0)

    def test_region_is_preserved(self):
        state = MotionState(
            position=WorldPosition(0.0, 0.0, region="lake"), heading=NORTH, speed=5.0
        )
        result = advance(state, HelmOrders(heading=NORTH, speed=5.0), BRISK, elapsed=10.0)
        self.assertEqual(result.position.region, "lake")


class TestSubStepping(BaseEvenniaTestCase):
    """Turning carves an arc rather than a corner."""

    def test_a_turning_vessel_does_not_pivot_on_the_spot(self):
        """
        Advanced in one jump, a turning vessel would swing instantly and then
        run the whole distance on her new heading. Sub-stepping makes her
        describe the curve she actually would.

        """
        state = at_origin(heading=NORTH, speed=10.0)
        orders = HelmOrders(heading=EAST, speed=10.0)
        arc = advance(state, orders, BRISK, elapsed=30.0)
        corner = advance(state, orders, BRISK, elapsed=30.0, step=30.0)
        self.assertNotAlmostEqual(arc.position.x, corner.position.x, places=1)

    def test_the_arc_stays_short_of_the_corner(self):
        """Turning while moving covers less ground east than pivoting first."""
        state = at_origin(heading=NORTH, speed=10.0)
        orders = HelmOrders(heading=EAST, speed=10.0)
        arc = advance(state, orders, BRISK, elapsed=30.0)
        corner = advance(state, orders, BRISK, elapsed=30.0, step=30.0)
        self.assertLess(arc.position.x, corner.position.x)

    def test_track_is_independent_of_scheduler_cadence(self):
        """
        A laggy server must produce the same voyage as a smooth one, or ships
        quietly end up somewhere else when the host is busy.

        """
        state = at_origin(heading=NORTH, speed=0.0)
        orders = HelmOrders(heading=EAST, speed=8.0)

        smooth = state
        for _ in range(60):
            smooth = advance(smooth, orders, BRISK, elapsed=1.0)

        laggy = state
        for _ in range(6):
            laggy = advance(laggy, orders, BRISK, elapsed=10.0)

        self.assertAlmostEqual(smooth.position.x, laggy.position.x, places=6)
        self.assertAlmostEqual(smooth.position.y, laggy.position.y, places=6)

    def test_zero_elapsed_changes_nothing(self):
        state = at_origin(heading=NORTH, speed=5.0)
        self.assertEqual(advance(state, HelmOrders(speed=5.0), BRISK, elapsed=0.0), state)

    def test_negative_elapsed_is_refused(self):
        with self.assertRaises(ValueError):
            advance(at_origin(), HelmOrders(), BRISK, elapsed=-1.0)

    def test_non_positive_step_is_refused(self):
        with self.assertRaises(ValueError):
            advance(at_origin(), HelmOrders(), BRISK, elapsed=1.0, step=0.0)

    def test_fractional_remainder_is_applied(self):
        state = at_origin(heading=NORTH, speed=10.0)
        result = advance(state, HelmOrders(heading=NORTH, speed=10.0), BRISK, elapsed=2.5)
        self.assertAlmostEqual(result.position.y, 25.0)


class TestDeterminism(BaseEvenniaTestCase):
    """The same voyage twice."""

    def test_identical_inputs_give_identical_tracks(self):
        state = at_origin(heading=17.0, speed=2.0)
        orders = HelmOrders(heading=203.0, speed=7.5)
        first = advance(state, orders, BRISK, elapsed=123.4)
        second = advance(state, orders, BRISK, elapsed=123.4)
        self.assertEqual(first, second)

    def test_state_is_immutable(self):
        state = at_origin()
        advance(state, HelmOrders(speed=5.0), BRISK, elapsed=10.0)
        self.assertEqual(state.speed, 0.0)
