"""
Building a ship at a dock, laying her up, and calling her back.

    maritime build                      what can be built, and what each hull is
    maritime build <rig> <name>         build one, alongside, ready to sail
    maritime summon <name>              bring a laid-up ship of yours to this dock
    maritime lay up <name>              put one of yours into ordinary and free her berth
    maritime player build on|off        whether players may build at all

**All of them want a quay under your feet, and none of them will walk to find one.** A dock
is a `PortRoom` with berths in it - the same rooms `dock` and `cast off` already work
against, so no game has to declare anything new. Somebody standing in a market square is
told to go to the dock rather than quietly served, because a ship appearing three streets
inland is worse than a refusal.

**A name has to be free.** Two ships called *Swift* is a harbour where `summon Swift` is a
coin toss, and where `@ship owner Swift = someone` may hand over the wrong hull. The check
is against every vessel in the game, laid up or not - a laid-up ship is still a ship, and
the whole point of laying her up is that she comes back.

**Laying up is the hygiene, and it is a real thing rather than a deletion.** See `ordinary`:
a ship in ordinary keeps her cargo, her crew, her damage and her compartments, and gives up
only her berth and her place on the water. She is out of the way, not gone.
"""

from evennia.commands.cmdset import CmdSet
from evennia.commands.command import Command
from evennia.utils import create
from evennia.utils.search import search_object

from .. import ordinary, shipyard, switches
from ..rooms import PortRoom, rig_gangway
from ..typeclasses import Vessel
from ..vessel import WEATHER_DECKS

#: Re-exported, so that the shipyard has one name for the permission and `switches` has one
#: place that knows how it is stored. It sits with the other runtime switches because it is
#: one of them, and it is named here because this is where it is read.
PLAYER_BUILD_KEY = switches.PLAYER_BUILD_KEY
players_may_build = switches.players_may_build
set_players_may_build = switches.set_players_may_build


def dock_here(caller):
    """
    Args:
        caller (Object): Whoever is asking.

    Returns:
        port (PortRoom or None): The quay they are standing on, if it is one.

    Notes:
        The room they are in and not a room nearby. Every other command in this contrib
        that reaches for a port walks outward from where somebody stands, because a shop
        three streets up still belongs to the harbour. This one does not, and should not:
        the answer to "may I build a ship here" ought to be the same for two people
        standing in the same place, and a bounded walk makes it depend on which way the
        exits happen to run.

    """
    where = getattr(caller, "location", None)
    if where is None:
        return None
    if not where.is_typeclass(PortRoom, exact=False):
        return None
    return where if where.berths else None


def a_berth_for(port, length, beam, draft):
    """
    Args:
        port (PortRoom): The quay.
        length (float): Her length, in metres.
        beam (float): Her beam, in metres.
        draft (float): How deep she sits, in metres.

    Returns:
        found (tuple): `(berth, said)` - a free berth that takes her, or None and a
            sentence saying why the last candidate would not.

    Notes:
        Reports the *reason* rather than only failing, because "no berth" and "no berth
        deep enough for a frigate" send somebody to two different places. A quay with
        three berths all too shallow answers about the water, which is what is actually
        wrong.

        Said in the words `dock` already uses. `Berth.takes` answers with a code, and a
        second set of sentences for the same three refusals is how a game ends up telling
        a player two different things about one berth.

    """
    from .mooring import BERTH_REFUSALS

    refusal = None
    empty = False
    for berth in port.berths:
        if port.occupant_of(berth) is not None:
            continue
        empty = True
        reason = berth.takes(length, beam, draft)
        if reason is None:
            return berth, None
        refusal = reason
    if not empty:
        return None, "every berth here is taken"
    if refusal is None:
        return None, "no berth here will take her"
    return None, BERTH_REFUSALS.get(refusal, "she cannot lie there").rstrip(".")


def named(name):
    """
    Args:
        name (str): What to look for.

    Returns:
        vessel (Vessel or None): The one hull of that name, if there is exactly one.

    Notes:
        Exact and case-insensitive. Evennia's own search would match on a prefix and
        happily return the first of several, which is precisely the ambiguity the
        uniqueness rule exists to prevent - so this asks for the whole name.

    """
    wanted = str(name or "").strip().lower()
    if not wanted:
        return None
    for found in search_object(name, exact=False):
        if isinstance(found, Vessel) and found.key.lower() == wanted:
            return found
    return None


