"""
Tests for battle repairs.

The claim the whole item rests on: **a jury rig is a scar, not a cooldown.** It does not
tick down, time does not heal it, and nothing aboard can lift it - so a ship carrying one
has somewhere she needs to be, which is a reason to make port no repair-over-time system
has.

"""

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest

from ..damage import HULL, MAST_DOWN_AT, OARS, RIGGING, WEAPONS
from ..motion import MotionLimits
from ..position import WorldPosition
from ..repairs import (
    DOING_NOTHING_ELSE,
    JURY_RIG_CEILING,
    JURY_RIG_PENALTY,
    canvas_after_jury_rig,
    doing_nothing_else,
    party_rate,
)
from ..rooms import ShipRoom
from ..sailing import FULL, FURLED
from ..typeclasses import Vessel
from ..vessel import OPEN

A_DAY = 86400.0


class TestTheArithmetic(BaseEvenniaTest):
    """The rates, with no ship attached."""

    def test_nobody_on_it_mends_nothing(self):
        self.assertEqual(party_rate(0), 0.0)

    def test_more_hands_mend_faster(self):
        self.assertGreater(party_rate(20), party_rate(5))

    def test_but_past_the_work_they_are_in_the_way(self):
        self.assertAlmostEqual(party_rate(20), party_rate(2000))

    def test_hove_to_counts_as_doing_nothing_else(self):
        self.assertTrue(doing_nothing_else(0.0, 0.0))

    def test_carrying_on_does_not(self):
        self.assertFalse(doing_nothing_else(4.0, 1.0))

    def test_nor_does_lying_still_with_canvas_set(self):
        """She is waiting for wind, not working. The hands are still at the sheets."""
        self.assertFalse(doing_nothing_else(0.0, 1.0))

    def test_a_sound_rig_is_not_docked(self):
        self.assertAlmostEqual(canvas_after_jury_rig(1.0, False), 1.0)

    def test_a_jury_rig_is(self):
        self.assertAlmostEqual(canvas_after_jury_rig(1.0, True), 1.0 - JURY_RIG_PENALTY)

    def test_and_it_costs_her_at_every_plan(self):
        """Multiplied, not capped: it is her rig that is worse, not her orders."""
        self.assertLess(canvas_after_jury_rig(0.5, True), 0.5)


