"""
Tests for the rules a ship's company runs on: what they are made of, what it costs them,
and when they stop.

The arithmetic only. What happens when a company is put aboard an actual hull lives in
`test_crew_aboard` - these two change for different reasons, which is the test of whether
a seam is real rather than a convenient place to cut a long file.

"""

import math

from evennia.utils.test_resources import BaseEvenniaTest

from ..crew import (
    ABLE,
    CRACK,
    DEFAULT_QUALITY,
    PRESSED,
    QUALITIES,
    RECOVER_SECONDS,
    SPEND_SECONDS,
    Division,
    MARINES,
    OARSMEN,
    SEAMEN,
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


class TestRatings(BaseEvenniaTest):
    """What a group aboard was shipped to do, as against how good they are."""

    def test_seamen_work_her_best(self):
        self.assertGreater(SEAMEN.working, OARSMEN.working)
        self.assertGreater(OARSMEN.working, MARINES.working)

    def test_marines_fight_best(self):
        self.assertGreater(MARINES.fighting, SEAMEN.fighting)
        self.assertGreater(SEAMEN.fighting, OARSMEN.fighting)

    def test_a_marine_cannot_reef_a_topsail(self):
        """
        Close to useless at working her, which is the whole cost of carrying them
        and the reason a merchantman has to think about it.

        """
        self.assertLess(MARINES.working, 0.3)

    def test_rating_and_quality_are_different_questions(self):
        """
        A crack marine and a crack seaman are both crack, and only one of them can
        hand a topsail in a gale.

        """
        crack_seaman = Division(SEAMEN, 1, 1, CRACK)
        crack_marine = Division(MARINES, 1, 1, CRACK)
        self.assertGreater(crack_seaman.hands, crack_marine.hands)
        self.assertGreater(crack_marine.strength, crack_seaman.strength)


class TestFightingIsNotSeamanship(BaseEvenniaTest):
    """
    The gap this item exists to close.

    `strength` read `quality.skill`, which is how well they work the ship - so a
    crack crew of seamen was the equal of a party of marines, which is exactly
    backwards. The marines cannot reef a topsail and will still carry a deck.

    """

    def test_quality_carries_both_axes(self):
        for quality in QUALITIES:
            self.assertGreater(quality.skill, 0.0)
            self.assertGreater(quality.fighting, 0.0)

    def test_they_are_not_the_same_number(self):
        self.assertNotEqual(
            [quality.skill for quality in QUALITIES],
            [quality.fighting for quality in QUALITIES],
        )

    def test_courage_spreads_less_than_trade(self):
        """
        Seamanship is a trade and takes years; standing up in a melee is much less
        a matter of training, so the spread between the worst and best is narrower.

        """
        skills = [quality.skill for quality in QUALITIES]
        fights = [quality.fighting for quality in QUALITIES]
        self.assertLess(max(fights) - min(fights), max(skills) - min(skills))

    def test_blending_carries_the_fighting_axis(self):
        mixed = blended(((PRESSED, 10), (CRACK, 10)))
        self.assertGreater(mixed.fighting, PRESSED.fighting)
        self.assertLess(mixed.fighting, CRACK.fighting)


class TestDivisions(BaseEvenniaTest):
    """A company made of groups."""

    def a_mixed_company(self, marines=20, seamen=40):
        """
        Returns:
            company (ShipsCompany): Seamen and marines together.

        """
        parts = [Division(SEAMEN, seamen, seamen, ABLE)]
        if marines:
            parts.append(Division(MARINES, marines, marines, ABLE))
        return ShipsCompany.of(parts)

    def test_the_totals_add_up(self):
        company = self.a_mixed_company()
        self.assertEqual(company.complement, 60)
        self.assertEqual(company.fit, 60)

    def test_the_parts_are_kept(self):
        company = self.a_mixed_company()
        self.assertIsNotNone(company.division(MARINES))
        self.assertEqual(company.division(MARINES).complement, 20)

    def test_a_group_she_does_not_carry(self):
        self.assertIsNone(self.a_mixed_company(marines=0).division(MARINES))

    def test_marines_make_her_a_worse_ship_and_a_harder_prize(self):
        """
        The trade Gary asked for, and it needs no money to be real: the same sixty
        people, and every marine is one fewer hand to work her.

        """
        without = self.a_mixed_company(marines=0, seamen=60)
        heavy = self.a_mixed_company(marines=30, seamen=30)
        self.assertGreater(without.hands, heavy.hands)
        self.assertGreater(heavy.strength, without.strength)

    def test_marines_earn_their_keep_at_equal_quality(self):
        """Otherwise nobody would ever ship them."""
        seamen_only = ShipsCompany.of([Division(SEAMEN, 60, 60, ABLE)])
        with_marines = self.a_mixed_company(marines=20, seamen=40)
        self.assertGreater(with_marines.strength, seamen_only.strength)

    def test_an_undivided_company_is_taken_for_seamen(self):
        """What a merchantman's whole company is."""
        plain = ShipsCompany(complement=60, fit=60, quality=ABLE)
        divided = ShipsCompany.of([Division(SEAMEN, 60, 60, ABLE)])
        self.assertAlmostEqual(plain.strength, divided.strength)
        self.assertAlmostEqual(plain.hands, divided.hands)

    def test_the_blend_reflects_who_is_left(self):
        company = ShipsCompany.of(
            [Division(SEAMEN, 40, 40, PRESSED), Division(MARINES, 20, 20, CRACK)]
        )
        self.assertGreater(company.quality.fighting, PRESSED.fighting)
        self.assertLess(company.quality.fighting, CRACK.fighting)

    def test_a_company_of_nobody_is_refused(self):
        """
        And refused in terms the caller can act on. `blended` would raise anyway,
        further down, complaining about qualities - which is true and unhelpful when
        what actually happened is that somebody built a company with nobody in it.
        Mutation testing found the guard unkillable precisely because the deeper
        error was masking it.

        """
        with self.assertRaises(ValueError) as refused:
            ShipsCompany.of([])
        self.assertIn("division", str(refused.exception))

    def test_casualties_in_one_division_weaken_that_trade(self):
        """
        Losing the marines and losing the topmen are different losses, and a
        company that could not say which had happened would be back where it
        started.

        """
        whole = ShipsCompany.of([Division(SEAMEN, 40, 40, ABLE), Division(MARINES, 20, 20, ABLE)])
        marines_gone = ShipsCompany.of(
            [Division(SEAMEN, 40, 40, ABLE), Division(MARINES, 20, 0, ABLE)]
        )
        seamen_gone = ShipsCompany.of(
            [Division(SEAMEN, 40, 20, ABLE), Division(MARINES, 20, 20, ABLE)]
        )

        # Twenty of each, lost. Which twenty decides what she can no longer do.
        working_cost_of_marines = whole.hands - marines_gone.hands
        working_cost_of_seamen = whole.hands - seamen_gone.hands
        self.assertLess(working_cost_of_marines, working_cost_of_seamen)

        fighting_cost_of_marines = whole.strength - marines_gone.strength
        fighting_cost_of_seamen = whole.strength - seamen_gone.strength
        self.assertGreater(fighting_cost_of_marines, fighting_cost_of_seamen)
