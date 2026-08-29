"""
Tests for keeping a lookout: the register, the hull, and what gets called.

"""

from django.test import override_settings

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaCommandTest, BaseEvenniaTest

from ..commands import CmdLookout, describe_contact
from ..formatting import RAW, format_range
from ..motion import HelmOrders, MotionLimits
from ..observation import CLASSIFIED, CONTACT, IDENTIFIED, VESSEL, Sighting
from ..position import EAST, METRES_PER_NAUTICAL_MILE, NORTH, WorldPosition
from ..sailing import FURLED, WORKING
from ..traffic import VesselTraffic, traffic
from ..typeclasses import ShipRoom, Vessel
from ..vessel import BELOW_WATERLINE, OPEN
from .base import EmptySeaMixin


class TestVesselTraffic(EmptySeaMixin, BaseEvenniaTest):
    """The register of who is afloat."""

    def setUp(self):
        super().setUp()
        self.register = VesselTraffic()
        self.hull = create.create_object(Vessel, key="Test Sloop")

    def test_a_noted_vessel_is_in_it(self):
        self.register.note(self.hull, WorldPosition(0.0, 0.0))
        self.assertIn(self.hull, self.register)

    def test_noting_twice_does_not_duplicate_her(self):
        """
        A vessel calls this every tick whether she has moved or not, so it has to
        be idempotent or the register fills with one ship.

        """
        self.register.note(self.hull, WorldPosition(0.0, 0.0))
        self.register.note(self.hull, WorldPosition(0.0, 0.0))
        self.assertEqual(len(self.register), 1)

    def test_noting_again_moves_her(self):
        self.register.note(self.hull, WorldPosition(0.0, 0.0))
        self.register.note(self.hull, WorldPosition(500.0, 0.0))
        self.assertEqual(self.register.position_of(self.hull), WorldPosition(500.0, 0.0))

    def test_forgetting_removes_her(self):
        self.register.note(self.hull, WorldPosition(0.0, 0.0))
        self.assertTrue(self.register.forget(self.hull))
        self.assertNotIn(self.hull, self.register)

    def test_forgetting_someone_absent_is_not_an_error(self):
        self.assertFalse(self.register.forget(self.hull))

    def test_near_finds_her(self):
        self.register.note(self.hull, WorldPosition(100.0, 0.0))
        self.assertEqual(self.register.near(WorldPosition(0.0, 0.0), 500.0), (self.hull,))

    def test_near_excludes_the_distant(self):
        self.register.note(self.hull, WorldPosition(5000.0, 0.0))
        self.assertEqual(self.register.near(WorldPosition(0.0, 0.0), 500.0), ())

    def test_a_deleted_vessel_leaves_the_water(self):
        """
        The register is memory, not a foreign key. Nothing removes her when her
        row goes, so a sunk and deleted hull would stay visible on the horizon -
        a haunting rather than a feature.

        """
        self.hull.maritime_position = WorldPosition(0.0, 0.0)
        self.hull.at_maritime_tick(1.0)
        self.assertIn(self.hull, traffic())
        self.hull.delete()
        self.assertEqual(len(traffic()), 0)


