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
from .formatting import about_how_long, format_range, format_speed, pick_scale
from .cargo import VOLUME, WEIGHT, stowed_volume
from .oars import (
    EASY_OARS,
    GIVE_WAY,
    HOLD_WATER,
    PADDLE,
    PADDLED,
    STRETCH_OUT,
    hands_available,
)
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
from .buoyage import ISOLATED_DANGER as ISOLATED_DANGER_KIND

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

#: How much drive has to be gone before anybody aboard remarks on it. The edge of a
#: wind shadow is a gradient, so without a threshold a ship sailing along one would
#: report entering and leaving it every few seconds - the wallpaper this module
#: exists to prevent. A twentieth of her drive is about where sails begin to slat.
NOTICEABLE_BLANKET = 0.05

#: Words that already do the work of "the". A vessel whose name carries its own
#: article should not be given a second one.
ARTICLES = ("the", "a", "an")


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
STOW_ORDER = "stow_order"
STROKE_ORDER = "stroke_order"
GRAPPLE_ORDER = "grapple_order"
CUT_GRAPPLES = "cut_grapples"
STRIKE_ORDER = "strike_order"
DISCHARGE_ORDER = "discharge_order"


#: What each stroke order sounds like, called and answered, in each vocabulary.
#:
#: Two columns rather than one with substitutions, because they are not the same
#: sentence with a word changed. A coxswain orders a boat's crew; a kayaker talks to
#: nobody at all, and giving them a bowman to answer would be worse than silence.
STROKE_CALLS = {
    (GIVE_WAY, False): ("Give way together!", "The oars come down and she gathers way."),
    (GIVE_WAY, True): ("You dig the blade in and settle to it.", ""),
    (PADDLE, False): ("Paddle ahead.", "The stroke shortens and she eases off."),
    (PADDLE, True): ("You ease off to a gentle stroke.", ""),
    (STRETCH_OUT, False): ("Stretch out!", "Backs go into it and the boat lifts."),
    (STRETCH_OUT, True): ("You put your back into it.", ""),
    (EASY_OARS, False): ("Easy all.", "Blades come out and she runs on."),
    (EASY_OARS, True): ("You lift the blade clear and let her run.", ""),
    (HOLD_WATER, False): ("Hold water!", "Blades bite and she stops in a length and a half."),
    (HOLD_WATER, True): ("You jam the blade in and she stops almost at once.", ""),
}


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


def open_sentence(text):
    """
    Raise the first letter of a phrase and leave the rest of it alone.

    Args:
        text (str): The phrase.

    Returns:
        text (str): The same phrase, fit to start a sentence.

    Notes:
        Not `str.capitalize`, which lowercases everything after the first
        character. That is harmless on a generated phrase and wrong the moment
        the phrase contains a name - it turned the Kittiwake into the kittiwake,
        which no test caught and one look at the water did.

    """
    return text[:1].upper() + text[1:]


