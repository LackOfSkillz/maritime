"""
Tests for the ship's company: what they are made of, what it costs them, and when they
stop.

"""

import math

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest

from ..crew import (
    ABLE,
    CRACK,
    DEFAULT_QUALITY,
    LANDSMEN,
    ORDINARY,
    PRESSED,
    QUALITIES,
    RECOVER_SECONDS,
    SEASONED,
    SPEND_SECONDS,
    CrewQuality,
    ShipsCompany,
    blended,
    spend,
)
from ..morale import (
    AGROUND,
    BOARDED,
    BROKEN,
    BUTCHERED,
    CAPTAIN_LOST,
    DRIVEN,
    ENEMY_STRUCK,
    FALL_SECONDS,
    LEADERLESS,
    MUTINY_READING,
    OFFICER_LOST,
    QUARTER_OFFERED,
    QUARTER_REFUSED,
    RISE_SECONDS,
    ROUT,
    SHAKEN,
    STEADY,
    STRIKE_READING,
    UNEASY,
    WAVERING,
    Factor,
    band_of,
    grievances,
    hesitation,
    mutinies,
    reading,
    settle,
    strikes,
    when_asked,
)
from ..motion import MotionLimits
from ..oars import GIVE_WAY, OAR_PLANS, STRETCH_OUT, EASY_OARS, rowed_speed
from ..position import WorldPosition
from ..rooms import ShipRoom
from ..typeclasses import Vessel
from ..vessel import OPEN
from .base import EmptySeaMixin


def never(*_args):
    """A roll that always comes up as low as it goes."""
    return 0.0


def always(*_args):
    """And one that never does."""
    return 1.0


def fixed(value):
    """
    Args:
        value (float): What the roll always comes up as.

    Returns:
        roll (callable): A roll of exactly that, for testing where the odds sit
            rather than which side of a coin they landed on.

    """
    return lambda *_args: value


class TestQualities(BaseEvenniaTest):
    """What a company is made of."""

    def test_better_crews_hold_out_longer(self):
        """The quiet half of quality: a good crew is hard to beat, not merely brave."""
        floors = [quality.casualty_floor for quality in QUALITIES]
        self.assertEqual(floors, sorted(floors))

    def test_and_start_steadier(self):
        morales = [quality.base_morale for quality in QUALITIES]
        self.assertEqual(morales, sorted(morales))

    def test_and_work_her_better(self):
        skills = [quality.skill for quality in QUALITIES]
        self.assertEqual(skills, sorted(skills))

    def test_the_two_claims_are_separate(self):
        """
        A pressed crew who cannot reef may still be too frightened to run; a crack
        crew who can do anything will still not stand at any price. If skill and
        nerve were the same number there would be no reason to hold both.

        """
        self.assertNotEqual(
            [quality.skill for quality in QUALITIES],
            [quality.base_morale for quality in QUALITIES],
        )

    def test_a_default_exists(self):
        self.assertIn(DEFAULT_QUALITY, QUALITIES)


class TestBlending(BaseEvenniaTest):
    """A ship is rarely one thing."""

    def test_one_kind_blends_to_itself(self):
        self.assertEqual(blended(((ABLE, 40),)).key, ABLE.key)
        self.assertAlmostEqual(blended(((ABLE, 40),)).skill, ABLE.skill)

    def test_a_mixture_lands_between(self):
        mixed = blended(((PRESSED, 10), (CRACK, 10)))
        self.assertGreater(mixed.skill, PRESSED.skill)
        self.assertLess(mixed.skill, CRACK.skill)

    def test_it_is_weighted_by_numbers(self):
        """Forty pressed men and ten crack ones is a pressed crew with help."""
        mostly_pressed = blended(((PRESSED, 40), (CRACK, 10)))
        even = blended(((PRESSED, 10), (CRACK, 10)))
        self.assertLess(mostly_pressed.skill, even.skill)

    def test_it_is_not_rounded_to_a_grade(self):
        """
        Rounding would make a mixture come out as a grade nobody in the company is,
        and would make the answer jump when one man dies.

        """
        mixed = blended(((PRESSED, 40), (CRACK, 10)))
        self.assertNotIn(mixed.skill, [quality.skill for quality in QUALITIES])

    def test_nobody_at_all_is_refused(self):
        with self.assertRaises(ValueError):
            blended(())

    def test_and_so_is_a_company_of_none(self):
        with self.assertRaises(ValueError):
            blended(((ABLE, 0),))


