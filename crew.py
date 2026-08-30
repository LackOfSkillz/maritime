"""
The ship's company: how many she is manned by, what they are made of, and what it costs
them to work her.

**A company is a number, not a crowd of objects.** A frigate carries three hundred people
and a galley two hundred oarsmen, and creating them as individuals to be counted every
tick would be absurd. Named characters aboard are the host game's, and always were; this
counts the rest, because the rest is what makes her work.

**Quality is two claims, not one.** How well they work her, and how much they will take
before they stop. Those are genuinely separate - a pressed crew who cannot reef in a
squall may still be terrified enough of the alternative to hold, and a crack crew who can
do anything will still not stand at any price. Collapsing them into one "veteran" number
loses the more interesting of the two.

**Exhaustion is a ship-level state.** How spent the company is, not how tired any person
is. That is the only honest place for it: what a stroke costs a *character* collides with
whatever stamina the host game already has, and a contrib with an opinion about it would
be arguing with the game it was installed in. At ship scale there is nothing to collide
with - she pulls slower and her people are closer to breaking, both of which are hers.

**It comes back slower than it goes.** Same asymmetry as morale, for the same reason and
by the same function.

"""

from dataclasses import dataclass, replace

from .morale import (
    AGROUND,
    BOARDED,
    CAPTAIN_LOST,
    ENEMY_STRUCK,
    band_of,
    grievances,
    hesitation,
    mutinies,
    reading,
    settle,
    strikes,
    when_asked,
)

#: How long, in seconds, hard pulling takes to spend a company most of the way. Half an
#: hour at racing stroke, which is about what a boat's crew has in them.
SPEND_SECONDS = 1800.0

#: And how long resting takes to bring them back. Longer, because it always is.
RECOVER_SECONDS = 2700.0


@dataclass(frozen=True)
class CrewQuality:
    """
    What a company is made of.

    Attributes:
        key (str): What to call them.
        base_morale (float): Where they sit with nothing acting on them, 0 to 1.
        casualty_floor (float): The fraction of themselves they will lose before
            striking is even a question. Better crews have a higher one and so must
            be hurt more before it can be asked.
        skill (float): How well they work her, 0 to 1.

    Notes:
        The floor is the quiet half of this. Two gates decide a surrender - a bad
        reading and enough loss - and it is the floor that makes a good crew hard to
        beat rather than merely brave. A crack company that has taken a fifth of its
        number is not asked the question at all.

    """

    key: str
    base_morale: float
    casualty_floor: float
    skill: float


#: The gradations, worst to best. The names are ratings and the language sailors used for
#: them: a landsman is a man who has never been to sea, an ordinary seaman has, an able
#: seaman can do the whole of the work, and a crack ship is one whose company can do it
#: faster than the ship alongside.
PRESSED = CrewQuality("pressed", base_morale=0.30, casualty_floor=0.30, skill=0.35)
LANDSMEN = CrewQuality("landsmen", base_morale=0.40, casualty_floor=0.35, skill=0.45)
ORDINARY = CrewQuality("ordinary", base_morale=0.50, casualty_floor=0.40, skill=0.60)
ABLE = CrewQuality("able", base_morale=0.60, casualty_floor=0.50, skill=0.75)
SEASONED = CrewQuality("seasoned", base_morale=0.70, casualty_floor=0.60, skill=0.85)
PICKED = CrewQuality("picked", base_morale=0.80, casualty_floor=0.70, skill=0.95)
CRACK = CrewQuality("crack", base_morale=0.85, casualty_floor=0.80, skill=1.00)

QUALITIES = (PRESSED, LANDSMEN, ORDINARY, ABLE, SEASONED, PICKED, CRACK)

#: What a ship gets when nobody has said. Ordinary seamen: competent, unremarkable, and
#: the sort of company most vessels actually sail with.
DEFAULT_QUALITY = ORDINARY


