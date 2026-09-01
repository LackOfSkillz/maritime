"""
Tests for the remembered seabed.

A cache is the easiest thing in this codebase to get wrong in a way nothing notices. It has
three failure modes and only one of them is loud:

    it is slower          loud, and the least likely
    it never hits         silent - indistinguishable from no cache except in a profile
    it answers wrongly    silent, rare, and catastrophic

So the tests here are mostly about the two quiet ones. That a repeated question is not asked
of the world twice; that a question *near* a remembered one is not answered with it; and,
above all, that a chart drawn from a warm cache is the same chart as one drawn from a cold
one. A cache that changed what was on the paper would be a cache that moved the coastline,
and the report would be "the chart is different after I sail past twice".
"""

from evennia.utils.test_resources import BaseEvenniaTestCase

from .. import seabed
from ..bathymetry import MaritimeMapProvider
from ..position import WorldPosition


class Counted(MaritimeMapProvider):
    """A seabed that says how often it was asked, and gives every point its own depth."""

    def __init__(self):
        super().__init__()
        self.asked = []

    def terrain_z_at(self, position):
        self.asked.append((position.x, position.y))
        return -20.0 - position.x * 0.001 - position.y * 0.0007


class SeabedTestCase(BaseEvenniaTestCase):
    def setUp(self):
        super().setUp()
        seabed.forget()
        self.world = Counted()
        self.addCleanup(seabed.forget)


class TestItRemembers(SeabedTestCase):
    def test_the_same_point_is_asked_of_the_world_once(self):
        read = seabed.reader(self.world, 100.0)
        for _ in range(5):
            read(WorldPosition(400.0, 700.0))
        self.assertEqual(len(self.world.asked), 1)

    def test_and_gives_the_same_answer_every_time(self):
        read = seabed.reader(self.world, 100.0)
        answers = {read(WorldPosition(400.0, 700.0)) for _ in range(5)}
        self.assertEqual(len(answers), 1)

    def test_two_readers_on_one_world_share_what_they_know(self):
        """
        The whole point. Two captains are two readers, and if they did not share there
        would be no cache - only a per-sheet scratchpad, which is what the grid already is.

        """
        seabed.reader(self.world, 100.0)(WorldPosition(400.0, 700.0))
        seabed.reader(self.world, 100.0)(WorldPosition(400.0, 700.0))
        self.assertEqual(len(self.world.asked), 1)

    def test_different_worlds_do_not(self):
        other = Counted()
        seabed.reader(self.world, 100.0)(WorldPosition(400.0, 700.0))
        seabed.reader(other, 100.0)(WorldPosition(400.0, 700.0))
        self.assertEqual(len(self.world.asked), 1)
        self.assertEqual(len(other.asked), 1)

    def test_and_neither_do_two_lattices(self):
        """
        A hundred-metre lattice and a two-hundred-metre one are different questions about
        the same ground, and the answers are not interchangeable - the coarse one's points
        are a subset, but its *indices* mean something else entirely.

        """
        seabed.reader(self.world, 100.0)(WorldPosition(400.0, 800.0))
        seabed.reader(self.world, 200.0)(WorldPosition(400.0, 800.0))
        self.assertEqual(len(self.world.asked), 2)


class TestItAnswersHonestly(SeabedTestCase):
    """The quiet, catastrophic failure: a nearby answer offered as this one."""

    def test_a_point_off_the_lattice_is_not_given_a_neighbours_depth(self):
        read = seabed.reader(self.world, 100.0)
        on = read(WorldPosition(400.0, 700.0))
        near = read(WorldPosition(437.0, 700.0))
        self.assertNotEqual(on, near)
        self.assertEqual(near, self.world.terrain_z_at(WorldPosition(437.0, 700.0)))

    def test_and_is_not_remembered_as_one(self):
        """
        Filling the cache with points nothing will ask about twice would cost memory to
        buy nothing, and would evict the lattice points that are worth keeping.

        """
        read = seabed.reader(self.world, 100.0)
        for _ in range(3):
            read(WorldPosition(437.0, 700.0))
        self.assertEqual(len(self.world.asked), 3)

    def test_floating_point_slop_still_counts_as_on_the_lattice(self):
        """
        The bug this tolerance exists for. A caller that snapped its corner asks about
        `k * cell + column * cell`, which is not quite `(k + column) * cell` - so an exact
        test rejected three points in five, and the cache held four thousand soundings
        where it should have held nine. It looked like a cache and behaved like a
        two-times speedup instead of a twenty-times one.

        """
        cell = 20000.0 / 95.0
        corner = seabed.snap(-13735.0, cell)
        read = seabed.reader(self.world, cell)
        for column in range(20):
            read(WorldPosition(corner + column * cell, corner))
        before = len(self.world.asked)
        for column in range(20):
            read(WorldPosition(corner + column * cell, corner))
        self.assertEqual(len(self.world.asked), before, "the lattice points were not held")
        self.assertEqual(before, 20)


