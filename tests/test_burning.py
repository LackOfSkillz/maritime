"""
Tests for fire aboard.

The three rules that make fire a situation rather than a debuff each get their own class:
it escalates while you ignore it, fighting it costs hands, and the pumps want her stopped.

"""

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest

from ..burning import (
    BUCKETS_ONLY,
    MOST_LIKELY,
    MOST_SEATS,
    PUMPING_SPEED,
    burn_damage,
    douse_chance,
    fighting_effect,
    hands_worth,
    pumps_draw,
    spread_chance,
)
from ..crew import ABLE
from ..damage import HULL
from ..motion import MotionLimits
from ..position import WorldPosition
from ..rooms import ShipRoom
from ..sailing import FULL, FURLED
from ..typeclasses import Vessel
from ..vessel import OPEN
from .base import EmptySeaMixin

NEVER = 0.999
ALWAYS = 0.0


class TestTheArithmetic(BaseEvenniaTest):
    """The pure functions, with no ship attached."""

    def test_a_stopped_ship_can_pump(self):
        self.assertTrue(pumps_draw(0.0))

    def test_a_ship_with_way_on_cannot(self):
        self.assertFalse(pumps_draw(PUMPING_SPEED + 1.0))

    def test_going_astern_drags_the_hoses_just_the_same(self):
        self.assertFalse(pumps_draw(-(PUMPING_SPEED + 1.0)))

    def test_more_hands_help(self):
        self.assertGreater(hands_worth(30, 1), hands_worth(10, 1))

    def test_but_they_help_less_and_less(self):
        """
        The reason a fire party is a detachment and not the whole watch. If returns were
        linear there would be no decision about how many to send.

        """
        first_ten = hands_worth(10, 1) - hands_worth(0, 1)
        second_ten = hands_worth(20, 1) - hands_worth(10, 1)
        self.assertGreater(first_ten, second_ten)

    def test_more_seats_want_more_hands(self):
        self.assertLess(hands_worth(30, 4), hands_worth(30, 1))

    def test_a_spread_chance_climbs_the_longer_it_is_ignored(self):
        self.assertGreater(spread_chance(600.0), spread_chance(60.0))

    def test_but_never_becomes_a_certainty(self):
        self.assertLessEqual(spread_chance(100000.0), MOST_LIKELY)

    def test_a_fire_party_holds_it_back(self):
        self.assertLess(spread_chance(600.0, effect=0.8), spread_chance(600.0))

    def test_a_party_doing_everything_stops_it_spreading(self):
        self.assertAlmostEqual(spread_chance(600.0, effect=1.0), 0.0)

    def test_dousing_takes_time(self):
        self.assertGreater(douse_chance(0.5, 600.0), douse_chance(0.5, 60.0))

    def test_and_a_party_achieving_nothing_never_gets_there(self):
        self.assertAlmostEqual(douse_chance(0.0, 100000.0), 0.0)

    def test_more_seats_burn_more(self):
        self.assertGreater(burn_damage(3, 60.0), burn_damage(1, 60.0))

    def test_and_longer_burns_more(self):
        self.assertGreater(burn_damage(1, 600.0), burn_damage(1, 60.0))


class TestTheStoppingRule(BaseEvenniaTest):
    """The gem: she has to choose between running and surviving."""

    def test_running_costs_the_fire_party_most_of_its_worth(self):
        stopped = fighting_effect(30, 1, speed=0.0, exposure=0.0)
        running = fighting_effect(30, 1, speed=5.0, exposure=0.0)
        self.assertAlmostEqual(running, stopped * BUCKETS_ONLY)

    def test_canvas_aloft_costs_more_of_it(self):
        handed = fighting_effect(30, 1, speed=0.0, exposure=0.0)
        spread = fighting_effect(30, 1, speed=0.0, exposure=1.0)
        self.assertLess(spread, handed)

    def test_the_worst_case_is_running_under_full_sail(self):
        best = fighting_effect(30, 1, speed=0.0, exposure=0.0)
        worst = fighting_effect(30, 1, speed=8.0, exposure=1.0)
        self.assertLess(worst, best / 4.0)


