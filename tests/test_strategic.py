"""
Tests for the ships that are somewhere else.

Two claims. **Analytical, not stepped**: a vessel untouched for a week costs what one
untouched for a second costs. And **strategic is not dormant**: a hull carrying anything
individual is refused rather than summarised, because a summary that dropped what it could
not carry would work in every test and lose a player's chest the first time it mattered.

"""

import time

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest

from ..motion import MotionLimits
from ..position import WorldPosition
from ..rooms import ShipRoom
from ..routes import Route, Waypoint
from ..strategic import (
    NO_ROUTE,
    NOT_A_HULL,
    OCCUPIED,
    Fleet,
    Passage,
    StrategicVessel,
    along,
    fleet,
    is_individual,
    materialise,
    summarise,
)
from ..typeclasses import Vessel
from ..vessel import OPEN

WEST = Waypoint(key="West", position=WorldPosition(0.0, 0.0))
MIDDLE = Waypoint(key="Middle", position=WorldPosition(1000.0, 0.0))
EAST = Waypoint(key="East", position=WorldPosition(2000.0, 0.0))
LEGS = Route(waypoints=(WEST, MIDDLE, EAST))


class TestWhereAPassageHasGot(BaseEvenniaTest):
    """Arithmetic on the elapsed time, and nothing else."""

    def setUp(self):
        super().setUp()
        self.passage = Passage(route=LEGS, speed=10.0, departed=0.0)

    def test_at_the_moment_she_left_she_is_at_the_first_mark(self):
        self.assertEqual(along(self.passage, now=0.0).position, WEST.position)

    def test_she_gets_along(self):
        self.assertAlmostEqual(along(self.passage, now=50.0).position.x, 500.0, places=3)

    def test_and_onto_the_second_leg(self):
        self.assertEqual(along(self.passage, now=150.0).leg, 1)

    def test_she_stops_at_the_last_mark(self):
        far = along(self.passage, now=1_000_000.0)
        self.assertEqual(far.position, EAST.position)
        self.assertTrue(far.arrived)

    def test_she_is_steering_down_the_leg_she_is_on(self):
        self.assertAlmostEqual(along(self.passage, now=50.0).heading, 90.0, places=3)

    def test_a_route_with_one_mark_is_a_ship_sitting_on_it(self):
        """
        Not an error. A vessel at anchor described in the same terms as one on passage, so
        nothing downstream needs two cases.

        """
        anchored = Passage(route=Route(waypoints=(WEST,)), speed=10.0)
        self.assertEqual(along(anchored, now=9999.0).position, WEST.position)

    def test_a_passage_with_no_route_has_nowhere_to_be(self):
        self.assertIsNone(along(Passage(route=Route()), now=0.0).position)

    def test_nor_does_a_passage_that_is_not_one(self):
        self.assertIsNone(along(None, now=0.0).position)

    def test_a_ship_making_nothing_stays_where_she_was(self):
        becalmed = Passage(route=LEGS, speed=0.0)
        self.assertEqual(along(becalmed, now=9999.0).position, WEST.position)

    def test_time_before_she_left_does_not_sail_her_backwards(self):
        late = Passage(route=LEGS, speed=10.0, departed=500.0)
        self.assertEqual(along(late, now=0.0).position, WEST.position)


class TestItDoesNotMatterHowLongSheWasLeft(BaseEvenniaTest):
    """Law 5, and the whole reason a background world is affordable."""

    def test_one_long_wait_is_the_same_as_many_short_ones(self):
        """
        Where a stepped model would differ, because it accumulates the error of every step
        it took. This one has no steps to accumulate.

        """
        passage = Passage(route=LEGS, speed=10.0, departed=0.0)
        straight_through = along(passage, now=150.0).position
        watched = [along(passage, now=float(second)) for second in range(0, 151)]
        self.assertAlmostEqual(watched[-1].position.x, straight_through.x, places=6)

    def test_and_it_costs_the_same_either_way(self):
        passage = Passage(route=LEGS, speed=10.0, departed=0.0)

        started = time.perf_counter()
        for _ in range(1000):
            along(passage, now=150.0)
        recent = time.perf_counter() - started

        started = time.perf_counter()
        for _ in range(1000):
            along(passage, now=150.0 + 7 * 24 * 3600.0)
        stale = time.perf_counter() - started

        self.assertLess(stale, max(recent, 1e-6) * 10.0)


