"""
Open water as somewhere a player can stand.

A ship solves this by being a place: her compartments are ordinary rooms, they never move,
and the hull underneath them carries the lot. Someone in the water has no such room. They
need one, and there is no sense in building rooms for an ocean nobody is in.

So the ocean is projected: a small pool of rooms, each one lent to whatever square of water
currently has somebody in it, and taken back when they leave. The rooms are the same rooms.
A pool of six will serve a whole sea, because the number of rooms needed is the number of
occupied cells, not the size of the ocean.

**The room is a view, not a location.** This is the one thing to hold on to, and it is what
separates this from Evennia's `wilderness` contrib, which was read closely before any of this
was written. There, the room *is* where you are - so recycling one has to preserve whatever
was inside it, and the contrib's own docstring warns that objects left behind end up with
`location = None`. Here a swimmer's truth is their `maritime_position`, held on the swimmer.
The room only shows the cell that position falls in. Releasing a room therefore loses
nothing: place the swimmer again and the projection hands back a room showing the same water.

That inversion pays for itself twice more:

    drift is not movement    a floating thing changes position every tick and only
                             changes room on the few ticks it crosses a cell boundary
    contacts are not local   what you can see from the water is computed from the
                             position, so it is unaffected by which room is lending it

**The pool is found by tag, not by typeclass.** `OceanRoom.objects.all()` filters on the
typeclass *path stored on the row*, so moving or renaming the class silently empties the
pool - which is a bug this contrib has already had once, in another module, and does not
intend to have again. A tag is a foreign key to a room and survives anything done to the
class.

"""

from evennia.objects.objects import DefaultRoom
from evennia.utils import create

from .resolver import NoWorldPosition, get_world_position
from .spatial import cell_centre, cell_of

# How wide a projected cell is, in metres. A hundred metres is about as far as you can
# usefully throw a line, which makes "in the same cell" mean roughly "close enough to
# be helped" - the only question the granularity actually has to answer.
CELL_SIZE = 100.0

# Tag category marking a room as belonging to the pool. Deliberately not a typeclass
# query - see the module docstring.
POOL_CATEGORY = "maritime_projection"

# Tag key every pool room carries. The category alone would do; the key makes the tag
# readable in `@py` and in the admin, where a bare category reads as a mystery.
POOL_TAG = "ocean"

# What a freshly built pool room is called before anybody sees it.
POOL_ROOM_KEY = "Open water"


class OceanRoom(DefaultRoom):
    """
    A room lent to one square of open water.

    Notes:
        Holds no world position of its own beyond the cell it is currently
        showing, and that changes as the pool reassigns it. Nothing should ever
        be stored here that it would hurt to lose, because the room will be
        showing different water within the hour.

    """

    def at_object_creation(self):
        """Set up a newly built pool room."""
        super().at_object_creation()
        self.db.showing = None
        self.tags.add(POOL_TAG, category=POOL_CATEGORY)

    @property
    def showing(self):
        """
        Returns:
            cell (tuple or None): The cell this room is currently lent to, or
                None if it is free.

        """
        return self.db.showing

    @showing.setter
    def showing(self, cell):
        """
        Args:
            cell (tuple or None): The cell to show, or None to return the room to
                the pool.

        Notes:
            Only ever written when the value changes. Every attribute assignment
            in Evennia is a pickle and a commit, and a projection that reassigned
            the same cell on every tick would be writing to the database for the
            privilege of changing nothing - see Law 10.

        """
        if self.db.showing != cell:
            self.db.showing = cell

    @property
    def maritime_position(self):
        """
        Returns:
            position (WorldPosition or None): The centre of the cell on show, or
                None while the room is free.

        Notes:
            Read by the resolver, and only for things in the water that have no
            position of their own - flotsam a game has not given one to, or a
            character being placed for the first time. Anything that *does* carry
            a position resolves to that instead, and should: the room is a
            hundred metres wide and the sea does not round off.

        """
        cell = self.db.showing
        return None if cell is None else cell_centre(tuple(cell), CELL_SIZE)

    def return_appearance(self, looker, **kwargs):
        """
        Describe the water, and what can be seen across it.

        Args:
            looker (Object): Whoever is looking.
            **kwargs: Passed through to Evennia's description machinery.

        Returns:
            text (str): The sea from surface level.

        Notes:
            There is nothing here to describe but the sea, so unlike a deck this
            is not an ordinary description with the weather appended - it is the
            weather. A pool room's own `db.desc` is left alone deliberately, since
            whatever it said would be a description of somewhere the room stopped
            being some time ago.

        """
        from . import config

        position = get_world_position(looker)
        if position is NoWorldPosition:
            position = self.maritime_position
        if position is None:
            return super().return_appearance(looker, **kwargs)
        return "\n".join(config.water_narrator_class()(position, looker).surface())


