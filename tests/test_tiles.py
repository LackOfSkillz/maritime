"""
Tests for the tiled seabed, and for the hazards that make it exact.

"""

from evennia.utils.test_resources import BaseEvenniaTestCase

from ..bathymetry import FlatSeaMapProvider, MaritimeMapProvider, ROCK, SAND
from ..grounding import (
    HOLED,
    check_hazards,
    check_swept_grounding,
    hull_points,
    sweep_positions,
)
from ..position import WorldPosition
from ..spatial import cell_of
from ..tiles import (
    DEFAULT_TILE_SIZE,
    UNMAPPED_TERRAIN_Z,
    DictTileSource,
    Hazard,
    Tile,
    TileSource,
    TiledMapProvider,
)

SHELF = ("default", 0, 0)
NEXT_ALONG = ("default", 1, 0)


def a_rock(**kwargs):
    """
    Args:
        **kwargs: Overrides.

    Returns:
        hazard (Hazard): A rock that dries at low water, in the middle of a tile.

    """
    settings = {
        "key": "the Whaleback",
        "x": 500.0,
        "y": 500.0,
        "radius": 8.0,
        "top_z": -0.5,
        "bottom": ROCK,
    }
    settings.update(kwargs)
    return Hazard(**settings)


def a_shelf(**kwargs):
    """
    Args:
        **kwargs: Overrides.

    Returns:
        tile (Tile): Ten metres of water over sand, with a rock on it.

    """
    settings = {
        "cell": SHELF,
        "terrain_z": -10.0,
        "bottom": SAND,
        "hazards": (a_rock(),),
    }
    settings.update(kwargs)
    return Tile(**settings)


class TestHazard(BaseEvenniaTestCase):
    """A discrete thing on the bottom."""

    def test_a_hazard_with_no_name(self):
        with self.assertRaises(ValueError):
            Hazard("", 0.0, 0.0, 5.0, -1.0)

    def test_a_hazard_with_no_extent(self):
        """A point nothing can ever be near is a hazard that does not work."""
        with self.assertRaises(ValueError):
            Hazard("nothing", 0.0, 0.0, 0.0, -1.0)

    def test_it_covers_its_own_centre(self):
        self.assertTrue(a_rock().covers(WorldPosition(500.0, 500.0)))

    def test_it_covers_a_point_inside_its_radius(self):
        self.assertTrue(a_rock().covers(WorldPosition(505.0, 500.0)))

    def test_it_does_not_cover_a_point_outside(self):
        self.assertFalse(a_rock().covers(WorldPosition(520.0, 500.0)))

    def test_it_is_not_in_another_region(self):
        self.assertFalse(a_rock().covers(WorldPosition(500.0, 500.0, region="elsewhere")))

    def test_a_track_that_runs_over_it(self):
        self.assertTrue(
            a_rock().near_track(WorldPosition(0.0, 500.0), WorldPosition(1000.0, 500.0))
        )

    def test_a_track_that_passes_clear(self):
        self.assertFalse(
            a_rock().near_track(WorldPosition(0.0, 800.0), WorldPosition(1000.0, 800.0))
        )

    def test_a_wide_hull_passes_closer_than_a_narrow_one(self):
        """The corridor is her beam wide, not a line."""
        track = (WorldPosition(0.0, 512.0), WorldPosition(1000.0, 512.0))
        self.assertFalse(a_rock().near_track(*track))
        self.assertTrue(a_rock().near_track(*track, margin=6.0))

    def test_a_track_astern_of_it_is_not_a_track_over_it(self):
        """A rock a mile behind is a mile away, not on the line extended back."""
        self.assertFalse(
            a_rock().near_track(WorldPosition(600.0, 500.0), WorldPosition(1000.0, 500.0))
        )


