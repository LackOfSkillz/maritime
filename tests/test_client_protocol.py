"""
Tests for the optional client protocol.

The acceptance test for this phase is one sentence: ashore the interface is none, aboard it
is the maritime one, and ashore again it is none. Everything else here exists to keep that
true when somebody is a passenger, in the water, on two connections, or on a terminal that
never asked for any of it.

Nothing in this file draws anything. That is the point of doing the protocol first.

"""

from evennia.server.signals import SIGNAL_OBJECT_POST_PUPPET
from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest, BaseEvenniaTestCase

from ..client import boundary
from ..client import (
    COMMAND,
    announce,
    CONTEXTS,
    MODE,
    NONE,
    PASSENGER,
    PROTOCOL_VERSION,
    SYNC,
    WATER,
    Mode,
    Sync,
    hello,
    mode_for,
    refresh,
    refresh_for,
    resolve_maritime_ui_context,
    sync_for,
    understands,
)
from ..position import WorldPosition
from ..projection import OceanProjection
from ..rooms import ShipRoom
from ..typeclasses import Flotsam, Vessel
from ..vessel import OPEN
from .base import EmptySeaMixin

HERE = WorldPosition(120.0, 340.0)


class FakeNdb:
    """Somewhere to hang session state, as Evennia's `.ndb` does."""

    def __getattr__(self, name):
        return None


class FakeSession:
    """
    A connection, without a network.

    Notes:
        The transport only ever asks a session three things - what it can draw, who
        it is puppeting, and to send something - so a stand-in that answers those is
        a truthful test double rather than a convenient one.

    """

    def __init__(self, puppet=None):
        self.puppet = puppet
        self.ndb = FakeNdb()
        self.sent = []

    def msg(self, **kwargs):
        self.sent.append(kwargs)

    def kinds(self):
        """
        Returns:
            kinds (list): The command names sent so far.

        """
        return [name for message in self.sent for name in message]

    def last(self, kind):
        """
        Returns:
            payload (dict or None): The keyword payload of the last message of
                that kind.

        """
        for message in reversed(self.sent):
            if kind in message:
                return message[kind][1]
        return None


class Watching:
    """
    Somebody standing somewhere, with connections.

    Notes:
        `refresh_for` asks a character for exactly two things - where they are and
        what is connected to them - so a stand-in that answers both is enough to
        test it with, and avoids fighting Evennia's real session handler over
        sessions that are not real.

    """

    def __init__(self, location, sessions=None):
        self.location = location
        self.sessions = sessions


class FakeSessionHandler:
    """What `character.sessions` answers."""

    def __init__(self, *sessions):
        self._sessions = list(sessions)

    def all(self):
        return list(self._sessions)


