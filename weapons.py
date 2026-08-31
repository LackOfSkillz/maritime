"""
Guns: what is mounted, whether it bears, and where the shot goes.

A weapon at sea is a mount on a moving platform shooting at a moving target across a gap
that takes real time to cross. Everything interesting follows from that last part:

    time of flight   the shot is not instant, so
    aim off          you fire where she will be, not where she is, and
    the solution     is wrong the moment she alters course

**Nothing here is a cannon.** A weapon is a range, a reload, a projectile speed, an arc and
an accuracy, and a game fills those in for smooth-bore guns, ballistae, harpoons, rockets or
something that spits lightning. The rules are the same for all of them because the geometry
is; only the numbers differ, and hard-coding a cannon would be writing one game's armoury
into a contrib.

**Shots are events, not objects.** A broadside is eight solutions, eight flight times and
eight results - not eight database rows tracked across the world for four seconds. A game
with fifty ships in action would otherwise be maintaining several hundred cannonballs it
does not need, and Evennia would be doing it in the reactor.

**Damage is not decided here.** A hit reports where it struck and with how much, and stops.
Hull sections, breaches, flooding and fire are their own phase and carry decisions that are
not mine to make - so `ShotResult` is deliberately something nothing consumes yet.

"""

import math
from dataclasses import dataclass, replace

from .ammunition import DEFAULT_SHOT, in_range, told_by
from .damage import guns_serviceable
from .results import Result
from .tactical import aspect, bears
from .weather import SEA_STATES

# How much of its accuracy a weapon keeps at the far edge of its range. Guns do
# not stop working at maximum range, they stop hitting anything - and a cliff
# edge would make range bands a formality rather than a decision.
LONG_RANGE_ACCURACY = 0.15

# How much accuracy a heavy sea takes, at the worst of it. A rolling deck is the
# single largest thing between a gun and its target, and gunners have always
# known to fire on the roll.
MAX_SEA_PENALTY = 0.7

# How much smaller a bow-on target is than a beam-on one. A hull end-on presents
# her width; broadside she presents her length, which for most vessels is three
# or four times as much.
END_ON_FRACTION = 0.35

# Reasons a gun will not fire.
NOT_LOADED = "not_loaded"
STILL_RELOADING = "still_reloading"
SHOT_FALLS_SHORT = "shot_falls_short"
WILL_NOT_BEAR = "will_not_bear"
OUT_OF_RANGE = "out_of_range"


@dataclass(frozen=True)
class WeaponType:
    """
    A kind of weapon, as a set of numbers.

    Attributes:
        key (str): Identifier.
        name (str): What it is called.
        arc (str): Which arc it is mounted on, from `tactical.ARCS`.
        max_range (float): Furthest it will reach, in metres.
        reload_time (float): Game seconds to serve it again.
        projectile_speed (float): How fast the shot flies, in metres per second.
        accuracy (float): Chance of a hit at point-blank on a beam-on target, in
            a flat calm, from 0 to 1.
        damage (float): What it does when it connects. Meaningless until the
            damage phase gives it a scale.
        penetration (float): How much structure it goes through. Likewise.
        crew (int): Hands needed to serve it.

    """

    key: str
    name: str
    arc: str
    max_range: float = 500.0
    reload_time: float = 90.0
    projectile_speed: float = 250.0
    accuracy: float = 0.6
    damage: float = 10.0
    penetration: float = 1.0
    crew: int = 4


@dataclass(frozen=True)
class Mount:
    """
    One weapon, in one place, in one state.

    Attributes:
        key (str): Identifier, unique aboard one vessel.
        weapon (WeaponType): What it is.
        loaded (bool): Whether there is a charge in her.
        ready_at (float): Game time she can be fired again.
        shot (Shot): What she is loaded with, and therefore what her captain means
            to do with her.

    """

    key: str
    weapon: object
    loaded: bool = False
    ready_at: float = 0.0
    shot: object = DEFAULT_SHOT

    @property
    def arc(self):
        """
        Returns:
            arc (str): The arc this mount bears on.

        """
        return self.weapon.arc


