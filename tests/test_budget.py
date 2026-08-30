"""
Tests for the reactor budget, and for the map provider that had to be kept to make it
worth having.

The budget is the only thing in this contrib measured in wall clock, so these are the
only tests here that sleep. They sleep in microseconds and assert about milliseconds,
which is a ratio wide enough that a loaded build machine does not make them lie.

"""

import time

from django.test import override_settings

from evennia.utils.test_resources import BaseEvenniaTestCase

from .. import config
from ..bathymetry import FlatSeaMapProvider, MaritimeMapProvider
from ..clock import ManualTimeProvider
from ..position import WorldPosition
from ..simulation import (
    ACTIVE,
    DEFAULT_BUDGET_MS,
    MaritimeSimulationService,
)
from ..tiles import DictTileSource, Tile, TiledMapProvider


class Slow:
    """An entity whose tick costs a known, measurable amount of wall clock."""

    def __init__(self, milliseconds):
        self.milliseconds = milliseconds
        self.ticks = 0

    def at_maritime_tick(self, elapsed):
        self.ticks += 1
        deadline = time.perf_counter() + self.milliseconds / 1000.0
        while time.perf_counter() < deadline:
            pass
        return True


class BudgetTestCase(BaseEvenniaTestCase):
    """A service with a manual clock and a fleet of known cost."""

    def service(self, budget_ms, batch_size=100):
        clock = ManualTimeProvider()
        return MaritimeSimulationService(clock, batch_size=batch_size, budget_ms=budget_ms)

    def fill(self, service, count, milliseconds):
        crew = [Slow(milliseconds) for _ in range(count)]
        for entity in crew:
            service.register(entity, ACTIVE)
        service.time.advance(10.0)
        return crew


class TestTheBudgetBounds(BudgetTestCase):
    """A pass stops when its time is spent."""

    def test_a_generous_budget_serves_everybody(self):
        service = self.service(budget_ms=200.0)
        self.fill(service, 8, milliseconds=1.0)
        self.assertEqual(len(service.tick()), 8)

    def test_a_tight_budget_does_not(self):
        service = self.service(budget_ms=5.0)
        self.fill(service, 20, milliseconds=2.0)
        served = service.tick()
        self.assertLess(len(served), 20)
        self.assertGreater(len(served), 0)

    def test_the_overrun_is_counted(self):
        service = self.service(budget_ms=5.0)
        self.fill(service, 20, milliseconds=2.0)
        service.tick()
        self.assertEqual(service.overruns, 1)

    def test_the_pass_reports_what_it_took(self):
        service = self.service(budget_ms=200.0)
        self.fill(service, 4, milliseconds=2.0)
        service.tick()
        self.assertGreater(service.last_pass_ms, 4.0)

    def test_at_least_one_entity_always_runs(self):
        """
        Checking the budget before an update rather than after would let one slow
        vessel starve herself out of the rotation forever. That is a livelock,
        not a limit.

        """
        service = self.service(budget_ms=0.001)
        crew = self.fill(service, 5, milliseconds=3.0)
        self.assertEqual(len(service.tick()), 1)
        self.assertEqual(sum(entity.ticks for entity in crew), 1)

    def test_the_rest_are_served_next_pass(self):
        """The rotation's cursor persists, so nothing is dropped - only deferred."""
        service = self.service(budget_ms=0.001)
        crew = self.fill(service, 4, milliseconds=2.0)
        for _ in range(4):
            service.time.advance(10.0)
            service.tick()
        self.assertTrue(all(entity.ticks >= 1 for entity in crew))

    def test_no_budget_at_all_means_no_limit(self):
        service = self.service(budget_ms=0.0)
        self.fill(service, 12, milliseconds=1.0)
        self.assertEqual(len(service.tick()), 12)

    def test_the_batch_is_still_a_backstop(self):
        """A budget alone would let one pathological entity be visited alone forever."""
        service = self.service(budget_ms=1000.0, batch_size=3)
        self.fill(service, 10, milliseconds=0.1)
        self.assertLessEqual(len(service.tick()), 3)

    def test_the_default_is_small_enough_to_be_invisible(self):
        """A player typing a command must never wait on the sea."""
        self.assertLessEqual(DEFAULT_BUDGET_MS, 20.0)


