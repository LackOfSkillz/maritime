"""
Tests for the wind, the sea it raises, and what you can see through it.

"""

from django.test import override_settings

from evennia.utils import create
from evennia.utils.test_resources import (
    BaseEvenniaCommandTest,
    BaseEvenniaTest,
    BaseEvenniaTestCase,
)

from ..commands import CmdWeather
from ..motion import HelmOrders, MotionLimits
from ..position import EAST, WEST, WorldPosition
from ..rooms import ShipRoom
from ..sailing import WindVector
from ..typeclasses import Vessel
from ..vessel import OPEN
from ..weather import (
    CALM,
    PHENOMENAL,
    SEA_STATES,
    WAVE_HEIGHTS,
    FlatWeatherProvider,
    MaritimeWeatherProvider,
    Weather,
    sea_drag,
    sea_state_for,
)
from .base import EmptySeaMixin

HERE = WorldPosition(0.0, 0.0)


class Gale(MaritimeWeatherProvider):
    """A game's own weather: a westerly gale with a high sea and thick air."""

    def weather_at(self, position, game_time):
        return Weather(
            wind=WindVector(bearing=WEST, speed=20.0),
            visibility=800.0,
            sea_state="high",
        )


class TestSeaStateForWind(BaseEvenniaTestCase):
    """The sea a steady wind raises."""

    def test_no_wind_no_sea(self):
        self.assertEqual(sea_state_for(0.0), CALM)

    def test_a_breeze_raises_a_slight_sea(self):
        self.assertEqual(sea_state_for(6.0), "slight")

    def test_a_gale_raises_a_high_one(self):
        self.assertEqual(sea_state_for(20.0), "very rough")

    def test_a_hurricane_tops_the_scale(self):
        self.assertEqual(sea_state_for(60.0), PHENOMENAL)

    def test_more_wind_never_means_less_sea(self):
        order = [SEA_STATES.index(sea_state_for(speed)) for speed in range(0, 60)]
        self.assertEqual(order, sorted(order))

    def test_every_wind_speed_raises_a_named_sea(self):
        for tenths in range(0, 800):
            self.assertIn(sea_state_for(tenths / 10.0), SEA_STATES)


class TestSeaDrag(BaseEvenniaTestCase):
    """What a heavy sea costs her."""

    def test_a_calm_costs_nothing(self):
        self.assertEqual(sea_drag(CALM), 0.0)

    def test_a_rough_sea_costs_something(self):
        self.assertGreater(sea_drag("rough"), 0.0)

    def test_a_worse_sea_costs_more(self):
        self.assertGreater(sea_drag("high"), sea_drag("moderate"))

    def test_it_never_stops_her_outright(self):
        """
        The danger is meant to come from the lee shore and the flooding, not from
        an arithmetic wall that makes heavy weather unplayable.

        """
        self.assertLess(sea_drag(PHENOMENAL), 1.0)

    def test_an_unknown_sea_costs_nothing(self):
        self.assertEqual(sea_drag("biblical"), 0.0)


class TestWeather(BaseEvenniaTestCase):
    """Wind, sea and visibility arriving together."""

    def test_a_flat_provider_returns_what_it_was_given(self):
        provider = FlatWeatherProvider(wind=WindVector(bearing=EAST, speed=9.0), visibility=5000.0)
        weather = provider.weather_at(HERE, 0.0)
        self.assertAlmostEqual(weather.wind.speed, 9.0)
        self.assertAlmostEqual(weather.visibility, 5000.0)

    def test_its_sea_follows_its_wind_by_default(self):
        """
        So a game that sets a gale gets a gale's sea without having to know this
        module exists.

        """
        provider = FlatWeatherProvider(wind=WindVector(speed=20.0))
        self.assertEqual(provider.weather_at(HERE, 0.0).sea_state, sea_state_for(20.0))

    def test_a_sea_can_be_set_against_the_wind(self):
        """
        Waves run on after the wind drops, so a calm with a heavy leftover swell
        is a real morning at sea and the provider must allow it.

        """
        provider = FlatWeatherProvider(wind=WindVector(speed=0.0), sea_state="rough")
        self.assertEqual(provider.weather_at(HERE, 0.0).sea_state, "rough")

    def test_wave_height_follows_the_state(self):
        self.assertLess(
            Weather(sea_state="slight").wave_height, Weather(sea_state="high").wave_height
        )

    def test_the_worst_sea_has_no_upper_bound(self):
        self.assertAlmostEqual(Weather(sea_state=PHENOMENAL).wave_height, WAVE_HEIGHTS[-1])

    def test_the_base_provider_must_be_implemented(self):
        with self.assertRaises(NotImplementedError):
            MaritimeWeatherProvider().weather_at(HERE, 0.0)


