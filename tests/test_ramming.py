"""
Ramming and sheering.

What is worth asserting here is not a table of outcomes - there is no table - but that the
arithmetic behaves the way a collision does. Faster hurts more than slower, by the square.
Heavier hurts more than lighter. A blow on the beam is worse than a fine one. Chasing her is
a poor way to hit her and meeting her is a violent one. And the ship delivering it never
gets away free, which is the whole reason ramming is a decision.

Relationships rather than magic numbers, wherever a relationship is the real claim. A test
that pins `weight == 41.7` passes until somebody retunes one constant and then fails without
telling anybody what broke.
"""

import math

from django.test import override_settings
from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest, BaseEvenniaTestCase

from .. import ramming
from ..damage import resilience
from ..motion import HelmOrders, MotionLimits
from ..position import WorldPosition
from ..rooms import ShipRoom
from ..tactical import PORT_BROADSIDE, STARBOARD_BROADSIDE
from ..typeclasses import Vessel
from ..weapons import Mount, WeaponType
from ..vessel import OPEN
from .base import EmptySeaMixin

#: A brig: length, beam, draft in metres. About two hundred tons.
BRIG = (30.0, 8.5, 3.6)

#: A ship's boat, for the cases about size.
BOAT = (7.0, 2.2, 0.6)

#: A frigate.
FRIGATE = (46.0, 12.0, 5.2)


def ram(**changes):
    """
    Args:
        **changes: Anything to differ from a brig striking a stopped brig square on the
            beam at four knots.

    Returns:
        result (RamResult): What came of it.

    Notes:
        The default is the reference collision the constants were set against, so a test
        that changes one thing is genuinely changing one thing.

    """
    setup = {
        "speed": 2.06,
        "heading": 0.0,
        "bearing": 0.0,
        "length": BRIG[0],
        "beam": BRIG[1],
        "draft": BRIG[2],
        "target_length": BRIG[0],
        "target_beam": BRIG[1],
        "target_draft": BRIG[2],
        "target_heading": 90.0,
    }
    setup.update(changes)
    return ramming.ram(**setup)


