"""
Working cargo: getting it aboard, getting it ashore, and reading what is in her.

Named for the bill of lading rather than for the cargo, because `commands/cargo.py`
would shadow `maritime.cargo` from inside this package - which is exactly how the
first attempt at splitting these commands broke.

**Cargo only moves alongside.** Not a rule invented for balance: a ship at sea has no
quay to work from, and a system that let a hold be filled in mid-ocean would make the
whole of docking optional. The precondition is the same `held_by` the rest of the
system already uses, so lying to an anchor does not count either - an anchorage needs
lighters, and lighters are a later phase.

"""

from ..cargo import commodity_named
from ..messaging import DISCHARGE_ORDER, STOW_ORDER
from ..stowage import FULL, NO_HOLD, NOT_ABOARD, NOTHING_TO_MOVE
from .base import MaritimeCommand

# What `discharge all` means, in tonnes. Larger than any hull this system will carry,
# and finite so that it cannot become an infinity somewhere downstream.
EVERYTHING = 1e9

# Why nothing moved, in words. Keyed by the codes `stowage` returns, so a new refusal
# there is a missing entry here rather than a silent blank.
REFUSALS = {
    NO_HOLD: "She has no hold to put it in.",
    FULL: "She will not take another ton of it.",
    NOT_ABOARD: "There is none of that aboard.",
    NOTHING_TO_MOVE: "You will have to say how much.",
}


def _alongside(command, vessel):
    """
    Whether cargo can be worked at all.

    Args:
        command (MaritimeCommand): The command asking.
        vessel (Vessel): The hull.

    Returns:
        alongside (bool): True if she is made fast to a quay. Explains why not,
            to the caller, if she is not.

    """
    if vessel.held_by() == "docked":
        return True
    command.caller.msg(
        "Cargo is worked alongside. Take her into a berth and make fast before "
        "you open the hatches."
    )
    return False


def _parse(command, default_tonnes=None):
    """
    Read a tonnage and a commodity out of what was typed.

    Args:
        command (MaritimeCommand): The command asking.
        default_tonnes (float, optional): What to assume when no figure is given.

    Returns:
        parsed (tuple): `(tonnes, commodity)`, or `(None, None)` if it could not
            be read. Explains the problem to the caller either way.

    Notes:
        Accepts `100 salt`, `100 tons of salt` and - with a default - `salt` on
        its own. The units are swallowed rather than parsed, because there is
        exactly one unit and asking a player to omit the word they would
        naturally type is the sort of thing that makes a command feel like a form.

    """
    words = (command.args or "").split()
    filler = {"tons", "ton", "tonnes", "tonne", "of"}

    tonnes = default_tonnes
    if words and words[0].lower() in ("all", "everything"):
        tonnes, words = EVERYTHING, words[1:]
    else:
        try:
            tonnes = float(words[0])
            words = words[1:]
        except (IndexError, ValueError):
            pass

    name = " ".join(word for word in words if word.lower() not in filler)
    if tonnes is None or not name:
        command.caller.msg(f"Usage: {command.key} <tons> <cargo>")
        return None, None
    if tonnes <= 0.0:
        command.caller.msg("Nothing is not a quantity.")
        return None, None

    from .. import config

    commodity = commodity_named(name, config.commodities())
    if commodity is None:
        command.caller.msg(f"Nobody here trades in {name}.")
        return None, None
    return tonnes, commodity


class CmdStow(MaritimeCommand):
    """
    Load cargo into her holds.

    Usage:
      stow <tons> <cargo>

    Takes what will fit and leaves the rest on the quay, and says which of the two
    capacities stopped her. That distinction is the whole of cargo work: a ship
    that has weighed out is down on her marks and will take nothing further, while
    one that has cubed out has run out of space and would still carry something
    denser.

    Weight goes into the lowest hold with room in it, because weight stowed high
    makes her tender.
    """

    key = "stow"
    aliases = ("lade",)

    def at_helm(self, vessel):
        """Get it aboard, and say what it cost her in draught."""
        if not _alongside(self, vessel):
            return
        tonnes, commodity = _parse(self)
        if commodity is None:
            return

        self.order(vessel, STOW_ORDER, what=commodity.name, tonnes=tonnes)
        result = vessel.load(commodity, tonnes)
        if not result:
            self.aboard(vessel, REFUSALS.get(result.code, "It will not go aboard."))
            return
        for line in vessel.narrator.stowed(result, commodity):
            self.aboard(vessel, line)


class CmdDischarge(MaritimeCommand):
    """
    Put cargo ashore.

    Usage:
      discharge <tons> <cargo>
      discharge all <cargo>

    Worked from the highest hold down, which is the reverse of loading and what a
    mate would do anyway - taking the weight off the top keeps her stiff through
    the discharge rather than leaving her tender halfway.
    """

    key = "discharge"
    aliases = ("unload",)

    def at_helm(self, vessel):
        """Break it out and send it ashore."""
        if not _alongside(self, vessel):
            return
        tonnes, commodity = _parse(self)
        if commodity is None:
            return

        aboard = next(
            (parcel.tonnes for parcel in vessel.cargo if parcel.commodity.key == commodity.key),
            0.0,
        )
        self.order(vessel, DISCHARGE_ORDER, what=commodity.name, tonnes=min(tonnes, aboard))
        result = vessel.discharge(commodity, tonnes)
        if not result:
            self.aboard(vessel, REFUSALS.get(result.code, "None of it comes out."))
            return
        for line in vessel.narrator.discharged(result, commodity):
            self.aboard(vessel, line)


class CmdManifest(MaritimeCommand):
    """
    Read what is in her, and what it is doing to her.

    Usage:
      manifest

    The cargo list is the short half. What a master needs before he sails is how
    deep she is sitting, how much freeboard is left him, and whether the weight
    has been stowed too high.
    """

    key = "manifest"
    aliases = ("cargo", "lading")

    def at_helm(self, vessel):
        """Report the manifest and her condition together."""
        self.caller.msg(chr(10).join(vessel.narrator.manifest(vessel.stowage())))
