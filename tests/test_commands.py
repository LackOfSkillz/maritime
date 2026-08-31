"""
Tests for the helm commands.

"""

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaCommandTest, BaseEvenniaTestCase

from .base import EmptySeaMixin

from ..commands import (
    CmdAllStop,
    CmdHelm,
    CmdPosition,
    CmdSpeed,
    knots_to_ms,
    ms_to_knots,
    vessel_of,
)
from ..motion import HelmOrders, MotionLimits
from ..position import WorldPosition
from ..typeclasses import ShipRoom, Vessel


class HelmTestCase(EmptySeaMixin, BaseEvenniaCommandTest):
    """A character standing on the deck of a vessel under way."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Test Sloop")
        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.deck.vessel = self.hull
        self.hull.maritime_position = WorldPosition(0.0, 0.0)
        self.hull.motion_limits = MotionLimits(max_speed=10.0, acceleration=1.0, turn_rate=6.0)
        self.char1.location = self.deck


class TestUnitConversion(BaseEvenniaCommandTest):
    """Knots at the edge, metres per second inside."""

    def test_one_knot_is_a_nautical_mile_per_hour(self):
        self.assertAlmostEqual(knots_to_ms(1.0) * 3600.0, 1852.0)

    def test_round_trips(self):
        self.assertAlmostEqual(ms_to_knots(knots_to_ms(8.0)), 8.0)

    def test_eight_knots_is_about_four_metres_per_second(self):
        self.assertAlmostEqual(knots_to_ms(8.0), 4.1156, places=4)


class TestVesselLookup(HelmTestCase):
    """Finding what the caller is standing on."""

    def test_finds_the_vessel_from_the_deck(self):
        self.assertIs(vessel_of(self.char1), self.hull)

    def test_finds_nothing_ashore(self):
        self.char1.location = self.room1
        self.assertIsNone(vessel_of(self.char1))

    def test_finds_nothing_when_nowhere(self):
        self.char1.location = None
        self.assertIsNone(vessel_of(self.char1))


class TestCmdHelm(HelmTestCase):
    """Ordering a heading."""

    def test_sets_the_ordered_heading(self):
        self.call(CmdHelm(), "072")
        self.assertEqual(self.hull.orders.heading, 72.0)

    def test_confirms_the_order(self):
        """Courses are spoken digit by digit, as they are at sea."""
        self.call(CmdHelm(), "072", 'You call out, "Helm, steer 0-7-2."')

    def test_the_helm_answers(self):
        """The repeat-back is how an order is confirmed heard."""
        output = self.call(CmdHelm(), "072")
        self.assertIn("Steering 0-7-2 now, sir.", output)

    def test_reports_when_given_no_argument(self):
        self.hull.orders = HelmOrders(heading=90.0)
        self.call(CmdHelm(), "", "Ordered heading 090.0")

    def test_reports_actual_alongside_ordered(self):
        """The gap between the two is most of what makes handling a ship."""
        self.hull.orders = HelmOrders(heading=90.0)
        self.hull.heading = 0.0
        output = self.call(CmdHelm(), "")
        self.assertIn("making good 000.0", output)

    def test_wraps_an_out_of_range_bearing(self):
        self.call(CmdHelm(), "400")
        self.assertEqual(self.hull.orders.heading, 40.0)

    def test_rejects_nonsense(self):
        self.call(CmdHelm(), "hard to port", "Give a bearing in degrees")

    def test_keeps_the_ordered_speed(self):
        self.hull.orders = HelmOrders(heading=0.0, speed=5.0)
        self.call(CmdHelm(), "180")
        self.assertEqual(self.hull.orders.speed, 5.0)

    def test_refuses_ashore(self):
        self.char1.location = self.room1
        self.call(CmdHelm(), "072", "You are not aboard a vessel.")


class TestCmdSpeed(HelmTestCase):
    """Ordering a speed."""

    def test_sets_the_ordered_speed(self):
        self.call(CmdSpeed(), "6")
        self.assertAlmostEqual(self.hull.orders.speed, knots_to_ms(6.0))

    def test_confirms_in_knots(self):
        self.call(CmdSpeed(), "6", 'You call out, "Make her 6 knots."')

    def test_the_mate_answers(self):
        output = self.call(CmdSpeed(), "6")
        self.assertIn("Making 6 knots now, sir.", output)

    def test_reports_when_given_no_argument(self):
        self.call(CmdSpeed(), "", "Ordered 0.0 knots")

    def test_reports_actual_alongside_ordered(self):
        self.hull.orders = HelmOrders(speed=knots_to_ms(8.0))
        self.hull.speed = 0.0
        output = self.call(CmdSpeed(), "")
        self.assertIn("making 0.0", output)

    def test_rejects_a_negative_speed(self):
        self.call(CmdSpeed(), "-5", "Order a reciprocal heading")

    def test_rejects_nonsense(self):
        self.call(CmdSpeed(), "fast", "Give a speed in knots")

    def test_keeps_the_ordered_heading(self):
        self.hull.orders = HelmOrders(heading=72.0)
        self.call(CmdSpeed(), "6")
        self.assertEqual(self.hull.orders.heading, 72.0)

    def test_refuses_ashore(self):
        self.char1.location = self.room1
        self.call(CmdSpeed(), "6", "You are not aboard a vessel.")


class TestCmdAllStop(HelmTestCase):
    """Taking the way off."""

    def test_orders_zero_speed(self):
        self.hull.orders = HelmOrders(heading=72.0, speed=5.0)
        self.call(CmdAllStop(), "")
        self.assertEqual(self.hull.orders.speed, 0.0)

    def test_keeps_the_heading_order(self):
        self.hull.orders = HelmOrders(heading=72.0, speed=5.0)
        self.call(CmdAllStop(), "")
        self.assertEqual(self.hull.orders.heading, 72.0)

    def test_is_called_out(self):
        output = self.call(CmdAllStop(), "")
        self.assertIn("All stop.", output)

    def test_the_mate_answers(self):
        output = self.call(CmdAllStop(), "")
        self.assertIn("All stop, aye sir.", output)


class TestCmdPosition(HelmTestCase):
    """Reporting state."""

    def test_names_the_vessel(self):
        self.assertIn("Test Sloop", self.call(CmdPosition(), ""))

    def test_shows_the_position(self):
        self.assertIn("Position", self.call(CmdPosition(), ""))

    def test_shows_ordered_against_actual(self):
        """Headings are shown as they are spoken, digit by digit."""
        self.hull.orders = HelmOrders(heading=90.0, speed=knots_to_ms(8.0))
        output = self.call(CmdPosition(), "")
        self.assertIn("ordered 0-9-0", output)
        self.assertIn("ordered 8.0 kt", output)

    def test_shows_a_navigators_position_not_coordinates(self):
        """A player reads a position; metres are for staff."""
        output = self.call(CmdPosition(), "")
        self.assertNotIn("0.000,", output)

    def test_refuses_ashore(self):
        self.char1.location = self.room1
        self.call(CmdPosition(), "", "You are not aboard a vessel.")


class TestHelmDrivesTheHull(HelmTestCase):
    """Orders given by a person actually move the ship."""

    def test_a_voyage_from_typed_commands(self):
        """
        The end-to-end path this phase exists to deliver: someone types an
        order, the simulation runs, and the vessel is somewhere else.

        """
        self.call(CmdHelm(), "090")
        self.call(CmdSpeed(), "8")

        for _ in range(60):
            self.hull.at_maritime_tick(5.0)

        self.assertGreater(self.hull.maritime_position.x, 0.0)
        self.assertAlmostEqual(self.hull.heading, 90.0, places=3)
        self.assertAlmostEqual(ms_to_knots(self.hull.speed), 8.0, places=2)

    def test_she_does_not_reach_the_order_at_once(self):
        self.call(CmdSpeed(), "8")
        self.hull.at_maritime_tick(1.0)
        self.assertLess(ms_to_knots(self.hull.speed), 8.0)

    def test_allstop_brings_her_to_rest(self):
        self.call(CmdSpeed(), "8")
        for _ in range(60):
            self.hull.at_maritime_tick(5.0)
        self.call(CmdAllStop(), "")
        for _ in range(60):
            self.hull.at_maritime_tick(5.0)
        self.assertEqual(self.hull.speed, 0.0)


class TestNoTwoCommandsAnswerToTheSameWord(BaseEvenniaTestCase):
    """
    Every key and alias in the contrib, checked for collisions.

    Written after `hold fire` shipped with a bare `hold` alias, which the oar
    order to hold water already answered to. Nothing caught it - the command had
    tests, they passed, and the collision only showed up when a captain on a deck
    tried to run his guns out and was told the ship had no oars aboard.

    A game may of course shadow any of these with its own; that is its business.
    This is only about the contrib not arguing with itself.

    """

    def spoken_words(self):
        """
        Returns:
            words (dict): Each key or alias, against the commands claiming it.

        """
        from .. import commands as command_module

        claimed = {}
        for name in dir(command_module):
            cmd = getattr(command_module, name)
            key = getattr(cmd, "key", None)
            if not isinstance(key, str) or not isinstance(cmd, type):
                continue
            for word in (key, *getattr(cmd, "aliases", ())):
                claimed.setdefault(word, set()).add(cmd.__name__)
        return claimed

    def test_nothing_is_claimed_twice(self):
        clashes = {
            word: sorted(owners) for word, owners in self.spoken_words().items() if len(owners) > 1
        }
        self.assertEqual(clashes, {})

    def test_and_the_check_is_actually_looking_at_something(self):
        """Guards the test above: an empty sweep would pass it trivially."""
        self.assertGreater(len(self.spoken_words()), 40)
