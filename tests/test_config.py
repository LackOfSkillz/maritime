"""
Tests for settings resolution.

"""

from django.test import override_settings
from evennia.utils.test_resources import BaseEvenniaTestCase

from .. import config
from ..clock import GameTimeProvider, ManualTimeProvider, MaritimeTimeProvider
from ..rng import RNGContext


class NotAProvider:
    """A class that is deliberately not a time provider."""


class TestGetSetting(BaseEvenniaTestCase):
    """Reading prefixed settings."""

    def test_returns_default_when_unset(self):
        self.assertEqual(config.get_setting("DEFINITELY_NOT_SET", "fallback"), "fallback")

    def test_default_is_none_when_unspecified(self):
        self.assertIsNone(config.get_setting("DEFINITELY_NOT_SET"))

    @override_settings(MARITIME_SOME_VALUE=42)
    def test_reads_a_configured_value(self):
        self.assertEqual(config.get_setting("SOME_VALUE"), 42)

    @override_settings(MARITIME_SOME_VALUE=0)
    def test_falsy_values_are_returned_not_replaced(self):
        """0 and "" are real values; only absence falls back to the default."""
        self.assertEqual(config.get_setting("SOME_VALUE", 99), 0)

    def test_prefix_is_applied(self):
        """The setting name in a game's settings.py carries the prefix."""
        self.assertEqual(config.SETTING_PREFIX, "MARITIME_")


class TestLoadClass(BaseEvenniaTestCase):
    """Dotted-path resolution."""

    def test_loads_a_class(self):
        path = f"{config.__package__}.clock.ManualTimeProvider"
        self.assertIs(config.load_class(path), ManualTimeProvider)

    def test_accepts_a_matching_expected_type(self):
        path = f"{config.__package__}.clock.ManualTimeProvider"
        self.assertIs(config.load_class(path, expected=MaritimeTimeProvider), ManualTimeProvider)

    def test_rejects_a_mismatched_type(self):
        """
        A misconfiguration must fail at load, naming what was wrong.

        Otherwise it surfaces much later as a missing attribute somewhere deep in
        the simulation, with nothing pointing back at the setting.

        """
        path = f"{__package__}.test_config.NotAProvider"
        with self.assertRaises(TypeError):
            config.load_class(path, expected=MaritimeTimeProvider)

    def test_error_names_the_setting_prefix(self):
        path = f"{__package__}.test_config.NotAProvider"
        with self.assertRaises(TypeError) as ctx:
            config.load_class(path, expected=MaritimeTimeProvider)
        self.assertIn("MARITIME_", str(ctx.exception))

    def test_unimportable_path_raises(self):
        with self.assertRaises(ImportError):
            config.load_class("no.such.module.NoSuchClass")


class TestTimeProvider(BaseEvenniaTestCase):
    """The configured time provider."""

    def test_defaults_to_the_game_clock(self):
        self.assertIsInstance(config.time_provider(), GameTimeProvider)

    def test_default_path_matches_this_package(self):
        """
        The default resolves relative to wherever this package actually lives.

        Note this cannot detect a *hardcoded* path while the contrib sits in the
        Evennia tree, since the literal and the derived value are identical there.
        That case is caught statically by check_discipline.py instead.

        """
        self.assertEqual(
            config.DEFAULT_TIME_PROVIDER, f"{config.__package__}.clock.GameTimeProvider"
        )

    def test_default_path_resolves(self):
        self.assertIs(config.load_class(config.DEFAULT_TIME_PROVIDER), GameTimeProvider)

    def test_returns_a_usable_provider(self):
        self.assertIsInstance(config.time_provider().now(), float)

    def test_returns_a_new_instance_each_call(self):
        """A cached instance would outlive a settings change during development."""
        self.assertIsNot(config.time_provider(), config.time_provider())

    def test_game_may_substitute_its_own(self):
        path = f"{config.__package__}.clock.ManualTimeProvider"
        with override_settings(MARITIME_TIME_PROVIDER=path):
            self.assertIsInstance(config.time_provider(), ManualTimeProvider)

    def test_substituted_provider_must_be_a_time_provider(self):
        path = f"{__package__}.test_config.NotAProvider"
        with override_settings(MARITIME_TIME_PROVIDER=path):
            with self.assertRaises(TypeError):
                config.time_provider()


class TestRngConfig(BaseEvenniaTestCase):
    """Seed configuration."""

    def test_seed_is_unset_by_default(self):
        """Live play should not replay the same storm every restart."""
        self.assertIsNone(config.rng_seed())

    @override_settings(MARITIME_RNG_SEED=729922)
    def test_reads_a_pinned_seed(self):
        self.assertEqual(config.rng_seed(), 729922)

    @override_settings(MARITIME_RNG_SEED="729922")
    def test_coerces_a_string_seed(self):
        """Settings files are hand-edited; a quoted number is an easy slip."""
        self.assertEqual(config.rng_seed(), 729922)

    def test_context_is_unseeded_by_default(self):
        first = config.rng_context()
        second = config.rng_context()
        self.assertNotEqual(first.seed, second.seed)

    def test_context_is_an_rng_context(self):
        self.assertIsInstance(config.rng_context(), RNGContext)

    @override_settings(MARITIME_RNG_SEED=729922)
    def test_pinned_seed_makes_contexts_replay(self):
        first = config.rng_context()
        second = config.rng_context()
        self.assertEqual(first.stream("weather").random(), second.stream("weather").random())