class OceanProjection:
    """
    Lends rooms to occupied water and takes them back.

    Notes:
        Holds no state of its own. Everything it needs - which rooms exist, and
        what each is showing - lives on the rooms, so two projections built a
        tick apart agree, and one built after a reload knows everything the last
        one did.

    """

    def __init__(self, cell_size=CELL_SIZE, room_typeclass=None, room_key=POOL_ROOM_KEY):
        """
        Args:
            cell_size (float, optional): How wide a projected cell is, in metres.
            room_typeclass (str or type, optional): What to build pool rooms
                from. Defaults to `OceanRoom`.
            room_key (str, optional): The name new pool rooms are given.

        Raises:
            ValueError: If `cell_size` is not positive. A zero-width cell would
                divide by zero on the first placement; a negative one would run
                the grid backwards, which is worse, because it would work.

        """
        if cell_size <= 0.0:
            raise ValueError(f"cell_size must be positive, got {cell_size!r}.")
        self.cell_size = float(cell_size)
        self.room_typeclass = room_typeclass or OceanRoom
        self.room_key = room_key

    # --- the pool -----------------------------------------------------------

    def pool(self):
        """
        Every room in the pool, lent or free.

        Returns:
            rooms (tuple): The pool rooms.

        Notes:
            A tag query, not a typeclass one. See the module docstring for the
            bug this avoids.

        """
        from evennia.objects.models import ObjectDB

        return tuple(ObjectDB.objects.get_by_tag(key=POOL_TAG, category=POOL_CATEGORY))

    def room_showing(self, cell):
        """
        The room already lent to a cell, if any.

        Args:
            cell (tuple): `(region, x_index, y_index)`.

        Returns:
            room (OceanRoom or None): The room, or None if that water has nobody
                in it.

        Notes:
            Scans the pool in Python rather than querying an attribute, because
            the pool is small by construction - one room per *occupied* cell -
            and an attribute query on a pickled tuple is neither indexed nor
            reliable across the several shapes a tuple can be stored in.

        """
        for room in self.pool():
            if room.db.showing is not None and tuple(room.db.showing) == tuple(cell):
                return room
        return None

    def free_room(self):
        """
        A pool room currently showing nothing.

        Returns:
            room (OceanRoom or None): A free room, or None if all are lent out.

        """
        for room in self.pool():
            if room.db.showing is None:
                return room
        return None

    def build_room(self):
        """
        Add a room to the pool.

        Returns:
            room (OceanRoom): The new room, free and unassigned.

        Notes:
            Called only when every existing room is lent out, so the pool grows to
            the high-water mark of simultaneously occupied cells and then stops.
            It is never shrunk: rooms are cheap to keep and the mark is a
            reasonable guess at what the game will need again.

        """
        return create.create_object(self.room_typeclass, key=self.room_key)

    def room_for(self, cell):
        """
        The room showing a cell, lending or building one if need be.

        Args:
            cell (tuple): `(region, x_index, y_index)`.

        Returns:
            room (OceanRoom): A room showing that water.

        """
        cell = tuple(cell)
        room = self.room_showing(cell)
        if room is not None:
            return room
        room = self.free_room() or self.build_room()
        room.showing = cell
        return room

    def release(self, room):
        """
        Take a room back into the pool.

        Args:
            room (OceanRoom): The room to free.

        Returns:
            released (bool): True if it was freed, False if somebody is still in
                it.

        Notes:
            Refuses while anything is still inside. Exits do not count - a pool
            room should not have any, but a game that rigs one has not thereby
            pinned the room forever.

            Even a forced release would lose nothing, because position lives on
            the swimmer rather than on the room. The check is here because a room
            emptying itself out from under somebody is confusing to watch, not
            because anything would be destroyed.

        """
        if any(not obj.destination for obj in room.contents):
            return False
        room.showing = None
        return True

    def sweep(self):
        """
        Release every pool room nobody is in.

        Returns:
            released (int): How many rooms were freed.

        Notes:
            `place` already releases the room somebody has just left, so in normal
            play this finds nothing. It exists for the abnormal case: a hard crash
            between the move and the release, or a game that deleted a character
            out from under the projection. Cheap enough to run at startup and
            worth doing there.

        """
        return sum(1 for room in self.pool() if room.db.showing is not None and self.release(room))

    # --- placing things -----------------------------------------------------

    def cell_for(self, position):
        """
        Which cell a position falls in, at this projection's scale.

        Args:
            position (WorldPosition): Where something is.

        Returns:
            cell (tuple): `(region, x_index, y_index)`.

        """
        return cell_of(position, self.cell_size)

    def place(self, obj, position=None):
        """
        Put something in the room showing the water it is in.

        Args:
            obj (Object): The thing in the water.
            position (WorldPosition, optional): Where it is. Defaults to whatever
                the resolver says.

        Returns:
            room (OceanRoom or None): The room it is now in, or None if it has no
                world position and so is not in the sea at all.

        Notes:
            Does nothing at all when the thing is already in the right room, which
            is almost every tick - a swimmer drifting at half a knot crosses a
            hundred-metre cell boundary about once every seven minutes, and moving
            them within their own cell would fire every arrival hook in the game
            for a change nobody can see.

            That case is settled by reading the room the thing is already in,
            before any query runs. Confirming it by looking the cell up in the
            pool would be correct and would also put a database round trip on the
            hot path of every drifting object on every tick, which is the same
            mistake as writing an attribute that has not changed.

            When it does cross a boundary and it is alone in its room, the room
            is pointed at the new cell instead of the thing being moved to
            another room. That is only sound because the room is a view: panning
            it is the same act as walking through it, and it saves a move, a
            departure and an arrival for the commonest case there is - one piece
            of wreckage drifting across empty sea. It is skipped the moment
            another room already shows the destination, because two rooms showing
            one cell would put two swimmers in the same water unable to see each
            other.

        """
        if position is None:
            position = get_world_position(obj)
        if position is NoWorldPosition or position is None:
            return None

        cell = self.cell_for(position)
        previous = obj.location
        showing = previous.db.showing if previous is not None else None
        if showing is not None and tuple(showing) == cell:
            return previous

        room = self.room_showing(cell)
        if room is None and showing is not None and self.alone(obj, previous):
            previous.showing = cell
            return previous
        if room is None:
            room = self.free_room() or self.build_room()
            room.showing = cell
        if previous is room:
            return room

        obj.move_to(room, quiet=True, move_hooks=False)
        if previous is not None and previous.db.showing is not None:
            self.release(previous)
        return room

    def alone(self, obj, room):
        """
        Whether something is the only thing in a room.

        Args:
            obj (Object): The thing to ignore.
            room (Object): The room to look in.

        Returns:
            alone (bool): True if nothing else is in there.

        Notes:
            Exits do not count, for the same reason they do not count in
            `release` - a rigged gangway is not company.

        """
        return not any(other is not obj and not other.destination for other in room.contents)

    def overboard(self, obj, position):
        """
        Put something into the sea.

        Args:
            obj (Object): Whoever or whatever has gone in.
            position (WorldPosition): Where they went in.

        Returns:
            room (OceanRoom): The water they are now in.

        Notes:
            Sets the position *before* placing, because placing reads it. Getting
            that order wrong puts a man overboard in whatever water the last
            person to fall in was occupying, which is the kind of bug that only
            shows up when two people go over at once.

        """
        obj.maritime_position = position
        return self.place(obj, position)

    def recover(self, obj, destination):
        """
        Take something out of the sea.

        Args:
            obj (Object): Whoever or whatever has been recovered.
            destination (Object): Where they are put - a deck, a boat, a quay.

        Returns:
            recovered (bool): True once they are out.

        Notes:
            Clears the world position on the way out. A rescued character who
            keeps theirs is still at sea as far as every other subsystem is
            concerned - visible as a contact, drifting on the tick, and standing
            on a deck - and the symptom surfaces a long way from the rescue.

        """
        previous = obj.location
        obj.move_to(destination, quiet=True, move_hooks=False)
        obj.maritime_position = None
        if previous is not None and previous.db.showing is not None:
            self.release(previous)
        return True
