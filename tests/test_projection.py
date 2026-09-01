"""
Tests for the projected ocean - the pool of rooms lent to occupied water.

These touch the database, so they use the object-creating test base.

"""

from django.test import override_settings
from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest

from ..position import WorldPosition
from ..projection import CELL_SIZE, OceanProjection, OceanRoom, cell_centre
from ..resolver import get_world_position
from ..typeclasses import Flotsam
from .base import EmptySeaMixin


class SmallerOcean(OceanRoom):
    """A pool room built from a different class, to prove the pool is not typeclass-bound."""


class ProjectionTestCase(EmptySeaMixin, BaseEvenniaTest):
    """Shared setup: one projection, and a cask to put in the water."""

    def setUp(self):
        super().setUp()
        self.sea = OceanProjection()
        self.cask = create.create_object(Flotsam, key="a cask")
        # Deliberately not the centre of its cell, so a test can tell the
        # difference between a swimmer's own position and the room's.
        self.here = WorldPosition(230.0, 310.0)
        self.far = WorldPosition(9250.0, 350.0)


class TestCellCentre(ProjectionTestCase):
    """Where a room stands in for its cell."""

    def test_the_middle_not_the_corner(self):
        centre = cell_centre(("default", 2, 3), 100.0)
        self.assertAlmostEqual(centre.x, 250.0)
        self.assertAlmostEqual(centre.y, 350.0)

    def test_it_sits_at_the_datum(self):
        self.assertEqual(cell_centre(("default", 0, 0), 100.0).z, 0.0)

    def test_it_keeps_the_region(self):
        self.assertEqual(cell_centre(("north", 0, 0), 100.0).region, "north")


class TestLendingRooms(ProjectionTestCase):
    """Rooms are lent to cells and taken back."""

    def test_a_new_cell_gets_a_room(self):
        room = self.sea.room_for(("default", 2, 3))
        self.assertEqual(tuple(room.showing), ("default", 2, 3))

    def test_the_same_cell_gets_the_same_room(self):
        first = self.sea.room_for(("default", 2, 3))
        self.assertEqual(self.sea.room_for(("default", 2, 3)), first)

    def test_a_second_occupied_cell_gets_a_second_room(self):
        first = self.sea.room_for(("default", 2, 3))
        self.cask.move_to(first, quiet=True, move_hooks=False)
        second = self.sea.room_for(("default", 90, 3))
        self.assertNotEqual(second, first)

    def test_a_free_room_is_reused_rather_than_a_new_one_built(self):
        """The pool is bounded by simultaneously occupied cells, not by the sea."""
        first = self.sea.room_for(("default", 2, 3))
        self.assertTrue(self.sea.release(first))
        self.assertEqual(self.sea.room_for(("default", 90, 3)), first)
        self.assertEqual(len(self.sea.pool()), 1)

    def test_the_pool_is_found_by_tag_not_by_typeclass(self):
        """A room built from a subclass is still in the pool - see the module docstring."""
        room = create.create_object(SmallerOcean, key="Open water")
        self.assertIn(room, self.sea.pool())

    def test_a_projection_built_later_sees_the_same_lending(self):
        """Nothing is held in memory, so two projections cannot disagree."""
        room = self.sea.room_for(("default", 2, 3))
        self.assertEqual(OceanProjection().room_showing(("default", 2, 3)), room)

    def test_a_zero_cell_size_is_refused(self):
        with self.assertRaises(ValueError):
            OceanProjection(cell_size=0.0)

    def test_a_negative_cell_size_is_refused(self):
        with self.assertRaises(ValueError):
            OceanProjection(cell_size=-100.0)


class TestReleasing(ProjectionTestCase):
    """Taking a room back."""

    def test_an_empty_room_is_released(self):
        room = self.sea.room_for(("default", 2, 3))
        self.assertTrue(self.sea.release(room))
        self.assertIsNone(room.showing)

    def test_an_occupied_room_is_not(self):
        room = self.sea.room_for(("default", 2, 3))
        self.cask.move_to(room, quiet=True, move_hooks=False)
        self.assertFalse(self.sea.release(room))
        self.assertIsNotNone(room.showing)

    def test_sweep_frees_rooms_nobody_is_in(self):
        self.sea.room_for(("default", 2, 3))
        self.sea.room_for(("default", 90, 3))
        self.assertEqual(self.sea.sweep(), 2)

    def test_sweep_leaves_occupied_rooms_alone(self):
        room = self.sea.room_for(("default", 2, 3))
        self.cask.move_to(room, quiet=True, move_hooks=False)
        self.assertEqual(self.sea.sweep(), 0)