class TestTile(BaseEvenniaTestCase):
    """One square of authored seabed."""

    def test_the_base_where_nothing_stands_on_it(self):
        self.assertAlmostEqual(a_shelf().terrain_z_at(WorldPosition(100.0, 100.0)), -10.0)

    def test_the_rock_where_it_does(self):
        self.assertAlmostEqual(a_shelf().terrain_z_at(WorldPosition(500.0, 500.0)), -0.5)

    def test_the_shallowest_of_several(self):
        tile = a_shelf(hazards=(a_rock(top_z=-4.0), a_rock(key="a second", top_z=-0.5)))
        self.assertAlmostEqual(tile.terrain_z_at(WorldPosition(500.0, 500.0)), -0.5)

    def test_something_deeper_than_the_shelf_does_not_lower_it(self):
        """A hollow in the ground is not something a keel meets."""
        tile = a_shelf(hazards=(a_rock(top_z=-40.0),))
        self.assertAlmostEqual(tile.terrain_z_at(WorldPosition(500.0, 500.0)), -10.0)

    def test_the_bottom_is_the_tiles_own(self):
        self.assertEqual(a_shelf().bottom_type_at(WorldPosition(100.0, 100.0)), SAND)

    def test_a_hazard_answers_for_its_own_material(self):
        """Touching sand is an inconvenience; touching rock holes her."""
        self.assertEqual(a_shelf().bottom_type_at(WorldPosition(500.0, 500.0)), ROCK)

    def test_its_bounds(self):
        self.assertEqual(a_shelf().bounds(DEFAULT_TILE_SIZE), (0.0, 0.0, 1000.0, 1000.0))

    def test_hazards_on_a_track(self):
        found = a_shelf().hazards_near_track(
            WorldPosition(0.0, 500.0), WorldPosition(1000.0, 500.0)
        )
        self.assertEqual(len(found), 1)

    def test_no_hazards_on_a_clear_track(self):
        self.assertEqual(
            a_shelf().hazards_near_track(WorldPosition(0.0, 900.0), WorldPosition(1000.0, 900.0)),
            (),
        )


class TestTileSource(BaseEvenniaTestCase):
    """Where tiles come from."""

    def test_the_interface_refuses_to_guess(self):
        with self.assertRaises(NotImplementedError):
            TileSource().tile_for(SHELF, DEFAULT_TILE_SIZE)

    def test_a_dict_source_finds_its_tile(self):
        source = DictTileSource([a_shelf()])
        self.assertIsNotNone(source.tile_for(SHELF, DEFAULT_TILE_SIZE))

    def test_a_dict_source_returns_nothing_for_unmapped_water(self):
        self.assertIsNone(DictTileSource([a_shelf()]).tile_for(NEXT_ALONG, DEFAULT_TILE_SIZE))

    def test_two_tiles_cannot_claim_one_square(self):
        """Keeping one silently would make the map depend on iteration order."""
        with self.assertRaises(ValueError):
            DictTileSource([a_shelf(), a_shelf(terrain_z=-40.0)])

    def test_it_files_a_tile_under_its_own_cell(self):
        source = DictTileSource([a_shelf(cell=NEXT_ALONG)])
        self.assertIsNone(source.tile_for(SHELF, DEFAULT_TILE_SIZE))

    def test_an_empty_source_is_a_legitimate_world(self):
        self.assertEqual(len(DictTileSource()), 0)


