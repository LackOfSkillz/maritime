"""
Keeping a lookout: what is in sight, where, and what changes.

"""

from evennia.commands.default.general import CmdLook

from ..formatting import format_range
from ..messaging import spell_bearing
from ..tactical import (
    arcs_bearing,
    aspect,
    aspect_name,
    closure,
    crossing_the_t,
    range_band,
    time_to_close,
)
from ..observation import (
    IDENTIFIED,
    bearing_in_points,
    QUARTER_ARC,
    RELATIVE_ARCS,
    direction_named,
    in_arc,
    DEFAULT_HEIGHT_OF_EYE,
    horizon_distance,
)
from ..vessel import WEATHER_DECKS
from .base import MaritimeCommand, vessel_of

# One knot is one nautical mile per hour, and a nautical mile is 1852 metres.
METRES_PER_SECOND_PER_KNOT = 1852.0 / 3600.0

# How far off a landmark can be and still be worth a bearing, in metres. The
# same reach as a berth search, because a quay you could tie up to is
# unambiguously a quay you can identify.
FIX_RANGE = 3000.0

# Fastest a vessel may be moving and still bring up safely. Letting go with way
# still on her is how cables part and anchors are left on the bottom.
MAX_ANCHORING_SPEED = 1.0


def sightings_toward(vessel, direction, height_of_eye=None):
    """
    What is in sight in one direction from a vessel.

    Args:
        vessel (Vessel): The hull.
        direction (tuple): From `direction_named`.
        height_of_eye (float, optional): How high the observer is standing.

    Returns:
        sightings (tuple): Contacts in that arc, nearest first.

    """
    _name, centre, width, relative = direction
    seen = vessel.contacts(height_of_eye) if height_of_eye else vessel.contacts()
    return in_arc(seen, centre, width, relative=relative)


class CmdLookout(MaritimeCommand):
    """
    Report what can be seen from where you stand.

    Usage:
      lookout

    What the sea holds, nearest first: where to look, how far off, and as much as
    can be told at that range. How far you can see depends on how high you are
    standing, so the answer from a masthead is not the answer from the deck.

    """

    key = "lookout"
    aliases = ("sightings",)

    def at_helm(self, vessel):
        """
        Args:
            vessel (Vessel): The hull the caller is aboard.

        """
        room = getattr(self.caller, "location", None)
        exposure = getattr(room, "exposure", None)
        if exposure not in WEATHER_DECKS:
            self.caller.msg("You cannot see the sea from in here.")
            return

        height = getattr(room, "height_of_eye", DEFAULT_HEIGHT_OF_EYE)
        seen = vessel.contacts(height)
        if not seen:
            self.caller.msg(
                f"Nothing in sight. The horizon is {format_range(horizon_distance(height))} off."
            )
            return

        lines = ["The lookout reports:"]
        lines.extend(vessel.narrator.contact_line(sighting) for sighting in seen)
        self.caller.msg("\n".join(lines))


class CmdTarget(MaritimeCommand):
    """
    Read the geometry between her and another vessel.

    Usage:
      target <name>

    Range and bearing, what aspect she shows, how fast the gap is shutting, and
    which of your arcs would bear. Only for a contact close enough to identify -
    you cannot take a firing solution on a shape you have not made out.

    Aspect is the one worth reading twice. A ship broad on your beam who is
    bow-on is coming for you; the same ship at the same bearing, stern-on, is
    leaving.

    """

    key = "target"
    aliases = ("solution", "range")

    def at_helm(self, vessel):
        """
        Args:
            vessel (Vessel): The hull the caller is aboard.

        """
        wanted = self.args.strip().lower()
        if not wanted:
            self.caller.msg("Take a solution on which vessel?")
            return

        room = getattr(self.caller, "location", None)
        if getattr(room, "exposure", None) not in WEATHER_DECKS:
            self.caller.msg("You cannot see the sea from in here.")
            return

        height = getattr(room, "height_of_eye", DEFAULT_HEIGHT_OF_EYE)
        for sighting in vessel.contacts(height):
            if sighting.level == IDENTIFIED and wanted in sighting.target.key.lower():
                self.report(vessel, sighting)
                return
        self.caller.msg(
            "Nothing of that name is near enough to make out. You cannot lay a "
            "solution on a shape you have not identified."
        )

    def report(self, vessel, sighting):
        """
        Args:
            vessel (Vessel): The hull the caller is aboard.
            sighting (Sighting): The identified contact.

        """
        her = sighting.target
        showing = aspect(vessel.maritime_position, her.maritime_position, her.heading)
        _course, made = vessel.made_good() or (vessel.heading, vessel.speed)
        _her_course, her_made = her.made_good() or (her.heading, her.speed)
        rate = closure(
            vessel.maritime_position,
            vessel.heading,
            made,
            her.maritime_position,
            her.heading,
            her_made,
        )

        self.caller.msg(f"{her.key}")
        self.caller.msg(
            f"  Range        {format_range(sighting.distance)}  ({range_band(sighting.distance)})"
        )
        self.caller.msg(
            f"  Bearing      {spell_bearing(sighting.bearing)}, "
            f"{bearing_in_points(sighting.relative)}"
        )
        self.caller.msg(f"  Aspect       {aspect_name(showing)}")
        self.caller.msg(
            f"  Closing      {abs(rate) * 1.9438:.1f} knots" + ("" if rate > 0 else " - opening")
        )

        meeting = time_to_close(sighting.distance, rate)
        if meeting is not None:
            self.caller.msg(f"  Together in  {meeting / 60.0:.1f} minutes at this rate")

        bearing_arcs = arcs_bearing(sighting.relative)
        if bearing_arcs:
            self.caller.msg(f"  Bearing on   {', '.join(bearing_arcs)}")
        else:
            self.caller.msg("  Bearing on   nothing; she is in none of your arcs")

        if crossing_the_t(sighting.relative, showing):
            self.caller.msg("  You have crossed her T.")