class WeatherTestCase(EmptySeaMixin, BaseEvenniaTest):
    """A hull under way, with weather over her."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Test Sloop")
        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.deck.vessel = self.hull
        self.deck.exposure = OPEN
        self.hull.maritime_position = HERE
        self.hull.motion_limits = MotionLimits(max_speed=10.0, acceleration=100.0, turn_rate=8.0)
        self.hull.heading = EAST
        self.hull.speed = 5.0
        self.hull.orders = HelmOrders(heading=EAST, speed=5.0)


class TestWeatherReachesTheVessel(WeatherTestCase):
    """The seam, from the hull's end."""

    def test_the_old_settings_still_work(self):
        """
        Those settings were the whole of weather before this existed. A game that
        set them should not have to learn about providers to keep the weather it
        already had.

        """
        with override_settings(MARITIME_WIND_SPEED=9.0, MARITIME_WIND_BEARING=WEST):
            self.assertAlmostEqual(self.hull.wind_here().speed, 9.0)

    def test_the_sea_follows_from_them(self):
        with override_settings(MARITIME_WIND_SPEED=20.0):
            self.assertEqual(self.hull.sea_here(), sea_state_for(20.0))

    def test_a_game_can_supply_its_own_weather(self):
        path = f"{Gale.__module__}.Gale"
        with override_settings(MARITIME_WEATHER_PROVIDER=path):
            self.assertAlmostEqual(self.hull.wind_here().speed, 20.0)
            self.assertEqual(self.hull.sea_here(), "high")

    def test_visibility_comes_from_the_same_weather(self):
        """
        One sampling. Reading the wind from one place and the visibility from
        another is how a system ends up with a gale you can see forever across.

        """
        from ..environment import visibility_at

        path = f"{Gale.__module__}.Gale"
        with override_settings(MARITIME_WEATHER_PROVIDER=path):
            self.assertAlmostEqual(visibility_at(HERE), 800.0)

    def test_an_unlaunched_vessel_finds_a_flat_calm(self):
        """
        A hull on the stocks is nowhere, so there is no weather over her.

        Tested against a provider that would give a different answer if asked.
        With the flat one it reports a calm whether the guard fires or not, which
        is exactly what mutation testing walked through the first time: a hull
        with no position would have been handed a `None` to look up weather at.

        """
        idle = create.create_object(Vessel, key="On The Stocks")
        path = f"{Gale.__module__}.Gale"
        with override_settings(MARITIME_WEATHER_PROVIDER=path):
            self.assertEqual(self.hull.sea_here(), "high")
            self.assertEqual(idle.sea_here(), CALM)


class TestASeaTakesHerWay(WeatherTestCase):
    """What heavy water costs a passage."""

    def run_east(self, **settings):
        """
        Args:
            **settings: Overrides for the run.

        Returns:
            easting (float): How far east she got.

        """
        self.hull.maritime_position = HERE
        base = {"MARITIME_DEFAULT_DEPTH": 1000.0, "MARITIME_MAP_PROVIDER": ""}
        base.update(settings)
        with override_settings(**base):
            for _ in range(10):
                self.hull.at_maritime_tick(60.0)
        return self.hull.maritime_position.x

    def test_a_calm_passage_is_the_baseline(self):
        self.assertGreater(self.run_east(MARITIME_SEA_STATE=CALM), 2500.0)

    def test_a_heavy_sea_slows_her(self):
        calm = self.run_east(MARITIME_SEA_STATE=CALM)
        heavy = self.run_east(MARITIME_SEA_STATE="high")
        self.assertLess(heavy, calm)

    def test_but_never_stops_her(self):
        self.assertGreater(self.run_east(MARITIME_SEA_STATE=PHENOMENAL), 0.0)


class TestTheDeckDescribesTheSea(WeatherTestCase):
    """What a weather deck says about the water."""

    def view(self):
        """
        Returns:
            text (str): The exterior, as one string.

        """
        return " ".join(self.hull.narrator.exterior(self.deck))

    def test_a_rough_sea_is_described(self):
        with override_settings(MARITIME_SEA_STATE="rough"):
            self.assertIn("rough", self.view())

    def test_a_calm_is_not_remarked_on(self):
        """
        The absence of waves is not news, and repeating it every time somebody
        looks is how ambient text becomes wallpaper.

        """
        with override_settings(MARITIME_SEA_STATE=CALM, MARITIME_WIND_SPEED=0.0):
            self.assertNotIn("sea", self.view().lower().replace("the sea", ""))

    def test_a_high_sea_says_she_labours(self):
        with override_settings(MARITIME_SEA_STATE="high"):
            self.assertIn("labours", self.view())


class TestCmdWeather(EmptySeaMixin, BaseEvenniaCommandTest):
    """Asking what the glass says."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Test Sloop")
        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.deck.vessel = self.hull
        self.deck.exposure = OPEN
        self.hull.maritime_position = HERE
        self.char1.location = self.deck

    def test_it_names_the_wind_by_force(self):
        with override_settings(MARITIME_WIND_SPEED=20.0):
            self.assertIn("force 8", self.call(CmdWeather(), ""))

    def test_it_reports_the_sea(self):
        with override_settings(MARITIME_SEA_STATE="rough"):
            self.assertIn("rough", self.call(CmdWeather(), ""))

    def test_it_reports_visibility(self):
        self.assertIn("Visibility", self.call(CmdWeather(), ""))

    def test_an_unlaunched_vessel_has_no_weather(self):
        self.hull.db.maritime_position = None
        self.hull.ndb.maritime_position = None
        self.assertIn("not afloat", self.call(CmdWeather(), ""))
