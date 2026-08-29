"""
Tests for what a lookout can see.

"""

from evennia.utils.test_resources import BaseEvenniaTestCase

from ..observation import (
    CLASSIFIED,
    CONTACT,
    DEFAULT_VISIBILITY,
    IDENTIFIED,
    VESSEL,
    Sighting,
    bearing_in_points,
    detection_level,
    detection_limit,
    geographic_range,
    horizon_distance,
    relative_bearing,
    scan,
    sight,
)
from ..position import METRES_PER_NAUTICAL_MILE, WorldPosition

HERE = WorldPosition(0.0, 0.0)


class TestHorizon(BaseEvenniaTestCase):
    """How far the water curves away."""

    def test_a_two_metre_eye_sees_about_three_miles(self):
        miles = horizon_distance(2.0) / METRES_PER_NAUTICAL_MILE
        self.assertAlmostEqual(miles, 2.93, places=2)

    def test_a_thirty_metre_masthead_sees_about_eleven(self):
        """
        The figure a navigator would recognise, and the reason to climb.

        """
        miles = horizon_distance(30.0) / METRES_PER_NAUTICAL_MILE
        self.assertAlmostEqual(miles, 11.34, places=2)

    def test_height_helps_but_with_diminishing_returns(self):
        """
        Square root, not linear. Four times the height is twice the range, which
        is why a taller mast is worth so much less than it looks.

        """
        self.assertAlmostEqual(horizon_distance(40.0), 2.0 * horizon_distance(10.0))

    def test_an_eye_at_the_surface_sees_nothing(self):
        self.assertEqual(horizon_distance(0.0), 0.0)

    def test_an_eye_below_the_surface_sees_nothing(self):
        self.assertEqual(horizon_distance(-3.0), 0.0)


class TestGeographicRange(BaseEvenniaTestCase):
    """Two horizons, not one."""

    def test_a_tall_target_is_seen_from_beyond_your_own_horizon(self):
        """
        The point of the whole model. Her masthead is over the curve looking
        back, so she is visible long before anything at your own height is.

        """
        own = horizon_distance(2.0)
        self.assertGreater(geographic_range(2.0, 30.0), own)

    def test_it_is_the_sum_of_both(self):
        self.assertAlmostEqual(
            geographic_range(2.0, 30.0), horizon_distance(2.0) + horizon_distance(30.0)
        )

    def test_it_is_symmetric(self):
        """If she can see you, you can see her - the geometry does not take sides."""
        self.assertAlmostEqual(geographic_range(2.0, 30.0), geographic_range(30.0, 2.0))

    def test_a_swimmer_is_only_visible_within_your_own_horizon(self):
        self.assertAlmostEqual(geographic_range(20.0, 0.0), horizon_distance(20.0))


class TestDetectionLimit(BaseEvenniaTestCase):
    """Whichever runs out first."""

    def test_clear_air_leaves_the_horizon_deciding(self):
        limit = detection_limit(2.0, 2.0, visibility=DEFAULT_VISIBILITY)
        self.assertAlmostEqual(limit, geographic_range(2.0, 2.0))

    def test_haze_overrides_the_horizon(self):
        limit = detection_limit(30.0, 30.0, visibility=500.0)
        self.assertAlmostEqual(limit, 500.0)

    def test_in_fog_height_stops_helping(self):
        """
        Why fog is dangerous rather than merely inconvenient: the masthead is
        worth nothing, and two ships close at a range neither chose.

        """
        low = detection_limit(2.0, 2.0, visibility=200.0)
        high = detection_limit(40.0, 40.0, visibility=200.0)
        self.assertEqual(low, high)

    def test_no_visibility_means_no_detection(self):
        self.assertEqual(detection_limit(30.0, 30.0, visibility=0.0), 0.0)

    def test_negative_visibility_is_treated_as_none(self):
        self.assertEqual(detection_limit(30.0, 30.0, visibility=-5.0), 0.0)


class TestDetectionLevel(BaseEvenniaTestCase):
    """How much you can tell."""

    def test_beyond_the_limit_is_nothing_at_all(self):
        self.assertIsNone(detection_level(1001.0, 1000.0))

    def test_at_the_edge_there_is_something_on_the_water(self):
        self.assertEqual(detection_level(950.0, 1000.0), CONTACT)

    def test_closer_in_it_is_a_vessel(self):
        self.assertEqual(detection_level(700.0, 1000.0), VESSEL)

    def test_closer_still_you_can_see_her_rig(self):
        self.assertEqual(detection_level(400.0, 1000.0), CLASSIFIED)

    def test_near_enough_you_know_the_ship(self):
        self.assertEqual(detection_level(150.0, 1000.0), IDENTIFIED)

    def test_certainty_only_ever_increases_as_you_close(self):
        """
        Closing to identify has to be worth doing, which needs the ladder to run
        one way.

        """
        order = [None, CONTACT, VESSEL, CLASSIFIED, IDENTIFIED]
        ranks = [order.index(detection_level(d, 1000.0)) for d in range(1200, 0, -100)]
        self.assertEqual(ranks, sorted(ranks))

    def test_a_zero_limit_sees_nothing_even_at_no_range(self):
        self.assertIsNone(detection_level(0.0, 0.0))


class TestRelativeBearing(BaseEvenniaTestCase):
    """Where something lies relative to your head."""

    def test_ahead_is_zero(self):
        self.assertAlmostEqual(relative_bearing(90.0, 90.0), 0.0)

    def test_starboard_is_positive(self):
        self.assertGreater(relative_bearing(0.0, 45.0), 0.0)

    def test_port_is_negative(self):
        self.assertLess(relative_bearing(0.0, 315.0), 0.0)

    def test_it_takes_the_short_way_round(self):
        self.assertAlmostEqual(relative_bearing(350.0, 10.0), 20.0)