class TestTiledMapProvider(BaseEvenniaTestCase):
    """A seabed assembled from tiles, over an unmapped ocean."""

    def setUp(self):
        super().setUp()
        self.sea = TiledMapProvider(DictTileSource([a_shelf()]))

    def test_it_is_a_map_provider(self):
        self.assertIsInstance(self.sea, MaritimeMapProvider)

    def test_a_zero_tile_size_is_refused(self):
        with self.assertRaises(ValueError):
            TiledMapProvider(tile_size=0.0)

    def test_terrain_comes_from_the_tile(self):
        self.assertAlmostEqual(self.sea.terrain_z_at(WorldPosition(100.0, 100.0)), -10.0)

    def test_a_hazard_stands_proud_of_it(self):
        self.assertAlmostEqual(self.sea.terrain_z_at(WorldPosition(500.0, 500.0)), -0.5)

    def test_unmapped_water_is_deep_open_sea(self):
        """A square nobody drew is ocean, not a hole in the world."""
        self.assertAlmostEqual(
            self.sea.terrain_z_at(WorldPosition(50000.0, 50000.0)), UNMAPPED_TERRAIN_Z
        )

    def test_a_base_provider_answers_for_unmapped_water(self):
        sea = TiledMapProvider(DictTileSource([a_shelf()]), base=FlatSeaMapProvider(depth=40.0))
        self.assertAlmostEqual(sea.terrain_z_at(WorldPosition(50000.0, 50000.0)), -40.0)

    def test_the_bottom_type_comes_through_too(self):
        self.assertEqual(self.sea.bottom_type_at(WorldPosition(500.0, 500.0)), ROCK)

    def test_unmapped_bottom_is_sand(self):
        self.assertEqual(self.sea.bottom_type_at(WorldPosition(50000.0, 50000.0)), SAND)

    def test_the_tile_under_a_point(self):
        self.assertEqual(self.sea.tile_at(WorldPosition(100.0, 100.0)).cell, SHELF)

    def test_the_cell_and_the_provider_agree(self):
        here = WorldPosition(100.0, 100.0)
        self.assertEqual(cell_of(here, self.sea.tile_size), self.sea.tile_at(here).cell)


class TestLoadingOnDemand(BaseEvenniaTestCase):
    """A world of ten thousand tiles keeps resident only the ones being sailed over."""

    def setUp(self):
        super().setUp()
        self.sea = TiledMapProvider(DictTileSource([a_shelf()]))

    def test_nothing_is_loaded_until_something_asks(self):
        self.assertEqual(self.sea.resident(), 0)

    def test_asking_loads_one(self):
        self.sea.terrain_z_at(WorldPosition(100.0, 100.0))
        self.assertEqual(self.sea.resident(), 1)

    def test_asking_again_does_not_load_it_twice(self):
        self.sea.terrain_z_at(WorldPosition(100.0, 100.0))
        self.sea.terrain_z_at(WorldPosition(200.0, 200.0))
        self.assertEqual(self.sea.loads, 1)

    def test_a_miss_is_remembered_too(self):
        """Open ocean is the commonest answer there is."""
        self.sea.terrain_z_at(WorldPosition(50000.0, 50000.0))
        self.sea.terrain_z_at(WorldPosition(50001.0, 50000.0))
        self.assertEqual(self.sea.loads, 1)

    def test_they_can_be_let_go(self):
        self.sea.terrain_z_at(WorldPosition(100.0, 100.0))
        self.assertEqual(self.sea.release(), 1)
        self.assertEqual(self.sea.resident(), 0)


class TestTracksAcrossTiles(BaseEvenniaTestCase):
    """Only the tiles a track crosses are consulted."""

    def setUp(self):
        super().setUp()
        self.sea = TiledMapProvider(
            DictTileSource([a_shelf(), a_shelf(cell=NEXT_ALONG, hazards=())])
        )

    def test_a_track_inside_one_tile_loads_one(self):
        self.sea.tiles_touching(WorldPosition(100.0, 100.0), WorldPosition(200.0, 200.0))
        self.assertEqual(self.sea.loads, 1)

    def test_a_track_across_a_boundary_loads_both(self):
        found = self.sea.tiles_touching(WorldPosition(900.0, 500.0), WorldPosition(1100.0, 500.0))
        self.assertEqual({tile.cell for tile in found}, {SHELF, NEXT_ALONG})

    def test_unmapped_squares_are_left_out(self):
        """A caller wanting hazards has no use for the squares that have none."""
        self.assertEqual(
            self.sea.tiles_touching(
                WorldPosition(50000.0, 50000.0), WorldPosition(50100.0, 50000.0)
            ),
            (),
        )

    def test_a_wide_hull_can_touch_a_tile_her_centre_never_enters(self):
        found = self.sea.tiles_touching(
            WorldPosition(500.0, 995.0), WorldPosition(600.0, 995.0), width=20.0
        )
        self.assertEqual(len(found), 1)


