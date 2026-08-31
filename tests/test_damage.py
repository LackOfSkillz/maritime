"""
Tests for what is broken and what that stops her doing.

"""

from django.test import override_settings

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest, BaseEvenniaTestCase

from ..damage import (
    DISABLED,
    DISARMED,
    HOLED,
    HULL,
    MAST_DOWN,
    MINIMUM_RESILIENCE,
    OARS,
    RIGGING,
    TRACKS,
    WEAPONS,
    Damage,
    canvas_drawing,
    casualties_from,
    guns_serviceable,
    looms_manned,
    resilience,
    serving_time,
    share_of,
    structural,
)
from ..crew import ABLE
from ..motion import MotionLimits
from ..oars import OAR_PLANS
from ..position import WorldPosition
from ..rooms import ShipRoom
from ..sailing import WORKING
from ..typeclasses import Vessel
from ..vessel import OPEN
from .base import EmptySeaMixin

#: What a default gun delivers, from `WeaponType.damage`. The scale is set against this.
A_GUN = 10.0


class TestTracks(BaseEvenniaTestCase):
    """Five things that break, not one."""

    def test_a_new_ship_is_sound(self):
        self.assertTrue(Damage().sound)

    def test_hurting_one_track_leaves_the_others_alone(self):
        """
        The whole argument for tracks. A ship whose rigging is cut about still has
        her guns, and a pool cannot say that.

        """
        hurt = Damage().hurt(RIGGING, 0.5)
        self.assertAlmostEqual(hurt.rigging, 0.5)
        self.assertAlmostEqual(hurt.hull, 0.0)
        self.assertAlmostEqual(hurt.weapons, 0.0)
        self.assertAlmostEqual(hurt.oars, 0.0)

    def test_damage_accumulates(self):
        hurt = Damage().hurt(HULL, 0.2).hurt(HULL, 0.3)
        self.assertAlmostEqual(hurt.hull, 0.5)

    def test_nothing_goes_past_destroyed(self):
        self.assertAlmostEqual(Damage().hurt(HULL, 40.0).hull, 1.0)

    def test_nor_below_sound(self):
        self.assertAlmostEqual(Damage().mended(HULL, 40.0).hull, 0.0)

    def test_repairs_undo_damage(self):
        hurt = Damage().hurt(OARS, 0.6).mended(OARS, 0.4)
        self.assertAlmostEqual(hurt.oars, 0.2)

    def test_a_hurt_ship_is_not_sound(self):
        self.assertFalse(Damage().hurt(WEAPONS, 0.01).sound)

    def test_the_worst_is_reported(self):
        hurt = Damage().hurt(HULL, 0.2).hurt(RIGGING, 0.7).hurt(OARS, 0.4)
        self.assertEqual(hurt.worst, (RIGGING, 0.7))

    def test_a_track_nobody_has_is_refused(self):
        with self.assertRaises(ValueError):
            Damage().of("morale")

    def test_every_track_can_be_hurt(self):
        for track in TRACKS:
            self.assertAlmostEqual(Damage().hurt(track, 0.5).of(track), 0.5)

    def test_damage_is_frozen(self):
        """
        Several things write damage in one tick - a broadside, a grounding, a fire -
        and a mutable version would let two of them interleave.

        """
        original = Damage()
        original.hurt(HULL, 0.5)
        self.assertTrue(original.sound)


class TestWhatItCosts(BaseEvenniaTestCase):
    """Each track feeding the simulation that already exists."""

    def test_cut_rigging_means_less_canvas_draws(self):
        self.assertAlmostEqual(canvas_drawing(Damage().hurt(RIGGING, 0.4)), 0.6)

    def test_sound_rigging_costs_nothing(self):
        self.assertAlmostEqual(canvas_drawing(Damage()), 1.0)

    def test_rigging_shot_away_entirely_leaves_nothing_drawing(self):
        self.assertAlmostEqual(canvas_drawing(Damage().hurt(RIGGING, 1.0)), 0.0)

    def test_only_rigging_touches_the_canvas(self):
        """Shooting for the hull does not slow her; that is why chain exists."""
        self.assertAlmostEqual(canvas_drawing(Damage().hurt(HULL, 0.9)), 1.0)

    def test_broken_oars_leave_fewer_looms_manned(self):
        self.assertEqual(looms_manned(12, Damage().hurt(OARS, 0.5)), 6)

    def test_half_an_oar_is_no_oar(self):
        """Rounded down, honestly."""
        self.assertEqual(looms_manned(3, Damage().hurt(OARS, 0.5)), 1)

    def test_oars_shot_away_leave_nobody_pulling(self):
        self.assertEqual(looms_manned(12, Damage().hurt(OARS, 1.0)), 0)

    def test_a_battered_battery_fights_fewer_guns(self):
        self.assertEqual(guns_serviceable(8, Damage().hurt(WEAPONS, 0.5)), 4)

    def test_a_sound_battery_fights_all_of_them(self):
        self.assertEqual(guns_serviceable(8, Damage()), 8)