class TestShipsCompany(BaseEvenniaTest):
    """Who is standing."""

    def test_a_full_company_has_no_casualties(self):
        company = ShipsCompany(complement=80, fit=80, quality=ABLE)
        self.assertEqual(company.casualties, 0)
        self.assertAlmostEqual(company.casualty_fraction, 0.0)

    def test_casualties_are_the_difference(self):
        company = ShipsCompany(complement=80, fit=60, quality=ABLE)
        self.assertEqual(company.casualties, 20)
        self.assertAlmostEqual(company.casualty_fraction, 0.25)

    def test_a_fraction_rather_than_a_count(self):
        """Forty dead means something different on a longboat and a ship of the line."""
        longboat = ShipsCompany(complement=50, fit=10, quality=ABLE)
        liner = ShipsCompany(complement=600, fit=560, quality=ABLE)
        self.assertEqual(longboat.casualties, liner.casualties)
        self.assertGreater(longboat.casualty_fraction, liner.casualty_fraction)

    def test_strength_counts_heads(self):
        few = ShipsCompany(complement=20, fit=20, quality=ABLE)
        many = ShipsCompany(complement=40, fit=40, quality=ABLE)
        self.assertGreater(many.strength, few.strength)

    def test_and_what_they_are_made_of(self):
        """Twenty able seamen and twenty pressed men are not the same boarding party."""
        able = ShipsCompany(complement=20, fit=20, quality=ABLE)
        pressed = ShipsCompany(complement=20, fit=20, quality=PRESSED)
        self.assertGreater(able.strength, pressed.strength)

    def test_so_numbers_can_be_answered_with_quality(self):
        """
        Forty pressed men are worth about twenty able seamen, which is the whole
        argument for holding quality rather than counting bodies. Neither number
        alone tells you who wins.

        """
        able = ShipsCompany(complement=20, fit=20, quality=ABLE)
        pressed = ShipsCompany(complement=40, fit=40, quality=PRESSED)
        self.assertGreater(pressed.fit, able.fit)
        self.assertLess(abs(pressed.strength - able.strength) / able.strength, 0.2)

    def test_being_hurt_takes_them_down(self):
        company = ShipsCompany(complement=80, fit=80, quality=ABLE).hurt(30)
        self.assertEqual(company.fit, 50)

    def test_and_never_below_nobody(self):
        company = ShipsCompany(complement=80, fit=10, quality=ABLE).hurt(400)
        self.assertEqual(company.fit, 0)

    def test_the_walking_wounded_come_back(self):
        company = ShipsCompany(complement=80, fit=50, quality=ABLE).recover(10)
        self.assertEqual(company.fit, 60)

    def test_but_no_further_than_full(self):
        """Coming back up is not the same as finding people who were never aboard."""
        company = ShipsCompany(complement=80, fit=70, quality=ABLE).recover(400)
        self.assertEqual(company.fit, 80)

    def test_more_standing_than_she_carries_is_refused(self):
        with self.assertRaises(ValueError):
            ShipsCompany(complement=10, fit=40, quality=ABLE)

    def test_a_negative_company_is_refused(self):
        with self.assertRaises(ValueError):
            ShipsCompany(complement=-1, fit=0, quality=ABLE)

    def test_and_negative_survivors(self):
        with self.assertRaises(ValueError):
            ShipsCompany(complement=10, fit=-1, quality=ABLE)

    def test_an_empty_hull_has_no_casualty_fraction_to_divide(self):
        self.assertAlmostEqual(ShipsCompany(complement=0, fit=0).casualty_fraction, 0.0)


class TestExhaustion(BaseEvenniaTest):
    """What pulling an oar costs, at ship scale."""

    def test_hard_pulling_spends_them(self):
        self.assertGreater(spend(0.0, 1.0, 600.0), 0.0)

    def test_easy_oars_let_them_recover(self):
        self.assertLess(spend(0.8, 0.0, 600.0), 0.8)

    def test_they_tend_towards_the_effort_asked(self):
        """Not an accumulator. A crew asked for half tends to half, and stays there."""
        settled = 0.0
        for _ in range(200):
            settled = spend(settled, 0.5, 300.0)
        self.assertAlmostEqual(settled, 0.5, places=3)

    def test_a_racing_stroke_gets_most_of_the_way_in_half_an_hour(self):
        self.assertGreater(spend(0.0, 1.0, SPEND_SECONDS), 0.5)

    def test_recovery_is_slower_than_spending(self):
        """The asymmetry is why a captain cannot simply stop and have them back."""
        self.assertGreater(RECOVER_SECONDS, SPEND_SECONDS)
        spent = spend(0.5, 1.0, 600.0) - 0.5
        rested = 0.5 - spend(0.5, 0.0, 600.0)
        self.assertGreater(spent, rested)

    def test_it_does_not_depend_on_how_often_it_is_asked(self):
        """
        A tick that runs twice as often must not tire a crew twice as fast, or the
        simulation changes when the server gets busy.

        """
        once = spend(0.0, 1.0, 600.0)
        many = 0.0
        for _ in range(60):
            many = spend(many, 1.0, 10.0)
        self.assertAlmostEqual(once, many, places=6)

    def test_no_time_passing_costs_nothing(self):
        self.assertAlmostEqual(spend(0.3, 1.0, 0.0), 0.3)

    def test_they_never_go_past_spent(self):
        self.assertLessEqual(spend(0.99, 1.0, 100000.0), 1.0)


