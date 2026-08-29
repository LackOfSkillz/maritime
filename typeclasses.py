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

from evennia.objects.objects import DefaultObject

from .motion import HelmOrders, MotionLimits, MotionState, advance
from .currents import STILL
from .grounding import check_grounding
from .observation import DEFAULT_HEIGHT_OF_EYE
from .sailing import (
    FURLED,
    steerage_floor,
    PolarCurve,
    achievable_speed,
    leeway_angle,
    sail_plan,
)
from .position import WorldPosition, normalize_bearing
from .traffic import traffic

# ShipRoom lives in rooms.py now, and is imported here for `ship_rooms` below - but
# also re-exported deliberately. Evennia stores a typeclass as a dotted path on the
# row, so every compartment already created in every game that has run this contrib
# has this module's name written into its database. Dropping the name here would not
# fail at startup; it would produce rooms that fail to resolve their typeclass one at
# a time as they are loaded, which is a considerably worse way to find out.
from .rooms import ShipRoom
from .vessel import WEATHER_DECKS


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
        self.db.air_draft = 12.0
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

    def wind_here(self):
        """
        The wind where this vessel is.

        Returns:
            wind (WindVector): The local wind.

        """
        from . import environment

        return environment.wind_at(self.maritime_position)

    def current_here(self):
        """
        The current where this vessel is.

        Returns:
            current (CurrentVector): Set and drift, or slack water if she has not
                been launched.

        """
        from . import config, environment

        position = self.maritime_position
        if position is None:
            return STILL
        return environment.current_at(position, config.time_provider().now())

    def keel_clearance(self):
        """
        How much water she has under her.

        Returns:
            clearance (float or None): Metres between keel and ground, or None if
                she has not been launched.

        """
        from . import config, environment

        position = self.maritime_position
        if position is None:
            return None
        return environment.clearance_at(position, self.draft, config.time_provider().now())

    def made_good(self):
        """
        Where she is actually going, and how fast.

        Returns:
            track (tuple or None): `(course, speed)` over the ground, or None if
                she has not been launched.

        Notes:
            Not the same as heading and speed, and the difference is the whole
            reason currents exist. `speed` is speed through the water - what a
            log line measures - so a vessel set sideways by a stream is making
            good a course she is not pointing at, at a speed she is not sailing.

        """
        from . import config, environment

        position = self.maritime_position
        if position is None:
            return None
        _current, course, made = environment.set_and_drift(
            position, self.heading, self.speed, config.time_provider().now()
        )
        return course, made

    @property
    def narrator(self):
        """
        The layer that turns what happens to her into what people hear.

        Returns:
            narrator (VesselNarrator): The configured narrator, bound to this
                hull.

        Notes:
            Built on demand rather than held, so a game that changes
            `MARITIME_NARRATOR` and reloads gets the new one without every
            existing vessel carrying a stale reference.

        """
        from . import config

        return config.narrator_class()(self)

    @property
    def air_draft(self):
        """
        How high she stands above the water.

        Returns:
            air_draft (float): Metres from the waterline to her highest point.

        Notes:
            Her masthead, not her deck. This is what decides how far away someone
            else can see her, and it is the same number that will decide whether
            she fits under a bridge - which is why it is height above the water
            and not height overall.

        """
        return float(self.db.air_draft or 0.0)

    @air_draft.setter
    def air_draft(self, metres):
        """
        Args:
            metres (float): Height above the waterline.

        """
        self.db.air_draft = float(metres)

    @property
    def height_of_eye(self):
        """
        How high this ship's own lookout sees from.

        Returns:
            height (float): Metres above the waterline.

        Notes:
            The highest weather deck she has, because that is where a lookout
            would stand. Building a masthead compartment therefore buys real
            range rather than flavour, and a ship with nothing but a main deck
            sees like a small boat - which she is.

        """
        heights = [room.height_of_eye for room in self.ship_rooms if room.exposure in WEATHER_DECKS]
        return max(heights) if heights else DEFAULT_HEIGHT_OF_EYE

    def contacts(self, height_of_eye=None):
        """
        What can be seen from this hull.

        Args:
            height_of_eye (float, optional): How high the observer's eye is, in
                metres above the waterline. Defaults to her own lookout's.

        Returns:
            sightings (tuple): `Sighting` objects, nearest first.

        Notes:
            Two phases. The register supplies candidates within the furthest
            anything could possibly be seen from this height, and each candidate
            is then tested against its own height - so a low boat and a tall ship
            at the same range get different answers, which is the entire point.

        """
        from . import environment

        position = self.maritime_position
        if position is None:
            return ()
        if height_of_eye is None:
            height_of_eye = self.height_of_eye
        candidates = environment.vessels_within_sight(position, height_of_eye, exclude=self)
        return environment.contacts_from(position, self.heading, height_of_eye, candidates)

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

        # Kept up to date before anything else, and whether or not she moves. A
        # ship at anchor is still visible, and still has a lookout.
        traffic().note(self, position)
        self.narrator.sightings(self.contacts())

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

        from . import config, environment

        world = self.map_here()
        now = config.time_provider().now()

        # The water is moving too. She is carried in addition to whatever she is
        # making through it, which is why her speed is untouched here - a log
        # line measures the water going past the hull, not the ground going past
        # the ship.
        after = MotionState(
            position=environment.carried_from(after.position, now, elapsed),
            heading=after.heading,
            speed=after.speed,
        )

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
            self.narrator.grounding(contact)
            return True

        self.ndb.speed = after.speed
        narrator = self.narrator
        narrator.underway(before, after)
        narrator.soundings(contact)
        return True

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

    def at_object_delete(self):
        """
        Take her off the register on the way out.

        Returns:
            proceed (bool): True, always - nothing here can refuse a deletion.

        Notes:
            The register is memory, not a foreign key, so nothing removes her
            from it when her row goes. A hull that sinks and is deleted would
            otherwise stay visible on the horizon indefinitely, which is a
            haunting rather than a feature.

        """
        traffic().forget(self)
        return super().at_object_delete()

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
