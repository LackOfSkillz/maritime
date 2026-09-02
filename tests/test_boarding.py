"""
Tests for boarding: the irons, the crossing, and whether the lines hold.

"""

from evennia.utils import create
from evennia.utils.test_resources import (
    BaseEvenniaCommandTest,
    BaseEvenniaTest,
    BaseEvenniaTestCase,
)

from ..boarding import (
    MOST_LINES,
    alongside,
    holding_closure,
    lines_across,
    unfouling_time,
    ALREADY_GRAPPLED,
    CLOSING_TOO_FAST,
    GRAPNEL_RANGE,
    LINES_PARTED,
    MAX_BOARDING_CLOSURE,
    MAX_HOLDING_CLOSURE,
    NO_DECK,
    SAME_VESSEL,
    TOO_FAR,
    bears_alongside,
    can_grapple,
    relative_speed,
    still_holding,
    velocity,
    within_reach,
)
from ..commands import CmdCutGrapples, CmdGrapple, CmdGrapples, CmdStrike
from ..motion import MotionLimits
from ..crew import ABLE, PRESSED
from ..position import WorldPosition
from ..rooms import ShipRoom
from ..traffic import traffic
from ..typeclasses import Vessel
from ..vessel import BELOW_WATERLINE, OPEN
from .base import EmptySeaMixin

HERE = WorldPosition(0.0, 0.0)
ALONGSIDE = WorldPosition(15.0, 0.0)
FAR = WorldPosition(400.0, 0.0)


class TestVelocity(BaseEvenniaTestCase):
    """Motion as components, so two of them can be subtracted."""

    def test_north_is_positive_northing(self):
        east, north = velocity(0.0, 5.0)
        self.assertAlmostEqual(east, 0.0)
        self.assertAlmostEqual(north, 5.0)

    def test_east_is_positive_easting(self):
        east, north = velocity(90.0, 5.0)
        self.assertAlmostEqual(east, 5.0)
        self.assertAlmostEqual(north, 0.0, places=6)

    def test_stopped_is_nothing(self):
        self.assertEqual(velocity(123.0, 0.0), (0.0, 0.0))


class TestRelativeSpeed(BaseEvenniaTestCase):
    """
    The number the whole of boarding turns on, and it is not either ship's speed.

    """

    def test_two_ships_matched_are_motionless_to_each_other(self):
        """Ten knots each, side by side, and they can be lashed at leisure."""
        self.assertAlmostEqual(relative_speed(90.0, 5.0, 90.0, 5.0), 0.0)

    def test_however_fast_they_are_both_going(self):
        self.assertAlmostEqual(relative_speed(45.0, 12.0, 45.0, 12.0), 0.0)

    def test_opposing_courses_add_up(self):
        self.assertAlmostEqual(relative_speed(90.0, 2.0, 270.0, 2.0), 4.0)

    def test_one_stopped_is_the_other_speed(self):
        self.assertAlmostEqual(relative_speed(90.0, 3.0, 0.0, 0.0), 3.0)

    def test_a_difference_in_speed_alone(self):
        self.assertAlmostEqual(relative_speed(90.0, 5.0, 90.0, 3.0), 2.0)

    def test_it_is_symmetric(self):
        self.assertAlmostEqual(
            relative_speed(30.0, 4.0, 200.0, 2.0), relative_speed(200.0, 2.0, 30.0, 4.0)
        )

    def test_a_right_angle(self):
        self.assertAlmostEqual(relative_speed(0.0, 3.0, 90.0, 4.0), 5.0)


class TestReach(BaseEvenniaTestCase):
    """How far a man can throw an iron."""

    def test_alongside_is_within_reach(self):
        self.assertTrue(within_reach(HERE, ALONGSIDE))

    def test_a_cable_off_is_not(self):
        self.assertFalse(within_reach(HERE, FAR))

    def test_exactly_at_the_limit_carries(self):
        self.assertTrue(within_reach(HERE, WorldPosition(GRAPNEL_RANGE, 0.0)))


