"""
Tests for the sea that moves.

The thing worth testing here is not that the arithmetic runs. It is that the *behaviour* a
game depends on emerges from the model rather than being written into it - because the whole
argument for building a tide out of constituents, instead of a sine wave with a fortnightly
multiplier bolted on, is that the interesting behaviour comes free and stays consistent.

So the tests ask for behaviour and never for coefficients:

    springs and neaps       a fortnightly cycle nobody scripted
    the lunar day           high water slipping later against the clock
    the table agrees        predictions that match the water they predict
    a game gets its numbers  the ranges a designer asked for, exactly

A test that checked `constituents[0].amplitude_m` would pass on a model with the cycle
hard-coded, which is precisely the model this is not.
"""

import math

from evennia.utils.test_resources import BaseEvenniaTestCase

from ..bathymetry import DATUM, MaritimeMapProvider
from ..position import WorldPosition
from ..tides import (
    M2_HOURS,
    SPRING_NEAP_DAYS,
    Constituent,
    HarmonicTide,
)

HOUR = 3600.0
DAY = 24.0 * HOUR


def daily_range(tide, day):
    """
    Returns:
        range (float): How far the water moved on that day, in metres.

    """
    heights = [tide.height_at(day * DAY + step * 600.0) for step in range(int(DAY / 600.0))]
    return max(heights) - min(heights)


class TestAGameGetsTheNumbersItAskedFor(BaseEvenniaTestCase):
    """
    A designer knows their harbour has four metres at springs, because that is what a tide
    table says. Nobody knows their harbour's M2 amplitude, so the interface takes the
    former and works out the latter - and it has to come back exact, not close.
    """

    def test_the_ranges_come_back_as_asked(self):
        tide = HarmonicTide.semidiurnal(spring_range_m=3.8, neap_range_m=1.6)
        self.assertAlmostEqual(tide.spring_range(), 3.8, places=6)
        self.assertAlmostEqual(tide.neap_range(), 1.6, places=6)

    def test_over_a_range_of_harbours(self):
        for springs, neaps in ((10.0, 4.5), (1.2, 0.9), (6.0, 6.0), (0.4, 0.1)):
            tide = HarmonicTide.semidiurnal(springs, neaps)
            self.assertAlmostEqual(tide.spring_range(), springs, places=6)
            self.assertAlmostEqual(tide.neap_range(), neaps, places=6)

    def test_neaps_larger_than_springs_is_refused(self):
        """
        The words mean something: springs are when the two tides add and neaps when they
        subtract, so a neap range larger than the spring one describes no sea that exists.
        Silently solving it would hand back a negative solar amplitude and a tide that ran
        backwards through its fortnight.

        """
        with self.assertRaises(ValueError):
            HarmonicTide.semidiurnal(spring_range_m=2.0, neap_range_m=3.0)

    def test_a_harbour_can_sit_off_the_datum(self):
        tide = HarmonicTide.semidiurnal(2.0, 1.0, mean_level_m=5.0)
        self.assertAlmostEqual(tide.height_at(0.0) - 5.0, tide.height_at(0.0) - tide.mean_level_m)
        self.assertGreater(min(tide.height_at(t * 600.0) for t in range(300)), 3.0)


class TestTheFortnightIsNotScripted(BaseEvenniaTestCase):
    """
    The heart of it.

    Nothing in the model checks a calendar, counts days, or knows what a spring tide is. Two
    waves turn at slightly different rates and drift in and out of step, and a fortnightly
    cycle is what that looks like from the beach.
    """

    def setUp(self):
        self.tide = HarmonicTide.semidiurnal(spring_range_m=4.0, neap_range_m=1.5)

    def test_the_range_varies_from_day_to_day(self):
        ranges = [daily_range(self.tide, day) for day in range(30)]
        self.assertGreater(max(ranges) - min(ranges), 1.5, "the tide barely changes over a month")

    def test_the_biggest_and_smallest_are_a_week_apart(self):
        """
        Springs to neaps is half the beat, and the beat is the two periods against each
        other. Nobody wrote 14.77 anywhere in the arithmetic.

        """
        ranges = [daily_range(self.tide, day) for day in range(30)]
        biggest = max(range(15), key=lambda day: ranges[day])
        smallest = min(range(15), key=lambda day: ranges[day])
        self.assertAlmostEqual(abs(biggest - smallest), SPRING_NEAP_DAYS / 2.0, delta=1.5)

    def test_and_it_comes_round_again_a_fortnight_later(self):
        """
        Consecutive peaks, found as peaks. Splitting the month in half and taking the
        largest day of each half compares whichever springs happen to fall there - over
        forty days that picked day 0 and day 29, which are two cycles apart and looked like
        a twenty-nine day fortnight.

        """
        ranges = [daily_range(self.tide, day) for day in range(45)]
        springs = [
            day
            for day in range(1, len(ranges) - 1)
            if ranges[day] > ranges[day - 1] and ranges[day] >= ranges[day + 1]
        ]
        self.assertGreaterEqual(len(springs), 2, "no fortnightly cycle to measure")
        for sooner, later in zip(springs, springs[1:]):
            self.assertAlmostEqual(later - sooner, SPRING_NEAP_DAYS, delta=2.0)

    def test_a_tide_with_no_solar_wave_has_no_fortnight(self):
        """
        The control. If the cycle came from anywhere but the beat, it would survive
        removing the wave it beats against.

        """
        lunar = HarmonicTide((Constituent("M2", M2_HOURS, 1.5),))
        ranges = [daily_range(lunar, day) for day in range(30)]
        self.assertLess(max(ranges) - min(ranges), 0.05, "a single wave produced a cycle")