def blended(parts):
    """
    One quality from several, weighted by how many of each.

    Args:
        parts (iterable): Pairs of `(CrewQuality, count)`.

    Returns:
        quality (CrewQuality): The company taken together.

    Raises:
        ValueError: If nobody was supplied.

    Notes:
        A ship is rarely one thing. She has seamen, and oarsmen, and perhaps a few
        soldiers who are better at fighting than at sailing, and what she does under
        fire is decided by the mixture rather than by the best of them.

        Weighted by head count and left as it falls, rather than rounded to the
        nearest named grade. Rounding would make forty pressed men and ten crack ones
        come out as a grade nobody in the company actually is, and would make the
        answer jump when one man dies.

    """
    parts = [(quality, float(count)) for quality, count in parts if count > 0]
    if not parts:
        raise ValueError("blended() needs at least one quality with somebody in it.")

    total = sum(count for _, count in parts)
    return CrewQuality(
        key="mixed" if len(parts) > 1 else parts[0][0].key,
        base_morale=sum(q.base_morale * n for q, n in parts) / total,
        casualty_floor=sum(q.casualty_floor * n for q, n in parts) / total,
        skill=sum(q.skill * n for q, n in parts) / total,
    )


@dataclass(frozen=True)
class ShipsCompany:
    """
    Who she is manned by, and how many of them are still standing.

    Attributes:
        complement (int): How many she is manned by when full.
        fit (int): How many are alive and able to work.
        quality (CrewQuality): What they are made of.

    """

    complement: int
    fit: int
    quality: CrewQuality = DEFAULT_QUALITY

    def __post_init__(self):
        """
        Raises:
            ValueError: If she is manned by a negative number of people, or by more
                than she has room for.

        """
        if self.complement < 0:
            raise ValueError(f"complement cannot be negative, got {self.complement!r}.")
        if self.fit < 0:
            raise ValueError(f"fit cannot be negative, got {self.fit!r}.")
        if self.fit > self.complement:
            raise ValueError(
                f"fit ({self.fit}) cannot exceed complement ({self.complement}); "
                "a ship cannot have more people standing than she is manned by."
            )

    @property
    def casualties(self):
        """
        Returns:
            lost (int): How many are down.

        """
        return self.complement - self.fit

    @property
    def casualty_fraction(self):
        """
        Returns:
            fraction (float): How much of herself she has lost, 0 to 1.

        Notes:
            A fraction rather than a count, because forty dead means something
            different on a longboat and on a ship of the line, and every gate that
            reads this cares about the proportion.

        """
        if self.complement <= 0:
            return 0.0
        return self.casualties / self.complement

    @property
    def strength(self):
        """
        Returns:
            strength (float): What they are worth in a fight, in effective hands.

        Notes:
            Numbers times what they are made of. Twenty able seamen and forty
            pressed men are not the same boarding party, and the point of holding
            quality at all is that this can say so.

        """
        return self.fit * self.quality.skill

    def hurt(self, lost):
        """
        Take casualties.

        Args:
            lost (int): How many went down.

        Returns:
            company (ShipsCompany): The company afterwards.

        Notes:
            Never below nobody. A ship can be hit hard enough to kill more people
            than she has, and the arithmetic should not have to be checked at every
            call site.

        """
        return replace(self, fit=max(0, self.fit - int(lost)))

    def recover(self, back):
        """
        Get some of them back on their feet.

        Args:
            back (int): How many returned to duty.

        Returns:
            company (ShipsCompany): The company afterwards.

        Notes:
            Capped at her complement, because the walking wounded coming back up is
            not the same as finding people who were never aboard.

        """
        return replace(self, fit=min(self.complement, self.fit + int(back)))


def spend(current, effort, elapsed):
    """
    Work them, or let them rest.

    Args:
        current (float): How spent they are now, 0 to 1.
        effort (float): What is being asked of them, 0 to 1. The stroke efforts in
            `oars` are on exactly this scale, which is not a coincidence.
        elapsed (float): Seconds of it.

    Returns:
        exhaustion (float): How spent they are now.

    Notes:
        Tends towards the effort rather than accumulating without limit. Easy oars
        all day tends towards rested; a racing stroke tends towards spent, and gets
        most of the way there in half an hour. A crew asked for nothing recovers.

        The same curve as morale, and for the same reason: the answer must not depend
        on how often the tick happens to run.

    """
    target = max(0.0, min(1.0, float(effort)))
    return settle(current, target, elapsed, fall=RECOVER_SECONDS, rise=SPEND_SECONDS)


