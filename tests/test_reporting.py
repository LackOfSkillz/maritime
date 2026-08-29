"""
Tests for what a ship's company is told while she is under way.

"""

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest

from .base import EmptySeaMixin

from django.test import override_settings

from ..messaging import (
    COMING_ROUND,
    VesselNarrator,
    compass_point,
    spell_bearing,
)
from ..motion import HelmOrders, MotionLimits
from ..position import WorldPosition
from ..typeclasses import ShipRoom, Vessel
from ..vessel import BELOW_WATERLINE, OPEN


class TestSpellBearing(EmptySeaMixin, BaseEvenniaTest):
    """Courses are spoken digit by digit."""

    def test_pads_to_three_figures(self):
        self.assertEqual(spell_bearing(90.0), "0-9-0")

    def test_separates_every_digit(self):
        self.assertEqual(spell_bearing(182.0), "1-8-2")

    def test_north_is_three_zeroes(self):
        self.assertEqual(spell_bearing(0.0), "0-0-0")

    def test_wraps_a_full_circle(self):
        self.assertEqual(spell_bearing(360.0), "0-0-0")

    def test_rounds_to_whole_degrees(self):
        self.assertEqual(spell_bearing(89.6), "0-9-0")

    def test_never_reads_as_a_single_number(self):
        """
        'Ninety' and 'one nine zero' are easy to confuse across a windy deck.
        'Zero-nine-zero' is not, which is the whole reason for the convention.

        """
        self.assertNotEqual(spell_bearing(90.0), "90")


class TestCompassPoint(EmptySeaMixin, BaseEvenniaTest):
    """Describing a heading the way a person would say it."""

    def test_cardinals(self):
        self.assertEqual(compass_point(0.0), "north")
        self.assertEqual(compass_point(90.0), "east")
        self.assertEqual(compass_point(180.0), "south")
        self.assertEqual(compass_point(270.0), "west")

    def test_intercardinals(self):
        self.assertEqual(compass_point(45.0), "northeast")
        self.assertEqual(compass_point(225.0), "southwest")

    def test_sixteen_points(self):
        self.assertEqual(compass_point(22.5), "north-northeast")

    def test_wraps_near_north(self):
        self.assertEqual(compass_point(359.0), "north")

    def test_handles_out_of_range(self):
        self.assertEqual(compass_point(450.0), "east")


