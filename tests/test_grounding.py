"""
Tests for finding the bottom.

"""

from django.test import override_settings

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest, BaseEvenniaTestCase

from ..bathymetry import MUD, REEF, ROCK, FlatSeaMapProvider, MaritimeMapProvider
from ..grounding import (
    AGROUND,
    HOLED,
    SHOAL_WARNING_CLEARANCE,
    TOUCHED,
    check_grounding,
    is_shoaling,
    keel_clearance,
    refloats_on_tide,
)
from ..motion import HelmOrders, MotionLimits
from ..position import EAST, WorldPosition
from ..typeclasses import ShipRoom, Vessel
from ..vessel import OPEN

HERE = WorldPosition(0.0, 0.0)


class Shelf(MaritimeMapProvider):
    """Deep to the west, drying out to the east: terrain_z = x/100 - 20."""

    def terrain_z_at(self, position):
        return position.x / 100.0 - 20.0


class ReefPatch(MaritimeMapProvider):
    """A rock shelf one metre down, everywhere."""

    def __init__(self, bottom=REEF, **kwargs):
        super().__init__(**kwargs)
        self._bottom = bottom

    def terrain_z_at(self, position):
        return -1.0

    def bottom_type_at(self, position):
        return self._bottom


class TestKeelClearance(BaseEvenniaTestCase):
    """Water under the keel."""

    def setUp(self):
        super().setUp()
        self.sea = FlatSeaMapProvider(depth=10.0)

    def test_clearance_is_depth_less_draft(self):
        self.assertAlmostEqual(keel_clearance(HERE, 2.0, self.sea, 0.0), 8.0)

    def test_a_deeper_hull_has_less_water(self):
        deep = keel_clearance(HERE, 6.0, self.sea, 0.0)
        shallow = keel_clearance(HERE, 2.0, self.sea, 0.0)
        self.assertLess(deep, shallow)

    def test_goes_negative_when_the_hull_is_in_the_ground(self):
        self.assertLess(keel_clearance(HERE, 12.0, self.sea, 0.0), 0.0)

    def test_follows_the_terrain(self):
        shelf = Shelf()
        deep = keel_clearance(WorldPosition(0.0, 0.0), 2.0, shelf, 0.0)
        shoal = keel_clearance(WorldPosition(1500.0, 0.0), 2.0, shelf, 0.0)
        self.assertGreater(deep, shoal)

    def test_the_tide_changes_it(self):
        """
        Clearance measured against the datum is a different number from the one
        that will actually run her aground.

        """

        class Rising(MaritimeMapProvider):
            def terrain_z_at(self, position):
                return -3.0

        from ..bathymetry import MaritimeTideProvider

        class Tide(MaritimeTideProvider):
            def surface_z_at(self, position, game_time):
                return game_time / 3600.0

        world = Rising(tide_provider=Tide())
        low = keel_clearance(HERE, 2.0, world, 0.0)
        high = keel_clearance(HERE, 2.0, world, 3600.0)
        self.assertAlmostEqual(high - low, 1.0)


class TestShoalWarning(BaseEvenniaTestCase):
    """Standing into shallow water."""

    def test_deep_water_is_not_shoaling(self):
        self.assertFalse(is_shoaling(HERE, 2.0, FlatSeaMapProvider(depth=50.0), 0.0))

    def test_shallow_water_is(self):
        self.assertTrue(is_shoaling(HERE, 2.0, FlatSeaMapProvider(depth=3.0), 0.0))

    def test_warns_before_grounding(self):
        """
        A vessel that grounds without warning is an accident; one that grounds
        after the leadsman has called is a decision.

        """
        sea = FlatSeaMapProvider(depth=2.0 + SHOAL_WARNING_CLEARANCE - 0.5)
        self.assertTrue(is_shoaling(HERE, 2.0, sea, 0.0))
        self.assertTrue(check_grounding(HERE, 2.0, 1.0, sea, 0.0))


class TestCheckGrounding(BaseEvenniaTestCase):
    """Meeting the ground."""

    def test_clear_water_succeeds(self):
        result = check_grounding(HERE, 2.0, 3.0, FlatSeaMapProvider(depth=50.0), 0.0)
        self.assertTrue(result)

    def test_reports_clearance_when_clear(self):
        result = check_grounding(HERE, 2.0, 3.0, FlatSeaMapProvider(depth=10.0), 0.0)
        self.assertAlmostEqual(result.clearance, 8.0)

    def test_too_little_water_fails(self):
        result = check_grounding(HERE, 5.0, 3.0, FlatSeaMapProvider(depth=2.0), 0.0)
        self.assertFalse(result)

    def test_reports_negative_clearance_when_aground(self):
        result = check_grounding(HERE, 5.0, 3.0, FlatSeaMapProvider(depth=2.0), 0.0)
        self.assertLess(result.clearance, 0.0)

    def test_slow_contact_merely_touches(self):
        result = check_grounding(HERE, 5.0, 0.2, FlatSeaMapProvider(depth=2.0), 0.0)
        self.assertEqual(result.severity, TOUCHED)

    def test_fast_contact_on_sand_runs_her_aground(self):
        result = check_grounding(HERE, 5.0, 5.0, FlatSeaMapProvider(depth=2.0), 0.0)
        self.assertEqual(result.severity, AGROUND)

    def test_fast_contact_on_rock_holes_her(self):
        """
        Why bottom type is worth modelling. Otherwise every grounding is the
        same event.

        """
        result = check_grounding(HERE, 5.0, 5.0, ReefPatch(bottom=ROCK), 0.0)
        self.assertEqual(result.severity, HOLED)

    def test_slow_contact_on_rock_does_not_hole_her(self):
        result = check_grounding(HERE, 5.0, 0.2, ReefPatch(bottom=ROCK), 0.0)
        self.assertEqual(result.severity, TOUCHED)

    def test_reports_the_bottom(self):
        result = check_grounding(HERE, 5.0, 1.0, ReefPatch(bottom=REEF), 0.0)
        self.assertEqual(result.bottom, REEF)


