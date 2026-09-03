"""
People who have paid to be somewhere else.

Cargo does not care when it arrives and does not complain, which is why a trade in cargo
alone makes a quiet game. A passenger is the same tonnage with an opinion: he is bound for a
named place, he paid before he sailed, and if she does not go there he wants his money back.
That is the whole of what this module adds, and it is enough to make a schedule matter.

**A passenger is whoever the game says is one.** Not a typeclass, not a character sheet -
an object and a destination. A game with NPC travellers and a game where the passengers are
other players use the same machinery, because the only thing this contrib needs to know is
where somebody is going.

**A timetable that cannot be kept is refused before she sails, not after.** A run that
repeats has to close: she must get back to where she started in the time the schedule
allows, or the second cycle begins late and every one after it begins later. Checking that
is arithmetic on distances the routes already know, and it is far kinder to say so when the
schedule is written than to let a game discover it three voyages in.

**The fare is taken when the passage is booked and refunded if she does not arrive.** Money
moves through `ledger`, onto the *ship's* purse, because a vessel earning her keep is a
vessel that can pay for her own repairs - and where a game's own economy takes it from there
is a game's business.

"""

from dataclasses import dataclass

from .ledger import Coin
from .results import Result

#: How much room one passenger wants, in cubic metres.
#:
#: Eight. A cabin passenger of the period had rather less than that and steerage had a great
#: deal less, but a ship that could carry two hundred people in her hold is a ship whose
#: interesting constraint has stopped being room and started being water and provisions -
#: which is a different model. This number keeps the constraint where a player can see it.
VOLUME_PER_PASSENGER = 8.0

#: The most of her internal volume that can be given over to people.
#:
#: A third. The rest is her hold, her stores and the working of the ship, and a hull with
#: every cubic metre full of passengers has nowhere to keep what they eat.
MOST_OF_HER = 0.34

NO_ROOM = "no_room"
NOT_ABOARD = "not_aboard"
ALREADY_ABOARD = "already_aboard"
NOT_THERE_YET = "not_there_yet"
CANNOT_REFUND = "cannot_refund"
CANNOT_BE_KEPT = "cannot_be_kept"
NO_ROUTE = "no_route"


@dataclass(frozen=True)
class Passage:
    """
    One person, and where he is going.

    Attributes:
        traveller (object): Whoever it is.
        bound_for (str): The name of the place he paid to reach.
        fare (Coin): What he paid.

    """

    traveller: object
    bound_for: str
    fare: Coin = None

    def stored(self):
        """
        Returns:
            stored (dict): The booking in a form an attribute can hold.

        Notes:
            **A dataclass holding a live object does not pickle.** Evennia's serialiser
            walks dicts, lists and tuples and knows how to pack a typeclassed object it
            finds in one; it cannot see inside a dataclass, so a `Passage` written straight
            to an attribute raises on the way in. A dict goes in, a `Passage` comes back
            out, and the object reference is packed and unpacked by the machinery that was
            built for it - including handing back `None` for somebody who has been deleted.

        """
        return {"traveller": self.traveller, "bound_for": self.bound_for, "fare": self.fare}

    @classmethod
    def from_stored(cls, stored):
        """
        Args:
            stored (dict): What came out of the attribute.

        Returns:
            passage (Passage): The booking.

        """
        return cls(
            traveller=stored.get("traveller"),
            bound_for=stored.get("bound_for", ""),
            fare=stored.get("fare"),
        )


@dataclass(frozen=True, kw_only=True)
class PassageResult(Result):
    """
    What happened to somebody's passage.

    Attributes:
        passage (Passage): The booking in question.
        landed (tuple): Who went ashore.
        refunded (Coin): What was given back.
        room (int): How many more she could take.

    """

    passage: Passage = None
    landed: tuple = ()
    refunded: Coin = None
    room: int = 0


@dataclass(frozen=True, kw_only=True)
class TimetableResult(Result):
    """
    Whether a schedule can be kept.

    Attributes:
        wanted (float): How long the schedule allows, in seconds.
        needed (float): How long the passage actually takes at the speed given.
        slack (float): The difference. Negative means she cannot do it.
        closes (bool): Whether the run gets her back where it started.

    """

    wanted: float = 0.0
    needed: float = 0.0
    slack: float = 0.0
    closes: bool = False


def accommodation_for(internal_volume, per_head=VOLUME_PER_PASSENGER, share=MOST_OF_HER):
    """
    How many people a hull of this size can carry.

    Args:
        internal_volume (float): Her volume in cubic metres.
        per_head (float, optional): How much room one wants.
        share (float, optional): How much of her can be given over to them.

    Returns:
        berths (int): How many.

    Notes:
        Derived, like her boats and her rating, so a builder who draws a bigger ship gets
        more of them without remembering to and cannot give a launch a hundred.

    """
    if per_head <= 0.0:
        return 0
    return max(0, int((max(0.0, float(internal_volume)) * share) / per_head))


def time_to_run(route, speed):
    """
    How long a passage takes at a given speed.

    Args:
        route (Route): The marks she is going by.
        speed (float): What she makes good, in metres a second.

    Returns:
        seconds (float): How long. Infinite if she is making nothing.

    """
    if speed <= 0.0:
        return float("inf")
    return route.distance / float(speed)