class TestTheBlowItself(BaseEvenniaTestCase):
    """The energy, and what decides how much of it lands."""

    def test_a_ram_on_the_beam_lands(self):
        self.assertTrue(ram().success)

    def test_speed_tells_by_the_square(self):
        """
        One half m vee squared, and the squared is the part that matters at the helm. Twice
        the speed is four times the collision, which is why a captain who wants to ram must
        commit to it and cannot creep up and lean on her.

        """
        slow = ram(speed=2.0)
        fast = ram(speed=4.0)
        self.assertAlmostEqual(fast.energy / slow.energy, 4.0, places=6)

    def test_weight_tells(self):
        """A heavier ship hurts more, because she is heavier and for no other reason."""
        light = ram(length=20.0, beam=6.0, draft=2.5)
        heavy = ram(length=FRIGATE[0], beam=FRIGATE[1], draft=FRIGATE[2])
        self.assertGreater(heavy.energy, light.energy)

    def test_the_lighter_ship_decides_the_collision(self):
        """
        A boat rowed at a frigate cannot deliver a frigate's worth of energy, because the
        energy has to come from somewhere and it comes from the mass that is moving. This is
        what stops a determined dinghy from opening a ship of the line.

        """
        result = ram(
            length=BOAT[0],
            beam=BOAT[1],
            draft=BOAT[2],
            target_length=FRIGATE[0],
            target_beam=FRIGATE[1],
            target_draft=FRIGATE[2],
            speed=4.0,
        )
        boat = ramming.displacement(*BOAT)
        frigate = ramming.displacement(*FRIGATE)
        reduced = boat * frigate / (boat + frigate)
        self.assertAlmostEqual(result.energy, 0.5 * reduced * 16.0, places=3)
        self.assertLess(reduced, boat, "the reduced mass is never more than the lighter ship")

    def test_a_blow_on_the_beam_beats_a_fine_one(self):
        """
        The reason crossing her course is worth the trouble. Square on her side, the whole
        collision goes into her; fine, most of it is turned along her length.

        """
        square = ram(target_heading=90.0)
        fine = ram(target_heading=30.0)
        self.assertGreater(square.weight, fine.weight)

    def test_a_course_along_her_side_glances_and_is_not_a_ram(self):
        """
        Running *along* the face rather than into it. She is beam-on and he is crossing her
        side almost parallel to it, which scrapes down her topsides and is `sheer`'s
        business, not a collision's.

        """
        result = ram(speed=20.0, heading=85.0, target_heading=90.0)
        self.assertFalse(result.success)
        self.assertEqual(result.code, "glanced")

    def test_running_square_into_her_stem_is_not_a_graze(self):
        """
        The case that broke the first version. Obliquity was measured from her beam, so the
        squarest blow there is - straight into her bow - came out at ninety degrees off and
        was refused as a glance.

        """
        self.assertTrue(ram(target_heading=180.0).success)

    def test_creeping_alongside_is_not_a_collision(self):
        """
        Every ship that ever came alongside another is moving relative to her. Without a
        floor, docking would be ramming.

        """
        result = ram(speed=0.15)
        self.assertFalse(result.success)
        self.assertEqual(result.code, "too_gently")

    def test_chasing_her_is_a_poor_way_to_ram_her(self):
        """
        Only closure does damage. Overhauling a ship making almost your own speed is a
        gentle bump however fast the pair of you are crossing the ground - and this falls
        out of the arithmetic rather than being a rule anybody wrote.

        """
        chasing = ramming.impact_speed(
            speed=5.0, heading=0.0, bearing=0.0, target_speed=4.6, target_heading=0.0
        )
        meeting = ramming.impact_speed(
            speed=5.0, heading=0.0, bearing=0.0, target_speed=4.6, target_heading=180.0
        )
        self.assertAlmostEqual(chasing, 0.4, places=6)
        self.assertAlmostEqual(meeting, 9.6, places=6)


class TestTheRammerPaysToo(BaseEvenniaTestCase):
    """
    The point of the whole item. A ram that only hurt the other ship would be a free
    attack, and a free attack is not a decision.
    """

    def test_she_takes_damage_as_well(self):
        self.assertGreater(ram().recoil, 0.0)

    def test_a_beak_drives_more_in_and_takes_less_back(self):
        """
        What a ram *is*: structure built forward of the hull so the collision happens out
        there rather than in her own timbers. Both halves of that, in one assertion each.

        """
        plain = ram(fitting=ramming.PLAIN)
        beaked = ram(fitting=ramming.RAM)
        self.assertGreater(beaked.weight, plain.weight)
        self.assertLess(beaked.recoil, plain.recoil)

    def test_bow_to_bow_is_bad_for_both(self):
        """
        The angle that spares the rammer is the angle that spares the target, so a fine
        blow is cheap for everybody. Meeting her head on is the one case where the geometry
        helps neither, and it is the collision every seaman is taught to avoid.

        """
        head_on = ram(target_heading=180.0, target_speed=2.06)
        crossing = ram(target_heading=90.0, target_speed=2.06)

        self.assertTrue(head_on.head_on)
        self.assertFalse(crossing.head_on)

        # Nothing is added for it. Two ships meeting close at the sum of their speeds and
        # the energy goes as the square of that, so the arithmetic makes it the worst
        # collision on the board without anybody writing a rule that says so.
        self.assertAlmostEqual(head_on.speed, 2.0 * crossing.speed, places=6)
        self.assertGreater(head_on.recoil, crossing.recoil)
        self.assertGreater(head_on.weight, crossing.weight)

    def test_an_unknown_fitting_is_an_error_rather_than_a_default(self):
        with self.assertRaises(ValueError):
            ram(fitting="battering ram")


