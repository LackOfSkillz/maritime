"""
Command sets for maritime play.

Evennia gathers commands from the caller, their account, their location and the objects
around them, and merges the lot for each input. That is what lets a command exist only
where it makes sense - and a helm order only makes sense with a deck under you.

Adding a set by *path* rather than by instance matters more than it looks. Evennia stores
a cmdset as the dotted path it was created from, so a set built on the fly survives until
the next reload and then quietly vanishes, taking every command with it.

"""

from evennia.commands.cmdset import CmdSet

from .commands import (
    CmdAllStop,
    CmdAnchor,
    CmdBelay,
    CmdCastOff,
    CmdChart,
    CmdCrew,
    CmdCurrent,
    CmdCutGrapples,
    CmdDischarge,
    CmdDock,
    CmdEasyOars,
    CmdFire,
    CmdFix,
    CmdFollow,
    CmdGiveWay,
    CmdGrapple,
    CmdGrapples,
    CmdGuns,
    CmdHelm,
    CmdHoldFire,
    CmdHoldWater,
    CmdKedge,
    CmdLoad,
    CmdLookAround,
    CmdLookout,
    CmdMakeFor,
    CmdManifest,
    CmdMaritimeStatus,
    CmdOars,
    CmdPaddleStroke,
    CmdPlot,
    CmdPorts,
    CmdPosition,
    CmdSail,
    CmdScan,
    CmdShipwright,
    CmdSound,
    CmdSpeed,
    CmdStow,
    CmdStretchOut,
    CmdStrike,
    CmdTarget,
    CmdWatch,
    CmdWeather,
    CmdWeighAnchor,
    CmdWind,
)


class HelmCmdSet(CmdSet):
    """
    Commands for working a vessel.

    Intended on a `ShipRoom`, so the orders are available to whoever is standing
    there and to nobody ashore. Putting it on a character instead would let them
    order a helm from a tavern.

    """

    key = "maritime_helm"
    priority = 1

    def at_cmdset_creation(self):
        """Populate the set."""
        self.add(CmdHelm())
        self.add(CmdCrew())
        self.add(CmdGuns())
        self.add(CmdLoad())
        self.add(CmdFire())
        self.add(CmdHoldFire())
        self.add(CmdLookout())
        self.add(CmdSpeed())
        self.add(CmdAllStop())
        self.add(CmdPosition())
        self.add(CmdSail())
        self.add(CmdScan())
        self.add(CmdTarget())
        self.add(CmdAnchor())
        self.add(CmdDock())
        self.add(CmdKedge())
        self.add(CmdStow())
        self.add(CmdDischarge())
        self.add(CmdManifest())
        self.add(CmdGrapple())
        self.add(CmdCutGrapples())
        self.add(CmdStrike())
        self.add(CmdGrapples())
        self.add(CmdGiveWay())
        self.add(CmdPaddleStroke())
        self.add(CmdStretchOut())
        self.add(CmdEasyOars())
        self.add(CmdHoldWater())
        self.add(CmdOars())
        self.add(CmdFix())
        self.add(CmdLookAround())
        self.add(CmdWatch())
        self.add(CmdCastOff())
        self.add(CmdWeighAnchor())
        self.add(CmdWind())
        self.add(CmdWeather())
        self.add(CmdCurrent())
        self.add(CmdChart())
        self.add(CmdFollow())
        self.add(CmdBelay())
        self.add(CmdPlot())
        self.add(CmdPorts())
        self.add(CmdMakeFor())
        self.add(CmdSound())
        self.add(CmdMaritimeStatus())


class ShipwrightCmdSet(CmdSet):
    """
    The builder's tools.

    Notes:
        Separate from `HelmCmdSet` because it is the one maritime command that must
        work with no deck under you. A world is built from dry land - usually from a
        batch file - and a set that only appeared aboard would be useless for the job
        it exists to do.

        Add it to the game's character or account cmdset rather than to a room. The
        command locks itself to Builders; the cmdset does not, so a game wanting it
        somewhere narrower can say so without editing this.

    """

    key = "maritime_shipwright"
    priority = 1

    def at_cmdset_creation(self):
        """Populate the set."""
        self.add(CmdShipwright())
