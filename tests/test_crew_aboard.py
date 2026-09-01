"""
Tests for a ship's company aboard an actual ship.

The rules themselves are in `test_crew`. These are the ones that need a hull under them:
what she sees for herself, what a watch costs her people, when she strikes or rises, and
what her company weighs in the hold.

Several of the bugs this suite has caught were only reachable from here. A company assigned
to a real vessel came back without its divisions; every pure-domain test passed.

"""

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest

from ..crew import (
    ABLE,
    CRACK,
    LANDSMEN,
    MARINES,
    MASS_PER_HAND,
    ORDINARY,
    PRESSED,
    SEAMEN,
    SEASONED,
    CrewQuality,
    Division,
    ShipsCompany,
    blended,
)
from ..morale import (
    AGROUND,
    BROKEN,
    CAPTAIN_LOST,
    DRIVEN,
    LEADERLESS,
    QUARTER_OFFERED,
    QUARTER_REFUSED,
    STEADY,
    STRIKE_READING,
)
from ..motion import MotionLimits
from ..oars import EASY_OARS, GIVE_WAY, OAR_PLANS, STRETCH_OUT, rowed_speed
from ..position import WorldPosition
from ..rooms import ShipRoom
from ..typeclasses import Vessel
from ..vessel import OPEN, VesselCapacity
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


class TestPeopleAreDeadweight(CrewedTestCase):
    """
    The cost of a fighting complement, with no money in it.

    Gary wanted shipping marines to be a decision. It already is, because people
    weigh something: every marine aboard is cargo she did not carry. That is true in
    a game with an economy and in one without, which is why it belongs here and the
    price of the man does not.

    """

    def setUp(self):
        super().setUp()
        self.hull.capacity = VesselCapacity(displacement=100000.0, internal_volume=400.0)

    def test_a_company_eats_into_what_she_can_carry(self):
        empty = self.hull.deadweight
        self.hull.man(60, ABLE)
        self.assertLess(self.hull.deadweight, empty)

    def test_by_what_they_weigh(self):
        empty = self.hull.deadweight
        self.hull.man(60, ABLE)
        self.assertAlmostEqual(empty - self.hull.deadweight, 60 * MASS_PER_HAND)

    def test_a_bigger_company_costs_more_cargo(self):
        self.hull.man(30, ABLE)
        lightly = self.hull.deadweight
        self.hull.man(90, ABLE)
        self.assertLess(self.hull.deadweight, lightly)

    def test_the_merchantman_s_choice(self):
        """
        The same sixty people either way. Shipping marines buys her a harder prize
        and costs her nothing at all in cargo - the cost is in what those hands
        cannot do, not in what they weigh.

        """
        self.hull.company = ShipsCompany.of([Division(SEAMEN, 60, 60, ABLE)])
        peaceful = self.hull.deadweight
        peaceful_strength = self.hull.company.strength

        self.hull.company = ShipsCompany.of(
            [Division(SEAMEN, 40, 40, ABLE), Division(MARINES, 20, 20, ABLE)]
        )
        self.assertAlmostEqual(self.hull.deadweight, peaceful)
        self.assertGreater(self.hull.company.strength, peaceful_strength)
        self.assertLess(self.hull.company.hands, 60 * SEAMEN.working * ABLE.skill)

    def test_a_larger_guard_does_cost_cargo(self):
        """Sixty seamen and twenty marines is eighty mouths, and the hold pays."""
        self.hull.company = ShipsCompany.of([Division(SEAMEN, 60, 60, ABLE)])
        unguarded = self.hull.deadweight
        self.hull.company = ShipsCompany.of(
            [Division(SEAMEN, 60, 60, ABLE), Division(MARINES, 20, 20, ABLE)]
        )
        self.assertAlmostEqual(unguarded - self.hull.deadweight, 20 * MASS_PER_HAND)

    def test_casualties_do_not_free_up_the_hold(self):
        """A hold that grew after a battle would be grotesque."""
        self.hull.man(60, ABLE)
        laden = self.hull.deadweight
        self.hull.take_casualties(30)
        self.assertAlmostEqual(self.hull.deadweight, laden)

    def test_a_ship_nobody_crewed_carries_everything(self):
        self.assertAlmostEqual(self.hull.deadweight, 100000.0)


class TestNobodyAboardNobodyHesitates(CrewedTestCase):
    """
    A vessel with no ship's company carries no morale penalty.

    She reported a morale of one half - the default a quality carries - which put
    her in the shaken band and served her guns fifteen per cent slower for no reason
    at all. Found by loading a gun on a live ship and noticing the reload was six
    seconds long than the gun's own rate.

    """

    def test_an_uncrewed_ship_does_not_hesitate(self):
        self.assertIsNone(self.hull.company)
        self.assertAlmostEqual(self.hull.hesitation, 0.0)

    def test_a_crewed_one_can(self):
        self.hull.man(60, ABLE)
        self.hull.morale = 0.0
        self.assertGreater(self.hull.hesitation, 0.0)

    def test_and_a_steady_crew_still_does_not(self):
        self.hull.man(60, CRACK)
        self.assertAlmostEqual(self.hull.hesitation, 0.0)

    def test_her_guns_are_served_at_their_own_rate(self):
        """The symptom that gave it away."""
        from ..damage import serving_time

        self.assertAlmostEqual(serving_time(90.0, self.hull.damage, self.hull.hesitation), 90.0)
