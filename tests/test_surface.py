"""
Tests for what the sea says to someone in it.

The companion to `test_exterior`, which covers the same world seen from a deck. The
two exist separately because the answers differ, and are meant to. The difference is
not symmetrical: a swimmer sees a ship's masts a long way off, and from that ship
there is nothing on the water at all.

"""

from django.test import override_settings

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest

from ..bathymetry import MaritimeMapProvider
from ..messaging import WaterNarrator
from ..position import WorldPosition
from ..projection import OceanProjection
from ..traffic import traffic
from ..typeclasses import Flotsam, Vessel
from .base import EmptySeaMixin

HERE = WorldPosition(230.0, 310.0)


class Shallows(MaritimeMapProvider):
    """Ground a metre down, everywhere."""

    def terrain_z_at(self, position):
        return -1.0


class Beach(MaritimeMapProvider):
    """Dry land, everywhere."""

    def terrain_z_at(self, position):
        return 1.0


class Terse(WaterNarrator):
    """A game replacing the voice of the sea."""

    def surface(self):
        return ("Water.",)


class SurfaceTestCase(EmptySeaMixin, BaseEvenniaTest):
    """Shared setup: one swimmer, in the water."""

    def setUp(self):
        super().setUp()
        self.sea = OceanProjection()
        self.swimmer = create.create_object(Flotsam, key="a swimmer")
        self.room = self.sea.overboard(self.swimmer, HERE)

    def surface(self):
        """
        Returns:
            text (str): What the swimmer sees, looking around.

        """
        return self.room.return_appearance(self.swimmer)


class TestTheWater(SurfaceTestCase):
    """The sea itself, from surface level."""

    def test_a_flat_calm_lies_flat(self):
        self.assertIn("almost flat", self.surface())

    @override_settings(MARITIME_WIND_SPEED=20.0, MARITIME_WIND_BEARING=0.0)
    def test_a_gale_heaves(self):
        self.assertIn("heaves around you", self.surface())

    @override_settings(MARITIME_WIND_SPEED=20.0, MARITIME_WIND_BEARING=0.0)
    def test_a_gale_takes_the_tops_off_the_water(self):
        self.assertIn("takes the tops off", self.surface())

    def test_a_flat_calm_has_no_wind_to_report(self):
        self.assertIn("no wind at all", self.surface())

    @override_settings(MARITIME_WIND_SPEED=4.0, MARITIME_WIND_BEARING=90.0)
    def test_a_light_air_is_named_for_where_it_comes_from(self):
        self.assertIn("light air comes out of the east", self.surface())


class TestTheGround(SurfaceTestCase):
    """Whether there is anything to stand on."""

    def test_deep_water_offers_nothing(self):
        """A swimmer in deep water has taken no sounding and should be told nothing."""
        self.assertNotIn("bottom", self.surface())

    @override_settings(MARITIME_MAP_PROVIDER=f"{__name__}.Shallows")
    def test_shallow_water_can_be_stood_in(self):
        self.assertIn("Your feet find the bottom", self.surface())

    @override_settings(MARITIME_MAP_PROVIDER=f"{__name__}.Beach")
    def test_dry_ground_is_not_swimming_at_all(self):
        self.assertIn("not swimming at all", self.surface())


class TestWhatCanBeSeen(SurfaceTestCase):
    """The horizon, from a foot above the water."""

    def test_an_empty_sea_is_empty(self):
        self.assertIn("Nothing at all breaks the horizon", self.surface())

    def test_a_ship_close_by_is_seen(self):
        hull = create.create_object(Vessel, key="Test Sloop")
        hull.maritime_position = WorldPosition(HERE.x, HERE.y + 500.0)
        traffic().note(hull, hull.maritime_position)
        self.assertIn("lies to the north", self.surface())

    def test_her_masts_are_seen_long_past_the_swimmers_own_horizon(self):
        """
        The swimmer's horizon is barely a mile. She is four miles off and still
        in sight, because height beats the curve and hers is in her masts.

        """
        hull = create.create_object(Vessel, key="Test Sloop")
        hull.maritime_position = WorldPosition(HERE.x, HERE.y + 7000.0)
        traffic().note(hull, hull.maritime_position)
        self.assertNotIn("Nothing at all", self.surface())

    def test_something_low_at_the_same_range_is_not(self):
        """
        What is lost from the water is everything low. An open boat four miles
        off is gone, and so - from her - is the swimmer.

        """
        boat = create.create_object(Vessel, key="Ship's Boat")
        boat.air_draft = 1.0
        boat.maritime_position = WorldPosition(HERE.x, HERE.y + 7000.0)
        traffic().note(boat, boat.maritime_position)
        self.assertIn("Nothing at all breaks the horizon", self.surface())

    def test_a_ships_name_keeps_its_capitals(self):
        """`str.capitalize` lowercases the rest, and turned the Kittiwake into the kittiwake."""
        hull = create.create_object(Vessel, key="Kittiwake")
        hull.maritime_position = WorldPosition(HERE.x, HERE.y + 500.0)
        traffic().note(hull, hull.maritime_position)
        self.assertIn("The Kittiwake lies", self.surface())

    def test_a_phrase_that_is_not_a_name_still_opens_the_sentence(self):
        hull = create.create_object(Vessel, key="Test Sloop")
        hull.maritime_position = WorldPosition(HERE.x, HERE.y + 7000.0)
        traffic().note(hull, hull.maritime_position)
        self.assertIn("A vessel", self.surface())

    def test_bearings_are_compass_not_relative(self):
        """A body in the water has no head for a bearing to be relative to."""
        hull = create.create_object(Vessel, key="Test Sloop")
        hull.maritime_position = WorldPosition(HERE.x + 500.0, HERE.y)
        traffic().note(hull, hull.maritime_position)
        text = self.surface()
        self.assertIn("lies to the east", text)
        self.assertNotIn("bow", text)


