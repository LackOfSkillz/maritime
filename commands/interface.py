"""
The switches whoever runs the game flips at runtime, and the one a player may be lent.

    maritime ui [on|off|hybrid]     which interface the game presents, for everybody
    maritime uncharted [on|off]     draw the sea as it truly is, for development
    maritime player gui [on|off]    whether an individual may choose for themselves
    maritime gui [...]              what one player chose, when the game allows it

**Three of these set the server, not the speaker.** Which interface a game presents is a
decision about what the game *is* - made once, by whoever runs it, and looking the same to
everybody logged in. A per-player switch would turn it into a matter of taste, and would
also make every bug report begin with working out which mode the reporter happened to be in.
So they are locked to Admin and above - which in Evennia's hierarchy is admins, developers
and the superuser and nobody else - they take effect for every session immediately, and they
persist across a reload. A game wanting them tighter still narrows the lock to
`perm(Developer)`; there is one `locks` line on each and nothing else to change.

The fourth is the exception, and it carries the *same* lock until a developer lends it out.
A player who cannot use the command should not be able to see that it exists, so it is
hidden rather than merely refused - see `CmdMyGui.access`. A game whose players include
somebody who cannot use a graphical panel at all has a reason this contrib cannot answer
from here, so the decision is offered to whoever runs the game rather than taken away from
them.

**`MARITIME_ASHORE_PANEL` still says what a game does out of the box.** These are the
runtime overrides, which is what makes it possible to see every behaviour without editing
Python and restarting a server between each.

**They have to work ashore, which is why they are not on the helm.** Every other command in
this contrib lives on a `ShipRoom` so that nobody orders a helm from a tavern. These are the
exception and have to be: somebody who has switched the panel off is by definition somewhere
it is not showing, and a command reachable only from a deck they cannot see is a switch with
no way back.

**A game installs them, because a contrib does not reach into a host game's character
cmdset.** `MaritimeInterfaceCmdSet` is the whole of it, and adding it is one line.
"""

from evennia.commands.cmdset import CmdSet
from evennia.commands.command import Command

from .. import switches
from .handbook import CmdMaritimeHelp
from ..client.context import wants_ashore_panel

#: What each choice does, in the words somebody would use to describe it.
#:
#: Kept beside the commands rather than written into their docstrings, so the same sentence
#: appears when a mode is set and when it is asked about. Two descriptions of one behaviour
#: is how they come to disagree.
MEANS = {
    switches.UI_ON: "always shown, ashore and afloat",
    switches.UI_OFF: "never shown",
    switches.UI_HYBRID: "shown aboard a vessel, hidden ashore",
}

#: What counts as yes and as no, for the switches that only have two positions.
#:
#: More spellings than strictly needed, because the cost of accepting `true` is nothing and
#: the cost of rejecting it is a developer typing the same command three times.
YES = ("on", "yes", "true", "1", "enable", "enabled")
NO = ("off", "no", "false", "0", "disable", "disabled")


def _yes_or_no(said):
    """
    Args:
        said (str): What was typed after the command.

    Returns:
        answer (bool or None): True, False, or None if it was neither.

    """
    said = said.strip().lower()
    if said in YES:
        return True
    if said in NO:
        return False
    return None


def _everybody():
    """
    Returns:
        puppets (list): One entry per character being played right now.

    Notes:
        Deduplicated, because a player watching from two clients puppets one character
        twice and would otherwise be sent everything twice.

        Total. A server with no session handler - a test, a shell - gets an empty list
        rather than an exception, so a switch can be set from anywhere and only the telling
        depends on there being anybody to tell.

    """
    try:
        from evennia.server.sessionhandler import SESSIONS

        sessions = SESSIONS.get_sessions()
    except Exception:
        return []

    seen = {}
    for session in sessions:
        puppet = getattr(session, "puppet", None)
        if puppet is not None:
            seen.setdefault(puppet.id, puppet)
    return list(seen.values())


