"""
Tests for the seabed written down.

A bake is a second copy of the world, and every failure here is a copy that disagrees with
the original. The disagreements are graded:

    a truncated file      read as a rectangle of very shoal water - every ship aground
    a foreign file        a coastline where there is open sea, looking like a generator bug
    a coarse quantisation contours that move, so the baked chart is not the unbaked one
    a stale rectangle     the last one, silently, for ever

None of those raises anything. All of them look like the world being wrong rather than the
file being wrong, which is why the checks are in the reader and not in the writer.

The one claim that needs stating carefully: a baked chart is **not** identical to an unbaked
one, and should not be. It is stored as integers, so it agrees to within half a unit - some
five millimetres, against a survey error the chart already carries of metres. Asserting
equality would be asserting that a lossy store is lossless, and the honest test is the bound.
"""

import os
import tempfile

from evennia.utils.test_resources import BaseEvenniaTestCase

from .. import bake, seabed
from ..bathymetry import MaritimeMapProvider
from ..position import WorldPosition


class Slope(MaritimeMapProvider):
    """Ground that is different at every point, so nothing agrees by accident."""

    def __init__(self, bias=0.0, deep=False):
        super().__init__()
        self.bias = bias
        self.deep = deep
        self.asked = 0

    def terrain_z_at(self, position):
        self.asked += 1
        ground = -20.0 - position.x * 0.001 - position.y * 0.0007 + self.bias
        return ground * (200.0 if self.deep else 1.0)


class BakeTestCase(BaseEvenniaTestCase):
    def setUp(self):
        super().setUp()
        seabed.forget()
        seabed.forget_baked()
        self.addCleanup(seabed.forget)
        self.addCleanup(seabed.forget_baked)
        self.world = Slope()
        self.where = tempfile.mkdtemp(prefix="maritime-bake-")

    def sound(self, world=None, cell=100.0, columns=24, rows=24):
        return bake.sound(world or self.world, -1000.0, -1000.0, cell, columns, rows)


class TestItSurvivesTheRoundTrip(BakeTestCase):
    def test_what_is_written_is_what_is_read(self):
        made = self.sound()
        path = os.path.join(self.where, "test.seabed")
        bake.write(path, made)
        back = bake.read(path)
        self.assertIsNotNone(back)
        for name in ("cell", "west", "south", "columns", "rows", "scale"):
            self.assertEqual(getattr(back, name), getattr(made, name), name)
        self.assertEqual(back.values, made.values)

    def test_and_answers_the_same_soundings(self):
        made = self.sound()
        path = os.path.join(self.where, "test.seabed")
        bake.write(path, made)
        back = bake.read(path)
        for column in range(0, 24, 5):
            x = -1000.0 + column * 100.0
            self.assertEqual(back.at(x, -1000.0), made.at(x, -1000.0))


class TestItAgreesWithTheWorld(BakeTestCase):
    def test_to_within_half_a_stored_unit(self):
        """
        The honest claim. Integers are lossy, so this is a bound and not an equality - and
        the bound is some five millimetres against a survey error of metres.

        """
        made = self.sound()
        truth = Slope()
        worst = 0.0
        for row in range(0, made.rows, 3):
            for column in range(0, made.columns, 3):
                x = made.west + column * made.cell
                y = made.south + row * made.cell
                worst = max(worst, abs(truth.terrain_z_at(WorldPosition(x, y)) - made.at(x, y)))
        self.assertLessEqual(worst, made.scale / 2.0 + 1e-9)

    def test_the_scale_is_chosen_from_the_ground_and_not_from_the_cell(self):
        """
        It was keyed to the cell size once, on the reasoning that coarse grids are for open
        ocean. That is a guess about geography rather than reasoning, and it stored whole
        metres for a shallow coast sounded at a kilometre - which moved every fathom line.

        """
        shallow = bake.sound(Slope(), -1000.0, -1000.0, 1000.0, 8, 8)
        deep = bake.sound(Slope(deep=True), -1000.0, -1000.0, 1000.0, 8, 8)
        self.assertEqual(shallow.cell, deep.cell)
        self.assertLess(shallow.scale, deep.scale)

    def test_a_shallow_coast_is_stored_to_the_centimetre(self):
        self.assertEqual(self.sound().scale, bake.FINEST_SCALE)

    def test_and_deep_water_still_fits(self):
        """A scale too fine for the range would overflow the short and wrap a trench into
        a mountain."""
        made = bake.sound(Slope(deep=True), -1000.0, -1000.0, 100.0, 16, 16)
        for value in made.values:
            self.assertGreater(value, bake.UNSOUNDED)


