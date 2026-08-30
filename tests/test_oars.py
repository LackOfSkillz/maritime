"""
Tests for human propulsion: oars, paddles, and the arms behind them.

"""

from django.test import override_settings

from evennia.utils import create
from evennia.utils.test_resources import (
    BaseEvenniaCommandTest,
    BaseEvenniaTest,
    BaseEvenniaTestCase,
)

from ..commands import CmdEasyOars, CmdGiveWay, CmdHoldWater, CmdOars, CmdStretchOut
from ..motion import HelmOrders, MotionLimits
from ..oars import (
    EASY_OARS,
    GIVE_WAY,
    HOLD_WATER,
    OAR_PLANS,
    PADDLE,
    PADDLED,
    ROWED,
    STRETCH_OUT,
    OarPlan,
    braking_limits,
    hands_available,
    reach,
    rowed_speed,
)
from ..position import WorldPosition
from ..rooms import ShipRoom
from ..typeclasses import Vessel
from ..vessel import OPEN
from .base import EmptySeaMixin

GIG = OAR_PLANS["gig"]
KAYAK = OAR_PLANS["paddle"]

HERE = WorldPosition(0.0, 0.0)


class TestOarPlan(BaseEvenniaTestCase):
    """What a boat is fitted with."""

    def test_a_boat_with_no_oars_is_not_a_pulling_boat(self):
        with self.assertRaises(ValueError):
            OarPlan(positions=0)

    def test_a_negative_rated_speed_is_refused(self):
        with self.assertRaises(ValueError):
            OarPlan(rated_speed=-1.0)

    def test_a_style_nobody_speaks_is_refused(self):
        with self.assertRaises(ValueError):
            OarPlan(style="poled")

    def test_a_racing_kayak_is_quicker_than_a_ships_cutter(self):
        """Surprises people until they see the two side by side."""
        self.assertGreater(OAR_PLANS["paddle"].rated_speed, OAR_PLANS["gig"].rated_speed)


class TestCrew(BaseEvenniaTestCase):
    """How much of her power is actually being pulled."""

    def test_a_full_crew_is_all_of_it(self):
        self.assertAlmostEqual(hands_available(GIG, 6), 1.0)

    def test_half_a_crew_is_half_of_it(self):
        self.assertAlmostEqual(hands_available(GIG, 3), 0.5)

    def test_nobody_pulls_nothing(self):
        self.assertEqual(hands_available(GIG, 0), 0.0)

    def test_a_seventh_hand_in_a_six_oared_gig_is_a_passenger(self):
        self.assertAlmostEqual(hands_available(GIG, 7), 1.0)

    def test_a_negative_crew_is_no_crew(self):
        self.assertEqual(hands_available(GIG, -3), 0.0)


class TestRowedSpeed(BaseEvenniaTestCase):
    """What the people in her make of it."""

    def test_a_full_crew_at_a_working_stroke(self):
        self.assertAlmostEqual(rowed_speed(GIG, GIVE_WAY, 6), 2.0 * 0.75)

    def test_stretching_out_is_faster(self):
        self.assertGreater(rowed_speed(GIG, STRETCH_OUT, 6), rowed_speed(GIG, GIVE_WAY, 6))

    def test_easy_oars_makes_nothing(self):
        self.assertEqual(rowed_speed(GIG, EASY_OARS, 6), 0.0)

    def test_holding_water_makes_nothing_either(self):
        self.assertEqual(rowed_speed(GIG, HOLD_WATER, 6), 0.0)

    def test_a_short_crew_is_a_slower_boat(self):
        """A six-oared gig pulled by two is a slow boat with four oars stowed."""
        self.assertAlmostEqual(rowed_speed(GIG, GIVE_WAY, 2), rowed_speed(GIG, GIVE_WAY, 6) / 3.0)

    def test_an_order_nobody_gives(self):
        with self.assertRaises(ValueError):
            rowed_speed(GIG, "harder", 6)


