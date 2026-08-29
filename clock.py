"""
The maritime clock.

Maritime never invents its own rate of time. It consumes elapsed *game* time from a
provider supplied by the host game, so a vessel's speed means the same thing whatever
ratio that game runs at: an eight-knot vessel covers eight nautical miles per in-world
hour, and how long that takes in wall-clock terms is the game's business, not ours.

A game running at 4:1 gets voyages four times faster in real terms than one running at
1:1, and neither needs a maritime-specific setting to make that happen.

Three providers live here:

    MaritimeTimeProvider    the interface every provider implements
    GameTimeProvider        the default, reading Evennia's own game clock
    ManualTimeProvider      time advanced explicitly, for tests and tools

The last is not merely a convenience. A voyage taking half an hour of wall time under a
production clock completes in microseconds when time is stepped on demand, which is the
difference between voyage tests being routine and being impossible to write.

"""

from evennia.utils import gametime

# Seconds per unit, used to turn keyword arguments into an offset.
_SECONDS_PER_MINUTE = 60.0
_SECONDS_PER_HOUR = 3600.0
_SECONDS_PER_DAY = 86400.0


class MaritimeTimeProvider:
    """
    Interface for supplying the maritime simulation with game time.

    Implementations answer one question - what time is it now, in game seconds -
    and everything else is derived from that. Time is measured in seconds and
    only ever moves forward.

    """

    def now(self):
        """
        The current game time.

        Returns:
            now (float): Game time in seconds. The origin is provider-defined and
                carries no meaning; only differences between two readings do.

        """
        raise NotImplementedError("A time provider must implement now().")

    def elapsed_game_seconds(self, since):
        """
        Game seconds that have passed since an earlier reading.

        Args:
            since (float): An earlier value returned by `now()`.

        Returns:
            elapsed (float): Game seconds elapsed. Never negative.

        Notes:
            A reading from the future returns 0.0 rather than a negative span.
            Time running backwards would let a simulation step undo itself, and
            silently clamping is safer than propagating a negative delta into
            movement integration.

        """
        return max(0.0, self.now() - since)


class GameTimeProvider(MaritimeTimeProvider):
    """
    The default provider, reading the host game's own clock.

    Delegates to `evennia.utils.gametime`, which applies the game's
    `TIME_FACTOR` setting. Maritime therefore inherits whatever rate the game
    already runs at and never scales time itself.

    """

    def now(self):
        """
        The host game's current game time.

        Returns:
            now (float): Absolute game time in seconds, including the game epoch.

        """
        return gametime.gametime(absolute=True)


class ManualTimeProvider(MaritimeTimeProvider):
    """
    A clock that only moves when told to.

    Intended for tests, benchmarks and offline tools, where waiting for real time
    to pass is not an option. Nothing advances this clock implicitly, so a test
    controls exactly how much game time a simulation has seen.

    Example:
        ```python
        clock = ManualTimeProvider()
        start = clock.now()
        clock.advance(hours=2, minutes=30)
        clock.elapsed_game_seconds(start)  # 9000.0
        ```

    """

    def __init__(self, start=0.0):
        """
        Args:
            start (float, optional): Game time this clock begins at, in seconds.

        """
        self._now = float(start)

    def now(self):
        """
        The current game time.

        Returns:
            now (float): Game time in seconds, as last set by `advance()`.

        """
        return self._now

    def advance(self, seconds=0.0, minutes=0.0, hours=0.0, days=0.0):
        """
        Move the clock forward.

        Args:
            seconds (float, optional): Game seconds to advance.
            minutes (float, optional): Game minutes to advance.
            hours (float, optional): Game hours to advance.
            days (float, optional): Game days to advance.

        Returns:
            now (float): The new current game time, for convenient chaining.

        Raises:
            ValueError: If the combined offset is negative. Rewinding would let a
                simulation step undo work already done, so it is refused rather
                than clamped - unlike a stale reading, a negative advance is a
                caller error worth surfacing.

        """
        offset = (
            float(seconds)
            + float(minutes) * _SECONDS_PER_MINUTE
            + float(hours) * _SECONDS_PER_HOUR
            + float(days) * _SECONDS_PER_DAY
        )
        if offset < 0:
            raise ValueError(f"Cannot advance a clock by a negative amount (got {offset}s).")
        self._now += offset
        return self._now
