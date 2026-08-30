"""
The base every maritime command shares, and the units they speak in.

"""

from evennia.commands.command import Command

from ..typeclasses import Vessel

# One knot is one nautical mile per hour, and a nautical mile is 1852 metres.
METRES_PER_SECOND_PER_KNOT = 1852.0 / 3600.0

# How far off a landmark can be and still be worth a bearing, in metres. The
# same reach as a berth search, because a quay you could tie up to is
# unambiguously a quay you can identify.
FIX_RANGE = 3000.0

# Fastest a vessel may be moving and still bring up safely. Letting go with way
# still on her is how cables part and anchors are left on the bottom.
MAX_ANCHORING_SPEED = 1.0


def knots_to_ms(knots):
    """
    Convert knots to metres per second.

    Args:
        knots (float): Speed in knots.

    Returns:
        speed (float): Speed in metres per second.

    """
    return float(knots) * METRES_PER_SECOND_PER_KNOT


def ms_to_knots(metres_per_second):
    """
    Convert metres per second to knots.

    Args:
        metres_per_second (float): Speed in metres per second.

    Returns:
        knots (float): Speed in knots.

    """
    return float(metres_per_second) / METRES_PER_SECOND_PER_KNOT


def vessel_of(caller):
    """
    The vessel the caller is aboard, if any.

    Args:
        caller (Object): Whoever typed the command.

    Returns:
        vessel (Vessel or None): The hull they are standing on.

    Notes:
        Walks the same chain the position resolver does, so being "aboard" means
        exactly what it means everywhere else rather than being decided separately
        here.

    """
    location = getattr(caller, "location", None)
    source = getattr(location, "maritime_position_source", None)
    return source if isinstance(source, Vessel) else None


class MaritimeCommand(Command):
    """Base for commands that require the caller to be aboard a vessel."""

    locks = "cmd:all()"
    help_category = "Maritime"

    def func(self):
        """Find the vessel, then defer to the command."""
        vessel = vessel_of(self.caller)
        if vessel is None:
            self.caller.msg("You are not aboard a vessel.")
            return
        self.at_helm(vessel)

    def at_helm(self, vessel):
        """
        Do the work, with a vessel guaranteed.

        Args:
            vessel (Vessel): The hull the caller is aboard.

        """
        raise NotImplementedError

    def order(self, vessel, event, **detail):
        """
        Give a spoken order, and let the crew answer it.

        Args:
            vessel (Vessel): The hull whose company is speaking.
            event (str): One of the order constants in `messaging`.
            **detail: What the order carries.

        Notes:
            The words come from the vessel's narrator, so a game that has
            replaced its voice has replaced this too. A command's job is to know
            *that* an order was given and to whom it carries - never what it
            sounds like.

        """
        spoken = vessel.narrator.order_for(event, who=self.caller.key, **detail)
        if spoken.called:
            self.caller.msg(spoken.called)
        if spoken.overheard:
            self.announce(spoken.overheard)
        if spoken.answered:
            self.aboard(vessel, spoken.answered)

    def announce(self, text):
        """
        Call an order out loud, so everyone in earshot hears it.

        Args:
            text (str): What the caller is heard to order.

        Notes:
            Orders on a ship are spoken. A helm order that only the person who
            typed it can see turns a crewed vessel into several people each
            sailing their own private ship.

        """
        location = getattr(self.caller, "location", None)
        if location is not None:
            location.msg_contents(text, exclude=self.caller)

    def aboard(self, vessel, text):
        """
        Send a line to everyone aboard, wherever they are standing.

        Args:
            vessel (Vessel): The hull whose company should hear it.
            text (str): What is said.

        Notes:
            An order acknowledged at the helm carries through the ship. Unlike
            `announce`, this reaches the hold as well as the deck, and includes
            the person who gave the order - they are meant to hear the answer.

        """
        for room in vessel.ship_rooms:
            room.msg_contents(text)
