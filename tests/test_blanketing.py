"""
Tests for taking the wind out of another ship's sails.

The one thing that makes position relative to *other ships* matter rather than only
position relative to the wind - which is why the weather gage was worth dying for.

"""

import math

from django.test import override_settings
from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest, BaseEvenniaTestCase

from ..motion import HelmOrders, MotionLimits
from ..position import WorldPosition
from ..rooms import ShipRoom
from ..sailing import (
    BARE_HULL_BLANKET,
    BATTLE,
    BLANKET_ARC,
    FULL,
    FURLED,
    WindVector,
    blanket_reach,
    blanketed_by,
    blanketing,
)
from ..traffic import traffic
from ..typeclasses import Vessel
from ..vessel import OPEN
from .base import EmptySeaMixin

#: A northerly, so the wind blows towards the south and a ship's lee is due south
#: of her. Every position below is chosen against that.
NORTHERLY = WindVector(bearing=0.0, speed=8.0)

TO_WINDWARD = WorldPosition(0.0, 0.0)
FRIGATE = 46.0


def astern(metres, off=0.0):
    """
    Args:
        metres (float): How far downwind of the ship to windward.
        off (float, optional): Degrees off dead astern of her.

    Returns:
        position (WorldPosition): Where that puts you.

    """
    bearing = math.radians(180.0 + off)
    return WorldPosition(metres * math.sin(bearing), metres * math.cos(bearing))


class TestHowFarAShadowReaches(BaseEvenniaTestCase):
    """Scaled by canvas, which is what ties this to fighting sail."""

    def test_a_full_press_throws_the_longest_shadow(self):
        self.assertGreater(blanket_reach(FRIGATE, FULL), blanket_reach(FRIGATE, BATTLE))

    def test_clearing_for_action_gives_up_the_blanket(self):
        """
        Which is the fourth side of the fighting-sail trade, and the one a captain
        is least likely to have thought about.

        """
        self.assertLess(blanket_reach(FRIGATE, BATTLE), blanket_reach(FRIGATE, FULL) * 0.7)

    def test_a_bare_hull_still_spoils_a_little_air(self):
        """She is still something standing up out of the water."""
        bare = blanket_reach(FRIGATE, FURLED)
        self.assertGreater(bare, 0.0)
        self.assertAlmostEqual(
            bare, FRIGATE * blanket_reach(1.0, FULL) * BARE_HULL_BLANKET, places=4
        )

    def test_a_bigger_ship_shadows_further(self):
        self.assertGreater(blanket_reach(60.0, FULL), blanket_reach(20.0, FULL))