class TestNothingIsDeletedByOneBlow(BaseEvenniaTestCase):
    """
    A collision is violent, but it is one event in one place and a hull is long. Without a
    ceiling the arithmetic is right and the outcome reads as a bug.
    """

    def test_neither_ship_loses_more_than_the_cap(self):
        result = ram(
            length=FRIGATE[0],
            beam=FRIGATE[1],
            draft=FRIGATE[2],
            target_length=BOAT[0],
            target_beam=BOAT[1],
            target_draft=BOAT[2],
            speed=8.0,
        )
        self.assertLessEqual(result.weight, ramming.MOST_ONE_BLOW * resilience(BOAT[0]) + 1e-9)
        self.assertLessEqual(result.recoil, ramming.MOST_ONE_BLOW * resilience(FRIGATE[0]) + 1e-9)

    def test_running_down_a_boat_barely_marks_her_own_stem(self):
        """The frigate destroys the boat and goes on. Both from the same expression."""
        result = ram(
            length=FRIGATE[0],
            beam=FRIGATE[1],
            draft=FRIGATE[2],
            target_length=BOAT[0],
            target_beam=BOAT[1],
            target_draft=BOAT[2],
            speed=4.0,
        )
        self.assertGreater(result.weight / resilience(BOAT[0]), 0.3)
        self.assertLess(result.recoil / resilience(FRIGATE[0]), 0.3)


class TestSheering(BaseEvenniaTestCase):
    """Running down her side to break the looms she has out."""

    def test_a_ship_with_no_oars_out_cannot_be_sheered(self):
        result = ramming.sheer(run=1.0, target_length=30.0, looms=False)
        self.assertFalse(result.success)
        self.assertEqual(result.broken, 0.0)

    def test_how_much_of_her_side_you_ran_down_decides_how_many(self):
        little = ramming.sheer(run=0.25, target_length=30.0, looms=True)
        whole = ramming.sheer(run=1.0, target_length=30.0, looms=True)
        self.assertAlmostEqual(whole.broken / little.broken, 4.0, places=6)

    def test_she_breaks_her_oars_against_you_as_they_go(self):
        """Weaker, because they break rather than bite - but it is not nothing."""
        result = ramming.sheer(run=1.0, target_length=30.0, looms=True)
        self.assertGreater(result.recoil, 0.0)
        self.assertLess(result.recoil, result.broken)

    def test_running_down_more_than_her_length_is_still_her_length(self):
        past = ramming.sheer(run=3.0, target_length=30.0, looms=True)
        whole = ramming.sheer(run=1.0, target_length=30.0, looms=True)
        self.assertEqual(past.broken, whole.broken)


class TestHowMuchOfHerSideWasRunDown(BaseEvenniaTestCase):
    """`side_run_down`, which is what turns a track across the water into a fraction."""

    def setUp(self):
        super().setUp()
        self.her = WorldPosition(0.0, 0.0, 0.0)

    def test_stem_to_stern_is_the_whole_of_her(self):
        run = ramming.side_run_down(
            before=self.her.moved(180.0, 20.0),
            after=self.her.moved(0.0, 20.0),
            target_position=self.her,
            target_heading=0.0,
            target_length=30.0,
        )
        self.assertAlmostEqual(run, 1.0, places=6)

    def test_reaching_her_quarter_takes_what_it_reached(self):
        """A tick that ended partway along her side broke the oars it got to and no more."""
        run = ramming.side_run_down(
            before=self.her.moved(180.0, 20.0),
            after=self.her,
            target_position=self.her,
            target_heading=0.0,
            target_length=30.0,
        )
        self.assertAlmostEqual(run, 0.5, places=6)

    def test_a_track_that_never_reached_her_ran_down_nothing(self):
        run = ramming.side_run_down(
            before=self.her.moved(180.0, 100.0),
            after=self.her.moved(180.0, 40.0),
            target_position=self.her,
            target_heading=0.0,
            target_length=30.0,
        )
        self.assertEqual(run, 0.0)

    def test_which_way_round_it_was_does_not_change_the_oars(self):
        forward = ramming.side_run_down(
            before=self.her.moved(180.0, 20.0),
            after=self.her.moved(0.0, 20.0),
            target_position=self.her,
            target_heading=0.0,
            target_length=30.0,
        )
        aft = ramming.side_run_down(
            before=self.her.moved(0.0, 20.0),
            after=self.her.moved(180.0, 20.0),
            target_position=self.her,
            target_heading=0.0,
            target_length=30.0,
        )
        self.assertAlmostEqual(forward, aft, places=6)


