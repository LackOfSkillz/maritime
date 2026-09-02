"""
Tests for the optional client protocol.

The acceptance test for this phase is one sentence: ashore the interface is none, aboard it
is the maritime one, and ashore again it is none. Everything else here exists to keep that
true when somebody is a passenger, in the water, on two connections, or on a terminal that
never asked for any of it.

Nothing in this file draws anything. That is the point of doing the protocol first.

"""

from django.test import override_settings
from evennia.server.signals import SIGNAL_OBJECT_POST_PUPPET
from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest, BaseEvenniaTestCase

from .. import config
from ..charts import Chart
from ..client import (
    COMMAND,
    CONTEXTS,
    MODE,
    NONE,
    PASSENGER,
    PROTOCOL_VERSION,
    SYNC,
    WATER,
    Mode,
    Sync,
    announce,
    boundary,
    hello,
    mode_for,
    refresh,
    refresh_for,
    resolve_maritime_ui_context,
    sync_for,
    transport,
    understands,
)
from ..client.state import CHART_REVISION_SECONDS
from ..position import WorldPosition
from ..projection import OceanProjection
from ..rooms import PortRoom, ShipRoom
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


class _Clock:
    """A time provider the tests wind by hand, so a revision turns when they say."""

    def __init__(self, at=0.0):
        self.at = at

    def now(self):
        return self.at


class FakeSessionHandler:
    """What `character.sessions` answers."""

    def __init__(self, *sessions):
        self._sessions = list(sessions)

    def all(self):
        return list(self._sessions)


#: Pinned, because these test what the contrib does and not what one game asked for.
#:
#: `MARITIME_ASHORE_PANEL` decides what happens when somebody steps off a gangway, and the
#: contrib's own answer - the one documented and the one that ships - is that maritime gets
#: out of the way. A suite that read the setting from whatever game it happened to run
#: inside would assert that answer here and the opposite answer in a game that turned the
#: panel on, which is a suite that tests its host rather than its subject.
@override_settings(MARITIME_ASHORE_PANEL=False)
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


@override_settings(MARITIME_ASHORE_PANEL=True)
class TestTheMapFollowsTheWalkerAshore(ClientTestCase):
    """
    **The map is a picture of where you are standing.**

    So the one moment it certainly changes is the moment you stand somewhere else. A panel
    that is not told keeps a dot on a room the player has left, and that is not merely
    untidy: every click is routed from that dot, so the route begins in the wrong place and
    the walk sends the first turning of somebody else's journey. Ten rooms along it is
    sending `north` at a pier whose only exit is `shore`.

    Two halves, because the bug had two: a quay that told nobody it had been walked into,
    and a refresh that had nothing to say when the situation had not changed.
    """

    def setUp(self):
        super().setUp()
        self.maps = []
        original = transport.send_land

        def spy(session):
            self.maps.append(session)
            return True

        transport.send_land = spy
        self.addCleanup(setattr, transport, "send_land", original)

    def test_a_quay_says_so_when_somebody_walks_onto_it(self):
        """
        A quay is by definition the room on the landward side of a crossing, and it was the
        one room type in the contrib that fired no hook at all. A ship's rooms did, so
        walking ashore raised the panel - and then walking on to the quay next door left
        that map behind.

        """
        told = []
        original = boundary.transport.refresh_for
        boundary.transport.refresh_for = lambda moved, room=None: told.append(moved) or 0
        self.addCleanup(setattr, boundary.transport, "refresh_for", original)

        quay = create.create_object(PortRoom, key="A Quay")
        quay.at_object_receive(self.char1, self.quay)
        self.assertIn(self.char1, told, "walking onto a quay told nobody")

    def test_moving_ashore_sends_a_map_although_the_situation_is_unchanged(self):
        """
        A street and the quay at the end of it are both `ashore`, so there is no situation
        to announce and the refresh used to return having sent nothing. The map is the news.

        """
        session = FakeSession(puppet=self.char1)
        self.ashore()

        hello(session)
        self.assertTrue(self.maps, "the first sight of a town sent no map")

        self.maps.clear()
        self.assertFalse(
            refresh(session), "the situation is unchanged, so nothing should be announced"
        )
        self.assertTrue(self.maps, "moving ashore sent no map")

    def test_it_stays_quiet_for_somebody_at_sea(self):
        """The other half of the same branch: a deck gets its chart, not a town plan."""
        session = FakeSession(puppet=self.char1)
        self.aboard()

        hello(session)
        self.maps.clear()
        refresh(session)
        self.assertEqual(self.maps, [], "a land map was drawn for somebody at sea")


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