class TestLyingInSomebodysLee(BaseEvenniaTestCase):
    """Two things have to be true: downwind of her, and close enough."""

    def lost(self, metres, off=0.0, plan=FULL):
        """
        Returns:
            lost (float): The fraction of drive taken out.

        """
        return blanketed_by(astern(metres, off), TO_WINDWARD, FRIGATE, plan, NORTHERLY)

    def test_close_under_her_stern_is_the_worst_place(self):
        self.assertGreater(self.lost(40.0), 0.4)

    def test_it_eases_with_distance(self):
        self.assertGreater(self.lost(50.0), self.lost(150.0))
        self.assertGreater(self.lost(150.0), self.lost(300.0))

    def test_and_ends(self):
        self.assertAlmostEqual(self.lost(blanket_reach(FRIGATE, FULL) + 10.0), 0.0)

    def test_luffing_out_of_her_lee_is_worth_doing(self):
        """Escaping a blanket is a manoeuvre rather than a wait."""
        self.assertGreater(self.lost(150.0, off=0.0), self.lost(150.0, off=15.0))
        self.assertGreater(self.lost(150.0, off=15.0), self.lost(150.0, off=22.0))

    def test_and_falls_away_quickly_across_the_cone(self):
        """
        Most of the loss is in the last few degrees, so luffing a little buys back a
        lot - which is what makes getting out of somebody's lee worth the course it
        costs. A gentler curve would make the whole cone uniformly bad and give a
        captain no reason to do anything about it.

        Ordering alone does not say this: a shallower taper falls in the same order
        and is a different sea.

        """
        deep = self.lost(150.0, off=0.0)
        self.assertLess(self.lost(150.0, off=BLANKET_ARC * 0.6), deep * 0.5)

    def test_outside_the_arc_is_clear_air(self):
        self.assertAlmostEqual(self.lost(150.0, off=BLANKET_ARC + 1.0), 0.0)

    def test_it_works_on_either_side(self):
        self.assertAlmostEqual(self.lost(150.0, off=12.0), self.lost(150.0, off=-12.0))

    def test_nobody_is_becalmed_entirely(self):
        """
        The air is disturbed rather than absent, so she keeps steerage way however
        badly she is placed. A ship that stopped dead would make the weather gage an
        execution rather than an advantage, and would let one ship pin another
        without ever firing at her.

        The bound is absolute on purpose. Writing it as `<= BLANKET_WORST` would say
        only that the code agrees with itself, and would go on passing if the
        constant were raised to a flat calm.

        """
        self.assertLess(max(self.lost(off) for off in (1.0, 10.0, 50.0, 200.0)), 0.75)

    def test_a_ship_to_leeward_shadows_nobody(self):
        """Upwind of her is clear air by definition."""
        upwind = WorldPosition(0.0, 200.0)
        self.assertAlmostEqual(blanketed_by(upwind, TO_WINDWARD, FRIGATE, FULL, NORTHERLY), 0.0)

    def test_a_ship_under_bare_poles_barely_blankets(self):
        self.assertLess(self.lost(50.0, plan=FURLED), self.lost(50.0, plan=FULL))

    def test_a_flat_calm_shadows_nothing(self):
        still = WindVector(bearing=0.0, speed=0.0)
        self.assertAlmostEqual(blanketed_by(astern(50.0), TO_WINDWARD, FRIGATE, FULL, still), 0.0)


class TestSeveralShipsToWindward(BaseEvenniaTestCase):
    """The worst shadow, not the sum of them."""

    def test_lying_behind_two_is_not_twice_as_calm(self):
        """
        The air is already spoiled. Adding shadows would let a squadron becalm a
        ship entirely, which is not a thing that happens.

        """
        one = [(TO_WINDWARD, FRIGATE, FULL)]
        two = [(TO_WINDWARD, FRIGATE, FULL), (WorldPosition(0.0, 60.0), FRIGATE, FULL)]
        me = astern(150.0)
        self.assertAlmostEqual(
            blanketing(me, FULL, NORTHERLY, two),
            max(blanketed_by(me, where, length, plan, NORTHERLY) for where, length, plan in two),
        )
        self.assertGreater(blanketing(me, FULL, NORTHERLY, one), 0.0)

    def test_an_empty_sea_shadows_nothing(self):
        self.assertAlmostEqual(blanketing(astern(150.0), FULL, NORTHERLY, []), 0.0)

    def test_a_ship_with_nothing_set_has_nothing_to_steal(self):
        others = [(TO_WINDWARD, FRIGATE, FULL)]
        self.assertAlmostEqual(blanketing(astern(50.0), FURLED, NORTHERLY, others), 0.0)


