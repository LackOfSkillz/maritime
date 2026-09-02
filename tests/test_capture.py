"""
Tests for taking a ship.

The four conditions get one test each for being *missing*, because a capture that happens
when it should not is the failure that matters here - it takes something off somebody who
never agreed to lose it, and there is no undo.

"""

from django.test import override_settings
from evennia.objects.objects import DefaultCharacter
from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest

from ..capture import (
    ALREADY_HERS,
    CAPTAIN_UNBEATEN,
    DECK_NOT_CARRIED,
    NO_CAPTOR,
    NOT_HELD,
    NOT_STRUCK,
    SAME_VESSEL,
    captain_subdued,
    may_be_taken,
    take,
)
from ..crew import ABLE, PRESSED
from ..events import bus
from ..motion import MotionLimits
from ..ownership import CAPTURED, CommandPassed, OwnershipTransferred, fleet_of
from ..position import WorldPosition
from ..rooms import ShipRoom
from ..typeclasses import Vessel
from ..vessel import OPEN
from .base import EmptySeaMixin


class SomebodyWithAKeyboard:
    """
    Stands in for a player, for the tests that call the policy directly.

    A real one would need a session attached, which is a lot of scaffolding to prove one
    boolean. What the policy looks at is `has_account`, so this is the honest minimum.

    It cannot be stored on a ship - an Evennia attribute takes database objects, not
    arbitrary Python - which is why anything that has to be *aboard* uses `PlayerCaptain`
    below instead.

    """

    has_account = True


class PlayerCaptain(DefaultCharacter):
    """
    A character that reads as somebody with a keyboard, and can be stored as one.

    Subclassed rather than mocked because the capture path writes to her attributes when
    she is released, and a captain who cannot be released would hide the half of the
    transfer that is easiest to get wrong.

    """

    @property
    def has_account(self):
        return True


class CaptureTestCase(EmptySeaMixin, BaseEvenniaTest):
    """A hull worth taking, and a hull to take her with."""

    def setUp(self):
        super().setUp()
        self.captor = self.a_ship("Kestrel", WorldPosition(0.0, 0.0))
        self.prize = self.a_ship("Petrel", WorldPosition(8.0, 0.0))
        self.raider = self.a_person("The raider")
        self.raiding_captain = self.a_person("The raiding captain")
        self.merchant = self.a_person("The merchant")
        self.merchant_captain = self.a_person("The merchant captain")

        self.captor.owner = self.raider
        self.captor.pass_command(self.raiding_captain)
        self.prize.owner = self.merchant
        self.prize.pass_command(self.merchant_captain)

    def a_ship(self, key, position):
        hull = create.create_object(Vessel, key=key)
        hull.length, hull.beam = 30.0, 8.5
        hull.motion_limits = MotionLimits(max_speed=6.0, acceleration=0.5, turn_rate=5.0)
        hull.maritime_position = position
        hull.heading = 0.0
        deck = create.create_object(ShipRoom, key=f"{key} Deck")
        deck.vessel = hull
        deck.exposure = OPEN
        return hull

    def a_person(self, key):
        return create.create_object("evennia.objects.objects.DefaultCharacter", key=key)

    def a_player(self, key):
        """Somebody with a keyboard, real enough to be stored and released."""
        return create.create_object(PlayerCaptain, key=key)

    def all_four(self):
        """Put every condition but the momentary one in place."""
        self.captor.grapple(self.prize)
        self.prize.strike(self.captor)


