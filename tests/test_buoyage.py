"""
Tests for what a mark means, and for the two invariants a marked coast has to satisfy.

"""

from evennia.utils.test_resources import BaseEvenniaTest

from ..buoyage import (
    BERTH_FACTOR,
    DANGER_KINDS,
    EAST_CARDINAL,
    EITHER,
    ISOLATED_DANGER,
    KINDS,
    MARKING_RANGE,
    MINIMUM_BERTH,
    NORTH_CARDINAL,
    PORT,
    PORT_HAND,
    SAFE_WATER,
    SOUTH_CARDINAL,
    SPECIAL,
    STARBOARD,
    STARBOARD_HAND,
    WEST_CARDINAL,
    Buoyage,
    berth_for,
    keep_clear,
    leave_to,
    marks_danger,
    safe_water_from,
    unmarked_dangers,
    unreachable_berths,
)
from ..charts import Chart
from ..position import WorldPosition
from ..routes import NavigationNetwork, Waypoint
from ..tiles import Hazard

INWARD = Buoyage(direction=90.0)


def a_rock(key="the Whaleback", x=3200.0, y=0.0, radius=40.0):
    """
    Returns:
        hazard (Hazard): Something on the bottom to be marked or not.

    """
    return Hazard(key=key, x=x, y=y, radius=radius, top_z=-1.5, bottom="rock")


def a_chart(west=0.0, east=10000.0, south=-5000.0, north=5000.0):
    """
    Returns:
        chart (Chart): A surveyed rectangle.

    """
    return Chart(key="approaches", west=west, east=east, south=south, north=north)


class TestWhatAMarkMeans(BaseEvenniaTest):
    """The meaning is the whole reason a mark is worth laying."""

    def test_a_cardinal_says_which_way_the_safe_water_lies(self):
        self.assertAlmostEqual(safe_water_from(NORTH_CARDINAL), 0.0)
        self.assertAlmostEqual(safe_water_from(EAST_CARDINAL), 90.0)
        self.assertAlmostEqual(safe_water_from(SOUTH_CARDINAL), 180.0)
        self.assertAlmostEqual(safe_water_from(WEST_CARDINAL), 270.0)

    def test_other_marks_do_not(self):
        """A safe-water mark says the channel is here, not where a rock is."""
        self.assertIsNone(safe_water_from(SAFE_WATER))
        self.assertIsNone(safe_water_from(PORT_HAND))
        self.assertIsNone(safe_water_from(ISOLATED_DANGER))

    def test_the_marks_that_warn_are_the_ones_that_warn(self):
        self.assertTrue(marks_danger(ISOLATED_DANGER))
        self.assertTrue(marks_danger(SOUTH_CARDINAL))
        self.assertFalse(marks_danger(SAFE_WATER))
        self.assertFalse(marks_danger(PORT_HAND))
        self.assertFalse(marks_danger(SPECIAL))

    def test_every_kind_is_accounted_for(self):
        for kind in KINDS:
            self.assertIsInstance(marks_danger(kind), bool)

    def test_a_danger_kind_is_a_kind(self):
        for kind in DANGER_KINDS:
            self.assertIn(kind, KINDS)


class TestWhichSideToLeaveIt(BaseEvenniaTest):
    """Laterals, and the part everybody gets wrong."""

    def test_a_port_hand_mark_is_left_to_port_going_in(self):
        self.assertEqual(leave_to(PORT_HAND, 90.0, INWARD), PORT)

    def test_and_a_starboard_hand_mark_to_starboard(self):
        self.assertEqual(leave_to(STARBOARD_HAND, 90.0, INWARD), STARBOARD)

    def test_they_swap_coming_out(self):
        """
        It marks the same edge of the same channel either way. The vessel turned
        round; the buoy did not.

        """
        self.assertEqual(leave_to(PORT_HAND, 270.0, INWARD), STARBOARD)
        self.assertEqual(leave_to(STARBOARD_HAND, 270.0, INWARD), PORT)

    def test_a_beating_vessel_does_not_change_her_mind_on_every_tack(self):
        """
        Working up a channel she heads well off the direction of buoyage on each
        board. If the test were tight she would swap which side of the channel she
        believed in twice a minute.

        """
        for heading in (45.0, 135.0):
            self.assertEqual(leave_to(PORT_HAND, heading, INWARD), PORT)

    def test_safe_water_may_be_passed_either_side(self):
        self.assertEqual(leave_to(SAFE_WATER, 90.0, INWARD), EITHER)

    def test_a_lateral_mark_means_nothing_without_a_direction_of_buoyage(self):
        """
        Which side to leave it depends entirely on which way a harbour considers
        "in", and no algorithm can work that out.

        """
        self.assertEqual(leave_to(PORT_HAND, 90.0, None), EITHER)

    def test_a_cardinal_is_not_a_lateral(self):
        self.assertEqual(leave_to(SOUTH_CARDINAL, 90.0, INWARD), EITHER)


