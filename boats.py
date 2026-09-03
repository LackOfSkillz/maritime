"""
A ship's boats, and what becomes of people when she goes down.

`DECISIONS.md` settled this: **the boats, and then the water.** She carries boats, the seats
are limited, and when she founders whoever is aboard takes one. If there is no seat left
they go into the water, and what *that* means is the game's - we put them there and publish
the conditions, because how much punishment a person absorbs is a character system and
character systems are what this contrib must not import.

**A boat is a boat.** Not a token, not a flag on the wreck: a small hull with one open room,
which is what a ship's boat actually is. She gets a position, she drifts on the current and
the wind, people can be in her, and she can be towed - all of it out of machinery that
already exists, because the thing being modelled really is a very small vessel.

**Boats can be shot away, and that is the point.** The source destroys them by name in its
criticals, so "did you keep your boats?" is a tactical question during the fight with a
consequence that outlives it. A ship that fought well and lost her boats has won something
her people will not enjoy.

"""

from dataclasses import dataclass

from .results import Result

#: How many a hull carries, by her length in metres.
#:
#: One boat to about fifteen metres, which puts two in a cutter and three or four in
#: something ship-rigged - the order of thing the period carried, and enough that losing one
#: matters without losing one being fatal.
METRES_PER_BOAT = 15.0

#: The most any hull carries however long she is. Past this they are in each other's way on
#: the booms and there is nowhere to swing them from.
MOST_BOATS = 6

#: How many people a boat will take.
#:
#: Crowded rather than comfortable, because a boat being launched off a sinking ship is not
#: being launched to a schedule.
SEATS_PER_BOAT = 12

#: What a ship's boat is, as a hull.
BOAT_LENGTH = 7.0
BOAT_BEAM = 2.1

#: **A boat adrift is carried by the current and not by the wind.**
#:
#: The tick already carries every hull on the set, so a boat with nobody pulling goes where
#: the water goes. What it does *not* model is her blowing to leeward, because leeway on a
#: vessel is computed from sail area and a boat under bare thwarts has none - `floating`
#: has a windage model for exactly this and it is for objects rather than hulls. A boat
#: therefore drifts a little more slowly than a real one would, and that is a known
#: simplification rather than an oversight.

NOT_SINKING = "not_sinking"
NO_BOATS = "no_boats"
NOBODY_ABOARD = "nobody_aboard"


@dataclass(frozen=True, kw_only=True)
class AbandonResult(Result):
    """
    What became of the people aboard.

    Attributes:
        boats (tuple): The boats that got away, as hulls.
        saved (int): How many got a seat.
        in_the_water (tuple): Who did not.
        seats (int): How many there were altogether.

    """

    boats: tuple = ()
    saved: int = 0
    in_the_water: tuple = ()
    seats: int = 0