class ClientTestCase(EmptySeaMixin, BaseEvenniaTest):
    """A ship at a quay, and somebody to walk aboard her."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Kestrel")
        self.hull.length, self.hull.beam = 18.0, 5.4
        self.hull.maritime_position = HERE
        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.deck.vessel = self.hull
        self.deck.exposure = OPEN
        self.quay = self.room1

    def aboard(self):
        """Put the test character on the deck."""
        self.char1.location = self.deck

    def ashore(self):
        """Put the test character back on land."""
        self.char1.location = self.quay


class TestWhatSituationSomebodyIsIn(ClientTestCase):
    """The resolver, which everything else asks."""

    def test_ashore_is_none(self):
        self.ashore()
        self.assertEqual(resolve_maritime_ui_context(self.char1), NONE)

    def test_aboard_a_ship_you_command_is_command(self):
        self.aboard()
        self.assertEqual(resolve_maritime_ui_context(self.char1), COMMAND)

    def test_aboard_a_ship_you_do_not_command_is_passenger(self):
        """
        Somebody else's ship, with a captain already in her. A passenger may look
        at the weather and the chart, because both are visible from a deck to
        anybody standing on it - and may not touch the helm.

        """
        self.hull.captain = self.char2
        self.aboard()
        self.assertEqual(resolve_maritime_ui_context(self.char1), PASSENGER)

    def test_in_the_water_is_water(self):
        sea = OceanProjection()
        swimmer = create.create_object(Flotsam, key="a swimmer")
        room = sea.overboard(swimmer, HERE)
        self.char1.location = room
        self.assertEqual(resolve_maritime_ui_context(self.char1), WATER)

    def test_nobody_at_all_is_none(self):
        """Total by construction. There is no situation this cannot answer."""
        self.assertEqual(resolve_maritime_ui_context(None), NONE)

    def test_it_only_ever_answers_something_it_declares(self):
        self.aboard()
        self.assertIn(resolve_maritime_ui_context(self.char1), CONTEXTS)

    def test_it_can_be_asked_about_a_room_somebody_is_not_in_yet(self):
        """
        The question at the moment somebody steps through a door: not where are
        they, but where are they going.

        """
        self.ashore()
        self.assertEqual(resolve_maritime_ui_context(self.char1, self.deck), COMMAND)
        self.assertEqual(resolve_maritime_ui_context(self.char1, self.quay), NONE)

    def test_asking_about_a_room_does_not_move_anybody(self):
        self.ashore()
        resolve_maritime_ui_context(self.char1, self.deck)
        self.assertIs(self.char1.location, self.quay)


class TestWhatGoesOnTheWire(BaseEvenniaTestCase):
    """Payloads are data and nothing else."""

    def test_every_message_carries_its_version(self):
        self.assertEqual(Mode().as_message()["version"], PROTOCOL_VERSION)
        self.assertEqual(Sync().as_message()["version"], PROTOCOL_VERSION)

    def test_a_mode_names_itself(self):
        self.assertEqual(Mode().kind, MODE)

    def test_a_sync_names_itself(self):
        self.assertEqual(Sync().kind, SYNC)

    def test_a_sync_carries_its_mode_whole(self):
        inside = Mode(mode=COMMAND, vessel_id="v7")
        self.assertEqual(Sync(mode=inside).as_message()["mode"], inside.as_message())

    def test_capabilities_travel_as_a_list(self):
        """A tuple is not JSON. This is the sort of thing that only fails on a wire."""
        message = Sync(capabilities=("mode", "chart")).as_message()
        self.assertIsInstance(message["capabilities"], list)

    def test_payloads_compare_by_value(self):
        """Which is what lets the transport tell "changed" from "the same again"."""
        self.assertEqual(Mode(mode=COMMAND, vessel_id="v7"), Mode(mode=COMMAND, vessel_id="v7"))
        self.assertNotEqual(Mode(mode=COMMAND, vessel_id="v7"), Mode(mode=COMMAND, vessel_id="v8"))


class TestBuildingTheSnapshot(ClientTestCase):
    """What a character's situation turns into."""

    def test_ashore_names_no_vessel(self):
        self.ashore()
        mode = mode_for(self.char1)
        self.assertEqual(mode.mode, NONE)
        self.assertIsNone(mode.vessel_id)

    def test_aboard_names_the_hull(self):
        self.aboard()
        self.assertEqual(mode_for(self.char1).vessel_id, f"v{self.hull.id}")

    def test_the_handle_is_not_the_name(self):
        """
        A client that has been shown two ships needs to tell them apart, and a game
        may well let a captain rename his.

        """
        self.aboard()
        handle = mode_for(self.char1).vessel_id
        self.hull.key = "Renamed"
        self.assertEqual(mode_for(self.char1).vessel_id, handle)

    def test_a_sync_carries_the_mode_and_the_capabilities(self):
        self.aboard()
        snapshot = sync_for(self.char1, ("mode", "chart"))
        self.assertEqual(snapshot.mode.mode, COMMAND)
        self.assertEqual(snapshot.capabilities, ("mode", "chart"))


