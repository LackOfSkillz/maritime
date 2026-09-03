"""
Tests for a ship's purse.

Two claims worth testing hardest. **Money is one integer**, and the denominations are a
rendering of it - because money kept as three numbers can be made to vanish by carrying
wrong, and money kept as a float stops adding up after enough voyages. And **the purse is on
the hull**, which is the ruling this whole thing exists to keep.

"""

from django.test import override_settings
from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest

from ..events import bus
from ..ledger import Coin, MoneyMoved, coinage
from ..typeclasses import Vessel


class TestCountingIt(BaseEvenniaTest):
    """The value type, with no ship attached."""

    def test_nothing_is_nothing(self):
        self.assertFalse(Coin())

    def test_a_shilling_is_twelve_pence(self):
        self.assertEqual(Coin.of(silver=1).smallest, 12)

    def test_and_a_pound_is_two_hundred_and_forty(self):
        self.assertEqual(Coin.of(gold=1).smallest, 240)

    def test_they_add_up(self):
        self.assertEqual(Coin.of(gold=1) + Coin.of(silver=1), Coin.of(gold=1, silver=1))

    def test_and_subtract(self):
        self.assertEqual(Coin.of(gold=1) - Coin.of(silver=1), Coin.of(silver=19))

    def test_they_compare(self):
        self.assertGreater(Coin.of(gold=1), Coin.of(silver=19))

    def test_a_bare_number_is_the_smallest_coin(self):
        """What a game counting in one unit means by it, and refusing it would make every
        call site wrap a number for nothing."""
        self.assertEqual(Coin.taken_from(30), Coin(smallest=30))

    def test_anything_else_is_refused(self):
        with self.assertRaises(TypeError):
            Coin.taken_from(1.5)

    def test_an_unknown_coin_is_refused(self):
        with self.assertRaises(ValueError):
            Coin.of(doubloons=3)


class TestSayingIt(BaseEvenniaTest):
    """How an amount reads when somebody is told it."""

    def test_it_splits_largest_first(self):
        split = Coin.of(gold=2, silver=3, copper=4).split()
        self.assertEqual(split["gold"], 2)
        self.assertEqual(split["silver"], 3)
        self.assertEqual(split["copper"], 4)

    def test_a_heap_of_pence_carries_properly(self):
        """The reason it is one integer: 250 pence is a pound, a shilling and ten."""
        split = Coin(smallest=250).split()
        self.assertEqual((split["gold"], split["silver"], split["copper"]), (1, 0, 10))

    def test_empty_denominations_are_not_said(self):
        self.assertEqual(str(Coin.of(gold=2)), "2 gold")

    def test_but_nothing_still_says_something(self):
        self.assertEqual(str(Coin()), "0 copper")

    def test_it_reads_as_a_person_would_count_it(self):
        self.assertEqual(str(Coin.of(gold=1, copper=5)), "1 gold, 5 copper")


class TestAGamesOwnCoins(BaseEvenniaTest):
    """A game that does not want pounds should not be given them."""

    @override_settings(MARITIME_COINAGE={"names": ("bit", "crown"), "ratios": (10,)})
    def test_it_can_name_its_own(self):
        names, ratios = coinage()
        self.assertEqual(names, ("bit", "crown"))
        self.assertEqual(Coin.of(crown=1).smallest, 10)

    @override_settings(MARITIME_COINAGE={"names": ("bit", "crown"), "ratios": (10,)})
    def test_and_they_are_counted_out_in_them(self):
        self.assertEqual(str(Coin(smallest=23)), "2 crown, 3 bit")

    @override_settings(MARITIME_COINAGE={"names": ("a", "b", "c"), "ratios": (2,)})
    def test_a_coinage_that_does_not_add_up_is_refused(self):
        """
        One ratio fewer than there are names, always. A coinage missing one is a coinage
        that would silently value the top coin at nothing.

        """
        with self.assertRaises(ValueError):
            coinage()


class PurseTestCase(BaseEvenniaTest):
    """A hull with a purse."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Kestrel")


class TestWhoseMoneyItIs(PurseTestCase):
    """The ruling this exists to keep."""

    def test_a_new_hull_carries_nothing(self):
        self.assertFalse(self.hull.purse)

    def test_the_purse_is_on_the_hull(self):
        self.hull.credit(Coin.of(gold=1), "her owner's advance")
        self.assertEqual(self.hull.purse, Coin.of(gold=1))

    def test_and_nothing_is_written_to_anybody(self):
        """
        What a person carries is the host game's business. A contrib that quietly gave a
        character a pocket would be reaching into a system it does not own.

        """
        self.hull.credit(Coin.of(gold=1), "her owner's advance")
        self.assertIsNone(self.char1.db.purse)
        self.assertIsNone(self.char1.db.coin)


class TestMoneyMoving(PurseTestCase):
    """Paying in, paying out, and refusing to."""

    def setUp(self):
        super().setUp()
        self.hull.credit(Coin.of(gold=1), "her owner's advance")

    def test_she_can_pay_for_something(self):
        self.assertTrue(self.hull.debit(Coin.of(silver=5), "cordage"))
        self.assertEqual(self.hull.purse, Coin.of(silver=15))

    def test_she_cannot_pay_for_what_she_has_not_got(self):
        self.assertFalse(self.hull.debit(Coin.of(gold=5), "a second ship"))

    def test_and_nothing_moves_when_she_cannot(self):
        before = self.hull.purse
        self.hull.debit(Coin.of(gold=5), "a second ship")
        self.assertEqual(self.hull.purse, before)

    def test_a_purse_never_goes_negative(self):
        """
        Debt is a relationship between people, and this contrib has no people in it. A game
        that lends money to a captain is modelling something it understands, and this is
        not it.

        """
        self.hull.debit(Coin.of(gold=99), "an impossible thing")
        self.assertGreaterEqual(self.hull.purse.smallest, 0)

    def test_affording_is_asked_without_spending(self):
        self.assertTrue(self.hull.can_afford(Coin.of(silver=5)))
        self.assertFalse(self.hull.can_afford(Coin.of(gold=2)))
        self.assertEqual(self.hull.purse, Coin.of(gold=1))


class TestWhatIsAnnounced(PurseTestCase):
    """The reason is what separates a ledger from a number."""

    def setUp(self):
        super().setUp()
        self.heard = []
        bus().subscribe(MoneyMoved, self.heard.append)

    def test_paying_in_is_announced(self):
        self.hull.credit(Coin.of(gold=1), "a prize paid out")
        self.assertEqual(len(self.heard), 1)

    def test_and_says_what_for(self):
        self.hull.credit(Coin.of(gold=1), "a prize paid out")
        self.assertEqual(self.heard[0].reason, "a prize paid out")

    def test_spending_is_announced_as_a_loss(self):
        self.hull.credit(Coin.of(gold=1), "advance")
        self.hull.debit(Coin.of(silver=5), "cordage")
        self.assertLess(self.heard[-1].amount.smallest, 0)

    def test_it_carries_the_balance(self):
        """
        A listener that had to ask afterwards would be asking after the next change had
        already happened.

        """
        self.hull.credit(Coin.of(gold=1), "advance")
        self.assertEqual(self.heard[-1].purse, Coin.of(gold=1))

    def test_a_refused_payment_announces_nothing(self):
        self.hull.debit(Coin.of(gold=9), "beyond her")
        self.assertEqual(self.heard, [])
