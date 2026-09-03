"""
Putting her back together, and what a ship's own people cannot do.

A hit-point model repairs by topping a number back up, and the only question it can ask is
how long that takes. This one asks a better one: **what can be mended at sea, and what has
to wait for a yard?**

    at sea      hull, oars, and canvas - the carpenter's work, indefinitely
    at sea      a mast, after a fashion, and she is slower for ever until a yard sees her
    a yard      the mast properly, and the guns she has no spares for

**The jury rig is the whole item.** A ship that loses a mast and rigs a spar in its place is
sailing again within a day, and she is slower for the rest of the commission. That is a
*scar*: it does not tick down, it does not heal with time, and nothing aboard can lift it.
It gives a reason to make port that no repair-over-time system has, because the reason is
not that she is broken - she is working perfectly, and she is worse.

**Repairs compete for hands like everything else.** The carpenter's party is drawn from the
same people the guns, the pumps and the fire want, which is why the source says only three
things are possible in action: bailing, pumping, and replacing sail. Nothing here enforces
that with a flag. It falls out of there being one crew.

**And she mends faster doing nothing else.** A ship hove to with her canvas in works at
twice the rate of one carrying on, because everybody who is not steering is on the job.
That is a real decision on a passage with somewhere to be.

"""

from dataclasses import dataclass

from .damage import HULL, MAST_DOWN_AT, OARS, RIGGING, WEAPONS
from .results import Result
from .stations import CARPENTER

#: What a fully-manned carpenter's party mends in a day, as a fraction of one track.
#:
#: A third. Three days of steady work to put a badly knocked-about hull right, which is the
#: order of thing the period's logs describe and long enough that a captain feels it.
MENDED_PER_DAY = 0.34

#: Hands wanted to work at that rate.
HANDS_PER_PARTY = 20.0

#: The exponent that makes more hands help less, as with a fire party and the pumps.
DIMINISHING = 0.6

#: What she mends at, hove to with nothing else to do.
#:
#: Doubled, from the source. Everybody not steering is on the job, and choosing to stop is
#: the price - which is a decision worth having on a passage with somewhere to be.
DOING_NOTHING_ELSE = 2.0

#: The most way she can carry and still count as doing nothing else, in metres a second.
QUIET_ENOUGH = 0.5

#: How much of her rigging a ship's own people can put back after a mast has gone.
#:
#: Not all of it. A spar lashed where a mast stood carries sail and does not carry as much,
#: and no amount of further work at sea improves it - which is what makes it a scar rather
#: than a slow repair.
JURY_RIG_CEILING = 0.75

#: What a jury rig costs her, as a fraction of the canvas that would otherwise draw.
JURY_RIG_PENALTY = 0.2

#: Tracks her own people can work on at sea at all.
#:
#: Not weapons: a dismounted gun wants a new carriage or a new gun, and a ship carries
#: spares for neither unless she took them out of a prize.
AT_SEA = (HULL, RIGGING, OARS)

NOTHING_TO_MEND = "nothing_to_mend"
NO_HANDS = "no_hands"
NOT_AT_SEA = "not_at_sea"
NEEDS_A_YARD = "needs_a_yard"
NOT_JURY_RIGGED = "not_jury_rigged"


@dataclass(frozen=True, kw_only=True)
class RepairResult(Result):
    """
    What a spell of work put right.

    Attributes:
        mended (dict): Track name to how much of it was made good.
        rate (float): What she was working at, per day.
        doing_nothing_else (bool): Whether she was hove to for it.
        jury_rigged (bool): Whether she is now sailing under a jury rig.
        wants_a_yard (tuple): What her own people cannot finish.

    """

    mended: dict = None
    rate: float = 0.0
    doing_nothing_else: bool = False
    jury_rigged: bool = False
    wants_a_yard: tuple = ()


def party_rate(hands, per_party=HANDS_PER_PARTY, falloff=DIMINISHING):
    """
    How fast a carpenter's party of this size works.

    Args:
        hands (float): How many are on it.
        per_party (float, optional): Hands wanted to work at the full rate.
        falloff (float, optional): The exponent that makes more help less.

    Returns:
        rate (float): Fraction of a track per day.

    Notes:
        Diminishing, like a fire party and the pumps, and for the same reason: there is
        only so much room round a shot-hole, and the hands past that are hands the guns
        could have had.

    """
    hands = max(0.0, float(hands))
    if not hands or per_party <= 0.0:
        return 0.0
    return MENDED_PER_DAY * min(1.0, (hands / per_party) ** falloff)


def doing_nothing_else(speed, sail_area, limit=QUIET_ENOUGH):
    """
    Args:
        speed (float): Her speed through the water, in metres a second.
        sail_area (float): The fraction of her canvas that is set.
        limit (float, optional): The most way that still counts as stopped.

    Returns:
        quiet (bool): Whether everybody not steering is free for the work.

    """
    return abs(float(speed)) <= limit and float(sail_area) <= 0.0


def canvas_after_jury_rig(drawing, jury_rigged, penalty=JURY_RIG_PENALTY):
    """
    Args:
        drawing (float): What her canvas would otherwise pull, from `damage.canvas_drawing`.
        jury_rigged (bool): Whether a spar is standing where a mast stood.
        penalty (float, optional): What that costs her.

    Returns:
        drawing (float): What actually pulls.

    Notes:
        Multiplied into the same number the rigging damage feeds, so a jury-rigged ship is
        slower at every sail plan rather than capped at one - the same shape as being cut
        about aloft, and for the same reason: it is her rig that is worse, not her orders.

    """
    if not jury_rigged:
        return float(drawing)
    return max(0.0, float(drawing) * (1.0 - float(penalty)))