class TestSnapping(SeabedTestCase):
    def test_it_lands_on_a_multiple_of_the_cell(self):
        for value in (0.0, 51.0, 99.9, 100.0, 1234.5):
            snapped = seabed.snap(value, 100.0)
            self.assertAlmostEqual(snapped % 100.0, 0.0, places=6)
            self.assertLessEqual(snapped, value)

    def test_it_goes_down_on_the_far_side_of_the_origin_too(self):
        """
        `int()` truncates towards zero, so west and south of the origin it rounds *up* -
        which puts two lattices either side a half-cell out of step and loses every hit
        across the meridian. The failure is invisible except as a cache that mysteriously
        stops working in one half of the world.

        """
        self.assertEqual(seabed.snap(-51.0, 100.0), -100.0)
        self.assertEqual(seabed.snap(-100.0, 100.0), -100.0)
        self.assertEqual(seabed.snap(-101.0, 100.0), -200.0)

    def test_two_places_within_a_cell_snap_together(self):
        self.assertEqual(seabed.snap(1201.0, 100.0), seabed.snap(1299.0, 100.0))


class TestItIsBounded(SeabedTestCase):
    def test_it_stops_growing(self):
        """
        An unbounded cache of a planet is a memory leak with a good excuse. This is the
        one property that cannot be checked by reading the code.

        """
        from django.test import override_settings

        with override_settings(MARITIME_SOUNDING_CACHE=1000):
            read = seabed.reader(self.world, 100.0)
            for step in range(4000):
                read(WorldPosition(step * 100.0, 0.0))
        self.assertLessEqual(seabed.statistics()["held"], 1100)

    def test_forgetting_really_forgets(self):
        read = seabed.reader(self.world, 100.0)
        read(WorldPosition(400.0, 700.0))
        self.assertEqual(seabed.statistics()["held"], 1)
        seabed.forget()
        self.assertEqual(seabed.statistics()["held"], 0)
        seabed.reader(self.world, 100.0)(WorldPosition(400.0, 700.0))
        self.assertEqual(len(self.world.asked), 2)

    def test_it_reports_whether_it_is_working(self):
        """
        A cache that never hits is indistinguishable from no cache except in a profile, so
        it has to be able to say. Nobody would ever find this out otherwise.

        """
        read = seabed.reader(self.world, 100.0)
        read(WorldPosition(400.0, 700.0))
        read(WorldPosition(400.0, 700.0))
        report = seabed.statistics()
        self.assertEqual(report["hits"], 1)
        self.assertEqual(report["misses"], 1)
        self.assertAlmostEqual(report["hit_rate"], 0.5)


class TestTheChartIsTheSameEitherWay(BaseEvenniaTestCase):
    """
    The claim that matters most, and the one a cache is most likely to break quietly.

    A chart drawn from a warm cache must be the chart drawn from a cold one. Anything else
    is a coastline that moves when somebody else sails past, and the bug report would be
    unrepeatable by whoever received it.
    """

    def test_a_sounded_grid_is_identical_warm_and_cold(self):
        from ..charts import Chart
        from ..client import cartography

        world = Counted()
        chart = Chart(key="a sheet", west=-9e4, east=9e4, south=-9e4, north=9e4)

        seabed.forget()
        cold = cartography.sample(chart, world, 0.0, -2000.0, -2000.0, 4000.0, steps=32)
        warm = cartography.sample(chart, world, 0.0, -2000.0, -2000.0, 4000.0, steps=32)
        self.assertEqual(cold, warm)
        seabed.forget()

    def test_and_so_are_the_contours_traced_from_it(self):
        from ..charts import Chart
        from ..client import cartography

        world = Counted()
        chart = Chart(key="a sheet", west=-9e4, east=9e4, south=-9e4, north=9e4)

        seabed.forget()
        cold = cartography.sample(chart, world, 0.0, -2000.0, -2000.0, 4000.0, steps=32)
        cold_lines = cartography.contour(cold, -20.0, -2000.0, -2000.0, 4000.0)
        warm = cartography.sample(chart, world, 0.0, -2000.0, -2000.0, 4000.0, steps=32)
        warm_lines = cartography.contour(warm, -20.0, -2000.0, -2000.0, 4000.0)
        self.assertEqual(cold_lines, warm_lines)
        self.assertTrue(cold_lines, "nothing was contoured, so nothing was compared")
        seabed.forget()
