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
#: How many hands one grapnel takes to throw, haul in and make fast.
#:
#: A line is not a switch. Somebody heaves the iron, somebody swigs it down, and somebody
#: takes a turn round a cleat while she is still moving - which is why a short-handed ship
#: gets fewer lines across than a full one from exactly the same position.
HANDS_PER_LINE = 3.0

#: The most lines two hulls will ever get across each other.
#:
#: Not a balance number: it is how many places there are along a rail to make one fast
#: before they start fouling each other. Beyond about a dozen the extra irons are landing on
#: top of the ones already there.
MOST_LINES = 12

#: How much of a hull's length has to be alongside for a full set of lines.
#:
#: Two ships meeting bow to bow have one point of contact and can get a couple of irons
#: across it. Two lying side by side have their whole length, and the difference is what
#: makes laying yourself alongside properly worth the trouble.
FULL_CONTACT = 0.6

#: How much harder each line makes it to break free, as a share of one line's worth.
#:
#: Sub-linear on purpose. Twelve lines do not hold twelve times as hard as one - they share
#: the load unevenly and the first few take most of it - but they do hold harder, and a ship
#: that has been thoroughly lashed should not sheer off as easily as one held by two irons.
HOLD_PER_LINE = 0.25

#: Hand-seconds of work to clear one iron that is holding.
#:
#: **Unfouling is harder the more contact there is**, which is the other half of making
#: lines a count. Getting free of two irons is a minute's work with an axe; getting free of
#: twelve, with the two hulls grinding together and half of them under strain, is an
#: undertaking - and a captain who let himself be thoroughly lashed has to live with it.
WORK_PER_IRON = 45.0

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
NOTHING_HELD = "nothing_held"
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
    lines: int = 0


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


def alongside(own_position, own_heading, own_length, her_position, her_heading, her_length):
    """
    How much of the two hulls are actually side by side.

    Args:
        own_position (WorldPosition): Where you are.
        own_heading (float): Your heading, in degrees.
        own_length (float): Your length, in metres.
        her_position (WorldPosition): Where she is.
        her_heading (float): Hers.
        her_length (float): Hers.

    Returns:
        overlap (float): The share of the shorter hull that has the other one beside it,
            0 to 1.

    Notes:
        **Contact geometry, which is what decides how many irons can reach.** Measured by
        projecting her stem and stern onto your fore-and-aft line and asking how much of you
        that span covers - so two ships lying parallel and level share their whole length,
        two meeting bow to bow share almost nothing, and a ship laid across another's stern
        shares whatever her quarter reaches.

        The shorter hull is the divisor. A ship's boat alongside a first-rate is entirely
        alongside her, even though she covers a twentieth of the bigger ship - and it is the
        boat's rail that runs out of places to make a line fast.

    """
    shorter = min(own_length, her_length)
    if shorter <= 0.0:
        return 0.0

    half = her_length / 2.0
    ends = sorted(
        _along_hull(own_position, own_heading, her_position.moved(her_heading, reach))
        for reach in (half, -half)
    )
    mine = own_length / 2.0
    overlap = min(ends[1], mine) - max(ends[0], -mine)
    return max(0.0, min(overlap, shorter)) / shorter


def _along_hull(origin, heading, point):
    """
    Args:
        origin (WorldPosition): The centre of the hull being measured against.
        heading (float): Her heading, in degrees.
        point (WorldPosition): The point to place.

    Returns:
        along (float): Metres forward of her centre, negative aft.

    """
    import math

    distance = origin.horizontal_distance_to(point)
    if distance <= 0.0:
        return 0.0
    return distance * math.cos(math.radians(origin.bearing_to(point) - heading))


def lines_across(overlap, closure, hands, skill=1.0, closure_limit=MAX_BOARDING_CLOSURE):
    """
    How many irons get across and are made fast.

    Args:
        overlap (float): How much of the hulls are alongside, from `alongside`.
        closure (float): Relative motion between them, in metres per second.
        hands (float): What her people are worth at working the ship.
        skill (float, optional): A multiplier for how handy they are.
        closure_limit (float, optional): The closure at which nothing will hold.

    Returns:
        lines (int): How many are fast. Zero means the boarding failed.

    Notes:
        **A count rather than a yes.** Everything about being lashed to another ship follows
        from how many lines are holding: whether she can sheer off, how long it takes to cut
        free, and how much of the two rails are close enough to fight across.

        Three things decide it and each can veto it on its own. How much of the two hulls
        are alongside says how many places there are to make one fast. The relative motion
        says how many of those throws stay put - a hull sheering away takes the iron with
        her. And the hands say how many the crew can actually get over, because each one
        costs three of them and a ship with sixty fit men cannot work twenty lines.

    """
    reach = min(1.0, max(0.0, overlap) / FULL_CONTACT)
    steady = 1.0 - min(1.0, max(0.0, closure) / max(1e-9, closure_limit))
    crew = max(0.0, hands) * max(0.0, skill) / HANDS_PER_LINE
    return int(min(MOST_LINES, MOST_LINES * reach * steady, crew))


