"""
Tests for continuous world positions.

"""

import math
from dataclasses import FrozenInstanceError

from evennia.utils.test_resources import BaseEvenniaTestCase

from ..position import (
    DEFAULT_REGION,
    EAST,
    NORTH,
    SOUTH,
    WEST,
    WorldPosition,
    normalize_bearing,
)


class TestNormalizeBearing(BaseEvenniaTestCase):
    """Wrapping angles into compass range."""

    def test_leaves_in_range_values(self):
        self.assertEqual(normalize_bearing(72.0), 72.0)

    def test_wraps_a_full_turn_to_zero(self):
        self.assertEqual(normalize_bearing(360.0), 0.0)

    def test_wraps_past_a_full_turn(self):
        self.assertEqual(normalize_bearing(370.0), 10.0)

    def test_wraps_negatives_forward(self):
        """A left turn past north is a bearing, not an error."""
        self.assertEqual(normalize_bearing(-90.0), 270.0)

    def test_wraps_many_turns(self):
        self.assertAlmostEqual(normalize_bearing(1090.0), 10.0)

    def test_does_not_clamp(self):
        """Clamping would pin a turning vessel to due north."""
        self.assertNotEqual(normalize_bearing(400.0), 360.0)


class TestConstruction(BaseEvenniaTestCase):
    """Building positions."""

    def test_defaults_to_datum_and_default_region(self):
        pos = WorldPosition(10.0, 20.0)
        self.assertEqual((pos.z, pos.region), (0.0, DEFAULT_REGION))

    def test_accepts_negative_elevation(self):
        """Below datum is the seabed, a diver, a settled wreck."""
        self.assertEqual(WorldPosition(0.0, 0.0, -40.0).z, -40.0)

    def test_is_immutable(self):
        pos = WorldPosition(1.0, 2.0)
        with self.assertRaises(FrozenInstanceError):
            pos.x = 5.0

    def test_equality_is_by_value(self):
        self.assertEqual(WorldPosition(1.0, 2.0, 3.0), WorldPosition(1.0, 2.0, 3.0))

    def test_region_participates_in_equality(self):
        self.assertNotEqual(WorldPosition(1.0, 2.0), WorldPosition(1.0, 2.0, region="lake"))

    def test_rejects_nan(self):
        """
        A NaN propagates silently through every distance that touches it.

        The first visible symptom is a vessel that has stopped moving for no
        apparent reason, far from where the bad value entered.

        """
        with self.assertRaises(ValueError):
            WorldPosition(float("nan"), 0.0)

    def test_rejects_infinity(self):
        with self.assertRaises(ValueError):
            WorldPosition(0.0, float("inf"))

    def test_rejects_non_finite_elevation(self):
        with self.assertRaises(ValueError):
            WorldPosition(0.0, 0.0, float("-inf"))


