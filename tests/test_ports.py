"""
Tests for berths, coming alongside, and the gangway.

"""

from evennia.utils import create
from evennia.utils.test_resources import (
    BaseEvenniaCommandTest,
    BaseEvenniaTest,
    BaseEvenniaTestCase,
)

from ..commands import CmdCastOff, CmdDock
from ..motion import HelmOrders, MotionLimits
from ..ports import (
    ALIGNMENT_TOLERANCE,
    ALONGSIDE_SPEED,
    APPROACH_RANGE,
    BADLY_ALIGNED,
    OCCUPIED,
    TOO_BEAMY,
    TOO_DEEP,
    TOO_FAR,
    TOO_FAST,
    TOO_LONG,
    Berth,
    alongside_side,
    can_dock,
    nearest_berth,
)
from ..position import EAST, NORTH, WEST, WorldPosition
from ..rooms import PortRoom, ShipRoom, berths_near, rig_gangway, unrig_gangway
from ..typeclasses import Vessel
from ..vessel import BELOW_WATERLINE, OPEN
from .base import EmptySeaMixin

QUAY = WorldPosition(0.0, 0.0)


def a_berth(**kwargs):
    """
    Args:
        **kwargs: Overrides.

    Returns:
        berth (Berth): A berth a test sloop comfortably fits.

    """
    settings = {
        "key": "north quay",
        "position": QUAY,
        "heading": EAST,
        "max_length": 30.0,
        "max_beam": 8.0,
        "max_draft": 4.0,
    }
    settings.update(kwargs)
    return Berth(**settings)


class TestBerthFit(BaseEvenniaTestCase):
    """What a berth will take."""

    def test_a_hull_that_fits(self):
        self.assertIsNone(a_berth().takes(18.0, 5.4, 2.2))

    def test_too_long(self):
        self.assertEqual(a_berth().takes(40.0, 5.4, 2.2), TOO_LONG)

    def test_too_broad(self):
        self.assertEqual(a_berth().takes(18.0, 12.0, 2.2), TOO_BEAMY)

    def test_drawing_too_much(self):
        """
        The tradeoff made physical: fit her out until she draws another half
        metre and her home berth may stop taking her.

        """
        self.assertEqual(a_berth().takes(18.0, 5.4, 6.0), TOO_DEEP)

    def test_an_unmeasured_dimension_is_no_limit(self):
        """
        Zero means nobody wrote it down, not that the berth is infinitely small.
        A game that has not filled in its berth sizes gets a working port.

        """
        self.assertIsNone(a_berth(max_length=0.0).takes(500.0, 5.4, 2.2))

    def test_the_heading_is_normalised(self):
        self.assertAlmostEqual(a_berth(heading=450.0).heading, 90.0)


class TestAlongsideSide(BaseEvenniaTestCase):
    """Which hand the quay is on."""

    def test_lying_with_the_quay(self):
        self.assertEqual(alongside_side(EAST, EAST), "port")

    def test_lying_the_other_way_round(self):
        self.assertEqual(alongside_side(WEST, EAST), "starboard")


