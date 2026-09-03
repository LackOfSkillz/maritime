"""
A ship's purse.

**Money lives on the hull, never on the person.** This contrib cannot know what a player is
- some games have no player currency at all, and none of them want a second one appearing
underneath the first - while every ship must pay for her repairs, her wages, her stores and
her cargo. So the purse is a fact about the vessel, exactly as her owner is, and a game
bridges it to people however it likes or not at all.

**Three denominations, because one cannot span a day's wage and the price of a ship.** A
single unit forces either absurd numbers for a hull or fractions for a loaf, and the
period's own coinage solves it the way every pre-decimal coinage did:

    twelve copper      one silver
    twenty silver      one gold

Authentic rather than decimal, and configurable, because a game with its own coins should
be able to say so without this pretending they are pounds.

**Held in the smallest unit, always.** Every amount is an integer number of copper, and the
gold and silver are a *rendering*. Money kept as three separate numbers is money that can be
made to disappear by carrying wrong, and money kept as a float is money that stops adding up
after enough voyages.

**It records nothing.** A purse says what she has, and every change publishes what moved and
why - and there the contrib stops. A game that keeps books has its own, and a second set
kept here would be a second set to disagree with the first.

"""

from dataclasses import dataclass

from .events import Event, bus

#: The coinage, smallest first: how many of each make one of the next.
#:
#: Twelve pence to the shilling and twenty shillings to the pound, which is the coinage of
#: the age this models. A game says `MARITIME_COINAGE` to use its own.
DEFAULT_RATIOS = (12, 20)

#: What each is called, smallest first.
DEFAULT_NAMES = ("copper", "silver", "gold")

NOT_ENOUGH = "not_enough"
NOT_A_SUM = "not_a_sum"


def coinage():
    """
    The names and ratios in force.

    Returns:
        coinage (tuple): `(names, ratios)`, both smallest first.

    Notes:
        Read rather than cached, so a game changing its mind about its own coins does not
        have to restart to be believed.

    """
    from . import config

    said = config.get_setting("COINAGE", None) or {}
    names = tuple(said.get("names") or DEFAULT_NAMES)
    ratios = tuple(said.get("ratios") or DEFAULT_RATIOS)
    if len(ratios) != len(names) - 1:
        raise ValueError(
            f"MARITIME_COINAGE needs one ratio fewer than it has names; got {len(names)} "
            f"names and {len(ratios)} ratios."
        )
    return names, ratios


@dataclass(frozen=True, order=True)
class Coin:
    """
    An amount of money.

    Attributes:
        smallest (int): How much, counted in the smallest denomination.

    Notes:
        **One integer, and the denominations are a rendering of it.** Money held as three
        numbers can be made to vanish by carrying wrong, and money held as a float stops
        adding up after enough voyages - neither is a thing to find out about from a player.

        Ordered and frozen, so amounts compare and add like the numbers they are and cannot
        be edited after somebody has been told what they were.

    """

    smallest: int = 0

    @classmethod
    def of(cls, **denominations):
        """
        Build an amount from denominations by name.

        Args:
            **denominations: `gold=2, silver=10` and so on, in whatever the coinage calls
                them.

        Returns:
            coin (Coin): The amount.

        Raises:
            ValueError: If a name is not one of the coins.

        """
        names, ratios = coinage()
        worth, total = 1, 0
        by_name = {}
        for place, name in enumerate(names):
            by_name[name] = worth
            if place < len(ratios):
                worth *= ratios[place]
        for name, count in denominations.items():
            if name not in by_name:
                raise ValueError(f"No coin called {name!r}; the coinage is {', '.join(names)}.")
            total += int(count) * by_name[name]
        return cls(smallest=total)

    def split(self):
        """
        Returns:
            split (dict): How many of each coin, largest first.

        """
        names, ratios = coinage()
        worth, places = 1, []
        for place, name in enumerate(names):
            places.append((name, worth))
            if place < len(ratios):
                worth *= ratios[place]

        left = int(self.smallest)
        out = {}
        for name, each in reversed(places):
            out[name] = left // each
            left -= out[name] * each
        return out

    def __str__(self):
        """
        Returns:
            said (str): The amount, in the coins somebody would count out.

        Notes:
            Empty denominations are left out, because "two gold and no silver and no copper"
            is not how anybody says it - but nothing at all still has to say something, so
            a purse with nothing in it reads as none of the smallest coin.

        """
        split = self.split()
        said = [f"{count} {name}" for name, count in split.items() if count]
        if not said:
            names, _ratios = coinage()
            return f"0 {names[0]}"
        return ", ".join(said)

    def __add__(self, other):
        return Coin(smallest=self.smallest + Coin.taken_from(other).smallest)

    def __sub__(self, other):
        return Coin(smallest=self.smallest - Coin.taken_from(other).smallest)

    def __bool__(self):
        return bool(self.smallest)

    @classmethod
    def taken_from(cls, amount):
        """
        Read an amount out of whatever a caller had to hand.

        Args:
            amount (Coin or int): The sum.

        Returns:
            coin (Coin): It, as a Coin.

        Raises:
            TypeError: If it is neither.

        Notes:
            A bare integer is taken as the smallest coin, because that is what a game
            counting in one unit means by it, and refusing them would make every call site
            wrap a number for no reason.

        """
        if isinstance(amount, Coin):
            return amount
        if isinstance(amount, int):
            return cls(smallest=amount)
        raise TypeError(f"A sum must be a Coin or a whole number, not {type(amount).__name__}.")


