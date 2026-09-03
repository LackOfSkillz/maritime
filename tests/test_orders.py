"""
Tests for what she is to do when nobody is asking.

Three claims. **Orders are named, not written**, so they survive a reload. **One order acts
and the rest are named**, because merging two orders that both want the helm gives a ship
that does neither thing properly. And **the condition is re-read, not latched**, which is
what lets an order let go of her when the squall passes.

"""

from django.test import override_settings

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest

from ..motion import HelmOrders, MotionLimits
from ..orders import (
    ACTIONS,
    CONDITIONS,
    MAKING_WATER_AT,
    NO_SUCH_ACTION,
    NO_SUCH_CONDITION,
    NO_SUCH_ORDER,
    NOTHING_IN_FORCE,
    StandingOrder,
)
from ..position import WorldPosition
from ..rooms import ShipRoom
from ..sailing import FULL, REEFED, WORKING
from ..typeclasses import Vessel
from ..vessel import OPEN, VesselCapacity
from .base import EmptySeaMixin

HERE = WorldPosition(0.0, 0.0)


def always(vessel):
    """
    Args:
        vessel (object): The hull.

    Returns:
        holds (bool): True.

    """
    return True


def never(vessel):
    """
    Args:
        vessel (object): The hull.

    Returns:
        holds (bool): False.

    """
    return False


def note_it(vessel):
    """
    An action a game might register, which records that it ran.

    Args:
        vessel (object): The hull.

    Returns:
        acted (bool): True.

    """
    vessel.db.was_noted = True
    return True


EXTRA_CONDITIONS = dict(CONDITIONS, always=always, never=never)
EXTRA_ACTIONS = dict(ACTIONS, note_it=note_it)


class OrderTestCase(EmptySeaMixin, BaseEvenniaTest):
    """A hull that can be left word with."""

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
        self.hull.sail_plan = FULL
        self.deck = create.create_object(ShipRoom, key="Deck")
        self.deck.vessel = self.hull
        self.deck.exposure = OPEN


class TestLeavingWord(OrderTestCase):
    """An order refused is better than one that never fires and never says why."""

    def test_a_new_hull_is_under_no_orders(self):
        self.assertEqual(self.hull.standing_orders, ())

    def test_word_can_be_left(self):
        self.assertTrue(self.hull.leave_order("squall", "blowing_hard", "shorten_sail"))
        self.assertEqual(len(self.hull.standing_orders), 1)

    def test_a_condition_nobody_can_answer_is_refused(self):
        result = self.hull.leave_order("nonsense", "if_she_feels_like_it", "shorten_sail")
        self.assertEqual(result.code, NO_SUCH_CONDITION)

    def test_and_an_action_nobody_can_take(self):
        result = self.hull.leave_order("nonsense", "blowing_hard", "summon_a_kraken")
        self.assertEqual(result.code, NO_SUCH_ACTION)

    def test_a_refused_order_is_not_kept(self):
        """
        The point of refusing. An order stored and never fired would fail silently every
        tick for the rest of the voyage.

        """
        self.hull.leave_order("nonsense", "if_she_feels_like_it", "shorten_sail")
        self.assertEqual(self.hull.standing_orders, ())

    def test_word_can_be_taken_back(self):
        self.hull.leave_order("squall", "blowing_hard", "shorten_sail")
        self.assertTrue(self.hull.cancel_order("squall"))
        self.assertEqual(self.hull.standing_orders, ())

    def test_cancelling_an_order_she_never_had_is_a_failure(self):
        self.assertEqual(self.hull.cancel_order("squall").code, NO_SUCH_ORDER)

    def test_leaving_the_same_word_twice_replaces_it(self):
        self.hull.leave_order("squall", "blowing_hard", "shorten_sail")
        self.hull.leave_order("squall", "making_water", "man_the_pumps")
        self.assertEqual(len(self.hull.standing_orders), 1)
        self.assertEqual(self.hull.standing_orders[0].then, "man_the_pumps")

    def test_orders_come_back_highest_priority_first(self):
        self.hull.leave_order("low", "blowing_hard", "shorten_sail", priority=1)
        self.hull.leave_order("high", "making_water", "man_the_pumps", priority=9)
        self.assertEqual([order.key for order in self.hull.standing_orders], ["high", "low"])

    def test_an_order_is_plain_values_and_survives_a_pickle(self):
        """
        Why the condition is a name. An attribute is a pickle, a function is not reliably
        one, and the order that worked all session would be gone after a reload.

        """
        import pickle

        order = StandingOrder(key="squall", when="blowing_hard", then="shorten_sail")
        self.assertEqual(pickle.loads(pickle.dumps(order)), order)