class TestHazardsOnATrack(BaseEvenniaTestCase):
    """What a hull would sweep through."""

    def setUp(self):
        super().setUp()
        self.sea = TiledMapProvider(DictTileSource([a_shelf()]))

    def test_a_track_over_the_rock_finds_it(self):
        found = self.sea.hazards_touching(WorldPosition(0.0, 500.0), WorldPosition(1000.0, 500.0))
        self.assertEqual(len(found), 1)

    def test_a_track_clear_of_it_finds_nothing(self):
        self.assertEqual(
            self.sea.hazards_touching(WorldPosition(0.0, 900.0), WorldPosition(1000.0, 900.0)),
            (),
        )

    def test_the_shallowest_comes_first(self):
        """Two rocks in one corridor are not equally bad news."""
        sea = TiledMapProvider(
            DictTileSource(
                [
                    a_shelf(
                        hazards=(
                            a_rock(key="the deep one", x=300.0, top_z=-6.0),
                            a_rock(key="the shallow one", x=700.0, top_z=-0.5),
                        )
                    )
                ]
            )
        )
        found = sea.hazards_touching(WorldPosition(0.0, 500.0), WorldPosition(1000.0, 500.0))
        self.assertEqual(found[0].key, "the shallow one")

    def test_a_plain_provider_has_none(self):
        """The base answers so grounding can ask unconditionally."""
        self.assertEqual(
            FlatSeaMapProvider().hazards_touching(
                WorldPosition(0.0, 0.0), WorldPosition(100.0, 0.0)
            ),
            (),
        )


class TestHazardsStopHer(BaseEvenniaTestCase):
    """
    The reason authored hazards exist.

    Notes:
        The sweep tests a hull at seven points on her outline, and something
        small enough fits between them. A hazard with a radius is measured
        against the whole corridor she swept and cannot be.

        `TestSamplingMissesIt` below is the proof, and it is measured rather than
        asserted: it walks the sampled pass itself and finds deep water at every
        point while the corridor test stops her.

    """

    def setUp(self):
        super().setUp()
        self.sea = TiledMapProvider(DictTileSource([a_shelf()]))
        self.before = WorldPosition(0.0, 500.0)
        self.after = WorldPosition(1000.0, 500.0)

    def test_a_rock_she_would_have_stepped_over_stops_her(self):
        """A kilometre in one tick, and an eight-metre rock in the middle of it."""
        result = check_swept_grounding(
            self.before, self.after, 90.0, 2.0, 10.0, 20.0, 6.0, self.sea, 0.0
        )
        self.assertFalse(result)

    def test_rock_at_speed_holes_her(self):
        result = check_swept_grounding(
            self.before, self.after, 90.0, 2.0, 10.0, 20.0, 6.0, self.sea, 0.0
        )
        self.assertEqual(result.severity, HOLED)

    def test_she_is_stopped_short_of_it_not_beyond_it(self):
        """Closest approach is on the far side of a rock she has sailed through."""
        result = check_swept_grounding(
            self.before, self.after, 90.0, 2.0, 10.0, 20.0, 6.0, self.sea, 0.0
        )
        self.assertLess(result.position.x, 500.0)

    def test_she_is_stopped_where_she_reaches_it(self):
        result = check_swept_grounding(
            self.before, self.after, 90.0, 2.0, 10.0, 20.0, 6.0, self.sea, 0.0
        )
        self.assertAlmostEqual(result.position.x, 500.0 - 8.0 - 3.0, places=2)

    def test_a_shallow_draught_passes_over_it(self):
        """The rock tops out half a metre down. A dinghy is fine."""
        result = check_swept_grounding(
            self.before, self.after, 90.0, 0.2, 10.0, 20.0, 6.0, self.sea, 0.0
        )
        self.assertTrue(result)

    def test_a_track_that_misses_it_is_clear(self):
        result = check_swept_grounding(
            WorldPosition(0.0, 900.0),
            WorldPosition(1000.0, 900.0),
            90.0,
            2.0,
            10.0,
            20.0,
            6.0,
            self.sea,
            0.0,
        )
        self.assertTrue(result)

    def test_her_beam_is_what_reaches_it(self):
        """Her centre passes twelve metres off; a twenty-metre beam does not."""
        track = (WorldPosition(0.0, 512.0), WorldPosition(1000.0, 512.0))
        narrow = check_swept_grounding(*track, 90.0, 2.0, 10.0, 20.0, 2.0, self.sea, 0.0)
        wide = check_swept_grounding(*track, 90.0, 2.0, 10.0, 20.0, 20.0, self.sea, 0.0)
        self.assertTrue(narrow)
        self.assertFalse(wide)

    def test_nothing_to_hit_returns_nothing(self):
        self.assertIsNone(
            check_hazards(
                WorldPosition(0.0, 900.0),
                WorldPosition(1000.0, 900.0),
                2.0,
                10.0,
                6.0,
                self.sea,
                0.0,
            )
        )

    def test_she_can_already_be_on_it_when_the_step_begins(self):
        """Not entering it - she is there. Stopping her is still the answer."""
        result = check_hazards(
            WorldPosition(500.0, 500.0),
            WorldPosition(1000.0, 500.0),
            2.0,
            10.0,
            6.0,
            self.sea,
            0.0,
        )
        self.assertIsNotNone(result)