@dataclass(frozen=True, kw_only=True)
class MoneyMoved(Event):
    """
    A ship's purse changed.

    Attributes:
        vessel (object): Whose purse.
        amount (Coin): How much moved. Negative when it was spent.
        reason (str): What for.
        purse (Coin): What she has now.

    Notes:
        Carries the reason because that is what separates a ledger from a number, and
        carries the balance because a listener that had to ask for it afterwards would be
        asking after the next change had already happened.

    """

    vessel: object
    amount: object = None
    reason: str = ""
    purse: object = None


class Purse:
    """
    A hull that carries money.

    Notes:
        Nothing here decides what anything costs. Prices are the game's - what a hull is
        worth, what a pilot charges, what a cargo fetches at the other end - and a contrib
        that shipped a price list would be arguing with every game that has one.

    """

    def at_object_creation(self):
        """Set up this part of a newly created vessel."""
        super().at_object_creation()
        self.db.purse = 0

    @property
    def purse(self):
        """
        Returns:
            purse (Coin): What she carries.

        """
        return Coin(smallest=int(self.db.purse or 0))

    def can_afford(self, amount):
        """
        Args:
            amount (Coin or int): The sum.

        Returns:
            afford (bool): Whether she has it.

        """
        return self.purse.smallest >= Coin.taken_from(amount).smallest

    def credit(self, amount, reason=""):
        """
        Pay money into her.

        Args:
            amount (Coin or int): How much.
            reason (str, optional): What for.

        Returns:
            purse (Coin): What she has afterwards.

        """
        sum_of = Coin.taken_from(amount)
        self.db.purse = self.purse.smallest + sum_of.smallest
        self._say_money_moved(sum_of, reason)
        return self.purse

    def debit(self, amount, reason=""):
        """
        Take money out of her.

        Args:
            amount (Coin or int): How much.
            reason (str, optional): What for.

        Returns:
            paid (bool): Whether she could afford it. Nothing moves if she could not.

        Notes:
            **A purse never goes negative.** Debt is a relationship between people and this
            contrib has no people in it; a game that lends money to a captain is modelling
            something it understands and this is not it.

        """
        sum_of = Coin.taken_from(amount)
        if sum_of.smallest > self.purse.smallest:
            return False
        self.db.purse = self.purse.smallest - sum_of.smallest
        self._say_money_moved(Coin(smallest=-sum_of.smallest), reason)
        return True

    def _say_money_moved(self, amount, reason):
        """
        Args:
            amount (Coin): What moved, negative when spent.
            reason (str): What for.

        """
        from . import config

        bus().publish(
            MoneyMoved(
                game_time=config.time_provider().now(),
                vessel=self,
                amount=amount,
                reason=reason,
                purse=self.purse,
            )
        )
