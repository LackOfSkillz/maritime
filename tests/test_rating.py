"""
Tests for what size of ship she is.

The claim: **a builder should not be able to lie.** The rating is worked out from her
dimensions every time it is asked for, so a bigger hull is a bigger ship whether or not
anybody remembered to say so, and a refit that lengthens her cannot leave a stale label
behind.

"""

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest

from ..rating import (
    BOAT,
    COASTER,
    CRAFT,
    GREAT_SHIP,
    LADDER,
    RATINGS,
    SHIP,
    bigger_than,
    burthen_of,
    rating_for,
    rating_of,
)
from ..typeclasses import Vessel


class TestTheLadder(BaseEvenniaTest):
    """The rungs themselves."""

    def test_every_rung_is_named(self):
        self.assertEqual(tuple(rung.key for rung in LADDER), RATINGS)

    def test_they_go_up(self):
        tons = [rung.upto for rung in LADDER]
        self.assertEqual(tons, sorted(tons))

    def test_the_top_one_has_no_ceiling(self):
        self.assertEqual(LADDER[-1].upto, float("inf"))

    def test_they_compare_by_rung(self):
        self.assertTrue(bigger_than(GREAT_SHIP, BOAT))
        self.assertFalse(bigger_than(BOAT, GREAT_SHIP))

    def test_and_a_rating_compares_the_same_as_its_name(self):
        self.assertTrue(bigger_than(LADDER[-1], BOAT))


class TestMeasuringHer(BaseEvenniaTest):
    """Burthen, which is what the age meant by how big a ship was."""

    def test_a_bigger_hull_measures_more(self):
        self.assertGreater(burthen_of(30.0, 9.0), burthen_of(20.0, 6.0))

    def test_beam_counts_and_not_only_length(self):
        """
        A long narrow hull and a short beamy one are different ships at the same length,
        and tons burthen is the measure that knows it.

        """
        self.assertNotAlmostEqual(burthen_of(20.0, 6.0), burthen_of(20.0, 9.0), places=1)

    def test_beam_counts_a_great_deal(self):
        """It is in there squared, which is why a beamy hull carries so much more."""
        self.assertGreater(burthen_of(20.0, 9.0), 2.0 * burthen_of(20.0, 6.0) * 0.7)


class TestWhereTheShippedHullsLand(BaseEvenniaTest):
    """
    Calibrated against the hulls this contrib ships rather than chosen and made to fit.

    A ladder whose rungs no real hull lands on is a ladder nobody is climbing, so each of
    these is a shipped hull and the rung it comes out on.

    """

    def test_the_yawl_is_a_boat(self):
        self.assertEqual(rating_of(10.0, 3.2).key, BOAT)

    def test_the_cutter_is_craft(self):
        self.assertEqual(rating_of(17.0, 5.0).key, CRAFT)

    def test_the_next_is_a_coaster(self):
        self.assertEqual(rating_of(20.0, 6.0).key, COASTER)

    def test_and_the_middling_hulls_are_ships(self):
        self.assertEqual(rating_of(27.0, 7.3).key, SHIP)
        self.assertEqual(rating_of(30.5, 9.3).key, SHIP)

    def test_and_the_largest_are_great_ships(self):
        self.assertEqual(rating_of(45.0, 9.5).key, GREAT_SHIP)
        self.assertEqual(rating_of(45.7, 12.2).key, GREAT_SHIP)

    def test_every_rung_has_a_hull_on_it(self):
        shipped = [(10.0, 3.2), (17.0, 5.0), (20.0, 6.0), (27.0, 7.3), (45.7, 12.2)]
        landed = {rating_of(length, beam).key for length, beam in shipped}
        self.assertEqual(landed, set(RATINGS))


class TestAHullKnowsHerOwn(BaseEvenniaTest):
    """Read every time, so it cannot fall out of step with the ship."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Kestrel")
        self.hull.length, self.hull.beam = 17.0, 5.0

    def test_she_reports_her_burthen(self):
        self.assertGreater(self.hull.burthen, 0.0)

    def test_and_her_rating(self):
        self.assertEqual(self.hull.rating.key, CRAFT)

    def test_lengthening_her_moves_her_up(self):
        """
        The whole reason it is derived. A rating written down at build time would survive a
        refit that made it wrong, and nobody would ever notice.

        """
        self.hull.length, self.hull.beam = 45.7, 12.2
        self.assertEqual(self.hull.rating.key, GREAT_SHIP)

    def test_nothing_was_written_down_to_make_that_true(self):
        self.hull.length, self.hull.beam = 45.7, 12.2
        self.assertIsNone(self.hull.db.rating)

    def test_a_rating_says_what_she_is_for(self):
        self.assertIn("coast", rating_for(60.0).what)
