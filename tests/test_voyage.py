"""
Tests for the sailing master: the smallest automation that gets her there.

"""

from django.test import override_settings
from evennia.utils import create
from evennia.utils.test_resources import (
    BaseEvenniaCommandTest,
    BaseEvenniaTest,
    BaseEvenniaTestCase,
)

from ..clock import MaritimeTimeProvider
from ..commands import CmdBelay, CmdFollow
from ..crew import ABLE
from ..currents import CurrentVector, made_good
from ..motion import HelmOrders, MotionLimits
from ..position import EAST, NORTH, WorldPosition
from ..rooms import ShipRoom
from ..routes import Route, Waypoint
from ..sailing import FULL, FURLED, REEFED, STORM, WindVector
from ..typeclasses import Vessel
from ..vessel import OPEN
from ..voyage import (
    MINIMUM_APPROACH,
    approach_speed,
    course_for_mark,
    sail_for_wind,
)
from .base import EmptySeaMixin

HERE = WorldPosition(0.0, 0.0)


class TestCourseForMark(BaseEvenniaTestCase):
    """Steering to allow for the set."""

    def test_slack_water_means_steering_straight_at_it(self):
        mark = WorldPosition(1000.0, 0.0)
        self.assertAlmostEqual(course_for_mark(HERE, mark, 5.0, CurrentVector()), EAST)

    def test_a_cross_current_makes_her_crab_up_into_it(self):
        """
        The whole point of knowing the set. Steering straight at a mark in a
        cross-current walks her downstream of it and she arrives somewhere else.

        """
        mark = WorldPosition(1000.0, 0.0)
        stream = CurrentVector(set=NORTH, drift=2.0)
        self.assertGreater(course_for_mark(HERE, mark, 5.0, stream), EAST)

    def test_and_the_course_it_picks_actually_makes_the_track_good(self):
        mark = WorldPosition(1000.0, 0.0)
        stream = CurrentVector(set=NORTH, drift=2.0)
        heading = course_for_mark(HERE, mark, 5.0, stream)
        course, _speed = made_good(heading, 5.0, stream)
        self.assertAlmostEqual(course, EAST, places=6)

    def test_a_stream_she_cannot_beat_still_gets_her_best(self):
        """
        No heading makes the track good, so she steers straight at the mark and
        does what she can. Honest about being insufficient, rather than inventing
        a course that does not work.

        """
        mark = WorldPosition(1000.0, 0.0)
        torrent = CurrentVector(set=NORTH, drift=20.0)
        self.assertAlmostEqual(course_for_mark(HERE, mark, 1.0, torrent), EAST)


class TestSailForWind(BaseEvenniaTestCase):
    """Carrying what the wind allows."""

    def test_a_light_air_carries_everything(self):
        self.assertIs(sail_for_wind(WindVector(speed=3.0)), FULL)

    def test_a_fresh_breeze_shortens_her(self):
        self.assertIs(sail_for_wind(WindVector(speed=15.0)), REEFED)

    def test_a_gale_puts_her_under_storm_canvas(self):
        self.assertIs(sail_for_wind(WindVector(speed=25.0)), STORM)

    def test_a_hurricane_takes_it_all_off_her(self):
        """
        The correct answer, not a failure to find one. Nothing aboard is rated
        for it.

        """
        self.assertIs(sail_for_wind(WindVector(speed=60.0)), FURLED)

    def test_more_wind_never_means_more_canvas(self):
        areas = [sail_for_wind(WindVector(speed=speed)).area for speed in range(0, 60)]
        self.assertEqual(areas, sorted(areas, reverse=True))


