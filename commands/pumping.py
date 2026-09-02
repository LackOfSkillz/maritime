"""
Making water: seeing how much, and fighting it.

"""

from ..flooding import FOUNDERS_AT, pump_rate, time_to_founder
from .base import MaritimeCommand


def _how_long(seconds):
    """
    Args:
        seconds (float): Until she founders.

    Returns:
        told (str): How long that is, in words a captain would use.

    """
    if seconds == float("inf"):
        return "she is holding it"
    if seconds < 300.0:
        return "minutes"
    if seconds < 3600.0:
        return f"about {seconds / 60.0:.0f} minutes"
    return f"about {seconds / 3600.0:.1f} hours"


class CmdPumps(MaritimeCommand):
    """
    How much water she has in her, and whether the pumps are winning.

    Usage:
      pumps
      water

    Tells you what is coming in, what is going out, and - the number that
    actually decides anything - how long she has at this rate.
    """

    key = "pumps"
    aliases = ("water", "well", "sound the well")

    def at_helm(self, vessel):
        """Report the water."""
        report = vessel.water_report()

        if not report.inflow and not vessel.water:
            self.caller.msg("She is tight and dry. Nothing in the well.")
            return

        deep = vessel.water / FOUNDERS_AT
        lines = [f"She has {deep * 100.0:.0f} per cent of her buoyancy in water."]

        if report.inflow:
            lines.append(f"She is making water at {report.inflow * 100.0:.1f} per cent a minute.")
        else:
            lines.append("She is not making any more.")

        if vessel.pump_party:
            lines.append(f"{vessel.pump_party:.0f} hands are on the pumps.")
        elif report.inflow:
            lines.append("Nobody is on the pumps.")

        if vessel.fothered:
            lines.append("There is a sail fothered under her.")

        left = time_to_founder(vessel.water, report.inflow, report.outflow)
        if left == float("inf"):
            if report.inflow:
                lines.append("The pumps are holding it.")
        else:
            lines.append(f"At this rate she has {_how_long(left)}.")
            if vessel.speed > 0.5:
                lines.append("Taking the way off her would slow what is coming in.")

        self.caller.msg(" ".join(lines))


class CmdManPumps(MaritimeCommand):
    """
    Put hands on the pumps.

    Usage:
      man pumps <hands>
      man pumps off

    They are the same hands a fire wants and the same hands the guns want.

    Two things beat numbers. Way through the water forces more of it in, so
    slowing her slows the leak - and past the point where the pumps are manned,
    extra hands are queueing rather than pumping.
    """

    key = "man pumps"
    aliases = ("man the pumps", "pump", "bail")

    def at_helm(self, vessel):
        """Send hands, or call them off."""
        wanted = self.args.strip().lower()
        if wanted in ("off", "none", "belay"):
            vessel.man_pumps(0)
            self.caller.msg("The pumps are abandoned.")
            return

        if not wanted:
            self.caller.msg(
                f"How many hands? {vessel.pump_party:.0f} are on them now, and full "
                f"pumps shift {pump_rate(999) * 100.0:.1f} per cent a minute."
            )
            return

        try:
            hands = float(wanted)
        except ValueError:
            self.caller.msg("Give a number of hands, as 'man pumps 40'.")
            return
        if hands < 0:
            self.caller.msg("A negative pump party is not a thing.")
            return

        report = vessel.man_pumps(hands)
        told = [f"{hands:.0f} hands are on the pumps."]
        if not report.inflow:
            told.append("She is not making water, but they will clear what is in her.")
        elif report.gaining:
            left = time_to_founder(vessel.water, report.inflow, report.outflow)
            told.append(f"It is not enough - she is still gaining, and has {_how_long(left)}.")
            if vessel.speed > 0.5:
                told.append("Take the way off her and the leak eases.")
        else:
            told.append("That is enough to hold it.")
        self.caller.msg(" ".join(told))


class CmdFother(MaritimeCommand):
    """
    Draw a sail under the hull, and let the sea press it into the hole.

    Usage:
      fother

    It does not mend her. It turns a leak she cannot outpump into one she can,
    which is what it did for the ships that survived to report it. The work takes
    a quarter of an hour and costs you the sail.
    """

    key = "fother"
    aliases = ("fother the sail", "fodder")

    def at_helm(self, vessel):
        """Get the sail under her."""
        if vessel.fothered:
            self.caller.msg("There is already a sail fothered under her.")
            return

        before = vessel.leak()
        vessel.fother()

        if vessel.fothered:
            self.caller.msg(
                "The sail is under her and the sea has pressed it home. "
                f"She was making {before * 100.0:.1f} per cent a minute; "
                f"now {vessel.leak() * 100.0:.1f}."
            )
            return

        self.caller.msg(
            "The hands are getting a sail over the bows and working it aft under her. "
            "A quarter of an hour, and she will be the better for it."
        )
