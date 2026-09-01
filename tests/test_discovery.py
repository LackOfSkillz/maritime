"""
Tests for who found what, and for the one property that makes it worth anything.

A discovery ledger is easy to write and easy to write uselessly. The failure is never a
traceback - it is a credit that quietly changes hands, and nobody notices until a player who
named an island finds somebody else's name on it. So the hardest-pressed claim here is that
**a claim is made once and never again**: not overwritten, not re-dated, not re-attributed,
however many ships raise the same headland on the same tick.

The rest follows from three ideas kept apart:

    sighted     raised from seaward, credited to the ship's company
    landed      a separate achievement, credited to one person
    coverage    who may draw what, which is nobody else's business

and from one rule about honesty: discovery is a fact about the *world*, so a ship that is
lost still finds the island she is looking at. Where it gets drawn is the navigator's problem.
"""

from dataclasses import replace

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest, BaseEvenniaTestCase

from ..bathymetry import MaritimeMapProvider
from ..discovery import (
    BANK,
    HEADLAND,
    Claim,
    Discovery,
    Landmark,
    credit_for,
    crew_of,
    ledger,
    set_foot,
    sight,
)
from ..observation import geographic_range
from ..position import WorldPosition
from ..typeclasses import ShipRoom, Vessel

#: A headland that stands well up, and a low bank that does not.
HORN = Landmark(
    key="The Greater Horn",
    position=WorldPosition(0.0, 20_000.0),
    radius=3_000.0,
    height=140.0,
    kind=HEADLAND,
)
SHALLOWS = Landmark(
    key="Muddy Ground",
    position=WorldPosition(0.0, 20_000.0),
    radius=800.0,
    height=0.0,
    kind=BANK,
)


class TestHowACreditReads(BaseEvenniaTestCase):
    """The part a player actually sees, and the only part they will remember."""

    def test_one_person_is_named_plainly(self):
        found = Discovery("x", sighted=Claim(("Aetos",), 0.0))
        self.assertEqual(found.credit(), ("First sighted by Aetos",))

    def test_two_are_joined(self):
        found = Discovery("x", sighted=Claim(("Aetos", "Kestrel"), 0.0))
        self.assertEqual(found.credit(), ("First sighted by Aetos and Kestrel",))

    def test_a_whole_company_reads_like_a_sentence(self):
        found = Discovery("x", sighted=Claim(("Aetos", "Kestrel", "Wren"), 0.0))
        self.assertEqual(found.credit(), ("First sighted by Aetos, with Kestrel and Wren",))

    def test_a_landing_is_reported_separately(self):
        found = Discovery("x", sighted=Claim(("Aetos",), 0.0), landed=Claim(("Kestrel",), 10.0))
        self.assertEqual(
            found.credit(),
            ("First sighted by Aetos", "First landing by Kestrel"),
        )

    def test_a_place_nobody_has_been_to_says_nothing(self):
        """
        The silence is the point. A place with no credit on it is a place still worth
        going to, and filling that space with "undiscovered" would be filling every map
        in the game with the word.

        """
        self.assertEqual(Discovery("x").credit(), ())

    def test_a_claim_with_nobody_in_it_does_not_pretend(self):
        found = Discovery("x", sighted=Claim((), 0.0))
        self.assertEqual(found.credit(), ("First sighted by persons unknown",))


class Coast(MaritimeMapProvider):
    """A world with two named places in it, both at the same spot and very different."""

    def terrain_z_at(self, position):
        return -50.0

    def landmarks_near(self, position, reach):
        return (HORN, SHALLOWS)


class DiscoveryTestCase(BaseEvenniaTest):
    """A hull with a company aboard, and a ledger that starts empty."""

    def setUp(self):
        super().setUp()
        for script in list(ledger().__class__.objects.all()):
            script.delete()

        self.hull = create.create_object(Vessel, key="Aetos")
        self.hull.maritime_position = WorldPosition(0.0, 0.0)
        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.deck.vessel = self.hull
        self.hull.map_here = lambda: Coast()

    def board(self, *characters):
        for character in characters:
            character.location = self.deck

    def close_enough(self, landmark, spare=0.5):
        """Put her within sight of it, by the same arithmetic the sighting uses."""
        reach = geographic_range(3.0, landmark.height) * spare
        self.hull.maritime_position = WorldPosition(
            landmark.position.x, landmark.position.y - reach
        )


