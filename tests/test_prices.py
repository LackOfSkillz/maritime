"""
Tests for what a hull costs.

The claim: **ships were contracted and bought by the ton burthen**, so the price hangs off
the one figure the yard already computes. A builder who draws a bigger ship gets a dearer one
without touching anything, and the yawl and the frigate are priced by the same rule rather
than by two opinions.

"""

from evennia.utils.test_resources import BaseEvenniaTestCase

from ..shipyard import (
    NAMES,
    PER_TON_BURTHEN,
    RIG_COST,
    burthen,
    figures,
    price_of,
    prices,
    specification,
)


class TestWhatSheCosts(BaseEvenniaTestCase):
    """Derived from her burthen, so nothing has to be kept in step."""

    def test_every_shipped_rig_has_a_price(self):
        self.assertEqual(set(prices()), set(NAMES))

    def test_and_none_of_them_is_free(self):
        for name in NAMES:
            self.assertGreater(price_of(name).smallest, 0, name)

    def test_a_rig_nobody_builds_has_no_price(self):
        self.assertIsNone(price_of("dreadnought"))

    def test_a_bigger_hull_costs_more(self):
        self.assertGreater(price_of("frigate").smallest, price_of("yawl").smallest)

    def test_the_seven_are_priced_in_order_of_size(self):
        """
        Nobody decided that order. It falls out of the burthen, which falls out of the
        dimensions somebody drew.

        """
        by_size = sorted(
            NAMES,
            key=lambda name: burthen(specification(name)["length"], specification(name)["beam"]),
        )
        by_price = sorted(NAMES, key=lambda name: price_of(name).smallest)
        self.assertEqual(
            [specification(name)["rig"] for name in by_size],
            [specification(name)["rig"] for name in by_price],
        )

    def test_a_square_rig_costs_more_than_a_fore_and_aft_one(self):
        """
        More spars, more standing rigging, more blocks, and a great deal more of it aloft.

        """
        self.assertGreater(RIG_COST["square"], RIG_COST["fore-and-aft"])

    def test_and_a_lug_rig_sits_between_them(self):
        self.assertLess(RIG_COST["fore-and-aft"], RIG_COST["lug"])
        self.assertLess(RIG_COST["lug"], RIG_COST["square"])

    def test_the_rig_actually_shows_in_the_price(self):
        spec = specification("cutter")
        tons = burthen(spec["length"], spec["beam"])
        plain = tons * PER_TON_BURTHEN
        self.assertAlmostEqual(
            price_of("cutter").smallest, round(plain * RIG_COST[spec["rig"]]), delta=1
        )

    def test_the_rate_can_be_changed_without_touching_the_hulls(self):
        dearer = price_of("cutter", per_ton=PER_TON_BURTHEN * 2)
        self.assertAlmostEqual(dearer.smallest, price_of("cutter").smallest * 2, delta=2)

    def test_every_rig_in_the_table_is_one_that_exists(self):
        """
        A cost for a rig nothing is built with would sit there looking correct for ever.

        """
        built = {specification(name)["rig"] for name in NAMES}
        self.assertEqual(set(RIG_COST) - built, set())

    def test_and_every_rig_that_exists_is_in_the_table(self):
        built = {specification(name)["rig"] for name in NAMES}
        self.assertEqual(built - set(RIG_COST), set())


class TestTheYardReportsIt(BaseEvenniaTestCase):
    """A price is one of her worked-out numbers, beside her dimensions."""

    def test_the_figures_carry_it(self):
        self.assertIsNotNone(figures("cutter")["price"])

    def test_and_it_is_the_same_price(self):
        self.assertEqual(figures("cutter")["price"], price_of("cutter"))

    def test_a_rig_nobody_builds_has_no_figures_at_all(self):
        self.assertIsNone(figures("dreadnought"))
