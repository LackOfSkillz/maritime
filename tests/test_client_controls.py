"""
Tests for what a button is allowed to do.

A control is a way of typing a command. Everything here is about keeping it that way:
that a browser cannot reach anything a captain shouting could not, cannot put text on a
command line, and cannot be offered - or obeyed - when it has no business giving orders.

A determined player has a JavaScript console and will call these by hand with whatever
arguments they like. Most of this file is that player.

"""

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest, BaseEvenniaTestCase

from ..client.context import COMMAND, NONE, PASSENGER, WATER
from ..client.controls import CONTROLS, MAX_ALTERATION, offered, order_for
from ..motion import HelmOrders, MotionLimits
from ..position import WorldPosition
from ..rooms import ShipRoom
from ..sailing import FULL
from ..typeclasses import Vessel
from ..vessel import OPEN
from .base import EmptySeaMixin

HERE = WorldPosition(0.0, 0.0)


class Steering:
    """
    A hull, for orders that are relative to how she is already heading.

    Notes:
        A stand-in rather than a real vessel, because `order_for` asks it exactly two
        things and building a ship to answer them would hide how little it needs.

    """

    def __init__(self, ordered=80.0, heading=84.0):
        self.orders = type("Orders", (), {"heading": ordered})()
        self.heading = heading


class TestTurningAPressIntoAnOrder(BaseEvenniaTestCase):
    """Every value is rebuilt here, so nothing a browser sends reaches a command."""

    def test_a_wheel_over_becomes_a_bearing(self):
        """
        `helm` takes a bearing, so "ten degrees to starboard" is added to what she is
        already steering and sent as the absolute order a text player would type.
        Inventing a `helm starboard 10` syntax to match the button would have given
        the graphical client a command the text one has not got.

        """
        self.assertEqual(
            order_for("starboard", {"degrees": 20}, Steering(ordered=84.0)), "helm 104"
        )

    def test_and_to_port_goes_the_other_way(self):
        self.assertEqual(order_for("port", {"degrees": 20}, Steering(ordered=84.0)), "helm 64")

    def test_a_wheel_over_wraps_around_the_compass(self):
        self.assertEqual(
            order_for("starboard", {"degrees": 20}, Steering(ordered=350.0)), "helm 10"
        )

    def test_steady_holds_the_head_she_is_actually_on(self):
        """
        Not the one she was last ordered. "Steady as she goes" means this heading,
        which is the point of saying it while she is still coming round.

        """
        self.assertEqual(order_for("steady", {}, Steering(ordered=120.0, heading=97.0)), "helm 97")

    def test_a_relative_order_with_no_hull_is_refused(self):
        self.assertIsNone(order_for("starboard", {"degrees": 10}))

    def test_an_unknown_control_is_refused(self):
        self.assertIsNone(order_for("scuttle"))

    def test_and_so_is_one_that_is_almost_a_control(self):
        self.assertIsNone(order_for("helm"))

    def test_an_action_that_is_not_even_a_name_is_refused(self):
        """
        A browser may send an object where a name belongs. `dict.get` raises on an
        unhashable key rather than politely missing, which turned a nonsense press
        into a traceback - found by sending nonsense deliberately.

        """
        for rubbish in ({}, [1, 2], None, 7):
            self.assertIsNone(order_for(rubbish))

    def test_a_wheel_over_is_clamped(self):
        """Four hundred degrees is not something a captain could say."""
        hard = order_for("starboard", {"degrees": 400}, Steering(ordered=0.0))
        self.assertEqual(hard, f"helm {int(MAX_ALTERATION)}")

    def test_and_never_reverses_itself(self):
        """
        A negative wheel-over to starboard is thirty degrees to starboard, not
        thirty to port. Which hand the wheel goes over is the control that was
        pressed, and no sign a browser sends may change it.

        """
        self.assertEqual(order_for("starboard", {"degrees": -30}, Steering(ordered=0.0)), "helm 30")
        self.assertEqual(order_for("port", {"degrees": -30}, Steering(ordered=0.0)), "helm 330")

    def test_a_bearing_is_wrapped_into_a_compass(self):
        self.assertEqual(order_for("heading", {"bearing": 450}), "helm 90")

    def test_nonsense_where_a_number_belongs_is_refused(self):
        for rubbish in ("north", None, {}, [1, 2]):
            self.assertIsNone(order_for("heading", {"bearing": rubbish}))

    def test_a_sail_plan_must_be_one_that_exists(self):
        self.assertEqual(order_for("sail", {"plan": "working"}), "sail working")
        self.assertIsNone(order_for("sail", {"plan": "spinnaker"}))

    def test_text_cannot_be_smuggled_onto_a_command_line(self):
        """
        The one control carrying a word rather than a number, and so the only place
        a client could otherwise have written its own command. The plan is matched
        against the plans that exist and rebuilt from the match, so what arrives is
        never what runs.

        """
        for attempt in (
            "working; @py print(1)",
            "working\nquit",
            "working full",
            "  working  ",
        ):
            line = order_for("sail", {"plan": attempt})
            self.assertIn(line, (None, "sail working"))

    def test_every_control_names_a_command(self):
        """A control with no command behind it is a promise nothing can keep."""
        for key, control in CONTROLS.items():
            self.assertTrue(control["command"], key)