class TestBerth(BaseEvenniaTest):
    """Sea-room, in the sense the word already had."""

    def test_a_bigger_danger_wants_more_room(self):
        self.assertGreater(berth_for(500.0), berth_for(200.0))

    def test_it_scales_with_the_danger(self):
        self.assertAlmostEqual(berth_for(500.0), 500.0 * BERTH_FACTOR)

    def test_a_rock_with_no_size_still_wants_room(self):
        """A rock the size of a cart wants a cable's room round it."""
        self.assertAlmostEqual(berth_for(0.0), MINIMUM_BERTH)

    def test_the_floor_only_ever_raises(self):
        self.assertGreaterEqual(berth_for(1.0), MINIMUM_BERTH)


class TestUnmarkedDangers(BaseEvenniaTest):
    """The invariant with teeth."""

    def test_a_charted_rock_with_nothing_on_it_is_reported(self):
        rock = a_rock()
        self.assertEqual(unmarked_dangers([rock], (), [a_chart()]), (rock,))

    def test_a_beacon_on_it_settles_the_matter(self):
        rock = a_rock()
        beacon = Waypoint("whaleback beacon", WorldPosition(3200.0, 100.0), ISOLATED_DANGER)
        self.assertEqual(unmarked_dangers([rock], (beacon,), [a_chart()]), ())

    def test_a_cardinal_laid_well_off_it_does_not(self):
        """
        A mark a mile away is not marking this rock. It may be marking something
        else entirely, which is exactly why distance has to count.

        """
        rock = a_rock()
        far = Waypoint("south cardinal", WorldPosition(3200.0, -1200.0), SOUTH_CARDINAL)
        self.assertEqual(unmarked_dangers([rock], (far,), [a_chart()]), (rock,))

    def test_a_cardinal_close_enough_does(self):
        rock = a_rock()
        near = Waypoint("south cardinal", WorldPosition(3200.0, -300.0), SOUTH_CARDINAL)
        self.assertEqual(unmarked_dangers([rock], (near,), [a_chart()]), ())

    def test_a_mark_that_does_not_warn_does_not_count(self):
        """A safe-water mark says the channel is here, not that there is a rock."""
        rock = a_rock()
        fairway = Waypoint("fairway buoy", WorldPosition(3200.0, 50.0), SAFE_WATER)
        self.assertEqual(unmarked_dangers([rock], (fairway,), [a_chart()]), (rock,))

    def test_an_unsurveyed_rock_is_nobody_s_negligence(self):
        """
        The load-bearing distinction. An unmarked rock in surveyed water is
        negligence; an unmarked rock in unsurveyed water is just the sea, and a
        system that reported it would make charts pointless and exploring safe.

        """
        outer = a_rock(key="outer shoal", x=90000.0)
        self.assertEqual(unmarked_dangers([outer], (), [a_chart()]), ())

    def test_a_world_with_no_charts_at_all_reports_nothing(self):
        self.assertEqual(unmarked_dangers([a_rock()], (), []), ())

    def test_several_are_all_reported(self):
        one, two = a_rock(key="one"), a_rock(key="two", y=900.0)
        self.assertEqual(unmarked_dangers([one, two], (), [a_chart()]), (one, two))

    def test_the_reach_is_tunable(self):
        rock = a_rock()
        mark = Waypoint("cardinal", WorldPosition(3200.0, MARKING_RANGE + 100.0), SOUTH_CARDINAL)
        self.assertEqual(unmarked_dangers([rock], (mark,), [a_chart()]), (rock,))
        self.assertEqual(
            unmarked_dangers([rock], (mark,), [a_chart()], reach=MARKING_RANGE + 200.0), ()
        )