class TestTheLunarDaySlips(BaseEvenniaTestCase):
    """
    High water is about fifty minutes later each day, because the moon takes a little over
    twenty-four hours to come round again. It is the most-noticed fact about tides and it
    falls out of one period not being twenty-four hours.
    """

    def test_high_water_comes_later_each_day(self):
        tide = HarmonicTide.semidiurnal(4.0, 1.5)
        first = tide.next_high_water(0.0)[0]
        # The high water about a day later.
        later = tide.next_high_water(first + 20.0 * HOUR)[0]
        slip = (later - first) - DAY
        self.assertGreater(slip, 20.0 * 60.0, "high water did not slip against the clock")
        self.assertLess(slip, 80.0 * 60.0, "high water slipped further than a lunar day allows")


class TestTheTableAgreesWithTheWater(BaseEvenniaTestCase):
    """
    A tide table that disagrees with the sea is worse than none, because a captain plans
    against it. These search the same function the water is drawn from, so the only way they
    can disagree is a bug in the search - which is what this is for.
    """

    def setUp(self):
        self.tide = HarmonicTide.semidiurnal(4.0, 1.5)

    def test_a_predicted_high_water_really_is_the_highest_thing_near_it(self):
        when, height = self.tide.next_high_water(0.0)
        for offset in (-3600.0, -600.0, -60.0, 60.0, 600.0, 3600.0):
            self.assertLessEqual(self.tide.height_at(when + offset), height + 1e-6)

    def test_and_a_low_water_the_lowest(self):
        when, height = self.tide.next_low_water(0.0)
        for offset in (-3600.0, -600.0, -60.0, 60.0, 600.0, 3600.0):
            self.assertGreaterEqual(self.tide.height_at(when + offset), height - 1e-6)

    def test_the_predicted_height_is_the_height_at_that_time(self):
        when, height = self.tide.next_high_water(0.0)
        self.assertAlmostEqual(self.tide.height_at(when), height, places=6)

    def test_a_table_alternates_high_and_low(self):
        states = [state for _, _, state in self.tide.table(0.0, entries=6)]
        self.assertEqual(len(states), 6)
        for sooner, later in zip(states, states[1:]):
            self.assertNotEqual(sooner, later, "two high waters in a row")

    def test_and_runs_forwards(self):
        times = [when for when, _, _ in self.tide.table(0.0, entries=6)]
        self.assertEqual(times, sorted(times))

    def test_turns_come_about_six_hours_apart(self):
        times = [when for when, _, _ in self.tide.table(0.0, entries=6)]
        for sooner, later in zip(times, times[1:]):
            self.assertAlmostEqual((later - sooner) / HOUR, 6.2, delta=1.2)

    def test_a_tide_with_no_waves_predicts_nothing_rather_than_lying(self):
        """A flat sea has no high water, and inventing one would be the worst answer."""
        self.assertIsNone(HarmonicTide(()).next_high_water(0.0))
        self.assertEqual(HarmonicTide(()).table(0.0), ())

    def test_asking_from_a_later_time_gives_a_later_answer(self):
        first = self.tide.next_high_water(0.0)[0]
        second = self.tide.next_high_water(first + 60.0)[0]
        self.assertGreater(second, first)