class TestTheFleet(BaseEvenniaTest):
    """A dict, deliberately - the expensive part was the ticks, and there are none."""

    def setUp(self):
        super().setUp()
        self.fleet = Fleet()
        self.record = StrategicVessel(key="Gull", passage=Passage(route=LEGS, speed=10.0))

    def test_a_ship_can_enter_the_background(self):
        handle = self.fleet.enter(self.record)
        self.assertIs(self.fleet.get(handle), self.record)

    def test_and_leave_it(self):
        handle = self.fleet.enter(self.record)
        self.assertIs(self.fleet.leave(handle), self.record)
        self.assertIsNone(self.fleet.get(handle))

    def test_leaving_twice_is_not_an_error(self):
        handle = self.fleet.enter(self.record)
        self.fleet.leave(handle)
        self.assertIsNone(self.fleet.leave(handle))

    def test_two_ships_get_two_handles(self):
        self.assertNotEqual(self.fleet.enter(self.record), self.fleet.enter(self.record))

    def test_a_handle_is_not_reused_after_she_leaves(self):
        """
        Otherwise a stale reference to a ship that has gone quietly becomes a reference to
        a different ship, which is the worst kind of bug to be handed.

        """
        first = self.fleet.enter(self.record)
        self.fleet.leave(first)
        self.assertNotEqual(self.fleet.enter(self.record), first)

    def test_the_whole_background_world_is_fixed_in_one_pass(self):
        for _ in range(5):
            self.fleet.enter(self.record)
        self.assertEqual(len(self.fleet.fixes(now=50.0)), 5)

    def test_the_ones_that_have_arrived_are_named(self):
        going = self.fleet.enter(self.record)
        there = self.fleet.enter(
            StrategicVessel(key="Tern", passage=Passage(route=Route(waypoints=(EAST,))))
        )
        arrived = self.fleet.arrived(now=50.0)
        self.assertIn(there, arrived)
        self.assertNotIn(going, arrived)

    def test_a_ship_can_be_sent_somewhere_else(self):
        handle = self.fleet.enter(self.record)
        back = Passage(route=Route(waypoints=(EAST, WEST)), speed=10.0)
        self.assertEqual(self.fleet.rerouted(handle, back).passage, back)

    def test_rerouting_a_ship_that_is_not_there_does_nothing(self):
        self.assertIsNone(self.fleet.rerouted(999, Passage(route=LEGS)))

    def test_rerouting_leaves_the_rest_of_her_alone(self):
        """Identity is preserved. She is the same ship going somewhere else."""
        handle = self.fleet.enter(self.record)
        after = self.fleet.rerouted(handle, Passage(route=Route(waypoints=(EAST, WEST))))
        self.assertEqual(after.key, self.record.key)

    def test_the_process_wide_one_is_the_same_one_every_time(self):
        self.assertIs(fleet(), fleet())


class TestABackgroundWorldIsAffordable(BaseEvenniaTest):
    """The benchmark the phase asked for: 100, 500 and 1000."""

    def fill(self, how_many):
        crowd = Fleet()
        for number in range(how_many):
            crowd.enter(
                StrategicVessel(
                    key=f"Hull {number}", passage=Passage(route=LEGS, speed=1.0 + number % 7)
                )
            )
        return crowd

    def cost_of(self, how_many):
        crowd = self.fill(how_many)
        started = time.perf_counter()
        crowd.fixes(now=500.0)
        return time.perf_counter() - started

    def test_a_hundred_are_fixed_at_once(self):
        self.assertEqual(len(self.fill(100).fixes(now=500.0)), 100)

    def test_five_hundred_are_too(self):
        self.assertEqual(len(self.fill(500).fixes(now=500.0)), 500)

    def test_and_a_thousand(self):
        self.assertEqual(len(self.fill(1000).fixes(now=500.0)), 1000)

    def test_the_cost_is_linear_in_the_fleet_and_not_worse(self):
        """
        Measured rather than asserted. Ten times the ships should be about ten times the
        work; anything that grew faster would be an index or a scan somebody added, and the
        point of the strategic state is that there is neither.

        """
        hundred = min(self.cost_of(100) for _ in range(3))
        thousand = min(self.cost_of(1000) for _ in range(3))
        self.assertLess(thousand, max(hundred, 1e-6) * 40.0)

    def test_a_thousand_ships_a_week_stale_still_fix_at_once(self):
        crowd = self.fill(1000)
        started = time.perf_counter()
        crowd.fixes(now=7 * 24 * 3600.0)
        self.assertLess(time.perf_counter() - started, 1.0)


