"""
Tests for what a ship's company is told while she is under way.

"""

from django.test import override_settings
from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaCommandTest, BaseEvenniaTest

from ..commands import CmdAllStop, CmdHelm, CmdPlot
from ..formatting import format_range
from ..messaging import (
    COMING_ROUND,
    HELM_ORDER,
    Order,
    VesselNarrator,
    compass_point,
    spell_bearing,
)
from ..motion import HelmOrders, MotionLimits
from ..observation import IDENTIFIED, Sighting
from ..position import WorldPosition
from ..routes import Route, Waypoint
from ..typeclasses import ShipRoom, Vessel
from ..vessel import BELOW_WATERLINE, OPEN
from .base import EmptySeaMixin


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
            room.vessel = self.hull
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
    """A game that would rather its ships and its crews said less."""

    def phrase_for(self, event, **detail):
        if event == COMING_ROUND:
            return "Turning.", "Turning."
        return super().phrase_for(event, **detail)

    def order_for(self, event, **detail):
        if event == HELM_ORDER:
            return Order(called=f"Steer {detail['spoken']}.", answered="Aye.")
        return super().order_for(event, **detail)


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
        self.deck.vessel = self.hull
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
        self.deck.vessel = self.hull
        self.deck.exposure = OPEN
        self.hold = create.create_object(ShipRoom, key="Hold")
        self.hold.vessel = self.hull
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


class TestTheCrewSpeakThroughTheNarratorToo(EmptySeaMixin, BaseEvenniaCommandTest):
    """
    A game's voice reaches the crew's replies, not only the ship's narration.

    It did not, once. Commands carried their own hardcoded prose, so overriding
    `MARITIME_NARRATOR` changed what the *ship* said and left the crew answering
    in the contrib's words - two voices in one game, and the second of them
    unreachable without forking every command.

    """

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Test Sloop")
        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.deck.vessel = self.hull
        self.deck.exposure = OPEN
        self.hull.maritime_position = WorldPosition(0.0, 0.0)
        self.char1.location = self.deck

    def test_the_default_crew_answer_in_full(self):
        output = self.call(CmdHelm(), "090")
        self.assertIn("Steering 0-9-0 now, sir", output)

    def test_a_game_can_replace_what_the_crew_say(self):
        with override_settings(MARITIME_NARRATOR=f"{Laconic.__module__}.Laconic"):
            output = self.call(CmdHelm(), "090")
        self.assertIn("Steer 0-9-0.", output)
        self.assertNotIn("sir", output)

    def test_orders_it_does_not_override_keep_the_default_voice(self):
        """Overriding one order inherits the rest, as with `phrase_for`."""
        with override_settings(MARITIME_NARRATOR=f"{Laconic.__module__}.Laconic"):
            output = self.call(CmdAllStop(), "")
        self.assertIn("All stop", output)


class TestOneUnitPerReport(EmptySeaMixin, BaseEvenniaTest):
    """
    A range column exists to be compared down. Mixing units gives that up.

    Seen live before this was fixed: "The horizon, all round - 2.9 miles off",
    then contacts at "2.7 miles" and "1.5 leagues" in the same list. Three ranges,
    two units, and no way to tell at a glance which was nearest - which is the one
    job the column has. `format_range` chooses per value, so a report has to choose
    once and pass it down.

    """

    #: Ranges that `format_range` would render in different units left to itself.
    #: Just over and just under the league boundary, which is where it changes its
    #: mind.
    MIXED = (4300.0, 9700.0, 16000.0)

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Test Sloop")
        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.deck.vessel = self.hull
        self.deck.exposure = OPEN
        self.hull.maritime_position = WorldPosition(0.0, 0.0)
        self.narrator = self.hull.narrator

    def sightings(self, distances):
        """
        Returns:
            sightings (tuple): One contact at each range, all identified.

        """
        return tuple(
            Sighting(
                target=create.create_object(Vessel, key=f"Sail {n}"),
                distance=metres,
                bearing=45.0,
                relative=45.0,
                level=IDENTIFIED,
            )
            for n, metres in enumerate(distances)
        )

    def units_in(self, lines):
        """
        Returns:
            units (set): Which distance units the report actually used.

        """
        text = " ".join(lines)
        return {
            word
            for word in ("cable", "cables", "mile", "miles", "league", "leagues")
            if word in text.split() or f"{word} " in text or text.endswith(word)
        }

    def test_a_sector_report_picks_one_unit(self):
        lines = self.narrator.sector_report("fore", self.sightings(self.MIXED))
        self.assertLessEqual(len(self.units_in(lines)), 1, lines)

    def test_and_the_horizon_agrees_with_the_contacts(self):
        lines = self.narrator.sector_report("fore", self.sightings(self.MIXED), horizon=20000.0)
        self.assertLessEqual(len(self.units_in(lines)), 1, lines)

    def test_the_sweep_scale_accounts_for_the_horizon_it_prints(self):
        """
        `all_round` prints the horizon on its first line, unlike `sector_report`,
        so the horizon is one of the numbers the unit has to suit. Choosing from
        the contacts alone gives one unit and the wrong one - a horizon rendered
        as "32.4 miles" beside contacts that wanted leagues.

        """
        sweep = (("fore", self.sightings((4300.0,))),)
        lines = self.narrator.all_round(sweep, horizon=60000.0)
        self.assertIn("leagues", " ".join(lines))
        self.assertNotIn("miles", " ".join(lines))

    def test_an_all_round_sweep_picks_one_unit(self):
        sweep = (
            ("fore", self.sightings(self.MIXED[:1])),
            ("starboard", self.sightings(self.MIXED[1:])),
            ("aft", ()),
        )
        lines = self.narrator.all_round(sweep, horizon=20000.0)
        self.assertLessEqual(len(self.units_in(lines)), 1, lines)

    def test_an_empty_sector_still_reads_sensibly(self):
        lines = self.narrator.sector_report("aft", (), horizon=20000.0)
        self.assertTrue(any("Nothing in sight" in line for line in lines))

    def test_the_mixture_is_real_without_a_scale(self):
        """
        Guards the test itself. If these ranges ever stopped straddling a unit
        boundary, every assertion above would pass for the wrong reason.

        """
        loose = {format_range(metres).split()[-1] for metres in self.MIXED}
        self.assertGreater(len(loose), 1)


class TestThePassageReportPicksOneUnit(EmptySeaMixin, BaseEvenniaCommandTest):
    """
    "Two miles to the mark, one league to run in all" is two numbers a captain has
    to convert before he can tell which is bigger - in the one sentence where the
    comparison is the entire point.

    """

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Test Sloop")
        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.deck.vessel = self.hull
        self.deck.exposure = OPEN
        self.hull.maritime_position = WorldPosition(0.0, 0.0)
        self.hull.motion_limits = MotionLimits(max_speed=8.0, acceleration=1.0, turn_rate=6.0)
        # Legs chosen so the near mark and the whole passage fall either side of a
        # unit boundary, which is where the report used to change its mind halfway.
        self.hull.route = Route(
            (
                Waypoint("fairway", WorldPosition(4300.0, 0.0)),
                Waypoint("the bar", WorldPosition(16000.0, 0.0)),
            )
        )
        self.char1.location = self.deck

    def test_both_ranges_read_in_the_same_unit(self):
        said = self.call(CmdPlot(), "")
        units = {word for word in ("miles", "leagues", "cables") if word in said}
        self.assertEqual(len(units), 1, said)
