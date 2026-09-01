"""
Tests for the runtime switches and the commands that flip them.

"""

from django.test import override_settings
from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaCommandTest

from .. import charts, switches
from ..client import context
from ..commands.interface import (
    CmdMaritimePlayerGui,
    CmdMaritimeUi,
    CmdMaritimeUncharted,
    CmdMyGui,
    MaritimeInterfaceCmdSet,
)
from ..position import WorldPosition
from ..typeclasses import ShipRoom, Vessel
from .base import EmptySeaMixin


@override_settings(MARITIME_ASHORE_PANEL=False)
class SwitchTestCase(BaseEvenniaCommandTest):
    """
    A test that starts and ends with nothing set, on a game that hides the panel ashore.

    The setting is pinned because it decides what an untouched server does, and a test
    that read it from whatever game it happened to run inside would pass here and fail in
    CI - or worse, the other way round. `TestTheGamesOwnDefault` is where it is exercised
    in both positions, deliberately and in one place.

    Notes:
        The cache has to be dropped at both ends. Django rolls the config table back
        between tests but knows nothing about a dictionary in a module, so a value read in
        one test would otherwise be the answer in the next - which is exactly the failure
        the cache is capable of and therefore exactly what the tests must not hide.

    """

    def setUp(self):
        super().setUp()
        switches._forget()

    def tearDown(self):
        switches._forget()
        super().tearDown()


class TestDefaults(SwitchTestCase):
    """What an untouched server does."""

    def test_ui_mode_is_hybrid_by_default(self):
        self.assertEqual(switches.ui_mode(), switches.UI_HYBRID)

    def test_uncharted_is_off_by_default(self):
        self.assertFalse(switches.uncharted())

    def test_players_may_not_choose_by_default(self):
        self.assertFalse(switches.players_may_choose())

    def test_nobody_has_chosen_by_default(self):
        self.assertIsNone(switches.ui_choice(self.char1))


class TestPersistence(SwitchTestCase):
    """What is set stays set, and is read back."""

    def test_ui_mode_reads_back(self):
        switches.set_ui_mode(switches.UI_OFF)
        self.assertEqual(switches.ui_mode(), switches.UI_OFF)

    def test_ui_mode_survives_the_cache_being_dropped(self):
        switches.set_ui_mode(switches.UI_ON)
        switches._forget()
        self.assertEqual(switches.ui_mode(), switches.UI_ON)

    def test_uncharted_reads_back(self):
        switches.set_uncharted(True)
        switches._forget()
        self.assertTrue(switches.uncharted())

    def test_player_gui_reads_back(self):
        switches.set_players_may_choose(True)
        switches._forget()
        self.assertTrue(switches.players_may_choose())

    def test_an_unknown_mode_is_refused(self):
        with self.assertRaises(ValueError):
            switches.set_ui_mode("periscope")

    def test_a_nonsense_value_in_the_table_reads_as_the_default(self):
        # Written straight past the setter, as an older version or a game's own code
        # could have done. The interface has to come back rather than stay broken.
        switches._hold(switches.UI_KEY, "periscope")
        self.assertEqual(switches.ui_mode(), switches.UI_HYBRID)