class TestDistance(BaseEvenniaTestCase):
    """Horizontal and true distance."""

    def test_horizontal_distance(self):
        self.assertAlmostEqual(
            WorldPosition(0.0, 0.0).horizontal_distance_to(WorldPosition(3.0, 4.0)), 5.0
        )

    def test_horizontal_distance_ignores_elevation(self):
        """Navigational distance: how far a vessel must actually travel."""
        surface = WorldPosition(0.0, 0.0, 0.0)
        deep = WorldPosition(3.0, 4.0, -1000.0)
        self.assertAlmostEqual(surface.horizontal_distance_to(deep), 5.0)

    def test_distance_includes_elevation(self):
        self.assertAlmostEqual(
            WorldPosition(0.0, 0.0, 0.0).distance_to(WorldPosition(0.0, 4.0, -3.0)), 5.0
        )

    def test_diver_beneath_a_hull_is_near_horizontally_but_not_in_space(self):
        """
        The distinction the two measures exist for.

        A diver forty metres down is nearly zero metres away for navigation and
        forty metres away for proximity. Conflating them would make a diver look
        adjacent to the hull above.

        """
        hull = WorldPosition(100.0, 100.0, 0.0)
        diver = WorldPosition(100.0, 100.0, -40.0)
        self.assertAlmostEqual(hull.horizontal_distance_to(diver), 0.0)
        self.assertAlmostEqual(hull.distance_to(diver), 40.0)

    def test_distance_to_self_is_zero(self):
        pos = WorldPosition(7.0, 8.0, 9.0)
        self.assertEqual(pos.distance_to(pos), 0.0)

    def test_distance_is_symmetric(self):
        first, second = WorldPosition(1.0, 2.0, 3.0), WorldPosition(4.0, 6.0, 8.0)
        self.assertAlmostEqual(first.distance_to(second), second.distance_to(first))

    def test_cross_region_distance_is_refused(self):
        ocean = WorldPosition(0.0, 0.0)
        lake = WorldPosition(0.0, 0.0, region="lake")
        with self.assertRaises(ValueError):
            ocean.distance_to(lake)

    def test_cross_region_horizontal_distance_is_refused(self):
        with self.assertRaises(ValueError):
            WorldPosition(0.0, 0.0).horizontal_distance_to(WorldPosition(0.0, 0.0, region="lake"))


class TestBearing(BaseEvenniaTestCase):
    """Compass bearings."""

    def setUp(self):
        super().setUp()
        self.origin = WorldPosition(0.0, 0.0)

    def test_north(self):
        self.assertAlmostEqual(self.origin.bearing_to(WorldPosition(0.0, 10.0)), NORTH)

    def test_east(self):
        """
        East is 90, which requires atan2(dx, dy) rather than the usual (dy, dx).

        Swapping them yields the mathematical convention - anticlockwise from
        east - and a vessel that steers at right angles to its orders.

        """
        self.assertAlmostEqual(self.origin.bearing_to(WorldPosition(10.0, 0.0)), EAST)

    def test_south(self):
        self.assertAlmostEqual(self.origin.bearing_to(WorldPosition(0.0, -10.0)), SOUTH)

    def test_west(self):
        self.assertAlmostEqual(self.origin.bearing_to(WorldPosition(-10.0, 0.0)), WEST)

    def test_north_east(self):
        self.assertAlmostEqual(self.origin.bearing_to(WorldPosition(10.0, 10.0)), 45.0)

    def test_north_west_wraps_into_range(self):
        self.assertAlmostEqual(self.origin.bearing_to(WorldPosition(-10.0, 10.0)), 315.0)

    def test_always_in_range(self):
        for x, y in ((1, 1), (-1, 1), (1, -1), (-1, -1), (0, 1), (1, 0)):
            bearing = self.origin.bearing_to(WorldPosition(float(x), float(y)))
            self.assertGreaterEqual(bearing, 0.0)
            self.assertLess(bearing, 360.0)

    def test_ignores_elevation(self):
        """A bearing is a heading to steer, and a vessel cannot steer downwards."""
        self.assertAlmostEqual(self.origin.bearing_to(WorldPosition(0.0, 10.0, -500.0)), NORTH)

    def test_same_horizontal_position_gives_zero(self):
        self.assertEqual(self.origin.bearing_to(WorldPosition(0.0, 0.0, -40.0)), 0.0)

    def test_cross_region_bearing_is_refused(self):
        with self.assertRaises(ValueError):
            self.origin.bearing_to(WorldPosition(1.0, 1.0, region="lake"))


