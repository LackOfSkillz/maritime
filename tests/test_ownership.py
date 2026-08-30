"""
Tests for who owns her, who commands her, and who answers to whom.

"""

from django.test import override_settings

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaCommandTest, BaseEvenniaTest

from ..commands import CmdHelm, CmdShipwright
from ..events import bus
from ..motion import MotionLimits
from ..ownership import (
    ADMIRAL,
    CAPTAIN,
    CAPTURED,
    GRANTED,
    SOLD,
    UNRANKED,
    CommandPassed,
    OwnershipTransferred,
    fleet_of,
    is_admiral,
    may_command,
    rank_of,
)
from ..position import WorldPosition
from ..rooms import ShipRoom
from ..typeclasses import Vessel
from ..vessel import OPEN
from .base import EmptySeaMixin


def everybody_may(character, vessel):
    """A policy that permits anything, for the test that proves the seam is real."""
    return True


def nobody_may(character, vessel):
    """A policy that permits nothing, likewise."""
    return False


class OwnershipTestCase(EmptySeaMixin, BaseEvenniaTest):
    """A hull, and people to give her to."""

    def setUp(self):
        super().setUp()
        self.hull = self.a_ship("Kestrel")
        self.merchant = self.a_person("A merchant")
        self.mate = self.a_person("The mate")

    def a_ship(self, key):
        hull = create.create_object(Vessel, key=key)
        hull.length, hull.beam = 18.0, 5.4
        hull.motion_limits = MotionLimits(max_speed=6.0, acceleration=0.5, turn_rate=5.0)
        hull.maritime_position = WorldPosition(0.0, 0.0)
        deck = create.create_object(ShipRoom, key=f"{key} Deck")
        deck.vessel = hull
        deck.exposure = OPEN
        return hull

    def a_person(self, key):
        return create.create_object("evennia.objects.objects.DefaultCharacter", key=key)


class TestOwnership(OwnershipTestCase):
    """Property."""

    def test_she_starts_belonging_to_nobody(self):
        self.assertIsNone(self.hull.owner)

    def test_she_can_be_given_to_somebody(self):
        self.hull.owner = self.merchant
        self.assertEqual(self.hull.owner, self.merchant)

    def test_and_they_know_they_have_her(self):
        """Both sides, maintained by the setter - as a compartment names its hull."""
        self.hull.owner = self.merchant
        self.assertEqual(fleet_of(self.merchant), (self.hull,))

    def test_giving_her_away_takes_her_off_the_old_fleet(self):
        self.hull.owner = self.merchant
        self.hull.owner = self.mate
        self.assertEqual(fleet_of(self.merchant), ())
        self.assertEqual(fleet_of(self.mate), (self.hull,))

    def test_she_can_be_disowned(self):
        self.hull.owner = self.merchant
        self.hull.owner = None
        self.assertIsNone(self.hull.owner)
        self.assertEqual(fleet_of(self.merchant), ())

    def test_giving_her_to_the_same_person_changes_nothing(self):
        self.hull.owner = self.merchant
        self.assertFalse(self.hull.transfer_ownership(self.merchant))

    def test_a_fleet_that_already_names_her_is_not_doubled(self):
        """
        Two sides of a link drift. A game that set `db.owner` directly, or a
        half-finished transfer, leaves her on a roster she is not on the books
        for - and the next transfer should tidy that rather than list her twice.

        """
        self.merchant.db.maritime_fleet = [self.hull]
        self.hull.transfer_ownership(self.merchant)
        self.assertEqual(fleet_of(self.merchant), (self.hull,))

    def test_a_deleted_owner_is_nobody(self):
        self.hull.owner = self.merchant
        self.merchant.delete()
        self.assertIsNone(self.hull.owner)

    def test_a_reason_nobody_records_is_refused(self):
        with self.assertRaises(ValueError):
            self.hull.transfer_ownership(self.merchant, reason="borrowed")


