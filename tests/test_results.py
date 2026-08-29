"""
Tests for structured domain results.

"""

from dataclasses import FrozenInstanceError, dataclass

from evennia.utils.test_resources import BaseEvenniaTestCase

from ..results import (
    INVALID_TARGET,
    NOT_PERMITTED,
    PRECONDITION_FAILED,
    UNSUPPORTED,
    Result,
)


@dataclass(frozen=True, kw_only=True)
class ManeuverResult(Result):
    """A stand-in for a real operation's result, used to test subclassing."""

    heading_change: float = 0.0
    speed_change: float = 0.0
    heel: float = 0.0


class TestResult(BaseEvenniaTestCase):
    """The base result type."""

    def test_ok_is_successful(self):
        self.assertTrue(Result.ok().success)

    def test_failed_is_unsuccessful(self):
        self.assertFalse(Result.failed(NOT_PERMITTED).success)

    def test_failed_carries_its_code(self):
        self.assertEqual(Result.failed(INVALID_TARGET).code, INVALID_TARGET)

    def test_success_has_no_code_by_default(self):
        self.assertEqual(Result.ok().code, "")

    def test_success_may_carry_a_code(self):
        """Some successes are worth distinguishing - accepted but deferred, say."""
        self.assertEqual(Result.ok(code="deferred").code, "deferred")

    def test_failure_without_a_code_is_refused(self):
        """
        An uncoded failure cannot be branched on or rendered.

        It would be indistinguishable from every other failure, which is exactly
        when the caller most needs to tell them apart.

        """
        with self.assertRaises(ValueError):
            Result(success=False)

    def test_failure_with_empty_code_is_refused(self):
        with self.assertRaises(ValueError):
            Result(success=False, code="")

    def test_truthiness_follows_success(self):
        self.assertTrue(bool(Result.ok()))
        self.assertFalse(bool(Result.failed(UNSUPPORTED)))

    def test_reads_naturally_in_a_conditional(self):
        result = Result.failed(PRECONDITION_FAILED)
        self.assertTrue(not result)

    def test_is_immutable(self):
        result = Result.ok()
        with self.assertRaises(FrozenInstanceError):
            result.success = False

    def test_requires_keyword_arguments(self):
        """
        Positional construction is refused.

        Keyword-only fields are what let subclasses add defaulted fields without
        tripping the dataclass rule against a non-default following a default.

        """
        with self.assertRaises(TypeError):
            Result(True)

    def test_equality_is_by_value(self):
        self.assertEqual(Result.ok(), Result.ok())
        self.assertNotEqual(Result.ok(), Result.failed(UNSUPPORTED))

    def test_standard_codes_are_distinct(self):
        codes = (NOT_PERMITTED, PRECONDITION_FAILED, INVALID_TARGET, UNSUPPORTED)
        self.assertEqual(len(set(codes)), len(codes))


class TestWithFields(BaseEvenniaTestCase):
    """Enriching a result as it passes through a layer."""

    def test_returns_a_new_result(self):
        original = ManeuverResult.ok(heading_change=7.2)
        enriched = original.with_fields(heel=10.8)
        self.assertIsNot(original, enriched)

    def test_leaves_the_original_untouched(self):
        original = ManeuverResult.ok(heading_change=7.2)
        original.with_fields(heading_change=99.0)
        self.assertEqual(original.heading_change, 7.2)

    def test_overrides_the_named_field(self):
        result = ManeuverResult.ok(heading_change=7.2).with_fields(heel=10.8)
        self.assertEqual(result.heel, 10.8)

    def test_preserves_unnamed_fields(self):
        result = ManeuverResult.ok(heading_change=7.2).with_fields(heel=10.8)
        self.assertEqual(result.heading_change, 7.2)

    def test_keeps_the_subclass(self):
        result = ManeuverResult.ok(heading_change=1.0).with_fields(heel=2.0)
        self.assertIsInstance(result, ManeuverResult)


class TestSubclassing(BaseEvenniaTestCase):
    """Operation-specific results built on the base."""

    def test_subclass_ok_carries_its_own_fields(self):
        result = ManeuverResult.ok(heading_change=7.2, speed_change=-0.4, heel=10.8)
        self.assertEqual(
            (result.heading_change, result.speed_change, result.heel), (7.2, -0.4, 10.8)
        )

    def test_subclass_ok_is_successful(self):
        self.assertTrue(ManeuverResult.ok(heading_change=7.2))

    def test_subclass_failure_still_requires_a_code(self):
        with self.assertRaises(ValueError):
            ManeuverResult(success=False)

    def test_subclass_failure_keeps_its_fields(self):
        result = ManeuverResult.failed(PRECONDITION_FAILED, heel=3.0)
        self.assertEqual(result.code, PRECONDITION_FAILED)
        self.assertEqual(result.heel, 3.0)

    def test_subclass_fields_default(self):
        """Defaults let an operation report only what it actually determined."""
        result = ManeuverResult.ok()
        self.assertEqual((result.heading_change, result.speed_change, result.heel), (0.0, 0.0, 0.0))

    def test_subclass_is_a_result(self):
        self.assertIsInstance(ManeuverResult.ok(), Result)

    def test_subclass_is_immutable(self):
        result = ManeuverResult.ok(heel=1.0)
        with self.assertRaises(FrozenInstanceError):
            result.heel = 2.0