class TestUnreachableBerths(BaseEvenniaTest):
    """Every dock has at least one marked approach, or the test goes red."""

    def a_coast(self):
        """
        Returns:
            network (NavigationNetwork): Open water, a fairway, and two berths - one
                of them connected to the fairway and one of them not.

        """
        network = NavigationNetwork()
        for key, x, y in (
            ("offing", 0.0, 0.0),
            ("fairway buoy", 1000.0, 0.0),
            ("stone quay", 2000.0, 0.0),
            ("smugglers cove", 2000.0, 3000.0),
        ):
            network.add(Waypoint(key, WorldPosition(x, y)))
        network.link("offing", "fairway buoy")
        network.link("fairway buoy", "stone quay")
        return network

    def test_a_berth_with_a_marked_approach_passes(self):
        self.assertEqual(unreachable_berths(self.a_coast(), ["stone quay"], ["offing"]), ())

    def test_a_berth_with_none_is_reported(self):
        self.assertEqual(
            unreachable_berths(self.a_coast(), ["smugglers cove"], ["offing"]),
            ("smugglers cove",),
        )

    def test_one_good_approach_is_enough(self):
        """
        A harbour with a single buoyed channel and foul ground all round it is a
        real harbour, not a broken one.

        """
        network = self.a_coast()
        network.add(Waypoint("northern offing", WorldPosition(0.0, 4000.0)))
        approaches = ["offing", "northern offing"]
        self.assertEqual(unreachable_berths(network, ["stone quay"], approaches), ())

    def test_every_berth_is_checked(self):
        stranded = unreachable_berths(self.a_coast(), ["stone quay", "smugglers cove"], ["offing"])
        self.assertEqual(stranded, ("smugglers cove",))

    def test_a_coast_with_no_way_in_strands_everything(self):
        self.assertEqual(unreachable_berths(self.a_coast(), ["stone quay"], []), ("stone quay",))


class TestAMarkCarriesItsMeaning(BaseEvenniaTest):
    """The join between buoyage and the marks the navigator already had."""

    def test_a_mark_without_a_kind_makes_no_claims(self):
        """
        Safe water is the honest default: it says "the channel is here" and nothing
        more, so a world that has not thought about buoyage gets marks that make no
        claims rather than marks that make wrong ones.

        """
        self.assertEqual(Waypoint("fairway", WorldPosition(0.0, 0.0)).kind, SAFE_WATER)

    def test_a_mark_can_be_told_what_it_is(self):
        mark = Waypoint("the Whaleback", WorldPosition(0.0, 0.0), ISOLATED_DANGER)
        self.assertTrue(marks_danger(mark.kind))

    def test_marks_still_plan_routes(self):
        """Giving them meaning must not stop them being places worth going by."""
        network = NavigationNetwork()
        network.add(Waypoint("one", WorldPosition(0.0, 0.0), SAFE_WATER))
        network.add(Waypoint("two", WorldPosition(1000.0, 0.0), PORT_HAND))
        network.link("one", "two")
        self.assertTrue(network.plan("one", "two"))


