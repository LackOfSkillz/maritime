"""
Tests for what a gun is loaded with, and therefore what her captain means to do.

"""

from evennia.utils.test_resources import BaseEvenniaTestCase

from ..ammunition import (
    BALL,
    CHAIN,
    CREW,
    DEFAULT_SHOT,
    GRAPE,
    SHOT_TYPES,
    Shot,
    carries,
    in_range,
    shot_named,
    told_by,
)
from ..damage import HULL, RIGGING
from ..tactical import STARBOARD_BROADSIDE
from ..position import WorldPosition
from ..weather import CALM
from ..weapons import SHOT_FALLS_SHORT, Mount, WeaponType, fire, serve

HERE = WorldPosition(0.0, 0.0)

GUN = WeaponType(
    key="nine", name="nine-pounder", arc=STARBOARD_BROADSIDE, max_range=800.0, damage=10.0
)


class TestIntent(BaseEvenniaTestCase):
    """Three answers to one question, and none of them strictly better."""

    def test_ball_is_for_the_hull(self):
        self.assertEqual(BALL.aimed_at, HULL)

    def test_chain_is_for_the_rigging(self):
        self.assertEqual(CHAIN.aimed_at, RIGGING)

    def test_grape_is_for_the_people(self):
        self.assertEqual(GRAPE.aimed_at, CREW)

    def test_the_crew_are_not_a_damage_track(self):
        """
        Casualties are people, and they live in the company. Keeping the marker
        distinct is what stops shot at the crew quietly becoming shot at the hull.

        """
        self.assertNotIn(CREW, (HULL, RIGGING))

    def test_no_shot_is_simply_the_strongest(self):
        """
        If one were, there would be no decision. Grape hits people hardest because
        people are soft, and it would be a poor way to open a plank.

        """
        heaviest = max(SHOT_TYPES, key=lambda shot: shot.weight)
        furthest = max(SHOT_TYPES, key=lambda shot: shot.reach)
        self.assertIsNot(heaviest, furthest)

    def test_a_game_can_carry_its_own(self):
        """Heated shot, langrage, a stone from a trebuchet - same three questions."""
        langrage = Shot("langrage", "langrage", CREW, weight=1.1, reach=0.2)
        self.assertEqual(langrage.aimed_at, CREW)


class TestReach(BaseEvenniaTestCase):
    """The constraint that makes it a real choice."""

    def test_ball_carries_as_far_as_the_gun(self):
        self.assertAlmostEqual(carries(BALL, GUN), GUN.max_range)

    def test_chain_tumbles_and_loses_its_way(self):
        self.assertLess(carries(CHAIN, GUN), carries(BALL, GUN))

    def test_grape_is_a_knife_range_weapon(self):
        self.assertLess(carries(GRAPE, GUN), carries(CHAIN, GUN))

    def test_at_long_range_only_the_sinking_shot_reaches(self):
        """
        Which is the whole tactical shape: a pirate wants chain and grape, and both
        mean closing - taking his enemy's ball the whole way in.

        """
        far = 600.0
        self.assertTrue(in_range(BALL, GUN, far))
        self.assertFalse(in_range(CHAIN, GUN, far))
        self.assertFalse(in_range(GRAPE, GUN, far))

    def test_close_enough_and_every_option_is_open(self):
        near = 150.0
        for shot in SHOT_TYPES:
            self.assertTrue(in_range(shot, GUN, near), shot.key)

    def test_a_captain_who_loads_early_shortens_his_own_reach(self):
        """The price of having made his mind up before he knew the range."""
        self.assertLess(carries(GRAPE, GUN), GUN.max_range)

    def test_nothing_reaches_past_the_gun_itself(self):
        self.assertFalse(in_range(BALL, GUN, GUN.max_range + 1.0))


class TestWeight(BaseEvenniaTestCase):
    """What a hit is worth, on top of the one lethality dial."""

    def test_ball_delivers_what_the_gun_does(self):
        self.assertAlmostEqual(told_by(BALL, GUN.damage), GUN.damage)

    def test_grape_hits_people_harder_than_ball_does(self):
        self.assertGreater(told_by(GRAPE, GUN.damage), told_by(BALL, GUN.damage))

    def test_chain_is_the_lighter_blow(self):
        """It is for cutting rigging, not for smashing."""
        self.assertLess(told_by(CHAIN, GUN.damage), told_by(BALL, GUN.damage))

    def test_a_gun_that_does_nothing_delivers_nothing(self):
        self.assertAlmostEqual(told_by(GRAPE, 0.0), 0.0)

    def test_negative_damage_is_not_a_repair(self):
        self.assertAlmostEqual(told_by(BALL, -40.0), 0.0)


