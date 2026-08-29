"""
The layer that speaks.

Everything else in this package returns data. A grounding is a `GroundingResult`; a step of
movement is two `MotionState`s. Nothing in the simulation knows the word "aground", and
that separation is deliberate - it is what lets a game replace every line of prose without
touching a line of physics.

This module is the other half of that bargain. It answers two questions the simulation
does not:

    which change is worth mentioning?    a ship reports that she is *coming round*, not
                                         that she is still turning, every two seconds
    who hears what?                      on deck you watch the sea go by; below you feel
                                         her heel and hear water on the planking

The first is why narration state lives here rather than in the vessel. Deciding whether to
speak needs to know what was last said, which is a property of the conversation and not of
the hull.

To change the words, subclass `VesselNarrator`, override `phrase_for`, and point
`MARITIME_NARRATOR` at it. Every line a vessel says passes through that one method, so a
game can be laconic, or florid, or in another language, or address a captain and a deck
hand differently, without reimplementing when to speak.

"""

from .grounding import HOLED, SHOAL_WARNING_CLEARANCE
from .observation import CLASSIFIED, IDENTIFIED, bearing_in_points
from .position import bearing_difference
from .vessel import WEATHER_DECKS

# Compass points, for describing a heading to someone who is not reading an
# instrument. Sixteen points is what a helmsman would actually call.
_COMPASS_POINTS = (
    "north",
    "north-northeast",
    "northeast",
    "east-northeast",
    "east",
    "east-southeast",
    "southeast",
    "south-southeast",
    "south",
    "south-southwest",
    "southwest",
    "west-southwest",
    "west",
    "west-northwest",
    "northwest",
    "north-northwest",
)

# Things that happen to a vessel that the people aboard would notice. These name
# the *event*, not the sentence - which is the point, since the sentence is what a
# game is expected to replace.
COMING_ROUND = "coming_round"
STEADY = "steady"
AT_SPEED = "at_speed"
WAY_OFF = "way_off"
RUN_AGROUND = "run_aground"
SIGHTED = "sighted"
CONTACT_LOST = "contact_lost"
CONTACT_CLOSER = "contact_closer"
HULL_HOLED = "hull_holed"
SHOALING = "shoaling"


def compass_point(bearing):
    """
    Describe a bearing the way a person would say it.

    Args:
        bearing (float): Compass bearing in degrees.

    Returns:
        name (str): One of the sixteen points, e.g. `"east-northeast"`.

    """
    index = int((bearing % 360.0) / 22.5 + 0.5) % 16
    return _COMPASS_POINTS[index]


def spell_bearing(bearing):
    """
    Speak a bearing the way it is actually said aloud.

    Args:
        bearing (float): Compass bearing in degrees.

    Returns:
        spoken (str): Digits separated, e.g. `"0-9-0"` for 090.

    Notes:
        Courses are always given digit by digit and always in three figures.
        "Ninety" and "one nine zero" are dangerously easy to confuse across a
        windy deck; "zero-nine-zero" is not, which is why the convention exists.

    """
    return "-".join(f"{int(round(bearing)) % 360:03d}")


