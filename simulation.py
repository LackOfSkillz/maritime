"""
The maritime simulation service.

One scheduler drives everything. Not a ticker per vessel, per cannon, per fire - one
service that decides what gets attention and how much.

That is partly a performance decision and partly a correctness one. Evennia's
`TickerHandler` identifies subscriptions by callback, interval and `idstring`, *not* by
their arguments, so a hundred vessels subscribing the same method at the same interval
silently overwrite one another. Nothing errors; ninety-nine ships just stop moving. A
single service with its own registry cannot make that mistake.

Work is tiered, because not everything deserves the same attention:

    DORMANT     docked or laid up. Not simulated at all.
    STRATEGIC   far from any player. Advanced occasionally and coarsely.
    ACTIVE      a player is aboard or nearby. Normal simulation.
    TACTICAL    combat, collision, boarding. Highest frequency.

Each pass is bounded. The service processes what fits in its budget and resumes from
where it stopped, so a large fleet lengthens the interval before any one vessel is
revisited rather than blocking the reactor while everything is served at once.

"""

from evennia.utils import logger

from .scheduler import FairQueue

# Simulation tiers, coarsest first.
DORMANT = "dormant"
STRATEGIC = "strategic"
ACTIVE = "active"
TACTICAL = "tactical"

TIERS = (DORMANT, STRATEGIC, ACTIVE, TACTICAL)

# How much game time should pass between updates at each tier. Dormant is absent
# because a dormant vessel is not simulated at all - it is not "very slow", it is off.
TIER_INTERVALS = {
    STRATEGIC: 60.0,
    ACTIVE: 5.0,
    TACTICAL: 1.0,
}

# Most game time any single update will be told has elapsed. Without a cap, a server
# that was down for a week would hand a vessel a week of movement in one step, and a
# fixed-step integrator would either take an hour to catch up or produce nonsense.
MAX_CATCHUP_SECONDS = 3600.0

# How many entries one pass will touch before yielding the reactor. Deliberately small:
# a pass that blocks is worse than a vessel updated a moment late.
DEFAULT_BATCH_SIZE = 25

# The hook an entity may implement to be simulated.
TICK_HOOK = "at_maritime_tick"


class _Entry:
    """Bookkeeping for one registered entity."""

    __slots__ = ("entity", "tier", "last_tick")

    def __init__(self, entity, tier, last_tick):
        self.entity = entity
        self.tier = tier
        self.last_tick = last_tick