class TestAsking(BaseEvenniaTestCase):
    """Naming a shot the way somebody would."""

    def test_by_its_key(self):
        self.assertIs(shot_named("chain"), CHAIN)

    def test_by_the_start_of_its_name(self):
        self.assertIs(shot_named("round"), BALL)

    def test_case_and_space_do_not_matter(self):
        self.assertIs(shot_named("  GRAPE "), GRAPE)

    def test_something_nobody_carries(self):
        self.assertIsNone(shot_named("canister"))

    def test_nothing_at_all(self):
        self.assertIsNone(shot_named(""))


class TestTheDefault(BaseEvenniaTestCase):
    """What a gun holds when nobody has said."""

    def test_she_is_loaded_with_ball(self):
        self.assertIs(DEFAULT_SHOT, BALL)

    def test_because_it_is_the_shot_that_works_at_any_range(self):
        """
        A battery loaded with grape and an enemy two miles off is a battery loaded
        with nothing, which is a worse default than being merely unimaginative.

        """
        self.assertAlmostEqual(DEFAULT_SHOT.reach, 1.0)


class TestTheGunRemembers(BaseEvenniaTestCase):
    """
    Loading, and what a gun holds afterwards.

    Mutation testing found this whole seam untested: the ammunition rules were
    thoroughly covered and nothing ever put a charge in an actual gun.

    """

    def a_gun(self, **kwargs):
        """
        Returns:
            mount (Mount): A loaded starboard gun.

        """
        settings = {"key": "starboard one", "weapon": GUN, "loaded": True, "ready_at": 0.0}
        settings.update(kwargs)
        return Mount(**settings)

    def test_serving_her_with_a_shot_loads_that_shot(self):
        served = serve(self.a_gun(loaded=False), now=0.0, shot=CHAIN)
        self.assertIs(served.shot, CHAIN)
        self.assertTrue(served.loaded)

    def test_serving_her_without_one_keeps_what_she_had(self):
        """
        A battery goes on firing the same thing until her captain changes his mind,
        which is how a gun crew behaves and saves saying it every time.

        """
        chained = serve(self.a_gun(loaded=False), now=0.0, shot=CHAIN)
        again = serve(chained, now=100.0)
        self.assertIs(again.shot, CHAIN)

    def test_a_gun_starts_with_ball(self):
        self.assertIs(self.a_gun().shot, DEFAULT_SHOT)

    def test_she_can_be_loaded_with_something_else_entirely(self):
        served = serve(self.a_gun(loaded=False), now=0.0, shot=GRAPE)
        self.assertIs(served.shot, GRAPE)


class TestFiringWhatIsInHer(BaseEvenniaTestCase):
    """What the shot does once the gun goes off."""

    def shoot(self, shot, distance, roll=0.0):
        """
        Args:
            shot (Shot): What is in the gun.
            distance (float): Range to the target, in metres.
            roll (float, optional): The injected die.

        Returns:
            result (ShotResult): What came of it.

        """
        mount = Mount(key="starboard one", weapon=GUN, loaded=True, ready_at=0.0, shot=shot)
        target = HERE.moved(90.0, distance)
        return fire(mount, HERE, 0.0, "her", target, 0.0, 0.0, CALM, 0.0, lambda: roll)

    def test_a_shot_that_will_not_reach_says_so(self):
        """
        Rather than missing quietly. A captain who has loaded grape has shortened
        his own reach for the afternoon, and needs to know that is why.

        """
        refused = self.shoot(GRAPE, 600.0)
        self.assertFalse(refused)
        self.assertEqual(refused.code, SHOT_FALLS_SHORT)

    def test_the_same_range_is_fine_for_ball(self):
        self.assertTrue(self.shoot(BALL, 600.0))

    def test_and_grape_is_deadly_close_to(self):
        self.assertTrue(self.shoot(GRAPE, 150.0))

    def test_a_hit_carries_what_was_in_the_gun(self):
        """Without this the caller cannot tell which track to hurt."""
        self.assertIs(self.shoot(CHAIN, 200.0).shot, CHAIN)

    def test_a_miss_carries_it_too(self):
        self.assertIs(self.shoot(CHAIN, 200.0, roll=1.0).shot, CHAIN)

    def test_the_damage_is_the_shot_s_rather_than_the_gun_s(self):
        heavy = self.shoot(GRAPE, 150.0).damage
        plain = self.shoot(BALL, 150.0).damage
        self.assertGreater(heavy, plain)
        self.assertAlmostEqual(heavy, told_by(GRAPE, GUN.damage))

    def test_chain_is_the_lighter_blow_in_practice(self):
        self.assertLess(self.shoot(CHAIN, 200.0).damage, self.shoot(BALL, 200.0).damage)