class TestMoraleFinallyCostsSomething(BaseEvenniaTestCase):
    """
    `hesitation` was computed the moment crews went in, and read by nothing - which
    made it a claim rather than a rule. This is where it starts to bite.

    """

    def test_a_steady_crew_serve_at_the_gun_s_own_rate(self):
        self.assertAlmostEqual(serving_time(90.0, hesitation=0.0), 90.0)

    def test_a_shaken_crew_serve_slower(self):
        self.assertGreater(serving_time(90.0, hesitation=0.3), 90.0)

    def test_a_broken_crew_slower_still(self):
        self.assertGreater(serving_time(90.0, hesitation=0.5), serving_time(90.0, hesitation=0.2))

    def test_but_they_do_not_stop(self):
        """
        Frightened, not gone. A battery that fell silent would make morale a kill
        switch rather than a cost, and there would be no decision left in it.

        The bound is an absolute one on purpose. Written against
        `HESITATION_ON_SERVING` it referenced the very constant it was meant to
        constrain, so it scaled with any change to it and could not fail - which is
        exactly what mutation testing found.

        """
        worst = serving_time(90.0, hesitation=1.0)
        self.assertGreater(worst, 90.0)
        self.assertLess(worst, 180.0, "a wholly shaken crew must still be firing")

    def test_a_battered_battery_is_slower_too(self):
        """Fewer hands who know the drill, working round wreckage."""
        self.assertGreater(
            serving_time(90.0, damage=Damage().hurt(WEAPONS, 0.5)), serving_time(90.0)
        )

    def test_fear_and_wreckage_compound(self):
        both = serving_time(90.0, damage=Damage().hurt(WEAPONS, 0.5), hesitation=0.5)
        fear = serving_time(90.0, hesitation=0.5)
        wreck = serving_time(90.0, damage=Damage().hurt(WEAPONS, 0.5))
        self.assertGreater(both, fear)
        self.assertGreater(both, wreck)


class TestScale(BaseEvenniaTestCase):
    """The one number that decides how lethal all of this is."""

    def test_a_bigger_hull_absorbs_more(self):
        self.assertGreater(resilience(60.0), resilience(20.0))

    def test_the_smallest_craft_still_takes_several_hits(self):
        """A coracle is not divided by nothing."""
        self.assertAlmostEqual(resilience(1.0), MINIMUM_RESILIENCE)
        self.assertLess(share_of(A_GUN, 1.0), 0.5)

    def test_the_same_shot_means_less_to_a_bigger_ship(self):
        """
        The whole reason damage is a fraction. Nothing downstream has to know it -
        it is decided once.

        """
        self.assertGreater(share_of(A_GUN, 14.0), share_of(A_GUN, 62.0))

    def test_a_sloop_is_reduced_over_a_long_engagement(self):
        """
        The calibration claim, pinned. Ships of the age were reduced over an hour of
        firing rather than in a broadside - if this ever becomes three hits, the
        scale has drifted and capture stops being worth attempting.

        """
        hits = 1.0 / share_of(A_GUN, 18.0)
        self.assertGreater(hits, 10)
        self.assertLess(hits, 25)

    def test_and_a_first_rate_takes_far_longer(self):
        small = 1.0 / share_of(A_GUN, 18.0)
        great = 1.0 / share_of(A_GUN, 62.0)
        self.assertGreater(great, small * 2)

    def test_a_miss_costs_nothing(self):
        self.assertAlmostEqual(share_of(0.0, 18.0), 0.0)

    def test_negative_damage_is_not_a_repair(self):
        """Mending is `mended`. A shot that did nothing did nothing."""
        self.assertAlmostEqual(share_of(-50.0, 18.0), 0.0)


