"""
Evennia typeclasses for vessels and their interiors.

Two objects, and the relationship between them is the whole point:

    Vessel     the thing that is somewhere. Holds the position.
    ShipRoom   a compartment. Holds no position, and points at its vessel.

A ship's cabin is not inside the hull by Evennia's containment - rooms have no location
at all - so a cabin names its vessel as its position source, and everyone standing in it
resolves through to wherever the hull has sailed. Nobody aboard stores a coordinate, so
moving the hull moves the entire ship's company at once, for free, with no bookkeeping.

**Position lives in memory and is checkpointed, not written per change.** Every assignment
to a `.db` attribute is a pickle and a database commit, and a vessel under way updates its
position constantly. Writing through on every change would make sailing the single most
expensive thing a server does. So the live value sits in `.ndb`, a dirty flag tracks
whether it has moved since the last save, and the value is flushed on reload, on shutdown,
and whenever something important happens.

That is Law 10 in practice: persistence is explicit, with defined moments, rather than a
side effect of assignment.

"""

from evennia.objects.objects import DefaultObject, DefaultRoom

from .motion import HelmOrders, MotionLimits, MotionState, advance
from .grounding import HOLED, SHOAL_WARNING_CLEARANCE, check_grounding, keel_clearance
from .sailing import (
    FURLED,
    steerage_floor,
    PolarCurve,
    WindVector,
    achievable_speed,
    leeway_angle,
    sail_plan,
)
from .position import WorldPosition, bearing_difference, normalize_bearing
from .vessel import EXPOSURES, INTERIOR, MAIN_DECK, OPEN, SEMI_EXPOSED

# Compass points, for describing a heading to someone who is not reading an
# instrument. Sixteen points is what a helmsman would actually call.
_COMPASS_POINTS = (
    "north",
    "north-northeast",
    "northeast",
    "east-northeast",
    "east",
    "east-southeast",
    "southeast",
    "south-southeast",
    "south",
    "south-southwest",
    "southwest",
    "west-southwest",
    "west",
    "west-northwest",
    "northwest",
    "north-northwest",
)

# Exposures from which someone can see the sea go by. Below deck you feel the
# motion but you do not watch the water, which is what makes an open deck worth
# standing on.
_WEATHER_DECKS = (OPEN, SEMI_EXPOSED)


def compass_point(bearing):
    """
    Describe a bearing the way a person would say it.

    Args:
        bearing (float): Compass bearing in degrees.

    Returns:
        name (str): One of the sixteen points, e.g. `"east-northeast"`.

    """
    index = int((bearing % 360.0) / 22.5 + 0.5) % 16
    return _COMPASS_POINTS[index]


