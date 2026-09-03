"""
Tests for what the package says it offers.

`__all__` is the contrib's public surface, and it is the one list nothing else checks. A name
in it that does not resolve is an `ImportError` in somebody else's game, thrown from the first
line of an example they copied out of the handbook - which is exactly how this file came to
exist.

"""

import importlib

from evennia.utils.test_resources import BaseEvenniaTestCase

#: The contrib's own dotted path, derived rather than written.
#:
#: `__package__` here is the tests package, so its parent is the contrib. Writing the path
#: out would pin this file to one place in one tree, and the whole point of the check below
#: is that somebody else can import the package from wherever they have put it.
PACKAGE = __package__.rsplit(".", 1)[0]


class TestThePublicSurface(BaseEvenniaTestCase):
    """Every promise in `__all__`, kept."""

    def setUp(self):
        super().setUp()
        self.maritime = importlib.import_module(PACKAGE)

    def test_the_package_declares_one(self):
        self.assertTrue(getattr(self.maritime, "__all__", None))

    def test_every_name_in_it_resolves(self):
        """
        The whole point. `Berth` was exported and `Coin` was not, so a handbook example
        beginning `from ...maritime import Coin` was an ImportError nobody had run.

        """
        missing = [name for name in self.maritime.__all__ if not hasattr(self.maritime, name)]
        self.assertEqual(missing, [], f"named in __all__ but not importable: {missing}")

    def test_nothing_is_promised_twice(self):
        """
        A duplicate is harmless to import and a sign the list is being edited by hand
        without being read, which is how the first gap got in.

        """
        names = list(self.maritime.__all__)
        self.assertEqual(sorted(names), sorted(set(names)))

    def test_it_is_in_order(self):
        """
        Kept sorted so that adding a name is a one-line diff in an obvious place. A list
        that had drifted out of order would make every future addition look like a rewrite.

        """
        names = list(self.maritime.__all__)
        self.assertEqual(names, sorted(names, key=str.lower))


class TestTheTypesTheHandbookTellsYouToImport(BaseEvenniaTestCase):
    """
    Named individually, because a page that cannot be run is worse than no page.

    Notes:
        These are the imports that actually appear in `web/static/maritime/help/`. The test
        above would catch them being dropped from `__all__`; this one says *why* each matters
        and fails with the page's name attached.

    """

    def setUp(self):
        super().setUp()
        self.maritime = importlib.import_module(PACKAGE)

    def test_passengers_and_trade_can_move_money(self):
        self.assertTrue(hasattr(self.maritime, "Coin"))

    def test_a_port_can_be_given_a_market(self):
        self.assertTrue(hasattr(self.maritime, "Market"))

    def test_a_berth_can_be_built(self):
        self.assertTrue(hasattr(self.maritime, "Berth"))

    def test_a_background_ship_can_be_made_and_found(self):
        for name in ("StrategicVessel", "Passage", "Fleet", "fleet", "materialise"):
            self.assertTrue(hasattr(self.maritime, name), name)

    def test_a_coast_can_be_populated(self):
        for name in ("Anchorage", "populate", "encounters", "routes_worth_sailing"):
            self.assertTrue(hasattr(self.maritime, name), name)

    def test_the_two_passages_are_told_apart(self):
        """
        Two modules have a `Passage` and they mean different things: a ship on her way
        somewhere, and one person's booking. Exporting both under one name would hand
        somebody the wrong one silently.

        """
        from ..passengers import Passage as Booking
        from ..strategic import Passage as OnPassage

        self.assertIs(self.maritime.Passage, OnPassage)
        self.assertIs(self.maritime.PassengerPassage, Booking)
        self.assertIsNot(OnPassage, Booking)


class TestTheSubmodulesTheHandbookNames(BaseEvenniaTestCase):
    """`from ...maritime import shipyard` and friends, which the pages use directly."""

    def test_each_one_imports(self):
        for name in (
            "economy",
            "orders",
            "passengers",
            "provisioning",
            "refits",
            "sections",
            "shipping",
            "shipyard",
            "strategic",
            "towing",
            "wrecks",
        ):
            with self.subTest(submodule=name):
                self.assertIsNotNone(importlib.import_module(f"{PACKAGE}.{name}"))