class TestPlacing(ProjectionTestCase):
    """Putting things in the water they are actually in."""

    def test_it_lands_in_a_room_showing_its_own_cell(self):
        self.cask.maritime_position = self.here
        room = self.sea.place(self.cask)
        self.assertEqual(self.cask.location, room)
        self.assertEqual(tuple(room.showing), self.sea.cell_for(self.here))

    def test_something_with_no_position_is_not_in_the_sea(self):
        self.assertIsNone(self.sea.place(self.cask))

    def test_placing_twice_in_one_cell_does_not_move_it(self):
        """Almost every tick. Moving it would fire every arrival hook for nothing."""
        self.cask.maritime_position = self.here
        room = self.sea.place(self.cask)
        again = self.sea.place(self.cask, WorldPosition(self.here.x + 1.0, self.here.y))
        self.assertEqual(again, room)
        self.assertEqual(len(self.sea.pool()), 1)

    def test_a_lone_drifter_keeps_its_room_and_the_room_pans(self):
        """Nobody else is looking through it, so the view moves rather than the swimmer."""
        self.cask.maritime_position = self.here
        first = self.sea.place(self.cask)
        second = self.sea.place(self.cask, self.far)
        self.assertEqual(second, first)
        self.assertEqual(tuple(second.showing), self.sea.cell_for(self.far))

    def test_it_moves_out_rather_than_dragging_company_along(self):
        """Panning a room somebody else is in would carry them across the sea with it."""
        spar = create.create_object(Flotsam, key="a spar")
        self.cask.maritime_position = self.here
        first = self.sea.place(self.cask)
        spar.move_to(first, quiet=True, move_hooks=False)
        second = self.sea.place(self.cask, self.far)
        self.assertNotEqual(second, first)
        self.assertEqual(tuple(first.showing), self.sea.cell_for(self.here))

    def test_two_drifters_converging_end_up_in_one_room(self):
        """Two rooms showing one cell would put them in the same water, unable to see it."""
        spar = create.create_object(Flotsam, key="a spar")
        self.sea.overboard(spar, self.far)
        self.sea.overboard(self.cask, self.here)
        self.assertEqual(self.sea.place(self.cask, self.far).id, spar.location.id)

    def test_the_room_left_behind_is_released(self):
        spar = create.create_object(Flotsam, key="a spar")
        self.sea.overboard(spar, self.far)
        self.sea.overboard(self.cask, self.here)
        vacated = self.cask.location
        self.sea.place(self.cask, self.far)
        self.assertIsNone(vacated.showing)

    def test_the_pool_does_not_grow_as_it_drifts(self):
        """One thing drifting across a hundred cells still needs exactly one room."""
        for step in range(20):
            self.sea.place(self.cask, WorldPosition(250.0 + step * CELL_SIZE, 350.0))
        self.assertEqual(len(self.sea.pool()), 1)


class TestOverboardAndRecovery(ProjectionTestCase):
    """Going in, and coming out."""

    def test_overboard_puts_it_in_the_right_water(self):
        room = self.sea.overboard(self.cask, self.here)
        self.assertEqual(self.cask.maritime_position, self.here)
        self.assertEqual(tuple(room.showing), self.sea.cell_for(self.here))

    def test_two_things_overboard_in_different_places_do_not_share_a_room(self):
        """The position is set before placing, so the second does not inherit the first."""
        spar = create.create_object(Flotsam, key="a spar")
        first = self.sea.overboard(self.cask, self.here)
        second = self.sea.overboard(spar, self.far)
        self.assertNotEqual(first, second)

    def test_recovery_clears_the_position(self):
        deck = create.create_object("evennia.objects.objects.DefaultRoom", key="Deck")
        self.sea.overboard(self.cask, self.here)
        self.sea.recover(self.cask, deck)
        self.assertIsNone(self.cask.maritime_position)
        self.assertEqual(self.cask.location, deck)

    def test_recovery_releases_the_water(self):
        deck = create.create_object("evennia.objects.objects.DefaultRoom", key="Deck")
        room = self.sea.overboard(self.cask, self.here)
        self.sea.recover(self.cask, deck)
        self.assertIsNone(room.showing)


