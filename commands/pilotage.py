"""
Where she is, what the water is doing, and what is under her.

"""

from ..formatting import RAW, format_depth, format_position, format_range, pick_scale
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


class CmdFollow(MaritimeCommand):
    """
    Hand the course to the sailing master.

    Usage:
      follow

    He steers for the next mark of the plotted course, allowing for the set,
    carries whatever the wind will let her carry, and takes the way off her
    coming up to the last one. He gives the con back when the passage is made.

    He does nothing else. He will not evade, divert, shorten for a lee shore or
    make any judgement beyond the four above - those are standing orders, and
    they are not his to give.

    """

    key = "follow"
    aliases = ("follow course", "make passage")

    def at_helm(self, vessel):
        """
        Args:
            vessel (Vessel): The hull the caller is aboard.

        """
        if not vessel.route:
            self.caller.msg("There is no course plotted for him to follow.")
            return
        if vessel.next_mark() is None:
            self.caller.msg("The course is run; there is no mark left to make.")
            return

        vessel.under_con = True
        self.caller.msg('You call out, "Sailing master, take the con."')
        self.announce(f'{self.caller.key} calls out, "Sailing master, take the con."')
        self.aboard(vessel, 'The sailing master answers, "I have her, sir."')


class CmdBelay(MaritimeCommand):
    """
    Take the con back from the sailing master.

    Usage:
      belay

    She holds whatever heading and canvas she had, and answers you again.

    """

    key = "belay"
    aliases = ("take the con", "stand down")

    def at_helm(self, vessel):
        """
        Args:
            vessel (Vessel): The hull the caller is aboard.

        """
        if not vessel.under_con:
            self.caller.msg("You have the con already.")
            return
        vessel.under_con = False
        self.caller.msg('You call out, "I have her."')
        self.announce(f'{self.caller.key} calls out, "I have her."')
        self.aboard(vessel, 'The sailing master answers, "You have her, sir."')


class CmdWeather(MaritimeCommand):
    """
    Report the weather: the wind, the sea and how far you can see.

    Usage:
      weather

    Wind, sea state and visibility together, because they are not independent
    things that happen to be true at the same time - a gale brings a high sea and
    takes your visibility with it.

    """

    key = "weather"
    aliases = ("forecast", "glass")

    def at_helm(self, vessel):
        """
        Args:
            vessel (Vessel): The hull the caller is aboard.

        """
        from ..environment import weather_at
        from ..messaging import BEAUFORT_NAMES
        from ..sailing import beaufort_force

        position = vessel.maritime_position
        if position is None:
            self.caller.msg("She is not afloat anywhere with weather.")
            return

        weather = weather_at(position)
        force = beaufort_force(weather.wind.speed)
        self.caller.msg(
            f"Wind         {BEAUFORT_NAMES[force]} from "
            f"{spell_bearing(weather.wind.bearing)}, force {force}"
        )
        self.caller.msg(f"Sea          {weather.sea_state}, " f"about {weather.wave_height:.1f} m")
        self.caller.msg(f"Visibility   {format_range(weather.visibility)}")


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


class CmdChart(MaritimeCommand):
    """
    Read what the chart says about the water here.

    Usage:
      chart

    A chart is knowledge, not the sea. It covers only where somebody surveyed, it
    is only as good as they were, and it has been going out of date since the day
    it was drawn. Its soundings are against the datum, so the tide is yours to
    apply - which is how a careful sailor still goes aground on a bank marked
    deep enough.

    Compare it with `sound`, which is the truth and reaches only as far as the
    lead line.

    """

    key = "chart"
    aliases = ("read chart", "charts")

    def at_helm(self, vessel):
        """
        Args:
            vessel (Vessel): The hull the caller is aboard.

        """
        from ..config import time_provider

        position = vessel.maritime_position
        if position is None:
            self.caller.msg("She is not afloat anywhere a chart covers.")
            return

        chart = vessel.chart_here()
        if chart is None:
            if not vessel.charts:
                self.caller.msg("There is not a chart aboard her.")
            else:
                self.caller.msg(
                    "You are off the edge of every chart she carries. "
                    "There are no soundings here at all."
                )
            return

        now = time_provider().now()
        quality = chart.quality_at(now)
        depth = vessel.charted_depth()

        self.caller.msg(f"{chart.key}, surveyed by {chart.maker}.")
        self.caller.msg(f"  Charted depth at datum   {format_depth(depth)}")
        self.caller.msg(f"  Confidence               {self.confidence(quality)}")

    def confidence(self, quality):
        """
        Args:
            quality (float): How good the chart is now, from 0 to 1.

        Returns:
            text (str): What a navigator would say about it.

        """
        if quality >= 0.9:
            return "a good survey, recently made"
        if quality >= 0.7:
            return "sound enough, though not new"
        if quality >= 0.4:
            return "old, and not to be leaned on"
        return "a rumour with a compass rose on it"


class CmdPlot(MaritimeCommand):
    """
    Plot a course to a mark, by way of safe water.

    Usage:
      plot <mark>
      plot

    Lays a route from the nearest mark to the one you name, following the water
    somebody has said is passable rather than a straight line across a headland.
    With no argument, reports the course she is already following.

    """

    key = "plot"
    aliases = ("course", "route")

    def at_helm(self, vessel):
        """
        Args:
            vessel (Vessel): The hull the caller is aboard.

        """
        from ..config import navigation_network

        position = vessel.maritime_position
        if position is None:
            self.caller.msg("She is not afloat.")
            return

        if not self.args.strip():
            self.report(vessel)
            return

        network = navigation_network()
        here = network.nearest(position)
        if here is None:
            self.caller.msg("There is not a mark laid in these waters.")
            return

        wanted = self.args.strip().lower()
        destination = network.waypoint(wanted)
        if destination is None:
            self.caller.msg(f"No mark called '{self.args.strip()}'.")
            return

        route = network.plan(here.key, destination.key)
        if not route:
            self.caller.msg(
                f"There is no safe water laid between {here.key} and {destination.key}."
            )
            return

        vessel.route = route
        self.caller.msg(
            f"Course plotted by way of {len(route)} marks, "
            f"{format_range(route.distance)} in all:"
        )
        for mark in route.waypoints:
            self.caller.msg(f"  {mark.key}")

    def report(self, vessel):
        """
        Args:
            vessel (Vessel): The hull.

        """
        if not vessel.route:
            self.caller.msg("She is following no course.")
            return
        mark = vessel.next_mark()
        if mark is None:
            self.caller.msg("She has run her course; there is no mark left to make.")
            return
        position = vessel.maritime_position
        bearing = spell_bearing(position.bearing_to(mark.position))
        # Both ranges in one unit. "Two miles to the mark, one league to run in
        # all" is two numbers a captain has to convert before he can tell which is
        # bigger, in the one sentence where the comparison is the whole point.
        to_mark = position.horizontal_distance_to(mark.position)
        remaining = vessel.passage_remaining()
        scale = pick_scale([to_mark, remaining])
        self.caller.msg(
            f"Making for {mark.key}, {bearing}, "
            f"{format_range(to_mark, scale=scale)}. "
            f"{format_range(remaining, scale=scale)} to run in all."
        )
