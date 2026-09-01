"""
Tests for rendering positions the way a navigator would write them.

"""

from django.test import override_settings
from evennia.utils.test_resources import BaseEvenniaTestCase

from ..formatting import (
    METRES_PER_MINUTE,
    METRIC,
    NAUTICAL,
    RAW,
    format_position,
    format_range,
    latitude_of,
    longitude_of,
    pick_scale,
)
from ..position import WorldPosition
from ..resolver import NoWorldPosition


class TestScale(BaseEvenniaTestCase):
    """The conversion rests on one definition."""

    def test_a_nautical_mile_is_one_minute(self):
        """
        This is a definition, not an approximation, which is why the whole
        conversion needs no fudge factor.

        """
        self.assertEqual(METRES_PER_MINUTE, 1852.0)

    def test_one_mile_north_is_one_minute_north(self):
        self.assertEqual(latitude_of(WorldPosition(0.0, 1852.0)), "0°01.0'N")

    def test_sixty_miles_north_is_one_degree(self):
        self.assertEqual(latitude_of(WorldPosition(0.0, 1852.0 * 60)), "1°00.0'N")


class TestLatitude(BaseEvenniaTestCase):
    """Northing becomes latitude."""

    def test_origin_is_zero(self):
        self.assertEqual(latitude_of(WorldPosition(0.0, 0.0)), "0°00.0'N")

    def test_north_is_north(self):
        self.assertIn("N", latitude_of(WorldPosition(0.0, 5000.0)))

    def test_south_is_south(self):
        self.assertIn("S", latitude_of(WorldPosition(0.0, -5000.0)))

    def test_hemisphere_not_a_minus_sign(self):
        """A navigator writes 12°S, never -12°."""
        self.assertNotIn("-", latitude_of(WorldPosition(0.0, -5000.0)))

    def test_degrees_and_decimal_minutes(self):
        """
        What charts and sights are actually worked in, and it avoids implying a
        precision dead reckoning does not have.

        """
        self.assertRegex(latitude_of(WorldPosition(0.0, 100000.0)), r"^\d+°\d\d\.\d'[NS]$")


class TestLongitude(BaseEvenniaTestCase):
    """Easting becomes longitude."""

    def test_east_is_east(self):
        self.assertIn("E", longitude_of(WorldPosition(5000.0, 0.0)))

    def test_west_is_west(self):
        self.assertIn("W", longitude_of(WorldPosition(-5000.0, 0.0)))

    def test_uses_the_same_scale_as_latitude(self):
        """
        This world is a plane. Narrowing longitude towards the poles would make
        the displayed position disagree with the distance actually sailed, which
        is a worse lie than the simplification it would fix.

        """
        east = longitude_of(WorldPosition(1852.0, 0.0))
        north = latitude_of(WorldPosition(0.0, 1852.0))
        self.assertEqual(east.rstrip("E"), north.rstrip("N"))


class TestOriginOffset(BaseEvenniaTestCase):
    """A game can put its world somewhere on the globe."""

    @override_settings(MARITIME_ORIGIN_NORTHING=1852.0 * 60 * 48)
    def test_northing_origin_shifts_latitude(self):
        self.assertEqual(latitude_of(WorldPosition(0.0, 0.0)), "48°00.0'N")

    @override_settings(MARITIME_ORIGIN_EASTING=-1852.0 * 60 * 4)
    def test_easting_origin_shifts_longitude(self):
        self.assertEqual(longitude_of(WorldPosition(0.0, 0.0)), "4°00.0'W")


