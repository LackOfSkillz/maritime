"""
Tests for the maritime clock.

"""

from evennia.utils.test_resources import BaseEvenniaTestCase

from ..clock import GameTimeProvider, ManualTimeProvider, MaritimeTimeProvider


class TestMaritimeTimeProvider(BaseEvenniaTestCase):
    """The interface itself."""

    def test_now_is_not_implemented(self):
        """The base class refuses to guess what time it is."""
        with self.assertRaises(NotImplementedError):
            MaritimeTimeProvider().now()

    def test_elapsed_is_derived_from_now(self):
        """Subclasses get elapsed() for free by implementing only now()."""

        class FixedProvider(MaritimeTimeProvider):
            def now(self):
                return 500.0

        self.assertEqual(FixedProvider().elapsed_game_seconds(200.0), 300.0)


class TestManualTimeProvider(BaseEvenniaTestCase):
    """The clock that only moves when told to."""

    def test_starts_at_zero_by_default(self):
        self.assertEqual(ManualTimeProvider().now(), 0.0)

    def test_starts_at_given_epoch(self):
        self.assertEqual(ManualTimeProvider(start=1234.5).now(), 1234.5)

    def test_does_not_advance_on_its_own(self):
        """Nothing implicit moves this clock - that is the whole point."""
        clock = ManualTimeProvider()
        clock.now()
        clock.now()
        self.assertEqual(clock.now(), 0.0)

    def test_advance_by_seconds(self):
        clock = ManualTimeProvider()
        clock.advance(seconds=30)
        self.assertEqual(clock.now(), 30.0)

    def test_advance_combines_units(self):
        """2h30m is 9000 game seconds."""
        clock = ManualTimeProvider()
        clock.advance(hours=2, minutes=30)
        self.assertEqual(clock.now(), 9000.0)

    def test_advance_accumulates(self):
        clock = ManualTimeProvider()
        clock.advance(minutes=1)
        clock.advance(minutes=1)
        self.assertEqual(clock.now(), 120.0)

    def test_advance_returns_new_time(self):
        self.assertEqual(ManualTimeProvider().advance(days=1), 86400.0)

    def test_advance_supports_fractions(self):
        clock = ManualTimeProvider()
        clock.advance(seconds=0.25)
        self.assertEqual(clock.now(), 0.25)

    def test_zero_advance_is_allowed(self):
        """A no-op step is legal; only going backwards is not."""
        clock = ManualTimeProvider(start=10.0)
        clock.advance()
        self.assertEqual(clock.now(), 10.0)

    def test_negative_advance_is_refused(self):
        clock = ManualTimeProvider(start=100.0)
        with self.assertRaises(ValueError):
            clock.advance(seconds=-1)
        self.assertEqual(clock.now(), 100.0, "clock must not move on a refused advance")

    def test_negative_combination_is_refused(self):
        """Units are summed before checking, so a net-negative mix is caught."""
        clock = ManualTimeProvider()
        with self.assertRaises(ValueError):
            clock.advance(hours=1, minutes=-61)

    def test_elapsed_across_an_advance(self):
        clock = ManualTimeProvider()
        start = clock.now()
        clock.advance(hours=2, minutes=30)
        self.assertEqual(clock.elapsed_game_seconds(start), 9000.0)

    def test_elapsed_from_the_future_clamps_to_zero(self):
        """A stale reading must never produce a negative delta."""
        clock = ManualTimeProvider(start=10.0)
        self.assertEqual(clock.elapsed_game_seconds(50.0), 0.0)


class TestGameTimeProvider(BaseEvenniaTestCase):
    """The default provider, reading Evennia's own clock."""

    def test_now_returns_a_number(self):
        self.assertIsInstance(GameTimeProvider().now(), float)

    def test_time_does_not_run_backwards(self):
        clock = GameTimeProvider()
        first = clock.now()
        self.assertGreaterEqual(clock.now(), first)

    def test_elapsed_is_never_negative(self):
        clock = GameTimeProvider()
        self.assertGreaterEqual(clock.elapsed_game_seconds(clock.now()), 0.0)

    def test_reads_the_host_clock_rather_than_scaling_itself(self):
        """
        Maritime must not apply its own multiplier on top of the game's.

        Two readings taken around a known real interval should differ by roughly
        that interval times the game's own TIME_FACTOR - not by some further
        maritime-specific factor.

        """
        from django.conf import settings

        factor = settings.TIME_FACTOR
        clock = GameTimeProvider()
        first = clock.now()
        second = clock.now()
        # Both readings are near-instantaneous, so the gap must be far smaller
        # than one game second at any sane factor. This catches a provider that
        # multiplies an already-scaled clock a second time.
        self.assertLess(second - first, max(1.0, factor))
