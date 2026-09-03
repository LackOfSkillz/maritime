"""
Tests for guns: whether they bear, where the shot goes, and whether it connects.

"""

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest, BaseEvenniaTestCase

from ..position import EAST, NORTH, WorldPosition
from ..tactical import FORWARD, PORT_BROADSIDE, STARBOARD_BROADSIDE
from ..typeclasses import Vessel
from ..weapons import (
    NOT_LOADED,
    OUT_OF_RANGE,
    STILL_RELOADING,
    WILL_NOT_BEAR,
    Mount,
    WeaponType,
    can_fire,
    fire,
    serve,
)
from ..ballistics import (
    END_ON_FRACTION,
    LONG_RANGE_ACCURACY,
    aim_point,
    aspect_accuracy,
    hit_chance,
    range_accuracy,
    sea_accuracy,
    time_of_flight,
)
from ..weather import CALM, PHENOMENAL
from .base import EmptySeaMixin

HERE = WorldPosition(0.0, 0.0)
ASTARBOARD = WorldPosition(300.0, 0.0)

GUN = WeaponType(
    key="long nine",
    name="long nine",
    arc=STARBOARD_BROADSIDE,
    max_range=800.0,
    reload_time=90.0,
    projectile_speed=250.0,
    accuracy=0.6,
    damage=10.0,
)


def a_mount(**kwargs):
    """
    Args:
        **kwargs: Overrides.

    Returns:
        mount (Mount): A loaded starboard gun, ready to fire.

    """
    settings = {"key": "starboard one", "weapon": GUN, "loaded": True, "ready_at": 0.0}
    settings.update(kwargs)
    return Mount(**settings)


class TestFlightAndAim(BaseEvenniaTestCase):
    """The shot is not instant, and she does not wait."""

    def test_flight_time_is_range_over_speed(self):
        self.assertAlmostEqual(time_of_flight(500.0, 250.0), 2.0)

    def test_an_instant_weapon_takes_no_time(self):
        self.assertAlmostEqual(time_of_flight(500.0, 0.0), 0.0)

    def test_a_stationary_target_is_aimed_at_directly(self):
        self.assertEqual(aim_point(ASTARBOARD, NORTH, 0.0, 2.0), ASTARBOARD)

    def test_a_moving_target_is_aimed_off(self):
        """
        The whole of gunnery against a moving ship: you fire where she will be.

        """
        laid = aim_point(ASTARBOARD, NORTH, 5.0, 2.0)
        self.assertAlmostEqual(laid.y, 10.0)

    def test_the_faster_she_goes_the_further_ahead_you_lay(self):
        slow = aim_point(ASTARBOARD, NORTH, 2.0, 4.0)
        fast = aim_point(ASTARBOARD, NORTH, 8.0, 4.0)
        self.assertGreater(fast.y, slow.y)

    def test_a_longer_flight_needs_more_lead(self):
        near = aim_point(ASTARBOARD, NORTH, 5.0, 1.0)
        far = aim_point(ASTARBOARD, NORTH, 5.0, 6.0)
        self.assertGreater(far.y, near.y)


