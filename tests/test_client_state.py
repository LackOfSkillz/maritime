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

from .. import config
from ..bathymetry import MaritimeMapProvider, SAND
from ..charts import Chart
from ..client.state import chart_for, contacts_for, status_for
from ..crew import ABLE
from ..damage import HULL, RIGGING
from ..motion import HelmOrders, MotionLimits
from ..observation import IDENTIFIED, VESSEL
from ..position import WorldPosition
from ..tiles import Hazard
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

    def test_she_says_what_class_of_hull_she_is(self):
        """
        Her `template_key`, which the host game chose. An interface may reasonably
        want to draw a brig differently from a cutter, and there is no other honest
        way for it to know - a rig here is a polar curve rather than a name.

        """
        self.hull.db.template_key = "brig"
        self.assertEqual(self.readings()["vessel"]["template"], "brig")

    def test_a_hull_of_no_length_says_nothing_about_her_length(self):
        """
        The same absence rule the class field follows, and until a mutation run went
        looking, nothing here checked it: dropping the guard still passed every test,
        and an interface reading `length: 0` would draw a ship of no length rather
        than omit the reading.

        A hull that was never given dimensions rather than one set to nothing - the
        setter coerces to float and will not take None, so never-measured is the only
        way this actually happens.

        """
        unmeasured = create.create_object(Vessel, key="Unnamed")
        unmeasured.maritime_position = HERE
        self.assertNotIn("length", status_for(unmeasured).as_message()["vessel"])

    def test_and_a_hull_of_no_class_says_nothing(self):
        """
        Absent rather than empty. A game that never set one gets no field at all,
        which is what lets the same interface serve a game with one sort of ship and
        a game with twenty.

        """
        self.assertNotIn("template", self.readings()["vessel"])

    def test_whatever_a_game_wrote_there_is_relayed_unchanged(self):
        """
        This contrib never interprets the value and must never grow a list of the
        classes it knows about. A game inventing a hull nobody here thought of is the
        normal case rather than an error.

        """
        for invented in ("xebec", "junk", "coracle-of-the-ninth-house"):
            self.hull.db.template_key = invented
            self.assertEqual(self.readings()["vessel"]["template"], invented)

    def test_a_contact_never_says_what_class_she_is(self):
        """
        The rule the whole payload is built on. What may be told about another ship
        is what the lookout has made out, governed by her sighting - never by what
        would be convenient for an interface to draw.

        """
        stranger = create.create_object(Vessel, key="Stranger")
        stranger.length, stranger.beam = 30.0, 8.0
        stranger.maritime_position = WorldPosition(0.0, 400.0)
        stranger.db.template_key = "frigate"
        traffic().note(stranger, stranger.maritime_position)

        for contact in contacts_for(self.hull).as_message()["contacts"]:
            self.assertNotIn("template", contact)

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


#: What `RockyBottom` answers with, and what reach it was asked for.
#:
#: Module level because `override_settings` resolves a provider by dotted path, so the
#: class it names cannot be handed anything by the test that wants it. The list is the
#: seam instead.
CHARTED_ROCKS = []
ASKED_FOR = []


class RockyBottom(MaritimeMapProvider):
    """Forty metres of water, and whatever rocks a test has put on the bottom."""

    def terrain_z_at(self, position):
        return -40.0

    def charted_dangers(self, position, reach):
        ASKED_FOR.append(reach)
        return tuple(CHARTED_ROCKS)


class OlderProvider(MaritimeMapProvider):
    """
    A provider written before charted dangers existed.

    A subclass, because the configuration refuses anything else - which is the answer to
    whether a game could have a provider that has never heard of this. It cannot: it
    inherits the base class, and the base class answers with nothing.
    """

    def terrain_z_at(self, position):
        return -40.0


# Derived rather than written out. This package targets a standalone repository as
# well as the Evennia tree, so a dotted path spelled by hand hardcodes one of the two
# homes - and CI checks for exactly that.
ROCKY = f"{__name__}.RockyBottom"
OLDER = f"{__name__}.OlderProvider"


