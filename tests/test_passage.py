"""
Tests for ordering a passage, and for the one question that decides everything else:
can she get there from here.

The pond is the case worth reading. It is water, it has a quay, a ship would float in it,
and nothing can be told to sail to it - because reachability is what a world *states*
through its marks and not what a search over the seabed *finds*. Half the tests here are
about that distinction holding.

"""

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaCommandTest

from .. import passage, shipyard
from ..buoyage import SAFE_WATER
from ..commands.passage import CmdMakeFor, CmdPorts, PassageCmdSet
from ..motion import HelmOrders, MotionLimits
from ..ports import Berth
from ..position import WorldPosition
from ..rooms import PortRoom
from ..routes import NavigationNetwork, Waypoint
from ..typeclasses import Vessel
from .base import EmptySeaMixin

EAST = 90.0

#: Three harbours and a pond, laid out so the interesting cases are all present at once.
#:
#: `home` and `away` have marks and a channel between them. `pond` has a quay and no mark
#: within reach of it, which is what makes it a pond. `shallow` has a mark and a berth too
#: small for anything.
HARBOURS = {
    "home": (0.0, 0.0),
    "away": (10000.0, 0.0),
    "shallow": (4000.0, 3000.0),
    "the pond": (2000.0, 40000.0),
}


class _Marks(NavigationNetwork):
    """Marks off three of the four harbours, and a channel joining two of them."""

    def __init__(self):
        super().__init__()
        self.add(Waypoint("home roads", WorldPosition(200.0, 0.0), SAFE_WATER))
        self.add(Waypoint("away roads", WorldPosition(9800.0, 0.0), SAFE_WATER))
        self.add(Waypoint("shallow roads", WorldPosition(4000.0, 2800.0), SAFE_WATER))
        self.link("home roads", "away roads")
        # `shallow` is marked and unlinked on purpose: a harbour can be somewhere you know
        # about and still be somewhere you cannot get to from here.


class PassageTestCase(EmptySeaMixin, BaseEvenniaCommandTest):
    """A cutter lying at one of four harbours."""

    def setUp(self):
        super().setUp()
        self.marks = _Marks()
        self.ports = {}
        for name, (east, north) in HARBOURS.items():
            port = create.create_object(PortRoom, key=name)
            port.maritime_position = WorldPosition(east, north)
            port.add_berth(
                Berth(
                    key=f"{name} quay",
                    position=WorldPosition(east, north),
                    heading=EAST,
                    max_length=40.0,
                    max_beam=12.0,
                    max_draft=0.5 if name == "shallow" else 6.0,
                )
            )
            self.ports[name] = port

        self.hull = shipyard.outfit(create.create_object(Vessel, key="Kittiwake"), "cutter")
        shipyard.compartments(self.hull, "cutter")
        self.hull.motion_limits = MotionLimits(max_speed=5.0, acceleration=0.4, turn_rate=4.0)
        self.hull.maritime_position = WorldPosition(300.0, 0.0)
        self.hull.heading = EAST
        self.hull.speed = 0.0
        self.hull.orders = HelmOrders(heading=EAST, speed=0.0)
        self.char1.location = self.hull.ship_rooms[0]

    def reach(self, name):
        """
        Args:
            name (str): One of `HARBOURS`.

        Returns:
            passage (Passage): What came of asking.

        """
        return passage.can_reach(self.hull, self.ports[name], self.marks)


class TestWhatCountsAsAHarbour(PassageTestCase):
    """`ports_afloat`, which is the list everything else works from."""

    def test_it_finds_the_ones_with_berths_and_a_position(self):
        found = set(passage.ports_afloat())
        self.assertEqual(found, set(self.ports.values()))

    def test_a_quay_with_no_berths_is_not_a_harbour(self):
        create.create_object(PortRoom, key="viewing platform").maritime_position = WorldPosition(
            0.0, 500.0
        )
        self.assertNotIn("viewing platform", [port.key for port in passage.ports_afloat()])

    def test_a_quay_not_on_the_water_yet_is_not_a_harbour(self):
        unfinished = create.create_object(PortRoom, key="unfinished")
        unfinished.add_berth(Berth(key="q", position=WorldPosition(0.0, 0.0), max_draft=6.0))
        self.assertNotIn("unfinished", [port.key for port in passage.ports_afloat()])