class TestHoldingWater(BaseEvenniaTestCase):
    """The one thing a pulling boat can do that a ship under sail cannot."""

    def setUp(self):
        super().setUp()
        self.limits = MotionLimits(max_speed=3.0, acceleration=0.2, turn_rate=8.0)

    def test_holding_water_stops_her_harder(self):
        self.assertGreater(
            braking_limits(self.limits, HOLD_WATER).acceleration, self.limits.acceleration
        )

    def test_easy_oars_does_not(self):
        """She keeps her way and loses it the way any hull does."""
        self.assertEqual(braking_limits(self.limits, EASY_OARS), self.limits)

    def test_pulling_does_not(self):
        self.assertEqual(braking_limits(self.limits, GIVE_WAY), self.limits)

    def test_nothing_else_about_her_changes(self):
        held = braking_limits(self.limits, HOLD_WATER)
        self.assertAlmostEqual(held.max_speed, self.limits.max_speed)
        self.assertAlmostEqual(held.turn_rate, self.limits.turn_rate)


class TestReach(BaseEvenniaTestCase):
    """How long a pull will take."""

    def test_still_water(self):
        self.assertAlmostEqual(reach(GIG, GIVE_WAY, 6, 1500.0), 1000.0)

    def test_with_the_stream(self):
        self.assertLess(reach(GIG, GIVE_WAY, 6, 1500.0, 0.5), 1000.0)

    def test_against_the_stream(self):
        self.assertGreater(reach(GIG, GIVE_WAY, 6, 1500.0, -0.5), 1000.0)

    def test_a_stream_faster_than_she_is(self):
        """A real answer, and one worth having before an hour of trying."""
        self.assertIsNone(reach(GIG, PADDLE, 6, 1500.0, -3.0))

    def test_nobody_pulling_never_gets_there(self):
        self.assertIsNone(reach(GIG, EASY_OARS, 6, 1500.0))


class BoatTestCase(EmptySeaMixin, BaseEvenniaTest):
    """A gig with one hand in her."""

    def setUp(self):
        super().setUp()
        self.boat = create.create_object(Vessel, key="Test Gig")
        self.boat.length = 8.0
        self.boat.beam = 2.0
        self.boat.light_draft = 0.4
        self.boat.motion_limits = MotionLimits(max_speed=3.0, acceleration=0.3, turn_rate=10.0)
        self.boat.maritime_position = HERE
        self.boat.oar_plan = GIG

        self.thwart = create.create_object(ShipRoom, key="Thwarts")
        self.thwart.vessel = self.boat
        self.thwart.exposure = OPEN
        self.char1.location = self.thwart


class TestOaredVessel(BoatTestCase):
    """A boat that is pulled rather than sailed."""

    def test_she_starts_at_easy_oars(self):
        self.assertEqual(self.boat.stroke, EASY_OARS)

    def test_she_is_under_oars(self):
        self.assertTrue(self.boat.under_oars)

    def test_a_boat_with_no_oars_is_not(self):
        self.boat.oar_plan = None
        self.assertFalse(self.boat.under_oars)

    def test_the_crew_is_who_is_actually_in_her(self):
        self.assertEqual(self.boat.rowing_crew, 1)

    def test_a_gangway_does_not_take_an_oar(self):
        """An exit is not a rower, however conveniently placed."""
        create.create_object(
            "evennia.objects.objects.DefaultExit",
            key="gangway",
            location=self.thwart,
            destination=self.room1,
        )
        self.assertEqual(self.boat.rowing_crew, 1)

    def test_a_crew_cannot_exceed_her_oars(self):
        for index in range(10):
            person = create.create_object(
                "evennia.objects.objects.DefaultCharacter", key=f"Hand {index}"
            )
            person.location = self.thwart
        self.assertEqual(self.boat.rowing_crew, GIG.positions)

    def test_one_hand_in_a_six_oared_gig_is_slow(self):
        self.boat.stroke = GIVE_WAY
        self.assertAlmostEqual(self.boat.rowing_speed(), 2.0 * 0.75 / 6.0)

    def test_an_order_nobody_gives_is_refused(self):
        with self.assertRaises(ValueError):
            self.boat.stroke = "faster"

    def test_a_plan_that_is_not_one_is_refused(self):
        with self.assertRaises(TypeError):
            self.boat.oar_plan = "six oars"


