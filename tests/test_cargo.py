"""
Tests for cargo: what stows how, and which capacity runs out first.

"""

from evennia.utils.test_resources import BaseEvenniaTestCase

from ..cargo import (
    FRESHWATER_DENSITY,
    NEITHER,
    SEAWATER_DENSITY,
    STANDARD_STOWAGE,
    VOLUME,
    WEIGHT,
    Commodity,
    Parcel,
    binding_limit,
    combine,
    commodity_named,
    deadweight,
    freeboard,
    laden_draft,
    laden_speed,
    overloaded,
    room_for,
    sinkage,
    stowed_moment,
    stowed_volume,
    take_from,
    tender,
    tonnes_per_centimetre,
    total_mass,
    total_tonnes,
)
from ..vessel import VesselCapacity

# Dense and packaged, light and packaged, dense and poured loose.
IRON = Commodity("iron", "pig iron", 0.35)
WOOL = Commodity("wool", "baled wool", 3.8)
SALT = Commodity("salt", "salt", 1.0, bulk=True)


class TestCommodity(BaseEvenniaTestCase):
    """A cargo described by how it stows."""

    def test_a_cargo_with_no_key(self):
        with self.assertRaises(ValueError):
            Commodity("", "nothing", 1.0)

    def test_a_cargo_that_takes_no_space(self):
        """A hull could carry an unbounded amount of it, which is a bug not a cargo."""
        with self.assertRaises(ValueError):
            Commodity("aether", "aether", 0.0)

    def test_a_cargo_of_negative_bulk(self):
        with self.assertRaises(ValueError):
            Commodity("antimatter", "antimatter", -1.0)


class TestParcel(BaseEvenniaTestCase):
    """A quantity of one cargo."""

    def test_mass_is_in_kilograms(self):
        self.assertAlmostEqual(Parcel(IRON, 10.0).mass, 10000.0)

    def test_volume_follows_the_stowage_factor(self):
        self.assertAlmostEqual(Parcel(WOOL, 10.0).volume, 38.0)

    def test_negative_cargo_is_refused(self):
        """It would let a hold be emptied past empty."""
        with self.assertRaises(ValueError):
            Parcel(IRON, -1.0)

    def test_nothing_is_a_valid_quantity(self):
        self.assertEqual(Parcel(IRON, 0.0).tonnes, 0.0)


class TestTotals(BaseEvenniaTestCase):
    """Adding cargo up."""

    def test_tonnes(self):
        self.assertAlmostEqual(total_tonnes([Parcel(IRON, 10.0), Parcel(WOOL, 5.0)]), 15.0)

    def test_mass(self):
        self.assertAlmostEqual(total_mass([Parcel(IRON, 10.0)]), 10000.0)

    def test_an_empty_hold_weighs_nothing(self):
        self.assertEqual(total_tonnes([]), 0.0)


class TestStowedVolume(BaseEvenniaTestCase):
    """How much hold a load actually takes up."""

    def test_packaged_cargo_pays_broken_stowage(self):
        self.assertAlmostEqual(stowed_volume([Parcel(WOOL, 10.0)], 0.1), 38.0 / 0.9)

    def test_bulk_cargo_does_not(self):
        """Loose grain has no packages to leave gaps between."""
        self.assertAlmostEqual(stowed_volume([Parcel(SALT, 10.0)], 0.1), 10.0)

    def test_no_broken_stowage_is_the_raw_figure(self):
        self.assertAlmostEqual(stowed_volume([Parcel(WOOL, 10.0)], 0.0), 38.0)

    def test_more_broken_stowage_wastes_more(self):
        self.assertGreater(
            stowed_volume([Parcel(WOOL, 10.0)], 0.2),
            stowed_volume([Parcel(WOOL, 10.0)], 0.1),
        )