class TestWhichMarkServesAHarbour(PassageTestCase):
    """`approach_for`, which is where the pond is decided."""

    def test_a_marked_harbour_has_one(self):
        self.assertIsNotNone(passage.approach_for(self.ports["home"], self.marks))

    def test_the_pond_has_none(self):
        self.assertIsNone(passage.approach_for(self.ports["the pond"], self.marks))

    def test_a_mark_too_far_off_does_not_count_as_serving_it(self):
        # The nearest mark to the pond exists; it is thirty-seven kilometres away and off
        # another coast. Nearest is not the same as near enough, and taking it would have
        # made every harbour in the world reachable from every other.
        nearest = self.marks.nearest(self.ports["the pond"].maritime_position)
        self.assertIsNotNone(nearest)
        self.assertGreater(
            self.ports["the pond"].maritime_position.horizontal_distance_to(nearest.position),
            passage.APPROACH_RANGE,
        )


class TestCanReach(PassageTestCase):
    """The whole question, and each way it is answered no."""

    def test_a_marked_harbour_with_a_channel_can_be_reached(self):
        self.assertTrue(self.reach("away"))

    def test_the_route_ends_at_the_berth_itself(self):
        # So the sailing master's slow final approach is the approach to the quay, which is
        # the whole reason the berth is on the end of the route rather than the mark.
        route = self.reach("away").route
        self.assertEqual(route.waypoints[-1].position, self.ports["away"].berths[0].position)

    def test_the_route_goes_by_way_of_the_marks(self):
        names = [mark.key for mark in self.reach("away").route.waypoints]
        self.assertIn("home roads", names)
        self.assertIn("away roads", names)

    def test_the_pond_cannot_be_reached(self):
        answer = self.reach("the pond")
        self.assertFalse(answer)
        self.assertEqual(answer.why, passage.NO_MARK)

    def test_and_it_says_so_in_words(self):
        self.assertIn("no channel is marked", self.reach("the pond").said)

    def test_a_marked_harbour_with_no_channel_to_it_cannot_be_reached(self):
        answer = self.reach("shallow")
        self.assertFalse(answer)

    def test_a_harbour_whose_berths_are_too_small_cannot_be_reached(self):
        # Asked before the route, because a course to a berth that will not take her is a
        # course to a disappointment three days from now.
        self.marks.link("home roads", "shallow roads")
        answer = self.reach("shallow")
        self.assertEqual(answer.why, passage.NO_BERTH)

    def test_a_ship_not_afloat_cannot_be_sent_anywhere(self):
        self.hull.maritime_position = None
        self.assertEqual(self.reach("away").why, passage.NOT_AFLOAT)

    def test_she_cannot_be_sent_where_she_already_is(self):
        self.hull.make_fast(self.ports["home"], self.ports["home"].berths[0])
        self.assertEqual(self.reach("home").why, passage.ALREADY_THERE)

    def test_a_taken_berth_is_no_berth(self):
        other = create.create_object(Vessel, key="Other")
        other.length, other.beam, other.light_draft = 20.0, 6.0, 2.6
        other.make_fast(self.ports["away"], self.ports["away"].berths[0])
        self.assertEqual(self.reach("away").why, passage.NO_BERTH)

    def test_every_refusal_has_a_sentence(self):
        for why in (
            passage.NO_MARK,
            passage.NO_ROUTE,
            passage.NO_BERTH,
            passage.NOT_AFLOAT,
            passage.ALREADY_THERE,
        ):
            said = passage.Passage(self.ports["home"], why=why).said
            self.assertTrue(said)
            self.assertNotIn("{", said)

    def test_a_passage_that_can_be_made_says_nothing(self):
        self.assertEqual(self.reach("away").said, "")


