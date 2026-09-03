"""
One hull dragging another.

Deferred here from wrecks, where it was first wanted, because a tug and a tow are the same
manoeuvre as a prize being brought in and a dismasted ship being got off a lee shore - and
building it three times would have produced three answers.

**The tow does not steer.** She goes where the towing hull goes, at the towing hull's speed,
and that is the whole of the arrangement. A tow that kept her own helm would be two ships
negotiating over one position, and a tow that were merely teleported to the tug would pass
through the ground between them. She is *placed* astern of the tug on the tug's own heading,
every step, which is where a tow actually is.

**What a tug can drag is a question about mass, not about size.** A big hull with no way on
her is a big hull; a small one deeply laden is worse than a large one light. `displacement`
and the manifest already know this, so the limit falls out of them rather than out of a table
of who may tow whom.

**A tow slows the tug and it is not free.** Doubling what she is dragging does not halve her
speed - a hull already moving takes surprisingly little to keep moving - but it costs, and it
costs more the heavier the tow. That is what makes bringing a prize in a decision rather than
a formality: a squadron towing two captures makes four knots and is caught by anything.

"""

from dataclasses import dataclass

from .results import Result

#: How far astern a tow rides, as a share of the towing hull's length.
#:
#: A length and a half of scope, which is short for a real tow and right for a game: long
#: enough that they are plainly two ships and short enough that the tow does not appear in a
#: different room from the tug.
SCOPE = 1.5

#: How much of her own way a tug keeps when dragging her own mass again.
#:
#: Two thirds. A hull under way takes far less to keep moving than to start, which is why
#: this is not a half - but a tug towing something as heavy as herself is plainly working,
#: and anything faster would make bringing a prize in free.
TOWING_AT_PARITY = 0.66

#: The most a tug will take on, as a multiple of her own displacement.
#:
#: Three. Past that she has the power to move it and not the power to stop it or turn it,
#: which is the thing that actually kills a tow - and a limit somewhere is better than a
#: launch dragging a first rate at a knot and a half.
MOST_SHE_WILL_TAKE = 3.0

NOT_A_HULL = "not_a_hull"
TOO_HEAVY = "too_heavy"
ALREADY_TOWING = "already_towing"
ALREADY_TOWED = "already_towed"
NOT_TOWING = "not_towing"
HERSELF = "herself"
NOWHERE = "nowhere"


@dataclass(frozen=True, kw_only=True)
class TowResult(Result):
    """
    What came of taking one in tow.

    Attributes:
        tow (object): What is being dragged.
        tug (object): What is dragging it.
        burden (float): How heavy the tow is, as a multiple of the tug.
        speed (float): What the tug can make with it, in metres a second.

    """

    tow: object = None
    tug: object = None
    burden: float = 0.0
    speed: float = 0.0


def all_up_weight(vessel):
    """
    What a hull weighs as she floats now.

    Args:
        vessel (object): The hull.

    Returns:
        kilograms (float): Her displacement plus what is in her.

    Notes:
        Her manifest counts, which is the thing that makes a tow interesting. A laden prize
        is a worse tow than the same ship light, and the way to make her towable is to start
        throwing cargo over the side - which is a decision, and a bitter one.

    """
    hull = float(getattr(getattr(vessel, "capacity", None), "displacement", 0.0))
    from .cargo import total_mass

    return hull + total_mass(getattr(vessel, "cargo", ()))


def burden_of(tug, tow):
    """
    How heavy a tow is, measured against the hull dragging it.

    Args:
        tug (object): The towing hull.
        tow (object): What is being dragged.

    Returns:
        burden (float): A multiple of the tug's own weight.

    """
    towing = all_up_weight(tug)
    if towing <= 0.0:
        return float("inf")
    return all_up_weight(tow) / towing


def towing_speed(clear_speed, burden, at_parity=TOWING_AT_PARITY):
    """
    What a tug makes with something behind her.

    Args:
        clear_speed (float): What she makes with nothing, in metres a second.
        burden (float): How heavy the tow is, as a multiple of her own weight.
        at_parity (float, optional): What she keeps towing her own weight again.

    Returns:
        speed (float): What she makes with it.

    Notes:
        **Not proportional, and deliberately.** A hull already moving takes little to keep
        moving, so halving her speed for every hull's weight added would make a tow
        impossible rather than expensive. What is wanted is a cost that is felt at the first
        tow and not fatal at the second, and a curve that falls away is that.

    """
    burden = max(0.0, float(burden))
    if burden <= 0.0:
        return float(clear_speed)
    return float(clear_speed) * at_parity**burden