class HullTestCase(BaseEvenniaTest):
    """A real hull that might be summarised."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Kestrel")
        self.hull.length, self.hull.beam = 24.0, 7.0
        self.hull.motion_limits = MotionLimits(max_speed=6.0, acceleration=0.5, turn_rate=5.0)
        self.hull.maritime_position = WEST.position
        self.hull.heading = 90.0
        self.deck = create.create_object(ShipRoom, key="Deck")
        self.deck.vessel = self.hull
        self.deck.exposure = OPEN


class TestWhatCannotBeSummarised(HullTestCase):
    """The guard that makes the two states safe to have."""

    def test_an_empty_hull_is_not_individual(self):
        self.assertFalse(is_individual(self.hull))

    def test_somebody_aboard_makes_her_individual(self):
        create.create_object(
            "evennia.objects.objects.DefaultCharacter", key="A hand", location=self.deck
        )
        self.assertTrue(is_individual(self.hull))

    def test_and_so_does_a_chest_in_the_cabin(self):
        """
        Not just people. A game that let a player leave a coil of rope on deck has let them
        leave something, and this contrib does not get to decide it was not worth keeping.

        """
        create.create_object(
            "evennia.objects.objects.DefaultObject", key="a chest", location=self.deck
        )
        self.assertTrue(is_individual(self.hull))

    def test_a_gangway_does_not(self):
        """An exit is part of how she is built, not something somebody left aboard."""
        create.create_object(
            "evennia.objects.objects.DefaultExit",
            key="gangway",
            location=self.deck,
            destination=self.deck,
        )
        self.assertFalse(is_individual(self.hull))

    def test_an_occupied_hull_is_refused_rather_than_truncated(self):
        create.create_object(
            "evennia.objects.objects.DefaultCharacter", key="A hand", location=self.deck
        )
        self.hull.route = LEGS
        self.assertEqual(summarise(self.hull).code, OCCUPIED)

    def test_something_that_is_not_a_hull_at_all_is_refused(self):
        thing = create.create_object("evennia.objects.objects.DefaultObject", key="a cask")
        self.assertEqual(summarise(thing).code, NOT_A_HULL)

    def test_a_hull_going_nowhere_cannot_be_summarised_by_her_route(self):
        self.assertEqual(summarise(self.hull).code, NO_ROUTE)

    def test_but_she_can_be_given_one(self):
        self.assertTrue(summarise(self.hull, passage=Passage(route=LEGS)))


class TestSummarising(HullTestCase):
    """What a record carries, and what it is careful not to."""

    def test_a_clear_hull_becomes_a_record(self):
        self.hull.route = LEGS
        self.assertTrue(summarise(self.hull))

    def test_the_record_keeps_her_name(self):
        self.assertEqual(summarise(self.hull, Passage(route=LEGS)).record.key, "Kestrel")

    def test_and_her_dimensions(self):
        record = summarise(self.hull, Passage(route=LEGS)).record
        self.assertAlmostEqual(record.length, 24.0)
        self.assertAlmostEqual(record.beam, 7.0)

    def test_a_record_holds_no_live_objects(self):
        """
        Everything on it is a plain value, which is why it survives a reload and pickles
        into an attribute. The moment it needed a reference, she would belong in the dormant
        state instead.

        """
        import pickle

        record = summarise(self.hull, Passage(route=LEGS)).record
        self.assertEqual(pickle.loads(pickle.dumps(record)), record)


class TestMaterialising(HullTestCase):
    """Identity is preserved: she comes back as herself, where the arithmetic put her."""

    def test_a_record_becomes_a_hull_again(self):
        record = summarise(self.hull, Passage(route=LEGS, speed=10.0)).record
        back = materialise(record, now=0.0)
        self.assertEqual(back.key, "Kestrel")

    def test_with_the_dimensions_she_went_away_with(self):
        record = summarise(self.hull, Passage(route=LEGS, speed=10.0)).record
        back = materialise(record, now=0.0)
        self.assertAlmostEqual(back.length, 24.0)
        self.assertAlmostEqual(back.beam, 7.0)

    def test_and_at_the_place_she_sailed_to(self):
        """
        Not at the place she left. She was on passage the whole time she was a record, and
        coming back where she started would be a ship that lost a week.

        """
        record = summarise(self.hull, Passage(route=LEGS, speed=10.0, departed=0.0)).record
        back = materialise(record, now=50.0)
        self.assertAlmostEqual(back.maritime_position.x, 500.0, places=3)

    def test_she_is_still_steering_her_passage(self):
        record = summarise(self.hull, Passage(route=LEGS, speed=10.0)).record
        back = materialise(record, now=50.0)
        self.assertAlmostEqual(back.heading, 90.0, places=3)

    def test_and_still_has_her_route_to_finish(self):
        record = summarise(self.hull, Passage(route=LEGS, speed=10.0)).record
        self.assertEqual(materialise(record, now=50.0).route, LEGS)

    def test_a_round_trip_puts_her_back_where_she_was(self):
        record = summarise(self.hull, Passage(route=LEGS, speed=10.0, departed=0.0)).record
        back = materialise(record, now=0.0)
        self.assertEqual(back.maritime_position, self.hull.maritime_position)