class TestCanDock(BaseEvenniaTestCase):
    """The preconditions for putting lines ashore."""

    def alongside(self, **kwargs):
        """
        Args:
            **kwargs: Overrides for the attempt.

        Returns:
            result (DockingResult): The outcome.

        """
        attempt = {
            "position": WorldPosition(10.0, 0.0),
            "speed": 0.2,
            "heading": EAST,
            "length": 18.0,
            "beam": 5.4,
            "draft": 2.2,
            "berth": a_berth(),
        }
        attempt.update(kwargs)
        return can_dock(**attempt)

    def test_a_good_approach_succeeds(self):
        self.assertTrue(self.alongside())

    def test_it_reports_which_side_she_lies(self):
        self.assertEqual(self.alongside().side, "port")

    def test_too_far_off(self):
        result = self.alongside(position=WorldPosition(APPROACH_RANGE + 50.0, 0.0))
        self.assertEqual(result.code, TOO_FAR)

    def test_it_reports_how_far_off_she_was(self):
        """So a captain is told what to do, not only that he cannot."""
        result = self.alongside(position=WorldPosition(400.0, 0.0))
        self.assertAlmostEqual(result.distance, 400.0)

    def test_way_still_on_her(self):
        """
        Coming alongside at speed is not docking, it is a collision with
        paperwork.

        """
        result = self.alongside(speed=ALONGSIDE_SPEED + 2.0)
        self.assertEqual(result.code, TOO_FAST)

    def test_walking_pace_is_allowed(self):
        self.assertTrue(self.alongside(speed=ALONGSIDE_SPEED))

    def test_lying_across_the_berth(self):
        result = self.alongside(heading=NORTH)
        self.assertEqual(result.code, BADLY_ALIGNED)

    def test_either_way_round_is_acceptable(self):
        """Port side to or starboard side to. Both are berthing."""
        self.assertTrue(self.alongside(heading=EAST))
        self.assertTrue(self.alongside(heading=WEST))

    def test_a_little_off_the_line_is_forgiven(self):
        self.assertTrue(self.alongside(heading=EAST + ALIGNMENT_TOLERANCE - 5.0))

    def test_an_occupied_berth(self):
        self.assertEqual(self.alongside(occupied=True).code, OCCUPIED)

    def test_fit_is_checked_before_the_approach(self):
        """
        No point telling a captain his approach is too fast for a berth his ship
        was never going to fit.

        """
        result = self.alongside(length=40.0, speed=8.0, position=WorldPosition(9000.0, 0.0))
        self.assertEqual(result.code, TOO_LONG)


class TestNearestBerth(BaseEvenniaTestCase):
    """Choosing which one she is trying for."""

    def test_it_finds_the_closest(self):
        near = a_berth(key="near", position=WorldPosition(10.0, 0.0))
        far = a_berth(key="far", position=WorldPosition(900.0, 0.0))
        self.assertIs(nearest_berth(QUAY, [far, near]), near)

    def test_no_berths_is_no_answer(self):
        self.assertIsNone(nearest_berth(QUAY, []))

    def test_another_region_does_not_count(self):
        elsewhere = a_berth(position=WorldPosition(1.0, 0.0, region="lake"))
        self.assertIsNone(nearest_berth(QUAY, [elsewhere]))


class PortTestCase(EmptySeaMixin, BaseEvenniaTest):
    """A quay, a sloop, and a deck to walk between them."""

    def setUp(self):
        super().setUp()
        self.port = create.create_object(PortRoom, key="North Quay")
        self.port.maritime_position = QUAY
        self.port.add_berth(a_berth())

        self.hull = create.create_object(Vessel, key="Test Sloop")
        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.deck.vessel = self.hull
        self.deck.exposure = OPEN
        self.hull.maritime_position = WorldPosition(10.0, 0.0)
        self.hull.motion_limits = MotionLimits(max_speed=10.0, acceleration=2.0, turn_rate=8.0)
        self.hull.heading = EAST
        self.hull.speed = 0.0
        self.hull.orders = HelmOrders(heading=EAST, speed=0.0)
        self.hull.length = 18.0
        self.hull.beam = 5.4
        self.hull.light_draft = 2.2


