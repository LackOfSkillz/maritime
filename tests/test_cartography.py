"""
Tests for drawing a chart out of what somebody surveyed.

Marching squares has sixteen cases and every one of them is a chance to draw a coastline
somewhere there is not one. Most of this file is about the two failures that would matter
in play: a line through water nobody sounded, and a line in the wrong place.

Nothing here needs a ship. Contouring is arithmetic over a grid of numbers, which is
exactly why it is worth having as its own module.

"""

from evennia.utils.test_resources import BaseEvenniaTestCase

import math

from ..bathymetry import MaritimeMapProvider
from ..charts import Chart
from ..client import cartography
from ..position import METRES_PER_FATHOM, WorldPosition

HERE = WorldPosition(1000.0, 2000.0)


class SlopingSeabed(MaritimeMapProvider):
    """
    A shelf rising steadily eastward, with a swell running through it.

    Steady enough that a coarse seed pass finds every contour there is, and rippled enough
    that there are several to find rather than one straight line down the middle.
    """

    def terrain_z_at(self, position):
        return -30.0 + position.x / 90.0 + 7.0 * math.sin(position.y / 400.0)


def flat(value, steps=5):
    """
    Returns:
        grid (list): A square of one repeated elevation.

    """
    return [[value] * steps for _ in range(steps)]


def sloping(steps=5, low=-20.0, high=20.0):
    """
    Returns:
        grid (list): A square rising steadily west to east, so it crosses datum
            exactly once down the middle.

    """
    return [
        [low + (high - low) * (column / float(steps - 1)) for column in range(steps)]
        for _ in range(steps)
    ]


class TestWhatCountsAsSurveyed(BaseEvenniaTestCase):
    """Off the sheet a chart answers nothing, and nothing is not a depth."""

    def test_a_depth_is_surveyed(self):
        self.assertTrue(cartography.surveyed(-12.5))
        self.assertTrue(cartography.surveyed(0))

    def test_nothing_is_not(self):
        self.assertFalse(cartography.surveyed(None))

    def test_and_neither_is_a_word(self):
        """`charts` answers with a marker off the sheet, not a number."""
        self.assertFalse(cartography.surveyed("unknown"))

    def test_a_flag_is_not_a_sounding(self):
        """
        True would otherwise pass for a depth of one, because in Python it is one.
        A chart that read a boolean as a fathom would draw a coastline out of it.

        """
        self.assertFalse(cartography.surveyed(True))


class TestTracingALevel(BaseEvenniaTestCase):
    """Marching squares, over grids whose answer is known by looking at them."""

    def test_water_everywhere_has_no_coastline(self):
        self.assertEqual(cartography.contour(flat(-30.0), 0.0, 0.0, 0.0, 400.0), [])

    def test_and_neither_has_dry_land(self):
        self.assertEqual(cartography.contour(flat(30.0), 0.0, 0.0, 0.0, 400.0), [])

    def test_a_slope_crossing_datum_has_one(self):
        self.assertTrue(cartography.contour(sloping(), 0.0, 0.0, 0.0, 400.0))

    def test_and_it_runs_where_the_crossing_is(self):
        """
        The grid rises evenly from west to east, so datum falls exactly halfway
        across. Every point of the line should be on that middle, whatever route
        the algorithm took to find it.

        """
        span = 400.0
        for start, finish in cartography.contour(sloping(), 0.0, 0.0, 0.0, span):
            self.assertAlmostEqual(start[0], span / 2.0, places=6)
            self.assertAlmostEqual(finish[0], span / 2.0, places=6)

    def test_a_deeper_level_traces_further_out(self):
        """
        Ten fathoms lies further from the shore than two, on a bottom that shoals
        evenly. Getting this backwards would put the deep water inshore.

        """
        grid = sloping()
        shallow = cartography.contour(grid, cartography.fathoms(2.0), 0.0, 0.0, 400.0)
        deep = cartography.contour(grid, cartography.fathoms(10.0), 0.0, 0.0, 400.0)
        self.assertLess(deep[0][0][0], shallow[0][0][0])

    def test_unsurveyed_water_is_never_contoured(self):
        """
        The rule the whole panel rests on. A cell with an unsounded corner is left
        alone, so the line stops at the edge of what somebody measured instead of
        being guessed across it.

        """
        grid = sloping()
        grid[2][2] = None
        grid[2][3] = None
        traced = cartography.contour(grid, 0.0, 0.0, 0.0, 400.0)
        for start, finish in traced:
            for point in (start, finish):
                self.assertFalse(150.0 < point[1] < 250.0 and 150.0 < point[0] < 350.0)

    def test_a_wholly_unsurveyed_square_draws_nothing(self):
        nothing = [[None] * 5 for _ in range(5)]
        self.assertEqual(cartography.contour(nothing, 0.0, 0.0, 0.0, 400.0), [])

    def test_the_line_is_interpolated_not_stepped(self):
        """
        A crossing three quarters of the way along an edge belongs three quarters
        along, not at the midpoint. Stepping is what makes a contoured coast look
        like a staircase.

        """
        grid = [[-30.0, 10.0], [-30.0, 10.0]]
        traced = cartography.contour(grid, 0.0, 0.0, 0.0, 100.0)
        self.assertAlmostEqual(traced[0][0][0], 75.0, places=6)