class TestTellingASession(ClientTestCase):
    """The transport, and its refusal to talk to clients that did not ask."""

    def test_a_session_that_never_announced_itself_hears_nothing(self):
        """
        It may be a terminal, and a terminal sent an unknown command name is
        entitled to print it at the player.

        """
        session = FakeSession(puppet=self.char1)
        self.aboard()
        self.assertFalse(refresh(session))
        self.assertEqual(session.sent, [])

    def test_announcing_itself_gets_a_full_snapshot_back(self):
        session = FakeSession(puppet=self.char1)
        self.aboard()
        self.assertTrue(hello(session))
        self.assertIn(SYNC, session.kinds())

    def test_and_the_snapshot_says_where_they_are(self):
        session = FakeSession(puppet=self.char1)
        self.aboard()
        hello(session)
        self.assertEqual(session.last(SYNC)["mode"]["mode"], COMMAND)

    def test_capability_is_remembered_on_the_session(self):
        session = FakeSession(puppet=self.char1)
        hello(session, capabilities=("mode", "chart"))
        self.assertTrue(understands(session))
        self.assertEqual(session.ndb.maritime_capabilities, ("mode", "chart"))

    def test_a_capability_the_server_does_not_know_is_dropped_not_refused(self):
        """An older server meeting a newer client should degrade, not argue."""
        session = FakeSession(puppet=self.char1)
        hello(session, capabilities=("mode", "holograms"))
        self.assertEqual(session.ndb.maritime_capabilities, ("mode",))

    def test_a_client_that_can_draw_nothing_still_gets_the_mode(self):
        session = FakeSession(puppet=self.char1)
        hello(session, capabilities=())
        self.assertEqual(session.ndb.maritime_capabilities, ("mode",))

    def test_a_version_from_the_future_is_accepted(self):
        """
        Refusing would leave a client one version ahead with no interface at all,
        when almost everything would have worked.

        """
        session = FakeSession(puppet=self.char1)
        self.assertTrue(hello(session, protocol_version=PROTOCOL_VERSION + 1))


class TestTheGuardsEachHoldOnTheirOwn(ClientTestCase):
    """
    Two public functions that must refuse on their own account.

    Both are normally reached through a caller that has already checked, which is
    exactly why they need testing directly: the day somebody calls one of them from
    somewhere new, the check has to be in the function rather than in the habit of
    its usual caller.

    """

    def test_announce_refuses_a_session_that_never_asked(self):
        """
        Reached through `refresh`, which checks first - so nothing catches it if
        this guard goes, and a terminal starts being sent JSON.

        """
        session = FakeSession(puppet=self.char1)
        self.aboard()
        self.assertFalse(announce(session, mode_for(self.char1)))
        self.assertEqual(session.sent, [])

    def test_and_sends_to_one_that_did(self):
        session = FakeSession(puppet=self.char1)
        hello(session)
        session.sent.clear()
        self.aboard()
        self.assertTrue(announce(session, mode_for(self.char1)))

    def test_notice_swallows_whatever_the_client_layer_does(self):
        """
        Tested on `notice` rather than by walking, because Evennia may well catch a
        raising hook itself - in which case walking would pass with no guard at all
        and prove nothing about this one.

        """
        original = boundary.transport.refresh_for

        def explode(*args, **kwargs):
            raise RuntimeError("the panel is on fire")

        boundary.transport.refresh_for = explode
        self.addCleanup(setattr, boundary.transport, "refresh_for", original)

        boundary.notice(self.char1)

    def test_but_it_does_pass_the_call_through(self):
        """Guards the test above: swallowing everything would also pass it."""
        seen = []
        original = boundary.transport.refresh_for
        boundary.transport.refresh_for = lambda moved, room=None: seen.append(moved)
        self.addCleanup(setattr, boundary.transport, "refresh_for", original)

        boundary.notice(self.char1)
        self.assertEqual(seen, [self.char1])