class TestBlanketingUnderWay(EmptySeaMixin, BaseEvenniaTest):
    """On real hulls, through the traffic register."""

    def a_sloop(self, key, position, length=46.0):
        """
        Returns:
            vessel (Vessel): A sloop under working canvas at that place.

        """
        hull = create.create_object(Vessel, key=key)
        hull.length, hull.beam = length, length / 3.8
        hull.motion_limits = MotionLimits(max_speed=8.0, acceleration=0.5, turn_rate=5.0)
        hull.maritime_position = position
        hull.heading = 180.0
        hull.sail_plan = FULL
        deck = create.create_object(ShipRoom, key=f"{key} Deck")
        deck.vessel = hull
        deck.exposure = OPEN
        traffic().note(hull, position)
        return hull

    def test_an_empty_sea_takes_nothing(self):
        with override_settings(MARITIME_WIND_BEARING=0.0, MARITIME_WIND_SPEED=8.0):
            alone = self.a_sloop("Alone", TO_WINDWARD)
            self.assertAlmostEqual(alone.blanketed(), 0.0)

    def test_a_ship_to_windward_takes_her_wind(self):
        with override_settings(MARITIME_WIND_BEARING=0.0, MARITIME_WIND_SPEED=8.0):
            self.a_sloop("Windward", TO_WINDWARD)
            sheltered = self.a_sloop("Leeward", astern(120.0))
            self.assertGreater(sheltered.blanketed(), 0.0)

    def test_and_it_costs_her_speed(self):
        with override_settings(MARITIME_WIND_BEARING=0.0, MARITIME_WIND_SPEED=8.0):
            clear = self.a_sloop("Clear", WorldPosition(5000.0, 0.0))
            clear.heading = 90.0
            free = clear.sailing_speed()

            self.a_sloop("Windward", TO_WINDWARD)
            sheltered = self.a_sloop("Leeward", astern(120.0))
            sheltered.heading = 90.0
            self.assertLess(sheltered.sailing_speed(), free)

    def test_the_windward_ship_is_untouched(self):
        """The whole point of the weather gage."""
        with override_settings(MARITIME_WIND_BEARING=0.0, MARITIME_WIND_SPEED=8.0):
            windward = self.a_sloop("Windward", TO_WINDWARD)
            self.a_sloop("Leeward", astern(120.0))
            self.assertAlmostEqual(windward.blanketed(), 0.0)

    def test_the_worst_shadow_wins_and_she_names_the_right_ship(self):
        """
        Two ships to windward, and only one of them is the answer. The register
        hands them over nearest-first, so a search that kept the last one it looked
        at would name the furthest ship and report the weakest of her shadows - and
        with a single ship to windward nothing would ever show it.

        """
        with override_settings(MARITIME_WIND_BEARING=0.0, MARITIME_WIND_SPEED=8.0):
            near = self.a_sloop("Nearer", TO_WINDWARD)
            self.a_sloop("Further", WorldPosition(0.0, 100.0))
            sheltered = self.a_sloop("Sheltered", astern(150.0))

            shadow = sheltered.shadow()
            self.assertIs(shadow.vessel, near)
            self.assertAlmostEqual(shadow.lost, sheltered.blanketed())

    def test_and_the_worst_is_the_one_that_slows_her(self):
        """Not the average of them, and not the last one looked at."""
        with override_settings(MARITIME_WIND_BEARING=0.0, MARITIME_WIND_SPEED=8.0):
            self.a_sloop("Nearer", TO_WINDWARD)
            self.a_sloop("Further", WorldPosition(0.0, 100.0))
            sheltered = self.a_sloop("Sheltered", astern(150.0))

            alone = self.a_sloop("Alone", WorldPosition(9000.0, 0.0))
            only_the_far_one = blanketed_by(
                astern(150.0), WorldPosition(0.0, 100.0), 46.0, FULL, NORTHERLY
            )
            self.assertGreater(sheltered.blanketed(), only_the_far_one)
            self.assertAlmostEqual(alone.blanketed(), 0.0)

    def test_a_small_ship_finds_the_big_one_taking_her_wind(self):
        """
        The broad-phase search has to be sized on the shadow she is looking for, not
        on the one she casts. A cutter two cables under a frigate's lee is squarely
        in it, and searching her own length downwind would find nobody at all.

        """
        with override_settings(MARITIME_WIND_BEARING=0.0, MARITIME_WIND_SPEED=8.0):
            self.a_sloop("Frigate", TO_WINDWARD, length=46.0)
            cutter = self.a_sloop("Cutter", astern(300.0), length=12.0)
            self.assertGreater(cutter.blanketed(), 0.0)

    def test_and_a_big_ship_is_not_shadowed_by_a_small_one_that_far_off(self):
        """The reach belongs to the hull casting it, so this is not symmetrical."""
        with override_settings(MARITIME_WIND_BEARING=0.0, MARITIME_WIND_SPEED=8.0):
            self.a_sloop("Cutter", TO_WINDWARD, length=12.0)
            frigate = self.a_sloop("Frigate", astern(300.0), length=46.0)
            self.assertAlmostEqual(frigate.blanketed(), 0.0)