class TestMoraleReading(BaseEvenniaTest):
    """Where they would settle, given how things stand."""

    def test_nothing_bearing_on_them_is_their_base(self):
        self.assertAlmostEqual(reading(ABLE.base_morale), ABLE.base_morale)

    def test_a_bad_factor_lowers_it(self):
        self.assertLess(reading(0.6, (BOARDED,)), 0.6)

    def test_a_good_one_raises_it(self):
        self.assertGreater(reading(0.6, (ENEMY_STRUCK,)), 0.6)

    def test_they_add_up(self):
        one = reading(0.9, (BOARDED,))
        two = reading(0.9, (BOARDED, CAPTAIN_LOST))
        self.assertLess(two, one)

    def test_losing_the_captain_is_worse_than_losing_an_officer(self):
        self.assertLess(reading(0.8, (CAPTAIN_LOST,)), reading(0.8, (OFFICER_LOST,)))

    def test_it_never_leaves_the_scale(self):
        self.assertGreaterEqual(reading(0.1, (CAPTAIN_LOST, BOARDED, AGROUND)), 0.0)
        self.assertLessEqual(reading(0.95, (ENEMY_STRUCK, ENEMY_STRUCK)), 1.0)

    def test_some_factors_never_touch_the_standing_condition(self):
        """
        Whether the enemy takes prisoners does not change how a crew feel hour to
        hour. It changes entirely what they will do when asked to give up.

        """
        self.assertAlmostEqual(reading(0.6, (QUARTER_REFUSED,)), 0.6)
        self.assertGreater(when_asked(0.6, (QUARTER_REFUSED,)), 0.6)

    def test_an_enemy_who_gives_quarter_makes_striking_easier(self):
        self.assertLess(when_asked(0.6, (QUARTER_OFFERED,)), 0.6)

    def test_being_asked_starts_from_where_they_actually_stand(self):
        """
        Not rebuilt from their quality. A crew ground down for an hour and a crew who
        have not are different crews when the question is put, and recomputing from
        the base would throw the hour away.

        """
        self.assertLess(when_asked(0.2, (QUARTER_REFUSED,)), when_asked(0.8, (QUARTER_REFUSED,)))

    def test_an_ordinary_factor_is_ignored_when_asked(self):
        self.assertAlmostEqual(when_asked(0.6, (BOARDED,)), 0.6)

    def test_a_game_can_bring_its_own(self):
        """Setting-specific morale belongs to the setting."""
        cursed = Factor("the ship is cursed", -0.4)
        self.assertAlmostEqual(reading(0.6, (cursed,)), 0.2)


class TestBands(BaseEvenniaTest):
    """Which of the five recognisable states they are in."""

    def test_the_whole_scale_is_covered(self):
        for value in (0.0, 0.14, 0.15, 0.34, 0.35, 0.54, 0.55, 0.74, 0.75, 1.0):
            self.assertIn(band_of(value), (BROKEN, WAVERING, SHAKEN, UNEASY, STEADY))

    def test_they_run_in_order(self):
        self.assertEqual(band_of(1.0), STEADY)
        self.assertEqual(band_of(0.6), UNEASY)
        self.assertEqual(band_of(0.4), SHAKEN)
        self.assertEqual(band_of(0.2), WAVERING)
        self.assertEqual(band_of(0.0), BROKEN)

    def test_a_worse_band_costs_her_more(self):
        self.assertLess(hesitation(1.0), hesitation(0.6))
        self.assertLess(hesitation(0.6), hesitation(0.4))
        self.assertLess(hesitation(0.4), hesitation(0.2))
        self.assertLess(hesitation(0.2), hesitation(0.0))

    def test_a_steady_crew_lose_nothing(self):
        self.assertAlmostEqual(hesitation(1.0), 0.0)

    def test_a_broken_one_is_not_useless(self):
        """They are frightened, not gone. Half of them is still half of them."""
        self.assertLess(hesitation(0.0), 1.0)