class TestTheFourConditions(CaptureTestCase):
    """All of them, or nothing."""

    def test_all_four_take_her(self):
        self.all_four()
        self.assertTrue(take(self.prize, self.captor, carried=True))

    def test_not_held_is_refused(self):
        self.prize.strike(self.captor)
        result = take(self.prize, self.captor, carried=True)
        self.assertFalse(result)
        self.assertEqual(result.code, NOT_HELD)

    def test_not_struck_is_refused(self):
        self.captor.grapple(self.prize)
        result = take(self.prize, self.captor, carried=True)
        self.assertFalse(result)
        self.assertEqual(result.code, NOT_STRUCK)

    def test_a_deck_not_carried_is_refused(self):
        self.all_four()
        result = take(self.prize, self.captor, carried=False)
        self.assertFalse(result)
        self.assertEqual(result.code, DECK_NOT_CARRIED)

    def test_a_captain_on_her_feet_is_refused(self):
        """The condition that stops a capture being paperwork."""
        self.all_four()
        self.prize.pass_command(self.a_player("Their player captain"))
        result = take(self.prize, self.captor, carried=True)
        self.assertFalse(result)
        self.assertEqual(result.code, CAPTAIN_UNBEATEN)

    def test_striking_to_somebody_else_does_not_count(self):
        """
        She struck, and she is held - but not to the same hull. Reading the two facts
        without comparing them would let a third ship collect a prize it never fought.

        """
        third = self.a_ship("Gannet", WorldPosition(16.0, 0.0))
        self.captor.grapple(self.prize)
        self.prize.strike(third)
        result = take(self.prize, self.captor, carried=True)
        self.assertFalse(result)
        self.assertEqual(result.code, NOT_STRUCK)

    def test_she_cannot_take_herself(self):
        self.assertEqual(take(self.prize, self.prize, carried=True).code, SAME_VESSEL)

    def test_nobody_takes_nothing(self):
        self.assertEqual(take(self.prize, None, carried=True).code, NO_CAPTOR)

    def test_every_condition_is_reported_not_just_the_first(self):
        """
        One round trip should tell somebody the whole truth. Naming only the first thing
        wrong makes a player fix it and try again to be told about the second.

        """
        result = take(self.prize, self.captor, carried=False)
        self.assertFalse(result.held)
        self.assertFalse(result.struck)
        self.assertFalse(result.carried)
        self.assertTrue(result.subdued)
        self.assertEqual(result.conditions_met, 1)


class TestAskingWithoutActing(CaptureTestCase):
    """`may_be_taken` answers the question and moves nothing."""

    def test_it_does_not_take_her(self):
        self.all_four()
        self.assertTrue(may_be_taken(self.prize, self.captor, carried=True))
        self.assertEqual(self.prize.owner, self.merchant)
        self.assertEqual(self.prize.captain, self.merchant_captain)

    def test_it_counts_what_is_missing(self):
        self.captor.grapple(self.prize)
        self.assertEqual(may_be_taken(self.prize, self.captor, carried=True).conditions_met, 3)


class TestWhatMoves(CaptureTestCase):
    """Ownership and command, to two people rather than to a side."""

    def setUp(self):
        super().setUp()
        self.all_four()
        self.heard = []
        bus().subscribe(OwnershipTransferred, self.heard.append)
        bus().subscribe(CommandPassed, self.heard.append)
        self.result = take(self.prize, self.captor, carried=True)

    def test_she_belongs_to_the_captors_owner(self):
        self.assertEqual(self.prize.owner, self.raider)

    def test_she_arrives_with_nobody_commanding_her(self):
        """
        A prize waits for a prize master. Handing her straight to the captor's captain is
        the obvious thing and it is wrong - see the test below for what it costs.

        """
        self.assertIsNone(self.prize.captain)

    def test_taking_her_does_not_cost_the_captor_her_own_captain(self):
        """
        The bug this test was written for. One ship per captain is a rule the contrib
        already keeps, so passing the prize to the captor's captain made him give up the
        ship he had just won her with - she came away from a victory uncommanded.

        """
        self.assertEqual(self.captor.captain, self.raiding_captain)
        self.assertEqual(self.raiding_captain.db.maritime_command, self.captor)

    def test_the_beaten_captain_no_longer_holds_her(self):
        """
        Command is held on both sides. Writing only the ship's end would leave a beaten
        captain still carrying a reference to the ship that was taken off him, and he
        would go on being able to give her orders.

        """
        self.assertIsNone(self.merchant_captain.db.maritime_command)

    def test_she_leaves_the_old_fleet_and_joins_the_new(self):
        self.assertEqual(fleet_of(self.merchant), ())
        self.assertIn(self.prize, fleet_of(self.raider))

    def test_the_transfer_says_it_was_a_capture(self):
        transfers = [e for e in self.heard if isinstance(e, OwnershipTransferred)]
        self.assertEqual([e.reason for e in transfers], [CAPTURED])

    def test_both_ends_of_both_changes_are_published(self):
        transfer = next(e for e in self.heard if isinstance(e, OwnershipTransferred))
        passed = next(e for e in self.heard if isinstance(e, CommandPassed))
        self.assertEqual((transfer.former_owner, transfer.owner), (self.merchant, self.raider))
        self.assertEqual((passed.former_captain, passed.captain), (self.merchant_captain, None))

    def test_the_result_carries_both_ends_too(self):
        self.assertEqual(self.result.former_owner, self.merchant)
        self.assertEqual(self.result.owner, self.raider)
        self.assertEqual(self.result.former_captain, self.merchant_captain)
        self.assertIsNone(self.result.captain)

    def test_striking_is_not_undone(self):
        """That she was beaten is a matter of history and survives changing hands."""
        self.assertTrue(self.prize.struck)

    def test_taking_her_twice_is_not_a_second_prize(self):
        """A game paying out on the event should not be paid twice for one ship."""
        again = take(self.prize, self.captor, carried=True)
        self.assertFalse(again)
        self.assertEqual(again.code, ALREADY_HERS)


