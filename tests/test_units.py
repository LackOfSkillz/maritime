"""
Tests for saying distances and depths the way they were said.

"""

from django.test import override_settings

from evennia.utils.test_resources import BaseEvenniaTestCase

from ..formatting import (
    FATHOMS,
    LEAGUES,
    METRES,
    METRIC,
    NAUTICAL,
    RAW,
    format_depth,
    format_range,
)
from ..messaging import LEAD_LINE_FATHOMS, leadsman_call
from ..position import (
    METRES_PER_CABLE,
    METRES_PER_FATHOM,
    METRES_PER_LEAGUE,
    METRES_PER_NAUTICAL_MILE,
)


def fathoms(count):
    """
    Args:
        count (float): Depth in fathoms.

    Returns:
        metres (float): The same depth in metres.

    """
    return count * METRES_PER_FATHOM


class TestFormatRange(BaseEvenniaTestCase):
    """Distances, in whichever scheme a game has chosen."""

    def test_leagues_above_three_miles(self):
        self.assertEqual(format_range(2.0 * METRES_PER_LEAGUE, units=LEAGUES), "2.0 leagues")

    def test_miles_between_one_and_three(self):
        self.assertEqual(format_range(2.0 * METRES_PER_NAUTICAL_MILE, units=LEAGUES), "2.0 miles")

    def test_the_nautical_scheme_never_reaches_leagues(self):
        """
        A working navigator reckons in sea miles however far off it is. The
        difference between the two schemes is register, not arithmetic.

        """
        far = 10.0 * METRES_PER_LEAGUE
        self.assertIn("miles", format_range(far, units=NAUTICAL))
        self.assertIn("leagues", format_range(far, units=LEAGUES))

    def test_every_scheme_falls_back_to_cables(self):
        """
        No scheme has a useful word for a tenth of its own unit, and every one of
        them borrowed the cable instead.

        """
        close = 300.0
        for units in (LEAGUES, NAUTICAL):
            self.assertIn("cable", format_range(close, units=units))

    def test_metric_uses_metres_and_kilometres(self):
        self.assertEqual(format_range(800.0, units=METRIC), "800 m")
        self.assertEqual(format_range(4300.0, units=METRIC), "4.3 km")

    def test_metric_never_says_cables(self):
        """A game that has chosen not to pretend should not be handed a cable."""
        self.assertNotIn("cable", format_range(300.0, units=METRIC))

    def test_raw_is_metres(self):
        self.assertEqual(format_range(1830.0, units=RAW), "1830 m")

    def test_one_cable_is_singular(self):
        self.assertEqual(format_range(185.2, units=LEAGUES), "one cable")

    def test_alongside(self):
        self.assertEqual(format_range(5.0, units=LEAGUES), "alongside")

    def test_the_default_is_leagues(self):
        self.assertIn("leagues", format_range(4.0 * METRES_PER_LEAGUE))

    def test_a_game_can_change_it(self):
        with override_settings(MARITIME_DISTANCE_UNITS=METRIC):
            self.assertIn("km", format_range(4.0 * METRES_PER_LEAGUE))


class TestFormatDepth(BaseEvenniaTestCase):
    """Depths."""

    def test_fathoms_by_default(self):
        self.assertEqual(format_depth(fathoms(7.0)), "7.0 fathoms")

    def test_metres_when_asked(self):
        self.assertEqual(format_depth(12.8, units=METRES), "12.8 m")

    def test_depth_is_settable_apart_from_distance(self):
        """
        A ship reckoned her run in leagues and her water in fathoms at the same
        moment. Tying the two together would force one of them to be wrong.

        """
        with override_settings(MARITIME_DISTANCE_UNITS=METRIC, MARITIME_DEPTH_UNITS=FATHOMS):
            self.assertIn("km", format_range(9000.0))
            self.assertIn("fathoms", format_depth(fathoms(5.0)))


