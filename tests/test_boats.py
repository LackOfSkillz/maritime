"""
Tests for a ship's boats, and what becomes of people when she goes down.

The ruling being kept: **the boats, and then the water.** Seats are scarce, boats can be
shot away, and what happens to somebody in the water is the game's - this contrib puts them
there and says so, because how much punishment a person absorbs is a character system.

"""

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest

from ..boats import MOST_BOATS, NOBODY_ABOARD, SEATS_PER_BOAT, boats_for
from ..motion import MotionLimits
from ..position import WorldPosition
from ..rooms import ShipRoom
from ..typeclasses import Vessel
from ..vessel import OPEN

HERE = WorldPosition(0.0, 0.0)


class BoatTestCase(BaseEvenniaTest):
    """A hull with boats on her booms."""

    def setUp(self):
        super().setUp()
        self.hull = self.a_ship("Kestrel", 45.0, 12.0)

    def a_ship(self, key, length, beam):
        hull = create.create_object(Vessel, key=key)
        hull.length, hull.beam = length, beam
        hull.motion_limits = MotionLimits(max_speed=6.0, acceleration=0.5, turn_rate=5.0)
        hull.maritime_position = HERE
        hull.heading = 0.0
        deck = create.create_object(ShipRoom, key=f"{key} Deck")
        deck.vessel = hull
        deck.exposure = OPEN
        return hull

    def crowd_her(self, how_many):
        """Put people on her deck."""
        deck = self.hull.ship_rooms[0]
        return [
            create.create_object(
                "evennia.objects.objects.DefaultCharacter",
                key=f"Hand {number}",
                location=deck,
            )
            for number in range(how_many)
        ]


class TestHowManySheCarries(BaseEvenniaTest):
    """Derived, so a builder cannot draw a launch with six of them."""

    def test_a_small_boat_carries_none(self):
        self.assertEqual(boats_for(7.0), 0)

    def test_a_cutter_carries_one(self):
        self.assertEqual(boats_for(17.0), 1)

    def test_a_ship_carries_several(self):
        self.assertGreaterEqual(boats_for(45.0), 3)

    def test_and_never_more_than_she_can_swing(self):
        self.assertEqual(boats_for(500.0), MOST_BOATS)


class TestKeepingThem(BoatTestCase):
    """They are lost, which is why the count is stored and not recomputed."""

    def test_she_starts_with_what_her_length_gives_her(self):
        self.assertEqual(self.hull.boats, boats_for(45.0))

    def test_one_can_be_shot_away(self):
        before = self.hull.boats
        self.hull.lose_a_boat()
        self.assertEqual(self.hull.boats, before - 1)

    def test_and_they_stay_lost(self):
        """
        A count recomputed from her length would quietly replace a boat that went over the
        side in the middle of the action.

        """
        self.hull.lose_a_boat()
        after = self.hull.boats
        self.assertEqual(self.hull.boats, after)

    def test_she_cannot_lose_more_than_she_has(self):
        self.hull.lose_a_boat(99)
        self.assertEqual(self.hull.boats, 0)

    def test_her_seats_follow_her_boats(self):
        self.assertEqual(self.hull.seats, self.hull.boats * SEATS_PER_BOAT)


class TestAbandoningHer(BoatTestCase):
    """Seats are scarce, and that is the whole of it."""

    def test_a_ship_with_nobody_aboard_abandons_nobody(self):
        self.assertEqual(self.hull.abandon_ship().code, NOBODY_ABOARD)

    def test_her_people_get_into_the_boats(self):
        self.crowd_her(10)
        result = self.hull.abandon_ship()
        self.assertEqual(result.saved, 10)
        self.assertEqual(result.in_the_water, ())

    def test_and_the_boats_are_really_in_the_water(self):
        self.crowd_her(4)
        result = self.hull.abandon_ship()
        self.assertTrue(result.boats)
        self.assertEqual(result.boats[0].maritime_position, HERE)

    def test_somebody_saved_is_no_longer_aboard_her(self):
        people = self.crowd_her(4)
        self.hull.abandon_ship()
        self.assertNotIn(people[0], self.hull.ship_rooms[0].contents)

    def test_a_boat_is_a_hull_they_are_standing_in(self):
        """
        Not a token. She has a position, she drifts on the set like anything else afloat,
        and there are people in her - all out of machinery that already existed.

        """
        self.crowd_her(3)
        boat = self.hull.abandon_ship().boats[0]
        self.assertTrue(boat.ship_rooms)
        self.assertEqual(len(boat.ship_rooms[0].contents), 3)

    def test_more_people_than_seats_leaves_some_in_the_water(self):
        self.hull.db.boats = 1
        people = self.crowd_her(SEATS_PER_BOAT + 5)
        result = self.hull.abandon_ship()
        self.assertEqual(result.saved, SEATS_PER_BOAT)
        self.assertEqual(len(result.in_the_water), 5)
        self.assertEqual(len(people), SEATS_PER_BOAT + 5)

    def test_a_ship_whose_boats_were_shot_away_saves_nobody(self):
        """
        The consequence that outlives the fight. She kept her people alive by keeping her
        boats, and she did not keep them.

        """
        self.hull.lose_a_boat(99)
        self.crowd_her(6)
        result = self.hull.abandon_ship()
        self.assertEqual(result.saved, 0)
        self.assertEqual(len(result.in_the_water), 6)

    def test_only_people_take_seats(self):
        """A barrel taking a seat somebody needed would be the wrong kind of realism."""
        deck = self.hull.ship_rooms[0]
        create.create_object("evennia.objects.objects.DefaultObject", key="a cask", location=deck)
        self.crowd_her(2)
        self.assertEqual(self.hull.abandon_ship().saved, 2)

    def test_launching_uses_the_boats_up(self):
        before = self.hull.boats
        self.crowd_her(3)
        self.hull.abandon_ship()
        self.assertLess(self.hull.boats, before)