class TestSettling(BaseEvenniaTest):
    """The standing condition, moving."""

    def test_it_moves_towards_the_target(self):
        self.assertLess(settle(0.8, 0.2, 60.0), 0.8)
        self.assertGreater(settle(0.2, 0.8, 60.0), 0.2)

    def test_it_never_overshoots(self):
        """To within float noise; the curve approaches the target, it does not cross."""
        self.assertAlmostEqual(settle(0.8, 0.2, 100000.0), 0.2, places=9)
        self.assertAlmostEqual(settle(0.2, 0.8, 100000.0), 0.8, places=9)

    def test_it_falls_faster_than_it_rises(self):
        """
        The whole reason morale is a standing condition rather than a check. A
        captain who spends his people cannot stop spending them and have them back.

        """
        self.assertLess(FALL_SECONDS, RISE_SECONDS)
        fallen = 0.5 - settle(0.5, 0.0, 60.0)
        risen = settle(0.5, 1.0, 60.0) - 0.5
        self.assertGreater(fallen, risen)

    def test_it_does_not_depend_on_how_often_it_is_asked(self):
        once = settle(0.9, 0.1, 300.0)
        many = 0.9
        for _ in range(30):
            many = settle(many, 0.1, 10.0)
        self.assertAlmostEqual(once, many, places=6)

    def test_no_time_passing_moves_nobody(self):
        self.assertAlmostEqual(settle(0.4, 0.9, 0.0), 0.4)

    def test_no_time_passing_beats_an_instant_span(self):
        """
        Two rules meet here and one of them has to win. Nothing should move when no
        time has passed, even where the response is configured as immediate - "no
        time" is a stronger claim than "arrives at once".

        """
        self.assertAlmostEqual(settle(0.4, 0.9, 0.0, fall=0.0, rise=0.0), 0.4)

    def test_a_clock_that_runs_backwards_moves_nobody(self):
        """
        The curve run with a negative span does not stand still, it accelerates the
        wrong way - so a clock that goes backwards would *raise* the morale of a crew
        being shelled. Refused rather than extrapolated.

        """
        self.assertAlmostEqual(settle(0.4, 0.9, -600.0), 0.4)
        self.assertAlmostEqual(spend(0.4, 1.0, -600.0), 0.4)

    def test_an_instant_span_arrives_at_once(self):
        self.assertAlmostEqual(settle(0.4, 0.9, 10.0, fall=0.0, rise=0.0), 0.9)

    def test_most_of_a_fall_happens_within_its_span(self):
        fallen = settle(1.0, 0.0, FALL_SECONDS)
        self.assertLess(fallen, 1.0 - math.exp(-1.0) + 0.01)
        self.assertGreater(fallen, 0.0)


class TestStriking(BaseEvenniaTest):
    """What a crew does when the enemy has beaten them."""

    def test_terrified_and_unhurt_they_fight_on(self):
        """One gate is not two. A frightened crew who have lost nobody hold."""
        self.assertFalse(strikes(0.0, casualties=0.0, floor=ABLE.casualty_floor))

    def test_cut_to_pieces_and_steady_they_fight_on(self):
        self.assertFalse(strikes(1.0, casualties=0.9 - 0.01, floor=ABLE.casualty_floor))

    def test_both_gates_open_and_they_strike(self):
        self.assertTrue(strikes(0.0, casualties=0.6, floor=ABLE.casualty_floor))

    def test_a_better_crew_must_be_hurt_more(self):
        """The floor is what makes a good crew hard to beat rather than merely brave."""
        hurt = 0.55
        self.assertTrue(strikes(0.0, hurt, floor=PRESSED.casualty_floor))
        self.assertFalse(strikes(0.0, hurt, floor=CRACK.casualty_floor))

    def test_past_rout_nobody_holds(self):
        """Not a question of nerve. There are not enough of them left to work her."""
        self.assertTrue(strikes(1.0, casualties=ROUT, floor=CRACK.casualty_floor))

    def test_the_reading_gate_is_real(self):
        self.assertFalse(strikes(STRIKE_READING + 0.01, 0.9 - 0.01, floor=0.1))
        self.assertTrue(strikes(STRIKE_READING, 0.9 - 0.01, floor=0.1))

    def test_without_a_roll_it_is_deterministic(self):
        for _ in range(5):
            self.assertTrue(strikes(0.0, 0.6, floor=ABLE.casualty_floor))

    def test_a_roll_can_save_her(self):
        """Variance, not the decision. The gates still have to be open."""
        self.assertFalse(strikes(0.0, 0.6, floor=ABLE.casualty_floor, roll=always))

    def test_and_can_condemn_her(self):
        self.assertTrue(strikes(0.0, 0.6, floor=ABLE.casualty_floor, roll=never))

    def test_a_roll_cannot_open_a_shut_gate(self):
        """A die that overrides the systems beneath it is a die that hollows them out."""
        self.assertFalse(strikes(0.0, casualties=0.0, floor=0.5, roll=never))
        self.assertFalse(strikes(1.0, casualties=0.6, floor=0.5, roll=never))

    def test_the_odds_scale_with_how_far_past_the_gates_she_is(self):
        """
        Not a coin flip once both gates open. A crew barely over the line usually
        hold; a crew far past it usually do not, and the same roll has to be able to
        tell those two apart or the gates are the only thing doing any work.

        """
        coin = fixed(0.7)
        barely = strikes(STRIKE_READING, casualties=0.4, floor=0.4, roll=coin)
        far = strikes(0.0, casualties=0.8, floor=0.4, roll=coin)
        self.assertFalse(barely)
        self.assertTrue(far)

    def test_both_margins_count_towards_the_odds(self):
        """
        Neither alone can carry it - the same argument the two gates make, applied
        to the odds instead of the question.

        """
        coin = fixed(0.85)
        reading_only = strikes(0.0, casualties=0.4, floor=0.4, roll=coin)
        losses_only = strikes(STRIKE_READING, casualties=0.8, floor=0.4, roll=coin)
        both = strikes(0.0, casualties=0.8, floor=0.4, roll=coin)
        self.assertFalse(reading_only)
        self.assertFalse(losses_only)
        self.assertTrue(both)


