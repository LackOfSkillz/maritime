"""
Tests for how long her people take to do what they are told.

The point of the item is that a ship carries what she carried until the work is done, so
most of these check what she is *still* under rather than what was ordered.

"""

from django.test import override_settings
from evennia.utils import create
from evennia.utils.test_resources import (
    BaseEvenniaCommandTest,
    BaseEvenniaTest,
    BaseEvenniaTestCase,
)

from ..commands import CmdSail
from ..crew import ABLE, CRACK, PRESSED, ShipsCompany
from ..handling import (
    CHANGED_MIND,
    Handling,
    handling_time,
    handling_work,
)
from ..motion import HelmOrders, MotionLimits
from ..position import WorldPosition
from ..rooms import ShipRoom
from ..sailing import BATTLE, FULL, FURLED, REEFED, WORKING
from ..typeclasses import Vessel
from ..vessel import OPEN
from .base import EmptySeaMixin

FRIGATE = 46.0
BREEZE = {"MARITIME_WIND_BEARING": 180.0, "MARITIME_WIND_SPEED": 8.0}


class TestHowMuchWorkAChangeIs(BaseEvenniaTestCase):
    """Canvas moved, times the size of the ship."""

    def test_handing_everything_is_more_work_than_taking_in_a_reef(self):
        self.assertGreater(
            handling_work(FULL, FURLED, FRIGATE), handling_work(FULL, WORKING, FRIGATE)
        )

    def test_a_bigger_ship_is_more_work(self):
        self.assertGreater(handling_work(FULL, FURLED, 60.0), handling_work(FULL, FURLED, 20.0))

    def test_setting_is_the_same_work_as_handing(self):
        """
        A sail is as much trouble to set as to hand. Making the two differ would be
        a claim about rigging rather than about people.

        """
        self.assertAlmostEqual(
            handling_work(FULL, REEFED, FRIGATE), handling_work(REEFED, FULL, FRIGATE)
        )

    def test_changing_nothing_is_no_work(self):
        self.assertAlmostEqual(handling_work(FULL, FULL, FRIGATE), 0.0)


class TestHowLongThatTakes(BaseEvenniaTestCase):
    """The same work, in different hands."""

    def hands_of(self, number, quality):
        """
        Returns:
            hands (float): What that many of those are worth at working her.

        """
        return ShipsCompany(complement=number, fit=number, quality=quality).hands

    def test_more_hands_are_faster(self):
        work = handling_work(FULL, FURLED, FRIGATE)
        self.assertLess(
            handling_time(work, self.hands_of(200, ABLE)),
            handling_time(work, self.hands_of(80, ABLE)),
        )

    def test_a_better_crew_is_faster(self):
        work = handling_work(FULL, FURLED, FRIGATE)
        self.assertLess(
            handling_time(work, self.hands_of(200, CRACK)),
            handling_time(work, self.hands_of(200, PRESSED)),
        )

    def test_a_frightened_crew_is_slower(self):
        work = handling_work(FULL, FURLED, FRIGATE)
        steady = handling_time(work, self.hands_of(200, ABLE), hesitation=0.0)
        shaken = handling_time(work, self.hands_of(200, ABLE), hesitation=1.0)
        self.assertGreater(shaken, steady)

    def test_but_a_frightened_crew_still_get_there(self):
        """Fear is a cost, not a kill switch. They are slow, not refusing."""
        work = handling_work(FULL, FURLED, FRIGATE)
        self.assertLess(handling_time(work, self.hands_of(200, ABLE), hesitation=1.0), float("inf"))

    def test_no_work_takes_no_time(self):
        self.assertAlmostEqual(handling_time(0.0, self.hands_of(200, ABLE)), 0.0)

    def test_nobody_to_do_it_means_it_never_gets_done(self):
        """
        Not instantly. An order given to a ship with nobody left to work her is
        work that never finishes, and answering "at once" would make casualties
        free at exactly the moment they should bite hardest.

        """
        work = handling_work(FULL, FURLED, FRIGATE)
        self.assertEqual(handling_time(work, 0.0), float("inf"))

    def test_a_crack_crew_beats_a_pressed_one_by_a_wide_margin(self):
        """Visible on any watch, which is the whole point of the item."""
        work = handling_work(FULL, BATTLE, FRIGATE)
        crack = handling_time(work, self.hands_of(200, CRACK))
        pressed = handling_time(work, self.hands_of(200, PRESSED))
        self.assertGreater(pressed, crack * 2)