class Vessel(DefaultObject):
    """
    A ship, as an Evennia object.

    This is the shell. The physics and rules live in the domain layer as plain
    Python; what this class adds is persistence, identity in the database, and the
    hooks that let Evennia tell it when the server is going away.

    """

    def at_object_creation(self):
        """Set up a newly created vessel."""
        super().at_object_creation()
        self.db.template_key = None
        self.db.maritime_position = None
        self.db.heading = 0.0
        self.db.speed = 0.0
        self.db.orders = HelmOrders()
        self.db.motion_limits = MotionLimits()
        self.db.sail_plan_key = FURLED.key
        self.db.anchored = False
        self.db.aground = False
        self.db.draft = 2.0
        self.db.polar_curve = PolarCurve()

    # --- position -----------------------------------------------------------

    @property
    def maritime_position(self):
        """
        Where this vessel is.

        Returns:
            position (WorldPosition or None): The live position if the vessel has
                moved since the last checkpoint, otherwise the saved one.

        Notes:
            Reads the in-memory value first. A vessel under way updates this many
            times a minute, and only the checkpoint touches the database.

        """
        live = self.ndb.maritime_position
        return live if live is not None else self.db.maritime_position

    @maritime_position.setter
    def maritime_position(self, position):
        """
        Move the vessel.

        Args:
            position (WorldPosition): The new position.

        Raises:
            TypeError: If given something that is not a `WorldPosition`. A tuple
                would survive here and fail much later inside a distance
                calculation, with nothing pointing back at the assignment.

        """
        if not isinstance(position, WorldPosition):
            raise TypeError(f"Expected a WorldPosition, got {type(position).__name__}.")
        self.ndb.maritime_position = position
        self.ndb.maritime_dirty = True

    @property
    def heading(self):
        """
        The vessel's heading, as a compass bearing.

        Returns:
            heading (float): Degrees, where north is 0 and east is 90.

        """
        live = self.ndb.heading
        return live if live is not None else (self.db.heading or 0.0)

    @heading.setter
    def heading(self, degrees):
        """
        Args:
            degrees (float): New heading. Wrapped into [0, 360).

        """
        self.ndb.heading = normalize_bearing(float(degrees))
        self.ndb.maritime_dirty = True

    @property
    def speed(self):
        """
        How fast she is actually going.

        Returns:
            speed (float): Metres per second. Not necessarily what was ordered.

        """
        live = self.ndb.speed
        return live if live is not None else (self.db.speed or 0.0)

    @speed.setter
    def speed(self, metres_per_second):
        """
        Args:
            metres_per_second (float): The new speed.

        Raises:
            ValueError: If negative. Ships do not travel astern; order a
                reciprocal heading instead.

        """
        value = float(metres_per_second)
        if value < 0.0:
            raise ValueError(f"Speed cannot be negative, got {value!r}.")
        self.ndb.speed = value
        self.ndb.maritime_dirty = True

    # --- orders -------------------------------------------------------------

    @property
    def orders(self):
        """
        What the helm has been told to do.

        Returns:
            orders (HelmOrders): The standing order. Targets, not instructions -
                the hull works towards them at whatever rate she can manage.

        """
        return self.db.orders or HelmOrders()

    @orders.setter
    def orders(self, orders):
        """
        Args:
            orders (HelmOrders): The new standing order.

        Raises:
            TypeError: If given anything else.

        Notes:
            Written straight to the database rather than held in memory. An order
            is given occasionally by a person, unlike position which changes many
            times a minute, so there is nothing to batch.

        """
        if not isinstance(orders, HelmOrders):
            raise TypeError(f"Expected HelmOrders, got {type(orders).__name__}.")
        self.db.orders = orders

    @property
    def motion_limits(self):
        """
        What this hull is physically capable of.

        Returns:
            limits (MotionLimits): Speed, acceleration and turn rate.

        """
        return self.db.motion_limits or MotionLimits()

    @motion_limits.setter
    def motion_limits(self, limits):
        """
        Args:
            limits (MotionLimits): The hull's capabilities.

        Raises:
            TypeError: If given anything else.

        """
        if not isinstance(limits, MotionLimits):
            raise TypeError(f"Expected MotionLimits, got {type(limits).__name__}.")
        self.db.motion_limits = limits

    @property
    def anchored(self):
        """
        Whether she lies to her anchor.

        Returns:
            anchored (bool): True if brought up.

        """
        return bool(self.db.anchored)

    @anchored.setter
    def anchored(self, value):
        """
        Args:
            value (bool): Whether she is brought up.

        """
        self.db.anchored = bool(value)

    @property
    def draft(self):
        """
        How deep she sits.

        Returns:
            draft (float): Metres.

        Notes:
            The light draft for now. Cargo, flooding and heel will make the
            working figure a derived one, which is why grounding takes it as an
            argument rather than reading a template.

        """
        return float(self.db.draft or 0.0)

    @draft.setter
    def draft(self, metres):
        """
        Args:
            metres (float): How deep she sits.

        """
        self.db.draft = float(metres)

    @property
    def aground(self):
        """
        Whether the hull is in the ground.

        Returns:
            aground (bool): True if she has found the bottom.

        """
        return bool(self.db.aground)

    @aground.setter
    def aground(self, value):
        """
        Args:
            value (bool): Whether she is aground.

        """
        self.db.aground = bool(value)

    def map_here(self):
        """
        The world's terrain.

        Returns:
            provider (MaritimeMapProvider): The configured map.

        """
        from . import config

        return config.map_provider()

    def keel_clearance(self):
        """
        How much water she has under her.

        Returns:
            clearance (float or None): Metres between keel and ground, or None if
                she has not been launched.

        """
        position = self.maritime_position
        if position is None:
            return None
        from . import config

        return keel_clearance(position, self.draft, self.map_here(), config.time_provider().now())

    # --- rig ----------------------------------------------------------------

    @property
    def sail_plan(self):
        """
        How much canvas is set.

        Returns:
            plan (SailPlan): The current sail plan. Bare poles by default - a
                vessel does not put to sea with sail already set.

        """
        return sail_plan(self.db.sail_plan_key or FURLED.key) or FURLED

    @sail_plan.setter
    def sail_plan(self, plan):
        """
        Args:
            plan (SailPlan): The plan to set.

        """
        self.db.sail_plan_key = plan.key

    @property
    def polar_curve(self):
        """
        How this rig drives at each angle off the wind.

        Returns:
            curve (PolarCurve): The hull's performance data.

        """
        return self.db.polar_curve or PolarCurve()

    @polar_curve.setter
    def polar_curve(self, curve):
        """
        Args:
            curve (PolarCurve): The rig's polar data.

        """
        self.db.polar_curve = curve

    def wind_here(self):
        """
        The wind where this vessel is.

        Returns:
            wind (WindVector): The local wind.

        Notes:
            A single world wind for now, from `MARITIME_WIND_BEARING` and
            `MARITIME_WIND_SPEED`. A weather provider replaces this later; the
            call site does not change when it does.

        """
        from . import config

        return WindVector(
            bearing=float(config.get_setting("WIND_BEARING", 0.0)),
            speed=float(config.get_setting("WIND_SPEED", 0.0)),
        )

    def sailing_speed(self):
        """
        The best speed she can make as she is currently set.

        Returns:
            speed (float): Metres per second.

        Notes:
            Replaces the ordered speed when under sail. A sailing vessel is not
            asked how fast to go; she goes as fast as the wind on this heading
            allows, which on some headings is not at all.

        """
        return achievable_speed(
            self.heading,
            self.wind_here(),
            self.sail_plan,
            self.polar_curve,
            self.motion_limits,
        )

    # --- simulation ---------------------------------------------------------

    def at_maritime_tick(self, elapsed):
        """
        Advance this vessel through a stretch of game time.

        Args:
            elapsed (float): Game seconds since her last update.

        Returns:
            moved (bool): True if she went anywhere.

        Notes:
            Called by the simulation service, never directly. A vessel with no
            position is not under way - she has not been launched - so there is
            nothing to advance.

        """
        position = self.maritime_position
        if position is None:
            return False
        if self.aground:
            # Held by the ground. Canvas and helm will not shift her; getting off
            # is a separate act, which is the point of running aground.
            if self.speed:
                self.ndb.speed = 0.0
                self.ndb.maritime_dirty = True
            return False
        if self.anchored:
            # She is held by the ground. Canvas and helm make no difference until
            # the anchor is weighed - which is the whole point of letting it go.
            if self.speed:
                self.ndb.speed = 0.0
                self.ndb.maritime_dirty = True
            return False

        before = MotionState(position=position, heading=self.heading, speed=self.speed)

        orders = self.orders
        wind = self.wind_here()
        under_sail = self.sail_plan.area > 0.0 and wind.speed > 0.0
        if under_sail:
            orders = HelmOrders(heading=orders.heading, speed=self.sailing_speed())

        limits = self.motion_limits
        if under_sail:
            # A crew with canvas aloft can back a sail to shove her bow round,
            # so she is never wholly without steering.
            floor = steerage_floor(wind, self.sail_plan)
            if floor > 0.0 and before.speed < limits.max_speed:
                needed = floor * limits.max_speed / max(before.speed, 1e-9)
                limits = MotionLimits(
                    max_speed=limits.max_speed,
                    acceleration=limits.acceleration,
                    turn_rate=max(limits.turn_rate, min(needed, limits.turn_rate * 20.0)),
                )

        after = advance(before, orders, limits, elapsed)

        if under_sail and after.speed > 0.0:
            slip = leeway_angle(after.heading, wind, self.sail_plan, after.speed)
            if slip:
                # She points one way and travels another. Correct the track
                # rather than the heading - her head really is where it was.
                travelled = before.position.horizontal_distance_to(after.position)
                after = MotionState(
                    position=before.position.moved(after.heading + slip, travelled),
                    heading=after.heading,
                    speed=after.speed,
                )
        if after == before:
            return False

        from . import config

        world = self.map_here()
        now = config.time_provider().now()

        # A surface vessel floats. Her elevation is decided by the water, not by
        # anything she does, so it is set rather than integrated - which is why
        # she cannot be sailed down to the seabed by assigning a negative z.
        floating = after.position.with_z(world.sea_surface_z_at(after.position, now))
        after = MotionState(position=floating, heading=after.heading, speed=after.speed)

        contact = check_grounding(floating, self.draft, after.speed, world, now)

        self.ndb.maritime_position = floating
        self.ndb.heading = after.heading
        self.ndb.maritime_dirty = True

        if not contact:
            self.ndb.speed = 0.0
            self.aground = True
            self._report_grounding(contact)
            return True

        self.ndb.speed = after.speed
        self._report_underway(before, after)
        self._report_soundings(contact)
        return True

    def _report_grounding(self, contact):
        """
        Tell the ship she has found the bottom.

        Args:
            contact (GroundingResult): What she struck and how hard.

        """
        if contact.severity == HOLED:
            topside = (
                "A grinding crash runs the length of her. She stops dead, canted "
                "over, and the sound of water is suddenly very loud."
            )
            below = "The hull screams against rock, and water bursts in through the seams."
        else:
            topside = (
                f"She slides to a halt with a long shudder, aground on "
                f"{contact.bottom}. The deck tilts, and stays tilted."
            )
            below = f"The hull grinds and settles. She is aground on {contact.bottom}."

        for room in self.ship_rooms:
            room.msg_contents(topside if room.exposure in _WEATHER_DECKS else below)

    def _report_soundings(self, contact):
        """
        Warn the ship when the water shoals beneath her.

        Args:
            contact (GroundingResult): The clearance she currently has.

        Notes:
            A vessel that grounds without warning is an accident; one that grounds
            after the leadsman has called diminishing water is a decision, and
            only the second is worth playing. Warned once on entering shallow
            water, not every tick, for the same reason turns are.

        """
        if contact.clearance >= SHOAL_WARNING_CLEARANCE:
            self.ndb.reported_shoaling = False
            return
        if self.ndb.reported_shoaling:
            return
        self.ndb.reported_shoaling = True

        call = (
            f"The leadsman calls the depth: {contact.clearance:.1f} metres "
            f"under her keel, and shoaling."
        )
        for room in self.ship_rooms:
            room.msg_contents(call)

    def _report_underway(self, before, after):
        """
        Tell anyone aboard what the ship is doing.

        Args:
            before (MotionState): State at the start of the step.
            after (MotionState): State at the end of it.

        Notes:
            Reports *transitions*, not conditions. A ship announces that she is
            coming round, and again when she is steady - not that she is still
            turning, every two seconds, for the whole minute it takes. Reporting
            a condition rather than a change is how ambient messaging turns into
            noise that players learn to scroll past.

            What reaches a person depends on where they stand. On deck you watch
            the sea go by; below, you feel her heel and hear the water on the
            planking but see none of it.

        """
        turning = abs(after.heading - before.heading) > 1e-6
        on_course = abs(bearing_difference(after.heading, self.orders.heading)) < 1e-6
        under_way = after.speed > 0.0
        gathering = after.speed > before.speed
        at_ordered_speed = under_way and abs(after.speed - self.orders.speed) < 1e-6

        was_turning = bool(self.ndb.reported_turning)
        was_at_speed = bool(self.ndb.reported_at_speed)
        was_under_way = bool(self.ndb.reported_under_way)

        topside = below = None

        if turning and not was_turning:
            side = "starboard" if bearing_difference(before.heading, after.heading) > 0 else "port"
            topside = f"The deck leans as she comes round to {side}."
            below = f"You feel her heel over, coming round to {side}."
            self.ndb.reported_turning = True
        elif was_turning and on_course and not turning:
            spoken = "-".join(f"{int(round(after.heading)) % 360:03d}")
            point = compass_point(after.heading)
            topside = (
                f'The helmsman reports, "Vessel steady on {spoken} now, sir." '
                f"She runs {point}, the sea sliding past her rail."
            )
            below = f'The call carries down from the helm: "Steady on {spoken}, sir."'
            self.ndb.reported_turning = False
        elif at_ordered_speed and gathering and not was_at_speed:
            topside = "She settles into her stride, water curling steadily from the bow."
            below = "The working of the hull settles into a steady rhythm."
            self.ndb.reported_at_speed = True
        elif was_under_way and not under_way:
            topside = "The last of her way falls off. She lies quiet on the water."
            below = "The sound of water along the planking dies away."

        if not at_ordered_speed:
            self.ndb.reported_at_speed = False
        self.ndb.reported_under_way = under_way

        if topside is None:
            return

        for room in self.ship_rooms:
            message = topside if room.exposure in _WEATHER_DECKS else below
            if message:
                room.msg_contents(message)

    # --- persistence --------------------------------------------------------

    def checkpoint(self):
        """
        Write live state to the database, if it has changed.

        Returns:
            saved (bool): True if anything was written.

        Notes:
            Skips the write entirely when nothing has moved. Re-saving an
            unchanged value still costs a pickle and a commit, and a fleet sitting
            at anchor would otherwise pay that on every checkpoint.

        """
        if not self.ndb.maritime_dirty:
            return False
        if self.ndb.maritime_position is not None:
            self.db.maritime_position = self.ndb.maritime_position
        if self.ndb.heading is not None:
            self.db.heading = self.ndb.heading
        if self.ndb.speed is not None:
            self.db.speed = self.ndb.speed
        self.ndb.maritime_dirty = False
        return True

    def at_server_reload(self):
        """Flush live state before the server restarts."""
        super().at_server_reload()
        self.checkpoint()

    def at_server_shutdown(self):
        """Flush live state before the server stops."""
        super().at_server_shutdown()
        self.checkpoint()

    # --- interior -----------------------------------------------------------

    @property
    def ship_rooms(self):
        """
        Every compartment belonging to this vessel.

        Returns:
            rooms (tuple): The `ShipRoom` objects that name this vessel, ordered
                from the lowest deck upward.

        Notes:
            Lowest first, matching the deck-plan ordering, because that is the
            order flooding will care about.

        """
        rooms = [room for room in ShipRoom.objects.all() if room.db.vessel == self]
        return tuple(sorted(rooms, key=lambda room: room.deck_level))

    def __repr__(self):
        return f"<Vessel {self.key} at {self.maritime_position}>"