class TestOrderingIt(PassageTestCase):
    """`make_for`, which is the only thing that changes the ship."""

    def test_it_lays_the_course(self):
        passage.make_for(self.hull, self.ports["away"], self.marks)
        self.assertTrue(self.hull.route)

    def test_it_hands_the_con_to_the_sailing_master(self):
        passage.make_for(self.hull, self.ports["away"], self.marks)
        self.assertTrue(self.hull.under_con)

    def test_it_gives_him_the_standing_order_to_go_alongside(self):
        passage.make_for(self.hull, self.ports["away"], self.marks)
        self.assertIs(self.hull.db.alongside_at, self.ports["away"])

    def test_it_throws_away_where_the_last_course_had_got_to(self):
        # The index is derived from where she is, not inherited from an order she was
        # given last week. She lies a hundred metres off "home roads" here, which is
        # inside arrival range, so the answer is one rather than four - and rather than
        # zero, which is what it used to be and which sent her back to a mark she was
        # already at.
        self.hull.route_index = 4
        passage.make_for(self.hull, self.ports["away"], self.marks)
        self.assertEqual(
            self.hull.route_index,
            self.hull.route.advance(self.hull.maritime_position, 0),
        )

    def test_it_does_not_send_her_round_a_mark_she_is_lying_on(self):
        # She was being told to make for the mark she was moored to, which sent her away
        # from it and then back to it - a lap of a buoy she was already at.
        first = self.marks.waypoint("home roads")
        self.hull.maritime_position = first.position
        passage.make_for(self.hull, self.ports["away"], self.marks)
        self.assertGreater(self.hull.route_index, 0)
        self.assertNotEqual(self.hull.next_mark().key, "home roads")

    def test_a_refused_passage_changes_nothing_at_all(self):
        # A half-given order - a course laid and no master, or a master told to dock
        # somewhere she has no course to - is worse than none.
        self.assertFalse(passage.make_for(self.hull, self.ports["the pond"], self.marks))
        self.assertFalse(self.hull.route)
        self.assertFalse(self.hull.under_con)
        self.assertIsNone(self.hull.db.alongside_at)


class TestGoingAlongside(PassageTestCase):
    """The standing order, carried out."""

    def test_she_is_laid_against_the_quay(self):
        self.hull.db.alongside_at = self.ports["away"]
        self.hull.maritime_position = self.ports["away"].berths[0].position
        self.assertIsNotNone(passage.take_her_alongside(self.hull))
        self.assertTrue(self.hull.docked)

    def test_her_gangway_comes_down(self):
        self.hull.db.alongside_at = self.ports["away"]
        passage.take_her_alongside(self.hull)
        self.assertTrue(self.hull.db.gangway)

    def test_the_order_is_spent_whatever_happens(self):
        # An order that survived being carried out would berth her again every time she was
        # ever told to follow a course.
        self.hull.db.alongside_at = self.ports["away"]
        passage.take_her_alongside(self.hull)
        self.assertIsNone(self.hull.db.alongside_at)

    def test_a_ship_with_no_order_is_left_alone(self):
        self.assertIsNone(passage.take_her_alongside(self.hull))
        self.assertFalse(self.hull.docked)

    def test_a_berth_that_will_not_take_her_leaves_her_lying_off(self):
        self.hull.db.alongside_at = self.ports["shallow"]
        self.assertIsNone(passage.take_her_alongside(self.hull))
        self.assertFalse(self.hull.docked)

    def test_a_ship_already_alongside_is_not_moved(self):
        self.hull.make_fast(self.ports["home"], self.ports["home"].berths[0])
        self.hull.db.alongside_at = self.ports["away"]
        self.assertIsNone(passage.take_her_alongside(self.hull))
        self.assertIs(self.hull.docked_at, self.ports["home"])

    def test_belaying_it_leaves_the_course_alone(self):
        passage.make_for(self.hull, self.ports["away"], self.marks)
        self.assertTrue(passage.belay_alongside(self.hull))
        self.assertIsNone(self.hull.db.alongside_at)
        self.assertTrue(self.hull.route)
        self.assertTrue(self.hull.under_con)

    def test_belaying_an_order_she_has_not_got_says_so(self):
        self.assertFalse(passage.belay_alongside(self.hull))


