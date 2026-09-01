"""
Tests for running a shot the length of a ship.

The most famous manoeuvre of the age, and here it is not a rule - it falls out of the
geometry the system was already computing. In a hex game raking needs a table of impact
modifiers; with a continuous bearing, the angle on her bow *is* the point of impact.

"""

from evennia.utils.test_resources import BaseEvenniaTestCase

from ..ammunition import BALL
from ..position import WorldPosition
from ..tactical import (
    BOW_RAKE,
    BOW_RAKE_WEIGHT,
    RAKE_ARC,
    STARBOARD_BROADSIDE,
    STERN_RAKE,
    STERN_RAKE_WEIGHT,
    raking,
    raking_weight,
)
from ..weapons import Mount, WeaponType, fire
from ..weather import CALM

HERE = WorldPosition(0.0, 0.0)
GUN = WeaponType(
    key="nine", name="nine-pounder", arc=STARBOARD_BROADSIDE, max_range=800.0, damage=10.0
)


class TestWhereAShotGoesIn(BaseEvenniaTestCase):
    """Which end of her, if either."""

    def test_dead_ahead_of_her_is_a_bow_rake(self):
        self.assertEqual(raking(0.0), BOW_RAKE)

    def test_dead_astern_of_her_is_a_stern_rake(self):
        self.assertEqual(raking(180.0), STERN_RAKE)

    def test_and_so_is_dead_astern_the_other_way_round(self):
        self.assertEqual(raking(-180.0), STERN_RAKE)

    def test_on_her_beam_is_neither(self):
        self.assertIsNone(raking(90.0))
        self.assertIsNone(raking(-90.0))

    def test_it_works_from_either_side(self):
        self.assertEqual(raking(20.0), raking(-20.0))

    def test_the_arc_is_narrow(self):
        """A position you have to achieve, not one you drift into."""
        self.assertIsNone(raking(RAKE_ARC + 1.0))
        self.assertEqual(raking(RAKE_ARC - 1.0), BOW_RAKE)


class TestWhatARakeIsWorth(BaseEvenniaTestCase):
    """The damage half, which is the whole point."""

    def test_a_beam_hit_is_an_ordinary_hit(self):
        self.assertAlmostEqual(raking_weight(90.0), 1.0)

    def test_a_stern_rake_is_the_worst_thing_that_can_happen_to_her(self):
        self.assertAlmostEqual(raking_weight(180.0), STERN_RAKE_WEIGHT)

    def test_a_bow_rake_is_bad_but_not_as_bad(self):
        """
        Structural rather than arbitrary. A bow is solid timber and knees built to
        meet the sea; a stern is windows, cabin and the weakest framing in the ship.

        """
        self.assertAlmostEqual(raking_weight(0.0), BOW_RAKE_WEIGHT)
        self.assertLess(raking_weight(0.0), raking_weight(180.0))

    def test_it_tapers_rather_than_stepping(self):
        """
        A shot fine on her bow is nearly a rake and ought to be worth nearly as
        much. A threshold would make two degrees the difference between a scratch
        and a catastrophe, which no gunner would recognise.

        """
        self.assertGreater(raking_weight(5.0), raking_weight(20.0))
        self.assertGreater(raking_weight(20.0), raking_weight(32.0))

    def test_and_falls_away_quickly(self):
        """Most of the benefit is in the last few degrees, which is why it is hard."""
        self.assertLess(raking_weight(RAKE_ARC * 0.8), 1.0 + (BOW_RAKE_WEIGHT - 1.0) * 0.25)

    def test_it_is_continuous_at_the_edge_of_the_arc(self):
        """No cliff. Just outside the arc and just inside are almost the same shot."""
        self.assertAlmostEqual(raking_weight(RAKE_ARC), 1.0, places=6)

    def test_nothing_outside_the_arc_is_worth_more(self):
        for aspect in (45.0, 60.0, 90.0, 120.0, 135.0):
            self.assertAlmostEqual(raking_weight(aspect), 1.0)


class TestRakingInAnger(BaseEvenniaTestCase):
    """Firing it, rather than computing it."""

    def shoot(self, target_heading, roll=0.0):
        """
        Args:
            target_heading (float): Which way she is pointing. We lie due east of
                her, so her heading decides what we are looking at.
            roll (float, optional): The injected die.

        Returns:
            result (ShotResult): What came of it.

        """
        mount = Mount(key="starboard one", weapon=GUN, loaded=True, ready_at=0.0, shot=BALL)
        target = HERE.moved(90.0, 200.0)
        return fire(mount, HERE, 0.0, "her", target, target_heading, 0.0, CALM, 0.0, lambda: roll)

    def test_catching_her_stern_on_rakes_her(self):
        """She is running due east; we are astern of her, dead in line."""
        result = self.shoot(target_heading=90.0)
        self.assertEqual(result.rake, STERN_RAKE)

    def test_meeting_her_bow_on_rakes_her_too(self):
        result = self.shoot(target_heading=270.0)
        self.assertEqual(result.rake, BOW_RAKE)

    def test_taking_her_on_the_beam_does_not(self):
        result = self.shoot(target_heading=0.0)
        self.assertIsNone(result.rake)

    def test_a_rake_tells_far_harder(self):
        raked = self.shoot(target_heading=90.0).damage
        beam = self.shoot(target_heading=0.0).damage
        self.assertGreater(raked, beam * 2)

    def test_a_miss_is_still_a_miss(self):
        """Position does not fire the gun for you."""
        self.assertFalse(self.shoot(target_heading=90.0, roll=1.0))

    def test_a_missed_rake_carries_the_geometry_anyway(self):
        """A gunner learns from it: he had the position and lost the shot."""
        missed = self.shoot(target_heading=90.0, roll=1.0)
        self.assertEqual(missed.rake, STERN_RAKE)
        self.assertAlmostEqual(missed.damage, 0.0)