class TestWhetherItIsMaking(BaseEvenniaTestCase):
    """
    The question a grounded hull asks: she comes off on a making tide and settles harder on
    a falling one.
    """

    def setUp(self):
        self.tide = HarmonicTide.semidiurnal(4.0, 1.5)
        self.where = WorldPosition(0.0, 0.0)

    def test_it_is_making_just_after_low_water(self):
        low = self.tide.next_low_water(0.0)[0]
        self.assertTrue(self.tide.is_rising(self.where, low + 600.0))

    def test_and_falling_just_after_high(self):
        high = self.tide.next_high_water(0.0)[0]
        self.assertFalse(self.tide.is_rising(self.where, high + 600.0))


class TestTheDiurnalInequality(BaseEvenniaTestCase):
    """
    Where the daily constituents are large the two high waters of a day differ in height,
    so "wait for high water" stops being a single instruction - one of them may float her
    over the bar and the other may not.
    """

    def test_a_mixed_tide_reports_the_form_factor_it_was_given(self):
        for form in (0.4, 0.9, 2.0):
            tide = HarmonicTide.mixed(3.0, 1.2, form=form)
            self.assertAlmostEqual(tide.form_factor(), form, places=6)

    def test_and_describes_itself_the_way_a_pilot_book_would(self):
        self.assertEqual(HarmonicTide.semidiurnal(3.0, 1.2).describes(), "semidiurnal")
        self.assertEqual(
            HarmonicTide.mixed(3.0, 1.2, form=0.8).describes(), "mixed, mainly semidiurnal"
        )
        self.assertEqual(
            HarmonicTide.mixed(3.0, 1.2, form=2.0).describes(), "mixed, mainly diurnal"
        )
        self.assertEqual(HarmonicTide.mixed(3.0, 1.2, form=4.0).describes(), "diurnal")

    def test_the_two_daily_highs_differ_when_they_should(self):
        """
        The behaviour, not the coefficient. A semidiurnal tide's two highs are nearly
        alike; a mixed one's are not, and that is the whole difference.

        """

        def spread(tide):
            highs = []
            when = 0.0
            while len(highs) < 2:
                found = tide.next_high_water(when)
                highs.append(found[1])
                when = found[0] + 600.0
            return abs(highs[0] - highs[1])

        self.assertLess(spread(HarmonicTide.semidiurnal(3.0, 1.2)), 0.25)
        self.assertGreater(spread(HarmonicTide.mixed(3.0, 1.2, form=1.5)), 0.4)


class TestTheTideTravels(BaseEvenniaTestCase):
    """
    A tidal wave is a wave: high water reaches one end of a coast before the other. Optional,
    because a small game does not care and a coast three hundred miles long does.
    """

    def test_without_a_progression_the_sea_turns_everywhere_at_once(self):
        tide = HarmonicTide.semidiurnal(4.0, 1.5)
        here = tide.surface_z_at(WorldPosition(0.0, 0.0), 5000.0)
        far = tide.surface_z_at(WorldPosition(200000.0, 0.0), 5000.0)
        self.assertAlmostEqual(here, far, places=9)

    def test_the_far_end_sees_what_the_near_end_saw_earlier(self):
        """
        The property itself, and it holds exactly rather than approximately: running the
        tide later up-coast is the same arithmetic as running the clock earlier here.

        """
        tide = HarmonicTide.semidiurnal(4.0, 1.5, progression=(0.0, 10.0))
        south, north = WorldPosition(0.0, 0.0), WorldPosition(0.0, 100000.0)
        for step in range(200):
            when = step * 600.0
            self.assertAlmostEqual(
                tide.surface_z_at(north, when),
                tide.surface_z_at(south, when - 10000.0),
                places=9,
            )

    def test_and_a_crest_reaches_the_far_end_later(self):
        """
        The same crest, followed up the coast. Comparing each end's *next* high water after
        one epoch compares different crests - the far end's next one is often the one that
        passed the near end before the search began, which reads as the tide arriving nine
        hours early.

        """
        tide = HarmonicTide.semidiurnal(4.0, 1.5, progression=(0.0, 10.0))
        south, north = WorldPosition(0.0, 0.0), WorldPosition(0.0, 100000.0)
        crest = tide.next_high_water(0.0, south)[0]
        # Search from an hour past it, so the crest found up-coast is that same one.
        same = tide.next_high_water(crest + 3600.0, north)[0]
        self.assertAlmostEqual(same - crest, 10000.0, delta=120.0)

    def test_a_wave_that_does_not_travel_is_refused(self):
        with self.assertRaises(ValueError):
            HarmonicTide.semidiurnal(4.0, 1.5, progression=(90.0, 0.0))


