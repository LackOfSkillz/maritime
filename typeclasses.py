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
from .navigation import Navigator, reckon
from .grounding import check_grounding
from .observation import Lookout
from .sailing import Rigged, steerage_floor, leeway_angle
from .position import WorldPosition, normalize_bearing
from .environment import Situated
from .ports import Berthing
from .traffic import traffic

# ShipRoom lives in rooms.py now, and is imported here for `ship_rooms` below - but
# also re-exported deliberately. Evennia stores a typeclass as a dotted path on the
# row, so every compartment already created in every game that has run this contrib
# has this module's name written into its database. Dropping the name here would not
# fail at startup; it would produce rooms that fail to resolve their typeclass one at
# a time as they are loaded, which is a considerably worse way to find out.
from .rooms import Compartmented, ShipRoom  # noqa: F401


class Vessel(Navigator, Berthing, Lookout, Rigged, Situated, Compartmented, DefaultObject):
    """
    A ship, as an Evennia object.

    This is the shell. The physics and rules live in the domain layer as plain
    Python; what this class adds is persistence, identity in the database, and the
    hooks that let Evennia tell it when the server is going away.

    """

    def at_object_creation(self):
        """
        Set up a newly created vessel.

        Notes:
            Only what a hull has regardless of what it does. Each mixin sets its
            own defaults through the same chain, so a concern's state is
            initialised in the file that owns it rather than in one list here
            that everything has to remember to edit.

        """
        super().at_object_creation()
        self.db.template_key = None
        self.db.maritime_position = None
        self.db.heading = 0.0
        self.db.speed = 0.0
        self.db.orders = HelmOrders()
        self.db.motion_limits = MotionLimits()
        self.db.anchored = False
        self.db.aground = False
        self.db.draft = 2.0

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

    # --- rig ----------------------------------------------------------------

    # --- simulation ---------------------------------------------------------

    #: What stops a hull answering her helm. Lines ashore, the ground under her,
    #: or her own anchor - canvas and rudder make no difference to any of them,
    #: and each is undone by a different act with its own name.
    HELD_FAST = ("docked", "aground", "anchored")

    def held_by(self):
        """
        What is holding her, if anything.

        Returns:
            reason (str or None): One of `HELD_FAST`, or None if she is free.

        """
        for reason in self.HELD_FAST:
            if getattr(self, reason):
                return reason
        return None

    def take_way_off(self):
        """
        Stop her, if she is still carrying way.

        Returns:
            stopped (bool): True if there was way to take off.

        """
        if not self.speed:
            return False
        self.ndb.speed = 0.0
        self.ndb.maritime_dirty = True
        return True

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

        if self.held_by():
            self.take_way_off()
            return False

        before = MotionState(position=position, heading=self.heading, speed=self.speed)

        orders = self.orders
        wind = self.wind_here()
        under_sail = self.sail_plan.area > 0.0 and wind.speed > 0.0
        if under_sail:
            orders = HelmOrders(heading=orders.heading, speed=self.sailing_speed())

        # A crew with canvas aloft can back a headsail to shove her bow round, so
        # she is never wholly without steering. This goes in as a turn floor
        # rather than as a raised turn rate: the rate is scaled by speed, being a
        # rudder, and a backed sail is not - which matters precisely when she is
        # stopped dead and pointing the wrong way.
        floor = steerage_floor(wind, self.sail_plan) if under_sail else 0.0
        after = advance(before, orders, self.motion_limits, elapsed, turn_floor=floor)

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

        # Course steered and distance logged, and nothing else. The gap this
        # opens against the truth is the current and the leeway - which is not a
        # penalty applied to the crew but the two things they cannot see.
        dr = self.dead_reckoning
        if dr is not None:
            self.dead_reckoning = reckon(dr, after.heading, after.speed, elapsed)

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

    def __repr__(self):
        return f"<Vessel {self.key} at {self.maritime_position}>"