class CmdScan(MaritimeCommand):
    """
    Sweep the whole horizon, quarter by quarter.

    Usage:
      scan

    Everything around her at once - ahead, to starboard, astern and to port -
    with empty quarters named as well as full ones. Knowing there is nothing off
    the port bow is worth as much as knowing there is something, and a report
    that only listed contacts would leave you unable to tell "nothing there" from
    "nobody looked".

    Swept from where you are standing, so a scan from the masthead reaches
    further than one from the deck.

    """

    key = "scan"
    aliases = ("sweep", "all round")

    def at_helm(self, vessel):
        """
        Args:
            vessel (Vessel): The hull the caller is aboard.

        """
        room = getattr(self.caller, "location", None)
        if getattr(room, "exposure", None) not in WEATHER_DECKS:
            self.caller.msg("You cannot see the sea from in here.")
            return

        height = getattr(room, "height_of_eye", DEFAULT_HEIGHT_OF_EYE)
        seen = vessel.contacts(height)
        sweep = [
            (name, in_arc(seen, centre, QUARTER_ARC, relative=True))
            for name, centre in RELATIVE_ARCS.items()
        ]
        self.caller.msg("\n".join(vessel.narrator.all_round(sweep, horizon_distance(height))))


class CmdLookAround(CmdLook):
    """
    Look about you, or in one direction.

    Usage:
      look
      look <direction>
      look <object>

    With a direction - fore, aft, port, starboard, or any compass point - reports
    what is in sight that way and nothing else. Ship-relative directions turn
    with her; compass directions do not, so a contact fine on the starboard bow
    stays there as she comes round while its true bearing changes.

    Anything that is not a direction is looked at in the ordinary way.

    """

    def func(self):
        """Look in a direction if one was named, and otherwise as usual."""
        direction = direction_named(self.args)
        vessel = vessel_of(self.caller)
        if direction is None or vessel is None:
            return super().func()

        room = getattr(self.caller, "location", None)
        if getattr(room, "exposure", None) not in WEATHER_DECKS:
            self.caller.msg("You cannot see the sea from in here.")
            return

        height = getattr(room, "height_of_eye", DEFAULT_HEIGHT_OF_EYE)
        seen = sightings_toward(vessel, direction, height)
        self.caller.msg(
            "\n".join(vessel.narrator.sector_report(direction[0], seen, horizon_distance(height)))
        )


class CmdWatch(MaritimeCommand):
    """
    Keep a standing watch in one direction.

    Usage:
      watch <direction>
      watch off

    Sets you watching fore, aft, port, starboard or a compass point. You are told
    when something lifts over the horizon that way and when it sinks again,
    rather than having to look every few minutes.

    A watch is kept from where you are standing, so one set at the masthead sees
    further than one set on deck.

    """

    key = "watch"
    aliases = ("keep watch",)

    def at_helm(self, vessel):
        """
        Args:
            vessel (Vessel): The hull the caller is aboard.

        """
        word = self.args.strip().lower()
        if word in ("off", "stop", "down", ""):
            if not self.caller.db.maritime_watch:
                self.caller.msg("You are not keeping a watch.")
                return
            self.caller.db.maritime_watch = None
            self.caller.ndb.maritime_watched = None
            self.caller.msg(vessel.narrator.watch_ended())
            return

        direction = direction_named(word)
        if direction is None:
            self.caller.msg("Watch which way? Fore, aft, port, starboard, or a compass point.")
            return

        room = getattr(self.caller, "location", None)
        if getattr(room, "exposure", None) not in WEATHER_DECKS:
            self.caller.msg("You cannot keep a watch from in here.")
            return

        self.caller.db.maritime_watch = direction[0]
        self.caller.ndb.maritime_watched = None
        self.caller.msg(vessel.narrator.watch_set(direction[0]))
