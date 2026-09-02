"""
`maritime help`: a way into the handbook from a client that has no buttons.

The handbook itself is a set of markdown files served as static content, so it is readable
three ways from one source - in a browser, in the repository's file browser, and in a text
editor. This is the fourth door: somebody playing over telnet, or in a client with the
graphical panel switched off, who needs to know where the manual is.

**It prints a link rather than the manual.** A fifteen-page handbook paged into a scrolling
terminal is not a manual, it is a wall, and the reader loses their place the moment anything
else happens on the deck. A link opens something they can read alongside the game and keep
open while they try what it told them.
"""

from django.conf import settings
from evennia.commands.cmdset import CmdSet
from evennia.commands.command import Command

#: Where the handbook lives, under whatever the game serves its static files from.
HANDBOOK_PATH = "/static/maritime/help.html"

#: What to say when there is no way to work out the site's address.
#:
#: A path rather than nothing. A player told "/static/maritime/help.html" can paste it after
#: their own game's address and get there; a player told nothing cannot.
NO_HOST = (
    "The handbook is at |w{path}|n on this game's web server. "
    "(This game has not set |wWEBSERVER_HOSTNAME|n, so the full address cannot be given "
    "here.)"
)


def handbook_url(topic=""):
    """
    The address of the handbook, as far as the game can work it out.

    Args:
        topic (str, optional): A page to open at, without its extension.

    Returns:
        url (str or None): A full address, or None if the game has not said where it is.

    Notes:
        **Built from the game's own settings, never guessed.** A contrib that assumed
        `localhost` would hand every player on a live server an address that works only for
        the person running it - and would do so silently, which is the worst kind of wrong
        answer.

        `WEBSERVER_HOSTNAME` is not a standard Evennia setting, deliberately: there is no
        setting that reliably holds the address a *player's browser* should use, because the
        server does not necessarily know how it is reached. So a game that wants full links
        says so, and one that does not gets the path and an honest explanation.

    """
    host = getattr(settings, "WEBSERVER_HOSTNAME", "") or ""
    host = host.strip().rstrip("/")
    if not host:
        return None
    if "://" not in host:
        host = "https://" + host
    return host + HANDBOOK_PATH + (("#" + topic) if topic else "")


class CmdMaritimeHelp(Command):
    """
    Open the Sailor's Handbook.

    Usage:
        maritime help
        maritime help <topic>

    Two halves. For anybody aboard: under-way, sailing, oars, navigation, soundings,
    harbours, lookout, guns, ramming, boarding, crew, cargo, ashore, interface.

    For anybody building with it: for-developers, integrating, adopting-a-part,
    your-own-world, your-own-ships, rooms-and-typeclasses, extending - and the two
    references, commands and settings.

    With a topic it opens at that page. In a browser the handbook is also on the panel:
    the |w?|n in its top right corner.
    """

    key = "maritime help"
    aliases = ("handbook", "maritime handbook")
    locks = "cmd:all()"
    help_category = "Maritime"

    #: The pages, in the order the handbook presents them, so that a mistyped topic
    #: can be answered with the list rather than a shrug - and answered in an order
    #: that teaches rather than one that files.
    #:
    #: Kept here rather than read off disk: a command that stats a directory to answer
    #: a typo is a command that fails differently depending on the file system. A test
    #: holds this list and the files to the same set.
    TOPICS = (
        "index",
        "under-way",
        "sailing",
        "oars",
        "navigation",
        "soundings",
        "harbours",
        "lookout",
        "guns",
        "ramming",
        "boarding",
        "crew",
        "cargo",
        "ashore",
        "interface",
        "for-developers",
        "integrating",
        "adopting-a-part",
        "your-own-world",
        "your-own-ships",
        "rooms-and-typeclasses",
        "extending",
        "commands",
        "settings",
    )

    def func(self):
        """Point them at it."""
        topic = (self.args or "").strip().lower().replace(" ", "-")
        if topic and topic not in self.TOPICS:
            self.caller.msg(
                f"There is no handbook page called '{topic}'. There is: "
                + ", ".join(f"|w{name}|n" for name in self.TOPICS if name != "index")
                + "."
            )
            return

        url = handbook_url(topic if topic != "index" else "")
        if url is None:
            self.caller.msg(NO_HOST.format(path=HANDBOOK_PATH))
            return

        # `|lu` is Evennia's markup for a URL link: clients that can open one make it
        # clickable, and clients that cannot show the address as text. Either way the
        # player ends up with something they can use.
        self.caller.msg(
            f"The Sailor's Handbook: |lu{url}|lt|w{url}|n|le\n"
            "It opens in your browser and can be left open while you sail."
        )


class MaritimeHandbookCmdSet(CmdSet):
    """
    One command: the way into the handbook.

    Notes:
        **Its own set, and not in with the switches.** The interface set holds the runtime
        controls and is locked to administrators, so that a game can install it and put
        nothing in front of its players. `maritime help` is open to everybody on purpose,
        and putting it in there quietly broke that promise - three tests that guard it
        caught the contradiction.

        Add this wherever the handbook should be reachable. On a character class is the
        usual answer, because somebody who does not know the game is exactly the person who
        cannot be relied upon to be standing on a deck when they need the manual. The helm
        set carries it as well, so a ship has it with no extra step.

    """

    key = "maritime_handbook"
    priority = 1

    def at_cmdset_creation(self):
        """Populate the set."""
        self.add(CmdMaritimeHelp())


__all__ = ("HANDBOOK_PATH", "handbook_url", "CmdMaritimeHelp", "MaritimeHandbookCmdSet")
