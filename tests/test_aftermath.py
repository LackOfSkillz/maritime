"""
Tests for the butcher's bill.

The claim worth testing hardest is that the split is a fact about the crew rather than about
the fight: same shot, same number, different ship.

"""

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest

from ..aftermath import (
    NERVE_RETURNS,
    NO_CASUALTIES,
    NO_SHIRKERS,
    WOUNDED_RECOVER,
    BillCounted,
    resolve,
)
from ..config import time_provider
from ..crew import CRACK, PRESSED, ABLE
from ..events import bus
from ..morale import FLOGGED, grievances
from ..motion import MotionLimits
from ..position import WorldPosition
from ..rooms import ShipRoom
from ..typeclasses import Vessel
from ..vessel import OPEN
from .base import EmptySeaMixin


class TestSortingTheBill(BaseEvenniaTest):
    """The four columns, with no ship attached."""

    def test_nobody_hurt_is_no_bill(self):
        self.assertEqual(resolve(0, ABLE).code, NO_CASUALTIES)

    def test_the_columns_add_up_to_the_count(self):
        """
        Four fractions rounded independently do not sum to the number you started with,
        and a bill that does not balance is a bug found in the field rather than here.

        """
        for count in (1, 7, 40, 113, 250):
            bill = resolve(count, ABLE)
            total = bill.dead + bill.wounded + bill.dazed + bill.shirkers
            self.assertEqual(total, count, f"bill of {count} did not balance")

    def test_a_steady_crew_comes_round(self):
        self.assertGreater(resolve(100, CRACK).dazed, resolve(100, PRESSED).dazed)

    def test_and_an_unsteady_one_does_not(self):
        self.assertGreater(resolve(100, PRESSED).shirkers, resolve(100, CRACK).shirkers)

    def test_same_shot_same_number_different_ship(self):
        """The sharpest thing the quality axis says anywhere, and it was already there."""
        crack = resolve(100, CRACK)
        pressed = resolve(100, PRESSED)
        self.assertEqual(crack.counted, pressed.counted)
        self.assertNotEqual(crack.shirkers, pressed.shirkers)

    def test_a_surgeon_moves_men_out_of_the_first_column(self):
        self.assertLess(resolve(100, ABLE, surgeon=1.0).dead, resolve(100, ABLE).dead)

    def test_and_into_the_second(self):
        self.assertGreater(resolve(100, ABLE, surgeon=1.0).wounded, resolve(100, ABLE).wounded)

    def test_he_does_not_change_the_total(self):
        doctored = resolve(100, ABLE, surgeon=1.0)
        self.assertEqual(doctored.dead + doctored.wounded + doctored.dazed + doctored.shirkers, 100)

    def test_he_cannot_save_everybody(self):
        self.assertGreater(resolve(100, ABLE, surgeon=1.0).dead, 0)


