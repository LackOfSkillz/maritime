"""
Tests for what the client is told about a ship.

Almost every test here is about something the payload must *not* contain. The interface
can only ever show what it was given, so the whole of "a graphical client must never make
the navigator more knowledgeable than the character" is enforced right here, in what these
builders decline to put on the wire.

"""

from django.test import override_settings

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest

from ..charts import Chart
from ..client.state import chart_for, contacts_for, status_for
from ..crew import ABLE
from ..damage import HULL, RIGGING
from ..motion import HelmOrders, MotionLimits
from ..observation import IDENTIFIED, VESSEL
from ..position import WorldPosition
from ..rooms import ShipRoom
from ..sailing import FULL
from ..traffic import traffic
from ..typeclasses import Vessel
from ..vessel import OPEN
from .base import EmptySeaMixin

HERE = WorldPosition(0.0, 0.0)
BREEZE = {"MARITIME_WIND_BEARING": 270.0, "MARITIME_WIND_SPEED": 9.0}


class StateTestCase(EmptySeaMixin, BaseEvenniaTest):
    """A hull with instruments worth reporting."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="HMS Aetos Folly")
        self.hull.length, self.hull.beam = 18.0, 5.4
        self.hull.motion_limits = MotionLimits(max_speed=8.0, acceleration=0.5, turn_rate=5.0)
        self.hull.maritime_position = HERE
        self.hull.heading = 90.0
        self.hull.orders = HelmOrders(heading=90.0, speed=4.0)
        self.hull.sail_plan = FULL
        deck = create.create_object(ShipRoom, key="Main Deck")
        deck.vessel = self.hull
        deck.exposure = OPEN
        traffic().note(self.hull, HERE)

    def readings(self):
        """
        Returns:
            status (dict): Her instruments, as they go on the wire.

        """
        return status_for(self.hull).as_message()


class TestWhatHerInstrumentsSay(StateTestCase):
    """The readings, and the ones that are deliberately absent."""

    def test_she_names_herself(self):
        self.assertEqual(self.readings()["vessel"]["name"], "HMS Aetos Folly")

    def test_heading_and_course_made_good_are_both_reported(self):
        """
        Two different quantities. One is where she points, the other where she is
        going, and the gap between them is what the water is doing to her -
        collapsing them would be the most misleading thing this could do.

        """
        with override_settings(**BREEZE):
            motion = self.readings()["motion"]
        self.assertIn("heading", motion)
        self.assertIn("course_made_good", motion)

    def test_speed_through_the_water_is_not_speed_over_the_ground(self):
        with override_settings(**BREEZE):
            motion = self.readings()["motion"]
        self.assertIn("speed_through_water", motion)
        self.assertIn("speed_over_ground", motion)

    def test_bearings_are_wrapped_into_a_compass(self):
        self.hull.heading = 450.0
        self.assertAlmostEqual(self.readings()["motion"]["heading"], 90.0)

    def test_a_flat_calm_reports_no_wind(self):
        """
        A reading appears because it is true here. There is no wind field on a
        windless day, rather than a wind field holding zero.

        """
        with override_settings(MARITIME_WIND_SPEED=0.0):
            self.assertNotIn("wind_from", self.readings()["environment"])

    def test_a_ship_off_her_chart_reports_no_depth(self):
        """
        The most important absence of all. Off the chart there is no sounding, and
        an interface showing zero fathoms would be inventing one.

        """
        self.assertNotIn("charted_depth", self.readings()["environment"])

    def test_and_one_on_it_does(self):
        self.hull.add_chart(Chart(key="a sheet", west=-5000, east=5000, south=-5000, north=5000))
        self.assertIn("charted_depth", self.readings()["environment"])

    def test_the_depth_reported_is_the_charted_one(self):
        """
        Never the true seabed. The number on the board is what the paper says, so a
        bad chart reads wrong on the instruments exactly as it does on the deck.

        """
        self.hull.add_chart(
            Chart(key="a sheet", west=-5000, east=5000, south=-5000, north=5000, quality=0.2)
        )
        self.assertAlmostEqual(
            self.readings()["environment"]["charted_depth"], self.hull.charted_depth()
        )


class TestWhatIsWrongWithHer(StateTestCase):
    """Condition is reported as soundness, so a bar empties as she is hurt."""

    def test_a_sound_hull_still_reports(self):
        """The track that sinks her is always on the board."""
        self.assertAlmostEqual(self.readings()["condition"]["hull"], 1.0)

    def test_a_hurt_hull_reports_less(self):
        self.hull.take_damage(HULL, 400.0)
        self.assertLess(self.readings()["condition"]["hull"], 1.0)

    def test_sound_rigging_is_not_mentioned(self):
        """Three bars at full is wallpaper. A bar appearing is news."""
        self.assertNotIn("rigging", self.readings()["condition"])

    def test_shot_rigging_is(self):
        self.hull.take_damage(RIGGING, 400.0)
        self.assertIn("rigging", self.readings()["condition"])

    def test_soundness_never_falls_below_nothing(self):
        self.hull.take_damage(HULL, 100000.0)
        self.assertGreaterEqual(self.readings()["condition"]["hull"], 0.0)


class TestWhoIsAboard(StateTestCase):
    """Her company, banded rather than counted."""

    def test_a_hull_with_no_company_reports_none(self):
        self.assertEqual(self.readings()["company"], {})

    def test_a_manned_hull_reports_her_complement(self):
        self.hull.man(40, ABLE)
        self.assertEqual(self.readings()["company"]["complement"], 40)

    def test_morale_travels_as_a_band_and_never_as_a_number(self):
        """
        The simulation bands it on purpose: a captain is told his people are
        wavering, which he can act on, rather than handed a percentage to manage.
        Publishing the number would undo that decision from outside.

        """
        self.hull.man(40, ABLE)
        morale = self.readings()["company"]["morale"]
        self.assertIsInstance(morale, str)
        self.assertNotIsInstance(morale, float)


class TestWhatTheLookoutHas(StateTestCase):
    """Bearing and range, and never a name she has not earned."""

    def a_ship_at(self, key, bearing, distance, air_draft=None):
        """
        Returns:
            vessel (Vessel): A hull at that bearing and range from us.

        """
        other = create.create_object(Vessel, key=key)
        other.length, other.beam = 30.0, 8.0
        if air_draft is not None:
            other.air_draft = air_draft
        other.maritime_position = HERE.moved(bearing, distance)
        other.sail_plan = FULL
        traffic().note(other, other.maritime_position)
        return other

    def test_an_empty_sea_reports_nothing(self):
        self.assertEqual(contacts_for(self.hull).as_message()["contacts"], [])

    def test_a_ship_close_by_is_reported(self):
        self.a_ship_at("the Marigold", 90.0, 400.0)
        self.assertTrue(contacts_for(self.hull).as_message()["contacts"])

    def test_she_is_reported_by_bearing_and_range(self):
        self.a_ship_at("the Marigold", 90.0, 400.0)
        seen = contacts_for(self.hull).as_message()["contacts"][0]
        self.assertAlmostEqual(seen["bearing"], 90.0, places=1)
        self.assertAlmostEqual(seen["range"], 400.0, places=0)

    def test_and_never_by_position(self):
        """
        A contact drawn at its true coordinates is a radar return. Bearing and
        range is what a lookout calls down and all a chart may plot.

        """
        self.a_ship_at("the Marigold", 90.0, 400.0)
        seen = contacts_for(self.hull).as_message()["contacts"][0]
        self.assertNotIn("x", seen)
        self.assertNotIn("y", seen)
        self.assertNotIn("position", seen)

    def test_a_ship_she_has_identified_is_named(self):
        self.a_ship_at("the Marigold", 90.0, 300.0)
        seen = contacts_for(self.hull).as_message()["contacts"][0]
        self.assertEqual(seen["level"], IDENTIFIED)
        self.assertIn("Marigold", seen["label"])

    def test_a_ship_she_has_not_is_not(self):
        """
        The rule the whole interface rests on. Her name exists in the database and
        never reaches the payload, so a browser cannot leak what it was never
        given - there is no filtering step here to forget.

        """
        self.a_ship_at("Nameless", 90.0, 18000.0, air_draft=60.0)
        seen = [
            contact
            for contact in contacts_for(self.hull).as_message()["contacts"]
            if contact["level"] != IDENTIFIED
        ]
        self.assertTrue(seen, "expected a contact too far off to identify")
        for contact in seen:
            self.assertNotIn("Nameless", contact["label"])
            self.assertFalse(contact["identified"])

    def test_an_unidentified_contact_says_only_what_she_looks_like(self):
        self.a_ship_at("Nameless", 90.0, 18000.0, air_draft=60.0)
        for contact in contacts_for(self.hull).as_message()["contacts"]:
            if contact["level"] == VESSEL:
                self.assertIn("sail", contact["label"])


class TestThePaper(StateTestCase):
    """The chart sheet, and what it declines to draw."""

    def give_her_a_chart(self, reach=6000.0):
        """Put a sheet aboard covering the water around her."""
        self.hull.add_chart(
            Chart(
                key="a sheet",
                west=-reach,
                east=reach,
                south=-reach,
                north=reach,
                quality=0.8,
            )
        )

    def test_a_ship_with_no_chart_draws_nothing(self):
        """
        Sailing without one is a real situation and should look like one, rather
        than like open sea.

        """
        sheet = chart_for(self.hull).as_message()
        self.assertEqual(sheet["coastline"], [])
        self.assertEqual(sheet["soundings"], [])

    def test_a_chart_draws_the_edge_of_its_own_coverage(self):
        self.give_her_a_chart()
        self.assertIn("west", chart_for(self.hull, 3000.0).as_message()["coverage"])

    def test_everything_it_sends_is_an_offset(self):
        """
        Nothing on the wire is a world coordinate, so a browser handed the whole
        payload still cannot say where she is.

        """
        self.give_her_a_chart()
        self.hull.maritime_position = WorldPosition(90000.0, 90000.0)
        sheet = chart_for(self.hull, 2000.0).as_message()
        for line in sheet["coastline"]:
            for east, north in line:
                self.assertLess(abs(east), 20000)
                self.assertLess(abs(north), 20000)

    def test_a_wider_sheet_is_asked_for_more_sea(self):
        self.give_her_a_chart(reach=40000.0)
        near = chart_for(self.hull, 2000.0).as_message()
        far = chart_for(self.hull, 20000.0).as_message()
        self.assertGreater(far["reach"], near["reach"])
