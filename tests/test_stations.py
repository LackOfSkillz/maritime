"""
Tests for posts, and who is standing them.

The claim under all of them: **the contrib owns what a post does to the ship, and the game
owns how good the person is.** So the shipped answer to "how well is this being kept?" is
*well enough*, always - and a game that replaces the seam is answered instead. A default
that quietly penalised anybody would be a skill system with the numbers hidden.

"""

from django.test import override_settings
from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest

from ..events import bus
from ..stations import (
    CARPENTER,
    GUNNERY,
    HELM,
    LOOKOUT,
    MASTER,
    NO_SUCCESSOR,
    NO_SUCH_POST,
    NOBODY_THERE,
    POSTS,
    SUCCESSION,
    WELL_ENOUGH,
    PostChanged,
)
from ..typeclasses import Vessel


def a_green_hand(character, post, vessel):
    """A policy that says everybody is hopeless, for the test that proves the seam is real."""
    return 0.25


class StationTestCase(BaseEvenniaTest):
    """A hull and some people to put on her posts."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Kestrel")
        self.mate = self.a_person("The mate")
        self.gunner = self.a_person("The gunner")

    def a_person(self, key):
        return create.create_object("evennia.objects.objects.DefaultCharacter", key=key)


class TestStandingAPost(StationTestCase):
    """Taking one, and leaving it."""

    def test_she_starts_with_nobody_posted(self):
        self.assertEqual(self.hull.posts, {})

    def test_somebody_can_take_one(self):
        self.assertTrue(self.hull.post_to(HELM, self.mate))
        self.assertIs(self.hull.keeper_of(HELM), self.mate)

    def test_a_post_that_does_not_exist_is_refused(self):
        self.assertEqual(self.hull.post_to("cook", self.mate).code, NO_SUCH_POST)

    def test_taking_one_gives_up_the_other(self):
        """
        A man at the helm is not also on the lookout, and letting him be would get two
        people's work out of one.

        """
        self.hull.post_to(HELM, self.mate)
        self.hull.post_to(LOOKOUT, self.mate)
        self.assertIsNone(self.hull.keeper_of(HELM))
        self.assertIs(self.hull.keeper_of(LOOKOUT), self.mate)

    def test_a_post_takes_one_person(self):
        self.hull.post_to(HELM, self.mate)
        result = self.hull.post_to(HELM, self.gunner)
        self.assertIs(result.relieved, self.mate)
        self.assertIs(self.hull.keeper_of(HELM), self.gunner)

    def test_posting_somebody_who_is_already_there(self):
        self.hull.post_to(HELM, self.mate)
        self.assertFalse(self.hull.post_to(HELM, self.mate))

    def test_they_can_be_stood_down(self):
        self.hull.post_to(HELM, self.mate)
        self.assertTrue(self.hull.relieve(HELM))
        self.assertIsNone(self.hull.keeper_of(HELM))

    def test_standing_down_an_empty_post(self):
        self.assertEqual(self.hull.relieve(HELM).code, NOBODY_THERE)

    def test_what_somebody_is_standing_can_be_asked(self):
        self.hull.post_to(GUNNERY, self.gunner)
        self.assertEqual(self.hull.post_of(self.gunner), GUNNERY)
        self.assertIsNone(self.hull.post_of(self.mate))


class TestWhatIsAnnounced(StationTestCase):
    """A game listening for who is where."""

    def setUp(self):
        super().setUp()
        self.heard = []
        bus().subscribe(PostChanged, self.heard.append)

    def test_taking_a_post_is_announced(self):
        self.hull.post_to(HELM, self.mate)
        self.assertEqual(self.heard[-1].keeper, self.mate)

    def test_and_carries_who_was_relieved(self):
        self.hull.post_to(HELM, self.mate)
        self.hull.post_to(HELM, self.gunner)
        self.assertIs(self.heard[-1].relieved, self.mate)

    def test_standing_down_is_announced_too(self):
        self.hull.post_to(HELM, self.mate)
        self.hull.relieve(HELM)
        self.assertIsNone(self.heard[-1].keeper)


class TestHowWellItIsKept(StationTestCase):
    """The seam the whole career design rests on."""

    def test_the_shipped_answer_is_well_enough(self):
        self.hull.post_to(HELM, self.mate)
        self.assertAlmostEqual(self.hull.competence_at(HELM), WELL_ENOUGH)

    def test_and_it_is_the_same_with_nobody_there(self):
        """
        A ship's people do these things anyway. A named post is a game saying *this* person
        does it, and only a game knows whether that is better.

        """
        self.assertAlmostEqual(self.hull.competence_at(HELM), WELL_ENOUGH)

    def test_the_default_penalises_nobody(self):
        """
        A default that quietly docked an unskilled crew would be a skill system with its
        numbers hidden - which is the one thing this must not ship.

        """
        self.assertEqual(WELL_ENOUGH, 1.0)

    @override_settings(MARITIME_COMPETENCE_POLICY=f"{__package__}.test_stations.a_green_hand")
    def test_a_game_can_answer_instead(self):
        self.hull.post_to(HELM, self.mate)
        self.assertAlmostEqual(self.hull.competence_at(HELM), 0.25)

    @override_settings(MARITIME_COMPETENCE_POLICY=f"{__package__}.test_stations.a_green_hand")
    def test_and_is_asked_about_every_post(self):
        for post in POSTS:
            self.assertAlmostEqual(self.hull.competence_at(post), 0.25)


class TestCommandSucceeding(StationTestCase):
    """Who takes her when her captain is gone."""

    def test_the_sailing_master_first(self):
        self.hull.post_to(MASTER, self.mate)
        self.hull.post_to(GUNNERY, self.gunner)
        self.assertTrue(self.hull.succeed_command())
        self.assertIs(self.hull.captain, self.mate)

    def test_then_the_guns(self):
        self.hull.post_to(GUNNERY, self.gunner)
        self.hull.succeed_command()
        self.assertIs(self.hull.captain, self.gunner)

    def test_a_ship_with_nobody_posted_has_no_successor(self):
        self.assertEqual(self.hull.succeed_command().code, NO_SUCCESSOR)

    def test_the_captain_does_not_succeed_himself(self):
        """
        A captain standing a post as well is still the captain. Handing her to him would
        report a succession that changed nothing.

        """
        self.hull.pass_command(self.mate)
        self.hull.post_to(MASTER, self.mate)
        self.assertEqual(self.hull.succeed_command().code, NO_SUCCESSOR)

    def test_the_order_is_written_down_rather_than_discovered(self):
        """
        So "who has her now?" is a thing somebody decided, not a thing that fell out of
        dictionary ordering.

        """
        self.assertEqual(SUCCESSION[0], MASTER)
        self.assertIn(CARPENTER, SUCCESSION)
        self.assertEqual(len(set(SUCCESSION)), len(POSTS))