class TestMovement(BaseEvenniaTestCase):
    """Deriving new positions."""

    def test_offset_shifts_each_axis(self):
        moved = WorldPosition(1.0, 2.0, 3.0).offset(dx=10.0, dy=20.0, dz=30.0)
        self.assertEqual((moved.x, moved.y, moved.z), (11.0, 22.0, 33.0))

    def test_offset_leaves_the_original(self):
        pos = WorldPosition(1.0, 2.0)
        pos.offset(dx=100.0)
        self.assertEqual(pos.x, 1.0)

    def test_offset_keeps_the_region(self):
        self.assertEqual(WorldPosition(0.0, 0.0, region="lake").offset(dx=1.0).region, "lake")

    def test_with_z_changes_only_elevation(self):
        seabed = WorldPosition(50.0, 60.0, 0.0).with_z(-14.2)
        self.assertEqual((seabed.x, seabed.y, seabed.z), (50.0, 60.0, -14.2))

    def test_moved_north(self):
        moved = WorldPosition(0.0, 0.0).moved(NORTH, 100.0)
        self.assertAlmostEqual(moved.x, 0.0)
        self.assertAlmostEqual(moved.y, 100.0)

    def test_moved_east(self):
        moved = WorldPosition(0.0, 0.0).moved(EAST, 100.0)
        self.assertAlmostEqual(moved.x, 100.0)
        self.assertAlmostEqual(moved.y, 0.0)

    def test_moved_covers_the_distance(self):
        origin = WorldPosition(0.0, 0.0)
        self.assertAlmostEqual(origin.horizontal_distance_to(origin.moved(72.0, 250.0)), 250.0)

    def test_moved_matches_the_bearing_travelled(self):
        """Travelling a bearing and then measuring it must agree."""
        origin = WorldPosition(0.0, 0.0)
        for bearing in (0.0, 45.0, 90.0, 137.5, 180.0, 271.3, 359.0):
            self.assertAlmostEqual(
                origin.bearing_to(origin.moved(bearing, 500.0)), bearing, places=6
            )

    def test_moved_wraps_out_of_range_bearings(self):
        origin = WorldPosition(0.0, 0.0)
        self.assertAlmostEqual(origin.moved(450.0, 10.0).x, origin.moved(90.0, 10.0).x, places=9)

    def test_moved_keeps_elevation(self):
        self.assertEqual(WorldPosition(0.0, 0.0, -20.0).moved(NORTH, 50.0).z, -20.0)

    def test_round_trip_returns_to_origin(self):
        origin = WorldPosition(100.0, 200.0)
        there_and_back = origin.moved(72.0, 500.0).moved(72.0 + 180.0, 500.0)
        self.assertAlmostEqual(origin.horizontal_distance_to(there_and_back), 0.0, places=6)


class TestRepresentation(BaseEvenniaTestCase):
    """Debug output."""

    def test_str_shows_coordinates_and_region(self):
        text = str(WorldPosition(18422.9, 9912.4, -3.5, region="western_sea"))
        self.assertIn("18422.900", text)
        self.assertIn("-3.500", text)
        self.assertIn("western_sea", text)

    def test_str_shows_millimetres(self):
        """
        Collision and boarding work at this scale, and this is the view a
        developer reads when working out why two hulls did or did not touch.

        """
        self.assertIn("18422.573", str(WorldPosition(18422.5734, 0.0)))

    def test_full_precision_is_retained_regardless_of_display(self):
        """Display rounding must never be mistaken for stored precision."""
        position = WorldPosition(925.8573215153035, -11011.44325490956)
        self.assertEqual(position.x, 925.8573215153035)
        self.assertEqual(position.y, -11011.44325490956)

    def test_sub_millimetre_differences_survive_arithmetic(self):
        """Grapple range checks depend on this holding."""
        first = WorldPosition(0.0, 0.0)
        second = first.offset(dx=0.0001)
        self.assertGreater(second.horizontal_distance_to(first), 0.0)

    def test_math_module_is_used_for_hypot(self):
        """Guards the horizontal formula against a hand-rolled regression."""
        self.assertAlmostEqual(
            WorldPosition(0.0, 0.0).horizontal_distance_to(WorldPosition(1.0, 1.0)),
            math.sqrt(2.0),
        )