class TestGrievances(BaseEvenniaTest):
    """What a company holds against her command."""

    def test_a_rested_well_led_crew_hold_nothing(self):
        self.assertEqual(grievances(exhaustion=0.0, casualties=0.0, floor=0.5), ())

    def test_being_driven_past_bearing(self):
        self.assertIn(DRIVEN, grievances(exhaustion=1.0, floor=0.5))

    def test_being_merely_tired_is_not_a_grievance(self):
        self.assertNotIn(DRIVEN, grievances(exhaustion=0.5, floor=0.5))

    def test_being_spent_while_he_will_not_strike(self):
        self.assertIn(BUTCHERED, grievances(casualties=0.6, floor=0.5, struck=False))

    def test_but_not_once_he_has(self):
        """
        The same crew, cut to pieces in a fight he ended, have been unlucky. The
        difference is whether he would stop, and it is the whole distinction between
        mutiny and defeat.

        """
        self.assertNotIn(BUTCHERED, grievances(casualties=0.6, floor=0.5, struck=True))

    def test_having_nobody_to_answer_to(self):
        self.assertIn(LEADERLESS, grievances(has_captain=False))

    def test_they_can_hold_several_at_once(self):
        held = grievances(exhaustion=1.0, casualties=0.9, floor=0.5, has_captain=False)
        self.assertEqual(set(held), {DRIVEN, BUTCHERED, LEADERLESS})


class TestMutiny(BaseEvenniaTest):
    """What a crew does when the captain has beaten them."""

    def test_one_grievance_is_a_complaint(self):
        """Two is agreement, and agreement is what turns muttering into a rising."""
        self.assertFalse(mutinies(0.0, (DRIVEN,)))

    def test_two_is_a_rising(self):
        self.assertTrue(mutinies(0.0, (DRIVEN, LEADERLESS)))

    def test_frightened_men_obey(self):
        """Low morale is necessary and nowhere near sufficient."""
        self.assertFalse(mutinies(MUTINY_READING + 0.01, (DRIVEN, LEADERLESS)))

    def test_it_takes_frightened_men_with_somebody_to_blame(self):
        self.assertTrue(mutinies(MUTINY_READING, (DRIVEN, LEADERLESS)))

    def test_grievances_alone_are_not_enough(self):
        self.assertFalse(mutinies(1.0, (DRIVEN, BUTCHERED, LEADERLESS)))

    def test_without_a_roll_it_is_deterministic(self):
        for _ in range(5):
            self.assertTrue(mutinies(0.0, (DRIVEN, LEADERLESS)))

    def test_a_roll_adds_variance_only(self):
        self.assertFalse(mutinies(0.0, (DRIVEN, LEADERLESS), roll=always))
        self.assertTrue(mutinies(0.0, (DRIVEN, LEADERLESS), roll=never))

    def test_a_roll_cannot_open_a_shut_gate(self):
        self.assertFalse(mutinies(1.0, (DRIVEN, LEADERLESS), roll=never))
        self.assertFalse(mutinies(0.0, (DRIVEN,), roll=never))

    def test_the_count_is_tunable(self):
        self.assertTrue(mutinies(0.0, (DRIVEN,), needed=1))

    def test_the_odds_scale_with_the_weight_of_grievance(self):
        """Two men muttering and a ship that has had enough are not the same odds."""
        coin = fixed(0.7)
        barely = mutinies(MUTINY_READING, (DRIVEN, LEADERLESS), roll=coin)
        furious = mutinies(0.0, (DRIVEN, BUTCHERED, LEADERLESS, DRIVEN), roll=coin)
        self.assertFalse(barely)
        self.assertTrue(furious)