class TestSamplingMissesIt(BaseEvenniaTestCase):
    """
    The pair of tests that justify the whole approach.

    Notes:
        Removing the rock and finding the track clear would prove only that the
        rock is what stopped her. These walk the sampled pass itself, find deep
        water at every one of the five hundred and sixty-seven points it looks
        at, and then watch the corridor test stop her on the thing it could not
        see.

        A two-metre rock four metres off her centreline. The gap it sits in is
        not purely along her length or purely across her beam - the seven outline
        points are spread in both directions at once, and a small enough circle
        fits between them. Which is exactly why the size of the gap was measured
        here rather than argued about.

    """

    def setUp(self):
        super().setUp()
        self.rock = a_rock(y=504.0, radius=2.0)
        self.sea = TiledMapProvider(DictTileSource([a_shelf(hazards=(self.rock,))]))
        # Kept well inside the tile: a hull point past its edge would find the
        # unmapped ocean rather than the shelf, and prove nothing about either.
        self.before = WorldPosition(100.0, 500.0)
        self.after = WorldPosition(900.0, 500.0)

    def test_the_sampled_pass_finds_deep_water_everywhere(self):
        for centre in sweep_positions(self.before, self.after, 20.0):
            for point in hull_points(centre, 90.0, 20.0, 6.0):
                self.assertAlmostEqual(self.sea.terrain_z_at(point), -10.0)

    def test_and_the_corridor_stops_her_anyway(self):
        result = check_swept_grounding(
            self.before, self.after, 90.0, 2.0, 10.0, 20.0, 6.0, self.sea, 0.0
        )
        self.assertFalse(result)
        self.assertEqual(result.bottom, ROCK)

    def test_the_rock_is_inside_the_water_she_displaces(self):
        """Four metres off her centreline, and her beam is six."""
        self.assertTrue(self.rock.near_track(self.before, self.after, margin=3.0))

    def test_and_no_sample_point_anywhere_lands_on_it(self):
        """The same claim as the first test, put the other way round."""
        points = [
            point
            for centre in sweep_positions(self.before, self.after, 20.0)
            for point in hull_points(centre, 90.0, 20.0, 6.0)
        ]
        self.assertGreater(len(points), 500)
        self.assertFalse(any(self.rock.covers(point) for point in points))


