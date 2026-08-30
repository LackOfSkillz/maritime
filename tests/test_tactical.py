"""
Tests for the geometry two ships in company generate about each other.

"""

from evennia.utils.test_resources import BaseEvenniaTestCase

from ..position import EAST, NORTH, SOUTH, WorldPosition
from ..tactical import (
    ARCS,
    DEFAULT_RANGE_BANDS,
    FORWARD,
    OMNI,
    PORT_BROADSIDE,
    STARBOARD_BROADSIDE,
    arcs_bearing,
    aspect,
    aspect_name,
    bears,
    closure,
    crossing_the_t,
    range_band,
    relative_heading,
    time_to_close,
)

HERE = WorldPosition(0.0, 0.0)
NORTH_OF_US = WorldPosition(0.0, 1000.0)


class TestRelativeHeading(BaseEvenniaTestCase):
    """How far two courses differ."""

    def test_the_same_course_is_no_difference(self):
        self.assertAlmostEqual(relative_heading(EAST, EAST), 0.0)

    def test_opposite_courses(self):
        self.assertAlmostEqual(abs(relative_heading(NORTH, SOUTH)), 180.0)

    def test_her_head_to_starboard_is_positive(self):
        self.assertGreater(relative_heading(NORTH, EAST), 0.0)


class TestAspect(BaseEvenniaTestCase):
    """Where you are, from her head."""

    def test_dead_ahead_of_her_is_bow_on(self):
        """She is north of us and heading south: we are right under her bow."""
        self.assertAlmostEqual(aspect(HERE, NORTH_OF_US, SOUTH), 0.0)

    def test_dead_astern_of_her_is_stern_on(self):
        self.assertAlmostEqual(abs(aspect(HERE, NORTH_OF_US, NORTH)), 180.0)

    def test_on_her_beam(self):
        self.assertAlmostEqual(abs(aspect(HERE, NORTH_OF_US, EAST)), 90.0)

    def test_it_is_not_the_same_as_relative_bearing(self):
        """
        The whole reason it exists. A ship at one bearing can be coming for you
        or leaving, and only aspect separates them.

        """
        coming = aspect(HERE, NORTH_OF_US, SOUTH)
        leaving = aspect(HERE, NORTH_OF_US, NORTH)
        self.assertNotAlmostEqual(coming, leaving)

    def test_it_is_named_the_way_it_is_reported(self):
        self.assertEqual(aspect_name(0.0), "bow-on")
        self.assertEqual(aspect_name(180.0), "stern-on")
        self.assertEqual(aspect_name(90.0), "beam-on to starboard")
        self.assertEqual(aspect_name(-40.0), "port bow")
        self.assertEqual(aspect_name(-140.0), "port quarter")

    def test_every_aspect_has_a_name(self):
        for degrees in range(-180, 181):
            self.assertTrue(aspect_name(float(degrees)))


class TestClosure(BaseEvenniaTestCase):
    """How fast the gap is shutting."""

    def test_steaming_straight_at_her_closes(self):
        self.assertAlmostEqual(closure(HERE, NORTH, 5.0, NORTH_OF_US, NORTH, 0.0), 5.0)

    def test_steaming_away_opens(self):
        self.assertAlmostEqual(closure(HERE, SOUTH, 5.0, NORTH_OF_US, NORTH, 0.0), -5.0)

    def test_head_on_closes_at_the_sum(self):
        self.assertAlmostEqual(closure(HERE, NORTH, 5.0, NORTH_OF_US, SOUTH, 4.0), 9.0)

    def test_steaming_abreast_closes_at_nothing(self):
        """
        An enormous relative motion and a closure of zero. Only the component
        along the line between them changes the range.

        """
        self.assertAlmostEqual(closure(HERE, EAST, 10.0, NORTH_OF_US, EAST, 10.0), 0.0)

    def test_a_stern_chase_closes_at_the_difference(self):
        self.assertAlmostEqual(closure(HERE, NORTH, 6.0, NORTH_OF_US, NORTH, 4.0), 2.0)

    def test_a_chase_she_is_winning_opens(self):
        self.assertAlmostEqual(closure(HERE, NORTH, 4.0, NORTH_OF_US, NORTH, 6.0), -2.0)


