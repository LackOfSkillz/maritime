"""
Tests for where the shot struck her, and what came in through the hole.

The claim: **a hole is under water when it is lower than she is deep.** Nothing about the
waterline is stored, so a ship that loads, or that is already making water, settles onto her
own wounds without anybody writing that down.

"""

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest

from ..cargo import commodity_named
from ..motion import MotionLimits
from ..position import WorldPosition
from ..rooms import ShipRoom
from ..sections import (
    ALREADY_PLUGGED,
    BOW,
    NO_SUCH_BREACH,
    NOT_A_SECTION,
    QUARTER,
    SECTIONS,
    WAIST,
    Breach,
    HullBreached,
    buoyancy_share,
    head_over,
    inflow_through,
    section_struck,
    under_water,
)
from ..typeclasses import Vessel
from ..vessel import BELOW_WATERLINE, OPEN, VesselCapacity

HERE = WorldPosition(0.0, 0.0)


class TestSectionStruck(BaseEvenniaTest):
    """Derived from geometry that already exists rather than rolled."""

    def test_crossed_ahead_is_hit_in_the_bow(self):
        self.assertEqual(section_struck(0.0), BOW)

    def test_engaged_broadside_is_hit_in_the_waist(self):
        self.assertEqual(section_struck(90.0), WAIST)
        self.assertEqual(section_struck(270.0), WAIST)

    def test_raked_from_astern_is_hit_in_the_quarter(self):
        self.assertEqual(section_struck(180.0), QUARTER)

    def test_the_side_she_is_hit_on_does_not_change_the_section(self):
        """A ship raked from astern is raked whichever quarter it came over."""
        self.assertEqual(section_struck(160.0), section_struck(200.0))

    def test_every_bearing_lands_somewhere(self):
        self.assertEqual(
            {section_struck(float(degrees)) for degrees in range(0, 360, 5)}, set(SECTIONS)
        )


class TestWhetherItIsUnderWater(BaseEvenniaTest):
    """The whole model, and it needs nothing stored."""

    def test_a_hole_above_her_draft_is_dry(self):
        self.assertFalse(under_water(Breach(WAIST, 0.05, 3.0), draft=2.0))

    def test_and_one_below_it_is_not(self):
        self.assertTrue(under_water(Breach(WAIST, 0.05, 1.0), draft=2.0))

    def test_the_head_over_it_is_how_far_under(self):
        self.assertAlmostEqual(head_over(Breach(WAIST, 0.05, 1.0), draft=2.5), 1.5)

    def test_a_dry_hole_has_no_head_at_all(self):
        self.assertAlmostEqual(head_over(Breach(WAIST, 0.05, 4.0), draft=2.5), 0.0)

    def test_loading_her_puts_a_dry_hole_under(self):
        """
        The consequence worth having. Nothing about the hole changed - she did.

        """
        hole = Breach(WAIST, 0.05, 2.2)
        self.assertFalse(under_water(hole, draft=2.0))
        self.assertTrue(under_water(hole, draft=2.4))


class TestWhatComesThrough(BaseEvenniaTest):
    """Torricelli, because that is what a hole in a tank does."""

    def test_a_dry_hole_admits_nothing(self):
        self.assertAlmostEqual(inflow_through(Breach(WAIST, 0.05, 3.0), draft=2.0), 0.0)

    def test_a_hole_with_no_size_admits_nothing(self):
        self.assertAlmostEqual(inflow_through(Breach(WAIST, 0.0, 0.5), draft=2.0), 0.0)

    def test_a_deeper_hole_admits_more(self):
        shallow = inflow_through(Breach(WAIST, 0.05, 1.9), draft=2.0)
        deep = inflow_through(Breach(WAIST, 0.05, 0.2), draft=2.0)
        self.assertGreater(deep, shallow)

    def test_but_not_proportionally_more(self):
        """
        The square root is the point. Four times the head is twice the water, not four
        times - so a hole well under her is bad and not catastrophic, which is the
        difference between a fight and a cutscene.

        """
        near = inflow_through(Breach(WAIST, 0.05, 1.0), draft=2.0)
        far = inflow_through(Breach(WAIST, 0.05, -2.0), draft=2.0)
        self.assertAlmostEqual(far / near, 2.0, places=6)

    def test_a_bigger_hole_admits_proportionally_more(self):
        small = inflow_through(Breach(WAIST, 0.05, 1.0), draft=2.0)
        big = inflow_through(Breach(WAIST, 0.10, 1.0), draft=2.0)
        self.assertAlmostEqual(big / small, 2.0, places=6)

    def test_plugging_one_stops_most_of_it(self):
        open_hole = inflow_through(Breach(WAIST, 0.05, 1.0), draft=2.0)
        stopped = inflow_through(Breach(WAIST, 0.05, 1.0, plugged=True), draft=2.0)
        self.assertLess(stopped, open_hole)

    def test_and_never_all_of_it(self):
        """A shot plug driven into a hole with the sea coming through gets a weep."""
        self.assertGreater(inflow_through(Breach(WAIST, 0.05, 1.0, plugged=True), 2.0), 0.0)


