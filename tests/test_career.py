"""
Tests for the things worth having done.

The claim: **this contrib knows when they happen and now says so.** Nothing here is a skill
system, a reputation or a level - a game that counts prizes has a pirate and one that counts
cargo delivered has a merchant, and they are the same events counted differently.

"""

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest

from ..cargo import commodity_named
from ..career import (
    TIDE,
    WORK,
    CameOffTheGround,
    CargoLanded,
    PassageMade,
    came_off_the_ground,
    cargo_landed,
    passage_made,
)
from ..events import bus
from ..motion import MotionLimits
from ..position import WorldPosition
from ..rooms import ShipRoom
from ..typeclasses import Vessel
from ..vessel import BELOW_WATERLINE, OPEN, VesselCapacity


class CareerTestCase(BaseEvenniaTest):
    """A hull and somebody listening for what she does."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Kestrel")
        self.hull.length, self.hull.beam = 18.0, 5.4
        self.hull.motion_limits = MotionLimits(max_speed=6.0, acceleration=0.5, turn_rate=5.0)
        self.hull.maritime_position = WorldPosition(0.0, 0.0)
        self.master = create.create_object(
            "evennia.objects.objects.DefaultCharacter", key="The master"
        )
        self.hull.pass_command(self.master)
        self.heard = []


class TestAPassageMade(CareerTestCase):
    """Arriving where she was told to go."""

    def setUp(self):
        super().setUp()
        bus().subscribe(PassageMade, self.heard.append)

    def test_it_is_announced(self):
        passage_made(self.hull, sailed=1000.0)
        self.assertEqual(len(self.heard), 1)

    def test_and_says_who_had_her(self):
        passage_made(self.hull, sailed=1000.0)
        self.assertIs(self.heard[0].captain, self.master)

    def test_and_how_far_she_sailed(self):
        passage_made(self.hull, sailed=1234.0)
        self.assertAlmostEqual(self.heard[0].sailed, 1234.0)


class TestTheLog(CareerTestCase):
    """What she sailed, not how far apart the two places are."""

    def test_a_new_hull_has_run_nothing(self):
        self.assertAlmostEqual(self.hull.distance_run, 0.0)

    def test_it_counts_up(self):
        self.hull.enter_in_the_log(100.0)
        self.hull.enter_in_the_log(50.0)
        self.assertAlmostEqual(self.hull.distance_run, 150.0)

    def test_streaming_it_starts_again(self):
        self.hull.enter_in_the_log(100.0)
        self.assertAlmostEqual(self.hull.stream_the_log(), 100.0)
        self.assertAlmostEqual(self.hull.distance_run, 0.0)

    def test_nothing_is_entered_for_nothing(self):
        self.hull.enter_in_the_log(0.0)
        self.assertAlmostEqual(self.hull.distance_run, 0.0)

    def test_beating_up_is_longer_than_the_chart_says(self):
        """
        The reason the log exists rather than a straight line between two marks. She tacks,
        so she sails further than the passage is - and a career paying by the straight line
        would pay a good captain less for the harder passage.

        """
        for leg in (400.0, 400.0, 400.0):
            self.hull.enter_in_the_log(leg)
        straight_line = 900.0
        self.assertGreater(self.hull.distance_run, straight_line)


class TestCargoLanded(CareerTestCase):
    """What a merchant's career is counted in."""

    def setUp(self):
        super().setUp()
        bus().subscribe(CargoLanded, self.heard.append)

    def test_it_is_announced(self):
        cargo_landed(self.hull, "salt", 12.0)
        self.assertEqual(len(self.heard), 1)

    def test_and_says_what_and_how_much(self):
        cargo_landed(self.hull, "salt", 12.0)
        self.assertEqual(self.heard[0].commodity, "salt")
        self.assertAlmostEqual(self.heard[0].tonnes, 12.0)

    def test_landing_nothing_says_nothing(self):
        """
        An event announcing that nothing happened is an event a game has to learn to
        ignore.

        """
        self.assertIsNone(cargo_landed(self.hull, "salt", 0.0))
        self.assertEqual(self.heard, [])

    def test_a_real_discharge_announces_itself(self):
        """Wired where cargo actually leaves her, not where a game runs a sale."""
        self.hull.light_draft = 2.0
        self.hull.capacity = VesselCapacity(
            displacement=120000.0, internal_volume=200.0, stability_moment=100000.0
        )
        hold = create.create_object(ShipRoom, key="Hold")
        hold.vessel = self.hull
        hold.deck_level = -1
        hold.exposure = BELOW_WATERLINE
        hold.hold_capacity = 120.0
        deck = create.create_object(ShipRoom, key="Deck")
        deck.vessel = self.hull
        deck.exposure = OPEN

        salt = commodity_named("salt")
        if salt is None:
            self.skipTest("the shipped commodities do not include salt")
        self.assertTrue(self.hull.load(salt, 5.0), "the fixture never got the cargo aboard")

        self.hull.discharge(salt, 5.0)
        self.assertTrue(self.heard)
        self.assertGreater(self.heard[-1].tonnes, 0.0)


class TestComingOffTheGround(CareerTestCase):
    """How she came off is the whole of the news."""

    def setUp(self):
        super().setUp()
        bus().subscribe(CameOffTheGround, self.heard.append)

    def test_the_tide_lifting_her_is_announced(self):
        came_off_the_ground(self.hull, TIDE, 0.1)
        self.assertEqual(self.heard[0].by, TIDE)

    def test_and_so_is_being_hauled_off(self):
        came_off_the_ground(self.hull, WORK, 0.1)
        self.assertEqual(self.heard[0].by, WORK)

    def test_the_two_are_told_apart(self):
        """
        Waiting for the tide is patience and kedging her off is work. A game rewarding
        seamanship rather than endurance needs to know which happened.

        """
        self.assertNotEqual(TIDE, WORK)

    def test_it_carries_what_the_grounding_cost_her(self):
        came_off_the_ground(self.hull, WORK, 0.35)
        self.assertAlmostEqual(self.heard[0].hurt, 0.35)
