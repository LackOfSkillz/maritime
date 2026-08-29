"""
Tests for terrain elevation, tides and derived water depth.

"""

from evennia.utils.test_resources import BaseEvenniaTestCase

from ..bathymetry import (
    DATUM,
    FlatSeaMapProvider,
    FlatTideProvider,
    MaritimeMapProvider,
    MaritimeTideProvider,
)
from ..position import WorldPosition


class SlopingShore(MaritimeMapProvider):
    """
    A shore that rises from deep water to dry land as x increases.

    terrain_z = x - 20, so x=0 is 20 m deep, x=20 is exactly at datum, and x=25
    stands 5 m above it. Enough to test the shoreline without inventing a map format.

    """

    def terrain_z_at(self, position):
        return position.x - 20.0


class RisingTide(MaritimeTideProvider):
    """A surface that climbs one metre per game hour, for testing tidal depth."""

    def surface_z_at(self, position, game_time):
        return game_time / 3600.0


class TestFlatTideProvider(BaseEvenniaTestCase):
    """The motionless surface."""

    def setUp(self):
        super().setUp()
        self.here = WorldPosition(0.0, 0.0)

    def test_defaults_to_the_datum(self):
        self.assertEqual(FlatTideProvider().surface_z_at(self.here, 0.0), DATUM)

    def test_ignores_time(self):
        tides = FlatTideProvider()
        self.assertEqual(
            tides.surface_z_at(self.here, 0.0), tides.surface_z_at(self.here, 999999.0)
        )

    def test_ignores_position(self):
        tides = FlatTideProvider()
        self.assertEqual(
            tides.surface_z_at(self.here, 0.0),
            tides.surface_z_at(WorldPosition(5000.0, -9000.0), 0.0),
        )

    def test_surface_may_sit_off_datum(self):
        """A lake can sit above the world datum."""
        self.assertEqual(FlatTideProvider(surface_z=210.0).surface_z_at(self.here, 0.0), 210.0)


class TestProviderInterfaces(BaseEvenniaTestCase):
    """The abstract bases refuse to guess."""

    def test_tide_provider_requires_implementation(self):
        with self.assertRaises(NotImplementedError):
            MaritimeTideProvider().surface_z_at(WorldPosition(0.0, 0.0), 0.0)

    def test_map_provider_requires_terrain(self):
        with self.assertRaises(NotImplementedError):
            MaritimeMapProvider().terrain_z_at(WorldPosition(0.0, 0.0))


class TestFlatSeaMapProvider(BaseEvenniaTestCase):
    """Uniform-depth sea."""

    def setUp(self):
        super().setUp()
        self.here = WorldPosition(0.0, 0.0)

    def test_depth_matches_construction(self):
        self.assertEqual(FlatSeaMapProvider(depth=40.0).water_depth_at(self.here, 0.0), 40.0)

    def test_terrain_sits_below_datum(self):
        self.assertEqual(FlatSeaMapProvider(depth=40.0).terrain_z_at(self.here), -40.0)

    def test_depth_is_uniform(self):
        sea = FlatSeaMapProvider(depth=40.0)
        self.assertEqual(
            sea.water_depth_at(WorldPosition(9999.0, -9999.0), 0.0),
            sea.water_depth_at(self.here, 0.0),
        )

    def test_negative_depth_is_refused(self):
        """Negative depth is land, which this provider does not model."""
        with self.assertRaises(ValueError):
            FlatSeaMapProvider(depth=-1.0)

    def test_zero_depth_is_allowed(self):
        self.assertEqual(FlatSeaMapProvider(depth=0.0).water_depth_at(self.here, 0.0), 0.0)


class TestDerivedDepth(BaseEvenniaTestCase):
    """Depth is computed from surface minus terrain, never stored."""

    def setUp(self):
        super().setUp()
        self.shore = SlopingShore()

    def test_depth_follows_terrain(self):
        self.assertEqual(self.shore.water_depth_at(WorldPosition(0.0, 0.0), 0.0), 20.0)

    def test_shallower_as_terrain_rises(self):
        self.assertEqual(self.shore.water_depth_at(WorldPosition(17.0, 0.0), 0.0), 3.0)

    def test_dry_land_has_no_water(self):
        self.assertEqual(self.shore.water_depth_at(WorldPosition(25.0, 0.0), 0.0), 0.0)

    def test_depth_never_goes_negative(self):
        """
        Negative depth would read as water below the seabed to anything
        comparing against a draft. How far the ground stands above water is
        still available from terrain_z_at.

        """
        self.assertGreaterEqual(self.shore.water_depth_at(WorldPosition(100.0, 0.0), 0.0), 0.0)

    def test_terrain_above_water_is_still_reported(self):
        self.assertEqual(self.shore.terrain_z_at(WorldPosition(25.0, 0.0)), 5.0)

    def test_depth_ignores_the_sampled_z(self):
        """Only x, y and region matter - what the ground does is independent of
        the elevation you happened to ask from."""
        surface = WorldPosition(10.0, 0.0, 0.0)
        deep = WorldPosition(10.0, 0.0, -500.0)
        self.assertEqual(
            self.shore.water_depth_at(surface, 0.0), self.shore.water_depth_at(deep, 0.0)
        )