class TestLeadsmanCall(BaseEvenniaTestCase):
    """The oldest reporting convention still in the language."""

    def test_a_marked_fathom_is_called_by_the_mark(self):
        self.assertEqual(leadsman_call(fathoms(7.0)), "By the mark seven!")

    def test_an_unmarked_fathom_is_called_by_the_deep(self):
        """
        The line had leather, rag or knots at nine depths and nothing at the
        others, so the call says which kind he found: by the mark means he felt
        something, by the deep means he counted.

        """
        self.assertEqual(leadsman_call(fathoms(6.0)), "By the deep six!")

    def test_two_fathoms_is_mark_twain(self):
        """
        The archaic form survived in this one call because it could not be
        confused with anything else shouted across a deck.

        """
        self.assertEqual(leadsman_call(fathoms(2.0)), "By the mark twain!")

    def test_a_half_over(self):
        self.assertEqual(leadsman_call(fathoms(3.5)), "And a half three!")

    def test_a_quarter_over(self):
        self.assertEqual(leadsman_call(fathoms(7.25)), "And a quarter seven!")

    def test_three_quarters_is_called_down_from_above(self):
        """
        "A quarter less eight" rather than "and three quarters seven" - shorter,
        and much harder to mishear.

        """
        self.assertEqual(leadsman_call(fathoms(7.75)), "A quarter less eight!")

    def test_it_reads_to_the_quarter_fathom(self):
        """As fine as a wet line marked in leather and rag can be read."""
        self.assertEqual(leadsman_call(fathoms(7.03)), "By the mark seven!")

    def test_beyond_the_line_there_is_no_answer(self):
        deep = fathoms(LEAD_LINE_FATHOMS + 5)
        self.assertEqual(leadsman_call(deep), "No bottom with this line!")

    def test_the_last_fathom_of_line_still_answers(self):
        self.assertEqual(leadsman_call(fathoms(LEAD_LINE_FATHOMS)), "By the mark twenty!")

    def test_under_a_fathom_is_its_own_alarm(self):
        self.assertEqual(leadsman_call(fathoms(0.5)), "Less than a fathom, sir!")

    def test_no_water_at_all(self):
        self.assertEqual(leadsman_call(0.0), "No water under her at all - she is on the ground!")

    def test_every_depth_has_a_call(self):
        """
        No gap in the ladder. A leadsman who has nothing to say is worse than no
        leadsman, because the deck assumes silence means water.

        """
        for quarter in range(0, (LEAD_LINE_FATHOMS + 2) * 4):
            self.assertTrue(leadsman_call(fathoms(quarter / 4.0)))


class TestTheUnitsThemselves(BaseEvenniaTestCase):
    """
    The conversions, checked against their definitions rather than against each
    other.

    Everything else in this module states a depth in fathoms and reads it back in
    fathoms, so a wrong metres-per-fathom would cancel out exactly and no test
    would notice. Mutation testing found precisely that: setting a fathom to two
    metres left the whole suite green. These are the assertions that touch the
    outside world.

    """

    def test_a_fathom_is_six_feet(self):
        self.assertAlmostEqual(METRES_PER_FATHOM, 6.0 * 0.3048, places=6)

    def test_a_nautical_mile_is_a_minute_of_latitude(self):
        self.assertEqual(METRES_PER_NAUTICAL_MILE, 1852.0)

    def test_a_league_is_three_sea_miles(self):
        self.assertAlmostEqual(METRES_PER_LEAGUE, 3.0 * METRES_PER_NAUTICAL_MILE)

    def test_a_cable_is_a_tenth_of_a_sea_mile(self):
        self.assertAlmostEqual(METRES_PER_CABLE * 10.0, METRES_PER_NAUTICAL_MILE)

    def test_a_cable_is_near_enough_a_hundred_fathoms(self):
        """
        Which is how the Royal Navy reckoned it. The two definitions disagree by
        about one per cent, and nobody ever argued about it.

        """
        self.assertAlmostEqual(METRES_PER_CABLE / METRES_PER_FATHOM, 100.0, delta=2.0)