class TestTheSailingMasterCarriesItOut(PassageTestCase):
    """
    The whole thing, end to end, through the tick the master actually runs on.

    Notes:
        Not a unit test of `take_her_alongside` - that is above. This is the wiring: the
        order given by one module, honoured by another, at the moment a third decides the
        passage is made. Four things written and never joined up is the failure this
        contrib has had most often.

    """

    def test_she_ends_the_passage_made_fast(self):
        passage.make_for(self.hull, self.ports["away"], self.marks)
        # Where she would be at the end of it: on the last waypoint, which is the berth.
        self.hull.maritime_position = self.hull.route.waypoints[-1].position
        self.hull.route_index = len(self.hull.route.waypoints)

        self.hull.work_her()

        self.assertFalse(self.hull.under_con)
        self.assertTrue(self.hull.docked)
        self.assertIs(self.hull.docked_at, self.ports["away"])

    def test_a_ship_merely_following_a_course_is_not_berthed(self):
        # `follow` has always ended with the con handed back and nothing else. Only a
        # standing order berths her, which is why the order is recorded rather than
        # inferred from her last waypoint happening to be a quay.
        answer = passage.can_reach(self.hull, self.ports["away"], self.marks)
        self.hull.route = answer.route
        self.hull.under_con = True
        self.hull.maritime_position = answer.route.waypoints[-1].position
        self.hull.route_index = len(answer.route.waypoints)

        self.hull.work_her()

        self.assertFalse(self.hull.under_con)
        self.assertFalse(self.hull.docked)


class TestPortsCommand(PassageTestCase):
    """`ports`."""

    def test_it_lists_the_harbours(self):
        said = self.call(CmdPorts(), "", None)
        for name in HARBOURS:
            self.assertIn(name, said)

    def test_it_says_why_an_unreachable_one_cannot_be_made(self):
        said = self.call(CmdPorts(), "", None)
        self.assertIn("no channel is marked into the pond", said)

    def test_a_ship_not_afloat_is_told_so(self):
        self.hull.maritime_position = None
        self.call(CmdPorts(), "", "She is not afloat.")


class TestMakeForCommand(PassageTestCase):
    """`make for`."""

    def test_it_wants_somewhere_to_go(self):
        self.call(CmdMakeFor(), "", "Make for where?")

    def test_it_refuses_a_harbour_nobody_has_heard_of(self):
        self.call(CmdMakeFor(), "Valparaiso", "No harbour called 'Valparaiso'")

    def test_it_refuses_an_ambiguous_name(self):
        create.create_object(PortRoom, key="homely").maritime_position = WorldPosition(50.0, 50.0)
        self.ports["home"].maritime_position = WorldPosition(0.0, 0.0)
        homely = [port for port in passage.ports_afloat() if port.key == "homely"]
        if homely:
            homely[0].add_berth(Berth(key="h", position=WorldPosition(50.0, 50.0), max_draft=6.0))
            self.call(CmdMakeFor(), "hom", "Which of them")

    def test_it_refuses_the_pond_and_says_why(self):
        self.call(CmdMakeFor(), "the pond", "She cannot be sent to the pond")
        self.assertFalse(self.hull.under_con)

    def test_the_aliases_are_the_words_people_reach_for(self):
        # "navigate to" is what somebody clicking a harbour on a chart would call it, and
        # "sail to" is what they would type. The key is the one a master would say.
        self.assertIn("sail to", CmdMakeFor.aliases)
        self.assertIn("navigate to", CmdMakeFor.aliases)


class TestTheCmdSet(PassageTestCase):
    """What a game gets with the helm."""

    def test_it_holds_both(self):
        made = PassageCmdSet()
        made.at_cmdset_creation()
        self.assertEqual({command.key for command in made.commands}, {"ports", "make for"})

    def test_the_helm_carries_them(self):
        from ..cmdsets import HelmCmdSet

        made = HelmCmdSet()
        made.at_cmdset_creation()
        keys = {command.key for command in made.commands}
        self.assertIn("ports", keys)
        self.assertIn("make for", keys)


class TestTheyNeedADeck(PassageTestCase):
    """Both are orders, and an order wants a deck under it."""

    def test_ordering_a_passage_ashore_says_so(self):
        self.char1.location = self.ports["home"]
        said = self.call(CmdMakeFor(), "away", None)
        self.assertNotIn("Sailing master", said)
        self.assertFalse(self.hull.under_con)

    def test_listing_the_harbours_ashore_says_so(self):
        self.char1.location = self.ports["home"]
        said = self.call(CmdPorts(), "", None)
        self.assertNotIn("Harbours she could", said)
