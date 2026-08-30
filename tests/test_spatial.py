"""
Tests for the spatial indexes, and for the grid they share the file with.

"""

from evennia.utils.test_resources import BaseEvenniaTestCase

from ..position import WorldPosition
from ..spatial import (
    ContactIndex,
    ProximityIndex,
    SpatialIndex,
    cell_bounds,
    cell_centre,
    cell_of,
    cells_touching,
    distance_to_track,
    nearest_on_track,
    track_entry,
)


class TestSpatialIndexBase(BaseEvenniaTestCase):
    """The base refuses to guess how it measures."""

    def test_distance_is_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            SpatialIndex()._distance(WorldPosition(0.0, 0.0), WorldPosition(1.0, 1.0))


class TestTracking(BaseEvenniaTestCase):
    """Insert, move, remove."""

    def setUp(self):
        super().setUp()
        self.index = ContactIndex()
        self.here = WorldPosition(0.0, 0.0)

    def test_starts_empty(self):
        self.assertEqual(len(self.index), 0)

    def test_insert_tracks_an_entity(self):
        self.index.insert("gull", self.here)
        self.assertIn("gull", self.index)

    def test_insert_records_the_position(self):
        self.index.insert("gull", self.here)
        self.assertEqual(self.index.position_of("gull"), self.here)

    def test_insert_is_idempotent(self):
        self.index.insert("gull", self.here).insert("gull", self.here)
        self.assertEqual(len(self.index), 1)

    def test_insert_replaces_the_position(self):
        moved = WorldPosition(100.0, 0.0)
        self.index.insert("gull", self.here).insert("gull", moved)
        self.assertEqual(self.index.position_of("gull"), moved)

    def test_insert_rejects_a_non_position(self):
        """A tuple would work today and break once the structure changes."""
        with self.assertRaises(TypeError):
            self.index.insert("gull", (0.0, 0.0))

    def test_move_updates_the_position(self):
        self.index.insert("gull", self.here)
        self.index.move("gull", WorldPosition(50.0, 0.0))
        self.assertEqual(self.index.position_of("gull").x, 50.0)

    def test_move_refuses_an_untracked_entity(self):
        """
        Silently inserting would turn a forgotten insert into an index that
        looks correct while missing everything that never moved.

        """
        with self.assertRaises(KeyError):
            self.index.move("ghost", self.here)

    def test_remove_reports_it_was_present(self):
        self.index.insert("gull", self.here)
        self.assertTrue(self.index.remove("gull"))

    def test_remove_stops_tracking(self):
        self.index.insert("gull", self.here)
        self.index.remove("gull")
        self.assertNotIn("gull", self.index)

    def test_removing_something_absent_is_not_an_error(self):
        """A vessel sinking twice in one tick is a real sequence."""
        self.assertFalse(self.index.remove("never-there"))

    def test_position_of_untracked_is_none(self):
        self.assertIsNone(self.index.position_of("ghost"))

    def test_clear_drops_everything(self):
        self.index.insert("a", self.here).insert("b", self.here)
        self.index.clear()
        self.assertEqual(len(self.index), 0)

    def test_repr_reports_the_count(self):
        self.index.insert("gull", self.here)
        self.assertIn("1", repr(self.index))


