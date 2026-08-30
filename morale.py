"""
How a ship's company feels about what is being done to them, and when they stop.

Morale here is a **standing condition**, not a check. A crew is not asked "do you break?"
at moments of crisis and found steady or found wanting; they hold a state that is ground
down by what happens to them and comes back slowly when it stops. That distinction is the
whole of this module. A crew that has been shelled for an hour and then given ten minutes'
peace is not the crew they were before the shelling, and a system that re-rolls a check
each time cannot represent that.

**It falls faster than it rises.** Two different rates, and the difference is not
decoration - it is why a captain who spends his people cannot simply stop spending them
and have them back.

**Nothing here is hidden.** The reading is computed from the base and the factors and is
inspectable at any time; a roll may be injected to add variance, and if none is the whole
system is deterministic and still works. A die that decides an outcome the systems
underneath it could not is a die that hollows them out.

**Two collapses, and which one you get depends on whose fault it is.**

    striking   what a crew does when the *enemy* has beaten them. They have been hurt
               past what men of their quality will bear and there is nothing dishonourable
               left to try.
    mutiny     what a crew does when the *captain* has. Every grievance is something
               command did or failed to do - drove them past exhaustion, spent them
               past bearing and would not strike, or is not aboard at all.

A crew that strikes has lost a fight. A crew that mutinies has lost confidence. Modelling
both as one "morale failure" loses the only part anybody cares about.

**This knows nothing about crews.** It takes numbers - a base, a casualty fraction, an
exhaustion - so that what a crew *is* can change without this changing. See `crew.py` for
the thing that supplies them.

"""

import math
from dataclasses import dataclass

#: How they are holding up, worst to best. A band rather than a number because a number
#: invites a progress bar, and a crew is not a progress bar - what matters is which of a
#: few recognisable states they are in, each of which a ship behaves differently in.
BROKEN = "broken"
WAVERING = "wavering"
SHAKEN = "shaken"
UNEASY = "uneasy"
STEADY = "steady"

#: Where one band gives way to the next, best first. Read as "at or above this value".
BANDS = (
    (0.75, STEADY),
    (0.55, UNEASY),
    (0.35, SHAKEN),
    (0.15, WAVERING),
    (0.0, BROKEN),
)

#: What each band costs her, as a fraction taken off what her people can do - gunnery
#: served slower, sail handled worse, an order obeyed a beat late. One number rather than
#: several, because the alternative is a table nobody can hold in their head.
HESITATION = {
    STEADY: 0.0,
    UNEASY: 0.05,
    SHAKEN: 0.15,
    WAVERING: 0.30,
    BROKEN: 0.50,
}

#: How long, in seconds, it takes a fall to run most of its course. Fast: a magazine going
#: up is felt across the ship within the minute.
FALL_SECONDS = 60.0

#: And a recovery. Slow, and deliberately an order of magnitude slower - a quarter of an
#: hour of quiet to undo what a minute of horror did.
RISE_SECONDS = 900.0

#: At or below this reading, striking is on the table. Not the same as striking: the
#: casualty gate has to be passed as well.
STRIKE_READING = 0.2

#: At or below this, mutiny is on the table - provided the grievances are there.
MUTINY_READING = 0.3

#: The fraction of a company lost past which nobody holds, whatever they are made of.
#: There is a point where there are simply not enough people left to work her.
ROUT = 0.9


@dataclass(frozen=True)
class Factor:
    """
    One named thing bearing on how they feel.

    Attributes:
        key (str): What it is, for a game to recognise and for messaging to speak.
        weight (float): What it moves the reading by. Negative is worse.
        only_when_asked (bool): True if it bears only on whether they will *strike*
            rather than on the standing condition. Whether the enemy takes prisoners
            does not change how a crew feels hour to hour; it changes entirely what
            they will do when the question is put.

    Notes:
        Data, not code. A game adds its own - a crew that will not fight their own
        countrymen, a company who believe the ship is cursed - by putting more of
        these in the list it hands in. Setting-specific morale belongs to the
        setting, and there is no way for this module to guess at it.

    """

    key: str
    weight: float
    only_when_asked: bool = False