class TestApproachSpeed(BaseEvenniaTestCase):
    """Taking the way off her at the end."""

    def test_a_mark_far_off_gets_full_speed(self):
        self.assertAlmostEqual(approach_speed(9000.0, 8.0, final=True), 8.0)

    def test_she_slows_coming_up_to_it(self):
        self.assertLess(approach_speed(200.0, 8.0, final=True), 8.0)

    def test_the_closer_she_is_the_slower_she_goes(self):
        near = approach_speed(100.0, 8.0, final=True)
        further = approach_speed(600.0, 8.0, final=True)
        self.assertLess(near, further)

    def test_she_never_loses_steerage(self):
        """
        A vessel below steerage way stops answering her helm, and a ship that
        cannot steer on her final approach is a worse problem than one arriving
        briskly.

        """
        self.assertGreaterEqual(approach_speed(0.0, 8.0, final=True), 8.0 * MINIMUM_APPROACH)

    def test_marks_along_the_way_are_passed_at_speed(self):
        """
        A buoy is rounded at whatever she is doing. Slowing for each would turn a
        passage into a series of stops.

        """
        self.assertAlmostEqual(approach_speed(50.0, 8.0, final=False), 8.0)

    def test_a_vessel_making_nothing_is_asked_for_nothing(self):
        self.assertAlmostEqual(approach_speed(100.0, 0.0, final=True), 0.0)