class TestOarsAndSailTogether(BoatTestCase):
    """A cutter carries a lug sail and twelve oars."""

    @override_settings(MARITIME_WIND_SPEED=8.0, MARITIME_WIND_BEARING=180.0)
    def test_sail_wins_when_there_is_wind_and_canvas(self):
        """Nobody rows a boat that is sailing."""
        from ..sailing import WORKING

        self.boat.sail_plan = WORKING
        self.assertFalse(self.boat.under_oars)

    @override_settings(MARITIME_WIND_SPEED=0.0)
    def test_but_oars_take_over_in_a_calm(self):
        from ..sailing import WORKING

        self.boat.sail_plan = WORKING
        self.assertTrue(self.boat.under_oars)

    @override_settings(MARITIME_WIND_SPEED=10.0, MARITIME_WIND_BEARING=270.0)
    def test_on_the_tick_she_sails_rather_than_rows(self):
        """
        Not just `under_oars` - what the hull actually does with her step. A
        boat with canvas set and a crew resting must move at what the wind
        makes, not at nothing.

        """
        from ..sailing import WORKING

        self.boat.sail_plan = WORKING
        self.boat.stroke = EASY_OARS
        self.boat.orders = HelmOrders(heading=90.0, speed=0.0)
        self.boat.at_maritime_tick(120.0)
        self.assertGreater(self.boat.speed, 0.0)


class TestPullingHer(BoatTestCase):
    """The tick, with oars driving her."""

    def test_pulling_moves_her(self):
        self.boat.stroke = STRETCH_OUT
        self.boat.orders = HelmOrders(heading=90.0, speed=0.0)
        self.boat.at_maritime_tick(60.0)
        self.assertGreater(self.boat.maritime_position.x, HERE.x)

    def test_easy_oars_lets_her_run_down(self):
        self.boat.stroke = STRETCH_OUT
        self.boat.orders = HelmOrders(heading=90.0, speed=0.0)
        self.boat.at_maritime_tick(60.0)
        under_way = self.boat.speed
        self.boat.stroke = EASY_OARS
        self.boat.at_maritime_tick(5.0)
        self.assertLess(self.boat.speed, under_way)

    def test_holding_water_stops_her_sooner_than_easy_oars(self):
        """
        The whole difference between the two orders, on the water.

        Watched one second after the order rather than three: a gig loses her
        way in a couple of seconds either way, and a window long enough for both
        to reach nothing would show no difference at all.

        """
        for index in range(5):
            hand = create.create_object(
                "evennia.objects.objects.DefaultCharacter", key=f"Oarsman {index}"
            )
            hand.location = self.thwart

        speeds = {}
        for order in (EASY_OARS, HOLD_WATER):
            self.boat.maritime_position = HERE
            self.boat.ndb.speed = 0.0
            self.boat.stroke = STRETCH_OUT
            self.boat.orders = HelmOrders(heading=90.0, speed=0.0)
            self.boat.at_maritime_tick(120.0)
            self.boat.stroke = order
            self.boat.at_maritime_tick(1.0)
            speeds[order] = self.boat.speed
        self.assertGreater(speeds[EASY_OARS], 0.0)
        self.assertLess(speeds[HOLD_WATER], speeds[EASY_OARS])

    def test_the_ordered_speed_is_ignored(self):
        """A pulling boat has no throttle. She goes at what the crew are making."""
        self.boat.stroke = PADDLE
        self.boat.orders = HelmOrders(heading=90.0, speed=99.0)
        self.boat.at_maritime_tick(120.0)
        self.assertLessEqual(self.boat.speed, self.boat.rowing_speed() + 1e-6)