class Tows:
    """
    A hull that can take another in tow, or be taken.

    Notes:
        Both ends on one mixin, because a tug and a tow are the same relationship seen from
        the two ends and putting them on separate mixins would let a hull be a tug that
        cannot be told she is also being towed.

    """

    def at_object_creation(self):
        """Set up this part of a newly created vessel."""
        super().at_object_creation()
        self.db.tow = None
        self.db.tug = None

    @property
    def tow(self):
        """
        Returns:
            tow (object or None): What she is dragging.

        """
        return self.db.tow

    @property
    def tug(self):
        """
        Returns:
            tug (object or None): What is dragging her.

        """
        return self.db.tug

    @property
    def under_tow(self):
        """
        Returns:
            towed (bool): Whether somebody else has her.

        """
        return self.tug is not None

    def take_in_tow(self, other):
        """
        Get a line aboard her and start dragging.

        Args:
            other (object): The hull to tow.

        Returns:
            result (TowResult): What she has taken on, or why she cannot.

        """
        if other is self:
            return TowResult(success=False, code=HERSELF)
        if not hasattr(other, "maritime_position"):
            return TowResult(success=False, code=NOT_A_HULL)
        if self.tow is not None:
            return TowResult(success=False, code=ALREADY_TOWING, tow=self.tow)
        if getattr(other, "tug", None) is not None:
            return TowResult(success=False, code=ALREADY_TOWED, tow=other)

        burden = burden_of(self, other)
        if burden > MOST_SHE_WILL_TAKE:
            return TowResult(success=False, code=TOO_HEAVY, tow=other, burden=burden)

        self.db.tow = other
        other.db.tug = self
        # Asked *after* the line is aboard, because `working_limits` already drags the tow
        # through `dragging` - working it out here as well would charge her for it twice.
        return TowResult(
            success=True,
            tow=other,
            tug=self,
            burden=burden,
            speed=self.working_limits.max_speed,
        )

    def slip_the_tow(self):
        """
        Let her go.

        Returns:
            result (TowResult): What was cast off, or a failure if she had nothing.

        Notes:
            Deliberately not conditional on anything. A tow is slipped in a hurry - the
            weather has come on, an enemy is in sight, or she is dragging her tug onto a
            lee shore - and a game that made it a check would be making the wrong thing
            difficult.

        """
        towed = self.tow
        if towed is None:
            return TowResult(success=False, code=NOT_TOWING)
        self.db.tow = None
        if getattr(towed, "tug", None) is self:
            towed.db.tug = None
        return TowResult(success=True, tow=towed, tug=self)

    def dragging(self, clear_speed):
        """
        What she can make with whatever is on the line.

        Args:
            clear_speed (float): What she would make with nothing, in metres a second.

        Returns:
            speed (float): What she makes as she is.

        Notes:
            Read by `working_limits`, which is what the tick steers her by - so a tow is a
            cost she actually pays rather than a number in a report. Takes the clear speed
            rather than fetching it, because `working_limits` is the thing computing it and
            asking it back for the answer it is halfway through would recurse.

        """
        if self.tow is None:
            return float(clear_speed)
        return towing_speed(clear_speed, burden_of(self, self.tow))

    def drag_the_tow(self):
        """
        Put the tow where a tow is: astern of the tug, on the tug's heading.

        Returns:
            moved (bool): Whether anything was dragged.

        Notes:
            **Placed rather than steered, and placed rather than teleported.** She has no
            helm of her own while she is on the line, and a tow that were simply set at the
            tug's own position would be inside her. Astern on the reciprocal of the tug's
            heading is where a tow actually rides, and it costs one call to work out.

            Called from the tick after the tug has moved, so a tow follows the step the tug
            took rather than the one before it.

        """
        towed = self.tow
        if towed is None:
            return False

        here = self.maritime_position
        if here is None or not towed.pk:
            return False

        astern = (self.heading + 180.0) % 360.0
        towed.maritime_position = here.moved(astern, self.length * SCOPE)
        towed.heading = self.heading
        towed.speed = self.speed
        return True