class Mends:
    """
    A hull her own people can work on, and a hull a yard has to finish.

    Notes:
        Nothing here happens on its own. Setting hands to repairs is an order, because the
        people doing it are people who were doing something else - and a contrib that
        quietly mended a ship while nobody was looking would be deciding for a captain what
        his crew were for.

    """

    def at_object_creation(self):
        """Set up this part of a newly created vessel."""
        super().at_object_creation()
        self.db.carpenters = 0.0
        self.db.jury_rigged = False

    @property
    def carpenters(self):
        """
        Returns:
            hands (float): How many are set to repairs.

        """
        return float(self.db.carpenters or 0.0)

    @property
    def jury_rigged(self):
        """
        Returns:
            rigged (bool): Whether a spar is standing where a mast stood.

        """
        return bool(self.db.jury_rigged)

    def set_carpenters(self, hands):
        """
        Put hands to work on her.

        Args:
            hands (float): How many. Zero calls them off.

        Returns:
            result (RepairResult): What that buys her, per day.

        """
        self.db.carpenters = max(0.0, float(hands))
        return self.repair_report()

    def wants_a_yard(self):
        """
        Returns:
            wants (tuple): What her own people cannot put right at sea.

        Notes:
            Weapons always, because she carries spares for neither a carriage nor a gun
            unless she took them out of a prize - and a jury rig, which is finished work
            that is permanently worse rather than unfinished work.

        """
        wanting = []
        if self.damage.of(WEAPONS) > 0.0:
            wanting.append(WEAPONS)
        if self.jury_rigged:
            wanting.append(RIGGING)
        return tuple(wanting)

    def repair_rate(self, quiet=None):
        """
        How fast the work is going.

        Args:
            quiet (bool, optional): Whether she is doing nothing else. Worked out if not
                given.

        Returns:
            rate (float): Fraction of a track per day.

        Notes:
            **Where the carpenter finally costs or saves something.** `competence_at` has
            existed since posts did and was read by nothing, which made the whole seam a
            claim rather than a rule - a game pointing `MARITIME_COMPETENCE_POLICY` at its
            own skill system got a number back and no consequence. A good carpenter getting
            more out of the same party is the plainest consequence there is.

        """
        if quiet is None:
            quiet = doing_nothing_else(self.speed, self.sail_plan.area)
        rate = party_rate(self.carpenters) * (DOING_NOTHING_ELSE if quiet else 1.0)
        return rate * self.competence_at(CARPENTER)

    def repair_report(self):
        """
        Returns:
            result (RepairResult): Where the work stands, without advancing it.

        """
        quiet = doing_nothing_else(self.speed, self.sail_plan.area)
        rate = self.repair_rate(quiet)
        return RepairResult(
            success=True,
            mended={},
            rate=rate,
            doing_nothing_else=quiet,
            jury_rigged=self.jury_rigged,
            wants_a_yard=self.wants_a_yard(),
        )

    def work_repairs(self, elapsed):
        """
        Let the carpenter's party work for a stretch of time.

        Args:
            elapsed (float): Game seconds.

        Returns:
            result (RepairResult or None): What they put right, or None if nobody is on it.

        Notes:
            **A mast is the one thing that comes back worse.** Her people can get a spar up
            where one went over the side, and she sails - but only to `JURY_RIG_CEILING`,
            and she is slower for ever after until a yard replaces it. Working longer does
            not help, which is what separates a scar from a slow repair.

        """
        if not self.carpenters:
            return None

        report = self.repair_report()
        if not report.rate:
            return None

        days = max(0.0, float(elapsed)) / 86400.0
        made_good = report.rate * days
        if not made_good:
            return None

        mended = {}
        for track in AT_SEA:
            hurt = self.damage.of(track)
            if hurt <= 0.0:
                continue

            wanted = min(hurt, made_good)
            if track == RIGGING:
                # A mast that has gone is not mended, it is replaced with something worse.
                # She may be worked back to the ceiling and no further, and she carries the
                # jury rig from then on.
                if hurt >= MAST_DOWN_AT:
                    self.db.jury_rigged = True
                floor = 1.0 - JURY_RIG_CEILING if self.jury_rigged else 0.0
                wanted = min(wanted, max(0.0, hurt - floor))

            if wanted > 0.0:
                self.repair(track, wanted)
                mended[track] = wanted

        if not mended:
            return None
        return RepairResult(
            success=True,
            mended=mended,
            rate=report.rate,
            doing_nothing_else=report.doing_nothing_else,
            jury_rigged=self.jury_rigged,
            wants_a_yard=self.wants_a_yard(),
        )

    def refit(self):
        """
        What a yard does that her own people cannot.

        Returns:
            result (RepairResult): What was put right.

        Notes:
            The other half of the tender ruling: routine work costs crew time and nothing
            else, and a yard costs money and days alongside. This is the *effect* of a
            refit; what it costs and how long she lies there is the game's, and is taken
            from her ledger rather than decided here.

            It is the only thing that lifts a jury rig, which is the whole reason a ship
            with one has somewhere she needs to be.

        """
        mended = {}
        for track in (HULL, RIGGING, OARS, WEAPONS):
            hurt = self.damage.of(track)
            if hurt > 0.0:
                self.repair(track, hurt)
                mended[track] = hurt
        self.db.jury_rigged = False
        return RepairResult(success=True, mended=mended, jury_rigged=False, wants_a_yard=())