class TestRefloating(BaseEvenniaTestCase):
    """Getting off again."""

    def test_soft_ground_refloats(self):
        """
        Only works because tide and terrain share one model: the water rises,
        the seabed does not, and a negative clearance becomes positive.

        """
        result = check_grounding(HERE, 5.0, 0.5, FlatSeaMapProvider(depth=2.0), 0.0)
        self.assertTrue(refloats_on_tide(result))

    def test_a_holed_hull_does_not(self):
        result = check_grounding(HERE, 5.0, 5.0, ReefPatch(bottom=ROCK), 0.0)
        self.assertFalse(refloats_on_tide(result))

    def test_reef_does_not_give_her_back(self):
        result = check_grounding(HERE, 5.0, 0.5, ReefPatch(bottom=REEF), 0.0)
        self.assertFalse(refloats_on_tide(result))

    def test_mud_does(self):
        class Mudflat(MaritimeMapProvider):
            def terrain_z_at(self, position):
                return -1.0

            def bottom_type_at(self, position):
                return MUD

        result = check_grounding(HERE, 5.0, 0.5, Mudflat(), 0.0)
        self.assertTrue(refloats_on_tide(result))


class TestVesselGrounding(BaseEvenniaTest):
    """
    A hull actually running aground.

    These override MARITIME_MAP_PROVIDER as well as the depth. A game that
    configures its own seabed would otherwise supply it here too, and these
    tests would quietly be measuring that map instead of the flat one they
    describe.

    """

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Test Sloop")
        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.deck.db.vessel = self.hull
        self.deck.exposure = OPEN
        self.hull.maritime_position = WorldPosition(0.0, 0.0)
        self.hull.motion_limits = MotionLimits(max_speed=10.0, acceleration=2.0, turn_rate=8.0)
        self.hull.heading = EAST
        self.hull.orders = HelmOrders(heading=EAST, speed=8.0)
        self.hull.draft = 2.0

    def test_deep_water_leaves_her_sailing(self):
        with override_settings(MARITIME_MAP_PROVIDER="", MARITIME_DEFAULT_DEPTH=100.0):
            for _ in range(10):
                self.hull.at_maritime_tick(5.0)
        self.assertFalse(self.hull.aground)

    def test_too_little_water_grounds_her(self):
        """The acceptance criterion: running onto the shoal stops her."""
        with override_settings(MARITIME_MAP_PROVIDER="", MARITIME_DEFAULT_DEPTH=1.0):
            self.hull.at_maritime_tick(5.0)
        self.assertTrue(self.hull.aground)

    def test_grounding_takes_the_way_off_her(self):
        with override_settings(MARITIME_MAP_PROVIDER="", MARITIME_DEFAULT_DEPTH=1.0):
            self.hull.at_maritime_tick(5.0)
        self.assertEqual(self.hull.speed, 0.0)

    def test_she_stays_put_once_aground(self):
        with override_settings(MARITIME_MAP_PROVIDER="", MARITIME_DEFAULT_DEPTH=1.0):
            self.hull.at_maritime_tick(5.0)
            where = self.hull.maritime_position
            for _ in range(10):
                self.hull.at_maritime_tick(5.0)
        self.assertEqual(self.hull.maritime_position, where)

    def test_the_ship_is_told(self):
        heard = []
        self.deck.msg_contents = lambda text, **kwargs: heard.append(text)
        with override_settings(MARITIME_MAP_PROVIDER="", MARITIME_DEFAULT_DEPTH=1.0):
            self.hull.at_maritime_tick(5.0)
        self.assertTrue(any("aground" in text for text in heard))

    def test_clearance_is_reportable(self):
        with override_settings(MARITIME_MAP_PROVIDER="", MARITIME_DEFAULT_DEPTH=20.0):
            self.assertAlmostEqual(self.hull.keel_clearance(), 18.0)

    def test_an_unlaunched_vessel_has_no_clearance(self):
        idle = create.create_object(Vessel, key="On The Stocks")
        self.assertIsNone(idle.keel_clearance())


class TestSurfaceConstraint(BaseEvenniaTest):
    """A surface vessel floats, and cannot be sailed under."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Test Sloop")
        self.hull.motion_limits = MotionLimits(max_speed=10.0, acceleration=2.0, turn_rate=8.0)
        self.hull.heading = EAST
        self.hull.orders = HelmOrders(heading=EAST, speed=5.0)
        self.hull.draft = 2.0

    def test_a_submerged_hull_is_returned_to_the_surface(self):
        """
        Her elevation is decided by the water, not by anything she does. Setting
        a negative z used to leave her sailing along forty metres down.

        """
        self.hull.maritime_position = WorldPosition(0.0, 0.0, -40.0)
        with override_settings(MARITIME_MAP_PROVIDER="", MARITIME_DEFAULT_DEPTH=100.0):
            self.hull.at_maritime_tick(5.0)
        self.assertAlmostEqual(self.hull.maritime_position.z, 0.0)

    def test_she_stays_at_the_surface_while_sailing(self):
        self.hull.maritime_position = WorldPosition(0.0, 0.0)
        with override_settings(MARITIME_MAP_PROVIDER="", MARITIME_DEFAULT_DEPTH=100.0):
            for _ in range(10):
                self.hull.at_maritime_tick(5.0)
        self.assertAlmostEqual(self.hull.maritime_position.z, 0.0)