class TestSayingItOnlyWhenItChanges(ClientTestCase):
    """A gangway is crossed rarely. Nothing should be said on the ticks between."""

    def setUp(self):
        super().setUp()
        self.client = FakeSession(puppet=self.char1)
        self.ashore()
        hello(self.client)
        self.client.sent.clear()

    def test_standing_still_says_nothing(self):
        self.assertFalse(refresh(self.client))
        self.assertEqual(self.client.sent, [])

    def test_going_aboard_says_so(self):
        self.aboard()
        self.assertTrue(refresh(self.client))
        self.assertEqual(self.client.last(MODE)["mode"], COMMAND)

    def test_and_says_it_once(self):
        self.aboard()
        refresh(self.client)
        self.client.sent.clear()
        self.assertFalse(refresh(self.client))

    def test_going_ashore_says_so_too(self):
        self.aboard()
        refresh(self.client)
        self.ashore()
        self.assertTrue(refresh(self.client))
        self.assertEqual(self.client.last(MODE)["mode"], NONE)

    def test_moving_between_two_rooms_of_one_ship_says_nothing(self):
        """Deck to hold is two rooms and one situation."""
        hold = create.create_object(ShipRoom, key="Hold")
        hold.vessel = self.hull
        self.aboard()
        refresh(self.client)
        self.client.sent.clear()

        self.char1.location = hold
        self.assertFalse(refresh(self.client))


class TestEverySessionIsTold(ClientTestCase):
    """A player may be watching from more than one place."""

    def test_both_connections_hear_about_it(self):
        self.aboard()
        watcher = Watching(self.deck)
        first, second = FakeSession(watcher), FakeSession(watcher)
        watcher.sessions = FakeSessionHandler(first, second)
        hello(first)
        hello(second)
        for session in (first, second):
            session.ndb.maritime_mode = None

        self.assertEqual(refresh_for(watcher), 2)

    def test_a_terminal_alongside_a_browser_is_left_alone(self):
        """
        Capability is a fact about a connection, not about a character. The one
        that never asked hears nothing while the other is told everything.

        """
        self.aboard()
        watcher = Watching(self.deck)
        browser, terminal = FakeSession(watcher), FakeSession(watcher)
        watcher.sessions = FakeSessionHandler(browser, terminal)
        hello(browser)
        browser.ndb.maritime_mode = None

        self.assertEqual(refresh_for(watcher), 1)
        self.assertEqual(terminal.sent, [])

    def test_nobody_at_all_is_not_an_error(self):
        self.assertEqual(refresh_for(None), 0)


