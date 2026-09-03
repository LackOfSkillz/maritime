"""
Things a player can click, which are the same things a player can type.

**A click sends a command.** Not a message of its own, not a protocol only the graphical
client speaks - the literal text somebody with a telnet session would have typed. That is
the whole rule, and it is the same one the chart already follows: a harbour on the sheet is
a symbol you click, and clicking it sends `make for Careenage`.

The rule earns its keep twice. A player who clicks their way around learns the commands by
watching them arrive in their own input, so the graphical client teaches the text one. And
nothing anybody builds for the panel can quietly become the only way to do something,
because if it cannot be typed it cannot be clicked either.

The markup is Evennia's own - `|lc command |lt what it says |le` - and a client that cannot
render a link is shown the plain text instead. So this costs a telnet player nothing, and
the code never has to ask which kind of client is looking.

"""

from django.utils.translation import gettext as _
from evennia.utils.utils import iter_to_str


def link(command, text=None):
    """
    Wrap some text so that clicking it types a command.

    Args:
        command (str): What clicking it sends, exactly as a player would type it.
        text (str, optional): What it says. The command itself if not given, which is
            the right default for an exit: the word on the screen *is* the word you type.

    Returns:
        markup (str): The text, clickable.

    Notes:
        No escaping, deliberately. A command with a `|` in it would break the markup, and
        the answer to that is not to build one - every command this contrib ships is
        letters, digits and spaces, and a game that invents one with a pipe in it has a
        larger problem than this function.

    """
    shown = command if text is None else text
    return f"|lc{command}|lt{shown}|le"


class ClickableExits:
    """
    A room whose exits can be clicked as well as typed.

    Notes:
        Mixed into a room typeclass. The contrib's own rooms have it; a game that wants it
        everywhere adds it to its own base room and changes nothing else.

        **Clicking an exit sends the exit's name**, because that is already how a player
        walks: `gangway` is a command, and so is `north`. There is no `go` in front of it
        and there does not need to be.

        Written out rather than wrapping `super()`, because the parent returns one joined
        sentence and picking the exit names back out of it would mean parsing prose this
        very method just produced.

    """

    def get_display_exits(self, looker, **kwargs):
        """
        Args:
            looker (Object): Whoever is looking.
            **kwargs: Passed through; `exit_order` is honoured as the parent honours it.

        Returns:
            text (str): The exits line, each exit clickable.

        """
        exits = self.filter_visible(self.contents_get(content_type="exit"), looker, **kwargs)
        names = [exit.get_display_name(looker, **kwargs) for exit in exits]

        order = kwargs.get("exit_order")
        if order:
            where = {name: place for place, name in enumerate(order)}
            names.sort()
            names.sort(key=lambda name: where.get(name, len(where)))

        if not names:
            return ""
        # The name is both the label and the command, so a player reading the panel is
        # reading their own next input.
        clickable = iter_to_str([link(name) for name in names], endsep=_(", and"))
        return f"|w{_('Exits')}:|n {clickable}"