class TestRadiusSearch(BaseEvenniaTestCase):
    """Finding candidates."""

    def setUp(self):
        super().setUp()
        self.index = ContactIndex()
        self.origin = WorldPosition(0.0, 0.0)
        self.index.insert("close", WorldPosition(100.0, 0.0))
        self.index.insert("middle", WorldPosition(500.0, 0.0))
        self.index.insert("far", WorldPosition(5000.0, 0.0))

    def test_finds_within_radius(self):
        self.assertEqual(set(self.index.near(self.origin, 600.0)), {"close", "middle"})

    def test_excludes_beyond_radius(self):
        self.assertNotIn("far", self.index.near(self.origin, 600.0))

    def test_includes_exactly_at_the_radius(self):
        self.assertIn("close", self.index.near(self.origin, 100.0))

    def test_orders_nearest_first(self):
        self.assertEqual(self.index.near(self.origin, 10000.0), ("close", "middle", "far"))

    def test_zero_radius_finds_only_coincident(self):
        self.index.insert("here", self.origin)
        self.assertEqual(self.index.near(self.origin, 0.0), ("here",))

    def test_negative_radius_is_refused(self):
        with self.assertRaises(ValueError):
            self.index.near(self.origin, -1.0)

    def test_empty_index_returns_nothing(self):
        self.assertEqual(ContactIndex().near(self.origin, 1000.0), ())

    def test_returns_a_tuple(self):
        """Candidates are a snapshot, not a live view of the index."""
        self.assertIsInstance(self.index.near(self.origin, 1000.0), tuple)


class TestRegionIsolation(BaseEvenniaTestCase):
    """Regions are separate coordinate spaces."""

    def test_other_regions_are_not_candidates(self):
        """
        A lake and an ocean may hold the same coordinates without those points
        being anywhere near each other.

        """
        index = ContactIndex()
        index.insert("on the lake", WorldPosition(0.0, 0.0, region="lake"))
        self.assertEqual(index.near(WorldPosition(0.0, 0.0), 10000.0), ())

    def test_same_region_is_found(self):
        index = ContactIndex()
        index.insert("on the lake", WorldPosition(0.0, 0.0, region="lake"))
        found = index.near(WorldPosition(0.0, 0.0, region="lake"), 10.0)
        self.assertEqual(found, ("on the lake",))

    def test_cross_region_search_does_not_raise(self):
        """
        Positions refuse cross-region comparison, so the index must filter
        before measuring rather than letting the exception escape.

        """
        index = ContactIndex()
        index.insert("elsewhere", WorldPosition(0.0, 0.0, region="lake"))
        index.insert("here", WorldPosition(10.0, 0.0))
        self.assertEqual(index.near(WorldPosition(0.0, 0.0), 100.0), ("here",))


class TestIndexGeometryDiffers(BaseEvenniaTestCase):
    """The two indexes measure different things, and that is the point."""

    def setUp(self):
        super().setUp()
        self.hull = WorldPosition(0.0, 0.0, 0.0)
        self.diver = WorldPosition(0.0, 0.0, -30.0)

    def test_contact_index_ignores_depth(self):
        """Horizon range is a surface question."""
        index = ContactIndex()
        index.insert("diver", self.diver)
        self.assertEqual(index.near(self.hull, 1.0), ("diver",))

    def test_proximity_index_respects_depth(self):
        """A diver thirty metres down cannot be boarded from the deck."""
        index = ProximityIndex()
        index.insert("diver", self.diver)
        self.assertEqual(index.near(self.hull, 1.0), ())

    def test_proximity_index_finds_within_true_range(self):
        index = ProximityIndex()
        index.insert("diver", self.diver)
        self.assertEqual(index.near(self.hull, 40.0), ("diver",))

    def test_the_same_entities_give_different_answers(self):
        """
        One measure cannot serve both questions - the reason there are two
        indexes rather than one with a tuning parameter.

        """
        contacts, proximity = ContactIndex(), ProximityIndex()
        for index in (contacts, proximity):
            index.insert("diver", self.diver)
        self.assertNotEqual(contacts.near(self.hull, 5.0), proximity.near(self.hull, 5.0))


class TestSharedBehaviour(BaseEvenniaTestCase):
    """Both indexes share the tracking contract."""

    def test_proximity_index_tracks_like_contact_index(self):
        index = ProximityIndex()
        index.insert("a", WorldPosition(0.0, 0.0, 0.0))
        index.move("a", WorldPosition(0.0, 0.0, -10.0))
        self.assertEqual(index.position_of("a").z, -10.0)

    def test_proximity_index_orders_nearest_first(self):
        index = ProximityIndex()
        index.insert("deep", WorldPosition(0.0, 0.0, -100.0))
        index.insert("shallow", WorldPosition(0.0, 0.0, -5.0))
        origin = WorldPosition(0.0, 0.0, 0.0)
        self.assertEqual(index.near(origin, 200.0), ("shallow", "deep"))


