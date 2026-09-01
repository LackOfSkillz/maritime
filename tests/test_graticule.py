"""
Tests for the meridians and parallels a chart is ruled with.

Two things are being checked, and they are not the same thing.

The first is that the lines are *right*: round numbers, one precision per set, drawn where
the projection puts them and nowhere else.

The second is that they *lean*. That is the whole reason the graticule was built - a flat
sheet cannot show a round world by bending its picture, but it can draw the lines that are
genuinely bent and let a navigator watch them converge as he zooms out. A graticule of
perfectly parallel meridians would pass every test about labels and fail the only one that
matters.
"""

import math

from evennia.utils.test_resources import BaseEvenniaTestCase

from ..bathymetry import FlatSeaMapProvider, MaritimeMapProvider
from ..client import cartography
from ..client.payloads import ChartSheet
from ..position import WorldPosition

DEGREE = "°"


class Globe(MaritimeMapProvider):
    """
    A world that knows where it is: a sphere, ruled the way a real one is.

    Latitude falls off with northing; longitude with easting, divided by the cosine of the
    latitude - which *is* the convergence, and the reason two meridians a fixed number of
    degrees apart stand closer together the nearer the pole you get.
    """

    RADIUS = 6371000.0

    def __init__(self, latitude=-21.5, longitude=149.9):
        super().__init__()
        self.latitude = latitude
        self.longitude = longitude

    def terrain_z_at(self, position):
        return -50.0

    def geographic_at(self, position):
        latitude = self.latitude + math.degrees(position.y / self.RADIUS)
        scale = max(math.cos(math.radians(latitude)), 1e-6)
        return (latitude, self.longitude + math.degrees(position.x / (self.RADIUS * scale)))


class TestAWorldWithNoGeographyIsRuledWithNothing(BaseEvenniaTestCase):
    """
    The dependency-free promise in its own shape. A seabed defined by an arithmetic ramp
    is not anywhere, and a chart of it must not invent a latitude to print in the margin.
    """

    def test_the_base_provider_declines_to_say_where_it_is(self):
        self.assertIsNone(FlatSeaMapProvider().geographic_at(WorldPosition(0.0, 0.0)))

    def test_and_so_gets_no_graticule(self):
        self.assertEqual(
            cartography.graticule(FlatSeaMapProvider(), WorldPosition(0.0, 0.0), 10000.0), []
        )

    def test_a_sheet_carries_none_by_default(self):
        self.assertEqual(ChartSheet().graticule, [])
        self.assertEqual(ChartSheet().as_message()["graticule"], [])


