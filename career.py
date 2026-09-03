"""
The things worth having done, announced.

A sea career runs on countable events: a passage made, a cargo landed, a prize taken, a
ship got off the ground she was hard on. Every one of these **already happens** in this
contrib. It simply did not say so out loud, and a game's own progression had nothing to
listen for.

**This ships no skill system, and it never will.** Not a small one, not a default one, not
an optional one - the moment it does, every game with its own has to fight it, and that is
the same rule keeping economy, character combat and stamina out. What ships instead is a
set of announcements with enough in them to count:

    a passage made        where from, where to, how far, how long
    a cargo landed        what, how much, where
    a prize taken         already announced, since the ownership work
    off the ground        how she came off, and what it cost

A game that counts prizes has a pirate. A game that counts cargo delivered has a merchant.
They are the same events counted differently, which is why this does not invent a
reputation model: careers are *histories*, and the contrib's job is to make sure everything
worth counting is announced with enough detail to count it.

**What is deliberately not here.** A chase won. It is on the roadmap and it is the one item
whose moment this contrib cannot honestly identify - a chase needs two ships and an
intention, and intention is not a thing a hull knows. A game that models pursuit knows when
one ends and can say so itself.

"""

from dataclasses import dataclass

from .events import Event, bus


@dataclass(frozen=True, kw_only=True)
class PassageMade(Event):
    """
    She arrived where she was told to go.

    Attributes:
        vessel (object): The hull.
        captain (object or None): Who had her.
        sailed (float): How far she came, in metres.
        seconds (float): How long it took, in game seconds.

    Notes:
        The distance is what she *sailed*, not the distance between the two places. A
        passage beating up against a headwind is longer than the chart says and is worth
        more of whatever a game pays for one.

    """

    vessel: object
    captain: object = None
    sailed: float = 0.0
    seconds: float = 0.0


@dataclass(frozen=True, kw_only=True)
class CargoLanded(Event):
    """
    Cargo came out of her at a quay.

    Attributes:
        vessel (object): The hull.
        captain (object or None): Who had her.
        commodity (str): What it was.
        tonnes (float): How much came off.
        port (object or None): Where.

    """

    vessel: object
    captain: object = None
    commodity: str = ""
    tonnes: float = 0.0
    port: object = None


@dataclass(frozen=True, kw_only=True)
class CameOffTheGround(Event):
    """
    She was aground and is not any more.

    Attributes:
        vessel (object): The hull.
        captain (object or None): Who had her.
        by (str): How - `TIDE` if the water came back, `WORK` if they hauled her off.
        hurt (float): What the grounding had cost her hull, 0 to 1.

    Notes:
        **How she came off is the whole of the news.** Waiting for the tide is patience;
        kedging her off is work, and a game that wants to reward seamanship rather than
        endurance needs to be able to tell them apart.

    """

    vessel: object
    captain: object = None
    by: str = ""
    hurt: float = 0.0


#: How a ship comes off the ground.
TIDE = "tide"
WORK = "work"


class KeepsALog:
    """
    A hull that records how far she has run.

    Notes:
        **What she sailed, not how far apart the two places are.** A passage beating up
        against a headwind is half as long again as the chart says, and a career that paid
        by the straight line would pay a good captain less for the harder passage.

        The log is streamed at the start of a passage rather than read and reset at the end,
        so a ship that never finishes one still has an honest figure on her.

    """

    @property
    def distance_run(self):
        """
        Returns:
            metres (float): How far she has sailed since the log was last streamed.

        """
        return float(self.db.distance_run or 0.0)

    def stream_the_log(self):
        """
        Start the count again.

        Returns:
            run (float): What it stood at.

        """
        stood = self.distance_run
        self.db.distance_run = 0.0
        return stood

    def enter_in_the_log(self, metres):
        """
        Args:
            metres (float): How far she has come since the last tick.

        Notes:
            Called from the tick with the distance actually covered, which already accounts
            for leeway and for the water having moved under her.

        """
        if metres:
            self.db.distance_run = self.distance_run + float(metres)


def passage_made(vessel, sailed=0.0, seconds=0.0):
    """
    Say she has arrived.

    Args:
        vessel (object): The hull.
        sailed (float, optional): How far she came, in metres.
        seconds (float, optional): How long it took.

    Returns:
        event (PassageMade): What was published.

    """
    from . import config

    told = PassageMade(
        game_time=config.time_provider().now(),
        vessel=vessel,
        captain=getattr(vessel, "captain", None),
        sailed=float(sailed),
        seconds=float(seconds),
    )
    bus().publish(told)
    return told


def cargo_landed(vessel, commodity, tonnes, port=None):
    """
    Say cargo came off her.

    Args:
        vessel (object): The hull.
        commodity (str): What it was.
        tonnes (float): How much.
        port (object, optional): Where.

    Returns:
        event (CargoLanded or None): What was published, or None if nothing came off.

    Notes:
        Nothing is said for a discharge that moved no cargo. An event announcing that
        nothing happened is an event a game has to learn to ignore.

    """
    if tonnes <= 0.0:
        return None

    from . import config

    told = CargoLanded(
        game_time=config.time_provider().now(),
        vessel=vessel,
        captain=getattr(vessel, "captain", None),
        commodity=str(commodity),
        tonnes=float(tonnes),
        port=port,
    )
    bus().publish(told)
    return told


def came_off_the_ground(vessel, by, hurt=0.0):
    """
    Say she is afloat again.

    Args:
        vessel (object): The hull.
        by (str): `TIDE` or `WORK`.
        hurt (float): What it cost her hull.

    Returns:
        event (CameOffTheGround): What was published.

    """
    from . import config

    told = CameOffTheGround(
        game_time=config.time_provider().now(),
        vessel=vessel,
        captain=getattr(vessel, "captain", None),
        by=str(by),
        hurt=float(hurt),
    )
    bus().publish(told)
    return told
