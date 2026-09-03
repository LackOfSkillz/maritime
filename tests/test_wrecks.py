"""
Tests for what is left after she goes down.

The claim: **a wreck is a place.** She sank somewhere real, she is as deep as the water was
there, and both what floated off her and what is still in her can be gone after by anybody
who wrote the position down.

"""

from django.test import override_settings

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest

from ..bathymetry import FlatSeaMapProvider
from ..cargo import commodity_named
from ..floating import Buoyancy
from ..motion import MotionLimits
from ..position import WorldPosition
from ..rooms import ShipRoom
from ..typeclasses import Vessel
from ..vessel import BELOW_WATERLINE, OPEN, VesselCapacity
from ..wrecks import FLOATS_FREE, NOT_A_WRECK, NOTHING_DOWN_THERE, SALVAGE_DEPTH, TOO_DEEP

HERE = WorldPosition(0.0, 0.0)

#: A hundred metres of water everywhere, so a depth assertion means what it says.
#:
#: The shipped coast is a real one - there are banks on it, and a wreck dropped at the
#: origin might be in three metres or ashore. Salvage is gated on depth and nothing else,
#: so a test of that gate has to know how deep the water is.
FLAT_SEA = f"{FlatSeaMapProvider.__module__}.{FlatSeaMapProvider.__qualname__}"
SEABED = 100.0

#: How far the surface moves, so an assertion about depth can allow for it.
TIDE_RANGE = 5.0


@override_settings(MARITIME_MAP_PROVIDER=FLAT_SEA, MARITIME_DEFAULT_DEPTH=SEABED)
class WreckTestCase(BaseEvenniaTest):
    """A laden hull that can be sunk on demand, in water of a known depth."""

    def setUp(self):
        super().setUp()
        from .. import config

        config.forget_map_provider()
        self.addCleanup(config.forget_map_provider)
        self.hull = create.create_object(Vessel, key="Kestrel")
        self.hull.length, self.hull.beam = 24.0, 7.0
        self.hull.light_draft = 2.0
        self.hull.motion_limits = MotionLimits(max_speed=6.0, acceleration=0.5, turn_rate=5.0)
        self.hull.capacity = VesselCapacity(
            displacement=120000.0, internal_volume=300.0, stability_moment=100000.0
        )
        self.hull.maritime_position = HERE
        self.hull.heading = 0.0

        self.hold = create.create_object(ShipRoom, key="Hold")
        self.hold.vessel = self.hull
        self.hold.deck_level = -1
        self.hold.exposure = BELOW_WATERLINE
        self.hold.hold_capacity = 200.0
        deck = create.create_object(ShipRoom, key="Deck")
        deck.vessel = self.hull
        deck.exposure = OPEN

        self.salt = commodity_named("salt")
        if self.salt is None:
            self.skipTest("the shipped commodities do not include salt")

    def sink_her(self, rate=0.1, when=0.0):
        """Take her buoyancy away and start the clock."""
        self.hull.buoyancy = Buoyancy(floats=False, sink_rate=rate)
        return self.hull.go_down(now=when)

    def lade_her(self, tonnes=40.0):
        """Get cargo into her, or say why the fixture is wrong."""
        self.assertTrue(self.hull.load(self.salt, tonnes), "the fixture never got cargo aboard")


class TestWhetherSheIsOne(WreckTestCase):
    """A wreck is a hull that stopped floating, not a different kind of object."""

    def test_a_ship_afloat_is_not_a_wreck(self):
        self.assertFalse(self.hull.wrecked)

    def test_and_reports_nothing(self):
        self.assertEqual(self.hull.wreck_report().code, NOT_A_WRECK)

    def test_one_that_has_stopped_floating_is(self):
        self.sink_her()
        self.assertTrue(self.hull.wrecked)

    def test_she_is_the_same_object_she_was(self):
        """
        Not copied into a Wreck typeclass. Her position, her holds and her name are already
        right where they were, and keeping two of anything in step is how they drift apart.

        """
        self.sink_her()
        self.assertEqual(self.hull.maritime_position, HERE)
        self.assertTrue(self.hull.wreck_report())