class BillTestCase(EmptySeaMixin, BaseEvenniaTest):
    """A hull with people to lose."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Kestrel")
        self.hull.length, self.hull.beam = 30.0, 8.5
        self.hull.motion_limits = MotionLimits(max_speed=6.0, acceleration=0.5, turn_rate=5.0)
        self.hull.maritime_position = WorldPosition(0.0, 0.0)
        self.hull.heading = 0.0
        deck = create.create_object(ShipRoom, key="Kestrel Deck")
        deck.vessel = self.hull
        deck.exposure = OPEN
        self.hull.man(200, ABLE)

    def maul_her(self, lost=80):
        """Put people off their feet."""
        self.hull.take_casualties(lost)


class TestCountingTheCost(BillTestCase):
    """Making the bill up on a real hull."""

    def test_an_unhurt_ship_has_no_bill(self):
        self.assertFalse(self.hull.count_the_cost())

    def test_a_mauled_one_does(self):
        self.maul_her()
        self.assertTrue(self.hull.count_the_cost())

    def test_the_dead_leave_her_complement(self):
        """A ship that has counted her cost is a smaller ship, not a bruised one."""
        self.maul_her()
        before = self.hull.company.complement
        bill = self.hull.count_the_cost()
        self.assertEqual(self.hull.company.complement, before - bill.dead)

    def test_the_dazed_are_back_at_once(self):
        self.maul_her()
        fit = self.hull.company.fit
        bill = self.hull.count_the_cost()
        self.assertEqual(self.hull.company.fit, fit + bill.dazed)

    def test_the_wounded_are_not(self):
        self.maul_her()
        bill = self.hull.count_the_cost()
        self.assertEqual(self.hull.wounded, bill.wounded)

    def test_nor_are_the_men_who_broke(self):
        self.maul_her()
        bill = self.hull.count_the_cost()
        self.assertEqual(self.hull.shirkers, bill.shirkers)


class TestWhatIsPublished(BillTestCase):
    """The fraction, which is the field the event exists for."""

    def setUp(self):
        super().setUp()
        self.heard = []
        bus().subscribe(BillCounted, self.heard.append)

    def test_it_is_announced(self):
        self.maul_her()
        self.hull.count_the_cost()
        self.assertEqual(len(self.heard), 1)

    def test_and_carries_the_fraction(self):
        """
        So a game can roll its own people against it. We never decide that somebody's
        character is hurt.

        """
        self.maul_her(100)
        self.hull.count_the_cost()
        self.assertGreater(self.heard[0].fraction, 0.0)
        self.assertLessEqual(self.heard[0].fraction, 1.0)

    def test_and_all_four_columns(self):
        self.maul_her()
        self.hull.count_the_cost()
        event = self.heard[0]
        self.assertEqual(
            event.dead + event.wounded + event.dazed + event.shirkers,
            80,
        )


class TestTheMenWhoBroke(BillTestCase):
    """The decision, and what each half of it costs."""

    def setUp(self):
        super().setUp()
        self.maul_her(120)
        self.bill = self.hull.count_the_cost()

    def test_there_were_some(self):
        self.assertGreater(self.hull.shirkers, 0)

    def test_starting_them_gets_the_hands_back(self):
        fit = self.hull.company.fit
        shirkers = self.hull.shirkers
        self.hull.punish_shirkers()
        self.assertEqual(self.hull.company.fit, fit + shirkers)
        self.assertEqual(self.hull.shirkers, 0)

    def test_and_the_company_holds_it_against_you(self):
        self.hull.punish_shirkers()
        self.assertIn(FLOGGED, self.hull.held_against_command())

    def test_letting_it_go_earns_no_grievance(self):
        self.hull.let_it_go()
        self.assertNotIn(FLOGGED, self.hull.held_against_command())

    def test_but_costs_you_the_hands(self):
        fit = self.hull.company.fit
        self.hull.let_it_go()
        self.assertEqual(self.hull.company.fit, fit)
        self.assertGreater(self.hull.shirkers, 0)

    def test_there_is_nobody_to_start_if_nobody_broke(self):
        self.hull.punish_shirkers()
        self.assertEqual(self.hull.punish_shirkers().code, NO_SHIRKERS)

    def test_the_grievance_is_a_real_one(self):
        """It goes through the same door as every other thing a crew holds."""
        self.assertIn(FLOGGED, grievances(punished=True))
        self.assertNotIn(FLOGGED, grievances(punished=False))


class TestTimeBringsThemBack(BillTestCase):
    """
    The wounded and the shaken, on different clocks.

    **Deadlines are stamped from the live clock**, so a test that hands in a bare offset is
    asking whether three days have passed since the epoch rather than since the action. It
    reads as a passing test of nothing. Anchor on the same clock the deadline came from.

    """

    def setUp(self):
        super().setUp()
        self.maul_her(120)
        self.hull.count_the_cost()
        self.action = time_provider().now()

    def test_nerve_returns_within_a_day(self):
        shirkers = self.hull.shirkers
        back = self.hull.stand_watch_over_the_hurt(now=self.action + NERVE_RETURNS + 1.0)
        self.assertGreaterEqual(back, shirkers)
        self.assertEqual(self.hull.shirkers, 0)

    def test_but_not_within_an_hour(self):
        self.hull.stand_watch_over_the_hurt(now=self.action + 3600.0)
        self.assertGreater(self.hull.shirkers, 0)

    def test_a_wound_takes_days(self):
        self.hull.stand_watch_over_the_hurt(now=self.action + NERVE_RETURNS + 1.0)
        self.assertGreater(self.hull.wounded, 0)

    def test_and_then_they_are_back(self):
        self.hull.stand_watch_over_the_hurt(now=self.action + WOUNDED_RECOVER + 1.0)
        self.assertEqual(self.hull.wounded, 0)

    def test_they_come_back_to_a_smaller_ship(self):
        """The dead do not come back, so she never musters what she sailed with."""
        sailed_with = 200
        self.hull.stand_watch_over_the_hurt(now=self.action + WOUNDED_RECOVER + 1.0)
        self.assertLess(self.hull.company.complement, sailed_with)
