"""
Making water.

Sinking should be a process you fight, not a threshold you cross. A ship that is simply
deleted when a number reaches a line has taken the last hour of somebody's afternoon and
given them nothing to do with it; a ship that is filling, and might yet be saved, is the
best situation this simulation can produce.

So `Buoyancy` has always carried a sink rate with nothing to drive it. This is what drives
it.

**The dilemma is the mirror of fire's, and deliberately not a copy.** Fire wants her stopped
because the hoses go over the side. Flooding wants her stopped for a different reason
entirely: **way through the water forces water in.** A breach with eight knots behind it
takes far more than the same breach lying quiet, because the sea is being driven into it. So

    fire      stop, or you cannot fight it
    flooding  stop, or you cannot outpump it

and a ship that is both alight and filling has one crew, two jobs, and a single decision
about her speed that makes one of them worse whichever way she takes it. That is the best
thing in the whole damage model and it costs nothing extra to build, because both halves were
built for their own reasons.

**Fothering is the third option, and it is the historical one.** Draw a sail under the hull
and let the sea press it into the hole. It is slow, it costs you the sail, and it does not
mend anything - but it turns a leak she cannot outpump into one she can, which is exactly
what it did for the ships that survived to report it.

**When she does go, her people go into the boats.** That is `boats`, and it is why having
them shot away during the fight is a consequence that outlives it. Whoever gets no seat is
in the water, and what *that* means is the game's - the event this publishes carries the
conditions so it can decide well.

"""

import math
from dataclasses import dataclass

from .damage import HULL
from .events import Event, bus
from .floating import Buoyancy
from .results import Result
from .vessel import OPEN

#: The share of her buoyancy that has to be water before she goes down.
FOUNDERS_AT = 1.0

#: How fast a completely opened hull fills, as a share of her buoyancy per minute, lying
#: still.
#:
#: Twenty minutes from open to gone, which is long enough to be a fight and short enough to
#: be frightening. Ships of the age that filled did it in that sort of time unless something
#: gave way all at once.
LEAK_AT_WORST = 0.05

#: The speed, in metres a second, at which way through the water doubles what comes in.
#:
#: About ten knots. The sea is being driven into the hole rather than finding its own way,
#: and every knot she carries is more of it.
SPEED_THAT_DOUBLES = 5.0

#: Hands wanted to work her pumps properly.
HANDS_PER_PUMP = 25.0

#: The exponent that makes more hands help less, as with a fire party.
DIMINISHING = 0.6

#: What fully-manned pumps shift, as a share of her buoyancy per minute.
#:
#: Set against `LEAK_AT_WORST` on purpose: pumps beat a badly holed ship that has stopped,
#: and lose to the same ship running. That single comparison is the whole decision.
PUMP_AT_BEST = 0.04

#: How long it takes to get a sail under her, in seconds.
FOTHERING_TIME = 900.0

#: How much of the inflow a fothered sail holds back.
FOTHERING_RELIEF = 0.6

#: How deep the water gets in a compartment before it is given up.
#:
#: Half its height. A man works in water to his knees and not to his chest, and by the time
#: it is over the gratings there is nothing down there worth doing anyway.
GIVEN_UP_AT = 0.5

#: How fast she goes down once she is no longer floating, in metres a second.
FOUNDERING_RATE = 0.4

NOT_MAKING_WATER = "not_making_water"
ALREADY_FOTHERED = "already_fothered"
STILL_FOTHERING = "still_fothering"
NO_CANVAS = "no_canvas"
FOUNDERED = "foundered"


@dataclass(frozen=True, kw_only=True)
class Foundered(Event):
    """
    She has gone down.

    Attributes:
        vessel (object): The hull.
        water (float): How much she had in her at the end.
        aboard (int): How many people were on her.

    Notes:
        Carries who was aboard because that is the question a game has to answer and this
        contrib will not: what becomes of them. The ruling is that they take to the boats
        and then the water, and a game that wants something else listens here.

    """

    vessel: object
    water: float = 0.0
    aboard: int = 0


@dataclass(frozen=True, kw_only=True)
class WaterResult(Result):
    """
    What the water did in one stretch of time.

    Attributes:
        water (float): How much is in her now, as a share of her buoyancy.
        came_in (float): What made its way in.
        pumped (float): What the pumps and buckets took out.
        inflow (float): The rate it is coming in at, per minute.
        outflow (float): The rate they are shifting it, per minute.
        gaining (bool): Whether the water is winning.
        foundered (bool): Whether she went down in this stretch.
        effect (float): How much good the pumps are doing, 0 to 1.
        fothered (bool): Whether a sail is under her.

    """

    water: float = 0.0
    came_in: float = 0.0
    pumped: float = 0.0
    inflow: float = 0.0
    outflow: float = 0.0
    gaining: bool = False
    foundered: bool = False
    effect: float = 0.0
    fothered: bool = False