class ControlsTestCase(EmptySeaMixin, BaseEvenniaTest):
    """A hull somebody might give orders to."""

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


class TestWhoIsOfferedWhat(ControlsTestCase):
    """Offered from the hull and from authority together."""

    def test_somebody_in_command_is_offered_the_helm(self):
        self.assertIn("port", offered(self.hull, COMMAND))

    def test_a_passenger_is_offered_nothing(self):
        """
        Not a disabled helm - no helm. A passenger looking at a greyed-out wheel is
        being told the interface thinks they might steer, and they may not.

        """
        self.assertEqual(offered(self.hull, PASSENGER), [])

    def test_and_neither_is_somebody_ashore(self):
        self.assertEqual(offered(self.hull, NONE), [])

    def test_nor_somebody_in_the_water(self):
        """A swimmer has problems of their own and no wheel to turn."""
        self.assertEqual(offered(self.hull, WATER), [])

    def test_no_hull_means_no_controls(self):
        self.assertEqual(offered(None, COMMAND), [])

    def test_what_is_offered_is_all_real(self):
        for key in offered(self.hull, COMMAND):
            self.assertIn(key, CONTROLS)


class TestPressingOne(ControlsTestCase):
    """End to end, through the same handler a typed command uses."""

    def setUp(self):
        super().setUp()
        from ..client import inputfuncs

        self.inputfuncs = inputfuncs
        self.ran = []
        self.char1.location = self.deck
        self.char1.execute_cmd = lambda line, **kwargs: self.ran.append(line)

    def press(self, action, **detail):
        """Press a control as a browser would."""
        session = type("Session", (), {"puppet": self.char1})()
        detail["action"] = action
        self.inputfuncs.maritime_action(session, **detail)

    def test_a_press_runs_the_command_it_stands_for(self):
        self.hull.orders = HelmOrders(heading=90.0, speed=0.0)
        self.press("starboard", degrees=10)
        self.assertEqual(self.ran, ["helm 100"])

    def test_it_goes_through_the_command_handler(self):
        """
        Not through the vessel. Every lock, every authority check and every refusal
        a typed order meets, a pressed one meets in the same place and the same
        words.

        """
        self.hull.heading = 45.0
        self.press("steady")
        self.assertEqual(self.ran, ["helm 45"])

    def test_an_invented_action_runs_nothing(self):
        self.press("scuttle")
        self.assertEqual(self.ran, [])

    def test_a_press_with_no_action_runs_nothing(self):
        session = type("Session", (), {"puppet": self.char1})()
        self.inputfuncs.maritime_action(session)
        self.assertEqual(self.ran, [])

    def test_a_session_puppeting_nobody_runs_nothing(self):
        session = type("Session", (), {"puppet": None})()
        self.inputfuncs.maritime_action(session, action="steady")
        self.assertEqual(self.ran, [])

    def test_a_passenger_forging_a_press_is_still_refused(self):
        """
        The whole point of the offered list being advisory. Nothing stops a browser
        sending an action it was never shown; what stops the order is the command,
        which checks authority when it runs.

        """
        self.hull.captain = self.char2
        self.assertEqual(offered(self.hull, PASSENGER), [])

        self.hull.orders = HelmOrders(heading=90.0, speed=0.0)
        self.press("port", degrees=10)
        self.assertEqual(self.ran, ["helm 80"])
        # The line is built, and the command refuses it. That refusal is tested
        # where command authority is tested; what matters here is that the browser
        # got no shortcut past it.
