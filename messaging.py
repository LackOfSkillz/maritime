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

from dataclasses import dataclass

from .grounding import HOLED, SHOAL_WARNING_CLEARANCE
from .formatting import format_range
from .observation import (
    CLASSIFIED,
    IDENTIFIED,
    VESSEL,
    bearing_in_points,
    direction_named,
    in_arc,
)
from .sailing import beaufort_force
from .weather import CALM, RIPPLED, SMOOTH
from .position import COMPASS_POINTS, METRES_PER_FATHOM, bearing_difference
from .vessel import WEATHER_DECKS

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


# --- orders, and the answers to them ---------------------------------------
#
# An order at sea is spoken, repeated back and acted on, and that exchange is the
# most-read text this system produces. It lives here rather than inside the
# commands for the same reason the ship's own narration does: a game that wants
# its own voice should change words in one file, not fork every command.
#
# There is no branching below and no state - it is prose, and it can grow to any
# length without costing anything.

HELM_ORDER = "helm_order"
SPEED_ORDER = "speed_order"
ALL_STOP = "all_stop"
SAIL_ORDER = "sail_order"
SAIL_CARRIED_HARD = "sail_carried_hard"
ANCHOR_ORDER = "anchor_order"
WEIGH_ORDER = "weigh_order"
CAST_THE_LEAD = "cast_the_lead"
ALONGSIDE_ORDER = "alongside_order"
MADE_FAST = "made_fast"
GANGWAY_DOWN = "gangway_down"
SINGLE_UP = "single_up"
LET_GO = "let_go"
WORK_THE_FIX = "work_the_fix"


@dataclass(frozen=True)
class Order:
    """
    What is said when an order is given.

    Attributes:
        called (str): What the person giving it hears themselves say.
        overheard (str): What everyone else on deck hears.
        answered (str): What the crew say back, carried through the ship. Empty
            if the order needs no answer.

    Notes:
        Three strings because an order is three events - given, overheard,
        answered - and a command that only printed the first would turn a crewed
        vessel into several people each sailing their own private ship.

    """

    called: str
    overheard: str = ""
    answered: str = ""


# --- what it looks like out there ------------------------------------------
#
# A ship's rooms are static objects and the world outside them is not. The deck
# description says what is nailed down; this says what is happening, and the two
# together are why a vessel can be an ordinary Evennia room and still feel like
# she is at sea.

#: What each Beaufort force is called. The scale is arithmetic and lives in
#: `sailing`; these are the words for it, and a game is free to replace them with
#: its own - "near gale" and "the sky gone the colour of a bruise" are the same
#: measurement.
BEAUFORT_NAMES = (
    "a flat calm",
    "light airs",
    "a light breeze",
    "a gentle breeze",
    "a moderate breeze",
    "a fresh breeze",
    "a strong breeze",
    "a near gale",
    "a gale",
    "a strong gale",
    "a storm",
    "a violent storm",
    "a hurricane",
)


#: How a sailor says each direction. Ship-relative words have their own
#: prepositions - you look *ahead* and *astern*, but *to* starboard - and a
#: compass direction is simply named.
DIRECTION_PHRASES = {
    "fore": "ahead",
    "aft": "astern",
    "port": "to port",
    "starboard": "to starboard",
}


#: What each sea looks like from a deck. A calm and a rippled sea say nothing,
#: because the absence of waves is not news and repeating it every time somebody
#: looks is how ambient text becomes wallpaper.
SEA_DESCRIPTIONS = {
    CALM: "",
    RIPPLED: "",
    SMOOTH: "The water is smooth, with only a low swell running.",
    "slight": "There is a slight sea, and she lifts gently to it.",
    "moderate": "A moderate sea runs, and she works in it.",
    "rough": "The sea is rough, breaking white along her weather side.",
    "very rough": "A very rough sea, and green water comes aboard forward.",
    "high": "A high sea runs, and she labours heavily in it.",
    "very high": "The sea is very high. She is swept from end to end.",
    "phenomenal": "The sea is beyond anything anyone aboard has words for.",
}