class TestThreadingTheSegments(BaseEvenniaTestCase):
    """Marching squares emits cells in no order; a chart wants runs."""

    def test_nothing_makes_nothing(self):
        self.assertEqual(cartography.join([]), [])

    def test_a_chain_becomes_one_run(self):
        segments = [
            ((0.0, 0.0), (10.0, 0.0)),
            ((10.0, 0.0), (20.0, 0.0)),
            ((20.0, 0.0), (30.0, 0.0)),
        ]
        joined = cartography.join(segments)
        self.assertEqual(len(joined), 1)
        self.assertEqual(len(joined[0]), 4)

    def test_a_chain_given_backwards_still_becomes_one_run(self):
        """The whole point: the order they arrive in means nothing."""
        segments = [
            ((20.0, 0.0), (30.0, 0.0)),
            ((0.0, 0.0), (10.0, 0.0)),
            ((10.0, 0.0), (20.0, 0.0)),
        ]
        self.assertEqual(len(cartography.join(segments)), 1)

    def test_two_separate_coasts_stay_separate(self):
        segments = [
            ((0.0, 0.0), (10.0, 0.0)),
            ((500.0, 500.0), (510.0, 500.0)),
        ]
        self.assertEqual(len(cartography.join(segments)), 2)

    def test_every_segment_is_used_exactly_once(self):
        """A dropped segment is a gap in the coast; a doubled one is a crease."""
        grid = sloping(steps=9)
        segments = cartography.contour(grid, 0.0, 0.0, 0.0, 800.0)
        joined = cartography.join(segments)
        drawn = sum(len(run) - 1 for run in joined)
        self.assertEqual(drawn, len(segments))


class TestThinningARun(BaseEvenniaTestCase):
    """A chart does not need a point every four hundred metres."""

    def test_a_straight_run_keeps_only_its_ends(self):
        straight = [(0.0, 0.0), (100.0, 0.0), (200.0, 0.0), (300.0, 0.0)]
        self.assertEqual(cartography.simplify(straight), [(0.0, 0.0), (300.0, 0.0)])

    def test_a_corner_is_kept(self):
        bent = [(0.0, 0.0), (100.0, 0.0), (100.0, 300.0)]
        self.assertEqual(len(cartography.simplify(bent)), 3)

    def test_a_short_run_is_left_alone(self):
        pair = [(0.0, 0.0), (10.0, 5.0)]
        self.assertEqual(cartography.simplify(pair), pair)

    def test_the_ends_always_survive(self):
        wandering = [(float(n), float(n % 3) * 40.0) for n in range(0, 400, 20)]
        thinned = cartography.simplify(wandering)
        self.assertEqual(thinned[0], wandering[0])
        self.assertEqual(thinned[-1], wandering[-1])


class TestSendingItOut(BaseEvenniaTestCase):
    """Offsets from where she reckons she is, never coordinates."""

    def test_a_run_comes_back_relative_to_her(self):
        line = [(1100.0, 2000.0), (1200.0, 2000.0), (1300.0, 2000.0)]
        out = cartography.as_offsets([line], HERE)
        self.assertEqual(out[0][0], [100, 0])

    def test_the_true_position_never_travels(self):
        """
        The rule that keeps a chart from becoming a satellite fix. Nothing in the
        payload is a world coordinate, so a browser cannot work out where she
        really is however hard it looks.

        """
        line = [(1100.0, 2000.0), (1200.0, 2100.0)]
        out = cartography.as_offsets([line], HERE)
        for point in out[0]:
            self.assertNotIn(HERE.x, point)
            self.assertNotIn(HERE.y, point)

    def test_a_run_thinned_to_nothing_is_dropped(self):
        self.assertEqual(cartography.as_offsets([[(0.0, 0.0)]], HERE), [])


