"""
What is broken, and what that stops her doing.

**Five tracks, not one pool.** Hull, rigging, oars, weapons and crew are damaged
separately, because a ship that is fast and toothless, one that is intact and cannot
steer, and one that is whole and unwilling are three different ships and a single
hit-point number cannot say which you are looking at. Every naval system that models a
ship as "hull points plus sail points" gives that up, and it is the most interesting thing
about being shot at.

**Each track feeds the simulation that already exists**, rather than an invented
"combat effectiveness":

    rigging   less canvas draws, and her polar curve does the rest
    oars      fewer looms manned, and `rowed_speed` already counts them
    weapons   fewer guns serviceable, and the arcs already know which bear
    crew      routed through the company, so morale and mutiny answer for free
    hull      the only one that sinks her

**Damage is a fraction, not a count of hits.** Hulls here have continuous sizes rather
than five size classes, so "five points" means nothing without asking how big she is.
What a shot does depends on what it hits: the same broadside is a bad afternoon for a
first-rate and the end of a cutter, and `share_of` is where that is decided.

**The interesting results are qualitative.** A number going down is bookkeeping. A mast
over the side and a hole below the waterline are events, and they are what a report should
say and what a player will remember.

**How lethal this is, is one number.** `RESILIENCE_PER_METRE` sets the scale of the whole
system and is deliberately set against the guns rather than guessed - a game that wants a
bloodier sea lowers it and everything downstream follows, with no other number to find.
Where the default sits is a judgement about the age being modelled rather than a fact, and
it is written down in `DECISIONS.md` for Gary to move.

"""

from dataclasses import dataclass, replace

#: What can be broken. Crew is not among them: casualties are people, not a fraction of
#: a system, and they already have somewhere better to live in `crew`.
HULL = "hull"
RIGGING = "rigging"
OARS = "oars"
WEAPONS = "weapons"
TRACKS = (HULL, RIGGING, OARS, WEAPONS)

#: What she is when a track has gone far enough to be worth a word rather than a number.
MAST_DOWN = "mast down"
HOLED = "holed"
DISABLED = "disabled"
DISARMED = "disarmed"

#: How far a track has to go before it stops being damage and becomes an event. Rigging
#: first, because a mast comes down long before the last shroud is cut.
MAST_DOWN_AT = 0.6
HOLED_AT = 0.7
DISABLED_AT = 0.8
DISARMED_AT = 0.9

#: How much punishment a hull absorbs, as a multiple of her length in metres. A bigger
#: ship is not merely bigger - she has more of everything to lose, and the shot that
#: ends a cutter is a bad afternoon for a first-rate.
#:
#: **This is the number that sets the scale of the whole system**, and it is set against
#: the guns rather than guessed. `WeaponType.damage` defaults to ten and its docstring has
#: always said it is meaningless until the damage phase gives it a scale; this is that
#: scale. At nine per metre a single hit from a default gun takes roughly:
#:
#:     a ship's boat, 8 m       one hit in nine of a track
#:     a sloop, 18 m            one hit in sixteen
#:     a frigate, 46 m          one hit in forty
#:     a first-rate, 62 m       one hit in fifty-five
#:
#: which is the right shape for the age it is modelling: ships were reduced over an hour
#: of firing, not in a broadside, and the ones that went quickly went by fire or magazine
#: rather than by being whittled. A game that wants a bloodier sea lowers it.
RESILIENCE_PER_METRE = 9.0

#: The least resilience anything has, so a coracle is not divided by nothing. Set so the
#: smallest imaginable craft still takes several hits rather than evaporating.
MINIMUM_RESILIENCE = 50.0

#: How much slower a shaken crew serve a gun, at their worst. Half again: they are
#: frightened, not gone, and a battery that stopped entirely would make morale a
#: kill switch rather than a cost.
HESITATION_ON_SERVING = 0.5


