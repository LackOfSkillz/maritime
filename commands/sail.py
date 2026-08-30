"""
What she carries aloft.

"""

from ..messaging import (
    SAIL_CARRIED_HARD,
    SAIL_ORDER,
    spell_bearing,
)
from ..sailing import SAIL_PLANS, relative_wind_angle, sail_plan
from .base import MaritimeCommand, ms_to_knots

# One knot is one nautical mile per hour, and a nautical mile is 1852 metres.
METRES_PER_SECOND_PER_KNOT = 1852.0 / 3600.0

# How far off a landmark can be and still be worth a bearing, in metres. The
# same reach as a berth search, because a quay you could tie up to is
# unambiguously a quay you can identify.
FIX_RANGE = 3000.0

# Fastest a vessel may be moving and still bring up safely. Letting go with way
# still on her is how cables part and anchors are left on the bottom.
MAX_ANCHORING_SPEED = 1.0


class CmdSail(MaritimeCommand):
    """
    Set, shorten or hand the sail.

    Usage:
      sail <plan>
      sail

    Plans, from least canvas to most:
      furled   - bare poles, no drive at all
      storm    - storm canvas, for weather that would take the sticks out of her
      reefed   - reefed sail, prudent in a fresh breeze
      working  - working sail, her everyday rig
      full     - everything she has, for light airs

    With no argument, reports what is set and what she is making of it.

    A sailing vessel is not ordered a speed. She makes what the wind on her
    heading allows, and setting more canvas than the weather will bear is how
    rigs are lost.

    Example:
      sail working
    """

    key = "sail"
    aliases = ("canvas",)

    def at_helm(self, vessel):
        """Set or report the sail plan."""
        wind = vessel.wind_here()
        if not self.args.strip():
            angle = relative_wind_angle(vessel.heading, wind)
            self.caller.msg(
                f"She carries {vessel.sail_plan.name}, "
                f"{angle:.0f} degrees off a wind of "
                f"{ms_to_knots(wind.speed):.0f} knots from {spell_bearing(wind.bearing)}. "
                f"She could make {ms_to_knots(vessel.sailing_speed()):.1f} knots."
            )
            return

        plan = sail_plan(self.args.strip().lower())
        if plan is None:
            names = ", ".join(known.key for known in SAIL_PLANS)
            self.caller.msg(f"No such sail plan. Try one of: {names}")
            return

        vessel.sail_plan = plan
        self.order(vessel, SAIL_ORDER, plan=plan.name)

        if wind.speed > plan.safe_wind:
            self.order(vessel, SAIL_CARRIED_HARD)
