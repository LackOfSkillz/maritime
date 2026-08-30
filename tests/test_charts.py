"""
Tests for charts, and for the routes laid between marks.

"""

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest, BaseEvenniaTestCase

from ..bathymetry import ROCK, UNKNOWN, FlatSeaMapProvider, MaritimeMapProvider
from ..charts import (
    CHART_LIFETIME,
    MAX_CHART_ERROR,
    Chart,
    best_chart_for,
    charted_bottom_at,
    charted_depth_at,
    charted_terrain_z_at,
    discrepancy,
)
from ..position import WorldPosition
from ..routes import ARRIVAL_RANGE, NavigationNetwork, Route, Waypoint
from ..typeclasses import Vessel
from .base import EmptySeaMixin

HERE = WorldPosition(500.0, 500.0)
SEA = FlatSeaMapProvider(depth=20.0)


def a_chart(**kwargs):
    """
    Args:
        **kwargs: Overrides.

    Returns:
        chart (Chart): A good chart of a square of sea.

    """
    settings = {
        "key": "Approaches to the Bar",
        "west": 0.0,
        "east": 1000.0,
        "south": 0.0,
        "north": 1000.0,
        "quality": 1.0,
        "surveyed_at": 0.0,
        "seed": 7,
        "maker": "the Harbour Board",
    }
    settings.update(kwargs)
    return Chart(**settings)


class TestCoverage(BaseEvenniaTestCase):
    """A chart is a sheet of paper and stops at its edges."""

    def test_a_place_on_the_sheet(self):
        self.assertTrue(a_chart().covers(HERE))

    def test_a_place_off_the_sheet(self):
        self.assertFalse(a_chart().covers(WorldPosition(5000.0, 500.0)))

    def test_another_region_is_not_covered(self):
        self.assertFalse(a_chart().covers(WorldPosition(500.0, 500.0, region="lake")))

    def test_off_the_chart_has_no_soundings_at_all(self):
        """
        A real and dangerous state, and it reads very differently from having bad
        soundings.

        """
        away = WorldPosition(5000.0, 500.0)
        self.assertIsNone(charted_depth_at(a_chart(), away, 0.0, SEA))


class TestQuality(BaseEvenniaTestCase):
    """How much a chart can be trusted."""

    def test_a_fresh_good_survey_is_trusted(self):
        self.assertAlmostEqual(a_chart().quality_at(0.0), 1.0)

    def test_age_takes_some_of_it_away(self):
        chart = a_chart()
        self.assertLess(chart.quality_at(CHART_LIFETIME), chart.quality_at(0.0))

    def test_but_never_all_of_it(self):
        """
        The coast stays where it was. An ancient chart is a poor guide, not a
        blank sheet.

        """
        self.assertGreater(a_chart().quality_at(CHART_LIFETIME * 10), 0.0)

    def test_a_poor_survey_starts_poor(self):
        self.assertLess(a_chart(quality=0.3).quality_at(0.0), 0.5)


class TestSoundings(BaseEvenniaTestCase):
    """What the paper says, and how wrong it is."""

    def test_a_perfect_chart_matches_the_sea(self):
        self.assertAlmostEqual(discrepancy(a_chart(), HERE, 0.0, SEA), 0.0)

    def test_a_poor_chart_does_not(self):
        self.assertNotAlmostEqual(discrepancy(a_chart(quality=0.2), HERE, 0.0, SEA), 0.0)

    def test_it_is_wrong_in_the_same_place_every_time(self):
        """
        The whole design. Noise regenerated per reading would be unlearnable - a
        navigator could not come to distrust one approach, because it would be
        differently wrong at every glance.

        """
        chart = a_chart(quality=0.2)
        first = charted_terrain_z_at(chart, HERE, 0.0, SEA)
        second = charted_terrain_z_at(chart, HERE, 0.0, SEA)
        self.assertEqual(first, second)

    def test_two_charts_are_wrong_in_different_places(self):
        one = charted_terrain_z_at(a_chart(seed=1, quality=0.2), HERE, 0.0, SEA)
        two = charted_terrain_z_at(a_chart(seed=2, quality=0.2), HERE, 0.0, SEA)
        self.assertNotEqual(one, two)

    def test_the_error_is_bounded(self):
        chart = a_chart(quality=0.0)
        self.assertLessEqual(abs(discrepancy(chart, HERE, 0.0, SEA)), MAX_CHART_ERROR + 1e-6)

    def test_it_varies_over_an_area_not_between_metres(self):
        """A survey is wrong about patches of sea, not about single points."""
        chart = a_chart(quality=0.2)
        close = charted_terrain_z_at(chart, WorldPosition(500.0, 500.0), 0.0, SEA)
        alongside = charted_terrain_z_at(chart, WorldPosition(501.0, 500.0), 0.0, SEA)
        self.assertEqual(close, alongside)

    def test_depth_is_given_at_the_datum(self):
        """
        Not at the present tide. Applying the state of the tide is the
        navigator's job, and doing it for them removes the commonest way a
        careful sailor still goes aground.

        """
        self.assertAlmostEqual(charted_depth_at(a_chart(), HERE, 0.0, SEA), 20.0)

    def test_a_good_chart_knows_the_ground(self):
        class Rocky(MaritimeMapProvider):
            def terrain_z_at(self, position):
                return -20.0

            def bottom_type_at(self, position):
                return ROCK

        self.assertEqual(charted_bottom_at(a_chart(), HERE, 0.0, Rocky()), ROCK)

    def test_a_bad_chart_admits_it_does_not(self):
        self.assertEqual(charted_bottom_at(a_chart(quality=0.1), HERE, 0.0, SEA), UNKNOWN)