class CrewedTestCase(EmptySeaMixin, BaseEvenniaTest):
    """A hull with people in her."""

    def setUp(self):
        super().setUp()
        self.hull = self.a_ship("Kestrel")

    def a_ship(self, key):
        hull = create.create_object(Vessel, key=key)
        hull.length, hull.beam = 18.0, 5.4
        hull.motion_limits = MotionLimits(max_speed=6.0, acceleration=0.5, turn_rate=5.0)
        hull.maritime_position = WorldPosition(0.0, 0.0)
        deck = create.create_object(ShipRoom, key=f"{key} Deck")
        deck.vessel = hull
        deck.exposure = OPEN
        return hull


class TestCrewedShip(CrewedTestCase):
    """The Evennia-side face."""

    def test_she_starts_with_nobody(self):
        """
        Not an empty company - no company. A game that has adopted none of this must
        still be able to sail, and every other test in this contrib builds ships
        nobody has crewed.

        """
        self.assertIsNone(self.hull.company)

    def test_manning_her_fills_her(self):
        self.hull.man(60, ABLE)
        self.assertEqual(self.hull.company.complement, 60)
        self.assertEqual(self.hull.company.fit, 60)

    def test_and_sets_them_where_men_of_that_quality_start(self):
        self.hull.man(60, CRACK)
        self.assertAlmostEqual(self.hull.morale, CRACK.base_morale)

    def test_casualties_take_them_down(self):
        self.hull.man(60, ABLE)
        self.hull.take_casualties(20)
        self.assertEqual(self.hull.company.fit, 40)
        self.assertAlmostEqual(self.hull.company.casualty_fraction, 1.0 / 3.0)

    def test_hurting_a_ship_with_no_company_is_not_an_error(self):
        self.assertIsNone(self.hull.take_casualties(10))

    def test_she_can_be_paid_off(self):
        self.hull.man(60, ABLE)
        self.hull.company = None
        self.assertIsNone(self.hull.company)

    def test_the_band_follows_the_number(self):
        self.hull.man(60, CRACK)
        self.assertEqual(self.hull.morale_band, STEADY)
        self.hull.morale = 0.1
        self.assertEqual(self.hull.morale_band, BROKEN)

    def test_hesitation_follows_the_band(self):
        self.hull.man(60, CRACK)
        steady = self.hull.hesitation
        self.hull.morale = 0.1
        self.assertGreater(self.hull.hesitation, steady)

    def test_morale_stays_on_the_scale(self):
        self.hull.morale = 40.0
        self.assertAlmostEqual(self.hull.morale, 1.0)
        self.hull.morale = -3.0
        self.assertAlmostEqual(self.hull.morale, 0.0)


class TestSheSeesForHerself(CrewedTestCase):
    """Conditions a game should not have to remember to report."""

    def test_no_captain_aboard(self):
        self.hull.man(60, ABLE)
        self.assertIn(CAPTAIN_LOST, self.hull.conditions())

    def test_and_one_who_is(self):
        self.hull.man(60, ABLE)
        self.hull.captain = create.create_object(
            "evennia.objects.objects.DefaultCharacter", key="The master"
        )
        self.assertNotIn(CAPTAIN_LOST, self.hull.conditions())

    def test_being_aground(self):
        self.hull.man(60, ABLE)
        self.hull.aground = True
        self.assertIn(AGROUND, self.hull.conditions())

    def test_a_crew_who_mind_being_aground(self):
        """The point of deriving them: a game that supplies nothing still gets this."""
        self.hull.man(60, ABLE)
        self.hull.captain = create.create_object(
            "evennia.objects.objects.DefaultCharacter", key="The master"
        )
        self.hull.feel(600.0)
        steady = self.hull.morale

        self.hull.aground = True
        self.hull.feel(600.0)
        self.assertLess(self.hull.morale, steady)


class TestTimePassingOverThem(CrewedTestCase):
    """The standing condition, on a real hull."""

    def test_a_watch_with_nothing_happening_costs_nothing(self):
        self.hull.man(60, ABLE)
        self.hull.captain = create.create_object(
            "evennia.objects.objects.DefaultCharacter", key="The master"
        )
        self.hull.exhaustion = 0.0
        self.hull.stand_watch(600.0)
        self.assertAlmostEqual(self.hull.exhaustion, 0.0, places=3)

    def test_pulling_hard_spends_them(self):
        self.hull.man(6, ABLE)
        self.hull.oar_plan = OAR_PLANS["gig"]
        self.hull.stroke = STRETCH_OUT
        self.hull.stand_watch(1200.0)
        self.assertGreater(self.hull.exhaustion, 0.2)

    def test_and_easy_oars_bring_them_back(self):
        self.hull.man(6, ABLE)
        self.hull.oar_plan = OAR_PLANS["gig"]
        self.hull.exhaustion = 0.9
        self.hull.stroke = EASY_OARS
        self.hull.stand_watch(1200.0)
        self.assertLess(self.hull.exhaustion, 0.9)

    def test_a_ship_with_no_company_stands_no_watch(self):
        self.assertFalse(self.hull.stand_watch(600.0))

    def test_morale_settles_towards_what_is_happening(self):
        self.hull.man(60, PRESSED)
        self.hull.morale = 1.0
        self.hull.feel(3600.0)
        self.assertLess(self.hull.morale, 1.0)


