"""
Compartments aboard a vessel.

A ship's room is an ordinary Evennia room that holds no position of its own. It names its
vessel, and the world-position resolver walks through to whatever the hull reports - which
is why moving a ship moves her whole company at once and a hundred passengers cost no more
than one.

Split out of `typeclasses.py` because a compartment is not a vessel, and because this is
where deck plans, stations, flooding order and compartment damage all land. `ShipRoom` is
still importable from `typeclasses` - see the note there.

"""

from evennia.objects.objects import DefaultExit, DefaultRoom
from evennia.utils import create

from .client.boundary import NoticesTheWaterline
from .observation import DEFAULT_HEIGHT_OF_EYE
from .ports import APPROACH_RANGE
from .position import WorldPosition
from .stowage import Stowed
from .vessel import EXPOSURES, INTERIOR, MAIN_DECK, WEATHER_DECKS


class ShipRoom(NoticesTheWaterline, Stowed, DefaultRoom):
    """
    A compartment aboard a vessel.

    Holds no position of its own. It names its vessel, and the world-position
    resolver walks through to whatever the hull reports - which is why a hundred
    people aboard cost nothing extra to move.

    Notes:
        `Stowed` makes any compartment a possible hold. One with no cargo capacity
        simply is not one, which is better than a separate hold typeclass:
        converting a cabin to cargo space in a refit is then setting a number
        rather than rebuilding the room.

    """

    def at_object_creation(self):
        """Set up a newly created compartment."""
        super().at_object_creation()
        self.db.vessel = None
        self.db.deck_level = MAIN_DECK
        self.db.exposure = INTERIOR
        self.db.height_of_eye = DEFAULT_HEIGHT_OF_EYE

    @property
    def vessel(self):
        """
        The hull this compartment belongs to.

        Returns:
            vessel (Vessel or None): Her ship.

        """
        return self.db.vessel

    @vessel.setter
    def vessel(self, vessel):
        """
        Args:
            vessel (Vessel or None): The hull to attach to, or None to detach.

        Notes:
            Maintains both sides of the link. The vessel keeps the list of her own
            compartments, so assigning `db.vessel` directly attaches nothing -
            use this.

        """
        previous = self.db.vessel
        if previous and previous.pk:
            previous.detach(self)
        self.db.vessel = vessel
        if vessel:
            vessel.attach(self)

    def return_appearance(self, looker, **kwargs):
        """
        Describe this compartment, and the sea outside it if there is one.

        Args:
            looker (Object): Whoever is looking.
            **kwargs: Passed through to Evennia's own description machinery.

        Returns:
            text (str): The room, then what is happening outside it.

        Notes:
            The room's own description says what is nailed down; a deck says the
            same thing in a gale off a lee shore as it does becalmed in harbour,
            and it should. Everything that changes is appended, and only for
            compartments open to the sky - there is no view from the hold.

        """
        appearance = super().return_appearance(looker, **kwargs)
        if self.exposure not in WEATHER_DECKS:
            return appearance

        vessel = self.vessel
        if vessel is None or vessel.maritime_position is None:
            return appearance

        outside = vessel.narrator.exterior(self)
        if not outside:
            return appearance
        return appearance + "\n\n" + " ".join(outside)

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
    def height_of_eye(self):
        """
        How high an observer standing here has their eye.

        Returns:
            height (float): Metres above the waterline.

        Notes:
            Set per compartment rather than derived from deck level, because the
            thing that makes a masthead worth manning is that it is nothing like
            a deck height above the water. A crosstree thirty metres up sees more
            than three times as far as a man on deck, and no formula over deck
            numbers would produce that.

        """
        height = self.db.height_of_eye
        return DEFAULT_HEIGHT_OF_EYE if height is None else float(height)

    @height_of_eye.setter
    def height_of_eye(self, metres):
        """
        Args:
            metres (float): Height above the waterline.

        """
        self.db.height_of_eye = float(metres)

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