#: The ones that are not setting-specific: things true of any ship in any world, which is
#: the only kind this contrib has any business having an opinion about.
CAPTAIN_LOST = Factor("captain_lost", -0.20)
OFFICER_LOST = Factor("officer_lost", -0.08)
BOARDED = Factor("boarded", -0.15)
AGROUND = Factor("aground", -0.10)
FOUNDERING = Factor("foundering", -0.25)
OUTGUNNED = Factor("outgunned", -0.10)
PRIZE_TAKEN = Factor("prize_taken", 0.15)
ENEMY_STRUCK = Factor("enemy_struck", 0.20)
QUARTER_REFUSED = Factor("quarter_refused", 0.15, only_when_asked=True)
QUARTER_OFFERED = Factor("quarter_offered", -0.10, only_when_asked=True)

STANDARD_FACTORS = (
    CAPTAIN_LOST,
    OFFICER_LOST,
    BOARDED,
    AGROUND,
    FOUNDERING,
    OUTGUNNED,
    PRIZE_TAKEN,
    ENEMY_STRUCK,
    QUARTER_REFUSED,
    QUARTER_OFFERED,
)

#: What a grievance is: something command did, or failed to do. Kept apart from the
#: factors above because these do not merely lower morale, they aim it at somebody.
DRIVEN = "driven"
BUTCHERED = "butchered"
LEADERLESS = "leaderless"

#: How exhausted a company has to be before being driven is a grievance rather than a
#: hard day. Below this they are tired; above it they were spent by somebody.
DRIVEN_THRESHOLD = 0.75

#: How many separate grievances it takes before mutiny is possible. Two, because one is a
#: complaint and two is agreement - and agreement is what turns muttering into a rising.
GRIEVANCES_NEEDED = 2


def reading(base, factors=()):
    """
    What the company would settle at, given how things stand.

    Args:
        base (float): Their floor and ceiling both, from what they are made of. 0 to 1.
        factors (iterable): The `Factor` instances currently bearing on them. Ones
            marked `only_when_asked` are ignored here; see `when_asked`.

    Returns:
        value (float): Where they are heading, 0 to 1.

    Notes:
        A target, not a state. Nothing feels this immediately - `settle` is what moves
        them towards it, and how fast depends on which way they are going.

    """
    value = float(base)
    for factor in factors:
        if factor.only_when_asked:
            continue
        value += factor.weight
    return max(0.0, min(1.0, value))


def when_asked(value, factors=()):
    """
    Where they stand at the moment the question is actually put to them.

    Args:
        value (float): Their standing morale, 0 to 1.
        factors (iterable): Everything bearing on them. Only the ones marked
            `only_when_asked` are applied.

    Returns:
        value (float): What to test against the striking gate.

    Notes:
        Applied to where they actually stand rather than recomputed from their base,
        which matters more than it sounds. A crew who have been ground down for an
        hour and a crew who have not are different crews when the question is put,
        and rebuilding the number from their quality would throw away the hour.

        Kept apart from `reading` because these factors genuinely do not bear on the
        standing condition. Whether the enemy takes prisoners does not change how a
        company feel watch to watch; it changes entirely what they will do when asked
        to give up, which is a different question asked at one moment.

    """
    for factor in factors:
        if factor.only_when_asked:
            value += factor.weight
    return max(0.0, min(1.0, value))


def band_of(value):
    """
    Args:
        value (float): A morale reading, 0 to 1.

    Returns:
        band (str): Which of the five they are in.

    """
    for floor, band in BANDS:
        if value >= floor:
            return band
    return BROKEN


def hesitation(value):
    """
    Args:
        value (float): A morale reading, 0 to 1.

    Returns:
        fraction (float): How much of what her people could do is not being done.

    Notes:
        Deliberately one number applied to everything rather than a separate penalty
        per task. A frightened crew is slower at all of it, and a table with a
        different figure for gunnery and for sail handling implies a precision
        nothing here has earned.

    """
    return HESITATION[band_of(value)]


def settle(current, target, elapsed, fall=FALL_SECONDS, rise=RISE_SECONDS):
    """
    Move them towards where they are heading.

    Args:
        current (float): Where they are, 0 to 1.
        target (float): Where they are heading, from `reading`.
        elapsed (float): Seconds since this was last done.
        fall (float, optional): Seconds over which most of a drop happens.
        rise (float, optional): Seconds over which most of a recovery happens.

    Returns:
        value (float): Where they are now.

    Notes:
        Exponential rather than linear, so the answer does not depend on how often it
        is asked. A tick that runs twice as often must not move morale twice as fast,
        or the simulation changes when the server gets busy.

        Falling is fast and rising is slow, and the asymmetry is the point. A captain
        who spends his people cannot stop spending them and have them back.

    """
    if elapsed <= 0.0:
        return current
    span = fall if target < current else rise
    if span <= 0.0:
        return target
    approach = 1.0 - math.exp(-elapsed / span)
    return current + (target - current) * approach


