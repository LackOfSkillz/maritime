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

from .formatting import RAW, format_depth, format_position, format_range
from .grounding import SHOAL_WARNING_CLEARANCE
from .messaging import (
    ALL_STOP,
    ALONGSIDE_ORDER,
    ANCHOR_ORDER,
    CAST_THE_LEAD,
    GANGWAY_DOWN,
    HELM_ORDER,
    LET_GO,
    MADE_FAST,
    SAIL_CARRIED_HARD,
    SAIL_ORDER,
    SINGLE_UP,
    SPEED_ORDER,
    WEIGH_ORDER,
    WORK_THE_FIX,
    leadsman_call,
    spell_bearing,
)
from .ports import (
    BADLY_ALIGNED,
    OCCUPIED,
    TOO_BEAMY,
    TOO_DEEP,
    TOO_FAR,
    TOO_FAST,
    TOO_LONG,
    can_dock,
)
from .rooms import berths_near, rig_gangway
from .navigation import FIX_UNCERTAINTY
from .observation import (
    CLASSIFIED,
    DEFAULT_HEIGHT_OF_EYE,
    IDENTIFIED,
    VESSEL,
    bearing_in_points,
    horizon_distance,
)
from .motion import HelmOrders
from .sailing import SAIL_PLANS, relative_wind_angle, sail_plan
from .position import bearing_difference, normalize_bearing
from .resolver import get_world_position
from .typeclasses import Vessel
from .vessel import WEATHER_DECKS

# One knot is one nautical mile per hour, and a nautical mile is 1852 metres.
METRES_PER_SECOND_PER_KNOT = 1852.0 / 3600.0

# How far off a landmark can be and still be worth a bearing, in metres. The
# same reach as a berth search, because a quay you could tie up to is
# unambiguously a quay you can identify.
FIX_RANGE = 3000.0

# Fastest a vessel may be moving and still bring up safely. Letting go with way
# still on her is how cables part and anchors are left on the bottom.
MAX_ANCHORING_SPEED = 1.0


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

    def order(self, vessel, event, **detail):
        """
        Give a spoken order, and let the crew answer it.

        Args:
            vessel (Vessel): The hull whose company is speaking.
            event (str): One of the order constants in `messaging`.
            **detail: What the order carries.

        Notes:
            The words come from the vessel's narrator, so a game that has
            replaced its voice has replaced this too. A command's job is to know
            *that* an order was given and to whom it carries - never what it
            sounds like.

        """
        spoken = vessel.narrator.order_for(event, who=self.caller.key, **detail)
        if spoken.called:
            self.caller.msg(spoken.called)
        if spoken.overheard:
            self.announce(spoken.overheard)
        if spoken.answered:
            self.aboard(vessel, spoken.answered)

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


class CmdLookout(MaritimeCommand):
    """
    Report what can be seen from where you stand.

    Usage:
      lookout

    What the sea holds, nearest first: where to look, how far off, and as much as
    can be told at that range. How far you can see depends on how high you are
    standing, so the answer from a masthead is not the answer from the deck.

    """

    key = "lookout"
    aliases = ("sightings",)

    def at_helm(self, vessel):
        """
        Args:
            vessel (Vessel): The hull the caller is aboard.

        """
        room = getattr(self.caller, "location", None)
        exposure = getattr(room, "exposure", None)
        if exposure not in WEATHER_DECKS:
            self.caller.msg("You cannot see the sea from in here.")
            return

        height = getattr(room, "height_of_eye", DEFAULT_HEIGHT_OF_EYE)
        seen = vessel.contacts(height)
        if not seen:
            self.caller.msg(
                f"Nothing in sight. The horizon is {format_range(horizon_distance(height))} off."
            )
            return

        lines = ["The lookout reports:"]
        for sighting in seen:
            where = bearing_in_points(sighting.relative).capitalize()
            lines.append(
                f"  {where:<34}{format_range(sighting.distance):>12}   "
                f"{describe_contact(sighting)}"
            )
        self.caller.msg("\n".join(lines))


def describe_contact(sighting):
    """
    Say as much about a contact as the range allows.

    Args:
        sighting (Sighting): What was seen.

    Returns:
        text (str): What the observer can honestly say it is.

    Notes:
        Bounded by the detection level rather than by what the target actually
        is. A hull at the edge of vision is a shape on the water even if the
        engine knows her name, and reporting the name anyway would make closing
        to identify pointless.

    """
    if sighting.level == IDENTIFIED:
        return f"the {sighting.target.key}"
    if sighting.level == CLASSIFIED:
        plan = sighting.target.sail_plan
        return "a vessel under sail" if plan.area > 0.0 else "a vessel, sails furled"
    if sighting.level == VESSEL:
        return "a sail"
    return "something on the water"


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


#: What to tell a captain when a berth will not have her. Keyed by the reason code
#: the domain returned, so adding a precondition means adding a line here and the
#: command needs no new branch.
BERTH_REFUSALS = {
    TOO_FAR: "The berth is {distance} off. Work her in closer before you put lines ashore.",
    TOO_FAST: "She still has way on. Take it off her before you go alongside.",
    BADLY_ALIGNED: "She is lying across the berth. Bring her round parallel to the quay.",
    TOO_LONG: "She is too long for that berth.",
    TOO_BEAMY: "She is too broad in the beam for that berth.",
    TOO_DEEP: "She draws too much for the water alongside there.",
    OCCUPIED: "There is a ship lying there already.",
}


