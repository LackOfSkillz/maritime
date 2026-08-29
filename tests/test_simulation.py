"""
Tests for the maritime simulation service.

"""

from evennia.utils.test_resources import BaseEvenniaTestCase

from ..clock import ManualTimeProvider
from ..simulation import (
    ACTIVE,
    DORMANT,
    MAX_CATCHUP_SECONDS,
    STRATEGIC,
    TACTICAL,
    TIER_INTERVALS,
    MaritimeSimulationService,
)


class Ship:
    """A registered entity that records how it was simulated."""

    def __init__(self, name="ship", explode=False):
        self.name = name
        self.explode = explode
        self.ticks = []
        self.saves = 0
        self.dirty = True

    def at_maritime_tick(self, elapsed):
        if self.explode:
            raise RuntimeError("bad update")
        self.ticks.append(elapsed)

    def checkpoint(self):
        if not self.dirty:
            return False
        self.dirty = False
        self.saves += 1
        return True

    def __repr__(self):
        return f"<Ship {self.name}>"


class Inert:
    """An entity with no maritime hooks at all."""


class ServiceTestCase(BaseEvenniaTestCase):
    """Shared setup with a hand-driven clock."""

    def setUp(self):
        super().setUp()
        self.clock = ManualTimeProvider()
        self.service = MaritimeSimulationService(self.clock)


class TestRegistration(ServiceTestCase):
    """Joining and leaving the simulation."""

    def test_starts_empty(self):
        self.assertEqual(len(self.service), 0)

    def test_register_adds(self):
        ship = Ship()
        self.assertTrue(self.service.register(ship))
        self.assertIn(ship, self.service)

    def test_register_defaults_to_active(self):
        ship = Ship()
        self.service.register(ship)
        self.assertEqual(self.service.tier_of(ship), ACTIVE)

    def test_registering_twice_updates_the_tier(self):
        ship = Ship()
        self.service.register(ship)
        self.assertFalse(self.service.register(ship, tier=TACTICAL))
        self.assertEqual(self.service.tier_of(ship), TACTICAL)

    def test_unregister_removes(self):
        ship = Ship()
        self.service.register(ship)
        self.assertTrue(self.service.unregister(ship))
        self.assertNotIn(ship, self.service)

    def test_unregistering_absent_is_not_an_error(self):
        self.assertFalse(self.service.unregister(Ship()))

    def test_unknown_tier_is_refused(self):
        with self.assertRaises(ValueError):
            self.service.register(Ship(), tier="whenever")

    def test_tier_of_unregistered_is_none(self):
        self.assertIsNone(self.service.tier_of(Ship()))

    def test_count_by_tier(self):
        self.service.register(Ship("a"), tier=ACTIVE)
        self.service.register(Ship("b"), tier=STRATEGIC)
        self.assertEqual(self.service.count(ACTIVE), 1)
        self.assertEqual(self.service.count(), 2)

    def test_zero_batch_size_is_refused(self):
        """A batch of zero registers vessels that are never once simulated."""
        with self.assertRaises(ValueError):
            MaritimeSimulationService(self.clock, batch_size=0)


class TestTierIntervals(ServiceTestCase):
    """Different tiers wait different lengths."""

    def test_tiers_get_faster_toward_tactical(self):
        self.assertGreater(TIER_INTERVALS[STRATEGIC], TIER_INTERVALS[ACTIVE])
        self.assertGreater(TIER_INTERVALS[ACTIVE], TIER_INTERVALS[TACTICAL])

    def test_not_due_immediately(self):
        ship = Ship()
        self.service.register(ship)
        self.assertFalse(self.service.is_due(ship))

    def test_due_after_the_interval(self):
        ship = Ship()
        self.service.register(ship, tier=ACTIVE)
        self.clock.advance(seconds=TIER_INTERVALS[ACTIVE])
        self.assertTrue(self.service.is_due(ship))

    def test_strategic_waits_longer_than_active(self):
        distant, near = Ship("distant"), Ship("near")
        self.service.register(distant, tier=STRATEGIC)
        self.service.register(near, tier=ACTIVE)
        self.clock.advance(seconds=TIER_INTERVALS[ACTIVE])
        self.assertTrue(self.service.is_due(near))
        self.assertFalse(self.service.is_due(distant))

    def test_dormant_is_never_due(self):
        """Dormant is off, not merely slow."""
        ship = Ship()
        self.service.register(ship, tier=DORMANT)
        self.clock.advance(days=30)
        self.assertFalse(self.service.is_due(ship))

    def test_unregistered_is_never_due(self):
        self.assertFalse(self.service.is_due(Ship()))