class TestCombine(BaseEvenniaTestCase):
    """A hold that took three lots of salt holds salt."""

    def test_like_is_folded_together(self):
        folded = combine([Parcel(SALT, 10.0), Parcel(SALT, 5.0)])
        self.assertEqual(len(folded), 1)
        self.assertAlmostEqual(folded[0].tonnes, 15.0)

    def test_unlike_is_kept_apart(self):
        self.assertEqual(len(combine([Parcel(SALT, 10.0), Parcel(IRON, 5.0)])), 2)

    def test_order_is_kept(self):
        folded = combine([Parcel(WOOL, 1.0), Parcel(IRON, 1.0), Parcel(WOOL, 1.0)])
        self.assertEqual(folded[0].commodity.key, "wool")

    def test_empty_parcels_are_dropped(self):
        self.assertEqual(combine([Parcel(SALT, 0.0)]), ())


class TestTakeFrom(BaseEvenniaTestCase):
    """Getting cargo back out."""

    def test_part_of_it(self):
        remaining, taken = take_from([Parcel(SALT, 10.0)], SALT, 4.0)
        self.assertAlmostEqual(taken.tonnes, 4.0)
        self.assertAlmostEqual(remaining[0].tonnes, 6.0)

    def test_all_of_it_leaves_nothing(self):
        remaining, taken = take_from([Parcel(SALT, 10.0)], SALT, 10.0)
        self.assertAlmostEqual(taken.tonnes, 10.0)
        self.assertEqual(remaining, ())

    def test_more_than_is_there_takes_what_is(self):
        """Asking for more than is aboard is an ordinary mistake at a quay."""
        _remaining, taken = take_from([Parcel(SALT, 10.0)], SALT, 40.0)
        self.assertAlmostEqual(taken.tonnes, 10.0)

    def test_something_that_is_not_there(self):
        remaining, taken = take_from([Parcel(SALT, 10.0)], IRON, 1.0)
        self.assertEqual(taken.tonnes, 0.0)
        self.assertAlmostEqual(remaining[0].tonnes, 10.0)

    def test_other_cargo_is_untouched(self):
        remaining, _taken = take_from([Parcel(SALT, 10.0), Parcel(IRON, 5.0)], SALT, 10.0)
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].commodity.key, "iron")


class TestDeadweight(BaseEvenniaTestCase):
    """What she may carry."""

    def test_the_whole_budget_when_she_weighs_nothing(self):
        self.assertAlmostEqual(deadweight(VesselCapacity(displacement=100000.0)), 100000.0)

    def test_her_own_weight_comes_off_it(self):
        self.assertAlmostEqual(deadweight(VesselCapacity(displacement=100000.0), 30000.0), 70000.0)

    def test_a_hull_heavier_than_her_budget_carries_nothing(self):
        self.assertEqual(deadweight(VesselCapacity(displacement=10000.0), 90000.0), 0.0)


class TestBindingLimit(BaseEvenniaTestCase):
    """Which capacity ran out."""

    def test_neither_when_she_is_empty(self):
        self.assertEqual(binding_limit([], 100000.0, 200.0), NEITHER)

    def test_weight_when_she_is_down_on_her_marks(self):
        self.assertEqual(binding_limit([Parcel(IRON, 100.0)], 100000.0, 200.0), WEIGHT)

    def test_volume_when_the_holds_are_full(self):
        self.assertEqual(binding_limit([Parcel(WOOL, 47.0)], 1000000.0, 150.0), VOLUME)

    def test_weight_wins_when_both_are_gone(self):
        """Overloaded is a seaworthiness problem; full is only a commercial one."""
        self.assertEqual(binding_limit([Parcel(WOOL, 47.0)], 47000.0, 150.0), WEIGHT)