class ShipRoom(DefaultRoom):
    """
    A compartment aboard a vessel.

    Holds no position of its own. It names its vessel, and the world-position
    resolver walks through to whatever the hull reports - which is why a hundred
    people aboard cost nothing extra to move.

    """

    def at_object_creation(self):
        """Set up a newly created compartment."""
        super().at_object_creation()
        self.db.vessel = None
        self.db.deck_level = MAIN_DECK
        self.db.exposure = INTERIOR

    @property
    def maritime_position_source(self):
        """
        The vessel this compartment belongs to.

        Returns:
            vessel (Vessel or None): The hull, which is what actually has a
                position.

        Notes:
            This is the hook the resolver follows. A ship's room is not contained
            by the hull in Evennia's sense, so ordinary location would never lead
            here.

        """
        return self.db.vessel

    @property
    def deck_level(self):
        """
        Which deck this compartment is on.

        Returns:
            level (int): Relative to the main deck. Negative is below.

        """
        level = self.db.deck_level
        return MAIN_DECK if level is None else level

    @deck_level.setter
    def deck_level(self, level):
        """
        Args:
            level (int): The new deck level.

        """
        self.db.deck_level = int(level)

    @property
    def exposure(self):
        """
        How sheltered this compartment is.

        Returns:
            exposure (str): One of the exposure levels.

        """
        return self.db.exposure or INTERIOR

    @exposure.setter
    def exposure(self, exposure):
        """
        Args:
            exposure (str): One of the known exposure levels.

        Raises:
            ValueError: If the value is not a known exposure. An unknown value
                would silently exclude the room from weather and flooding, which
                looks like those systems failing rather than a bad setting.

        """
        if exposure not in EXPOSURES:
            raise ValueError(f"Exposure must be one of {EXPOSURES}, got {exposure!r}.")
        self.db.exposure = exposure

    def __repr__(self):
        return f"<ShipRoom {self.key} deck {self.deck_level}>"