class TestTheTransferIsAnnounced(OwnershipTestCase):
    """A game hooks the event; no money changes hands here."""

    def setUp(self):
        super().setUp()
        self.heard = []
        self.unsubscribe = bus().subscribe(OwnershipTransferred, self.heard.append)
        self.addCleanup(self.unsubscribe)

    def test_a_transfer_is_published(self):
        self.hull.transfer_ownership(self.merchant, reason=SOLD)
        self.assertEqual(len(self.heard), 1)

    def test_it_carries_both_ends(self):
        """A listener almost always needs the owner who is no longer there."""
        self.hull.transfer_ownership(self.merchant, reason=SOLD)
        self.hull.transfer_ownership(self.mate, reason=CAPTURED)
        self.assertEqual(self.heard[-1].former_owner, self.merchant)
        self.assertEqual(self.heard[-1].owner, self.mate)

    def test_the_default_reason_is_a_grant(self):
        self.hull.transfer_ownership(self.merchant)
        self.assertEqual(self.heard[-1].reason, GRANTED)

    def test_it_says_why(self):
        """Sold and taken by force are the same transfer and different stories."""
        self.hull.transfer_ownership(self.merchant, reason=CAPTURED)
        self.assertEqual(self.heard[-1].reason, CAPTURED)

    def test_a_transfer_that_did_not_happen_is_not_announced(self):
        self.hull.transfer_ownership(self.merchant)
        self.hull.transfer_ownership(self.merchant)
        self.assertEqual(len(self.heard), 1)

    def test_it_is_stamped_with_the_time(self):
        self.hull.transfer_ownership(self.merchant)
        self.assertIsNotNone(self.heard[-1].game_time)


class TestCommand(OwnershipTestCase):
    """Command, which is not property."""

    def test_she_starts_without_a_captain(self):
        self.assertIsNone(self.hull.captain)

    def test_somebody_can_be_given_command(self):
        self.hull.captain = self.mate
        self.assertEqual(self.hull.captain, self.mate)

    def test_a_captain_can_pass_it_on(self):
        """What makes captain a role rather than a label."""
        second = self.a_person("The bosun")
        self.hull.captain = self.mate
        self.assertTrue(self.hull.pass_command(second))
        self.assertEqual(self.hull.captain, second)

    def test_and_can_relinquish_it(self):
        self.hull.captain = self.mate
        self.hull.pass_command(None)
        self.assertIsNone(self.hull.captain)
        self.assertIsNone(self.mate.db.maritime_command)

    def test_a_captain_commands_one_ship(self):
        """A man cannot be on two decks."""
        second = self.a_ship("Petrel")
        self.hull.captain = self.mate
        second.captain = self.mate
        self.assertIsNone(self.hull.captain)
        self.assertEqual(second.captain, self.mate)

    def test_command_is_not_ownership(self):
        """A merchant who owns four ships is aboard at most one of them."""
        self.hull.owner = self.merchant
        self.hull.captain = self.mate
        self.assertEqual(self.hull.owner, self.merchant)
        self.assertEqual(self.hull.captain, self.mate)

    def test_passing_command_is_announced(self):
        heard = []
        unsubscribe = bus().subscribe(CommandPassed, heard.append)
        self.addCleanup(unsubscribe)
        self.hull.captain = self.mate
        self.assertEqual(heard[-1].captain, self.mate)


