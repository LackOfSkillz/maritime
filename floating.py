"""
Things in the water that are not ships.

A swimmer, a barrel, a raft, a corpse, a chest of sugar and a lifebuoy are all the same
problem: they hold a position, they have no way of their own, and the sea moves them. What
separates them is only how much of the wind they catch.

    the current   moves everything in it, equally, because it is the water
    the wind      moves what stands out of the water, in proportion to how much does
    windage       is that proportion, and it is the only difference between a raft and a man

**Nothing here has propulsion.** A floating thing does not steer, cannot hold a course and
has no orders. That is what makes it a different problem from a vessel rather than a small
one - a hull with the engines stopped is a floating thing, and this is what happens to her.

**Drift is not a special case of sailing.** It reuses the current and the wind that vessels
already read, from the same providers, at the same moment. A barrel and the ship that lost
it are carried by the same water, so they stay together, which is exactly what makes
searching for something you dropped a solvable problem.

"""

from dataclasses import dataclass

# How much of the wind each kind of floating thing catches, as a fraction of wind
# speed. A swimmer is almost all underwater and barely feels it; an upturned boat
# is a sail that nobody asked for.
SWIMMER_WINDAGE = 0.01
DEBRIS_WINDAGE = 0.02
BARREL_WINDAGE = 0.03
RAFT_WINDAGE = 0.06
UPTURNED_HULL_WINDAGE = 0.10

# How high a swimmer's eye is above the water, in metres. Their own horizon is
# barely a mile off, but a ship's masts stand well above it, so the danger is not
# that a swimmer cannot see her - it is that she carries no height to be seen by,
# and from that deck a mile away there is nothing on the water at all.
SWIMMER_HEIGHT_OF_EYE = 0.3

# How deep the water has to be before a swimmer stops being able to stand in it.
STANDING_DEPTH = 1.5


@dataclass(frozen=True)
class Buoyancy:
    """
    Whether a thing floats, and for how long.

    Attributes:
        floats (bool): Whether it is up at all.
        sink_rate (float): Metres per second downward once it is not, which the
            water column phase will use and nothing does yet.

    Notes:
        Two fields because they answer different questions. Something that has
        stopped floating is still somewhere - it is going down through a water
        column that is a real place - and collapsing that into a boolean would
        delete every wreck before anybody could dive on it.

    """

    floats: bool = True
    sink_rate: float = 0.0


def wind_drift(wind, windage):
    """
    How fast the wind pushes something floating.

    Args:
        wind (WindVector): The wind, named for where it blows *from*.
        windage (float): The fraction of wind speed this thing catches.

    Returns:
        drift (tuple): `(bearing, speed)` - where it is pushed towards, and how
            fast, in metres per second.

    Notes:
        Towards where the wind is going, which is the reciprocal of where it
        comes from. This is the one place in the system where a wind bearing has
        to be turned around, and getting it wrong would blow every survivor
        upwind - which is the kind of error that looks like a physics bug for a
        week before anybody checks the sign.

    """
    return wind.blowing_towards, wind.speed * max(0.0, windage)


def drift(position, current, wind, windage, elapsed):
    """
    Where the sea has taken something.

    Args:
        position (WorldPosition): Where it was.
        current (CurrentVector): The water under it.
        wind (WindVector): The wind over it.
        windage (float): How much of the wind it catches.
        elapsed (float): Game seconds.

    Returns:
        position (WorldPosition): Where it is now.

    Notes:
        The current first and in full - it is the water, and everything in the
        water goes with it - then the wind, in proportion to how much of the
        thing stands up out of that water. A swimmer and the raft beside him
        separate slowly for exactly this reason, and a search pattern that
        assumed they stayed together would look in the wrong place.

    """
    from .currents import carried

    moved = carried(position, current, elapsed)
    if elapsed <= 0.0 or windage <= 0.0 or wind.speed <= 0.0:
        return moved
    bearing, speed = wind_drift(wind, windage)
    return moved.moved(bearing, speed * elapsed)


def separation(first_windage, second_windage, wind, elapsed):
    """
    How far apart two floating things drift in a stretch of time.

    Args:
        first_windage (float): One thing's windage.
        second_windage (float): The other's.
        wind (WindVector): The wind over both.
        elapsed (float): Game seconds.

    Returns:
        distance (float): Metres between them, from the wind alone.

    Notes:
        The current cancels - it carries both equally - so what separates two
        floating things is entirely the difference in what they catch. That is
        why a search for a man who went over with a lifebuoy widens in a
        predictable direction, and it is the arithmetic a rescue would actually
        do.

    """
    return abs(first_windage - second_windage) * max(0.0, wind.speed) * max(0.0, elapsed)


def sinking_depth(started_at, now, buoyancy, seabed_depth):
    """
    How deep something that has stopped floating has got.

    Args:
        started_at (float): Game time it began to sink.
        now (float): Game time now.
        buoyancy (Buoyancy): Whether it floats, and how fast it goes down.
        seabed_depth (float): How deep the water is here, in metres.

    Returns:
        depth (float): Metres below the surface, never past the bottom.

    Notes:
        Stops at the seabed, because the alternative is objects falling forever
        through a world that has a floor. What happens to it when it gets there -
        settling, burial, being findable by a diver - is the water column phase's
        business.

    """
    if buoyancy.floats or buoyancy.sink_rate <= 0.0:
        return 0.0
    fallen = max(0.0, now - started_at) * buoyancy.sink_rate
    return min(fallen, max(0.0, seabed_depth))


