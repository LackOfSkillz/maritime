"""
The builder's command for making ships and saying who they belong to.

One verb with subcommands rather than a menu, because a menu cannot be scripted and a
world is usually built by a batch file at three in the morning rather than by somebody
clicking through prompts. Everything here is available from `@py` and from a batch
command as well, since it is all ordinary method calls on the hull.

Locked to Builders. Creating ships and reassigning property are not things a player does
by typing - a player buys a ship, and buying is the game's economy calling
`transfer_ownership`.

"""

from evennia.commands.command import Command
from evennia.utils import create
from evennia.utils.search import search_object

from ..motion import MotionLimits
from ..ownership import ADMIRAL, GRANTED, SOLD, fleet_of, rank_of
from ..position import WorldPosition
from ..rooms import ShipRoom
from ..typeclasses import Vessel
from ..vessel import OPEN

#: What a bare `@ship create` gives you: a small, seaworthy, unremarkable hull with one
#: deck. Enough to sail and to be improved on, which is what a builder wants from a
#: default - not a fully rigged ship of the line they then have to argue with.
DEFAULT_HULL = {
    "length": 18.0,
    "beam": 5.4,
    "draft": 2.2,
    "air_draft": 20.0,
}

#: How many hulls one `@ship list` shows before it says how many it held back.
#: A screen, roughly. A world of any size has more ships than a builder wants at once.
PAGE = 30

USAGE = """|wShip building|n

  |w@ship create <name>|n            build a hull with one open deck
  |w@ship list [<name>]|n            every ship, or the ones named like that
  |w@ship info <ship>|n              who owns and commands her
  |w@ship owner <ship> = <who>|n     set her owner (|wnone|n to disown)
  |w@ship captain <ship> = <who>|n   set her captain (|wnone|n to leave her without)
  |w@ship fleet <who>|n              every ship somebody owns, and their rank

Owner is property; captain is command. They are deliberately different people as
often as not - a merchant who owns four ships is aboard at most one of them."""