class TestCanGrapple(BaseEvenniaTestCase):
    """Whether the irons will go across."""

    def test_alongside_and_matched(self):
        self.assertTrue(can_grapple(HERE, 90.0, 4.0, ALONGSIDE, 90.0, 4.0))

    def test_too_far_off(self):
        result = can_grapple(HERE, 90.0, 0.0, FAR, 90.0, 0.0)
        self.assertFalse(result)
        self.assertEqual(result.code, TOO_FAR)

    def test_alongside_but_going_by(self):
        result = can_grapple(HERE, 90.0, 4.0, ALONGSIDE, 270.0, 4.0)
        self.assertFalse(result)
        self.assertEqual(result.code, CLOSING_TOO_FAST)

    def test_range_is_reported_before_closure(self):
        """A ship a mile off is not closing too fast, she is a mile off."""
        result = can_grapple(HERE, 90.0, 5.0, FAR, 270.0, 5.0)
        self.assertEqual(result.code, TOO_FAR)

    def test_it_carries_both_numbers_either_way(self):
        result = can_grapple(HERE, 90.0, 4.0, ALONGSIDE, 270.0, 4.0)
        self.assertAlmostEqual(result.distance, 15.0)
        self.assertAlmostEqual(result.closure, 8.0)

    def test_the_limit_itself_holds(self):
        self.assertTrue(can_grapple(HERE, 90.0, MAX_BOARDING_CLOSURE, ALONGSIDE, 90.0, 0.0))


class TestStillHolding(BaseEvenniaTestCase):
    """Lines already made up have more purchase than thrown ones."""

    def test_a_made_up_line_takes_more_than_a_thrown_one(self):
        sheering = MAX_BOARDING_CLOSURE + 0.5
        self.assertFalse(can_grapple(HERE, 90.0, sheering, ALONGSIDE, 90.0, 0.0))
        self.assertTrue(still_holding(HERE, 90.0, sheering, ALONGSIDE, 90.0, 0.0))

    def test_but_a_hard_sheer_always_breaks_free(self):
        result = still_holding(HERE, 90.0, MAX_HOLDING_CLOSURE + 1.0, ALONGSIDE, 90.0, 0.0)
        self.assertFalse(result)
        self.assertEqual(result.code, LINES_PARTED)

    def test_drawing_out_of_reach_parts_them_too(self):
        result = still_holding(HERE, 90.0, 0.0, FAR, 90.0, 0.0)
        self.assertFalse(result)
        self.assertEqual(result.code, LINES_PARTED)


class TestBearing(BaseEvenniaTestCase):
    """Advisory, not a rule."""

    def test_on_the_beam_is_alongside(self):
        self.assertTrue(bears_alongside(0.0, HERE, WorldPosition(20.0, 0.0)))

    def test_dead_ahead_is_a_collision(self):
        self.assertFalse(bears_alongside(0.0, HERE, WorldPosition(0.0, 20.0)))

    def test_dead_astern_is_not_alongside_either(self):
        self.assertFalse(bears_alongside(0.0, HERE, WorldPosition(0.0, -20.0)))


class BoardingTestCase(EmptySeaMixin, BaseEvenniaTest):
    """Two hulls, each with a weather deck."""

    def setUp(self):
        super().setUp()
        self.ours = self.a_ship("Kestrel", HERE)
        self.theirs = self.a_ship("Petrel", ALONGSIDE)

    def a_ship(self, key, position):
        hull = create.create_object(Vessel, key=key)
        hull.length, hull.beam = 18.0, 5.4
        hull.motion_limits = MotionLimits(max_speed=6.0, acceleration=0.5, turn_rate=5.0)
        hull.maritime_position = position
        hull.heading = 90.0
        deck = create.create_object(ShipRoom, key=f"{key} Deck")
        deck.vessel = hull
        deck.exposure = OPEN
        traffic().note(hull, position)
        return hull


