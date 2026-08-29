"""
Tests for testing a whole hull along a whole track.

"""

from django.test import override_settings

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest, BaseEvenniaTestCase

from ..bathymetry import ROCK, FlatSeaMapProvider, MaritimeMapProvider
from ..grounding import (
    MIN_SWEEP_STEP,
    check_swept_grounding,
    hull_points,
    sweep_positions,
)
from ..motion import HelmOrders, MotionLimits
from ..position import EAST, NORTH, WorldPosition
from ..rooms import ShipRoom
from ..typeclasses import Vessel
from ..vessel import OPEN
from .base import EmptySeaMixin

HERE = WorldPosition(0.0, 0.0)


class NarrowReef(MaritimeMapProvider):
    """
    A rock ledge ten metres wide, lying across an otherwise deep shelf.

    Narrow enough that a vessel moving faster than ten metres a tick can step
    clean over it if only her destination is tested.

    """

    START, END = 500.0, 510.0

    def terrain_z_at(self, position):
        if self.START <= position.x <= self.END:
            return -1.0
        return -40.0

    def bottom_type_at(self, position):
        return ROCK


class Shelving(MaritimeMapProvider):
    """
    Ground that rises steadily to the east, a metre for every ten.

    A hull lying along it has different water at her bow and her stern, which is
    what makes "the least found anywhere on her" a different number from "the
    most".

    """

    def terrain_z_at(self, position):
        return -20.0 + position.x / 10.0


class ReefToTheSide(MaritimeMapProvider):
    """Deep water, and a rock shelf just off the track to starboard."""

    def terrain_z_at(self, position):
        return -1.0 if position.y > 3.0 else -40.0

    def bottom_type_at(self, position):
        return ROCK


class TestHullPoints(BaseEvenniaTestCase):
    """A hull is not a point."""

    def test_an_unmeasured_hull_is_tested_at_her_centre(self):
        """
        A game that has not measured its ships gets the old behaviour rather than
        a hull of size zero or an error.

        """
        self.assertEqual(hull_points(HERE, NORTH, 0.0, 0.0), (HERE,))

    def test_a_measured_hull_gives_several_points(self):
        self.assertEqual(len(hull_points(HERE, NORTH, 20.0, 6.0)), 7)

    def test_her_bow_is_half_a_length_ahead(self):
        points = hull_points(HERE, NORTH, 20.0, 6.0)
        self.assertAlmostEqual(max(point.y for point in points), 10.0)

    def test_she_is_as_wide_as_her_beam(self):
        points = hull_points(HERE, EAST, 20.0, 6.0)
        spread = max(point.y for point in points) - min(point.y for point in points)
        self.assertAlmostEqual(spread, 6.0)

    def test_the_outline_turns_with_her(self):
        heading_north = hull_points(HERE, NORTH, 20.0, 6.0)
        heading_east = hull_points(HERE, EAST, 20.0, 6.0)
        self.assertAlmostEqual(max(point.y for point in heading_north), 10.0)
        self.assertAlmostEqual(max(point.x for point in heading_east), 10.0)


class TestSweepPositions(BaseEvenniaTestCase):
    """Sampling the track rather than its end."""

    def test_a_short_step_is_tested_once(self):
        near = WorldPosition(1.0, 0.0)
        self.assertEqual(sweep_positions(HERE, near, 20.0), (near,))

    def test_a_long_run_is_broken_up(self):
        far = WorldPosition(500.0, 0.0)
        self.assertGreater(len(sweep_positions(HERE, far, 20.0)), 10)

    def test_it_always_ends_where_she_was_going(self):
        far = WorldPosition(500.0, 0.0)
        self.assertEqual(sweep_positions(HERE, far, 20.0)[-1], far)

    def test_the_gaps_never_exceed_half_her_length(self):
        """
        So consecutive footprints overlap, and nothing longer than the gap can
        lie between two tests untouched.

        """
        far = WorldPosition(500.0, 0.0)
        positions = (HERE,) + sweep_positions(HERE, far, 40.0)
        gaps = [
            positions[i].horizontal_distance_to(positions[i + 1]) for i in range(len(positions) - 1)
        ]
        self.assertLessEqual(max(gaps), 20.0 + 1e-6)

    def test_an_unmeasured_hull_still_gets_a_bounded_number_of_samples(self):
        """
        A length of zero would otherwise ask for an unbounded number of steps
        across a long run.

        """
        far = WorldPosition(1000.0, 0.0)
        self.assertLessEqual(len(sweep_positions(HERE, far, 0.0)), 1000.0 / MIN_SWEEP_STEP + 2)