class TestBearingInPoints(BaseEvenniaTestCase):
    """Saying it the way a lookout calls it."""

    def test_dead_ahead(self):
        self.assertEqual(bearing_in_points(0.0), "dead ahead")

    def test_a_shade_off_is_still_dead_ahead(self):
        self.assertEqual(bearing_in_points(3.0), "dead ahead")

    def test_dead_astern(self):
        self.assertEqual(bearing_in_points(180.0), "dead astern")

    def test_points_off_the_bow(self):
        self.assertEqual(bearing_in_points(22.5), "two points off the starboard bow")

    def test_the_side_is_named(self):
        self.assertEqual(bearing_in_points(-22.5), "two points off the port bow")

    def test_broad_on_the_bow(self):
        self.assertEqual(bearing_in_points(45.0), "broad on the starboard bow")

    def test_on_the_beam(self):
        self.assertEqual(bearing_in_points(90.0), "on the starboard beam")
        self.assertEqual(bearing_in_points(-90.0), "on the port beam")

    def test_broad_on_the_quarter(self):
        self.assertEqual(bearing_in_points(135.0), "broad on the starboard quarter")

    def test_fine_on_the_quarter(self):
        self.assertEqual(bearing_in_points(-160.0), "fine on the port quarter")

    def test_every_bearing_has_a_call(self):
        """No gap in the ladder, and no bearing a lookout cannot report."""
        for degrees in range(-180, 181):
            self.assertTrue(bearing_in_points(float(degrees)))


class TestSight(BaseEvenniaTestCase):
    """Looking at one thing."""

    def test_something_close_is_seen(self):
        found = sight(HERE, 0.0, 30.0, "her", WorldPosition(0.0, 1000.0), 30.0)
        self.assertIsInstance(found, Sighting)

    def test_something_over_the_horizon_is_not(self):
        far = WorldPosition(0.0, 100.0 * METRES_PER_NAUTICAL_MILE)
        self.assertIsNone(sight(HERE, 0.0, 30.0, "her", far, 30.0))

    def test_it_reports_the_range(self):
        found = sight(HERE, 0.0, 30.0, "her", WorldPosition(0.0, 1000.0), 30.0)
        self.assertAlmostEqual(found.distance, 1000.0)

    def test_it_reports_a_true_bearing(self):
        found = sight(HERE, 0.0, 30.0, "her", WorldPosition(1000.0, 0.0), 30.0)
        self.assertAlmostEqual(found.bearing, 90.0)

    def test_it_reports_where_to_look(self):
        found = sight(HERE, 45.0, 30.0, "her", WorldPosition(1000.0, 0.0), 30.0)
        self.assertAlmostEqual(found.relative, 45.0)

    def test_dead_astern_is_reported_as_astern_from_either_side(self):
        """
        Plus and minus 180 are the same bearing, and a lookout says the same
        thing about both. Only the sign of the turn back to it differs, and
        nobody is turning towards their own wake.

        """
        found = sight(HERE, 270.0, 30.0, "her", WorldPosition(1000.0, 0.0), 30.0)
        self.assertAlmostEqual(abs(found.relative), 180.0)
        self.assertEqual(bearing_in_points(found.relative), "dead astern")

    def test_another_region_is_not_visible(self):
        """
        Regions are separate coordinate spaces. A lake and an ocean can hold the
        same numbers without being anywhere near each other.

        """
        elsewhere = WorldPosition(0.0, 1000.0, region="lake")
        self.assertIsNone(sight(HERE, 0.0, 30.0, "her", elsewhere, 30.0))

    def test_elevation_does_not_shorten_the_range(self):
        """
        A surface-horizon question is asked across the surface. Counting the metre
        or two between two floating hulls as range would make a thing slightly
        harder to see for being slightly higher, which is backwards.

        """
        flat = sight(HERE, 0.0, 30.0, "her", WorldPosition(0.0, 1000.0, 0.0), 30.0)
        raised = sight(HERE, 0.0, 30.0, "her", WorldPosition(0.0, 1000.0, 5.0), 30.0)
        self.assertAlmostEqual(flat.distance, raised.distance)

    def test_a_taller_ship_is_seen_from_further_off(self):
        far = WorldPosition(0.0, 8.0 * METRES_PER_NAUTICAL_MILE)
        self.assertIsNone(sight(HERE, 0.0, 2.0, "boat", far, 2.0))
        self.assertIsNotNone(sight(HERE, 0.0, 2.0, "ship", far, 40.0))


class TestScan(BaseEvenniaTestCase):
    """Looking at everything."""

    def setUp(self):
        super().setUp()
        self.candidates = [
            ("far", WorldPosition(0.0, 3000.0), 30.0),
            ("near", WorldPosition(0.0, 500.0), 30.0),
            ("middle", WorldPosition(0.0, 1500.0), 30.0),
        ]

    def test_nearest_first(self):
        seen = scan(HERE, 0.0, 30.0, self.candidates)
        self.assertEqual([found.target for found in seen], ["near", "middle", "far"])

    def test_it_drops_what_cannot_be_seen(self):
        beyond = ("beyond", WorldPosition(0.0, 100.0 * METRES_PER_NAUTICAL_MILE), 30.0)
        seen = scan(HERE, 0.0, 30.0, self.candidates + [beyond])
        self.assertNotIn("beyond", [found.target for found in seen])

    def test_an_empty_sea_is_an_empty_result(self):
        self.assertEqual(scan(HERE, 0.0, 30.0, []), ())

    def test_fog_shortens_everything(self):
        seen = scan(HERE, 0.0, 30.0, self.candidates, visibility=1000.0)
        self.assertEqual([found.target for found in seen], ["near"])