class MaritimeSimulationService:
    """
    Decides what gets simulated, when, and for how long.

    Owns its registry rather than relying on a global, so a test can run a whole
    fleet through hundreds of ticks without touching anything the live game holds.

    """

    def __init__(self, time_provider, batch_size=DEFAULT_BATCH_SIZE):
        """
        Args:
            time_provider (MaritimeTimeProvider): Supplies game time. The service
                never reads a clock directly, so a test can drive a fleet through
                a week of simulation in milliseconds.
            batch_size (int, optional): Entries touched per pass.

        Raises:
            ValueError: If `batch_size` is not positive. A batch of zero would
                register vessels that are never once simulated.

        """
        if batch_size <= 0:
            raise ValueError(f"batch_size must be positive, got {batch_size!r}.")
        self.time = time_provider
        self.batch_size = batch_size
        self._entries = {}
        self._queue = FairQueue()
        self.ticks_run = 0
        self.updates_run = 0
        self.failures = 0

    # --- registration -------------------------------------------------------

    def register(self, entity, tier=ACTIVE):
        """
        Put an entity under simulation.

        Args:
            entity (any): The thing to simulate. May implement
                `at_maritime_tick(elapsed_game_seconds)`.
            tier (str, optional): Which tier to start in.

        Returns:
            registered (bool): True if newly registered.

        Raises:
            ValueError: If `tier` is not a known tier.

        """
        if tier not in TIERS:
            raise ValueError(f"Unknown tier {tier!r}; expected one of {TIERS}.")
        if entity in self._entries:
            self._entries[entity].tier = tier
            return False
        self._entries[entity] = _Entry(entity, tier, self.time.now())
        self._queue.add(entity)
        return True

    def unregister(self, entity):
        """
        Stop simulating an entity.

        Args:
            entity (any): The entity to drop.

        Returns:
            removed (bool): True if it had been registered.

        """
        if entity not in self._entries:
            return False
        del self._entries[entity]
        self._queue.remove(entity)
        return True

    def set_tier(self, entity, tier):
        """
        Move an entity between tiers.

        Args:
            entity (any): A registered entity.
            tier (str): The tier to move it to.

        Returns:
            service (MaritimeSimulationService): This service, for chaining.

        Raises:
            KeyError: If the entity is not registered.
            ValueError: If the tier is unknown.

        Notes:
            Promotion does not reset the clock. A vessel moving from strategic to
            active still owes whatever game time passed while it was distant, so
            it catches up rather than silently losing that stretch of its voyage.

        """
        if tier not in TIERS:
            raise ValueError(f"Unknown tier {tier!r}; expected one of {TIERS}.")
        if entity not in self._entries:
            raise KeyError(f"{entity!r} is not registered with this service.")
        self._entries[entity].tier = tier
        return self

    def tier_of(self, entity):
        """
        Which tier an entity is in.

        Args:
            entity (any): The entity to look up.

        Returns:
            tier (str or None): Its tier, or None if unregistered.

        """
        entry = self._entries.get(entity)
        return entry.tier if entry else None

    # --- simulation ---------------------------------------------------------

    def is_due(self, entity, now=None):
        """
        Whether an entity is ready for its next update.

        Args:
            entity (any): A registered entity.
            now (float, optional): Game time to judge against. Defaults to the
                current time.

        Returns:
            due (bool): True if enough game time has passed for its tier. Always
                False for dormant entities, which are not simulated at all.

        """
        entry = self._entries.get(entity)
        if entry is None or entry.tier == DORMANT:
            return False
        interval = TIER_INTERVALS[entry.tier]
        current = self.time.now() if now is None else now
        return (current - entry.last_tick) >= interval

    def tick(self):
        """
        Run one bounded pass of the simulation.

        Returns:
            updated (tuple): The entities updated during this pass.

        Notes:
            Takes a batch from the rotation, skips whatever is not yet due, and
            updates the rest. Because the rotation's cursor persists, a fleet
            larger than the batch is served across successive passes rather than
            having its tail ignored.

            A hook that raises is logged and skipped. One vessel with a broken
            update must not stop every other vessel in the world.

        """
        self.ticks_run += 1
        now = self.time.now()
        updated = []

        for entity in self._queue.next_batch(self.batch_size):
            entry = self._entries.get(entity)
            if entry is None or entry.tier == DORMANT:
                continue
            elapsed = now - entry.last_tick
            if elapsed < TIER_INTERVALS[entry.tier]:
                continue
            entry.last_tick = now
            if self._update(entity, min(elapsed, MAX_CATCHUP_SECONDS)):
                updated.append(entity)

        return tuple(updated)

    def _update(self, entity, elapsed):
        """
        Run one entity's update hook.

        Args:
            entity (any): The entity to update.
            elapsed (float): Game seconds since its last update, capped.

        Returns:
            updated (bool): True if a hook ran without raising.

        """
        hook = getattr(entity, TICK_HOOK, None)
        if not callable(hook):
            return False
        try:
            hook(elapsed)
        except Exception:
            self.failures += 1
            logger.log_trace(f"maritime: {TICK_HOOK} failed for {entity!r}")
            return False
        self.updates_run += 1
        return True

    # --- persistence --------------------------------------------------------

    def checkpoint(self):
        """
        Ask every registered entity to save its state.

        Returns:
            saved (int): How many entities actually wrote anything.

        Notes:
            Entities decide for themselves whether they have changed, so a fleet
            at anchor costs almost nothing. A failure is logged and skipped rather
            than abandoning the rest of the flush - losing one vessel's position
            is far better than losing the fleet's.

        """
        saved = 0
        for entity in tuple(self._entries):
            checkpoint = getattr(entity, "checkpoint", None)
            if not callable(checkpoint):
                continue
            try:
                if checkpoint():
                    saved += 1
            except Exception:
                self.failures += 1
                logger.log_trace(f"maritime: checkpoint failed for {entity!r}")
        return saved

    # --- introspection ------------------------------------------------------

    def count(self, tier=None):
        """
        How many entities are registered.

        Args:
            tier (str, optional): Count only this tier. All tiers when omitted.

        Returns:
            count (int): Number registered.

        """
        if tier is None:
            return len(self._entries)
        return sum(1 for entry in self._entries.values() if entry.tier == tier)

    def registered(self):
        """
        Every registered entity.

        Returns:
            entities (tuple): In registration order.

        """
        return tuple(self._entries)

    @property
    def passes_for_full_sweep(self):
        """
        Passes needed before every registered entity has been considered.

        Returns:
            passes (int): Worst case, given the current batch size.

        Notes:
            The starvation bound. Multiply by the real interval between passes to
            get the longest a vessel can wait, which is the figure to check a
            tier's interval against.

        """
        if not self._entries:
            return 0
        return -(-len(self._entries) // self.batch_size)

    def __contains__(self, entity):
        return entity in self._entries

    def __len__(self):
        return len(self._entries)

    def __repr__(self):
        return f"MaritimeSimulationService({len(self._entries)} registered)"
