"""
What a cargo is worth, and why it is worth more there than here.

`DECISIONS.md` settled this and then reversed its own earlier deferral, and the reversal was
right: the interesting half was already built. `stowage` models *both* capacities. Heavy
cheap cargo - grain, salt, coal, timber, stone - fills her tonnage while the hold stands half
empty; light valuable cargo fills the volume long before the marks go under. **The cargoes
worth thinking about are the ones that trade the two off**, and no other naval system can
express that, because none of them carry two capacities.

**Off by default.** A game arriving with its own economy must be untouched, so nothing here
runs unless `MARITIME_CARGO_ECONOMY` says so. That is not timidity - an economy is the part
of a game most likely to already exist, and a contrib that quietly started pricing salt would
be the worst kind of guest.

**A port has a surplus of what it exports and a shortage of what it imports, and price
follows from that** rather than from a table of what each thing costs at each quay. Two
numbers per port instead of one per commodity per port, and the trade routes draw themselves:
carry what is cheap here to where it is dear, and the map tells you where that is.

**The worth of a commodity lives here and not on `Commodity`.** That type is deliberately
silent about value - it says how a thing stows and nothing else, so that a game with its own
economy can use the stowage model without arguing about prices. Putting a worth on it would
break that promise for every game that wanted the one and not the other.

**Worth is not derivable from how a thing stows.** It is tempting: dense cargo is cheap, so
perhaps value falls with stowage factor. Hay disposes of it - bulky, and worth almost nothing.
Spice and hay stow much alike and are not remotely alike, so the table below is authored,
and honestly authored, rather than dressed up as a derivation.

"""

from dataclasses import dataclass, field

from .ledger import Coin
from .results import Result

#: What a tonne of each is worth where it is neither wanted nor spare, in the smallest coin.
#:
#: Spread across three orders of magnitude on purpose. A hold full of grain and a hold full
#: of spice are the same ship carrying two completely different risks, and a range narrow
#: enough to be "balanced" would make the choice of cargo a formality.
WORTH = {
    "hay": 4,
    "coal": 12,
    "salt": 20,
    "grain": 26,
    "timber": 30,
    "shot": 45,
    "iron": 60,
    "hides": 90,
    "sugar": 140,
    "wool": 160,
    "wine": 220,
    "tobacco": 400,
}

#: What a port pays for what it has too much of, and asks for what it has too little.
#:
#: A little over half, and a little over half again on top. The gap is what a passage is
#: worth making for - wide enough that a full hold pays for the voyage, narrow enough that
#: one run does not buy a frigate.
EXPORTS_AT = 0.6
IMPORTS_AT = 1.7

NOT_TRADED_HERE = "not_traded_here"
ECONOMY_IS_OFF = "economy_is_off"
NOTHING_TO_SELL = "nothing_to_sell"
CANNOT_AFFORD = "cannot_afford"


@dataclass(frozen=True)
class Market:
    """
    What one place wants and what it has too much of.

    Attributes:
        key (str): The port's name.
        exports (tuple): Commodity keys it has a surplus of.
        imports (tuple): Commodity keys it is short of.

    Notes:
        Two lists rather than a price per commodity, which is the whole of the design. A
        builder writes what a place *is* - a grain coast, a mining port, a city that eats -
        and the prices and the trade routes fall out of that. Authoring prices directly
        would mean authoring them again every time a commodity was added.

    """

    key: str
    exports: tuple = field(default_factory=tuple)
    imports: tuple = field(default_factory=tuple)

    def rate_for(self, commodity_key):
        """
        Args:
            commodity_key (str): Which commodity.

        Returns:
            rate (float): What this port pays against the standing worth.

        Notes:
            A place that both exports and imports the same thing is an entrepot, and it
            trades it at the standing rate - which is the honest answer rather than an error,
            because such places existed and did exactly that.

        """
        exports = commodity_key in self.exports
        imports = commodity_key in self.imports
        if exports and imports:
            return 1.0
        if exports:
            return EXPORTS_AT
        if imports:
            return IMPORTS_AT
        return 1.0


@dataclass(frozen=True, kw_only=True)
class TradeResult(Result):
    """
    What a parcel came to.

    Attributes:
        commodity (str): What was traded.
        tonnes (float): How much.
        price (Coin): What it came to altogether.
        rate (float): What the port paid against the standing worth.

    """

    commodity: str = ""
    tonnes: float = 0.0
    price: Coin = None
    rate: float = 1.0


def trading():
    """
    Returns:
        on (bool): Whether the shipped economy is running.

    Notes:
        Off unless a game says otherwise. Read on each call rather than cached, so a game
        can turn it on in a test without a reload.

    """
    from . import config

    return bool(config.get_setting("CARGO_ECONOMY", False))


