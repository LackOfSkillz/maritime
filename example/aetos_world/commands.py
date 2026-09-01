"""
Buying things ashore, and building the place in the first place.

Three commands, and two of them are for players:

    browse [<person>]        what is on the counter, and what it costs
    buy <thing> [from <person>]   hand over coin and get the thing
    build_aetos              a builder command that makes the whole coast

**`browse` exists because a shop with a hidden list is a locked door.** A player who has to
guess the name of what is for sale will guess twice and then leave, so the list is one
command away and the command is the obvious word.

**What is bought becomes a real object.** Not a counter on the character, not a flag - an
ordinary Evennia object that can be dropped, given away, stowed in a hold or left on a
table. That matters more than it sounds: it is the difference between a shop that furnishes
the world and a shop that increments a number.

**Drinking ashore is what the crew came for.** Buying anything at a counter while your ship
is alongside is a run ashore, and the morale of the people aboard her lifts for it. That is
wired here rather than in the contrib because morale of that kind belongs to a setting -
see `shoreleave`.
"""

from evennia.commands.command import Command
from evennia.utils import create

from . import people, shoreleave

#: What a bought thing is, unless a game says otherwise.
GOODS = "evennia.objects.objects.DefaultObject"


def counters_here(caller):
    """
    Args:
        caller (Object): Who is looking.

    Returns:
        vendors (list): Everybody selling anything in this room.

    """
    where = getattr(caller, "location", None)
    if where is None:
        return []
    return [
        thing
        for thing in where.contents
        if thing.is_typeclass(people.Vendor, exact=False) and thing.stock
    ]


class CmdBrowse(Command):
    """
    See what is for sale here.

    Usage:
        browse
        browse <person>

    Shows the counter you are standing at: what is on it, and what each thing costs. With
    more than one seller in the room, name the one you mean.
    """

    key = "browse"
    aliases = ("wares", "list")
    locks = "cmd:all()"
    help_category = "Ashore"

    def func(self):
        """Read out a counter."""
        selling = counters_here(self.caller)
        if not selling:
            self.caller.msg("There is nobody selling anything here.")
            return

        wanted = self.args.strip().lower()
        if wanted:
            selling = [one for one in selling if one.key.lower().startswith(wanted)]
            if not selling:
                self.caller.msg(f"Nobody called '{self.args.strip()}' is selling here.")
                return

        keeper = selling[0]
        lines = [f"|w{keeper.key}|n has:"]
        for name, price, kind, _ in keeper.stock:
            lines.append(f"  {name:<26} {price:>3} coin   |x{kind}|n")
        lines.append(f"You have {people.purse_of(self.caller)} coin.")
        self.caller.msg("\n".join(lines))


class CmdBuy(Command):
    """
    Buy something from somebody standing here.

    Usage:
        buy <thing>
        buy <thing> from <person>

    The thing becomes yours - a real object you can carry, drop, give away or stow. If your
    ship is lying alongside, buying at a counter counts as a run ashore for her people, and
    they will be the better for it for a few days.
    """

    key = "buy"
    locks = "cmd:all()"
    help_category = "Ashore"

    def func(self):
        """Take the coin and hand over the goods."""
        if not self.args.strip():
            self.caller.msg("Buy what?")
            return

        wanted, _, whom = self.args.strip().partition(" from ")
        selling = counters_here(self.caller)
        if not selling:
            self.caller.msg("There is nobody selling anything here.")
            return
        if whom.strip():
            selling = [one for one in selling if one.key.lower().startswith(whom.strip().lower())]
            if not selling:
                self.caller.msg(f"Nobody called '{whom.strip()}' is selling here.")
                return

        keeper = selling[0]
        line = keeper.sells(wanted)
        if line is None:
            self.caller.msg(f"{keeper.key} does not sell '{wanted.strip()}'. Try |wbrowse|n.")
            return

        name, price, kind, description = line
        if not people.charge(self.caller, price):
            held = people.purse_of(self.caller)
            self.caller.msg(f"{name} costs {price} coin and you have {held}.")
            return

        goods = create.create_object(GOODS, key=name, location=self.caller)
        goods.db.desc = description
        goods.db.kind = kind
        goods.db.bought_from = keeper.key

        self.caller.msg(f"You buy {name} from {keeper.key} for {price} coin.")
        self.caller.location.msg_contents(
            f"{self.caller.key} buys {name} from {keeper.key}.", exclude=self.caller
        )
        self._run_ashore(kind)

    def _run_ashore(self, kind):
        """
        Note that this crew has been ashore, if their ship is here to notice.

        Args:
            kind (str): What was bought, so a drink counts for a little more.

        Notes:
            Granted for buying anything rather than only for drinking, because what lifts a
            crew is being let off the ship - the bar is only where they go. A captain who
            stands a round for people still aboard has bought a round.

            Nothing happens at all if no ship is lying here, which is the honest answer: a
            passenger ashore on his own business has no crew to cheer up.

        """
        from ... import config

        vessel = _ship_alongside(self.caller)
        if vessel is None:
            return

        held = shoreleave.granted(vessel, config.time_provider().now(), drink=kind == "strong")
        if held:
            self.caller.msg("|gWord of the run ashore gets back to the ship.|n")