class TestGrappling(BoardingTestCase):
    """Getting the irons across, aboard a real hull."""

    def test_she_starts_free(self):
        self.assertFalse(self.ours.grappled)

    def test_matched_and_alongside_holds(self):
        self.assertTrue(self.ours.grapple(self.theirs))
        self.assertTrue(self.ours.grappled)

    def test_both_hulls_know_about_it(self):
        """A one-sided attachment is the first symptom of a much worse bug."""
        self.ours.grapple(self.theirs)
        self.assertEqual(self.theirs.grappled_to, self.ours)

    def test_it_rigs_a_crossing(self):
        self.ours.grapple(self.theirs)
        deck = self.ours.boarding_deck
        crossings = [obj for obj in deck.contents if obj.destination]
        self.assertEqual(len(crossings), 1)
        self.assertEqual(crossings[0].destination, self.theirs.boarding_deck)

    def test_the_crossing_goes_both_ways(self):
        """The grapples are her way across too."""
        self.ours.grapple(self.theirs)
        back = [obj for obj in self.theirs.boarding_deck.contents if obj.destination]
        self.assertEqual(back[0].destination, self.ours.boarding_deck)

    def test_a_ship_going_by_is_refused(self):
        self.theirs.heading = 270.0
        self.theirs.ndb.speed = 4.0
        self.ours.ndb.speed = 4.0
        result = self.ours.grapple(self.theirs)
        self.assertEqual(result.code, CLOSING_TOO_FAST)

    def test_a_refusal_rigs_nothing(self):
        """A refused boarding must not leave an exit anybody can walk through."""
        self.theirs.maritime_position = FAR
        self.ours.grapple(self.theirs)
        self.assertEqual([obj for obj in self.ours.boarding_deck.contents if obj.destination], [])

    def test_you_cannot_board_your_own_ship(self):
        self.assertEqual(self.ours.grapple(self.ours).code, SAME_VESSEL)

    def test_a_hull_already_fast_refuses(self):
        third = self.a_ship("Fulmar", WorldPosition(10.0, 5.0))
        self.ours.grapple(self.theirs)
        self.assertEqual(third.grapple(self.theirs).code, ALREADY_GRAPPLED)

    def test_a_hull_with_no_open_deck_cannot_be_boarded(self):
        """You board onto a deck, never into a hold."""
        hold = create.create_object(ShipRoom, key="Sealed Hold")
        sealed = create.create_object(Vessel, key="Coffin")
        sealed.maritime_position = ALONGSIDE
        hold.vessel = sealed
        hold.exposure = BELOW_WATERLINE
        self.assertEqual(self.ours.grapple(sealed).code, NO_DECK)

    def test_the_party_lands_on_the_highest_weather_deck(self):
        top = create.create_object(ShipRoom, key="Petrel Top")
        top.vessel = self.theirs
        top.exposure = OPEN
        top.deck_level = 3
        self.assertEqual(self.theirs.boarding_deck, top)


class TestCuttingThem(BoardingTestCase):
    """Letting her go."""

    def test_it_frees_both(self):
        self.ours.grapple(self.theirs)
        self.assertTrue(self.ours.cast_off_grapples())
        self.assertFalse(self.ours.grappled)
        self.assertFalse(self.theirs.grappled)

    def test_the_crossing_goes_with_them(self):
        self.ours.grapple(self.theirs)
        self.ours.cast_off_grapples()
        for hull in (self.ours, self.theirs):
            self.assertEqual([obj for obj in hull.boarding_deck.contents if obj.destination], [])

    def test_cutting_nothing_says_so(self):
        self.assertFalse(self.ours.cast_off_grapples())

    def test_either_ship_can_cut(self):
        self.ours.grapple(self.theirs)
        self.theirs.cast_off_grapples()
        self.assertFalse(self.ours.grappled)