class TestPrintedSoundings(BaseEvenniaTestCase):
    """Figures on the paper, as a chart prints them."""

    def test_depths_are_printed_in_fathoms(self):
        grid = flat(-METRES_PER_FATHOM * 7.0, steps=7)
        printed = cartography.soundings(grid, 0.0, 0.0, 600.0, HERE, every=3)
        self.assertTrue(printed)
        self.assertAlmostEqual(printed[0][2], 7.0, places=1)

    def test_land_is_not_sounded(self):
        """A chart does not print a depth for a hillside."""
        self.assertEqual(cartography.soundings(flat(12.0), 0.0, 0.0, 400.0, HERE), [])

    def test_and_neither_is_unsurveyed_water(self):
        nothing = [[None] * 5 for _ in range(5)]
        self.assertEqual(cartography.soundings(nothing, 0.0, 0.0, 400.0, HERE), [])

    def test_they_are_thinned(self):
        """
        A chart prints a legible scatter, not every sounding ever taken. Two
        thousand figures is not a chart, it is a spreadsheet.

        """
        grid = flat(-20.0, steps=13)
        every = cartography.soundings(grid, 0.0, 0.0, 1200.0, HERE, every=1)
        thinned = cartography.soundings(grid, 0.0, 0.0, 1200.0, HERE, every=4)
        self.assertLess(len(thinned), len(every) / 4)


class TestTheEdgeOfThePaper(BaseEvenniaTestCase):
    """Off the chart is a state, and the interface has to be able to show it."""

    def test_the_bounds_come_back_as_offsets(self):
        class Sheet:
            west, east, south, north = 0.0, 4000.0, 0.0, 4000.0

        edges = cartography.coverage(Sheet(), HERE)
        self.assertEqual(edges["west"], -1000.0)
        self.assertEqual(edges["east"], 3000.0)


class TestFathomsAsElevations(BaseEvenniaTestCase):
    """Depths are spoken in fathoms and contoured as elevations."""

    def test_a_depth_becomes_a_negative_elevation(self):
        self.assertAlmostEqual(cartography.fathoms(5.0), -5.0 * METRES_PER_FATHOM)

    def test_a_deeper_line_is_further_below_datum(self):
        self.assertLess(cartography.fathoms(10.0), cartography.fathoms(2.0))

    def test_it_does_not_matter_how_the_depth_was_signed(self):
        self.assertEqual(cartography.fathoms(5.0), cartography.fathoms(-5.0))