@dataclass(frozen=True)
class Damage:
    """
    How much of each of her systems has been taken away.

    Attributes:
        hull (float): 0 sound, 1 destroyed.
        rigging (float): As above.
        oars (float): As above.
        weapons (float): As above.

    Notes:
        Frozen, and every change returns a new one. Damage is the sort of state that
        gets written from several places in a tick - a broadside, a grounding, a
        fire - and a mutable version would let two of them interleave.

    """

    hull: float = 0.0
    rigging: float = 0.0
    oars: float = 0.0
    weapons: float = 0.0

    def of(self, track):
        """
        Args:
            track (str): One of `TRACKS`.

        Returns:
            amount (float): How much of it is gone.

        Raises:
            ValueError: If that is not a track.

        """
        if track not in TRACKS:
            raise ValueError(f"Unknown damage track {track!r}; expected one of {TRACKS}.")
        return getattr(self, track)

    def hurt(self, track, amount):
        """
        Args:
            track (str): What was hit.
            amount (float): How much of that system it took, 0 to 1.

        Returns:
            damage (Damage): Her state afterwards.

        """
        return replace(self, **{track: _clamp(self.of(track) + max(0.0, amount))})

    def mended(self, track, amount):
        """
        Args:
            track (str): What was worked on.
            amount (float): How much of it was put right.

        Returns:
            damage (Damage): Her state afterwards.

        """
        return replace(self, **{track: _clamp(self.of(track) - max(0.0, amount))})

    @property
    def sound(self):
        """
        Returns:
            sound (bool): True if nothing is damaged at all.

        """
        return all(self.of(track) <= 0.0 for track in TRACKS)

    @property
    def worst(self):
        """
        Returns:
            worst (tuple): `(track, amount)` for whatever is furthest gone.

        """
        return max(((track, self.of(track)) for track in TRACKS), key=lambda pair: pair[1])


def resilience(length, per_metre=RESILIENCE_PER_METRE, floor=MINIMUM_RESILIENCE):
    """
    How much punishment a hull absorbs before she is finished.

    Args:
        length (float): Her length overall, in metres.
        per_metre (float, optional): Resilience per metre of her.
        floor (float, optional): The least anything has.

    Returns:
        resilience (float): What a full track's worth of damage costs.

    Notes:
        Length rather than displacement, because length is a fact every hull here
        already carries and displacement is not. It is a proxy and an honest one:
        the thing that matters is that a big ship has more to lose.

    """
    return max(floor, length * per_metre)


def share_of(amount, length):
    """
    What a given weight of damage means to a given hull.

    Args:
        amount (float): Damage delivered, in whatever units the game's weapons speak.
        length (float): The hull's length overall, in metres.

    Returns:
        share (float): The fraction of one track it takes out.

    Notes:
        The whole reason damage is a fraction. The same broadside is the end of a
        cutter and a bad afternoon for a first-rate, and nothing else in the system
        has to know that - it is decided once, here.

    """
    return max(0.0, amount) / resilience(length)


def casualties_from(amount, length, complement):
    """
    How many of her people a weight of damage takes.

    Args:
        amount (float): Damage delivered, in the units her weapons speak.
        length (float): The hull's length overall, in metres.
        complement (int): How many she is manned by when full.

    Returns:
        lost (int): How many are down.

    Notes:
        The same share a hull takes, applied to the people instead - a shot that
        would take a twentieth of her structure takes a twentieth of her company.
        That keeps one dial governing how lethal everything is rather than two that
        can drift apart.

        Rounded to the nearest whole person, because half a casualty is not a thing
        anybody can report, and capped at the whole company - a shot heavy enough to
        take a hull twice over still only kills the people who are aboard.

    """
    share = min(1.0, share_of(amount, length))
    return int(round(share * max(0, complement)))


def canvas_drawing(damage):
    """
    Args:
        damage (Damage): What is broken.

    Returns:
        fraction (float): How much of the sail she sets is actually pulling.

    Notes:
        Multiplied into the sail plan rather than subtracted from it, so a ship with
        her rigging cut about carries less sail *at every plan* - which is what makes
        shooting for the rigging a way of catching somebody rather than killing them.

    """
    return _clamp(1.0 - damage.rigging)


def looms_manned(positions, damage):
    """
    Args:
        positions (int): How many oars she is fitted for.
        damage (Damage): What is broken.

    Returns:
        manned (int): How many are still there to pull.

    Notes:
        Rounded down, and honestly: half an oar is no oar. A galley with her sweeps
        shot away on one side is the point of sheering, and this is the number that
        makes it worth doing.

    """
    return max(0, int(positions * (1.0 - damage.oars)))


def guns_serviceable(count, damage):
    """
    Args:
        count (int): How many guns she mounts.
        damage (Damage): What is broken.

    Returns:
        serviceable (int): How many can still be fought.

    """
    return max(0, int(count * (1.0 - damage.weapons)))


