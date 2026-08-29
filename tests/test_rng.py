"""
Tests for deterministic randomness.

"""

import subprocess
import sys

from evennia.utils.test_resources import BaseEvenniaTestCase

from ..rng import (
    AI,
    COMBAT,
    DAMAGE,
    NAVIGATION,
    STANDARD_STREAMS,
    WEATHER,
    RNGContext,
    derive_seed,
)


class TestDeriveSeed(BaseEvenniaTestCase):
    """Seed derivation from master seed plus stream name."""

    def test_is_deterministic(self):
        self.assertEqual(derive_seed(1234, "weather"), derive_seed(1234, "weather"))

    def test_differs_by_stream_name(self):
        self.assertNotEqual(derive_seed(1234, "weather"), derive_seed(1234, "combat"))

    def test_differs_by_master_seed(self):
        self.assertNotEqual(derive_seed(1234, "weather"), derive_seed(5678, "weather"))

    def test_returns_an_int(self):
        self.assertIsInstance(derive_seed(1, "x"), int)


class TestRNGContext(BaseEvenniaTestCase):
    """The context and its streams."""

    def test_same_seed_reproduces_a_stream(self):
        first = RNGContext(seed=729922).stream(WEATHER).random()
        second = RNGContext(seed=729922).stream(WEATHER).random()
        self.assertEqual(first, second)

    def test_different_seeds_diverge(self):
        first = RNGContext(seed=1).stream(WEATHER).random()
        second = RNGContext(seed=2).stream(WEATHER).random()
        self.assertNotEqual(first, second)

    def test_different_streams_produce_different_values(self):
        """
        Two streams from one context must not share a sequence.

        Seeding every stream from the master seed alone would make weather,
        combat and damage roll identically in lockstep - independent-looking but
        perfectly correlated, which is worse than obviously shared state because
        nothing appears wrong until the numbers are compared.

        """
        rng = RNGContext(seed=42)
        values = [rng.stream(name).random() for name in STANDARD_STREAMS]
        self.assertEqual(len(set(values)), len(values))

    def test_streams_are_independent(self):
        """
        Draining one stream must not shift another.

        This is what lets a failing scenario be narrowed: change the weather
        model without disturbing what combat rolls.

        """
        drained = RNGContext(seed=42)
        for _ in range(100):
            drained.stream(WEATHER).random()
        combat_after_draining = drained.stream(COMBAT).random()

        untouched = RNGContext(seed=42).stream(COMBAT).random()
        self.assertEqual(combat_after_draining, untouched)

    def test_stream_advances_between_calls(self):
        """The same name returns the same generator, not a fresh one."""
        rng = RNGContext(seed=7)
        first = rng.stream(COMBAT).random()
        second = rng.stream(COMBAT).random()
        self.assertNotEqual(first, second)

    def test_same_name_returns_the_same_object(self):
        rng = RNGContext(seed=7)
        self.assertIs(rng.stream(COMBAT), rng.stream(COMBAT))

    def test_full_sequence_reproduces(self):
        """A whole interleaved run replays identically from the seed."""

        def run():
            rng = RNGContext(seed=99)
            out = []
            for _ in range(20):
                out.append(rng.stream(NAVIGATION).random())
                out.append(rng.stream(DAMAGE).randint(1, 100))
                out.append(rng.stream(AI).choice("abcdef"))
            return out

        self.assertEqual(run(), run())

    def test_seed_is_generated_when_omitted(self):
        rng = RNGContext()
        self.assertIsInstance(rng.seed, int)

    def test_generated_seeds_differ(self):
        self.assertNotEqual(RNGContext().seed, RNGContext().seed)

    def test_generated_seed_is_reproducible_once_known(self):
        """An unseeded run can be replayed by recording its seed."""
        original = RNGContext()
        value = original.stream(WEATHER).random()
        replay = RNGContext(seed=original.seed).stream(WEATHER).random()
        self.assertEqual(value, replay)

    def test_unnamed_stream_is_refused(self):
        rng = RNGContext(seed=1)
        with self.assertRaises(ValueError):
            rng.stream("")

    def test_arbitrary_stream_names_are_allowed(self):
        """Games may add their own streams without editing this module."""
        rng = RNGContext(seed=1)
        self.assertIsNotNone(rng.stream("tides").random())

    def test_reset_rewinds_streams_without_changing_seed(self):
        rng = RNGContext(seed=55)
        first = rng.stream(COMBAT).random()
        rng.reset()
        self.assertEqual(rng.seed, 55)
        self.assertEqual(rng.stream(COMBAT).random(), first)

    def test_reset_returns_the_context(self):
        rng = RNGContext(seed=1)
        self.assertIs(rng.reset(), rng)

    def test_active_streams_reports_what_was_used(self):
        rng = RNGContext(seed=1)
        rng.stream(WEATHER).random()
        rng.stream(COMBAT).random()
        self.assertEqual(rng.active_streams(), (COMBAT, WEATHER))

    def test_active_streams_starts_empty(self):
        self.assertEqual(RNGContext(seed=1).active_streams(), ())

    def test_repr_shows_the_seed(self):
        self.assertIn("729922", repr(RNGContext(seed=729922)))

    def test_standard_streams_are_distinct(self):
        self.assertEqual(len(set(STANDARD_STREAMS)), len(STANDARD_STREAMS))


class TestCrossProcessReproducibility(BaseEvenniaTestCase):
    """Seeds must survive a process restart."""

    def test_stable_across_separate_interpreters(self):
        """
        Python salts string hashing per process unless PYTHONHASHSEED is fixed.

        If seed derivation ever reverts to the builtin hash(), this catches it -
        the value would differ between two interpreters and reproducibility would
        be silently lost across a server restart.

        """
        code = (
            "import hashlib;"
            "d=hashlib.sha256('729922:weather'.encode('utf-8')).digest();"
            "print(int.from_bytes(d[:8],'big'))"
        )
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, check=True
        )
        self.assertEqual(int(result.stdout.strip()), derive_seed(729922, WEATHER))
