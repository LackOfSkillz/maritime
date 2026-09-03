"""
Commands for working a vessel, grouped by the station that gives them.

Helm, sail, pilotage, lookout and mooring are separate modules because they are
separate jobs aboard a real ship, and because that is how the design has
always described them - contextual command groups, exposed by cmdset. Splitting
them now, while there are sixteen, is cheaper than splitting them when gunnery
and damage control arrive.

Everything is re-exported here, so `from ..commands import CmdHelm` goes on
working and nothing outside this package needs to know which station a command
belongs to.

The modules are named for the job rather than for the domain module each leans
on: `commands/navigation.py` would shadow `maritime.navigation` from inside this
package, which is exactly how the first attempt at this split broke.

"""

from .base import MaritimeCommand, knots_to_ms, ms_to_knots, vessel_of
from .boarding import (
    CmdCutGrapples,
    CmdGrapple,
    CmdGrapples,
    CmdStrike,
)
from .crew import CmdCrew
from .gunnery import CmdFire, CmdGuns, CmdHoldFire, CmdLoad
from .handbook import CmdMaritimeHelp, MaritimeHandbookCmdSet
from .helm import CmdAllStop, CmdHelm, CmdSpeed
from .lading import CmdDischarge, CmdManifest, CmdStow
from .lookout import (
    CmdLookAround,
    CmdLookout,
    CmdScan,
    CmdTarget,
    CmdWatch,
    sightings_toward,
)
from .aftermath import CmdButchersBill, CmdLetItGo, CmdStartThem
from .company import CmdCompany, CmdKeepStation, CmdPartCompany
from .repairing import CmdRefit, CmdRepairs, CmdSetRepairs
from .firefighting import CmdFightFire, CmdFires
from .pumping import CmdFother, CmdManPumps, CmdPumps
from .mooring import (
    BERTH_REFUSALS,
    CmdAnchor,
    CmdCutCable,
    CmdCastOff,
    CmdDock,
    CmdKedge,
    CmdSpring,
    CmdWeighAnchor,
)
from .passage import CmdMakeFor, CmdPorts, PassageCmdSet
from .pilotage import (
    CmdBelay,
    CmdChart,
    CmdCurrent,
    CmdFix,
    CmdFollow,
    CmdMaritimeStatus,
    CmdPlot,
    CmdPosition,
    CmdSound,
    CmdWeather,
    CmdWind,
)
from .rowing import (
    CmdEasyOars,
    CmdGiveWay,
    CmdHoldWater,
    CmdOars,
    CmdPaddleStroke,
    CmdStretchOut,
)
from .sail import CmdSail
from .shipwright import CmdShipwright

__all__ = (
    "CmdMaritimeHelp",
    "MaritimeHandbookCmdSet",
    "MaritimeCommand",
    "CmdStow",
    "CmdShipwright",
    "CmdGrapple",
    "CmdCutGrapples",
    "CmdStrike",
    "CmdGrapples",
    "CmdGiveWay",
    "CmdPaddleStroke",
    "CmdStretchOut",
    "CmdEasyOars",
    "CmdHoldWater",
    "CmdOars",
    "CmdDischarge",
    "CmdManifest",
    "vessel_of",
    "knots_to_ms",
    "ms_to_knots",
    "sightings_toward",
    "BERTH_REFUSALS",
    "CmdGuns",
    "CmdLoad",
    "CmdFire",
    "CmdHoldFire",
    "CmdCrew",
    "CmdHelm",
    "CmdSpeed",
    "CmdAllStop",
    "CmdSail",
    "CmdPosition",
    "CmdMaritimeStatus",
    "CmdWeather",
    "CmdWind",
    "CmdChart",
    "CmdFollow",
    "CmdBelay",
    "CmdPlot",
    "CmdPorts",
    "CmdMakeFor",
    "PassageCmdSet",
    "CmdCurrent",
    "CmdFix",
    "CmdSound",
    "CmdLookout",
    "CmdScan",
    "CmdTarget",
    "CmdLookAround",
    "CmdWatch",
    "CmdDock",
    "CmdKedge",
    "CmdCastOff",
    "CmdAnchor",
    "CmdRefit",
    "CmdRepairs",
    "CmdSetRepairs",
    "CmdCompany",
    "CmdKeepStation",
    "CmdPartCompany",
    "CmdButchersBill",
    "CmdLetItGo",
    "CmdStartThem",
    "CmdFightFire",
    "CmdFother",
    "CmdManPumps",
    "CmdPumps",
    "CmdFires",
    "CmdCutCable",
    "CmdSpring",
    "CmdWeighAnchor",
)