def landing_deck(vessel):
    """
    Args:
        vessel (Vessel): The hull.

    Returns:
        deck (ShipRoom or None): Her lowest weather deck.

    Notes:
        The lowest, because a gangway reaches a quay from the main deck. The same rule as
        `CmdDock` uses, and for the same reason.

    """
    decks = [room for room in vessel.ship_rooms if room.exposure in WEATHER_DECKS]
    if not decks:
        return None
    return min(decks, key=lambda room: room.height_of_eye)


def send_them_to_the_dock(caller):
    """
    Args:
        caller (Object): Whoever asked in the wrong place.

    Notes:
        Says what is missing rather than only that something is. "You cannot do that here"
        leaves somebody wandering; "go to a dock" tells them where to wander to.

    """
    caller.msg(
        "Ships are built and laid up at a dock, and this is not one. Find a quay with "
        "berths in it - anywhere you could |wdock|n a ship - and try again there."
    )


class CmdMaritimeBuild(Command):
    """
    Build a ship at this dock.

    Usage:
        maritime build
        maritime build <rig> <name>

    With no argument it lists what can be built and what each one is: how big she is, what
    she measures, what she will carry and how many she sleeps.

    Otherwise she is built alongside in a free berth, with her gangway down, ready to
    board. You must be standing on a quay, the name must not already belong to a ship, and
    there has to be a berth here that will take her - a frigate does not fit a fishing
    berth.

    Examples:
        maritime build cutter Kittiwake
        maritime build frigate HMS Amphitrite
    """

    key = "maritime build"
    aliases = ("maritime shipyard",)
    locks = "cmd:perm(Admin)"
    help_category = "Maritime"

    def access(self, srcobj, access_type="cmd", default=False, session=None):
        """
        Args:
            srcobj (Object): Who is trying to reach the command.
            access_type (str, optional): Which lock is being asked about.
            default (bool, optional): What to answer when no such lock exists.
            session (Session, optional): Passed through to the lock functions.

        Returns:
            allowed (bool): Whether they may use it.

        Notes:
            Hidden from players until the game turns building on, rather than visible and
            refused - the same bargain `maritime gui` makes, for the same reason. A player
            who can read the help for a command that will never work has been told about a
            feature this game does not have.

        """
        if access_type == "cmd" and players_may_build():
            return True
        return super().access(srcobj, access_type, default, session=session)

    def func(self):
        """List the hulls, or build one."""
        said = self.args.strip()
        if not said:
            self._list()
            return

        rig, _, name = said.partition(" ")
        name = name.strip().strip("=").strip()
        if not name:
            self.caller.msg("Build her as what, and call her what? |wmaritime build cutter Swift|n")
            return

        spec = shipyard.specification(rig)
        if spec is None:
            self.caller.msg(
                f"There is no '{rig}' in the book. |wmaritime build|n lists what there is."
            )
            return

        port = dock_here(self.caller)
        if port is None:
            send_them_to_the_dock(self.caller)
            return

        if named(name) is not None:
            self.caller.msg(
                f"There is a ship called |w{name}|n already. Two of a name is one too many "
                "- pick another."
            )
            return

        berth, why = a_berth_for(port, spec["length"], spec["beam"], spec["draft"])
        if berth is None:
            self.caller.msg(f"She cannot lie here: {why}.")
            return

        self._build(rig, name, port, berth)

    def _build(self, rig, name, port, berth):
        """
        Args:
            rig (str): One of `shipyard.NAMES`.
            name (str): What to call her.
            port (PortRoom): The quay.
            berth (Berth): Where she will lie.

        Notes:
            Her compartments are made before she is made fast, because `make_fast` rigs a
            gangway to a deck and a hull with no decks yet has none to rig it to.

        """
        hull = shipyard.outfit(create.create_object(Vessel, key=name), rig)
        shipyard.compartments(hull, rig)

        deck = landing_deck(hull)
        gangway = rig_gangway(deck, port) if deck is not None else ()
        hull.make_fast(port, berth, gangway)

        worked = shipyard.figures(rig)
        self.caller.msg(
            f"|w{hull.key}|n is built and lying in {berth.key}: a {rig} of "
            f"{worked['burthen']:.0f} tons burthen, {worked['length']:.1f} m by "
            f"{worked['beam']:.1f}, drawing {worked['draft']:.1f}, {worked['rig']}-rigged. "
            "Her gangway is down."
        )
        port.msg_contents(
            f"{hull.key} lies newly built in {berth.key}, and her gangway comes down.",
            exclude=self.caller,
        )

    def _list(self):
        """Read out the book of hulls."""
        lines = [
            "Hulls that can be built here:",
            f"  |w{'hull':<10}{'length':>8}{'beam':>7}{'draft':>7}{'tons':>7}"
            f"{'hold':>8}{'sleeps':>7}  rig|n",
        ]
        for name in shipyard.NAMES:
            worked = shipyard.figures(name)
            lines.append(
                f"  {name:<10}{worked['length']:>7.1f}m{worked['beam']:>6.1f}m"
                f"{worked['draft']:>6.1f}m{worked['burthen']:>7.0f}"
                f"{worked['hold']:>7.0f}m3{worked['berths']:>7}  |x{worked['rig']}|n"
            )
        lines.append("|xTons are burthen - what she measures, not what she weighs.|n")
        lines.append("|wmaritime build <rig> <name>|n, standing on a quay.")
        self.caller.msg("\n".join(lines))


