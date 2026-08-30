"""
Tests for looking in a direction, and for keeping a watch there.

"""

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaCommandTest, BaseEvenniaTestCase

from ..commands import CmdLookAround, CmdScan, CmdWatch
from ..motion import MotionLimits
from ..observation import (
    POINT_ARC,
    QUARTER_ARC,
    Sighting,
    direction_named,
    in_arc,
    normalise_direction,
    within_arc,
)
from ..position import EAST, WEST, WorldPosition
from ..rooms import ShipRoom
from ..traffic import traffic
from ..typeclasses import Vessel
from ..vessel import BELOW_WATERLINE, OPEN
from .base import EmptySeaMixin


def a_sighting(relative=0.0, bearing=0.0, target=None):
    """
    Args:
        relative (float): Relative bearing.
        bearing (float): True bearing.
        target (any): What was seen.

    Returns:
        sighting (Sighting): A stand-in.

    """
    return Sighting(
        target=target, distance=1000.0, bearing=bearing, relative=relative, level="vessel"
    )


class TestWithinArc(BaseEvenniaTestCase):
    """Whether a bearing falls in a sector."""

    def test_dead_centre_is_inside(self):
        self.assertTrue(within_arc(0.0, 0.0))

    def test_the_edge_is_inside(self):
        self.assertTrue(within_arc(45.0, 0.0, QUARTER_ARC))

    def test_just_past_the_edge_is_not(self):
        self.assertFalse(within_arc(46.0, 0.0, QUARTER_ARC))

    def test_it_wraps_around_north(self):
        """A sector centred on north has to hold 350 and 010 alike."""
        self.assertTrue(within_arc(350.0, 0.0, QUARTER_ARC))
        self.assertTrue(within_arc(10.0, 0.0, QUARTER_ARC))

    def test_a_narrow_arc_excludes_more(self):
        self.assertTrue(within_arc(30.0, 0.0, QUARTER_ARC))
        self.assertFalse(within_arc(30.0, 0.0, POINT_ARC))


class TestDirectionNamed(BaseEvenniaTestCase):
    """Turning a typed word into an arc."""

    def test_the_four_quarters(self):
        for word in ("fore", "aft", "port", "starboard"):
            self.assertIsNotNone(direction_named(word))

    def test_compass_points(self):
        self.assertIsNotNone(direction_named("north"))
        self.assertIsNotNone(direction_named("south-southwest"))

    def test_nonsense_names_nothing(self):
        self.assertIsNone(direction_named("sideways"))

    def test_an_empty_word_names_nothing(self):
        self.assertIsNone(direction_named(""))

    def test_it_is_case_insensitive(self):
        self.assertIsNotNone(direction_named("  STARBOARD "))

    def test_aliases_resolve_to_one_name(self):
        """
        So a watch set with "astern" is the same watch as one set with "abaft",
        rather than two watches that happen to point the same way.

        """
        for alias in ("astern", "stern", "abaft"):
            self.assertEqual(direction_named(alias)[0], "aft")

    def test_relative_directions_are_marked_relative(self):
        self.assertTrue(direction_named("fore")[3])

    def test_compass_directions_are_not(self):
        self.assertFalse(direction_named("north")[3])

    def test_a_quarter_is_wider_than_a_point(self):
        self.assertGreater(direction_named("fore")[2], direction_named("north")[2])

    def test_abbreviations(self):
        """
        "se" is what people type. Making them spell out "south-east" is handing
        them a puzzle instead of a compass.

        """
        for short, full in (("n", "north"), ("se", "southeast"), ("ene", "east-northeast")):
            self.assertEqual(direction_named(short)[0], full)

    def test_spacing_and_hyphens_do_not_matter(self):
        for spelling in ("southeast", "south east", "south-east", "SOUTH  EAST"):
            self.assertEqual(direction_named(spelling)[0], "southeast")

    def test_normalising_strips_what_does_not_matter(self):
        self.assertEqual(normalise_direction("  South-East "), "southeast")

    def test_starboard_has_a_short_form_too(self):
        self.assertEqual(direction_named("stbd")[0], "starboard")

    def test_larboard_is_port(self):
        """The older word, and one an age-of-sail player may well reach for."""
        self.assertEqual(direction_named("larboard")[0], "port")


