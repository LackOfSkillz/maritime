"""
After the firing stops: making up the bill, and what to do about the men who broke.

"""

from ..aftermath import NO_SHIRKERS
from .base import MaritimeCommand


class CmdButchersBill(MaritimeCommand):
    """
    Make up the butcher's bill.

    Usage:
      butchers bill
      bill

    Sorts the men who are off their feet into the four things that number
    contains: the dead, the wounded who will be days coming back, the dazed who
    are up again within the hour, and the ones who were not hurt at all and would
    not fight.

    How that splits is a fact about your crew rather than about the fight. Steady
    men come round; men who were never steady do not.
    """

    key = "butchers bill"
    # Not "muster": that is `crew`'s, and mustering the company is exactly what that
    # command does. Two commands in one set sharing an alias does not raise - one of
    # them simply displaces the other, and `crew` vanished from the helm set until a
    # contract test noticed it had.
    aliases = ("bill", "butcher's bill", "count the cost")

    def at_helm(self, vessel):
        """Count them."""
        bill = vessel.count_the_cost(surgeon=self.surgeon_aboard(vessel))
        if not bill:
            self.caller.msg("Nobody is off their feet. There is no bill to make up.")
            return

        told = [f"Of {bill.counted} off their feet:"]
        told.append(f"  {bill.dead} dead")
        told.append(f"  {bill.wounded} wounded, and days from their duty")
        told.append(f"  {bill.dazed} knocked about, and up again")
        told.append(f"  {bill.shirkers} not hurt at all")
        if bill.saved:
            told.append(f"The surgeon has {bill.saved} of them who would otherwise be gone.")
        told.append(f"She took {bill.fraction * 100.0:.0f} per cent.")
        if bill.shirkers:
            told.append(
                "The ones who were not hurt broke and went below. Start them back to their "
                "duty, or let it go and be short of them."
            )
        self.caller.msg("\n".join(told))

    def surgeon_aboard(self, vessel):
        """
        Args:
            vessel (Vessel): The hull.

        Returns:
            surgeon (float): How well she is doctored, 0 to 1.

        Notes:
            Whether a ship carries a surgeon is a question about her people, which is the
            host game's business. Until a game says otherwise she is assumed to have the
            ordinary provision of a ship her size, which is some and not much.

        """
        return float(getattr(vessel.db, "surgeon", 0.5) or 0.0)


class CmdStartThem(MaritimeCommand):
    """
    Start the shirkers back to their duty.

    Usage:
      start them

    They are on their feet again this minute. The company will hold it against
    you, and a company that holds things against its captain is how a mutiny
    begins - so this is a decision about when you need the hands rather than a
    free way to get them.
    """

    key = "start them"
    aliases = ("start the shirkers", "flog them", "punish shirkers")

    def at_helm(self, vessel):
        """Put them back to work."""
        result = vessel.punish_shirkers()
        if not result:
            if result.code == NO_SHIRKERS:
                self.caller.msg("Nobody broke. There is nobody to start.")
            return
        self.caller.msg(
            f"{result.shirkers} are back on their feet and at their stations. "
            "The lower deck saw it, and will remember."
        )


class CmdLetItGo(MaritimeCommand):
    """
    Say nothing about the men who broke.

    Usage:
      let it go

    No grievance, and no hands either - they will come round in their own time,
    which is a day. That is the honest cost of it, and the reason starting them
    is a real temptation rather than an obviously bad idea.
    """

    key = "let it go"
    aliases = ("say nothing", "pardon them", "overlook it")

    def at_helm(self, vessel):
        """Leave them alone."""
        result = vessel.let_it_go()
        if not result:
            if result.code == NO_SHIRKERS:
                self.caller.msg("Nobody broke. There is nothing to overlook.")
            return
        self.caller.msg(
            f"Nothing is said. {result.shirkers} are still below, and will be for a day. "
            "The lower deck saw that too."
        )