class TestFindingTheContact(BaseEvenniaTestCase):
    """
    Whether one hull's step reached another at all - and the swept part, which is the half
    that is easy to leave out and impossible to notice afterwards.
    """

    def setUp(self):
        super().setUp()
        self.her = WorldPosition(0.0, 0.0, 0.0)

    def test_a_point_inside_her_is_inside_her(self):
        self.assertTrue(ramming.struck_by(self.her, 0.0, 30.0, 8.0, self.her.moved(0.0, 10.0)))

    def test_a_point_beyond_her_stem_is_not(self):
        self.assertFalse(ramming.struck_by(self.her, 0.0, 30.0, 8.0, self.her.moved(0.0, 20.0)))

    def test_a_point_off_her_beam_is_not(self):
        self.assertFalse(ramming.struck_by(self.her, 0.0, 30.0, 8.0, self.her.moved(90.0, 10.0)))

    def test_a_hull_with_no_dimensions_is_struck_by_nothing(self):
        """A game that has not measured its hulls gets no ramming rather than an error."""
        self.assertFalse(ramming.struck_by(self.her, 0.0, 0.0, 0.0, self.her))

    def test_a_step_that_ends_short_of_her_never_touched_her(self):
        start = self.her.moved(180.0, 200.0)
        self.assertIsNone(
            ramming.contact_along(
                before=start,
                after=start.moved(0.0, 50.0),
                heading=0.0,
                length=30.0,
                target_position=self.her,
                target_heading=90.0,
                target_length=30.0,
                target_beam=8.0,
            )
        )

    def test_a_step_that_reaches_her_finds_where_it_did(self):
        start = self.her.moved(180.0, 100.0)
        contact = ramming.contact_along(
            before=start,
            after=start.moved(0.0, 200.0),
            heading=0.0,
            length=30.0,
            target_position=self.her,
            target_heading=90.0,
            target_length=30.0,
            target_beam=8.0,
        )
        self.assertIsNotNone(contact)

    def test_a_fast_ship_cannot_step_clean_through_a_small_one(self):
        """
        **The reason this is swept.** A hull tested only where she ends up passes straight
        through anything narrower than one tick of her movement - and the faster she goes,
        the more ships she is entitled to ignore, which is precisely backwards.

        A boat lying across the track, and a frigate crossing the whole of it in one step.

        """
        start = self.her.moved(180.0, 400.0)
        end = self.her.moved(0.0, 400.0)

        self.assertFalse(
            ramming.struck_by(self.her, 0.0, BOAT[0], BOAT[1], end.moved(0.0, FRIGATE[0] / 2.0)),
            "the boat was under the frigate's stem at the end of the step, so this "
            "proves nothing",
        )
        self.assertIsNotNone(
            ramming.contact_along(
                before=start,
                after=end,
                heading=0.0,
                length=FRIGATE[0],
                target_position=self.her,
                target_heading=90.0,
                target_length=BOAT[0],
                target_beam=BOAT[1],
            ),
            "the frigate stepped clean through a boat lying across her track",
        )