def strikes(value, casualties, floor, roll=None):
    """
    Whether they will strike her colours.

    Args:
        value (float): Their reading with the question actually put - that is,
            `reading(..., asked=True)`, so that whether quarter is given counts.
        casualties (float): The fraction of the company lost, 0 to 1.
        floor (float): How much loss men of their quality will take before the
            question is even worth asking. From their quality; better crews have
            a higher one and so must be hurt more.
        roll (callable, optional): Returns 0 to 1. Adds variance. Without it this
            is entirely deterministic and still works.

    Returns:
        struck (bool): True if she strikes.

    Notes:
        Two gates, and both must be passed. A crew can be terrified and unhurt and
        fight on; a crew can be cut to pieces and steady and fight on. It takes both,
        which is why a single "morale" number could never have expressed this.

        Above `ROUT` there is no gate and no roll. That is not a question of nerve -
        there are not enough of them left to work her.

    """
    if casualties >= ROUT:
        return True
    if casualties < floor:
        return False
    if value > STRIKE_READING:
        return False
    if roll is None:
        return True
    return roll() < _pressure(value, STRIKE_READING, casualties, floor)


def grievances(exhaustion=0.0, casualties=0.0, floor=1.0, has_captain=True, struck=False):
    """
    What the company holds against her command.

    Args:
        exhaustion (float): How spent they are, 0 to 1.
        casualties (float): The fraction of the company lost.
        floor (float): What men of their quality will bear before it is a grievance.
        has_captain (bool): Whether anybody is aboard giving orders.
        struck (bool): Whether she has already struck.

    Returns:
        held (tuple): The grievance keys, in no particular order.

    Notes:
        Every one of these is command's doing, which is what separates this from the
        factors that merely lower morale. Being outgunned is nobody's fault; being
        driven past exhaustion is somebody's.

        Casualties only count once she has *not* struck. A crew cut to pieces in a
        fight their captain is still trying to win have been spent; the same crew cut
        to pieces in a fight he ended have been unlucky. The difference is whether he
        would stop, and it is the entire distinction between mutiny and defeat.

    """
    held = []
    if exhaustion >= DRIVEN_THRESHOLD:
        held.append(DRIVEN)
    if casualties >= floor and not struck:
        held.append(BUTCHERED)
    if not has_captain:
        held.append(LEADERLESS)
    return tuple(held)


def mutinies(value, held, needed=GRIEVANCES_NEEDED, roll=None):
    """
    Whether the company will turn on their command.

    Args:
        value (float): Their standing reading, 0 to 1.
        held (iterable): The grievances, from `grievances`.
        needed (int, optional): How many it takes.
        roll (callable, optional): Returns 0 to 1. Adds variance; without it this is
            deterministic.

    Returns:
        risen (bool): True if they rise.

    Notes:
        Two gates again, and deliberately the same shape as striking - low morale is
        necessary and nowhere near sufficient. Frightened men obey. It takes
        frightened men who have decided the fright is somebody's fault.

    """
    held = tuple(held)
    if len(held) < needed:
        return False
    if value > MUTINY_READING:
        return False
    if roll is None:
        return True
    return roll() < _pressure(value, MUTINY_READING, float(len(held)), float(needed))


def _pressure(value, threshold, quantity, gate):
    """
    How likely a collapse is, once both gates are open.

    Args:
        value (float): The reading.
        threshold (float): The reading gate it passed.
        quantity (float): Whatever the second gate measured - casualties, grievances.
        gate (float): What that gate required.

    Returns:
        chance (float): 0 to 1.

    Notes:
        Grows with how far past both gates things are, so a crew barely over the line
        usually holds and a crew far past it usually does not. The midpoint of the two
        margins rather than their sum, so neither alone can carry it - which is the
        same argument the two gates make, applied to the odds instead of the question.

    """
    reading_margin = 0.0 if threshold <= 0.0 else (threshold - value) / threshold
    quantity_margin = 0.0 if quantity <= gate else min(1.0, (quantity - gate) / max(gate, 1e-9))
    return max(0.0, min(1.0, 0.5 + 0.5 * (reading_margin + quantity_margin) / 2.0))