class TestTheRocksReachThePaper(StateTestCase):
    """
    The half of the charted layer that was designed and never drawn.

    `docs/client.md` has said since the interface was specified that the charted layer
    carries land, soundings, marks *and hazards*. The first three arrived. Grounding has
    been asking providers for hazards the whole time, so a rock a game had authored would
    hole a hull that sailed over it while the chart drew open water above it - which is
    worse than a rock drawn nowhere, because the captain has looked at the paper and is
    entitled to believe it.

    It cannot come from the soundings. Those are sampled on a grid, and anything narrower
    than the grid is missed rather than smoothed - and missed differently depending on
    where the grid falls, so it would appear and vanish as she sailed.
    """

    def setUp(self):
        super().setUp()
        self.hull.add_chart(Chart(key="the approaches", west=-9e4, east=9e4, south=-9e4, north=9e4))
        CHARTED_ROCKS.clear()
        ASKED_FOR.clear()
        self.addCleanup(CHARTED_ROCKS.clear)
        self.addCleanup(ASKED_FOR.clear)

    def sheet(self, reach=6000.0):
        return chart_for(self.hull, reach).as_message()

    def rocky(self, *hazards):
        """Put those rocks on the bottom, under a provider that reports them."""
        CHARTED_ROCKS.extend(hazards)
        override = override_settings(MARITIME_MAP_PROVIDER=ROCKY)
        override.enable()
        self.addCleanup(override.disable)
        config.forget_map_provider()
        self.addCleanup(config.forget_map_provider)

    def test_a_world_with_no_rocks_publishes_none(self):
        self.rocky()
        self.assertEqual(self.sheet()["dangers"], [])

    @override_settings(MARITIME_MAP_PROVIDER=OLDER)
    def test_a_provider_that_never_heard_of_them_is_not_an_error(self):
        """
        Additive, like `hazards_touching` before it. A game whose provider predates this
        overrides `terrain_z_at` and nothing else, inherits an answer of nothing, and gets
        a chart exactly as it was.

        This is also where it turned out a provider *cannot* simply not have the method:
        the configuration checks the type, so anything a game points a setting at is a
        subclass and has it. The guard in `_dangers_within` stays for a provider assigned
        directly - a test double, or a game reaching past its own settings.

        """
        config.forget_map_provider()
        self.addCleanup(config.forget_map_provider)
        self.assertEqual(self.sheet()["dangers"], [])

    def test_a_rock_arrives_as_an_offset(self):
        """
        Offsets, like everything else on the sheet. A browser is never handed a survey
        of the world, and a chart that has drifted from the reckoning draws the rock in
        the wrong place - which is what being lost looks like.

        """
        self.rocky(Hazard(key="the Whaleback", x=1200.0, y=-400.0, radius=70.0, top_z=-3.5))
        drawn = self.sheet()["dangers"]
        self.assertEqual(len(drawn), 1)
        self.assertEqual(drawn[0]["east"], 1200.0)
        self.assertEqual(drawn[0]["north"], -400.0)
        self.assertEqual(drawn[0]["label"], "the Whaleback")
        self.assertNotIn("x", drawn[0])

    def test_it_carries_the_water_over_it(self):
        """The number that decides whether she may pass."""
        self.rocky(Hazard(key="the Whaleback", x=800.0, y=0.0, radius=70.0, top_z=-3.5))
        self.assertEqual(self.sheet()["dangers"][0]["top_z"], -3.5)

    def test_and_what_it_is_made_of(self):
        self.rocky(Hazard(key="a shoal", x=800.0, y=0.0, radius=90.0, top_z=-2.0, bottom=SAND))
        self.assertEqual(self.sheet()["dangers"][0]["bottom"], SAND)

    def test_one_that_dries_says_so(self):
        """
        Land at chart datum reads differently from three metres of water, and the
        interface has to be able to draw it differently without doing the arithmetic
        itself.

        """
        self.rocky(
            Hazard(key="the Brawn", x=500.0, y=0.0, radius=40.0, top_z=0.6),
            Hazard(key="the Whaleback", x=900.0, y=0.0, radius=70.0, top_z=-3.5),
        )
        drying = {d["label"]: d["dries"] for d in self.sheet()["dangers"]}
        self.assertEqual(drying, {"the Brawn": True, "the Whaleback": False})

    def test_the_worst_news_is_first(self):
        self.rocky(
            Hazard(key="deep one", x=200.0, y=0.0, radius=50.0, top_z=-9.0),
            Hazard(key="shoal one", x=400.0, y=0.0, radius=50.0, top_z=-1.5),
            Hazard(key="middling", x=600.0, y=0.0, radius=50.0, top_z=-4.0),
        )
        self.assertEqual(
            [d["label"] for d in self.sheet()["dangers"]],
            ["shoal one", "middling", "deep one"],
        )

    def test_the_provider_is_asked_for_the_sheet_she_is_drawing(self):
        """
        Not a fixed radius. A captain zoomed out to twenty miles is asking about twenty
        miles of rocks, and a sheet that answered for two would leave the rest of the
        paper looking surveyed and empty.

        """
        self.rocky()
        ASKED_FOR.clear()
        self.sheet(reach=3000.0)
        self.sheet(reach=18000.0)
        self.assertEqual(ASKED_FOR, [3000.0, 18000.0])

    def test_they_are_not_buoyage(self):
        """
        Two layers, drawn differently on purpose. A buoy is a thing somebody moored and
        it can drag; a rock is a thing somebody found and it cannot, and a chart that
        confused them would have a captain looking for a light on a reef.

        """
        self.rocky(Hazard(key="the Whaleback", x=800.0, y=0.0, radius=70.0, top_z=-3.5))
        drawn = self.sheet()
        self.assertEqual(len(drawn["dangers"]), 1)
        self.assertEqual(drawn["marks"], [])