class TestWhichPartOfHerWasStruck(BaseEvenniaTestCase):
    """
    `face_struck`, which decides both how much she can turn aside and what a square blow
    even means.
    """

    def struck(self, bearing, heading=0.0, length=30.0, beam=8.5):
        """
        Args:
            bearing (float): From the rammer to her.
            heading (float, optional): Her heading.
            length (float, optional): Her length.
            beam (float, optional): Her breadth.

        Returns:
            face (str): Which part of her took it.

        """
        return ramming.face_struck(bearing, heading, length, beam)[0]

    def test_coming_up_from_astern_strikes_her_stern(self):
        self.assertEqual(self.struck(bearing=0.0, heading=0.0), ramming.STERN)

    def test_meeting_her_strikes_her_bow(self):
        self.assertEqual(self.struck(bearing=0.0, heading=180.0), ramming.BOW)

    def test_crossing_her_strikes_her_side(self):
        self.assertEqual(self.struck(bearing=0.0, heading=90.0), ramming.SIDE)

    def test_a_beamy_hull_presents_a_wider_bow_than_a_fine_one(self):
        """
        The corner between stem and topsides is her own proportions, not a fixed arc. A
        barge is nearly all bow from ahead; a fine cutter is a knife edge.

        """
        fine = self.struck(bearing=0.0, heading=195.0, length=40.0, beam=6.0)
        beamy = self.struck(bearing=0.0, heading=195.0, length=40.0, beam=30.0)
        self.assertEqual(fine, ramming.SIDE)
        self.assertEqual(beamy, ramming.BOW)

    def test_her_side_is_the_weakest_part_of_her(self):
        self.assertEqual(max(ramming.FACE_STRENGTH.values()), ramming.FACE_STRENGTH[ramming.SIDE])

    def test_her_stem_is_the_strongest(self):
        self.assertEqual(min(ramming.FACE_STRENGTH.values()), ramming.FACE_STRENGTH[ramming.BOW])


class TestHowSquareTheBlowWas(BaseEvenniaTestCase):
    """`obliquity`, measured to the face struck rather than to her beam."""

    def test_straight_into_a_face_is_square(self):
        self.assertAlmostEqual(ramming.obliquity(heading=0.0, outward=180.0), 0.0)

    def test_along_a_face_does_not_bite(self):
        self.assertAlmostEqual(ramming.obliquity(heading=90.0, outward=180.0), 90.0)

    def test_it_does_not_care_which_way_round_the_angle_lies(self):
        self.assertAlmostEqual(
            ramming.obliquity(heading=45.0, outward=180.0),
            ramming.obliquity(heading=315.0, outward=180.0),
        )


class TestTheArithmeticAgrees(BaseEvenniaTestCase):
    """Closure and displacement, which everything above is built on."""

    def test_closing_speed_is_the_component_along_the_line(self):
        """A ship crossing at right angles to the line between them is not closing at all."""
        self.assertAlmostEqual(
            ramming.impact_speed(speed=5.0, heading=90.0, bearing=0.0), 0.0, places=6
        )

    def test_two_ships_meeting_add_their_speeds(self):
        closing = ramming.impact_speed(
            speed=3.0, heading=0.0, bearing=0.0, target_speed=2.0, target_heading=180.0
        )
        self.assertAlmostEqual(closing, 5.0, places=6)

    def test_displacement_is_the_box_she_fills(self):
        self.assertAlmostEqual(
            ramming.displacement(30.0, 8.0, 4.0, block=0.5, density=1000.0),
            30.0 * 8.0 * 4.0 * 0.5 * 1000.0,
            places=3,
        )

    def test_a_hull_with_a_negative_dimension_weighs_nothing(self):
        self.assertEqual(ramming.displacement(-30.0, 8.0, 4.0), 0.0)


