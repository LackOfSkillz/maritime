"""
Where she is, what the water is doing, and what is under her.

"""

from ..formatting import RAW, format_depth, format_position, format_range
from ..grounding import SHOAL_WARNING_CLEARANCE
from ..messaging import (
    CAST_THE_LEAD,
    WORK_THE_FIX,
    leadsman_call,
    spell_bearing,
)
from ..rooms import berths_near
from ..navigation import FIX_UNCERTAINTY
from ..sailing import relative_wind_angle
from ..position import bearing_difference
from ..resolver import get_world_position
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


class CmdPosition(MaritimeCommand):
    """
    Report the vessel's state.

    Usage:
      position

    Shows where she is, what she is doing, and what she has been ordered to do.
    """

    key = "position"
    aliases = ("pos",)

    def at_helm(self, vessel):
        """Report position, heading and speed against what was ordered."""
        where = get_world_position(vessel)
        orders = vessel.orders
        lines = [
            f"|w{vessel.key}|n",
            f"  Position   {format_position(where)}",
            f"  Heading    {spell_bearing(vessel.heading)}"
            f"   ordered {spell_bearing(orders.heading)}",
            f"  Speed      {ms_to_knots(vessel.speed):.1f} kt"
            f"   ordered {ms_to_knots(orders.speed):.1f} kt",
        ]
        self.caller.msg("\n".join(lines))


class CmdMaritimeStatus(MaritimeCommand):
    """
    Staff view of a vessel's simulation state.

    Usage:
      @maritime

    Shows the underlying coordinates and motion state rather than the navigator's
    view. For working out why a vessel is where she is - a different question from
    where a character believes she is.
    """

    key = "@maritime"
    locks = "cmd:perm(Builder)"

    def at_helm(self, vessel):
        """Report the raw simulation state."""
        where = get_world_position(vessel)
        orders = vessel.orders
        limits = vessel.motion_limits
        lines = [
            f"|w{vessel.key}|n  (#{vessel.id})",
            f"  Coordinates  {format_position(where, style=RAW)}",
            f"  Heading      {vessel.heading:.4f}   ordered {orders.heading:.4f}",
            f"  Speed        {vessel.speed:.4f} m/s   ordered {orders.speed:.4f} m/s",
            f"  Limits       max {limits.max_speed:.2f} m/s,"
            f" accel {limits.acceleration:.2f} m/s2, turn {limits.turn_rate:.2f} deg/s",
            f"  Unsaved      {bool(vessel.ndb.maritime_dirty)}",
        ]
        self.caller.msg(chr(10).join(lines))


class CmdWind(MaritimeCommand):
    """
    Read the wind.

    Usage:
      wind

    Reports where the wind is from, how hard it blows, and how the vessel lies
    to it - which is what decides whether she can go where you want.
    """

    key = "wind"

    def at_helm(self, vessel):
        """Report the wind and how she lies to it."""
        wind = vessel.wind_here()
        if wind.speed <= 0.0:
            self.caller.msg("Flat calm. Not a breath, and the sails hang slack.")
            return

        angle = relative_wind_angle(vessel.heading, wind)
        if angle < 30.0:
            lying = "She lies head to wind and will not sail."
        elif angle < 60.0:
            lying = "She is close-hauled, working hard to windward."
        elif angle < 120.0:
            lying = "She has it on the beam, her best point of sailing."
        elif angle < 160.0:
            lying = "She has it on the quarter, running easy."
        else:
            lying = "She runs square before it."

        self.caller.msg(
            f"The wind is {ms_to_knots(wind.speed):.0f} knots "
            f"from {spell_bearing(wind.bearing)}. {lying}"
        )


class CmdCurrent(MaritimeCommand):
    """
    Report the set and drift of the current.

    Usage:
      current

    Where the water is going and how fast, and what it is doing to her: the
    course and speed she is making good, as against the course she is steering
    and the speed she is sailing.

    A current is named for where it goes. The wind is named for where it comes
    from. Both are correct and neither is going to change.

    """

    key = "current"
    aliases = ("set", "drift")

    def at_helm(self, vessel):
        """
        Args:
            vessel (Vessel): The hull the caller is aboard.

        """
        current = vessel.current_here()
        if not current.running:
            self.caller.msg("Slack water. She goes where she points.")
            return

        drift = f"{ms_to_knots(current.drift):.1f} knots"
        self.caller.msg(f"The current sets {spell_bearing(current.set)}, drift {drift}.")

        track = vessel.made_good()
        if track is None:
            return
        course, made = track
        if abs(bearing_difference(vessel.heading, course)) < 0.5:
            return
        self.caller.msg(
            f"She heads {spell_bearing(vessel.heading)} and makes good "
            f"{spell_bearing(course)} at "
            f"{ms_to_knots(made):.1f} knots."
        )


class CmdFix(MaritimeCommand):
    """
    Fix her position from a landmark in sight.

    Usage:
      fix

    A dead reckoning drifts, because the water moves and the log cannot see it.
    Bringing something of known position within sight lets you say where you are
    again - and the difference between where you thought you were and where you
    actually are is the set and drift that has been carrying you, which is worth
    more than the fix itself.

    Out of sight of land there is nothing to fix on.

    """

    key = "fix"
    aliases = ("take a fix",)

    def at_helm(self, vessel):
        """
        Args:
            vessel (Vessel): The hull the caller is aboard.

        """
        position = vessel.maritime_position
        if position is None:
            self.caller.msg("She is not afloat.")
            return

        landmarks = berths_near(position, radius=FIX_RANGE)
        if not landmarks:
            self.caller.msg(
                "No landmark in sight. There is nothing out here to fix her position by."
            )
            return

        port, _berth = landmarks[0]
        before = vessel.reckoned_position
        experienced = vessel.fix_position()
        moved = before.horizontal_distance_to(vessel.maritime_position)

        self.order(vessel, WORK_THE_FIX, landmark=port.key)
        if moved < FIX_UNCERTAINTY:
            self.caller.msg("She is where you reckoned her, near enough.")
        else:
            self.caller.msg(
                f"You were out by {format_range(moved)}. " f"The reckoning is corrected."
            )
        if experienced.running:
            self.caller.msg(
                f"That is a set of {spell_bearing(experienced.set)}, drift "
                f"{ms_to_knots(experienced.drift):.1f} knots you have been carrying."
            )


class CmdSound(MaritimeCommand):
    """
    Take a sounding.

    Usage:
      sound

    Reports the water under the keel - not the depth of the sea, but how much of
    it is between the hull and the ground. That is the number that matters, and
    it already accounts for her draft and the state of the tide.

    In poor visibility a run of soundings is also a position line: a depth
    profile along a track is a signature, and a navigator who knows the chart can
    read where she is from it.
    """

    key = "sound"
    aliases = ("depth", "leadline")

    def at_helm(self, vessel):
        """Cast the lead, and report both what it found and what it leaves her."""
        clearance = vessel.keel_clearance()
        if clearance is None:
            self.caller.msg("She is not afloat anywhere the lead would reach.")
            return

        self.order(vessel, CAST_THE_LEAD)

        if clearance <= 0.0:
            self.aboard(vessel, 'The leadsman calls, "No bottom under her - she is on it, sir!"')
            return

        depth = clearance + vessel.draft
        report = f'The leadsman calls, "{leadsman_call(depth)}"'
        under = f"{format_depth(clearance)} under her keel"
        if clearance < SHOAL_WARNING_CLEARANCE:
            self.aboard(vessel, f"{report} That is {under}. Shoal water, sir.")
            return
        self.aboard(vessel, f"{report} That is {under}.")
