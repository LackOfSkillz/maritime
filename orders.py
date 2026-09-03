"""
What she is to do when nobody is asking.

A captain cannot be at the rail for every hour of a passage, and a mate who only steers for
the next mark will sail a burning ship into an enemy squadron because nobody told him not
to. A standing order is the instruction left behind: *if this, then that* - and the whole of
the design is in what "this" and "that" are allowed to be.

**Orders are named, not written.** A condition is a key into a registry and so is an action.
The tempting design is to store a callable on the order, and it does not survive: an Evennia
attribute is a pickle, a function is not reliably one, and the order that worked all session
is gone after a reload. Names survive anything.

**The highest priority whose condition holds is the one in force, and only one is.** Two
orders that both want the helm cannot both have it, so this does not try to merge them - it
picks, and it *records what it overrode*. A captain who finds his ship anchored instead of
running needs to be told which order did it, and an order silently losing to another is the
single worst thing this module could do.

**Replanning is taking the con.** An order that fires takes her out of the sailing master's
hands for as long as its condition holds, and gives her back when it stops - which is why the
condition is re-read every tick rather than latched. A ship that shortened down for a squall
should make sail again when it passes without anybody remembering to say so.

**Nothing here decides what a game's orders are.** The conditions and actions shipped are the
ones answerable out of state this contrib already owns - she is making water, she is alight,
there is no water under her. A game with a war, a cargo market or a weather god registers its
own and they rank alongside these.

"""

from dataclasses import dataclass, replace

from .results import Result

#: How much water is worth an order about.
#:
#: A tenth of her buoyancy. Below that she is weeping and a ship weeps; past it somebody
#: should be at the pumps, which is exactly the sort of thing a captain leaves word about.
MAKING_WATER_AT = 0.1

#: How little water under her keel is worth an order about, in metres.
SHOAL_AT = 3.0

#: How hard it has to blow before she should be shortening down, in metres a second.
#:
#: Fifteen, about a near gale. This is not the speed her canvas splits at - `sail_for_wind`
#: already knows that per plan - it is the speed at which a captain would want to be told
#: rather than to find out.
BLOWING_AT = 15.0

NO_SUCH_CONDITION = "no_such_condition"
NO_SUCH_ACTION = "no_such_action"
NO_SUCH_ORDER = "no_such_order"
NOTHING_IN_FORCE = "nothing_in_force"


@dataclass(frozen=True)
class StandingOrder:
    """
    One instruction left behind.

    Attributes:
        key (str): What it is called, and how it is cancelled.
        when (str): A condition name.
        then (str): An action name.
        priority (int): Higher wins. Ties go to the order given first.

    Notes:
        Four plain values, so an order pickles into an attribute and comes back after a
        reload as the order it was. Storing the condition as a callable would be tidier to
        read and would quietly stop working the first time the server restarted.

    """

    key: str
    when: str
    then: str
    priority: int = 0


@dataclass(frozen=True, kw_only=True)
class OrderResult(Result):
    """
    What the standing orders did, and what they did not.

    Attributes:
        order (StandingOrder): The one in force, if any.
        overridden (tuple): Orders whose conditions also held and which lost.
        acted (bool): Whether anything was actually done to her.

    """

    order: StandingOrder = None
    overridden: tuple = ()
    acted: bool = False


def making_water(vessel):
    """
    Args:
        vessel (object): The hull.

    Returns:
        holds (bool): Whether she has enough water in her to want an order.

    """
    return float(getattr(vessel, "water", 0.0)) >= MAKING_WATER_AT


def on_fire(vessel):
    """
    Args:
        vessel (object): The hull.

    Returns:
        holds (bool): Whether she is on fire.

    """
    return bool(getattr(vessel, "alight", False))


def aground(vessel):
    """
    Args:
        vessel (object): The hull.

    Returns:
        holds (bool): Whether she is on the ground.

    """
    return bool(getattr(vessel, "aground", False))


def blowing_hard(vessel):
    """
    Args:
        vessel (object): The hull.

    Returns:
        holds (bool): Whether it is blowing hard enough to want an order.

    """
    here = getattr(vessel, "maritime_position", None)
    if here is None:
        return False
    from .environment import weather_at

    return weather_at(here).wind.speed >= BLOWING_AT


def shoal_water(vessel):
    """
    Args:
        vessel (object): The hull.

    Returns:
        holds (bool): Whether there is little enough under her keel to want an order.

    Notes:
        Asked of the same model the groundings use, so an order about shoal water fires over
        the shoals the chart shows rather than over a second set invented for orders.

    """
    here = getattr(vessel, "maritime_position", None)
    if here is None:
        return False
    from . import config
    from .environment import clearance_at

    return clearance_at(here, vessel.draft, config.time_provider().now()) <= SHOAL_AT


def stranger_in_sight(vessel):
    """
    Args:
        vessel (object): The hull.

    Returns:
        holds (bool): Whether anything at all is in sight.

    Notes:
        Anything, not an enemy. Who is an enemy is a question about a game's world and this
        contrib does not have one - a game that knows registers `enemy_in_sight` of its own
        and ranks it above this.

    """
    return bool(vessel.contacts())


#: The conditions this contrib can answer out of what it already owns.
CONDITIONS = {
    "making_water": making_water,
    "on_fire": on_fire,
    "aground": aground,
    "blowing_hard": blowing_hard,
    "shoal_water": shoal_water,
    "stranger_in_sight": stranger_in_sight,
}


def shorten_sail(vessel):
    """
    Take in canvas.

    Args:
        vessel (object): The hull.

    Returns:
        acted (bool): Whether anything changed.

    """
    from .sailing import REEFED

    if vessel.sail_plan.area <= REEFED.area:
        return False
    vessel.sail_plan = REEFED
    return True


