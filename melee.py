"""
Carrying a deck, and holding one.

A boarding action at ship scale: one party crosses, one party meets them, and the fight is
decided by how much of each side can actually be brought to bear rather than by how many
each ship carries.

**Frontage is the whole idea.** Numbers matter, but a hundred men cannot fight through a
gap two men wide. How much of the two hulls are touching decides how many can cross at
once, and that is a *measurement* here rather than a table of adjacencies: both hulls carry
a length, a beam, a heading and a position, so `boarding.alongside` already knows how much
of them is side by side. Bow to bow admits a handful. Laid properly alongside, with the
rails together for the length of the shorter ship, admits as many as can stand at them.

**And the defenders are capped too**, which is the detail that stops boarding from being
decided by headcount. A repelling party may be any size at all - every soul aboard may
turn out - but only about twice the boarders can reach the fighting. The rest are behind
them on a crowded deck, waiting for somebody in front to fall. A ship with three hundred
men does not beat forty marines by three hundred to forty; she beats them by eighty to
forty, and that is a fight the marines can win.

**Frontage decides the scale, and then decides the fight.** While the defender still has
men to spare she meets whatever crosses with twice its number, however wide the contact - so
a narrow gap and a whole rail give the same odds and only the size of the fight differs.
The moment she cannot field twice what comes over, every extra man across is a man she has
nobody to meet, and the contact starts deciding the outcome instead of merely its scale.
Which is the whole argument for beating her down before boarding her, and it was not
designed in: it fell out of the two caps meeting, and a test found it.

**Strength is people, not a number on the hull.** `crew.Division.strength` already sums a
group by what each of them is worth in a melee - marines are worth twice what oarsmen are,
and quality multiplies both - so nothing here has an opinion about who is dangerous. It
asks the company and the company answers.

Pure arithmetic. Nothing in this module knows what an Evennia object is.
"""

from dataclasses import dataclass

from .results import Result

#: How many people can stand at a rail, per metre of it.
#:
#: Shoulder to shoulder with room to swing is a little over a metre and a half each. It is
#: the number that turns a contact measured in metres into a party measured in men, and it
#: is the only place this module has an opinion about how big a person is.
MEN_PER_METRE = 0.6

#: How much being properly alongside is worth.
#:
#: Rails together and lashed the length of her, rather than touching at an angle. Doubling
#: is what the source says and it is the right shape: a ship laid alongside deliberately is
#: not twice as close as one that fell against her, she is twice as *available*, because
#: every foot of the contact is somewhere a man can cross rather than one point where the
#: hulls happen to meet.
ALONGSIDE_BONUS = 2.0

#: How much of the contact counts as properly alongside.
#:
#: Above this share of the shorter hull the two are lying together rather than touching, and
#: the bonus applies. Below it they are in contact at an angle and the frontage is whatever
#: the geometry gives.
LYING_TOGETHER = 0.5

#: The fewest a boarding can ever put across.
#:
#: Two hulls that touch at all touch somewhere, and somebody can always get over. Without a
#: floor, a bow-to-bow contact rounds to nobody and a boarding that the geometry permits
#: reports that not a man could cross, which reads as a bug.
FEWEST_ACROSS = 2

#: How many defenders can reach the fighting, per boarder.
#:
#: **The cap that stops boarding being decided by headcount.** A repelling party may be any
#: size; only the front of it is in the fight. Twice the boarders is about what a crowded
#: deck admits round a boarding party's frontage, and the rest are waiting for room.
DEFENDERS_PER_BOARDER = 2.0

#: How much stronger one side has to be to settle it in one exchange.
#:
#: Below this the fight is not resolved: both sides feed in what they have and it goes on.
#: A boarding decided instantly the moment either side had a nose in front would make
#: reinforcing pointless, and reinforcing is most of what a boarding action is.
DECISIVE = 1.5

BOARDERS_BEATEN = "boarders_beaten"
DEFENDERS_BEATEN = "defenders_beaten"
UNOPPOSED = "unopposed"
UNRESOLVED = "unresolved"
NOBODY_CROSSED = "nobody_crossed"


@dataclass(frozen=True, kw_only=True)
class MeleeResult(Result):
    """
    What came of one exchange on a boarded deck.

    Attributes:
        outcome (str): One of the four above.
        across (int): How many crossed.
        met (int): How many defenders could reach them.
        boarding_strength (float): What the party that crossed was worth.
        repelling_strength (float): What met them was worth.
        edge (float): The ratio between them, boarders over defenders. Above one the
            boarders are winning.
        taken (bool): Whether her deck has been carried.

    Notes:
        A failed result means nobody crossed at all - the hulls were not in contact, or
        there was nobody left to send. `UNRESOLVED` is a *successful* result: the fight
        happened and is still happening, which is the commonest outcome of any single
        exchange and is not a failure of anything.

    """

    outcome: str = UNRESOLVED
    across: int = 0
    met: int = 0
    boarding_strength: float = 0.0
    repelling_strength: float = 0.0
    edge: float = 0.0
    taken: bool = False