class TestPortRoom(PortTestCase):
    """The quayside."""

    def test_it_stands_somewhere_on_the_water(self):
        """
        Unlike a ship's room, which has no position of its own. This is where the
        two coordinate systems meet.

        """
        self.assertEqual(self.port.maritime_position, QUAY)

    def test_it_refuses_a_position_that_is_not_one(self):
        with self.assertRaises(TypeError):
            self.port.maritime_position = "the docks"

    def test_a_character_on_the_quay_has_a_world_position(self):
        from ..resolver import get_world_position

        self.char1.location = self.port
        self.assertEqual(get_world_position(self.char1), QUAY)

    def test_berths_can_be_looked_up_by_name(self):
        self.assertIsNotNone(self.port.berth_named("NORTH QUAY"))

    def test_an_unknown_berth_is_not_found(self):
        self.assertIsNone(self.port.berth_named("dry dock"))

    def test_two_berths_cannot_share_a_name(self):
        """A booking system that cannot say where a ship is."""
        with self.assertRaises(ValueError):
            self.port.add_berth(a_berth())

    def test_berths_near_finds_it_from_the_water(self):
        found = berths_near(self.hull.maritime_position)
        self.assertEqual([berth.key for _port, berth in found], ["north quay"])

    def test_berths_near_ignores_the_far_side_of_the_world(self):
        self.assertEqual(berths_near(WorldPosition(90000.0, 0.0)), ())

    def test_a_quay_with_no_position_is_skipped(self):
        create.create_object(PortRoom, key="Unplaced")
        self.assertEqual(len(berths_near(self.hull.maritime_position)), 1)


class TestGangway(PortTestCase):
    """The exit that exists only while she is made fast."""

    def test_rigging_it_makes_two_exits(self):
        ashore, aboard = rig_gangway(self.deck, self.port)
        self.assertEqual(ashore.destination, self.port)
        self.assertEqual(aboard.destination, self.deck)

    def test_it_is_walked_across_rather_than_teleported(self):
        """
        Law 7: a physical relationship creates a traversal. It is an ordinary
        exit, so it can be followed, blocked, watched and locked like any other,
        and none of that needed designing.

        """
        rig_gangway(self.deck, self.port)
        self.char1.location = self.deck
        self.char1.execute_cmd("ashore")
        self.assertEqual(self.char1.location, self.port)

    def test_unrigging_removes_them(self):
        exits = rig_gangway(self.deck, self.port)
        self.assertEqual(unrig_gangway(exits), 2)

    def test_unrigging_an_already_gone_gangway_is_not_an_error(self):
        """
        Refusing to cast off because one end has already vanished would strand a
        ship at a quay that no longer exists.

        """
        exits = rig_gangway(self.deck, self.port)
        unrig_gangway(exits)
        self.assertEqual(unrig_gangway(exits), 0)


class TestMakingFast(PortTestCase):
    """Being held by her lines."""

    def dock(self):
        """
        Returns:
            result (DockingResult): The outcome of a good approach.

        """
        berth = self.port.berths[0]
        self.hull.make_fast(self.port, berth, rig_gangway(self.deck, self.port))
        return berth

    def test_she_knows_she_is_made_fast(self):
        self.dock()
        self.assertTrue(self.hull.docked)

    def test_she_is_moved_to_the_berth(self):
        berth = self.dock()
        self.assertEqual(self.hull.maritime_position, berth.position)

    def test_she_lies_along_the_quay(self):
        berth = self.dock()
        self.assertAlmostEqual(self.hull.heading, berth.heading)

    def test_the_port_knows_who_is_lying_there(self):
        berth = self.dock()
        self.assertIs(self.port.occupant_of(berth), self.hull)

    def test_sail_and_helm_will_not_shift_her(self):
        """
        Lines ashore hold her against wind, sail and helm alike. Getting under
        way is an act with a name.

        """
        self.dock()
        self.hull.orders = HelmOrders(heading=WEST, speed=8.0)
        where = self.hull.maritime_position
        for _ in range(10):
            self.hull.at_maritime_tick(5.0)
        self.assertEqual(self.hull.maritime_position, where)

    def test_letting_go_frees_her(self):
        self.dock()
        self.hull.let_go()
        self.assertFalse(self.hull.docked)

    def test_letting_go_takes_the_gangway_with_it(self):
        self.dock()
        self.assertEqual(self.hull.let_go(), 2)

    def test_letting_go_frees_the_berth(self):
        berth = self.dock()
        self.hull.let_go()
        self.assertIsNone(self.port.occupant_of(berth))

    def test_she_answers_her_helm_again(self):
        self.dock()
        self.hull.let_go()
        self.hull.orders = HelmOrders(heading=EAST, speed=5.0)
        self.hull.at_maritime_tick(10.0)
        self.assertGreater(self.hull.speed, 0.0)

    def test_being_made_fast_survives_a_reload(self):
        berth = self.dock()
        self.hull.at_server_reload()
        self.hull.ndb.maritime_position = None
        self.hull.ndb.heading = None
        self.assertTrue(self.hull.docked)
        self.assertEqual(self.hull.maritime_position, berth.position)

    def test_being_made_fast_survives_an_unclean_stop(self):
        """
        The reason docking persists at once rather than at the next checkpoint.

        A reload runs hooks and flushes everything anyway, so it cannot tell
        whether this was written now or later - which is why the first version of
        this test passed with the immediate write removed. A crash runs no hooks
        at all: whatever was still only in memory is simply gone. Her berth
        position lives in .ndb like every other position, so without the write
        she comes back flagged as made fast, at the coordinates she was at before
        she docked, with a gangway to nowhere.

        """
        berth = self.dock()
        self.hull.ndb.maritime_position = None
        self.hull.ndb.heading = None
        self.hull.ndb.speed = None
        self.assertTrue(self.hull.docked)
        self.assertEqual(self.hull.maritime_position, berth.position)