def compass_point(bearing):
    """
    Describe a bearing the way a person would say it.

    Args:
        bearing (float): Compass bearing in degrees.

    Returns:
        name (str): One of the sixteen points, e.g. `"east-northeast"`.

    """
    index = int((bearing % 360.0) / 22.5 + 0.5) % 16
    return COMPASS_POINTS[index]


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
            spoken = leadsman_call(detail["depth"])
            call = f'The leadsman calls, "{spoken}" - and shoaling.'
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
        self.deliver(*self.phrase_for(SHOALING, depth=contact.depth))

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
        self.stand_watches(seen)

    def order_for(self, event, **detail):
        """
        The words for one spoken order.

        Args:
            event (str): One of the order constants in this module.
            **detail: What the order carries - a bearing, a sail plan, a berth.
                `who` is the name of whoever gave it.

        Returns:
            order (Order): Called, overheard and answered.

        Raises:
            KeyError: If the order is not one this voice knows.

        Notes:
            The counterpart of `phrase_for`, and the other half of replacing the
            prose of the whole system. Between them, every player-facing word a
            vessel or her crew produces passes through two methods on one class.

        """
        who = detail.get("who", "Someone")

        if event == HELM_ORDER:
            spoken = detail["spoken"]
            return Order(
                called=f'You call out, "Helm, steer {spoken}."',
                overheard=f'{who} calls out, "Helm, steer {spoken}."',
                answered=f'The helmsman answers, "Steering {spoken} now, sir."',
            )

        if event == SPEED_ORDER:
            knots = detail["knots"]
            return Order(
                called=f'You call out, "Make her {knots:.0f} knots."',
                overheard=f'{who} calls out, "Make her {knots:.0f} knots."',
                answered=f'The mate answers, "Making {knots:.0f} knots now, sir."',
            )

        if event == ALL_STOP:
            return Order(
                called='You call out, "All stop."',
                overheard=f'{who} calls out, "All stop."',
                answered='The mate answers, "All stop, aye sir."',
            )

        if event == SAIL_ORDER:
            name = detail["plan"]
            return Order(
                called=f'You call out, "Set {name}!"',
                overheard=f'{who} calls out, "Set {name}!"',
                answered=f'The mate answers, "{name.capitalize()}, aye sir."',
            )

        if event == SAIL_CARRIED_HARD:
            return Order(
                called="",
                answered='The mate adds, "She is carrying more than she should in this, sir."',
            )

        if event == ANCHOR_ORDER:
            return Order(
                called='You call out, "Let go the anchor!"',
                overheard=f'{who} calls out, "Let go the anchor!"',
                answered=(
                    "The cable roars out through the hawse, and the anchor takes the "
                    "ground. She brings up and lies quiet."
                ),
            )

        if event == WEIGH_ORDER:
            return Order(
                called='You call out, "Weigh anchor!"',
                overheard=f'{who} calls out, "Weigh anchor!"',
                answered=(
                    "The capstan turns and the cable comes in dripping. "
                    'The mate calls, "Anchor\'s aweigh, sir!"'
                ),
            )

        if event == CAST_THE_LEAD:
            return Order(
                called="You order a cast of the lead.",
                overheard=f"{who} orders a cast of the lead.",
            )

        if event == ALONGSIDE_ORDER:
            return Order(
                called='You call out, "Take her alongside!"',
                overheard=f'{who} calls out, "Take her alongside!"',
                answered='The mate answers, "Alongside, aye sir."',
            )

        if event == MADE_FAST:
            return Order(
                called="",
                answered=(
                    f"Lines go ashore fore and aft. She is made fast at "
                    f"{detail['berth']}, {detail['side']} side to."
                ),
            )

        if event == GANGWAY_DOWN:
            return Order(called="", answered="The gangway comes down onto the quay.")

        if event == SINGLE_UP:
            return Order(
                called='You call out, "Single up, and stand by to let go!"',
                overheard=f'{who} calls out, "Single up, and stand by to let go!"',
                answered='The mate answers, "Singled up, aye sir."',
            )

        if event == LET_GO:
            return Order(
                called="",
                answered=(
                    "The gangway comes up. Lines are let go fore and aft, and she "
                    "swings clear of the quay."
                ),
            )

        if event == WORK_THE_FIX:
            return Order(
                called="",
                answered=f"The mate takes a bearing on {detail['landmark']} and works the fix.",
            )

        raise KeyError(event)

    def exterior(self, room=None):
        """
        What the sea outside looks like from a weather deck.

        Args:
            room (ShipRoom, optional): Where the observer is standing. Height of
                eye comes from it, so a masthead sees further than a deck.

        Returns:
            lines (tuple): Sentences describing what is happening outside.

        Notes:
            Static rooms, moving world. A ship's compartments are ordinary
            Evennia objects that never change; everything that makes standing on
            her deck feel like being at sea is out here, assembled fresh each
            time somebody looks.

            Nothing is invented for it. Her motion, the wind, the water and what
            the lookout can see are all already being computed - this is the one
            place they are put into a sentence.

        """
        vessel = self.vessel
        lines = []

        motion = self.motion_line(vessel)
        if motion:
            lines.append(motion)

        weather = self.weather_line(vessel)
        if weather:
            lines.append(weather)

        height = getattr(room, "height_of_eye", None)
        sighted = self.sighted_line(vessel, height)
        if sighted:
            lines.append(sighted)

        return tuple(lines)

    def motion_line(self, vessel):
        """
        Args:
            vessel (Vessel): The hull.

        Returns:
            line (str): What she is doing.

        """
        held = vessel.held_by()
        if held == "docked":
            return "She lies alongside, still and solid underfoot."
        if held == "aground":
            return "She sits canted and unmoving, hard on the ground."
        if held == "anchored":
            return "She lies to her anchor, swinging slowly with the water."
        if vessel.speed <= 0.0:
            return "She lies quiet, with no way on her at all."
        return f"She runs {compass_point(vessel.heading)}, the sea sliding past her rail."

    def weather_line(self, vessel):
        """
        Args:
            vessel (Vessel): The hull.

        Returns:
            line (str): The wind, and the water under it.

        """
        wind = vessel.wind_here()
        force = beaufort_force(wind.speed)
        if force == 0:
            weather = "There is not a breath of wind, and the water lies like oil."
        else:
            weather = (
                f"{BEAUFORT_NAMES[force].capitalize()} comes out of the "
                f"{compass_point(wind.bearing)}."
            )

        sea = self.sea_line(vessel.sea_here())
        if sea:
            weather += f" {sea}"

        current = vessel.current_here()
        if current.running:
            weather += f" The water itself is setting {compass_point(current.set)}."
        return weather

    def sea_line(self, sea_state):
        """
        What the water is doing, said the way it looks rather than named.

        Args:
            sea_state (str): One of `SEA_STATES`.

        Returns:
            line (str): A sentence, or empty for a sea flat enough not to mention.

        Notes:
            A calm and a rippled sea are not worth remarking on every time
            somebody looks - the absence of waves is not news. Everything from a
            slight sea upward is.

        """
        return SEA_DESCRIPTIONS.get(sea_state, "")

    def sighted_line(self, vessel, height_of_eye=None):
        """
        Args:
            vessel (Vessel): The hull.
            height_of_eye (float, optional): How high the observer is standing.

        Returns:
            line (str): What is in sight, or an empty horizon.

        Notes:
            Uses the observer's own height, so the same look from a masthead and
            from the deck can honestly disagree about whether there is anything
            out there.

        """
        seen = vessel.contacts(height_of_eye) if height_of_eye else vessel.contacts()
        if not seen:
            return "Nothing breaks the horizon."

        nearest = seen[0]
        where = bearing_in_points(nearest.relative)
        rest = ""
        if len(seen) > 1:
            others = len(seen) - 1
            rest = f", and {others} more sail{'s' if others != 1 else ''} besides"
        return f"A sail stands {where}{rest}."

    def stand_watches(self, seen):
        """
        Tell anyone keeping a watch what has come and gone in their arc.

        Args:
            seen (tuple): Everything the ship can see, nearest first.

        Notes:
            A watch is kept from where the watcher is standing, so one set at the
            masthead genuinely sees further than one set on deck - the same
            contact can be news to one and invisible to the other.

            What each watcher has already been shown is kept on their `.ndb`, so
            it empties on a reload exactly as the ship's own memory of her
            contacts does. Both refill together and nobody is told the sea is
            newly full of ships.

        """
        vessel = self.vessel
        for room in vessel.ship_rooms:
            if room.exposure not in WEATHER_DECKS:
                continue
            for watcher in room.contents:
                where = watcher.attributes.get("maritime_watch", None) if watcher.pk else None
                if not where:
                    continue
                direction = direction_named(where)
                if direction is None:
                    continue
                self.report_watch(watcher, room, direction, seen)

    def report_watch(self, watcher, room, direction, seen):
        """
        Tell one watcher what has changed in their arc.

        Args:
            watcher (Object): Whoever is keeping the watch.
            room (ShipRoom): Where they are standing.
            direction (tuple): From `direction_named`.
            seen (tuple): Everything the ship can see.

        """
        name, centre, width, relative = direction
        height = getattr(room, "height_of_eye", None)
        if height is not None and height != self.vessel.height_of_eye:
            seen = self.vessel.contacts(height)
        found = in_arc(seen, centre, width, relative=relative)

        was = dict(watcher.ndb.maritime_watched or {})
        now = {}
        for sighting in found:
            now[sighting.target.id] = sighting.level
            if sighting.target.id not in was:
                watcher.msg(self.came_into_view(name, sighting))
        for gone in was:
            if gone not in now:
                watcher.msg(self.went_out_of_view(name))
        watcher.ndb.maritime_watched = now

    def describe_contact(self, sighting):
        """
        Say as much about a contact as the range allows.

        Args:
            sighting (Sighting): What was seen.

        Returns:
            text (str): What an observer can honestly say it is.

        Notes:
            Bounded by the detection level rather than by what the target
            actually is. A hull at the edge of vision is a shape on the water
            even though the engine knows her name, and saying the name anyway
            would make closing to identify pointless.

        """
        if sighting.level == IDENTIFIED:
            return f"the {sighting.target.key}"
        if sighting.level == CLASSIFIED:
            plan = sighting.target.sail_plan
            return "a vessel under sail" if plan.area > 0.0 else "a vessel, sails furled"
        if sighting.level == VESSEL:
            return "a sail"
        return "something on the water"

    def contact_line(self, sighting):
        """
        One contact, as a line of a report.

        Args:
            sighting (Sighting): What was seen.

        Returns:
            line (str): Where to look, her true bearing, her range and what she
                is.

        Notes:
            Both bearings, because they answer different questions. The relative
            one turns a head in the right direction; the true one goes on the
            chart, and stays put when the ship comes round.

        """
        return (
            f"  {bearing_in_points(sighting.relative).capitalize():<32}"
            f"{spell_bearing(sighting.bearing):>7}"
            f"{format_range(sighting.distance):>14}   "
            f"{self.describe_contact(sighting)}"
        )

    def sector_report(self, where, sightings, horizon=None):
        """
        What is in sight in one direction.

        Args:
            where (str): What the direction is called - "fore", "north".
            sightings (tuple): `Sighting` objects in that arc, nearest first.
            horizon (float, optional): How far the observer can see, in metres.

        Returns:
            lines (tuple): What the watch reports.

        """
        phrase = self.direction_phrase(where)
        if not sightings:
            empty = f"Nothing in sight {phrase}."
            if horizon:
                empty += f" The horizon is {format_range(horizon)} off."
            return (empty,)

        lines = [f"Looking {phrase}:"]
        lines.extend(self.contact_line(sighting) for sighting in sightings)
        return tuple(lines)

    def all_round(self, sweep, horizon=None):
        """
        Everything around the ship, quarter by quarter.

        Args:
            sweep (tuple): `(name, sightings)` pairs, in the order to report.
            horizon (float, optional): How far the observer can see, in metres.

        Returns:
            lines (tuple): The whole sweep.

        Notes:
            Reports empty quarters as well as full ones, and deliberately. A
            lookout who only mentions what he can see leaves you unable to tell
            "nothing there" from "nobody looked", and those are very different
            things to know before altering course.

        """
        lines = ["The horizon, all round:"]
        if horizon:
            lines[0] = f"The horizon, all round - {format_range(horizon)} off:"
        for name, sightings in sweep:
            heading = self.direction_phrase(name).capitalize()
            if not sightings:
                lines.append(f"  {heading:<16}nothing")
                continue
            lines.append(f"  {heading:<16}{self.describe_contact(sightings[0])}, ")
            lines[-1] += (
                f"{bearing_in_points(sightings[0].relative)}, "
                f"{format_range(sightings[0].distance)}"
            )
            for extra in sightings[1:]:
                lines.append(f"  {'':<16}{self.describe_contact(extra)}, ")
                lines[-1] += f"{bearing_in_points(extra.relative)}, {format_range(extra.distance)}"
        return tuple(lines)

    def direction_phrase(self, where):
        """
        Args:
            where (str): A direction name.

        Returns:
            phrase (str): How a sailor would say it - "to starboard", "astern".

        """
        return DIRECTION_PHRASES.get(where, f"to the {where}")

    def watch_set(self, where):
        """
        Args:
            where (str): The direction now being watched.

        Returns:
            line (str): Confirmation.

        """
        return f"You settle down to watch {self.direction_phrase(where)}."

    def watch_ended(self):
        """
        Returns:
            line (str): Confirmation that the watch is over.

        """
        return "You stand down from your watch."

    def came_into_view(self, where, sighting):
        """
        Args:
            where (str): The direction being watched.
            sighting (Sighting): What has appeared.

        Returns:
            line (str): What the watcher notices.

        """
        return (
            f"Something lifts over the horizon {self.direction_phrase(where)}: "
            f"a sail, {bearing_in_points(sighting.relative)}."
        )

    def went_out_of_view(self, where):
        """
        Args:
            where (str): The direction being watched.

        Returns:
            line (str): What the watcher notices.

        """
        return f"The sail you were watching {self.direction_phrase(where)} sinks from sight."

    def passage_made(self):
        """
        Tell the ship the sailing master has run out of marks.

        Notes:
            He gives up the con rather than holding it and doing nothing. A mate
            who has finished should say so, or nobody knows whether she is being
            steered.

        """
        self.deliver(
            "The sailing master reports the passage made, and hands back the con.",
            "Word comes down that the passage is made.",
        )

    def trimmed(self, plan):
        """
        Tell the ship the watch has changed her canvas.

        Args:
            plan (SailPlan): What she is carrying now.

        """
        self.deliver(
            f"Without being told, the watch shortens to {plan.name}.",
            f"You hear the watch working aloft; she is under {plan.name} now.",
        )

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


