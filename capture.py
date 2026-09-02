"""
Taking a ship.

A prize is a hull somebody else built, crewed and paid for, and now answers to you. It is
the most valuable thing that can happen in a fight and it is deliberately the hardest, for
one reason: **if capture were the easier road nobody would ever fight to sink anything.**
Sinking a ship destroys the thing worth having. Taking her keeps it. So the price of taking
her has to be paid in the currency a fight is fought in - time, hands, and risk - or the
whole tactical triangle collapses into "board everything, always".

Hence four conditions, every one of them required, and no partial credit:

    1. She is grappled and held alongside
    2. She has struck
    3. Her deck has been carried
    4. Her captain is subdued or killed

They are not four ways of saying the same thing. A ship can be lashed to you with her
colours still up. She can strike and then have the surrender repudiated by a boarding party
that will not have it. Her deck can be carried while her captain fights on in the cabin, and
**a ship whose captain is still on her feet has not been taken however many people are
standing on her deck.** That fourth condition is what stops a capture being paperwork.

The four are checked *together, at one moment*, because three of them are momentary. Carrying
a deck is the outcome of one exchange, not a state a ship sits in; so is being held, once
lines start parting. Reading them at different times would let a capture be assembled out of
conditions that were never simultaneously true.

**What this module will not decide.** Whether a *player* captain is subdued. Resolving that
at ship scale would mean this contrib deciding when somebody's character is beaten, which is
the one thing it must never do - the same rule that keeps character combat, stamina and the
economy out. So the fourth condition goes through a seam. The default settles NPC captains
at ship scale, so that NPC ships can be taken at all, and answers *no* for anybody with an
account attached: a game that wants players' ships takeable points
`MARITIME_SUBDUED_POLICY` at its own function and decides in its own terms.

Answering no is the safe direction to be wrong in. A capture that does not happen is a fight
that continues; a capture that happens wrongly has taken something off a player that they did
not agree to lose.

"""

from dataclasses import dataclass

from .config import subdued_policy
from .ownership import CAPTURED
from .results import Result

# --- why a capture did not happen -------------------------------------------------------
#
# One code per condition, so a renderer can say which of the four is missing rather than
# "you cannot do that" - the commonest of these is genuinely useful advice.

NOT_HELD = "not_held"
NOT_STRUCK = "not_struck"
DECK_NOT_CARRIED = "deck_not_carried"
CAPTAIN_UNBEATEN = "captain_unbeaten"

NO_CAPTOR = "no_captor"
SAME_VESSEL = "same_vessel"
ALREADY_HERS = "already_hers"


@dataclass(frozen=True, kw_only=True)
class CaptureResult(Result):
    """
    Whether a hull changed hands, and which of the four conditions were true.

    Attributes:
        prize (object or None): The hull being taken.
        captor (object or None): The hull taking her.
        held (bool): Condition one - grappled and lashed alongside.
        struck (bool): Condition two - her colours are down.
        carried (bool): Condition three - her deck was carried this exchange.
        subdued (bool): Condition four - her captain is beaten or dead.
        former_owner (object or None): Who owned her before.
        owner (object or None): Who owns her now.
        former_captain (object or None): Who had her before.
        captain (object or None): Who has her now.

    Notes:
        **All four conditions are reported whether or not the capture succeeded.** A
        failure that says only the first thing it found wrong makes a player fix that
        and try again to be told about the second, which is three round trips to learn
        one sentence. `code` names the first missing condition for a caller that wants
        to branch; the four flags are there so a renderer can say the whole truth.

    """

    prize: object = None
    captor: object = None
    held: bool = False
    struck: bool = False
    carried: bool = False
    subdued: bool = False
    former_owner: object = None
    owner: object = None
    former_captain: object = None
    captain: object = None

    @property
    def conditions_met(self):
        """
        Returns:
            met (int): How many of the four hold. Four is a capture.

        """
        return sum((self.held, self.struck, self.carried, self.subdued))


def captain_subdued(captain, prize, captor):
    """
    The shipped answer to "is her captain beaten?".

    Args:
        captain (object or None): Whoever had her. None if nobody did.
        prize (object): The hull being taken.
        captor (object): The hull taking her.

    Returns:
        subdued (bool): Whether the fourth condition holds.

    Notes:
        Three cases, and only the middle one is interesting.

        **Nobody had her.** A ship with no captain has nobody to beat, so the condition
        is vacuously true. This is not a loophole: getting a deck carried and her colours
        down is still three conditions' worth of work, and a ship nobody commands is
        exactly the ship that should be easiest to take.

        **Somebody with an account had her.** Answer no, always, and let a game that
        wants otherwise replace this. Deciding here that a player is beaten would be this
        contrib reaching into a character system it does not own, and reaching into it to
        take away a possession, which is the worst version of that mistake.

        **An NPC had her.** Resolved at ship scale: her captain went down with the deck.
        Anything finer would need a character-scale fight this contrib has no business
        simulating, and without this NPC ships could never be taken at all, which would
        leave capture built and unreachable.

    """
    if captain is None:
        return True
    if getattr(captain, "has_account", False):
        return False
    return True


