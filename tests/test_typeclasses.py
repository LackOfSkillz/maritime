"""
Tests for the vessel and ship-room typeclasses.

These touch the database, so they use the object-creating test base rather than
the settings-only one.

"""

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest

from ..position import WorldPosition
from ..resolver import NoWorldPosition, get_world_position
from ..typeclasses import ShipRoom, Vessel
from ..vessel import BELOW_WATERLINE, INTERIOR, MAIN_DECK, OPEN


class VesselTestCase(BaseEvenniaTest):
    """Shared setup: one hull with one compartment aboard."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Test Sloop")
        self.cabin = create.create_object(ShipRoom, key="Cabin")
        self.cabin.db.vessel = self.hull
        self.at_sea = WorldPosition(18422.0, 9912.0)


class TestVesselPosition(VesselTestCase):
    """Where a vessel is."""

    def test_starts_with_no_position(self):
        self.assertIsNone(self.hull.maritime_position)

    def test_accepts_a_position(self):
        self.hull.maritime_position = self.at_sea
        self.assertEqual(self.hull.maritime_position, self.at_sea)

    def test_rejects_a_non_position(self):
        """A tuple survives assignment and fails much later, inside a distance."""
        with self.assertRaises(TypeError):
            self.hull.maritime_position = (1.0, 2.0)

    def test_setting_does_not_touch_the_database(self):
        """
        The whole reason position lives in memory.

        Every .db assignment is a pickle and a commit, and a vessel under way
        moves constantly. Writing through would make sailing the most expensive
        thing the server does.

        """
        self.hull.maritime_position = self.at_sea
        self.assertIsNone(self.hull.db.maritime_position)

    def test_reads_the_live_value_before_the_saved_one(self):
        self.hull.maritime_position = self.at_sea
        self.hull.checkpoint()
        moved = WorldPosition(1.0, 2.0)
        self.hull.maritime_position = moved
        self.assertEqual(self.hull.maritime_position, moved)

    def test_falls_back_to_the_saved_value(self):
        """After a restart there is no live value, only what was checkpointed."""
        self.hull.maritime_position = self.at_sea
        self.hull.checkpoint()
        self.hull.ndb.maritime_position = None
        self.assertEqual(self.hull.maritime_position, self.at_sea)


class TestVesselHeading(VesselTestCase):
    """Which way she is pointing."""

    def test_starts_at_north(self):
        self.assertEqual(self.hull.heading, 0.0)

    def test_accepts_a_heading(self):
        self.hull.heading = 72.0
        self.assertEqual(self.hull.heading, 72.0)

    def test_wraps_out_of_range_headings(self):
        self.hull.heading = 400.0
        self.assertEqual(self.hull.heading, 40.0)

    def test_wraps_negative_headings(self):
        self.hull.heading = -90.0
        self.assertEqual(self.hull.heading, 270.0)


class TestCheckpoint(VesselTestCase):
    """Explicit persistence."""

    def test_writes_the_position(self):
        self.hull.maritime_position = self.at_sea
        self.hull.checkpoint()
        self.assertEqual(self.hull.db.maritime_position, self.at_sea)

    def test_writes_the_heading(self):
        self.hull.heading = 72.0
        self.hull.checkpoint()
        self.assertEqual(self.hull.db.heading, 72.0)

    def test_reports_that_it_saved(self):
        self.hull.maritime_position = self.at_sea
        self.assertTrue(self.hull.checkpoint())

    def test_skips_when_nothing_moved(self):
        """
        Re-saving an unchanged value still costs a pickle and a commit.

        A fleet at anchor would otherwise pay that on every checkpoint.

        """
        self.hull.maritime_position = self.at_sea
        self.hull.checkpoint()
        self.assertFalse(self.hull.checkpoint())

    def test_becomes_dirty_again_after_moving(self):
        self.hull.maritime_position = self.at_sea
        self.hull.checkpoint()
        self.hull.maritime_position = WorldPosition(1.0, 1.0)
        self.assertTrue(self.hull.checkpoint())

    def test_reload_hook_flushes(self):
        self.hull.maritime_position = self.at_sea
        self.hull.at_server_reload()
        self.assertEqual(self.hull.db.maritime_position, self.at_sea)

    def test_shutdown_hook_flushes(self):
        self.hull.maritime_position = self.at_sea
        self.hull.at_server_shutdown()
        self.assertEqual(self.hull.db.maritime_position, self.at_sea)

    def test_survives_a_simulated_restart(self):
        """
        The acceptance criterion for this phase.

        Checkpoint, discard everything held in memory as a restart would, and
        the vessel still knows where she is.

        """
        self.hull.maritime_position = self.at_sea
        self.hull.heading = 72.0
        self.hull.at_server_shutdown()

        self.hull.ndb.maritime_position = None
        self.hull.ndb.heading = None
        self.hull.ndb.maritime_dirty = None

        self.assertEqual(self.hull.maritime_position, self.at_sea)
        self.assertEqual(self.hull.heading, 72.0)


class TestShipRoom(VesselTestCase):
    """Compartments."""

    def test_names_its_vessel_as_position_source(self):
        self.assertIs(self.cabin.maritime_position_source, self.hull)

    def test_defaults_to_the_main_deck(self):
        self.assertEqual(self.cabin.deck_level, MAIN_DECK)

    def test_defaults_to_interior(self):
        self.assertEqual(self.cabin.exposure, INTERIOR)

    def test_deck_level_is_settable(self):
        self.cabin.deck_level = -1
        self.assertEqual(self.cabin.deck_level, -1)

    def test_exposure_is_settable(self):
        self.cabin.exposure = OPEN
        self.assertEqual(self.cabin.exposure, OPEN)

    def test_rejects_unknown_exposure(self):
        """
        An unknown value would silently exclude the room from weather and
        flooding, which looks like those systems failing.

        """
        with self.assertRaises(ValueError):
            self.cabin.exposure = "breezy"

    def test_room_holds_no_position_of_its_own(self):
        self.assertFalse(hasattr(self.cabin, "maritime_position"))


class TestResolutionThroughTheHull(VesselTestCase):
    """The relationship this phase exists to establish."""

    def test_compartment_resolves_to_the_hull(self):
        self.hull.maritime_position = self.at_sea
        self.assertEqual(get_world_position(self.cabin), self.at_sea)

    def test_character_aboard_resolves_to_the_hull(self):
        """A character knows nothing about ships and still resolves correctly."""
        self.hull.maritime_position = self.at_sea
        self.char1.location = self.cabin
        self.assertEqual(get_world_position(self.char1), self.at_sea)

    def test_moving_the_hull_moves_everyone_aboard(self):
        """
        Nobody aboard stores a coordinate, so a hundred people cost nothing
        extra to move.

        """
        self.hull.maritime_position = self.at_sea
        self.char1.location = self.cabin
        self.hull.maritime_position = WorldPosition(20000.0, 10000.0)
        self.assertEqual(get_world_position(self.char1).x, 20000.0)

    def test_unpositioned_hull_leaves_occupants_nowhere(self):
        self.char1.location = self.cabin
        self.assertIs(get_world_position(self.char1), NoWorldPosition)


class TestVesselInterior(VesselTestCase):
    """A vessel knows its own compartments."""

    def test_finds_its_rooms(self):
        self.assertIn(self.cabin, self.hull.ship_rooms)

    def test_excludes_other_vessels_rooms(self):
        other_hull = create.create_object(Vessel, key="Other Sloop")
        other_room = create.create_object(ShipRoom, key="Other Cabin")
        other_room.db.vessel = other_hull
        self.assertNotIn(other_room, self.hull.ship_rooms)

    def test_orders_rooms_lowest_deck_first(self):
        hold = create.create_object(ShipRoom, key="Cargo Hold")
        hold.db.vessel = self.hull
        hold.deck_level = -1
        bilge = create.create_object(ShipRoom, key="Bilge")
        bilge.db.vessel = self.hull
        bilge.deck_level = -2
        bilge.exposure = BELOW_WATERLINE
        levels = [room.deck_level for room in self.hull.ship_rooms]
        self.assertEqual(levels, sorted(levels))
        self.assertEqual(levels[0], -2)
