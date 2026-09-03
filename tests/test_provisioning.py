"""
Tests for what she has aboard to keep her people alive.

The claim: **this is the pacing lever, and it is geography rather than a dial.** How far a
hull can go is her stores divided by her company, both of which a player chose. And running
out costs morale, not lives - a contrib that killed a game's characters over biscuit would
be writing a survival system nobody asked for.

"""

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest

from ..crew import SEAMEN, Division, ShipsCompany
from ..ledger import Coin
from ..motion import MotionLimits
from ..position import WorldPosition
from ..provisioning import (
    CANNOT_AFFORD,
    HUNGER,
    NOTHING_TO_STOW,
    RATION,
    RUNNING_SHORT,
    SHORT_ALLOWANCE,
    daily_ration,
    days_of,
)
from ..rooms import ShipRoom
from ..typeclasses import Vessel
from ..vessel import OPEN, VesselCapacity

HERE = WorldPosition(0.0, 0.0)


class TestHowLongItLasts(BaseEvenniaTest):
    """Days, not a percentage - a number a player can count on his fingers."""

    def test_a_company_gets_through_its_ration(self):
        self.assertAlmostEqual(daily_ration(40), 40 * RATION)

    def test_a_ship_with_nobody_aboard_gets_through_nothing(self):
        self.assertAlmostEqual(daily_ration(0), 0.0)

    def test_and_can_go_for_ever(self):
        self.assertEqual(days_of(1.0, complement=0), float("inf"))

    def test_stores_last_as_long_as_they_last(self):
        self.assertAlmostEqual(days_of(40 * RATION * 30.0, complement=40), 30.0)

    def test_a_smaller_crew_goes_further_on_the_same_casks(self):
        """
        The whole of the pacing model. A ship crowded with marines for a boarding cannot
        cross an ocean, and nobody has to be told - they can count.

        """
        self.assertGreater(days_of(10.0, complement=20), days_of(10.0, complement=40))

    def test_short_allowance_stretches_them(self):
        full = days_of(10.0, complement=40)
        stretched = days_of(10.0, complement=40, allowance=SHORT_ALLOWANCE)
        self.assertAlmostEqual(stretched, full * SHORT_ALLOWANCE, places=6)

    def test_an_empty_hold_lasts_no_time_at_all(self):
        self.assertAlmostEqual(days_of(0.0, complement=40), 0.0)


class ProvisionTestCase(BaseEvenniaTest):
    """A hull with a company to feed."""

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
        self.deck = create.create_object(ShipRoom, key="Deck")
        self.deck.vessel = self.hull
        self.deck.exposure = OPEN
        self.hull.company = ShipsCompany(
            complement=40, fit=40, divisions=(Division(SEAMEN, 40, 40),)
        )


class TestStoringShip(ProvisionTestCase):
    """Bought, out of her own purse."""

    def test_a_new_hull_has_nothing_aboard(self):
        self.assertAlmostEqual(self.hull.stores, 0.0)

    def test_stores_can_be_taken_on(self):
        self.assertTrue(self.hull.take_on_stores(5.0))
        self.assertAlmostEqual(self.hull.stores, 5.0)

    def test_taking_on_nothing_is_refused(self):
        self.assertEqual(self.hull.take_on_stores(0.0).code, NOTHING_TO_STOW)

    def test_they_add_up(self):
        self.hull.take_on_stores(5.0)
        self.hull.take_on_stores(3.0)
        self.assertAlmostEqual(self.hull.stores, 8.0)

    def test_they_can_be_paid_for(self):
        self.hull.credit(Coin.of(gold=5), reason="the fixture")
        before = self.hull.purse
        self.hull.take_on_stores(5.0, cost=Coin.of(gold=2))
        self.assertLess(self.hull.purse.smallest, before.smallest)

    def test_a_ship_that_cannot_pay_gets_nothing(self):
        self.assertEqual(self.hull.take_on_stores(5.0, cost=Coin.of(gold=99)).code, CANNOT_AFFORD)

    def test_and_takes_nothing_aboard(self):
        """
        Refused rather than half-done. A chandler who was not paid did not deliver.

        """
        self.hull.take_on_stores(5.0, cost=Coin.of(gold=99))
        self.assertAlmostEqual(self.hull.stores, 0.0)

    def test_she_reports_how_long_they_will_last(self):
        self.hull.take_on_stores(40 * RATION * 30.0)
        self.assertAlmostEqual(self.hull.days_of_stores(), 30.0, places=3)


class TestGettingThroughThem(ProvisionTestCase):
    """The clock that was missing."""

    def setUp(self):
        super().setUp()
        self.hull.take_on_stores(40 * RATION * 30.0)

    def test_a_day_costs_her_a_day(self):
        before = self.hull.days_of_stores()
        self.hull.eat(1.0)
        self.assertAlmostEqual(self.hull.days_of_stores(), before - 1.0, places=3)

    def test_and_says_what_was_eaten(self):
        self.assertAlmostEqual(self.hull.eat(1.0).eaten, daily_ration(40), places=6)

    def test_no_time_passing_eats_nothing(self):
        before = self.hull.stores
        self.hull.eat(0.0)
        self.assertAlmostEqual(self.hull.stores, before)

    def test_she_says_when_she_is_running_short(self):
        self.assertFalse(self.hull.stores_report().short)
        self.hull.eat(30.0 - RUNNING_SHORT + 1.0)
        self.assertTrue(self.hull.stores_report().short)

    def test_and_when_she_is_out(self):
        self.hull.eat(40.0)
        self.assertTrue(self.hull.stores_report().out)

    def test_she_cannot_eat_more_than_she_has(self):
        self.hull.eat(400.0)
        self.assertAlmostEqual(self.hull.stores, 0.0)

    def test_a_ship_with_nobody_aboard_eats_nothing(self):
        self.hull.company = ShipsCompany(complement=0, fit=0)
        before = self.hull.stores
        self.hull.eat(10.0)
        self.assertAlmostEqual(self.hull.stores, before)