class TestCells(BaseEvenniaTestCase):
    """Which square of the world a position falls in."""

    def test_a_position_inside_a_cell(self):
        self.assertEqual(cell_of(WorldPosition(250.0, 350.0), 100.0), ("default", 2, 3))

    def test_the_lower_edge_belongs_to_its_own_cell(self):
        self.assertEqual(cell_of(WorldPosition(200.0, 300.0), 100.0), ("default", 2, 3))

    def test_negative_coordinates_floor_rather_than_truncate(self):
        """Truncation would make the two cells either side of zero share an index."""
        self.assertEqual(cell_of(WorldPosition(-50.0, -150.0), 100.0), ("default", -1, -2))

    def test_either_side_of_zero_are_different_cells(self):
        self.assertNotEqual(
            cell_of(WorldPosition(-1.0, 0.0), 100.0),
            cell_of(WorldPosition(1.0, 0.0), 100.0),
        )

    def test_regions_are_separate_grids(self):
        self.assertNotEqual(
            cell_of(WorldPosition(250.0, 350.0, region="north"), 100.0),
            cell_of(WorldPosition(250.0, 350.0, region="south"), 100.0),
        )


class TestCellGeometry(BaseEvenniaTestCase):
    """Where a cell is, and how big."""

    def test_the_centre_is_the_middle(self):
        centre = cell_centre(("default", 2, 3), 100.0)
        self.assertAlmostEqual(centre.x, 250.0)
        self.assertAlmostEqual(centre.y, 350.0)

    def test_the_centre_sits_at_the_datum(self):
        self.assertEqual(cell_centre(("default", 0, 0), 100.0).z, 0.0)

    def test_the_centre_keeps_the_region(self):
        self.assertEqual(cell_centre(("north", 0, 0), 100.0).region, "north")

    def test_the_bounds(self):
        self.assertEqual(cell_bounds(("default", 2, 3), 100.0), (200.0, 300.0, 300.0, 400.0))

    def test_negative_bounds(self):
        self.assertEqual(cell_bounds(("default", -1, -2), 100.0), (-100.0, -200.0, 0.0, -100.0))

    def test_a_centre_is_inside_its_own_cell(self):
        cell = ("default", 7, -4)
        self.assertEqual(cell_of(cell_centre(cell, 250.0), 250.0), cell)


class TestCellsTouching(BaseEvenniaTestCase):
    """Which squares a track passes through."""

    def test_a_track_inside_one_cell(self):
        cells = cells_touching(WorldPosition(10.0, 10.0), WorldPosition(20.0, 20.0), 100.0)
        self.assertEqual(cells, (("default", 0, 0),))

    def test_a_track_across_a_boundary(self):
        cells = cells_touching(WorldPosition(90.0, 10.0), WorldPosition(110.0, 10.0), 100.0)
        self.assertEqual(set(cells), {("default", 0, 0), ("default", 1, 0)})

    def test_a_diagonal_track_covers_the_box(self):
        cells = cells_touching(WorldPosition(90.0, 90.0), WorldPosition(110.0, 110.0), 100.0)
        self.assertEqual(len(cells), 4)

    def test_a_margin_widens_it(self):
        """Half a beam, when the track is a ship's."""
        narrow = cells_touching(WorldPosition(50.0, 95.0), WorldPosition(60.0, 95.0), 100.0)
        wide = cells_touching(
            WorldPosition(50.0, 95.0), WorldPosition(60.0, 95.0), 100.0, margin=20.0
        )
        self.assertEqual(len(narrow), 1)
        self.assertEqual(len(wide), 2)

    def test_a_track_of_no_length_is_still_one_cell(self):
        here = WorldPosition(50.0, 50.0)
        self.assertEqual(cells_touching(here, here, 100.0), (("default", 0, 0),))

    def test_two_regions_are_not_a_track(self):
        with self.assertRaises(ValueError):
            cells_touching(
                WorldPosition(0.0, 0.0, region="north"),
                WorldPosition(100.0, 0.0, region="south"),
                100.0,
            )