class ReportingTestCase(EmptySeaMixin, BaseEvenniaTest):
    """A sloop with an open deck and a hold below."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Test Sloop")
        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.hold = create.create_object(ShipRoom, key="Cargo Hold")
        for room, level, exposure in ((self.deck, 0, OPEN), (self.hold, -1, BELOW_WATERLINE)):
            room.db.vessel = self.hull
            room.deck_level = level
            room.exposure = exposure
        self.hull.maritime_position = WorldPosition(0.0, 0.0)
        self.hull.motion_limits = MotionLimits(max_speed=10.0, acceleration=1.0, turn_rate=6.0)
        self.heard = []
        self.deck.msg_contents = lambda text, **kwargs: self.heard.append(("deck", text))
        self.hold.msg_contents = lambda text, **kwargs: self.heard.append(("hold", text))

    def said_on(self, where):
        """Everything heard in one part of the ship."""
        return [text for place, text in self.heard if place == where]


class TestTransitionsNotConditions(ReportingTestCase):
    """Ambient messaging reports changes, never states."""

    def test_a_turn_is_announced_once(self):
        """
        Reporting 'she is turning' every tick is how ambient messaging becomes
        noise players learn to scroll past.

        """
        self.hull.speed = 10.0
        self.hull.orders = HelmOrders(heading=90.0, speed=10.0)
        for _ in range(10):
            self.hull.at_maritime_tick(1.0)
        leaning = [text for text in self.said_on("deck") if "comes round" in text]
        self.assertEqual(len(leaning), 1)

    def test_steady_is_reported_when_she_arrives(self):
        self.hull.speed = 10.0
        self.hull.orders = HelmOrders(heading=90.0, speed=10.0)
        for _ in range(40):
            self.hull.at_maritime_tick(1.0)
        self.assertTrue(any("steady on 0-9-0" in text for text in self.said_on("deck")))

    def test_holding_a_course_says_nothing(self):
        """A ship running steadily has nothing to announce."""
        self.hull.speed = 10.0
        self.hull.heading = 90.0
        self.hull.orders = HelmOrders(heading=90.0, speed=10.0)
        self.heard.clear()
        for _ in range(20):
            self.hull.at_maritime_tick(1.0)
        self.assertEqual(self.said_on("deck"), [])

    def test_reaching_ordered_speed_is_announced_once(self):
        self.hull.orders = HelmOrders(heading=0.0, speed=5.0)
        for _ in range(30):
            self.hull.at_maritime_tick(1.0)
        stride = [text for text in self.said_on("deck") if "stride" in text]
        self.assertEqual(len(stride), 1)

    def test_a_second_turn_is_announced_again(self):
        """Once-only must not mean once-ever."""
        self.hull.speed = 10.0
        self.hull.orders = HelmOrders(heading=90.0, speed=10.0)
        for _ in range(40):
            self.hull.at_maritime_tick(1.0)
        self.hull.orders = HelmOrders(heading=180.0, speed=10.0)
        self.heard.clear()
        for _ in range(10):
            self.hull.at_maritime_tick(1.0)
        self.assertTrue(any("comes round" in text for text in self.said_on("deck")))


class TestExposureDecidesWhatYouHear(ReportingTestCase):
    """Where you stand changes what reaches you."""

    def test_both_parts_of_the_ship_are_told(self):
        self.hull.speed = 10.0
        self.hull.orders = HelmOrders(heading=90.0, speed=10.0)
        self.hull.at_maritime_tick(1.0)
        self.assertTrue(self.said_on("deck"))
        self.assertTrue(self.said_on("hold"))

    def test_they_are_told_different_things(self):
        """
        On deck you watch the sea go by; below you feel her heel and hear water
        on the planking but see none of it.

        """
        self.hull.speed = 10.0
        self.hull.orders = HelmOrders(heading=90.0, speed=10.0)
        self.hull.at_maritime_tick(1.0)
        self.assertNotEqual(self.said_on("deck")[0], self.said_on("hold")[0])

    def test_the_deck_sees_the_sea(self):
        self.hull.speed = 10.0
        self.hull.orders = HelmOrders(heading=90.0, speed=10.0)
        for _ in range(40):
            self.hull.at_maritime_tick(1.0)
        self.assertTrue(any("sea sliding past" in text for text in self.said_on("deck")))

    def test_the_hold_does_not(self):
        self.hull.speed = 10.0
        self.hull.orders = HelmOrders(heading=90.0, speed=10.0)
        for _ in range(40):
            self.hull.at_maritime_tick(1.0)
        self.assertFalse(any("sea sliding past" in text for text in self.said_on("hold")))

    def test_the_hold_feels_the_heel(self):
        self.hull.speed = 10.0
        self.hull.orders = HelmOrders(heading=90.0, speed=10.0)
        self.hull.at_maritime_tick(1.0)
        self.assertTrue(any("heel" in text for text in self.said_on("hold")))


class TestTurnDirection(ReportingTestCase):
    """Which way she leans."""

    def test_starboard_turn_says_starboard(self):
        self.hull.speed = 10.0
        self.hull.orders = HelmOrders(heading=90.0, speed=10.0)
        self.hull.at_maritime_tick(1.0)
        self.assertIn("starboard", self.said_on("deck")[0])

    def test_port_turn_says_port(self):
        self.hull.heading = 90.0
        self.hull.speed = 10.0
        self.hull.orders = HelmOrders(heading=0.0, speed=10.0)
        self.hull.at_maritime_tick(1.0)
        self.assertIn("port", self.said_on("deck")[0])

    def test_a_turn_across_north_reports_the_short_way(self):
        """Ordered a few degrees east of north from just west of it: starboard."""
        self.hull.heading = 350.0
        self.hull.speed = 10.0
        self.hull.orders = HelmOrders(heading=10.0, speed=10.0)
        self.hull.at_maritime_tick(1.0)
        self.assertIn("starboard", self.said_on("deck")[0])


class Laconic(VesselNarrator):
    """A game that would rather its ships said less."""

    def phrase_for(self, event, **detail):
        if event == COMING_ROUND:
            return "Turning.", "Turning."
        return super().phrase_for(event, **detail)


class NotANarrator:
    """
    Configured by mistake: a perfectly good class that is simply not a narrator.

    Deliberately one that would construct without complaint. A stand-in that blew
    up on its own account would let the type check pass its test while doing
    nothing.

    """

    def __init__(self, vessel):
        self.vessel = vessel


class TestNarratorSeam(EmptySeaMixin, BaseEvenniaTest):
    """
    The prose is replaceable without touching the simulation.

    The reason the speaking layer is a separate module at all. If a game cannot
    change the words without reimplementing when to say them, the separation is
    decorative.

    """

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Test Sloop")
        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.deck.db.vessel = self.hull
        self.deck.exposure = OPEN
        self.heard = []
        self.deck.msg_contents = lambda text, **kwargs: self.heard.append(text)
        self.hull.maritime_position = WorldPosition(0.0, 0.0)
        self.hull.motion_limits = MotionLimits(max_speed=10.0, acceleration=2.0, turn_rate=8.0)
        self.hull.speed = 10.0
        self.hull.orders = HelmOrders(heading=90.0, speed=10.0)

    def test_the_default_narrator_is_the_one_here(self):
        self.assertIsInstance(self.hull.narrator, VesselNarrator)

    def test_a_game_can_replace_every_word(self):
        with override_settings(MARITIME_NARRATOR=f"{Laconic.__module__}.Laconic"):
            self.hull.at_maritime_tick(1.0)
        self.assertEqual(self.heard, ["Turning."])

    def test_replacing_the_words_does_not_replace_the_timing(self):
        """
        A narrator that only overrides phrases still speaks once per transition,
        because deciding when to speak is not part of what it overrode.

        """
        with override_settings(MARITIME_NARRATOR=f"{Laconic.__module__}.Laconic"):
            for _ in range(5):
                self.hull.at_maritime_tick(1.0)
        self.assertEqual(self.heard.count("Turning."), 1)

    def test_a_narrator_that_is_not_one_is_refused(self):
        """
        Fails at the point of misconfiguration, naming the class, rather than as
        a missing attribute somewhere inside a tick.

        """
        with override_settings(MARITIME_NARRATOR=f"{Laconic.__module__}.NotANarrator"):
            with self.assertRaises(TypeError):
                self.hull.narrator

    def test_an_unknown_event_is_an_error_not_silence(self):
        with self.assertRaises(KeyError):
            VesselNarrator(self.hull).phrase_for("no_such_event")


class TestDelivery(EmptySeaMixin, BaseEvenniaTest):
    """Who hears what."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Test Sloop")
        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.deck.db.vessel = self.hull
        self.deck.exposure = OPEN
        self.hold = create.create_object(ShipRoom, key="Hold")
        self.hold.db.vessel = self.hull
        self.hold.exposure = BELOW_WATERLINE
        self.topside, self.below = [], []
        self.deck.msg_contents = lambda text, **kwargs: self.topside.append(text)
        self.hold.msg_contents = lambda text, **kwargs: self.below.append(text)

    def test_each_part_of_the_ship_hears_its_own_line(self):
        VesselNarrator(self.hull).deliver("On deck.", "Below.")
        self.assertEqual((self.topside, self.below), (["On deck."], ["Below."]))

    def test_an_event_can_reach_the_deck_only(self):
        """
        Saying nothing below is a real answer. Not every event carries down.

        """
        VesselNarrator(self.hull).deliver("On deck.")
        self.assertEqual((self.topside, self.below), (["On deck."], []))