class TestEveryCornerOfTheCaseTable(BaseEvenniaTestCase):
    """
    One cell at a time, with the answer known by looking at it.

    The sloping grids above only ever produce a crossing from the left edge to the
    right one, so most of the sixteen cases were never run at all - swapping two of
    them changed nothing any test could see. A coastline that cut the wrong corner
    of a headland would have shipped.

    Each grid below is a single cell: `[[bottom_left, bottom_right], [top_left,
    top_right]]`, one hundred metres square, contoured at datum.

    """

    SPAN = 100.0

    def cut(self, bottom_left, bottom_right, top_left, top_right):
        """
        Returns:
            segments (list): What one cell of those four corners produces.

        """
        grid = [[bottom_left, bottom_right], [top_left, top_right]]
        return cartography.contour(grid, 0.0, 0.0, 0.0, self.SPAN)

    def edges_touched(self, segment):
        """
        Returns:
            edges (set): Which sides of the cell a segment ends on.

        """
        touched = set()
        for x, y in segment:
            if abs(x) < 0.001:
                touched.add("left")
            if abs(x - self.SPAN) < 0.001:
                touched.add("right")
            if abs(y) < 0.001:
                touched.add("bottom")
            if abs(y - self.SPAN) < 0.001:
                touched.add("top")
        return touched

    def test_one_dry_corner_cuts_that_corner_off(self):
        """
        Land in the south-west only. The waterline must cross the west side and the
        south side - cutting any other pair would put the shore through open water.

        """
        cut = self.cut(10.0, -10.0, -10.0, -10.0)
        self.assertEqual(len(cut), 1)
        self.assertEqual(self.edges_touched(cut[0]), {"left", "bottom"})

    def test_and_the_opposite_case_cuts_the_same_corner(self):
        """
        Water in the south-west, land everywhere else. The line is in the same
        place; only which side is dry has changed.

        """
        cut = self.cut(-10.0, 10.0, 10.0, 10.0)
        self.assertEqual(self.edges_touched(cut[0]), {"left", "bottom"})

    def test_each_of_the_four_corners_cuts_its_own(self):
        corners = {
            "south-west": ((10.0, -10.0, -10.0, -10.0), {"left", "bottom"}),
            "south-east": ((-10.0, 10.0, -10.0, -10.0), {"bottom", "right"}),
            "north-east": ((-10.0, -10.0, -10.0, 10.0), {"right", "top"}),
            "north-west": ((-10.0, -10.0, 10.0, -10.0), {"left", "top"}),
        }
        for where, (grid, expected) in corners.items():
            cut = self.cut(*grid)
            self.assertEqual(len(cut), 1, where)
            self.assertEqual(self.edges_touched(cut[0]), expected, where)

    def test_land_to_the_west_gives_a_shore_running_north_and_south(self):
        """
        Which crosses the *top and bottom* of the cell, not its sides. A line
        running north enters and leaves through the horizontal edges - stated here
        because the first version of this test asserted the opposite, confidently.

        """
        cut = self.cut(10.0, -10.0, 10.0, -10.0)
        self.assertEqual(self.edges_touched(cut[0]), {"bottom", "top"})

    def test_land_to_the_south_gives_a_shore_running_east_and_west(self):
        cut = self.cut(10.0, 10.0, -10.0, -10.0)
        self.assertEqual(self.edges_touched(cut[0]), {"left", "right"})

    def test_a_saddle_is_drawn_as_two_lines(self):
        """
        Land on one diagonal and water on the other is genuinely ambiguous - the
        cell could be read either way. Two separate lines is the conventional answer
        and the one that never joins two shores that are not connected.

        """
        self.assertEqual(len(self.cut(10.0, -10.0, -10.0, 10.0)), 2)
        self.assertEqual(len(self.cut(-10.0, 10.0, 10.0, -10.0)), 2)

    def test_a_cell_wholly_under_water_is_left_alone(self):
        self.assertEqual(self.cut(-10.0, -10.0, -10.0, -10.0), [])

    def test_a_cell_wholly_dry_is_too(self):
        self.assertEqual(self.cut(10.0, 10.0, 10.0, 10.0), [])

    def test_every_line_ends_on_the_edge_of_its_cell(self):
        """
        A contour is a crossing of edges. A point in the middle of a cell means the
        interpolation has gone somewhere it should not.

        """
        for grid in (
            (10.0, -10.0, -10.0, -10.0),
            (-10.0, 10.0, -10.0, -10.0),
            (10.0, 10.0, -10.0, -10.0),
            (10.0, -10.0, -10.0, 10.0),
        ):
            for segment in self.cut(*grid):
                self.assertTrue(self.edges_touched(segment))
                self.assertEqual(len(self.edges_touched(segment)), 2)


