"""
Tests for the water moving under her.

"""

from django.test import override_settings

from evennia.utils import create
from evennia.utils.test_resources import (
    BaseEvenniaCommandTest,
    BaseEvenniaTest,
    BaseEvenniaTestCase,
)

from ..bathymetry import ROCK, MaritimeMapProvider
from ..commands import CmdCurrent
from ..currents import (
    STILL,
    CurrentVector,
    FlatCurrentProvider,
    carried,
    course_to_steer,
    drift_offset,
    made_good,
)
from ..motion import HelmOrders, MotionLimits
from ..position import EAST, NORTH, SOUTH, WEST, WorldPosition
from ..typeclasses import ShipRoom, Vessel
from ..vessel import OPEN
from .base import EmptySeaMixin

HERE = WorldPosition(0.0, 0.0)


class Southerly(FlatCurrentProvider):
    """A game's own current provider, three knots to the south."""

    def __init__(self):
        super().__init__(CurrentVector(set=SOUTH, drift=3.0))


class LedgeToTheNorth(MaritimeMapProvider):
    """Deep water, and a rock shelf fifty metres to the north of the start."""

    def terrain_z_at(self, position):
        return -1.0 if position.y > 50.0 else -40.0

    def bottom_type_at(self, position):
        return ROCK


class TestCurrentVector(BaseEvenniaTestCase):
    """Set and drift."""

    def test_slack_water_is_not_running(self):
        self.assertFalse(STILL.running)

    def test_a_stream_is_running(self):
        self.assertTrue(CurrentVector(set=90.0, drift=0.5).running)

    def test_the_set_is_normalised(self):
        self.assertAlmostEqual(CurrentVector(set=450.0, drift=1.0).set, 90.0)

    def test_a_negative_drift_is_refused(self):
        """
        A current running backwards is a current with the opposite set. Allowing
        both spellings means two representations of one state, and something
        eventually compares them.

        """
        with self.assertRaises(ValueError):
            CurrentVector(set=90.0, drift=-1.0)

    def test_an_east_setting_current_runs_east(self):
        east, north = CurrentVector(set=EAST, drift=2.0).components()
        self.assertAlmostEqual(east, 2.0)
        self.assertAlmostEqual(north, 0.0, places=6)

    def test_a_north_setting_current_runs_north(self):
        """
        The opposite convention from wind, and the one that matters here: a
        current is named for where it *goes*, a wind for where it comes from.

        """
        east, north = CurrentVector(set=NORTH, drift=2.0).components()
        self.assertAlmostEqual(north, 2.0)
        self.assertAlmostEqual(east, 0.0, places=6)


class TestCarried(BaseEvenniaTestCase):
    """Being taken along by it."""

    def test_slack_water_moves_nothing(self):
        self.assertEqual(carried(HERE, STILL, 3600.0), HERE)

    def test_no_time_moves_nothing(self):
        self.assertEqual(carried(HERE, CurrentVector(set=EAST, drift=1.0), 0.0), HERE)

    def test_a_stream_carries_it(self):
        where = carried(HERE, CurrentVector(set=EAST, drift=2.0), 100.0)
        self.assertAlmostEqual(where.x, 200.0)

    def test_the_offset_is_rate_times_time(self):
        east, north = drift_offset(CurrentVector(set=EAST, drift=1.5), 60.0)
        self.assertAlmostEqual(east, 90.0)
        self.assertAlmostEqual(north, 0.0, places=6)

    def test_anything_floating_is_carried_the_same(self):
        """
        Takes a current and a duration rather than a vessel, because a swimmer, a
        barrel and a wreck are carried at the same rate.

        """
        stream = CurrentVector(set=SOUTH, drift=1.0)
        self.assertEqual(carried(HERE, stream, 10.0), carried(HERE, stream, 10.0))


class TestMadeGood(BaseEvenniaTestCase):
    """Where she is actually going."""

    def test_slack_water_leaves_her_going_where_she_points(self):
        course, speed = made_good(EAST, 5.0, STILL)
        self.assertAlmostEqual(course, EAST)
        self.assertAlmostEqual(speed, 5.0)

    def test_a_fair_current_makes_her_faster(self):
        _course, speed = made_good(EAST, 5.0, CurrentVector(set=EAST, drift=2.0))
        self.assertAlmostEqual(speed, 7.0)

    def test_a_foul_current_makes_her_slower(self):
        _course, speed = made_good(EAST, 5.0, CurrentVector(set=WEST, drift=2.0))
        self.assertAlmostEqual(speed, 3.0)

    def test_a_current_on_the_beam_sets_her_off_course(self):
        """
        The whole reason currents exist: her head is one way and her track is
        another, and only the second one gets her anywhere.

        """
        course, _speed = made_good(EAST, 5.0, CurrentVector(set=NORTH, drift=2.0))
        self.assertLess(course, EAST)
        self.assertGreater(course, NORTH)

    def test_a_current_on_the_beam_also_makes_her_faster(self):
        """Counter-intuitive and correct: the vectors add, they do not trade."""
        _course, speed = made_good(EAST, 5.0, CurrentVector(set=NORTH, drift=2.0))
        self.assertGreater(speed, 5.0)

    def test_stemming_the_tide_exactly_goes_nowhere(self):
        """
        Sailing into a stream at its own rate. A real situation and not an error,
        so her head stays where she is pointing it.

        """
        course, speed = made_good(EAST, 2.0, CurrentVector(set=WEST, drift=2.0))
        self.assertAlmostEqual(speed, 0.0, places=6)
        self.assertAlmostEqual(course, EAST)

    def test_a_current_moves_a_vessel_making_no_way(self):
        _course, speed = made_good(EAST, 0.0, CurrentVector(set=NORTH, drift=1.5))
        self.assertAlmostEqual(speed, 1.5)