def _ship_alongside(character):
    """
    Args:
        character (Object): Who is ashore.

    Returns:
        vessel (Vessel or None): A ship lying at this port, or None if none is.

    Notes:
        Asked of the vessels rather than of the berth. A `Berth` is a description of a
        place - its depth, its length, which way it lies - and deliberately knows nothing
        about who is in it; the hull is what records where she is made fast. Looking for an
        `occupant` on the berth was inventing an attribute that does not exist, and it
        would have quietly found nobody for ever.

        Walks up from wherever the buyer is standing to the port room the berths belong to,
        so this works from a shop three streets inland as well as from the quay itself -
        which is the point, because the bar is never on the pier.

    """
    from ...typeclasses import Vessel

    port = _port_of(getattr(character, "location", None))
    if port is None:
        return None
    for hull in Vessel.objects.all():
        if hull.docked_at == port:
            return hull
    return None


def _port_of(room, reach=6):
    """
    Args:
        room (Object): Where somebody is standing.
        reach (int, optional): How many rooms to walk before giving up.

    Returns:
        port (PortRoom or None): The nearest room with berths.

    Notes:
        A breadth-first walk over exits, bounded, because a town is a handful of rooms
        across and an unbounded search would wander into the cane. Bounded searches that
        quietly find nothing are a hazard; this one is bounded to more than the distance
        from any counter in Careenage to its own waterfront.

    """
    from ...rooms import PortRoom

    if room is None:
        return None
    seen = {room}
    edge = [room]
    for _ in range(reach):
        following = []
        for here in edge:
            if here.is_typeclass(PortRoom, exact=False) and getattr(here, "berths", ()):
                return here
            for way in here.contents:
                target = getattr(way, "destination", None)
                if target is not None and target not in seen:
                    seen.add(target)
                    following.append(target)
        edge = following
    return None


#: What a hundredweight of cargo fetches, in coin per tonne.
#:
#: Two prices and a spread between them, which is the whole of trading: an island pays well
#: for what it wants and asks well for what it has, and the difference between two islands
#: is where a voyage makes money. Deliberately crude - a real economy prices by supply, and
#: this is an example showing that the seam exists rather than a market.
PAID_PER_TONNE = 9
CHARGED_PER_TONNE = 6


class CmdMarket(Command):
    """
    What this port buys and sells by the ton.

    Usage:
        market

    Islands trade. Each wants one cargo and offers another, and a captain who reads both
    before sailing does better than one who does not - the chain of them makes a round.
    """

    key = "market"
    aliases = ("trade",)
    locks = "cmd:all()"
    help_category = "Ashore"

    def func(self):
        """Read out what the island trades."""
        island = _island_here(self.caller)
        if island is None:
            self.caller.msg("Nobody here trades by the ton.")
            return

        from . import islands

        wants, offers = islands.trade_at(island)
        lines = [f"|w{island['key']}|n trades:"]
        if wants:
            lines.append(
                f"  buys  {wants.name:<18} {PAID_PER_TONNE} coin the ton   "
                "|xsell <tons> " + wants.key + "|n"
            )
        if offers:
            lines.append(
                f"  sells {offers.name:<18} {CHARGED_PER_TONNE} coin the ton  "
                "|xbuy cargo <tons> " + offers.key + "|n"
            )
        self.caller.msg(chr(10).join(lines))


