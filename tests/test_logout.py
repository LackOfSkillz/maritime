"""
LOGOUT-001: what Evennia does when a character disconnects, pinned as tests.

These are not tests of this contrib. They are tests of the engine underneath it,
written because the answers decide how passengers, flooding and vessel destruction
have to be built, and because guessing at them would have been cheaper now and much
more expensive later. `docs/logout.md` is the write-up.

If one of these ever fails, Evennia has changed something this design leans on, and
the failure is the notice. That is the whole point of pinning them.

"""

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest

from ..position import WorldPosition
from ..resolver import NoWorldPosition, get_world_position
from ..rooms import ShipRoom, absent_from, everyone_in
from ..typeclasses import Vessel
from ..vessel import OPEN
from .base import EmptySeaMixin


class Silent:
    """An account that records what it was told rather than sending it anywhere."""

    def __init__(self):
        self.said = []

    def msg(self, text, session=None):
        self.said.append(text)


class LogoutTestCase(EmptySeaMixin, BaseEvenniaTest):
    """A passenger in a cabin aboard a ship, and a quay to call home."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Spike Packet")
        self.hull.maritime_position = WorldPosition(1000.0, 0.0)

        self.cabin = create.create_object(ShipRoom, key="Passenger Cabin")
        self.cabin.vessel = self.hull
        self.cabin.exposure = OPEN

        self.quay = create.create_object("evennia.objects.objects.DefaultRoom", key="The Quay")

        self.passenger = create.create_object(
            "evennia.objects.objects.DefaultCharacter", key="A Passenger"
        )
        self.passenger.home = self.quay
        self.passenger.location = self.cabin


class TestUnpuppeting(LogoutTestCase):
    """What logging out actually does."""

    def test_she_is_taken_off_the_grid_entirely(self):
        """Not left standing in the cabin - removed from the world."""
        self.passenger.at_post_unpuppet()
        self.assertIsNone(self.passenger.location)

    def test_the_room_is_remembered(self):
        self.passenger.at_post_unpuppet()
        self.assertEqual(self.passenger.db.prelogout_location, self.cabin)

    def test_she_is_not_in_the_rooms_contents(self):
        """The finding that matters most. See `absent_from`."""
        self.passenger.at_post_unpuppet()
        self.assertNotIn(self.passenger, self.cabin.contents)

    def test_she_has_no_world_position_at_all(self):
        """Correct, and worth knowing: an offline passenger is not at sea."""
        self.passenger.at_post_unpuppet()
        self.assertIs(get_world_position(self.passenger), NoWorldPosition)

    def test_a_session_still_attached_keeps_her_aboard(self):
        """Only the last session leaving stows her away."""
        self.passenger.sessions.add(self.session)
        self.passenger.at_post_unpuppet()
        self.assertEqual(self.passenger.location, self.cabin)


class TestReconnecting(LogoutTestCase):
    """What logging back in does."""

    def test_she_is_put_back_in_the_same_room(self):
        self.passenger.at_post_unpuppet()
        self.passenger.at_pre_puppet(account=Silent())
        self.assertEqual(self.passenger.location, self.cabin)

    def test_and_the_room_has_taken_her_with_it(self):
        """
        The payoff of ships not being moving rooms.

        She logged out off one coast and back in off another, and nothing stored
        a coordinate for her. Because a compartment holds no position, restoring
        a stale room reference restores the *right* position rather than an old
        one.

        """
        self.passenger.at_post_unpuppet()
        self.hull.maritime_position = WorldPosition(5000.0, 0.0)
        self.passenger.at_pre_puppet(account=Silent())
        self.assertEqual(get_world_position(self.passenger).x, 5000.0)

    def test_an_already_placed_character_is_left_alone(self):
        self.passenger.at_pre_puppet(account=Silent())
        self.assertEqual(self.passenger.location, self.cabin)


class TestWhichHooksFire(LogoutTestCase):
    """
    The asymmetry, and the reason it exists.

    Notes:
        `at_post_unpuppet` sets `location = None` directly, and Evennia's location
        setter fires no move hooks at all - it updates the foreign key and the
        contents cache and returns. `at_pre_puppet` then calls
        `at_object_receive` explicitly.

        So a room hears people arrive and never hears them leave. Anything
        counting who is aboard from move hooks will over-count by exactly the
        number of players who logged out there.

    """

    def setUp(self):
        super().setUp()
        self.seen = []
        self.cabin.at_object_leave = lambda obj, target, **kw: self.seen.append("leave")
        self.cabin.at_object_receive = lambda obj, source, **kw: self.seen.append("receive")

    def test_nothing_fires_on_logout(self):
        self.passenger.at_post_unpuppet()
        self.assertEqual(self.seen, [])

    def test_receive_fires_on_login(self):
        self.passenger.at_post_unpuppet()
        self.seen.clear()
        self.passenger.at_pre_puppet(account=Silent())
        self.assertEqual(self.seen, ["receive"])


class TestWhenTheRoomIsGone(LogoutTestCase):
    """She sank while they were offline."""

    def test_the_remembered_room_becomes_nothing(self):
        """A deleted row deserialises to None rather than to a broken reference."""
        self.passenger.at_post_unpuppet()
        self.cabin.delete()
        self.assertIsNone(self.passenger.db.prelogout_location)

    def test_and_they_are_silently_sent_home(self):
        """
        The default policy, and it is a policy. A ship that founders and is
        deleted teleports every offline passenger to their home room, with no
        message and no event anybody can hook. Recorded in `DECISIONS.md`.

        """
        self.passenger.at_post_unpuppet()
        self.cabin.delete()
        self.passenger.at_pre_puppet(account=Silent())
        self.assertEqual(self.passenger.location, self.quay)

    def test_with_no_home_either_they_are_stuck(self):
        self.passenger.home = None
        self.passenger.at_post_unpuppet()
        self.cabin.delete()
        account = Silent()
        self.passenger.at_pre_puppet(account=account)
        self.assertIsNone(self.passenger.location)
        self.assertTrue(account.said)


class TestFindingThemAnyway(LogoutTestCase):
    """The helpers that close the gap this spike found."""

    def test_an_absent_passenger_is_found(self):
        self.passenger.at_post_unpuppet()
        self.assertEqual(absent_from(self.cabin), (self.passenger,))

    def test_a_present_one_is_not_absent(self):
        self.assertEqual(absent_from(self.cabin), ())

    def test_somebody_absent_from_another_room_is_not_found(self):
        other = create.create_object(ShipRoom, key="Another Cabin")
        other.vessel = self.hull
        self.passenger.location = other
        self.passenger.at_post_unpuppet()
        self.assertEqual(absent_from(self.cabin), ())

    def test_everyone_in_counts_both(self):
        aboard = create.create_object(
            "evennia.objects.objects.DefaultCharacter", key="Still Aboard"
        )
        aboard.location = self.cabin
        self.passenger.at_post_unpuppet()
        self.assertEqual(set(everyone_in(self.cabin)), {aboard, self.passenger})

    def test_a_gangway_is_not_a_passenger(self):
        exit_obj = create.create_object(
            "evennia.objects.objects.DefaultExit",
            key="gangway",
            location=self.cabin,
            destination=self.quay,
        )
        self.assertNotIn(exit_obj, everyone_in(self.cabin))

    def test_the_ships_company_includes_the_offline(self):
        """What has to be resolved before she is ever broken up."""
        self.passenger.at_post_unpuppet()
        self.assertIn(self.passenger, self.hull.ships_company())

    def test_and_walking_her_rooms_alone_would_miss_them(self):
        """The pair to the test above, and the reason `ships_company` exists."""
        self.passenger.at_post_unpuppet()
        by_contents = [obj for room in self.hull.ship_rooms for obj in room.contents]
        self.assertNotIn(self.passenger, by_contents)