class TestAShipNobodyHasVictualled(ProvisionTestCase):
    """Zero is a fact about what she has, not about whether anybody ever gave her any."""

    def test_a_new_hull_has_never_been_stored(self):
        self.assertFalse(self.hull.victualled)

    def test_and_eats_nothing(self):
        before = self.hull.morale
        self.hull.eat(100.0)
        self.assertAlmostEqual(self.hull.morale, before)

    def test_which_is_what_keeps_an_existing_world_from_starving(self):
        """
        Every hull in every existing game knows nothing about stores. Without this they
        would all begin losing morale on the first tick after the module was installed, and
        a game that wanted none of this would have had a famine installed with it.

        """
        self.hull.eat(1000.0)
        self.assertAlmostEqual(self.hull.morale, self.hull.morale)
        self.assertGreater(self.hull.morale, 0.0)

    def test_storing_her_puts_her_in_the_model(self):
        self.hull.take_on_stores(1.0)
        self.assertTrue(self.hull.victualled)

    def test_and_she_stays_in_it_when_she_has_eaten_everything(self):
        """
        A ship that has eaten everything aboard *is* starving, and that is the whole point.

        """
        self.hull.take_on_stores(40 * RATION * 2.0)
        self.hull.eat(10.0)
        self.assertTrue(self.hull.victualled)
        self.assertAlmostEqual(self.hull.stores, 0.0)

        before = self.hull.morale
        self.hull.eat(1.0)
        self.assertLess(self.hull.morale, before)


class TestGoingHungry(ProvisionTestCase):
    """Morale, not lives."""

    def setUp(self):
        super().setUp()
        # Stored once and eaten out, so she is a ship that has run out rather than one
        # nobody has ever victualled - which are different states and behave differently.
        self.hull.take_on_stores(40 * RATION * 0.5)
        self.hull.eat(1.0)

    def test_a_fed_company_keeps_its_temper(self):
        self.hull.take_on_stores(40 * RATION * 30.0)
        before = self.hull.morale
        self.hull.eat(1.0)
        self.assertAlmostEqual(self.hull.morale, before)

    def test_an_unfed_one_does_not(self):
        before = self.hull.morale
        self.hull.eat(1.0)
        self.assertLess(self.hull.morale, before)

    def test_and_it_gets_worse_the_longer_it_goes_on(self):
        """
        Hunger is slow. A company on short commons for a day are grumbling and a company
        starving for a fortnight are a different ship.

        """
        after_a_day = self.hull.morale - HUNGER
        self.hull.eat(1.0)
        self.assertAlmostEqual(self.hull.morale, max(0.0, after_a_day), places=6)
        self.hull.eat(3.0)
        self.assertLess(self.hull.morale, max(0.0, after_a_day))

    def test_it_never_goes_below_nothing(self):
        self.hull.eat(1000.0)
        self.assertGreaterEqual(self.hull.morale, 0.0)

    def test_nobody_dies_of_it(self):
        """
        A contrib that started killing a game's characters over biscuit would be writing a
        survival system nobody asked for.

        """
        before = self.hull.company.complement
        self.hull.eat(100.0)
        self.assertEqual(self.hull.company.complement, before)


class TestShortAllowance(ProvisionTestCase):
    """A real decision: their temper traded for sea room."""

    def setUp(self):
        super().setUp()
        self.hull.take_on_stores(40 * RATION * 30.0)

    def test_a_ship_starts_on_full_rations(self):
        self.assertFalse(self.hull.short_allowance)
        self.assertAlmostEqual(self.hull.allowance, 1.0)

    def test_they_can_be_put_on_short_commons(self):
        self.hull.short_allowance = True
        self.assertAlmostEqual(self.hull.allowance, SHORT_ALLOWANCE)

    def test_which_makes_the_stores_last_longer(self):
        full = self.hull.days_of_stores()
        self.hull.short_allowance = True
        self.assertGreater(self.hull.days_of_stores(), full)

    def test_and_costs_them_something(self):
        self.hull.short_allowance = True
        before = self.hull.morale
        self.hull.eat(4.0)
        self.assertLess(self.hull.morale, before)

    def test_but_less_than_going_without_altogether(self):
        """
        Which is what makes it a decision rather than a worse option. Half rations are
        unpleasant; nothing at all is a different ship.

        """
        self.hull.short_allowance = True
        self.hull.eat(4.0)
        on_short = self.hull.morale

        # Victualled and eaten out, so she is genuinely starving rather than merely
        # unknown to the model - which is the distinction `victualled` exists to draw.
        starved = create.create_object(Vessel, key="Wren")
        starved.company = ShipsCompany(complement=40, fit=40, divisions=(Division(SEAMEN, 40, 40),))
        starved.take_on_stores(40 * RATION * 0.1)
        starved.eat(4.0)
        self.assertAlmostEqual(starved.stores, 0.0)
        self.assertGreater(on_short, starved.morale)