@override_settings(MARITIME_ORDER_CONDITIONS=EXTRA_CONDITIONS, MARITIME_ORDER_ACTIONS=EXTRA_ACTIONS)
class TestWhatAGameCanRegister(OrderTestCase):
    """A game with a war of its own ranks its conditions alongside these."""

    def test_a_game_condition_is_accepted(self):
        self.assertTrue(self.hull.leave_order("test", "always", "shorten_sail"))

    def test_and_a_game_action(self):
        self.assertTrue(self.hull.leave_order("test", "always", "note_it"))

    def test_and_it_actually_runs(self):
        self.hull.leave_order("test", "always", "note_it")
        self.hull.obey_standing_orders()
        self.assertTrue(self.hull.db.was_noted)

    def test_the_shipped_ones_still_work_alongside(self):
        self.assertTrue(self.hull.leave_order("squall", "blowing_hard", "shorten_sail"))


@override_settings(MARITIME_ORDER_CONDITIONS=EXTRA_CONDITIONS, MARITIME_ORDER_ACTIONS=EXTRA_ACTIONS)
class TestWhichOrderIsInForce(OrderTestCase):
    """One acts, and the rest are named."""

    def test_a_ship_with_no_orders_has_none_in_force(self):
        self.assertEqual(self.hull.order_in_force().code, NOTHING_IN_FORCE)

    def test_nor_has_one_whose_conditions_are_all_false(self):
        self.hull.leave_order("quiet", "never", "shorten_sail")
        self.assertEqual(self.hull.order_in_force().code, NOTHING_IN_FORCE)

    def test_an_order_whose_condition_holds_is_in_force(self):
        self.hull.leave_order("test", "always", "shorten_sail")
        self.assertEqual(self.hull.order_in_force().order.key, "test")

    def test_the_higher_priority_wins(self):
        self.hull.leave_order("low", "always", "shorten_sail", priority=1)
        self.hull.leave_order("high", "always", "heave_to", priority=9)
        self.assertEqual(self.hull.order_in_force().order.key, "high")

    def test_and_the_loser_is_named_rather_than_forgotten(self):
        """
        The single worst thing this module could do is let an order lose silently. A captain
        who finds his ship hove to instead of reefed needs to be told which order did it.

        """
        self.hull.leave_order("low", "always", "shorten_sail", priority=1)
        self.hull.leave_order("high", "always", "heave_to", priority=9)
        overridden = self.hull.order_in_force().overridden
        self.assertEqual([order.key for order in overridden], ["low"])

    def test_a_tie_goes_to_the_order_given_first(self):
        """
        A stated rule, so it is worth a test rather than an accident of how a sort happens
        to behave. Two orders of equal weight are settled by which one the captain left
        first, which is the answer he would expect.

        """
        self.hull.leave_order("first", "always", "shorten_sail", priority=5)
        self.hull.leave_order("second", "always", "heave_to", priority=5)
        self.assertEqual(self.hull.order_in_force().order.key, "first")

    def test_an_order_that_does_not_hold_is_not_named_as_overridden(self):
        self.hull.leave_order("quiet", "never", "shorten_sail", priority=1)
        self.hull.leave_order("loud", "always", "heave_to", priority=9)
        self.assertEqual(self.hull.order_in_force().overridden, ())

    def test_only_the_winner_acts(self):
        """
        Merging two orders that both want the helm gives a ship that does neither thing
        properly. She is hove to, not reefed and hove to at once.

        """
        self.hull.leave_order("low", "always", "shorten_sail", priority=1)
        self.hull.leave_order("high", "always", "heave_to", priority=9)
        self.hull.obey_standing_orders()
        self.assertAlmostEqual(self.hull.sail_plan.area, 0.0)