class TestRoomFor(BaseEvenniaTestCase):
    """How much more will go aboard."""

    def test_bounded_by_weight_for_something_dense(self):
        """Fifty tonnes of iron is eighteen cubic metres; the mass is what stops her."""
        self.assertAlmostEqual(room_for(IRON, [], 50000.0, 1000.0), 50.0)

    def test_bounded_by_volume_for_something_light(self):
        self.assertAlmostEqual(room_for(WOOL, [], 1e9, 38.0, 0.0), 10.0)

    def test_broken_stowage_costs_her_capacity(self):
        self.assertLess(room_for(WOOL, [], 1e9, 38.0, 0.1), 10.0)

    def test_bulk_pays_no_broken_stowage(self):
        self.assertAlmostEqual(room_for(SALT, [], 1e9, 10.0, 0.5), 10.0)

    def test_a_full_ship_has_room_for_nothing(self):
        self.assertEqual(room_for(IRON, [Parcel(IRON, 50.0)], 50000.0, 1000.0), 0.0)

    def test_never_negative(self):
        self.assertEqual(room_for(IRON, [Parcel(IRON, 500.0)], 50000.0, 1000.0), 0.0)


class TestImmersion(BaseEvenniaTestCase):
    """What weight does to how deep she sits."""

    def test_a_bigger_waterplane_takes_more_to_sink(self):
        self.assertGreater(tonnes_per_centimetre(40.0, 8.0), tonnes_per_centimetre(20.0, 6.0))

    def test_the_figure_itself(self):
        """20 x 6 at a coefficient of 0.8 is 96 square metres, which in seawater is 0.984."""
        self.assertAlmostEqual(tonnes_per_centimetre(20.0, 6.0), 0.984, places=4)

    def test_a_finer_hull_sinks_further_under_the_same_load(self):
        """The coefficient is the difference between a barge and a clipper."""
        barge = tonnes_per_centimetre(20.0, 6.0, coefficient=0.9)
        clipper = tonnes_per_centimetre(20.0, 6.0, coefficient=0.7)
        self.assertGreater(sinkage(50000.0, clipper), sinkage(50000.0, barge))

    def test_fresh_water_sinks_her_further(self):
        """The same cargo puts her deeper in a river than in the sea."""
        salt = tonnes_per_centimetre(20.0, 6.0, density=SEAWATER_DENSITY)
        fresh = tonnes_per_centimetre(20.0, 6.0, density=FRESHWATER_DENSITY)
        self.assertGreater(sinkage(50000.0, fresh), sinkage(50000.0, salt))

    def test_nothing_aboard_sinks_her_not_at_all(self):
        self.assertEqual(sinkage(0.0, 1.0), 0.0)

    def test_a_hull_with_no_waterplane_does_not_divide_by_zero(self):
        self.assertEqual(sinkage(50000.0, 0.0), 0.0)

    def test_laden_draft_starts_from_the_light_one(self):
        self.assertAlmostEqual(laden_draft(2.0, 0.0, 1.0), 2.0)

    def test_a_hundred_tonnes_on_one_tonne_per_centimetre_is_a_metre(self):
        self.assertAlmostEqual(laden_draft(2.0, 100000.0, 1.0), 3.0)


class TestFreeboard(BaseEvenniaTestCase):
    """How much hull is out of the water."""

    def test_what_is_left_above_the_waterline(self):
        self.assertAlmostEqual(freeboard(4.0, 2.5), 1.5)

    def test_never_negative(self):
        self.assertEqual(freeboard(4.0, 6.0), 0.0)

    def test_a_light_ship_is_not_overloaded(self):
        self.assertFalse(overloaded(4.0, 2.0, 2.0))

    def test_a_ship_down_to_her_marks_is(self):
        self.assertTrue(overloaded(4.0, 2.0, 3.8))

    def test_a_hull_with_no_freeboard_light_is_always_overloaded(self):
        self.assertTrue(overloaded(2.0, 2.0, 2.0))

    def test_a_big_hull_is_overloaded_with_metres_still_showing(self):
        """
        Ten metres of light freeboard and two left. That is a ship loaded past
        her marks, and a fixed threshold in metres would call her fine.

        """
        self.assertTrue(overloaded(20.0, 10.0, 18.0))

    def test_a_small_hull_is_not_overloaded_at_the_same_freeboard(self):
        """
        A lighter with sixty centimetres of freeboard light is doing what a
        lighter does. The same rule has to serve her and the merchantman.

        """
        self.assertFalse(overloaded(1.2, 0.6, 0.8))