class TestLinesParting(BoardingTestCase):
    """
    Re-tested as the hulls move, not granted once.

    Notes:
        A grapple that could never fail would make being boarded permanent. A
        ship that puts her helm hard over and fills her sails breaks free, and
        that is what makes being boarded survivable and worth trying to survive.

    """

    def test_a_matched_pair_hold(self):
        self.ours.grapple(self.theirs)
        self.assertTrue(self.ours.check_grapples())
        self.assertTrue(self.ours.grappled)

    def test_a_hard_sheer_breaks_free(self):
        self.ours.grapple(self.theirs)
        self.theirs.heading = 270.0
        self.theirs.ndb.speed = 4.0
        self.assertFalse(self.ours.check_grapples())
        self.assertFalse(self.ours.grappled)

    def test_and_takes_the_crossing_with_it(self):
        self.ours.grapple(self.theirs)
        self.theirs.ndb.speed = 6.0
        self.theirs.heading = 270.0
        self.ours.check_grapples()
        self.assertEqual([obj for obj in self.ours.boarding_deck.contents if obj.destination], [])

    def test_drawing_away_parts_them(self):
        self.ours.grapple(self.theirs)
        self.theirs.maritime_position = FAR
        self.assertFalse(self.ours.check_grapples())

    def test_a_free_hull_has_nothing_to_check(self):
        self.assertIsNone(self.ours.check_grapples())

    def test_the_tick_checks_them(self):
        """Which is what makes it happen at all, rather than only when asked."""
        self.ours.grapple(self.theirs)
        self.theirs.heading = 270.0
        self.theirs.ndb.speed = 5.0
        self.ours.at_maritime_tick(30.0)
        self.assertFalse(self.ours.grappled)


class TestStriking(BoardingTestCase):
    """A fact, and nothing more."""

    def test_she_starts_with_her_colours_up(self):
        self.assertFalse(self.theirs.struck)

    def test_striking_records_who_to(self):
        self.theirs.strike(self.ours)
        self.assertEqual(self.theirs.struck_to, self.ours)

    def test_striking_twice_changes_nothing(self):
        self.theirs.strike(self.ours)
        self.assertFalse(self.theirs.strike(self.ours))

    def test_colours_can_go_back_up(self):
        """A prize crew can be overwhelmed. A state only enterable is unusable."""
        self.theirs.strike(self.ours)
        self.assertTrue(self.theirs.rehoist())
        self.assertFalse(self.theirs.struck)

    def test_rehoisting_a_ship_that_never_struck(self):
        self.assertFalse(self.theirs.rehoist())

    def test_striking_confers_nothing(self):
        """
        What a captor may do with a prize is a question about authority, which
        this contrib deliberately does not answer. See `DECISIONS.md`.

        """
        self.theirs.strike(self.ours)
        self.assertIsNone(self.theirs.db.commanded_by)


class BoardingCommandTestCase(EmptySeaMixin, BaseEvenniaCommandTest):
    """Somebody on a deck with another ship alongside."""

    def setUp(self):
        super().setUp()
        self.ours = create.create_object(Vessel, key="Kestrel")
        self.ours.length, self.ours.beam = 18.0, 5.4
        self.ours.maritime_position = HERE
        self.ours.heading = 90.0
        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.deck.vessel = self.ours
        self.deck.exposure = OPEN
        self.deck.height_of_eye = 2.0
        self.char1.location = self.deck

        self.theirs = create.create_object(Vessel, key="Petrel")
        self.theirs.length, self.theirs.beam = 18.0, 5.4
        self.theirs.maritime_position = ALONGSIDE
        self.theirs.heading = 90.0
        their_deck = create.create_object(ShipRoom, key="Petrel Deck")
        their_deck.vessel = self.theirs
        their_deck.exposure = OPEN
        traffic().note(self.ours, HERE)
        traffic().note(self.theirs, ALONGSIDE)


class TestBoardingCommands(BoardingCommandTestCase):
    """The three verbs."""

    def test_grappling_a_ship_alongside(self):
        self.call(CmdGrapple(), "Petrel")
        self.assertTrue(self.ours.grappled)

    def test_the_order_is_spoken(self):
        self.call(CmdGrapple(), "Petrel", 'You call out, "Grapnels away')

    def test_a_ship_nobody_can_see(self):
        self.call(CmdGrapple(), "Albatross", "No ship of that name")

    def test_no_name_at_all(self):
        self.call(CmdGrapple(), "", "Usage:")

    def test_cutting_them(self):
        self.ours.grapple(self.theirs)
        self.call(CmdCutGrapples(), "")
        self.assertFalse(self.ours.grappled)

    def test_cutting_nothing(self):
        self.call(CmdCutGrapples(), "", "She is not fast to anything.")

    def test_striking_needs_somebody_alongside(self):
        self.call(CmdStrike(), "", "There is nobody alongside")

    def test_striking(self):
        self.ours.grapple(self.theirs)
        self.call(CmdStrike(), "")
        self.assertTrue(self.ours.struck)

    def test_striking_again_rehoists(self):
        self.ours.grapple(self.theirs)
        self.ours.strike(self.theirs)
        self.call(CmdStrike(), "")
        self.assertFalse(self.ours.struck)

    def test_the_report_when_free(self):
        self.call(CmdGrapples(), "", "She is not fast to anything.")

    def test_the_report_when_fast(self):
        self.ours.grapple(self.theirs)
        self.call(CmdGrapples(), "", "Kestrel - fast to the Petrel")

    def test_the_report_names_the_relative_speed(self):
        self.ours.grapple(self.theirs)
        self.assertIn("Relative speed", chr(10).join(self.ours.narrator.grapple_report(self.ours)))


