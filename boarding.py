"""
Grapples, and the crossing they make possible.

Boarding is not a combat mechanic. It is two hulls held together long enough for people
to walk from one to the other, and every hard part of it is seamanship:

    relative velocity   what actually matters, and it is not speed
    grapnel range       how far a man can throw an iron with a line on it
    holding             whether the lines take the strain or part
    the crossing        two ordinary exits between two weather decks

**Speed is not the constraint. Relative velocity is.** Two ships running side by side at
ten knots on the same course are motionless with respect to each other and can be lashed
together at leisure; the same two ships at four knots on opposing courses close at eight
and will tear the irons out of the rail. Matching her course and speed *is* the manoeuvre,
and modelling it any other way would make a chase and an ambush the same problem.

**Lines part.** A grapnel that held when she was matched does not hold when she sheers
off, so the attachment is re-tested as the hulls move rather than granted once. That is
what makes a boarded ship worth trying to shake off, and it is why the crossing has to be
something that can be taken away again.

**You board onto a deck, never into a hold.** The crossing links weather decks, because
that is where the rails are. A boarding party arriving in a sealed magazine would be a
routing accident presented as a tactic.

**No character combat here, and none coming.** The fight that follows is the host game's
own - it already has one, and a maritime contrib shipping a second would be arguing with
it. What this provides is the two ships held alongside and a way across.

**Who may command a prize is not decided here.** That she has struck is a fact and is
recorded; what that entitles the captor to do is a question about authority, which is
phase 14 and is Gary's. See `DECISIONS.md`.

"""

import math
from dataclasses import dataclass

from .position import bearing_difference
from .results import Result

# How far a grapnel can be thrown with a line bent to it, in metres. Short - this is a
# man throwing an iron, not a gun firing one - and it is why closing to board is a
# genuinely dangerous thing to have to do.
GRAPNEL_RANGE = 25.0

# How fast two hulls may be moving relative to one another and still be lashed
# together, in metres per second. About two knots: a walking pace of difference, which
# is what a crew can take up on the lines without them parting.
MAX_BOARDING_CLOSURE = 1.0

# How much relative speed the lines will stand once they are on, before they part.
# Higher than the figure for getting them on, because a made-up line has purchase a
# thrown one does not - but not by much, and a ship that sheers off hard will always
# break free.
MAX_HOLDING_CLOSURE = 2.5

# Why a grapple did not go on, or did not hold.
TOO_FAR = "too_far"
CLOSING_TOO_FAST = "closing_too_fast"
NO_DECK = "no_deck"
NOT_GRAPPLED = "not_grappled"
ALREADY_GRAPPLED = "already_grappled"
SAME_VESSEL = "same_vessel"
LINES_PARTED = "lines_parted"


@dataclass(frozen=True, kw_only=True)
class GrappleResult(Result):
    """
    What happened when the irons went across.

    Attributes:
        distance (float): How far apart the hulls were, in metres.
        closure (float): How fast they were moving relative to one another.
        target (object or None): The hull grappled, when one was.

    Notes:
        Carries both numbers whether it succeeded or failed, because "she is
        eighty metres off" and "she is alongside but drawing away at four knots"
        are different problems with different answers and a bare refusal tells a
        player neither.

    """

    distance: float = 0.0
    closure: float = 0.0
    target: object = None


def velocity(heading, speed):
    """
    A vessel's motion as components.

    Args:
        heading (float): Where her head is pointing, in degrees.
        speed (float): Speed through the water, in metres per second.

    Returns:
        components (tuple): `(east, north)` in metres per second.

    """
    radians = math.radians(heading)
    return speed * math.sin(radians), speed * math.cos(radians)


def relative_speed(own_heading, own_speed, her_heading, her_speed):
    """
    How fast two hulls are moving with respect to one another.

    Args:
        own_heading (float): Your heading, in degrees.
        own_speed (float): Your speed, in metres per second.
        her_heading (float): Hers.
        her_speed (float): Hers.

    Returns:
        speed (float): The magnitude of the difference, in metres per second.

    Notes:
        The number the whole of boarding turns on, and it is not either ship's
        speed. Two vessels running side by side at ten knots are motionless with
        respect to each other; the same two at four knots on opposing courses are
        closing at eight. Matching her course and speed is the manoeuvre.

        A magnitude rather than a signed closure, because for holding two hulls
        together it does not matter whether she is drawing ahead, dropping astern
        or sheering off - it matters how fast the gap is changing at all.

    """
    own_east, own_north = velocity(own_heading, own_speed)
    her_east, her_north = velocity(her_heading, her_speed)
    return math.hypot(own_east - her_east, own_north - her_north)