class HandlingShipTestCase(EmptySeaMixin, BaseEvenniaTest):
    """A frigate with a company aboard, under way."""

    def setUp(self):
        super().setUp()
        self.heard = []
        self.hull = create.create_object(Vessel, key="Kestrel")
        self.hull.length, self.hull.beam = FRIGATE, 12.0
        self.hull.motion_limits = MotionLimits(max_speed=8.0, acceleration=0.5, turn_rate=5.0)
        self.hull.maritime_position = WorldPosition(0.0, 0.0)
        self.hull.heading = 90.0
        self.hull.orders = HelmOrders(heading=90.0, speed=4.0)
        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.deck.vessel = self.hull
        self.deck.exposure = OPEN
        self.deck.msg_contents = lambda text, **kwargs: self.heard.append(text)
        self.hull.man(200, ABLE)
        self.hull.sail_plan = FULL


class TestOrderingSail(HandlingShipTestCase):
    """What happens between the order and the canvas."""

    def test_an_order_takes_time(self):
        self.assertGreater(self.hull.order_sail(BATTLE, 0.0), 0.0)

    def test_and_she_carries_what_she_carried_until_it_is_done(self):
        """
        The heart of it. A captain who leaves shortening down until he can see the
        squall is still under a full press when it arrives.

        """
        self.hull.order_sail(BATTLE, 0.0)
        self.assertIs(self.hull.sail_plan, FULL)

    def test_she_is_working_aloft_meanwhile(self):
        self.hull.order_sail(BATTLE, 0.0)
        self.assertTrue(self.hull.working_aloft)

    def test_nothing_happens_early(self):
        seconds = self.hull.order_sail(BATTLE, 0.0)
        self.assertIsNone(self.hull.finish_handling(seconds - 1.0))
        self.assertIs(self.hull.sail_plan, FULL)

    def test_and_then_it_does(self):
        seconds = self.hull.order_sail(BATTLE, 0.0)
        self.assertIs(self.hull.finish_handling(seconds), BATTLE)
        self.assertIs(self.hull.sail_plan, BATTLE)

    def test_and_the_deck_is_clear_afterwards(self):
        seconds = self.hull.order_sail(BATTLE, 0.0)
        self.hull.finish_handling(seconds)
        self.assertFalse(self.hull.working_aloft)

    def test_finishing_twice_does_nothing_the_second_time(self):
        seconds = self.hull.order_sail(BATTLE, 0.0)
        self.hull.finish_handling(seconds)
        self.assertIsNone(self.hull.finish_handling(seconds + 100.0))

    def test_ordering_what_she_already_carries_is_no_work(self):
        self.assertAlmostEqual(self.hull.order_sail(FULL, 0.0), 0.0)
        self.assertFalse(self.hull.working_aloft)

    def test_a_bigger_change_takes_longer(self):
        to_battle = self.hull.time_to_set(BATTLE)
        to_furled = self.hull.time_to_set(FURLED)
        self.assertGreater(to_furled, to_battle)

    def test_a_boat_with_no_company_answers_at_once(self):
        """
        Her people are the host game's, not ours to be slow for. A kayak whose
        paddler took four minutes to shorten sail would be this contrib inventing a
        crew for a hull that has none.

        """
        boat = create.create_object(Vessel, key="Dinghy")
        boat.length = 4.0
        boat.sail_plan = FULL
        self.assertAlmostEqual(boat.order_sail(FURLED, 0.0), 0.0)
        self.assertIs(boat.sail_plan, FURLED)


