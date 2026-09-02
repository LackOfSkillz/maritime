"""
Carrying a deck.

The claim worth testing is not that a bigger force wins - it is that **frontage decides how
much of a force can be brought to bear**, so that numbers matter without settling it. A ship
with three hundred men should not beat forty marines by three hundred to forty.
"""

from evennia.utils.test_resources import BaseEvenniaTestCase

from .. import melee
from ..crew import ABLE, CRACK, MARINES, OARSMEN, PRESSED, SEAMEN, Division


def party(rating=SEAMEN, fit=100, quality=ABLE):
    """
    Args:
        rating (Rating, optional): What they were shipped to do.
        fit (int, optional): How many are standing.
        quality (CrewQuality, optional): What they are made of.

    Returns:
        division (Division): One group aboard.

    """
    return Division(rating=rating, complement=fit, fit=fit, quality=quality)


class TestHowManyCanCross(BaseEvenniaTestCase):
    """Frontage, measured off the hulls rather than read from a table."""

    def test_lying_alongside_admits_more_than_touching_at_an_angle(self):
        self.assertGreater(melee.frontage(1.0, 30.0), melee.frontage(0.2, 30.0))

    def test_a_longer_contact_admits_more(self):
        self.assertGreater(melee.frontage(1.0, 46.0), melee.frontage(1.0, 18.0))

    def test_being_properly_alongside_doubles_it(self):
        """
        Rails together for the length of her, rather than meeting at a point. Compared just
        either side of the threshold so that only the bonus differs.

        """
        # A long hull, so that rounding a party to whole people does not swamp the
        # ratio being asserted - at eight men across, one man of truncation is a tenth.
        just_under = melee.frontage(melee.LYING_TOGETHER - 0.001, 200.0)
        just_over = melee.frontage(melee.LYING_TOGETHER, 200.0)
        self.assertAlmostEqual(just_over / just_under, melee.ALONGSIDE_BONUS, delta=0.1)

    def test_hulls_barely_in_contact_still_admit_somebody(self):
        """Two ships that touch, touch somewhere, and somebody can always get over."""
        self.assertEqual(melee.frontage(0.001, 30.0), melee.FEWEST_ACROSS)

    def test_no_contact_admits_nobody(self):
        self.assertEqual(melee.frontage(0.0, 30.0), 0)

    def test_a_hull_with_no_length_admits_nobody_rather_than_erroring(self):
        self.assertEqual(melee.frontage(1.0, 0.0), 0)


class TestHowManyCanMeetThem(BaseEvenniaTestCase):
    """The cap on defenders, which is the point of the whole item."""

    def test_only_about_twice_the_boarders_reach_the_fighting(self):
        self.assertEqual(melee.can_reach(40), 80)

    def test_a_crowd_behind_them_is_not_in_the_fight(self):
        """
        **Headcount does not decide a boarding.** Three hundred men aboard does not mean
        three hundred in the melee; it means the front of them, and the rest waiting for
        somebody to fall.

        """
        result = melee.fight(
            boarding=[party(MARINES, fit=40, quality=CRACK)],
            repelling=[party(SEAMEN, fit=300, quality=PRESSED)],
            overlap=1.0,
            shorter_length=30.0,
        )
        self.assertLessEqual(result.met, melee.can_reach(result.across))
        self.assertLess(result.met, 300)

    def test_forty_marines_can_beat_a_much_larger_pressed_crew(self):
        """The fight the cap exists to make possible."""
        result = melee.fight(
            boarding=[party(MARINES, fit=40, quality=CRACK)],
            repelling=[party(SEAMEN, fit=300, quality=PRESSED)],
            overlap=1.0,
            shorter_length=30.0,
        )
        self.assertTrue(result.taken, "the marines were beaten by a crowd that could not reach")


class TestWhoIsSentAcross(BaseEvenniaTestCase):
    """`party_strength`: a captain sends the people he shipped to fight."""

    def test_marines_go_first(self):
        divisions = [party(SEAMEN, fit=100), party(MARINES, fit=20)]
        twenty = melee.party_strength(divisions, 20)
        just_seamen = melee.party_strength([party(SEAMEN, fit=100)], 20)
        self.assertGreater(twenty, just_seamen)

    def test_a_party_of_oarsmen_is_worth_less_than_the_same_number_of_marines(self):
        self.assertLess(
            melee.party_strength([party(OARSMEN, fit=50)], 50),
            melee.party_strength([party(MARINES, fit=50)], 50),
        )

    def test_quality_tells_as_well_as_type(self):
        self.assertGreater(
            melee.party_strength([party(SEAMEN, fit=50, quality=CRACK)], 50),
            melee.party_strength([party(SEAMEN, fit=50, quality=PRESSED)], 50),
        )

    def test_asking_for_more_than_she_has_gets_what_she_has(self):
        divisions = [party(SEAMEN, fit=10)]
        self.assertEqual(melee.party_strength(divisions, 500), melee.party_strength(divisions, 10))

    def test_a_division_with_nobody_left_is_worth_nothing(self):
        self.assertEqual(melee.party_strength([party(SEAMEN, fit=0)], 10), 0.0)