class TestTicking(ServiceTestCase):
    """Running the simulation."""

    def test_nothing_runs_before_the_interval(self):
        ship = Ship()
        self.service.register(ship)
        self.assertEqual(self.service.tick(), ())
        self.assertEqual(ship.ticks, [])

    def test_runs_when_due(self):
        ship = Ship()
        self.service.register(ship)
        self.clock.advance(seconds=TIER_INTERVALS[ACTIVE])
        self.assertEqual(self.service.tick(), (ship,))

    def test_passes_elapsed_game_time(self):
        ship = Ship()
        self.service.register(ship)
        self.clock.advance(seconds=10.0)
        self.service.tick()
        self.assertEqual(ship.ticks, [10.0])

    def test_resets_the_clock_after_updating(self):
        ship = Ship()
        self.service.register(ship)
        self.clock.advance(seconds=10.0)
        self.service.tick()
        self.assertFalse(self.service.is_due(ship))

    def test_dormant_entities_are_skipped(self):
        ship = Ship()
        self.service.register(ship, tier=DORMANT)
        self.clock.advance(days=1)
        self.service.tick()
        self.assertEqual(ship.ticks, [])

    def test_entity_without_a_hook_is_harmless(self):
        self.service.register(Inert())
        self.clock.advance(seconds=100.0)
        self.assertEqual(self.service.tick(), ())

    def test_catchup_is_capped(self):
        """
        A server down for a week must not hand a vessel a week of movement.

        A fixed-step integrator would either grind for an hour or produce
        nonsense.

        """
        ship = Ship()
        self.service.register(ship)
        self.clock.advance(days=7)
        self.service.tick()
        self.assertEqual(ship.ticks, [MAX_CATCHUP_SECONDS])

    def test_counts_ticks_and_updates(self):
        ship = Ship()
        self.service.register(ship)
        self.clock.advance(seconds=10.0)
        self.service.tick()
        self.assertEqual(self.service.ticks_run, 1)
        self.assertEqual(self.service.updates_run, 1)


class TestFailureIsolation(ServiceTestCase):
    """One broken vessel must not stop the world."""

    def test_a_failing_hook_does_not_stop_the_others(self):
        broken, sound = Ship("broken", explode=True), Ship("sound")
        self.service.register(broken)
        self.service.register(sound)
        self.clock.advance(seconds=10.0)
        self.service.tick()
        self.assertEqual(len(sound.ticks), 1)

    def test_a_failing_hook_does_not_propagate(self):
        self.service.register(Ship("broken", explode=True))
        self.clock.advance(seconds=10.0)
        self.service.tick()  # must not raise

    def test_failures_are_counted(self):
        self.service.register(Ship("broken", explode=True))
        self.clock.advance(seconds=10.0)
        self.service.tick()
        self.assertEqual(self.service.failures, 1)

    def test_a_failing_vessel_still_advances_its_clock(self):
        """Otherwise a broken vessel is retried every single pass forever."""
        broken = Ship("broken", explode=True)
        self.service.register(broken)
        self.clock.advance(seconds=10.0)
        self.service.tick()
        self.assertFalse(self.service.is_due(broken))