class TestThePaperIsDrawnOnlyWhenItChanges(ClientTestCase):
    """
    What it costs to say nothing, which is the expensive half of this layer.

    A sheet goes out once a revision. It used to be *drawn* on every tick and then
    compared, so twenty-nine drawings in thirty were thrown away - and the comment above
    the code said it did the opposite, which is how it survived. Against a hand-written
    seabed a sheet costs eighteen milliseconds and the waste was invisible; against a
    generated world one costs the better part of a second, and it is a third of a core per
    crewed vessel spent producing nothing.

    The session finder is stubbed here because it has its own tests and walking real rooms
    would only be testing those again. What these drive is the gate.

    The connection is `self.browser` and not `self.session`, which is the base class's own
    and which shadowing broke every teardown in this file - a name collision, on the day
    a name collision was being fixed elsewhere.
    """

    def setUp(self):
        super().setUp()
        self.aboard()
        self.browser = FakeSession(self.char1)
        hello(self.browser)
        self.browser.sent.clear()

        self.clock = _Clock()
        self.drawn = []

        real_chart_for = transport.chart_for

        def counted(vessel, reach, centre=(0.0, 0.0)):
            # Both, because a sheet is a scale *and* a place. Counting only the scale
            # would call two captains looking at opposite ends of the same coast one
            # drawing, which is the economy these tests exist to measure.
            self.drawn.append((reach, centre))
            return real_chart_for(vessel, reach, centre)

        for name, value in (
            ("chart_for", counted),
            ("_graphical_sessions_aboard", lambda vessel: [self.browser]),
        ):
            self.addCleanup(setattr, transport, name, getattr(transport, name))
            setattr(transport, name, value)

        real_time_provider = config.time_provider
        self.addCleanup(setattr, config, "time_provider", real_time_provider)
        config.time_provider = lambda: self.clock

    def tick(self, times=1):
        for _ in range(times):
            transport.broadcast_status(self.hull)

    def test_a_ship_at_anchor_is_drawn_once(self):
        self.tick(30)
        self.assertEqual(len(self.drawn), 1, f"drew {len(self.drawn)} sheets for one")

    def test_and_drawn_again_when_the_revision_turns(self):
        self.tick()
        self.clock.at += CHART_REVISION_SECONDS
        self.tick()
        self.assertEqual(len(self.drawn), 2)

    def test_thirty_ticks_of_a_two_second_simulation_is_one_drawing(self):
        """
        The arithmetic that makes this worth doing. A revision is a minute; the driver
        ticks every two seconds.

        """
        for _ in range(30):
            self.tick()
            self.clock.at += 2.0
        self.assertEqual(len(self.drawn), 1)

    def test_a_chart_found_mid_minute_is_not_held_back(self):
        """
        The regression the revision gate would have introduced on its own. Gating on
        time alone would leave a chart bought or unrolled halfway through a minute
        invisible until the minute turned, and the code being replaced noticed at once
        because it redrew everything every tick. Losing that would be paying for the
        saving with a worse interface.

        """
        self.tick()
        self.assertEqual(len(self.drawn), 1)

        self.hull.add_chart(Chart(key="approaches", west=-9e4, east=9e4, south=-9e4, north=9e4))
        self.tick()
        self.assertEqual(len(self.drawn), 2, "a new chart waited for the clock")

    def test_two_scales_are_two_drawings_and_no_more(self):
        watcher = FakeSession(self.char1)
        hello(watcher)
        watcher.ndb.maritime_reach = 4000.0
        self.browser.ndb.maritime_reach = 20000.0
        transport._graphical_sessions_aboard = lambda vessel: [self.browser, watcher]

        self.tick(10)
        self.assertEqual(sorted(self.drawn), [(4000.0, (0.0, 0.0)), (20000.0, (0.0, 0.0))])

    def test_everybody_at_one_scale_contours_once(self):
        watcher = FakeSession(self.char1)
        hello(watcher)
        for session in (self.browser, watcher):
            session.ndb.maritime_reach = 8000.0
        transport._graphical_sessions_aboard = lambda vessel: [self.browser, watcher]

        self.tick(10)
        self.assertEqual(self.drawn, [(8000.0, (0.0, 0.0))])

    def test_both_of_them_are_still_sent_it(self):
        watcher = FakeSession(self.char1)
        hello(watcher)
        for session in (self.browser, watcher):
            session.ndb.maritime_reach = 8000.0
            session.sent.clear()
        transport._graphical_sessions_aboard = lambda vessel: [self.browser, watcher]

        self.tick()
        for session in (self.browser, watcher):
            self.assertIn("maritime_chart", session.kinds())

    def test_a_zoom_stamps_it_the_way_a_tick_would(self):
        """
        Two places write that stamp. If they disagreed the tick after a zoom would
        redraw what the zoom had just sent, which is the waste this whole change is
        about, arriving by a different door.

        """
        self.tick()
        self.drawn.clear()
        transport.redraw_chart(self.browser)
        self.assertEqual(len(self.drawn), 1)

        self.drawn.clear()
        self.tick(5)
        self.assertEqual(self.drawn, [])