class TestTimeToClose(BaseEvenniaTestCase):
    """A captain's estimate, not a prophecy."""

    def test_closing_gives_a_time(self):
        self.assertAlmostEqual(time_to_close(1000.0, 5.0), 200.0)

    def test_opening_gives_none(self):
        """Never is the honest answer, and infinity is not a number for a report."""
        self.assertIsNone(time_to_close(1000.0, -5.0))

    def test_a_steady_range_gives_none(self):
        self.assertIsNone(time_to_close(1000.0, 0.0))

    def test_already_together_gives_none(self):
        self.assertIsNone(time_to_close(0.0, 5.0))


class TestRangeBands(BaseEvenniaTestCase):
    """What to call a distance."""

    def test_alongside_is_boarding_range(self):
        self.assertEqual(range_band(10.0), "boarding")

    def test_a_cable_off_is_close(self):
        self.assertEqual(range_band(180.0), "close")

    def test_a_mile_off_is_long(self):
        self.assertEqual(range_band(900.0), "long")

    def test_beyond_the_longest_band_is_out_of_range(self):
        self.assertEqual(range_band(90000.0), "out of range")

    def test_the_bands_are_a_game_decision(self):
        """
        Presentation, not physics. What counts as long depends on what a game
        arms its ships with, and hard-coding it would put a weapons decision
        inside a geometry module.

        """
        mine = (("shouting distance", 500.0), ("spitting distance", 50.0))
        self.assertEqual(range_band(300.0, mine), "shouting distance")

    def test_every_distance_falls_in_some_band(self):
        for metres in range(0, 3000, 10):
            self.assertTrue(range_band(float(metres)))

    def test_the_bands_run_longest_first(self):
        reaches = [reach for _name, reach in DEFAULT_RANGE_BANDS]
        self.assertEqual(reaches, sorted(reaches, reverse=True))


class TestArcs(BaseEvenniaTestCase):
    """What can be brought to bear."""

    def test_a_target_ahead_is_in_the_forward_arc(self):
        self.assertTrue(bears(0.0, FORWARD))

    def test_a_target_abeam_is_not(self):
        self.assertFalse(bears(90.0, FORWARD))

    def test_a_target_to_starboard_is_on_that_broadside(self):
        self.assertTrue(bears(90.0, STARBOARD_BROADSIDE))
        self.assertFalse(bears(90.0, PORT_BROADSIDE))

    def test_an_omni_mount_bears_everywhere(self):
        for degrees in range(-180, 181, 15):
            self.assertTrue(bears(float(degrees), OMNI))

    def test_an_unknown_arc_bears_nothing(self):
        self.assertFalse(bears(0.0, "the masthead"))

    def test_more_than_one_arc_can_bear_at_once(self):
        """
        A target fine on the bow is in the forward arc and the edge of a
        broadside both, and that overlap is the whole of manoeuvring for
        position.

        """
        found = arcs_bearing(40.0)
        self.assertIn(FORWARD, found)
        self.assertIn(STARBOARD_BROADSIDE, found)

    def test_every_arc_bears_on_its_own_centre(self):
        for name, (centre, _width) in ARCS.items():
            self.assertTrue(bears(centre, name))


class TestCrossingTheT(BaseEvenniaTestCase):
    """The position everybody manoeuvres for."""

    def test_she_abeam_and_you_ahead_of_her(self):
        self.assertTrue(crossing_the_t(own_relative=90.0, target_aspect=0.0))

    def test_a_stern_chase_is_not_crossing_her_t(self):
        self.assertFalse(crossing_the_t(own_relative=0.0, target_aspect=180.0))

    def test_beam_to_beam_is_not_either(self):
        self.assertFalse(crossing_the_t(own_relative=90.0, target_aspect=90.0))

    def test_it_needs_both_halves(self):
        """
        She is abeam but you are on her quarter: your broadside bears and so does
        hers, which is a gunnery duel and not a crossed T.

        """
        self.assertFalse(crossing_the_t(own_relative=90.0, target_aspect=140.0))
