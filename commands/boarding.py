"""
Getting the irons across, cutting them, and striking.

Three verbs and no fourth. Crossing to a boarded ship is *walking* - the grapples are two
ordinary exits, so `board` is not a command at all, it is the exit's name. That is Law 7
doing what it was put there for: nobody had to design a second kind of movement for a
hostile one.

What happens once the parties meet is the host game's own. This contrib holds two hulls
together and gets out of the way.

"""

from ..boarding import (
    ALREADY_GRAPPLED,
    CLOSING_TOO_FAST,
    NO_DECK,
    NOT_GRAPPLED,
    SAME_VESSEL,
    TOO_FAR,
    bears_alongside,
)
from ..formatting import format_range, format_speed
from ..messaging import CUT_GRAPPLES, GRAPPLE_ORDER, STRIKE_ORDER
from ..observation import IDENTIFIED
from .base import MaritimeCommand

#: Why the irons did not go across, in words. Keyed by the codes `boarding` returns, so
#: a new refusal there is a missing entry here rather than a silent blank.
REFUSALS = {
    TOO_FAR: "She is {distance} off. Nothing will carry that far - close her.",
    CLOSING_TOO_FAST: (
        "She is going by at {closure}. Match her course and speed or the irons "
        "will come straight out of the rail."
    ),
    NO_DECK: "There is no open deck on one of you to throw to.",
    ALREADY_GRAPPLED: "One of you is already fast to somebody.",
    SAME_VESSEL: "You cannot board your own ship.",
}


def _identified(command, vessel, name):
    """
    Find a named hull among the ones the lookout has actually made out.

    Args:
        command (MaritimeCommand): The command asking.
        vessel (Vessel): The hull looking.
        name (str): What was typed.

    Returns:
        target (Vessel or None): The hull, or None. Explains why not, if not.

    Notes:
        Identified contacts only, exactly as gunnery insists. You cannot throw an
        iron onto a shape you have not made out, and being able to name her is
        what proves you have.

    """
    wanted = (name or "").strip().lower()
    if not wanted:
        command.caller.msg(f"Usage: {command.key} <ship>")
        return None

    for sighting in vessel.contacts():
        if sighting.level != IDENTIFIED:
            continue
        if wanted in sighting.target.key.lower():
            return sighting.target

    command.caller.msg("No ship of that name is near enough to make out.")
    return None


class CmdGrapple(MaritimeCommand):
    """
    Throw the irons and lash her alongside.

    Usage:
      grapple <ship>

    What decides this is not her speed and not yours - it is how fast the two of
    you are moving relative to one another. Two ships running side by side at ten
    knots on the same course are motionless with respect to each other and can be
    lashed together at leisure. The same two on opposing courses will tear the
    irons out of the rail.

    Matching her course and speed is the manoeuvre.

    Once she is fast, the grapples are an ordinary exit. Walk across them.
    """

    key = "grapple"
    aliases = ("throw irons", "board")

    def at_helm(self, vessel):
        """Put the irons across, if she will take them."""
        target = _identified(self, vessel, self.args)
        if target is None:
            return

        self.order(vessel, GRAPPLE_ORDER, name=target.key)
        result = vessel.grapple(target)
        if not result:
            refusal = REFUSALS.get(result.code, "The irons will not go across.")
            self.caller.msg(
                refusal.format(
                    distance=format_range(result.distance),
                    closure=format_speed(result.closure),
                )
            )
            return

        for line in vessel.narrator.grappled(result, target):
            self.aboard(vessel, line)

        here = vessel.maritime_position
        if here is not None and not bears_alongside(vessel.heading, here, target.maritime_position):
            self.caller.msg(
                "She is nearly end-on to you. The lines will hold, but there is not "
                "much rail to cross by."
            )


class CmdCutGrapples(MaritimeCommand):
    """
    Cut the lines and let her go.

    Usage:
      cut grapples

    Takes the crossing away with them, from both ships at once. Anybody standing
    on the wrong deck when the lines are cut stays there.
    """

    key = "cut grapples"
    aliases = ("unhook", "cut lines")

    def at_helm(self, vessel):
        """Cut them, if there is anything to cut."""
        if not vessel.grappled:
            self.caller.msg("She is not fast to anything.")
            return

        other = vessel.grappled_to
        self.order(vessel, CUT_GRAPPLES, name=other.key)
        vessel.cast_off_grapples()
        for line in vessel.narrator.grapples_cut(other):
            self.aboard(vessel, line)


class CmdStrike(MaritimeCommand):
    """
    Strike your colours.

    Usage:
      strike

    Surrender to whatever is fast alongside. This records that she has struck and
    nothing more: what a captor may then do with her - who may give her orders,
    who owns her - is a question about authority this contrib deliberately does
    not answer.

    Colours can be rehoisted. A prize crew can be overwhelmed.
    """

    key = "strike"
    aliases = ("strike colours", "surrender")

    def at_helm(self, vessel):
        """Strike, or take it back."""
        if vessel.struck:
            captor = vessel.struck_to
            vessel.rehoist()
            self.aboard(vessel, vessel.narrator.rehoisted(captor))
            return

        other = vessel.grappled_to
        if other is None:
            self.caller.msg("There is nobody alongside to strike to.")
            return

        self.order(vessel, STRIKE_ORDER, name=other.key)
        vessel.strike(other)
        for line in vessel.narrator.struck_colours(other):
            self.aboard(vessel, line)


class CmdGrapples(MaritimeCommand):
    """
    Report what she is fast to, and how well.

    Usage:
      grapples

    The number that matters is the relative speed, because that is what the lines
    are taking. A pair of hulls matched to a tenth of a knot will hold all day;
    one sheering off will break free.
    """

    key = "grapples"
    aliases = ("irons",)

    def at_helm(self, vessel):
        """Report the lines."""
        if not vessel.grappled:
            self.caller.msg("She is not fast to anything.")
            return
        self.caller.msg(chr(10).join(vessel.narrator.grapple_report(vessel)))


__all__ = ("CmdGrapple", "CmdCutGrapples", "CmdStrike", "CmdGrapples", "NOT_GRAPPLED")