class TestItIsAWorkingProviderAndNothingSpecial(BaseEvenniaTestCase):
    """
    It has to be usable exactly where `FlatTideProvider` is, or it is a nice model that no
    game can install.
    """

    def test_a_map_provider_takes_it_and_depths_move(self):
        class Shelf(MaritimeMapProvider):
            def terrain_z_at(self, position):
                return -3.0

        world = Shelf(tide_provider=HarmonicTide.semidiurnal(4.0, 1.5))
        where = WorldPosition(0.0, 0.0)
        depths = [world.water_depth_at(where, step * 600.0) for step in range(80)]
        self.assertGreater(max(depths) - min(depths), 1.5, "the depth did not follow the tide")

    def test_and_the_shoreline_moves_with_it(self):
        """
        The claim `bathymetry` makes: the shoreline is where terrain crosses the surface,
        so it moves on its own without any terrain changing.

        """

        class Foreshore(MaritimeMapProvider):
            def terrain_z_at(self, position):
                return -1.0

        world = Foreshore(tide_provider=HarmonicTide.semidiurnal(4.0, 1.5))
        where = WorldPosition(0.0, 0.0)
        wet = [world.is_submerged_at(where, step * 600.0) for step in range(80)]
        self.assertIn(True, wet)
        self.assertIn(False, wet, "ground a metre down never dried on a four-metre tide")

    def test_the_datum_is_still_the_datum(self):
        """Mean level defaults to the datum, so a game that adds a tide does not silently
        raise or lower its whole sea."""
        tide = HarmonicTide.semidiurnal(4.0, 1.5)
        self.assertEqual(tide.mean_level_m, DATUM)
        average = sum(tide.height_at(step * 600.0) for step in range(4000)) / 4000.0
        self.assertAlmostEqual(average, DATUM, delta=0.05)

    def test_sampling_it_is_cheap(self):
        """
        Every depth query in the world goes through this. A tide that cost real time would
        show up as the whole simulation being slow rather than as a slow tide.

        """
        import time

        tide = HarmonicTide.mixed(4.0, 1.5, form=0.8)
        where = WorldPosition(0.0, 0.0)
        start = time.perf_counter()
        for step in range(20000):
            tide.surface_z_at(where, step * 60.0)
        each = (time.perf_counter() - start) / 20000.0 * 1e6
        self.assertLess(each, 20.0, f"a tide sample cost {each:.2f} us")

    def test_it_says_what_it_is(self):
        self.assertIn("springs", repr(HarmonicTide.semidiurnal(4.0, 1.5)))
        self.assertIn("semidiurnal", repr(HarmonicTide.semidiurnal(4.0, 1.5)))


class TestTheMathsIsTheMathsWeMeantToWrite(BaseEvenniaTestCase):
    """
    A few facts about constituents that are cheap to check and expensive to get wrong.
    """

    def test_a_constituent_repeats_after_its_period(self):
        wave = Constituent("M2", M2_HOURS, 1.5)
        self.assertAlmostEqual(wave.height_at(0.0), wave.height_at(M2_HOURS * HOUR), places=6)

    def test_amplitude_is_half_the_range(self):
        """The factor of two that catches everybody: a table prints the range, the model
        holds the amplitude."""
        wave = Constituent("M2", M2_HOURS, 1.5)
        heights = [wave.height_at(step * 60.0) for step in range(1000)]
        self.assertAlmostEqual(max(heights) - min(heights), 3.0, places=3)

    def test_phase_moves_it_and_nothing_else(self):
        plain = Constituent("M2", M2_HOURS, 1.5)
        shifted = Constituent("M2", M2_HOURS, 1.5, phase_deg=90.0)
        quarter = M2_HOURS * HOUR / 4.0
        self.assertAlmostEqual(plain.height_at(quarter), shifted.height_at(2.0 * quarter), places=4)

    def test_a_tide_with_only_daily_waves_is_infinitely_diurnal(self):
        """
        Rather than dividing by zero. A purely diurnal tide is a real thing, and infinity
        is the honest form factor for one.

        """
        from ..tides import K1_HOURS

        self.assertEqual(HarmonicTide((Constituent("K1", K1_HOURS, 1.0),)).form_factor(), math.inf)