class TestKeepingClear(BaseEvenniaTest):
    """
    What a helmsman does about a marked danger.

    The cardinals were built inverted first time - a south cardinal sent her north,
    straight over the rock the mark exists to warn of - and every unit test of the
    surrounding machinery passed. These are the tests that would have caught it.

    """

    HERE = WorldPosition(0.0, 0.0)
    EAST = 90.0

    def a_mark(self, kind, x=1000.0, y=0.0):
        """
        Returns:
            mark (Waypoint): A mark of that kind, at that place.

        """
        return Waypoint(kind, WorldPosition(x, y), kind)

    def steering(self, mark, heading=None, berth=200.0):
        """
        Returns:
            clearance (Clearance): What she decided.

        """
        return keep_clear(self.HERE, self.EAST if heading is None else heading, [mark], berth=berth)

    def test_a_south_cardinal_sends_her_south_of_it(self):
        """Safe water lies south of a south cardinal. She comes round to starboard."""
        self.assertGreater(self.steering(self.a_mark(SOUTH_CARDINAL)).heading, self.EAST)

    def test_a_north_cardinal_sends_her_north_of_it(self):
        self.assertLess(self.steering(self.a_mark(NORTH_CARDINAL)).heading, self.EAST)

    def test_the_mark_decides_the_side_even_when_it_costs_more(self):
        """
        The whole point of a cardinal is that the cheaper-looking way round is the
        one with the rock in it. A mark lying a little to starboard of her track
        would be cheapest to pass to port of - and a north cardinal still sends her
        the other way.

        """
        mark = self.a_mark(NORTH_CARDINAL, y=-60.0)
        self.assertLess(self.steering(mark).heading, self.EAST)

    def test_an_isolated_danger_is_passed_the_cheaper_way(self):
        """Deep water all round is what the mark means, so she turns away from it."""
        to_port = self.a_mark(ISOLATED_DANGER, y=30.0)
        to_starboard = self.a_mark(ISOLATED_DANGER, y=-30.0)
        self.assertGreater(self.steering(to_port).heading, self.EAST)
        self.assertLess(self.steering(to_starboard).heading, self.EAST)

    def test_a_cardinal_pointing_along_the_line_of_sight_still_decides(self):
        """
        An east cardinal seen from due west says the safe water is beyond it, which
        names no side at all. She has to do something, so she does the same thing
        every time rather than dithering.

        """
        first = self.steering(self.a_mark(EAST_CARDINAL)).heading
        second = self.steering(self.a_mark(EAST_CARDINAL)).heading
        self.assertAlmostEqual(first, second)

    def test_she_does_not_steer_round_a_fairway_buoy(self):
        """That is what a fairway buoy is for."""
        clearance = self.steering(self.a_mark(SAFE_WATER))
        self.assertAlmostEqual(clearance.heading, self.EAST)
        self.assertIsNone(clearance.mark)

    def test_nor_round_a_special_mark(self):
        self.assertAlmostEqual(self.steering(self.a_mark(SPECIAL)).heading, self.EAST)

    def test_a_danger_already_clear_is_left_alone(self):
        mark = self.a_mark(SOUTH_CARDINAL, y=-900.0)
        self.assertAlmostEqual(self.steering(mark).heading, self.EAST)

    def test_a_danger_abaft_the_beam_is_behind_her(self):
        """A helmsman who kept altering for what he had passed would sail in circles."""
        mark = self.a_mark(SOUTH_CARDINAL, x=-500.0)
        self.assertAlmostEqual(self.steering(mark).heading, self.EAST)

    def test_a_danger_beyond_the_horizon_of_care_is_ignored(self):
        mark = self.a_mark(SOUTH_CARDINAL, x=99000.0)
        self.assertAlmostEqual(self.steering(mark).heading, self.EAST)

    def test_the_alteration_shrinks_with_distance(self):
        """
        An early alteration is a small one, which is how a helmsman actually behaves
        and why standing on until the last moment costs you.

        """
        near = self.steering(self.a_mark(SOUTH_CARDINAL, x=400.0)).altered
        far = self.steering(self.a_mark(SOUTH_CARDINAL, x=2000.0)).altered
        self.assertGreater(near, far)

    def test_a_wider_berth_is_a_bigger_alteration(self):
        mark = self.a_mark(SOUTH_CARDINAL)
        self.assertGreater(
            self.steering(mark, berth=400.0).altered, self.steering(mark, berth=100.0).altered
        )

    def test_she_clears_it_by_the_berth_she_was_given(self):
        """The arithmetic has to actually produce the clearance it promises."""
        import math

        berth = 250.0
        mark = self.a_mark(SOUTH_CARDINAL)
        clearance = self.steering(mark, berth=berth)
        offset = math.radians(abs(clearance.heading - 90.0))
        self.assertAlmostEqual(1000.0 * math.sin(offset), berth, delta=1.0)

    def test_the_most_pressing_danger_wins(self):
        """Two marks, and the one that needs the bigger alteration is obeyed."""
        far = self.a_mark(SOUTH_CARDINAL, x=2200.0)
        near = self.a_mark(SOUTH_CARDINAL, x=500.0)
        both = keep_clear(self.HERE, self.EAST, [far, near], berth=200.0)
        self.assertEqual(both.mark, near)

    def test_it_reports_what_forced_the_alteration(self):
        """A helmsman who altered course should be able to say why."""
        clearance = self.steering(self.a_mark(SOUTH_CARDINAL))
        self.assertIsNotNone(clearance.mark)
        self.assertGreater(clearance.altered, 0.0)

    def test_clear_water_alters_nothing_and_blames_nobody(self):
        clearance = keep_clear(self.HERE, self.EAST, [], berth=200.0)
        self.assertAlmostEqual(clearance.heading, self.EAST)
        self.assertIsNone(clearance.mark)
        self.assertAlmostEqual(clearance.altered, 0.0)