class TestTheAngleTurnsTheBlowAside(BaseEvenniaTestCase):
    """
    The cosine that does the work a table of raking bonuses does elsewhere. Asserted
    through `ram` rather than against the private helper, because the claim is about the
    collision and not about the arithmetic in the middle of it.
    """

    def test_weight_falls_off_with_the_cosine_of_the_obliquity(self):
        """
        Both blows land on her side; one is square to it and one is thirty degrees off.
        Only the angle differs, and the damage differs by its cosine.

        """
        square = ram(target_heading=90.0)
        off = ram(heading=30.0, target_heading=90.0, speed=2.06 / math.cos(math.radians(30.0)))
        self.assertAlmostEqual(square.speed, off.speed, places=6)
        self.assertAlmostEqual(off.weight / square.weight, math.cos(math.radians(30.0)), places=6)


class TestOneShipActuallyRunsIntoAnother(EmptySeaMixin, BaseEvenniaTest):
    """
    The wiring, which is the half the arithmetic above cannot prove.

    Deep water everywhere, so nothing here can be confused with running aground - the two
    are resolved on the same track in the same tick, and a test that let the seabed near it
    would not be able to say which one stopped her.
    """

    def setUp(self):
        super().setUp()
        self.rammer = self.hull_at(WorldPosition(0.0, -120.0), heading=0.0, key="Rammer")
        self.rammer.motion_limits = MotionLimits(max_speed=10.0, acceleration=4.0, turn_rate=8.0)
        self.rammer.orders = HelmOrders(heading=0.0, speed=2.0)

        # Lying square across her track, stopped.
        self.target = self.hull_at(WorldPosition(0.0, 0.0), heading=90.0, key="Target")

    def hull_at(self, where, heading, key):
        """
        Args:
            where (WorldPosition): Where to put her.
            heading (float): Which way she points, in degrees.
            key (str): Her name.

        Returns:
            hull (Vessel): A brig, floating.

        """
        hull = create.create_object(Vessel, key=key)
        deck = create.create_object(ShipRoom, key=f"{key} Deck")
        deck.vessel = hull
        deck.exposure = OPEN
        hull.length, hull.beam = BRIG[0], BRIG[1]
        hull.light_draft = BRIG[2]
        hull.maritime_position = where
        hull.heading = heading
        return hull

    def steam_in(self, ticks=20, hulls=None):
        """
        Run the clock until she has crossed the water between them.

        Args:
            ticks (int, optional): How many five-second steps to take.
            hulls (tuple, optional): Who to tick. Both of them by default.

        Notes:
            **Both ships tick, because in the world both ships tick.** A vessel puts
            herself into the traffic register as she runs, so one that is never given a
            tick is not on the water as far as anybody else can tell - and a test that
            ticked only the rammer would be asking her to run into a ship the register has
            never heard of.

        """
        for hull in hulls or (self.rammer, self.target):
            with override_settings(
                MARITIME_TIDE_PROVIDER="", MARITIME_MAP_PROVIDER="", MARITIME_DEFAULT_DEPTH=100.0
            ):
                hull.at_maritime_tick(0.0)

        rammer, target = hulls or (self.rammer, self.target)
        with override_settings(
            MARITIME_TIDE_PROVIDER="", MARITIME_MAP_PROVIDER="", MARITIME_DEFAULT_DEPTH=100.0
        ):
            for _ in range(ticks):
                rammer.at_maritime_tick(5.0)
                target.at_maritime_tick(5.0)
                # **Stopped at the first blow.**
                #
                # A ship with way still ordered on grinds into the wreck again on the next
                # tick, and again after that, until both of them are matchwood. That is
                # arguably what she would do; it is not what these tests are measuring, and
                # a second collision hides which of the two the first one hurt more.
                if not target.damage.sound or not rammer.damage.sound:
                    return

    def test_she_stops_at_the_other_ship_rather_than_sailing_through_her(self):
        """
        The acceptance criterion for the whole item. Before this, two hulls occupied the
        same water and nothing anywhere noticed.

        """
        self.steam_in()
        self.assertLess(
            self.rammer.maritime_position.horizontal_distance_to(self.target.maritime_position),
            BRIG[0],
            "she sailed straight through her",
        )
        self.assertEqual(self.rammer.speed, 0.0, "the collision did not take the way off her")

    def test_the_ship_struck_is_damaged(self):
        self.steam_in()
        self.assertGreater(self.target.damage.hull, 0.0)

    def test_the_ship_doing_it_is_damaged_too(self):
        """The point of the item: ramming costs the rammer, so it is a decision."""
        self.steam_in()
        self.assertGreater(self.rammer.damage.hull, 0.0)

    def test_a_beam_strike_costs_the_target_more_than_the_rammer(self):
        self.steam_in()
        self.assertGreater(self.target.damage.hull, self.rammer.damage.hull)

    def test_she_does_not_ram_water(self):
        """A clear stretch of sea leaves both of them sound, and her still going."""
        self.target.maritime_position = WorldPosition(5000.0, 5000.0)
        self.steam_in()
        self.assertTrue(self.rammer.damage.sound)
        self.assertGreater(self.rammer.speed, 0.0)

    def test_a_bow_fitting_is_a_plain_stem_unless_somebody_says_otherwise(self):
        self.assertEqual(self.rammer.bow_fitting, ramming.PLAIN)

    def test_a_bow_cannot_be_fitted_with_nonsense(self):
        with self.assertRaises(ValueError):
            self.rammer.bow_fitting = "a very large hammer"

    def test_a_beak_shifts_the_cost_onto_the_ship_she_hits(self):
        """
        Same collision, different bow. What a ram *is*, asserted through the tick rather
        than through the arithmetic.

        """
        self.rammer.bow_fitting = ramming.RAM
        self.steam_in()
        beaked = (self.rammer.damage.hull, self.target.damage.hull)

        plain_rammer = self.hull_at(WorldPosition(0.0, -120.0), heading=0.0, key="Plain")
        plain_rammer.motion_limits = MotionLimits(max_speed=10.0, acceleration=4.0, turn_rate=8.0)
        plain_rammer.orders = HelmOrders(heading=0.0, speed=2.0)
        fresh = self.hull_at(WorldPosition(3000.0, 0.0), heading=90.0, key="Fresh")
        plain_rammer.maritime_position = WorldPosition(3000.0, -120.0)

        self.steam_in(hulls=(plain_rammer, fresh))

        self.assertLess(beaked[0], plain_rammer.damage.hull, "the beak did not spare her stem")
        self.assertGreater(beaked[1], fresh.damage.hull, "the beak did not bite any deeper")