class TestExhaustionSlowsHer(CrewedTestCase):
    """What the stat is for."""

    def test_spent_men_pull_slower(self):
        plan = OAR_PLANS["gig"]
        fresh = rowed_speed(plan, GIVE_WAY, 6, exhaustion=0.0)
        spent_crew = rowed_speed(plan, GIVE_WAY, 6, exhaustion=1.0)
        self.assertLess(spent_crew, fresh)

    def test_but_they_still_pull(self):
        """A boat rowed by exhausted men is slow rather than stopped."""
        self.assertGreater(rowed_speed(OAR_PLANS["gig"], GIVE_WAY, 6, exhaustion=1.0), 0.0)

    def test_a_fresh_crew_is_unchanged(self):
        plan = OAR_PLANS["gig"]
        self.assertAlmostEqual(
            rowed_speed(plan, GIVE_WAY, 6, exhaustion=0.0),
            plan.rated_speed * 0.75,
        )

    def test_the_boat_feels_it(self):
        self.hull.man(6, ABLE)
        self.hull.oar_plan = OAR_PLANS["gig"]
        self.hull.stroke = GIVE_WAY
        fresh = self.hull.rowing_speed()
        self.hull.exhaustion = 1.0
        self.assertLess(self.hull.rowing_speed(), fresh)


class TestWhoIsAtTheOars(CrewedTestCase):
    """Two ways of knowing, both real."""

    def test_a_company_mans_the_looms(self):
        """
        A galley's two hundred oarsmen are a number on the hull. Two hundred objects
        to be counted every tick would be absurd.

        """
        self.hull.man(200, PRESSED)
        self.hull.oar_plan = OAR_PLANS["cutter"]
        self.assertEqual(self.hull.rowing_crew, OAR_PLANS["cutter"].positions)

    def test_a_shorthanded_company_leaves_looms_empty(self):
        self.hull.man(12, ABLE)
        self.hull.oar_plan = OAR_PLANS["cutter"]
        self.hull.take_casualties(8)
        self.assertEqual(self.hull.rowing_crew, 4)

    def test_a_boat_nobody_crewed_still_counts_heads(self):
        """A gig pulled by whoever climbed into her is exactly the people in her."""
        self.hull.oar_plan = OAR_PLANS["gig"]
        deck = self.hull.ship_rooms[0]
        for number in range(3):
            create.create_object(
                "evennia.objects.objects.DefaultCharacter",
                key=f"Hand {number}",
                location=deck,
            )
        self.assertEqual(self.hull.rowing_crew, 3)


class TestSheStopsOrRises(CrewedTestCase):
    """The two collapses, on a real hull."""

    def a_captain(self):
        captain = create.create_object("evennia.objects.objects.DefaultCharacter", key="The master")
        self.hull.captain = captain
        return captain

    def test_a_fresh_crew_do_neither(self):
        self.hull.man(60, ABLE)
        self.a_captain()
        self.assertFalse(self.hull.will_strike())
        self.assertFalse(self.hull.will_mutiny())

    def test_a_beaten_crew_strike(self):
        self.hull.man(60, ABLE)
        self.a_captain()
        self.hull.take_casualties(40)
        self.hull.morale = 0.0
        self.assertTrue(self.hull.will_strike())

    def test_a_ship_with_no_company_does_not(self):
        self.hull.morale = 0.0
        self.assertFalse(self.hull.will_strike())
        self.assertFalse(self.hull.will_mutiny())

    def test_a_driven_leaderless_crew_rise(self):
        """Both grievances are command's doing, which is what makes it a mutiny."""
        self.hull.man(60, ABLE)
        self.hull.exhaustion = 1.0
        self.hull.morale = 0.0
        held = self.hull.held_against_command()
        self.assertEqual(set(held), {DRIVEN, LEADERLESS})
        self.assertTrue(self.hull.will_mutiny())

    def test_a_crew_who_have_struck_do_not_rise(self):
        """The fight is over. Rising now is a different story than this one."""
        self.hull.man(60, ABLE)
        self.hull.exhaustion = 1.0
        self.hull.morale = 0.0
        self.hull.db.struck_to = self.a_ship("Petrel")
        self.assertTrue(self.hull.struck)
        self.assertFalse(self.hull.will_mutiny())

    def test_being_boarded_is_not_command_s_fault(self):
        """
        The distinction the two collapses exist to draw. An enemy on the deck ruins
        morale and gives the crew nothing to hold against their own captain.

        """
        self.hull.man(60, ABLE)
        self.a_captain()
        self.hull.morale = 0.0
        self.assertNotIn(DRIVEN, self.hull.held_against_command())
        self.assertFalse(self.hull.will_mutiny())

    def test_a_roll_is_obeyed_here_too(self):
        self.hull.man(60, ABLE)
        self.a_captain()
        self.hull.take_casualties(40)
        self.hull.morale = 0.0
        self.assertFalse(self.hull.will_strike(roll=always))
        self.assertTrue(self.hull.will_strike(roll=never))

    def test_quarter_refused_stiffens_them(self):
        """
        An enemy who kills prisoners is a reason to keep fighting, and it bears on
        this question only - it does not change how they feel hour to hour.

        """
        self.hull.man(60, SEASONED)
        self.a_captain()
        self.hull.take_casualties(40)
        self.hull.morale = STRIKE_READING
        self.assertTrue(self.hull.will_strike(factors=(QUARTER_OFFERED,)))
        self.assertFalse(self.hull.will_strike(factors=(QUARTER_REFUSED,)))