def _held_alongside(prize, captor):
    """
    Condition one, from the grapples rather than from a flag.

    Args:
        prize (object): The hull being taken.
        captor (object): The hull taking her.

    Returns:
        held (bool): Whether the two are fast to each other.

    Notes:
        Asks both hulls, because grappling maintains the reference on both sides and a
        one-sided check would let a stale attribute on either of them stand in for
        contact that has since been cut.

    """
    return getattr(prize, "grappled_to", None) is captor and (
        getattr(captor, "grappled_to", None) is prize
    )


def may_be_taken(prize, captor, carried):
    """
    Test the four conditions without acting on them.

    Args:
        prize (object): The hull being taken.
        captor (object): The hull taking her.
        carried (bool): Whether her deck was carried in the exchange just fought.

    Returns:
        result (CaptureResult): Successful when all four hold. Nothing is moved either
            way - this only answers the question.

    Notes:
        Separate from `take` so that a command can tell somebody what is still wanted
        without half-performing a capture to find out.

    """
    if captor is None or prize is None:
        return CaptureResult(success=False, code=NO_CAPTOR, prize=prize, captor=captor)
    if prize is captor:
        return CaptureResult(success=False, code=SAME_VESSEL, prize=prize, captor=captor)

    held = _held_alongside(prize, captor)
    struck = getattr(prize, "struck_to", None) is captor
    carried = bool(carried)
    subdued = bool(subdued_policy()(getattr(prize, "captain", None), prize, captor))

    # First missing condition in the order they are listed, so the code and the prose a
    # renderer builds from it agree about which one to mention first.
    code = None
    for holds, why in (
        (held, NOT_HELD),
        (struck, NOT_STRUCK),
        (carried, DECK_NOT_CARRIED),
        (subdued, CAPTAIN_UNBEATEN),
    ):
        if not holds:
            code = why
            break

    return CaptureResult(
        success=code is None,
        code=code,
        prize=prize,
        captor=captor,
        held=held,
        struck=struck,
        carried=carried,
        subdued=subdued,
    )


def take(prize, captor, carried):
    """
    Take her, if all four conditions hold.

    Args:
        prize (object): The hull being taken.
        captor (object): The hull taking her.
        carried (bool): Whether her deck was carried in the exchange just fought.

    Returns:
        result (CaptureResult): Successful only if she changed hands, carrying both ends
            of both transfers.

    Notes:
        **She passes to the captor's owner**, a person rather than a side, because "side"
        is a concept this contrib does not have and the host game does. A game with
        nations, crews or companies listens for the event and does its own bookkeeping.

        **Command is vacated, not handed across.** The obvious reading of "command passes
        with her" is that the captor's captain takes her, and it is wrong: one ship per
        captain is a rule this contrib already keeps, because a man cannot be on two
        decks, so handing him the prize makes him *abandon the ship he just won her with*.
        A test caught exactly that.

        So a prize arrives with nobody commanding her, which is also what actually
        happened at sea - you put a **prize master** aboard out of your own people. That
        is `pass_command`, it already exists, and appointing one is the owner's decision
        rather than something a capture should make for him. It is the same division the
        fleet already draws: an admiral holds hulls and appoints captains to them.

        **No money changes hands, here or ever.** What a prize is worth is the host
        game's economy. The event carries enough for a game to price her.

        Striking is not undone. That she struck is a matter of history, and a prize
        rehoisting her own colours the moment she is taken would erase the fact that she
        was beaten.

    """
    result = may_be_taken(prize, captor, carried)
    if not result:
        return result

    former_owner = getattr(prize, "owner", None)
    former_captain = getattr(prize, "captain", None)
    owner = getattr(captor, "owner", None)

    if former_owner is owner and former_captain is None:
        # She is already theirs on both counts. Recapturing your own prize is not a
        # capture, and publishing one would have a game paying out twice.
        return CaptureResult(
            success=False,
            code=ALREADY_HERS,
            prize=prize,
            captor=captor,
            held=result.held,
            struck=result.struck,
            carried=result.carried,
            subdued=result.subdued,
            former_owner=former_owner,
            owner=former_owner,
            former_captain=former_captain,
            captain=former_captain,
        )

    prize.transfer_ownership(owner, reason=CAPTURED)

    # Through `pass_command` rather than by setting `db.captain`, because command is held
    # on both sides: her beaten captain carries a reference back to her, and writing only
    # this end would leave him still holding the ship that was taken off him - and still
    # able to give her orders.
    prize.pass_command(None)

    return CaptureResult(
        success=True,
        code=CAPTURED,
        prize=prize,
        captor=captor,
        held=True,
        struck=True,
        carried=True,
        subdued=True,
        former_owner=former_owner,
        owner=owner,
        former_captain=former_captain,
        captain=None,
    )