def frontage(overlap, shorter_length, men_per_metre=MEN_PER_METRE):
    """
    How many can cross at once, from how the hulls touch.

    Args:
        overlap (float): How much of them is alongside, 0 to 1, from `boarding.alongside`.
        shorter_length (float): The length of the shorter hull, in metres.
        men_per_metre (float, optional): How many can stand at a metre of rail.

    Returns:
        men (int): How many can be in the crossing at one time.

    Notes:
        Measured, not tabulated. The contact is a real length of rail - the overlap times
        the shorter hull - and a person occupies a real amount of it. Laid properly
        alongside doubles the answer, because every foot of the contact is then somewhere a
        man can cross rather than a point where two hulls happen to meet.

        Never fewer than `FEWEST_ACROSS` where there is any contact at all: two ships that
        touch, touch somewhere, and somebody can always get over.

    """
    if overlap <= 0.0 or shorter_length <= 0.0:
        return 0

    rail = overlap * shorter_length * men_per_metre
    if overlap >= LYING_TOGETHER:
        rail *= ALONGSIDE_BONUS
    return max(FEWEST_ACROSS, int(rail))


def can_reach(across, per_boarder=DEFENDERS_PER_BOARDER):
    """
    How many defenders can actually get at a boarding party.

    Args:
        across (int): How many crossed.
        per_boarder (float, optional): How many defenders reach the fighting per boarder.

    Returns:
        men (int): How many of the repelling party are in the fight.

    Notes:
        **This is what stops a boarding being decided by headcount**, and it is the detail
        every other implementation of this leaves out. Every soul aboard may turn out to
        repel; only the front of them is fighting. A ship with three hundred men does not
        beat forty marines by three hundred to forty - she beats them by eighty to forty,
        and the marines can win that.

    """
    return int(max(0, across) * per_boarder)


def party_strength(divisions, men):
    """
    What the best `men` a company can spare are worth in a fight.

    Args:
        divisions (iterable): `crew.Division` objects to draw from.
        men (int): How many to take.

    Returns:
        strength (float): Their fighting value.

    Notes:
        **Marines first, then seamen, then whoever is left.** A captain sending a boarding
        party sends the people he shipped to fight, and a party drawn evenly across the
        company would be a captain who did not know his own crew.

        Fractions of a division are taken at that division's own worth per man, which is
        what `strength` over `fit` gives - so taking half the marines is worth half the
        marines and not half the ship's average.

    """
    left = max(0, men)
    total = 0.0
    for division in sorted(divisions, key=_worth_each, reverse=True):
        if left <= 0:
            break
        taken = min(left, division.fit)
        total += _worth_each(division) * taken
        left -= taken
    return total


def _worth_each(division):
    """
    Args:
        division (Division): One group aboard.

    Returns:
        worth (float): What one of them is worth in a melee.

    """
    return division.strength / division.fit if division.fit else 0.0


def fight(boarding, repelling, overlap, shorter_length, decisive=DECISIVE):
    """
    One exchange on a boarded deck.

    Args:
        boarding (iterable): The attacker's `crew.Division` objects.
        repelling (iterable): The defender's.
        overlap (float): How the hulls touch, from `boarding.alongside`.
        shorter_length (float): The shorter hull's length, in metres.
        decisive (float, optional): How much stronger one side must be to settle it.

    Returns:
        result (MeleeResult): What happened, and whether her deck was carried.

    Notes:
        Four outcomes, as the source has them: the boarders are beaten, the defenders are
        beaten and the ship is taken, neither and both sides feed in more, or nobody met
        them at all and she is taken unopposed.

        Unopposed is not the same as winning. A ship with nobody left standing to meet a
        boarding party has already lost, and the fight that would have decided it does not
        need to be rolled.

    """
    across = frontage(overlap, shorter_length)
    fit = sum(division.fit for division in boarding)
    across = min(across, fit)
    if across <= 0:
        return MeleeResult(
            success=False,
            code=NOBODY_CROSSED,
            outcome=NOBODY_CROSSED,
        )

    met = min(can_reach(across), sum(division.fit for division in repelling))
    attack = party_strength(boarding, across)

    if met <= 0:
        return MeleeResult(
            success=True,
            outcome=UNOPPOSED,
            across=across,
            boarding_strength=attack,
            taken=True,
        )

    defence = party_strength(repelling, met)
    edge = attack / defence if defence > 0.0 else float("inf")

    if edge >= decisive:
        outcome, taken = DEFENDERS_BEATEN, True
    elif edge <= 1.0 / decisive:
        outcome, taken = BOARDERS_BEATEN, False
    else:
        outcome, taken = UNRESOLVED, False

    return MeleeResult(
        success=True,
        outcome=outcome,
        across=across,
        met=met,
        boarding_strength=attack,
        repelling_strength=defence,
        edge=edge,
        taken=taken,
    )


__all__ = (
    "MEN_PER_METRE",
    "ALONGSIDE_BONUS",
    "LYING_TOGETHER",
    "FEWEST_ACROSS",
    "DEFENDERS_PER_BOARDER",
    "DECISIVE",
    "BOARDERS_BEATEN",
    "DEFENDERS_BEATEN",
    "UNOPPOSED",
    "UNRESOLVED",
    "NOBODY_CROSSED",
    "MeleeResult",
    "frontage",
    "can_reach",
    "party_strength",
    "fight",
)