def make_sail(vessel):
    """
    Set working canvas.

    Args:
        vessel (object): The hull.

    Returns:
        acted (bool): Whether anything changed.

    """
    from .sailing import WORKING

    if vessel.sail_plan.area >= WORKING.area:
        return False
    vessel.sail_plan = WORKING
    return True


def heave_to(vessel):
    """
    Take the way off her and leave her lying.

    Args:
        vessel (object): The hull.

    Returns:
        acted (bool): Whether anything changed.

    Notes:
        Furled and stopped, rather than backed against a topsail. Backing one sail against
        another needs a rig this contrib does not model - a sail plan is an area and a
        limit - so what is shipped is the thing the area *can* say.

    """
    from .motion import HelmOrders
    from .sailing import FURLED

    changed = vessel.sail_plan.area > 0.0
    vessel.sail_plan = FURLED
    vessel.orders = HelmOrders(heading=vessel.heading, speed=0.0)
    return changed


def clear_for_action(vessel):
    """
    Fighting sail, and the con back to whoever is aboard.

    Args:
        vessel (object): The hull.

    Returns:
        acted (bool): Whether anything changed.

    """
    from .sailing import BATTLE

    changed = vessel.sail_plan is not BATTLE
    vessel.sail_plan = BATTLE
    return changed


def man_the_pumps(vessel):
    """
    Put hands on the pumps.

    Args:
        vessel (object): The hull.

    Returns:
        acted (bool): Whether anything changed.

    """
    company = getattr(vessel, "company", None)
    hands = company.complement if company is not None else 0
    if not hands:
        return False
    return bool(vessel.man_pumps(max(1.0, hands * 0.25)))


#: The actions this contrib can take without knowing anything about a game.
ACTIONS = {
    "shorten_sail": shorten_sail,
    "make_sail": make_sail,
    "heave_to": heave_to,
    "clear_for_action": clear_for_action,
    "man_the_pumps": man_the_pumps,
}


def condition_named(name):
    """
    Args:
        name (str): A condition key.

    Returns:
        condition (callable or None): What answers it.

    """
    from . import config

    return config.order_conditions().get(name)


def action_named(name):
    """
    Args:
        name (str): An action key.

    Returns:
        action (callable or None): What carries it out.

    """
    from . import config

    return config.order_actions().get(name)


class UnderOrders:
    """
    A hull with instructions left on her.

    Notes:
        The orders are hers rather than her captain's, deliberately. A ship handed to a
        prize master should keep the orders she was sailing under until somebody changes
        them, and orders that lived on a person would go over the side with him.

    """

    def at_object_creation(self):
        """Set up this part of a newly created vessel."""
        super().at_object_creation()
        self.db.standing_orders = []

    @property
    def standing_orders(self):
        """
        Returns:
            orders (tuple): Every order left on her, highest priority first.

        """
        given = tuple(self.db.standing_orders or ())
        return tuple(sorted(given, key=lambda order: -order.priority))

    def leave_order(self, key, when, then, priority=0):
        """
        Leave word about what she is to do.

        Args:
            key (str): What to call it.
            when (str): A condition name.
            then (str): An action name.
            priority (int, optional): Higher wins.

        Returns:
            result (OrderResult): The order, or why it was refused.

        Notes:
            Refuses a condition or action it does not know, rather than storing it and
            failing silently every tick for the rest of the voyage. An order that never
            fires and never says why is worse than no order.

        """
        if condition_named(when) is None:
            return OrderResult(success=False, code=NO_SUCH_CONDITION)
        if action_named(then) is None:
            return OrderResult(success=False, code=NO_SUCH_ACTION)

        given = [order for order in (self.db.standing_orders or ()) if order.key != key]
        made = StandingOrder(key=key, when=when, then=then, priority=int(priority))
        given.append(made)
        self.db.standing_orders = given
        return OrderResult(success=True, order=made)

    def cancel_order(self, key):
        """
        Take an order back.

        Args:
            key (str): Which one.

        Returns:
            result (OrderResult): What was cancelled, or a failure.

        """
        given = list(self.db.standing_orders or ())
        for order in given:
            if order.key == key:
                given.remove(order)
                self.db.standing_orders = given
                return OrderResult(success=True, order=order)
        return OrderResult(success=False, code=NO_SUCH_ORDER)

    def orders_that_hold(self):
        """
        Returns:
            holding (tuple): Every order whose condition is true, highest priority first.

        Notes:
            Re-read rather than latched, which is what makes an order let go of her. A ship
            that shortened down for a squall makes sail again when it passes, because the
            condition stopped being true and nobody had to remember to say so.

        """
        holding = []
        for order in self.standing_orders:
            condition = condition_named(order.when)
            if condition is not None and condition(self):
                holding.append(order)
        return tuple(holding)

    def order_in_force(self):
        """
        Returns:
            result (OrderResult): The one in force and what it overrode.

        """
        holding = self.orders_that_hold()
        if not holding:
            return OrderResult(success=False, code=NOTHING_IN_FORCE)
        return OrderResult(success=True, order=holding[0], overridden=holding[1:])

    def obey_standing_orders(self):
        """
        Do whatever the orders say, if any of them say anything.

        Returns:
            result (OrderResult): What was done, and what lost.

        Notes:
            **One order acts, and the rest are named.** Merging two orders that both want
            the helm would produce a ship doing neither thing properly; picking one and
            saying which is a ship that did as it was told and a captain who can find out
            why.

            Called from the tick before the sailing master works her, so an order that has
            taken her out of his hands has already done so by the time he asks for the helm.

        """
        standing = self.order_in_force()
        if not standing:
            return standing

        action = action_named(standing.order.then)
        acted = bool(action(self)) if action is not None else False
        return replace(standing, acted=acted)
