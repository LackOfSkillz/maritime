"""
Tests for what a static room says about a moving world.

"""

from django.test import override_settings

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest, BaseEvenniaTestCase

from ..messaging import BEAUFORT_NAMES
from ..motion import HelmOrders, MotionLimits
from ..position import EAST, SOUTH, WEST, WorldPosition
from ..rooms import PortRoom, ShipRoom
from ..sailing import BEAUFORT_LIMITS, beaufort_force
from ..traffic import traffic
from ..typeclasses import Vessel
from ..vessel import BELOW_WATERLINE, OPEN
from .base import EmptySeaMixin


class TestBeaufort(BaseEvenniaTestCase):
    """Naming a wind by what it does."""

    def test_a_flat_calm(self):
        self.assertEqual(beaufort_force(0.0), 0)

    def test_a_fresh_breeze(self):
        self.assertEqual(beaufort_force(9.0), 5)

    def test_a_gale(self):
        self.assertEqual(beaufort_force(18.0), 8)

    def test_the_scale_tops_out(self):
        """Force 12 has no upper bound, and a hurricane is a hurricane."""
        self.assertEqual(beaufort_force(200.0), 12)

    def test_it_never_indexes_past_its_names(self):
        self.assertEqual(len(BEAUFORT_NAMES), len(BEAUFORT_LIMITS) + 1)

    def test_every_speed_has_a_name(self):
        for tenths in range(0, 500):
            self.assertTrue(BEAUFORT_NAMES[beaufort_force(tenths / 10.0)])

    def test_the_bands_are_uneven(self):
        """
        Beaufort defined the scale by what a full-rigged ship could carry, not by
        arithmetic, which is why the bands widen as they climb.

        """
        widths = [
            BEAUFORT_LIMITS[i + 1] - BEAUFORT_LIMITS[i] for i in range(len(BEAUFORT_LIMITS) - 1)
        ]
        self.assertGreater(widths[-1], widths[0])


