"""
Tests for cargo aboard a real hull: holds, loading, and what it costs her.

These touch the database, so they use the object-creating test base.

"""

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaCommandTest, BaseEvenniaTest

from ..bathymetry import MaritimeMapProvider
from ..commands import CmdDischarge, CmdManifest, CmdStow
from ..cargo import Commodity, Parcel, VOLUME, WEIGHT, commodity_named
from ..grounding import keel_clearance
from ..motion import MotionLimits
from ..position import WorldPosition
from ..ports import TOO_DEEP, Berth, can_dock
from ..rooms import PortRoom, ShipRoom
from ..stowage import FULL, NOTHING_TO_MOVE, NOT_ABOARD, NO_HOLD, PART_ONLY
from ..typeclasses import Vessel
from ..vessel import BELOW_WATERLINE, OPEN, VesselCapacity
from .base import EmptySeaMixin

IRON = Commodity("iron", "pig iron", 0.35)
WOOL = Commodity("wool", "baled wool", 3.8)
SALT = Commodity("salt", "salt", 1.0, bulk=True)

HERE = WorldPosition(0.0, 0.0)


class Bar(MaritimeMapProvider):
    """Three metres of water, everywhere. Enough for her light and not enough loaded."""

    def terrain_z_at(self, position):
        return -3.0