class TestAccuracyFactors(BaseEvenniaTestCase):
    """Four things multiplied, each separately arguable."""

    def test_point_blank_keeps_everything(self):
        self.assertAlmostEqual(range_accuracy(0.0, 800.0), 1.0)

    def test_the_far_edge_keeps_little(self):
        self.assertAlmostEqual(range_accuracy(800.0, 800.0), LONG_RANGE_ACCURACY)

    def test_it_falls_away_smoothly(self):
        """
        No cliff. A hard edge would turn range bands into a formality rather
        than a decision about when to open fire.

        Checking that it decreases is not enough - a cliff decreases too, and
        mutation testing walked straight through the first version of this. The
        middle of the range has to be strictly between the two ends.

        """
        steps = [range_accuracy(float(metres), 800.0) for metres in range(0, 900, 50)]
        self.assertEqual(steps, sorted(steps, reverse=True))

        halfway = range_accuracy(400.0, 800.0)
        self.assertLess(halfway, range_accuracy(0.0, 800.0))
        self.assertGreater(halfway, range_accuracy(800.0, 800.0))

    def test_beyond_maximum_range_is_no_worse_than_at_it(self):
        self.assertAlmostEqual(range_accuracy(9000.0, 800.0), LONG_RANGE_ACCURACY)

    def test_a_calm_costs_nothing(self):
        self.assertAlmostEqual(sea_accuracy(CALM), 1.0)

    def test_a_heavy_sea_costs_a_great_deal(self):
        self.assertLess(sea_accuracy(PHENOMENAL), 0.5)

    def test_an_unknown_sea_costs_nothing(self):
        self.assertAlmostEqual(sea_accuracy("biblical"), 1.0)

    def test_a_beam_on_target_is_the_easiest(self):
        self.assertAlmostEqual(aspect_accuracy(90.0), 1.0)

    def test_a_bow_on_target_is_the_hardest(self):
        """
        Which is why a ship under fire turns towards the guns, and why crossing
        a T is worth manoeuvring for from both sides of the exchange.

        """
        self.assertAlmostEqual(aspect_accuracy(0.0), END_ON_FRACTION)

    def test_stern_on_is_as_narrow_as_bow_on(self):
        self.assertAlmostEqual(aspect_accuracy(180.0), aspect_accuracy(0.0))

    def test_the_chance_never_leaves_its_bounds(self):
        for metres in range(0, 1000, 50):
            for state in (CALM, "rough", PHENOMENAL):
                for angle in (-180.0, -90.0, 0.0, 90.0, 180.0):
                    chance = hit_chance(GUN, float(metres), state, angle)
                    self.assertGreaterEqual(chance, 0.0)
                    self.assertLessEqual(chance, 1.0)

    def test_a_misconfigured_weapon_is_still_clamped(self):
        """
        The upper clamp is defensive, and a sensible weapon never reaches it -
        which is why the sweep above cannot tell whether it is there. A game that
        writes an accuracy of three is the case it exists for.

        """
        absurd = WeaponType(
            key="wishful", name="wishful thinking", arc=STARBOARD_BROADSIDE, accuracy=3.0
        )
        self.assertLessEqual(hit_chance(absurd, 0.0, CALM, 90.0), 1.0)


class TestCanFire(BaseEvenniaTestCase):
    """Whether the gun will speak at all."""

    def test_a_loaded_gun_that_bears_will_fire(self):
        self.assertTrue(can_fire(a_mount(), 90.0, 300.0, 0.0))

    def test_an_empty_gun_will_not(self):
        self.assertEqual(can_fire(a_mount(loaded=False), 90.0, 300.0, 0.0).code, NOT_LOADED)

    def test_a_gun_still_being_served_will_not(self):
        mount = a_mount(ready_at=100.0)
        self.assertEqual(can_fire(mount, 90.0, 300.0, 50.0).code, STILL_RELOADING)

    def test_a_gun_that_does_not_bear_will_not(self):
        self.assertEqual(can_fire(a_mount(), -90.0, 300.0, 0.0).code, WILL_NOT_BEAR)

    def test_a_target_beyond_reach_will_not(self):
        self.assertEqual(can_fire(a_mount(), 90.0, 9000.0, 0.0).code, OUT_OF_RANGE)

    def test_the_charge_is_checked_before_the_range(self):
        """
        Telling a captain his gun is out of range when it is not even loaded
        helps nobody.

        """
        empty = a_mount(loaded=False)
        self.assertEqual(can_fire(empty, 90.0, 9000.0, 0.0).code, NOT_LOADED)

    def test_serving_her_loads_and_starts_the_clock(self):
        served = serve(a_mount(loaded=False), 100.0)
        self.assertTrue(served.loaded)
        self.assertAlmostEqual(served.ready_at, 100.0 + GUN.reload_time)