class TestTheUnitsMeet(BaseEvenniaTest):
    """One function where cubic metres a second becomes a share of buoyancy a minute."""

    def test_a_ship_with_no_displacement_takes_nothing(self):
        self.assertAlmostEqual(buoyancy_share(1.0, displacement=0.0), 0.0)

    def test_the_same_hole_is_worse_in_a_smaller_ship(self):
        small = buoyancy_share(0.1, displacement=50_000.0)
        big = buoyancy_share(0.1, displacement=500_000.0)
        self.assertGreater(small, big)

    def test_it_is_a_share_per_minute_and_not_per_second(self):
        """
        Flooding counts per minute and a hole counts per second. Sixty is the only thing
        between them, and getting it wrong reads as plausible for a long time.

        """
        self.assertAlmostEqual(buoyancy_share(1.0, 1_025_000.0), 60.0 / 1000.0, places=6)


class SectionTestCase(BaseEvenniaTest):
    """A hull that can be holed."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Kestrel")
        self.hull.length, self.hull.beam = 24.0, 7.0
        self.hull.light_draft = 2.0
        self.hull.hull_depth = 4.0
        self.hull.motion_limits = MotionLimits(max_speed=6.0, acceleration=0.5, turn_rate=5.0)
        self.hull.capacity = VesselCapacity(
            displacement=200_000.0, internal_volume=300.0, stability_moment=100_000.0
        )
        self.hull.maritime_position = HERE
        self.hull.heading = 0.0

        self.hold = create.create_object(ShipRoom, key="Hold")
        self.hold.vessel = self.hull
        self.hold.deck_level = -1
        self.hold.exposure = BELOW_WATERLINE
        self.hold.hold_capacity = 200.0
        self.deck = create.create_object(ShipRoom, key="Deck")
        self.deck.vessel = self.hull
        self.deck.exposure = OPEN


class TestHolingHer(SectionTestCase):
    """Holes are kept; whether they are under water is not."""

    def test_a_new_hull_is_whole(self):
        self.assertEqual(self.hull.breaches, ())

    def test_she_can_be_holed(self):
        self.assertTrue(self.hull.hole(WAIST, 0.05, 1.0))
        self.assertEqual(len(self.hull.breaches), 1)

    def test_a_hole_nowhere_in_particular_is_refused(self):
        self.assertEqual(self.hull.hole("amidships-ish", 0.05, 1.0).code, NOT_A_SECTION)

    def test_she_can_be_holed_more_than_once(self):
        self.hull.hole(WAIST, 0.05, 1.0)
        self.hull.hole(BOW, 0.02, 0.5)
        self.assertEqual(len(self.hull.breaches), 2)

    def test_a_hole_below_her_draft_is_making_water(self):
        self.hull.hole(WAIST, 0.05, 1.0)
        self.assertEqual(len(self.hull.holed_below()), 1)

    def test_and_one_above_it_is_not(self):
        self.hull.hole(WAIST, 0.05, 3.5)
        self.assertEqual(self.hull.holed_below(), ())

    def test_a_dry_hole_costs_her_nothing(self):
        self.hull.hole(WAIST, 0.05, 3.5)
        self.assertAlmostEqual(self.hull.breach_inflow(), 0.0)

    def test_a_wet_one_costs_her(self):
        self.hull.hole(WAIST, 0.05, 1.0)
        self.assertGreater(self.hull.breach_inflow(), 0.0)


class TestSheSettlesOntoHerOwnWounds(SectionTestCase):
    """The spiral nobody wrote."""

    def test_loading_her_puts_a_dry_hole_under(self):
        salt = commodity_named("salt")
        if salt is None:
            self.skipTest("the shipped commodities do not include salt")
        self.hull.hole(WAIST, 0.05, self.hull.draft + 0.05)
        self.assertEqual(self.hull.holed_below(), (), "the fixture holed her below already")

        self.assertTrue(self.hull.load(salt, 80.0), "the fixture never got cargo aboard")
        self.assertEqual(len(self.hull.holed_below()), 1)

    def test_and_it_starts_costing_her(self):
        salt = commodity_named("salt")
        if salt is None:
            self.skipTest("the shipped commodities do not include salt")
        self.hull.hole(WAIST, 0.05, self.hull.draft + 0.05)
        self.assertAlmostEqual(self.hull.breach_inflow(), 0.0)
        self.hull.load(salt, 80.0)
        self.assertGreater(self.hull.breach_inflow(), 0.0)


class TestPluggingThem(SectionTestCase):
    """What the carpenter can do about it."""

    def test_a_hole_can_be_plugged(self):
        made = self.hull.hole(WAIST, 0.05, 1.0).breach
        self.assertTrue(self.hull.plug(made))

    def test_and_it_stays_plugged(self):
        made = self.hull.hole(WAIST, 0.05, 1.0).breach
        self.hull.plug(made)
        self.assertTrue(self.hull.breaches[0].plugged)

    def test_plugging_slows_the_water(self):
        made = self.hull.hole(WAIST, 0.05, 1.0).breach
        before = self.hull.breach_inflow()
        self.hull.plug(made)
        self.assertLess(self.hull.breach_inflow(), before)

    def test_but_does_not_stop_it(self):
        made = self.hull.hole(WAIST, 0.05, 1.0).breach
        self.hull.plug(made)
        self.assertGreater(self.hull.breach_inflow(), 0.0)

    def test_a_hole_she_has_not_got_cannot_be_plugged(self):
        self.assertEqual(self.hull.plug(Breach(BOW, 0.9, 0.1)).code, NO_SUCH_BREACH)

    def test_nor_can_one_already_stopped(self):
        made = self.hull.hole(WAIST, 0.05, 1.0).breach
        stopped = self.hull.plug(made).breach
        self.assertEqual(self.hull.plug(stopped).code, ALREADY_PLUGGED)


class TestSayingSoOutLoud(SectionTestCase):
    """A game narrates the hit; the contrib does not."""

    def setUp(self):
        super().setUp()
        from ..events import bus

        self.heard = []
        bus().subscribe(HullBreached, self.heard.append)

    def test_being_holed_is_announced(self):
        self.hull.hole(WAIST, 0.05, 1.0)
        self.assertEqual(len(self.heard), 1)

    def test_and_says_where_and_how_big(self):
        self.hull.hole(BOW, 0.07, 1.0)
        self.assertEqual(self.heard[0].section, BOW)
        self.assertAlmostEqual(self.heard[0].area, 0.07)

    def test_and_whether_the_sea_is_coming_in(self):
        self.hull.hole(WAIST, 0.05, 1.0)
        self.assertTrue(self.heard[0].under_water)
        self.hull.hole(WAIST, 0.05, 3.5)
        self.assertFalse(self.heard[1].under_water)

    def test_a_hole_that_is_refused_is_not_announced(self):
        self.hull.hole("somewhere", 0.05, 1.0)
        self.assertEqual(self.heard, [])


class TestTheLeakAddsThem(SectionTestCase):
    """Two sources of water, added, because they are different water."""

    def test_a_whole_ship_makes_no_water(self):
        self.assertAlmostEqual(self.hull.leak(), 0.0)

    def test_a_holed_one_does(self):
        self.hull.hole(WAIST, 0.05, 1.0)
        self.assertGreater(self.hull.leak(), 0.0)

    def test_even_with_her_hull_track_untouched(self):
        """
        The gap the track could not describe. Her planking is sound everywhere except the
        one place there is a hole in it, and a single number per hull cannot say that.

        """
        from ..damage import HULL

        self.assertAlmostEqual(self.hull.damage.of(HULL), 0.0)
        self.hull.hole(WAIST, 0.05, 1.0)
        self.assertGreater(self.hull.leak(), 0.0)

    def test_plugging_it_slows_what_she_makes(self):
        made = self.hull.hole(WAIST, 0.05, 1.0).breach
        before = self.hull.leak()
        self.hull.plug(made)
        self.assertLess(self.hull.leak(), before)


class TestGettingOutOfAFloodedHold(SectionTestCase):
    """Up, not off - she has not foundered yet."""

    def crowd(self, room, how_many=2):
        return [
            create.create_object(
                "evennia.objects.objects.DefaultCharacter",
                key=f"Hand {number}",
                location=room,
            )
            for number in range(how_many)
        ]

    def test_a_dry_ship_drives_nobody_out(self):
        self.crowd(self.hold)
        self.assertEqual(self.hull.untenable(), ())
        self.assertEqual(self.hull.flood_out(), ())

    def test_water_in_her_makes_the_hold_untenable(self):
        self.hull.db.water = 0.9
        self.assertIn(self.hold, self.hull.untenable())

    def test_and_her_people_come_up(self):
        people = self.crowd(self.hold)
        self.hull.db.water = 0.9
        moved = self.hull.flood_out()
        self.assertEqual(len(moved), len(people))
        self.assertEqual(people[0].location, self.deck)

    def test_they_are_on_deck_and_not_in_the_sea(self):
        """
        `abandon_ship` is a different moment. Confusing the two would drown a crew every
        time a hold took water.

        """
        people = self.crowd(self.hold)
        self.hull.db.water = 0.9
        self.hull.flood_out()
        self.assertIn(people[0].location, self.hull.ship_rooms)

    def test_cargo_does_not_climb_the_ladder(self):
        create.create_object(
            "evennia.objects.objects.DefaultObject", key="a cask", location=self.hold
        )
        self.crowd(self.hold, 1)
        self.hull.db.water = 0.9
        self.assertEqual(len(self.hull.flood_out()), 1)

    def test_the_open_deck_is_where_they_go(self):
        self.assertIs(self.hull.highest_deck(), self.deck)

    def test_she_fills_from_the_bottom(self):
        """
        The orlop goes before the hold. A ship that lost every compartment at once would
        drown a crew in one step instead of driving them up a deck at a time.

        """
        orlop = create.create_object(ShipRoom, key="Orlop")
        orlop.vessel = self.hull
        orlop.deck_level = -2
        orlop.exposure = BELOW_WATERLINE

        self.hull.db.water = 0.3
        lost = self.hull.untenable()
        self.assertIn(orlop, lost)
        self.assertNotIn(self.hold, lost)

    def test_and_the_hold_follows_it(self):
        orlop = create.create_object(ShipRoom, key="Orlop")
        orlop.vessel = self.hull
        orlop.deck_level = -2
        orlop.exposure = BELOW_WATERLINE

        self.hull.db.water = 0.9
        self.assertEqual(len(self.hull.untenable()), 2)

    def test_somebody_driven_out_of_the_orlop_goes_to_the_weather_deck(self):
        """
        All the way up, not one deck at a time. Climbing a level per tick would need a
        ladder graph this contrib does not have, and the deck is where you want to be on a
        ship that is filling anyway.

        """
        orlop = create.create_object(ShipRoom, key="Orlop")
        orlop.vessel = self.hull
        orlop.deck_level = -2
        orlop.exposure = BELOW_WATERLINE
        people = self.crowd(orlop, 1)

        self.hull.db.water = 0.3
        self.hull.flood_out()
        self.assertIs(people[0].location, self.deck)

    def test_a_hull_with_no_compartments_has_nothing_to_flood(self):
        bare = create.create_object(Vessel, key="Bare")
        bare.db.water = 0.9
        self.assertEqual(bare.untenable(), ())
        self.assertEqual(bare.flood_out(), ())
