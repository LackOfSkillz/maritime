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
from .observation import IDENTIFIED
from .results import Result
from .tactical import aspect, bears, raking, raking_weight
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

#: Refusals where the gun never went off, so no charge was spent and nothing was
#: heard. `SHOT_FALLS_SHORT` is deliberately not among them: that gun *fired* and
#: the shot simply did not carry, which is the price of having loaded grape.
NEVER_FIRED = (NOT_LOADED, STILL_RELOADING, WILL_NOT_BEAR, OUT_OF_RANGE)


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
        rake (str or None): Whether the shot ran her length, and from which end.
        aim_point (WorldPosition or None): Where the gun was laid.

    Notes:
        A hit says where and how hard, and stops. What that does to a hull is the
        damage phase's business, and this deliberately has no way of asking.

    """

    mount: str = ""
    target: object = None
    shot: object = DEFAULT_SHOT
    rake: object = None
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
    steadiness=1.0,
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
        steadiness (float, optional): How well laid the gun is, 1.0 for a shot
            taken deliberately. Below that for one snatched as a target crosses,
            and lower again for a crew too frightened to take their time.

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
    chance = (
        hit_chance(mount.weapon, distance, sea_state, showing)
        * mount.shot.accuracy
        * max(0.0, steadiness)
    )

    common = {
        "mount": mount.key,
        "target": target,
        "distance": distance,
        "flight_time": flight,
        "chance": chance,
        "aim_point": laid,
        "shot": mount.shot,
        "rake": raking(showing),
    }

    # What is in the gun decides how far she is any use. A captain who loaded grape
    # has shortened his own reach for the afternoon, which is the price of having
    # made his mind up early - and the refusal has to say so, or he will think the
    # gun is broken.
    if not in_range(mount.shot, mount.weapon, distance):
        return ShotResult.failed("shot_falls_short", damage=0.0, **common)

    if roll() <= chance:
        # A shot that strikes her end-on runs the length of her instead of stopping
        # at a plank. No table decides that - the angle on her bow *is* the point of
        # impact, so raking is something a captain achieves by sailing well and
        # something he can be caught by if he lets somebody across his stern.
        told = told_by(mount.shot, mount.weapon.damage) * raking_weight(showing)
        return ShotResult.ok(damage=told, **common)
    return ShotResult.failed("missed", damage=0.0, **common)


#: How well a gun is laid when the shot is snatched rather than taken. A crew
#: holding their fire are laying on a target that is crossing them, and they pull
#: the lanyard on a bearing rather than on a considered solution.
OPPORTUNITY_ACCURACY = 0.7

#: How well a gun is laid at a ship that is about to hit you.
#:
#: Worse than a snatched shot and much worse than a considered one. A crew who can see a
#: bow coming at them are firing at the last moment at something they cannot miss and
#: cannot stop, and the range is nothing - so the penalty is not about the difficulty of the
#: shot. It is about the men.
#:
#: **It is not free, and the reload is the price.** The source makes those guns unavailable
#: for the next phase; a continuous simulation does not have phases, and does not need the
#: rule - firing starts every one of those reload clocks, so a captain who empties his
#: battery into a rammer meets whatever comes next with nothing loaded. The cost is the same
#: cost, arrived at by not adding anything.
POINT_BLANK_ACCURACY = 0.5

#: How much of that is lost again by a wholly shaken crew, on the same terms as
#: the serving and handling penalties. Frightened people snatch harder.
HESITATION_ON_LAYING = 0.5


@dataclass(frozen=True)
class Broadside:
    """
    What a broadside did, for somebody else to put into words.

    Attributes:
        target (any): What was fired on.
        distance (float): How far off she was, in metres.
        fired (int): How many guns actually spoke.
        hits (int): How many of them told.
        rakes (tuple): The rakes among those hits.
        carried_away (tuple): What was newly broken about her.

    """

    target: object
    distance: float
    fired: int
    hits: int
    rakes: tuple = ()
    carried_away: tuple = ()


@dataclass(frozen=True)
class Holding:
    """
    Guns run out and held, waiting for something to bear.

    Attributes:
        target_key (str or None): The name she is waiting for, lowercased. None
            if she is watching an arc rather than a ship.
        arc (str or None): The arc she is watching. None if she is waiting on a
            named ship.

    Notes:
        Exactly one of the two is set, and the difference between them is the
        whole decision.

        Waiting on a **named ship** is safe and requires you to have identified
        her, so it does not work in fog, in the dark, or at the edge of vision -
        which is where you most want your guns held ready.

        Watching an **arc** works in any weather and fires at whatever crosses it.
        That is the teeth. Nothing here knows what a friend is - factions are the
        host game's business - and nothing needs to: an order to fire at anything
        that crosses to starboard is *already* an order that will kill your own
        consort, and the captain who gave it said so.

    """

    target_key: str = None
    arc: str = None


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

    # --- holding fire -------------------------------------------------------

    @property
    def holding(self):
        """
        Returns:
            holding (Holding or None): What the battery is waiting for, if
                anything.

        """
        return self.db.holding

    @holding.setter
    def holding(self, order):
        """
        Args:
            order (Holding or None): What to wait for, or None to stand down.

        """
        self.db.holding = order

    def hold_fire(self, target_key=None, arc=None):
        """
        Run the guns out and wait.

        Args:
            target_key (str, optional): A ship to wait for by name.
            arc (str, optional): An arc to watch instead.

        Returns:
            holding (Holding): The order now standing.

        Raises:
            ValueError: If neither or both are given. "Hold your fire" with
                nothing named is not an order, and a gun crew told to watch both
                a ship and a bearing would have to guess which the captain meant.

        """
        named = bool(target_key)
        watching = bool(arc)
        if named == watching:
            raise ValueError("Hold fire on a named ship or on an arc, not neither and not both.")
        self.holding = Holding(
            target_key=target_key.lower() if named else None,
            arc=arc if watching else None,
        )
        return self.holding

    def stand_down(self):
        """
        Returns:
            stood_down (bool): True if she had been holding.

        """
        if self.holding is None:
            return False
        self.holding = None
        return True

    def opportunity(self, sightings):
        """
        What the standing order says to fire on, now.

        Args:
            sightings (iterable): `Sighting` objects, as the lookout has them.

        Returns:
            sighting (Sighting or None): The contact to fire on, or None if
                nothing the order covers is bearing.

        Notes:
            Nearest first, because that is the order the lookout reports in and
            the one a gunner would choose anyway.

            A named ship has to be *identified*, which is the cost of the safe
            order: a shape on the water is not a name, so holding fire on the
            Marigold does nothing in fog. An arc asks only that something is
            there, which is why it works in fog and why it is dangerous.

        """
        held = self.holding
        if held is None:
            return None

        for seen in sightings:
            if not self.guns_bearing(seen.relative):
                continue
            if held.target_key is not None:
                if seen.level != IDENTIFIED:
                    continue
                if held.target_key not in seen.target.key.lower():
                    continue
            elif not bears(seen.relative, held.arc):
                continue
            return seen
        return None

    def fire_broadside(self, sighting, now, roll, steadiness=1.0):
        """
        Fire everything that bears on this contact, and apply what tells.

        Args:
            sighting (Sighting): What is being fired on.
            now (float): Game time in seconds.
            roll (callable): An injected RNG stream.
            steadiness (float, optional): How well the guns are laid.

        Returns:
            broadside (Broadside): What happened, for somebody else to say.

        Notes:
            Domain returns data and `messaging` speaks, so nothing here says a
            word. It exists at all because the deck gun command and the standing
            order both have to resolve a broadside, and two copies of this loop
            would drift - one of them getting raking right and the other not.

        """
        from .ammunition import CREW

        her = sighting.target
        _course, her_speed = her.made_good() or (her.heading, her.speed)

        fired = hits = 0
        rakes = []
        failures = []
        for mount in self.guns_bearing(sighting.relative):
            shot = fire(
                mount,
                self.maritime_position,
                self.heading,
                her,
                her.maritime_position,
                her.heading,
                her_speed,
                self.sea_here(),
                now,
                roll,
                steadiness,
            )
            # Every refusal where she never went off, not just the two obvious
            # ones. A gun that will not reach is a gun that did not fire, and
            # counting it would spend the charge and report a broadside for a
            # shot nobody took.
            if shot.code in NEVER_FIRED:
                continue
            fired += 1
            self.replace_mount(discharge(mount))
            if not shot:
                continue

            hits += 1
            if shot.rake:
                rakes.append(shot.rake)
            # Which track it tells on is what the gunner loaded, which is what he
            # meant to do. The crew are people rather than a track, so they go
            # through the company and morale answers for free.
            if shot.shot.aimed_at is CREW:
                her.take_crew_casualties(shot.damage)
            else:
                failures.extend(her.take_damage(shot.shot.aimed_at, shot.damage))

        return Broadside(
            target=her,
            distance=sighting.distance,
            fired=fired,
            hits=hits,
            rakes=tuple(rakes),
            carried_away=tuple(failures),
        )

    def take_opportunity(self):
        """
        Fire on a standing order, if anything the order covers now bears.

        Returns:
            broadside (Broadside or None): What happened, or None if she was not
                holding, nothing bore, or not a gun was ready.

        Notes:
            Called every tick and does nothing on almost all of them, which is
            why it asks the cheap question first. A ship not holding her fire
            pays one attribute read for this.

            The order stands after it is used. A captain who wants one broadside
            and no more stands his guns down; one watching a channel wants every
            ship that comes through it, and having to say so again after each
            would make the order useless for the thing it is for.

        """
        from . import config
        from .rng import COMBAT

        if self.holding is None:
            return None

        seen = self.opportunity(self.contacts())
        if seen is None:
            return None

        now = config.time_provider().now()
        roll = config.rng_context().stream(COMBAT).random
        result = self.fire_broadside(seen, now, roll, self.laying_steadiness())
        if not result.fired:
            return None

        self.narrator.opportunity_fire(seen, self.holding)
        self.narrator.broadside(result)
        return result

    def defensive_fire(self, rammer):
        """
        Fire everything that bears at a ship driving at her, in the moment before she hits.

        Args:
            rammer (Vessel): The ship about to strike her.

        Returns:
            broadside (Broadside or None): What happened, or None if nothing bore, nothing
                was loaded, or she never saw her coming.

        Notes:
            **Not a standing order and not a reaction anybody has to declare.** A gun crew
            watching a bow come at them fire. What makes it a decision rather than free
            damage is on the other side of the ledger: every gun that speaks here begins
            its reload, so she meets whatever follows the collision with an empty battery.

            She has to have seen her. Ranging on a ship close enough to ram is not the hard
            part - if the guns bear and are loaded, they go off - but a ship that is not on
            her lookout's list is one nobody aboard is looking at, and firing at her would
            be the battery serving a contact the ship does not have.

        """
        from . import config
        from .rng import COMBAT

        seen = next((sighting for sighting in self.contacts() if sighting.target is rammer), None)
        if seen is None:
            return None

        now = config.time_provider().now()
        roll = config.rng_context().stream(COMBAT).random
        result = self.fire_broadside(seen, now, roll, self.point_blank_steadiness())
        if not result.fired:
            return None

        self.narrator.defensive_fire(rammer, result)
        self.narrator.broadside(result)
        return result

    def point_blank_steadiness(self):
        """
        Returns:
            steadiness (float): How well the battery lays a shot at an oncoming bow.

        Notes:
            Worse than a snatched shot, and degraded again by whatever her people are
            feeling. A frightened crew still fire - they fire badly, which is the same rule
            that governs serving the guns and working the rigging.

        """
        return POINT_BLANK_ACCURACY * (1.0 - HESITATION_ON_LAYING * self.hesitation)

    def laying_steadiness(self):
        """
        Returns:
            steadiness (float): How well the battery lays a snatched shot.

        Notes:
            Opportunity fire is worse than a shot taken deliberately, and worse
            again in a frightened crew. `hesitation` degrades rather than gates
            here, as it does at the serving and in the rigging - a shaken crew
            fire, they just fire badly.

        """
        return OPPORTUNITY_ACCURACY * (1.0 - HESITATION_ON_LAYING * self.hesitation)
