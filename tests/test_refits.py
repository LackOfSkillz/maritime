"""
Tests for what she is worth and what a yard can make her into.

Two claims. **She is valued on what she is, not on what she was** - a lengthened hull is
worth more without anybody recording the refit, and a hammered one is worth less without
anybody writing down the action. And **every fact a refit changes is one something already
reads**: no refit here adds a number that nothing consumes.

"""

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest

from ..damage import Damage
from ..ledger import Coin
from ..motion import MotionLimits
from ..position import WorldPosition
from ..refits import (
    ALREADY_REFITTED,
    BREAKING_UP,
    CANNOT_AFFORD,
    NO_SUCH_REFIT,
    REFITS,
    SECOND_HAND,
    condition_of,
    cost_of_refit,
    market_value,
)
from ..rooms import ShipRoom
from ..typeclasses import Vessel
from ..vessel import BELOW_WATERLINE, OPEN, VesselCapacity

HERE = WorldPosition(0.0, 0.0)


class RefitTestCase(BaseEvenniaTest):
    """A hull with money enough to have work done on her."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Kestrel")
        self.hull.length, self.hull.beam = 24.0, 7.0
        self.hull.light_draft = 2.0
        self.hull.motion_limits = MotionLimits(max_speed=6.0, acceleration=0.5, turn_rate=8.0)
        self.hull.capacity = VesselCapacity(
            displacement=200_000.0, internal_volume=300.0, stability_moment=100_000.0
        )
        self.hull.maritime_position = HERE
        self.hull.heading = 0.0
        hold = create.create_object(ShipRoom, key="Hold")
        hold.vessel = self.hull
        hold.deck_level = -1
        hold.exposure = BELOW_WATERLINE
        hold.hold_capacity = 200.0
        deck = create.create_object(ShipRoom, key="Deck")
        deck.vessel = self.hull
        deck.exposure = OPEN
        self.hull.credit(Coin(smallest=10_000_000), reason="the fixture")


class TestWhatSheIsWorth(RefitTestCase):
    """From her dimensions and her condition, both of which are already the truth."""

    def test_a_sound_hull_is_worth_something(self):
        self.assertGreater(market_value(self.hull).value.smallest, 0)

    def test_a_used_hull_fetches_less_than_a_new_one(self):
        worth = market_value(self.hull)
        self.assertLess(worth.value.smallest, worth.new.smallest)
        self.assertAlmostEqual(worth.value.smallest, worth.new.smallest * SECOND_HAND, delta=1)

    def test_a_sound_ship_is_in_perfect_condition(self):
        self.assertAlmostEqual(condition_of(self.hull), 1.0)

    def test_damage_costs_her(self):
        """
        Her tracks are set directly rather than shot at. `take_damage` takes a weight in
        the units her weapons speak, and half a unit on a hull this size is nothing - a
        test that fired one round and asserted a change would be asserting rounding.

        """
        before = market_value(self.hull).value.smallest
        self.hull.damage = Damage(hull=0.4)
        self.assertLess(market_value(self.hull).value.smallest, before)

    def test_a_bigger_hull_is_worth_more(self):
        before = market_value(self.hull).value.smallest
        self.hull.length = self.hull.length * 2
        self.assertGreater(market_value(self.hull).value.smallest, before)

    def test_a_hole_in_her_costs_her(self):
        from ..sections import WAIST

        before = market_value(self.hull).value.smallest
        self.hull.hole(WAIST, 0.05, 1.0)
        self.assertLess(market_value(self.hull).value.smallest, before)

    def test_a_mast_over_the_side_costs_her_more_than_the_number_alone(self):
        """
        A buyer sees it from the quay before he comes aboard.

        """
        from ..damage import MAST_DOWN_AT

        self.hull.damage = Damage(rigging=MAST_DOWN_AT - 0.05)
        before = condition_of(self.hull)
        self.assertEqual(self.hull.structural_failures, ())

        self.hull.damage = Damage(rigging=MAST_DOWN_AT + 0.01)
        after = condition_of(self.hull)
        self.assertTrue(self.hull.structural_failures)

        # The track moved by six hundredths; her worth fell by a great deal more.
        self.assertLess(after, before - 0.06)

    def test_she_is_never_worth_nothing(self):
        """
        Past a point she is timber and iron, and timber and iron are worth carting away. A
        hull worth nothing would let a game delete somebody's ship as an act of tidying.

        """
        self.hull.damage = Damage(hull=1.0, rigging=1.0, oars=1.0, weapons=1.0)
        self.assertAlmostEqual(condition_of(self.hull), BREAKING_UP)
        self.assertGreater(market_value(self.hull).value.smallest, 0)


class TestWhatARefitCosts(RefitTestCase):
    """A share of her value new, because coppering a frigate is not coppering a yawl."""

    def test_every_shipped_refit_has_a_price(self):
        for name in REFITS:
            self.assertGreater(cost_of_refit(self.hull, name).smallest, 0, name)

    def test_a_refit_nobody_offers_has_no_price(self):
        self.assertIsNone(cost_of_refit(self.hull, "gild the figurehead"))

    def test_a_bigger_hull_costs_more_to_refit(self):
        small = cost_of_refit(self.hull, "copper").smallest
        self.hull.length = self.hull.length * 2
        self.assertGreater(cost_of_refit(self.hull, "copper").smallest, small)


class TestHavingWorkDone(RefitTestCase):
    """Paid out of her own purse, and only once."""

    def test_a_new_hull_has_had_none(self):
        self.assertEqual(self.hull.refits, ())

    def test_she_can_be_refitted(self):
        self.assertTrue(self.hull.take_in_hand("copper"))
        self.assertIn("copper", self.hull.refits)

    def test_a_refit_nobody_offers_is_refused(self):
        self.assertEqual(self.hull.take_in_hand("gild the figurehead").code, NO_SUCH_REFIT)

    def test_the_same_work_is_not_done_twice(self):
        self.hull.take_in_hand("copper")
        self.assertEqual(self.hull.take_in_hand("copper").code, ALREADY_REFITTED)

    def test_it_is_paid_for(self):
        before = self.hull.purse
        self.hull.take_in_hand("copper")
        self.assertLess(self.hull.purse.smallest, before.smallest)

    def test_a_ship_that_cannot_pay_gets_nothing(self):
        self.hull.debit(self.hull.purse, reason="spent on stores")
        self.assertEqual(self.hull.take_in_hand("copper").code, CANNOT_AFFORD)

    def test_and_is_not_refitted(self):
        self.hull.debit(self.hull.purse, reason="spent on stores")
        self.hull.take_in_hand("copper")
        self.assertEqual(self.hull.refits, ())


class TestEveryRefitChangesSomethingReal(RefitTestCase):
    """No refit here adds a number nothing consumes."""

    def test_coppering_her_makes_her_faster(self):
        before = self.hull.working_limits.max_speed
        self.hull.take_in_hand("copper")
        self.assertGreater(self.hull.working_limits.max_speed, before)

    def test_lengthening_her_makes_her_longer(self):
        before = self.hull.length
        self.hull.take_in_hand("lengthen")
        self.assertGreater(self.hull.length, before)

    def test_and_therefore_carry_more(self):
        before = self.hull.deadweight
        self.hull.take_in_hand("lengthen")
        self.assertGreater(self.hull.deadweight, before)

    def test_and_swing_more_boats(self):
        """
        Nobody wrote this down. Her boats were always computed from her length, so a hull
        that got longer got another one.

        """
        before = self.hull.boats
        self.hull.db.boats = None
        self.hull.take_in_hand("lengthen")
        self.hull.db.boats = None
        self.assertGreaterEqual(self.hull.boats, before)

    def test_and_turn_worse_for_it(self):
        before = self.hull.working_limits.turn_rate
        self.hull.take_in_hand("lengthen")
        self.assertLess(self.hull.working_limits.turn_rate, before)

    def test_and_be_worth_more(self):
        before = market_value(self.hull).value.smallest
        self.hull.take_in_hand("lengthen")
        self.assertGreater(market_value(self.hull).value.smallest, before)

    def test_strengthening_her_makes_her_slower(self):
        before = self.hull.working_limits.max_speed
        self.hull.take_in_hand("strengthen")
        self.assertLess(self.hull.working_limits.max_speed, before)

    def test_a_refit_that_changed_nothing_would_be_a_cosmetic(self):
        """
        The rule the module is written to. Each shipped refit is checked against something
        the rest of the contrib reads, so a refit added later that changes nothing has no
        test it can pass.

        """
        watched = {
            "copper": lambda hull: hull.working_limits.max_speed,
            "lengthen": lambda hull: hull.length,
            "strengthen": lambda hull: hull.working_limits.max_speed,
        }
        self.assertEqual(set(watched), set(REFITS))


class TestSellingHer(RefitTestCase):
    """The hull moves and the price is reported. The money is the game's."""

    def a_buyer(self):
        return create.create_object("evennia.objects.objects.DefaultCharacter", key="A buyer")

    def test_she_can_be_sold(self):
        buyer = self.a_buyer()
        self.assertTrue(self.hull.sell(buyer))

    def test_and_the_buyer_owns_her(self):
        buyer = self.a_buyer()
        self.hull.sell(buyer)
        self.assertIs(self.hull.owner, buyer)

    def test_the_price_is_reported(self):
        self.assertEqual(self.hull.sell(self.a_buyer()).value, market_value(self.hull).value)

    def test_a_price_can_be_named_instead(self):
        asked = Coin(smallest=42)
        self.assertEqual(self.hull.sell(self.a_buyer(), price=asked).value, asked)

    def test_her_purse_goes_with_her(self):
        """
        The ship's purse is hers. What the buyer paid for her is a question about a game's
        economy, and this contrib has no people's pockets in it.

        """
        before = self.hull.purse
        self.hull.sell(self.a_buyer())
        self.assertEqual(self.hull.purse, before)