def within_reach(own_position, her_position, reach=GRAPNEL_RANGE):
    """
    Whether an iron would carry that far.

    Args:
        own_position (WorldPosition): Where you are.
        her_position (WorldPosition): Where she is.
        reach (float, optional): How far a grapnel throws, in metres.

    Returns:
        near (bool): True if she is close enough to try.

    """
    return own_position.horizontal_distance_to(her_position) <= reach


def can_grapple(
    own_position,
    own_heading,
    own_speed,
    her_position,
    her_heading,
    her_speed,
    reach=GRAPNEL_RANGE,
    closure=MAX_BOARDING_CLOSURE,
):
    """
    Whether the irons will go across and hold.

    Args:
        own_position (WorldPosition): Where you are.
        own_heading (float): Your heading, in degrees.
        own_speed (float): Your speed, in metres per second.
        her_position (WorldPosition): Where she is.
        her_heading (float): Hers.
        her_speed (float): Hers.
        reach (float, optional): How far a grapnel throws.
        closure (float, optional): Fastest relative motion that can be lashed.

    Returns:
        result (GrappleResult): Successful if the irons will hold, failed with a
            reason if not. Carries the distance and the closure either way.

    Notes:
        Range first, then relative motion. A ship a mile off is not "closing too
        fast", she is a mile off, and reporting the second problem when the first
        one is the real one sends a player to fix the wrong thing.

    """
    distance = own_position.horizontal_distance_to(her_position)
    closing = relative_speed(own_heading, own_speed, her_heading, her_speed)

    if distance > reach:
        return GrappleResult(success=False, code=TOO_FAR, distance=distance, closure=closing)
    if closing > closure:
        return GrappleResult(
            success=False, code=CLOSING_TOO_FAST, distance=distance, closure=closing
        )
    return GrappleResult(success=True, distance=distance, closure=closing)


def still_holding(
    own_position,
    own_heading,
    own_speed,
    her_position,
    her_heading,
    her_speed,
    reach=GRAPNEL_RANGE,
    closure=MAX_HOLDING_CLOSURE,
):
    """
    Whether lines already made up are still holding.

    Args:
        own_position (WorldPosition): Where you are.
        own_heading (float): Your heading, in degrees.
        own_speed (float): Your speed, in metres per second.
        her_position (WorldPosition): Where she is.
        her_heading (float): Hers.
        her_speed (float): Hers.
        reach (float, optional): How far the lines run before they are drawn out.
        closure (float, optional): Most relative motion a made-up line will take.

    Notes:
        A looser test than getting them on, and deliberately: a line made fast has
        purchase a thrown one does not, so a crew can hold a ship that was sheering
        gently. It is not much looser, because a hull that puts her helm hard over
        and fills her sails will always break free - which is what makes being
        boarded survivable and worth trying to survive.

    Returns:
        result (GrappleResult): Successful while the lines hold, failed with
            `LINES_PARTED` when they do not.

    """
    distance = own_position.horizontal_distance_to(her_position)
    closing = relative_speed(own_heading, own_speed, her_heading, her_speed)

    if distance > reach or closing > closure:
        return GrappleResult(success=False, code=LINES_PARTED, distance=distance, closure=closing)
    return GrappleResult(success=True, distance=distance, closure=closing)


def bears_alongside(own_heading, own_position, her_position):
    """
    Whether she lies on a beam rather than ahead or astern.

    Args:
        own_heading (float): Your heading, in degrees.
        own_position (WorldPosition): Where you are.
        her_position (WorldPosition): Where she is.

    Returns:
        alongside (bool): True if she is broad enough on the bow or quarter to
            come alongside rather than to be rammed.

    Notes:
        Advisory rather than a precondition. Ships have boarded across a bow and
        over a stern, and a rule forbidding it would be inventing a restriction
        that the sea does not have - but a player asking "can I board her" wants
        to know that she is dead ahead, because that is a collision rather than a
        boarding.

    """
    relative = abs(bearing_difference(own_heading, own_position.bearing_to(her_position)))
    return 30.0 <= relative <= 150.0