class TestCourseToSteer(BaseEvenniaTestCase):
    """The navigator's triangle."""

    def test_slack_water_means_steering_the_track(self):
        self.assertAlmostEqual(course_to_steer(EAST, 5.0, STILL), EAST)

    def test_you_steer_up_into_the_set(self):
        """
        A current setting north pushes her north of her track, so she steers
        south of it to compensate.

        """
        heading = course_to_steer(EAST, 5.0, CurrentVector(set=NORTH, drift=2.0))
        self.assertGreater(heading, EAST)

    def test_steering_it_actually_makes_the_track_good(self):
        """The assertion that makes the rest of this class mean anything."""
        stream = CurrentVector(set=NORTH, drift=2.0)
        heading = course_to_steer(EAST, 5.0, stream)
        course, _speed = made_good(heading, 5.0, stream)
        self.assertAlmostEqual(course, EAST, places=6)

    def test_it_works_for_an_awkward_angle(self):
        stream = CurrentVector(set=200.0, drift=1.2)
        heading = course_to_steer(047.0, 4.0, stream)
        course, _speed = made_good(heading, 4.0, stream)
        self.assertAlmostEqual(course, 47.0, places=6)

    def test_a_current_stronger_than_the_vessel_can_be_unanswerable(self):
        """
        A boat that cannot outrun the stream cannot make good a course across it.
        Returning None says so, rather than a heading that quietly does not work.

        """
        self.assertIsNone(course_to_steer(EAST, 1.0, CurrentVector(set=NORTH, drift=5.0)))

    def test_a_vessel_making_no_way_has_no_answer(self):
        self.assertIsNone(course_to_steer(EAST, 0.0, CurrentVector(set=NORTH, drift=1.0)))

    def test_no_heading_makes_headway_straight_into_a_faster_stream(self):
        self.assertIsNone(course_to_steer(EAST, 2.0, CurrentVector(set=WEST, drift=3.0)))