class TestChangingYourMind(HandlingShipTestCase):
    """Ordering three things in a minute gets a slower answer than ordering one."""

    def test_it_costs_extra(self):
        straight = self.hull.time_to_set(FURLED)
        self.hull.order_sail(BATTLE, 0.0)
        changed = self.hull.time_to_set(FURLED)
        self.assertGreater(changed, straight)

    def test_by_about_what_it_says_it_does(self):
        straight = self.hull.time_to_set(FURLED)
        self.hull.order_sail(BATTLE, 0.0)
        self.assertAlmostEqual(self.hull.time_to_set(FURLED), straight * (1.0 + CHANGED_MIND))

    def test_the_new_order_replaces_the_old_one(self):
        self.hull.order_sail(BATTLE, 0.0)
        seconds = self.hull.order_sail(FURLED, 0.0)
        self.assertIs(self.hull.finish_handling(seconds), FURLED)

    def test_and_the_old_one_never_arrives(self):
        """A countermanded order is countermanded, not queued behind the new one."""
        self.hull.order_sail(BATTLE, 0.0)
        seconds = self.hull.order_sail(FURLED, 0.0)
        self.hull.finish_handling(seconds)
        self.assertIs(self.hull.sail_plan, FURLED)
        self.assertIsNone(self.hull.finish_handling(seconds + 10_000.0))


class TestAFrightenedCrewAloft(HandlingShipTestCase):
    """
    Morale's second customer, after the gun deck.

    These have to work to isolate fear, because casualties do two things at once
    and the larger of them is not fear. Losing 120 of 200 hands would slow her
    right down if the survivors were perfectly steady, so a test that merely
    checks "she got slower" proves nothing about morale at all - which is what
    the first version of this did.

    Morale also does not move at the instant people fall. It settles towards the
    new state over the following minute, so nothing here is true until a watch
    has passed over them.

    """

    def maul_her(self, seconds=60.0):
        """
        Take heavy casualties and let it sink in.

        Returns:
            hands (tuple): Effective hands before and after.

        """
        before = self.hull.hands_to_work_her()
        self.hull.take_casualties(120)
        self.hull.stand_watch(seconds)
        return before, self.hull.hands_to_work_her()

    def test_casualties_alone_do_not_frighten_anybody_yet(self):
        """The fall is not instantaneous, and pretending otherwise hid this."""
        steady = self.hull.hesitation
        self.hull.take_casualties(120)
        self.assertAlmostEqual(self.hull.hesitation, steady)

    def test_but_a_watch_over_them_does(self):
        steady = self.hull.hesitation
        self.maul_her()
        self.assertGreater(self.hull.hesitation, steady)

    def test_casualties_cost_her_more_than_the_hands_they_took(self):
        """
        The claim worth making, and the only one that isolates fear: she is slower
        by *more* than the missing hands account for. Fewer people and frightened
        people compound rather than competing.

        """
        before = self.hull.time_to_set(FURLED)
        had, left = self.maul_her()
        after = self.hull.time_to_set(FURLED)

        hands_alone = had / left
        self.assertGreater(after / before, hands_alone * 1.05)

    def test_and_they_still_get_it_done(self):
        """Fear is a cost, not a kill switch."""
        self.maul_her()
        self.assertLess(self.hull.time_to_set(FURLED), float("inf"))


class TestWhatTheDeckIsTold(HandlingShipTestCase):
    """An order the ship cannot see the end of is not a decision."""

    def test_she_says_how_long_it_will_be(self):
        seconds = self.hull.order_sail(BATTLE, 0.0)
        self.hull.narrator.hands_aloft(BATTLE, seconds)
        self.assertTrue(any("aloft" in line for line in self.heard))

    def test_and_reports_when_it_is_set(self):
        seconds = self.hull.order_sail(BATTLE, 0.0)
        self.hull.finish_handling(seconds)
        self.hull.narrator.sail_set(BATTLE)
        self.assertTrue(any("set, sir" in line for line in self.heard))

    def test_the_tick_reports_it_without_being_asked(self):
        with override_settings(**BREEZE):
            seconds = self.hull.order_sail(BATTLE, 0.0)
            self.heard.clear()
            self.hull.at_maritime_tick(seconds + 1.0)
        self.assertTrue(any("set, sir" in line for line in self.heard))