class TestSheFiresIntoWhatIsAboutToHitHer(EmptySeaMixin, BaseEvenniaTest):
    """
    Roadmap item Q. The one moment a broadside is certain of its target is the moment before
    that target arrives.

    What makes it a decision rather than free damage is the reload: every gun that speaks
    starts its clock, so she meets whatever follows the collision with nothing loaded. The
    source makes those guns unavailable for a phase; a continuous simulation gets the same
    cost by not adding a rule at all.
    """

    def setUp(self):
        super().setUp()
        self.rammer = self.hull_at(WorldPosition(0.0, -120.0), heading=0.0, key="Rammer")
        self.rammer.motion_limits = MotionLimits(max_speed=10.0, acceleration=4.0, turn_rate=8.0)
        self.rammer.orders = HelmOrders(heading=0.0, speed=2.0)
        self.target = self.hull_at(WorldPosition(0.0, 0.0), heading=90.0, key="Target")

    hull_at = TestOneShipActuallyRunsIntoAnother.hull_at
    steam_in = TestOneShipActuallyRunsIntoAnother.steam_in

    def every_shot_tells(self):
        """
        Returns:
            patch (context manager): One in which every gun that can hit, does.

        Notes:
            **The dice are not what this class is testing.** A ship driving at you presents
            her bow, which is the narrowest she has - `aspect_accuracy` makes her a fraction
            of the target she would be broadside on - so a defensive broadside genuinely
            misses most of the time, and four guns at forty metres scoring nothing is an
            ordinary afternoon rather than a bug.

            That is a design property worth keeping: it is why ramming is worth attempting
            at all. But a test of the wiring cannot be built on it, so the roll is pinned
            and what is asserted is the accounting.

        """
        from unittest import mock

        from .. import config

        class Certain:
            def stream(self, name):
                return type("S", (), {"random": staticmethod(lambda: 0.0)})()

        return mock.patch.object(config, "rng_context", lambda: Certain())

    def arm(self, hull, count=4):
        """
        Args:
            hull (Vessel): Who to give guns to.
            count (int, optional): How many guns a side.

        Returns:
            hull (Vessel): The same ship, with a loaded broadside each side.

        Notes:
            Both sides, because which one bears depends on which way the rammer comes in
            and a test that armed one side would pass or fail on the geometry rather than
            on the thing it is asking about.

        """
        for side in (STARBOARD_BROADSIDE, PORT_BROADSIDE):
            gun = WeaponType(
                key=f"{side} nine",
                name="nine pounder",
                arc=side,
                max_range=800.0,
                reload_time=90.0,
                projectile_speed=250.0,
                accuracy=0.6,
                damage=10.0,
            )
            for index in range(count):
                hull.add_mount(Mount(key=f"{side} {index}", weapon=gun, loaded=True, ready_at=0.0))
        return hull

    def test_a_bow_on_rammer_is_a_hard_target(self):
        """
        Not an accident, and worth stating. She is coming at you end-on, which is the
        smallest she will ever look, so the last broadside is a poor bet - and that is why
        ramming is worth attempting in the first place.

        """
        from ..ballistics import aspect_accuracy

        self.assertLess(aspect_accuracy(0.0), aspect_accuracy(90.0))

    def test_she_fires_at_a_ship_driving_at_her(self):
        """
        **Armed against unarmed, because the rammer is hurt either way.**

        The collision alone damages the ship delivering it, so "the rammer took damage"
        proves nothing at all - it is true with no guns on the board. What proves the
        broadside happened is that running at a ship with a loaded battery costs more than
        running at the same ship without one.

        """
        self.arm(self.target)
        with self.every_shot_tells():
            self.steam_in()
        shot_at = self.rammer.damage.hull + self.rammer.damage.rigging

        quiet_rammer = self.hull_at(WorldPosition(4000.0, -120.0), heading=0.0, key="Quiet")
        quiet_rammer.motion_limits = MotionLimits(max_speed=10.0, acceleration=4.0, turn_rate=8.0)
        quiet_rammer.orders = HelmOrders(heading=0.0, speed=2.0)
        unarmed = self.hull_at(WorldPosition(4000.0, 0.0), heading=90.0, key="Unarmed")
        with self.every_shot_tells():
            self.steam_in(hulls=(quiet_rammer, unarmed))

        self.assertGreater(
            shot_at,
            quiet_rammer.damage.hull + quiet_rammer.damage.rigging,
            "running at a loaded battery cost no more than running at an empty ship",
        )

    def test_an_unarmed_ship_simply_takes_it(self):
        """No guns, no reaction, and no error either."""
        self.steam_in()
        self.assertTrue(self.target.damage.hull > 0.0)

    def test_firing_leaves_her_battery_empty(self):
        """
        The whole cost of the item. She spends her broadside on the ship hitting her, and
        has nothing for whatever comes next.

        """
        self.arm(self.target)
        loaded_before = sum(1 for mount in self.target.mounts if mount.loaded)
        with self.every_shot_tells():
            self.steam_in()
        loaded_after = sum(1 for mount in self.target.mounts if mount.loaded)
        self.assertGreater(loaded_before, 0)
        self.assertLess(loaded_after, loaded_before, "not a gun was spent")

    def test_a_point_blank_shot_is_laid_worse_than_a_snatched_one(self):
        """Worse than opportunity fire, which is itself worse than a considered shot."""
        self.arm(self.target)
        self.assertLess(self.target.point_blank_steadiness(), self.target.laying_steadiness())