class TestHowManyLinesGetAcross(BaseEvenniaTestCase):
    """
    Roadmap item L: grapples are a count, not a yes.

    Everything about being lashed to another ship follows from how many are fast - how hard
    she is to shake off, and how much of the two rails are close enough to fight across. The
    arithmetic is asserted as relationships, because the claim is "more contact means more
    lines" and not "this position yields seven".
    """

    def test_lying_alongside_gets_more_across_than_meeting_bow_to_bow(self):
        alongside_lines = lines_across(overlap=1.0, closure=0.0, hands=200.0)
        touching = lines_across(overlap=0.05, closure=0.0, hands=200.0)
        self.assertGreater(alongside_lines, touching)

    def test_a_hull_sheering_away_takes_the_irons_with_her(self):
        steady = lines_across(overlap=1.0, closure=0.0, hands=200.0)
        sheering = lines_across(overlap=1.0, closure=MAX_BOARDING_CLOSURE * 0.9, hands=200.0)
        self.assertGreater(steady, sheering)

    def test_a_short_handed_ship_gets_fewer_over(self):
        """Each line costs hands, so sixty fit men cannot work twenty of them."""
        full = lines_across(overlap=1.0, closure=0.0, hands=200.0)
        thin = lines_across(overlap=1.0, closure=0.0, hands=9.0)
        self.assertGreater(full, thin)
        self.assertEqual(thin, 3)

    def test_nobody_left_to_throw_them_gets_none(self):
        self.assertEqual(lines_across(overlap=1.0, closure=0.0, hands=0.0), 0)

    def test_it_never_exceeds_what_a_rail_has_room_for(self):
        self.assertLessEqual(lines_across(overlap=1.0, closure=0.0, hands=1e6), MOST_LINES)

    def test_more_lines_hold_harder(self):
        self.assertGreater(holding_closure(12), holding_closure(1))

    def test_but_not_twelve_times_harder(self):
        """
        Sub-linear on purpose. Breaking free has to stay possible, because it is what makes
        being boarded survivable and worth trying to survive.

        """
        self.assertLess(holding_closure(12), 3.0 * holding_closure(1))

    def test_one_line_holds_what_one_line_always_held(self):
        self.assertAlmostEqual(holding_closure(1), MAX_HOLDING_CLOSURE)


class TestHowMuchOfThemIsAlongside(BaseEvenniaTestCase):
    """`alongside`, which is the contact geometry the count is built on."""

    def setUp(self):
        super().setUp()
        self.her = WorldPosition(0.0, 0.0)

    def test_two_ships_level_and_parallel_share_their_whole_length(self):
        overlap = alongside(self.her.moved(90.0, 8.0), 0.0, 30.0, self.her, 0.0, 30.0)
        self.assertAlmostEqual(overlap, 1.0, places=6)

    def test_bow_to_bow_shares_almost_nothing(self):
        overlap = alongside(self.her.moved(180.0, 30.0), 0.0, 30.0, self.her, 180.0, 30.0)
        self.assertLess(overlap, 0.05)

    def test_half_a_length_out_shares_half_of_her(self):
        overlap = alongside(self.her.moved(0.0, 15.0), 0.0, 30.0, self.her, 0.0, 30.0)
        self.assertAlmostEqual(overlap, 0.5, places=6)

    def test_a_boat_alongside_a_ship_is_entirely_alongside_her(self):
        """
        The shorter hull is the divisor: it is the boat's rail that runs out of places to
        make a line fast, not the ship's.

        """
        overlap = alongside(self.her.moved(90.0, 6.0), 0.0, 6.0, self.her, 0.0, 46.0)
        self.assertAlmostEqual(overlap, 1.0, places=6)

    def test_a_hull_with_no_length_shares_nothing_rather_than_dividing_by_zero(self):
        self.assertEqual(alongside(self.her, 0.0, 0.0, self.her, 0.0, 30.0), 0.0)


