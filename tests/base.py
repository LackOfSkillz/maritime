"""
Shared setup for tests that put vessels on the water.

Two kinds of leak, both of which have already caused failures, and both of which are the
same mistake: a test that describes a world it did not actually ask for.

**The register of who is afloat is process-wide and lives in memory**, which is correct at
runtime - there is one sea per process - and a trap under a test runner, where the process
outlives the database. Django rolls each test's rows back; it has no opinion about a Python
dict, so a vessel from a finished test stays afloat and turns up as a sail on the horizon in
the next one. That surfaced as three failures when observation was wired in, which is the
useful kind of failure: it is what would happen in a running game to any vessel destroyed
without telling the register, and it is why `Vessel.at_object_delete` now does.

**The world's weather and ground come from settings**, and the tests run under the dev
game's settings file. Every time that game configured something - a seabed, then a current -
tests that had never mentioned it started quietly measuring it instead of the flat, still,
empty sea they described. Twice is a pattern, so the neutral world is asserted here once
rather than remembered in each test that happens to need it.

A test that wants ground, or a stream, or wind says so with its own `override_settings`,
which nests over these perfectly well.

"""

from django.test import override_settings

from ..traffic import traffic

#: A sea with nothing in it: no ground, no stream, no wind, and nobody afloat.
EMPTY_SEA = {
    "MARITIME_MAP_PROVIDER": "",
    "MARITIME_CURRENT_PROVIDER": "",
    "MARITIME_CURRENT_SET": 0.0,
    "MARITIME_CURRENT_DRIFT": 0.0,
    "MARITIME_WIND_BEARING": 0.0,
    "MARITIME_WIND_SPEED": 0.0,
    # An empty sea has nothing in it, and that includes buoys. Without this the
    # host game's own marks come through the settings and appear on the horizon of
    # every test that thought it was sailing on blank water - which is how a test
    # named "an empty sea reports the horizon" ended up looking at a fairway buoy.
    "MARITIME_NAVIGATION_NETWORK": "",
}


class EmptySeaMixin:
    """
    Starts each test on an empty sea, whatever the host game has configured.

    Notes:
        Mix in ahead of the Evennia test base so this `setUp` runs first and still
        chains upward:

            class TestSomething(EmptySeaMixin, BaseEvenniaTest):

    """

    def setUp(self):
        super().setUp()
        traffic().clear()
        self.addCleanup(traffic().clear)
        blank = override_settings(**EMPTY_SEA)
        blank.enable()
        self.addCleanup(blank.disable)