class TestTheMapProviderIsKept(BaseEvenniaTestCase):
    """
    The find that made the budget worth measuring.

    Notes:
        A `TiledMapProvider` caches the squares it has loaded. Building a fresh
        one per call threw that away every time anybody asked the depth of
        anything, so a vessel reloaded every tile she was over on every tick. It
        showed up as a tiled world costing more per vessel with one ship on it
        than with twenty, which is not a thing that can be true.

    """

    def setUp(self):
        super().setUp()
        config.forget_map_provider()
        self.addCleanup(config.forget_map_provider)

    def test_the_same_provider_comes_back(self):
        self.assertIs(config.map_provider(), config.map_provider())

    def test_and_it_keeps_what_it_has_loaded(self):
        provider = config.map_provider()
        if isinstance(provider, TiledMapProvider):
            provider.tile_at(WorldPosition(0.0, 0.0))
            self.assertGreater(config.map_provider().resident(), 0)

    @override_settings(MARITIME_MAP_PROVIDER="")
    def test_a_flat_sea_is_still_a_provider(self):
        self.assertIsInstance(config.map_provider(), FlatSeaMapProvider)

    @override_settings(MARITIME_MAP_PROVIDER="", MARITIME_DEFAULT_DEPTH=50.0)
    def test_changing_a_setting_gives_a_new_one(self):
        """A cached instance that outlived a settings change would waste an afternoon."""
        first = config.map_provider()
        with override_settings(MARITIME_DEFAULT_DEPTH=120.0):
            self.assertIsNot(config.map_provider(), first)

    @override_settings(MARITIME_MAP_PROVIDER="")
    def test_the_depth_follows_the_setting(self):
        with override_settings(MARITIME_DEFAULT_DEPTH=50.0):
            self.assertAlmostEqual(
                config.map_provider().terrain_z_at(WorldPosition(0.0, 0.0)), -50.0
            )

    def test_it_can_be_dropped_on_purpose(self):
        first = config.map_provider()
        self.assertTrue(config.forget_map_provider())
        self.assertIsNot(config.map_provider(), first)

    def test_dropping_nothing_says_so(self):
        config.forget_map_provider()
        self.assertFalse(config.forget_map_provider())

    def test_only_one_is_ever_held(self):
        """Keyed on the settings, and the old one goes when they change."""
        with override_settings(MARITIME_MAP_PROVIDER="", MARITIME_DEFAULT_DEPTH=10.0):
            config.map_provider()
        with override_settings(MARITIME_MAP_PROVIDER="", MARITIME_DEFAULT_DEPTH=20.0):
            config.map_provider()
        self.assertEqual(len(config._MAP_PROVIDER), 1)

    def test_it_is_still_a_map_provider(self):
        self.assertIsInstance(config.map_provider(), MaritimeMapProvider)


class TestTheBudgetSetting(BaseEvenniaTestCase):
    """A game can change it."""

    def test_the_default(self):
        self.assertAlmostEqual(config.tick_budget_ms(), DEFAULT_BUDGET_MS)

    @override_settings(MARITIME_TICK_BUDGET_MS=3.5)
    def test_a_game_can_tighten_it(self):
        self.assertAlmostEqual(config.tick_budget_ms(), 3.5)

    @override_settings(MARITIME_TICK_BUDGET_MS=0.0)
    def test_a_game_can_turn_it_off(self):
        self.assertEqual(config.tick_budget_ms(), 0.0)


class TestTilesAreWhyItMatters(BaseEvenniaTestCase):
    """The cache is only worth keeping because loading is not free."""

    def test_a_reloaded_provider_starts_empty(self):
        source = DictTileSource([Tile(cell=("default", 0, 0), terrain_z=-10.0)])
        first = TiledMapProvider(source)
        first.terrain_z_at(WorldPosition(100.0, 100.0))
        self.assertEqual(first.loads, 1)

        second = TiledMapProvider(source)
        second.terrain_z_at(WorldPosition(100.0, 100.0))
        self.assertEqual(second.loads, 1)

    def test_a_kept_one_does_not_reload(self):
        source = DictTileSource([Tile(cell=("default", 0, 0), terrain_z=-10.0)])
        provider = TiledMapProvider(source)
        for _ in range(20):
            provider.terrain_z_at(WorldPosition(100.0, 100.0))
        self.assertEqual(provider.loads, 1)