class TestFormatPosition(BaseEvenniaTestCase):
    """Choosing a presentation."""

    def setUp(self):
        super().setUp()
        self.somewhere = WorldPosition(1852.0 * 30, 1852.0 * 90)

    def test_nautical_shows_a_bearing_pair(self):
        text = format_position(self.somewhere, style=NAUTICAL)
        self.assertIn("N", text)
        self.assertIn("E", text)

    def test_nautical_hides_coordinates(self):
        """A player should not be reading metres off an instrument."""
        self.assertNotIn("166680", format_position(self.somewhere, style=NAUTICAL))

    def test_raw_shows_coordinates(self):
        self.assertIn("166680", format_position(self.somewhere, style=RAW))

    def test_defaults_to_nautical(self):
        self.assertEqual(format_position(self.somewhere), format_position(self.somewhere, NAUTICAL))

    @override_settings(MARITIME_POSITION_STYLE=RAW)
    def test_a_game_may_choose_raw(self):
        self.assertIn("166680", format_position(self.somewhere))

    def test_unknown_style_is_refused(self):
        """
        A typo would otherwise fall through to a default and quietly show staff
        coordinates to players.

        """
        with self.assertRaises(ValueError):
            format_position(self.somewhere, style="approximately")

    def test_no_position_says_so(self):
        self.assertEqual(format_position(NoWorldPosition), "not at sea")

    def test_none_says_so(self):
        self.assertEqual(format_position(None), "not at sea")

    def test_depth_is_reported_when_submerged(self):
        submerged = WorldPosition(0.0, 0.0, -40.0)
        self.assertIn("40.0 m below", format_position(submerged))

    def test_surface_positions_mention_no_depth(self):
        self.assertNotIn("below", format_position(WorldPosition(0.0, 0.0, 0.0)))


class TestOneUnitPerReport(BaseEvenniaTestCase):
    """
    A range column exists to be compared at a glance.

    Seen live, and the reason this exists: "The horizon, all round - 2.9 miles off"
    followed by contacts at "2.7 miles" and "1.5 leagues". Three ranges, two units,
    and no way to tell which was furthest without doing arithmetic.

    """

    def test_a_report_that_reaches_leagues_speaks_in_leagues(self):
        scale = pick_scale([5400.0, 5000.0, 8300.0])
        said = [format_range(distance, scale=scale) for distance in (5400.0, 5000.0, 8300.0)]
        self.assertTrue(all("leagues" in line for line in said), said)

    def test_a_report_that_does_not_stays_in_miles(self):
        """Not everything becomes leagues - only a report that actually reaches them."""
        scale = pick_scale([5400.0, 3000.0])
        said = [format_range(distance, scale=scale) for distance in (5400.0, 3000.0)]
        self.assertTrue(all("miles" in line for line in said), said)

    def test_miles_and_leagues_never_share_a_list(self):
        """The whole point. This is the pairing that was wrong."""
        ranges = [5400.0, 5000.0, 8300.0, 900.0]
        scale = pick_scale(ranges)
        said = [format_range(distance, scale=scale) for distance in ranges]
        self.assertFalse(
            any("miles" in line for line in said) and any("leagues" in line for line in said),
            said,
        )

    def test_cables_survive_alongside_a_bigger_unit(self):
        """
        A cable beside a league is two scales of measurement, the way feet sit
        beside miles - it reads correctly and nobody converts anything. Miles beside
        leagues is one scale said two ways, which is the confusing one.

        """
        scale = pick_scale([8300.0, 900.0])
        self.assertIn("cables", format_range(900.0, scale=scale))
        self.assertIn("leagues", format_range(8300.0, scale=scale))

    def test_the_scale_comes_from_the_furthest_range(self):
        """
        Chosen from the largest, so a report reaching out to leagues speaks in
        leagues throughout rather than changing vocabulary partway down the column.

        """
        self.assertEqual(pick_scale([900.0, 8300.0]), pick_scale([8300.0, 900.0]))

    def test_an_empty_report_still_chooses_something(self):
        self.assertIsNotNone(pick_scale([]))

    def test_a_single_range_still_picks_its_own(self):
        """Without a scale each range decides for itself, which is right for one figure."""
        self.assertIn("leagues", format_range(8300.0))
        self.assertIn("miles", format_range(3000.0))

    def test_a_scheme_with_nothing_to_choose_says_so(self):
        """
        Metric has one big unit and raw has none at all, so there is no pair to be
        caught mixing. Saying None is more honest than handing back a scale the
        caller would only ignore.

        """
        self.assertIsNone(pick_scale([8300.0, 900.0], units=METRIC))
        self.assertIsNone(pick_scale([8300.0, 900.0], units=RAW))

    def test_metric_is_left_alone(self):
        scale = pick_scale([8300.0, 900.0], units=METRIC)
        self.assertIn("km", format_range(8300.0, units=METRIC, scale=scale))
        self.assertIn("m", format_range(900.0, units=METRIC, scale=scale))