class Crewed:
    """
    The Evennia-side face of the company and how they are holding up.

    Notes:
        Holds five numbers and derives everything else. What a game has to supply is
        her complement and what her people are made of; casualties, exhaustion and
        morale are consequences of what is done to her, and this works them out.

        Nothing here speaks. `messaging` says what a wavering crew looks like from
        the quarterdeck; this only knows that they are wavering.

    """

    def at_object_creation(self):
        """Set up this part of a newly created vessel."""
        super().at_object_creation()
        self.db.complement = 0
        self.db.fit = 0
        self.db.crew_quality = DEFAULT_QUALITY
        self.db.morale = DEFAULT_QUALITY.base_morale
        self.db.exhaustion = 0.0

    # --- the company --------------------------------------------------------

    @property
    def company(self):
        """
        Returns:
            company (ShipsCompany or None): Who she is manned by, or None if nobody
                has said.

        Notes:
            A vessel with no company is not a vessel with an empty one. She is a boat
            nobody has bothered to crew, and every rule here leaves her alone - which
            is what lets a game adopt none of this and still sail.

        """
        complement = self.db.complement or 0
        if complement <= 0:
            return None
        return ShipsCompany(
            complement=complement,
            fit=self.db.fit or 0,
            quality=self.db.crew_quality or DEFAULT_QUALITY,
        )

    @company.setter
    def company(self, company):
        """
        Args:
            company (ShipsCompany or None): Her company, or None to say she has none.

        """
        if company is None:
            if self.db.complement != 0:
                self.db.complement = 0
            if self.db.fit != 0:
                self.db.fit = 0
            return
        if self.db.complement != company.complement:
            self.db.complement = company.complement
        if self.db.fit != company.fit:
            self.db.fit = company.fit
        if self.db.crew_quality != company.quality:
            self.db.crew_quality = company.quality

    def man(self, complement, quality=DEFAULT_QUALITY):
        """
        Give her a full company.

        Args:
            complement (int): How many.
            quality (CrewQuality, optional): What they are made of.

        Returns:
            company (ShipsCompany): What she now has.

        Notes:
            The ordinary way to crew a ship, as distinct from assigning a company
            that has already been through something. Their morale starts where men of
            their quality start.

        """
        self.company = ShipsCompany(complement=complement, fit=complement, quality=quality)
        self.morale = quality.base_morale
        return self.company

    def take_casualties(self, lost):
        """
        Args:
            lost (int): How many went down.

        Returns:
            company (ShipsCompany or None): The company afterwards.

        """
        company = self.company
        if company is None:
            return None
        self.company = company.hurt(lost)
        return self.company

    # --- what it costs them -------------------------------------------------

    @property
    def exhaustion(self):
        """
        Returns:
            spent (float): How spent the company is, 0 to 1.

        """
        stored = self.db.exhaustion
        return 0.0 if stored is None else stored

    @exhaustion.setter
    def exhaustion(self, value):
        """
        Args:
            value (float): How spent they are, 0 to 1.

        """
        value = max(0.0, min(1.0, float(value)))
        if self.db.exhaustion != value:
            self.db.exhaustion = value

    def work(self, effort, elapsed):
        """
        Ask something of them for a while.

        Args:
            effort (float): What is being asked, 0 to 1. The stroke efforts in `oars`
                are on this scale, which is not a coincidence.
            elapsed (float): Seconds of it.

        Returns:
            spent (float): How spent they are now.

        """
        if self.company is None:
            return 0.0
        self.exhaustion = spend(self.exhaustion, effort, elapsed)
        return self.exhaustion

    def stand_watch(self, elapsed, factors=()):
        """
        Let a watch pass over the company: what it cost them, and how they feel.

        Args:
            elapsed (float): Seconds of it.
            factors (iterable, optional): Anything bearing on them she cannot see.

        Returns:
            stood (bool): True if there was anybody to stand it.

        Notes:
            Called from the tick, so a game gets tiring and flagging crews without
            wiring anything. Only the oars tire them here - it is the one effort this
            contrib actually measures, and the honest thing to do about the rest is
            let them rest rather than invent a number for how hard sailing is.

            A game with more to say calls `work` directly. Manning the pumps through
            a night, beating to windward in a gale, a chase held for six hours: all
            real, all costs this cannot see, and all a single call away.

        """
        if self.company is None:
            return False
        from .oars import STROKE_EFFORT

        effort = STROKE_EFFORT.get(self.stroke, 0.0) if self.under_oars else 0.0
        self.work(effort, elapsed)
        self.feel(elapsed, factors)
        return True

    # --- how they feel about it ---------------------------------------------

    @property
    def morale(self):
        """
        Returns:
            value (float): Where the company stands, 0 to 1.

        """
        stored = self.db.morale
        if stored is None:
            company = self.company
            return company.quality.base_morale if company else DEFAULT_QUALITY.base_morale
        return stored

    @morale.setter
    def morale(self, value):
        """
        Args:
            value (float): Where they stand, 0 to 1.

        """
        value = max(0.0, min(1.0, float(value)))
        if self.db.morale != value:
            self.db.morale = value

    @property
    def morale_band(self):
        """
        Returns:
            band (str): Which of the five they are in.

        """
        return band_of(self.morale)

    @property
    def hesitation(self):
        """
        Returns:
            fraction (float): How much of what her people could do is not being done.

        """
        return hesitation(self.morale)

    def conditions(self):
        """
        The factors she can see for herself.

        Returns:
            factors (tuple): What is bearing on her company, from her own state.

        Notes:
            Derived rather than handed in, because a game should not have to remember
            to tell a ship she is aground. What she cannot see - that these are her
            countrymen, that the enemy has a reputation - is exactly what a game adds
            to the list, and why `feel` takes more.

        """
        found = []
        if self.captain is None:
            found.append(CAPTAIN_LOST)
        if self.aground:
            found.append(AGROUND)
        if self.grappled and not self.struck:
            found.append(BOARDED)
        alongside = self.grappled_to
        if alongside is not None and getattr(alongside, "struck_to", None) is self:
            found.append(ENEMY_STRUCK)
        return tuple(found)

    def feel(self, elapsed, factors=()):
        """
        Let time pass over them.

        Args:
            elapsed (float): Seconds since this was last done.
            factors (iterable, optional): Anything bearing on them she cannot see.

        Returns:
            value (float): Where they stand now.

        Notes:
            Her own conditions are always included. What is handed in is added to
            them rather than replacing them, so a game that supplies nothing still
            gets a crew who mind being aground.

        """
        company = self.company
        if company is None:
            return self.morale
        bearing = self.conditions() + tuple(factors)
        target = reading(company.quality.base_morale, bearing)
        self.morale = settle(self.morale, target, elapsed)
        return self.morale

    # --- and when they stop -------------------------------------------------

    def will_strike(self, factors=(), roll=None):
        """
        Whether the company will strike her colours.

        Args:
            factors (iterable, optional): Anything she cannot see for herself.
            roll (callable, optional): Returns 0 to 1. Without it, deterministic.

        Returns:
            striking (bool): True if they will.

        Notes:
            Tested against where they actually stand, adjusted for the factors that
            bear only on being asked - whether the enemy is known to give quarter.
            An hour of being ground down counts; so does knowing what surrendering to
            this particular enemy is worth.

        """
        company = self.company
        if company is None:
            return False
        bearing = self.conditions() + tuple(factors)
        return strikes(
            when_asked(self.morale, bearing),
            company.casualty_fraction,
            company.quality.casualty_floor,
            roll=roll,
        )

    def held_against_command(self):
        """
        Returns:
            held (tuple): What the company holds against her command.

        """
        company = self.company
        if company is None:
            return ()
        return grievances(
            exhaustion=self.exhaustion,
            casualties=company.casualty_fraction,
            floor=company.quality.casualty_floor,
            has_captain=self.captain is not None,
            struck=self.struck,
        )

    def will_mutiny(self, roll=None):
        """
        Whether the company will turn on her command.

        Args:
            roll (callable, optional): Returns 0 to 1. Without it, deterministic.

        Returns:
            rising (bool): True if they will.

        Notes:
            A crew who have already struck do not mutiny. The fight is over, and
            whatever they hold against their captain, rising against him now is a
            different story than this one is telling.

        """
        if self.company is None or self.struck:
            return False
        return mutinies(self.morale, self.held_against_command(), roll=roll)
