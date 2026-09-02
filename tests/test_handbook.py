"""
The handbook, and whether it is still telling the truth.

Documentation rots quietly. A page that names a command which has since been renamed reads
exactly like a page that does not, and the only person who finds out is a player who typed
it and got "command not available" - which teaches them the manual is unreliable, and after
that they stop reading it.

So the parts that *can* be checked mechanically are checked here: that every page it links
to exists, that every command it tells somebody to type is a command, and that the contents
list and the files agree with each other. What the prose actually says is not testable and
is not tested.
"""

import re
from pathlib import Path

from django.test import override_settings
from evennia.utils.test_resources import BaseEvenniaTest, BaseEvenniaTestCase

from ..commands.handbook import HANDBOOK_PATH, CmdMaritimeHelp, handbook_url

#: Where the pages live.
HELP = Path(__file__).resolve().parent.parent / "web" / "static" / "maritime" / "help"

#: Words that begin an indented line in a page but are not something to type.
#:
#: The pages show what to type as indented blocks, which is also how a wrapped example or a
#: continuation line can look. These are the ones that are prose.
NOT_COMMANDS = frozenset()


def pages():
    """
    Returns:
        pages (list): Every markdown file in the handbook.

    """
    return sorted(HELP.glob("*.md"))


def commands_in(text):
    """
    Args:
        text (str): One page's markdown.

    Returns:
        typed (list): The first word or two of every indented example line.

    Notes:
        Indented blocks are how the handbook shows what to type, so every one of them is a
        claim that a command exists. Arguments are stripped: `helm 090` is a claim about
        `helm`, and `load ball` is a claim about `load` - but `cut grapples` and
        `make for` are two-word command keys, so both lengths are offered and the check
        passes if either is real.

    """
    found = []
    fenced = False
    in_block = False
    blank_before = True
    for line in text.split("\n"):
        # **Fenced blocks are code, not orders.** The player pages show what to type as a
        # bare indented block; the developer pages show Python in ``` fences, and reading
        # those as commands makes the check fail on `north = create.create_object(...)`.
        if line.startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            continue

        indented = bool(re.match(r"^ {4}[a-z@]", line))
        if not indented:
            in_block = False
            blank_before = not line.strip()
            continue

        # **An indented block has to open one.** Markdown puts a blank line before a code
        # block, and puts none before the second line of a wrapped list item - which is
        # indented to the same depth and is prose. Without this the contents page reported
        # that nobody could type "file outside", which is true and is not a defect.
        if not (blank_before or in_block):
            continue
        in_block = True
        blank_before = False

        words = line.strip().split()
        if not words:
            continue
        found.append((words[0], " ".join(words[:2]) if len(words) > 1 else words[0]))
    return found


class TestEveryPageIsReachable(BaseEvenniaTestCase):
    """A manual with a dead link in it is a manual somebody stops trusting."""

    def test_there_is_a_handbook(self):
        self.assertTrue(HELP.is_dir(), "the handbook directory is missing")
        self.assertTrue(pages(), "the handbook has no pages")

    def test_every_link_between_pages_resolves(self):
        broken = []
        for page in pages():
            for href in re.findall(r"\]\(([a-z0-9-]+\.md)\)", page.read_text(encoding="utf-8")):
                if not (HELP / href).exists():
                    broken.append(f"{page.name} -> {href}")
        self.assertEqual(broken, [], "these links go nowhere")

    def test_every_page_can_be_got_back_to_the_contents_from(self):
        """
        Every page but the contents itself links home. A reader who followed three links
        and wants to start again should not have to use the browser's back button.

        """
        adrift = [
            page.name
            for page in pages()
            if page.name != "index.md" and "index.md" not in page.read_text(encoding="utf-8")
        ]
        self.assertEqual(adrift, [], "these pages cannot get back to the contents")

    def test_the_command_and_the_files_list_the_same_pages(self):
        """
        Two lists of the same thing, which is one list and one opportunity to disagree. The
        command's list answers a mistyped topic, so a page missing from it is a page the
        player is told does not exist.

        """
        on_disk = {page.stem for page in pages()}
        self.assertEqual(set(CmdMaritimeHelp.TOPICS), on_disk)

    def test_the_page_the_contents_links_to_are_all_of_them(self):
        contents = (HELP / "index.md").read_text(encoding="utf-8")
        linked = set(re.findall(r"\]\(([a-z0-9-]+)\.md\)", contents))
        missing = {page.stem for page in pages()} - linked - {"index"}
        self.assertEqual(missing, set(), "these pages are not listed in the contents")