def serving_time(base, damage=None, hesitation=0.0, penalty=HESITATION_ON_SERVING):
    """
    How long it takes to serve a gun again.

    Args:
        base (float): The weapon's own reload time, in game seconds.
        damage (Damage, optional): What is broken about her.
        hesitation (float, optional): How much of what her people could do is not
            being done, from `morale`.
        penalty (float, optional): How much slower a wholly shaken crew are.

    Returns:
        seconds (float): How long this gun will take.

    Notes:
        This is where morale finally costs something. `hesitation` has been computed
        since the crew went in and read by nothing, which made it a claim rather than
        a rule; a frightened crew serving their guns slower is the plainest possible
        way for it to matter.

        Damage to the battery slows the rest too - fewer hands who know the drill,
        working round wreckage - so the two compound rather than competing.

    """
    slower = 1.0 + penalty * _clamp(hesitation)
    if damage is not None:
        slower *= 1.0 + damage.weapons
    return base * slower


def structural(damage):
    """
    What is wrong with her in words rather than numbers.

    Args:
        damage (Damage): What is broken.

    Returns:
        failures (tuple): Keys from `MAST_DOWN`, `HOLED`, `DISABLED`, `DISARMED`.

    Notes:
        A number going down is bookkeeping; a mast over the side is an event. These
        are what a report should lead with and what anybody will remember afterwards,
        and they are derived rather than stored so they cannot disagree with the
        tracks they come from.

    """
    failures = []
    if damage.rigging >= MAST_DOWN_AT:
        failures.append(MAST_DOWN)
    if damage.hull >= HOLED_AT:
        failures.append(HOLED)
    if damage.oars >= DISABLED_AT:
        failures.append(DISABLED)
    if damage.weapons >= DISARMED_AT:
        failures.append(DISARMED)
    return tuple(failures)


def _clamp(value):
    """
    Args:
        value (float): Any number.

    Returns:
        value (float): The same, held between 0 and 1.

    """
    return max(0.0, min(1.0, value))


class Damaged:
    """
    The Evennia-side face of what is broken.

    Notes:
        Holds one frozen `Damage` and converts weights of damage into shares of it,
        which is the only thing that needs to know how big she is. Everything else
        reads the tracks and answers for itself.

    """

    def at_object_creation(self):
        """Set up this part of a newly created vessel."""
        super().at_object_creation()
        self.db.damage = Damage()

    @property
    def damage(self):
        """
        Returns:
            damage (Damage): What is broken about her.

        """
        stored = self.db.damage
        return stored if stored is not None else Damage()

    @damage.setter
    def damage(self, damage):
        """
        Args:
            damage (Damage): Her state.

        """
        if self.db.damage != damage:
            self.db.damage = damage

    def take_damage(self, track, amount):
        """
        Something hit her.

        Args:
            track (str): Which of `TRACKS` was struck.
            amount (float): Damage delivered, in the units her weapons speak -
                `ShotResult.damage` and the like, not a fraction.

        Returns:
            failures (tuple): Anything that carried away as a result, from
                `structural`. Empty if she merely took it.

        Notes:
            Takes a weight rather than a fraction on purpose. A caller with a shot
            in its hand knows what the shot was worth and does not know how big the
            target is; this does, and converting in one place is what stops every
            weapon in every game having to.

            Returns only what is *newly* wrong. A mast that was already over the
            side does not come down twice, and a report that said so every time she
            was hit again would be worse than silence.

        """
        before = set(structural(self.damage))
        self.damage = self.damage.hurt(track, share_of(amount, self.length))
        return tuple(wrong for wrong in structural(self.damage) if wrong not in before)

    def take_crew_casualties(self, amount):
        """
        Something hit her people.

        Args:
            amount (float): Damage delivered, in the units her weapons speak.

        Returns:
            lost (int): How many are down. Zero if nobody has crewed her.

        Notes:
            Crew is the one track that is not a track. Casualties are people, and
            they already have somewhere better to live - so this routes through the
            company, which means morale, exhaustion, striking and mutiny all answer
            without a line of new wiring. That join is the whole reason the crew
            work was done first.

        """
        company = self.company
        if company is None:
            return 0
        lost = casualties_from(amount, self.length, company.complement)
        if lost:
            self.take_casualties(lost)
        return lost

    def repair(self, track, fraction):
        """
        Args:
            track (str): What was worked on.
            fraction (float): How much of that track was put right, 0 to 1.

        Returns:
            damage (Damage): Her state afterwards.

        """
        self.damage = self.damage.mended(track, fraction)
        return self.damage

    @property
    def structural_failures(self):
        """
        Returns:
            failures (tuple): What is wrong with her, in words.

        """
        return structural(self.damage)

    @property
    def seaworthy(self):
        """
        Returns:
            seaworthy (bool): False once she is open to the sea.

        Notes:
            Holed is the only one of the failures that is about *sinking*. A ship
            with her masts gone and every gun dismounted is a wreck to look at and
            will still float home.

        """
        return HOLED not in self.structural_failures
