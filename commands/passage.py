"""
Telling the sailing master where she is bound.

    ports                what harbours she could make for, and which she cannot
    make for <port>      lay the course, hand him the con, and go alongside at the end

**This is `plot`, `follow` and `dock` in one order, and that is exactly what it is for.**
A captain can do all three by hand and should be able to; the point of this one is that it
is a single decision - *take her to Longhope* - which is how a decision of that size is
actually made, and which is what a chart with harbours drawn on it invites somebody to
click.

**It refuses when she cannot get there, and says which of the reasons it is.** There are
only four - no channel marked, no safe water between, no berth she fits, she is not afloat
- and telling somebody which one they have hit is the difference between a command that
seems broken and one that has told them something about the world.

**The pond is not on the list.** Not because it is small or fresh or shallow, but because
no channel is marked into it. See `passage`, and `routes` before that: what a ship can
reach is a thing a world states, not a thing an algorithm finds.
"""

from evennia.commands.cmdset import CmdSet

from .. import passage
from ..formatting import format_range
from .base import MaritimeCommand

#: How far a port may be and still be listed, in metres.
#:
#: Two hundred kilometres, which on this scale is a week's sailing and several coasts. The
#: list is of places she could be *told* to go, and a harbour she cannot reach is still
#: worth seeing on it with the reason attached - "no safe water laid between here and
#: there" is knowledge, and a harbour silently absent is not.
LISTING_RANGE = 200000.0


class CmdPorts(MaritimeCommand):
    """
    What harbours she could be told to make for.

    Usage:
      ports

    Lists every quay within reach of this coast, how far off it is, and - for the ones she
    cannot make - why not. A harbour with no channel marked into it is one no course can be
    laid to, however much water there is in it.

    """

    key = "ports"
    aliases = ("harbours", "harbors")

    def at_helm(self, vessel):
        """
        Args:
            vessel (Vessel): The hull the caller is aboard.

        """
        here = vessel.maritime_position
        if here is None:
            self.caller.msg("She is not afloat.")
            return

        found = [
            port
            for port in passage.ports_afloat()
            if port.maritime_position.region == here.region
            and here.horizontal_distance_to(port.maritime_position) <= LISTING_RANGE
        ]
        if not found:
            self.caller.msg("There is no harbour within reach of these waters.")
            return

        lines = ["Harbours she could be told to make for:"]
        for port in sorted(
            found, key=lambda one: here.horizontal_distance_to(one.maritime_position)
        ):
            off = format_range(here.horizontal_distance_to(port.maritime_position))
            can = passage.can_reach(vessel, port)
            if can:
                lines.append(f"  |w{port.key:<22}|n {off:>10}   |xby {len(can.route)} marks|n")
            else:
                lines.append(f"  |x{port.key:<22}  {off:>10}   {can.said}|n")
        lines.append("|wmake for <harbour>|n hands the course to the sailing master.")
        self.caller.msg(chr(10).join(lines))


class CmdMakeFor(MaritimeCommand):
    """
    Order a passage to a harbour, and to lie alongside at the end of it.

    Usage:
      make for <harbour>

    Lays the course by way of the marked channels, hands the con to the sailing master, and
    gives him the one standing order he takes: to warp her in when she arrives. He steers,
    carries what the wind allows, gives the marked dangers their berth, and takes the way
    off her coming up to the quay.

    |wbelay|n takes the con back at any point. She keeps the course; you keep the helm.

    """

    key = "make for"
    aliases = ("sail to", "navigate to", "set course for")

    def at_helm(self, vessel):
        """
        Args:
            vessel (Vessel): The hull the caller is aboard.

        """
        wanted = self.args.strip()
        if not wanted:
            self.caller.msg("Make for where? |wports|n lists them.")
            return

        port = self.harbour_called(wanted, vessel)
        if port is None:
            return

        ordered = passage.make_for(vessel, port)
        if not ordered:
            self.caller.msg(f"She cannot be sent to {port.key}: {ordered.said}.")
            return

        self.caller.msg(f'You say, "Sailing master - make for {port.key}, and lay her alongside."')
        self.announce(f"{self.caller.key} orders a passage to {port.key}.")
        self.aboard(
            vessel,
            f'The sailing master answers, "{port.key} it is, sir - '
            f'{format_range(ordered.route.distance)} by {len(ordered.route)} marks."',
        )
        if vessel.anchored:
            # Said here as well as when it happens, so the captain knows before the capstan
            # turns that weighing is part of what he has just agreed to.
            self.caller.msg("|xHe will weigh and make sail himself.|n")

    def harbour_called(self, wanted, vessel):
        """
        Args:
            wanted (str): What the captain called it.
            vessel (Vessel): The hull, so the answer can be about her waters.

        Returns:
            port (PortRoom or None): The one harbour meant, or None if it was said.

        Notes:
            Matched on a prefix and then on exactly one answer, because "make for long"
            should reach Longhope and must not silently pick between Longhope and Long
            Reach. A name that fits two harbours is a name that has not been said yet.

        """
        here = vessel.maritime_position
        said = wanted.lower()
        found = [
            port
            for port in passage.ports_afloat()
            if port.maritime_position.region == here.region and port.key.lower().startswith(said)
        ]
        if not found:
            self.caller.msg(f"No harbour called '{wanted}'. |wports|n lists them.")
            return None
        if len(found) > 1:
            names = ", ".join(port.key for port in found)
            self.caller.msg(f"Which of them - {names}?")
            return None
        return found[0]


class PassageCmdSet(CmdSet):
    """
    Ordering a passage, for a ship's own compartments.

    Notes:
        On a `ShipRoom` with the rest of the helm commands, because ordering a passage is
        an order and an order wants a deck under it. Added to `HelmCmdSet` rather than
        installed separately; this set exists so a game that wants the rest of the helm
        without this can leave it out.

    """

    key = "maritime_passage"

    def at_cmdset_creation(self):
        """Populate the set."""
        self.add(CmdPorts())
        self.add(CmdMakeFor())


__all__ = ("LISTING_RANGE", "CmdPorts", "CmdMakeFor", "PassageCmdSet")