class ExteriorTestCase(EmptySeaMixin, BaseEvenniaTest):
    """A ship with a deck, a masthead and a hold."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Test Sloop")
        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.deck.vessel = self.hull
        self.deck.exposure = OPEN
        self.hold = create.create_object(ShipRoom, key="Cargo Hold")
        self.hold.vessel = self.hull
        self.hold.exposure = BELOW_WATERLINE
        self.hull.maritime_position = WorldPosition(0.0, 0.0)
        self.hull.motion_limits = MotionLimits(max_speed=10.0, acceleration=2.0, turn_rate=8.0)
        self.hull.heading = EAST
        self.hull.speed = 4.0
        self.hull.orders = HelmOrders(heading=EAST, speed=4.0)
        self.hull.air_draft = 12.0

    def view(self, room=None):
        """
        Args:
            room (ShipRoom, optional): Where to look from.

        Returns:
            text (str): The exterior, as one string.

        """
        return " ".join(self.hull.narrator.exterior(room or self.deck))


class TestTheViewOutside(ExteriorTestCase):
    """What is happening, as against what is nailed down."""

    def test_a_ship_under_way_says_so(self):
        self.assertIn("runs east", self.view())

    def test_a_ship_with_no_way_on_says_so(self):
        self.hull.speed = 0.0
        self.assertIn("no way on her", self.view())

    def test_a_ship_at_anchor_says_so(self):
        self.hull.anchored = True
        self.assertIn("anchor", self.view())

    def test_a_ship_aground_says_so(self):
        self.hull.aground = True
        self.assertIn("hard on the ground", self.view())

    def test_the_wind_is_named_by_its_force(self):
        with override_settings(MARITIME_WIND_SPEED=9.0, MARITIME_WIND_BEARING=WEST):
            self.assertIn("fresh breeze", self.view())

    def test_a_calm_is_described_as_one(self):
        with override_settings(MARITIME_WIND_SPEED=0.0):
            self.assertIn("not a breath", self.view())

    def test_the_wind_is_named_for_where_it_comes_from(self):
        with override_settings(MARITIME_WIND_SPEED=9.0, MARITIME_WIND_BEARING=WEST):
            self.assertIn("out of the west", self.view())

    def test_a_running_current_is_mentioned(self):
        with override_settings(MARITIME_CURRENT_SET=SOUTH, MARITIME_CURRENT_DRIFT=1.0):
            self.assertIn("setting south", self.view())

    def test_slack_water_is_not_mentioned(self):
        """Saying "there is no current" every time somebody looks is noise."""
        self.assertNotIn("setting", self.view())

    def test_an_empty_sea_says_so(self):
        self.assertIn("Nothing breaks the horizon", self.view())

    def test_a_sail_in_sight_is_reported_with_a_bearing(self):
        other = create.create_object(Vessel, key="Marigold")
        other.air_draft = 12.0
        other.maritime_position = WorldPosition(0.0, 1000.0)
        traffic().note(other, other.maritime_position)
        self.assertIn("A sail stands", self.view())
        self.assertIn("port beam", self.view())

    def test_more_than_one_is_counted(self):
        for index in range(3):
            other = create.create_object(Vessel, key=f"Sail {index}")
            other.air_draft = 12.0
            other.maritime_position = WorldPosition(float(500 + index * 100), 0.0)
            traffic().note(other, other.maritime_position)
        self.assertIn("2 more sails besides", self.view())


class TestWhereYouStandDecidesWhatYouSee(ExteriorTestCase):
    """The height-of-eye model, showing up in an ordinary look."""

    def setUp(self):
        super().setUp()
        self.masthead = create.create_object(ShipRoom, key="Masthead")
        self.masthead.vessel = self.hull
        self.masthead.exposure = OPEN
        self.masthead.height_of_eye = 28.0

        self.other = create.create_object(Vessel, key="Marigold")
        self.other.air_draft = 28.0
        self.other.maritime_position = WorldPosition(0.0, 29800.0)
        traffic().note(self.other, self.other.maritime_position)

    def test_the_deck_sees_nothing(self):
        self.assertIn("Nothing breaks the horizon", self.view(self.deck))

    def test_the_masthead_sees_her(self):
        """
        The same ship at the same instant, and the two views honestly disagree.
        That is the whole return on modelling height of eye at all.

        """
        self.assertIn("A sail stands", self.view(self.masthead))


class TestTheRoomItself(ExteriorTestCase):
    """What `look` actually produces."""

    def test_a_weather_deck_shows_the_sea(self):
        appearance = self.deck.return_appearance(self.char1)
        self.assertIn("runs east", appearance)

    def test_the_static_description_is_still_there(self):
        self.deck.db.desc = "Weathered planking runs fore and aft."
        appearance = self.deck.return_appearance(self.char1)
        self.assertIn("Weathered planking", appearance)

    def test_there_is_no_view_from_the_hold(self):
        appearance = self.hold.return_appearance(self.char1)
        self.assertNotIn("runs east", appearance)

    def test_a_room_with_no_vessel_is_left_alone(self):
        orphan = create.create_object(ShipRoom, key="Adrift")
        orphan.exposure = OPEN
        self.assertNotIn("horizon", orphan.return_appearance(self.char1))

    def test_an_unlaunched_vessel_shows_no_sea(self):
        """
        A hull on the stocks is not at sea, and a deck that described the horizon
        from a shipyard would be lying.

        """
        yard = create.create_object(Vessel, key="On The Stocks")
        deck = create.create_object(ShipRoom, key="Her Deck")
        deck.vessel = yard
        deck.exposure = OPEN
        self.assertNotIn("horizon", deck.return_appearance(self.char1))

    def test_a_quay_is_not_a_ship(self):
        """PortRoom is a room in its own right and has no exterior of this kind."""
        quay = create.create_object(PortRoom, key="North Quay")
        quay.maritime_position = WorldPosition(0.0, 0.0)
        self.assertNotIn("horizon", quay.return_appearance(self.char1))
