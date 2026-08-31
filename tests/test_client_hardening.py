"""
Tests for the client layer under conditions nobody arranged.

A reconnect mid-voyage, a character let go, a ship destroyed underneath a session, a
protocol from the future. None of these are the happy path and all of them happen, and
the rule for every one is the same: the interface may go blank, and the simulation may
not notice.

"""

from evennia.server.signals import SIGNAL_OBJECT_POST_UNPUPPET
from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest

from ..client import boundary, hello, mode_for, refresh, understands
from ..client.payloads import MODE, PROTOCOL_VERSION, SYNC
from ..client.state import chart_for, contacts_for, status_for
from ..motion import MotionLimits
from ..position import WorldPosition
from ..rooms import ShipRoom
from ..sailing import FULL
from ..typeclasses import Vessel
from ..vessel import OPEN
from .base import EmptySeaMixin
from .test_client_protocol import FakeSession

HERE = WorldPosition(0.0, 0.0)


class HardeningTestCase(EmptySeaMixin, BaseEvenniaTest):
    """A ship, a deck, and a connection that is about to have a bad day."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="HMS Aetos Folly")
        self.hull.length, self.hull.beam = 18.0, 5.4
        self.hull.motion_limits = MotionLimits(max_speed=8.0, acceleration=0.5, turn_rate=5.0)
        self.hull.maritime_position = HERE
        self.hull.sail_plan = FULL
        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.deck.vessel = self.hull
        self.deck.exposure = OPEN
        self.char1.location = self.deck


class TestComingBackAfterADisconnection(HardeningTestCase):
    """
    Reconnection is not a special case, and that is the design.

    A client that has just come back says exactly what a client arriving for the
    first time says, and gets the same full snapshot. There is no resynchronisation
    path to get wrong, because there is no resynchronisation path.

    """

    def test_a_returning_client_gets_a_complete_picture(self):
        session = FakeSession(puppet=self.char1)
        hello(session)
        self.assertIn(SYNC, session.kinds())

    def test_and_it_says_where_she_is_now_rather_than_where_she_was(self):
        session = FakeSession(puppet=self.char1)
        hello(session)
        session.sent.clear()

        ashore = self.room1
        self.char1.location = ashore
        hello(session)
        self.assertEqual(session.last(SYNC)["mode"]["mode"], "none")

    def test_capability_does_not_survive_the_connection(self):
        """
        Held on `.ndb`, which empties on a reload - correctly. A browser that has
        gone away has no capability, and the one that comes back announces itself
        again.

        """
        session = FakeSession(puppet=self.char1)
        hello(session)
        self.assertTrue(understands(session))

        session.ndb.maritime_capabilities = None
        self.assertFalse(understands(session))


class TestLettingGoOfACharacter(HardeningTestCase):
    """The interface goes with them."""

    def test_the_session_is_told_it_is_ashore(self):
        session = FakeSession(puppet=self.char1)
        hello(session)
        session.sent.clear()

        SIGNAL_OBJECT_POST_UNPUPPET.send(sender=self.char1, session=session, account=None)
        self.assertEqual(session.last(MODE)["mode"], "none")

    def test_and_forgets_what_it_was_showing(self):
        """
        Otherwise the next character it takes up inherits a ship, and may be
        standing in a field.

        """
        session = FakeSession(puppet=self.char1)
        hello(session)
        SIGNAL_OBJECT_POST_UNPUPPET.send(sender=self.char1, session=session, account=None)
        self.assertIsNone(session.ndb.maritime_mode)

    def test_a_session_that_never_asked_is_still_left_alone(self):
        session = FakeSession(puppet=self.char1)
        SIGNAL_OBJECT_POST_UNPUPPET.send(sender=self.char1, session=session, account=None)
        self.assertEqual(session.sent, [])

    def test_a_signal_with_no_session_is_not_an_error(self):
        SIGNAL_OBJECT_POST_UNPUPPET.send(sender=self.char1, session=None, account=None)


class TestAShipThatStopsExisting(HardeningTestCase):
    """A hull can be destroyed while somebody is standing on her deck."""

    def test_a_hull_never_launched_reports_no_instruments(self):
        """
        On the stocks rather than destroyed, but the same shape of answer: a hull
        with no position has nothing an instrument could read, and the honest reply
        is nothing rather than a board full of zeroes.

        """
        on_the_stocks = create.create_object(Vessel, key="Unnamed")
        self.assertIsNone(status_for(on_the_stocks))

    def test_her_chart_is_empty_rather_than_absent(self):
        sheet = chart_for(self.hull).as_message()
        self.assertEqual(sheet["coastline"], [])

    def test_a_hull_of_none_is_handled_everywhere(self):
        """
        Evennia hands back None for a deleted reference, so every builder gets one
        eventually. None of them may raise.

        """
        self.assertIsNone(status_for(None))
        self.assertEqual(contacts_for(None).as_message()["contacts"], [])
        self.assertEqual(chart_for(None).as_message()["coastline"], [])

    def test_a_session_aboard_a_hull_that_answers_nothing_is_not_an_error(self):
        session = FakeSession(puppet=self.char1)
        hello(session)
        self.deck.vessel = create.create_object(Vessel, key="Unnamed")
        refresh(session, force=True)


class TestAProtocolFromTheFuture(HardeningTestCase):
    """A client one version ahead should lose a field, not an interface."""

    def test_a_newer_client_is_accepted(self):
        session = FakeSession(puppet=self.char1)
        self.assertTrue(hello(session, protocol_version=PROTOCOL_VERSION + 5))

    def test_and_told_what_this_server_speaks(self):
        session = FakeSession(puppet=self.char1)
        hello(session, protocol_version=PROTOCOL_VERSION + 5)
        self.assertEqual(session.last(SYNC)["version"], PROTOCOL_VERSION)

    def test_a_version_that_is_not_a_number_is_survived(self):
        from ..client import inputfuncs

        session = FakeSession(puppet=self.char1)
        inputfuncs.maritime_hello(session, protocol_version="the latest one")
        self.assertTrue(understands(session))

    def test_capabilities_that_are_not_a_list_are_survived(self):
        from ..client import inputfuncs

        session = FakeSession(puppet=self.char1)
        inputfuncs.maritime_hello(session, capabilities="chart")
        self.assertTrue(understands(session))


class TestNonsenseFromABrowser(HardeningTestCase):
    """Everything arriving from a client is untrusted, including its shape."""

    def setUp(self):
        super().setUp()
        from ..client import inputfuncs

        self.inputfuncs = inputfuncs
        self.client = FakeSession(puppet=self.char1)
        hello(self.client)

    def test_a_view_of_nonsense_is_ignored(self):
        for rubbish in ("wide", None, {}, [50]):
            self.inputfuncs.maritime_view(self.client, reach=rubbish)

    def test_an_absurd_view_is_clamped_rather_than_obeyed(self):
        """
        A browser asking for a thousand leagues is asking the server to contour half
        the world on its behalf.

        """
        from ..client.transport import MAX_REACH

        self.inputfuncs.maritime_view(self.client, reach=10_000_000.0)
        self.assertLessEqual(self.client.ndb.maritime_reach, MAX_REACH)

    def test_and_a_tiny_one_is_too(self):
        from ..client.transport import MIN_REACH

        self.inputfuncs.maritime_view(self.client, reach=0.001)
        self.assertGreaterEqual(self.client.ndb.maritime_reach, MIN_REACH)

    def test_an_action_of_nonsense_runs_nothing(self):
        ran = []
        self.char1.execute_cmd = lambda line, **kwargs: ran.append(line)
        for rubbish in (None, 42, {"nested": True}, "scuttle"):
            self.inputfuncs.maritime_action(self.client, action=rubbish)
        self.assertEqual(ran, [])


class TestNothingHereStopsTheShip(HardeningTestCase):
    """The simulation carries on whatever the interface does."""

    def test_a_tick_survives_a_broken_client_layer(self):
        from django.test import override_settings

        from ..client import transport

        original = transport.broadcast_status
        transport.broadcast_status = lambda vessel: (_ for _ in ()).throw(RuntimeError("no"))
        self.addCleanup(setattr, transport, "broadcast_status", original)

        with override_settings(MARITIME_WIND_BEARING=180.0, MARITIME_WIND_SPEED=8.0):
            self.hull.at_maritime_tick(1.0)

    def test_and_a_player_can_still_walk(self):
        original = boundary.transport.refresh_for
        boundary.transport.refresh_for = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no"))
        self.addCleanup(setattr, boundary.transport, "refresh_for", original)

        self.char1.move_to(self.room1, quiet=True)
        self.assertIs(self.char1.location, self.room1)

    def test_and_the_mode_can_still_be_worked_out(self):
        """The resolver is the last thing standing; it must never depend on any of this."""
        self.assertIsNotNone(mode_for(self.char1))