class WatchTestCase(EmptySeaMixin, BaseEvenniaTest):
    """Two ships and somewhere to stand."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Test Sloop")
        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.deck.db.vessel = self.hull
        self.deck.exposure = OPEN
        self.hull.maritime_position = WorldPosition(0.0, 0.0)
        self.hull.motion_limits = MotionLimits(max_speed=10.0, acceleration=2.0, turn_rate=8.0)
        self.hull.heading = NORTH
        self.hull.orders = HelmOrders(heading=NORTH, speed=0.0)
        self.hull.air_draft = 12.0

        self.other = create.create_object(Vessel, key="Marigold")
        self.other.air_draft = 12.0
        self.heard = []
        self.deck.msg_contents = lambda text, **kwargs: self.heard.append(text)

    def put_other_at(self, x, y=0.0):
        """
        Args:
            x (float): Easting in metres.
            y (float, optional): Northing in metres.

        """
        self.other.maritime_position = WorldPosition(x, y)
        traffic().note(self.other, self.other.maritime_position)


class TestVesselSight(WatchTestCase):
    """What a hull can see."""

    def test_an_empty_sea_shows_nothing(self):
        self.assertEqual(self.hull.contacts(), ())

    def test_another_vessel_within_range_is_seen(self):
        self.put_other_at(1000.0)
        self.assertEqual([s.target for s in self.hull.contacts()], [self.other])

    def test_she_does_not_see_herself(self):
        """
        She is in the register too, and at range zero, so without this she would
        report a permanent contact alongside.

        """
        traffic().note(self.hull, self.hull.maritime_position)
        self.assertEqual(self.hull.contacts(), ())

    def test_a_vessel_beyond_the_horizon_is_not_seen(self):
        self.put_other_at(60.0 * METRES_PER_NAUTICAL_MILE)
        self.assertEqual(self.hull.contacts(), ())

    def test_an_unlaunched_vessel_sees_nothing(self):
        idle = create.create_object(Vessel, key="On The Stocks")
        self.assertEqual(idle.contacts(), ())

    def test_a_vessel_with_no_position_is_not_a_contact(self):
        """She is registered but has since been taken off the water."""
        self.put_other_at(1000.0)
        self.other.ndb.maritime_position = None
        self.other.db.maritime_position = None
        self.assertEqual(self.hull.contacts(), ())

    def test_fog_shortens_what_she_sees(self):
        self.put_other_at(3000.0)
        self.assertTrue(self.hull.contacts())
        with override_settings(MARITIME_VISIBILITY=500.0):
            self.assertEqual(self.hull.contacts(), ())

    def test_a_taller_ship_is_visible_further_off(self):
        far = 13.0 * METRES_PER_NAUTICAL_MILE
        self.put_other_at(far)
        self.assertEqual(self.hull.contacts(), ())
        self.other.air_draft = 60.0
        self.assertTrue(self.hull.contacts())


class TestHeightOfEye(WatchTestCase):
    """Where the lookout stands."""

    def test_a_bare_deck_sees_from_deck_height(self):
        self.assertEqual(self.hull.height_of_eye, self.deck.height_of_eye)

    def test_a_masthead_raises_her_eye(self):
        top = create.create_object(ShipRoom, key="Masthead")
        top.db.vessel = self.hull
        top.exposure = OPEN
        top.height_of_eye = 28.0
        self.assertEqual(self.hull.height_of_eye, 28.0)

    def test_a_hold_does_not_count_however_high_it_is_set(self):
        """
        A lookout is on a weather deck. A compartment below decks has no view
        whatever its number says.

        """
        hold = create.create_object(ShipRoom, key="Hold")
        hold.db.vessel = self.hull
        hold.exposure = BELOW_WATERLINE
        hold.height_of_eye = 99.0
        self.assertEqual(self.hull.height_of_eye, self.deck.height_of_eye)

    def test_a_hull_with_no_rooms_still_has_an_eye(self):
        bare = create.create_object(Vessel, key="Bare")
        self.assertGreater(bare.height_of_eye, 0.0)

    def test_going_aloft_extends_the_horizon(self):
        """The whole reason to man a masthead."""
        far = 11.0 * METRES_PER_NAUTICAL_MILE
        self.put_other_at(far)
        self.assertEqual(self.hull.contacts(2.0), ())
        self.assertTrue(self.hull.contacts(30.0))


class TestSightingReports(WatchTestCase):
    """What gets called down from the deck."""

    def test_a_new_sail_is_cried(self):
        self.put_other_at(1000.0)
        self.hull.at_maritime_tick(1.0)
        self.assertTrue(any("Sail ho!" in text for text in self.heard))

    def test_the_cry_says_where_to_look(self):
        self.put_other_at(1000.0)
        self.hull.at_maritime_tick(1.0)
        self.assertTrue(any("starboard beam" in text for text in self.heard))

    def test_a_sail_is_only_cried_once(self):
        """
        News once. Reporting every contact every tick buries the one that just
        appeared under the three that did not.

        """
        self.put_other_at(1000.0)
        for _ in range(5):
            self.hull.at_maritime_tick(1.0)
        self.assertEqual(len([t for t in self.heard if "Sail ho!" in t]), 1)

    def test_losing_her_is_reported(self):
        self.put_other_at(1000.0)
        self.hull.at_maritime_tick(1.0)
        self.heard.clear()
        self.put_other_at(60.0 * METRES_PER_NAUTICAL_MILE)
        self.hull.at_maritime_tick(1.0)
        self.assertTrue(any("horizon" in text for text in self.heard))

    def test_closing_to_identify_is_reported(self):
        self.put_other_at(12000.0)
        self.hull.at_maritime_tick(1.0)
        self.heard.clear()
        self.put_other_at(200.0)
        self.hull.at_maritime_tick(1.0)
        self.assertTrue(any("Marigold" in text for text in self.heard))

    def test_a_ship_at_anchor_still_keeps_a_watch(self):
        """
        The tick returns early for an anchored hull. Observation happens before
        that, because a ship at anchor is exactly where you want a lookout.

        """
        self.hull.anchored = True
        self.put_other_at(1000.0)
        self.hull.at_maritime_tick(1.0)
        self.assertTrue(any("Sail ho!" in text for text in self.heard))

    def test_a_ship_aground_still_keeps_a_watch(self):
        self.hull.aground = True
        self.put_other_at(1000.0)
        self.hull.at_maritime_tick(1.0)
        self.assertTrue(any("Sail ho!" in text for text in self.heard))


class TestDescribeContact(BaseEvenniaTest):
    """Saying only as much as the range allows."""

    def setUp(self):
        super().setUp()
        self.other = create.create_object(Vessel, key="Marigold")

    def sighting(self, level):
        """
        Args:
            level (str): Detection level to describe.

        Returns:
            sighting (Sighting): A stand-in at that level.

        """
        return Sighting(target=self.other, distance=1000.0, bearing=0.0, relative=0.0, level=level)

    def test_a_far_contact_is_not_named(self):
        """
        The engine knows her name at every range. Saying it anyway would make
        closing to identify pointless.

        """
        self.assertNotIn("Marigold", describe_contact(self.sighting(CONTACT)))

    def test_a_vessel_is_a_sail(self):
        self.assertEqual(describe_contact(self.sighting(VESSEL)), "a sail")

    def test_a_classified_contact_shows_her_canvas(self):
        self.other.sail_plan = WORKING
        self.assertIn("under sail", describe_contact(self.sighting(CLASSIFIED)))

    def test_a_classified_contact_with_nothing_set_is_bare(self):
        self.other.sail_plan = FURLED
        self.assertIn("furled", describe_contact(self.sighting(CLASSIFIED)))

    def test_an_identified_contact_is_named(self):
        self.assertIn("Marigold", describe_contact(self.sighting(IDENTIFIED)))


class TestFormatRange(BaseEvenniaTest):
    """Distances the way they are said."""

    def test_miles_above_a_mile(self):
        self.assertEqual(format_range(2.0 * METRES_PER_NAUTICAL_MILE), "2.0 miles")

    def test_cables_below_a_mile(self):
        self.assertEqual(format_range(0.3 * METRES_PER_NAUTICAL_MILE), "three cables")

    def test_one_cable_is_singular(self):
        self.assertEqual(format_range(0.1 * METRES_PER_NAUTICAL_MILE), "one cable")

    def test_alongside(self):
        self.assertEqual(format_range(5.0), "alongside")

    def test_raw_style_is_metres(self):
        self.assertEqual(format_range(1830.0, units=RAW), "1830 m")


class TestCmdLookout(EmptySeaMixin, BaseEvenniaCommandTest):
    """Asking what is out there."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Test Sloop")
        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.deck.db.vessel = self.hull
        self.deck.exposure = OPEN
        self.hull.maritime_position = WorldPosition(0.0, 0.0)
        self.hull.heading = EAST
        self.hull.air_draft = 12.0
        self.char1.location = self.deck

        self.other = create.create_object(Vessel, key="Marigold")
        self.other.air_draft = 12.0

    def test_an_empty_sea_reports_the_horizon(self):
        output = self.call(CmdLookout(), "")
        self.assertIn("Nothing in sight", output)

    def test_a_contact_is_listed(self):
        self.other.maritime_position = WorldPosition(0.0, 1000.0)
        traffic().note(self.other, self.other.maritime_position)
        output = self.call(CmdLookout(), "")
        self.assertIn("port beam", output)

    def test_the_range_is_given(self):
        self.other.maritime_position = WorldPosition(0.0, 1000.0)
        traffic().note(self.other, self.other.maritime_position)
        output = self.call(CmdLookout(), "")
        self.assertIn("cables", output)

    def test_you_cannot_see_out_from_below(self):
        hold = create.create_object(ShipRoom, key="Hold")
        hold.db.vessel = self.hull
        hold.exposure = BELOW_WATERLINE
        self.char1.location = hold
        output = self.call(CmdLookout(), "")
        self.assertIn("cannot see the sea", output)

    def test_it_needs_a_deck_under_you(self):
        self.char1.location = self.room1
        output = self.call(CmdLookout(), "")
        self.assertIn("not aboard a vessel", output)