class RepairTestCase(BaseEvenniaTest):
    """A hull with something wrong with her."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Kestrel")
        self.hull.length, self.hull.beam = 18.0, 5.4
        self.hull.motion_limits = MotionLimits(max_speed=6.0, acceleration=0.5, turn_rate=5.0)
        self.hull.maritime_position = WorldPosition(0.0, 0.0)
        self.hull.sail_plan = FURLED
        deck = create.create_object(ShipRoom, key="Main Deck")
        deck.vessel = self.hull
        deck.exposure = OPEN

    def hurt(self, track, amount):
        """Break something."""
        self.hull.damage = self.hull.damage.hurt(track, amount)


class TestWorkingOnHer(RepairTestCase):
    """What her own people can put right."""

    def test_nobody_set_to_it_does_nothing(self):
        self.hurt(HULL, 0.5)
        self.assertIsNone(self.hull.work_repairs(A_DAY))

    def test_a_party_mends_her_hull(self):
        self.hurt(HULL, 0.5)
        self.hull.set_carpenters(20)
        self.hull.work_repairs(A_DAY)
        self.assertLess(self.hull.damage.of(HULL), 0.5)

    def test_and_her_oars(self):
        self.hurt(OARS, 0.5)
        self.hull.set_carpenters(20)
        self.hull.work_repairs(A_DAY)
        self.assertLess(self.hull.damage.of(OARS), 0.5)

    def test_but_never_her_guns(self):
        """
        She carries spares for neither a carriage nor a gun, unless she took them out of a
        prize. A dismounted gun waits for a yard.

        """
        self.hurt(WEAPONS, 0.5)
        self.hull.set_carpenters(20)
        self.hull.work_repairs(A_DAY)
        self.assertAlmostEqual(self.hull.damage.of(WEAPONS), 0.5)

    def test_the_guns_are_named_as_wanting_a_yard(self):
        self.hurt(WEAPONS, 0.5)
        self.assertIn(WEAPONS, self.hull.wants_a_yard())

    def test_hove_to_she_works_at_twice_the_rate(self):
        self.hull.set_carpenters(20)
        self.hull.ndb.speed = 0.0
        self.hull.sail_plan = FURLED
        quiet = self.hull.repair_report().rate

        self.hull.ndb.speed = 4.0
        self.hull.sail_plan = FULL
        carrying_on = self.hull.repair_report().rate

        self.assertAlmostEqual(quiet, carrying_on * DOING_NOTHING_ELSE)

    def test_nothing_to_mend_is_nothing_done(self):
        self.hull.set_carpenters(20)
        self.assertIsNone(self.hull.work_repairs(A_DAY))


class TestTheJuryRig(RepairTestCase):
    """The scar, which is the whole item."""

    def setUp(self):
        super().setUp()
        self.hurt(RIGGING, 0.9)
        self.hull.set_carpenters(20)

    def test_she_starts_properly_rigged(self):
        self.assertFalse(create.create_object(Vessel, key="Sound").jury_rigged)

    def test_working_a_mast_that_has_gone_leaves_a_jury_rig(self):
        self.hull.work_repairs(A_DAY)
        self.assertTrue(self.hull.jury_rigged)

    def test_it_can_be_worked_back_to_the_ceiling(self):
        for _ in range(10):
            self.hull.work_repairs(A_DAY)
        self.assertAlmostEqual(self.hull.damage.of(RIGGING), 1.0 - JURY_RIG_CEILING, places=3)

    def test_and_no_further_however_long_they_work(self):
        """
        A scar, not a slow repair. Working longer is the thing that does not help, and it
        is the difference between the two.

        """
        for _ in range(10):
            self.hull.work_repairs(A_DAY)
        settled = self.hull.damage.of(RIGGING)
        for _ in range(30):
            self.hull.work_repairs(A_DAY)
        self.assertAlmostEqual(self.hull.damage.of(RIGGING), settled, places=6)

    def test_she_is_slower_for_it(self):
        self.hull.work_repairs(A_DAY)
        self.hull.sail_plan = FULL
        rigged = self.hull.sailing_speed()

        self.hull.db.jury_rigged = False
        self.hull.damage = self.hull.damage.mended(RIGGING, 1.0)
        sound = self.hull.sailing_speed()
        self.assertLess(rigged, sound)

    def test_and_she_is_named_as_wanting_a_yard(self):
        self.hull.work_repairs(A_DAY)
        self.assertIn(RIGGING, self.hull.wants_a_yard())

    def test_rigging_merely_cut_about_is_not_a_jury_rig(self):
        """A mast down is a different thing from shot through the shrouds."""
        sound = create.create_object(Vessel, key="Petrel")
        sound.damage = sound.damage.hurt(RIGGING, MAST_DOWN_AT / 2.0)
        sound.set_carpenters(20)
        sound.work_repairs(A_DAY)
        self.assertFalse(sound.jury_rigged)


class TestWhatAYardDoes(RepairTestCase):
    """The only thing that lifts a scar."""

    def test_it_puts_everything_right(self):
        for track in (HULL, RIGGING, OARS, WEAPONS):
            self.hurt(track, 0.6)
        self.hull.refit()
        for track in (HULL, RIGGING, OARS, WEAPONS):
            self.assertAlmostEqual(self.hull.damage.of(track), 0.0, places=6)

    def test_including_the_guns_her_people_could_not(self):
        self.hurt(WEAPONS, 0.6)
        self.hull.refit()
        self.assertAlmostEqual(self.hull.damage.of(WEAPONS), 0.0, places=6)

    def test_and_it_is_the_only_thing_that_lifts_a_jury_rig(self):
        self.hurt(RIGGING, 0.9)
        self.hull.set_carpenters(20)
        self.hull.work_repairs(A_DAY)
        self.assertTrue(self.hull.jury_rigged)

        self.hull.refit()
        self.assertFalse(self.hull.jury_rigged)
        self.assertEqual(self.hull.wants_a_yard(), ())