def boats_for(length, per_boat=METRES_PER_BOAT, most=MOST_BOATS):
    """
    How many boats a hull of this size carries.

    Args:
        length (float): Her length, in metres.
        per_boat (float, optional): Metres of ship to a boat.
        most (int, optional): The most any hull carries.

    Returns:
        boats (int): How many.

    Notes:
        Derived rather than authored, for the same reason her rating is: a builder who draws
        a bigger ship should not have to remember to give her more boats, and should not be
        able to draw a launch with six of them.

    """
    return max(0, min(int(most), int(float(length) // float(per_boat))))


class Boats:
    """
    A hull that carries boats, and can put her people into them.

    Notes:
        The count is stored rather than derived, because boats are *lost* - shot away,
        stove in, sent away with a prize crew - and a number that recomputed itself from her
        length would quietly replace them.

    """

    def at_object_creation(self):
        """Set up this part of a newly created vessel."""
        super().at_object_creation()
        self.db.boats = None

    @property
    def boats(self):
        """
        Returns:
            boats (int): How many she has left.

        Notes:
            Filled from her length on first asking, so a hull built before boats existed
            has the right number rather than none - and a hull that has lost some keeps
            having lost them.

        """
        carried = self.db.boats
        if carried is None:
            carried = boats_for(self.length)
            self.db.boats = carried
        return int(carried)

    @property
    def seats(self):
        """
        Returns:
            seats (int): How many people her boats will take altogether.

        """
        return self.boats * SEATS_PER_BOAT

    def lose_a_boat(self, how_many=1):
        """
        A boat is gone - shot away, stove in, or sent off with a prize crew.

        Args:
            how_many (int, optional): How many.

        Returns:
            left (int): How many she still has.

        """
        self.db.boats = max(0, self.boats - max(0, int(how_many)))
        return self.boats

    def people_aboard(self):
        """
        Returns:
            people (tuple): Everybody in her compartments.

        Notes:
            Characters only. Her cargo is not saved by being put in a boat, and a barrel
            taking a seat somebody else needed would be the wrong kind of realism.

        """
        found = []
        for room in self.ship_rooms:
            for thing in room.contents:
                if getattr(thing, "destination", None) is not None:
                    continue
                if thing.is_typeclass("evennia.objects.objects.DefaultCharacter", exact=False):
                    found.append(thing)
        return tuple(found)

    def hoist_out(self, how_many=1):
        """
        Put boats in the water.

        Args:
            how_many (int, optional): How many to launch.

        Returns:
            boats (tuple): The hulls, floating where she is.

        Notes:
            Real hulls, because a ship's boat is a very small vessel and modelling her as
            anything else would mean building drift, position and occupancy a second time.

        """
        from evennia.utils import create

        from .motion import MotionLimits
        from .rooms import ShipRoom
        from .typeclasses import Vessel
        from .vessel import OPEN

        launched = []
        for number in range(min(int(how_many), self.boats)):
            boat = create.create_object(Vessel, key=f"{self.key}'s boat")
            boat.length, boat.beam = BOAT_LENGTH, BOAT_BEAM
            boat.motion_limits = MotionLimits(max_speed=1.5, acceleration=0.3, turn_rate=20.0)
            boat.maritime_position = self.maritime_position
            boat.heading = self.heading
            boat.owner = self.owner

            thwarts = create.create_object(ShipRoom, key=f"In {self.key}'s boat")
            thwarts.vessel = boat
            thwarts.exposure = OPEN
            thwarts.db.desc = (
                "Open to the weather, and low enough in the water that the sea is at eye "
                "level. There are oars along the thwarts and a breaker of water under the "
                "stern sheets."
            )
            launched.append(boat)

        self.db.boats = self.boats - len(launched)
        return tuple(launched)

    def abandon_ship(self):
        """
        Put her people into the boats, and the rest into the water.

        Returns:
            result (AbandonResult): Who got away and who did not.

        Notes:
            **Seats are scarce, and that is the whole of it.** A ship that kept her boats
            saves her people; one that had them shot away puts them over the side. Nothing
            here decides what happens to somebody in the water - that is the game's, and the
            event carries the conditions so it can decide well.

            Called when something else has determined she is going down. This does not
            decide that either.

        """
        people = self.people_aboard()
        if not people:
            return AbandonResult(success=False, code=NOBODY_ABOARD, seats=self.seats)

        wanted = min(self.boats, -(-len(people) // SEATS_PER_BOAT))
        launched = self.hoist_out(wanted) if wanted else ()

        saved, adrift = [], list(people)
        for boat in launched:
            thwarts = boat.ship_rooms[0]
            for _seat in range(SEATS_PER_BOAT):
                if not adrift:
                    break
                somebody = adrift.pop(0)
                somebody.location = thwarts
                saved.append(somebody)

        return AbandonResult(
            success=True,
            boats=launched,
            saved=len(saved),
            in_the_water=tuple(adrift),
            seats=len(launched) * SEATS_PER_BOAT,
        )