class ShoreRoom(NoticesTheWaterline, DefaultRoom):
    """
    An ordinary room on land, which keeps a maritime client's map current.

    Notes:
        **Use this for the streets of a port town.** A land map is a picture of where the
        player is standing, so the one moment it certainly changes is the moment they stand
        somewhere else - and a room has to say so, because nothing else knows. A panel that
        is not told keeps its dot on a room the player has left, and since every click on
        the map is routed from that dot, the walk it works out begins somewhere they are
        not.

        There is nothing maritime about the room itself: no position, no berth, no water.
        It is a `DefaultRoom` that reports arrivals, and a game that already has its own
        room typeclass should mix `NoticesTheWaterline` into that instead of adopting this
        one - the mixin is the contract and this is the convenience.

        Only needed with `MARITIME_ASHORE_PANEL` on. With the panel off, maritime gets out
        of the way ashore and there is no map to keep current, so the hook resolves to
        nothing and costs a comparison.

    """

    #: Ashore by construction, so a builder does not also have to tag it.
    #:
    #: The tag is for marking somebody else's rooms as land. A room that *is* this type has
    #: already said what it is, and making it say so twice is how one of the two gets
    #: forgotten - which is what happened to the island tracks.
    maritime_ashore = True


class PortRoom(NoticesTheWaterline, DefaultRoom):
    """
    A quayside: ordinary room space that also stands somewhere on the water.

    Unlike a `ShipRoom`, this holds a position of its own. It is the one place
    where the two coordinate systems meet - walk in off the street and you are in
    a normal room; look out and you are at a set of real coordinates that a ship
    can be near.

    Notes:
        Inland rooms legitimately have no maritime position and that is not an
        error. A port is the exception, and the resolver finds it through the
        ordinary `location` link, so nothing standing on the quay needs to know
        it is special.

        **It notices the waterline, which for a long time it did not.** A quay is by
        definition the room on the landward side of a crossing, and it was the one room
        type in the contrib that never told anybody's client they had arrived. A ship's
        rooms did, so walking ashore raised the panel and drew a map - and then walking on
        to the quay next door left that map behind, still marked with the room the player
        had left. Clicking a street on it worked out a route from there, and the walk sent
        the first turning of somebody else's journey.

    """

    def at_object_creation(self):
        """Set up a newly created quayside."""
        super().at_object_creation()
        self.db.maritime_position = None
        self.db.berths = []

    @property
    def maritime_position(self):
        """
        Where this quay stands.

        Returns:
            position (WorldPosition or None): Her coordinates, or None if the
                port has not been placed yet.

        """
        return self.db.maritime_position

    @maritime_position.setter
    def maritime_position(self, position):
        """
        Args:
            position (WorldPosition): Where the quay is.

        Raises:
            TypeError: If it is not a `WorldPosition`.

        """
        if not isinstance(position, WorldPosition):
            raise TypeError(f"Expected a WorldPosition, got {type(position).__name__}.")
        self.db.maritime_position = position

    @property
    def berths(self):
        """
        Every berth at this quay.

        Returns:
            berths (tuple): `Berth` objects.

        """
        return tuple(self.db.berths or ())

    def add_berth(self, berth):
        """
        Add a berth to this quay.

        Args:
            berth (Berth): The berth.

        Returns:
            room (PortRoom): This room, for chaining.

        Raises:
            ValueError: If a berth of that key is already here. Two berths with
                one name is a booking system that cannot say where a ship is.

        Notes:
            Reads the whole list, appends and writes it back once. Mutating the
            stored list in place would commit on every touch - see Law 10.

        """
        existing = list(self.db.berths or ())
        if any(other.key == berth.key for other in existing):
            raise ValueError(f"{self.key} already has a berth called {berth.key!r}.")
        existing.append(berth)
        self.db.berths = existing
        return self

    def berth_named(self, key):
        """
        Args:
            key (str): The berth's identifier.

        Returns:
            berth (Berth or None): The berth, if this quay has one by that name.

        """
        for berth in self.berths:
            if berth.key.lower() == str(key).lower():
                return berth
        return None

    def occupant_of(self, berth):
        """
        Whoever is lying in a berth.

        Args:
            berth (Berth): The berth.

        Returns:
            vessel (Vessel or None): The hull made fast there, if any.

        """
        for vessel in self.db.moored or ():
            if vessel and vessel.berth_key == berth.key:
                return vessel
        return None

    def moor(self, vessel):
        """
        Record a vessel as lying here.

        Args:
            vessel (Vessel): The hull.

        Returns:
            room (PortRoom): This room, for chaining.

        """
        moored = [other for other in (self.db.moored or ()) if other and other != vessel]
        moored.append(vessel)
        self.db.moored = moored
        return self

    def cast_off(self, vessel):
        """
        Record a vessel as gone.

        Args:
            vessel (Vessel): The hull.

        Returns:
            room (PortRoom): This room, for chaining.

        """
        self.db.moored = [other for other in (self.db.moored or ()) if other and other != vessel]
        return self

    def __repr__(self):
        return f"<PortRoom {self.key} at {self.maritime_position}>"