class TestBestChart(BaseEvenniaTestCase):
    """Reaching for the good one."""

    def test_the_better_survey_wins(self):
        poor = a_chart(key="poor", quality=0.3)
        good = a_chart(key="good", quality=0.9)
        self.assertIs(best_chart_for([poor, good], HERE), good)

    def test_a_chart_that_does_not_cover_it_is_ignored(self):
        elsewhere = a_chart(key="elsewhere", west=9000.0, east=9999.0, quality=1.0)
        here = a_chart(key="here", quality=0.4)
        self.assertIs(best_chart_for([elsewhere, here], HERE), here)

    def test_no_chart_covering_it_is_no_chart(self):
        self.assertIsNone(best_chart_for([], HERE))


class TestVesselCharts(EmptySeaMixin, BaseEvenniaTest):
    """The charts a ship carries."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Test Sloop")
        self.hull.maritime_position = HERE

    def test_she_starts_with_none(self):
        self.assertEqual(self.hull.charts, ())

    def test_a_chart_can_be_put_aboard(self):
        self.hull.add_chart(a_chart())
        self.assertEqual(len(self.hull.charts), 1)

    def test_two_charts_cannot_share_a_name(self):
        self.hull.add_chart(a_chart())
        with self.assertRaises(ValueError):
            self.hull.add_chart(a_chart())

    def test_she_reads_the_chart_covering_her(self):
        self.hull.add_chart(a_chart())
        self.assertIsNotNone(self.hull.chart_here())

    def test_off_the_chart_she_reads_nothing(self):
        self.hull.add_chart(a_chart())
        self.hull.maritime_position = WorldPosition(9000.0, 9000.0)
        self.assertIsNone(self.hull.chart_here())

    def test_two_ships_can_disagree_about_the_same_water(self):
        """
        Charts are a ship's own property, so a good chart and a bad one in the
        same bay is a real situation rather than a contradiction.

        """
        other = create.create_object(Vessel, key="Marigold")
        other.maritime_position = HERE
        self.hull.add_chart(a_chart(key="good", quality=1.0))
        other.add_chart(a_chart(key="bad", quality=0.1, seed=99))
        self.assertNotEqual(self.hull.charted_depth(), other.charted_depth())


class TestRoutes(BaseEvenniaTestCase):
    """Marks, and the legs between them."""

    def setUp(self):
        super().setUp()
        self.route = Route(
            (
                Waypoint("first", WorldPosition(0.0, 0.0)),
                Waypoint("second", WorldPosition(1000.0, 0.0)),
                Waypoint("third", WorldPosition(2000.0, 0.0)),
            )
        )

    def test_the_distance_is_the_sum_of_the_legs(self):
        self.assertAlmostEqual(self.route.distance, 2000.0)

    def test_she_starts_making_for_the_first_mark(self):
        self.assertEqual(self.route.mark(0).key, "first")

    def test_reaching_a_mark_ticks_the_route_on(self):
        index = self.route.advance(WorldPosition(0.0, 0.0), 0)
        self.assertEqual(self.route.mark(index).key, "second")

    def test_arriving_is_passing_close_not_touching(self):
        """A buoy is a place you pass. A vessel that had to hit one would circle."""
        near = WorldPosition(ARRIVAL_RANGE - 1.0, 0.0)
        self.assertEqual(self.route.advance(near, 0), 1)

    def test_a_mark_passed_close_aboard_does_not_stall_her(self):
        """
        Advances past several at once. A route that stopped on the first would
        have her circling a buoy she had already left astern.

        """
        self.assertEqual(self.route.advance(WorldPosition(0.0, 0.0), 0), 1)

    def test_a_run_route_has_no_next_mark(self):
        self.assertIsNone(self.route.mark(len(self.route)))

    def test_progress_is_carried_rather_than_guessed_from_position(self):
        """
        The flaw this replaced. Deriving progress from "the first mark she is not
        near" looks right until she reaches the end, at which point the first
        mark is the furthest away and she is sent back to the beginning.

        """
        at_the_end = WorldPosition(2000.0, 0.0)
        self.assertEqual(self.route.advance(at_the_end, 2), 3)
        self.assertIsNone(self.route.mark(3))

    def test_being_set_down_beside_the_last_buoy_is_not_completing_the_passage(self):
        beside_the_last = WorldPosition(2000.0, 5000.0)
        self.assertEqual(self.route.mark(self.route.advance(beside_the_last, 0)).key, "first")

    def test_remaining_counts_only_what_is_left(self):
        self.assertAlmostEqual(self.route.remaining(WorldPosition(1000.0, 0.0), 2), 1000.0)

    def test_an_empty_route_is_falsy(self):
        self.assertFalse(Route())


class TestNavigationNetwork(BaseEvenniaTestCase):
    """The marks a game has laid."""

    def setUp(self):
        super().setUp()
        self.network = NavigationNetwork()
        for key, x, y in (
            ("harbour a", 0.0, 0.0),
            ("fairway", 1000.0, 0.0),
            ("north cardinal", 1000.0, 1000.0),
            ("bar beacon", 2000.0, 1000.0),
            ("harbour b", 3000.0, 1000.0),
            ("isolated", 9000.0, 9000.0),
        ):
            self.network.add(Waypoint(key, WorldPosition(x, y)))
        self.network.link("harbour a", "fairway")
        self.network.link("fairway", "north cardinal")
        self.network.link("north cardinal", "bar beacon")
        self.network.link("bar beacon", "harbour b")

    def test_it_plans_a_way_through(self):
        route = self.network.plan("harbour a", "harbour b")
        self.assertEqual(
            [mark.key for mark in route.waypoints],
            ["harbour a", "fairway", "north cardinal", "bar beacon", "harbour b"],
        )

    def test_a_mark_with_no_safe_water_to_it_cannot_be_reached(self):
        """
        Two harbours with no water between them are two harbours you cannot sail
        between, and saying so beats inventing a leg across a headland.

        """
        self.assertFalse(self.network.plan("harbour a", "isolated"))

    def test_an_unknown_mark_gives_no_route(self):
        self.assertFalse(self.network.plan("harbour a", "atlantis"))

    def test_a_route_to_where_you_are_is_one_mark(self):
        self.assertEqual(len(self.network.plan("fairway", "fairway")), 1)

    def test_it_takes_the_shorter_way_when_there_are_two(self):
        self.network.link("fairway", "bar beacon")
        route = self.network.plan("harbour a", "harbour b")
        self.assertNotIn("north cardinal", [mark.key for mark in route.waypoints])

    def test_shorter_means_shorter_and_not_fewer_marks(self):
        """
        Weighted by real distance, not by hops. Mutation testing walked straight
        through the test above, because there the shorter way was also the one
        with fewer marks - so it could not tell the two rules apart. Here a long
        way round is one hop and the short way is two.

        """
        self.network.add(Waypoint("stepping stone", WorldPosition(1500.0, 500.0)))
        self.network.link("fairway", "stepping stone")
        self.network.link("stepping stone", "bar beacon")
        self.network.link("fairway", "harbour b")  # one hop, but a very long one

        route = self.network.plan("fairway", "bar beacon")
        self.assertIn("stepping stone", [mark.key for mark in route.waypoints])

    def test_safe_water_runs_both_ways(self):
        """
        A channel passable one way and not the other is a real thing - a tidal
        gate, a traffic scheme - and it deserves its own representation rather
        than arriving as a half-built link that looks like an oversight.

        """
        out = self.network.plan("harbour a", "harbour b")
        home = self.network.plan("harbour b", "harbour a")
        self.assertTrue(home)
        self.assertEqual(
            [mark.key for mark in home.waypoints],
            list(reversed([mark.key for mark in out.waypoints])),
        )

    def test_marks_cannot_share_a_name(self):
        with self.assertRaises(ValueError):
            self.network.add(Waypoint("fairway", WorldPosition(0.0, 0.0)))

    def test_linking_an_unlaid_mark_is_an_error(self):
        with self.assertRaises(KeyError):
            self.network.link("fairway", "atlantis")

    def test_it_finds_the_nearest_mark(self):
        self.assertEqual(self.network.nearest(WorldPosition(950.0, 50.0)).key, "fairway")

    def test_marks_in_another_region_are_not_near(self):
        self.assertIsNone(self.network.nearest(WorldPosition(0.0, 0.0, region="lake")))