class TestUpAndDownTheRiver(BoatTestCase):
    """
    The demonstration a river exists for.

    Notes:
        Rowing up a stream and down it are the same work and different voyages,
        and only the ground says so. This falls straight out of speed being
        through the water everywhere in the system - nothing here subtracts a
        current from anything.

    """

    def setUp(self):
        super().setUp()
        # A full crew. One hand in a six-oared gig cannot beat a river, which is
        # true and makes for a dull demonstration.
        for index in range(5):
            hand = create.create_object(
                "evennia.objects.objects.DefaultCharacter", key=f"Oarsman {index}"
            )
            hand.location = self.thwart

    @override_settings(MARITIME_CURRENT_SET=90.0, MARITIME_CURRENT_DRIFT=0.6)
    def test_downstream_is_quicker_than_upstream(self):
        self.boat.stroke = GIVE_WAY
        self.boat.heading = 90.0
        downstream = self.boat.pull_for(1000.0)
        self.boat.heading = 270.0
        upstream = self.boat.pull_for(1000.0)
        self.assertLess(downstream, upstream)

    @override_settings(MARITIME_CURRENT_SET=90.0, MARITIME_CURRENT_DRIFT=0.6)
    def test_the_work_is_identical(self):
        """Same stroke, same crew, same speed through the water. Different voyage."""
        self.boat.stroke = GIVE_WAY
        self.boat.heading = 90.0
        with_it = self.boat.rowing_speed()
        self.boat.heading = 270.0
        against_it = self.boat.rowing_speed()
        self.assertAlmostEqual(with_it, against_it)

    @override_settings(MARITIME_CURRENT_SET=90.0, MARITIME_CURRENT_DRIFT=3.0)
    def test_a_stream_she_cannot_beat(self):
        self.boat.stroke = PADDLE
        self.boat.heading = 270.0
        self.assertIsNone(self.boat.pull_for(1000.0))

    def test_slack_water_is_the_same_either_way(self):
        self.boat.stroke = GIVE_WAY
        self.boat.heading = 90.0
        east = self.boat.pull_for(1000.0)
        self.boat.heading = 270.0
        self.assertAlmostEqual(east, self.boat.pull_for(1000.0))


class RowingCommandTestCase(EmptySeaMixin, BaseEvenniaCommandTest):
    """Somebody sitting on a thwart."""

    def setUp(self):
        super().setUp()
        self.boat = create.create_object(Vessel, key="Test Gig")
        self.boat.length, self.boat.beam = 8.0, 2.0
        self.boat.maritime_position = HERE
        self.boat.oar_plan = GIG
        self.thwart = create.create_object(ShipRoom, key="Thwarts")
        self.thwart.vessel = self.boat
        self.thwart.exposure = OPEN
        self.char1.location = self.thwart


class TestRowingCommands(RowingCommandTestCase):
    """The orders a coxswain gives."""

    def test_give_way(self):
        self.call(CmdGiveWay(), "")
        self.assertEqual(self.boat.stroke, GIVE_WAY)

    def test_stretch_out(self):
        self.call(CmdStretchOut(), "")
        self.assertEqual(self.boat.stroke, STRETCH_OUT)

    def test_easy(self):
        self.boat.stroke = GIVE_WAY
        self.call(CmdEasyOars(), "")
        self.assertEqual(self.boat.stroke, EASY_OARS)

    def test_hold_water(self):
        self.call(CmdHoldWater(), "")
        self.assertEqual(self.boat.stroke, HOLD_WATER)

    def test_the_order_is_spoken(self):
        self.call(CmdGiveWay(), "", 'You call out, "Give way together!"')

    def test_a_boat_with_no_oars(self):
        self.boat.oar_plan = None
        self.call(CmdGiveWay(), "", "She has no oars aboard.")

    def test_a_boat_made_fast(self):
        self.boat.db.docked_at = self.room1
        self.call(CmdGiveWay(), "", "She is made fast alongside.")

    def test_oars_reports_her(self):
        self.call(CmdOars(), "", "Test Gig - six oars")

    def test_oars_can_set_the_stroke_too(self):
        self.call(CmdOars(), "stretch out")
        self.assertEqual(self.boat.stroke, STRETCH_OUT)

    def test_oars_refuses_an_order_nobody_gives(self):
        self.call(CmdOars(), "harder", "No such order.")


