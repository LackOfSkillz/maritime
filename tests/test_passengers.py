"""
Tests for people who have paid to be somewhere else.

The claim that makes a passenger different from cargo: **he wants his money back.** Cargo
does not care when it arrives. A captain who takes a prize instead of a passage has been
paid for the prize and not for the passage, and can work out for himself whether that was
worth it.

And the one that makes a schedule real: **a timetable that cannot be kept is refused before
she sails.** A run that repeats has to close.

"""

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest

from ..ledger import Coin
from ..motion import MotionLimits
from ..passengers import (
    ALREADY_ABOARD,
    CANNOT_BE_KEPT,
    NO_ROOM,
    NO_ROUTE,
    NOT_ABOARD,
    NOT_THERE_YET,
    VOLUME_PER_PASSENGER,
    accommodation_for,
    can_be_kept,
    time_to_run,
)
from ..position import WorldPosition
from ..rooms import ShipRoom
from ..routes import Route, Waypoint
from ..typeclasses import Vessel
from ..vessel import OPEN, VesselCapacity

HERE = WorldPosition(0.0, 0.0)

HOME = Waypoint(key="Home", position=WorldPosition(0.0, 0.0))
AWAY = Waypoint(key="Away", position=WorldPosition(10_000.0, 0.0))
OUT_AND_BACK = Route(waypoints=(HOME, AWAY, HOME))
ONE_WAY = Route(waypoints=(HOME, AWAY))


class TestHowManySheCanCarry(BaseEvenniaTest):
    """Derived, so a builder cannot give a launch a hundred."""

    def test_a_boat_carries_nobody(self):
        self.assertEqual(accommodation_for(4.0), 0)

    def test_a_ship_carries_several(self):
        self.assertGreater(accommodation_for(300.0), 1)

    def test_twice_the_volume_is_about_twice_the_people(self):
        """
        About, not exactly. A berth is a whole person, so the count truncates and two
        half-berths in two ships are not a berth in either.

        """
        self.assertAlmostEqual(accommodation_for(600.0), 2 * accommodation_for(300.0), delta=1)

    def test_a_hull_with_no_volume_carries_nobody(self):
        self.assertEqual(accommodation_for(0.0), 0)

    def test_not_all_of_her_is_given_over_to_them(self):
        """
        A hull with every cubic metre full of passengers has nowhere to keep what they eat.

        """
        everybody = 300.0 / VOLUME_PER_PASSENGER
        self.assertLess(accommodation_for(300.0), everybody)


class TestWhetherAScheduleCanBeKept(BaseEvenniaTest):
    """Arithmetic on distances the routes already know."""

    def test_a_ship_making_nothing_never_arrives(self):
        self.assertEqual(time_to_run(ONE_WAY, 0.0), float("inf"))

    def test_a_generous_schedule_can_be_kept(self):
        self.assertTrue(can_be_kept(OUT_AND_BACK, speed=10.0, allowed=100_000.0))

    def test_a_mean_one_cannot(self):
        self.assertEqual(can_be_kept(OUT_AND_BACK, speed=10.0, allowed=10.0).code, CANNOT_BE_KEPT)

    def test_it_says_how_short_she_is(self):
        result = can_be_kept(OUT_AND_BACK, speed=10.0, allowed=10.0)
        self.assertLess(result.slack, 0.0)
        self.assertAlmostEqual(result.needed - result.wanted, -result.slack, places=3)

    def test_a_run_that_ends_where_it_started_closes(self):
        self.assertTrue(can_be_kept(OUT_AND_BACK, speed=10.0, allowed=100_000.0).closes)

    def test_one_that_does_not_is_told_so(self):
        self.assertFalse(can_be_kept(ONE_WAY, speed=10.0, allowed=100_000.0).closes)

    def test_a_run_that_does_not_close_pays_for_the_passage_home(self):
        """
        The whole point of validating a cycle. Otherwise the second sailing starts wherever
        the first one finished, and every one after it is later than the last.

        """
        one_way = can_be_kept(ONE_WAY, speed=10.0, allowed=100_000.0)
        there_and_back = can_be_kept(OUT_AND_BACK, speed=10.0, allowed=100_000.0)
        self.assertAlmostEqual(one_way.needed, there_and_back.needed, places=3)

    def test_unless_the_schedule_says_she_does_not_come_back(self):
        one_way = can_be_kept(ONE_WAY, speed=10.0, allowed=100_000.0, returns=False)
        self.assertLess(one_way.needed, can_be_kept(ONE_WAY, 10.0, 100_000.0).needed)

    def test_a_route_with_one_mark_is_not_a_schedule(self):
        self.assertEqual(can_be_kept(Route(waypoints=(HOME,)), 10.0, 100.0).code, NO_ROUTE)

    def test_nor_is_no_route_at_all(self):
        self.assertEqual(can_be_kept(None, 10.0, 100.0).code, NO_ROUTE)


