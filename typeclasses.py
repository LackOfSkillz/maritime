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
from .position import WorldPosition, normalize_bearing
from .vessel import EXPOSURES, INTERIOR, MAIN_DECK


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

        before = MotionState(position=position, heading=self.heading, speed=self.speed)
        after = advance(before, self.orders, self.motion_limits, elapsed)
        if after == before:
            return False

        self.ndb.maritime_position = after.position
        self.ndb.heading = after.heading
        self.ndb.speed = after.speed
        self.ndb.maritime_dirty = True
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