class TestSoundingOnlyWhereItMatters(BaseEvenniaTestCase):
    """
    Most of a sheet has no contour in it, and sounding all of it was the whole cost.

    A seed grid finds the contours; only the cells carrying one are sounded in full. The
    rest are filled from their own corners, which can neither invent nor hide a crossing,
    because bilinear interpolation stays between the values it is given.

    The interesting tests here are the ones about what it *cannot* promise. Refinement
    only ever looks more closely at something the seed pass already noticed, so the seed
    is the resolution that matters and a coarse one draws a different, worse coastline
    while looking like a bargain.
    """

    def setUp(self):
        super().setUp()
        self.chart = Chart(key="a sheet", west=-9e4, east=9e4, south=-9e4, north=9e4)

    def counted(self, world):
        """Wrap a world so every depth it is asked for is counted."""
        asked = []

        class Counting:
            def terrain_z_at(inner, position):
                asked.append((position.x, position.y))
                return world.terrain_z_at(position)

            def __getattr__(inner, name):
                return getattr(world, name)

        return Counting(), asked

    def test_the_seed_is_only_as_coarse_as_the_sheet_allows(self):
        """
        The rule that keeps this honest. A wide sheet has samples further apart than the
        finest thing in the water, so there is nothing safe to seed with and everything
        is sounded - which is what it did before any of this existed.

        """
        self.assertEqual(cartography._seed_factor(cell=420.0, ceiling=2), 1)
        self.assertEqual(cartography._seed_factor(cell=210.0, ceiling=2), 1)
        self.assertEqual(cartography._seed_factor(cell=42.0, ceiling=2), 2)
        self.assertEqual(cartography._seed_factor(cell=42.0, ceiling=1), 1)

    def test_it_sounds_far_fewer_points_than_the_grid_has(self):
        world = SlopingSeabed()
        counting, asked = self.counted(world)
        steps = 48
        cartography.sample(self.chart, counting, 0.0, -1000.0, -1000.0, 2000.0, steps=steps)
        self.assertLess(
            len(asked),
            steps * steps * 0.75,
            f"sounded {len(asked)} of {steps * steps}; the seed pass is doing nothing",
        )

    def test_and_sounds_every_point_when_told_not_to_be_clever(self):
        """`coarse=1` is the old behaviour, kept so it can be compared against."""
        counting, asked = self.counted(SlopingSeabed())
        steps = 24
        cartography.sample(
            self.chart, counting, 0.0, -1000.0, -1000.0, 2000.0, steps=steps, coarse=1
        )
        self.assertEqual(len(set(asked)), steps * steps)

    def test_the_contour_is_the_one_a_fully_sounded_grid_would_draw(self):
        """
        The property the whole thing rests on: where the seed pass finds a contour, what
        gets drawn is what sounding every point would have drawn.

        Compared as positions rather than as a count of segments. Counting was the first
        version of this and it is brittle for a reason worth remembering - a contour that
        grazes the edge of the paper breaks into slightly different numbers of pieces
        depending on which points were taken, while running through all the same water.
        What matters to a navigator is where the line is, not how many pieces the tracer
        cut it into.

        """
        world = SlopingSeabed()
        span, west, south = 2000.0, -1000.0, -1000.0
        cell = span / 47.0
        full = cartography.sample(self.chart, world, 0.0, west, south, span, steps=48, coarse=1)
        seeded = cartography.sample(self.chart, world, 0.0, west, south, span, steps=48)

        checked = 0
        for level in cartography.traced_levels():
            here = [
                point
                for segment in cartography.contour(full, level, west, south, span)
                for point in segment
            ]
            there = [
                point
                for segment in cartography.contour(seeded, level, west, south, span)
                for point in segment
            ]
            if not here:
                continue
            self.assertTrue(there, f"the seeded pass lost the {level} m contour entirely")
            for x, y in here:
                nearest = min(math.hypot(x - a, y - b) for a, b in there)
                self.assertLess(
                    nearest,
                    cell,
                    f"the {level} m contour moved {nearest:.0f} m, more than one cell",
                )
                checked += 1
        self.assertGreater(checked, 50, "this test traced almost nothing")

    def test_a_cell_with_no_contour_in_it_still_reads_as_a_depth(self):
        grid = cartography.sample(
            self.chart, SlopingSeabed(), 0.0, -1000.0, -1000.0, 2000.0, steps=48
        )
        for row in grid:
            for value in row:
                self.assertTrue(cartography.surveyed(value), "a filled cell came back unsounded")

    def test_a_filled_cell_never_invents_a_crossing(self):
        """
        Bilinear interpolation is bounded by its corners, so a cell whose corners are all
        on one side of a level stays on that side throughout. Asserted directly, because
        it is the argument that makes skipping the cell safe.

        """
        for corners in ((-30.0, -28.0, -31.0, -29.0), (5.0, 7.0, 6.0, 8.0)):
            self.assertFalse(cartography._worth_refining(corners, cartography.traced_levels()))
        # and one that straddles the waterline is refined
        self.assertTrue(
            cartography._worth_refining((-1.0, 2.0, -3.0, 1.0), (cartography.COASTLINE,))
        )

    def test_unsurveyed_water_is_always_looked_at_closely(self):
        """
        Off the edge of the paper there is nothing to interpolate between, and filling
        there would be the chart inventing coverage it does not have.

        """
        self.assertTrue(cartography._worth_refining((-30.0, None, -31.0, -29.0), (0.0,)))

    def test_the_printed_figures_are_sounded_rather_than_interpolated(self):
        """
        A printed depth is a number a captain acts on, not a line he reads a shape from.
        There are a few dozen of them and they are cheap, so none is ever a guess.

        """
        world = SlopingSeabed()
        counting, asked = self.counted(world)
        steps, span, west, south = 48, 4000.0, -2000.0, -2000.0
        cartography.sample(self.chart, counting, 0.0, west, south, span, steps=steps)

        sounded = {(round(x, 3), round(y, 3)) for x, y in asked}
        cell = span / float(steps - 1)
        every = max(1, int(round(steps / float(cartography.PRINTED))))
        for row in range(0, steps, every):
            for column in range(0, steps, every):
                here = (round(west + column * cell, 3), round(south + row * cell, 3))
                self.assertIn(here, sounded, f"a printed figure at {here} was a guess")
