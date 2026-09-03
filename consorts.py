"""
Sailing in company.

The sailing master already steers for a mark. A consort is the same job with a mark that
moves: *two cables on her starboard quarter*, held while she tacks, wears, makes sail and
takes it in again. Convoys, escorts and a squadron that manoeuvres together all come out of
that one order, and nothing else has to be built for any of them.

**A station is relative to the ship you are keeping it on, not to the compass.** "On her
starboard quarter" stays on her quarter when she turns; a station held on a compass bearing
would put you across her bows the moment she wore. That is what station-keeping *is*, and
getting it wrong is the whole difference between a squadron and a crowd.

    keep station on Petrel, 2 points on her starboard quarter, 2 cables

**It composes with the wind shadow, and that is a trap worth leaving in.** A station
directly to leeward of your consort is a station in her lee - she takes your wind, and you
fall astern trying to hold a place you cannot sail to. The blocked-wind work already models
this, and nothing here warns anybody about it. Choosing a station is a decision, and a
station that quietly worked everywhere would not be one.

**She holds it herself, and she does not cheat.** Station-keeping steers and trims like a
captain would: it can only ask for a heading and a sail plan, and if the consort is faster
or better handled it falls behind and says so. A ship that magically pinned herself to
another's quarter would be a tow-rope with extra steps.

"""

from dataclasses import dataclass

from .motion import HelmOrders
from .results import Result

#: How close to her station counts as being on it, as a fraction of the ordered distance.
#:
#: A tenth. Closer than that is not station-keeping, it is a collision waiting for a
#: wind-shift, and no ship under sail holds a place better than this.
ON_STATION = 0.1

#: The furthest station anybody may be ordered to hold, in metres.
#:
#: Two miles. Past that she is not in company, she is a separate ship going the same way -
#: and a signal she cannot read is not an order she can obey.
MOST_STATION = 3700.0

#: The closest, in metres. A ship's length and a little, because closer is a collision.
LEAST_STATION = 40.0

NO_CONSORT = "no_consort"
SAME_VESSEL = "same_vessel"
TOO_FAR = "too_far"
TOO_CLOSE = "too_close"
LOST_HER = "lost_her"
NOT_IN_COMPANY = "not_in_company"


@dataclass(frozen=True, kw_only=True)
class StationResult(Result):
    """
    Where she should be, and where she is.

    Attributes:
        consort (object or None): The hull she is keeping station on.
        bearing (float): Her station, in degrees relative to the consort's heading.
        distance (float): How far off the consort she should be, in metres.
        wanted (WorldPosition or None): The water she should be in.
        off_by (float): How far she is from it, in metres.
        on_station (bool): Whether that is close enough.
        astern (bool): Whether she is falling behind rather than merely off to one side.

    """

    consort: object = None
    bearing: float = 0.0
    distance: float = 0.0
    wanted: object = None
    off_by: float = 0.0
    on_station: bool = False
    astern: bool = False


def station_point(position, heading, bearing, distance):
    """
    The water a ship keeping station should be in.

    Args:
        position (WorldPosition): Where the consort is.
        heading (float): Where the consort is heading, in degrees.
        bearing (float): The station, in degrees *relative to her heading* - 0 ahead, 90 on
            her starboard beam, 180 astern, 270 to port.
        distance (float): How far off her, in metres.

    Returns:
        where (WorldPosition): The station.

    Notes:
        Relative to her heading, which is the whole point. A station on a compass bearing
        would swing across her bows every time she tacked, and a squadron ordered to hold
        one would sail through itself the first time the wind came ahead.

    """
    return position.moved((float(heading) + float(bearing)) % 360.0, float(distance))


def off_station(own, wanted):
    """
    Args:
        own (WorldPosition): Where she is.
        wanted (WorldPosition): Where she should be.

    Returns:
        distance (float): How far apart, in metres.

    """
    if own is None or wanted is None:
        return 0.0
    return own.horizontal_distance_to(wanted)