class CargoTestCase(EmptySeaMixin, BaseEvenniaTest):
    """A hull with one hold below and a deck above it."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Test Hoy")
        self.hull.length = 20.0
        self.hull.beam = 6.0
        self.hull.light_draft = 2.0
        self.hull.capacity = VesselCapacity(
            displacement=120000.0, internal_volume=200.0, stability_moment=100000.0
        )
        self.hull.maritime_position = HERE
        self.hull.motion_limits = MotionLimits(max_speed=6.0, acceleration=0.5, turn_rate=5.0)

        self.hold = create.create_object(ShipRoom, key="Main Hold")
        self.hold.vessel = self.hull
        self.hold.deck_level = -1
        self.hold.exposure = BELOW_WATERLINE
        self.hold.hold_capacity = 120.0

        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.deck.vessel = self.hull
        self.deck.deck_level = 0
        self.deck.exposure = OPEN


class TestHolds(CargoTestCase):
    """A compartment that takes cargo, and one that does not."""

    def test_a_compartment_with_capacity_is_a_hold(self):
        self.assertTrue(self.hold.is_hold)

    def test_one_without_is_not(self):
        self.assertFalse(self.deck.is_hold)

    def test_negative_capacity_is_refused(self):
        with self.assertRaises(ValueError):
            self.hold.hold_capacity = -1.0

    def test_only_holds_are_listed(self):
        self.assertEqual(self.hull.holds, (self.hold,))

    def test_holds_are_listed_lowest_first(self):
        """So that "the first hold with room" is also the lowest one with room."""
        lower = create.create_object(ShipRoom, key="Lower Hold")
        lower.vessel = self.hull
        lower.deck_level = -2
        lower.hold_capacity = 50.0
        self.assertEqual(self.hull.holds[0], lower)

    def test_stowing_in_something_that_is_not_a_hold(self):
        with self.assertRaises(ValueError):
            self.deck.stow(Parcel(SALT, 1.0))

    def test_stowing_more_than_will_fit(self):
        with self.assertRaises(ValueError):
            self.hold.stow(Parcel(SALT, 500.0))

    def test_space_left_falls_as_it_fills(self):
        before = self.hold.space_left()
        self.hold.stow(Parcel(SALT, 10.0))
        self.assertLess(self.hold.space_left(), before)


class TestWhichCapacityBinds(CargoTestCase):
    """The whole trade, in two loads."""

    def test_something_dense_weighs_out(self):
        """120 tonnes of salt is 120 cubic metres of hold and all of her deadweight."""
        result = self.hull.load(SALT, 200.0)
        self.assertAlmostEqual(result.parcel.tonnes, 120.0, places=4)
        self.assertEqual(result.limit, WEIGHT)

    def test_something_light_cubes_out(self):
        """The same hull takes a quarter of the tonnage of wool and is barely down."""
        result = self.hull.load(WOOL, 200.0)
        self.assertLess(result.parcel.tonnes, 30.0)
        self.assertEqual(result.limit, VOLUME)

    def test_the_light_cargo_leaves_her_higher(self):
        self.hull.load(WOOL, 200.0)
        wool_draft = self.hull.draft
        self.hull.discharge(WOOL, 999.0)
        self.hull.load(SALT, 200.0)
        self.assertLess(wool_draft, self.hull.draft)

    def test_a_partial_load_still_succeeds(self):
        result = self.hull.load(SALT, 200.0)
        self.assertTrue(result)
        self.assertEqual(result.code, PART_ONLY)
        self.assertAlmostEqual(result.refused, 80.0, places=4)

    def test_a_load_that_fits_entirely_says_nothing_extra(self):
        result = self.hull.load(SALT, 10.0)
        self.assertEqual(result.code, "")
        self.assertEqual(result.refused, 0.0)


class TestLoading(CargoTestCase):
    """Getting it aboard."""

    def test_it_ends_up_in_the_hold(self):
        self.hull.load(SALT, 10.0)
        self.assertAlmostEqual(self.hold.stowed[0].tonnes, 10.0)

    def test_the_lowest_hold_is_filled_first(self):
        lower = create.create_object(ShipRoom, key="Lower Hold")
        lower.vessel = self.hull
        lower.deck_level = -2
        lower.hold_capacity = 20.0
        self.hull.load(SALT, 10.0)
        self.assertEqual(len(lower.stowed), 1)
        self.assertEqual(len(self.hold.stowed), 0)

    def test_a_load_runs_across_holds(self):
        lower = create.create_object(ShipRoom, key="Lower Hold")
        lower.vessel = self.hull
        lower.deck_level = -2
        lower.hold_capacity = 20.0
        self.hull.load(SALT, 60.0)
        self.assertAlmostEqual(lower.stowed[0].tonnes, 20.0, places=4)
        self.assertAlmostEqual(self.hold.stowed[0].tonnes, 40.0, places=4)

    def test_a_named_hold_is_used(self):
        upper = create.create_object(ShipRoom, key="Upper Hold")
        upper.vessel = self.hull
        upper.deck_level = 0
        upper.hold_capacity = 20.0
        self.hull.load(SALT, 10.0, hold=upper)
        self.assertEqual(len(upper.stowed), 1)
        self.assertEqual(len(self.hold.stowed), 0)

    def test_a_hull_with_no_hold_takes_nothing(self):
        self.hold.hold_capacity = 0.0
        self.assertEqual(self.hull.load(SALT, 10.0).code, NO_HOLD)

    def test_loading_nothing(self):
        self.assertEqual(self.hull.load(SALT, 0.0).code, NOTHING_TO_MOVE)

    def test_loading_into_a_full_ship(self):
        self.hull.load(SALT, 200.0)
        self.assertEqual(self.hull.load(SALT, 10.0).code, FULL)

    def test_the_deadweight_is_spent_once(self):
        """Asking the hull again per hold would let her take the same tonnage twice."""
        lower = create.create_object(ShipRoom, key="Lower Hold")
        lower.vessel = self.hull
        lower.deck_level = -2
        lower.hold_capacity = 200.0
        self.hull.load(SALT, 500.0)
        self.assertAlmostEqual(self.hull.cargo_tonnes, 120.0, places=4)


class TestDischarging(CargoTestCase):
    """Getting it ashore."""

    def test_some_of_it(self):
        self.hull.load(SALT, 50.0)
        result = self.hull.discharge(SALT, 20.0)
        self.assertAlmostEqual(result.parcel.tonnes, 20.0)
        self.assertAlmostEqual(self.hull.cargo_tonnes, 30.0)

    def test_all_of_it(self):
        self.hull.load(SALT, 50.0)
        self.hull.discharge(SALT, 999.0)
        self.assertEqual(self.hull.cargo, ())

    def test_something_that_is_not_aboard(self):
        self.assertEqual(self.hull.discharge(IRON, 10.0).code, NOT_ABOARD)

    def test_discharging_nothing(self):
        self.assertEqual(self.hull.discharge(SALT, 0.0).code, NOTHING_TO_MOVE)

    def test_the_highest_hold_is_emptied_first(self):
        """Taking the weight off the top keeps her stiff through the discharge."""
        lower = create.create_object(ShipRoom, key="Lower Hold")
        lower.vessel = self.hull
        lower.deck_level = -2
        lower.hold_capacity = 20.0
        self.hull.load(SALT, 60.0)
        self.hull.discharge(SALT, 40.0)
        self.assertAlmostEqual(lower.stowed[0].tonnes, 20.0, places=4)
        self.assertEqual(len(self.hold.stowed), 0)

    def test_she_rises_as_it_comes_out(self):
        self.hull.load(SALT, 100.0)
        deep = self.hull.draft
        self.hull.discharge(SALT, 50.0)
        self.assertLess(self.hull.draft, deep)


class TestDraft(CargoTestCase):
    """The working figure, derived at last."""

    def test_empty_she_floats_at_her_light_draft(self):
        self.assertAlmostEqual(self.hull.draft, self.hull.light_draft)

    def test_cargo_puts_her_deeper(self):
        self.hull.load(SALT, 100.0)
        self.assertGreater(self.hull.draft, self.hull.light_draft)

    def test_it_cannot_be_set(self):
        """A stored draft would be a second source of truth the next transfer overwrites."""
        with self.assertRaises(AttributeError):
            self.hull.draft = 3.0

    def test_the_light_draft_can(self):
        self.hull.light_draft = 2.5
        self.assertAlmostEqual(self.hull.draft, 2.5)

    def test_a_negative_light_draft_is_refused(self):
        with self.assertRaises(ValueError):
            self.hull.light_draft = -1.0

    def test_freeboard_falls_as_she_loads(self):
        light = self.hull.freeboard
        self.hull.load(SALT, 100.0)
        self.assertLess(self.hull.freeboard, light)

    def test_hull_depth_defaults_to_twice_the_light_draft(self):
        self.assertAlmostEqual(self.hull.hull_depth, 4.0)

    def test_a_measured_hull_depth_wins(self):
        self.hull.hull_depth = 5.0
        self.assertAlmostEqual(self.hull.hull_depth, 5.0)


class TestTheConsequences(CargoTestCase):
    """
    What loading actually costs her.

    Notes:
        The point of the phase. Cargo that only showed up in a manifest would be
        a list; these are the four places it reaches into systems that were built
        before it and did not have to change to receive it.

    """

    def test_a_laden_ship_grounds_where_a_light_one_swims(self):
        provider = Bar()
        light = keel_clearance(HERE, self.hull.draft, provider, 0.0)
        self.hull.load(SALT, 120.0)
        laden = keel_clearance(HERE, self.hull.draft, provider, 0.0)
        self.assertGreater(light, 0.0)
        self.assertLess(laden, 0.0)

    def test_a_berth_that_took_her_light_refuses_her_loaded(self):
        berth = Berth(
            key="the quay",
            position=HERE,
            heading=0.0,
            max_length=30.0,
            max_beam=10.0,
            max_draft=2.5,
        )
        light = can_dock(HERE, 0.0, 0.0, self.hull.length, self.hull.beam, self.hull.draft, berth)
        self.assertTrue(light)
        self.hull.load(SALT, 120.0)
        laden = can_dock(HERE, 0.0, 0.0, self.hull.length, self.hull.beam, self.hull.draft, berth)
        self.assertFalse(laden)
        self.assertEqual(laden.code, TOO_DEEP)

    def test_a_laden_ship_is_slower(self):
        light = self.hull.working_limits.max_speed
        self.hull.load(SALT, 120.0)
        self.assertLess(self.hull.working_limits.max_speed, light)

    def test_her_own_limits_are_left_alone(self):
        """`motion_limits` is what a game authored; `working_limits` is what she can do."""
        self.hull.load(SALT, 120.0)
        self.assertAlmostEqual(self.hull.motion_limits.max_speed, 6.0)

    def test_only_the_top_speed_moves(self):
        self.hull.load(SALT, 120.0)
        self.assertAlmostEqual(self.hull.working_limits.turn_rate, 5.0)
        self.assertAlmostEqual(self.hull.working_limits.acceleration, 0.5)

    def test_weight_stowed_low_does_not_make_her_tender(self):
        self.hull.load(SALT, 100.0)
        self.assertFalse(self.hull.stowage().tender)

    def test_weight_stowed_high_does(self):
        upper = create.create_object(ShipRoom, key="Deck Cargo")
        upper.vessel = self.hull
        upper.deck_level = 2
        upper.hold_capacity = 100.0
        self.hull.load(SALT, 100.0, hold=upper)
        self.assertTrue(self.hull.stowage().tender)

    def test_loading_her_past_her_marks(self):
        self.hull.capacity = VesselCapacity(displacement=1000000.0, internal_volume=200.0)
        self.hold.hold_capacity = 1000.0
        self.hull.load(SALT, 200.0)
        self.assertTrue(self.hull.stowage().overloaded)


class TestStowageReading(CargoTestCase):
    """One reading, taken at one moment."""

    def test_an_empty_ship_is_in_ballast(self):
        stowage = self.hull.stowage()
        self.assertEqual(stowage.parcels, ())
        self.assertEqual(stowage.tonnes, 0.0)

    def test_the_mass_and_the_draft_agree(self):
        self.hull.load(SALT, 50.0)
        stowage = self.hull.stowage()
        self.assertAlmostEqual(stowage.tonnes, 50.0)
        self.assertAlmostEqual(stowage.draft, self.hull.draft)

    def test_hold_volume_is_the_holds_not_the_build_budget(self):
        """`internal_volume` is what cabins and stores compete for when she is built."""
        self.assertAlmostEqual(self.hull.hold_volume, 120.0)
        self.assertAlmostEqual(self.hull.capacity.internal_volume, 200.0)

    def test_broken_stowage_is_configurable(self):
        self.hull.broken_stowage = 0.0
        loose = self.hull.load(WOOL, 200.0).parcel.tonnes
        self.hull.discharge(WOOL, 999.0)
        self.hull.broken_stowage = 0.25
        self.assertLess(self.hull.load(WOOL, 200.0).parcel.tonnes, loose)

    def test_broken_stowage_of_one_is_refused(self):
        """Nothing would ever fit anywhere, which is a mistake rather than a cargo."""
        with self.assertRaises(ValueError):
            self.hull.broken_stowage = 1.0

    def test_a_capacity_that_is_not_one_is_refused(self):
        with self.assertRaises(TypeError):
            self.hull.capacity = "large"


class CargoCommandTestCase(EmptySeaMixin, BaseEvenniaCommandTest):
    """A character on the deck of a hoy lying alongside."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Test Hoy")
        self.hull.length = 20.0
        self.hull.beam = 6.0
        self.hull.light_draft = 2.0
        self.hull.capacity = VesselCapacity(displacement=120000.0, internal_volume=200.0)
        self.hull.maritime_position = HERE

        self.hold = create.create_object(ShipRoom, key="Main Hold")
        self.hold.vessel = self.hull
        self.hold.deck_level = -1
        self.hold.hold_capacity = 120.0

        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.deck.vessel = self.hull
        self.deck.exposure = OPEN
        self.char1.location = self.deck

        # Really made fast, rather than a flag set to look like it: `docked` is
        # derived from the berth she is lying in, so faking it would test nothing.
        self.quay = create.create_object(PortRoom, key="The Quay")
        self.quay.maritime_position = HERE
        alongside = Berth(key="the quay", position=HERE, heading=0.0, max_draft=10.0)
        self.quay.add_berth(alongside)
        self.hull.make_fast(self.quay, alongside)