class TestRank(OwnershipTestCase):
    """Derived from what answers to you, never granted."""

    def test_somebody_with_no_ships_is_unranked(self):
        self.assertEqual(rank_of(self.merchant), UNRANKED)

    def test_one_ship_makes_a_captain(self):
        self.hull.owner = self.merchant
        self.assertEqual(rank_of(self.merchant), CAPTAIN)

    def test_a_second_ship_makes_an_admiral(self):
        """It arrives with the ship rather than being conferred."""
        second = self.a_ship("Petrel")
        self.hull.owner = self.merchant
        self.assertFalse(is_admiral(self.merchant))
        second.owner = self.merchant
        self.assertTrue(is_admiral(self.merchant))
        self.assertEqual(rank_of(self.merchant), ADMIRAL)

    def test_and_leaves_with_one(self):
        second = self.a_ship("Petrel")
        self.hull.owner = self.merchant
        second.owner = self.merchant
        second.owner = None
        self.assertFalse(is_admiral(self.merchant))

    def test_commanding_somebody_elses_ship_still_makes_a_captain(self):
        """A man with no ship of his own who has been given command is a captain."""
        self.hull.owner = self.merchant
        self.hull.captain = self.mate
        self.assertEqual(fleet_of(self.mate), ())
        self.assertEqual(rank_of(self.mate), CAPTAIN)

    def test_a_sunk_ship_leaves_the_fleet(self):
        second = self.a_ship("Petrel")
        self.hull.owner = self.merchant
        second.owner = self.merchant
        second.delete()
        self.assertEqual(len(fleet_of(self.merchant)), 1)

    def test_the_stored_roster_does_not_collect_the_drowned(self):
        """
        A sunk ship reads as nobody, so a fleet that still lists her looks right
        from outside. The list itself is persisted, though, and a merchant who
        loses a ship every few years and buys another would carry every wreck he
        ever owned in a growing attribute. Acquiring tidies it.

        """
        lost = self.a_ship("Petrel")
        self.hull.owner = self.merchant
        lost.owner = self.merchant
        lost.delete()

        third = self.a_ship("Fulmar")
        third.owner = self.merchant
        self.assertEqual(self.merchant.db.maritime_fleet, [self.hull, third])

    def test_nobody_is_unranked(self):
        self.assertEqual(rank_of(None), UNRANKED)


class TestWhoMayCommand(OwnershipTestCase):
    """The default policy, which is deliberately small."""

    def test_an_unowned_ship_answers_to_anybody(self):
        """
        Not an oversight. A game that has not adopted ownership must still be
        able to sail, and every example in this contrib builds ships that belong
        to nobody.

        """
        self.assertTrue(may_command(self.mate, self.hull))

    def test_her_captain_may(self):
        self.hull.captain = self.mate
        self.assertTrue(may_command(self.mate, self.hull))

    def test_and_nobody_else(self):
        self.hull.captain = self.mate
        self.assertFalse(may_command(self.merchant, self.hull))

    def test_her_owner_may_when_no_captain_is_appointed(self):
        self.hull.owner = self.merchant
        self.assertTrue(may_command(self.merchant, self.hull))

    def test_but_not_once_one_is(self):
        """An owner who appointed a captain has appointed a captain."""
        self.hull.owner = self.merchant
        self.hull.captain = self.mate
        self.assertFalse(may_command(self.merchant, self.hull))

    def test_a_ship_that_is_not_there(self):
        self.assertFalse(may_command(self.mate, None))


class TestThePolicyIsReplaceable(OwnershipTestCase):
    """The seam that matters more than the default does."""

    @override_settings(MARITIME_COMMAND_POLICY=f"{__name__}.nobody_may")
    def test_a_game_can_refuse_everybody(self):
        self.assertFalse(self.hull.may_be_commanded_by(self.mate))

    @override_settings(MARITIME_COMMAND_POLICY=f"{__name__}.everybody_may")
    def test_a_game_can_permit_everybody(self):
        self.hull.captain = self.merchant
        self.assertTrue(self.hull.may_be_commanded_by(self.mate))

    def test_the_default_is_used_otherwise(self):
        self.hull.captain = self.merchant
        self.assertFalse(self.hull.may_be_commanded_by(self.mate))


