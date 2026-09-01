"""
Tests for dead reckoning, and for being wrong about where you are.

"""

from django.test import override_settings
from evennia.utils import create
from evennia.utils.test_resources import (
    BaseEvenniaCommandTest,
    BaseEvenniaTest,
    BaseEvenniaTestCase,
)

from ..commands import CmdFix
from ..motion import HelmOrders, MotionLimits
from ..navigation import (
    FIX_UNCERTAINTY,
    UNCERTAINTY_PER_DISTANCE,
    DeadReckoning,
    error_of,
    reckon,
    set_and_drift,
    take_fix,
)
from ..ports import Berth
from ..position import EAST, NORTH, SOUTH, WorldPosition
from ..rooms import PortRoom, ShipRoom
from ..typeclasses import Vessel
from ..vessel import OPEN
from .base import EmptySeaMixin

HERE = WorldPosition(0.0, 0.0)


class TestReckoning(BaseEvenniaTestCase):
    """Advancing an estimate by course and log."""

    def test_it_advances_on_the_course_steered(self):
        dr = reckon(take_fix(HERE, 0.0), EAST, 5.0, 100.0)
        self.assertAlmostEqual(dr.position.x, 500.0)

    def test_it_accumulates_the_distance_run(self):
        dr = reckon(reckon(take_fix(HERE, 0.0), EAST, 5.0, 100.0), EAST, 5.0, 100.0)
        self.assertAlmostEqual(dr.run, 1000.0)

    def test_standing_still_does_not_advance_it(self):
        dr = take_fix(HERE, 0.0)
        self.assertEqual(reckon(dr, EAST, 0.0, 100.0), dr)

    def test_negative_time_does_not_advance_it(self):
        dr = take_fix(HERE, 0.0)
        self.assertEqual(reckon(dr, EAST, 5.0, -10.0), dr)

    def test_uncertainty_grows_with_the_run(self):
        near = reckon(take_fix(HERE, 0.0), EAST, 5.0, 100.0)
        far = reckon(take_fix(HERE, 0.0), EAST, 5.0, 10000.0)
        self.assertGreater(far.uncertainty, near.uncertainty)

    def test_a_fresh_fix_is_not_perfectly_certain(self):
        """
        Fixing by eye off a landmark is good, not exact. A navigator who believed
        a fix absolutely would never revise it.

        """
        self.assertAlmostEqual(take_fix(HERE, 0.0).uncertainty, FIX_UNCERTAINTY)

    def test_uncertainty_is_a_fraction_of_the_run(self):
        dr = reckon(take_fix(HERE, 0.0), EAST, 10.0, 100.0)
        self.assertAlmostEqual(dr.uncertainty, FIX_UNCERTAINTY + UNCERTAINTY_PER_DISTANCE * 1000.0)

    def test_a_fix_resets_the_run(self):
        dr = reckon(take_fix(HERE, 0.0), EAST, 5.0, 1000.0)
        self.assertAlmostEqual(take_fix(dr.position, 100.0).run, 0.0)


class TestSetAndDrift(BaseEvenniaTestCase):
    """Learning the current by being wrong about where you were."""

    def test_the_difference_over_the_time_is_the_current(self):
        """
        Real practice, and the payoff of taking a fix: the vector from where you
        thought you were to where you are, divided by the elapsed time.

        """
        dr = DeadReckoning(position=HERE, run=1000.0, elapsed=100.0, fixed_at=0.0)
        current = set_and_drift(dr, WorldPosition(0.0, 200.0))
        self.assertAlmostEqual(current.drift, 2.0)
        self.assertAlmostEqual(current.set, NORTH)

    def test_being_exactly_right_means_slack_water(self):
        dr = DeadReckoning(position=HERE, run=1000.0, elapsed=100.0, fixed_at=0.0)
        self.assertFalse(set_and_drift(dr, HERE).running)

    def test_no_elapsed_time_gives_no_answer(self):
        """A reckoning that has not run anywhere has learned nothing."""
        dr = DeadReckoning(position=HERE, run=0.0, elapsed=0.0, fixed_at=0.0)
        self.assertFalse(set_and_drift(dr, WorldPosition(0.0, 200.0)).running)

    def test_the_reckoning_carries_its_own_elapsed_time(self):
        """
        Rather than asking a clock. Dividing by wall time assumes the reckoning
        was advanced in step with it, which is false for any caller that ticks a
        vessel faster or slower than real - every test, and the whole strategic
        tier.

        """
        dr = reckon(take_fix(HERE, 0.0), EAST, 5.0, 600.0)
        self.assertAlmostEqual(dr.elapsed, 600.0)