class BurningTestCase(EmptySeaMixin, BaseEvenniaTest):
    """A hull that can be set alight."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Kestrel")
        self.hull.length, self.hull.beam = 30.0, 8.5
        self.hull.motion_limits = MotionLimits(max_speed=6.0, acceleration=0.5, turn_rate=5.0)
        self.hull.maritime_position = WorldPosition(0.0, 0.0)
        self.hull.heading = 0.0
        self.hull.sail_plan = FURLED
        deck = create.create_object(ShipRoom, key="Kestrel Deck")
        deck.vessel = self.hull
        deck.exposure = OPEN


class TestCatchingFire(BurningTestCase):
    """Getting alight, and reporting it."""

    def test_she_starts_cold(self):
        self.assertFalse(self.hull.alight)
        self.assertEqual(self.hull.seats_of_fire, 0)

    def test_she_can_be_set_alight(self):
        self.assertTrue(self.hull.catch_fire())
        self.assertTrue(self.hull.alight)

    def test_a_second_fire_is_a_second_seat(self):
        self.hull.catch_fire()
        self.hull.catch_fire()
        self.assertEqual(self.hull.seats_of_fire, 2)

    def test_there_is_a_limit_to_how_alight_she_gets(self):
        self.hull.catch_fire(MOST_SEATS * 3)
        self.assertEqual(self.hull.seats_of_fire, MOST_SEATS)

    def test_catching_nothing_sets_nothing_alight(self):
        self.assertFalse(self.hull.catch_fire(0))

    def test_she_can_be_put_out_wholesale(self):
        self.hull.catch_fire(3)
        self.assertEqual(self.hull.douse(), 3)
        self.assertFalse(self.hull.alight)

    def test_a_ship_not_alight_has_no_party_to_send(self):
        self.assertFalse(self.hull.fight_fire(20))


class TestBurning(BurningTestCase):
    """What it does to her, over time."""

    def test_a_ship_not_alight_does_not_burn(self):
        self.assertIsNone(self.hull.work_fire(600.0))

    def test_fire_eats_her_hull(self):
        self.hull.catch_fire()
        before = self.hull.damage.of(HULL)
        self.hull.work_fire(600.0, roll=lambda: NEVER)
        self.assertGreater(self.hull.damage.of(HULL), before)

    def test_and_hurts_her_people(self):
        self.hull.man(120, ABLE)
        self.hull.catch_fire(3)
        result = self.hull.work_fire(1800.0, roll=lambda: NEVER)
        self.assertGreater(result.scorched, 0)

    def test_canvas_aloft_puts_some_of_it_into_the_rigging(self):
        self.hull.sail_plan = FULL
        self.hull.catch_fire()
        result = self.hull.work_fire(600.0, roll=lambda: NEVER)
        self.assertGreater(result.rigging, 0.0)

    def test_bare_poles_leave_far_less_to_catch(self):
        self.hull.sail_plan = FURLED
        self.hull.catch_fire()
        handed = self.hull.work_fire(600.0, roll=lambda: NEVER).rigging

        self.hull.douse()
        self.hull.sail_plan = FULL
        self.hull.catch_fire()
        spread = self.hull.work_fire(600.0, roll=lambda: NEVER).rigging
        self.assertGreater(spread, handed)


class TestSpreading(BurningTestCase):
    """The escalating clock, which is the whole mechanic."""

    def test_an_unfought_fire_spreads(self):
        self.hull.catch_fire()
        result = self.hull.work_fire(600.0, roll=lambda: ALWAYS)
        self.assertTrue(result.spread)
        self.assertEqual(self.hull.seats_of_fire, 2)

    def test_and_the_clock_resets_when_it_does(self):
        """
        So a long-burning ship is not facing one fire that got worse, she is facing
        several, each with its own clock. That is what makes ignoring it compound.

        """
        self.hull.catch_fire()
        self.hull.work_fire(600.0, roll=lambda: ALWAYS)
        self.assertAlmostEqual(float(self.hull.db.fire_unchecked), 0.0)

    def test_ignoring_it_makes_the_next_spread_likelier(self):
        self.hull.catch_fire()
        first = self.hull.work_fire(300.0, roll=lambda: NEVER).chance
        second = self.hull.work_fire(300.0, roll=lambda: NEVER).chance
        self.assertGreater(second, first)

    def test_it_cannot_spread_past_the_limit(self):
        self.hull.catch_fire(MOST_SEATS)
        self.hull.work_fire(600.0, roll=lambda: ALWAYS)
        self.assertEqual(self.hull.seats_of_fire, MOST_SEATS)


class TestFightingIt(BurningTestCase):
    """Hands, and where she is pointing when she uses them."""

    def test_a_party_can_put_a_seat_out(self):
        self.hull.catch_fire(2)
        self.hull.fight_fire(60)
        result = self.hull.work_fire(600.0, roll=lambda: ALWAYS)
        self.assertEqual(result.doused, 1)
        self.assertEqual(self.hull.seats_of_fire, 1)

    def test_the_last_seat_out_stands_the_party_down(self):
        self.hull.catch_fire()
        self.hull.fight_fire(60)
        self.hull.work_fire(600.0, roll=lambda: ALWAYS)
        self.assertFalse(self.hull.alight)
        self.assertAlmostEqual(self.hull.fire_party, 0.0)

    def test_a_party_holds_the_spread_back(self):
        self.hull.catch_fire()
        unfought = self.hull.work_fire(600.0, roll=lambda: NEVER).chance

        self.hull.douse()
        self.hull.catch_fire()
        self.hull.fight_fire(60)
        fought = self.hull.work_fire(600.0, roll=lambda: NEVER).chance
        self.assertLess(fought, unfought)

    def test_stopping_her_is_worth_more_than_the_party_is(self):
        """
        The decision the whole mechanic exists for. Same fire, same hands - the only
        difference is whether she is still running.

        """
        self.hull.catch_fire()
        self.hull.fight_fire(60)
        self.hull.ndb.speed = 0.0
        stopped = self.hull.fire_fighting_effect()
        self.hull.ndb.speed = 5.0
        running = self.hull.fire_fighting_effect()
        self.assertGreater(stopped, running * 2.0)

    def test_the_report_says_whether_the_pumps_draw(self):
        self.hull.catch_fire()
        self.hull.ndb.speed = 5.0
        self.assertFalse(self.hull.fight_fire(60).pumping)
        self.hull.ndb.speed = 0.0
        self.assertTrue(self.hull.fight_fire(60).pumping)


class TestSheBurnsWhereverSheIs(BurningTestCase):
    """A fire does not care that she is tied up."""

    def test_an_anchored_ship_still_burns(self):
        """
        And cannot even run from it. The tick works the fire above the early return that
        every other kind of movement lives below.

        """
        self.hull.anchored = True
        self.hull.catch_fire()
        before = self.hull.damage.of(HULL)
        self.hull.work_fire(600.0, roll=lambda: NEVER)
        self.assertGreater(self.hull.damage.of(HULL), before)