class CmdMaritimeSummon(Command):
    """
    Bring a laid-up ship of yours round to this dock.

    Usage:
        maritime summon
        maritime summon <name>

    With no argument it lists the ships of yours that are laid up. Otherwise she is
    brought forward into a free berth here, with her gangway down.

    Only ships you may command - yours by ownership, by being her captain, or by having
    taken her and had her made over to you. A ship already on the water is where she is;
    this is for the ones in ordinary.
    """

    key = "maritime summon"
    aliases = ("maritime recall",)
    locks = "cmd:all()"
    help_category = "Maritime"

    def func(self):
        """Find her and bring her forward."""
        wanted = self.args.strip()

        if not wanted:
            self._list()
            return

        port = dock_here(self.caller)
        if port is None:
            send_them_to_the_dock(self.caller)
            return

        hull = named(wanted)
        if hull is None:
            self.caller.msg(f"There is no ship called '{wanted}'.")
            return

        from ..ownership import may_command

        if not may_command(self.caller, hull):
            # Told plainly rather than told she does not exist. Hiding the ship would be
            # security through confusion, and a captain who has just lost a prize to a
            # court deserves to hear that rather than to be told the sea forgot her.
            self.caller.msg(f"{hull.key} does not answer to you.")
            return

        if not ordinary.in_ordinary(hull):
            where = hull.docked_at
            self.caller.msg(
                f"{hull.key} is not laid up - she is lying at {where.key}."
                if where is not None
                else f"{hull.key} is not laid up. She is at sea."
            )
            return

        berth, why = a_berth_for(port, hull.length, hull.beam, hull.draft)
        if berth is None:
            self.caller.msg(f"She cannot lie here: {why}.")
            return

        deck = landing_deck(hull)
        gangway = rig_gangway(deck, port) if deck is not None else ()
        ordinary.bring_forward(hull, port, berth, gangway)

        self.caller.msg(f"|w{hull.key}|n is brought forward into {berth.key}, gangway down.")
        port.msg_contents(
            f"{hull.key} is warped in to {berth.key} and her gangway comes down.",
            exclude=self.caller,
        )

    def _list(self):
        """Say what is laid up and waiting."""
        laid_up = ordinary.fleet_of(self.caller, laid_up=True)
        if not laid_up:
            afloat = ordinary.fleet_of(self.caller, laid_up=False)
            if afloat:
                self.caller.msg(
                    "Nothing of yours is laid up. On the water: "
                    + ", ".join(f"|w{hull.key}|n" for hull in afloat)
                    + "."
                )
            else:
                self.caller.msg("You have no ships.")
            return
        lines = ["Laid up, and waiting:"]
        for hull in laid_up:
            lines.append(f"  |w{hull.key}|n - {hull.length:.1f} m, drawing {hull.draft:.1f}")
        lines.append("|wmaritime summon <name>|n, standing on a quay.")
        self.caller.msg("\n".join(lines))