def leak_rate(hull_damage, speed, fothered=False):
    """
    How fast she is making water.

    Args:
        hull_damage (float): Her hull track, 0 to 1.
        speed (float): Her speed through the water, in metres a second.
        fothered (bool, optional): Whether a sail has been drawn under the hull.

    Returns:
        rate (float): Share of her buoyancy per minute.

    Notes:
        **Squared in the damage**, so a scraped hull barely weeps and an opened one floods.
        A linear leak would have every damaged ship slowly sinking, which would make the
        whole model a nuisance rather than a crisis - the interesting states are dry and
        drowning, not permanently damp.

        **Linear in her speed**, because the water is being forced in. This is the term
        that makes running expensive, and it is why a ship that could outrun her enemy
        cannot always afford to.

    """
    hurt = max(0.0, min(1.0, float(hull_damage)))
    if not hurt:
        return 0.0
    rate = LEAK_AT_WORST * hurt * hurt
    rate *= 1.0 + abs(float(speed)) / SPEED_THAT_DOUBLES
    if fothered:
        rate *= 1.0 - FOTHERING_RELIEF
    return rate


def pump_rate(hands, per_pump=HANDS_PER_PUMP, falloff=DIMINISHING):
    """
    What the hands on her pumps shift.

    Args:
        hands (float): How many are on them.
        per_pump (float, optional): Hands wanted to work them properly.
        falloff (float, optional): The exponent that makes more help less.

    Returns:
        rate (float): Share of her buoyancy per minute.

    Notes:
        Diminishing like a fire party and for the same reason: there are only so many
        places to stand. Past the point where the pumps are manned, the extra hands are
        queueing rather than pumping, and they are hands that could be somewhere useful.

    """
    hands = max(0.0, float(hands))
    if not hands or per_pump <= 0.0:
        return 0.0
    return PUMP_AT_BEST * min(1.0, (hands / per_pump) ** falloff)


def time_to_founder(water, inflow, outflow):
    """
    How long she has, at this rate.

    Args:
        water (float): How much is in her, as a share of her buoyancy.
        inflow (float): Coming in, per minute.
        outflow (float): Going out, per minute.

    Returns:
        seconds (float): How long until she founders, or `math.inf` if she is holding it.

    Notes:
        The number a captain actually wants. Not "how bad is it" but "how long have I
        got", because that is what a decision is made against.

    """
    gaining = float(inflow) - float(outflow)
    if gaining <= 0.0:
        return math.inf
    left = max(0.0, FOUNDERS_AT - float(water))
    return (left / gaining) * 60.0