def _tell_everybody(chart_too=False):
    """
    Push a change to every screen on the server, not only to whoever typed it.

    Args:
        chart_too (bool, optional): Also re-send the chart, for a switch that changes what
            is drawn on it rather than whether it is drawn at all.

    Returns:
        told (int): How many characters were sent something.

    Notes:
        At once rather than at the next tick. Somebody who has just flipped a switch and
        watches nothing happen for a minute concludes it is broken - which is the whole
        reason to have a command instead of a settings file.

        **Everybody, because the change is everybody's.** Refreshing only the caller would
        leave a server in two states at once: the person who set it seeing the new
        interface and everybody else on the old one until they happened to move. That is
        worse than not refreshing at all, because it looks like it worked.

    """
    from ..client.transport import redraw_chart, refresh_for

    told = 0
    for puppet in _everybody():
        refresh_for(puppet)
        told += 1
        if not chart_too:
            continue
        sessions = getattr(puppet, "sessions", None)
        if sessions is None:
            continue
        for session in sessions.all():
            redraw_chart(session)
    return told


class CmdMaritimeUi(Command):
    """
    Say when the maritime panel should be shown.

    Usage:
        maritime ui
        maritime ui on
        maritime ui off
        maritime ui hybrid

    With no argument it reports what the panel is doing now. Otherwise:

        on       always, whether anybody is aboard or ashore
        off      never - the game's own interface has the screen
        hybrid   up while aboard a vessel, gone when anybody steps off

    This sets it for the whole server, for everybody, and survives a reload. It overrides
    the game's own MARITIME_ASHORE_PANEL setting until it is changed again.
    """

    key = "maritime ui"
    aliases = ("maritime interface",)
    locks = "cmd:perm(Admin)"
    help_category = "Maritime"

    def func(self):
        """Read or set the mode."""
        asked = self.args.strip().lower()

        if not asked:
            self._report()
            return

        if asked not in switches.UI_MODES:
            self.caller.msg(
                f"'{asked}' is not one of {', '.join(switches.UI_MODES)}. "
                "Try |wmaritime ui|n on its own to see what they do."
            )
            return

        switches.set_ui_mode(asked)
        self.caller.msg(f"Maritime panel set server-wide: |w{asked}|n - {MEANS[asked]}.")
        told = _tell_everybody()
        if told > 1:
            self.caller.msg(f"|x{told} characters told.|n")

    def _report(self):
        """Say what the panel is doing and what else it could do."""
        held = switches.ui_mode()
        lines = [f"Maritime panel (server-wide): |w{held}|n - {MEANS[held]}."]
        for choice in switches.UI_MODES:
            if choice != held:
                lines.append(f"  |wmaritime ui {choice}|n - {MEANS[choice]}")
        if held == switches.UI_HYBRID and not wants_ashore_panel():
            lines.append(
                "  |xThis game hides the panel ashore by default; "
                "|wmaritime ui on|n|x overrides that.|n"
            )
        if switches.players_may_choose():
            lines.append(
                "  |xPlayers may override this for themselves - |wmaritime player gui|n|x.|n"
            )
        self.caller.msg("\n".join(lines))


class CmdMaritimeUncharted(Command):
    """
    Draw the sea as it truly is, rather than as somebody surveyed it.

    Usage:
        maritime uncharted
        maritime uncharted on
        maritime uncharted off

    A development switch. With it on, every chart reads the world itself: nothing is off
    the paper, no survey error is applied, and a ship carrying no chart at all still gets
    one. That makes the whole world visible for building and testing.

    It sets the server, for everybody, and survives a reload - so it is worth turning off
    again before anybody plays. A game running with this on has no navigation in it: the
    ordinary business of not knowing what is under you is the thing being switched away.

    It opens the paper, not the lookout. Other ships are still seen when they are seen.
    """

    key = "maritime uncharted"
    aliases = ("maritime charts",)
    locks = "cmd:perm(Admin)"
    help_category = "Maritime"

    def func(self):
        """Read or set the switch."""
        asked = self.args.strip()

        if not asked:
            self._report()
            return

        wanted = _yes_or_no(asked)
        if wanted is None:
            self.caller.msg("Say |wmaritime uncharted on|n or |wmaritime uncharted off|n.")
            return

        switches.set_uncharted(wanted)
        if wanted:
            self.caller.msg(
                "|yUncharted water: on.|n Every chart now reads the world itself. "
                "There is no navigation in a game left like this - turn it off before play."
            )
        else:
            self.caller.msg("Uncharted water: |woff|n. Charts read the paper again.")
        told = _tell_everybody(chart_too=True)
        if told > 1:
            self.caller.msg(f"|x{told} characters told.|n")

    def _report(self):
        """Say which way the switch is set."""
        if switches.uncharted():
            self.caller.msg(
                "Uncharted water: |yon|n - charts read the world itself, survey and all "
                "its errors ignored. |wmaritime uncharted off|n to put the paper back."
            )
        else:
            self.caller.msg(
                "Uncharted water: |woff|n - charts read what was surveyed, which is the "
                "game. |wmaritime uncharted on|n to see the whole world while building."
            )