class TestWhatIsWrongInWords(BaseEvenniaTestCase):
    """A number going down is bookkeeping; a mast over the side is an event."""

    def test_a_sound_ship_has_nothing_wrong(self):
        self.assertEqual(structural(Damage()), ())

    def test_a_mast_comes_down_before_the_last_shroud_is_cut(self):
        self.assertIn(MAST_DOWN, structural(Damage().hurt(RIGGING, 0.6)))

    def test_light_rigging_damage_carries_nothing_away(self):
        self.assertEqual(structural(Damage().hurt(RIGGING, 0.5)), ())

    def test_enough_hull_and_she_is_open_to_the_sea(self):
        self.assertIn(HOLED, structural(Damage().hurt(HULL, 0.8)))

    def test_enough_oars_and_she_cannot_be_pulled(self):
        self.assertIn(DISABLED, structural(Damage().hurt(OARS, 0.9)))

    def test_enough_guns_and_she_cannot_fight(self):
        self.assertIn(DISARMED, structural(Damage().hurt(WEAPONS, 0.95)))

    def test_several_can_be_wrong_at_once(self):
        wreck = Damage().hurt(RIGGING, 0.9).hurt(HULL, 0.9)
        self.assertIn(MAST_DOWN, structural(wreck))
        self.assertIn(HOLED, structural(wreck))

    def test_the_words_cannot_disagree_with_the_tracks(self):
        """Derived rather than stored, so there is nothing to keep in step."""
        wreck = Damage().hurt(RIGGING, 0.9)
        self.assertIn(MAST_DOWN, structural(wreck))
        self.assertEqual(structural(wreck.mended(RIGGING, 0.9)), ())

    def test_rigging_carries_away_before_the_hull_opens(self):
        """
        A mast goes long before she is holed, which is what makes shooting for the
        rigging the way to *catch* a ship rather than sink her.

        """
        creeping = Damage()
        first = None
        for _ in range(20):
            creeping = creeping.hurt(RIGGING, 0.05).hurt(HULL, 0.05)
            if structural(creeping):
                first = structural(creeping)[0]
                break
        self.assertEqual(first, MAST_DOWN)