def describe_contact(sighting):
    """
    Say as much about a contact as the range allows.

    Args:
        sighting (Sighting): What was seen.

    Returns:
        text (str): What an observer can honestly say it is.

    Notes:
        Bounded by the detection level rather than by what the target actually
        is. A hull at the edge of vision is a shape on the water even though the
        engine knows her name, and saying the name anyway would make closing to
        identify pointless.

        A function rather than a method because both narrators need exactly this
        answer and neither needs anything of the other. A ship seen from a deck
        and the same ship seen from the water at the same range are the same
        ship, described the same way.

    """
    if sighting.level == IDENTIFIED:
        # Ships are spoken of with the article - "the Marigold" - but a game is
        # free to have put one in the name itself, and "the the Kittiwake" is how
        # that reads on a deck. Seen live in a sweep.
        name = sighting.target.key
        article = "" if name.split(" ", 1)[0].lower() in ARTICLES else "the "
        return f"{article}{name}"
    if sighting.level == CLASSIFIED:
        plan = sighting.target.sail_plan
        return "a vessel under sail" if plan.area > 0.0 else "a vessel, sails furled"
    if sighting.level == VESSEL:
        return "a sail"
    return "something on the water"


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

        if event == STOW_ORDER:
            what = detail["what"]
            tonnes = detail["tonnes"]
            return Order(
                called=f'You call out, "Get {tonnes:.0f} tons of {what} aboard."',
                overheard=f'{who} calls out, "Get {tonnes:.0f} tons of {what} aboard."',
                answered='The mate answers, "Aye sir - rig the yard tackle."',
            )

        if event == DISCHARGE_ORDER:
            what = detail["what"]
            tonnes = detail["tonnes"]
            return Order(
                called=f'You call out, "Break out {tonnes:.0f} tons of {what}."',
                overheard=f'{who} calls out, "Break out {tonnes:.0f} tons of {what}."',
                answered='The mate answers, "Aye sir - hands to the hatches."',
            )

        if event == STROKE_ORDER:
            plan = detail["plan"]
            called, answered = STROKE_CALLS[(detail["stroke"], plan.style == PADDLED)]
            if plan.style == PADDLED:
                return Order(called=called, overheard=f"{who} settles to a new stroke.")
            return Order(
                called=f'You call out, "{called}"',
                overheard=f'{who} calls out, "{called}"',
                answered=answered,
            )

        if event == GRAPPLE_ORDER:
            name = detail["name"]
            return Order(
                called='You call out, "Grapnels away - get her alongside!"',
                overheard=f'{who} calls out, "Grapnels away!"',
                answered=f"Irons and lines go across towards the {name}.",
            )

        if event == CUT_GRAPPLES:
            return Order(
                called='You call out, "Cut the grapples!"',
                overheard=f'{who} calls out, "Cut the grapples!"',
                answered="Axes come down on the lines.",
            )

        if event == STRIKE_ORDER:
            return Order(
                called='You call out, "Strike the colours."',
                overheard=f"{who} gives the order to strike.",
                answered="Nobody says anything at all.",
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
        return describe_contact(sighting)

    def contact_line(self, sighting, scale=None):
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
            f"{format_range(sighting.distance, scale=scale):>14}   "
            f"{self.describe_contact(sighting)}"
        )

    def mark_line(self, sighting, scale=None):
        """
        One navigational mark, as a line of a report.

        Args:
            sighting (Sighting): The mark that was seen.

        Returns:
            line (str): Where to look, its bearing, its range, and what it means.

        Notes:
            The meaning is the part worth printing. "A buoy, two miles" tells a
            navigator nothing he could act on; "south cardinal - safe water to the
            south" tells him which way to go round, which is the only reason the
            thing was moored there.

        """
        mark = sighting.target
        return (
            f"  {bearing_in_points(sighting.relative).capitalize():<32}"
            f"{spell_bearing(sighting.bearing):>7}"
            f"{format_range(sighting.distance, scale=scale):>14}   "
            f"{self.describe_mark(mark)}"
        )

    def describe_mark(self, mark):
        """
        Args:
            mark (Waypoint): The mark.

        Returns:
            text (str): Its name and what it is telling you.

        """
        from .buoyage import safe_water_from

        towards = safe_water_from(mark.kind)
        if towards is not None:
            return f"the {mark.key} - safe water to the {compass_point(towards)}"
        if mark.kind == ISOLATED_DANGER_KIND:
            return f"the {mark.key} - foul ground, deep water all round it"
        return f"the {mark.key}"

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
            # One range on its own, so there is nothing for it to disagree with and
            # no scale to choose. The horizon is only ever reported here, in the
            # branch where nothing else is.
            empty = f"Nothing in sight {phrase}."
            if horizon:
                empty += f" The horizon is {format_range(horizon)} off."
            return (empty,)

        # One unit for the whole column, on the same grounds as `all_round`: it is
        # there to be compared down, and a list reading "2.7 miles" against "1.5
        # leagues" has given that up.
        scale = pick_scale([sighting.distance for sighting in sightings])
        lines = [f"Looking {phrase}:"]
        lines.extend(self.contact_line(sighting, scale) for sighting in sightings)
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
        # One unit for the whole sweep, chosen before a word of it is written. A
        # range column exists to be compared at a glance, and "2.9 miles" on one
        # line with "1.5 leagues" on the next gives that up.
        ranges = [sighting.distance for _name, found in sweep for sighting in found]
        if horizon:
            ranges.append(horizon)
        scale = pick_scale(ranges)

        lines = ["The horizon, all round:"]
        if horizon:
            lines[0] = f"The horizon, all round - {format_range(horizon, scale=scale)} off:"
        for name, sightings in sweep:
            heading = self.direction_phrase(name).capitalize()
            if not sightings:
                lines.append(f"  {heading:<16}nothing")
                continue
            lines.append(f"  {heading:<16}{self.describe_contact(sightings[0])}, ")
            lines[-1] += (
                f"{bearing_in_points(sightings[0].relative)}, "
                f"{format_range(sightings[0].distance, scale=scale)}"
            )
            for extra in sightings[1:]:
                lines.append(f"  {'':<16}{self.describe_contact(extra)}, ")
                lines[-1] += (
                    f"{bearing_in_points(extra.relative)}, "
                    f"{format_range(extra.distance, scale=scale)}"
                )
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

    def stowed(self, result, commodity):
        """
        What went aboard, and what it did to her.

        Args:
            result (TransferResult): What crossed the rail.
            commodity (Commodity): What was being loaded.

        Returns:
            lines (tuple): What the deck hears.

        Notes:
            Always says which capacity stopped her, because "she is full" and
            "she is down on her marks" are different problems with different
            answers. A ship that cubed out will take a denser cargo; one that
            weighed out will not take anything at all.

        """
        moved = result.parcel.tonnes
        lines = [
            f"{moved:.0f} tons of {commodity.name} go down into the " f"{result.hold.key.lower()}."
        ]
        if result.refused > 0.0:
            lines.append(self.refusal_line(result, commodity))
        return tuple(lines)

    def refusal_line(self, result, commodity):
        """
        Args:
            result (TransferResult): What crossed the rail, and what did not.
            commodity (Commodity): What was being loaded.

        Returns:
            line (str): Why the rest of it is still on the quay.

        """
        left = result.refused
        if result.limit == WEIGHT:
            return (
                f"{left:.0f} tons of {commodity.name} stay on the quay - she is down "
                f"on her marks and will not take the weight."
            )
        if result.limit == VOLUME:
            return (
                f"{left:.0f} tons of {commodity.name} stay on the quay - the holds are "
                f"full, though she would carry the weight of something denser."
            )
        return f"{left:.0f} tons of {commodity.name} stay on the quay."

    def discharged(self, result, commodity):
        """
        Args:
            result (TransferResult): What came out.
            commodity (Commodity): What was being discharged.

        Returns:
            lines (tuple): What the deck hears.

        """
        moved = result.parcel.tonnes
        lines = [f"{moved:.0f} tons of {commodity.name} come up out of her and go ashore."]
        if result.refused > 0.0:
            lines.append(f"There is no more {commodity.name} aboard.")
        return tuple(lines)

    def manifest(self, stowage):
        """
        Everything aboard, and how she is sitting for it.

        Args:
            stowage (Stowage): One reading of how she is loaded.

        Returns:
            lines (tuple): The manifest, then her condition.

        Notes:
            The condition is the part worth reading. A list of cargo is a list;
            what a master needs to know before he sails is how deep she is, how
            much freeboard is left and whether the weight is too high in her.

            Each line shows the hold that parcel actually occupies rather than
            the volume of the goods themselves, so the column adds up to the
            total. Showing the raw figure and a total that included broken
            stowage made the manifest look like it could not add.

        """
        vessel = self.vessel
        lines = [f"|w{vessel.key}|n - manifest"]
        if not stowage.parcels:
            lines.append("  She is in ballast. There is nothing in her holds.")
        else:
            broken = vessel.broken_stowage
            for parcel in stowage.parcels:
                lines.append(
                    f"  {parcel.commodity.name:<20}{parcel.tonnes:>8.1f} tons"
                    f"{stowed_volume([parcel], broken):>10.1f} m3"
                )
            lines.append(f"  {'':<20}{stowage.tonnes:>8.1f} tons{stowage.volume:>10.1f} m3 stowed")

        lines.append("")
        lines.append(f"  Draught    {stowage.draft:.2f} m   freeboard {stowage.freeboard:.2f} m")
        lines.append(f"  Capacity   {self.capacity_line(stowage)}")
        if stowage.overloaded:
            lines.append("  |rShe is loaded past her marks. She is not fit to go to sea.|n")
        if stowage.tender:
            lines.append("  |yThe weight is too high in her. She will be tender in a seaway.|n")
        return tuple(lines)

    def capacity_line(self, stowage):
        """
        Args:
            stowage (Stowage): One reading of how she is loaded.

        Returns:
            line (str): Which capacity has run out, in words a mate would use.

        """
        if stowage.limit == WEIGHT:
            return "she has weighed out - no more weight will go in her"
        if stowage.limit == VOLUME:
            return "she has cubed out - the holds are full"
        return "she will take more of either weight or measurement"

    #: What each morale band looks like from the quarterdeck. The domain knows they
    #: are wavering; this is the only place that knows what wavering looks like.
    BEARING = {
        "steady": "steady, and going about their work",
        "uneasy": "uneasy - quieter than they were",
        "shaken": "shaken. Orders are obeyed a beat late",
        "wavering": "wavering. Some of them are looking to the boats",
        "broken": "broken. Whatever is asked of them now will be half done",
    }

    #: And how spent they are. A scale rather than a number, because nobody standing
    #: on a deck ever knew their crew were at sixty-one per cent.
    SPENT = (
        (0.85, "spent - there is nothing left in them"),
        (0.65, "flagging badly"),
        (0.40, "tiring"),
        (0.15, "working hard, but holding it"),
        (0.0, "fresh"),
    )

    #: What the company hold against their command, said plainly. These are the words
    #: that turn a number into a warning a captain can act on.
    GRIEVANCE = {
        "driven": "they have been driven past what they have in them",
        "butchered": "they are being spent, and the colours are still flying",
        "leaderless": "there is nobody aft giving orders",
    }

    #: What each structural failure looks like from the deck. These are the lines a
    #: player will remember afterwards - not that a number went down, but that the
    #: maintopmast came over the side and took the forestay with it.
    CARRIED_AWAY = {
        "mast down": (
            "A mast goes over the side with a crack you feel through the deck, "
            "and hangs alongside in a raffle of rigging.",
            "Something enormous comes down on deck. She lurches, and stays lurched.",
        ),
        "holed": (
            "She is holed below the waterline. You can hear the sea coming in.",
            "The planking bursts inward and the sea comes in with it.",
        ),
        "disabled": (
            "The last of her sweeps is shot away. She will not be pulled anywhere.",
            "The rowing stops, and does not start again.",
        ),
        "disarmed": (
            "The last gun is dismounted. She has nothing left to fight with.",
            "The guns fall silent above you.",
        ),
    }

    #: What it looks like to run a shot the length of somebody. Named because it is
    #: the moment of the age - a captain works an hour for this and it is over in
    #: seconds, and if it went past as an unusually large number nobody would know
    #: what they had just done.
    RAKED = {
        "bow rake": "The shot goes in at her bow and runs the length of her.",
        "stern rake": (
            "The shot goes in through her stern windows and runs the whole length "
            "of her gundeck. Nothing in the way of it is left standing."
        ),
    }

    def raked(self, target, rake):
        """
        Tell the ship she has raked somebody.

        Args:
            target (Vessel): Who took it.
            rake (str): `BOW_RAKE` or `STERN_RAKE`.

        Notes:
            Said to the ship that *fired*, because it is her achievement. What it
            looked like from the receiving end is that ship's own business, and
            worse.

        """
        spoken = self.RAKED.get(rake)
        if spoken:
            self.deliver(f"You rake the {target.key}. {spoken}")

    def carried_away(self, failures):
        """
        Tell the ship what has just broken.

        Args:
            failures (iterable): Keys from `damage.structural`, as returned by
                `take_damage` - only what is *newly* wrong.

        Notes:
            Said once each, because that is what `take_damage` hands over. A mast
            already over the side does not come down again, and the alternative -
            announcing every failure on every hit - is how a battle becomes
            unreadable at exactly the moment it gets interesting.

        """
        for failure in failures:
            spoken = self.CARRIED_AWAY.get(failure)
            if spoken:
                self.deliver(*spoken)

    def giving_a_berth(self, mark, altered=0.0):
        """
        The mate alters course to clear a marked danger.

        Args:
            mark (Waypoint or None): What he is keeping clear of, or None if the
                water ahead is clear.
            altered (float, optional): How far off the ordered course he came.

        Notes:
            Said out loud, and it has to be. A helmsman who quietly steered somewhere
            other than where he was told would be a bug wearing a feature's coat -
            the player has to know the course was changed, what changed it, and by
            how much, or the next time they look at the compass they will not trust
            it.

            Said *once*, which took a live sail to notice. Clearing a mark takes
            many ticks and the first version announced every one of them, which is
            precisely the wallpaper this module exists to prevent: a ship reports
            that she is coming round, not that she is still turning. The state rides
            on `.ndb` beside the shoaling warning, and resets when the water ahead is
            clear so the next mark is announced properly.

        """
        vessel = self.vessel
        if mark is None:
            # Nothing to say - and crucially, nothing to forget. Clearing a mark
            # settles at exactly the berth, so she stops turning, swings back
            # towards her course, and raises the same danger again a moment later.
            # Resetting here made her announce the same buoy twice on one passage.
            return
        if vessel.ndb.berth_given == mark.key:
            return
        vessel.ndb.berth_given = mark.key
        self.deliver(
            f'The mate says, "Giving the {mark.key} a berth, sir." '
            f"She comes round {altered:.0f} degrees.",
            f"She comes round. Word is they are keeping clear of the {mark.key}.",
        )

    def in_the_lee(self, blanket):
        """
        Somebody to windward has taken her wind, or given it back.

        Args:
            blanket (Blanket): The worst shadow on her, and who is casting it.

        Notes:
            Said out loud for the same reason the mate calls a course alteration: a
            ship that silently lost a third of her speed would be an invisible
            penalty, and the captain would go looking for damage that is not there.
            Naming the ship responsible is the whole of it - the answer to "why are
            we slowing" is "because she is to windward of us", and the answer to
            that is to alter course, which is a decision rather than a wait.

            Announced on the way in and on the way out, once each. The state rides
            on `.ndb` beside the berth warning, keyed by *who* has the wind of her,
            so that passing from one ship's lee straight into another's is reported
            as the new ship rather than passed over in silence.

        """
        vessel = self.vessel
        held = blanket.lost >= NOTICEABLE_BLANKET
        was = vessel.ndb.blanketed_by

        if not held:
            if was is not None:
                vessel.ndb.blanketed_by = None
                self.deliver(
                    'The mate says, "Our wind again, sir." The sails fill and stiffen.',
                    "Her sails fill and stiffen as she comes out into clear air.",
                )
            return

        who = blanket.vessel.key if blanket.vessel is not None else None
        if was == who:
            return
        vessel.ndb.blanketed_by = who
        self.deliver(
            f'The sails slat and go slack. The mate says, "{who} has the wind of us, sir."',
            f"Her sails slat and go slack in {who}'s lee.",
        )

    def opportunity_fire(self, sighting, holding):
        """
        The moment a held battery decides to speak.

        Args:
            sighting (Sighting): What crossed the arc.
            holding (Holding): What the order was.

        Notes:
            Said before the broadside rather than after, because the order the
            deck hears matters: the guns going off on their own is alarming, and
            the sentence that explains it should arrive first.

            A ship held on an *arc* is named only as what the lookout can honestly
            call her, which may be nothing more than a shape. That is the whole
            danger of the order, and softening it here by using her real name
            would hide the one thing the captain needs to see.

        """
        if holding.target_key is not None:
            self.deliver(
                '"There she is!" The battery goes off without further orders.',
                "The guns go off overhead without an order being passed.",
            )
            return
        self.deliver(
            f"{open_sentence(describe_contact(sighting))} crosses the "
            f"{holding.arc}, and the held guns take her.",
            "The guns go off overhead without an order being passed.",
        )

    def broadside(self, result):
        """
        Say what a broadside did, on both decks.

        Args:
            result (Broadside): What it did.

        Notes:
            Gathered into one place because two callers fire broadsides now - a
            captain who orders one, and a battery that has been holding its fire
            and just found something in its arc. From a deck they are the same
            event and should sound like it.

            What broke aboard the other ship is said aboard *her*, through her own
            narrator. A rake is said here, because it is this ship's achievement
            and what it looked like from the receiving end is her business, and
            worse.

        """
        if not result.fired:
            self.deliver(
                "Not a gun is ready. The crews are still at it.",
                "The guns stay silent; they are still being served.",
            )
            return

        guns = f"{result.fired} gun{'s' if result.fired != 1 else ''}"
        self.deliver(
            f"{guns} go off together, and the smoke rolls away to leeward.",
            f"{guns} go off overhead, and the whole hull jumps with it.",
        )

        if result.hits:
            self.deliver(
                f"{result.hits} of them tell on {result.target.key}, "
                f"{format_range(result.distance)} off."
            )
        else:
            self.deliver(f"The whole broadside goes wide of {result.target.key}.")

        for rake in result.rakes:
            self.raked(result.target, rake)
        if result.carried_away:
            result.target.narrator.carried_away(result.carried_away)

    def crew_report(self, vessel):
        """
        Who she is manned by, and how they are bearing it.

        Args:
            vessel (Vessel): The ship.

        Returns:
            lines (tuple): Her company, or a single line if she has none.

        Notes:
            The grievances are the part worth having. A morale number tells a captain
            his people are unhappy; this tells him what about, and every one of them
            is something he did - which is the only kind of warning anybody can act
            on before it becomes a rising.

        """
        company = vessel.company
        if company is None:
            return ("She has no ship's company. Whoever is aboard is who works her.",)

        lines = [f"|w{vessel.key}|n - {company.fit} of {company.complement} hands"]
        lines.append(f"  Rated      {company.quality.key}")
        if company.casualties:
            lines.append(
                f"  Casualties {company.casualties} "
                f"({company.casualty_fraction * 100:.0f}% of her company)"
            )
        lines.append(f"  Bearing    They are {self.BEARING[vessel.morale_band]}.")
        lines.append(f"  Condition  They are {self.spent_words(vessel.exhaustion)}.")

        held = vessel.held_against_command()
        if held:
            lines.append("")
            lines.append("  |rWhat they hold against you:|n")
            for grievance in held:
                lines.append(f"    {self.GRIEVANCE[grievance]}")
        return tuple(lines)

    def spent_words(self, exhaustion):
        """
        Args:
            exhaustion (float): How spent they are, 0 to 1.

        Returns:
            words (str): What that looks like from the deck.

        """
        for floor, words in self.SPENT:
            if exhaustion >= floor:
                return words
        return self.SPENT[-1][1]

    def oar_report(self, vessel):
        """
        What she is being pulled by, and what it is making.

        Args:
            vessel (Vessel): The boat.

        Returns:
            lines (tuple): Her arrangement, her crew, and both speeds.

        Notes:
            Both speeds, because in a river they are different numbers and the
            difference is the whole story. A crew pulling two knots up a
            one-knot stream is working exactly as hard as one making three knots
            down it, and only the ground says so.

        """
        plan = vessel.oar_plan
        crew = vessel.rowing_crew
        hands = "paddler" if plan.style == PADDLED else "rower"
        lines = [f"|w{vessel.key}|n - {plan.name}"]
        lines.append(
            f"  Crew       {crew} of {plan.positions} {hands}"
            f"{'' if crew == 1 else 's'}"
            f"  ({hands_available(plan, crew) * 100:.0f}% of her power)"
        )
        lines.append(f"  Stroke     {vessel.stroke.replace('_', ' ')}")
        lines.append(f"  Through the water  {format_speed(vessel.rowing_speed())}")

        made = vessel.made_good()
        if made is not None:
            course, over_ground = made
            lines.append(
                f"  Over the ground    {format_speed(over_ground)}, "
                f"course {spell_bearing(course)}"
            )
        return tuple(lines)

    def grappled(self, result, other):
        """
        The irons have gone across and held.

        Args:
            result (GrappleResult): What the throw achieved.
            other (Vessel): The hull now alongside.

        Returns:
            lines (tuple): What the deck hears.

        Notes:
            Plain metres rather than `format_range`, which is right everywhere
            else and wrong here: it says "alongside" for anything under a cable,
            so the sentence came out as "fast alongside, alongside off". At
            grapnel range a bare number is what a sailor would say anyway.

        """
        return (
            f"The irons bite and the lines come taut. The {other.key} is fast "
            f"alongside, {result.distance:.0f} metres off.",
            "The grapples are a way across. So are they for her.",
        )

    def grapples_cut(self, other):
        """
        Args:
            other (Vessel): The hull let go.

        Returns:
            lines (tuple): What the deck hears.

        """
        return (
            f"The lines part under the axes and the {other.key} sheers away.",
            "Anybody left on the wrong deck is on the wrong deck.",
        )

    def grapples_parted(self, result):
        """
        The lines have gone on their own.

        Args:
            result (GrappleResult): The reading when they went.

        Notes:
            Delivered rather than returned, because nobody asked for this - it
            happens on the tick and the deck finds out about it the way a deck
            does, which is suddenly.

        """
        self.deliver(
            f"The lines come up bar-taut, snap, and whip back across the deck. "
            f"She has broken free at {format_speed(result.closure)}.",
            "Something heavy goes over on deck above you.",
        )

    def struck_colours(self, other):
        """
        Args:
            other (Vessel): Who she struck to.

        Returns:
            lines (tuple): What the deck hears.

        """
        return (
            "The colours come down.",
            f"She has struck to the {other.key}.",
        )

    def rehoisted(self, captor):
        """
        Args:
            captor (Vessel or None): Who she had struck to.

        Returns:
            line (str): What the deck hears.

        """
        name = f" The {captor.key} is not going to like it." if captor else ""
        return f"The colours go back up.{name}"

    def grapple_report(self, vessel):
        """
        What she is fast to, and how hard the lines are working.

        Args:
            vessel (Vessel): The hull.

        Returns:
            lines (tuple): The reading.

        Notes:
            Reports the relative speed rather than either ship's, because that is
            what the lines are actually taking. Two hulls matched to a tenth of a
            knot hold all day at any speed at all.

        """
        from .boarding import MAX_HOLDING_CLOSURE, relative_speed

        other = vessel.grappled_to
        closing = relative_speed(vessel.heading, vessel.speed, other.heading, other.speed)
        lines = [f"|w{vessel.key}|n - fast to the {other.key}"]
        lines.append(
            f"  Relative speed  {format_speed(closing)}"
            f"   (the lines will take {format_speed(MAX_HOLDING_CLOSURE)})"
        )
        if closing > MAX_HOLDING_CLOSURE * 0.7:
            lines.append("  |yThe lines are working hard. She is trying to get away.|n")
        if vessel.struck:
            lines.append(f"  She has struck to the {vessel.struck_to.key}.")
        if other.struck:
            lines.append(f"  The {other.key} has struck.")
        return tuple(lines)

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

    def hands_aloft(self, plan, seconds):
        """
        The hands go up to make a change of canvas.

        Args:
            plan (SailPlan): What they have been sent to set.
            seconds (float): How long they are expected to be at it.

        Notes:
            The estimate is the point of saying anything. An order that took an
            unknown time would leave a captain guessing whether to wait or to order
            something else, and guessing is not the decision this is meant to
            create. The decision is whether he has time for it, and he can only make
            that if he knows roughly what it costs.

        """
        self.deliver(
            f"The hands go aloft to set {plan.name}. It will be {about_how_long(seconds)}.",
            "You hear them working aloft.",
        )

    def sail_set(self, plan):
        """
        The change of canvas is finished.

        Args:
            plan (SailPlan): What she is carrying now.

        """
        self.deliver(
            f'The mate reports, "{plan.name.capitalize()} set, sir." The hands come down.',
            f"The working overhead stops, and she settles to {plan.name}.",
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


class WaterNarrator:
    """
    Turns being in the sea into what the person in it perceives.

    Attributes:
        position (WorldPosition): Where they are.
        swimmer (Object or None): Whoever is in the water.

    Notes:
        A separate voice from `VesselNarrator`, and not a subclass of it, because
        almost nothing carries across. A ship narrates her own behaviour to
        people standing on her; the sea narrates nothing and does not know anyone
        is there. Everything below is what a person in the water could work out
        for themselves, which is very little, and that scarcity is the point.

        Bearings are given as compass points rather than relative ones. A lookout
        says "broad on the port bow" because the ship has a head to be relative
        to; a swimmer turning in the water does not, and reporting a relative
        bearing from a body with no heading would be inventing a fact.

    """

    def __init__(self, position, swimmer=None):
        """
        Args:
            position (WorldPosition): Where the water is.
            swimmer (Object, optional): Who is in it.

        """
        self.position = position
        self.swimmer = swimmer

    def surface(self):
        """
        What can be perceived from the surface of the sea.

        Returns:
            lines (tuple): Sentences, in the order they are worth hearing.

        """
        lines = [self.water_line()]
        ground = self.ground_line()
        if ground:
            lines.append(ground)
        lines.append(self.wind_line())
        lines.extend(self.sighted_lines())
        return tuple(line for line in lines if line)

    def water_line(self):
        """
        Returns:
            line (str): The sea itself, from surface level.

        Notes:
            The same sea state a deck would report reads very differently from
            in it. A moderate sea is a pleasant sail and a serious problem for a
            swimmer, so this is written from the water rather than reusing
            `SEA_DESCRIPTIONS`, which is written from a rail.

        """
        from . import environment

        sea = environment.sea_state_at(self.position)
        if sea in (CALM, RIPPLED):
            return "You are in the open sea, and it lies almost flat around you."
        if sea == SMOOTH:
            return "You are in the open sea, lifting and falling on a low swell."
        return (
            "You are in the open sea. It heaves around you, and the horizon "
            "disappears each time you go down into a trough."
        )

    def ground_line(self):
        """
        Returns:
            line (str): Whether there is ground within reach, or empty when there
                is not.

        Notes:
            Only spoken when the bottom is close enough to stand on. A swimmer in
            deep water has no way to know what is under them, and telling them
            would hand out a sounding nobody took.

        """
        from . import config, environment
        from .floating import STANDING_DEPTH

        depth = environment.clearance_at(self.position, 0.0, config.time_provider().now())
        if depth > STANDING_DEPTH:
            return ""
        if depth <= 0.0:
            return "Your feet are on dry ground. You are not swimming at all."
        return "Your feet find the bottom. You can stand here."

    def wind_line(self):
        """
        Returns:
            line (str): The wind, felt rather than measured.

        """
        from . import environment

        wind = environment.wind_at(self.position)
        force = beaufort_force(wind.speed)
        if force == 0:
            return "There is no wind at all, and no sound but your own breathing."
        if force <= 3:
            return f"A light air comes out of the {compass_point(wind.bearing)}."
        return (
            f"{BEAUFORT_NAMES[force].capitalize()} comes out of the "
            f"{compass_point(wind.bearing)}, and takes the tops off the water."
        )

    def sighted_lines(self):
        """
        Returns:
            lines (tuple): What can be seen from surface level, nearest first.

        Notes:
            A swimmer sees further than the horizon suggests, because height
            beats the curve and a ship carries hers in her masts. What is lost
            from down here is everything low: a boat, a raft, another swimmer.
            The asymmetry runs the cruel way round - you watch her stand on for
            an hour, and from her deck there is nothing to see.

        """
        from . import environment
        from .floating import SWIMMER_HEIGHT_OF_EYE

        seen = environment.contacts_from(
            self.position,
            0.0,
            SWIMMER_HEIGHT_OF_EYE,
            environment.vessels_within_sight(self.position, SWIMMER_HEIGHT_OF_EYE),
        )
        if not seen:
            return ("Nothing at all breaks the horizon.",)
        # One unit here too. Someone in the water has worse problems than unit
        # conversion, and this is the report they most need to read at a glance.
        scale = pick_scale([sighting.distance for sighting in seen])
        return tuple(
            f"{open_sentence(self.describe_contact(sighting))} lies to the "
            f"{compass_point(sighting.bearing)}, "
            f"{format_range(sighting.distance, scale=scale)} off."
            for sighting in seen
        )

    def describe_contact(self, sighting):
        """
        Args:
            sighting (Sighting): What was seen.

        Returns:
            phrase (str): What it can be called at this range.

        Notes:
            Deliberately the same wording `VesselNarrator` uses, from the same
            function rather than a second copy of it. Two descriptions of one
            ship that drifted apart would let a player tell where the observer
            was standing from the prose, which is a tell rather than a feature.

        """
        return describe_contact(sighting)
