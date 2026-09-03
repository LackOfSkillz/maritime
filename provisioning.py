"""
What she has aboard to keep her people alive, and how long it lasts.

`crew` has always counted a hand as a hundred and twenty kilograms - himself, his kit, and
the water and provisions he will get through - so the *weight* of feeding a company has been
in the model since there were companies. What was missing is the clock: a ship provisioned
for six weeks can go six weeks, and a captain who does not know which week he is in is not
making decisions, he is guessing.

**This is the pacing lever, and it is geography rather than a dial.** How far a hull can go
is her stores divided by her company, and both of those are things a player chose. A small
crew goes further on the same casks; a ship crowded with marines for a boarding cannot cross
an ocean. Nobody has to be told they are on a short passage - they can count.

**Running out is not a kill switch.** The company gets hungry, then they get sullen, and
their morale is what carries it - which is a system that already exists and already costs
her something at the guns and on the yards. A contrib that started killing a game's
characters over biscuit would be writing a survival system nobody asked for.

**Provisioning is bought, from the ship's purse.** A hull that has been at sea for a month
and comes in to store is a hull spending what she earned, which is the loop `ledger` and
`passengers` are both feeding.

"""

from dataclasses import dataclass

from .ledger import Coin
from .results import Result

#: What one person gets through in a day, in tonnes.
#:
#: Four kilograms - biscuit, salt meat, and above all water, which is most of it by weight.
#: A figure a period victualler would recognise, and one that makes a hundred tonnes of
#: stores feed a company of forty for something over a year, which is about right for a
#: ship that has taken on everything she can hold.
RATION = 0.004

#: How many game seconds make a day, for a tick that counts in seconds and a company
#: that eats in days.
SECONDS_A_DAY = 86400.0

#: How many days of stores counts as running short.
#:
#: A week. Far enough out that a captain has time to do something about it - bear away for a
#: port, put the company on short allowance, catch fish - which is the point of warning him
#: rather than telling him afterwards.
RUNNING_SHORT = 7.0

#: What being out of stores costs the company's morale, per day.
#:
#: A twentieth. Slow, because hunger is slow: a company on short commons for a day are
#: grumbling and a company starving for a fortnight are a different ship. That curve is what
#: makes running out a situation rather than an event.
HUNGER = 0.05

#: What short allowance buys: how far it stretches the stores, and what it costs in morale.
#:
#: Half again as long, at a fortieth of morale a day. It is the decision a captain of the
#: period actually made, and it is a real one - he trades his people's temper for sea room.
SHORT_ALLOWANCE = 1.5
SHORT_ALLOWANCE_COST = 0.025

NO_STORES = "no_stores"
NOTHING_TO_STOW = "nothing_to_stow"
CANNOT_AFFORD = "cannot_afford"
NO_ROOM = "no_room"


@dataclass(frozen=True, kw_only=True)
class StoresResult(Result):
    """
    How she stands for stores.

    Attributes:
        stores (float): What she has aboard, in tonnes.
        days (float): How long it will last at the present allowance.
        eaten (float): What was got through, in tonnes.
        short (bool): Whether she is running short.
        out (bool): Whether she has nothing left.
        paid (Coin): What was spent on stores.

    """

    stores: float = 0.0
    days: float = 0.0
    eaten: float = 0.0
    short: bool = False
    out: bool = False
    paid: Coin = None


def daily_ration(complement, ration=RATION, allowance=1.0):
    """
    What a company gets through in a day.

    Args:
        complement (int): How many people are aboard.
        ration (float, optional): What one gets through, in tonnes.
        allowance (float, optional): How far the stores are being stretched.

    Returns:
        tonnes (float): What the day costs her.

    """
    stretched = max(1.0, float(allowance))
    return max(0, int(complement)) * float(ration) / stretched


def days_of(stores, complement, ration=RATION, allowance=1.0):
    """
    How long she can go.

    Args:
        stores (float): What she has aboard, in tonnes.
        complement (int): How many people are aboard.
        ration (float, optional): What one gets through, in tonnes.
        allowance (float, optional): How far the stores are being stretched.

    Returns:
        days (float): How many. Infinite if there is nobody to feed.

    Notes:
        **The number a player can count on his fingers**, which is why it is days and not a
        percentage. "Eighteen days of stores and twenty-two days of passage" is a decision;
        "stores at forty-one per cent" is a status bar.

    """
    per_day = daily_ration(complement, ration, allowance)
    if per_day <= 0.0:
        return float("inf")
    return max(0.0, float(stores)) / per_day


