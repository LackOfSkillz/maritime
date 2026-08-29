"""
Tests for the spatial indexes.

"""

from evennia.utils.test_resources import BaseEvenniaTestCase

from ..position import WorldPosition
from ..spatial import ContactIndex, ProximityIndex, SpatialIndex


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
