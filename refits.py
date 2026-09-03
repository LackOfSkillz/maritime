"""
What she is worth, and what a yard can make her into.

A hull bought new has a price - `shipyard` works it out from her burthen, which is how ships
were actually contracted. What this adds is the two things that happen afterwards: she is
worth less than that once somebody has shot at her, and she can be made into a different ship
by people with money and a dry dock.

**She is valued on what she is, not on what she was.** Her worth is computed from the
dimensions she has *now* and the condition she is in *now* - so a hull that has been
lengthened is worth more without anybody recording that she was lengthened, and a hull that
has been hammered is worth less without anybody writing down that she was in an action. Both
fall out of `burthen` and the damage tracks, which already know.

**A refit changes a fact, and every fact it changes is one something already reads.** No
refit here adds a number that nothing consumes. Coppering her makes her faster because
`motion_limits` is what the tick steers her by; lengthening her makes her carry more because
`capacity` is what `stowage` divides by, and it makes her turn worse in the same breath,
because a longer hull does. A refit that only made a line of text appear would be a cosmetic,
and cosmetics are a game's.

**This contrib does not hold a person's money.** A sale moves the hull and reports the price;
who pays whom is the game's, because a game knows whether its players have pockets. What
*is* here is the ship's own purse, which is what a refit is paid out of - a vessel earning
her keep pays for her own copper.

"""

from dataclasses import dataclass, replace

from .ledger import Coin
from .results import Result
from .shipyard import PER_TON_BURTHEN, burthen

#: What a hull fetches second-hand, against her cost new.
#:
#: Four fifths, before her condition is counted. A ship that has been to sea is a ship
#: somebody else has already had the good of, and the gap between new and nearly-new is
#: where a yard makes its living.
SECOND_HAND = 0.8

#: The least she is worth however badly she has been used.
#:
#: A tenth. Past that she is not a ship, she is timber and iron - and timber and iron are
#: still worth carting away, which is why this is not zero. A hull worth nothing at all
#: would let a game delete somebody's ship as an act of tidying.
BREAKING_UP = 0.1

#: What each named structural failure takes off what is left.
#:
#: A quarter for a mast over the side or a battery of dismounted guns, a twentieth for each
#: hole in her. A buyer sees the first from the quay and finds the second with a lantern.
FAILURE_COST = 0.75
HOLE_COST = 0.95

NO_SUCH_REFIT = "no_such_refit"
ALREADY_REFITTED = "already_refitted"
CANNOT_AFFORD = "cannot_afford"
NOT_HERS = "not_hers"


@dataclass(frozen=True, kw_only=True)
class ValueResult(Result):
    """
    What she would fetch.

    Attributes:
        value (Coin): What she is worth as she lies.
        new (Coin): What a hull of her tonnage costs new.
        condition (float): How much of her value her condition leaves her, 0 to 1.

    """

    value: Coin = None
    new: Coin = None
    condition: float = 1.0


@dataclass(frozen=True, kw_only=True)
class RefitResult(Result):
    """
    What a yard did to her.

    Attributes:
        refit (str): Which one.
        paid (Coin): What it cost.
        done (tuple): Every refit she now carries.

    """

    refit: str = ""
    paid: Coin = None
    done: tuple = ()


def condition_of(vessel):
    """
    How much of her value her state leaves her.

    Args:
        vessel (object): The hull.

    Returns:
        condition (float): From `BREAKING_UP` to 1.

    Notes:
        Read off the damage tracks and her holes, which already exist and already mean
        something. A second condition number kept beside them would drift from them, and the
        symptom would be a ship that looks sound in a survey and sinks on the way home.

    """
    from .damage import TRACKS, structural

    damage = getattr(vessel, "damage", None)
    if damage is None:
        return 1.0

    # Averaged across her tracks, because a surveyor walking a ship over prices all of her -
    # a sound hull with her rigging gone is worth more than a holed one with new spars, and
    # both are worth less than a ship that has never been fired at.
    hurt = sum(damage.of(track) for track in TRACKS) / len(TRACKS)
    sound = 1.0 - hurt

    # And the named failures cost her again on top. A mast over the side is not a number
    # going down, it is a thing a buyer sees from the quay before he comes aboard.
    sound *= FAILURE_COST ** len(structural(damage))
    sound *= HOLE_COST ** len(getattr(vessel, "breaches", ()))

    return max(BREAKING_UP, min(1.0, sound))


def market_value(vessel, per_ton=PER_TON_BURTHEN, second_hand=SECOND_HAND):
    """
    What she would fetch as she lies.

    Args:
        vessel (object): The hull.
        per_ton (int, optional): What a ton burthen costs, in the smallest coin.
        second_hand (float, optional): What a used hull fetches against a new one.

    Returns:
        result (ValueResult): Her worth, what she cost new, and her condition.

    Notes:
        **Computed from what she is now.** A hull that has been lengthened is worth more
        without anybody recording the refit, and one that has been hammered is worth less
        without anybody writing down the action - because her dimensions and her damage are
        already the truth about her.

    """
    tons = burthen(vessel.length, vessel.beam)
    new = Coin(smallest=int(round(tons * float(per_ton))))
    condition = condition_of(vessel)
    return ValueResult(
        success=True,
        value=Coin(smallest=int(round(new.smallest * second_hand * condition))),
        new=new,
        condition=condition,
    )