class CmdMaritimePlayerGui(Command):
    """
    Say whether players may choose their own interface.

    Usage:
        maritime player gui
        maritime player gui on
        maritime player gui off

    Off by default: one interface for one game, chosen by whoever runs it. Turning this on
    lends that choice to each account, through |wmaritime gui|n, and their choice then
    overrides the server's for them alone.

    Turning it off again does not erase what anybody chose. It stops those choices being
    read, and turning it back on restores them.
    """

    key = "maritime player gui"
    aliases = ("maritime player ui",)
    locks = "cmd:perm(Admin)"
    help_category = "Maritime"

    def func(self):
        """Read or set the permission."""
        asked = self.args.strip()

        if not asked:
            self._report()
            return

        wanted = _yes_or_no(asked)
        if wanted is None:
            self.caller.msg("Say |wmaritime player gui on|n or |wmaritime player gui off|n.")
            return

        switches.set_players_may_choose(wanted)
        if wanted:
            self.caller.msg(
                "Players may now set their own interface with |wmaritime gui|n. "
                f"Anybody who has not chosen stays on the server's: |w{switches.ui_mode()}|n."
            )
        else:
            self.caller.msg(
                "Players may no longer choose. Everybody is back on the server's "
                f"|w{switches.ui_mode()}|n, and nobody's own choice has been erased."
            )
        told = _tell_everybody()
        if told > 1:
            self.caller.msg(f"|x{told} characters told.|n")

    def _report(self):
        """Say whether the choice is lent out, and how many have taken it."""
        if switches.players_may_choose():
            chosen = sum(1 for puppet in _everybody() if switches.ui_choice(puppet))
            said = f" {chosen} of those playing have chosen one." if chosen else ""
            self.caller.msg("Players may choose their own interface with |wmaritime gui|n." + said)
        else:
            self.caller.msg(
                f"Players may not choose. Everybody is on |w{switches.ui_mode()}|n. "
                "|wmaritime player gui on|n lends them the choice."
            )


