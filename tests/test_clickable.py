"""
Tests for the things a player can click.

The rule under all of them: **a click sends a command a player could have typed.** Every
test here is really a test of that, from one angle or another.

"""

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest
from evennia.utils.ansi import strip_ansi

from ..clickable import ClickableExits, link
from ..rooms import ShipRoom, ShoreRoom
from ..vessel import OPEN
from .base import EmptySeaMixin


class TestTheMarkup(BaseEvenniaTest):
    """The wrapper, with no room attached."""

    def test_it_says_what_it_sends(self):
        self.assertEqual(link("north"), "|lcnorth|ltnorth|le")

    def test_and_can_say_something_else(self):
        self.assertEqual(
            link("buy rope from Bram", "a coil of rope"),
            "|lcbuy rope from Bram|lta coil of rope|le",
        )

    def test_the_command_is_the_default_label(self):
        """
        Right for an exit and worth stating: the word on the screen *is* the word you
        type, so a player clicking their way about is reading their own next input.

        """
        self.assertIn("|ltgangway|le", link("gangway"))


class ClickableRoomTestCase(EmptySeaMixin, BaseEvenniaTest):
    """A deck with somewhere to go from it."""

    def setUp(self):
        super().setUp()
        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.deck.exposure = OPEN
        self.quay = create.create_object(ShoreRoom, key="Stone Quay")
        create.create_object(
            "evennia.objects.objects.DefaultExit",
            key="gangway",
            location=self.deck,
            destination=self.quay,
        )
        create.create_object(
            "evennia.objects.objects.DefaultExit",
            key="down",
            location=self.deck,
            destination=self.quay,
        )


class TestEveryExitIsClickable(ClickableRoomTestCase):
    """What a room's exits line looks like."""

    def shown(self):
        """
        Returns:
            text (str): The exits line as the room renders it.

        """
        return self.deck.get_display_exits(self.char1)

    def test_the_line_is_there_at_all(self):
        self.assertIn("Exits", strip_ansi(self.shown()))

    def test_each_exit_carries_its_own_command(self):
        shown = self.shown()
        self.assertIn("|lcgangway|ltgangway|le", shown)
        self.assertIn("|lcdown|ltdown|le", shown)

    def test_clicking_one_types_the_exit_name(self):
        """
        Not `go gangway`. Walking through an exit *is* typing its name in Evennia, so a
        click that sent anything else would be inventing a second way to do one thing.

        """
        self.assertNotIn("go gangway", self.shown())

    def test_a_room_with_no_exits_says_nothing(self):
        sealed = create.create_object(ShipRoom, key="The Hold")
        self.assertEqual(sealed.get_display_exits(self.char1), "")

    def test_it_still_reads_as_a_sentence(self):
        """
        A telnet player sees the labels with the markup stripped, so the line has to be
        prose before it is anything else.

        """
        plain = strip_ansi(self.shown())
        self.assertIn("gangway", plain)
        self.assertIn("down", plain)

    def test_the_ordering_the_parent_offers_is_honoured(self):
        first = self.deck.get_display_exits(self.char1, exit_order=("gangway", "down"))
        second = self.deck.get_display_exits(self.char1, exit_order=("down", "gangway"))
        self.assertLess(first.index("gangway"), first.index("down"))
        self.assertLess(second.index("down"), second.index("gangway"))


class TestWhichRoomsHaveIt(BaseEvenniaTest):
    """Every room this contrib ships, and a seam for the ones it does not."""

    def test_a_ships_compartment(self):
        self.assertTrue(issubclass(ShipRoom, ClickableExits))

    def test_and_the_shore(self):
        self.assertTrue(issubclass(ShoreRoom, ClickableExits))

    def test_it_is_a_mixin_a_game_can_take(self):
        """
        A game that wants clickable exits on its *own* rooms adds one class to its base
        room and changes nothing else. It is not this contrib's business to reach into a
        typeclass it does not own.

        """
        from evennia.objects.objects import DefaultRoom

        class TheirRoom(ClickableExits, DefaultRoom):
            pass

        self.assertTrue(hasattr(TheirRoom, "get_display_exits"))
