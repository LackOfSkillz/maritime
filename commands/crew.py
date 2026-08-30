"""
Asking after the ship's company.

One command, and it reports rather than orders. What a captain does about a crew who
have been driven past bearing is give different orders elsewhere - ease the stroke,
strike the colours, find them a captain - and there is nothing to type here that would
make unhappy men happy.

"""

from .base import MaritimeCommand


class CmdCrew(MaritimeCommand):
    """
    Ask after the ship's company.

    Usage:
      crew

    How many of them are still standing, what they are rated, how they are bearing
    it, and - if there is anything - what they hold against you. That last part is
    the one worth reading. Every grievance on that list is something command did,
    and a crew who hold two of them are a crew who have started agreeing with each
    other.
    """

    key = "crew"
    aliases = ("company", "muster")

    def at_helm(self, vessel):
        """Report her people."""
        self.caller.msg(chr(10).join(vessel.narrator.crew_report(vessel)))
