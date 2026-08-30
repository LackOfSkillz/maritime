"""
Tests for things in the water that are not ships.

"""

from evennia.utils.test_resources import BaseEvenniaTestCase

from ..currents import CurrentVector
from ..floating import (
    BARREL_WINDAGE,
    RAFT_WINDAGE,
    SWIMMER_WINDAGE,
    Buoyancy,
    cell_of,
    drift,
    separation,
    sinking_depth,
    wind_drift,
)
from ..position import WorldPosition
from ..sailing import WindVector

HERE = WorldPosition(1000.0, 1000.0)
STILL = CurrentVector(set=0.0, drift=0.0)
NO_WIND = WindVector(bearing=0.0, speed=0.0)

# A northerly: blowing *from* the north, so it pushes things south.
NORTHERLY = WindVector(bearing=0.0, speed=10.0)


class TestWindDrift(BaseEvenniaTestCase):
    """The wind pushes floating things downwind, not upwind."""

    def test_pushes_the_way_the_wind_is_going(self):
        bearing, _speed = wind_drift(NORTHERLY, RAFT_WINDAGE)
        self.assertAlmostEqual(bearing, 180.0)

    def test_speed_is_the_windage_fraction(self):
        _bearing, speed = wind_drift(NORTHERLY, 0.05)
        self.assertAlmostEqual(speed, 0.5)

    def test_negative_windage_pushes_nothing(self):
        _bearing, speed = wind_drift(NORTHERLY, -1.0)
        self.assertEqual(speed, 0.0)


class TestDrift(BaseEvenniaTestCase):
    """Where the sea takes something."""

    def test_still_water_and_no_wind_moves_nothing(self):
        self.assertEqual(drift(HERE, STILL, NO_WIND, RAFT_WINDAGE, 600.0), HERE)

    def test_a_northerly_carries_it_south(self):
        after = drift(HERE, STILL, NORTHERLY, 0.05, 100.0)
        self.assertAlmostEqual(after.y, HERE.y - 50.0, places=3)
        self.assertAlmostEqual(after.x, HERE.x, places=3)

    def test_the_current_carries_it_whatever_its_windage(self):
        """The water is the water. A swimmer and a raft go with it alike."""
        stream = CurrentVector(set=90.0, drift=1.0)
        swimmer = drift(HERE, stream, NO_WIND, SWIMMER_WINDAGE, 60.0)
        raft = drift(HERE, stream, NO_WIND, RAFT_WINDAGE, 60.0)
        self.assertAlmostEqual(swimmer.x, raft.x, places=6)

    def test_windage_separates_them(self):
        """A raft outruns a swimmer downwind, which is why searches widen."""
        swimmer = drift(HERE, STILL, NORTHERLY, SWIMMER_WINDAGE, 600.0)
        raft = drift(HERE, STILL, NORTHERLY, RAFT_WINDAGE, 600.0)
        self.assertLess(raft.y, swimmer.y)

    def test_no_elapsed_time_moves_nothing(self):
        self.assertEqual(drift(HERE, CurrentVector(90.0, 2.0), NORTHERLY, 0.5, 0.0), HERE)

    def test_zero_windage_leaves_only_the_current(self):
        stream = CurrentVector(set=90.0, drift=1.0)
        with_wind = drift(HERE, stream, NORTHERLY, 0.0, 60.0)
        without = drift(HERE, stream, NO_WIND, 0.0, 60.0)
        self.assertEqual(with_wind, without)


class TestSeparation(BaseEvenniaTestCase):
    """How far apart two floating things get."""

    def test_matches_what_drift_actually_does(self):
        first = drift(HERE, STILL, NORTHERLY, SWIMMER_WINDAGE, 600.0)
        second = drift(HERE, STILL, NORTHERLY, BARREL_WINDAGE, 600.0)
        predicted = separation(SWIMMER_WINDAGE, BARREL_WINDAGE, NORTHERLY, 600.0)
        self.assertAlmostEqual(first.horizontal_distance_to(second), predicted, places=3)

    def test_order_does_not_matter(self):
        self.assertEqual(
            separation(SWIMMER_WINDAGE, RAFT_WINDAGE, NORTHERLY, 60.0),
            separation(RAFT_WINDAGE, SWIMMER_WINDAGE, NORTHERLY, 60.0),
        )

    def test_equal_windage_never_separates(self):
        self.assertEqual(separation(RAFT_WINDAGE, RAFT_WINDAGE, NORTHERLY, 3600.0), 0.0)

    def test_no_wind_never_separates(self):
        """The current cancels, so with no wind there is nothing left to separate them."""
        self.assertEqual(separation(SWIMMER_WINDAGE, RAFT_WINDAGE, NO_WIND, 3600.0), 0.0)


class TestSinking(BaseEvenniaTestCase):
    """What happens to something that has stopped floating."""

    def test_something_that_floats_never_goes_down(self):
        self.assertEqual(sinking_depth(0.0, 600.0, Buoyancy(floats=True, sink_rate=1.0), 50.0), 0.0)

    def test_it_goes_down_at_its_own_rate(self):
        self.assertAlmostEqual(
            sinking_depth(0.0, 10.0, Buoyancy(floats=False, sink_rate=0.5), 50.0), 5.0
        )

    def test_it_stops_at_the_seabed(self):
        self.assertAlmostEqual(
            sinking_depth(0.0, 10000.0, Buoyancy(floats=False, sink_rate=0.5), 50.0), 50.0
        )

    def test_a_zero_rate_never_goes_down(self):
        self.assertEqual(sinking_depth(0.0, 600.0, Buoyancy(floats=False), 50.0), 0.0)


class TestCells(BaseEvenniaTestCase):
    """Which square of water a position falls in."""

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