class TestTheSubduedSeam(CaptureTestCase):
    """The one condition this contrib will not answer for itself."""

    def test_an_npc_captain_goes_down_with_the_deck(self):
        self.assertTrue(captain_subdued(self.merchant_captain, self.prize, self.captor))

    def test_a_ship_nobody_commands_has_nobody_to_beat(self):
        self.assertTrue(captain_subdued(None, self.prize, self.captor))

    def test_somebody_with_an_account_is_never_beaten_by_default(self):
        """
        The safe direction to be wrong in. A capture that does not happen is a fight that
        continues; one that happens wrongly cannot be undone.

        """
        self.assertFalse(captain_subdued(SomebodyWithAKeyboard(), self.prize, self.captor))

    @override_settings(MARITIME_SUBDUED_POLICY=f"{__package__}.test_capture.everybody_is_beaten")
    def test_a_game_can_replace_it(self):
        self.all_four()
        self.prize.pass_command(self.a_player("Their player captain"))
        self.assertTrue(take(self.prize, self.captor, carried=True))

    @override_settings(MARITIME_SUBDUED_POLICY=f"{__package__}.test_capture.nobody_is_beaten")
    def test_and_can_refuse_every_capture(self):
        self.all_four()
        result = take(self.prize, self.captor, carried=True)
        self.assertFalse(result)
        self.assertEqual(result.code, CAPTAIN_UNBEATEN)


class TestStormingHerTakesHer(CaptureTestCase):
    """The wiring: an exchange that carries her deck is where a capture happens."""

    def test_carrying_her_deck_with_the_rest_in_place_takes_her(self):
        self.captor.man(120, ABLE)
        self.prize.man(40, PRESSED)
        self.all_four()
        result = self.captor.storm_her()
        self.assertTrue(result.taken)
        self.assertEqual(self.prize.owner, self.raider)

    def test_carrying_her_deck_without_a_surrender_takes_nothing(self):
        """
        Three conditions is not four, and the melee is not allowed to skip the other
        three just because it produced the one it knows about.

        """
        self.captor.man(120, ABLE)
        self.prize.man(40, PRESSED)
        self.captor.grapple(self.prize)
        result = self.captor.storm_her()
        self.assertTrue(result.taken)
        self.assertEqual(self.prize.owner, self.merchant)


def everybody_is_beaten(captain, prize, captor):
    """A policy that settles any captain, for the test that proves the seam is real."""
    return True


def nobody_is_beaten(captain, prize, captor):
    """A policy that settles none, likewise."""
    return False