class TestGoingDown(WreckTestCase):
    """How deep she has got, worked out rather than ticked."""

    def test_she_starts_at_the_surface(self):
        self.sink_her(when=0.0)
        self.assertAlmostEqual(self.hull.depth_now(now=0.0), 0.0)

    def test_and_gets_deeper(self):
        self.sink_her(rate=0.1, when=0.0)
        self.assertGreater(self.hull.depth_now(now=100.0), self.hull.depth_now(now=10.0))

    def test_she_stops_at_the_bottom(self):
        """
        The whole reason `sinking_depth` takes a seabed. A wreck that kept falling would be
        a hundred metres down in ten metres of water, and salvage would never reach her.

        """
        self.sink_her(rate=1.0, when=0.0)
        rested = 100_000.0
        self.assertAlmostEqual(
            self.hull.depth_now(now=rested), self.hull.water_here(now=rested), places=3
        )

    def test_and_says_so(self):
        self.sink_her(rate=1.0, when=0.0)
        self.assertTrue(self.hull.wreck_report(now=100_000.0).on_the_bottom)

    def test_a_ship_afloat_is_no_depth_at_all(self):
        self.assertAlmostEqual(self.hull.depth_now(), 0.0)

    def test_going_down_twice_does_not_raise_her(self):
        """
        A second stamp would restart her descent, which is a wreck rising back towards the
        surface and a thing nobody wants to have to explain.

        """
        self.sink_her(rate=0.1, when=0.0)
        deep = self.hull.depth_now(now=200.0)
        self.hull.go_down(now=500.0)
        self.assertAlmostEqual(self.hull.depth_now(now=200.0), deep)


class TestWaterHere(WreckTestCase):
    """The depth comes from the model every other sounding comes from."""

    def test_it_is_the_seabed_the_map_says(self):
        """
        Read off the same model the soundings and the groundings use, rather than a second
        one written for wrecks - so a wreck on a bank is on the bank the chart shows.

        """
        self.assertAlmostEqual(self.hull.water_here(now=0.0), SEABED, delta=TIDE_RANGE)

    def test_and_the_tide_is_in_it(self):
        """
        Measured, not assumed: a flat sea of a hundred metres reads deeper than a hundred
        metres, because the surface is where the tide has put it. That is the point of
        asking `clearance_at` rather than the terrain - a wreck in nine metres at low water
        is in eleven at high, and salvage cares.

        """
        surfaces = {round(self.hull.water_here(now=hour * 3600.0), 3) for hour in range(13)}
        self.assertGreater(len(surfaces), 1)
        self.assertLess(max(surfaces) - min(surfaces), 2 * TIDE_RANGE)

    def test_a_hull_nowhere_has_no_water_under_her(self):
        self.hull.maritime_position = None
        self.assertAlmostEqual(self.hull.water_here(now=0.0), 0.0)


class TestWhatFloatsFree(WreckTestCase):
    """A share of it, and out of her rather than copied out of her."""

    def test_some_of_her_cargo_comes_up(self):
        self.lade_her(40.0)
        self.assertTrue(self.sink_her())

    def test_and_it_is_floating_where_she_sank(self):
        self.lade_her(40.0)
        adrift = self.sink_her()
        self.assertEqual(adrift[0].maritime_position, HERE)

    def test_not_all_of_it(self):
        """A hold full of salt does not bob to the surface."""
        self.lade_her(40.0)
        self.sink_her()
        left = sum(parcel.tonnes for parcel in self.hold.stowed)
        self.assertGreater(left, 0.0)

    def test_what_floated_off_is_no_longer_down_there(self):
        """
        Taken out of her holds rather than copied out of them. Cargo counted twice is cargo
        somebody eventually notices.

        """
        self.lade_her(40.0)
        adrift = self.sink_her()
        floated = sum(thing.db.tonnes for thing in adrift)
        left = sum(parcel.tonnes for parcel in self.hold.stowed)
        self.assertAlmostEqual(floated + left, 40.0, places=3)

    def test_the_share_is_the_one_published(self):
        self.lade_her(100.0)
        adrift = self.sink_her()
        floated = sum(thing.db.tonnes for thing in adrift)
        self.assertAlmostEqual(floated, 100.0 * FLOATS_FREE, places=3)

    def test_an_empty_ship_spills_nothing(self):
        self.assertEqual(self.sink_her(), ())

    def test_a_hull_nowhere_spills_nothing(self):
        self.lade_her(40.0)
        self.hull.maritime_position = None
        self.assertEqual(self.hull.spill_cargo(), ())