class DriftingTestCase(EmptySeaMixin, BaseEvenniaTest):
    """A hull with somewhere to be."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Test Sloop")
        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.deck.vessel = self.hull
        self.deck.exposure = OPEN
        self.hull.maritime_position = WorldPosition(0.0, 0.0)
        self.hull.motion_limits = MotionLimits(max_speed=10.0, acceleration=100.0, turn_rate=8.0)
        self.hull.heading = EAST
        self.hull.speed = 5.0
        self.hull.orders = HelmOrders(heading=EAST, speed=5.0)


class TestVesselDrift(DriftingTestCase):
    """The water carrying a ship."""

    def test_slack_water_leaves_her_track_on_her_heading(self):
        with override_settings(MARITIME_DEFAULT_DEPTH=100.0, MARITIME_MAP_PROVIDER=""):
            self.hull.at_maritime_tick(10.0)
        self.assertAlmostEqual(self.hull.maritime_position.y, 0.0, places=6)

    def test_a_beam_current_sets_her_off_her_heading(self):
        with override_settings(
            MARITIME_DEFAULT_DEPTH=100.0,
            MARITIME_MAP_PROVIDER="",
            MARITIME_CURRENT_SET=NORTH,
            MARITIME_CURRENT_DRIFT=2.0,
        ):
            self.hull.at_maritime_tick(10.0)
        self.assertAlmostEqual(self.hull.maritime_position.y, 20.0)

    def test_her_heading_is_unchanged_by_it(self):
        """The water moves her; it does not turn her."""
        with override_settings(
            MARITIME_DEFAULT_DEPTH=100.0,
            MARITIME_MAP_PROVIDER="",
            MARITIME_CURRENT_SET=NORTH,
            MARITIME_CURRENT_DRIFT=2.0,
        ):
            self.hull.at_maritime_tick(10.0)
        self.assertAlmostEqual(self.hull.heading, EAST)

    def test_her_speed_is_speed_through_the_water(self):
        """
        A log line measures the water going past the hull, not the ground going
        past the ship. Keeping speed through-water means the current never has to
        be subtracted back out of anything.

        """
        with override_settings(
            MARITIME_DEFAULT_DEPTH=100.0,
            MARITIME_MAP_PROVIDER="",
            MARITIME_CURRENT_SET=EAST,
            MARITIME_CURRENT_DRIFT=2.0,
        ):
            self.hull.at_maritime_tick(10.0)
        self.assertAlmostEqual(self.hull.speed, 5.0)

    def test_but_she_makes_good_more_than_she_sails(self):
        with override_settings(
            MARITIME_CURRENT_SET=EAST,
            MARITIME_CURRENT_DRIFT=2.0,
        ):
            _course, made = self.hull.made_good()
        self.assertAlmostEqual(made, 7.0)

    def test_an_unlaunched_vessel_makes_good_nothing(self):
        idle = create.create_object(Vessel, key="On The Stocks")
        self.assertIsNone(idle.made_good())

    def test_an_unlaunched_vessel_finds_slack_water(self):
        idle = create.create_object(Vessel, key="On The Stocks")
        self.assertFalse(idle.current_here().running)

    def test_a_game_can_supply_its_own_provider(self):
        path = f"{Southerly.__module__}.Southerly"
        with override_settings(MARITIME_CURRENT_PROVIDER=path):
            self.assertAlmostEqual(self.hull.current_here().drift, 3.0)


class TestPassageTimes(DriftingTestCase):
    """
    First-voyage acceptance: the three cases that could not be written before.

    A passage should take a different time depending on which way the water was
    going. Without that, a current is decoration.

    """

    def passage_east(self, **settings):
        """
        Args:
            **settings: Overrides for the run.

        Returns:
            easting (float): How far east she got in a fixed stretch of time.

        """
        self.hull.maritime_position = WorldPosition(0.0, 0.0)
        base = {"MARITIME_DEFAULT_DEPTH": 1000.0, "MARITIME_MAP_PROVIDER": ""}
        base.update(settings)
        with override_settings(**base):
            for _ in range(10):
                self.hull.at_maritime_tick(60.0)
        return self.hull.maritime_position.x

    def test_a_neutral_passage_is_the_baseline(self):
        self.assertAlmostEqual(self.passage_east(), 3000.0)

    def test_a_favourable_current_gets_her_there_sooner(self):
        neutral = self.passage_east()
        fair = self.passage_east(MARITIME_CURRENT_SET=EAST, MARITIME_CURRENT_DRIFT=1.0)
        self.assertGreater(fair, neutral)

    def test_an_adverse_current_gets_her_there_later(self):
        neutral = self.passage_east()
        foul = self.passage_east(MARITIME_CURRENT_SET=WEST, MARITIME_CURRENT_DRIFT=1.0)
        self.assertLess(foul, neutral)

    def test_the_difference_is_exactly_the_drift(self):
        """
        Six hundred seconds at one metre per second is six hundred metres, either
        way. If this is off, something is scaling the current by the timestep.

        """
        neutral = self.passage_east()
        fair = self.passage_east(MARITIME_CURRENT_SET=EAST, MARITIME_CURRENT_DRIFT=1.0)
        self.assertAlmostEqual(fair - neutral, 600.0)


class TestCurrentSetsHerAground(DriftingTestCase):
    """The reason a safe heading is not a safe passage."""

    def test_the_water_can_put_her_on_the_ground(self):
        """
        She is steering along a safe line and the stream carries her sideways
        onto it. Falls out for nothing, because grounding tests where she ended
        up rather than where she was pointed.

        """
        path = f"{LedgeToTheNorth.__module__}.LedgeToTheNorth"
        self.hull.light_draft = 2.0
        with override_settings(
            MARITIME_MAP_PROVIDER=path,
            MARITIME_CURRENT_SET=NORTH,
            MARITIME_CURRENT_DRIFT=3.0,
        ):
            for _ in range(5):
                self.hull.at_maritime_tick(10.0)
        self.assertTrue(self.hull.aground)


class TestCmdCurrent(EmptySeaMixin, BaseEvenniaCommandTest):
    """Asking what the water is doing."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Test Sloop")
        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.deck.vessel = self.hull
        self.deck.exposure = OPEN
        self.hull.maritime_position = WorldPosition(0.0, 0.0)
        self.hull.heading = EAST
        self.hull.speed = 5.0
        self.char1.location = self.deck

    def test_slack_water_says_so(self):
        output = self.call(CmdCurrent(), "")
        self.assertIn("Slack water", output)

    def test_a_stream_reports_set_and_drift(self):
        with override_settings(MARITIME_CURRENT_SET=90.0, MARITIME_CURRENT_DRIFT=1.0):
            output = self.call(CmdCurrent(), "")
        self.assertIn("sets 0-9-0", output)
        self.assertIn("drift", output)

    def test_it_reports_the_track_when_it_differs(self):
        with override_settings(MARITIME_CURRENT_SET=NORTH, MARITIME_CURRENT_DRIFT=2.0):
            output = self.call(CmdCurrent(), "")
        self.assertIn("makes good", output)

    def test_it_says_nothing_about_a_track_that_matches_the_heading(self):
        """A current dead astern or dead ahead changes the speed, not the course."""
        with override_settings(MARITIME_CURRENT_SET=EAST, MARITIME_CURRENT_DRIFT=2.0):
            output = self.call(CmdCurrent(), "")
        self.assertNotIn("makes good", output)