def absent_from(room):
    """
    Characters who are logged out but belong in this room.

    Args:
        room (Object): The compartment to ask about.

    Returns:
        absent (tuple): Characters whose last location was here.

    Notes:
        **`room.contents` is not the list of people aboard.** Evennia takes an
        unpuppeted character off the grid entirely - `at_post_unpuppet` sets
        `location = None` and remembers the room in `prelogout_location` - so
        somebody who logged out in a cabin is in no room's contents at all. That
        was measured rather than assumed; see `docs/logout.md`.

        This matters most where it is least visible. Enumerating a ship's
        compartments to resolve everybody aboard before she is broken up would
        find every passenger who happened to be online and silently miss every
        one who was not.

        Implemented as an indexed query for off-grid objects, then a check in
        Python. The set of logged-out characters is small and the alternative -
        filtering on the attribute value - would mean matching Evennia's own
        packing of an object reference, which is an implementation detail and
        not a promise.

    """
    from evennia.objects.models import ObjectDB

    return tuple(
        obj
        for obj in ObjectDB.objects.filter(db_location__isnull=True)
        if obj.db.prelogout_location == room
    )


def everyone_in(room):
    """
    Everybody who belongs in a room, present or logged out.

    Args:
        room (Object): The compartment to ask about.

    Returns:
        occupants (tuple): Its contents, then whoever is stowed away from it.

    Notes:
        What "who is aboard" has to mean anywhere it decides a fate - flooding,
        capture, breaking a hull up. Exits are left out, since a gangway is not a
        passenger.

    """
    present = tuple(obj for obj in room.contents if not obj.destination)
    return present + absent_from(room)


def rig_gangway(deck, quay):
    """
    Put a gangway between a ship's deck and a quay.

    Args:
        deck (ShipRoom): The compartment the gangway lands on aboard.
        quay (PortRoom): The quayside it reaches.

    Returns:
        exits (tuple): The two exits created, ship-to-shore first.

    Notes:
        Two ordinary Evennia exits, and deliberately nothing cleverer. This is
        Law 7: a physical relationship creates a traversal, so walking ashore is
        walking, with all the ordinary consequences - it can be followed, blocked,
        watched and locked like any other exit, and none of that needed
        designing.

    """
    ashore = create.create_object(
        DefaultExit, key="gangway", aliases=["ashore"], location=deck, destination=quay
    )
    aboard = create.create_object(
        DefaultExit, key="gangway", aliases=["aboard"], location=quay, destination=deck
    )
    return ashore, aboard


def rig_grapples(own_deck, her_deck):
    """
    Put a crossing between two decks lashed alongside.

    Args:
        own_deck (ShipRoom): The deck the irons went from.
        her_deck (ShipRoom): The deck they went to.

    Returns:
        exits (tuple): The two exits created, outward first.

    Notes:
        The same two ordinary exits a gangway is, and for the same reason. Law 7
        does not have a special case for a hostile traversal: crossing to a ship
        you are boarding is walking, so it can be followed, blocked, watched and
        locked exactly like walking ashore, and none of that needed designing
        twice.

        Named for what a sailor would call them rather than for what they connect,
        because "the grapples" is what is about to be cut.

    """
    across = create.create_object(
        DefaultExit,
        key="grapples",
        aliases=["across", "board"],
        location=own_deck,
        destination=her_deck,
    )
    back = create.create_object(
        DefaultExit,
        key="grapples",
        aliases=["across", "back"],
        location=her_deck,
        destination=own_deck,
    )
    return across, back


def unrig_gangway(exits):
    """
    Take the gangway away.

    Args:
        exits (iterable): Exits to remove.

    Returns:
        removed (int): How many were actually deleted.

    Notes:
        Tolerant of exits that have already gone. A gangway can be destroyed by
        anything that deletes rooms, and refusing to cast off because one end has
        already vanished would strand a ship at a quay that no longer exists.

        Used for grapples too. Taking a crossing away is the same act whichever
        way it was made, and a second function that deleted exits slightly
        differently would be a second place for the same bug.

    """
    removed = 0
    for exit_object in tuple(exits or ()):
        if exit_object and exit_object.pk:
            exit_object.delete()
            removed += 1
    return removed