class PassengerTestCase(BaseEvenniaTest):
    """A hull with cabins in her."""

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

    def a_traveller(self, name="A traveller"):
        return create.create_object(
            "evennia.objects.objects.DefaultCharacter", key=name, location=self.deck
        )


class TestSellingAPassage(PassengerTestCase):
    """A passenger is an object and a destination, and nothing more."""

    def test_a_new_hull_has_sold_none(self):
        self.assertEqual(self.hull.passages, ())

    def test_a_passage_can_be_sold(self):
        self.assertTrue(self.hull.book_passage(self.a_traveller(), "Away"))

    def test_and_she_remembers_it(self):
        self.hull.book_passage(self.a_traveller(), "Away")
        self.assertEqual(len(self.hull.passages), 1)

    def test_the_same_person_cannot_book_twice(self):
        somebody = self.a_traveller()
        self.hull.book_passage(somebody, "Away")
        self.assertEqual(self.hull.book_passage(somebody, "Away").code, ALREADY_ABOARD)

    def test_she_cannot_take_more_than_she_has_room_for(self):
        for number in range(self.hull.accommodation):
            self.hull.book_passage(self.a_traveller(f"Passenger {number}"), "Away")
        self.assertEqual(
            self.hull.book_passage(self.a_traveller("One too many"), "Away").code, NO_ROOM
        )

    def test_the_room_left_counts_down(self):
        before = self.hull.room_for_passengers()
        self.hull.book_passage(self.a_traveller(), "Away")
        self.assertEqual(self.hull.room_for_passengers(), before - 1)

    def test_the_fare_goes_onto_the_ships_purse(self):
        """
        A vessel earning her keep is a vessel that can pay for her own repairs, which is
        the loop this contrib is trying to close.

        """
        before = self.hull.purse
        self.hull.book_passage(self.a_traveller(), "Away", fare=Coin.of(gold=2))
        self.assertGreater(self.hull.purse.smallest, before.smallest)

    def test_a_passage_can_be_sold_for_nothing(self):
        self.assertTrue(self.hull.book_passage(self.a_traveller(), "Away", fare=None))


class TestTheManifest(PassengerTestCase):
    """What a purser reads out."""

    def test_an_empty_ship_has_an_empty_manifest(self):
        self.assertEqual(self.hull.passenger_list(), ())

    def test_it_names_them_and_where_they_are_bound(self):
        self.hull.book_passage(self.a_traveller("Mister Vale"), "Away")
        self.assertEqual(self.hull.passenger_list(), (("Mister Vale", "Away"),))

    def test_it_is_names_rather_than_objects(self):
        """
        A manifest is a document, and a document does not hold references to things that
        can be deleted.

        """
        self.hull.book_passage(self.a_traveller("Mister Vale"), "Away")
        self.assertIsInstance(self.hull.passenger_list()[0][0], str)

    def test_it_keeps_the_order_they_booked_in(self):
        self.hull.book_passage(self.a_traveller("First"), "Away")
        self.hull.book_passage(self.a_traveller("Second"), "Away")
        self.assertEqual([name for name, _ in self.hull.passenger_list()], ["First", "Second"])

    def test_a_traveller_who_has_been_deleted_is_no_longer_aboard(self):
        somebody = self.a_traveller()
        self.hull.book_passage(somebody, "Away")
        somebody.delete()
        self.assertEqual(self.hull.passages, ())