class TestDistanceToTrack(BaseEvenniaTestCase):
    """How close a track passes to something."""

    def setUp(self):
        super().setUp()
        self.before = WorldPosition(0.0, 0.0)
        self.after = WorldPosition(100.0, 0.0)

    def test_a_point_beside_the_middle(self):
        point = WorldPosition(50.0, 30.0)
        self.assertAlmostEqual(distance_to_track(point, self.before, self.after), 30.0)

    def test_a_point_on_the_track(self):
        self.assertAlmostEqual(
            distance_to_track(WorldPosition(50.0, 0.0), self.before, self.after), 0.0
        )

    def test_a_point_beyond_the_end_measures_to_the_end(self):
        """The segment, not the line through it - a rock astern is astern."""
        point = WorldPosition(200.0, 0.0)
        self.assertAlmostEqual(distance_to_track(point, self.before, self.after), 100.0)

    def test_a_point_behind_the_start(self):
        point = WorldPosition(-50.0, 0.0)
        self.assertAlmostEqual(distance_to_track(point, self.before, self.after), 50.0)

    def test_a_track_of_no_length_is_a_point(self):
        point = WorldPosition(30.0, 40.0)
        self.assertAlmostEqual(distance_to_track(point, self.before, self.before), 50.0)

    def test_the_nearest_place_on_it(self):
        nearest = nearest_on_track(WorldPosition(50.0, 30.0), self.before, self.after)
        self.assertAlmostEqual(nearest.x, 50.0)
        self.assertAlmostEqual(nearest.y, 0.0)

    def test_the_nearest_place_is_clamped_to_the_segment(self):
        nearest = nearest_on_track(WorldPosition(500.0, 0.0), self.before, self.after)
        self.assertAlmostEqual(nearest.x, 100.0)


class TestTrackEntry(BaseEvenniaTestCase):
    """Where a track first comes within reach of something."""

    def setUp(self):
        super().setUp()
        self.before = WorldPosition(0.0, 0.0)
        self.after = WorldPosition(100.0, 0.0)
        self.rock = WorldPosition(50.0, 0.0)

    def test_she_enters_before_she_is_abreast_of_it(self):
        """The whole reason this exists rather than closest approach."""
        entry = track_entry(self.rock, self.before, self.after, 10.0)
        self.assertAlmostEqual(entry.x, 40.0)

    def test_a_track_that_never_reaches_it(self):
        self.assertIsNone(track_entry(WorldPosition(50.0, 200.0), self.before, self.after, 10.0))

    def test_a_track_that_stops_short_of_it(self):
        self.assertIsNone(track_entry(WorldPosition(500.0, 0.0), self.before, self.after, 10.0))

    def test_already_inside_it_when_the_step_began(self):
        """She does not enter. She is there."""
        entry = track_entry(WorldPosition(5.0, 0.0), self.before, self.after, 10.0)
        self.assertEqual(entry, self.before)

    def test_a_glancing_track(self):
        entry = track_entry(WorldPosition(50.0, 9.0), self.before, self.after, 10.0)
        self.assertIsNotNone(entry)
        self.assertLess(entry.x, 50.0)

    def test_a_track_of_no_length_that_is_clear(self):
        self.assertIsNone(track_entry(self.rock, self.before, self.before, 10.0))

    def test_a_track_of_no_length_that_is_on_it(self):
        self.assertEqual(track_entry(self.rock, self.rock, self.rock, 10.0), self.rock)

    def test_the_entry_is_at_the_datum(self):
        self.assertEqual(track_entry(self.rock, self.before, self.after, 10.0).z, 0.0)