class TestAKayakIsToldSomethingElse(RowingCommandTestCase):
    """
    One model, two vocabularies.

    Notes:
        A kayaker talks to nobody. Giving them a bowman to answer would be worse
        than silence, so the paddled column of `STROKE_CALLS` has no reply in it
        at all.

    """

    def setUp(self):
        super().setUp()
        self.boat.oar_plan = KAYAK

    def test_nobody_is_ordered_about(self):
        self.call(CmdGiveWay(), "", "You dig the blade in and settle to it.")

    def test_the_report_counts_paddlers(self):
        self.call(CmdOars(), "", "Test Gig - a double blade")

    def test_the_style_is_what_decides_it(self):
        self.assertEqual(KAYAK.style, PADDLED)
        self.assertEqual(GIG.style, ROWED)


class TestBlownAbout(BoatTestCase):
    """
    A boat nobody is driving still goes somewhere.

    Notes:
        The pond demonstration: stop paddling in a breeze and you fetch up on the
        lee shore. Small enough to be invisible over one tick and unmistakable
        over a quarter of an hour, which is exactly right - a hull is mostly
        underwater.

    """

    @override_settings(MARITIME_WIND_SPEED=6.0, MARITIME_WIND_BEARING=0.0)
    def test_a_northerly_pushes_an_idle_boat_south(self):
        self.boat.stroke = EASY_OARS
        self.boat.at_maritime_tick(900.0)
        self.assertLess(self.boat.maritime_position.y, HERE.y)

    @override_settings(MARITIME_WIND_SPEED=6.0, MARITIME_WIND_BEARING=0.0)
    def test_a_hull_that_catches_nothing_stays_put(self):
        self.boat.windage = 0.0
        self.boat.stroke = EASY_OARS
        self.assertFalse(self.boat.at_maritime_tick(900.0))

    def test_a_calm_moves_nothing(self):
        self.boat.stroke = EASY_OARS
        self.assertFalse(self.boat.at_maritime_tick(900.0))

    @override_settings(MARITIME_WIND_SPEED=6.0, MARITIME_WIND_BEARING=0.0)
    def test_a_lighter_hull_is_pushed_further(self):
        before = self.boat.maritime_position
        self.boat.stroke = EASY_OARS
        self.boat.at_maritime_tick(600.0)
        modest = before.horizontal_distance_to(self.boat.maritime_position)

        self.boat.maritime_position = before
        self.boat.windage = 0.2
        self.boat.at_maritime_tick(600.0)
        self.assertGreater(before.horizontal_distance_to(self.boat.maritime_position), modest)

    @override_settings(MARITIME_WIND_SPEED=10.0, MARITIME_WIND_BEARING=270.0)
    def test_a_sailing_hull_is_not_blown_twice(self):
        """
        Under canvas the wind is already driving her and leeway says how much of
        that goes sideways. Tested on the track rather than on a flag: give her
        canvas, sail her twice with wildly different windage, and the two runs
        have to land in the same place.

        """
        from ..sailing import WORKING

        tracks = []
        for windage in (0.0, 0.5):
            # Identical starting state both times, heading included: a hull that
            # begins one run already steadied on her course sails further than one
            # that has to come round first, and that difference is not windage.
            self.boat.maritime_position = HERE
            self.boat.ndb.speed = 0.0
            self.boat.heading = 90.0
            self.boat.sail_plan = WORKING
            self.boat.windage = windage
            self.boat.orders = HelmOrders(heading=90.0, speed=0.0)
            self.boat.at_maritime_tick(300.0)
            tracks.append(self.boat.maritime_position)

        self.assertAlmostEqual(tracks[0].x, tracks[1].x, places=6)
        self.assertAlmostEqual(tracks[0].y, tracks[1].y, places=6)

    def test_windage_above_one_is_refused(self):
        with self.assertRaises(ValueError):
            self.boat.windage = 1.5

    def test_windage_below_zero_is_refused(self):
        with self.assertRaises(ValueError):
            self.boat.windage = -0.1