class TestLandingThem(PassengerTestCase):
    """By name, because how near is near enough is a game's question."""

    def test_nobody_lands_at_a_place_nobody_is_bound_for(self):
        self.hull.book_passage(self.a_traveller(), "Away")
        self.assertEqual(self.hull.land_passengers("Somewhere Else").code, NOT_THERE_YET)

    def test_they_land_where_they_paid_to_go(self):
        somebody = self.a_traveller()
        self.hull.book_passage(somebody, "Away")
        landed = self.hull.land_passengers("Away")
        self.assertEqual(landed.landed, (somebody,))

    def test_and_are_no_longer_aboard(self):
        self.hull.book_passage(self.a_traveller(), "Away")
        self.hull.land_passengers("Away")
        self.assertEqual(self.hull.passages, ())

    def test_but_the_ones_bound_elsewhere_stay(self):
        self.hull.book_passage(self.a_traveller("Getting off"), "Away")
        self.hull.book_passage(self.a_traveller("Going on"), "Further")
        self.hull.land_passengers("Away")
        self.assertEqual([name for name, _ in self.hull.passenger_list()], ["Going on"])

    def test_landing_them_makes_room(self):
        self.hull.book_passage(self.a_traveller(), "Away")
        before = self.hull.room_for_passengers()
        self.hull.land_passengers("Away")
        self.assertEqual(self.hull.room_for_passengers(), before + 1)


class TestGivingTheMoneyBack(PassengerTestCase):
    """What makes a passenger different from cargo."""

    def test_somebody_who_never_booked_gets_nothing(self):
        self.assertEqual(self.hull.refund_passage(self.a_traveller()).code, NOT_ABOARD)

    def test_a_passage_can_be_refunded(self):
        somebody = self.a_traveller()
        self.hull.book_passage(somebody, "Away", fare=Coin.of(gold=2))
        self.assertTrue(self.hull.refund_passage(somebody))

    def test_the_money_leaves_the_ship(self):
        somebody = self.a_traveller()
        self.hull.book_passage(somebody, "Away", fare=Coin.of(gold=2))
        with_fare = self.hull.purse
        self.hull.refund_passage(somebody)
        self.assertLess(self.hull.purse.smallest, with_fare.smallest)

    def test_and_it_is_exactly_what_he_paid(self):
        somebody = self.a_traveller()
        before = self.hull.purse
        self.hull.book_passage(somebody, "Away", fare=Coin.of(gold=2))
        self.hull.refund_passage(somebody)
        self.assertEqual(self.hull.purse.smallest, before.smallest)

    def test_he_is_no_longer_aboard(self):
        somebody = self.a_traveller()
        self.hull.book_passage(somebody, "Away", fare=Coin.of(gold=2))
        self.hull.refund_passage(somebody)
        self.assertEqual(self.hull.passages, ())

    def test_a_free_passage_refunds_nothing_and_still_lets_him_off(self):
        somebody = self.a_traveller()
        self.hull.book_passage(somebody, "Away")
        result = self.hull.refund_passage(somebody)
        self.assertTrue(result)
        self.assertIsNone(result.refunded)

    def test_a_ship_that_cannot_pay_refuses_rather_than_going_into_debt(self):
        """
        Debt is a game's question and this contrib has no view on it. What it will not do
        is quietly let a purse go negative.

        """
        somebody = self.a_traveller()
        self.hull.book_passage(somebody, "Away", fare=Coin.of(gold=2))
        self.hull.debit(self.hull.purse, reason="spent on stores")
        self.assertFalse(self.hull.refund_passage(somebody))

    def test_and_he_is_still_aboard_owed_his_money(self):
        somebody = self.a_traveller()
        self.hull.book_passage(somebody, "Away", fare=Coin.of(gold=2))
        self.hull.debit(self.hull.purse, reason="spent on stores")
        self.hull.refund_passage(somebody)
        self.assertEqual(len(self.hull.passages), 1)