class TestInArc(BaseEvenniaTestCase):
    """Filtering what is in sight down to one direction."""

    def setUp(self):
        super().setUp()
        self.ahead = a_sighting(relative=0.0, bearing=90.0)
        self.to_port = a_sighting(relative=-90.0, bearing=0.0)
        self.astern = a_sighting(relative=180.0, bearing=270.0)

    def test_it_keeps_what_is_in_the_sector(self):
        found = in_arc([self.ahead, self.to_port, self.astern], 0.0, QUARTER_ARC)
        self.assertEqual(found, (self.ahead,))

    def test_it_can_measure_from_north_instead(self):
        """
        Looking to starboard and looking east are the same question in two
        reference frames, and coming round changes only one of the answers.

        """
        found = in_arc([self.ahead, self.to_port, self.astern], 0.0, QUARTER_ARC, relative=False)
        self.assertEqual(found, (self.to_port,))

    def test_an_empty_sea_gives_an_empty_sector(self):
        self.assertEqual(in_arc([], 0.0, QUARTER_ARC), ())


class DirectionTestCase(EmptySeaMixin, BaseEvenniaCommandTest):
    """A ship heading east, with a sail to the north of her."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Test Sloop")
        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.deck.vessel = self.hull
        self.deck.exposure = OPEN
        self.hull.maritime_position = WorldPosition(0.0, 0.0)
        self.hull.motion_limits = MotionLimits(max_speed=10.0, acceleration=2.0, turn_rate=8.0)
        self.hull.heading = EAST
        self.hull.air_draft = 12.0
        self.char1.location = self.deck

        self.other = create.create_object(Vessel, key="Marigold")
        self.other.air_draft = 12.0
        self.other.maritime_position = WorldPosition(0.0, 2000.0)
        traffic().note(self.other, self.other.maritime_position)


class TestLookInADirection(DirectionTestCase):
    """look fore, look north."""

    def test_a_sail_to_port_is_found_looking_to_port(self):
        self.assertIn("port beam", self.call(CmdLookAround(), "port"))

    def test_and_not_found_looking_to_starboard(self):
        self.assertIn("Nothing in sight to starboard", self.call(CmdLookAround(), "starboard"))

    def test_the_same_sail_is_found_by_compass_bearing(self):
        self.assertIn("port beam", self.call(CmdLookAround(), "north"))

    def test_relative_directions_turn_with_her(self):
        """
        Come round and the sail changes side without moving. That is the whole
        difference between a relative bearing and a true one.

        """
        self.assertIn("Nothing in sight", self.call(CmdLookAround(), "starboard"))
        self.hull.heading = WEST
        self.assertIn("beam", self.call(CmdLookAround(), "starboard"))

    def test_compass_directions_do_not(self):
        self.hull.heading = WEST
        self.assertIn("beam", self.call(CmdLookAround(), "north"))

    def test_looking_at_something_still_works(self):
        """
        Anything that is not a direction is looked at in the ordinary way, or
        this command would have broken `look` aboard every ship.

        """
        self.assertIn("Main Deck", self.call(CmdLookAround(), ""))

    def test_there_is_no_view_from_below(self):
        hold = create.create_object(ShipRoom, key="Hold")
        hold.vessel = self.hull
        hold.exposure = BELOW_WATERLINE
        self.char1.location = hold
        self.assertIn("cannot see the sea", self.call(CmdLookAround(), "fore"))


class TestKeepingAWatch(DirectionTestCase):
    """A standing watch, and what it reports."""

    def tick(self):
        """Advance the vessel one step so watches are stood."""
        self.hull.at_maritime_tick(1.0)

    def test_setting_a_watch_is_confirmed(self):
        self.assertIn("watch to port", self.call(CmdWatch(), "port"))

    def test_an_unknown_direction_is_refused(self):
        self.assertIn("Watch which way", self.call(CmdWatch(), "sideways"))

    def test_standing_down(self):
        self.call(CmdWatch(), "port")
        self.assertIn("stand down", self.call(CmdWatch(), "off"))

    def test_standing_down_without_a_watch(self):
        self.assertIn("not keeping a watch", self.call(CmdWatch(), "off"))

    def test_a_watch_cannot_be_kept_from_below(self):
        hold = create.create_object(ShipRoom, key="Hold")
        hold.vessel = self.hull
        hold.exposure = BELOW_WATERLINE
        self.char1.location = hold
        self.assertIn("cannot keep a watch", self.call(CmdWatch(), "port"))

    def test_a_contact_coming_into_view_is_reported(self):
        heard = []
        self.char1.msg = lambda text=None, **kwargs: heard.append(str(text))
        self.char1.db.maritime_watch = "port"
        self.tick()
        self.assertTrue(any("lifts over the horizon" in line for line in heard))

    def test_it_is_reported_once_and_not_every_tick(self):
        heard = []
        self.char1.msg = lambda text=None, **kwargs: heard.append(str(text))
        self.char1.db.maritime_watch = "port"
        for _ in range(5):
            self.tick()
        self.assertEqual(len([line for line in heard if "lifts over" in line]), 1)

    def test_a_contact_leaving_is_reported(self):
        self.char1.db.maritime_watch = "port"
        self.tick()
        heard = []
        self.char1.msg = lambda text=None, **kwargs: heard.append(str(text))
        self.other.maritime_position = WorldPosition(0.0, 90000.0)
        traffic().note(self.other, self.other.maritime_position)
        self.tick()
        self.assertTrue(any("sinks from sight" in line for line in heard))

    def test_a_watch_the_other_way_hears_nothing(self):
        heard = []
        self.char1.msg = lambda text=None, **kwargs: heard.append(str(text))
        self.char1.db.maritime_watch = "starboard"
        self.tick()
        self.assertFalse(any("lifts over the horizon" in line for line in heard))

    def test_a_watch_is_kept_from_where_the_watcher_stands(self):
        """
        One set at the masthead sees further than one set on deck, so the same
        contact can be news to one watcher and invisible to another aboard the
        same ship.

        """
        masthead = create.create_object(ShipRoom, key="Masthead")
        masthead.vessel = self.hull
        masthead.exposure = OPEN
        masthead.height_of_eye = 28.0

        self.other.air_draft = 28.0
        self.other.maritime_position = WorldPosition(0.0, 29800.0)
        traffic().note(self.other, self.other.maritime_position)

        on_deck, aloft = [], []
        self.char1.msg = lambda text=None, **kwargs: on_deck.append(str(text))
        self.char1.db.maritime_watch = "port"

        watcher = create.create_object(key="Lookout", location=masthead)
        watcher.msg = lambda text=None, **kwargs: aloft.append(str(text))
        watcher.db.maritime_watch = "port"

        self.tick()
        self.assertFalse(any("lifts over" in line for line in on_deck))
        self.assertTrue(any("lifts over" in line for line in aloft))


class TestScan(DirectionTestCase):
    """One sweep, all round."""

    def test_it_names_every_quarter(self):
        output = self.call(CmdScan(), "")
        for quarter in ("Ahead", "To starboard", "Astern", "To port"):
            self.assertIn(quarter, output)

    def test_empty_quarters_are_reported_as_empty(self):
        """
        A lookout who only mentions what he can see leaves you unable to tell
        "nothing there" from "nobody looked", and those are very different
        things to know before altering course.

        """
        self.assertIn("nothing", self.call(CmdScan(), ""))

    def test_a_contact_appears_in_its_own_quarter(self):
        output = self.call(CmdScan(), "")
        to_port = [line for line in output.splitlines() if "To port" in line]
        self.assertTrue(to_port)
        self.assertIn("Marigold", to_port[0])

    def test_it_says_how_far_it_can_see(self):
        self.assertIn("off:", self.call(CmdScan(), ""))

    def test_it_sweeps_from_where_you_stand(self):
        masthead = create.create_object(ShipRoom, key="Masthead")
        masthead.vessel = self.hull
        masthead.exposure = OPEN
        masthead.height_of_eye = 28.0
        self.other.air_draft = 28.0
        self.other.maritime_position = WorldPosition(0.0, 29800.0)
        traffic().note(self.other, self.other.maritime_position)

        self.assertIn("nothing", self.call(CmdScan(), ""))
        self.char1.location = masthead
        # Seen, but only as a sail - at that range she is not identifiable, and
        # the report says exactly as much as the range allows.
        self.assertIn("a sail", self.call(CmdScan(), ""))

    def test_there_is_no_scanning_from_below(self):
        hold = create.create_object(ShipRoom, key="Hold")
        hold.vessel = self.hull
        hold.exposure = BELOW_WATERLINE
        self.char1.location = hold
        self.assertIn("cannot see the sea", self.call(CmdScan(), ""))


class TestTheReportItself(DirectionTestCase):
    """What a contact line actually tells you."""

    def test_it_gives_both_bearings(self):
        """
        The relative one turns a head in the right direction; the true one goes
        on the chart and stays put when she comes round.

        """
        output = self.call(CmdLookAround(), "port")
        self.assertIn("port beam", output)
        self.assertIn("-", output)

    def test_it_says_what_she_is(self):
        self.assertIn("Marigold", self.call(CmdLookAround(), "port"))

    def test_it_gives_a_range(self):
        output = self.call(CmdLookAround(), "port")
        self.assertTrue(any(unit in output for unit in ("cable", "miles", "leagues")))

    def test_an_empty_sector_says_how_far_you_can_see(self):
        """
        Otherwise "nothing in sight" is unbounded, and a captain cannot tell an
        empty sea from a short horizon.

        """
        self.assertIn("horizon is", self.call(CmdLookAround(), "starboard"))
