"""
Helm commands.

The player-facing edge of the motion model. These translate what someone types into
`HelmOrders` on a vessel, and report what the hull is actually doing - which is rarely
the same thing, since orders are targets a ship works towards rather than instructions
she obeys.

Commands are the one layer permitted to speak. Everything below them returns structured
values and lets this layer decide what a person sees, which is what allows a game to
replace the wording without touching the simulation.

Speeds are entered and shown in knots, because that is what sailors use, while the
domain works in metres per second throughout. Converting at this boundary keeps display
units out of the physics, so a game preferring kilometres per hour changes this file and
nothing else.

"""

from evennia.commands.command import Command

from .formatting import RAW, format_position
from .motion import HelmOrders
from .position import normalize_bearing
from .resolver import get_world_position
from .typeclasses import Vessel

# One knot is one nautical mile per hour, and a nautical mile is 1852 metres.
METRES_PER_SECOND_PER_KNOT = 1852.0 / 3600.0


def spell_bearing(bearing):
    """
    Speak a bearing the way it is actually said aloud.

    Args:
        bearing (float): Compass bearing in degrees.

    Returns:
        spoken (str): Digits separated, e.g. `"0-9-0"` for 090.

    Notes:
        Courses are always given digit by digit and always in three figures.
        "Ninety" and "one nine zero" are dangerously easy to confuse across a
        windy deck; "zero-nine-zero" is not, which is why the convention exists.

    """
    return "-".join(f"{int(round(bearing)) % 360:03d}")


def knots_to_ms(knots):
    """
    Convert knots to metres per second.

    Args:
        knots (float): Speed in knots.

    Returns:
        speed (float): Speed in metres per second.

    """
    return float(knots) * METRES_PER_SECOND_PER_KNOT


def ms_to_knots(metres_per_second):
    """
    Convert metres per second to knots.

    Args:
        metres_per_second (float): Speed in metres per second.

    Returns:
        knots (float): Speed in knots.

    """
    return float(metres_per_second) / METRES_PER_SECOND_PER_KNOT


def vessel_of(caller):
    """
    The vessel the caller is aboard, if any.

    Args:
        caller (Object): Whoever typed the command.

    Returns:
        vessel (Vessel or None): The hull they are standing on.

    Notes:
        Walks the same chain the position resolver does, so being "aboard" means
        exactly what it means everywhere else rather than being decided separately
        here.

    """
    location = getattr(caller, "location", None)
    source = getattr(location, "maritime_position_source", None)
    return source if isinstance(source, Vessel) else None


class MaritimeCommand(Command):
    """Base for commands that require the caller to be aboard a vessel."""

    locks = "cmd:all()"
    help_category = "Maritime"

    def func(self):
        """Find the vessel, then defer to the command."""
        vessel = vessel_of(self.caller)
        if vessel is None:
            self.caller.msg("You are not aboard a vessel.")
            return
        self.at_helm(vessel)

    def at_helm(self, vessel):
        """
        Do the work, with a vessel guaranteed.

        Args:
            vessel (Vessel): The hull the caller is aboard.

        """
        raise NotImplementedError

    def announce(self, text):
        """
        Call an order out loud, so everyone in earshot hears it.

        Args:
            text (str): What the caller is heard to order.

        Notes:
            Orders on a ship are spoken. A helm order that only the person who
            typed it can see turns a crewed vessel into several people each
            sailing their own private ship.

        """
        location = getattr(self.caller, "location", None)
        if location is not None:
            location.msg_contents(text, exclude=self.caller)

    def aboard(self, vessel, text):
        """
        Send a line to everyone aboard, wherever they are standing.

        Args:
            vessel (Vessel): The hull whose company should hear it.
            text (str): What is said.

        Notes:
            An order acknowledged at the helm carries through the ship. Unlike
            `announce`, this reaches the hold as well as the deck, and includes
            the person who gave the order - they are meant to hear the answer.

        """
        for room in vessel.ship_rooms:
            room.msg_contents(text)


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
        self.caller.msg(f'You call out, "Helm, steer {spoken}."')
        self.announce(f'{self.caller.key} calls out, "Helm, steer {spoken}."')
        self.aboard(vessel, f'The helmsman answers, "Steering {spoken} now, sir."')


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
        self.caller.msg(f'You call out, "Make her {knots:.0f} knots."')
        self.announce(f'{self.caller.key} calls out, "Make her {knots:.0f} knots."')
        self.aboard(vessel, f'The mate answers, "Making {knots:.0f} knots now, sir."')


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
        self.caller.msg('You call out, "All stop."')
        self.announce(f'{self.caller.key} calls out, "All stop."')
        self.aboard(vessel, 'The mate answers, "All stop, aye sir."')


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