@dataclass(frozen=True, kw_only=True)
class ShotResult(Result):
    """
    What came of firing.

    Attributes:
        mount (str): Which gun fired.
        target (any): What it was fired at.
        distance (float): Range at the moment of firing, in metres.
        flight_time (float): How long the shot was in the air, in game seconds.
        chance (float): The hit chance that was rolled against.
        damage (float): What connected, if anything.
        shot (Shot): What was in the gun, which says what track this tells on.
        aim_point (WorldPosition or None): Where the gun was laid.

    Notes:
        A hit says where and how hard, and stops. What that does to a hull is the
        damage phase's business, and this deliberately has no way of asking.

    """

    mount: str = ""
    target: object = None
    shot: object = DEFAULT_SHOT
    distance: float = 0.0
    flight_time: float = 0.0
    chance: float = 0.0
    damage: float = 0.0
    aim_point: object = None


def time_of_flight(distance, projectile_speed):
    """
    How long the shot is in the air.

    Args:
        distance (float): Range in metres.
        projectile_speed (float): How fast it flies, in metres per second.

    Returns:
        seconds (float): Game seconds of flight.

    """
    if projectile_speed <= 0.0:
        return 0.0
    return distance / projectile_speed


def aim_point(target_position, target_heading, target_speed, flight_time):
    """
    Where to lay the gun, given that she will not wait.

    Args:
        target_position (WorldPosition): Where she is now.
        target_heading (float): Her heading, in degrees.
        target_speed (float): Her speed over the ground, in metres per second.
        flight_time (float): How long the shot will be in the air.

    Returns:
        position (WorldPosition): Where to aim.

    Notes:
        Aiming off, which is the whole of gunnery against a moving target. It
        assumes she holds her course for the flight, and that assumption is
        wrong the instant she alters - which is exactly why altering course under
        fire is worth doing, and why this is a solution rather than a guarantee.

    """
    if target_speed <= 0.0 or flight_time <= 0.0:
        return target_position
    return target_position.moved(target_heading, target_speed * flight_time)


def range_accuracy(distance, max_range):
    """
    How much of a weapon's accuracy survives the range.

    Args:
        distance (float): Range in metres.
        max_range (float): The weapon's reach.

    Returns:
        fraction (float): From `LONG_RANGE_ACCURACY` to 1.

    Notes:
        Falls away smoothly rather than at a cliff. Guns do not stop working at
        maximum range, they stop hitting - and a hard edge would turn range bands
        into a formality instead of a decision about when to open fire.

    """
    if max_range <= 0.0:
        return 0.0
    reach = min(1.0, max(0.0, distance / max_range))
    return 1.0 - (1.0 - LONG_RANGE_ACCURACY) * reach


def sea_accuracy(sea_state):
    """
    How much of it survives the motion of the deck.

    Args:
        sea_state (str): One of `SEA_STATES`.

    Returns:
        fraction (float): From 1 in a calm down to `1 - MAX_SEA_PENALTY`.

    Notes:
        The largest single thing between a gun and its target. Gunners have
        always fired on the roll for this reason, which is a refinement this does
        not model - here the sea simply makes shooting harder, which is the part
        that changes decisions.

    """
    if sea_state not in SEA_STATES:
        return 1.0
    worst = max(1, len(SEA_STATES) - 1)
    return 1.0 - MAX_SEA_PENALTY * (SEA_STATES.index(sea_state) / worst)


def aspect_accuracy(angle):
    """
    How big a target she is, at this aspect.

    Args:
        angle (float): Her aspect, from `tactical.aspect`.

    Returns:
        fraction (float): From `END_ON_FRACTION` bow-on to 1 beam-on.

    Notes:
        A hull end-on presents her width; broadside she presents her length,
        which for most vessels is three or four times as much. It is why a ship
        under fire turns towards the guns, and why crossing a T is worth
        manoeuvring for from both sides of the exchange.

    """
    broadside = abs(math.sin(math.radians(angle)))
    return END_ON_FRACTION + (1.0 - END_ON_FRACTION) * broadside


