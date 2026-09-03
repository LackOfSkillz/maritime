"""
Tests for what a cargo is worth.

Three claims. **Off by default**, so a game with its own economy is untouched. **A port has
a surplus of what it exports and a shortage of what it imports**, and price follows from that
rather than from a table per quay - so the trade routes draw themselves. And **she is paid
for what actually moved**, not for what was asked for.

"""

from django.test import override_settings

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest, BaseEvenniaTestCase

from ..cargo import commodity_named
from ..economy import (
    CANNOT_AFFORD,
    ECONOMY_IS_OFF,
    EXPORTS_AT,
    IMPORTS_AT,
    NOTHING_TO_SELL,
    WORTH,
    Market,
    cargo_worth,
    price_at,
    trading,
    worth_of,
)
from ..ledger import Coin
from ..motion import MotionLimits
from ..position import WorldPosition
from ..rooms import ShipRoom
from ..typeclasses import Vessel
from ..vessel import BELOW_WATERLINE, OPEN, VesselCapacity

HERE = WorldPosition(0.0, 0.0)

#: A grain coast: it grows more than it eats and has to buy everything else.
GRAIN_COAST = Market(key="Harrowmouth", exports=("grain", "hay"), imports=("wine", "iron"))

#: A city that eats: no fields, and money enough to want what other people grow.
THE_CITY = Market(key="Careenage", exports=("wine", "iron"), imports=("grain", "hay"))


class TestTheStandingWorth(BaseEvenniaTestCase):
    """Authored, and honestly authored."""

    def test_every_shipped_commodity_has_a_worth(self):
        """
        A commodity missing from the table would price at nothing and look entirely
        deliberate doing it.

        """
        from ..cargo import STANDARD_STOWAGE

        self.assertEqual({one.key for one in STANDARD_STOWAGE} - set(WORTH), set())

    def test_and_nothing_in_the_table_is_a_commodity_nobody_ships(self):
        from ..cargo import STANDARD_STOWAGE

        self.assertEqual(set(WORTH) - {one.key for one in STANDARD_STOWAGE}, set())

    def test_a_tonne_is_worth_what_the_table_says(self):
        self.assertEqual(worth_of("salt", 1.0).smallest, WORTH["salt"])

    def test_two_tonnes_are_worth_twice(self):
        self.assertEqual(worth_of("salt", 2.0).smallest, 2 * WORTH["salt"])

    def test_something_nobody_ships_is_worth_nothing(self):
        self.assertEqual(worth_of("moonlight", 1.0).smallest, 0)

    def test_the_worths_span_orders_of_magnitude(self):
        """
        A hold of grain and a hold of tobacco are the same ship carrying two completely
        different risks. A range narrow enough to be balanced would make the choice of cargo
        a formality.

        """
        self.assertGreater(max(WORTH.values()) / min(WORTH.values()), 50)

    def test_worth_does_not_follow_how_a_thing_stows(self):
        """
        The tempting derivation, and the reason it is not used. Hay is bulky and worth
        almost nothing; wine stows tighter and is worth fifty times as much.

        """
        hay = commodity_named("hay")
        wine = commodity_named("wine")
        if hay is None or wine is None:
            self.skipTest("the shipped commodities do not include hay and wine")
        self.assertGreater(hay.stowage_factor, wine.stowage_factor)
        self.assertGreater(WORTH["wine"], WORTH["hay"])


