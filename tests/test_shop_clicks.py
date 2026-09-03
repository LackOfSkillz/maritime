"""
Tests for buying things by clicking, in the example world.

Two rules, and everything here is one of them from some angle.

**A click sends a command a player could have typed.** So the graphical client can never
become the only way to do anything, and somebody clicking their way about is reading their
own next input.

**The ship pays.** `DECISIONS.md` settled that money lives on the hull rather than on the
person, because this contrib cannot know what a player is - some games have no player
currency at all - while every ship must pay for her repairs, her wages and her cargo. The
demo used to charge the character, which taught the opposite of the design it exists to
demonstrate.

Note that `call` strips markup by default, and renders it away even with `noansi=False` -
so what a link *sends* is tested against the `link` helper in `test_clickable`, and what a
player *sees and can do* is tested here.

"""

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaCommandTest

from ..example.aetos_world import people
from ..example.aetos_world.commands import CmdBrowse, CmdBuy
from ..motion import MotionLimits
from ..ports import Berth
from ..position import EAST, WorldPosition
from ..rooms import PortRoom, ShipRoom, ShoreRoom
from ..typeclasses import Vessel
from ..vessel import OPEN

QUAY = WorldPosition(0.0, 0.0)

WARES = (
    ("a coil of ratline", 3, "cordage", "Three-strand, laid hard, and new."),
    ("a tin lantern", 7, "gear", "Punched tin with a horn window."),
)


class ShopTestCase(BaseEvenniaCommandTest):
    """A counter, somebody behind it, and a ship alongside to pay for it."""

    def setUp(self):
        super().setUp()
        self.quay = create.create_object(PortRoom, key="Stone Quay")
        self.quay.maritime_position = QUAY
        self.berth = Berth(
            key="north quay",
            position=QUAY,
            heading=EAST,
            max_length=30.0,
            max_beam=8.0,
            max_draft=4.0,
        )
        self.quay.add_berth(self.berth)

        # The shop is off the quay, because the chandler is never on the pier.
        self.shop = create.create_object(ShoreRoom, key="The Chandlery")
        create.create_object(
            "evennia.objects.objects.DefaultExit",
            key="out",
            location=self.shop,
            destination=self.quay,
        )

        self.hull = create.create_object(Vessel, key="Kestrel")
        self.hull.length, self.hull.beam = 18.0, 5.4
        self.hull.motion_limits = MotionLimits(max_speed=6.0, acceleration=0.5, turn_rate=5.0)
        self.hull.maritime_position = QUAY
        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.deck.vessel = self.hull
        self.deck.exposure = OPEN
        self.hull.make_fast(self.quay, self.berth)

        self.char1.location = self.shop
        self.keeper, _made = people.make(
            key="Bram",
            description="A chandler with a pencil behind one ear.",
            stock=WARES,
            greeting="Bram looks up.",
            home=self.shop,
        )


class TestTheKeeperIsClickable(ShopTestCase):
    """Reading the room and asking what she has are the same gesture."""

    def test_her_name_carries_the_browse_command(self):
        self.assertIn("|lcbrowse Bram|lt", self.keeper.get_display_name(self.char1))

    def test_and_still_reads_as_her_name(self):
        self.assertIn("Bram", self.keeper.get_display_name(self.char1))


class TestWhatTheCounterSays(ShopTestCase):
    """The wares, and whose money is going to buy them."""

    def test_it_lists_them_with_prices(self):
        told = self.call(CmdBrowse(), "")
        self.assertIn("a coil of ratline", told)
        self.assertIn("3 coin", told)

    def test_the_purse_it_names_is_the_ships(self):
        told = self.call(CmdBrowse(), "")
        self.assertIn("Kestrel carries", told)

    def test_and_never_the_players(self):
        told = self.call(CmdBrowse(), "")
        self.assertNotIn("You have", told)


class TestNothingIsBoughtWithoutAsking(ShopTestCase):
    """The one thing here that walking back does not undo."""

    def test_buying_asks_first(self):
        self.assertIn("Purchase", self.call(CmdBuy(), "ratline"))

    def test_and_takes_no_money_yet(self):
        before = people.purse_of(self.hull)
        self.call(CmdBuy(), "ratline")
        self.assertEqual(people.purse_of(self.hull), before)

    def test_nor_hands_anything_over(self):
        self.call(CmdBuy(), "ratline")
        self.assertEqual([thing.key for thing in self.char1.contents], [])

    def test_the_question_offers_both_answers(self):
        told = self.call(CmdBuy(), "ratline")
        self.assertIn("[ Yes ]", told)
        self.assertIn("[ No ]", told)

    def test_it_says_which_ship_is_paying(self):
        self.assertIn("Kestrel carries", self.call(CmdBuy(), "ratline"))


class TestSayingYes(ShopTestCase):
    """The answer, which is also what a player who knows their mind types first."""

    def test_it_hands_the_goods_over(self):
        self.call(CmdBuy(), "/yes ratline")
        self.assertIn("a coil of ratline", [thing.key for thing in self.char1.contents])

    def test_and_the_ship_pays(self):
        before = people.purse_of(self.hull)
        self.call(CmdBuy(), "/yes ratline")
        self.assertEqual(people.purse_of(self.hull), before - 3)

    def test_the_player_is_never_charged(self):
        """
        Not merely 'the ship paid' - nothing may be written to the character at all. What
        a person carries is the host game's business, and a demo that quietly invented a
        pocket for them would be the contrib reaching into a system it does not own.

        """
        self.call(CmdBuy(), "/yes ratline")
        self.assertIsNone(self.char1.db.coin)

    def test_a_player_can_type_it_without_ever_clicking(self):
        """
        The rule from the other end. If the switch were reachable only through the link,
        the graphical client would have a way to buy that a telnet player does not.

        """
        told = self.call(CmdBuy(), "/yes a tin lantern from Bram")
        self.assertIn("You buy", told)


class TestWithNoShipAlongside(BaseEvenniaCommandTest):
    """A counter with nobody's hull at the quay to pay for anything."""

    def setUp(self):
        super().setUp()
        self.shop = create.create_object(ShoreRoom, key="The Chandlery")
        self.char1.location = self.shop
        self.keeper, _made = people.make(
            key="Bram",
            description="A chandler.",
            stock=WARES,
            greeting="Bram looks up.",
            home=self.shop,
        )

    def test_browsing_still_works(self):
        """Looking costs nothing, and being told what is here is how somebody learns."""
        self.assertIn("a coil of ratline", self.call(CmdBrowse(), ""))

    def test_but_says_there_is_nothing_to_pay_with(self):
        self.assertIn("No ship of yours", self.call(CmdBrowse(), ""))

    def test_and_buying_is_refused_kindly(self):
        told = self.call(CmdBuy(), "/yes ratline")
        self.assertIn("Bring one alongside", told)

    def test_with_nothing_handed_over(self):
        self.call(CmdBuy(), "/yes ratline")
        self.assertEqual([thing.key for thing in self.char1.contents], [])


class TestWhatSheSailsWith(ShopTestCase):
    """The demo's purse, which exists so nobody is stopped by pocket money."""

    def test_two_hundred_gold_in_the_smallest_unit(self):
        self.assertEqual(people.STARTING_COIN, 200 * 20 * 12)

    def test_which_is_hundreds_of_purchases(self):
        dearest = max(price for _name, price, _kind, _desc in WARES)
        self.assertGreater(people.STARTING_COIN / dearest, 100)