class TestLadenSpeed(BaseEvenniaTestCase):
    """A loaded hull is slower."""

    def test_empty_makes_her_best_speed(self):
        self.assertAlmostEqual(laden_speed(6.0, 0.0, 100000.0), 6.0)

    def test_full_costs_her_the_whole_penalty(self):
        self.assertAlmostEqual(laden_speed(6.0, 100000.0, 100000.0, 0.25), 4.5)

    def test_half_loaded_costs_her_half_of_it(self):
        self.assertAlmostEqual(laden_speed(6.0, 50000.0, 100000.0, 0.25), 5.25)

    def test_a_hull_that_carries_nothing_is_unaffected(self):
        self.assertAlmostEqual(laden_speed(6.0, 0.0, 0.0), 6.0)

    def test_overloading_does_not_reverse_her(self):
        self.assertGreaterEqual(laden_speed(6.0, 500000.0, 100000.0), 0.0)


class TestStability(BaseEvenniaTestCase):
    """Weight stowed high."""

    def test_weight_low_in_her_comes_out_negative(self):
        """Ballast and cargo stowed low are weight doing good."""
        self.assertLess(stowed_moment([(10000.0, -2)]), 0.0)

    def test_weight_on_deck_comes_out_positive(self):
        self.assertGreater(stowed_moment([(10000.0, 1)]), 0.0)

    def test_the_main_deck_is_the_datum(self):
        self.assertEqual(stowed_moment([(10000.0, 0)]), 0.0)

    def test_a_low_stow_is_not_tender(self):
        self.assertFalse(tender(stowed_moment([(10000.0, -2)]), 1000.0))

    def test_a_high_stow_is(self):
        self.assertTrue(tender(stowed_moment([(10000.0, 2)]), 1000.0))

    def test_a_hull_with_no_stated_tolerance_is_never_tender(self):
        """Silence is not a claim that she is unstable."""
        self.assertFalse(tender(1e9, 0.0))


class TestStandardStowage(BaseEvenniaTestCase):
    """The reference table, and finding things in it."""

    def test_the_spread_is_the_point(self):
        """Iron and hay differ by more than twenty times, which is the whole trade."""
        factors = {c.key: c.stowage_factor for c in STANDARD_STOWAGE}
        self.assertGreater(factors["hay"] / factors["iron"], 20.0)

    def test_found_by_key(self):
        self.assertEqual(commodity_named("wool").key, "wool")

    def test_found_by_name(self):
        self.assertEqual(commodity_named("baled wool").key, "wool")

    def test_found_by_part_of_a_name(self):
        self.assertEqual(commodity_named("pig").key, "iron")

    def test_case_is_ignored(self):
        self.assertEqual(commodity_named("Pig Iron").key, "iron")

    def test_something_nobody_trades_in(self):
        self.assertIsNone(commodity_named("moonlight"))

    def test_nothing_typed_at_all(self):
        self.assertIsNone(commodity_named(""))

    def test_a_key_beats_a_name_it_appears_inside(self):
        """
        `cask` is a key here and also sits inside `wine in cask`, which comes
        first. Without an exact-key pass, asking for casks gets you wine.

        """
        table = (
            Commodity("wine", "wine in cask", 1.6),
            Commodity("cask", "empty casks", 5.0),
        )
        self.assertEqual(commodity_named("cask", table).key, "cask")

    def test_a_name_still_wins_over_a_name_it_appears_inside(self):
        table = (
            Commodity("hides", "salted hides", 2.5),
            Commodity("salt", "salt", 1.0, bulk=True),
        )
        self.assertEqual(commodity_named("salt", table).key, "salt")