def copper_her(vessel):
    """
    Sheathe her bottom in copper.

    Args:
        vessel (object): The hull.

    Notes:
        The refit of the period, and it did two things: it kept the weed and the worm off,
        which is fouling this contrib does not model, and it made her faster, which is
        something the tick reads on every step. What is shipped is the half that is real
        here rather than a number standing in for the half that is not.

    """
    limits = vessel.motion_limits
    vessel.motion_limits = replace(limits, max_speed=limits.max_speed * 1.08)


def lengthen_her(vessel):
    """
    Cut her in half and put a new section in.

    Args:
        vessel (object): The hull.

    Notes:
        **The refit that shows how much of this model is derived.** She gets longer, and
        from that alone she carries more, rates higher, swings another boat and takes longer
        to come round - because every one of those was computed from her length and none of
        them is stored. The only thing written here is the length and the tonnage it buys.

    """
    vessel.length = vessel.length * 1.15
    capacity = vessel.capacity
    vessel.capacity = replace(
        capacity,
        displacement=capacity.displacement * 1.15,
        internal_volume=capacity.internal_volume * 1.15,
    )
    limits = vessel.motion_limits
    vessel.motion_limits = replace(limits, turn_rate=limits.turn_rate * 0.9)


def strengthen_her(vessel):
    """
    Double her frames and her topsides.

    Args:
        vessel (object): The hull.

    Notes:
        Heavier and slower, and she takes more hammering before it tells. The trade a
        merchantman working a dangerous coast actually made.

    """
    limits = vessel.motion_limits
    vessel.motion_limits = replace(limits, max_speed=limits.max_speed * 0.94)
    vessel.db.doubled = True


#: What a yard will do to her, and what each costs against her value new.
#:
#: Priced as a share of a new hull of her tonnage rather than as a flat sum, because
#: coppering a frigate is not the same job as coppering a yawl and a flat price would make
#: one of them absurd.
REFITS = {
    "copper": {
        "share": 0.12,
        "do": copper_her,
        "what": "Her bottom sheathed in copper. She is faster for it.",
    },
    "lengthen": {
        "share": 0.35,
        "do": lengthen_her,
        "what": "Cut in half and lengthened. She carries more and turns worse.",
    },
    "strengthen": {
        "share": 0.20,
        "do": strengthen_her,
        "what": "Frames doubled and topsides strengthened. Slower, and harder to hurt.",
    },
}


def cost_of_refit(vessel, refit, per_ton=PER_TON_BURTHEN):
    """
    What a yard wants for a refit on this hull.

    Args:
        vessel (object): The hull.
        refit (str): Which refit.
        per_ton (int, optional): What a ton burthen costs, in the smallest coin.

    Returns:
        cost (Coin or None): What it comes to, or None if there is no such refit.

    """
    work = REFITS.get(refit)
    if work is None:
        return None
    tons = burthen(vessel.length, vessel.beam)
    return Coin(smallest=int(round(tons * float(per_ton) * work["share"])))


class Refitted:
    """
    A hull a yard has had its hands on.

    Notes:
        What she has had done is kept, and only so that she cannot have it done twice.
        Everything a refit *did* lives where that kind of fact already lives - her length,
        her limits, her capacity - rather than being reconstructed from a list, because a
        list of refits that had to be replayed to know how fast she is would be a second
        source of truth about her speed.

    """

    def at_object_creation(self):
        """Set up this part of a newly created vessel."""
        super().at_object_creation()
        self.db.refits = []

    @property
    def refits(self):
        """
        Returns:
            done (tuple): What she has had done.

        """
        return tuple(self.db.refits or ())

    def what_she_is_worth(self):
        """
        Returns:
            result (ValueResult): What she would fetch as she lies.

        """
        return market_value(self)

    def take_in_hand(self, refit):
        """
        Send her in for structural work.

        Args:
            refit (str): Which one.

        Returns:
            result (RefitResult): What was done, or why it was not.

        Notes:
            Paid out of her own purse. A vessel earning her keep pays for her own copper,
            which is the loop `ledger`, `passengers` and `provisioning` are all feeding.

            Named `take_in_hand` and not `refit`, because `Mends.refit` already means the
            yard finishing what her own carpenter could not - and two mixins with the same
            public name do not raise, they silently displace one another. The guard in
            `test_mixins` is there because that has happened before.

        """
        work = REFITS.get(refit)
        if work is None:
            return RefitResult(success=False, code=NO_SUCH_REFIT, done=self.refits)
        if refit in self.refits:
            return RefitResult(success=False, code=ALREADY_REFITTED, done=self.refits)

        cost = cost_of_refit(self, refit)
        if not self.debit(cost, reason=f"refit: {refit}"):
            return RefitResult(success=False, code=CANNOT_AFFORD, done=self.refits)

        work["do"](self)
        self.db.refits = list(self.refits) + [refit]
        return RefitResult(success=True, refit=refit, paid=cost, done=self.refits)

    def sell(self, buyer, price=None):
        """
        Hand her to somebody else, and say what she went for.

        Args:
            buyer (object): Whoever is taking her.
            price (Coin, optional): What she went for. Her market value if not given.

        Returns:
            result (ValueResult): What she fetched.

        Notes:
            **The money does not move here.** This contrib has no people's pockets in it -
            it has a ship's purse, which is hers and goes with her. Who pays whom is a
            question about a game's economy, and the price is reported so the game can
            settle it.

        """
        from .ownership import SOLD

        worth = self.what_she_is_worth()
        asking = worth.value if price is None else price
        self.transfer_ownership(buyer, reason=SOLD)
        return replace(worth, value=asking)