class TestSalvage(WreckTestCase):
    """Depth is the whole of the difficulty."""

    def test_nothing_can_be_got_out_of_a_ship_still_afloat(self):
        self.lade_her(40.0)
        self.assertEqual(self.hull.salvage(self.salt, 5.0).code, NOT_A_WRECK)

    def test_a_wreck_in_reach_gives_up_her_cargo(self):
        self.lade_her(40.0)
        self.sink_her(rate=0.0001, when=0.0)
        got = self.hull.salvage(self.salt, 5.0, now=0.0)
        self.assertTrue(got)
        self.assertAlmostEqual(got.tonnes, 5.0, places=3)

    def test_and_it_is_really_gone_from_her(self):
        self.lade_her(40.0)
        self.sink_her(rate=0.0001, when=0.0)
        before = sum(parcel.tonnes for parcel in self.hold.stowed)
        self.hull.salvage(self.salt, 5.0, now=0.0)
        after = sum(parcel.tonnes for parcel in self.hold.stowed)
        self.assertAlmostEqual(before - after, 5.0, places=3)

    def test_she_cannot_give_up_more_than_she_has(self):
        self.lade_her(10.0)
        self.sink_her(rate=0.0001, when=0.0)
        aboard = sum(parcel.tonnes for parcel in self.hold.stowed)
        got = self.hull.salvage(self.salt, 999.0, now=0.0)
        self.assertAlmostEqual(got.tonnes, aboard, places=3)
        self.assertAlmostEqual(got.left, 0.0, places=3)

    def test_a_wreck_with_none_of_it_has_none_of_it(self):
        self.sink_her(rate=0.0001, when=0.0)
        self.assertEqual(self.hull.salvage(self.salt, 5.0, now=0.0).code, NOTHING_DOWN_THERE)

    def test_one_lying_too_deep_cannot_be_worked(self):
        """
        The ruling. A ship lost on a bank is a salvage job and one lost off soundings is a
        story, and nothing but the depth she sank in decides which.

        """
        self.lade_her(40.0)
        self.sink_her(rate=1.0, when=0.0)
        self.assertGreater(SEABED, SALVAGE_DEPTH, "the fixture cannot reach past diving depth")
        self.assertEqual(self.hull.salvage(self.salt, 5.0, now=100_000.0).code, TOO_DEEP)

    def test_and_the_same_wreck_could_be_worked_on_the_way_down(self):
        """
        Disabling the depth gate has to break something. She passed through diving reach on
        her way to the bottom, and the only difference is when they got there.

        """
        self.lade_her(40.0)
        self.sink_her(rate=1.0, when=0.0)
        self.assertTrue(self.hull.salvage(self.salt, 1.0, now=0.0))


class TestWhatIsStillInHer(WreckTestCase):
    """The report says, so a diver knows before going down."""

    def test_it_lists_what_she_carried(self):
        self.lade_her(40.0)
        self.sink_her(rate=0.0001, when=0.0)
        aboard = self.hull.wreck_report(now=0.0).aboard
        self.assertTrue(any(parcel.commodity.key == self.salt.key for parcel in aboard))

    def test_a_wreck_in_reach_says_so(self):
        self.sink_her(rate=0.0001, when=0.0)
        self.assertTrue(self.hull.wreck_report(now=0.0).reachable)