class TestWhatItRules(BaseEvenniaTestCase):
    def setUp(self):
        self.world = Globe()
        self.here = WorldPosition(0.0, 0.0)

    def ruled(self, reach=50000.0):
        return cartography.graticule(self.world, self.here, reach)

    def test_a_world_that_is_somewhere_gets_both_sets(self):
        self.assertEqual({line["kind"] for line in self.ruled()}, {"parallel", "meridian"})

    def test_the_lines_fall_on_round_numbers(self):
        """
        A navigator reads a position off these. Ruled at an arbitrary fraction they are
        decoration, and he is left interpolating against a number nobody can hold in mind.

        """
        for line in self.ruled():
            figure = float(line["label"][:-2])
            self.assertAlmostEqual(figure * 100.0, round(figure * 100.0), places=6)

    def test_one_precision_for_the_whole_set(self):
        """
        The bug this was written for: precision picked per value prints "21.6" beside
        "21.62" - each correct alone, and ragged as a set, which is the one thing a ruled
        scale must not be.

        """
        for kind in ("parallel", "meridian"):
            figures = {
                len(line["label"].split(DEGREE)[0].split(".")[-1])
                for line in self.ruled()
                if line["kind"] == kind and "." in line["label"]
            }
            self.assertLessEqual(len(figures), 1, f"{kind}s ruled at mixed precision")

    def test_south_and_west_rather_than_a_minus_sign(self):
        """A negative latitude is not a thing anybody says aloud."""
        labels = [line["label"] for line in self.ruled()]
        self.assertTrue(labels)
        for label in labels:
            self.assertNotIn("-", label)
            self.assertIn(label[-1], "NSEW")

    def test_the_southern_hemisphere_reads_south(self):
        for line in self.ruled():
            if line["kind"] == "parallel":
                self.assertTrue(line["label"].endswith("S"), line["label"])

    def test_a_few_lines_each_way_rather_than_a_thicket(self):
        """Ruled too finely, the frame competes with the soundings it exists to locate."""
        for kind in ("parallel", "meridian"):
            distinct = {line["label"] for line in self.ruled() if line["kind"] == kind}
            self.assertGreaterEqual(len(distinct), 2)
            self.assertLessEqual(len(distinct), 12)

    def test_it_rules_more_finely_as_she_zooms_in(self):
        """
        A sheet covering two hundred kilometres wants whole degrees; one covering five
        wants hundredths. A fixed spacing gives the close view no lines at all and the
        wide one a solid grey wash.

        """

        def step_of(reach):
            figures = sorted(
                {
                    float(line["label"][:-2])
                    for line in self.ruled(reach)
                    if line["kind"] == "parallel"
                }
            )
            return min(later - sooner for sooner, later in zip(figures, figures[1:]))

        self.assertLess(step_of(5000.0), step_of(200000.0))

    def test_the_lines_stay_on_the_sheet(self):
        reach = 50000.0
        for line in self.ruled(reach):
            for east, north in line["line"]:
                self.assertLessEqual(abs(east), reach + 1.0)
                self.assertLessEqual(abs(north), reach + 1.0)

    def test_offsets_are_from_her_and_not_from_the_corner(self):
        """
        Everything else on the sheet is measured from where she reckons she is. A
        graticule in absolute metres would draw itself hundreds of kilometres off the
        paper, and would do it only for a ship that had sailed away from the origin -
        which is the kind of bug that passes every test written at (0, 0).

        """
        self.here = WorldPosition(400000.0, -250000.0)
        drawn = self.ruled(50000.0)
        self.assertTrue(drawn)
        for line in drawn:
            for east, north in line["line"]:
                self.assertLess(abs(east), 51000.0)
                self.assertLess(abs(north), 51000.0)


class TestTheLinesLean(BaseEvenniaTestCase):
    """
    The one that matters. Every test above would pass on a square grid.
    """

    def lean(self, reach):
        """
        Args:
            reach (float): How far the sheet extends, in metres.

        Returns:
            lean (float): How far the most slanted meridian moves east-west down the
                sheet, in metres. Zero on a plane; on a globe, the convergence.

        """
        widest = 0.0
        for line in cartography.graticule(Globe(), WorldPosition(0.0, 0.0), reach):
            if line["kind"] != "meridian" or len(line["line"]) < 2:
                continue
            eastings = [point[0] for point in line["line"]]
            widest = max(widest, max(eastings) - min(eastings))
        return widest

    def test_a_meridian_is_not_a_vertical_line(self):
        self.assertGreater(self.lean(200000.0), 100.0)

    def test_and_it_leans_further_the_further_out_she_looks(self):
        """
        The curvature cue, stated as an assertion. Close in, the sheet is flat enough that
        the meridians stand square and the chart is honest to draw itself flat. Zoomed
        out, they visibly converge - so a player can see the world is round without the
        client ever having been told that it is.

        """
        self.assertGreater(self.lean(400000.0), self.lean(50000.0) * 4.0)

    def test_they_lean_the_way_the_hemisphere_says(self):
        """
        Convergence has a direction, and getting it backwards is a sign error that no
        test about magnitude would catch. South of the equator the meridians spread as
        you go north, because the parallels there are longer.

        """
        ruled = cartography.graticule(Globe(-21.5), WorldPosition(0.0, 0.0), 400000.0)
        leaning = [
            line
            for line in ruled
            if line["kind"] == "meridian" and abs(line["line"][0][0]) > 100000.0
        ]
        self.assertTrue(leaning, "no meridian far enough off centre to lean measurably")
        for line in leaning:
            southerly = min(line["line"], key=lambda point: point[1])
            northerly = max(line["line"], key=lambda point: point[1])
            # Further from the centreline in the north than in the south: spreading.
            self.assertGreater(abs(northerly[0]), abs(southerly[0]), line["label"])