class TestWhoGetsTheCredit(DiscoveryTestCase):
    def test_the_company_aboard_is_credited(self):
        self.board(self.char1, self.char2)
        self.close_enough(HORN)
        sight(self.hull, 100.0)
        credit = credit_for(HORN.key)
        self.assertTrue(credit)
        self.assertIn(str(self.char1.key), credit[0])
        self.assertIn(str(self.char2.key), credit[0])

    def test_the_captain_is_named_first(self):
        """
        A discovery is a ship's, and a ship has somebody answerable for her.

        Asked of the order in the claim rather than of where the names fall in the
        sentence. Searching the rendered line for each name found the captain and the
        hand at the same index, because the test characters are called Char and Char2 and
        one is a prefix of the other - so the assertion was about string matching and
        never about who was named first.

        """
        self.board(self.char1, self.char2)
        self.hull.captain = self.char2
        self.close_enough(HORN)
        sight(self.hull, 100.0)
        named = ledger().sighted(HORN.key).by
        self.assertEqual(named[0], str(self.char2.key))
        self.assertIn(str(self.char1.key), named)

    def test_an_empty_ship_discovers_nothing(self):
        """
        There is nobody to credit. A hull sailing itself across an ocean and claiming
        everything it passed would make discovery a matter of leaving a ship running.

        """
        self.close_enough(HORN)
        self.assertEqual(sight(self.hull, 100.0), ())
        self.assertEqual(credit_for(HORN.key), ())

    def test_the_ship_is_recorded_with_them(self):
        self.board(self.char1)
        self.close_enough(HORN)
        sight(self.hull, 100.0)
        self.assertEqual(ledger().sighted(HORN.key).vessel, "Aetos")


class TestAClaimIsMadeOnceAndNeverAgain(DiscoveryTestCase):
    """
    The property that makes the whole thing worth having.

    It never fails loudly. It fails by a credit changing hands, months later, in front of
    the person who earned it.
    """

    def setUp(self):
        super().setUp()
        self.board(self.char1)
        self.close_enough(HORN)
        sight(self.hull, 100.0)
        self.first = credit_for(HORN.key)

    def test_sailing_past_it_again_changes_nothing(self):
        for when in (200.0, 300.0, 400.0):
            sight(self.hull, when)
        self.assertEqual(credit_for(HORN.key), self.first)

    def test_and_the_time_is_not_rewritten(self):
        sight(self.hull, 9_000.0)
        self.assertEqual(ledger().sighted(HORN.key).at, 100.0)

    def test_a_second_ship_does_not_take_it(self):
        other = create.create_object(Vessel, key="Interloper")
        other.maritime_position = self.hull.maritime_position
        deck = create.create_object(ShipRoom, key="Her Deck")
        deck.vessel = other
        other.map_here = lambda: Coast()
        self.char2.location = deck

        self.assertEqual(sight(other, 500.0), ())
        self.assertEqual(credit_for(HORN.key), self.first)
        self.assertNotIn(str(self.char2.key), credit_for(HORN.key)[0])

    def test_the_ledger_itself_refuses_a_second_claim(self):
        """
        The guard in the ledger rather than the one in `sight`, and they are not the same
        guard. `sight` asks whether a place is claimed before claiming it, which is enough
        for one ship sailing past twice - so removing the ledger's own check breaks nothing
        that anybody was testing, and leaves the race wide open.

        Two ships raise the same headland on the same tick. Both ask, both are told it is
        unclaimed, and both write. Only the ledger can decide that.

        """
        book = ledger()
        before = book.sighted(HORN.key)
        book.record_sighting(HORN.key, ("Interloper",), 5_000.0, "Interloper")
        after = book.sighted(HORN.key)
        self.assertEqual(after.by, before.by)
        self.assertEqual(after.at, before.at)
        self.assertNotIn("Interloper", after.by)

    def test_and_a_landing_is_just_as_final(self):
        book = ledger()
        book.record_landing(HORN.key, ("Kestrel",), 100.0)
        book.record_landing(HORN.key, ("Latecomer",), 200.0)
        self.assertEqual(book.landed(HORN.key).by, ("Kestrel",))

    def test_the_ledger_says_it_found_nothing_rather_than_reporting_a_find(self):
        """
        `sight` returns what it *claimed*, not what it saw. A caller announcing "land
        discovered" from a non-empty return would announce it on every tick for ever.

        """
        self.assertEqual(sight(self.hull, 600.0), ())


class TestWhetherItCouldActuallyBeSeen(DiscoveryTestCase):
    """
    Sighted, not merely near. The rule is the same one the lookout reports use, so a
    discovery happens exactly when somebody could have called it.
    """

    def setUp(self):
        super().setUp()
        self.board(self.char1)

    def test_a_high_headland_is_raised_from_a_long_way_off(self):
        self.close_enough(HORN, spare=0.9)
        self.assertTrue(sight(self.hull, 100.0))

    def test_and_not_from_beyond_that(self):
        self.close_enough(HORN, spare=1.2)
        self.assertEqual(sight(self.hull, 100.0), ())
        self.assertEqual(credit_for(HORN.key), ())

    def test_a_low_bank_has_to_be_almost_underfoot(self):
        """
        Height decides range, which is why this is `geographic_range` and not a radius. At
        the distance the headland is raised from, the bank at the same spot is invisible.

        """
        self.close_enough(HORN, spare=0.9)
        found = {made.key for made in sight(self.hull, 100.0)}
        self.assertIn(HORN.key, found)
        self.assertNotIn(SHALLOWS.key, found)

    def test_a_lost_ship_still_finds_what_she_is_looking_at(self):
        """
        Discovery is a fact about the world, not about the chart. Keyed to the reckoning,
        a navigator's error would decide what exists - and a badly lost ship would sail
        through an archipelago discovering nothing.

        """
        self.close_enough(HORN, spare=0.5)
        self.hull.start_reckoning()

        # Put her reckoning a long way out - the way a vessel really holds one, or the
        # test sets an attribute nothing reads and proves only that it did so.
        lost = self.hull.dead_reckoning
        self.assertIsNotNone(lost, "she has no reckoning to be wrong about")
        self.hull.dead_reckoning = replace(lost, position=WorldPosition(4e5, 4e5))
        self.assertNotEqual(
            self.hull.reckoned_position.x, self.hull.maritime_position.x
        )

        self.assertTrue(sight(self.hull, 100.0))