# Marks on a hand lead line, in fathoms. Leather, rags and knots at these depths
# and nothing at the others, so a leadsman could read the line by feel in the
# dark. The unmarked fathoms between them are the deeps, which is why a call
# names which kind it is: "by the mark" means he felt something, "by the deep"
# means he counted.
LEAD_MARKS = (2, 3, 5, 7, 10, 13, 15, 17, 20)

# How much line a hand lead has. Past this there is no answer to give.
LEAD_LINE_FATHOMS = 20

# Spoken numbers, because a leadsman calls rather than reads. Two is "twain" in
# this call and nowhere else - the archaic form survived precisely because it
# could not be confused with anything else shouted across a deck.
# Index 0 is never used - a call of under one fathom is handled before this.
_FATHOM_WORDS = (
    "",
    "one",
    "twain",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
    "twenty",
)


def leadsman_call(metres):
    """
    Call a sounding the way a leadsman calls it.

    Args:
        metres (float): Depth of water, in metres. Not clearance under the keel -
            a leadsman reports what his line finds, and knows nothing about the
            draft of the ship he is standing on.

    Returns:
        call (str): e.g. `"By the mark seven!"`, `"And a half three!"`,
            `"A quarter less eight!"`, `"No bottom with this line!"`

    Notes:
        Read to the quarter fathom, because that is as fine as a wet line marked
        in leather and rag can be read. A depth landing on a mark is called by
        it; one landing between marks is called by the deep; a quarter or a half
        over is called as such, and three quarters is called down from the
        fathom above - "a quarter less eight" rather than "and three quarters
        seven", which is both shorter and harder to mishear.

    """
    quarters = int(round(metres / METRES_PER_FATHOM * 4.0))
    if quarters <= 0:
        return "No water under her at all - she is on the ground!"
    if quarters < 4:
        return "Less than a fathom, sir!"

    whole, remainder = divmod(quarters, 4)
    if remainder == 3:
        whole, remainder = whole + 1, -1
    if whole > LEAD_LINE_FATHOMS:
        return "No bottom with this line!"

    word = _FATHOM_WORDS[whole]
    if remainder == -1:
        return f"A quarter less {word}!"
    if remainder == 1:
        return f"And a quarter {word}!"
    if remainder == 2:
        return f"And a half {word}!"
    return f"By the {'mark' if whole in LEAD_MARKS else 'deep'} {word}!"