class TestDraggingAsksForSomewhereElse(ClientTestCase):
    """
    The round trip a drag makes, driven through the input function the browser calls.

    Dragging was broken twice over and the second one is the reason this exists. The first
    time, the request carried no place, so the server always drew around the ship. That was
    fixed - and dragging still did nothing, because nothing *sent* a request when the drag
    ended. The offset was plumbed the whole way through and never travelled.

    So this test does not check that a sheet can be drawn somewhere else. It checks that
    asking for one, the way the client asks, delivers one.
    """

    def setUp(self):
        super().setUp()
        self.aboard()
        self.hull.add_chart(Chart(key="the approaches", west=-9e4, east=9e4, south=-9e4, north=9e4))
        self.browser = FakeSession(self.char1)
        hello(self.browser)
        self.browser.sent.clear()

    def ask(self, **kwargs):
        """
        Returns:
            sheet (dict or None): What the client would have received, or None if the
                request produced no sheet at all.

        """
        from ..client.inputfuncs import maritime_view

        self.browser.sent.clear()
        maritime_view(self.browser, reach=4000.0, **kwargs)
        return self.browser.last("maritime_chart")

    def test_asking_without_an_offset_puts_her_in_the_middle(self):
        drawn = self.ask()
        self.assertIsNotNone(drawn, "no sheet was sent at all")
        self.assertEqual([abs(part) for part in drawn["own"]], [0.0, 0.0])

    def test_asking_with_one_moves_the_sheet_and_says_where_she_is(self):
        drawn = self.ask(east=3000.0, north=-1500.0)
        self.assertIsNotNone(drawn, "a drag produced no sheet")
        self.assertEqual(drawn["own"], [-3000.0, 1500.0])

    def test_and_the_ground_under_it_is_different_ground(self):
        """
        The bug in one assertion. If a drag still only slid the picture, these would be
        the same sheet with the ship drawn somewhere else on it.

        """
        here = self.ask()
        away = self.ask(east=70000.0, north=70000.0)
        self.assertNotEqual(here["soundings"], away["soundings"])

    def test_dragging_back_gives_the_first_sheet_again(self):
        first = self.ask()
        self.ask(east=70000.0, north=70000.0)
        again = self.ask()
        self.assertEqual(first["soundings"], again["soundings"])
        self.assertEqual(first["coastline"], again["coastline"])

    def test_a_drag_is_not_suppressed_as_an_unchanged_view(self):
        """
        The redraw stamp exists so a ship at anchor is not drawn thirty times a minute.
        Blind to *where* the sheet is, it would swallow every drag: same reach, same
        revision, same chart, therefore nothing to send.

        """
        self.assertIsNotNone(self.ask(east=5000.0), "the first drag was suppressed")
        self.assertIsNotNone(self.ask(east=9000.0), "a second drag was suppressed")


class TestComingBackAboard(ClientTestCase):
    """
    **A change of mode rebuilds the client's panels, so the server must stop believing
    the client still holds what it was last sent.**

    Seen in play: a captain went ashore, came back to his ship, and the board reported
    "awaiting report" with every reading blank while the chart drew perfectly. The mode
    had switched, the panels had been rebuilt empty, and the next tick compared her
    instruments against what the *old* panels had been holding, found them identical,
    and sent nothing. A ship lying quiet produces the same numbers for hours, so nothing
    was ever going to shift and the board was never going to fill in.

    It is not a teleport bug. Walking back up the gangway does exactly the same thing.

    """

    def a_listening_session(self):
        """A session that has announced itself and can draw everything."""
        session = FakeSession(puppet=self.char1)
        hello(session)
        return session

    def test_the_reading_it_was_holding_is_forgotten(self):
        self.aboard()
        session = self.a_listening_session()
        session.ndb.maritime_status = {"a reading": "already on screen"}

        self.ashore()
        refresh(session)
        self.aboard()
        refresh(session)

        self.assertIsNone(session.ndb.maritime_status)

    def test_and_so_is_the_sheet(self):
        """Same argument, same cache, same silence if it is left standing."""
        self.aboard()
        session = self.a_listening_session()
        session.ndb.maritime_chart_stamp = ("a sheet", "already on screen")

        self.ashore()
        refresh(session)
        self.aboard()
        refresh(session)

        self.assertIsNone(session.ndb.maritime_chart_stamp)

    def test_going_the_other_way_forgets_them_too(self):
        """Stepping ashore rebuilds the panels just as thoroughly."""
        self.aboard()
        session = self.a_listening_session()
        session.ndb.maritime_status = {"a reading": "already on screen"}

        self.ashore()
        refresh(session)

        self.assertIsNone(session.ndb.maritime_status)

    def test_but_walking_about_aboard_keeps_them(self):
        """
        A mover who has not changed mode still has her panels in front of her, and
        clearing these would redraw the board on every step along a deck - which would
        steal focus from somebody trying to read it.

        """
        self.aboard()
        session = self.a_listening_session()
        held = {"a reading": "already on screen"}
        session.ndb.maritime_status = held

        refresh(session)

        self.assertEqual(session.ndb.maritime_status, held)