class TestItOnlyTellsYouToTypeRealCommands(BaseEvenniaTest):
    """
    **The check that matters.** A handbook naming a command that does not exist is worse
    than no handbook: the player types it, is refused, and concludes the manual is wrong
    about everything else too.
    """

    def known_commands(self):
        """
        Returns:
            keys (set): Every command key and alias this contrib ships.

        """
        import importlib
        import pkgutil

        from evennia.commands.command import Command

        from .. import commands as package

        keys = set()
        modules = [package]
        for found in pkgutil.iter_modules(package.__path__):
            modules.append(importlib.import_module(f"{package.__name__}.{found.name}"))
        # The example world ships the shopkeeping verbs, which the handbook documents.
        modules.append(
            importlib.import_module(
                f"{package.__name__.rsplit('.', 1)[0]}.example.aetos_world.commands"
            )
        )

        for module in modules:
            for name in dir(module):
                thing = getattr(module, name)
                if isinstance(thing, type) and issubclass(thing, Command) and thing is not Command:
                    if getattr(thing, "key", None):
                        keys.add(thing.key.lower())
                    for alias in getattr(thing, "aliases", ()) or ():
                        keys.add(str(alias).lower())
        return keys

    def test_every_command_the_handbook_names_exists(self):
        keys = self.known_commands()
        self.assertIn("helm", keys, "the command sweep found nothing, so this proves nothing")

        wrong = []
        for page in pages():
            for one, two in commands_in(page.read_text(encoding="utf-8")):
                if one in keys or two in keys:
                    continue
                if one in NOT_COMMANDS:
                    continue
                wrong.append(f"{page.name}: {two!r}")
        self.assertEqual(
            wrong, [], "the handbook tells people to type these, and they are not real"
        )


class TestPointingSomebodyAtIt(BaseEvenniaTest):
    """`maritime help`, for a client with no buttons on it."""

    def test_it_builds_an_address_from_the_games_own_settings(self):
        with override_settings(WEBSERVER_HOSTNAME="https://example.test"):
            self.assertEqual(handbook_url(), "https://example.test" + HANDBOOK_PATH)

    def test_a_bare_hostname_is_given_a_scheme(self):
        with override_settings(WEBSERVER_HOSTNAME="example.test"):
            self.assertTrue(handbook_url().startswith("https://"))

    def test_a_topic_opens_at_that_page(self):
        with override_settings(WEBSERVER_HOSTNAME="example.test"):
            self.assertTrue(handbook_url("guns").endswith("#guns"))

    def test_a_game_that_has_not_said_where_it_is_gets_no_address(self):
        """
        **Never guessed.** Assuming localhost would hand every player on a live server an
        address that works only for the person running it, and would do it silently.

        """
        with override_settings(WEBSERVER_HOSTNAME=""):
            self.assertIsNone(handbook_url())

    def said_by(self, command, args=""):
        """
        Args:
            command (Command): The command to run.
            args (str, optional): What was typed after it.

        Returns:
            said (str): Everything it told the caller.

        Notes:
            The command is driven directly with a stand-in for the caller, rather than
            through `execute_cmd` and Evennia's session machinery. What is being tested is
            what the command says, and routing that through a live session would be testing
            the session.

        """
        heard = []

        class Caller:
            def msg(self, text="", **kwargs):
                heard.append(str(text))

        order = command()
        order.caller = Caller()
        order.args = args
        order.func()
        return "\n".join(heard)

    def test_it_still_says_where_the_handbook_is(self):
        """A path can be pasted after a known address. Nothing cannot."""
        with override_settings(WEBSERVER_HOSTNAME=""):
            self.assertIn(HANDBOOK_PATH, self.said_by(CmdMaritimeHelp))

    def test_it_gives_a_full_address_when_the_game_has_said_where_it_is(self):
        with override_settings(WEBSERVER_HOSTNAME="example.test"):
            self.assertIn("https://example.test" + HANDBOOK_PATH, self.said_by(CmdMaritimeHelp))

    def test_a_topic_nobody_has_is_answered_with_the_ones_that_exist(self):
        said = self.said_by(CmdMaritimeHelp, "submarines")
        self.assertIn("no handbook page", said)
        self.assertIn("boarding", said)