class TestWhatAPortPays(BaseEvenniaTestCase):
    """Two lists per port, and the trade routes draw themselves."""

    def test_a_port_pays_less_for_what_it_has_too_much_of(self):
        self.assertAlmostEqual(GRAIN_COAST.rate_for("grain"), EXPORTS_AT)

    def test_and_more_for_what_it_is_short_of(self):
        self.assertAlmostEqual(GRAIN_COAST.rate_for("wine"), IMPORTS_AT)

    def test_and_the_standing_rate_for_anything_else(self):
        self.assertAlmostEqual(GRAIN_COAST.rate_for("sugar"), 1.0)

    def test_an_entrepot_trades_at_the_standing_rate(self):
        """
        A place that both ships a thing out and brings it in is not an error. Such places
        existed and did exactly that.

        """
        both = Market(key="Entrepot", exports=("wine",), imports=("wine",))
        self.assertAlmostEqual(both.rate_for("wine"), 1.0)

    def test_the_passage_worth_making_is_visible_in_the_prices(self):
        """
        Carry what is cheap here to where it is dear. Nobody wrote the route down; it falls
        out of what each place is.

        """
        cheap = price_at(GRAIN_COAST, "grain", 40.0).smallest
        dear = price_at(THE_CITY, "grain", 40.0).smallest
        self.assertGreater(dear, cheap)

    def test_and_the_return_passage_pays_too(self):
        cheap = price_at(THE_CITY, "wine", 10.0).smallest
        dear = price_at(GRAIN_COAST, "wine", 10.0).smallest
        self.assertGreater(dear, cheap)

    def test_nowhere_in_particular_pays_the_standing_rate(self):
        self.assertEqual(price_at(None, "salt", 3.0), worth_of("salt", 3.0))


class TestWhatSheIsCarryingIsWorth(BaseEvenniaTest):
    """What piracy follows - value, not traffic."""

    def test_an_empty_hold_is_worth_nothing(self):
        self.assertEqual(cargo_worth(()).smallest, 0)

    def test_a_full_one_is_worth_what_is_in_it(self):
        from ..cargo import Parcel

        salt = commodity_named("salt")
        if salt is None:
            self.skipTest("the shipped commodities do not include salt")
        self.assertEqual(cargo_worth((Parcel(salt, 10.0),)).smallest, WORTH["salt"] * 10)

    def test_a_wine_ship_is_a_better_prize_than_a_grain_ship(self):
        """
        One decision seen from two sides: a raider who hunted traffic would hunt grain
        coasters, and a raider who hunts value goes where the wine is.

        """
        from ..cargo import Parcel

        wine, grain = commodity_named("wine"), commodity_named("grain")
        if wine is None or grain is None:
            self.skipTest("the shipped commodities do not include wine and grain")
        self.assertGreater(
            cargo_worth((Parcel(wine, 20.0),)).smallest,
            cargo_worth((Parcel(grain, 20.0),)).smallest,
        )