class TestABadFileIsRefused(BakeTestCase):
    """Refused, not raised. A bad bake is a thing a game starts without, having said so."""

    def test_something_that_is_not_a_bake_at_all(self):
        path = os.path.join(self.where, "rubbish.seabed")
        with open(path, "wb") as out:
            out.write(b"this is not a seabed")
        self.assertIsNone(bake.read(path))

    def test_a_full_length_file_that_is_not_ours(self):
        """
        The magic, tested on its own.

        A short scrap of nonsense is caught by the length check long before the magic is
        consulted, so it proves nothing about the magic - removing that check entirely left
        every test passing. What it guards against is a *plausible* file: the right size,
        the wrong format, and every one of its bytes read as depths.

        """
        made = self.sound()
        path = os.path.join(self.where, "foreign.seabed")
        bake.write(path, made)
        whole = bytearray(open(path, "rb").read())
        whole[0:8] = b"NOTOURS!"
        with open(path, "wb") as out:
            out.write(bytes(whole))
        self.assertIsNone(bake.read(path))

    def test_a_truncated_one(self):
        """
        The worst possible failure if it got through: a half-written rectangle reads as
        very shoal water, and every ship in the region goes aground on nothing.

        """
        made = self.sound()
        path = os.path.join(self.where, "short.seabed")
        bake.write(path, made)
        whole = open(path, "rb").read()
        with open(path, "wb") as out:
            out.write(whole[: len(whole) // 2])
        self.assertIsNone(bake.read(path))

    def test_one_that_is_not_there(self):
        self.assertIsNone(bake.read(os.path.join(self.where, "absent.seabed")))

    def test_a_bake_of_another_world_is_not_loaded(self):
        """
        A file from another seed describes another planet. Reading it would put a coastline
        where there is open water, which looks exactly like a bug in the generator and is
        very hard to recognise as a stale file.

        """
        bake.write(os.path.join(self.where, "other.seabed"), self.sound())
        loaded = bake.load(self.where, Slope(bias=500.0))
        self.assertEqual(loaded, ())

    def test_but_its_own_world_is(self):
        bake.write(os.path.join(self.where, "mine.seabed"), self.sound())
        self.assertEqual(len(bake.load(self.where, self.world)), 1)


class TestItIsAskedBeforeTheWorld(BakeTestCase):
    def test_a_baked_point_does_not_reach_the_world(self):
        made = self.sound()
        seabed.remember_baked(self.world, made)
        seabed.forget()

        asked = self.world.asked
        read = seabed.reader(self.world, 100.0)
        for column in range(10):
            read(WorldPosition(made.west + column * 100.0, made.south))
        self.assertEqual(self.world.asked, asked, "a baked sounding was asked of the world")

    def test_a_point_outside_it_falls_through(self):
        made = self.sound()
        seabed.remember_baked(self.world, made)
        seabed.forget()

        asked = self.world.asked
        seabed.reader(self.world, 100.0)(WorldPosition(500_000.0, 500_000.0))
        self.assertGreater(self.world.asked, asked, "a point off the bake was not sounded")

    def test_a_bake_at_another_spacing_is_not_used(self):
        """
        A rectangle sounded every hundred metres has nothing to say about a point fifty
        along, and answering with the nearest thing it knows would be the cache lying.

        """
        made = self.sound()
        seabed.remember_baked(self.world, made)
        seabed.forget()

        asked = self.world.asked
        seabed.reader(self.world, 50.0)(WorldPosition(made.west, made.south))
        self.assertGreater(self.world.asked, asked)

    def test_forgetting_the_cache_does_not_forget_the_bake(self):
        """
        Separate on purpose. Dropping an expensive bake as a side effect of clearing a
        memory cache would quietly undo a server's whole startup, and the symptom would be
        charts getting slower over time for no visible reason.

        """
        seabed.remember_baked(self.world, self.sound())
        seabed.forget()
        self.assertEqual(len(seabed.baked_for(self.world, 100.0)), 1)
        seabed.forget_baked()
        self.assertEqual(len(seabed.baked_for(self.world, 100.0)), 0)


class TestWhichSpacingsAreWorthBaking(BaseEvenniaTestCase):
    def test_they_come_from_the_zoom_ladder(self):
        """
        A bake at any other spacing is a file nothing ever reads, because a chart's cell is
        its span over its grid and its span is twice whatever zoom was asked for.

        """
        cells = bake.chart_cells((1000.0, 10000.0), 96)
        self.assertEqual(len(cells), 2)
        self.assertAlmostEqual(cells[0], 2.0 * 10000.0 / 95.0)
        self.assertAlmostEqual(cells[1], 2.0 * 1000.0 / 95.0)

    def test_coarsest_first_so_the_cheap_one_is_ready_soonest(self):
        cells = bake.chart_cells((500.0, 5000.0, 50000.0), 96)
        self.assertEqual(list(cells), sorted(cells, reverse=True))

    def test_two_zooms_that_want_one_spacing_bake_it_once(self):
        self.assertEqual(len(bake.chart_cells((4000.0, 4000.0), 96)), 1)