class TestTheRoomIsAView(ProjectionTestCase):
    """
    The one thing that separates this from a wilderness.

    Notes:
        In Evennia's `wilderness` contrib the room *is* where you are, so
        recycling one has to preserve its contents and its own docstring warns
        that anything left behind ends up with `location = None`. Here the truth
        is the position, held on the thing in the water. These tests are the
        proof that releasing a room therefore costs nothing.

    """

    def test_a_swimmer_resolves_to_its_own_position_not_the_rooms(self):
        """The room is a hundred metres wide. The sea does not round off."""
        self.sea.overboard(self.cask, self.here)
        self.assertEqual(get_world_position(self.cask), self.here)
        self.assertNotEqual(self.cask.location.maritime_position, self.here)

    def test_a_released_room_gives_the_same_water_back(self):
        room = self.sea.overboard(self.cask, self.here)
        self.cask.move_to(None, quiet=True, move_hooks=False, to_none=True)
        self.assertTrue(self.sea.release(room))
        self.assertEqual(self.sea.place(self.cask), room)
        self.assertEqual(self.cask.maritime_position, self.here)

    def test_a_recycled_room_does_not_take_the_position_with_it(self):
        room = self.sea.overboard(self.cask, self.here)
        self.cask.move_to(None, quiet=True, move_hooks=False, to_none=True)
        self.sea.release(room)
        self.sea.room_for(("default", 500, 500))
        self.assertEqual(self.cask.maritime_position, self.here)

    def test_an_empty_room_has_no_position_at_all(self):
        room = self.sea.room_for(("default", 2, 3))
        self.sea.release(room)
        self.assertIsNone(room.maritime_position)


class TestDrifting(ProjectionTestCase):
    """A floating thing on the simulation tick."""

    def test_still_water_moves_nothing(self):
        self.sea.overboard(self.cask, self.here)
        self.assertFalse(self.cask.at_maritime_tick(600.0))

    @override_settings(MARITIME_CURRENT_SET=90.0, MARITIME_CURRENT_DRIFT=1.0)
    def test_a_stream_carries_it(self):
        self.sea.overboard(self.cask, self.here)
        self.assertTrue(self.cask.at_maritime_tick(60.0))
        self.assertAlmostEqual(self.cask.maritime_position.x, self.here.x + 60.0, places=3)

    @override_settings(MARITIME_CURRENT_SET=90.0, MARITIME_CURRENT_DRIFT=1.0)
    def test_it_ends_up_in_the_room_showing_its_new_water(self):
        self.sea.overboard(self.cask, self.here)
        self.cask.at_maritime_tick(600.0)
        self.assertEqual(
            tuple(self.cask.location.showing),
            self.sea.cell_for(self.cask.maritime_position),
        )

    def test_something_not_in_the_water_does_not_drift(self):
        self.assertFalse(self.cask.at_maritime_tick(600.0))

    @override_settings(MARITIME_CURRENT_SET=90.0, MARITIME_CURRENT_DRIFT=1.0)
    def test_the_checkpoint_writes_the_drifted_position(self):
        self.sea.overboard(self.cask, self.here)
        self.cask.at_maritime_tick(60.0)
        self.assertTrue(self.cask.checkpoint())
        self.assertEqual(self.cask.db.maritime_position, self.cask.ndb.maritime_position)

    def test_the_checkpoint_writes_nothing_when_it_has_not_moved(self):
        self.sea.overboard(self.cask, self.here)
        self.cask.checkpoint()
        self.assertFalse(self.cask.checkpoint())


class TestFloatingProperties(ProjectionTestCase):
    """Windage and buoyancy, as stored."""

    def test_windage_is_settable(self):
        self.cask.windage = 0.25
        self.assertAlmostEqual(self.cask.windage, 0.25)

    def test_windage_above_one_is_refused(self):
        """Above 1 it would outrun the wind pushing it."""
        with self.assertRaises(ValueError):
            self.cask.windage = 1.5

    def test_windage_below_zero_is_refused(self):
        with self.assertRaises(ValueError):
            self.cask.windage = -0.1

    def test_a_position_that_is_not_one_is_refused(self):
        with self.assertRaises(TypeError):
            self.cask.maritime_position = (1.0, 2.0)

    def test_none_takes_it_out_of_the_water(self):
        self.cask.maritime_position = self.here
        self.cask.maritime_position = None
        self.assertIsNone(self.cask.maritime_position)

    def test_a_buoyancy_that_is_not_one_is_refused(self):
        with self.assertRaises(TypeError):
            self.cask.buoyancy = "floats"
