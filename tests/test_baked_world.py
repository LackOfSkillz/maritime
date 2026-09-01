"""
Tests for a world served off disk.

The bundle that ships with the contrib is a second copy of a coast somebody generated, and
the thing worth proving is that a game which clones the repo gets a *world* rather than a
grid of numbers. Depth is the easy half. The half that is easy to lose is everything else:

    the bottom      what holds an anchor and what holes a hull
    the dangers     the rocks a survey marked, which soundings cannot imply
    the landmarks   islands with names, so there is something to be first to
    the latitude    without which the chart cannot be ruled

Those come from a manifest in plain text beside the soundings, and a bundle missing it would
still draw a perfectly convincing coastline with none of them - which is exactly the failure
that would ship unnoticed.
"""

import json
import os
import tempfile

from evennia.utils.test_resources import BaseEvenniaTestCase

from .. import bake, seabed
from ..baked_world import OFF_THE_BUNDLE_M, BakedMapProvider
from ..bathymetry import ROCK, SAND, MaritimeMapProvider
from ..discovery import Landmark
from ..position import WorldPosition
from ..tiles import Hazard

ROCK_AT = (400.0, 300.0)


class SmallWorld(MaritimeMapProvider):
    """A generated world with everything a bundle has to carry."""

    def terrain_z_at(self, position):
        return -20.0 - position.x * 0.002 - position.y * 0.001

    def bottom_type_at(self, position):
        return SAND

    def charted_dangers(self, position, reach):
        return (
            Hazard(
                key="the Brawn", x=ROCK_AT[0], y=ROCK_AT[1], radius=60.0, top_z=-2.0, bottom=ROCK
            ),
        )

    def landmarks_near(self, position, reach):
        return (
            Landmark(
                key="The Greater Horn",
                x=800.0,
                y=-200.0,
                radius=300.0,
                height=90.0,
                kind="headland",
            ),
        )

    def geographic_at(self, position):
        import math

        latitude = -21.5 + math.degrees(position.y / 6_371_000.0)
        return (latitude, 149.9 + math.degrees(position.x / 6_371_000.0))


class BundleTestCase(BaseEvenniaTestCase):
    def setUp(self):
        super().setUp()
        seabed.forget()
        seabed.forget_baked()
        self.addCleanup(seabed.forget)
        self.addCleanup(seabed.forget_baked)
        self.world = SmallWorld()
        self.where = tempfile.mkdtemp(prefix="maritime-bundle-")
        bake.bundle(
            self.world,
            [("near", (-1000.0, -1000.0, 1000.0, 1000.0), 50.0)],
            self.where,
        )
        self.shipped = BakedMapProvider(self.where)


class TestItIsAWorldAndNotAGrid(BundleTestCase):
    def test_it_knows_the_ground(self):
        for x, y in ((0.0, 0.0), (350.0, -450.0), (-800.0, 900.0)):
            here = WorldPosition(x, y)
            self.assertAlmostEqual(
                self.shipped.terrain_z_at(here), self.world.terrain_z_at(here), delta=0.05
            )

    def test_it_knows_what_the_survey_marked(self):
        """
        Soundings cannot imply these. A rock narrower than the grid is not smoothed away by
        sampling, it is *missed* - so if the manifest did not carry it, a bundle would draw
        open water over something that holes hulls.

        """
        dangers = self.shipped.charted_dangers(WorldPosition(0.0, 0.0), 2000.0)
        self.assertEqual([danger.key for danger in dangers], ["the Brawn"])
        self.assertEqual(dangers[0].bottom, ROCK)

    def test_and_measures_a_hull_against_them(self):
        """The chart and the physics have to be two questions about one list."""
        touched = self.shipped.hazards_touching(
            WorldPosition(ROCK_AT[0] - 500.0, ROCK_AT[1]),
            WorldPosition(ROCK_AT[0] + 500.0, ROCK_AT[1]),
            width=4.0,
        )
        self.assertEqual([danger.key for danger in touched], ["the Brawn"])

    def test_and_misses_them_when_she_passes_clear(self):
        self.assertEqual(
            self.shipped.hazards_touching(
                WorldPosition(ROCK_AT[0] - 500.0, ROCK_AT[1] + 900.0),
                WorldPosition(ROCK_AT[0] + 500.0, ROCK_AT[1] + 900.0),
            ),
            (),
        )

    def test_it_knows_the_bottom_where_it_matters(self):
        self.assertEqual(self.shipped.bottom_type_at(WorldPosition(*ROCK_AT)), ROCK)
        self.assertEqual(self.shipped.bottom_type_at(WorldPosition(0.0, 0.0)), SAND)

    def test_it_knows_what_is_worth_being_first_to(self):
        marks = self.shipped.landmarks_near(WorldPosition(0.0, 0.0), 2000.0)
        self.assertEqual([mark.key for mark in marks], ["The Greater Horn"])
        self.assertEqual(marks[0].height, 90.0)

    def test_it_knows_where_in_the_world_it_is(self):
        """Without this the chart cannot be ruled, and the globe has nothing to place."""
        here = self.shipped.geographic_at(WorldPosition(0.0, 0.0))
        there = self.world.geographic_at(WorldPosition(0.0, 0.0))
        self.assertAlmostEqual(here[0], there[0], places=4)
        self.assertAlmostEqual(here[1], there[1], places=4)

    def test_the_manifest_is_readable_text(self):
        """
        The interesting half of a world stays reviewable. Only the bulk is binary, which is
        the whole argument for shipping this at all.

        """
        with open(os.path.join(self.where, bake.MANIFEST), encoding="utf-8") as source:
            record = json.load(source)
        self.assertEqual(len(record["dangers"]), 1)
        self.assertEqual(len(record["landmarks"]), 1)
        self.assertTrue(record["anchor"])


class TestItsEdge(BundleTestCase):
    def test_beyond_the_soundings_is_deep_water(self):
        """
        A bundle has an edge, and a ship sailing over it should find open ocean and an
        unsurveyed chart - not a cliff, and not dry land at elevation zero, which is what
        an unsounded array of shorts would give.

        """
        self.assertEqual(
            self.shipped.terrain_z_at(WorldPosition(500_000.0, 500_000.0)), OFF_THE_BUNDLE_M
        )
        self.assertLess(OFF_THE_BUNDLE_M, -100.0)

    def test_a_bundle_that_is_not_there_is_not_an_error(self):
        """A game pointed at nothing gets a working provider with nothing in it, and can
        say so, rather than failing to start."""
        empty = BakedMapProvider(tempfile.mkdtemp(prefix="maritime-empty-"))
        self.assertEqual(empty.levels, ())
        self.assertEqual(empty.terrain_z_at(WorldPosition(0.0, 0.0)), OFF_THE_BUNDLE_M)
        self.assertIsNone(empty.geographic_at(WorldPosition(0.0, 0.0)))


class TestOnALatticePointItIsExact(BundleTestCase):
    def test_a_sounded_point_is_not_interpolated(self):
        """
        Interpolation is the cost of shipping data instead of a generator, and it should be
        paid only between the soundings. On one of them the answer is the sounding itself,
        so a chart drawn at a baked scale is the chart the generator drew.

        """
        sheet = self.shipped.levels[0]
        for column in (3, 11, 27):
            x = sheet.west + column * sheet.cell
            y = sheet.south + column * sheet.cell
            self.assertAlmostEqual(
                self.shipped.terrain_z_at(WorldPosition(x, y)), sheet.at(x, y), places=9
            )