class DamagedShipTestCase(EmptySeaMixin, BaseEvenniaTest):
    """A hull that can be broken."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Kestrel")
        self.hull.length, self.hull.beam = 18.0, 5.4
        self.hull.motion_limits = MotionLimits(max_speed=6.0, acceleration=0.5, turn_rate=5.0)
        self.hull.maritime_position = WorldPosition(0.0, 0.0)
        deck = create.create_object(ShipRoom, key="Main Deck")
        deck.vessel = self.hull
        deck.exposure = OPEN


class TestTakingDamage(DamagedShipTestCase):
    """The join between a weight of damage and a fraction of a track."""

    def test_a_new_ship_is_sound(self):
        self.assertTrue(self.hull.damage.sound)
        self.assertTrue(self.hull.seaworthy)

    def test_a_hit_takes_a_share_of_a_track(self):
        self.hull.take_damage(HULL, 100.0)
        self.assertAlmostEqual(self.hull.damage.hull, share_of(100.0, 18.0))

    def test_a_caller_hands_in_a_weight_not_a_fraction(self):
        """
        Whoever has a shot in its hand knows what the shot was worth and does not
        know how big the target is. Converting in one place is what stops every
        weapon in every game having to.

        """
        self.hull.take_damage(HULL, 10.0)
        self.assertGreater(self.hull.damage.hull, 0.0)
        self.assertLess(self.hull.damage.hull, 0.2)

    def test_the_same_shot_hurts_a_smaller_ship_more(self):
        boat = create.create_object(Vessel, key="a gig")
        boat.length = 6.0
        boat.take_damage(HULL, 100.0)
        self.hull.take_damage(HULL, 100.0)
        self.assertGreater(boat.damage.hull, self.hull.damage.hull)

    def test_a_structural_failure_is_reported_when_it_happens(self):
        carried_away = self.hull.take_damage(RIGGING, 10000.0)
        self.assertIn(MAST_DOWN, carried_away)

    def test_but_not_twice(self):
        """
        A mast that is already over the side does not come down again, and a report
        that said so on every later hit would be worse than silence.

        """
        self.hull.take_damage(RIGGING, 10000.0)
        self.assertEqual(self.hull.take_damage(RIGGING, 500.0), ())

    def test_a_hit_that_breaks_nothing_reports_nothing(self):
        self.assertEqual(self.hull.take_damage(HULL, 10.0), ())

    def test_repairs_put_it_right(self):
        self.hull.take_damage(OARS, 200.0)
        before = self.hull.damage.oars
        self.hull.repair(OARS, 0.1)
        self.assertLess(self.hull.damage.oars, before)

    def test_holed_is_the_only_one_that_is_about_sinking(self):
        """
        A ship with her masts gone and every gun dismounted is a wreck to look at
        and will still float home.

        """
        self.hull.take_damage(RIGGING, 10000.0)
        self.hull.take_damage(WEAPONS, 10000.0)
        self.assertTrue(self.hull.seaworthy)
        self.hull.take_damage(HULL, 10000.0)
        self.assertFalse(self.hull.seaworthy)


class TestDamageChangesWhatSheCanDo(DamagedShipTestCase):
    """The point of the tracks: they feed the simulation that already exists."""

    def test_shot_away_sweeps_cannot_be_pulled(self):
        """
        What makes sheering worth the trouble - it takes the looms rather than the
        men, and a full crew cannot pull an oar that is not there.

        """
        self.hull.oar_plan = OAR_PLANS["cutter"]
        self.hull.man(30, ABLE)
        sound = self.hull.rowing_crew
        self.hull.take_damage(OARS, 500.0)
        self.assertLess(self.hull.rowing_crew, sound)

    def test_a_crew_cannot_make_up_for_missing_oars(self):
        self.hull.oar_plan = OAR_PLANS["cutter"]
        self.hull.man(200, ABLE)
        self.hull.take_damage(OARS, 100000.0)
        self.assertEqual(self.hull.rowing_crew, 0)

    def test_cut_rigging_slows_her(self):
        """
        Applied to the plan rather than the answer, so she is slower at every sail
        plan - which is why shooting for the rigging is how you catch a ship.

        """
        with override_settings(MARITIME_WIND_BEARING=180.0, MARITIME_WIND_SPEED=8.0):
            self.hull.sail_plan = WORKING
            self.hull.heading = 90.0
            sound = self.hull.sailing_speed()
            self.hull.take_damage(RIGGING, 500.0)
            self.assertLess(self.hull.sailing_speed(), sound)

    def test_hull_damage_does_not_slow_her(self):
        """Shooting for the hull is how you sink a ship, not how you catch one."""
        with override_settings(MARITIME_WIND_BEARING=180.0, MARITIME_WIND_SPEED=8.0):
            self.hull.sail_plan = WORKING
            self.hull.heading = 90.0
            sound = self.hull.sailing_speed()
            self.hull.take_damage(HULL, 500.0)
            self.assertAlmostEqual(self.hull.sailing_speed(), sound)

    def test_a_sound_ship_sails_at_her_own_speed(self):
        with override_settings(MARITIME_WIND_BEARING=180.0, MARITIME_WIND_SPEED=8.0):
            self.hull.sail_plan = WORKING
            self.hull.heading = 90.0
            self.assertGreater(self.hull.sailing_speed(), 0.0)


class TestCrewIsNotATrack(DamagedShipTestCase):
    """
    Casualties are people, not a fraction of a system.

    Routing them through the company is the whole reason the crew work was done
    first: morale, exhaustion, striking and mutiny all answer without a line of new
    wiring.

    """

    def test_grape_takes_people(self):
        self.hull.man(60, ABLE)
        lost = self.hull.take_crew_casualties(60.0)
        self.assertGreater(lost, 0)
        self.assertEqual(self.hull.company.fit, 60 - lost)

    def test_a_shot_heavy_enough_for_two_hulls_still_only_kills_the_people_aboard(self):
        self.hull.man(60, ABLE)
        self.assertEqual(self.hull.take_crew_casualties(100000.0), 60)
        self.assertEqual(self.hull.company.fit, 0)

    def test_a_ship_nobody_crewed_loses_nobody(self):
        self.assertEqual(self.hull.take_crew_casualties(500.0), 0)

    def test_the_same_dial_governs_people_and_timber(self):
        """
        A shot that would take a twentieth of her structure takes a twentieth of her
        company - one dial rather than two that can drift apart.

        """
        self.hull.man(100, ABLE)
        self.hull.take_crew_casualties(100.0)
        expected = casualties_from(100.0, 18.0, 100)
        self.assertEqual(self.hull.company.casualties, expected)
        self.assertGreater(expected, 0)
        self.assertLess(expected, 100)

    def test_casualties_reach_morale_with_no_new_wiring(self):
        """The join that made the ordering of this work worth arguing about."""
        self.hull.man(60, ABLE)
        self.hull.captain = create.create_object(
            "evennia.objects.objects.DefaultCharacter", key="The master"
        )
        steady = self.hull.morale
        self.hull.take_crew_casualties(300.0)
        self.hull.feel(600.0)
        self.assertLess(self.hull.morale, steady)

    def test_and_far_enough_they_will_strike(self):
        self.hull.man(60, ABLE)
        self.hull.captain = create.create_object(
            "evennia.objects.objects.DefaultCharacter", key="The master"
        )
        self.hull.take_crew_casualties(8000.0)
        self.hull.morale = 0.0
        self.assertTrue(self.hull.will_strike())

    def test_heavier_losses_weigh_heavier(self):
        """
        Proportional, not a threshold. A crew do not feel nothing at forty-nine per
        cent and everything at fifty - they feel each loss, and the gate that decides
        whether surrender is a question is the separate mechanism that does have a
        threshold.

        """
        from ..morale import casualty_factor

        light = casualty_factor(0.1).weight
        heavy = casualty_factor(0.8).weight
        self.assertLess(heavy, light)

    def test_a_company_that_has_lost_more_feels_worse(self):
        """The same claim, on a real hull, through the standing condition."""
        scratched = create.create_object(Vessel, key="Scratched")
        scratched.length = 18.0
        scratched.man(100, ABLE)
        scratched.captain = create.create_object(
            "evennia.objects.objects.DefaultCharacter", key="One master"
        )
        scratched.take_casualties(5)
        scratched.feel(3600.0)

        mauled = create.create_object(Vessel, key="Mauled")
        mauled.length = 18.0
        mauled.man(100, ABLE)
        mauled.captain = create.create_object(
            "evennia.objects.objects.DefaultCharacter", key="Another master"
        )
        mauled.take_casualties(70)
        mauled.feel(3600.0)

        self.assertLess(mauled.morale, scratched.morale)

    def test_half_a_casualty_is_nobody(self):
        self.assertEqual(casualties_from(0.0, 18.0, 100), 0)


class TestABatteryCanBeWrecked(DamagedShipTestCase):
    """A wrecked ship must not keep firing a full broadside."""

    def a_battery(self, guns=4):
        """Give her a broadside of identical guns."""
        from ..tactical import STARBOARD_BROADSIDE
        from ..weapons import Mount, WeaponType

        gun = WeaponType(key="nine", name="nine-pounder", arc=STARBOARD_BROADSIDE)
        self.hull.db.mounts = [Mount(key=f"starboard {n}", weapon=gun) for n in range(1, guns + 1)]

    def test_a_sound_ship_fights_her_whole_battery(self):
        self.a_battery()
        self.assertEqual(len(self.hull.serviceable_mounts), 4)

    def test_a_battered_one_fights_fewer(self):
        self.a_battery()
        self.hull.take_damage(WEAPONS, 500.0)
        self.assertLess(len(self.hull.serviceable_mounts), 4)

    def test_a_dismounted_gun_bears_on_nothing(self):
        """
        Reading the whole battery here would let a wrecked ship keep firing a full
        broadside, which is the exact failure the weapons track exists to prevent.

        """
        self.a_battery()
        sound = len(self.hull.guns_bearing(90.0))
        self.hull.take_damage(WEAPONS, 500.0)
        self.assertLess(len(self.hull.guns_bearing(90.0)), sound)

    def test_a_disarmed_ship_has_nothing_left(self):
        self.a_battery()
        self.hull.take_damage(WEAPONS, 100000.0)
        self.assertEqual(self.hull.serviceable_mounts, ())
        self.assertIn(DISARMED, self.hull.structural_failures)