class CmdMaritimeLayUp(Command):
    """
    Put a ship of yours into ordinary, and free her berth.

    Usage:
        maritime lay up <name>

    She keeps her cargo, her crew and her damage, and gives up her place on the water. Get
    her back with |wmaritime summon|n at any dock.

    She has to be at rest with nobody aboard her, and she has to answer to you.
    """

    key = "maritime lay up"
    aliases = ("maritime layup",)
    locks = "cmd:all()"
    help_category = "Maritime"

    def func(self):
        """Take her out of commission."""
        wanted = self.args.strip()
        if not wanted:
            self.caller.msg("Lay up which ship? |wmaritime lay up <name>|n")
            return

        hull = named(wanted)
        if hull is None:
            self.caller.msg(f"There is no ship called '{wanted}'.")
            return

        from ..ownership import may_command

        if not may_command(self.caller, hull):
            self.caller.msg(f"{hull.key} does not answer to you.")
            return

        where = hull.docked_at
        refused = ordinary.lay_up(hull)
        if refused is not None:
            self.caller.msg(refused)
            return

        self.caller.msg(f"|w{hull.key}|n is laid up. |wmaritime summon|n brings her back.")
        if where is not None:
            where.msg_contents(f"{hull.key} is towed out and laid up.", exclude=self.caller)


class CmdMaritimePlayerBuild(Command):
    """
    Say whether players may build ships.

    Usage:
        maritime player build
        maritime player build on
        maritime player build off

    Off by default, and staff can build either way. A demo world wants players building
    ships; a game with an economy wants them bought, won or inherited, and would be
    surprised by a command that makes a frigate out of nothing.

    While it is off, |wmaritime build|n is hidden from players rather than refused.
    """

    key = "maritime player build"
    aliases = ("maritime player shipyard",)
    locks = "cmd:perm(Admin)"
    help_category = "Maritime"

    def func(self):
        """Read or set the permission."""
        from .interface import _yes_or_no

        said = self.args.strip()
        if not said:
            self._report()
            return

        wanted = _yes_or_no(said)
        if wanted is None:
            self.caller.msg("Say |wmaritime player build on|n or |wmaritime player build off|n.")
            return

        set_players_may_build(wanted)
        if wanted:
            self.caller.msg(
                "Players may now build ships at any dock with |wmaritime build|n. "
                f"There are {len(shipyard.NAMES)} hulls in the book."
            )
        else:
            self.caller.msg(
                "Players may no longer build ships. Anything already built stays built."
            )

    def _report(self):
        """Say which way it is set."""
        if players_may_build():
            self.caller.msg(
                "Players may build ships at a dock. |wmaritime player build off|n stops it."
            )
        else:
            self.caller.msg(
                "Only staff may build ships. |wmaritime player build on|n opens it to " "everybody."
            )


class MaritimeShipyardCmdSet(CmdSet):
    """
    Building, laying up and summoning, for a character rather than a ship.

    Notes:
        Add it to your game's own character cmdset:

            from evennia.contrib.full_systems.maritime.commands.shipyard import (
                MaritimeShipyardCmdSet,
            )
            self.add(MaritimeShipyardCmdSet)

        On a character because a ship is built from dry land, by somebody standing on a
        quay who has not got one yet. Every command in it checks for that quay itself.

        `maritime summon` and `maritime lay up` are open to everybody, because they only
        ever act on ships that already answer to whoever typed them. `maritime build` is
        staff-only until `maritime player build on`.

    """

    key = "maritime_shipyard"
    priority = 1

    def at_cmdset_creation(self):
        """Populate the set."""
        self.add(CmdMaritimeBuild())
        self.add(CmdMaritimeSummon())
        self.add(CmdMaritimeLayUp())
        self.add(CmdMaritimePlayerBuild())


__all__ = (
    "PLAYER_BUILD_KEY",
    "players_may_build",
    "set_players_may_build",
    "dock_here",
    "a_berth_for",
    "named",
    "landing_deck",
    "CmdMaritimeBuild",
    "CmdMaritimeSummon",
    "CmdMaritimeLayUp",
    "CmdMaritimePlayerBuild",
    "MaritimeShipyardCmdSet",
)
