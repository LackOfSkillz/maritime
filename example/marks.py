"""
The marks laid in the example world's waters.

Every island in this chain has a harbour on its western side, and until this module
existed not one of them had a buoyed approach - which is exactly the failure the buoyage
invariant is for. A world can be built, tested, sailed and demonstrated with every
harbour a guess, because nothing was checking.

**One safe-water mark off each harbour, and one offing they all connect to.** That is the
smallest thing that satisfies "every berth has a marked approach", and it is deliberately
the smallest: a demonstration world should show the shape of the rule rather than bury it
under pilotage nobody reads.

**The offing is the seaward end of everything.** A vessel arriving from open water makes
it first, and every approach runs from there. That gives the invariant something to ask
its question *from* - "reachable from open water" needs somewhere that counts as open
water, and it has to be authored rather than guessed.

"""

from ..buoyage import SAFE_WATER, Buoyage
from ..position import WorldPosition
from ..routes import NavigationNetwork, Waypoint
from .geography import ISLANDS, harbour_position
from .world import STONE_QUAY

#: Which way is "in". Inbound here is eastward, from the offing towards the chain.
BUOYAGE = Buoyage(direction=90.0)

#: Where a vessel arriving from open water makes her landfall, west of everything.
OFFING = WorldPosition(-1200.0, 0.0)

#: How far off a harbour its fairway buoy is moored, in metres. Far enough to be in
#: water a keel can float in, near enough that raising it means you have found the
#: place.
FAIRWAY_OFFSET = 320.0


def fairway_key(name):
    """
    Args:
        name (str): An island's name.

    Returns:
        key (str): What its fairway buoy is called.

    """
    return f"{name} fairway"


def harbour_key(name):
    """
    Args:
        name (str): An island's name.

    Returns:
        key (str): What its harbour mark is called.

    """
    return f"{name} harbour"


def berths():
    """
    Returns:
        keys (tuple): Every mark that stands at a place a vessel can lie.

    Notes:
        What the invariant is *about*. A berth with no marked approach is the thing
        the test refuses to let a builder ship.

    """
    return ("stone quay",) + tuple(harbour_key(name) for name, _x, _y, _reach in ISLANDS)


def seaward():
    """
    Returns:
        keys (tuple): The marks a vessel arriving from open water would make first.

    """
    return ("the offing",)


class Approaches(NavigationNetwork):
    """
    The marks of this chain, laid at load.

    Notes:
        Authored rather than derived. Which water is safe is a statement this world
        makes about itself, and an algorithm that searched the seabed for a way
        through would find every gap a hull could theoretically squeeze - including
        the ones no sane master would take at night.

    """

    def __init__(self):
        super().__init__()
        self.add(Waypoint("the offing", OFFING, SAFE_WATER))
        self.add(Waypoint("stone quay", STONE_QUAY, SAFE_WATER))
        self.link("the offing", "stone quay")

        for island in ISLANDS:
            name = island[0]
            harbour = harbour_position(island)
            fairway = harbour.offset(dx=-FAIRWAY_OFFSET)

            self.add(Waypoint(fairway_key(name), fairway, SAFE_WATER))
            self.add(Waypoint(harbour_key(name), harbour, SAFE_WATER))
            self.link("the offing", fairway_key(name))
            self.link(fairway_key(name), harbour_key(name))
