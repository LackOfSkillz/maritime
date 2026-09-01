"""
Tests for fighting sail: what shortening down buys, and what it costs.

Every benefit is derived from the canvas rather than granted to the plan, which is what
stops it being a free upgrade. She is slower, harder to dismast, and fires faster, and a
captain has to judge whether he still needs the speed.

"""

from django.test import override_settings
from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest, BaseEvenniaTestCase

from ..crew import ABLE
from ..damage import RIGGING, serving_time
from ..motion import MotionLimits
from ..position import WorldPosition
from ..rooms import ShipRoom
from ..sailing import (
    BARE_POLE_EXPOSURE,
    BATTLE,
    FULL,
    FURLED,
    REEFED,
    SAIL_PLANS,
    WEATHER_PLANS,
    WORKING,
    WindVector,
    hands_aloft,
    rigging_exposed,
)
from ..typeclasses import Vessel
from ..vessel import OPEN
from ..voyage import sail_for_wind
from .base import EmptySeaMixin

BREEZE = {"MARITIME_WIND_BEARING": 180.0, "MARITIME_WIND_SPEED": 8.0}


class TestFightingSail(BaseEvenniaTestCase):
    """A plan that answers what is about to happen rather than the weather."""

    def test_she_is_a_plan_like_any_other(self):
        self.assertIn(BATTLE, SAIL_PLANS)

    def test_she_carries_less_than_working_sail(self):
        self.assertLess(BATTLE.area, WORKING.area)

    def test_and_more_than_reefed(self):
        """Enough to manoeuvre. A ship that cannot manoeuvre is a target."""
        self.assertGreater(BATTLE.area, REEFED.area)


class TestSheIsNotAWeatherPlan(BaseEvenniaTestCase):
    """
    The sailing master must never reach for her on his own.

    She stands more wind than working sail, so a mate picking the largest plan the
    weather allows would set her in a fresh breeze - clearing the ship for action on
    a quiet passage with nothing in sight. Sail area does not say what a plan is for,
    and this is the seam where that mattered.

    """

    def test_she_is_not_on_the_weather_ladder(self):
        self.assertNotIn(BATTLE, WEATHER_PLANS)

    def test_but_she_is_still_a_plan_a_captain_may_order(self):
        self.assertIn(BATTLE, SAIL_PLANS)

    def test_a_fresh_breeze_still_gets_reefed_sail(self):
        """The regression itself: she stands 20 to reefed's 18, and won."""
        self.assertIs(sail_for_wind(WindVector(bearing=0.0, speed=15.0)), REEFED)

    def test_no_weather_whatever_produces_fighting_sail(self):
        for speed in range(0, 40):
            self.assertIsNot(sail_for_wind(WindVector(bearing=0.0, speed=float(speed))), BATTLE)

    def test_the_weather_ladder_is_otherwise_the_whole_set(self):
        """Nothing else went missing when fighting sail came out of it."""
        self.assertEqual(set(SAIL_PLANS) - set(WEATHER_PLANS), {BATTLE})


class TestWhatIsAloftToBeShotAway(BaseEvenniaTestCase):
    """Derived from the canvas, which is what stops it being a free upgrade."""

    def test_a_full_press_has_everything_to_lose(self):
        self.assertAlmostEqual(rigging_exposed(FULL), 1.0)

    def test_fighting_sail_has_less(self):
        self.assertLess(rigging_exposed(BATTLE), rigging_exposed(FULL))

    def test_she_cannot_make_herself_immune_by_furling(self):
        """
        Masts, yards and standing rigging are still up there. A ship under bare
        poles is harder to dismast and not impossible to dismast.

        """
        self.assertAlmostEqual(rigging_exposed(FURLED), BARE_POLE_EXPOSURE)
        self.assertGreater(rigging_exposed(FURLED), 0.0)

    def test_it_rises_with_every_sail_set(self):
        exposures = [rigging_exposed(plan) for plan in sorted(SAIL_PLANS, key=lambda p: p.area)]
        self.assertEqual(exposures, sorted(exposures))


class TestWhoIsAloftAndWhoIsAtTheGuns(BaseEvenniaTestCase):
    """The other half of the trade."""

    def test_a_full_press_ties_up_a_third_of_her(self):
        self.assertGreater(hands_aloft(FULL), 0.3)

    def test_fighting_sail_frees_half_of_those(self):
        self.assertLess(hands_aloft(BATTLE), hands_aloft(FULL) * 0.6)

    def test_bare_poles_need_nobody(self):
        self.assertAlmostEqual(hands_aloft(FURLED), 0.0)

    def test_a_shortened_ship_serves_her_guns_faster(self):
        under_press = serving_time(90.0) * (1.0 + hands_aloft(FULL))
        cleared = serving_time(90.0) * (1.0 + hands_aloft(BATTLE))
        self.assertLess(cleared, under_press)


class BattleSailShipTestCase(EmptySeaMixin, BaseEvenniaTest):
    """A hull that can shorten down."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Kestrel")
        self.hull.length, self.hull.beam = 18.0, 5.4
        self.hull.motion_limits = MotionLimits(max_speed=6.0, acceleration=0.5, turn_rate=5.0)
        self.hull.maritime_position = WorldPosition(0.0, 0.0)
        deck = create.create_object(ShipRoom, key="Main Deck")
        deck.vessel = self.hull
        deck.exposure = OPEN
        self.hull.man(60, ABLE)


class TestTheTrade(BattleSailShipTestCase):
    """All three consequences, on a hull, at once."""

    def test_shortening_down_costs_her_speed(self):
        with override_settings(**BREEZE):
            self.hull.heading = 90.0
            self.hull.sail_plan = FULL
            fast = self.hull.sailing_speed()
            self.hull.sail_plan = BATTLE
            self.assertLess(self.hull.sailing_speed(), fast)

    def test_and_buys_her_rigging(self):
        """
        The same chain shot, against the same ship, twice - and what she has aloft
        decides how much of it tells.

        """
        self.hull.sail_plan = FULL
        self.hull.take_damage(RIGGING, 200.0)
        under_press = self.hull.damage.rigging

        cleared = create.create_object(Vessel, key="Petrel")
        cleared.length = 18.0
        cleared.sail_plan = BATTLE
        cleared.take_damage(RIGGING, 200.0)

        self.assertLess(cleared.damage.rigging, under_press)

    def test_a_furled_ship_is_hardest_of_all_to_dismast(self):
        self.hull.sail_plan = FURLED
        self.hull.take_damage(RIGGING, 200.0)
        furled = self.hull.damage.rigging

        pressed = create.create_object(Vessel, key="Petrel")
        pressed.length = 18.0
        pressed.sail_plan = FULL
        pressed.take_damage(RIGGING, 200.0)

        self.assertLess(furled, pressed.damage.rigging)

    def test_but_never_immune(self):
        self.hull.sail_plan = FURLED
        self.hull.take_damage(RIGGING, 200.0)
        self.assertGreater(self.hull.damage.rigging, 0.0)

    def test_only_the_rigging_track_cares_what_is_set(self):
        """
        Shortening down does not armour her hull. A ball goes through the same
        planking whatever she has aloft.

        """
        from ..damage import HULL

        self.hull.sail_plan = FURLED
        self.hull.take_damage(HULL, 200.0)
        furled = self.hull.damage.hull

        pressed = create.create_object(Vessel, key="Petrel")
        pressed.length = 18.0
        pressed.sail_plan = FULL
        pressed.take_damage(HULL, 200.0)

        self.assertAlmostEqual(furled, pressed.damage.hull)