class TestGettingFreeAgain(BaseEvenniaTestCase):
    """
    The other half of a count: unfouling is harder the more contact there is.

    A captain who let himself be thoroughly lashed has to live with it, and that is what
    makes laying yourself properly alongside worth the trouble from both sides.
    """

    def test_twelve_irons_take_longer_to_clear_than_two(self):
        self.assertGreater(unfouling_time(12, hands=100.0), unfouling_time(2, hands=100.0))

    def test_nothing_holding_is_no_work_at_all(self):
        self.assertEqual(unfouling_time(0, hands=100.0), 0.0)

    def test_a_short_handed_ship_is_longer_at_it(self):
        self.assertGreater(unfouling_time(6, hands=20.0), unfouling_time(6, hands=100.0))

    def test_a_frightened_crew_are_slower(self):
        """The same rule that governs serving the guns and working the rigging."""
        self.assertGreater(
            unfouling_time(6, hands=100.0, hesitation=1.0),
            unfouling_time(6, hands=100.0, hesitation=0.0),
        )

    def test_nobody_to_do_it_means_it_never_finishes(self):
        """An order given to an empty ship is work that never ends, not work that is free."""
        self.assertEqual(unfouling_time(6, hands=0.0), float("inf"))


class TestStormingHerDeck(EmptySeaMixin, BaseEvenniaTest):
    """
    The join between two lashed hulls and the melee arithmetic.

    What is asserted here is the wiring, not the fight: that she measures the real contact
    between the two hulls rather than assuming one, and that a ship holding nobody storms
    nobody.
    """

    def setUp(self):
        super().setUp()
        self.mine = create.create_object(Vessel, key="Boarder")
        self.hers = create.create_object(Vessel, key="Prize")
        for hull, key in ((self.mine, "Boarder"), (self.hers, "Prize")):
            hull.length, hull.beam = 30.0, 8.5
            deck = create.create_object(ShipRoom, key=f"{key} Deck")
            deck.vessel = hull
            deck.exposure = OPEN
        self.mine.maritime_position = WorldPosition(0.0, 0.0)
        self.hers.maritime_position = WorldPosition(8.0, 0.0)
        self.mine.heading = self.hers.heading = 0.0

    def test_a_ship_holding_nobody_storms_nobody(self):
        self.assertIsNone(self.mine.storm_her())

    def test_lashed_alongside_she_can_send_a_party(self):
        self.mine.man(120, ABLE)
        self.hers.man(40, PRESSED)
        self.mine.grapple(self.hers)
        result = self.mine.storm_her()
        self.assertIsNotNone(result)
        self.assertGreater(result.across, 0)

    def test_the_contact_she_fights_across_is_the_real_one(self):
        """
        Lying level and parallel is the whole of her length; drawn out to her bow is a
        fraction of it. The melee reads the hulls rather than being told a number.

        """
        self.mine.man(120, ABLE)
        self.hers.man(200, ABLE)
        self.mine.grapple(self.hers)
        level = self.mine.storm_her().across

        self.hers.maritime_position = WorldPosition(8.0, 27.0)
        drawn_out = self.mine.storm_her().across
        self.assertGreater(level, drawn_out)

    def test_a_ship_nobody_has_crewed_still_answers(self):
        """
        A game that has not modelled complements gets a boarding that resolves rather than
        an exception - the same courtesy the rest of the contrib extends to an unmeasured
        hull.

        """
        self.mine.grapple(self.hers)
        self.assertIsNotNone(self.mine.storm_her())