class VesselNarrator:
    """
    Turns what happened to a vessel into what the people aboard hear.

    Attributes:
        vessel (Vessel): The hull being narrated.

    Notes:
        Cheap to build and holds nothing of its own - what has already been said
        is kept on the vessel's `.ndb`, so narration survives being rebuilt every
        tick but not a reload, which is correct: after a reload nobody has been
        told anything yet.

    """

    def __init__(self, vessel):
        """
        Args:
            vessel (Vessel): The hull to speak for.

        """
        self.vessel = vessel

    # --- delivery -----------------------------------------------------------

    def deliver(self, topside, below=None):
        """
        Say something to the ship's company, according to where they stand.

        Args:
            topside (str): What is heard on a weather deck.
            below (str, optional): What is heard below. Omitted means those
                compartments hear nothing at all, which is a real answer - not
                every event reaches the hold.

        """
        for room in self.vessel.ship_rooms:
            message = topside if room.exposure in WEATHER_DECKS else below
            if message:
                room.msg_contents(message)

    def phrase_for(self, event, **detail):
        """
        The words for one event.

        Args:
            event (str): One of the event constants in this module.
            **detail: Whatever that event carries - a heading, a bottom type, a
                clearance.

        Returns:
            phrases (tuple): `(topside, below)`. Either may be `None` to say
                nothing in that part of the ship.

        Raises:
            KeyError: If the event is not one this narrator knows. A subclass
                adding events should handle its own and defer the rest to
                `super()`.

        Notes:
            The single override point. Every line a vessel speaks comes through
            here, so replacing the prose of the entire system is one method.

        """
        if event == COMING_ROUND:
            side = detail["side"]
            return (
                f"The deck leans as she comes round to {side}.",
                f"You feel her heel over, coming round to {side}.",
            )

        if event == STEADY:
            spoken = spell_bearing(detail["heading"])
            point = compass_point(detail["heading"])
            return (
                f'The helmsman reports, "Vessel steady on {spoken} now, sir." '
                f"She runs {point}, the sea sliding past her rail.",
                f'The call carries down from the helm: "Steady on {spoken}, sir."',
            )

        if event == AT_SPEED:
            return (
                "She settles into her stride, water curling steadily from the bow.",
                "The working of the hull settles into a steady rhythm.",
            )

        if event == WAY_OFF:
            return (
                "The last of her way falls off. She lies quiet on the water.",
                "The sound of water along the planking dies away.",
            )

        if event == HULL_HOLED:
            return (
                "A grinding crash runs the length of her. She stops dead, canted "
                "over, and the sound of water is suddenly very loud.",
                "The hull screams against rock, and water bursts in through the seams.",
            )

        if event == RUN_AGROUND:
            bottom = detail["bottom"]
            return (
                f"She slides to a halt with a long shudder, aground on {bottom}. "
                f"The deck tilts, and stays tilted.",
                f"The hull grinds and settles. She is aground on {bottom}.",
            )

        if event == SIGHTED:
            where = bearing_in_points(detail["relative"])
            return (
                f'The lookout cries, "Sail ho! {where.capitalize()}!"',
                'The cry of "Sail ho!" carries down from the deck.',
            )

        if event == CONTACT_LOST:
            return "The sail you were watching dips below the horizon and is gone.", None

        if event == CONTACT_CLOSER:
            if detail["level"] == IDENTIFIED:
                return f"You can read her now. She is the {detail['name']}.", None
            return "She is close enough now to make out her rig.", None

        if event == SHOALING:
            call = (
                f"The leadsman calls the depth: {detail['clearance']:.1f} metres "
                f"under her keel, and shoaling."
            )
            return call, call

        raise KeyError(event)

    # --- events -------------------------------------------------------------

    def underway(self, before, after):
        """
        Tell anyone aboard what the ship is doing.

        Args:
            before (MotionState): State at the start of the step.
            after (MotionState): State at the end of it.

        Notes:
            Reports *transitions*, not conditions. A ship announces that she is
            coming round, and again when she is steady - not that she is still
            turning, every two seconds, for the whole minute it takes. Reporting
            a condition rather than a change is how ambient messaging turns into
            noise that players learn to scroll past.

        """
        event, detail = self._transition(before, after)
        if event is None:
            return
        self.deliver(*self.phrase_for(event, **detail))

    def grounding(self, contact):
        """
        Tell the ship she has found the bottom.

        Args:
            contact (GroundingResult): What she struck and how hard.

        """
        if contact.severity == HOLED:
            self.deliver(*self.phrase_for(HULL_HOLED))
        else:
            self.deliver(*self.phrase_for(RUN_AGROUND, bottom=contact.bottom))

    def soundings(self, contact):
        """
        Warn the ship when the water shoals beneath her.

        Args:
            contact (GroundingResult): The clearance she currently has.

        Notes:
            A vessel that grounds without warning is an accident; one that
            grounds after the leadsman has called diminishing water is a
            decision, and only the second is worth playing. Warned once on
            entering shallow water, not every tick, for the same reason turns
            are.

        """
        vessel = self.vessel
        if contact.clearance >= SHOAL_WARNING_CLEARANCE:
            vessel.ndb.reported_shoaling = False
            return
        if vessel.ndb.reported_shoaling:
            return
        vessel.ndb.reported_shoaling = True
        self.deliver(*self.phrase_for(SHOALING, clearance=contact.clearance))

    def sightings(self, seen):
        """
        Tell the ship what the lookout can see.

        Args:
            seen (tuple): `Sighting` objects, nearest first.

        Notes:
            Transitions again, and for the same reason: a sail on the horizon is
            news once. Reporting every contact every tick would bury the one that
            just appeared under twenty repetitions of the three that did not.

            Three things are worth a cry - a sail where there was none, one that
            has dropped below the horizon, and one that has come close enough to
            tell something new about. The third is why the detection ladder has
            rungs at all.

        """
        vessel = self.vessel
        was = dict(vessel.ndb.contacts or {})
        now = {}

        for sighting in seen:
            key = sighting.target.id
            now[key] = sighting.level
            if key not in was:
                self.deliver(*self.phrase_for(SIGHTED, relative=sighting.relative))
            elif sighting.level != was[key] and sighting.level in (CLASSIFIED, IDENTIFIED):
                self.deliver(
                    *self.phrase_for(
                        CONTACT_CLOSER,
                        level=sighting.level,
                        name=sighting.target.key,
                    )
                )

        for key in was:
            if key not in now:
                self.deliver(*self.phrase_for(CONTACT_LOST))

        vessel.ndb.contacts = now

    # --- transitions --------------------------------------------------------

    def _transition(self, before, after):
        """
        Decide which change, if any, is worth mentioning.

        Args:
            before (MotionState): State at the start of the step.
            after (MotionState): State at the end of it.

        Returns:
            change (tuple): `(event, detail)`, where `event` is `None` if nothing
                has changed that anyone would remark on.

        Notes:
            Consumes the change as it reports it - the flags on the vessel's
            `.ndb` are updated here, so calling this twice for one step reports
            once. Kept separate from the words so a game can change what is said
            without inheriting the bookkeeping that decides when to say it.

        """
        vessel = self.vessel
        turning = abs(after.heading - before.heading) > 1e-6
        on_course = abs(bearing_difference(after.heading, vessel.orders.heading)) < 1e-6
        under_way = after.speed > 0.0
        gathering = after.speed > before.speed
        at_ordered_speed = under_way and abs(after.speed - vessel.orders.speed) < 1e-6

        was_turning = bool(vessel.ndb.reported_turning)
        was_at_speed = bool(vessel.ndb.reported_at_speed)
        was_under_way = bool(vessel.ndb.reported_under_way)

        event, detail = None, {}

        if turning and not was_turning:
            side = "starboard" if bearing_difference(before.heading, after.heading) > 0 else "port"
            event, detail = COMING_ROUND, {"side": side}
            vessel.ndb.reported_turning = True
        elif was_turning and on_course and not turning:
            event, detail = STEADY, {"heading": after.heading}
            vessel.ndb.reported_turning = False
        elif at_ordered_speed and gathering and not was_at_speed:
            event = AT_SPEED
            vessel.ndb.reported_at_speed = True
        elif was_under_way and not under_way:
            event = WAY_OFF

        if not at_ordered_speed:
            vessel.ndb.reported_at_speed = False
        vessel.ndb.reported_under_way = under_way

        return event, detail