class TestWhatBelongsOnTheChart(BaseEvenniaTestCase):
    """
    The other half of a hazard, and the half a captain actually gets to use.

    `hazards_touching` answers what a hull would hit. This answers what the paper should
    show, and without it a game could author a rock that holes a ship while its own chart
    drew open water over the spot - which is worse than a rock drawn nowhere, because the
    captain has looked and is entitled to believe what he saw.

    The two must agree. A chart showing one set of rocks while the physics used another
    would be a chart that lies in a new and more interesting way.
    """

    def setUp(self):
        super().setUp()
        self.sea = TiledMapProvider(DictTileSource([a_shelf()]))

    def test_a_rock_on_the_sheet_is_reported(self):
        found = self.sea.charted_dangers(WorldPosition(500.0, 500.0), 400.0)
        self.assertEqual([hazard.key for hazard in found], ["the Whaleback"])

    def test_one_off_the_sheet_is_not(self):
        """Centred well clear of it - the rock sits at the middle of its own tile."""
        found = self.sea.charted_dangers(WorldPosition(100.0, 100.0), 50.0)
        self.assertEqual(found, ())

    def test_the_box_is_square_because_the_paper_is(self):
        """
        A rock off the corner of the sheet is still on the sheet. Measured as a circle it
        would drop out at the corners, which is where a captain planning a turn is
        looking.

        """
        corner = WorldPosition(500.0 - 390.0, 500.0 - 390.0)
        self.assertTrue(self.sea.charted_dangers(corner, 400.0))

    def test_unmapped_water_contributes_nothing(self):
        empty = TiledMapProvider(DictTileSource([]))
        self.assertEqual(empty.charted_dangers(WorldPosition(0.0, 0.0), 5000.0), ())

    def test_a_plain_provider_answers_with_nothing(self):
        """Additive: a game with no authored hazards gets a chart exactly as it was."""
        self.assertEqual(
            FlatSeaMapProvider(30.0).charted_dangers(WorldPosition(0.0, 0.0), 5000.0), ()
        )

    def test_the_worst_news_is_first(self):
        crowded = Tile(
            cell=SHELF,
            terrain_z=-10.0,
            bottom=SAND,
            hazards=(
                a_rock(key="deep one", x=400.0, y=500.0, top_z=-9.0),
                a_rock(key="shoal one", x=500.0, y=500.0, top_z=-1.5),
                a_rock(key="middling", x=600.0, y=500.0, top_z=-4.0),
            ),
        )
        found = TiledMapProvider(DictTileSource([crowded])).charted_dangers(
            WorldPosition(500.0, 500.0), 400.0
        )
        self.assertEqual([hazard.key for hazard in found], ["shoal one", "middling", "deep one"])

    def test_it_reads_the_tiles_the_sheet_covers_and_no_others(self):
        """
        A chart is a few kilometres and a world may be ten thousand tiles. Loading the
        ones outside the sheet to discover they are outside the sheet would put the cost
        of a world into the cost of a chart.

        """
        sea = TiledMapProvider(DictTileSource([a_shelf()]))
        sea.charted_dangers(WorldPosition(500.0, 500.0), 200.0)
        self.assertEqual(sea.loads, 1)

    def test_and_it_reads_all_of_them_when_the_sheet_is_wide(self):
        sea = TiledMapProvider(DictTileSource([a_shelf()]))
        sea.charted_dangers(WorldPosition(500.0, 500.0), 2500.0)
        self.assertGreater(sea.loads, 1)

    def test_the_chart_and_the_physics_agree_about_the_same_rock(self):
        """
        The property that makes this worth having. What a hull sweeps through and what
        the paper shows are two questions about one list.

        """
        drawn = self.sea.charted_dangers(WorldPosition(500.0, 500.0), 400.0)
        struck = self.sea.hazards_touching(
            WorldPosition(300.0, 500.0), WorldPosition(700.0, 500.0), width=6.0
        )
        self.assertEqual([h.key for h in drawn], [h.key for h in struck])