class TestBeingToldAboutIt(EmptySeaMixin, BaseEvenniaTest):
    """
    A silent thirty per cent is a bug wearing a feature's coat.

    The captain has to be able to answer "why are we slowing", and the answer has to
    name a ship, because the remedy is to alter course away from her.

    """

    def setUp(self):
        super().setUp()
        self.heard = []
        self.hull = create.create_object(Vessel, key="Kestrel")
        self.hull.length, self.hull.beam = 18.0, 5.4
        self.hull.motion_limits = MotionLimits(max_speed=8.0, acceleration=0.5, turn_rate=5.0)
        self.hull.maritime_position = astern(120.0)
        self.hull.heading = 180.0
        self.hull.sail_plan = FULL
        self.hull.orders = HelmOrders(heading=180.0, speed=4.0)
        deck = create.create_object(ShipRoom, key="Main Deck")
        deck.vessel = self.hull
        deck.exposure = OPEN
        deck.msg_contents = lambda text, **kwargs: self.heard.append(text)
        traffic().note(self.hull, self.hull.maritime_position)

    def a_ship_to_windward(self, key="Weatherly"):
        """
        Returns:
            vessel (Vessel): A frigate under full sail, dead to windward of us.

        """
        hull = create.create_object(Vessel, key=key)
        hull.length, hull.beam = 46.0, 12.0
        hull.maritime_position = TO_WINDWARD
        hull.heading = 180.0
        hull.sail_plan = FULL
        traffic().note(hull, hull.maritime_position)
        return hull

    def tick(self, times=1):
        """Run the simulation step that decides her speed."""
        with override_settings(MARITIME_WIND_BEARING=0.0, MARITIME_WIND_SPEED=8.0):
            for _ in range(times):
                self.hull.at_maritime_tick(1.0)

    def said_about_the_lee(self):
        """
        Returns:
            lines (list): Everything said that mentions being blanketed.

        """
        return [line for line in self.heard if "slat" in line or "wind again" in line]

    def test_clear_air_is_not_worth_mentioning(self):
        self.tick(3)
        self.assertEqual(self.said_about_the_lee(), [])

    def test_she_says_who_has_the_wind_of_her(self):
        self.a_ship_to_windward()
        self.tick()
        self.assertTrue(any("Weatherly" in line for line in self.said_about_the_lee()))

    def test_and_says_it_once(self):
        """
        Not every tick. Lying in somebody's lee lasts minutes, and a ship reports
        that she has been blanketed rather than that she still is.

        """
        self.a_ship_to_windward()
        self.tick(6)
        self.assertEqual(len(self.said_about_the_lee()), 1)

    def test_she_says_when_she_gets_her_wind_back(self):
        windward = self.a_ship_to_windward()
        self.tick()
        windward.maritime_position = WorldPosition(20000.0, 0.0)
        traffic().note(windward, windward.maritime_position)
        self.tick()
        self.assertTrue(any("wind again" in line for line in self.said_about_the_lee()))

    def test_and_says_that_once_too(self):
        windward = self.a_ship_to_windward()
        self.tick()
        windward.maritime_position = WorldPosition(20000.0, 0.0)
        traffic().note(windward, windward.maritime_position)
        self.tick(6)
        self.assertEqual(len([line for line in self.heard if "wind again" in line]), 1)

    def test_passing_from_one_lee_into_another_names_the_new_ship(self):
        """
        Keyed by who, not by whether. A ship that tracked only "am I blanketed"
        would go quiet exactly when the situation changed, which is the moment the
        captain most needs to know about.

        """
        first = self.a_ship_to_windward("Weatherly")
        self.tick()
        first.maritime_position = WorldPosition(20000.0, 0.0)
        traffic().note(first, first.maritime_position)
        self.a_ship_to_windward("Audacious")
        self.tick()
        self.assertTrue(any("Audacious" in line for line in self.said_about_the_lee()))