class TestSheStillWorksWhenSheIsNotMoving(HandlingShipTestCase):
    """
    Whether she is going anywhere has nothing to do with whether her people can
    work.

    Found live: she ran aground with an order outstanding and the hands stayed aloft
    for good, because the tick gave up on a held vessel before it got to them. A ship
    hard on the ground is a ship whose captain very much wants his canvas off her,
    and furling alongside a quay is the most ordinary thing in the world.

    """

    def held(self, how):
        """Put her in one of the states that stops her answering her helm."""
        setattr(self.hull, how, True)

    def test_a_grounded_ship_still_gets_her_canvas_off(self):
        with override_settings(**BREEZE):
            seconds = self.hull.order_sail(FURLED, 0.0)
            self.held("aground")
            self.heard.clear()
            self.hull.at_maritime_tick(seconds + 1.0)
        self.assertIs(self.hull.sail_plan, FURLED)

    def test_and_so_does_an_anchored_one(self):
        with override_settings(**BREEZE):
            seconds = self.hull.order_sail(FURLED, 0.0)
            self.held("anchored")
            self.hull.at_maritime_tick(seconds + 1.0)
        self.assertIs(self.hull.sail_plan, FURLED)

    def test_and_the_deck_hears_about_it(self):
        with override_settings(**BREEZE):
            seconds = self.hull.order_sail(FURLED, 0.0)
            self.held("aground")
            self.heard.clear()
            self.hull.at_maritime_tick(seconds + 1.0)
        self.assertTrue(any("set, sir" in line for line in self.heard))


class TestAPlanThatWentAway(HandlingShipTestCase):
    """A game may redefine its sail plans between one tick and the next."""

    def test_she_keeps_what_she_has(self):
        """
        Rather than losing her canvas to a configuration change. The hands come
        down and she carries on under what was already set.

        """
        self.hull.handling = Handling(plan_key="no-such-plan", was_key=FULL.key, finish_at=0.0)
        self.assertIsNone(self.hull.finish_handling(10.0))
        self.assertIs(self.hull.sail_plan, FULL)
        self.assertFalse(self.hull.working_aloft)


class TestBelayingAnOrder(HandlingShipTestCase):
    """Ordering what she already carries is how you countermand a change."""

    def test_it_cancels_the_work_in_hand(self):
        self.hull.order_sail(BATTLE, 0.0)
        self.hull.order_sail(FULL, 0.0)
        self.assertFalse(self.hull.working_aloft)

    def test_and_she_keeps_what_she_had(self):
        self.hull.order_sail(BATTLE, 0.0)
        self.hull.order_sail(FULL, 0.0)
        self.assertIs(self.hull.sail_plan, FULL)

    def test_and_the_countermanded_plan_never_arrives(self):
        self.hull.order_sail(BATTLE, 0.0)
        self.hull.order_sail(FULL, 0.0)
        self.assertIsNone(self.hull.finish_handling(10_000.0))
        self.assertIs(self.hull.sail_plan, FULL)


class TestTheSailCommandGoesThroughTheHands(EmptySeaMixin, BaseEvenniaCommandTest):
    """
    The player-facing path, which is the one that matters and was untested.

    Every rule above can be right and still not reach a captain, if the command
    quietly assigns the plan instead of asking for the work to be done.

    """

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Test Sloop")
        self.hull.length, self.hull.beam = FRIGATE, 12.0
        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.deck.vessel = self.hull
        self.deck.exposure = OPEN
        self.hull.maritime_position = WorldPosition(0.0, 0.0)
        self.hull.motion_limits = MotionLimits(max_speed=10.0, acceleration=1.0, turn_rate=6.0)
        self.hull.man(200, ABLE)
        self.hull.sail_plan = FULL
        self.char1.location = self.deck

    def test_the_order_is_answered_at_once(self):
        self.assertIn("aye sir", self.call(CmdSail(), "battle"))

    def test_but_the_canvas_does_not_change_yet(self):
        self.call(CmdSail(), "battle")
        self.assertIs(self.hull.sail_plan, FULL)

    def test_and_the_hands_are_sent_aloft(self):
        self.call(CmdSail(), "battle")
        self.assertTrue(self.hull.working_aloft)

    def test_the_deck_is_told_how_long(self):
        self.assertIn("hands go aloft", self.call(CmdSail(), "battle"))

    def test_and_a_captain_checking_his_canvas_is_told_they_are_at_it(self):
        self.call(CmdSail(), "battle")
        self.assertIn("aloft, setting", self.call(CmdSail(), ""))

    def test_an_uncrewed_boat_still_answers_at_once(self):
        """A dinghy is not slow. Her people are the host game's."""
        self.hull.company = None
        self.call(CmdSail(), "furled")
        self.assertIs(self.hull.sail_plan, FURLED)