def holding_closure(lines, base=MAX_HOLDING_CLOSURE, per_line=HOLD_PER_LINE):
    """
    How much relative motion the lines will take before they part.

    Args:
        lines (int): How many are fast.
        base (float, optional): What one line will take.
        per_line (float, optional): What each extra adds, as a share of the base.

    Returns:
        closure (float): Metres per second she can sheer at and still be held.

    Notes:
        Sub-linear, and by the square root: the first irons take most of the load and the
        rest share what is left. Twelve lines hold roughly twice as hard as one rather than
        twelve times, which is enough to matter and not enough to make a well-lashed ship
        unbreakable - and breaking free has to stay possible, because it is what makes being
        boarded survivable and worth trying to survive.

    """
    import math

    return base * (1.0 + per_line * math.sqrt(max(0, lines - 1)))


def unfouling_time(lines, hands, hesitation=0.0):
    """
    How long it takes to clear the irons and get free.

    Args:
        lines (int): How many are fast.
        hands (float): What her people are worth at working the ship.
        hesitation (float, optional): How much of what they could do is not being done.

    Returns:
        seconds (float): How long they will be at it. Zero if nothing is holding.

    Notes:
        Routed through `handling_time` rather than divided out here, so that being short
        handed and being frightened cost the same on this job as they cost on every other -
        and so that an unmanned ship gets the same answer as she gets everywhere else, which
        is that the work never finishes rather than that it finishes instantly.

    """
    from .handling import handling_time

    return handling_time(WORK_PER_IRON * max(0, lines), hands, hesitation)


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
        self.db.lines = 0
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

        # **How many, not whether.** Everything about being lashed to another ship follows
        # from the count: how hard she is to shake off, how long it takes to cut free, and
        # how much of the two rails are close enough to fight across.
        fast = lines_across(
            alongside(here, self.heading, self.length, there, other.heading, other.length),
            result.closure,
            self.working_hands(),
        )
        if fast <= 0:
            return GrappleResult(
                success=False,
                code=NOTHING_HELD,
                distance=result.distance,
                closure=result.closure,
                target=other,
            )

        exits = rig_grapples(own_deck, her_deck)
        self.db.grappled_to = other
        self.db.grapples = list(exits)
        self.db.lines = fast
        other.db.grappled_to = self
        other.db.grapples = list(exits)
        other.db.lines = fast
        return GrappleResult(
            success=True,
            distance=result.distance,
            closure=result.closure,
            target=other,
            lines=fast,
        )

    def working_hands(self):
        """
        Returns:
            hands (float): What her people are worth at working the ship, or a nominal
                crew if nobody has manned her.

        Notes:
            A hull nobody has crewed still has to be able to grapple, because a game that
            has not modelled complements should get boarding rather than an exception. She
            is treated as adequately manned, which is the same courtesy the rest of the
            contrib extends to an unmeasured hull.

        """
        company = self.company
        if company is None:
            return MOST_LINES * HANDS_PER_LINE
        return company.hands

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
        self.db.lines = 0
        self.db.grappled_to = None
        if other is not None:
            unrig_gangway(other.db.grapples or ())
            other.db.grapples = []
            other.db.lines = 0
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

        # Two irons and twelve are not the same hold. The tolerated closure grows with the
        # count, so a ship that laid herself properly alongside and got her whole rail over
        # is genuinely harder to sheer away from than one held by a lucky throw.
        result = still_holding(
            here,
            self.heading,
            self.speed,
            there,
            other.heading,
            other.speed,
            closure=holding_closure(self.lines),
        )
        result = GrappleResult(
            success=bool(result),
            code=result.code,
            distance=result.distance,
            closure=result.closure,
            target=other,
            lines=self.lines,
        )
        if not result:
            self.cast_off_grapples()
        return result

    @property
    def lines(self):
        """
        Returns:
            lines (int): How many irons are fast to whatever she is holding.

        """
        return int(self.db.lines or 0)

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