class TestSweptGrounding(BaseEvenniaTestCase):
    """What the sweep catches that a point test does not."""

    def swept(self, start, end, **kwargs):
        """
        Args:
            start (WorldPosition): Where she began.
            end (WorldPosition): Where she was going.
            **kwargs: Overrides.

        Returns:
            result (GroundingResult): The outcome.

        """
        attempt = {
            "heading": EAST,
            "draft": 2.0,
            "speed": 5.0,
            "length": 20.0,
            "beam": 6.0,
            "map_provider": NarrowReef(),
            "game_time": 0.0,
        }
        attempt.update(kwargs)
        return check_swept_grounding(start, end, **attempt)

    def test_deep_water_all_the_way_is_clear(self):
        result = self.swept(HERE, WorldPosition(400.0, 0.0))
        self.assertTrue(result)

    def test_a_clear_run_ends_where_she_was_going(self):
        """
        And never at the shallowest place she crossed, or she would be dragged
        back to the thinnest water on her track.

        """
        end = WorldPosition(400.0, 0.0)
        self.assertEqual(self.swept(HERE, end).position, end)

    def test_she_cannot_step_over_a_narrow_reef(self):
        """
        The whole reason for the sweep. Both ends of this move are in forty
        metres of water; a point test at the destination says she is perfectly
        safe, and she has just driven over a rock ledge at ten knots.

        """
        result = self.swept(WorldPosition(450.0, 0.0), WorldPosition(560.0, 0.0))
        self.assertFalse(result)

    def test_the_old_point_test_would_have_missed_it(self):
        """States the gap explicitly, so nobody closes it again by accident."""
        from ..grounding import check_grounding

        destination = WorldPosition(560.0, 0.0)
        self.assertTrue(check_grounding(destination, 2.0, 5.0, NarrowReef(), 0.0))
        self.assertFalse(self.swept(WorldPosition(450.0, 0.0), destination))

    def test_she_is_stopped_where_she_struck(self):
        """
        Not where she was going. A ship that hit a reef a third of the way
        through a tick did not travel the other two thirds.

        """
        result = self.swept(WorldPosition(450.0, 0.0), WorldPosition(560.0, 0.0))
        self.assertLess(result.position.x, 560.0)

    def test_her_bow_grounds_though_her_centre_is_clear(self):
        """
        A large ship can have her bow over a reef while her centre is still in
        deep water, and testing the centre alone calls that safe.

        """
        edge = WorldPosition(0.0, 0.0)
        clear = check_swept_grounding(edge, edge, NORTH, 2.0, 1.0, 0.0, 0.0, ReefToTheSide(), 0.0)
        wide = check_swept_grounding(edge, edge, NORTH, 2.0, 1.0, 20.0, 6.0, ReefToTheSide(), 0.0)
        self.assertTrue(clear)
        self.assertFalse(wide)

    def test_a_level_bottom_gives_one_clearance(self):
        result = check_swept_grounding(
            HERE, HERE, EAST, 2.0, 1.0, 20.0, 6.0, FlatSeaMapProvider(depth=10.0), 0.0
        )
        self.assertAlmostEqual(result.clearance, 8.0)

    def test_it_reports_the_least_water_found_anywhere_on_her(self):
        """
        A vessel whose bow is in three metres and whose stern is in twelve has
        three, which is the number that decides anything.

        Measured on sloping ground on purpose. On a level bottom every point on
        the hull returns the same clearance, so a test there cannot tell the
        least from the greatest - and mutation testing duly walked straight
        through the first version of this.

        """
        result = check_swept_grounding(HERE, HERE, EAST, 2.0, 1.0, 20.0, 6.0, Shelving(), 0.0)
        self.assertAlmostEqual(result.clearance, 17.0)
        self.assertNotAlmostEqual(result.clearance, 19.0)


class TestVesselSweeps(EmptySeaMixin, BaseEvenniaTest):
    """A hull under way over a reef she would once have skipped."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Test Sloop")
        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.deck.vessel = self.hull
        self.deck.exposure = OPEN
        self.hull.maritime_position = WorldPosition(450.0, 0.0)
        self.hull.motion_limits = MotionLimits(max_speed=20.0, acceleration=100.0, turn_rate=8.0)
        self.hull.heading = EAST
        self.hull.speed = 20.0
        self.hull.orders = HelmOrders(heading=EAST, speed=20.0)
        self.hull.draft = 2.0
        self.hull.length = 20.0
        self.hull.beam = 6.0

    def test_a_fast_hull_no_longer_steps_over_the_ledge(self):
        path = f"{NarrowReef.__module__}.NarrowReef"
        with override_settings(MARITIME_MAP_PROVIDER=path):
            self.hull.at_maritime_tick(10.0)
        self.assertTrue(self.hull.aground)

    def test_and_she_is_left_at_the_ledge_not_beyond_it(self):
        path = f"{NarrowReef.__module__}.NarrowReef"
        with override_settings(MARITIME_MAP_PROVIDER=path):
            self.hull.at_maritime_tick(10.0)
        self.assertLess(self.hull.maritime_position.x, NarrowReef.END + 20.0)