class Boarded:
    """
    The Evennia-side face of this module: irons out, or irons in.

    Notes:
        A hull knows one thing about boarding - whether she is lashed to another
        and by what crossing. Everything about the fight that follows is the host
        game's, and everything about what a captor may then *do* with her is
        phase 14 and Gary's.

    """

    def at_object_creation(self):
        """Set up this part of a newly created vessel."""
        super().at_object_creation()
        self.db.grappled_to = None
        self.db.grapples = []
        self.db.struck_to = None

    # --- what she is holding on to ------------------------------------------

    @property
    def grappled_to(self):
        """
        Returns:
            vessel (Vessel or None): The hull she is lashed to, or None.

        """
        held = self.db.grappled_to
        return held if held and held.pk else None

    @property
    def grappled(self):
        """
        Returns:
            grappled (bool): Whether she is held to anything.

        """
        return self.grappled_to is not None

    @property
    def boarding_deck(self):
        """
        The deck a boarding party crosses to.

        Returns:
            room (ShipRoom or None): Her highest weather deck, or None if she has
                none - which is a hull nobody can board, and a real answer.

        Notes:
            Highest rather than any, so a party arrives where the rail is rather
            than in a companionway. You board onto a deck, never into a hold: a
            boarding party materialising in a sealed magazine would be a routing
            accident presented as a tactic.

        """
        from .vessel import WEATHER_DECKS

        decks = [room for room in self.ship_rooms if room.exposure in WEATHER_DECKS]
        if not decks:
            return None
        return max(decks, key=lambda room: room.deck_level)

    # --- getting the irons across -------------------------------------------

    def grapple(self, other):
        """
        Throw the irons and lash her alongside.

        Args:
            other (Vessel): The hull to board.

        Returns:
            result (GrappleResult): What happened, with the distance and the
                closure whether it worked or not.

        Notes:
            Rigs the crossing on success and nothing on failure, so a refused
            boarding leaves no exit anybody could walk through by accident.

        """
        from .rooms import rig_grapples

        if other is self:
            return GrappleResult(success=False, code=SAME_VESSEL, target=other)
        if self.grappled or getattr(other, "grappled", False):
            return GrappleResult(success=False, code=ALREADY_GRAPPLED, target=other)

        own_deck, her_deck = self.boarding_deck, other.boarding_deck
        if own_deck is None or her_deck is None:
            return GrappleResult(success=False, code=NO_DECK, target=other)

        here, there = self.maritime_position, other.maritime_position
        if here is None or there is None:
            return GrappleResult(success=False, code=TOO_FAR, target=other)

        result = can_grapple(here, self.heading, self.speed, there, other.heading, other.speed)
        if not result:
            return GrappleResult(
                success=False,
                code=result.code,
                distance=result.distance,
                closure=result.closure,
                target=other,
            )

        exits = rig_grapples(own_deck, her_deck)
        self.db.grappled_to = other
        self.db.grapples = list(exits)
        other.db.grappled_to = self
        other.db.grapples = list(exits)
        return GrappleResult(
            success=True, distance=result.distance, closure=result.closure, target=other
        )

    def cast_off_grapples(self):
        """
        Cut the lines and take the crossing away.

        Returns:
            freed (bool): True if there was anything to cut.

        Notes:
            Clears both hulls. A one-sided release would leave the other believing
            she was still held, and the first symptom would be a ship refusing to
            grapple anything ever again.

        """
        from .rooms import unrig_gangway

        other = self.grappled_to
        unrig_gangway(self.db.grapples or ())
        self.db.grapples = []
        self.db.grappled_to = None
        if other is not None:
            unrig_gangway(other.db.grapples or ())
            other.db.grapples = []
            other.db.grappled_to = None
            return True
        return False

    def check_grapples(self):
        """
        Test lines already made up, and cut them if they have parted.

        Returns:
            result (GrappleResult or None): The reading, or None if she is not
                grappled to anything.

        Notes:
            Called on the tick, because a grapple that was granted once and never
            re-tested would make being boarded permanent. A ship that puts her
            helm hard over and fills her sails will always break free, and that is
            what makes being boarded survivable and worth trying to survive.

        """
        other = self.grappled_to
        if other is None:
            return None

        here, there = self.maritime_position, other.maritime_position
        if here is None or there is None:
            self.cast_off_grapples()
            return GrappleResult(success=False, code=LINES_PARTED, target=other)

        result = still_holding(here, self.heading, self.speed, there, other.heading, other.speed)
        if not result:
            self.cast_off_grapples()
        return result

    # --- striking -----------------------------------------------------------

    @property
    def struck_to(self):
        """
        Returns:
            vessel (Vessel or None): The hull she struck her colours to.

        """
        taken = self.db.struck_to
        return taken if taken and taken.pk else None

    @property
    def struck(self):
        """
        Returns:
            struck (bool): Whether she has surrendered.

        """
        return self.struck_to is not None

    def strike(self, to):
        """
        Strike her colours.

        Args:
            to (Vessel): The hull she surrenders to.

        Returns:
            struck (bool): True if she had not already struck.

        Notes:
            Records a fact and confers nothing. That she has struck is a matter of
            history; what it entitles her captor to *do* - who may give her orders,
            who owns her, what happens to the people aboard - is a question about
            authority, which is phase 14 and is Gary's. See `DECISIONS.md`.

        """
        if self.struck:
            return False
        self.db.struck_to = to
        return True

    def rehoist(self):
        """
        Take back a surrender.

        Returns:
            rehoisted (bool): True if she had struck.

        Notes:
            Exists because a prize crew can be overwhelmed and a boarding can be
            repelled, and a state that could only be entered would make either of
            those unrepresentable.

        """
        if not self.struck:
            return False
        self.db.struck_to = None
        return True