class TestFirstFootfall(DiscoveryTestCase):
    def setUp(self):
        super().setUp()
        self.board(self.char1)

    def test_stepping_ashore_is_its_own_claim(self):
        set_foot(self.char1, HORN, 500.0)
        credit = credit_for(HORN.key)
        self.assertEqual(len(credit), 1)
        self.assertIn("First landing", credit[0])

    def test_it_credits_one_person_and_not_a_boatload(self):
        """
        A boat's crew arrive one at a time and somebody is out first, which is how it has
        always been reported. Crediting the whole boat would make the moment worth nothing
        to anybody in it.

        """
        set_foot(self.char1, HORN, 500.0)
        self.assertEqual(ledger().landed(HORN.key).by, (str(self.char1.key),))

    def test_the_second_person_ashore_gets_nothing(self):
        set_foot(self.char1, HORN, 500.0)
        self.assertIsNone(set_foot(self.char2, HORN, 600.0))
        self.assertEqual(ledger().landed(HORN.key).by, (str(self.char1.key),))

    def test_you_cannot_stand_on_a_sandbank(self):
        """Some places have nothing to plant a flag in, and a landing on one is a bug
        upstream rather than an achievement."""
        self.assertIsNone(set_foot(self.char1, SHALLOWS, 500.0))
        self.assertEqual(credit_for(SHALLOWS.key), ())

    def test_landing_and_sighting_are_independent(self):
        """
        Frequently different people, and either can come first: a place can be landed on
        by somebody who was not there when it was raised, and raised by a ship that never
        put a boat down.

        """
        self.close_enough(HORN)
        sight(self.hull, 100.0)
        set_foot(self.char2, HORN, 500.0)
        credit = credit_for(HORN.key)
        self.assertEqual(len(credit), 2)
        self.assertIn(str(self.char1.key), credit[0])
        self.assertIn(str(self.char2.key), credit[1])

    def test_it_takes_a_name_as_readily_as_a_landmark(self):
        """
        A game recording a landing from its own rooms has a name and no `Landmark` object
        to hand, and should not have to build one to say somebody stepped ashore. A bare
        name is taken as somewhere landable, since a game that says "they landed here" has
        already decided that it can be landed on.

        """
        made = set_foot(self.char1, "Somewhere", 1.0)
        self.assertIsNotNone(made)
        self.assertEqual(ledger().landed("Somewhere").by, (str(self.char1.key),))


class TestAWorldThatNamesNothing(DiscoveryTestCase):
    """
    The dependency-free shape again. A featureless shelf has nothing to discover, and that
    is the right answer rather than a gap.
    """

    def test_the_base_provider_offers_no_landmarks(self):
        from ..bathymetry import FlatSeaMapProvider

        self.assertEqual(FlatSeaMapProvider().landmarks_near(WorldPosition(0.0, 0.0), 50_000.0), ())

    def test_and_a_ship_on_it_discovers_nothing(self):
        from ..bathymetry import FlatSeaMapProvider

        self.board(self.char1)
        self.hull.map_here = lambda: FlatSeaMapProvider()
        self.assertEqual(sight(self.hull, 100.0), ())

    def test_a_provider_that_never_heard_of_landmarks_is_not_an_error(self):
        class Older:
            def terrain_z_at(self, position):
                return -20.0

        self.board(self.char1)
        self.hull.map_here = lambda: Older()
        self.assertEqual(sight(self.hull, 100.0), ())


class TestWhoCountsAsCompany(DiscoveryTestCase):
    def test_only_people_players_are(self):
        """
        An achievement shared with eleven hired hands who exist as a number in the manifest
        is not one. The ledger would fill with names nobody recognises and the captain's own
        would be lost among them.

        """
        self.board(self.char1)
        hand = create.create_object("evennia.objects.objects.DefaultObject", key="a barrel")
        hand.location = self.deck
        self.assertEqual(crew_of(self.hull), (str(self.char1.key),))

    def test_a_captain_ashore_is_not_credited(self):
        self.board(self.char1)
        self.hull.captain = self.char2
        self.char2.location = self.room1
        self.assertNotIn(str(self.char2.key), crew_of(self.hull))