class TestBudgetAndFairness(ServiceTestCase):
    """A fleet larger than the batch is still served."""

    def test_batch_bounds_one_pass(self):
        service = MaritimeSimulationService(self.clock, batch_size=3)
        fleet = [Ship(str(i)) for i in range(10)]
        for ship in fleet:
            service.register(ship)
        self.clock.advance(seconds=10.0)
        self.assertEqual(len(service.tick()), 3)

    def test_every_vessel_is_reached_across_passes(self):
        """
        The starvation guarantee, at the service level.

        A fleet four times the batch size must be fully served in four passes,
        not have its tail ignored.

        """
        service = MaritimeSimulationService(self.clock, batch_size=5)
        fleet = [Ship(str(i)) for i in range(20)]
        for ship in fleet:
            service.register(ship)
        self.clock.advance(seconds=10.0)
        for _ in range(service.passes_for_full_sweep):
            service.tick()
        self.assertTrue(all(ship.ticks for ship in fleet))

    def test_sweep_bound_accounts_for_batch_size(self):
        service = MaritimeSimulationService(self.clock, batch_size=5)
        for index in range(20):
            service.register(Ship(str(index)))
        self.assertEqual(service.passes_for_full_sweep, 4)

    def test_sweep_bound_rounds_up(self):
        service = MaritimeSimulationService(self.clock, batch_size=5)
        for index in range(21):
            service.register(Ship(str(index)))
        self.assertEqual(service.passes_for_full_sweep, 5)

    def test_empty_service_needs_no_passes(self):
        self.assertEqual(self.service.passes_for_full_sweep, 0)


class TestTierPromotion(ServiceTestCase):
    """Moving between tiers."""

    def test_set_tier_changes_it(self):
        ship = Ship()
        self.service.register(ship, tier=STRATEGIC)
        self.service.set_tier(ship, TACTICAL)
        self.assertEqual(self.service.tier_of(ship), TACTICAL)

    def test_promotion_does_not_lose_elapsed_time(self):
        """
        A vessel promoted from strategic still owes the game time that passed
        while it was distant, rather than silently losing that stretch.

        """
        ship = Ship()
        self.service.register(ship, tier=STRATEGIC)
        self.clock.advance(seconds=45.0)
        self.service.set_tier(ship, ACTIVE)
        self.service.tick()
        self.assertEqual(ship.ticks, [45.0])

    def test_unknown_tier_is_refused(self):
        ship = Ship()
        self.service.register(ship)
        with self.assertRaises(ValueError):
            self.service.set_tier(ship, "eventually")

    def test_unregistered_entity_is_refused(self):
        with self.assertRaises(KeyError):
            self.service.set_tier(Ship(), ACTIVE)


class TestCheckpointing(ServiceTestCase):
    """Coordinated persistence."""

    def test_asks_every_entity_to_save(self):
        ships = [Ship(str(i)) for i in range(3)]
        for ship in ships:
            self.service.register(ship)
        self.assertEqual(self.service.checkpoint(), 3)

    def test_unchanged_entities_are_not_counted(self):
        """A fleet at anchor costs almost nothing to checkpoint."""
        ship = Ship()
        self.service.register(ship)
        self.service.checkpoint()
        self.assertEqual(self.service.checkpoint(), 0)

    def test_entity_without_checkpoint_is_skipped(self):
        self.service.register(Inert())
        self.assertEqual(self.service.checkpoint(), 0)

    def test_a_failing_checkpoint_does_not_abandon_the_rest(self):
        """Losing one vessel's position is better than losing the fleet's."""

        class Stubborn(Ship):
            def checkpoint(self):
                raise RuntimeError("disk on fire")

        self.service.register(Stubborn("bad"))
        sound = Ship("sound")
        self.service.register(sound)
        self.assertEqual(self.service.checkpoint(), 1)
        self.assertEqual(sound.saves, 1)

    def test_checkpoint_failures_are_counted(self):
        class Stubborn(Ship):
            def checkpoint(self):
                raise RuntimeError("disk on fire")

        self.service.register(Stubborn("bad"))
        self.service.checkpoint()
        self.assertEqual(self.service.failures, 1)
