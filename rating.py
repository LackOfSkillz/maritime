"""
What size of ship she is, worked out rather than declared.

A career runs from a pulled boat to something with a quarterdeck, and every game that has
one needs to know where on that ladder a given hull sits. The temptation is to write it on
her: a field saying `rating = "sloop"`, set by whoever built her.

**Derived, because a builder should not be able to lie.** Her length and her beam are known,
the period's own tonnage rule turns them into burthen, and burthen is what a ship *is*. So a
builder who draws a bigger hull gets a bigger rating without remembering to say so, and
cannot make a great ship that claims to be a dinghy - which is the same argument that has
`rank_of` reading a fleet rather than a title.

**Burthen and not length.** A long narrow hull and a short beamy one are different ships and
the same length; tons burthen is the measure that knows it, and it is the measure the age
actually used when it said how big a ship was.

**What this is for, and what it is not.** It answers *how big*. Whether a particular person
may command her is a question about that person, and it goes through
`MARITIME_COMMAND_POLICY` like every other question about authority - a game with a career
ladder checks the rating there and this stays out of it.

"""

from dataclasses import dataclass

#: The ladder, smallest first.
BOAT = "boat"
CRAFT = "craft"
COASTER = "coaster"
SHIP = "ship"
GREAT_SHIP = "great ship"

RATINGS = (BOAT, CRAFT, COASTER, SHIP, GREAT_SHIP)


@dataclass(frozen=True)
class Rating:
    """
    One rung of the ladder.

    Attributes:
        key (str): What it is called.
        upto (float): The most tons burthen that still counts as this, or `inf`.
        what (str): What a hull of this size is for.

    """

    key: str
    upto: float
    what: str


#: Where each rung ends, in tons burthen.
#:
#: Calibrated against the hulls this contrib ships rather than chosen and then made to fit:
#: the yawl comes out a boat at about fifteen tons, the cutter a craft, the two mid-sized
#: hulls coasters and ships, and the largest two great ships at six hundred and a thousand.
#: A ladder whose rungs no shipped hull lands on is a ladder nobody is climbing.
LADDER = (
    Rating(BOAT, 25.0, "pulled or under one sail, and no business out of sight of land"),
    Rating(CRAFT, 100.0, "decked and handy, and safe enough along a coast"),
    Rating(COASTER, 200.0, "a small trader, and as much ship as one person can hold in mind"),
    Rating(SHIP, 500.0, "ocean-going, and wants a proper company to work her"),
    Rating(GREAT_SHIP, float("inf"), "the largest thing afloat, and a command in its own right"),
)


def burthen_of(length, beam):
    """
    Her tons burthen, by the period's own rule.

    Args:
        length (float): Length on deck, in metres.
        beam (float): Extreme breadth, in metres.

    Returns:
        tons (float): Tons burthen.

    Notes:
        Taken from `shipyard.burthen` rather than restated, so a hull cannot measure one
        size when she is built and another when she is rated.

    """
    from .shipyard import burthen

    return burthen(float(length), float(beam))


def rating_for(tons):
    """
    Args:
        tons (float): Tons burthen.

    Returns:
        rating (Rating): Which rung she sits on.

    """
    for rung in LADDER:
        if float(tons) <= rung.upto:
            return rung
    return LADDER[-1]


def rating_of(length, beam):
    """
    Args:
        length (float): Length on deck, in metres.
        beam (float): Extreme breadth, in metres.

    Returns:
        rating (Rating): What size of ship that is.

    """
    return rating_for(burthen_of(length, beam))


def bigger_than(one, other):
    """
    Args:
        one (Rating or str): A rating.
        other (Rating or str): Another.

    Returns:
        bigger (bool): Whether the first outranks the second.

    Notes:
        By position on the ladder rather than by tonnage, so a game asking "may he command
        anything above a coaster?" gets an answer about rungs and not about a boundary case
        two tons either side of one.

    """
    keys = [rung.key for rung in LADDER]
    first = one.key if isinstance(one, Rating) else one
    second = other.key if isinstance(other, Rating) else other
    return keys.index(first) > keys.index(second)


class Rated:
    """
    A hull that knows what size of ship she is.

    Notes:
        Read every time rather than stored. A hull whose rating was written down at build
        time would keep it after a refit that lengthened her, and the whole point of
        deriving it is that it cannot fall out of step with the ship.

    """

    @property
    def burthen(self):
        """
        Returns:
            tons (float): Her tons burthen.

        """
        return burthen_of(self.length, self.beam)

    @property
    def rating(self):
        """
        Returns:
            rating (Rating): What size of ship she is.

        """
        return rating_for(self.burthen)
