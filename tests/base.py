"""
Shared setup for tests that put vessels on the water.

The register of who is afloat is process-wide and lives in memory, which is correct at
runtime - there is one sea per process - and a trap under a test runner, where the process
outlives the database. Django rolls each test's rows back; it has no opinion about a
Python dict, so a vessel from a finished test stays afloat and turns up as a sail on the
horizon in the next one.

That surfaced as three failures the first time observation was wired in, which is the
useful kind of failure: it is exactly what would happen in a running game to any vessel
destroyed without telling the register, and it is why `Vessel.at_object_delete` now does.

"""

from ..traffic import traffic


class EmptySeaMixin:
    """
    Starts each test with nobody on the water.

    Notes:
        Mix in ahead of the Evennia test base so this `setUp` runs first and still
        chains upward:

            class TestSomething(EmptySeaMixin, BaseEvenniaTest):

    """

    def setUp(self):
        super().setUp()
        traffic().clear()
        self.addCleanup(traffic().clear)
