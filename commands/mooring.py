"""
Coming alongside, letting go, and bringing up to an anchor.

"""

from ..formatting import format_range
from ..messaging import (
    ALONGSIDE_ORDER,
    ANCHOR_ORDER,
    GANGWAY_DOWN,
    LET_GO,
    MADE_FAST,
    SINGLE_UP,
    WEIGH_ORDER,
)
from ..ports import (
    BADLY_ALIGNED,
    OCCUPIED,
    TOO_BEAMY,
    TOO_DEEP,
    TOO_FAR,
    TOO_FAST,
    TOO_LONG,
    can_dock,
)
from ..rooms import berths_near, rig_gangway
from ..motion import HelmOrders
from ..vessel import WEATHER_DECKS
from .base import MAX_ANCHORING_SPEED, MaritimeCommand, ms_to_knots

BERTH_REFUSALS = {
    TOO_FAR: "The berth is {distance} off. Work her in closer before you put lines ashore.",
    TOO_FAST: "She still has way on. Take it off her before you go alongside.",
    BADLY_ALIGNED: "She is lying across the berth. Bring her round parallel to the quay.",
    TOO_LONG: "She is too long for that berth.",
    TOO_BEAMY: "She is too broad in the beam for that berth.",
    TOO_DEEP: "She draws too much for the water alongside there.",
    OCCUPIED: "There is a ship lying there already.",
}


class CmdDock(MaritimeCommand):
    """
    Bring her alongside and make fast.

    Usage:
      dock
      dock <berth>

    Puts lines ashore and lowers the gangway, after which the quay is one step
    off the deck like any other exit. She must be near enough for the lines to
    reach, slow enough not to break the quay, lying roughly along it, and small
    enough to fit the berth.

    With no argument she takes the nearest berth, and says why if it will not
    have her.

    """

    key = "dock"
    aliases = ("moor", "berth")

    def at_helm(self, vessel):
        """
        Args:
            vessel (Vessel): The hull the caller is aboard.

        """
        if vessel.docked:
            self.caller.msg("She is already made fast.")
            return

        position = vessel.maritime_position
        if position is None:
            self.caller.msg("She is not afloat anywhere near a quay.")
            return

        found = berths_near(position)
        if not found:
            self.caller.msg("There is no berth within reach of her lines.")
            return

        if self.args.strip():
            wanted = self.args.strip().lower()
            found = [pair for pair in found if pair[1].key.lower() == wanted]
            if not found:
                self.caller.msg(f"No berth called '{self.args.strip()}' within reach.")
                return

        port, berth = found[0]
        result = can_dock(
            position,
            vessel.speed,
            vessel.heading,
            vessel.length,
            vessel.beam,
            vessel.draft,
            berth,
            occupied=port.occupant_of(berth) is not None,
        )
        if not result:
            refusal = BERTH_REFUSALS.get(result.code, "She cannot lie there.")
            self.caller.msg(refusal.format(distance=format_range(result.distance)))
            return

        deck = self.landing_deck(vessel)
        if deck is None:
            self.caller.msg("She has no open deck for a gangway to land on.")
            return

        self.order(vessel, ALONGSIDE_ORDER)

        gangway = rig_gangway(deck, port)
        vessel.make_fast(port, berth, gangway)

        self.order(vessel, MADE_FAST, berth=berth.key, side=result.side)
        self.order(vessel, GANGWAY_DOWN)
        port.msg_contents(f"{vessel.key} comes alongside, and her gangway comes down.")

    def landing_deck(self, vessel):
        """
        The deck a gangway would land on.

        Args:
            vessel (Vessel): The hull.

        Returns:
            room (ShipRoom or None): Her lowest weather deck, or None if she has
                no deck open to the sky.

        Notes:
            The lowest, not the highest. A gangway reaches a quay from the main
            deck; running it to the masthead because that is where the lookout
            stands would be a remarkable sight.

        """
        decks = [room for room in vessel.ship_rooms if room.exposure in WEATHER_DECKS]
        if not decks:
            return None
        return min(decks, key=lambda room: room.height_of_eye)


class CmdCastOff(MaritimeCommand):
    """
    Let go the lines and get under way.

    Usage:
      cast off

    Takes the gangway up and lets go fore and aft. The quay stops being one step
    off the deck, and she answers her helm again.

    """

    key = "cast off"
    aliases = ("castoff", "undock", "unmoor")

    def at_helm(self, vessel):
        """
        Args:
            vessel (Vessel): The hull the caller is aboard.

        """
        if not vessel.docked:
            self.caller.msg("She is not made fast to anything.")
            return

        port = vessel.docked_at
        self.order(vessel, SINGLE_UP)

        vessel.let_go()

        self.order(vessel, LET_GO)
        if port:
            port.msg_contents(f"{vessel.key} takes in her gangway and casts off.")


class CmdAnchor(MaritimeCommand):
    """
    Let go the anchor.

    Usage:
      drop anchor
      anchor

    Brings the vessel up and holds her. She must have little enough way on to
    bring up safely - letting go with the ship still running is how cables part
    and anchors are lost.

    While anchored she will not answer her helm or make way, whatever canvas is
    set. Use `weigh anchor` to get under way again.
    """

    key = "drop anchor"
    aliases = ("anchor", "let go anchor", "come to anchor")

    def at_helm(self, vessel):
        """Let go, if she is quiet enough to bring up."""
        if vessel.anchored:
            self.caller.msg("She already lies to her anchor.")
            return
        if vessel.speed > MAX_ANCHORING_SPEED:
            self.caller.msg(
                f"She has too much way on - {ms_to_knots(vessel.speed):.1f} knots. "
                "Take the way off her first, or you will part the cable."
            )
            return

        vessel.anchored = True
        vessel.orders = HelmOrders(heading=vessel.orders.heading, speed=0.0)
        self.order(vessel, ANCHOR_ORDER)


class CmdWeighAnchor(MaritimeCommand):
    """
    Weigh the anchor and get under way.

    Usage:
      weigh anchor
      weigh

    Breaks the anchor out of the ground and brings it home. She will answer her
    helm again, though she will need canvas set and a wind to go anywhere.
    """

    key = "weigh anchor"
    aliases = ("weigh", "up anchor")

    def at_helm(self, vessel):
        """Break out the anchor."""
        if not vessel.anchored:
            self.caller.msg("The anchor is already catted; she is not brought up.")
            return

        vessel.anchored = False
        self.order(vessel, WEIGH_ORDER)