class TestTheConditionsSheCanAnswer(OrderTestCase):
    """Each is answerable out of state this contrib already owns."""

    def test_a_dry_ship_is_not_making_water(self):
        self.hull.leave_order("pumps", "making_water", "man_the_pumps")
        self.assertEqual(self.hull.orders_that_hold(), ())

    def test_a_wet_one_is(self):
        self.hull.leave_order("pumps", "making_water", "man_the_pumps")
        self.hull.db.water = MAKING_WATER_AT + 0.05
        self.assertEqual(len(self.hull.orders_that_hold()), 1)

    def test_a_ship_not_alight_is_not_on_fire(self):
        self.hull.leave_order("fire", "on_fire", "heave_to")
        self.assertEqual(self.hull.orders_that_hold(), ())

    def test_one_that_is_alight_is(self):
        self.hull.leave_order("fire", "on_fire", "heave_to")
        self.hull.catch_fire(1)
        self.assertEqual(len(self.hull.orders_that_hold()), 1)

    def test_a_ship_afloat_is_not_aground(self):
        self.hull.leave_order("ashore", "aground", "heave_to")
        self.assertEqual(self.hull.orders_that_hold(), ())

    def test_one_on_the_ground_is(self):
        self.hull.leave_order("ashore", "aground", "heave_to")
        self.hull.aground = True
        self.assertEqual(len(self.hull.orders_that_hold()), 1)

    def test_a_hull_nowhere_answers_nothing_about_the_weather(self):
        self.hull.leave_order("squall", "blowing_hard", "shorten_sail")
        self.hull.maritime_position = None
        self.assertEqual(self.hull.orders_that_hold(), ())

    def test_nor_about_the_water_under_her(self):
        self.hull.leave_order("shoals", "shoal_water", "heave_to")
        self.hull.maritime_position = None
        self.assertEqual(self.hull.orders_that_hold(), ())

    def test_an_empty_sea_has_no_strangers_in_it(self):
        self.hull.leave_order("sail ho", "stranger_in_sight", "clear_for_action")
        self.assertEqual(self.hull.orders_that_hold(), ())


class TestTheActionsSheCanTake(OrderTestCase):
    """Canvas, the helm and the pumps - and nothing that needs a game."""

    def test_shortening_sail_takes_canvas_in(self):
        self.hull.sail_plan = FULL
        ACTIONS["shorten_sail"](self.hull)
        self.assertAlmostEqual(self.hull.sail_plan.area, REEFED.area)

    def test_shortening_a_ship_already_reefed_changes_nothing(self):
        self.hull.sail_plan = REEFED
        self.assertFalse(ACTIONS["shorten_sail"](self.hull))

    def test_making_sail_sets_canvas(self):
        self.hull.sail_plan = REEFED
        ACTIONS["make_sail"](self.hull)
        self.assertAlmostEqual(self.hull.sail_plan.area, WORKING.area)

    def test_making_sail_on_a_ship_already_carrying_it_changes_nothing(self):
        self.hull.sail_plan = FULL
        self.assertFalse(ACTIONS["make_sail"](self.hull))

    def test_heaving_to_furls_her_and_stops_her(self):
        self.hull.sail_plan = FULL
        self.hull.orders = HelmOrders(heading=0.0, speed=4.0)
        ACTIONS["heave_to"](self.hull)
        self.assertAlmostEqual(self.hull.sail_plan.area, 0.0)
        self.assertAlmostEqual(self.hull.orders.speed, 0.0)

    def test_clearing_for_action_sets_fighting_sail(self):
        from ..sailing import BATTLE

        ACTIONS["clear_for_action"](self.hull)
        self.assertIs(self.hull.sail_plan, BATTLE)

    def test_a_ship_with_nobody_aboard_cannot_man_her_pumps(self):
        self.assertFalse(ACTIONS["man_the_pumps"](self.hull))


@override_settings(MARITIME_ORDER_CONDITIONS=EXTRA_CONDITIONS, MARITIME_ORDER_ACTIONS=EXTRA_ACTIONS)
class TestAnOrderLetsGoOfHer(OrderTestCase):
    """Re-read, not latched. The squall passes and she makes sail again."""

    def test_an_order_that_holds_acts(self):
        self.hull.leave_order("test", "always", "shorten_sail")
        self.assertTrue(self.hull.obey_standing_orders().acted)

    def test_and_reports_that_it_did(self):
        self.hull.leave_order("test", "always", "shorten_sail")
        self.assertEqual(self.hull.obey_standing_orders().order.key, "test")

    def test_an_order_whose_condition_has_stopped_holding_does_nothing(self):
        """
        The whole reason `orders_that_hold` is asked again rather than a flag being set the
        first time. A latched order would leave a ship reefed for the rest of the voyage
        because it blew hard once.

        """
        self.hull.leave_order("weather", "making_water", "shorten_sail")
        self.hull.db.water = MAKING_WATER_AT + 0.05
        self.assertTrue(self.hull.obey_standing_orders())

        self.hull.db.water = 0.0
        self.assertEqual(self.hull.obey_standing_orders().code, NOTHING_IN_FORCE)

    def test_an_order_that_changes_nothing_still_reports_which_one_it_was(self):
        """
        Acting and being in force are different facts. An order to shorten sail on a ship
        already reefed did not fail - there was simply nothing left to take in.

        """
        self.hull.sail_plan = REEFED
        self.hull.leave_order("test", "always", "shorten_sail")
        result = self.hull.obey_standing_orders()
        self.assertTrue(result)
        self.assertFalse(result.acted)
