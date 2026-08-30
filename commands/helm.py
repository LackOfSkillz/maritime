"""
Steering her, and telling her how fast to go.

"""

from ..messaging import (
    ALL_STOP,
    HELM_ORDER,
    SPEED_ORDER,
    spell_bearing,
)
from ..motion import HelmOrders
from ..position import normalize_bearing
from .base import MaritimeCommand, knots_to_ms, ms_to_knots

# One knot is one nautical mile per hour, and a nautical mile is 1852 metres.
METRES_PER_SECOND_PER_KNOT = 1852.0 / 3600.0

# How far off a landmark can be and still be worth a bearing, in metres. The
# same reach as a berth search, because a quay you could tie up to is
# unambiguously a quay you can identify.
FIX_RANGE = 3000.0

# Fastest a vessel may be moving and still bring up safely. Letting go with way
# still on her is how cables part and anchors are left on the bottom.
MAX_ANCHORING_SPEED = 1.0


class CmdHelm(MaritimeCommand):
    """
    Order a heading.

    Usage:
      helm <bearing>
      helm

    Steer the vessel onto a compass bearing, where north is 0 and east is 90.
    With no argument, reports what the helm is currently ordered to steer.

    The hull comes round at whatever rate her rudder allows, and a vessel with no
    way on cannot steer at all.

    Example:
      helm 072
    """

    key = "helm"
    aliases = ("steer",)

    def at_helm(self, vessel):
        """Set or report the ordered heading."""
        orders = vessel.orders
        if not self.args.strip():
            self.caller.msg(
                f"Ordered heading {orders.heading:05.1f}, " f"making good {vessel.heading:05.1f}."
            )
            return
        try:
            bearing = normalize_bearing(float(self.args.strip()))
        except ValueError:
            self.caller.msg("Give a bearing in degrees, for example: helm 072")
            return
        spoken = spell_bearing(bearing)
        vessel.orders = HelmOrders(heading=bearing, speed=orders.speed)
        self.order(vessel, HELM_ORDER, spoken=spoken)


class CmdSpeed(MaritimeCommand):
    """
    Order a speed.

    Usage:
      speed <knots>
      speed

    Ask the vessel to make a given speed in knots. With no argument, reports what
    was ordered and what she is actually making.

    She gathers and loses way gradually, so the two will differ for a while after
    any change.

    Example:
      speed 6
    """

    key = "speed"

    def at_helm(self, vessel):
        """Set or report the ordered speed."""
        orders = vessel.orders
        if not self.args.strip():
            self.caller.msg(
                f"Ordered {ms_to_knots(orders.speed):.1f} knots, "
                f"making {ms_to_knots(vessel.speed):.1f}."
            )
            return
        try:
            knots = float(self.args.strip())
        except ValueError:
            self.caller.msg("Give a speed in knots, for example: speed 6")
            return
        if knots < 0:
            self.caller.msg("Order a reciprocal heading rather than a negative speed.")
            return
        vessel.orders = HelmOrders(heading=orders.heading, speed=knots_to_ms(knots))
        self.order(vessel, SPEED_ORDER, knots=knots)


class CmdAllStop(MaritimeCommand):
    """
    Take the way off her.

    Usage:
      allstop

    Orders zero speed. She will not stop at once - a hull carries her way for some
    time, and loses steering as she slows.
    """

    key = "allstop"
    aliases = ("all stop",)

    def at_helm(self, vessel):
        """Order zero speed, keeping the current heading order."""
        vessel.orders = HelmOrders(heading=vessel.orders.heading, speed=0.0)
        self.order(vessel, ALL_STOP)