def berths_near(position, radius=APPROACH_RANGE):
    """
    Berths a vessel at this position could try for.

    Args:
        position (WorldPosition): Where she is.
        radius (float, optional): How far to look, in metres.

    Returns:
        berths (tuple): `(port, berth)` pairs, nearest berth first.

    Notes:
        A linear pass over every quay in the world. Fine for the number of ports
        a game has, and it would not be for the number of vessels - but ports do
        not move, so when this wants an index it will be a much simpler one than
        the vessel register.

    """
    found = []
    for port in PortRoom.objects.all():
        where = port.maritime_position
        if where is None or where.region != position.region:
            continue
        for berth in port.berths:
            distance = position.horizontal_distance_to(berth.position)
            if distance <= radius:
                found.append((distance, port, berth))
    found.sort(key=lambda item: item[0])
    return tuple((port, berth) for _distance, port, berth in found)


class Compartmented:
    """
    A vessel's own compartments.

    Notes:
        The link has two sides. `ShipRoom.vessel` maintains both, and this holds
        the list - which is what makes finding a ship's rooms a read rather than
        a query about typeclass path strings.

    """

    def at_object_creation(self):
        """Set up this part of a newly created vessel."""
        super().at_object_creation()
        self.db.compartments = []

    def attach(self, room):
        """
        Record a compartment as belonging to this hull.

        Args:
            room (ShipRoom): The compartment.

        Returns:
            vessel (Vessel): This hull, for chaining.

        Notes:
            Called by `ShipRoom.vessel`; there is no reason to call it directly.

        """
        rooms = [other for other in (self.db.compartments or ()) if other and other != room]
        rooms.append(room)
        self.db.compartments = rooms
        return self

    def detach(self, room):
        """
        Forget a compartment.

        Args:
            room (ShipRoom): The compartment.

        Returns:
            vessel (Vessel): This hull, for chaining.

        """
        self.db.compartments = [
            other for other in (self.db.compartments or ()) if other and other != room
        ]
        return self

    def reattach_compartments(self):
        """
        Rebuild the compartment list by looking for rooms that name this hull.

        Returns:
            count (int): How many compartments were found.

        Notes:
            The repair path, and the upgrade path. Compartments used to be found
            by asking the typeclass manager for every `ShipRoom` and filtering,
            which is a full table scan on every call and - worse - depends on the
            *string* Evennia stored in each row. Moving the class to another
            module left that string naming the old one, so the manager returned
            nothing at all while the rooms themselves loaded perfectly: a ship
            with compartments behaving exactly like a ship with none.

            This scans by type rather than by path, so it repairs both that and
            any game that set `db.vessel` directly before the link had two sides.
            Run once per vessel after upgrading.

        """
        from evennia import ObjectDB

        found = [
            room
            for room in ObjectDB.objects.all()
            if isinstance(room, ShipRoom) and room.db.vessel == self
        ]
        self.db.compartments = found
        return len(found)

    @property
    def ship_rooms(self):
        """
        Every compartment belonging to this vessel.

        Returns:
            rooms (tuple): The `ShipRoom` objects that name this vessel, ordered
                from the lowest deck upward.

        Notes:
            Read from a list the vessel keeps, not from a query. This is asked on
            every tick, and the query it replaced was a full pass over every ship
            room in the world - and one that silently returned nothing for rooms
            created before the class moved module.

            Lowest deck first, matching the deck-plan ordering, because that is
            the order flooding will care about.

        """
        rooms = [room for room in (self.db.compartments or ()) if room and room.pk]
        return tuple(sorted(rooms, key=lambda room: room.deck_level))

    def ships_company(self):
        """
        Everybody aboard her, logged in or not.

        Returns:
            aboard (tuple): Every character and object in her compartments,
                including those Evennia has stowed away on logout.

        Notes:
            The list that has to be resolved before she is ever broken up. Walking
            `room.contents` alone would miss every offline passenger, because an
            unpuppeted character is in no room at all - see `absent_from` and
            `docs/logout.md`.

        """
        aboard = []
        for room in self.ship_rooms:
            aboard.extend(everyone_in(room))
        return tuple(aboard)