class InCompany:
    """
    A hull that can be told to keep station on another.

    Notes:
        One consort at a time. A ship cannot hold two stations, and a squadron is a chain
        of ships each keeping station on the next rather than a fleet all watching the
        flagship - which is how it was actually done, because the ship ahead is the one you
        can see.

    """

    def at_object_creation(self):
        """Set up this part of a newly created vessel."""
        super().at_object_creation()
        self.db.consort = None
        self.db.station_bearing = 0.0
        self.db.station_distance = 0.0

    @property
    def consort(self):
        """
        Returns:
            consort (Vessel or None): The hull she is keeping station on.

        """
        her = self.db.consort
        return her if her and her.pk else None

    @property
    def in_company(self):
        """
        Returns:
            in_company (bool): Whether she is keeping station on anybody.

        """
        return self.consort is not None

    def keep_station(self, consort, bearing, distance):
        """
        Take station on another ship.

        Args:
            consort (Vessel): The hull to keep station on.
            bearing (float): Where to sit, in degrees relative to *her* heading.
            distance (float): How far off her, in metres.

        Returns:
            result (StationResult): Failed if the station cannot be held.

        Notes:
            Ordering a station gives up any passage she was making. A ship cannot steer for
            a mark and for a moving ship at once, and a mate trying to do both would take
            whichever the code asked him about last - which is not a decision anybody made.

        """
        if consort is None:
            return StationResult(success=False, code=NO_CONSORT)
        if consort is self:
            return StationResult(success=False, code=SAME_VESSEL)

        distance = float(distance)
        if distance > MOST_STATION:
            return StationResult(success=False, code=TOO_FAR, distance=distance)
        if distance < LEAST_STATION:
            return StationResult(success=False, code=TOO_CLOSE, distance=distance)

        self.db.consort = consort
        self.db.station_bearing = float(bearing) % 360.0
        self.db.station_distance = distance
        # She is following a ship now, not a route. Holding both would have the sailing
        # master steering for whichever he was asked about last.
        self.under_con = False
        return self.station()

    def part_company(self):
        """
        Leave off keeping station.

        Returns:
            parted (bool): True if she was in company.

        Notes:
            She is left steering as she was, rather than stopped. A ship told to stop
            keeping station is being told to do something else, and what that is belongs to
            whoever gave the order.

        """
        if not self.in_company:
            return False
        self.db.consort = None
        return True

    def station(self):
        """
        Where she should be, and how far off it she is.

        Returns:
            result (StationResult): Failed if she is not in company, or has lost sight of
                the ship she was keeping station on.

        """
        consort = self.consort
        if consort is None:
            return StationResult(success=False, code=NOT_IN_COMPANY)

        hers = consort.maritime_position
        mine = self.maritime_position
        if hers is None or mine is None:
            return StationResult(success=False, code=LOST_HER, consort=consort)

        bearing = float(self.db.station_bearing or 0.0)
        distance = float(self.db.station_distance or 0.0)
        wanted = station_point(hers, consort.heading, bearing, distance)
        adrift = off_station(mine, wanted)

        return StationResult(
            success=True,
            consort=consort,
            bearing=bearing,
            distance=distance,
            wanted=wanted,
            off_by=adrift,
            on_station=adrift <= distance * ON_STATION,
            # Behind the station rather than beside it, which is the failure that means
            # she cannot keep up rather than that she has wandered.
            astern=mine.horizontal_distance_to(hers) > distance * (1.0 + ON_STATION),
        )

    def work_station(self):
        """
        Steer for her station, and carry what will get her there.

        Returns:
            worked (bool): True if she did anything.

        Notes:
            Called from the tick beside `work_her`, and never with it: a ship keeping
            station is not running a passage. She steers and trims and nothing else - if
            the consort is faster, or better handled, or has the wind of her, she falls
            behind and the report says so rather than the arithmetic quietly closing the
            gap.

        """
        if not self.in_company or self.held_by():
            return False

        where = self.station()
        if not where:
            # Lost her. Left steering as she was rather than stopped, because a ship whose
            # consort has gone is a ship on her own, not a ship with no orders.
            self.part_company()
            return False

        if where.on_station:
            # Match her, rather than steering for a point she is about to leave.
            self.orders = HelmOrders(heading=where.consort.heading, speed=where.consort.speed)
            return True

        from .voyage import course_for_mark

        wind = self.wind_here()
        heading = course_for_mark(
            self.maritime_position, where.wanted, self.speed, self.current_here()
        )
        # Everything she has, if she is astern of her station; her consort's pace if she is
        # merely off to one side. A ship crowding sail to close a gap she is already inside
        # is a ship that will overrun it.
        wanted = self.sailing_speed(self.shadow()) if where.astern else where.consort.speed
        self.orders = HelmOrders(heading=heading, speed=wanted)
        if wind is not None and where.astern and self.sail_plan.area < 1.0:
            from .sailing import FULL

            self.sail_plan = FULL
        return True


def squadron(leader):
    """
    Every ship keeping station on this one, and on those, and so on.

    Args:
        leader (Vessel): The hull at the head of it.

    Returns:
        company (tuple): The hulls astern of her, nearest first.

    Notes:
        A chain rather than a fan. Each ship keeps station on the one ahead, because that
        is the ship she can see - so a squadron is discovered by walking the chain rather
        than by asking who is following the flagship.

    """
    from .typeclasses import Vessel

    following = {}
    for hull in Vessel.objects.all_family():
        ahead = getattr(hull, "consort", None)
        if ahead is not None:
            following.setdefault(ahead.id, []).append(hull)

    company, queue = [], [leader]
    seen = {leader.id}
    while queue:
        ship = queue.pop(0)
        for astern in following.get(ship.id, ()):
            if astern.id in seen:
                # A ring of ships each keeping station on the next has no head, and
                # walking it would not stop.
                continue
            seen.add(astern.id)
            company.append(astern)
            queue.append(astern)
    return tuple(company)


__all__ = (
    "ON_STATION",
    "MOST_STATION",
    "LEAST_STATION",
    "StationResult",
    "station_point",
    "off_station",
    "InCompany",
    "squadron",
)
