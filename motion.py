"""
How a vessel actually moves.

Pure functions over plain data. Nothing here touches the database, an Evennia object or
a player - hand it a state, some orders and a stretch of game time, and it returns the
state that results. That is what makes a voyage testable in microseconds and reproducible
from a seed.

Ships do not respond instantly. An order is a *target*: the helm asks for a heading and
the hull swings towards it at whatever rate her rudder and speed allow; the master asks
for a speed and she gathers or loses way over time. The gap between what was ordered and
what the vessel is currently doing is most of what makes handling a ship feel like
handling a ship rather than driving a cursor.

Motion integrates in fixed sub-steps rather than one large jump. A vessel told to turn
and then advanced thirty seconds in a single calculation would pivot on the spot and
travel the whole distance on her new heading; sub-stepping makes her carve the arc she
actually would. It also means the same voyage produces the same track regardless of how
often the scheduler happened to run, which is what stops a laggy server from quietly
changing where ships end up.

"""

import math
from dataclasses import dataclass, replace

from .position import WorldPosition, bearing_difference, normalize_bearing

# Game seconds per integration sub-step. Small enough that a turn describes an arc,
# large enough that an hour of catch-up is a few thousand cheap iterations.
SIMULATION_STEP = 1.0


@dataclass(frozen=True)
class MotionLimits:
    """
    What a hull is physically capable of.

    Attributes:
        max_speed (float): Fastest she will go under her own power, in metres per
            second. Sailing will later derive an effective ceiling from wind; this
            is the hull's own limit.
        acceleration (float): How quickly she gathers or loses way, in metres per
            second squared. Deliberately one figure for both: a hull that stops as
            slowly as it starts is closer to the truth than one that brakes.
        turn_rate (float): Degrees per second at full speed.

    """

    max_speed: float = 5.0
    acceleration: float = 0.1
    turn_rate: float = 3.0

    def __post_init__(self):
        """Reject limits that would make motion meaningless."""
        for name in ("max_speed", "acceleration", "turn_rate"):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"MotionLimits.{name} must be finite and non-negative.")


@dataclass(frozen=True)
class HelmOrders:
    """
    What the vessel has been told to do.

    Attributes:
        heading (float): Compass bearing to steer, in degrees.
        speed (float): Speed to make, in metres per second.

    """

    heading: float = 0.0
    speed: float = 0.0

    def __post_init__(self):
        """Normalise the ordered heading and refuse a negative speed."""
        object.__setattr__(self, "heading", normalize_bearing(float(self.heading)))
        if self.speed < 0.0:
            raise ValueError(
                f"Ordered speed cannot be negative, got {self.speed!r}. "
                "Order a reciprocal heading rather than a negative speed."
            )


@dataclass(frozen=True)
class MotionState:
    """
    Where a vessel is and what she is doing.

    Attributes:
        position (WorldPosition): Where she is.
        heading (float): Which way she is actually pointing, in degrees. Not
            necessarily what was ordered.
        speed (float): How fast she is actually going, in metres per second.

    """

    position: WorldPosition
    heading: float = 0.0
    speed: float = 0.0

    def __post_init__(self):
        """Normalise heading and reject impossible speed."""
        object.__setattr__(self, "heading", normalize_bearing(float(self.heading)))
        if not math.isfinite(self.speed) or self.speed < 0.0:
            raise ValueError(f"Speed must be finite and non-negative, got {self.speed!r}.")


def turn_rate_at_speed(limits, speed, floor=0.0):
    """
    How fast a hull can turn at a given speed.

    Args:
        limits (MotionLimits): The hull's capabilities.
        speed (float): Current speed in metres per second.
        floor (float, optional): Degrees per second available regardless of
            speed.

    Returns:
        rate (float): Degrees per second available right now.

    Notes:
        A rudder works by deflecting water flowing past it, so a vessel dead in the
        water has almost no steering at all. Scaling the turn rate with speed is
        what makes losing way a genuine problem rather than an inconvenience, and
        it is why a becalmed ship cannot simply spin to face a threat.

        Scales linearly to full rate at maximum speed. Cruder than reality, where
        the curve flattens off, but it captures the part that matters: slow ships
        steer badly.

        **The floor is not scaled**, and that is the whole reason it exists. Some
        things turn a ship without any water flowing past the rudder at all: a
        backed headsail, a sweep over the quarter, a warp to a bollard, a tug on
        the bow. Feeding those through the speed scaling multiplies them by zero
        at exactly the moment they are the only thing that would work - a hull
        stopped dead and pointing the wrong way, which is the definition of being
        in irons and the one situation the mechanism is for.

    """
    floor = max(floor, 0.0)
    if limits.max_speed <= 0.0:
        return floor
    return max(limits.turn_rate * min(1.0, speed / limits.max_speed), floor)


def _step(state, orders, limits, elapsed, turn_floor=0.0):
    """
    Advance one sub-step.

    Args:
        state (MotionState): Current state.
        orders (HelmOrders): What was ordered.
        limits (MotionLimits): Hull capabilities.
        elapsed (float): Game seconds for this sub-step.

    Returns:
        state (MotionState): The state after this sub-step.

    Notes:
        Speed changes first, then heading, then position. Turning before moving
        means the vessel travels on the heading she has just reached, which over
        many small steps traces the arc she would actually follow.

    """
    target_speed = min(orders.speed, limits.max_speed)
    speed_change = limits.acceleration * elapsed
    if target_speed > state.speed:
        speed = min(target_speed, state.speed + speed_change)
    else:
        speed = max(target_speed, state.speed - speed_change)

    available_turn = turn_rate_at_speed(limits, speed, turn_floor) * elapsed
    wanted_turn = bearing_difference(state.heading, orders.heading)
    if abs(wanted_turn) <= available_turn:
        heading = orders.heading
    else:
        heading = normalize_bearing(state.heading + math.copysign(available_turn, wanted_turn))

    position = state.position
    if speed > 0.0:
        position = position.moved(heading, speed * elapsed)

    return replace(state, position=position, heading=heading, speed=speed)


def advance(state, orders, limits, elapsed, step=SIMULATION_STEP, turn_floor=0.0):
    """
    Advance a vessel through a stretch of game time.

    Args:
        state (MotionState): Where she is now.
        orders (HelmOrders): What she has been told to do.
        limits (MotionLimits): What she is capable of.
        elapsed (float): Game seconds to advance.
        step (float, optional): Sub-step size in game seconds.
        turn_floor (float, optional): Degrees per second of turning available
            regardless of speed - a backed sail, a sweep, a warp, a tug.

    Returns:
        state (MotionState): Where she ends up.

    Raises:
        ValueError: If `elapsed` is negative or `step` is not positive.

    Notes:
        Integrates in fixed sub-steps. Advancing thirty seconds in one calculation
        would let a turning vessel pivot on the spot and then run the whole
        distance on her new heading; sub-stepping makes her carve the arc.

        It also decouples the track from how often the scheduler ran, so a laggy
        server produces the same voyage as a smooth one rather than quietly
        putting ships somewhere else.

    """
    if elapsed < 0.0:
        raise ValueError(f"Cannot advance by negative time, got {elapsed!r}.")
    if step <= 0.0:
        raise ValueError(f"Sub-step must be positive, got {step!r}.")
    if elapsed == 0.0:
        return state

    whole_steps = int(elapsed // step)
    remainder = elapsed - whole_steps * step

    current = state
    for _ in range(whole_steps):
        current = _step(current, orders, limits, step, turn_floor)
    if remainder > 0.0:
        current = _step(current, orders, limits, remainder, turn_floor)
    return current