class TradeTestCase(BaseEvenniaTest):
    """A hull with a hold and money in her."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Kestrel")
        self.hull.length, self.hull.beam = 24.0, 7.0
        self.hull.light_draft = 2.0
        self.hull.motion_limits = MotionLimits(max_speed=6.0, acceleration=0.5, turn_rate=5.0)
        self.hull.capacity = VesselCapacity(
            displacement=200_000.0, internal_volume=300.0, stability_moment=100_000.0
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
        self.hull.credit(Coin(smallest=1_000_000), reason="the fixture")
        self.salt = commodity_named("salt")
        if self.salt is None:
            self.skipTest("the shipped commodities do not include salt")


class TestTheEconomyIsOffByDefault(TradeTestCase):
    """A game arriving with its own economy must be untouched."""

    def test_it_is_off(self):
        self.assertFalse(trading())

    def test_she_cannot_buy(self):
        self.assertEqual(self.hull.buy_cargo(THE_CITY, self.salt, 5.0).code, ECONOMY_IS_OFF)

    def test_nor_sell(self):
        self.assertEqual(self.hull.sell_cargo(THE_CITY, self.salt, 5.0).code, ECONOMY_IS_OFF)

    def test_and_nothing_moves(self):
        before = self.hull.purse
        self.hull.buy_cargo(THE_CITY, self.salt, 5.0)
        self.assertEqual(self.hull.purse, before)
        self.assertEqual(self.hull.cargo, ())

    def test_the_refusal_is_a_clear_answer_rather_than_an_error(self):
        """
        A game that calls something it should not have gets told so, instead of an
        AttributeError from somewhere three frames down.

        """
        self.assertIsNotNone(self.hull.buy_cargo(THE_CITY, self.salt, 5.0).code)

    def test_but_what_she_carries_can_still_be_valued(self):
        """
        Valuing a manifest is a question, not a transaction. A game that wants to know what
        a prize is worth should not have to turn an economy on to find out.

        """
        self.hull.load(self.salt, 10.0)
        self.assertGreater(self.hull.what_she_carries_is_worth().smallest, 0)


@override_settings(MARITIME_CARGO_ECONOMY=True)
class TestTrading(TradeTestCase):
    """Paid for what actually moved."""

    def test_it_is_on(self):
        self.assertTrue(trading())

    def test_she_can_buy_a_cargo(self):
        self.assertTrue(self.hull.buy_cargo(THE_CITY, self.salt, 5.0))

    def test_and_it_is_aboard(self):
        self.hull.buy_cargo(THE_CITY, self.salt, 5.0)
        self.assertAlmostEqual(sum(p.tonnes for p in self.hull.cargo), 5.0, places=3)

    def test_and_paid_for(self):
        before = self.hull.purse
        self.hull.buy_cargo(THE_CITY, self.salt, 5.0)
        self.assertLess(self.hull.purse.smallest, before.smallest)

    def test_a_ship_that_cannot_pay_buys_nothing(self):
        self.hull.debit(self.hull.purse, reason="spent")
        self.assertEqual(self.hull.buy_cargo(THE_CITY, self.salt, 5.0).code, CANNOT_AFFORD)

    def test_and_takes_nothing_aboard(self):
        self.hull.debit(self.hull.purse, reason="spent")
        self.hull.buy_cargo(THE_CITY, self.salt, 5.0)
        self.assertEqual(self.hull.cargo, ())

    def test_she_is_charged_only_for_what_went_in(self):
        """
        Her hold or her marks may stop her short. A captain charged for cargo still
        standing on the quay would be right to complain.

        """
        result = self.hull.buy_cargo(THE_CITY, self.salt, 10_000.0)
        if not result:
            self.skipTest("the fixture hull took the whole cargo")
        self.assertLess(result.tonnes, 10_000.0)
        self.assertEqual(result.price, price_at(THE_CITY, "salt", result.tonnes))

    def test_she_can_sell_what_she_carries(self):
        self.hull.load(self.salt, 10.0)
        self.assertTrue(self.hull.sell_cargo(THE_CITY, self.salt, 10.0))

    def test_and_is_paid_for_it(self):
        self.hull.load(self.salt, 10.0)
        before = self.hull.purse
        self.hull.sell_cargo(THE_CITY, self.salt, 10.0)
        self.assertGreater(self.hull.purse.smallest, before.smallest)

    def test_selling_what_she_has_not_got_pays_nothing(self):
        self.assertEqual(self.hull.sell_cargo(THE_CITY, self.salt, 10.0).code, NOTHING_TO_SELL)

    def test_she_is_paid_only_for_what_came_out(self):
        self.hull.load(self.salt, 4.0)
        sold = self.hull.sell_cargo(THE_CITY, self.salt, 999.0)
        self.assertAlmostEqual(sold.tonnes, 4.0, places=3)
        self.assertEqual(sold.price, price_at(THE_CITY, "salt", sold.tonnes))

    def test_the_whole_loop_pays(self):
        """
        The thing the phase exists for. Buy where it is cheap, carry it, sell where it is
        dear, and be better off than when you started.

        """
        grain = commodity_named("grain")
        if grain is None:
            self.skipTest("the shipped commodities do not include grain")
        started = self.hull.purse.smallest
        bought = self.hull.buy_cargo(GRAIN_COAST, grain, 40.0)
        self.assertTrue(bought, "the fixture never got the cargo aboard")
        self.hull.sell_cargo(THE_CITY, grain, bought.tonnes)
        self.assertGreater(self.hull.purse.smallest, started)