class TestWorkingCargoAlongside(CargoCommandTestCase):
    """Cargo only moves at a quay."""

    def test_stowing_at_sea_is_refused(self):
        """A hold filled in mid-ocean would make the whole of docking optional."""
        self.hull.let_go()
        self.call(CmdStow(), "10 salt", "Cargo is worked alongside.")

    def test_discharging_at_sea_is_refused(self):
        self.hull.let_go()
        self.call(CmdDischarge(), "10 salt", "Cargo is worked alongside.")

    def test_the_manifest_can_be_read_anywhere(self):
        """Reading what is in her is not cargo work."""
        self.hull.let_go()
        self.call(CmdManifest(), "", "Test Hoy - manifest")


class TestCmdStow(CargoCommandTestCase):
    """Getting it aboard."""

    def test_it_goes_into_the_hold(self):
        self.call(CmdStow(), "10 salt")
        self.assertAlmostEqual(self.hull.cargo_tonnes, 10.0)

    def test_the_order_is_spoken(self):
        self.call(CmdStow(), "10 salt", "You call out,")

    def test_tons_of_is_allowed(self):
        self.call(CmdStow(), "10 tons of salt")
        self.assertAlmostEqual(self.hull.cargo_tonnes, 10.0)

    def test_a_cargo_nobody_trades_in(self):
        self.call(CmdStow(), "10 moonlight", "Nobody here trades in moonlight.")

    def test_no_quantity_at_all(self):
        self.call(CmdStow(), "salt", "Usage:")

    def test_a_partial_load_leaves_the_rest_ashore(self):
        self.call(CmdStow(), "200 salt")
        self.assertAlmostEqual(self.hull.cargo_tonnes, 120.0, places=4)

    def test_a_ship_with_no_hold_takes_nothing(self):
        self.hold.hold_capacity = 0.0
        self.call(CmdStow(), "10 salt")
        self.assertEqual(self.hull.cargo, ())