class TestTheCacheIsReal(SwitchTestCase):
    """The database is asked once, not every time."""

    def test_a_second_read_does_not_query(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        switches.ui_mode()
        with CaptureQueriesContext(connection) as caught:
            for _ in range(20):
                switches.ui_mode()
        self.assertEqual(len(caught), 0)

    def test_a_first_read_does_query(self):
        # The other half of the measurement. Without this, a cache that returned a
        # hard-coded default and never touched the database at all would pass the test
        # above perfectly.
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as caught:
            switches.ui_mode()
        self.assertGreater(len(caught), 0)

    def test_setting_is_seen_at_once(self):
        switches.ui_mode()
        switches.set_ui_mode(switches.UI_OFF)
        self.assertEqual(switches.ui_mode(), switches.UI_OFF)


class TestOnePersonsChoice(SwitchTestCase):
    """What an account chose, and when it counts."""

    def test_a_choice_is_ignored_while_the_game_forbids_it(self):
        switches.set_ui_choice(self.char1, switches.UI_OFF)
        self.assertEqual(switches.ui_mode_for(self.char1), switches.UI_HYBRID)

    def test_a_choice_wins_once_the_game_allows_it(self):
        switches.set_players_may_choose(True)
        switches.set_ui_choice(self.char1, switches.UI_OFF)
        self.assertEqual(switches.ui_mode_for(self.char1), switches.UI_OFF)

    def test_forbidding_again_does_not_erase_it(self):
        switches.set_players_may_choose(True)
        switches.set_ui_choice(self.char1, switches.UI_OFF)
        switches.set_players_may_choose(False)
        self.assertEqual(switches.ui_mode_for(self.char1), switches.UI_HYBRID)
        switches.set_players_may_choose(True)
        self.assertEqual(switches.ui_mode_for(self.char1), switches.UI_OFF)

    def test_somebody_who_never_chose_gets_the_servers(self):
        switches.set_players_may_choose(True)
        switches.set_ui_mode(switches.UI_ON)
        self.assertEqual(switches.ui_mode_for(self.char1), switches.UI_ON)

    def test_the_choice_lives_on_the_account(self):
        switches.set_ui_choice(self.char1, switches.UI_ON)
        self.assertEqual(getattr(self.account.db, switches.MY_UI_ATTRIBUTE), switches.UI_ON)

    def test_clearing_goes_back_to_the_servers(self):
        switches.set_players_may_choose(True)
        switches.set_ui_choice(self.char1, switches.UI_OFF)
        switches.set_ui_choice(self.char1, None)
        self.assertEqual(switches.ui_mode_for(self.char1), switches.UI_HYBRID)

    def test_nonsense_on_the_account_reads_as_no_choice(self):
        # Written straight past the setter, as an older version could have left it. A
        # value nobody recognises must not silently take a player's panel away and leave
        # them with no obvious way to get it back.
        switches.set_players_may_choose(True)
        setattr(self.account.db, switches.MY_UI_ATTRIBUTE, "periscope")
        self.assertIsNone(switches.ui_choice(self.char1))
        self.assertEqual(switches.ui_mode_for(self.char1), switches.UI_HYBRID)

    def test_an_unknown_choice_is_refused(self):
        with self.assertRaises(ValueError):
            switches.set_ui_choice(self.char1, "periscope")

    def test_an_object_with_no_account_keeps_nothing(self):
        thing = create.create_object("evennia.objects.objects.DefaultObject", key="a crate")
        self.assertIsNone(switches.set_ui_choice(thing, switches.UI_ON))
        self.assertIsNone(switches.ui_choice(thing))

    def test_nobody_at_all_resolves_to_the_servers(self):
        switches.set_players_may_choose(True)
        self.assertEqual(switches.ui_mode_for(None), switches.UI_HYBRID)


class TestTheResolverAsksForThisPerson(EmptySeaMixin, SwitchTestCase):
    """The context a character gets follows their own mode when they have one."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Test Sloop")
        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.deck.vessel = self.hull
        self.hull.maritime_position = WorldPosition(0.0, 0.0)
        self.char1.location = self.deck
        # Both of them aboard, so that a difference between the two is a difference in
        # what they chose rather than a difference in where they are standing.
        self.char2.location = self.deck

    def test_aboard_is_a_ship_context_by_default(self):
        self.assertIn(
            context.resolve_maritime_ui_context(self.char1),
            (context.COMMAND, context.PASSENGER),
        )

    def test_the_server_switching_off_takes_the_panel_from_everybody(self):
        switches.set_ui_mode(switches.UI_OFF)
        self.assertEqual(context.resolve_maritime_ui_context(self.char1), context.NONE)

    def test_a_players_own_off_is_ignored_while_the_game_forbids_it(self):
        switches.set_ui_choice(self.char1, switches.UI_OFF)
        self.assertNotEqual(context.resolve_maritime_ui_context(self.char1), context.NONE)

    def test_a_players_own_off_takes_their_panel_when_allowed(self):
        switches.set_players_may_choose(True)
        switches.set_ui_choice(self.char1, switches.UI_OFF)
        self.assertEqual(context.resolve_maritime_ui_context(self.char1), context.NONE)

    def test_one_players_choice_leaves_everybody_else_alone(self):
        switches.set_players_may_choose(True)
        switches.set_ui_choice(self.char1, switches.UI_OFF)
        self.assertNotEqual(context.resolve_maritime_ui_context(self.char2), context.NONE)

    def test_on_puts_the_panel_ashore(self):
        switches.set_ui_mode(switches.UI_ON)
        self.char1.location = self.room1
        self.assertEqual(context.resolve_maritime_ui_context(self.char1), context.ASHORE)

    def test_hybrid_leaves_an_ordinary_room_alone(self):
        switches.set_ui_mode(switches.UI_HYBRID)
        self.char1.location = self.room1
        self.assertEqual(context.resolve_maritime_ui_context(self.char1), context.NONE)


class TestGroundTruth(SwitchTestCase):
    """The chart the uncharted switch reads."""

    def test_it_covers_a_place_no_real_chart_would(self):
        chart = charts.ground_truth("default", 0.0)
        self.assertTrue(chart.covers(WorldPosition(4.0e7, -4.0e7)))

    def test_it_does_not_cross_regions(self):
        chart = charts.ground_truth("default", 0.0)
        self.assertFalse(chart.covers(WorldPosition(0.0, 0.0, 0.0, "elsewhere")))

    def test_it_has_no_error_in_it(self):
        world = _FlatSea(-40.0)
        chart = charts.ground_truth("default", 0.0)
        for east in (0.0, 137.0, 5000.0, -91234.5):
            read = charts.charted_terrain_z_at(chart, WorldPosition(east, east), 0.0, world)
            self.assertAlmostEqual(read, -40.0, places=9)

    def test_an_ordinary_chart_does_have_error_in_it(self):
        # The measurement the test above is only meaningful against: a chart of the same
        # patch at a quality anybody would call good is still wrong somewhere.
        world = _FlatSea(-40.0)
        paper = charts.Chart(
            key="a survey",
            west=-1.0e6,
            east=1.0e6,
            south=-1.0e6,
            north=1.0e6,
            quality=0.8,
            seed=7,
        )
        read = [
            charts.charted_terrain_z_at(paper, WorldPosition(east, east), 0.0, world)
            for east in (0.0, 137.0, 5000.0, -91234.5)
        ]
        self.assertTrue(any(abs(value + 40.0) > 1e-6 for value in read))

    def test_it_is_stamped_now_so_it_does_not_decay(self):
        far_future = charts.CHART_LIFETIME * 4.0
        chart = charts.ground_truth("default", far_future)
        self.assertAlmostEqual(chart.quality_at(far_future), 1.0)


class _FlatSea:
    """A world with one depth everywhere, so any error shows as a difference."""

    def __init__(self, depth):
        self.depth = depth

    def terrain_z_at(self, position):
        return self.depth


class TestUiCommand(SwitchTestCase):
    """`maritime ui`."""

    def test_reports_without_setting_anything(self):
        self.call(CmdMaritimeUi(), "", "Maritime panel (server-wide)")
        self.assertEqual(switches.ui_mode(), switches.UI_HYBRID)

    def test_sets_the_server(self):
        self.call(CmdMaritimeUi(), "off", "Maritime panel set server-wide: off")
        self.assertEqual(switches.ui_mode(), switches.UI_OFF)

    def test_refuses_nonsense(self):
        self.call(CmdMaritimeUi(), "periscope", "'periscope' is not one of on, off, hybrid")
        self.assertEqual(switches.ui_mode(), switches.UI_HYBRID)

    def test_is_locked_to_staff(self):
        self.assertIn("perm(Admin)", CmdMaritimeUi.locks)


class TestUnchartedCommand(SwitchTestCase):
    """`maritime uncharted`."""

    def test_reports_without_setting_anything(self):
        self.call(
            CmdMaritimeUncharted(), "", "Uncharted water: off - charts read what was surveyed"
        )
        self.assertFalse(switches.uncharted())

    def test_turns_it_on(self):
        self.call(CmdMaritimeUncharted(), "on", "Uncharted water: on.")
        self.assertTrue(switches.uncharted())

    def test_warns_that_the_game_has_no_navigation_left(self):
        said = self.call(CmdMaritimeUncharted(), "on", None)
        self.assertIn("turn it off before play", said)

    def test_turns_it_off_again(self):
        switches.set_uncharted(True)
        self.call(
            CmdMaritimeUncharted(), "off", "Uncharted water: off. Charts read the paper again"
        )
        self.assertFalse(switches.uncharted())

    def test_takes_other_spellings_of_yes(self):
        self.call(CmdMaritimeUncharted(), "true", "Uncharted water: on.")
        self.assertTrue(switches.uncharted())

    def test_refuses_nonsense(self):
        self.call(CmdMaritimeUncharted(), "maybe", "Say maritime uncharted on")
        self.assertFalse(switches.uncharted())

    def test_is_locked_to_staff(self):
        self.assertIn("perm(Admin)", CmdMaritimeUncharted.locks)


class TestPlayerGuiCommand(SwitchTestCase):
    """`maritime player gui`."""

    def test_reports_without_setting_anything(self):
        self.call(CmdMaritimePlayerGui(), "", "Players may not choose")
        self.assertFalse(switches.players_may_choose())

    def test_lends_the_choice_out(self):
        self.call(CmdMaritimePlayerGui(), "on", "Players may now set their own")
        self.assertTrue(switches.players_may_choose())

    def test_takes_it_back(self):
        switches.set_players_may_choose(True)
        self.call(CmdMaritimePlayerGui(), "off", "Players may no longer choose")
        self.assertFalse(switches.players_may_choose())

    def test_says_it_erases_nothing(self):
        switches.set_players_may_choose(True)
        said = self.call(CmdMaritimePlayerGui(), "off", None)
        self.assertIn("has been erased", said)

    def test_refuses_nonsense(self):
        self.call(CmdMaritimePlayerGui(), "sometimes", "Say maritime player gui on")

    def test_is_locked_to_staff(self):
        self.assertIn("perm(Admin)", CmdMaritimePlayerGui.locks)


class TestMyGuiCommand(SwitchTestCase):
    """`maritime gui`."""

    def test_says_no_while_the_game_forbids_it(self):
        self.call(CmdMyGui(), "off", "This game sets the interface for everybody")
        self.assertIsNone(switches.ui_choice(self.char1))

    def test_sets_this_persons_own(self):
        switches.set_players_may_choose(True)
        self.call(CmdMyGui(), "off", "Your maritime panel")
        self.assertEqual(switches.ui_choice(self.char1), switches.UI_OFF)

    def test_leaves_the_server_alone(self):
        switches.set_players_may_choose(True)
        self.call(CmdMyGui(), "off", "Your maritime panel: off")
        self.assertEqual(switches.ui_mode(), switches.UI_HYBRID)

    def test_default_clears_it(self):
        switches.set_players_may_choose(True)
        switches.set_ui_choice(self.char1, switches.UI_OFF)
        self.call(CmdMyGui(), "default", "Back to whatever this game does")
        self.assertIsNone(switches.ui_choice(self.char1))

    def test_reports_which_it_is_and_why(self):
        switches.set_players_may_choose(True)
        said = self.call(CmdMyGui(), "", None)
        self.assertIn("which is the game's own", said)
        switches.set_ui_choice(self.char1, switches.UI_ON)
        said = self.call(CmdMyGui(), "", None)
        self.assertIn("which you chose", said)

    def test_refuses_nonsense(self):
        switches.set_players_may_choose(True)
        self.call(CmdMyGui(), "periscope", "'periscope' is not one of on, off, hybrid or default")

    def test_is_hidden_from_players_until_the_game_lends_it_out(self):
        self.assertFalse(CmdMyGui().access(self.char2, "cmd"))

    def test_opens_to_players_once_the_game_lends_it_out(self):
        switches.set_players_may_choose(True)
        self.assertTrue(CmdMyGui().access(self.char2, "cmd"))

    def test_closes_again_when_the_game_takes_it_back(self):
        switches.set_players_may_choose(True)
        switches.set_players_may_choose(False)
        self.assertFalse(CmdMyGui().access(self.char2, "cmd"))

    def test_staff_can_always_reach_it(self):
        # So that whoever is deciding whether to lend it out can see what it does first.
        self.char1.permissions.add("Admin")
        self.assertTrue(CmdMyGui().access(self.char1, "cmd"))

    def test_it_takes_the_session_the_parser_passes(self):
        # The cmdhandler calls access(caller, "cmd", session=session) on every command in
        # the merged set for every line anybody types. An override missing that keyword
        # does not break this command - it raises out of the parser and breaks the game.
        self.assertFalse(CmdMyGui().access(self.char2, "cmd", session=None))
        switches.set_players_may_choose(True)
        self.assertTrue(CmdMyGui().access(self.char2, "cmd", session=None))

    def test_widening_only_touches_the_cmd_lock(self):
        switches.set_players_may_choose(True)
        self.assertFalse(CmdMyGui().access(self.char2, "call", default=False))


class TestTheCmdSet(SwitchTestCase):
    """What a game gets by installing one line."""

    def test_holds_all_four(self):
        made = MaritimeInterfaceCmdSet()
        made.at_cmdset_creation()
        keys = {command.key for command in made.commands}
        self.assertEqual(
            keys,
            {"maritime ui", "maritime uncharted", "maritime player gui", "maritime gui"},
        )

    def test_none_of_them_are_open_to_players_out_of_the_box(self):
        made = MaritimeInterfaceCmdSet()
        made.at_cmdset_creation()
        reachable = [one.key for one in made.commands if one.access(self.char2, "cmd")]
        self.assertEqual(reachable, [])

    def test_lending_the_choice_out_exposes_exactly_one(self):
        switches.set_players_may_choose(True)
        made = MaritimeInterfaceCmdSet()
        made.at_cmdset_creation()
        reachable = [one.key for one in made.commands if one.access(self.char2, "cmd")]
        self.assertEqual(reachable, ["maritime gui"])

    def test_no_two_keys_shadow_each_other(self):
        # `maritime gui` and `maritime player gui` both begin with `maritime `, and a
        # parser that took the first prefix it matched would make one of them unreachable.
        made = MaritimeInterfaceCmdSet()
        made.at_cmdset_creation()
        keys = sorted(command.key for command in made.commands)
        for typed, wanted in (
            ("maritime gui on", "maritime gui"),
            ("maritime player gui on", "maritime player gui"),
            ("maritime ui on", "maritime ui"),
            ("maritime uncharted on", "maritime uncharted"),
        ):
            matched = max((key for key in keys if typed.startswith(key)), key=len, default=None)
            self.assertEqual(matched, wanted, f"'{typed}' reached the wrong command")


class TestTheGamesOwnDefault(SwitchTestCase):
    """What `MARITIME_ASHORE_PANEL` decides, when nobody has overridden it."""

    @override_settings(MARITIME_ASHORE_PANEL=False)
    def test_a_game_that_hides_the_panel_ashore_defaults_to_hybrid(self):
        self.assertEqual(switches.default_ui_mode(), switches.UI_HYBRID)
        self.assertEqual(switches.ui_mode(), switches.UI_HYBRID)

    @override_settings(MARITIME_ASHORE_PANEL=True)
    def test_a_game_that_wants_it_ashore_defaults_to_on(self):
        self.assertEqual(switches.default_ui_mode(), switches.UI_ON)
        self.assertEqual(switches.ui_mode(), switches.UI_ON)

    @override_settings(MARITIME_ASHORE_PANEL=True)
    def test_the_runtime_switch_still_overrides_it(self):
        switches.set_ui_mode(switches.UI_OFF)
        self.assertEqual(switches.ui_mode(), switches.UI_OFF)


class TestUnchartedChangesTheChart(EmptySeaMixin, SwitchTestCase):
    """
    What the switch is actually for, measured on the sheet rather than on the flag.

    Notes:
        The flag being set is not the feature. Every earlier version of a switch like this
        that broke did so with the flag reading perfectly and nothing downstream consulting
        it, so these ask the sheet.

    """

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Test Sloop")
        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.deck.vessel = self.hull
        self.hull.maritime_position = WorldPosition(0.0, 0.0)

    def sheet(self, reach=3000.0):
        """
        Returns:
            drawn (dict): The chart as it would go on the wire.

        """
        from ..client.state import chart_for

        return chart_for(self.hull, reach).as_message()

    def test_a_ship_with_no_chart_draws_nothing(self):
        self.assertEqual(self.sheet()["soundings"], [])

    def test_a_ship_with_no_chart_draws_the_world_once_it_is_on(self):
        switches.set_uncharted(True)
        self.assertNotEqual(self.sheet()["soundings"], [])

    def test_the_paper_has_no_edge_within_reach(self):
        switches.set_uncharted(True)
        edges = self.sheet()["coverage"]
        for side in ("west", "east", "south", "north"):
            self.assertGreater(abs(edges[side]), 1.0e8)

    def test_it_goes_back_to_nothing_when_switched_off(self):
        switches.set_uncharted(True)
        self.assertNotEqual(self.sheet()["soundings"], [])
        switches.set_uncharted(False)
        self.assertEqual(self.sheet()["soundings"], [])


class _FakeSession:
    """A session with a puppet and nothing else worth having."""

    def __init__(self, puppet):
        self.puppet = puppet


class TestEverybodyIsTold(SwitchTestCase):
    """
    A server-wide switch reaches every screen, not only the one that typed it.

    Notes:
        Faked sessions rather than real ones, because what is being checked is which
        characters are reached and how many times - which is arithmetic over the session
        handler, and does not need a socket to be wrong.

    """

    def sessions_of(self, *puppets):
        """
        Args:
            *puppets (Object): Who is being played, once per session.

        Returns:
            patched (contextmanager): A session handler answering with those.

        """
        from unittest import mock

        handler = mock.Mock()
        handler.get_sessions.return_value = [_FakeSession(one) for one in puppets]
        return mock.patch("evennia.server.sessionhandler.SESSIONS", handler)

    def test_finds_everybody_being_played(self):
        from ..commands.interface import _everybody

        with self.sessions_of(self.char1, self.char2):
            self.assertEqual(set(_everybody()), {self.char1, self.char2})

    def test_counts_one_character_once_however_many_clients(self):
        from ..commands.interface import _everybody

        with self.sessions_of(self.char1, self.char1, self.char1):
            self.assertEqual(_everybody(), [self.char1])

    def test_ignores_a_session_puppeting_nobody(self):
        from ..commands.interface import _everybody

        with self.sessions_of(self.char1, None):
            self.assertEqual(_everybody(), [self.char1])

    def test_finds_nobody_when_there_is_no_handler(self):
        from unittest import mock

        from ..commands.interface import _everybody

        with mock.patch("evennia.server.sessionhandler.SESSIONS", None):
            self.assertEqual(_everybody(), [])

    def test_the_ui_command_refreshes_everybody_not_just_the_caller(self):
        from unittest import mock

        from ..commands import interface

        with self.sessions_of(self.char1, self.char2):
            with mock.patch.object(interface, "_tell_everybody", return_value=0) as told:
                self.call(interface.CmdMaritimeUi(), "off", "Maritime panel set")
        told.assert_called_once()

    def test_a_refresh_reaches_each_character_once(self):
        from unittest import mock

        from ..client import transport

        with self.sessions_of(self.char1, self.char1, self.char2):
            with mock.patch.object(transport, "refresh_for") as refreshed:
                from ..commands.interface import _tell_everybody

                told = _tell_everybody()
        self.assertEqual(told, 2)
        self.assertEqual(
            {call.args[0] for call in refreshed.call_args_list}, {self.char1, self.char2}
        )

    def test_uncharted_also_redraws_the_chart(self):
        # The panel is already up and in the right mode; what changed is what is *on* it,
        # so a refresh alone would leave every captain looking at the old sheet until they
        # next zoomed.
        from unittest import mock

        from ..client import transport

        with self.sessions_of(self.char1):
            with mock.patch.object(transport, "refresh_for"):
                with mock.patch.object(transport, "redraw_chart") as redrawn:
                    from ..commands.interface import _tell_everybody

                    _tell_everybody(chart_too=True)
        self.assertTrue(redrawn.called)

    def test_an_ordinary_refresh_does_not_redraw_the_chart(self):
        from unittest import mock

        from ..client import transport

        with self.sessions_of(self.char1):
            with mock.patch.object(transport, "refresh_for"):
                with mock.patch.object(transport, "redraw_chart") as redrawn:
                    from ..commands.interface import _tell_everybody

                    _tell_everybody()
        self.assertFalse(redrawn.called)