class TestQualityIsStored(CrewedTestCase):
    """It has to survive a reload, which means it has to survive a pickle."""

    def test_it_comes_back_as_what_it_was(self):
        self.hull.man(60, SEASONED)
        self.assertEqual(self.hull.company.quality, SEASONED)

    def test_a_blended_quality_survives_too(self):
        mixed = blended(((LANDSMEN, 30), (ORDINARY, 10)))
        self.hull.company = ShipsCompany(complement=40, fit=40, quality=mixed)
        self.assertAlmostEqual(self.hull.company.quality.skill, mixed.skill)

    def test_a_custom_quality_is_allowed(self):
        """A game with its own gradations should not have to use ours."""
        marines = CrewQuality("marines", base_morale=0.9, casualty_floor=0.9, skill=0.5)
        self.hull.company = ShipsCompany(complement=20, fit=20, quality=marines)
        self.assertEqual(self.hull.company.quality.key, "marines")


class TestTheCrewCommand(CrewedTestCase):
    """What a captain actually sees."""

    def voice(self):
        """
        Returns:
            text (str): The report, as one block.

        """
        return chr(10).join(self.hull.narrator.crew_report(self.hull))

    def test_a_ship_nobody_crewed_says_so(self):
        self.assertIn("no ship's company", self.voice())

    def test_it_counts_them(self):
        self.hull.man(60, ABLE)
        self.assertIn("60 of 60 hands", self.voice())

    def test_it_says_what_they_are_rated(self):
        self.hull.man(60, SEASONED)
        self.assertIn("seasoned", self.voice())

    def test_casualties_appear_only_once_there_are_some(self):
        self.hull.man(60, ABLE)
        self.assertNotIn("Casualties", self.voice())
        self.hull.take_casualties(15)
        self.assertIn("Casualties", self.voice())

    def test_it_describes_the_band_rather_than_the_number(self):
        """Nobody on a deck ever knew their crew were at sixty-one per cent."""
        self.hull.man(60, CRACK)
        said = self.voice()
        self.assertIn("steady", said)
        self.assertNotIn("0.8", said)

    def test_a_broken_crew_read_differently(self):
        self.hull.man(60, ABLE)
        self.hull.morale = 0.0
        self.assertIn("half done", self.voice())

    def test_it_describes_how_spent_they_are(self):
        self.hull.man(60, ABLE)
        self.assertIn("fresh", self.voice())
        self.hull.exhaustion = 1.0
        self.assertIn("nothing left in them", self.voice())

    def test_every_exhaustion_has_words(self):
        self.hull.man(60, ABLE)
        for spent in (0.0, 0.2, 0.5, 0.7, 0.9, 1.0):
            self.assertTrue(self.hull.narrator.spent_words(spent))

    def test_every_band_has_words(self):
        self.hull.man(60, ABLE)
        for value in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0):
            self.hull.morale = value
            self.assertIn("They are", self.voice())

    def test_grievances_are_named_rather_than_counted(self):
        """
        The part worth having. A number says his people are unhappy; this says what
        about, and every one of them is something he did.

        """
        self.hull.man(60, ABLE)
        self.hull.exhaustion = 1.0
        said = self.voice()
        self.assertIn("hold against you", said)
        self.assertIn("driven past what they have in them", said)
        self.assertIn("nobody aft giving orders", said)

    def test_a_well_led_rested_crew_hold_nothing(self):
        self.hull.man(60, ABLE)
        self.hull.captain = create.create_object(
            "evennia.objects.objects.DefaultCharacter", key="The master"
        )
        self.assertNotIn("hold against you", self.voice())