class TestCmdDischarge(CargoCommandTestCase):
    """Getting it ashore."""

    def test_it_comes_out(self):
        self.hull.load(commodity_named("salt"), 50.0)
        self.call(CmdDischarge(), "20 salt")
        self.assertAlmostEqual(self.hull.cargo_tonnes, 30.0)

    def test_all_of_it(self):
        self.hull.load(commodity_named("salt"), 50.0)
        self.call(CmdDischarge(), "all salt")
        self.assertEqual(self.hull.cargo, ())

    def test_something_that_is_not_aboard(self):
        self.call(CmdDischarge(), "10 salt")
        self.assertEqual(self.hull.cargo, ())


class TestCmdManifest(CargoCommandTestCase):
    """Reading what is in her."""

    def test_an_empty_ship_is_in_ballast(self):
        self.assertIn(
            "She is in ballast", chr(10).join(self.hull.narrator.manifest(self.hull.stowage()))
        )

    def test_cargo_is_listed(self):
        self.hull.load(commodity_named("salt"), 50.0)
        self.assertIn("salt", chr(10).join(self.hull.narrator.manifest(self.hull.stowage())))

    def test_her_draught_is_reported(self):
        self.assertIn("Draught", chr(10).join(self.hull.narrator.manifest(self.hull.stowage())))

    def test_weighing_out_is_named_as_such(self):
        self.hull.load(commodity_named("salt"), 200.0)
        self.assertIn("weighed out", chr(10).join(self.hull.narrator.manifest(self.hull.stowage())))

    def test_cubing_out_is_named_as_such(self):
        self.hull.load(commodity_named("wool"), 200.0)
        self.assertIn("cubed out", chr(10).join(self.hull.narrator.manifest(self.hull.stowage())))


