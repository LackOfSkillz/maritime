"""
Sailing in company: taking station on another ship, and leaving off.

"""

from ..consorts import LEAST_STATION, MOST_STATION, NOT_IN_COMPANY, SAME_VESSEL, TOO_CLOSE
from ..formatting import format_range
from ..observation import DEFAULT_HEIGHT_OF_EYE, IDENTIFIED
from ..position import METRES_PER_CABLE
from ..vessel import WEATHER_DECKS
from .base import MaritimeCommand

#: Where a station may be, said the way a sailor says it rather than in degrees.
#:
#: Relative to the consort's heading throughout, which is what makes "her quarter" mean the
#: same water after she has worn as before it.
STATIONS = {
    "ahead": 0.0,
    "starboard bow": 45.0,
    "starboard beam": 90.0,
    "abeam": 90.0,
    "starboard quarter": 135.0,
    "astern": 180.0,
    "port quarter": 225.0,
    "port beam": 270.0,
    "port bow": 315.0,
}

#: What she takes if nobody says. Astern at two cables is the ordinary station for a ship
#: following another, and the one nobody has to think about.
DEFAULT_STATION = "astern"
DEFAULT_CABLES = 2.0


def read_station(words):
    """
    Read a station out of what somebody typed.

    Args:
        words (str): The part after the consort's name.

    Returns:
        station (tuple): `(bearing, distance)` in degrees and metres.

    Notes:
        Both halves are optional and either order is accepted, because "astern two cables"
        and "two cables astern" are the same order and a player should not have to find out
        which one this wanted.

    """
    said = " ".join(words.lower().split())
    bearing = None
    for name in sorted(STATIONS, key=len, reverse=True):
        if name in said:
            bearing = STATIONS[name]
            said = said.replace(name, " ", 1)
            break

    distance = None
    parts = said.replace(",", " ").split()
    for index, part in enumerate(parts):
        try:
            number = float(part)
        except ValueError:
            continue
        after = index + 1
        rest = " ".join(parts[after:])
        # Cables unless somebody says metres, because a station is quoted in cables by
        # anybody who has ever kept one.
        distance = number if rest.startswith("m") else number * METRES_PER_CABLE
        break

    if bearing is None:
        bearing = STATIONS[DEFAULT_STATION]
    if distance is None:
        distance = DEFAULT_CABLES * METRES_PER_CABLE
    return bearing, distance


def name_for(bearing):
    """
    Args:
        bearing (float): Degrees relative to the consort's heading.

    Returns:
        name (str): What a sailor would call it.

    """
    closest = min(STATIONS.items(), key=lambda pair: abs(pair[1] - float(bearing) % 360.0))
    return closest[0]


class CmdKeepStation(MaritimeCommand):
    """
    Take station on another ship and hold it.

    Usage:
      keep station on <ship>
      keep station on <ship> <where> <how far>

    Holds a place relative to her - `astern`, `starboard quarter`, `port beam`
    and so on - and keeps holding it while she tacks, wears and makes or takes
    in sail. Without a station named she takes two cables astern.

    A station is relative to *her* heading, not to the compass, which is what
    makes "her quarter" the same water after she has come about as before it.

    She holds it by steering and trimming, like anybody else. If your consort is
    faster, or better handled, or has the wind of you, you fall astern - and a
    station directly to leeward of her is a station in her lee, which is a
    mistake nobody will stop you making.
    """

    key = "keep station"
    aliases = ("take station", "in company", "consort")

    def at_helm(self, vessel):
        """Take station, or say why not."""
        said = self.args.strip()
        if not said:
            self.caller.msg(
                "Keep station on which ship? Try |wkeep station on Petrel astern 2 cables|n."
            )
            return

        if said.lower().startswith("on "):
            said = said[3:].strip()

        # Only a ship somebody aboard has actually made out. Ordering a station on a
        # contact nobody has identified would be keeping company with a smudge on the
        # horizon, and the lookout is the one who says which ship it is.
        room = getattr(self.caller, "location", None)
        if getattr(room, "exposure", None) not in WEATHER_DECKS:
            self.caller.msg("You cannot see the sea from in here.")
            return

        wanted = said.split()[0].lower()
        height = getattr(room, "height_of_eye", DEFAULT_HEIGHT_OF_EYE)
        consort = next(
            (
                sighting.target
                for sighting in vessel.contacts(height)
                if sighting.level == IDENTIFIED and wanted in sighting.target.key.lower()
            ),
            None,
        )
        if consort is None:
            self.caller.msg(f"No ship called '{said.split()[0]}' has been made out from here.")
            return

        past_the_name = len(said.split()[0])
        bearing, distance = read_station(said[past_the_name:])
        result = vessel.keep_station(consort, bearing, distance)
        if not result:
            if result.code == SAME_VESSEL:
                self.caller.msg("She cannot keep station on herself.")
            elif result.code == TOO_CLOSE:
                self.caller.msg(
                    f"That is inside {format_range(LEAST_STATION)} - close enough to be a "
                    "collision rather than a station."
                )
            else:
                self.caller.msg(
                    f"That is further off than {format_range(MOST_STATION)}. Past that she "
                    "is not in company, she is a separate ship going the same way."
                )
            return

        self.order(
            vessel,
            f"Take station on {consort.key}, {name_for(bearing)}, " f"{format_range(distance)}.",
        )
        if result.on_station:
            self.caller.msg(f"She is on station already, {name_for(bearing)} of {consort.key}.")
        else:
            self.caller.msg(
                f"{format_range(result.off_by)} to make up to her station "
                f"{name_for(bearing)} of {consort.key}."
            )


class CmdPartCompany(MaritimeCommand):
    """
    Leave off keeping station.

    Usage:
      part company

    She stops holding her station and steers as she is. Stopping keeping station
    is not an order to do anything else, so she is left where the last order put
    her rather than brought up short.
    """

    key = "part company"
    aliases = ("part", "leave company")

    def at_helm(self, vessel):
        """Break off."""
        consort = vessel.consort
        if not vessel.part_company():
            self.caller.msg("She is not in company with anybody.")
            return
        self.order(vessel, f"Part company with {consort.key}.")


class CmdCompany(MaritimeCommand):
    """
    Whether she is holding her station.

    Usage:
      station

    Where she should be, how far off it she is, and whether the trouble is that
    she has wandered or that she cannot keep up - which want different answers.

    Not `company`: that is the crew's word for her people, and it had it first.
    """

    key = "station"
    aliases = ("station report", "consorts")

    def at_helm(self, vessel):
        """Report the station."""
        where = vessel.station()
        if not where:
            if where.code == NOT_IN_COMPANY:
                self.caller.msg("She is sailing on her own.")
            else:
                self.caller.msg("Her consort is no longer in sight.")
            return

        told = [
            f"Keeping station on |w{where.consort.key}|n, "
            f"{name_for(where.bearing)}, {format_range(where.distance)}."
        ]
        if where.on_station:
            told.append("She is on station.")
        elif where.astern:
            told.append(
                f"She is {format_range(where.off_by)} out and falling astern - "
                "more sail, or a shorter station."
            )
        else:
            told.append(f"She is {format_range(where.off_by)} out of position.")
        self.caller.msg(" ".join(told))