class CmdSellCargo(Command):
    """
    Sell cargo out of your ship's hold to the island.

    Usage:
        sell <tons> <cargo>

    She has to be lying at the pier, and the island has to want what you are selling. The
    cargo comes out of her holds and the coin goes in your purse.
    """

    key = "sell"
    locks = "cmd:all()"
    help_category = "Ashore"

    def func(self):
        """Take cargo out of the hold and pay for it."""
        from ...cargo import commodity_named
        from . import islands

        island = _island_here(self.caller)
        if island is None:
            self.caller.msg("Nobody here buys cargo by the ton.")
            return

        vessel = _ship_alongside(self.caller)
        if vessel is None:
            self.caller.msg("You have no ship lying here to sell out of.")
            return

        tons, _, what = self.args.strip().partition(" ")
        try:
            tonnes = float(tons)
        except ValueError:
            self.caller.msg("Sell how many tons of what? Try |wsell 5 salt|n.")
            return

        commodity = commodity_named(what.strip())
        wants, _offers = islands.trade_at(island)
        if commodity is None or wants is None or commodity.key != wants.key:
            self.caller.msg(
                f"{island['key']} does not buy that. Try |wmarket|n to see what it wants."
            )
            return

        # A TransferResult, not a list of parcels: it carries the one parcel that crossed
        # the rail, how much was refused, and which capacity refused it. Treating it as a
        # sequence read as "nothing came off" for a discharge that had worked perfectly.
        landed = vessel.discharge(commodity, tonnes)
        if not landed.success or landed.parcel is None:
            self.caller.msg(f"She has no {commodity.name} aboard.")
            return

        moved = landed.parcel.tonnes
        paid = int(round(moved * PAID_PER_TONNE))
        self.caller.db.coin = people.purse_of(self.caller) + paid
        self.caller.msg(f"You land {moved:.1f} tons of {commodity.name} and are paid {paid} coin.")
        if landed.refused:
            self.caller.msg(f"{landed.refused:.1f} tons stayed aboard - she had no more to land.")
        self.caller.location.msg_contents(
            f"{self.caller.key} lands {moved:.1f} tons of {commodity.name}.",
            exclude=self.caller,
        )


def _island_here(character):
    """
    Args:
        character (Object): Who is asking.

    Returns:
        island (dict or None): The island whose pier this is, if it is one.

    Notes:
        Found through the pier's own `landmark`, which the builder wrote there - so this
        works from the pier itself and from anywhere the port walk reaches, and does not
        need a second list of which room belongs to which island.

    """
    from . import islands

    port = _port_of(getattr(character, "location", None))
    name = getattr(getattr(port, "db", None), "landmark", None) if port else None
    if not name:
        return None
    for island in islands.ISLANDS:
        if island["key"] == name:
            return island
    return None


class CmdBuildAetos(Command):
    """
    Build the Aetos coast ashore: the town, the islands and their people.

    Usage:
        build_aetos

    Safe to run more than once. Everything is found before it is made, so a second run adds
    nothing and moves nothing.
    """

    key = "build_aetos"
    locks = "cmd:perm(Builder)"
    help_category = "Building"

    def func(self):
        """Make the world."""
        from . import build

        self.caller.msg("Building the Aetos coast. This takes a moment.")
        made = build(on_report=self.caller.msg)
        self.caller.msg(
            f"Done. {made['rooms']} rooms, {made['exits']} exits and {made['people']} "
            "people made."
        )


__all__ = (
    "GOODS",
    "PAID_PER_TONNE",
    "CHARGED_PER_TONNE",
    "counters_here",
    "CmdBrowse",
    "CmdBuy",
    "CmdMarket",
    "CmdSellCargo",
    "CmdBuildAetos",
)