class ReckoningTestCase(EmptySeaMixin, BaseEvenniaTest):
    """A hull under way with a reckoning running."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Test Sloop")
        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.deck.vessel = self.hull
        self.deck.exposure = OPEN
        self.hull.maritime_position = WorldPosition(0.0, 0.0)
        self.hull.motion_limits = MotionLimits(max_speed=10.0, acceleration=100.0, turn_rate=8.0)
        self.hull.heading = EAST
        self.hull.speed = 5.0
        self.hull.orders = HelmOrders(heading=EAST, speed=5.0)
        self.hull.start_reckoning()

    def run_for(self, ticks=10, seconds=60.0, **settings):
        """
        Args:
            ticks (int): How many ticks to run.
            seconds (float): Game seconds per tick.
            **settings: Overrides for the run.

        """
        base = {"MARITIME_DEFAULT_DEPTH": 1000.0, "MARITIME_MAP_PROVIDER": ""}
        base.update(settings)
        with override_settings(**base):
            for _ in range(ticks):
                self.hull.at_maritime_tick(seconds)


class TestVesselReckoning(ReckoningTestCase):
    """What the crew believe, against what is true."""

    def test_in_slack_water_the_reckoning_is_right(self):
        """
        And it should be. Nothing here rolls an error - a ship whose water is not
        moving and who makes no leeway is not lost, and should not be made lost
        for the sake of a mechanic.

        """
        self.run_for()
        self.assertAlmostEqual(error_of(self.hull.dead_reckoning, self.hull.maritime_position), 0.0)

    def test_a_current_makes_her_wrong(self):
        self.run_for(MARITIME_CURRENT_SET=SOUTH, MARITIME_CURRENT_DRIFT=1.0)
        self.assertGreater(error_of(self.hull.dead_reckoning, self.hull.maritime_position), 100.0)

    def test_the_error_is_exactly_what_the_water_did(self):
        """
        Not approximately, and not randomly. Six hundred seconds of one metre a
        second is six hundred metres of error, because the error *is* the
        current she could not see.

        """
        self.run_for(MARITIME_CURRENT_SET=SOUTH, MARITIME_CURRENT_DRIFT=1.0)
        self.assertAlmostEqual(
            error_of(self.hull.dead_reckoning, self.hull.maritime_position), 600.0, places=3
        )

    def test_the_longer_she_runs_the_worse_it_gets(self):
        self.run_for(ticks=3, MARITIME_CURRENT_SET=SOUTH, MARITIME_CURRENT_DRIFT=1.0)
        early = error_of(self.hull.dead_reckoning, self.hull.maritime_position)
        self.run_for(ticks=7, MARITIME_CURRENT_SET=SOUTH, MARITIME_CURRENT_DRIFT=1.0)
        self.assertGreater(error_of(self.hull.dead_reckoning, self.hull.maritime_position), early)

    def test_the_crew_are_shown_the_reckoning_not_the_truth(self):
        self.run_for(MARITIME_CURRENT_SET=SOUTH, MARITIME_CURRENT_DRIFT=1.0)
        self.assertNotEqual(self.hull.reckoned_position, self.hull.maritime_position)
        self.assertEqual(self.hull.reckoned_position, self.hull.dead_reckoning.position)

    def test_a_vessel_with_no_reckoning_falls_back_to_the_truth(self):
        """A hull that has never run anywhere has nothing to be wrong about."""
        idle = create.create_object(Vessel, key="On The Stocks")
        idle.maritime_position = WorldPosition(5.0, 5.0)
        self.assertEqual(idle.reckoned_position, idle.maritime_position)

    def test_a_fix_puts_her_right(self):
        self.run_for(MARITIME_CURRENT_SET=SOUTH, MARITIME_CURRENT_DRIFT=1.0)
        self.hull.fix_position()
        self.assertAlmostEqual(error_of(self.hull.dead_reckoning, self.hull.maritime_position), 0.0)

    def test_a_fix_reports_the_set_she_has_been_carrying(self):
        """
        The real prize. Not that she now knows where she is, but that she now
        knows what has been moving her - which is the input for steering the next
        leg to allow for it.

        """
        self.run_for(MARITIME_CURRENT_SET=SOUTH, MARITIME_CURRENT_DRIFT=1.0)
        learned = self.hull.fix_position()
        self.assertAlmostEqual(learned.set, SOUTH, places=3)
        self.assertAlmostEqual(learned.drift, 1.0, places=3)

    def test_fixing_an_unlaunched_vessel_teaches_nothing(self):
        idle = create.create_object(Vessel, key="On The Stocks")
        self.assertFalse(idle.fix_position().running)

    def test_being_made_fast_is_a_fix(self):
        """
        Lying at a quay whose position is on the chart is knowing where you are.

        """
        port = create.create_object(PortRoom, key="Quay")
        port.maritime_position = WorldPosition(900.0, 0.0)
        berth = Berth(key="quay", position=WorldPosition(900.0, 0.0), heading=EAST)
        self.run_for(MARITIME_CURRENT_SET=SOUTH, MARITIME_CURRENT_DRIFT=1.0)
        self.hull.make_fast(port, berth)
        self.assertAlmostEqual(error_of(self.hull.dead_reckoning, self.hull.maritime_position), 0.0)


class TestCmdFix(EmptySeaMixin, BaseEvenniaCommandTest):
    """Taking a bearing on something you can name."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Test Sloop")
        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.deck.vessel = self.hull
        self.deck.exposure = OPEN
        self.hull.maritime_position = WorldPosition(0.0, 0.0)
        self.hull.heading = EAST
        self.char1.location = self.deck

        self.port = create.create_object(PortRoom, key="North Quay")
        self.port.maritime_position = WorldPosition(500.0, 0.0)
        self.port.add_berth(Berth(key="quay", position=WorldPosition(500.0, 0.0), heading=EAST))

    def test_a_landmark_in_sight_gives_a_fix(self):
        output = self.call(CmdFix(), "")
        self.assertIn("works the fix", output)

    def test_out_of_sight_of_land_there_is_nothing_to_fix_on(self):
        """
        Which is why the open sea is where dead reckoning matters, and why
        sailors hugged coastlines for centuries.

        """
        self.hull.maritime_position = WorldPosition(90000.0, 0.0)
        output = self.call(CmdFix(), "")
        self.assertIn("No landmark in sight", output)

    def test_a_good_reckoning_is_confirmed_rather_than_corrected(self):
        self.hull.start_reckoning()
        output = self.call(CmdFix(), "")
        self.assertIn("where you reckoned her", output)

    def test_a_bad_reckoning_is_corrected_by_a_stated_amount(self):
        self.hull.dead_reckoning = take_fix(WorldPosition(0.0, 4000.0), 0.0)
        output = self.call(CmdFix(), "")
        self.assertIn("out by", output)