def hit_chance(weapon, distance, sea_state, target_aspect):
    """
    The chance this shot connects.

    Args:
        weapon (WeaponType): What is firing.
        distance (float): Range in metres.
        sea_state (str): The sea she is shooting from.
        target_aspect (float): The target's aspect, in degrees.

    Returns:
        chance (float): From 0 to 1.

    Notes:
        Four independent factors multiplied: the weapon, the range, the sea and
        the size of what she is showing you. Each is separately arguable and
        separately tunable, which is the point of not rolling them into one
        number nobody can reason about.

    """
    return max(
        0.0,
        min(
            1.0,
            weapon.accuracy
            * range_accuracy(distance, weapon.max_range)
            * sea_accuracy(sea_state)
            * aspect_accuracy(target_aspect),
        ),
    )


def can_fire(mount, relative_bearing, distance, now):
    """
    Whether this gun will fire at all.

    Args:
        mount (Mount): The gun.
        relative_bearing (float): Where the target lies, from her head.
        distance (float): Range in metres.
        now (float): Game time in seconds.

    Returns:
        result (ShotResult): Successful if she will fire, failed with the reason
            if she will not.

    Notes:
        Checked in the order a gun crew discovers them: charge, then whether she
        has been served, then whether she bears, then whether it is worth the
        powder. Telling a captain his gun is out of range when it is not even
        loaded helps nobody.

    """
    if not mount.loaded:
        return ShotResult.failed(NOT_LOADED, mount=mount.key, distance=distance)
    if now < mount.ready_at:
        return ShotResult.failed(STILL_RELOADING, mount=mount.key, distance=distance)
    if not bears(relative_bearing, mount.arc):
        return ShotResult.failed(WILL_NOT_BEAR, mount=mount.key, distance=distance)
    if distance > mount.weapon.max_range:
        return ShotResult.failed(OUT_OF_RANGE, mount=mount.key, distance=distance)
    return ShotResult.ok(mount=mount.key, distance=distance)


def serve(mount, now, seconds=None, shot=None):
    """
    Load her, and start the clock on the next round.

    Args:
        mount (Mount): The gun.
        now (float): Game time in seconds.
        seconds (float, optional): How long this crew will take over it. Defaults
            to the weapon's own rate, which is what it takes when nothing is
            wrong - see `damage.serving_time` for what makes it longer.
        shot (Shot, optional): What to load her with. Defaults to whatever she had
            last, so a battery keeps firing the same thing until somebody says
            otherwise.

    Returns:
        mount (Mount): The gun, loaded and ready when her time comes.

    Notes:
        Takes the time rather than working it out. What slows a gun crew is a fact
        about the *ship* - how frightened they are, how much of the battery is
        wreckage - and a weapon that reached out for that would have to know what
        it was bolted to.

    """
    delay = mount.weapon.reload_time if seconds is None else seconds
    charge = mount.shot if shot is None else shot
    return replace(mount, loaded=True, ready_at=now + delay, shot=charge)


def discharge(mount):
    """
    Empty her, having fired.

    Args:
        mount (Mount): The gun.

    Returns:
        mount (Mount): The gun, empty.

    Notes:
        Separate from firing because whether a refused shot costs a charge is a
        rule and not arithmetic, and the caller is where rules live. Her reload
        clock is untouched - serving her again is what starts that.

    """
    return replace(mount, loaded=False)