class TestTheVoiceIsReplaceable(SurfaceTestCase):
    """One setting changes everything the sea says."""

    @override_settings(MARITIME_WATER_NARRATOR=f"{__name__}.Terse")
    def test_a_game_can_replace_it(self):
        self.assertEqual(self.surface(), "Water.")

    def test_the_default_is_used_otherwise(self):
        self.assertNotEqual(self.surface(), "Water.")


class TestSomethingWithNoPositionOfItsOwn(SurfaceTestCase):
    """A looker that resolves through the room rather than carrying its own position."""

    def test_it_falls_back_to_the_cell(self):
        """An ordinary character in the water resolves through the room to its centre."""
        self.char1.move_to(self.room, quiet=True, move_hooks=False)
        self.assertIn("open sea", self.room.return_appearance(self.char1))


class TestOneUnitFromTheWaterToo(SurfaceTestCase):
    """
    A swimmer sees a very short way and a very long way at once - a boat within
    hail, and a ship's masts hull-down beyond his own horizon. That spread is
    exactly where a per-value unit reads worst, and he is the person least able to
    spare the arithmetic.

    """

    def test_both_contacts_read_in_the_same_unit(self):
        near = create.create_object(Vessel, key="Ship's Boat")
        near.maritime_position = WorldPosition(HERE.x, HERE.y + 4300.0)
        traffic().note(near, near.maritime_position)

        far = create.create_object(Vessel, key="Kittiwake")
        far.air_draft = 60.0
        far.maritime_position = WorldPosition(HERE.x, HERE.y + 20000.0)
        traffic().note(far, far.maritime_position)

        text = self.surface()
        units = {word for word in ("cables", "miles", "leagues") if word in text}
        self.assertEqual(len(units), 1, text)

    def test_and_both_are_actually_in_sight(self):
        """Guards the test above: one contact could never mix units with itself."""
        near = create.create_object(Vessel, key="Ship's Boat")
        near.maritime_position = WorldPosition(HERE.x, HERE.y + 4300.0)
        traffic().note(near, near.maritime_position)

        far = create.create_object(Vessel, key="Kittiwake")
        far.air_draft = 60.0
        far.maritime_position = WorldPosition(HERE.x, HERE.y + 20000.0)
        traffic().note(far, far.maritime_position)

        text = self.surface()
        self.assertEqual(text.count("lies to the north"), 2, text)


class TestNamesThatCarryTheirOwnArticle(SurfaceTestCase):
    """
    "The the Kittiwake" - seen live in a sweep, because a builder had put the
    article in the name and the narrator adds one of its own.

    """

    def named(self, key):
        """
        Returns:
            text (str): What the swimmer says about a ship of that name.

        """
        hull = create.create_object(Vessel, key=key)
        hull.maritime_position = WorldPosition(HERE.x, HERE.y + 500.0)
        traffic().note(hull, hull.maritime_position)
        return self.surface()

    def test_a_name_with_the_in_it_is_not_given_another(self):
        self.assertNotIn("the the", self.named("the Kittiwake").lower())

    def test_and_is_still_named(self):
        self.assertIn("Kittiwake", self.named("the Kittiwake"))

    def test_an_ordinary_name_still_gets_one(self):
        self.assertIn("The Marigold lies", self.named("Marigold"))

    def test_a_name_beginning_with_an_indefinite_article_is_left_alone(self):
        """A ship's boat may well be "a launch"; she is not "the a launch"."""
        self.assertNotIn("the a ", self.named("a launch").lower())