class OrdersTestCase(EmptySeaMixin, BaseEvenniaCommandTest):
    """Somebody on a deck, trying to give an order."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Kestrel")
        self.hull.length, self.hull.beam = 18.0, 5.4
        self.hull.motion_limits = MotionLimits(max_speed=6.0, acceleration=0.5, turn_rate=5.0)
        self.hull.maritime_position = WorldPosition(0.0, 0.0)
        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.deck.vessel = self.hull
        self.deck.exposure = OPEN
        self.char1.location = self.deck
        self.stranger = create.create_object(
            "evennia.objects.objects.DefaultCharacter", key="A stranger"
        )


class TestOrdersObeyThePolicy(OrdersTestCase):
    """Which is what makes any of this more than bookkeeping."""

    def test_an_unowned_ship_takes_orders_from_anybody(self):
        self.call(CmdHelm(), "090")
        self.assertAlmostEqual(self.hull.orders.heading, 90.0)

    def test_her_captain_is_obeyed(self):
        self.hull.captain = self.char1
        self.call(CmdHelm(), "090")
        self.assertAlmostEqual(self.hull.orders.heading, 90.0)

    def test_a_stranger_is_not(self):
        self.hull.captain = self.stranger
        self.call(CmdHelm(), "090", "Kestrel answers to A stranger, not to you.")
        self.assertAlmostEqual(self.hull.orders.heading, 0.0)

    def test_the_refusal_names_who_may(self):
        """A bare "you cannot do that" tells a player nothing they can act on."""
        self.hull.owner = self.stranger
        said = self.call(CmdHelm(), "090")
        self.assertIn("belongs to A stranger, and has no captain appointed", said)


class TestShipwright(OrdersTestCase):
    """The builder's tool."""

    def test_it_shows_usage_with_no_arguments(self):
        self.call(CmdShipwright(), "", "Ship building")

    def test_it_builds_a_ship(self):
        self.call(CmdShipwright(), "create Petrel", "Built")
        from evennia.utils.search import search_object

        built = [obj for obj in search_object("Petrel") if isinstance(obj, Vessel)]
        self.assertEqual(len(built), 1)
        self.assertEqual(len(built[0].ship_rooms), 1)

    def test_a_new_ship_belongs_to_nobody(self):
        said = self.call(CmdShipwright(), "create Petrel")
        self.assertIn("She belongs to nobody", said)

    def test_it_needs_a_name(self):
        self.call(CmdShipwright(), "create", "Usage:")

    def test_it_lists_them(self):
        said = self.call(CmdShipwright(), "list")
        self.assertIn("Kestrel", said)

    def test_the_list_can_be_narrowed(self):
        self.call(CmdShipwright(), "create Petrel")
        said = self.call(CmdShipwright(), "list Kes")
        self.assertIn("Kestrel", said)
        self.assertNotIn("Petrel", said)

    def test_a_narrowing_that_matches_nothing(self):
        self.call(CmdShipwright(), "list Albatross", "No ship's name contains")

    def test_a_long_list_says_what_it_held_back(self):
        """A list that silently stopped short would be worse than no list at all."""
        from ..commands.shipwright import PAGE

        for number in range(PAGE + 2):
            create.create_object(Vessel, key=f"Hulk {number:02d}")
        said = self.call(CmdShipwright(), "list")
        self.assertIn("more. Narrow it with", said)

    def test_it_reports_one(self):
        self.hull.owner = self.stranger
        self.call(CmdShipwright(), "info Kestrel", "Kestrel")

    def test_it_sets_an_owner(self):
        self.call(CmdShipwright(), "owner Kestrel = A stranger")
        self.assertEqual(self.hull.owner, self.stranger)

    def test_it_sets_a_captain(self):
        self.call(CmdShipwright(), "captain Kestrel = A stranger")
        self.assertEqual(self.hull.captain, self.stranger)

    def test_it_can_disown_her(self):
        self.hull.owner = self.stranger
        said = self.call(CmdShipwright(), "owner Kestrel = none")
        self.assertIn("belongs to nobody", said)
        self.assertIsNone(self.hull.owner)

    def test_it_notices_an_admiral(self):
        second = create.create_object(Vessel, key="Petrel")
        second.owner = self.stranger
        said = self.call(CmdShipwright(), "owner Kestrel = A stranger")
        self.assertIn("is an admiral", said)

    def test_it_reports_a_fleet(self):
        self.hull.owner = self.stranger
        said = self.call(CmdShipwright(), "fleet A stranger")
        self.assertIn("Kestrel", said)

    def test_a_ship_that_does_not_exist(self):
        self.call(CmdShipwright(), "info Albatross", "No ship called")

    def test_somebody_who_does_not_exist(self):
        self.call(CmdShipwright(), "owner Kestrel = Nobody At All", "Nobody and nothing")

    def test_a_malformed_assignment(self):
        self.call(CmdShipwright(), "owner Kestrel", "Usage:")

    def test_an_unknown_subcommand(self):
        self.call(CmdShipwright(), "scuttle Kestrel", "Ship building")

    def test_it_is_locked_to_builders(self):
        """Reassigning property is not something a player does by typing."""
        self.assertIn("Builder", CmdShipwright.locks)