class ConTestCase(EmptySeaMixin, BaseEvenniaTest):
    """A hull with a course plotted and somewhere to be."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Test Sloop")
        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.deck.vessel = self.hull
        self.deck.exposure = OPEN
        self.hull.maritime_position = HERE
        self.hull.motion_limits = MotionLimits(max_speed=8.0, acceleration=100.0, turn_rate=8.0)
        self.hull.heading = NORTH
        self.hull.orders = HelmOrders(heading=NORTH, speed=0.0)
        self.hull.route = Route(
            (
                Waypoint("fairway", WorldPosition(4000.0, 0.0)),
                Waypoint("the bar", WorldPosition(8000.0, 0.0)),
            )
        )

    def sail(self, ticks=1, seconds=60.0, **settings):
        """
        Args:
            ticks (int): How many ticks to run.
            seconds (float): Game seconds per tick.
            **settings: Overrides for the run.

        """
        base = {"MARITIME_DEFAULT_DEPTH": 1000.0, "MARITIME_MAP_PROVIDER": ""}
        base.update(settings)
        with override_settings(**base):
            for _ in range(ticks):
                self.hull.at_maritime_tick(seconds)


class WatchClock(MaritimeTimeProvider):
    """
    A clock the test drives, since `time_provider` builds a fresh provider per call.

    Handling deadlines are kept on the simulation clock, the same one the gun deck
    uses for reload times. A test that ticks a hull twelve times in a millisecond has
    to move that clock itself, or no ordered sail would ever be set.

    """

    seconds = 0.0

    def now(self):
        """
        Returns:
            now (float): Whatever the test has wound it to.

        """
        return WatchClock.seconds


class TestTheWatchIsNoFasterThanTheHands(ConTestCase):
    """
    The mate goes through the same seam a captain's order goes through.

    A watch that could re-rig the ship instantly while the captain waited four
    minutes for the same change would make ordering sail yourself strictly worse
    than saying nothing, which is the wrong lesson to teach about being in command.

    """

    def setUp(self):
        super().setUp()
        self.hull.length = 46.0
        self.hull.man(200, ABLE)
        self.hull.under_con = True
        self.hull.sail_plan = FULL
        WatchClock.seconds = 0.0

    def sail(self, ticks=1, seconds=60.0, **settings):
        """Tick, winding the simulation clock on by the same amount."""
        settings.setdefault("MARITIME_TIME_PROVIDER", f"{WatchClock.__module__}.WatchClock")
        for _ in range(ticks):
            super().sail(ticks=1, seconds=seconds, **settings)
            WatchClock.seconds += seconds

    def test_he_does_not_get_it_instantly(self):
        self.sail(MARITIME_WIND_SPEED=15.0)
        self.assertIs(self.hull.sail_plan, FULL)
        self.assertTrue(self.hull.working_aloft)

    def test_but_he_does_get_it(self):
        self.sail(ticks=12, seconds=60.0, MARITIME_WIND_SPEED=15.0)
        self.assertIs(self.hull.sail_plan, REEFED)

    def test_he_does_not_start_over_every_tick(self):
        """
        Re-ordering while the hands are still aloft would push the finish out by a
        changed-mind penalty on every tick, and the sail would never be set at all.

        """
        self.sail(MARITIME_WIND_SPEED=15.0)
        due = self.hull.handling.finish_at
        self.sail(ticks=3, seconds=1.0, MARITIME_WIND_SPEED=15.0)
        self.assertAlmostEqual(self.hull.handling.finish_at, due)


class TestTheSailingMaster(ConTestCase):
    """What he does with the con."""

    def test_he_does_nothing_until_he_has_it(self):
        self.sail()
        self.assertAlmostEqual(self.hull.orders.heading, NORTH)

    def test_given_it_he_steers_for_the_mark(self):
        self.hull.under_con = True
        self.sail(MARITIME_WIND_SPEED=8.0, MARITIME_WIND_BEARING=NORTH)
        self.assertAlmostEqual(self.hull.orders.heading, EAST, places=3)

    def test_he_sets_what_the_wind_allows(self):
        self.hull.under_con = True
        self.sail(MARITIME_WIND_SPEED=15.0)
        self.assertIs(self.hull.sail_plan, REEFED)

    def test_he_shortens_when_it_freshens(self):
        self.hull.under_con = True
        self.sail(MARITIME_WIND_SPEED=5.0)
        self.assertIs(self.hull.sail_plan, FULL)
        self.sail(MARITIME_WIND_SPEED=25.0)
        self.assertIs(self.hull.sail_plan, STORM)

    def test_he_allows_for_the_set(self):
        self.hull.under_con = True
        self.hull.speed = 5.0
        self.sail(
            MARITIME_WIND_SPEED=8.0,
            MARITIME_CURRENT_SET=NORTH,
            MARITIME_CURRENT_DRIFT=1.0,
        )
        self.assertGreater(self.hull.orders.heading, EAST)

    def test_a_ship_with_no_way_on_cannot_allow_for_it_yet(self):
        """
        Crabbing into a stream is done with the water flowing past the hull, so a
        vessel lying stopped has nothing to crab with. He steers straight at the
        mark until she has way, and corrects once she does - which is what a real
        hand does and is why this is not a bug.

        """
        self.hull.under_con = True
        self.hull.speed = 0.0
        self.sail(
            MARITIME_WIND_SPEED=8.0,
            MARITIME_CURRENT_SET=NORTH,
            MARITIME_CURRENT_DRIFT=1.0,
        )
        self.assertAlmostEqual(self.hull.orders.heading, EAST)

    def test_he_hands_the_con_back_when_the_passage_is_made(self):
        """
        Rather than holding it and doing nothing. A mate who has finished should
        say so, or nobody knows whether she is being steered.

        """
        self.hull.under_con = True
        self.hull.route_index = 2
        self.sail()
        self.assertFalse(self.hull.under_con)

    def test_he_actually_gets_her_there(self):
        """The point of the whole phase."""
        self.hull.under_con = True
        self.sail(ticks=40, seconds=60.0, MARITIME_WIND_SPEED=8.0)
        self.assertGreater(self.hull.maritime_position.x, 4000.0)

    def test_he_takes_the_way_off_her_at_the_last_mark(self):
        self.hull.maritime_position = WorldPosition(7900.0, 0.0)
        self.hull.route_index = 1
        self.hull.under_con = True
        self.sail(MARITIME_WIND_SPEED=8.0)
        self.assertLess(self.hull.orders.speed, self.hull.motion_limits.max_speed)

    def test_but_not_at_the_ones_along_the_way(self):
        self.hull.maritime_position = WorldPosition(3900.0, 0.0)
        self.hull.under_con = True
        self.sail(MARITIME_WIND_SPEED=8.0)
        self.assertAlmostEqual(self.hull.orders.speed, self.hull.motion_limits.max_speed)

    def test_he_cannot_work_a_ship_that_is_held(self):
        """
        Made fast or aground, he is as stuck as anybody. He has no private channel to the
        hull.

        Notes:
            This said "or anchored" until he was given the job of weighing for a passage
            himself - which is right, and is a genuine narrowing of the rule rather than an
            exception to it. An anchor is a thing he can pick up; a berth and a sandbank are
            not. The two cases below are the ones where he really is as stuck as anybody,
            and `test_he_weighs_for_a_passage` is the one where he is not.

        """
        # Holed on rock, which no tide lifts. Setting `aground` alone is not enough any
        # more and should not be: these tests sail on a thousand metres of water, so a hull
        # merely flagged aground floats off on the first tick - correctly, and which is the
        # whole point of `float_off`.
        self.hull.aground = True
        self.hull.db.grounding = {"severity": "holed", "bottom": "rock", "clearance": -2.0}
        self.hull.under_con = True
        self.sail(MARITIME_WIND_SPEED=8.0)
        self.assertTrue(self.hull.aground)
        self.assertAlmostEqual(self.hull.orders.heading, NORTH)

    def test_nor_one_that_is_made_fast(self):
        self.hull.db.docked_at = self.hull  # anything not None; he is not going anywhere
        self.hull.under_con = True
        self.sail(MARITIME_WIND_SPEED=8.0)
        self.assertAlmostEqual(self.hull.orders.heading, NORTH)

    def test_he_leaves_an_anchored_ship_alone_with_no_passage_ordered(self):
        # An anchor is what a ship lies to when nobody has told her to go anywhere, and
        # weighing it uninvited would be a mate deciding to sail.
        self.hull.route = None
        self.hull.anchored = True
        self.hull.under_con = True
        self.sail(MARITIME_WIND_SPEED=8.0)
        self.assertTrue(self.hull.anchored)
        self.assertAlmostEqual(self.hull.orders.heading, NORTH)

    def test_he_weighs_for_a_passage(self):
        """
        Given the con and somewhere to go, he brings the anchor home himself.

        Notes:
            Ordering a passage is one decision, and a mate who accepted it and then sat at
            anchor waiting to be told to weigh would have to be told twice - which is the
            thing `make for` exists to avoid.

        """
        self.hull.anchored = True
        self.hull.under_con = True
        self.sail(MARITIME_WIND_SPEED=8.0)
        self.assertFalse(self.hull.anchored)


class TestTheConCommands(EmptySeaMixin, BaseEvenniaCommandTest):
    """Handing him the con and taking it back."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Test Sloop")
        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.deck.vessel = self.hull
        self.deck.exposure = OPEN
        self.hull.maritime_position = HERE
        self.char1.location = self.deck

    def test_he_refuses_without_a_course(self):
        self.assertIn("no course plotted", self.call(CmdFollow(), ""))

    def test_with_one_he_takes_her(self):
        self.hull.route = Route((Waypoint("fairway", WorldPosition(4000.0, 0.0)),))
        self.assertIn("I have her", self.call(CmdFollow(), ""))
        self.assertTrue(self.hull.under_con)

    def test_he_refuses_a_course_already_run(self):
        self.hull.route = Route((Waypoint("here", HERE),))
        self.assertIn("course is run", self.call(CmdFollow(), ""))

    def test_the_con_can_be_taken_back(self):
        self.hull.route = Route((Waypoint("fairway", WorldPosition(4000.0, 0.0)),))
        self.call(CmdFollow(), "")
        self.assertIn("You have her", self.call(CmdBelay(), ""))
        self.assertFalse(self.hull.under_con)

    def test_taking_back_a_con_you_already_have(self):
        self.assertIn("have the con already", self.call(CmdBelay(), ""))
