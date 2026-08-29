"""
Deterministic randomness for the maritime simulation.

Domain code never calls the global `random` module. Every stochastic mechanic draws
from a named stream owned by an `RNGContext`, so that a run can be reproduced exactly
from the seed that produced it - a storm, a chase, a hull breach, an NPC's decision.

Streams are independent. Weather drawing a hundred numbers does not shift what combat
rolls next, which is what makes a failing scenario shrinkable: you can change one
subsystem without disturbing the others' sequences.

Example:
    ```python
    rng = RNGContext(seed=729922)
    wind = rng.stream(WEATHER).gauss(12.0, 3.0)
    hit = rng.stream(COMBAT).random() < 0.4
    ```

Reproducibility here is a *testing* property. It holds for identical inputs applied in
an identical order; it is not a promise that a live multiplayer session replays from a
seed, since real play interleaves player actions unpredictably.

"""

import hashlib
import random

# The standard streams. Games may request any name they like - these exist so the
# common ones are spelled consistently rather than as scattered string literals.
NAVIGATION = "navigation"
COMBAT = "combat"
DAMAGE = "damage"
WEATHER = "weather"
AI = "ai"

STANDARD_STREAMS = (NAVIGATION, COMBAT, DAMAGE, WEATHER, AI)

# Seeds are drawn from this range when none is supplied. Wide enough that an
# accidental collision between two runs is not worth worrying about, small enough
# to stay readable in a log line or a bug report.
_MAX_SEED = 2**63 - 1


def derive_seed(master_seed, stream_name):
    """
    Derive a stream's seed from the master seed and the stream's name.

    Args:
        master_seed (int): The run's master seed.
        stream_name (str): Name of the stream, e.g. `"weather"`.

    Returns:
        seed (int): A seed unique to this master/stream pair.

    Notes:
        Uses SHA-256 rather than Python's built-in `hash()`. String hashing is
        salted per process unless `PYTHONHASHSEED` is fixed, so `hash()` would
        give a different stream seed on every server start and silently destroy
        the reproducibility this module exists to provide.

    """
    digest = hashlib.sha256(f"{master_seed}:{stream_name}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


class RNGContext:
    """
    A set of independent, reproducible random streams.

    One context represents one run. Hand it to the simulation and every stochastic
    decision becomes replayable from `context.seed`.

    """

    def __init__(self, seed=None):
        """
        Args:
            seed (int, optional): Master seed for the run. When omitted, one is
                generated and exposed as `.seed` so the run can be reproduced
                later - record it alongside anything worth reproducing.

        """
        if seed is None:
            seed = random.SystemRandom().randrange(_MAX_SEED)
        self.seed = int(seed)
        self._streams = {}

    def stream(self, name):
        """
        Get a named random stream, creating it on first use.

        Args:
            name (str): Stream name. Use the module constants for the standard
                ones; any other string creates a stream of its own.

        Returns:
            stream (random.Random): A generator seeded from this context's master
                seed and the given name. Repeated calls with the same name return
                the same object, so a stream advances rather than restarting.

        Raises:
            ValueError: If the name is empty. An unnamed stream would collide with
                every other unnamed stream and quietly couple unrelated systems.

        """
        if not name:
            raise ValueError("A random stream must be named.")
        if name not in self._streams:
            self._streams[name] = random.Random(derive_seed(self.seed, name))
        return self._streams[name]

    def reset(self):
        """
        Discard every stream, so the next use starts from the seed again.

        Returns:
            context (RNGContext): This context, for chaining.

        Notes:
            Used between scenario runs that must start from identical state. It
            does not change the seed - only rewinds the streams derived from it.

        """
        self._streams.clear()
        return self

    def active_streams(self):
        """
        Names of the streams created so far.

        Returns:
            names (tuple): Stream names, sorted. Useful in a failure report, to
                show which subsystems actually consumed randomness during a run.

        """
        return tuple(sorted(self._streams))

    def __repr__(self):
        return f"RNGContext(seed={self.seed})"