class TestCrossingTheWaterline(ClientTestCase):
    """
    The acceptance test for this phase: ashore is none, aboard is the maritime
    interface, ashore again is none.

    Driven by walking, through the real room hooks and the real resolver. Only the
    delivery to a session is stood in for, because delivery is tested above and
    Evennia's own session handler is not a thing to fight in a test about doors.

    Nothing in a host game was changed to make this work. Both sides of the crossing
    are rooms this contrib owns, which is why there is no integration step for a
    game to forget.

    """

    def setUp(self):
        super().setUp()
        self.seen = []
        original = boundary.transport.refresh_for

        def spy(moved, room=None):
            if moved is self.char1:
                self.seen.append(mode_for(moved, room).mode)
            return 0

        boundary.transport.refresh_for = spy
        self.addCleanup(setattr, boundary.transport, "refresh_for", original)
        self.ashore()
        self.seen.clear()

    def test_walking_aboard_and_ashore_again(self):
        self.char1.move_to(self.deck, quiet=True)
        self.char1.move_to(self.quay, quiet=True)
        self.assertEqual(self.seen, [COMMAND, NONE])

    def test_the_interface_is_put_away_on_the_way_out(self):
        """
        Announced as they leave rather than on arrival ashore, because the room
        being left is ours and the room being entered may be anybody's.

        """
        self.char1.move_to(self.deck, quiet=True)
        self.seen.clear()
        self.char1.move_to(self.quay, quiet=True)
        self.assertEqual(self.seen, [NONE])

    def test_moving_within_one_ship_never_says_command_twice_over(self):
        """
        Deck to hold fires the hooks, and both ends resolve to the same situation,
        so the transport has nothing to send. The hook firing is not the same as
        the player being told.

        """
        hold = create.create_object(ShipRoom, key="Hold")
        hold.vessel = self.hull
        self.char1.move_to(self.deck, quiet=True)
        self.seen.clear()
        self.char1.move_to(hold, quiet=True)
        self.assertEqual(set(self.seen), {COMMAND})

    def test_going_over_the_side_is_noticed(self):
        """
        The projection moves swimmers with the hooks off, deliberately, so this
        would go unannounced if `overboard` did not say so itself - and going into
        the sea changes a player's situation about as much as it can be changed.

        """
        sea = OceanProjection()
        self.char1.move_to(self.deck, quiet=True)
        self.seen.clear()
        sea.overboard(self.char1, HERE)
        self.assertIn(WATER, self.seen)

    def test_and_so_is_being_pulled_out_again(self):
        sea = OceanProjection()
        sea.overboard(self.char1, HERE)
        self.seen.clear()
        sea.recover(self.char1, self.deck)
        self.assertIn(COMMAND, self.seen)


class TestTakingControlOfACharacter(ClientTestCase):
    """
    Logging in aboard your own ship is arriving without having moved.

    No room hook can see it - nobody went through a door - so a player who
    connected while standing on their own quarterdeck saw no interface at all until
    they happened to walk somewhere. Found by connecting to a running testbed and
    watching nothing happen, which is the only way it could have been found.

    """

    def test_a_session_that_has_announced_itself_is_told_on_puppeting(self):
        session = FakeSession(puppet=self.char1)
        self.aboard()
        hello(session)
        session.sent.clear()
        session.ndb.maritime_mode = None

        SIGNAL_OBJECT_POST_PUPPET.send(sender=self.char1, session=session, account=None)
        self.assertEqual(session.last(SYNC)["mode"]["mode"], COMMAND)

    def test_and_told_even_though_nothing_changed_since_the_handshake(self):
        """
        Forced rather than compared. A session that has just taken a character has
        been told nothing yet, and "the same as last time" is the wrong answer when
        there was no last time.

        """
        session = FakeSession(puppet=self.char1)
        self.aboard()
        hello(session)
        session.sent.clear()

        SIGNAL_OBJECT_POST_PUPPET.send(sender=self.char1, session=session, account=None)
        self.assertTrue(session.sent)

    def test_a_session_that_never_announced_itself_is_still_left_alone(self):
        """A terminal logging in is a terminal, and gets no JSON for its trouble."""
        session = FakeSession(puppet=self.char1)
        self.aboard()

        SIGNAL_OBJECT_POST_PUPPET.send(sender=self.char1, session=session, account=None)
        self.assertEqual(session.sent, [])

    def test_a_failure_never_stops_somebody_logging_in(self):
        original = boundary.transport.refresh
        boundary.transport.refresh = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no"))
        self.addCleanup(setattr, boundary.transport, "refresh", original)

        SIGNAL_OBJECT_POST_PUPPET.send(sender=self.char1, session=FakeSession(), account=None)


class TestABrokenInterfaceNeverTrapsAnybody(ClientTestCase):
    """The worst a failed client layer may do is leave a stale panel."""

    def test_a_player_still_walks(self):
        original = boundary.transport.refresh_for

        def explode(*args, **kwargs):
            raise RuntimeError("the panel is on fire")

        boundary.transport.refresh_for = explode
        self.addCleanup(setattr, boundary.transport, "refresh_for", original)

        self.ashore()
        self.char1.move_to(self.deck, quiet=True)
        self.assertIs(self.char1.location, self.deck)