class CmdMyGui(Command):
    """
    Choose the interface you see.

    Usage:
        maritime gui
        maritime gui on
        maritime gui off
        maritime gui hybrid
        maritime gui default

    Available to everybody only when this game has said so, and most games have not - one
    interface for one game is the ordinary arrangement.

        on        the maritime panel, ashore and afloat
        off       the game's own interface throughout
        hybrid    the panel aboard a vessel, the game's own ashore
        default   whatever this game does, which is what you had before

    Your choice is kept against your account, so it follows you between characters.
    """

    key = "maritime gui"
    aliases = ("maritime my ui",)

    #: The same lock the other three carry, and for the same reason.
    #:
    #: Widened at runtime by `access` when the game has lent the choice out. Written this
    #: way round on purpose: a command whose lock is `all()` and which merely *refuses*
    #: players is still a command they can see in `help`, ask about and file a bug against,
    #: and "why can I see a command I am not allowed to use" is a fair question with no
    #: good answer. Hidden until it works is the honest state.
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
            Open to everybody once the game has said so, and locked to staff before then.
            Deliberately not a lock function: a contrib cannot add one to a host game's
            `LOCK_FUNCS` without asking that game to edit its settings, and a switch whose
            installation instructions run to two steps is a switch that gets installed
            halfway.

            Only the `cmd` lock is widened. Everything else - `call`, and whatever a game
            adds - goes to the ordinary machinery, because this is a statement about who
            may use the command and not about anything else that could ever be asked.

            **The signature has to match Evennia's exactly, `session` included.** The
            cmdhandler calls `access(caller, "cmd", session=session)` on every command in
            the merged set on every line anybody types, so an override missing that keyword
            does not break this command - it raises out of the parser and breaks the game.

        """
        if access_type == "cmd" and switches.players_may_choose():
            return True
        return super().access(srcobj, access_type, default, session=session)

    def func(self):
        """Read or set this person's own choice."""
        asked = self.args.strip().lower()

        if not switches.players_may_choose():
            self.caller.msg(
                "This game sets the interface for everybody, and it is currently "
                f"|w{switches.ui_mode()}|n - {MEANS[switches.ui_mode()]}."
            )
            return

        if not asked:
            self._report()
            return

        if asked in ("default", "clear", "reset", "none"):
            switches.set_ui_choice(self.caller, None)
            now = switches.ui_mode()
            self.caller.msg(f"Back to whatever this game does: |w{now}|n - {MEANS[now]}.")
            self._refresh()
            return

        if asked not in switches.UI_MODES:
            self.caller.msg(
                f"'{asked}' is not one of {', '.join(switches.UI_MODES)} or |wdefault|n."
            )
            return

        if switches.set_ui_choice(self.caller, asked) is None:
            # Nothing to keep it on. A character nobody is playing has no account, which is
            # not an error anywhere else and should not be reported as one here.
            self.caller.msg("There is no account here to remember that against.")
            return

        self.caller.msg(f"Your maritime panel: |w{asked}|n - {MEANS[asked]}.")
        self._refresh()

    def _report(self):
        """Say what this person is seeing and why."""
        mine = switches.ui_choice(self.caller)
        if mine is None:
            now = switches.ui_mode()
            lines = [f"Your maritime panel: |w{now}|n - {MEANS[now]}, which is the game's own."]
        else:
            lines = [f"Your maritime panel: |w{mine}|n - {MEANS[mine]}, which you chose."]
        for choice in switches.UI_MODES:
            if choice != (mine or switches.ui_mode()):
                lines.append(f"  |wmaritime gui {choice}|n - {MEANS[choice]}")
        if mine is not None:
            lines.append("  |wmaritime gui default|n - back to whatever this game does")
        self.caller.msg("\n".join(lines))

    def _refresh(self):
        """
        Redraw for this person only.

        Notes:
            Only this person, unlike every other command in this module, because this is
            the one switch that is theirs. Telling the server would be the same bug in
            reverse.

        """
        from ..client.transport import refresh_for

        refresh_for(self.caller)


class MaritimeInterfaceCmdSet(CmdSet):
    """
    The maritime cmdset that belongs on a character rather than on a ship.

    Notes:
        Add it to your game's own character cmdset:

            from evennia.contrib.full_systems.maritime.commands.interface import (
                MaritimeInterfaceCmdSet,
            )
            self.add(MaritimeInterfaceCmdSet)

        Everything else this contrib offers lives on a `ShipRoom`, so that orders can only
        be given where they make sense. These are the exception, and have to be: somebody
        who has switched the panel off is somewhere it is not showing, and could not reach
        a command that existed only on a deck.

        All four are locked to Admin and above, so adding the set to a character class puts
        nothing at all in front of your players. `maritime gui` opens to everybody the
        moment a developer runs `maritime player gui on`, and closes again when they run
        `maritime player gui off`.

    """

    key = "maritime_interface"
    priority = 1

    def at_cmdset_creation(self):
        """Populate the set."""
        self.add(CmdMaritimeUi())
        self.add(CmdMaritimeUncharted())
        self.add(CmdMaritimePlayerGui())
        self.add(CmdMyGui())
        # Everybody, always. A player who cannot find the manual is a player who cannot
        # find out that the manual exists, and locking the way in behind the permission
        # that opens the panel would put it furthest from the people who need it most.
        self.add(CmdMaritimeHelp())


__all__ = (
    "MEANS",
    "YES",
    "NO",
    "CmdMaritimeUi",
    "CmdMaritimeUncharted",
    "CmdMaritimePlayerGui",
    "CmdMyGui",
    "CmdMaritimeHelp",
    "MaritimeInterfaceCmdSet",
)