class TestTidalDepth(BaseEvenniaTestCase):
    """Moving the surface changes every depth without touching terrain."""

    def setUp(self):
        super().setUp()
        self.sea = FlatSeaMapProvider(depth=3.0, tide_provider=RisingTide())
        self.here = WorldPosition(0.0, 0.0)

    def test_depth_at_low_water(self):
        self.assertAlmostEqual(self.sea.water_depth_at(self.here, 0.0), 3.0)

    def test_depth_rises_with_the_tide(self):
        self.assertAlmostEqual(self.sea.water_depth_at(self.here, 3600.0), 4.0)

    def test_terrain_does_not_move_with_the_tide(self):
        """The seabed is unchanged; only the surface moved."""
        self.assertEqual(self.sea.terrain_z_at(self.here), self.sea.terrain_z_at(self.here))
        self.assertEqual(self.sea.terrain_z_at(self.here), -3.0)

    def test_surface_elevation_tracks_time(self):
        self.assertAlmostEqual(self.sea.sea_surface_z_at(self.here, 7200.0), 2.0)

    def test_a_shoal_can_dry_out_and_flood(self):
        """
        The whole point of one shared model.

        A bank 2 m above datum is dry at low water and covered once the tide
        rises past it, with no terrain changing.

        """

        class Bank(MaritimeMapProvider):
            def terrain_z_at(self, position):
                return 2.0

        bank = Bank(tide_provider=RisingTide())
        self.assertFalse(bank.is_submerged_at(self.here, 0.0))
        self.assertTrue(bank.is_submerged_at(self.here, 3600.0 * 3))


class TestShoreline(BaseEvenniaTestCase):
    """The shoreline is where terrain crosses the surface."""

    def setUp(self):
        super().setUp()
        self.shore = SlopingShore()

    def test_submerged_below_the_crossing(self):
        self.assertTrue(self.shore.is_submerged_at(WorldPosition(19.0, 0.0), 0.0))

    def test_dry_above_the_crossing(self):
        self.assertFalse(self.shore.is_submerged_at(WorldPosition(21.0, 0.0), 0.0))

    def test_exactly_at_the_surface_is_not_submerged(self):
        """Zero depth is a waterline, not water."""
        self.assertFalse(self.shore.is_submerged_at(WorldPosition(20.0, 0.0), 0.0))


class TestProjection(BaseEvenniaTestCase):
    """Projecting a point onto the surface or the seabed."""

    def setUp(self):
        super().setUp()
        self.sea = FlatSeaMapProvider(depth=40.0)
        self.here = WorldPosition(100.0, 200.0, -12.0)

    def test_surface_position_sits_at_the_surface(self):
        self.assertEqual(self.sea.surface_position(self.here, 0.0).z, DATUM)

    def test_surface_position_keeps_x_and_y(self):
        surfaced = self.sea.surface_position(self.here, 0.0)
        self.assertEqual((surfaced.x, surfaced.y), (100.0, 200.0))

    def test_seabed_position_sits_on_the_ground(self):
        self.assertEqual(self.sea.seabed_position(self.here).z, -40.0)

    def test_seabed_position_keeps_x_and_y(self):
        settled = self.sea.seabed_position(self.here)
        self.assertEqual((settled.x, settled.y), (100.0, 200.0))

    def test_surface_position_follows_the_tide(self):
        tidal = FlatSeaMapProvider(depth=40.0, tide_provider=RisingTide())
        self.assertAlmostEqual(tidal.surface_position(self.here, 3600.0).z, 1.0)

    def test_seabed_position_accepts_a_time_for_symmetry(self):
        """Terrain does not move, but call sites read better when both match."""
        self.assertEqual(
            self.sea.seabed_position(self.here), self.sea.seabed_position(self.here, 9999.0)
        )