class TestTheFourOutcomes(BaseEvenniaTestCase):
    """As the source has them."""

    def fight(self, boarding, repelling, overlap=1.0):
        """
        Args:
            boarding (list): The attacker's divisions.
            repelling (list): The defender's.
            overlap (float, optional): How the hulls touch.

        Returns:
            result (MeleeResult): What happened.

        """
        return melee.fight(boarding, repelling, overlap, 30.0)

    def test_a_deck_nobody_defends_is_taken_unopposed(self):
        result = self.fight([party(MARINES, fit=40)], [])
        self.assertEqual(result.outcome, melee.UNOPPOSED)
        self.assertTrue(result.taken)

    def test_a_much_stronger_party_carries_her(self):
        result = self.fight(
            [party(MARINES, fit=60, quality=CRACK)], [party(OARSMEN, fit=30, quality=PRESSED)]
        )
        self.assertEqual(result.outcome, melee.DEFENDERS_BEATEN)
        self.assertTrue(result.taken)

    def test_a_much_weaker_party_is_thrown_back(self):
        result = self.fight(
            [party(OARSMEN, fit=10, quality=PRESSED)], [party(MARINES, fit=80, quality=CRACK)]
        )
        self.assertEqual(result.outcome, melee.BOARDERS_BEATEN)
        self.assertFalse(result.taken)

    def test_equal_companies_do_not_make_an_even_fight(self):
        """
        **The defender has the deck**, and twice the boarders can reach them. So a hundred
        seamen boarding a hundred seamen are thrown back, and that is right: you do not
        board a ship that is still fighting you on equal terms. You beat her down first.

        """
        result = self.fight([party(SEAMEN, fit=80)], [party(SEAMEN, fit=80)])
        self.assertEqual(result.outcome, melee.BOARDERS_BEATEN)

    def test_a_close_fight_is_not_settled_in_one_exchange(self):
        """
        Marines against seamen is close, once the two-to-one reach is paid for. Neither
        side carries it, both feed in more, and that is not a failure - reinforcing is most
        of what a boarding action is, and a fight decided the moment either side had a nose
        in front would make it pointless.

        """
        result = self.fight([party(MARINES, fit=80)], [party(SEAMEN, fit=200)])
        self.assertEqual(result.outcome, melee.UNRESOLVED)
        self.assertTrue(result.success, "an unresolved fight is a fight, not an error")
        self.assertFalse(result.taken)

    def test_hulls_not_in_contact_send_nobody(self):
        result = self.fight([party(MARINES, fit=40)], [party(SEAMEN, fit=40)], overlap=0.0)
        self.assertFalse(result.success)
        self.assertEqual(result.code, melee.NOBODY_CROSSED)

    def test_a_ship_with_nobody_left_to_send_sends_nobody(self):
        result = self.fight([party(SEAMEN, fit=0)], [party(SEAMEN, fit=40)])
        self.assertFalse(result.success)

    def test_she_never_sends_more_than_she_has(self):
        result = self.fight([party(MARINES, fit=3)], [party(SEAMEN, fit=200)])
        self.assertLessEqual(result.across, 3)


class TestFrontageMattersMoreThanNumbers(BaseEvenniaTestCase):
    """
    The claim the whole item rests on: the same two companies, decided differently by how
    their hulls happen to be touching.
    """

    def test_against_a_full_crew_frontage_changes_the_scale_and_not_the_odds(self):
        """
        **Worth stating, because it is not what you would guess.** While the defender has
        men to spare, she meets whatever crosses with twice its number however wide the
        contact - so a narrow gap and a whole rail give the same odds, and only the size of
        the fight differs.

        """
        boarding = [party(MARINES, fit=60, quality=CRACK)]
        plenty = [party(SEAMEN, fit=400, quality=ABLE)]

        alongside = melee.fight(boarding, plenty, 1.0, 30.0)
        touching = melee.fight(boarding, plenty, 0.08, 30.0)

        self.assertGreater(alongside.across, touching.across)
        self.assertAlmostEqual(alongside.edge, touching.edge, places=6)

    def test_against_a_thinned_crew_frontage_decides_it(self):
        """
        And this is where it tells - which is *why you beat her down before you board her*.

        Once the defender cannot field twice whatever crosses, every extra man over the
        rail is a man she has nobody to meet. The same two companies, the same quality, and
        the only difference is whether the boarder took the trouble to lay himself properly
        alongside.

        """
        boarding = [party(MARINES, fit=60, quality=CRACK)]
        thinned = [party(SEAMEN, fit=40, quality=ABLE)]

        alongside = melee.fight(boarding, thinned, 1.0, 30.0)
        touching = melee.fight(boarding, thinned, 0.08, 30.0)

        self.assertGreater(
            alongside.edge,
            touching.edge,
            "getting properly alongside bought the boarders nothing",
        )
        self.assertTrue(alongside.taken)
        self.assertFalse(touching.taken)
