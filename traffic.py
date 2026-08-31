"""
Who is on the water.

Detection is the first thing in this contrib that is not about one vessel. A hull can
compute her own position, her own speed and her own clearance alone, but she cannot see
anybody without something that knows who else is out there.

That register lives here, in memory, and vessels put themselves into it as they tick. The
alternative was to thread a service reference through every hull, or to query the database
for vessels on every scan; the first couples movement to simulation for no reason, and the
second turns looking out of the window into a table scan.

**It is rebuilt, not persisted, and that is the right shape.** After a reload nobody is in
it until each vessel has ticked once - and after a reload no vessel remembers what she
could see either, because that memory is `.ndb` too. The two empty together and refill
together, so a ship does not come back from a reload having lost sight of a contact that
never went anywhere. A register that survived the reload while the memory of it did not
would announce the entire sea as newly sighted.

The gap is one tier interval, and only for vessels the simulation has never once visited.
Anything registered with the service is guaranteed to be reached - the scheduler is fair by
construction - so nothing stays invisible.

"""

from .spatial import ContactIndex

# Height in metres of the tallest thing worth widening a search for - roughly the
# main truck of a large square-rigger. Used only to pick a broad-phase radius: the
# real test is done per target, against that target's own height.
MAX_TARGET_HEIGHT = 60.0

# Length in metres of the longest hull worth widening a search for - roughly a
# first-rate. Used only to pick a broad-phase radius, on the same terms as the
# height above: a ship's blanket reaches downwind in proportion to HER length, not
# the length of whoever is lying in it, so a cutter has to look further than her own
# shadow to find the three-decker taking her wind. The real test is done per target.
MAX_HULL_LENGTH = 80.0


class VesselTraffic:
    """
    The vessels currently on the water, and where.

    Notes:
        A thin wrapper on a `ContactIndex` rather than a bare index, so that the
        thing callers reach for has a name that says what it holds, and so tests
        can work on their own instance instead of on process-wide state.

    """

    def __init__(self):
        self._index = ContactIndex()

    def note(self, vessel, position):
        """
        Record where a vessel is now.

        Args:
            vessel (Vessel): The hull.
            position (WorldPosition): Where she is.

        Returns:
            traffic (VesselTraffic): This register, for chaining.

        Notes:
            Idempotent. A vessel that has not moved may call this every tick, and
            one that has never called it before is simply added.

        """
        if vessel in self._index:
            self._index.move(vessel, position)
        else:
            self._index.insert(vessel, position)
        return self

    def forget(self, vessel):
        """
        Drop a vessel from the register.

        Args:
            vessel (Vessel): The hull to remove.

        Returns:
            removed (bool): True if she had been in it.

        """
        if vessel not in self._index:
            return False
        self._index.remove(vessel)
        return True

    def near(self, position, radius):
        """
        Vessels within a radius of a point, nearest first.

        Args:
            position (WorldPosition): Centre of the search.
            radius (float): Surface radius in metres.

        Returns:
            vessels (tuple): Candidates, nearest first.

        Notes:
            Candidates, not sightings. Whether any of them can actually be seen
            depends on height, weather and light, none of which a register knows.

        """
        return self._index.near(position, radius)

    def position_of(self, vessel):
        """
        Where the register last saw a vessel.

        Args:
            vessel (Vessel): The hull.

        Returns:
            position (WorldPosition or None): Her last recorded position.

        """
        return self._index.position_of(vessel)

    def clear(self):
        """
        Empty the register.

        Returns:
            traffic (VesselTraffic): This register, for chaining.

        """
        self._index.clear()
        return self

    def __contains__(self, vessel):
        return vessel in self._index

    def __len__(self):
        return len(self._index)

    def __repr__(self):
        return f"VesselTraffic({len(self._index)} afloat)"


_TRAFFIC = VesselTraffic()


def traffic():
    """
    The process-wide register of vessels on the water.

    Returns:
        traffic (VesselTraffic): The register.

    Notes:
        One per process, because there is one sea per process. Held behind a
        function rather than exported as a name so that reaching for it is a call
        rather than an import-time binding - a module that grabbed the object at
        import would keep pointing at a register that tests had replaced.

    """
    return _TRAFFIC