class Provisioned:
    """
    A hull with stores in her, and a company getting through them.

    Notes:
        The stores are not cargo, deliberately. Cargo is something she is carrying for
        somebody and can be sold or thrown over the side; stores are what her people eat,
        and putting the two in the same hold would let a game sell a company's water by
        accident - and would make her stores subject to a cargo capacity they are not
        really competing for, since `crew` already counts their weight in the company's.

    """

    def at_object_creation(self):
        """Set up this part of a newly created vessel."""
        super().at_object_creation()
        self.db.stores = 0.0
        self.db.short_allowance = False
        self.db.victualled = False

    @property
    def stores(self):
        """
        Returns:
            stores (float): What she has aboard, in tonnes.

        """
        return max(0.0, float(self.db.stores or 0.0))

    @property
    def victualled(self):
        """
        Returns:
            victualled (bool): Whether anybody has ever stored ship.

        Notes:
            **A ship nobody has victualled is not a starving ship.** Without this every hull
            in every existing world - none of which knows what stores are - would begin
            losing morale on the first tick after this module was installed, and a game that
            wants none of this would have had a famine installed with it.

            The same shape of mistake the purse made once: zero is a fact about what she
            has, not a fact about whether anybody has ever given her any. A flag says which,
            and once she has been stored she is in the model for good - a ship that has eaten
            everything aboard *is* starving, and that is the whole point.

        """
        return bool(self.db.victualled)

    @property
    def short_allowance(self):
        """
        Returns:
            short (bool): Whether the company is on reduced rations.

        """
        return bool(self.db.short_allowance)

    @short_allowance.setter
    def short_allowance(self, value):
        """
        Args:
            value (bool): Whether to put them on short allowance.

        """
        self.db.short_allowance = bool(value)

    @property
    def allowance(self):
        """
        Returns:
            allowance (float): How far the stores are being stretched.

        """
        return SHORT_ALLOWANCE if self.short_allowance else 1.0

    def mouths(self):
        """
        Returns:
            aboard (int): How many people she is feeding.

        """
        company = getattr(self, "company", None)
        return company.complement if company is not None else 0

    def days_of_stores(self):
        """
        Returns:
            days (float): How long what she has will last at the present allowance.

        """
        return days_of(self.stores, self.mouths(), allowance=self.allowance)

    def stores_report(self):
        """
        Returns:
            result (StoresResult): How she stands, without changing anything.

        """
        days = self.days_of_stores()
        return StoresResult(
            success=True,
            stores=self.stores,
            days=days,
            short=days <= RUNNING_SHORT,
            out=self.stores <= 0.0,
        )

    def take_on_stores(self, tonnes, cost=None):
        """
        Store ship.

        Args:
            tonnes (float): How much to take aboard.
            cost (Coin, optional): What the chandler wants for it.

        Returns:
            result (StoresResult): How she stands afterwards, or why she could not.

        Notes:
            Paid out of her own purse, which is the loop this contrib is trying to close: a
            hull that carried passengers and landed cargo has the money to victual for the
            next passage, and one that has done neither has to decide what to sell.

        """
        wanted = max(0.0, float(tonnes))
        if wanted <= 0.0:
            return StoresResult(success=False, code=NOTHING_TO_STOW, stores=self.stores)

        if cost is not None and not self.debit(cost, reason="stores"):
            return StoresResult(success=False, code=CANNOT_AFFORD, stores=self.stores)

        self.db.stores = self.stores + wanted
        self.db.victualled = True
        report = self.stores_report()
        return StoresResult(
            success=True,
            stores=report.stores,
            days=report.days,
            short=report.short,
            out=report.out,
            paid=cost,
        )

    def eat(self, days):
        """
        Let the company get through a stretch of days.

        Args:
            days (float): How long, in days.

        Returns:
            result (StoresResult): What was eaten and how she stands.

        Notes:
            **Running out costs morale rather than lives.** The company get hungry, then
            sullen, and morale is what carries it - which already costs her at the guns and
            on the yards. Killing a game's characters over biscuit would be writing a
            survival system nobody asked for.

        """
        elapsed = max(0.0, float(days))
        if elapsed <= 0.0 or not self.victualled:
            return self.stores_report()

        wanted = daily_ration(self.mouths(), allowance=self.allowance) * elapsed
        eaten = min(wanted, self.stores)
        self.db.stores = self.stores - eaten

        went_without = elapsed if wanted <= 0.0 else elapsed * (1.0 - eaten / wanted)
        if went_without > 0.0:
            self.morale = max(0.0, self.morale - HUNGER * went_without)
        elif self.short_allowance:
            self.morale = max(0.0, self.morale - SHORT_ALLOWANCE_COST * elapsed)

        report = self.stores_report()
        return StoresResult(
            success=True,
            stores=report.stores,
            days=report.days,
            eaten=eaten,
            short=report.short,
            out=report.out,
        )