def fire(
    mount,
    position,
    heading,
    target,
    target_position,
    target_heading,
    target_speed,
    sea_state,
    now,
    roll,
):
    """
    Lay the gun and pull the lanyard.

    Args:
        mount (Mount): The gun.
        position (WorldPosition): Where the firing ship is.
        heading (float): Her heading, in degrees.
        target (any): What is being shot at.
        target_position (WorldPosition): Where the target is.
        target_heading (float): The target's heading.
        target_speed (float): The target's speed over the ground.
        sea_state (str): The sea being fired from.
        now (float): Game time in seconds.
        roll (callable): Returns a float from 0 to 1 - an injected RNG stream.

    Returns:
        result (ShotResult): Successful on a hit, failed on a miss or a refusal,
            carrying the solution either way.

    Notes:
        The RNG arrives as an argument rather than being reached for, which is
        Law 9: a fight replays identically from the same seed, and a test can
        hand in a fixed roll and know exactly what should happen.

        The gun is not discharged here - that is the caller's business, because
        whether a refused shot costs a charge is a rule and not arithmetic.

    """
    distance = position.horizontal_distance_to(target_position)
    relative = position.bearing_to(target_position) - heading

    ready = can_fire(mount, relative, distance, now)
    if not ready:
        return ready

    flight = time_of_flight(distance, mount.weapon.projectile_speed)
    laid = aim_point(target_position, target_heading, target_speed, flight)
    showing = aspect(position, target_position, target_heading)
    chance = hit_chance(mount.weapon, distance, sea_state, showing) * mount.shot.accuracy

    common = {
        "mount": mount.key,
        "target": target,
        "distance": distance,
        "flight_time": flight,
        "chance": chance,
        "aim_point": laid,
        "shot": mount.shot,
    }

    # What is in the gun decides how far she is any use. A captain who loaded grape
    # has shortened his own reach for the afternoon, which is the price of having
    # made his mind up early - and the refusal has to say so, or he will think the
    # gun is broken.
    if not in_range(mount.shot, mount.weapon, distance):
        return ShotResult.failed("shot_falls_short", damage=0.0, **common)

    if roll() <= chance:
        return ShotResult.ok(damage=told_by(mount.shot, mount.weapon.damage), **common)
    return ShotResult.failed("missed", damage=0.0, **common)


class Armed:
    """
    The guns a vessel carries, and the state each is in.

    Notes:
        The Evennia-side face of this module. Mounts are hers, so two ships in
        the same action have their own reload clocks and their own empty guns.

    """

    def at_object_creation(self):
        """Set up this part of a newly created vessel."""
        super().at_object_creation()
        self.db.mounts = []

    @property
    def mounts(self):
        """
        Returns:
            mounts (tuple): Every gun aboard.

        """
        return tuple(self.db.mounts or ())

    @property
    def serviceable_mounts(self):
        """
        Returns:
            mounts (tuple): The guns that can still be fought.

        Notes:
            Damage to the battery takes guns out of it. Which guns is not modelled -
            they come off the end of the list rather than being chosen - because
            *which* gun was dismounted matters far less than how many she can still
            bring to bear, and pretending otherwise would be precision this has not
            earned.

        """
        mounts = self.mounts
        return mounts[: guns_serviceable(len(mounts), self.damage)]

    def mount_named(self, key):
        """
        Args:
            key (str): The mount's identifier.

        Returns:
            mount (Mount or None): That gun, if she carries it.

        """
        for mount in self.mounts:
            if mount.key.lower() == str(key).lower():
                return mount
        return None

    def add_mount(self, mount):
        """
        Put a gun aboard.

        Args:
            mount (Mount): The gun.

        Returns:
            vessel (Vessel): This hull, for chaining.

        Raises:
            ValueError: If a mount of that name is already aboard.

        """
        aboard = list(self.db.mounts or ())
        if any(other.key == mount.key for other in aboard):
            raise ValueError(f"She already mounts a gun called {mount.key!r}.")
        aboard.append(mount)
        self.db.mounts = aboard
        return self

    def replace_mount(self, mount):
        """
        Write a gun back after its state has changed.

        Args:
            mount (Mount): The gun, in its new state.

        Returns:
            vessel (Vessel): This hull, for chaining.

        Notes:
            Mounts are frozen, so serving or firing one produces a new object
            rather than mutating the stored list in place - which would commit on
            every touch. See Law 10.

        """
        self.db.mounts = [
            mount if other.key == mount.key else other for other in (self.db.mounts or ())
        ]
        return self

    def guns_bearing(self, relative_bearing):
        """
        Every gun that could be brought to bear on this bearing.

        Args:
            relative_bearing (float): Where the target lies, from her head.

        Returns:
            mounts (tuple): The guns whose arcs cover it.

        Notes:
            Bearing and serviceable. Whether each is loaded or served is
            `can_fire`'s question - this is the part that manoeuvring changes,
            and the part that being shot about takes away.

            A dismounted gun does not bear on anything. Reading the whole battery
            here would let a wrecked ship keep firing a full broadside, which is
            the exact failure the weapons track exists to prevent.

        """
        return tuple(
            mount for mount in self.serviceable_mounts if bears(relative_bearing, mount.arc)
        )