class Floating:
    """
    The Evennia-side face of this module.

    Notes:
        Mixed into anything that sits on the water without steering it - a
        swimmer, a raft, a cask of powder, a body. It is deliberately not part of
        `Vessel`: a ship that has lost her way is still a ship, with a hull, a
        draft and a company aboard, and giving her two positions that both claim
        to be authoritative would be a worse bug than any it could fix.

    """

    def at_object_creation(self):
        """Set up a newly created floating thing."""
        super().at_object_creation()
        self.db.maritime_position = None
        self.db.windage = DEBRIS_WINDAGE
        self.db.buoyancy = Buoyancy()

    @property
    def maritime_position(self):
        """
        Where this is floating.

        Returns:
            position (WorldPosition or None): Where it is, or None if it is not
                in the water at all.

        Notes:
            Live value first, exactly as a vessel does it. Drift moves a floating
            thing on every tick, and paying a pickle and a commit for each of
            those is how a few hundred pieces of wreckage bring a server to its
            knees.

        """
        live = self.ndb.maritime_position
        return live if live is not None else self.db.maritime_position

    @maritime_position.setter
    def maritime_position(self, position):
        """
        Args:
            position (WorldPosition or None): Where it is now, or None to take it
                out of the water.

        Raises:
            TypeError: If given anything else.

        Notes:
            None is a real value here, unlike on a vessel - being pulled from the
            sea is an ordinary thing to happen to a swimmer - and it is written
            through immediately rather than deferred. A recovery that a crash
            could undo would put a rescued character back in the water, and the
            write costs nothing because it happens once.

        """
        from .position import WorldPosition

        if position is None:
            self.ndb.maritime_position = None
            self.db.maritime_position = None
            self.ndb.maritime_dirty = False
            return
        if not isinstance(position, WorldPosition):
            raise TypeError(f"Expected a WorldPosition or None, got {type(position).__name__}.")
        self.ndb.maritime_position = position
        self.ndb.maritime_dirty = True

    @property
    def windage(self):
        """
        Returns:
            windage (float): The fraction of wind speed this catches.

        """
        value = self.db.windage
        return DEBRIS_WINDAGE if value is None else float(value)

    @windage.setter
    def windage(self, fraction):
        """
        Args:
            fraction (float): How much of the wind it catches, from 0 to 1.

        Raises:
            ValueError: If outside that range. Above 1 the thing would outrun the
                wind pushing it, which is not a fast raft but a broken one.

        """
        fraction = float(fraction)
        if not 0.0 <= fraction <= 1.0:
            raise ValueError(f"Windage must be between 0 and 1, got {fraction!r}.")
        if self.db.windage != fraction:
            self.db.windage = fraction

    @property
    def buoyancy(self):
        """
        Returns:
            buoyancy (Buoyancy): Whether it floats, and how fast it goes down if
                not.

        """
        return self.db.buoyancy or Buoyancy()

    @buoyancy.setter
    def buoyancy(self, buoyancy):
        """
        Args:
            buoyancy (Buoyancy): The new state.

        Raises:
            TypeError: If given anything else.

        """
        if not isinstance(buoyancy, Buoyancy):
            raise TypeError(f"Expected a Buoyancy, got {type(buoyancy).__name__}.")
        self.db.buoyancy = buoyancy

    def checkpoint(self):
        """
        Write the drifted position to the database, if it has moved.

        Returns:
            saved (bool): True if anything was written.

        Notes:
            Same contract as a vessel's, so the simulation service checkpoints
            wreckage and warships through one code path without knowing the
            difference.

        """
        if not self.ndb.maritime_dirty:
            return False
        if self.ndb.maritime_position is not None:
            self.db.maritime_position = self.ndb.maritime_position
        self.ndb.maritime_dirty = False
        return True

    def at_server_reload(self):
        """Flush the drifted position before the server restarts."""
        super().at_server_reload()
        self.checkpoint()

    def at_server_shutdown(self):
        """Flush the drifted position before the server stops."""
        super().at_server_shutdown()
        self.checkpoint()

    def at_maritime_tick(self, elapsed):
        """
        Let the sea move this along.

        Args:
            elapsed (float): Game seconds since the last update.

        Returns:
            moved (bool): True if it went anywhere.

        Notes:
            Reads the same current and the same wind a vessel in that water would
            read, so a barrel dropped over the side stays with the ship that
            dropped it until the wind separates them - which is the whole reason
            searching for something you lost is a thing a player can do.

        """
        from . import config, environment

        position = self.maritime_position
        if position is None or elapsed <= 0.0:
            return False

        now = config.time_provider().now()
        moved = drift(
            position,
            environment.current_at(position, now),
            environment.wind_at(position, now),
            self.windage,
            elapsed,
        )
        if moved == position:
            return False

        self.maritime_position = moved
        config.projection().place(self, moved)
        return True
