"""
The script that drives the simulation.

Everything below this is inert without it. The motion model knows how a hull behaves
over a stretch of game time, and the service knows whose turn it is - but something has
to actually call them, repeatedly, while nobody is looking. That is this.

One script for the whole game, not one per vessel. Evennia's own documentation is blunt
about the alternative: a ticker per object, firing constantly and finding nothing
changed, is the classic way to make a MUD slow. Worse here, `TickerHandler` identifies
subscriptions by callback, interval and idstring but not by their arguments, so a fleet
subscribing the same method at the same interval silently overwrites itself and most of
the ships simply stop.

The registry lives in memory and is rebuilt at startup from the database. That is
deliberate: which vessels are currently worth simulating is a runtime question, and
persisting it would mean maintaining a second copy of a truth the database already holds.

"""

from evennia.scripts.scripts import DefaultScript
from evennia.utils import logger

from . import config
from .simulation import ACTIVE, DORMANT, MaritimeSimulationService
from .typeclasses import Vessel

# Real seconds between passes. Game time advances at whatever rate the host game
# runs, so this is a cadence, not a speed - a game at 4:1 simply covers more
# in-world time per pass than one at 1:1.
DEFAULT_INTERVAL = 2

# Passes between checkpoints. Movement is held in memory, so this decides how much
# of a voyage an unclean shutdown could lose - about a minute at the default
# interval, against writing every vessel to disk every couple of seconds.
CHECKPOINT_EVERY = 30


class MaritimeDriver(DefaultScript):
    """
    Runs the maritime simulation on a repeating interval.

    Create one per game. It finds the vessels, ticks the service, and flushes
    state to disk periodically.

    """

    def at_script_creation(self):
        """Configure the repeating script."""
        self.key = "maritime_driver"
        self.desc = "Drives the maritime simulation."
        self.interval = DEFAULT_INTERVAL
        self.persistent = True
        self.db.passes = 0

    def at_start(self):
        """
        Build the service and register whatever is afloat.

        Notes:
            Runs on server start as well as on creation, which is what restores
            the registry after a reload without persisting it separately.

            Takes its clock from `ndb.time_provider` if one has been set,
            otherwise from configuration. That override is what makes the driver
            testable at all: against the live clock, a test would have to wait in
            real time for a vessel to become due, which is the exact problem the
            time seam exists to remove.

        """
        clock = self.ndb.time_provider or config.time_provider()
        self.ndb.service = MaritimeSimulationService(clock, budget_ms=config.tick_budget_ms())
        self.rebuild_registry()

    def rebuild_registry(self):
        """
        Register every launched vessel with the service.

        Returns:
            count (int): How many vessels were registered.

        Notes:
            A vessel with no position has not been launched - she is on the
            stocks - so there is nothing to simulate. Registering her would mean
            waking her every pass to discover she is still not afloat.

        """
        service = self.ndb.service
        if service is None:
            return 0
        registered = 0
        for vessel in Vessel.objects.all():
            if vessel.maritime_position is None:
                continue
            service.register(vessel, tier=ACTIVE)
            registered += 1
        return registered

    def at_repeat(self):
        """
        Run one pass of the simulation.

        Notes:
            A failure here is logged rather than raised. An exception escaping a
            repeating script stops the script, which would silently freeze every
            vessel in the game until someone noticed.

        """
        service = self.ndb.service
        if service is None:
            self.at_start()
            service = self.ndb.service

        try:
            service.tick()
        except Exception:
            logger.log_trace("maritime: simulation pass failed")
            return

        self.db.passes = (self.db.passes or 0) + 1
        if self.db.passes % CHECKPOINT_EVERY == 0:
            try:
                service.checkpoint()
            except Exception:
                logger.log_trace("maritime: checkpoint pass failed")

    def at_server_shutdown(self):
        """Flush every vessel before the server stops."""
        service = self.ndb.service
        if service is not None:
            service.checkpoint()

    def at_server_reload(self):
        """Flush every vessel before the server restarts."""
        service = self.ndb.service
        if service is not None:
            service.checkpoint()

    # --- convenience --------------------------------------------------------

    def add_vessel(self, vessel, tier=ACTIVE):
        """
        Put a vessel under simulation immediately.

        Args:
            vessel (Vessel): The hull to simulate.
            tier (str, optional): Which tier to start her in.

        Returns:
            added (bool): True if newly registered.

        """
        if self.ndb.service is None:
            self.at_start()
        return self.ndb.service.register(vessel, tier=tier)

    def lay_up(self, vessel):
        """
        Stop simulating a vessel without unregistering her.

        Args:
            vessel (Vessel): The hull to lay up.

        Returns:
            service (MaritimeSimulationService): The service, for chaining.

        Notes:
            Dormant rather than removed, so she is still known and still
            checkpointed - she is simply not being advanced.

        """
        if self.ndb.service is None:
            self.at_start()
        return self.ndb.service.set_tier(vessel, DORMANT)

    @property
    def service(self):
        """
        The simulation service this script drives.

        Returns:
            service (MaritimeSimulationService or None): The live service.

        """
        return self.ndb.service
