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
    CmdWeighAnchor,
    CmdFire,
    CmdGuns,
    CmdHelm,
    CmdLoad,
    CmdLookout,
    CmdMaritimeStatus,
    CmdPosition,
    CmdAnchor,
    CmdCastOff,
    CmdDock,
    CmdLookAround,
    CmdFix,
    CmdWatch,
    CmdBelay,
    CmdChart,
    CmdFollow,
    CmdCurrent,
    CmdPlot,
    CmdSail,
    CmdScan,
    CmdTarget,
    CmdSound,
    CmdSpeed,
    CmdWeather,
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
        self.add(CmdGuns())
        self.add(CmdLoad())
        self.add(CmdFire())
        self.add(CmdLookout())
        self.add(CmdSpeed())
        self.add(CmdAllStop())
        self.add(CmdPosition())
        self.add(CmdSail())
        self.add(CmdScan())
        self.add(CmdTarget())
        self.add(CmdAnchor())
        self.add(CmdDock())
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
        self.add(CmdSound())
        self.add(CmdMaritimeStatus())