class TestCmdDock(EmptySeaMixin, BaseEvenniaCommandTest):
    """Ordering her alongside."""

    def setUp(self):
        super().setUp()
        self.port = create.create_object(PortRoom, key="North Quay")
        self.port.maritime_position = QUAY
        self.port.add_berth(a_berth())

        self.hull = create.create_object(Vessel, key="Test Sloop")
        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.deck.vessel = self.hull
        self.deck.exposure = OPEN
        self.hull.maritime_position = WorldPosition(10.0, 0.0)
        self.hull.heading = EAST
        self.hull.length = 18.0
        self.hull.beam = 5.4
        self.hull.light_draft = 2.2
        self.char1.location = self.deck

    def test_a_good_approach_makes_her_fast(self):
        self.call(CmdDock(), "")
        self.assertTrue(self.hull.docked)

    def test_the_order_is_spoken(self):
        output = self.call(CmdDock(), "")
        self.assertIn("Take her alongside", output)

    def test_the_refusal_says_why(self):
        self.hull.speed = 6.0
        output = self.call(CmdDock(), "")
        self.assertIn("way on", output)

    def test_a_refusal_leaves_her_at_sea(self):
        self.hull.speed = 6.0
        self.call(CmdDock(), "")
        self.assertFalse(self.hull.docked)

    def test_a_berth_can_be_named(self):
        self.call(CmdDock(), "north quay")
        self.assertTrue(self.hull.docked)

    def test_an_unknown_berth_is_reported(self):
        output = self.call(CmdDock(), "dry dock")
        self.assertIn("No berth called", output)

    def test_no_quay_within_reach(self):
        self.hull.maritime_position = WorldPosition(80000.0, 0.0)
        output = self.call(CmdDock(), "")
        self.assertIn("no berth within reach", output.lower())

    def test_she_cannot_dock_twice(self):
        self.call(CmdDock(), "")
        output = self.call(CmdDock(), "")
        self.assertIn("already made fast", output)

    def test_a_ship_with_no_open_deck_has_nowhere_to_land_it(self):
        self.deck.exposure = BELOW_WATERLINE
        output = self.call(CmdDock(), "")
        self.assertIn("no open deck", output)

    def test_casting_off_frees_her(self):
        self.call(CmdDock(), "")
        self.call(CmdCastOff(), "")
        self.assertFalse(self.hull.docked)

    def test_casting_off_is_spoken(self):
        self.call(CmdDock(), "")
        output = self.call(CmdCastOff(), "")
        self.assertIn("let go", output)

    def test_casting_off_a_ship_at_sea(self):
        output = self.call(CmdCastOff(), "")
        self.assertIn("not made fast", output)