def worth_of(commodity_key, tonnes=1.0, worth=None):
    """
    What a parcel is worth where it is neither wanted nor spare.

    Args:
        commodity_key (str): Which commodity.
        tonnes (float, optional): How much of it.
        worth (dict, optional): The standing worths. The shipped table by default.

    Returns:
        price (Coin): What it comes to.

    """
    table = WORTH if worth is None else worth
    return Coin(smallest=int(round(table.get(commodity_key, 0) * max(0.0, float(tonnes)))))


def price_at(market, commodity_key, tonnes=1.0, worth=None):
    """
    What a parcel fetches at one place.

    Args:
        market (Market): The port.
        commodity_key (str): Which commodity.
        tonnes (float, optional): How much of it.
        worth (dict, optional): The standing worths.

    Returns:
        price (Coin): What that port pays.

    Notes:
        **The trade routes draw themselves.** Carry what is cheap here to where it is dear;
        the map already says where that is, because a builder wrote what each place exports
        and what it eats.

    """
    standing = worth_of(commodity_key, tonnes, worth)
    rate = 1.0 if market is None else market.rate_for(commodity_key)
    return Coin(smallest=int(round(standing.smallest * rate)))


def cargo_worth(parcels, worth=None):
    """
    What a whole manifest is worth at the standing rate.

    Args:
        parcels (iterable): `Parcel` objects.
        worth (dict, optional): The standing worths.

    Returns:
        price (Coin): What is in her.

    Notes:
        **This is what piracy follows.** `DECISIONS.md` makes the point twice because it is
        one decision seen from two sides: a raider who hunted traffic would hunt grain
        coasters, and a raider who hunts value goes where the wine and the tobacco are - which
        is what makes choosing a cargo a choice about danger as well as about money.

    """
    total = 0
    for parcel in parcels or ():
        total += worth_of(parcel.commodity.key, parcel.tonnes, worth).smallest
    return Coin(smallest=total)


class Trades:
    """
    A hull that can buy and sell what she carries.

    Notes:
        Every method here refuses outright when the economy is off, rather than being absent.
        A game that has its own economy gets a clear answer from a call it should not have
        made, instead of an `AttributeError` from somewhere three frames down.

        `buy_cargo` and `sell_cargo` rather than `buy` and `sell`, because `Refitted.sell`
        already means selling the *ship*. Two mixins with the same public name do not raise -
        they silently displace one another, and a captain who meant to land forty tons of
        salt would have sold his vessel.

    """

    def what_she_carries_is_worth(self):
        """
        Returns:
            price (Coin): What is in her holds, at the standing rate.

        """
        return cargo_worth(self.cargo)

    def buy_cargo(self, market, commodity, tonnes):
        """
        Take a cargo aboard and pay for it.

        Args:
            market (Market): The port she is lying at.
            commodity (Commodity): What to buy.
            tonnes (float): How much.

        Returns:
            result (TradeResult): What she bought, or why she did not.

        Notes:
            The load comes first and the payment second, so a hull that could not physically
            take the cargo is not charged for it. `load` already knows about both her
            capacities; this only knows about money.

        """
        if not trading():
            return TradeResult(success=False, code=ECONOMY_IS_OFF)

        price = price_at(market, commodity.key, tonnes)
        if not self.can_afford(price):
            return TradeResult(success=False, code=CANNOT_AFFORD, price=price)

        stowed = self.load(commodity, tonnes)
        if not stowed:
            return TradeResult(success=False, code=stowed.code, price=price)

        # Paid for what actually went in, not what was asked for. `load` reports a parcel
        # and a refusal, because her hold or her marks may stop her short - and a captain
        # charged for cargo still standing on the quay would be right to complain.
        got = stowed.parcel.tonnes if stowed.parcel is not None else 0.0
        if got <= 0.0:
            return TradeResult(success=False, code=stowed.code, price=price)
        due = price_at(market, commodity.key, got)
        self.debit(due, reason=f"bought {commodity.name}")
        return TradeResult(
            success=True,
            commodity=commodity.name,
            tonnes=got,
            price=due,
            rate=market.rate_for(commodity.key) if market else 1.0,
        )

    def sell_cargo(self, market, commodity, tonnes):
        """
        Put a cargo ashore and be paid for it.

        Args:
            market (Market): The port she is lying at.
            commodity (Commodity): What to sell.
            tonnes (float): How much.

        Returns:
            result (TradeResult): What she sold, or why she did not.

        Notes:
            Paid for what actually came out of her rather than for what was asked for, so a
            hull who sold more than she had is not paid for cargo she never carried.

        """
        if not trading():
            return TradeResult(success=False, code=ECONOMY_IS_OFF)

        landed = self.discharge(commodity, tonnes)
        got = landed.parcel.tonnes if landed.parcel is not None else 0.0
        if got <= 0.0:
            return TradeResult(success=False, code=NOTHING_TO_SELL)

        due = price_at(market, commodity.key, got)
        self.credit(due, reason=f"sold {commodity.name}")
        return TradeResult(
            success=True,
            commodity=commodity.name,
            tonnes=got,
            price=due,
            rate=market.rate_for(commodity.key) if market else 1.0,
        )