class CmdDock(MaritimeCommand):
    """
    Bring her alongside and make fast.

    Usage:
      dock
      dock <berth>

    Puts lines ashore and lowers the gangway, after which the quay is one step
    off the deck like any other exit. She must be near enough for the lines to
    reach, slow enough not to break the quay, lying roughly along it, and small
    enough to fit the berth.

    With no argument she takes the nearest berth, and says why if it will not
    have her.

    """

    key = "dock"
    aliases = ("moor", "berth")

    def at_helm(self, vessel):
        """
        Args:
            vessel (Vessel): The hull the caller is aboard.

        """
        if vessel.docked:
            self.caller.msg("She is already made fast.")
            return

        position = vessel.maritime_position
        if position is None:
            self.caller.msg("She is not afloat anywhere near a quay.")
            return

        found = berths_near(position)
        if not found:
            self.caller.msg("There is no berth within reach of her lines.")
            return

        if self.args.strip():
            wanted = self.args.strip().lower()
            found = [pair for pair in found if pair[1].key.lower() == wanted]
            if not found:
                self.caller.msg(f"No berth called '{self.args.strip()}' within reach.")
                return

        port, berth = found[0]
        result = can_dock(
            position,
            vessel.speed,
            vessel.heading,
            vessel.length,
            vessel.beam,
            vessel.draft,
            berth,
            occupied=port.occupant_of(berth) is not None,
        )
        if not result:
            refusal = BERTH_REFUSALS.get(result.code, "She cannot lie there.")
            self.caller.msg(refusal.format(distance=format_range(result.distance)))
            return

        deck = self.landing_deck(vessel)
        if deck is None:
            self.caller.msg("She has no open deck for a gangway to land on.")
            return

        self.order(vessel, ALONGSIDE_ORDER)

        gangway = rig_gangway(deck, port)
        vessel.make_fast(port, berth, gangway)

        self.order(vessel, MADE_FAST, berth=berth.key, side=result.side)
        self.order(vessel, GANGWAY_DOWN)
        port.msg_contents(f"{vessel.key} comes alongside, and her gangway comes down.")

    def landing_deck(self, vessel):
        """
        The deck a gangway would land on.

        Args:
            vessel (Vessel): The hull.

        Returns:
            room (ShipRoom or None): Her lowest weather deck, or None if she has
                no deck open to the sky.

        Notes:
            The lowest, not the highest. A gangway reaches a quay from the main
            deck; running it to the masthead because that is where the lookout
            stands would be a remarkable sight.

        """
        decks = [room for room in vessel.ship_rooms if room.exposure in WEATHER_DECKS]
        if not decks:
            return None
        return min(decks, key=lambda room: room.height_of_eye)


class CmdCastOff(MaritimeCommand):
    """
    Let go the lines and get under way.

    Usage:
      cast off

    Takes the gangway up and lets go fore and aft. The quay stops being one step
    off the deck, and she answers her helm again.

    """

    key = "cast off"
    aliases = ("castoff", "undock", "unmoor")

    def at_helm(self, vessel):
        """
        Args:
            vessel (Vessel): The hull the caller is aboard.

        """
        if not vessel.docked:
            self.caller.msg("She is not made fast to anything.")
            return

        port = vessel.docked_at
        self.order(vessel, SINGLE_UP)

        vessel.let_go()

        self.order(vessel, LET_GO)
        if port:
            port.msg_contents(f"{vessel.key} takes in her gangway and casts off.")


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


class CmdAnchor(MaritimeCommand):
    """
    Let go the anchor.

    Usage:
      drop anchor
      anchor

    Brings the vessel up and holds her. She must have little enough way on to
    bring up safely - letting go with the ship still running is how cables part
    and anchors are lost.

    While anchored she will not answer her helm or make way, whatever canvas is
    set. Use `weigh anchor` to get under way again.
    """

    key = "drop anchor"
    aliases = ("anchor", "let go anchor", "come to anchor")

    def at_helm(self, vessel):
        """Let go, if she is quiet enough to bring up."""
        if vessel.anchored:
            self.caller.msg("She already lies to her anchor.")
            return
        if vessel.speed > MAX_ANCHORING_SPEED:
            self.caller.msg(
                f"She has too much way on - {ms_to_knots(vessel.speed):.1f} knots. "
                "Take the way off her first, or you will part the cable."
            )
            return

        vessel.anchored = True
        vessel.orders = HelmOrders(heading=vessel.orders.heading, speed=0.0)
        self.order(vessel, ANCHOR_ORDER)


class CmdWeighAnchor(MaritimeCommand):
    """
    Weigh the anchor and get under way.

    Usage:
      weigh anchor
      weigh

    Breaks the anchor out of the ground and brings it home. She will answer her
    helm again, though she will need canvas set and a wind to go anywhere.
    """

    key = "weigh anchor"
    aliases = ("weigh", "up anchor")

    def at_helm(self, vessel):
        """Break out the anchor."""
        if not vessel.anchored:
            self.caller.msg("The anchor is already catted; she is not brought up.")
            return

        vessel.anchored = False
        self.order(vessel, WEIGH_ORDER)


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