class TestInlandWaterKeepsItsOwnLevel(BaseEvenniaTestCase):
    """
    A pond is not a bay.

    It sits at whatever height its valley holds it at, it does not rise and fall with the
    sea, and the only reason it is hard is that a world has one datum and the pond is
    nowhere near it. `WorldPosition` has carried a region since the beginning and nothing was
    using it for water; this is what it is for.
    """

    def setUp(self):
        from ..bathymetry import FlatTideProvider
        from ..tides import RegionalWater

        self.sea = HarmonicTide.semidiurnal(4.0, 1.5)
        self.water = RegionalWater(
            sea=self.sea, waters={"the pond": FlatTideProvider(surface_z=23.0)}
        )

    def test_the_sea_answers_for_everywhere_unnamed(self):
        where = WorldPosition(0.0, 0.0)
        for step in range(40):
            when = step * 900.0
            self.assertEqual(
                self.water.surface_z_at(where, when), self.sea.surface_z_at(where, when)
            )

    def test_the_pond_stands_where_it_stands(self):
        pond = WorldPosition(0.0, 0.0, region="the pond")
        for step in range(40):
            self.assertEqual(self.water.surface_z_at(pond, step * 900.0), 23.0)

    def test_the_same_place_is_pond_or_sea_depending_only_on_which_you_ask_for(self):
        """
        The mechanism in one assertion. Region is a property of the question, not of the
        ground, which is what lets a pond sit twenty-three metres above a sea that is
        directly beneath it.

        """
        here = WorldPosition(1234.0, -567.0)
        pond = WorldPosition(1234.0, -567.0, region="the pond")
        self.assertNotEqual(self.water.surface_z_at(here, 0.0), self.water.surface_z_at(pond, 0.0))

    def test_the_pond_does_not_move_when_the_sea_does(self):
        pond = WorldPosition(0.0, 0.0, region="the pond")
        sea = WorldPosition(0.0, 0.0)
        levels = {self.water.surface_z_at(pond, step * 900.0) for step in range(60)}
        tides = {round(self.water.surface_z_at(sea, step * 900.0), 3) for step in range(60)}
        self.assertEqual(len(levels), 1, "the pond followed the tide")
        self.assertGreater(len(tides), 20, "the sea did not move")

    def test_an_unnamed_region_is_still_the_sea(self):
        """A game that tags its ocean rooms by area must not find each area a separate lake."""
        where = WorldPosition(0.0, 0.0, region="the western approaches")
        self.assertEqual(
            self.water.surface_z_at(where, 3000.0),
            self.sea.surface_z_at(where, 3000.0),
        )

    def test_depth_arithmetic_is_untouched(self):
        """
        The point of doing it here rather than in the map provider. Depth is still surface
        less ground, so a pond five metres deep comes out five metres deep by exactly the
        subtraction that gives a harbour its nine.

        """

        class Bowl(MaritimeMapProvider):
            def terrain_z_at(self, position):
                return 18.0

        world = Bowl(tide_provider=self.water)
        pond = WorldPosition(0.0, 0.0, region="the pond")
        self.assertAlmostEqual(world.water_depth_at(pond, 0.0), 5.0, places=6)
        # The very same ground, asked about as sea, is a hill.
        self.assertEqual(world.water_depth_at(WorldPosition(0.0, 0.0), 0.0), 0.0)

    def test_a_named_water_can_have_a_tide_of_its_own(self):
        """
        Each inland water is a full provider rather than a number, so a tidal lagoon behind
        a sill can have its own smaller tide. A float would have made the common case one
        character shorter and this impossible.

        """
        from ..tides import RegionalWater

        lagoon = HarmonicTide.semidiurnal(0.6, 0.2, mean_level_m=1.0)
        water = RegionalWater(sea=self.sea, waters={"the lagoon": lagoon})
        inside = WorldPosition(0.0, 0.0, region="the lagoon")
        outside = WorldPosition(0.0, 0.0)
        swing = [water.surface_z_at(inside, step * 900.0) for step in range(80)]
        open_sea = [water.surface_z_at(outside, step * 900.0) for step in range(80)]
        self.assertGreater(max(swing) - min(swing), 0.2, "the lagoon has no tide")
        self.assertLess(
            max(swing) - min(swing),
            (max(open_sea) - min(open_sea)) / 2.0,
            "the lagoon's tide is not smaller than the sea's",
        )

    def test_it_can_be_asked_which_water_answers_for_a_region(self):
        """Asking the sea for the pond's high water gives a confident and wrong answer."""
        from ..bathymetry import FlatTideProvider

        self.assertIsInstance(self.water.water_for("the pond"), FlatTideProvider)
        self.assertIs(self.water.water_for("anywhere else"), self.sea)

    def test_with_no_sea_given_it_is_a_motionless_one(self):
        from ..tides import RegionalWater

        self.assertEqual(RegionalWater().surface_z_at(WorldPosition(0.0, 0.0), 999.0), DATUM)
