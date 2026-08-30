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

from .helm import CmdAllStop, CmdHelm, CmdSpeed
from .lookout import CmdLookAround, CmdLookout, CmdScan, CmdWatch, sightings_toward
from .pilotage import (
    CmdChart,
    CmdCurrent,
    CmdFix,
    CmdMaritimeStatus,
    CmdPlot,
    CmdPosition,
    CmdSound,
    CmdWind,
)
from .mooring import BERTH_REFUSALS, CmdAnchor, CmdCastOff, CmdDock, CmdWeighAnchor
from .sail import CmdSail
from .base import MaritimeCommand, knots_to_ms, ms_to_knots, vessel_of

__all__ = (
    "MaritimeCommand",
    "vessel_of",
    "knots_to_ms",
    "ms_to_knots",
    "sightings_toward",
    "BERTH_REFUSALS",
    "CmdHelm",
    "CmdSpeed",
    "CmdAllStop",
    "CmdSail",
    "CmdPosition",
    "CmdMaritimeStatus",
    "CmdWind",
    "CmdChart",
    "CmdPlot",
    "CmdCurrent",
    "CmdFix",
    "CmdSound",
    "CmdLookout",
    "CmdScan",
    "CmdLookAround",
    "CmdWatch",
    "CmdDock",
    "CmdCastOff",
    "CmdAnchor",
    "CmdWeighAnchor",
)