class TestTheCargoVoice(CargoTestCase):
    """
    The words for a load, tested where the whole line is visible.

    Notes:
        Deliberately not through the commands. Evennia's command harness matches
        the start of what was sent, and it is the *last* line - the one saying
        why the rest is still on the quay - that carries the information.

    """

    def manifest(self):
        """
        Returns:
            text (str): The whole manifest as one block.

        """
        return chr(10).join(self.hull.narrator.manifest(self.hull.stowage()))

    def test_a_full_load_says_where_it_went(self):
        result = self.hull.load(SALT, 10.0)
        lines = self.hull.narrator.stowed(result, SALT)
        self.assertEqual(len(lines), 1)
        self.assertIn("main hold", lines[0])

    def test_weighing_out_is_explained_as_weight(self):
        result = self.hull.load(SALT, 200.0)
        self.assertIn("down on her marks", self.hull.narrator.refusal_line(result, SALT))

    def test_cubing_out_is_explained_as_space(self):
        """The useful half: a denser cargo would still go aboard."""
        result = self.hull.load(WOOL, 200.0)
        self.assertIn("something denser", self.hull.narrator.refusal_line(result, WOOL))

    def test_a_discharge_says_what_came_out(self):
        self.hull.load(SALT, 50.0)
        result = self.hull.discharge(SALT, 20.0)
        self.assertIn("go ashore", self.hull.narrator.discharged(result, SALT)[0])

    def test_discharging_more_than_is_aboard_says_so(self):
        self.hull.load(SALT, 50.0)
        result = self.hull.discharge(SALT, 80.0)
        self.assertIn("no more salt", self.hull.narrator.discharged(result, SALT)[1])

    def test_an_overloaded_ship_is_warned_about(self):
        self.hull.capacity = VesselCapacity(displacement=1000000.0, internal_volume=200.0)
        self.hold.hold_capacity = 1000.0
        self.hull.load(SALT, 200.0)
        self.assertIn("not fit to go to sea", self.manifest())

    def test_a_tender_ship_is_warned_about(self):
        upper = create.create_object(ShipRoom, key="Deck Cargo")
        upper.vessel = self.hull
        upper.deck_level = 2
        upper.hold_capacity = 100.0
        self.hull.load(SALT, 100.0, hold=upper)
        self.assertIn("tender in a seaway", self.manifest())
