"""
The carpenter's party, and the yard that finishes what they cannot.

"""

from ..damage import RIGGING, TRACKS, WEAPONS
from ..repairs import DOING_NOTHING_ELSE
from .base import MaritimeCommand

#: What each track is called when somebody is being told what is wrong.
CALLED = {
    "hull": "her hull",
    "rigging": "her rigging",
    "oars": "her oars",
    "weapons": "her guns",
}


class CmdRepairs(MaritimeCommand):
    """
    What is broken, who is working on it, and what wants a yard.

    Usage:
      repairs

    Her state track by track, the rate the carpenter's party is working at, and
    the things her own people cannot put right however long they have.
    """

    key = "repairs"
    aliases = ("damage", "carpenter")

    def at_helm(self, vessel):
        """Report the state of her."""
        report = vessel.repair_report()
        broken = [(track, vessel.damage.of(track)) for track in TRACKS]
        broken = [(track, hurt) for track, hurt in broken if hurt > 0.0]

        told = []
        if not broken:
            told.append("She is sound.")
        else:
            told.append("Wrong with her:")
            for track, hurt in broken:
                told.append(f"  {CALLED.get(track, track):<14} {hurt * 100:>3.0f} per cent gone")

        if vessel.carpenters:
            told.append(
                f"{vessel.carpenters:.0f} hands are on repairs, mending "
                f"{report.rate * 100:.0f} per cent of a track a day."
            )
            if not report.doing_nothing_else:
                told.append(
                    f"Heaving to and handing her canvas would work at "
                    f"{DOING_NOTHING_ELSE:.0f} times that."
                )
        elif broken:
            told.append("Nobody is working on her.")

        if vessel.jury_rigged:
            told.append(
                "|yShe is under a jury rig.|n A spar stands where a mast did; she carries "
                "sail and not as much, and no work aboard will improve it."
            )
        wanting = vessel.wants_a_yard()
        if wanting:
            named = " and ".join(CALLED.get(track, track) for track in wanting)
            told.append(f"{named.capitalize()} wants a yard.")

        self.caller.msg("\n".join(told))


class CmdSetRepairs(MaritimeCommand):
    """
    Put hands to work on her.

    Usage:
      set repairs <hands>
      set repairs off

    They are the same hands the guns want, the pumps want and a fire wants -
    which is why, in action, the only things anybody can do are bail, pump and
    replace sail. Nothing forbids it. There is simply one crew.

    She mends at twice the rate hove to with her canvas in, because everybody
    who is not steering is on the job. On a passage with somewhere to be, that
    is a real decision.
    """

    key = "set repairs"
    aliases = ("repair party", "set carpenters")

    def at_helm(self, vessel):
        """Send the party, or call them off."""
        said = self.args.strip().lower()
        if said in ("off", "none", "belay"):
            vessel.set_carpenters(0)
            self.caller.msg("The carpenter's party is called off.")
            return

        if not said:
            self.caller.msg(
                f"How many hands? {vessel.carpenters:.0f} are on it now. " "Try |wset repairs 20|n."
            )
            return

        try:
            hands = float(said)
        except ValueError:
            self.caller.msg("Give a number of hands, as 'set repairs 20'.")
            return
        if hands < 0:
            self.caller.msg("A negative carpenter's party is not a thing.")
            return

        report = vessel.set_carpenters(hands)
        told = [f"{hands:.0f} hands are set to work on her."]
        told.append(f"That is {report.rate * 100:.0f} per cent of a track a day.")
        if not report.doing_nothing_else:
            told.append("Twice that if she heaves to and hands her canvas.")
        self.caller.msg(" ".join(told))


class CmdRefit(MaritimeCommand):
    """
    Have a yard put right what her own people cannot.

    Usage:
      refit

    Only alongside. A yard replaces a jury-rigged mast with a real one and
    remounts guns she carries no spares for, and it is the only thing that lifts
    a jury rig - which is the whole reason a ship carrying one has somewhere she
    needs to be.

    What a refit costs and how long she lies there is the game's business, and
    is taken from her own purse.
    """

    key = "refit"
    aliases = ("overhaul",)

    def at_helm(self, vessel):
        """Hand her over to the yard."""
        if not vessel.docked:
            self.caller.msg("A yard cannot reach her out here. Bring her alongside and try again.")
            return

        was_rigged = vessel.jury_rigged
        wanted = [track for track in TRACKS if vessel.damage.of(track) > 0.0]
        if not wanted and not was_rigged:
            self.caller.msg("There is nothing for a yard to do. She is sound.")
            return

        vessel.refit()
        told = ["The yard takes her in hand."]
        if RIGGING in wanted or was_rigged:
            told.append("A proper mast goes in where the spar was.")
        if WEAPONS in wanted:
            told.append("Her guns are remounted.")
        told.append("She is sound.")
        self.caller.msg(" ".join(told))