class CmdShipwright(Command):
    """
    Build ships, and say who they belong to.

    Usage:
      @ship create <name>
      @ship list [<name>]
      @ship info <ship>
      @ship owner <ship> = <character>
      @ship captain <ship> = <character>
      @ship fleet <character>

    Owner is property and captain is command, and they are separate on purpose: a
    merchant who owns four ships is aboard at most one of them, and a captain who
    owns nothing still gives the orders on the deck he stands on.

    Hold more than one ship and you are an admiral. That is derived from what
    answers to you rather than granted, so it arrives with the second ship and
    leaves with the loss of one.
    """

    key = "@ship"
    aliases = ("@ships", "@shipwright")
    locks = "cmd:perm(Builder)"
    help_category = "Building"

    def func(self):
        """Dispatch on the subcommand. No deck required - this is a builder's tool."""
        args = (self.args or "").strip()
        if not args:
            self.caller.msg(USAGE)
            return

        verb, _, rest = args.partition(" ")
        handler = {
            "create": self.do_create,
            "list": self.do_list,
            "info": self.do_info,
            "owner": self.do_owner,
            "captain": self.do_captain,
            "fleet": self.do_fleet,
        }.get(verb.lower())

        if handler is None:
            self.caller.msg(USAGE)
            return
        handler(rest.strip())

    # --- building -----------------------------------------------------------

    def do_create(self, name):
        """
        Args:
            name (str): What to call her.

        """
        if not name:
            self.caller.msg("Usage: @ship create <name>")
            return

        hull = create.create_object(Vessel, key=name)
        hull.length = DEFAULT_HULL["length"]
        hull.beam = DEFAULT_HULL["beam"]
        hull.light_draft = DEFAULT_HULL["draft"]
        hull.air_draft = DEFAULT_HULL["air_draft"]
        hull.motion_limits = MotionLimits(max_speed=5.0, acceleration=0.4, turn_rate=4.0)
        hull.maritime_position = WorldPosition(0.0, 0.0)

        deck = create.create_object(ShipRoom, key=f"{name} Deck")
        deck.vessel = hull
        deck.exposure = OPEN
        deck.height_of_eye = 2.0
        deck.db.desc = "A bare deck. Somebody will have to make something of her."

        self.caller.msg(
            f"Built |w{hull.key}|n (#{hull.id}) with one deck (#{deck.id}).\n"
            f"She belongs to nobody, which means anybody aboard can sail her. "
            f"Set an owner with |w@ship owner {hull.key} = <character>|n."
        )

    # --- reporting ----------------------------------------------------------

    def do_list(self, match):
        """
        Args:
            match (str): Show only hulls whose name contains this, if given.

        Notes:
            Bounded, and it has to be. A world of any size has more ships than a
            screen has lines, and a builder looking for one of them wants the one
            rather than all of them. What was left out is said out loud - a list
            that silently stopped short would be worse than no list at all.

        """
        hulls = sorted(Vessel.objects.all_family(), key=lambda hull: hull.key.lower())
        if match:
            hulls = [hull for hull in hulls if match.lower() in hull.key.lower()]

        if not hulls:
            if match:
                self.caller.msg(f"No ship's name contains {match!r}.")
                return
            self.caller.msg("There are no ships. Build one with |w@ship create <name>|n.")
            return

        held = len(hulls) - PAGE
        narrowed = f" matching {match!r}" if match else ""
        lines = [f"|w{len(hulls)} ship(s){narrowed}|n", ""]
        for hull in hulls[:PAGE]:
            lines.append(
                f"  {hull.key:<24} (#{hull.id:<5}) "
                f"owner {self.who(hull.owner):<18} captain {self.who(hull.captain)}"
            )
        if held > 0:
            lines.append("")
            lines.append(
                f"  |x...and {held} more. Narrow it with|n |w@ship list <part of a name>|n|x.|n"
            )
        self.caller.msg("\n".join(lines))

    def do_info(self, name):
        """
        Args:
            name (str): Which ship.

        """
        hull = self.find_ship(name)
        if hull is None:
            return

        owner = hull.owner
        lines = [f"|w{hull.key}|n (#{hull.id})", ""]
        lines.append(f"  Owner     {self.who(owner)}")
        if owner is not None:
            lines.append(f"            {rank_of(owner)}, {len(fleet_of(owner))} ship(s)")
        lines.append(f"  Captain   {self.who(hull.captain)}")
        lines.append(
            f"  Hull      {hull.length:.1f} x {hull.beam:.1f} m, " f"drawing {hull.draft:.2f} m"
        )
        lines.append(f"  Decks     {', '.join(room.key for room in hull.ship_rooms) or 'none'}")
        if hull.owner is None and hull.captain is None:
            lines.append("")
            lines.append("  She answers to anybody aboard her.")
        self.caller.msg("\n".join(lines))

    def do_fleet(self, name):
        """
        Args:
            name (str): Whose fleet.

        """
        who = self.find_character(name)
        if who is None:
            return

        fleet = fleet_of(who)
        rank = rank_of(who)
        if not fleet:
            commanded = who.db.maritime_command
            if commanded and commanded.pk:
                self.caller.msg(
                    f"|w{who.key}|n owns nothing and commands the {commanded.key}. "
                    f"That still makes them a {rank}."
                )
                return
            self.caller.msg(f"|w{who.key}|n owns no ships.")
            return

        lines = [f"|w{who.key}|n - {rank}, {len(fleet)} ship(s)", ""]
        for hull in fleet:
            lines.append(f"  {hull.key:<24} captain {self.who(hull.captain)}")
        if rank == ADMIRAL:
            lines.append("")
            lines.append("  What an admiral may do with a fleet is the game's to decide.")
        self.caller.msg("\n".join(lines))

    # --- assignment ---------------------------------------------------------

    def do_owner(self, rest):
        """
        Args:
            rest (str): `<ship> = <character>`.

        """
        hull, who, cleared = self.parse_assignment(rest, "owner")
        if hull is None:
            return

        before = rank_of(hull.owner) if hull.owner else None
        hull.transfer_ownership(who, reason=GRANTED if who else SOLD)

        if cleared:
            self.caller.msg(f"{hull.key} now belongs to nobody.")
            return

        note = ""
        if rank_of(who) == ADMIRAL and before != ADMIRAL:
            note = f" That is {len(fleet_of(who))} ships - {who.key} is an admiral."
        self.caller.msg(f"{hull.key} now belongs to {who.key}.{note}")

    def do_captain(self, rest):
        """
        Args:
            rest (str): `<ship> = <character>`.

        """
        hull, who, cleared = self.parse_assignment(rest, "captain")
        if hull is None:
            return

        hull.pass_command(who)
        if cleared:
            owner = hull.owner
            after = (
                f" She answers to {owner.key} until somebody is appointed."
                if owner
                else " She answers to anybody aboard her."
            )
            self.caller.msg(f"{hull.key} has no captain.{after}")
            return
        self.caller.msg(f"{who.key} has command of {hull.key}.")

    # --- helpers ------------------------------------------------------------

    def parse_assignment(self, rest, role):
        """
        Read `<ship> = <character>`.

        Args:
            rest (str): What was typed after the subcommand.
            role (str): What is being assigned, for the usage line.

        Returns:
            parsed (tuple): `(vessel, character, cleared)`. The vessel is None if
                anything could not be resolved, and the reason has been reported.

        """
        ship_name, sep, who_name = rest.partition("=")
        if not sep:
            self.caller.msg(f"Usage: @ship {role} <ship> = <character>")
            return None, None, False

        hull = self.find_ship(ship_name.strip())
        if hull is None:
            return None, None, False

        who_name = who_name.strip()
        if who_name.lower() in ("none", "nobody", ""):
            return hull, None, True

        who = self.find_character(who_name)
        if who is None:
            return None, None, False
        return hull, who, False

    def find_ship(self, name):
        """
        Args:
            name (str): What was typed.

        Returns:
            vessel (Vessel or None): The hull, reporting the failure if not.

        """
        if not name:
            self.caller.msg("Which ship?")
            return None
        found = [obj for obj in search_object(name) if isinstance(obj, Vessel)]
        if not found:
            self.caller.msg(f"No ship called {name!r}.")
            return None
        return found[0]

    def find_character(self, name):
        """
        Args:
            name (str): What was typed.

        Returns:
            character (Object or None): The character, reporting the failure if not.

        Notes:
            Searches everything rather than only characters, because a game may
            well want a ship owned by a company, a crown or a temple - and none of
            those is a character.

        """
        if not name:
            self.caller.msg("Which character?")
            return None
        found = search_object(name)
        if not found:
            self.caller.msg(f"Nobody and nothing called {name!r}.")
            return None
        return found[0]

    def who(self, character):
        """
        Args:
            character (Object or None): Somebody, or nobody.

        Returns:
            name (str): Their name, or a word for the absence of one.

        """
        return character.key if character is not None else "|xnobody|n"