class MakesWater:
    """
    A hull that fills through her own damage, and the people who fight it.

    Notes:
        The water is a single number rather than a set of compartments. Compartments would
        be more faithful to a modern ship and less faithful to this period - a wooden hull
        is one space with a bilge, and water in the fore hold is water in the ship.

    """

    def at_object_creation(self):
        """Set up this part of a newly created vessel."""
        super().at_object_creation()
        self.db.water = 0.0
        self.db.pump_party = 0.0
        self.db.fothered = False
        self.db.fothering_until = 0.0
        self.db.buoyancy = Buoyancy()

    @property
    def buoyancy(self):
        """
        Returns:
            buoyancy (Buoyancy): Whether she is up, and how fast she goes down if not.

        Notes:
            The same field `floating.Floating` keeps, deliberately, and not inherited from
            it. `Floating` is for things that have no way of their own - a barrel, a raft,
            a man - and giving a ship its position handling would be the wrong half of the
            right idea. What a foundered ship shares with a barrel is only this: she is
            somewhere, going down, and still a place.

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
            raise TypeError(f"Buoyancy must be a Buoyancy, got {type(buoyancy).__name__}.")
        self.db.buoyancy = buoyancy

    @property
    def afloat(self):
        """
        Returns:
            afloat (bool): Whether she is still up.

        """
        return bool(self.buoyancy.floats)

    @property
    def water(self):
        """
        Returns:
            water (float): How much is in her, as a share of her buoyancy.

        """
        return float(self.db.water or 0.0)

    @property
    def making_water(self):
        """
        Returns:
            making (bool): Whether she is taking any in.

        """
        return self.leak() > 0.0

    @property
    def pump_party(self):
        """
        Returns:
            hands (float): How many are on the pumps.

        """
        return float(self.db.pump_party or 0.0)

    @property
    def fothered(self):
        """
        Returns:
            fothered (bool): Whether a sail is under her hull.

        """
        return bool(self.db.fothered)

    def leak(self):
        """
        Returns:
            rate (float): What she is making, as a share of her buoyancy per minute.

        Notes:
            **Two sources, added.** The hull track is her general condition - strained seams,
            started planks, everything a number per track can say. `sections` adds what is
            coming through holes that are actually below her waterline, which the track
            cannot say because it does not know where anything is.

            They are added rather than one replacing the other, because they are different
            water. A ship with no holes in her still weeps at the seams if she has been
            hammered, and a ship holed once below the waterline is in trouble that her
            otherwise sound hull does not describe.

        """
        seams = leak_rate(self.damage.of(HULL), self.speed, self.fothered)
        holes = self.breach_inflow() if hasattr(self, "breach_inflow") else 0.0
        return seams + (holes * (1.0 - FOTHERING_RELIEF) if self.fothered else holes)

    def untenable(self):
        """
        Which of her compartments the water has driven her people out of.

        Returns:
            drowned (tuple): Compartments, lowest first.

        Notes:
            **She fills from the bottom**, which is not a modelling choice so much as the
            only thing water does. The share of her buoyancy she has lost is taken as the
            share of her internal height the sea has climbed, so the orlop goes first, the
            hold next, and the weather deck only when she is going anyway.

            **And it is given up before it is full**, at `GIVEN_UP_AT` of its own height.
            A compartment that only counted as lost when it was full to the beams would let
            a ship with a third of her buoyancy gone still have people working comfortably
            in the bilge, and would drown them all at once at the end instead of driving
            them up a deck at a time.

            Derived on asking rather than flagged on each compartment. A stored flag would
            have to be cleared when the pumps gained, and a hold that stayed marked flooded
            after it had been pumped out is exactly the kind of stale state that survives
            a code review and not a playtest.

        """
        rooms = [room for room in self.ship_rooms if room.exposure != OPEN]
        if not rooms:
            return ()

        levels = sorted({room.deck_level for room in rooms})
        risen = float(self.water)
        drowned = {
            level
            for rank, level in enumerate(levels)
            if risen >= (rank + GIVEN_UP_AT) / len(levels)
        }
        return tuple(
            sorted(
                (room for room in rooms if room.deck_level in drowned),
                key=lambda room: room.deck_level,
            )
        )

    def highest_deck(self):
        """
        Returns:
            room (object or None): The compartment furthest from the water.

        """
        rooms = list(self.ship_rooms)
        if not rooms:
            return None
        return max(rooms, key=lambda room: (room.exposure == OPEN, room.deck_level))

    def flood_out(self):
        """
        Get her people out of the compartments the sea has taken.

        Returns:
            moved (tuple): Who had to leave.

        Notes:
            **Up, not off.** Somebody driven out of a flooded hold is on deck, not in the
            water - she has not foundered yet, and confusing the two would drown a crew
            every time a hold took water. `abandon_ship` is a different moment and this is
            not it.

            Called from the tick, so a player standing in the hold of a ship that is filling
            is moved by the water rather than by a message telling them they ought to move.

        """
        drowning = self.untenable()
        if not drowning:
            return ()

        higher = self.highest_deck()
        if higher is None or higher in drowning:
            return ()

        moved = []
        for room in drowning:
            for thing in tuple(room.contents):
                if getattr(thing, "destination", None) is not None:
                    continue
                if not thing.is_typeclass("evennia.objects.objects.DefaultCharacter", exact=False):
                    continue
                thing.location = higher
                moved.append(thing)
        return tuple(moved)

    def man_pumps(self, hands):
        """
        Put hands on the pumps.

        Args:
            hands (float): How many. Zero calls them off.

        Returns:
            result (WaterResult): What that buys her.

        Notes:
            They are the same hands a fire wants, and the same hands the guns want. That
            competition is not modelled here because it is not arithmetic - it is a
            captain deciding, and the contrib's job is to make the decision cost
            something rather than to make it for him.

        """
        self.db.pump_party = max(0.0, float(hands))
        return self.water_report()

    def fother(self, now=None):
        """
        Draw a sail under the hull and let the sea press it into the hole.

        Args:
            now (float, optional): Game time. Fetched if not given.

        Returns:
            result (WaterResult): Successful once the work is begun.

        Notes:
            **It does not mend her.** It turns a leak she cannot outpump into one she can,
            and that is all - she still has to make port and she still has to be hauled
            out. What it buys is the chance to do either.

            It costs a sail, which a game may or may not care about, and it wants her
            quiet: a ship charging along will not keep the canvas where it was put. That
            second cost is not enforced here because the speed term in `leak_rate` already
            charges her for running, and charging twice for one decision is how a model
            stops being legible.

        """
        started = self._water_now() if now is None else float(now)
        if self.fothered:
            return WaterResult(success=False, code=ALREADY_FOTHERED, water=self.water)

        until = float(self.db.fothering_until or 0.0)
        if until:
            if started < until:
                return WaterResult(success=False, code=STILL_FOTHERING, water=self.water)
            self.db.fothered = True
            self.db.fothering_until = 0.0
            return self.water_report()

        self.db.fothering_until = started + FOTHERING_TIME
        return self.water_report()

    def water_report(self):
        """
        Returns:
            result (WaterResult): Where she stands, without advancing anything.

        """
        inflow = self.leak()
        outflow = pump_rate(self.pump_party)
        return WaterResult(
            success=True,
            water=self.water,
            inflow=inflow,
            outflow=outflow,
            gaining=inflow > outflow,
            effect=min(1.0, outflow / inflow) if inflow else 1.0,
            fothered=self.fothered,
        )

    def start_pumping_out(self):
        """
        Reset her to dry. For a game that has repaired or careened her.

        Returns:
            water (float): How much she had in her.

        """
        had = self.water
        self.db.water = 0.0
        return had

    def work_water(self, elapsed):
        """
        Let the water rise or fall for a stretch of time.

        Args:
            elapsed (float): Game seconds.

        Returns:
            result (WaterResult or None): What happened, or None if she is dry and tight.

        Notes:
            Runs even when she is not leaking, so that a ship with water in her and her
            hull mended still has to pump it out rather than being dry the moment the
            carpenter finishes.

        """
        minutes = max(0.0, float(elapsed)) / 60.0
        inflow = self.leak()
        outflow = pump_rate(self.pump_party)

        if not inflow and not self.water:
            return None

        # Fothering finishes on its own, so that a captain who ordered it does not have to
        # stand over the work and order it again.
        until = float(self.db.fothering_until or 0.0)
        if until and self._water_now() >= until:
            self.db.fothered = True
            self.db.fothering_until = 0.0
            inflow = self.leak()

        came_in = inflow * minutes
        pumped = min(outflow * minutes, self.water + came_in)
        water = max(0.0, self.water + came_in - pumped)

        foundered = water >= FOUNDERS_AT
        if foundered:
            water = FOUNDERS_AT
        self.db.water = water

        if foundered:
            self._founder()
        else:
            # She is not gone, but the hold may be. Whoever is standing in it comes up.
            self.flood_out()

        return WaterResult(
            success=True,
            code=FOUNDERED if foundered else None,
            water=water,
            came_in=came_in,
            pumped=pumped,
            inflow=inflow,
            outflow=outflow,
            gaining=inflow > outflow,
            foundered=foundered,
            effect=min(1.0, outflow / inflow) if inflow else 1.0,
            fothered=self.fothered,
        )

    def _founder(self):
        """
        She has gone down.

        Notes:
            Sets the buoyancy that `floating` has always been ready for and announces it.
            What becomes of the people aboard is the game's, and the event says how many
            there were so it can decide.

        """
        self.buoyancy = Buoyancy(floats=False, sink_rate=FOUNDERING_RATE)

        # **The boats, and then the water.** Her people go over the side before she does,
        # into whatever boats she has left - which is why having them shot away during the
        # fight is a consequence that outlives it. Whoever gets no seat is in the water, and
        # what that means is the game's: the event below carries what it needs to decide.
        self.abandon_ship()

        # **And then she is a place.** She stops being a ship the moment the buoyancy goes,
        # but she does not stop being *somewhere* - `wrecks` records when, lets what will
        # float free do so, and hands the rest to the seabed she sank over.
        self.go_down()

        company = self.company
        bus().publish(
            Foundered(
                game_time=self._water_now(),
                vessel=self,
                water=self.water,
                aboard=company.complement if company is not None else 0,
            )
        )

    def _water_now(self):
        """
        Returns:
            now (float): Game time in seconds.

        """
        from . import config

        return config.time_provider().now()