class TestFiring(BaseEvenniaTestCase):
    """Pulling the lanyard."""

    def shoot(self, roll, **kwargs):
        """
        Args:
            roll (float): The die, as a fixed value.
            **kwargs: Overrides.

        Returns:
            result (ShotResult): What came of it.

        """
        attempt = {
            "mount": a_mount(),
            "position": HERE,
            "heading": NORTH,
            "target": "her",
            "target_position": ASTARBOARD,
            "target_heading": NORTH,
            "target_speed": 0.0,
            "sea_state": CALM,
            "now": 0.0,
            "roll": lambda: roll,
        }
        attempt.update(kwargs)
        return fire(**attempt)

    def test_a_certain_roll_hits(self):
        self.assertTrue(self.shoot(0.0))

    def test_a_hopeless_roll_misses(self):
        self.assertFalse(self.shoot(1.0))

    def test_a_hit_carries_its_damage(self):
        self.assertAlmostEqual(self.shoot(0.0).damage, GUN.damage)

    def test_a_miss_carries_none(self):
        self.assertAlmostEqual(self.shoot(1.0).damage, 0.0)

    def test_both_carry_the_solution(self):
        """A miss is as informative as a hit; the gunner learns from it."""
        for roll in (0.0, 1.0):
            result = self.shoot(roll)
            self.assertGreater(result.flight_time, 0.0)
            self.assertIsNotNone(result.aim_point)

    def test_a_refused_shot_never_reaches_the_roll(self):
        def explode():
            raise AssertionError("the die should not have been thrown")

        self.assertFalse(
            fire(
                a_mount(loaded=False),
                HERE,
                NORTH,
                "her",
                ASTARBOARD,
                NORTH,
                0.0,
                CALM,
                0.0,
                explode,
            )
        )

    def test_the_random_stream_is_handed_in(self):
        """
        Law 9. A fight replays identically from the same seed, and a test can
        hand in a fixed roll and know exactly what should happen.

        """
        self.assertTrue(self.shoot(0.0))
        self.assertFalse(self.shoot(1.0))

    def test_a_heavy_sea_makes_the_same_shot_harder(self):
        calm = self.shoot(0.5, sea_state=CALM).chance
        rough = self.shoot(0.5, sea_state=PHENOMENAL).chance
        self.assertLess(rough, calm)

    def test_a_bow_on_target_is_harder_than_a_beam_on_one(self):
        beam = self.shoot(0.5, target_heading=NORTH).chance
        bow = self.shoot(0.5, target_heading=EAST).chance
        self.assertLess(bow, beam)


class TestArmedVessel(EmptySeaMixin, BaseEvenniaTest):
    """The guns a ship carries."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Test Sloop")
        self.hull.maritime_position = HERE
        self.hull.heading = NORTH

    def test_she_starts_unarmed(self):
        self.assertEqual(self.hull.mounts, ())

    def test_a_gun_can_be_put_aboard(self):
        self.hull.add_mount(a_mount())
        self.assertEqual(len(self.hull.mounts), 1)

    def test_two_guns_cannot_share_a_name(self):
        self.hull.add_mount(a_mount())
        with self.assertRaises(ValueError):
            self.hull.add_mount(a_mount())

    def test_a_gun_can_be_found_by_name(self):
        self.hull.add_mount(a_mount())
        self.assertIsNotNone(self.hull.mount_named("STARBOARD ONE"))

    def test_serving_a_gun_writes_it_back(self):
        """
        Mounts are frozen, so a change makes a new one - and the stored list has
        to be told, or the reload clock is lost the moment it is set.

        """
        self.hull.add_mount(a_mount(loaded=False))
        self.hull.replace_mount(serve(self.hull.mount_named("starboard one"), 10.0))
        self.assertTrue(self.hull.mount_named("starboard one").loaded)

    def test_only_the_guns_that_bear_are_offered(self):
        self.hull.add_mount(a_mount(key="starboard one"))
        port_gun = WeaponType(key="port nine", name="port nine", arc=PORT_BROADSIDE)
        self.hull.add_mount(Mount(key="port one", weapon=port_gun, loaded=True))
        bearing = self.hull.guns_bearing(90.0)
        self.assertEqual([mount.key for mount in bearing], ["starboard one"])

    def test_a_target_fine_on_the_bow_can_bring_two_arcs_to_bear(self):
        self.hull.add_mount(a_mount(key="starboard one"))
        chaser = WeaponType(key="bow chaser", name="bow chaser", arc=FORWARD)
        self.hull.add_mount(Mount(key="chaser", weapon=chaser, loaded=True))
        self.assertEqual(len(self.hull.guns_bearing(40.0)), 2)

    def test_two_ships_keep_their_own_reload_clocks(self):
        other = create.create_object(Vessel, key="Marigold")
        self.hull.add_mount(a_mount(ready_at=500.0))
        other.add_mount(a_mount(ready_at=0.0))
        self.assertNotEqual(
            self.hull.mount_named("starboard one").ready_at,
            other.mount_named("starboard one").ready_at,
        )