def can_be_kept(route, speed, allowed, returns=True):
    """
    Whether a schedule is sailable.

    Args:
        route (Route): The marks of one run.
        speed (float): What she makes good, in metres a second.
        allowed (float): How long the schedule gives her, in seconds.
        returns (bool, optional): Whether the run has to bring her back to the start.

    Returns:
        result (TimetableResult): What the schedule wants against what it needs.

    Notes:
        **A run that repeats has to close.** If the last mark is not the first, the schedule
        must pay for the passage home as well - otherwise the second cycle starts wherever
        the first one finished, and every sailing after it is later than the last. That is
        the failure a timetable is written to avoid, so it is the one worth checking.

    """
    marks = route.waypoints if route else ()
    if len(marks) < 2:
        return TimetableResult(success=False, code=NO_ROUTE)

    closes = marks[0].position == marks[-1].position
    needed = time_to_run(route, speed)
    if returns and not closes:
        needed += marks[-1].position.horizontal_distance_to(marks[0].position) / max(speed, 1e-9)

    slack = float(allowed) - needed
    return TimetableResult(
        success=slack >= 0.0,
        code=None if slack >= 0.0 else CANNOT_BE_KEPT,
        wanted=float(allowed),
        needed=needed,
        slack=slack,
        closes=closes,
    )


class CarriesPassengers:
    """
    A hull that sells passages.

    Notes:
        The bookings are hers rather than her captain's, for the same reason her standing
        orders are: a ship handed to somebody else still owes the people in her cabins the
        voyage they paid for.

    """

    def at_object_creation(self):
        """Set up this part of a newly created vessel."""
        super().at_object_creation()
        self.db.passages = []

    @property
    def accommodation(self):
        """
        Returns:
            berths (int): How many people she can carry.

        """
        volume = getattr(self.capacity, "internal_volume", 0.0)
        return accommodation_for(volume)

    @property
    def passages(self):
        """
        Returns:
            booked (tuple): Every passage sold, deleted travellers dropped.

        Notes:
            Filtered on the way out, because an Evennia attribute holding a deleted object
            hands back None and a passage booked by nobody is not a passage.

        """
        booked = (Passage.from_stored(stored) for stored in (self.db.passages or ()))
        return tuple(
            passage for passage in booked if passage.traveller is not None and passage.traveller.pk
        )

    def passenger_list(self):
        """
        Returns:
            manifest (tuple): `(name, destination)` pairs, in the order they booked.

        Notes:
            What a purser reads out. Names rather than objects, because a manifest is a
            document and a document does not hold references to things that can be deleted.

        """
        return tuple((passage.traveller.key, passage.bound_for) for passage in self.passages)

    def room_for_passengers(self):
        """
        Returns:
            room (int): How many more she could take.

        """
        return max(0, self.accommodation - len(self.passages))

    def book_passage(self, traveller, bound_for, fare=None):
        """
        Sell somebody a passage.

        Args:
            traveller (object): Whoever it is.
            bound_for (str): Where he is going.
            fare (Coin, optional): What he paid.

        Returns:
            result (PassageResult): The booking, or why she cannot take him.

        Notes:
            **The fare goes onto the ship's purse.** A vessel earning her keep is a vessel
            that can pay for her own repairs, which is the loop this contrib is trying to
            close - what a game does with the money after that is a game's business.

        """
        if any(passage.traveller is traveller for passage in self.passages):
            return PassageResult(success=False, code=ALREADY_ABOARD)
        if not self.room_for_passengers():
            return PassageResult(success=False, code=NO_ROOM, room=0)

        made = Passage(traveller=traveller, bound_for=bound_for, fare=fare)
        booked = list(self.db.passages or ())
        booked.append(made.stored())
        self.db.passages = booked

        if fare is not None:
            self.credit(fare, reason=f"passage to {bound_for}")
        return PassageResult(success=True, passage=made, room=self.room_for_passengers())

    def land_passengers(self, arrived_at):
        """
        Put ashore everybody who paid to come here.

        Args:
            arrived_at (str): The name of the place she has reached.

        Returns:
            result (PassageResult): Who went ashore.

        Notes:
            By name rather than by position, because "has she arrived?" is a question about
            a game's world - a port, a berth, a beach - and this contrib does not get to
            decide how near is near enough.

        """
        going = [passage for passage in self.passages if passage.bound_for == arrived_at]
        if not going:
            return PassageResult(success=False, code=NOT_THERE_YET)

        staying = [passage for passage in self.passages if passage not in going]
        self.db.passages = [passage.stored() for passage in staying]
        return PassageResult(
            success=True,
            landed=tuple(passage.traveller for passage in going),
            room=self.room_for_passengers(),
        )

    def refund_passage(self, traveller):
        """
        Give somebody his money back.

        Args:
            traveller (object): Whoever it is.

        Returns:
            result (PassageResult): What was returned, or why nothing was.

        Notes:
            **What makes a passenger different from cargo.** She did not go where she said
            she would, and he is entitled to what he paid - which means a captain who takes
            a prize instead of a passage has been paid for the prize and not for the
            passage, and can work out for himself whether that was worth it.

            A ship that cannot pay refuses rather than going into debt. Debt is a game's
            question and this contrib has no view on it.

        """
        for passage in self.passages:
            if passage.traveller is not traveller:
                continue
            given = None
            if passage.fare is not None:
                if not self.debit(passage.fare, reason="refunded passage"):
                    return PassageResult(success=False, code=CANNOT_REFUND, passage=passage)
                given = passage.fare
            self.db.passages = [
                booked.stored() for booked in self.passages if booked.traveller is not traveller
            ]
            return PassageResult(success=True, passage=passage, refunded=given)
        return PassageResult(success=False, code=NOT_ABOARD)
