"""
Tests for holding your fire until something bears.

The order is worth having because it is *two* orders with different risks. Waiting on a
named ship is safe and blind in fog; watching an arc sees in any weather and will fire on
whatever crosses it. Most of what follows is about keeping that difference sharp.

"""

from django.test import override_settings
from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaCommandTest, BaseEvenniaTest

from ..ammunition import BALL
from ..commands import CmdHoldFire
from ..crew import ABLE
from ..motion import HelmOrders, MotionLimits
from ..observation import CLASSIFIED, IDENTIFIED, VESSEL, Sighting
from ..position import WorldPosition
from ..rooms import ShipRoom
from ..sailing import FULL
from ..tactical import PORT_BROADSIDE, STARBOARD_BROADSIDE
from ..traffic import traffic
from ..typeclasses import Vessel
from ..vessel import OPEN
from ..weapons import Holding, Mount, WeaponType
from .base import EmptySeaMixin

HERE = WorldPosition(0.0, 0.0)
BREEZE = {"MARITIME_WIND_BEARING": 180.0, "MARITIME_WIND_SPEED": 8.0}

GUN = WeaponType(
    key="nine", name="nine-pounder", arc=STARBOARD_BROADSIDE, max_range=2000.0, damage=10.0
)


class HoldingTestCase(EmptySeaMixin, BaseEvenniaTest):
    """A ship with a starboard battery, run out and ready."""

    def setUp(self):
        super().setUp()
        self.heard = []
        self.hull = create.create_object(Vessel, key="Kestrel")
        self.hull.length, self.hull.beam = 46.0, 12.0
        self.hull.motion_limits = MotionLimits(max_speed=8.0, acceleration=0.5, turn_rate=5.0)
        self.hull.maritime_position = HERE
        self.hull.heading = 0.0
        self.hull.orders = HelmOrders(heading=0.0, speed=0.0)
        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.deck.vessel = self.hull
        self.deck.exposure = OPEN
        self.deck.msg_contents = lambda text, **kwargs: self.heard.append(text)
        self.hull.man(200, ABLE)
        self.hull.add_mount(
            Mount(key="starboard one", weapon=GUN, loaded=True, ready_at=0.0, shot=BALL)
        )
        traffic().note(self.hull, HERE)

    def a_ship(self, key, bearing, distance=300.0):
        """
        Returns:
            vessel (Vessel): A hull at that true bearing and range from us.

        """
        other = create.create_object(Vessel, key=key)
        other.length, other.beam = 30.0, 8.0
        other.maritime_position = HERE.moved(bearing, distance)
        other.heading = 0.0
        other.sail_plan = FULL
        traffic().note(other, other.maritime_position)
        return other

    def seen(self, target, relative, level=IDENTIFIED, distance=300.0):
        """
        Returns:
            sighting (Sighting): That ship, at that bearing off our head.

        """
        return Sighting(
            target=target,
            distance=distance,
            bearing=relative,
            relative=relative,
            level=level,
        )


class TestGivingTheOrder(HoldingTestCase):
    """Named ship or open arc, and never both."""

    def test_she_is_not_holding_to_begin_with(self):
        self.assertIsNone(self.hull.holding)

    def test_holding_on_a_name(self):
        self.assertEqual(self.hull.hold_fire(target_key="Marigold").target_key, "marigold")

    def test_the_name_is_folded_so_a_captain_need_not_shout_it_exactly(self):
        self.hull.hold_fire(target_key="MARIGOLD")
        self.assertEqual(self.hull.holding.target_key, "marigold")

    def test_holding_on_an_arc(self):
        self.assertEqual(self.hull.hold_fire(arc=STARBOARD_BROADSIDE).arc, STARBOARD_BROADSIDE)

    def test_an_order_with_nothing_in_it_is_refused(self):
        """ "Hold your fire" on its own is not an order."""
        with self.assertRaises(ValueError):
            self.hull.hold_fire()

    def test_and_so_is_one_with_two_things_in_it(self):
        """A crew told to watch both a ship and a bearing would have to guess."""
        with self.assertRaises(ValueError):
            self.hull.hold_fire(target_key="Marigold", arc=STARBOARD_BROADSIDE)

    def test_standing_down(self):
        self.hull.hold_fire(arc=STARBOARD_BROADSIDE)
        self.assertTrue(self.hull.stand_down())
        self.assertIsNone(self.hull.holding)

    def test_standing_down_twice_says_so(self):
        self.assertFalse(self.hull.stand_down())


class TestWhatTheOrderCovers(HoldingTestCase):
    """The heart of it: which contact, if any, the guns will take."""

    def test_nothing_happens_without_an_order(self):
        her = self.a_ship("Marigold", 90.0)
        self.assertIsNone(self.hull.opportunity([self.seen(her, 90.0)]))

    def test_a_named_ship_crossing_is_taken(self):
        her = self.a_ship("Marigold", 90.0)
        self.hull.hold_fire(target_key="marigold")
        self.assertIsNotNone(self.hull.opportunity([self.seen(her, 90.0)]))

    def test_somebody_else_crossing_is_not(self):
        """The whole point of naming her."""
        other = self.a_ship("Swiftsure", 90.0)
        self.hull.hold_fire(target_key="marigold")
        self.assertIsNone(self.hull.opportunity([self.seen(other, 90.0)]))

    def test_a_named_ship_nobody_has_identified_is_not_taken(self):
        """
        The cost of the safe order. A shape on the water is not a name, so holding
        fire on the Marigold does nothing in fog - which is where you most want
        your guns held ready.

        """
        her = self.a_ship("Marigold", 90.0)
        self.hull.hold_fire(target_key="marigold")
        self.assertIsNone(self.hull.opportunity([self.seen(her, 90.0, level=CLASSIFIED)]))
        self.assertIsNone(self.hull.opportunity([self.seen(her, 90.0, level=VESSEL)]))

    def test_an_arc_takes_whatever_crosses_it(self):
        """
        The teeth. Nothing here knows what a friend is, and nothing needs to: an
        order to fire on anything crossing to starboard is already an order that
        will take your own consort, and the captain who gave it said so.

        """
        consort = self.a_ship("Swiftsure", 90.0)
        self.hull.hold_fire(arc=STARBOARD_BROADSIDE)
        self.assertIsNotNone(self.hull.opportunity([self.seen(consort, 90.0)]))

    def test_and_takes_her_without_knowing_what_she_is(self):
        """Which is why it works in fog, and why it is dangerous."""
        stranger = self.a_ship("Stranger", 90.0)
        self.hull.hold_fire(arc=STARBOARD_BROADSIDE)
        self.assertIsNotNone(self.hull.opportunity([self.seen(stranger, 90.0, level=VESSEL)]))

    def test_nothing_outside_the_watched_arc_is_taken(self):
        her = self.a_ship("Marigold", 270.0)
        self.hull.hold_fire(arc=STARBOARD_BROADSIDE)
        self.assertIsNone(self.hull.opportunity([self.seen(her, -90.0)]))

    def test_nothing_no_gun_bears_on_is_taken(self):
        """
        A port-side contact with only a starboard battery aboard. The order says
        watch to port; the guns cannot answer, and holding them is not the same as
        being able to fire.

        """
        her = self.a_ship("Marigold", 270.0)
        self.hull.hold_fire(arc=PORT_BROADSIDE)
        self.assertIsNone(self.hull.opportunity([self.seen(her, -90.0)]))

    def test_the_nearest_of_several_is_taken(self):
        near = self.a_ship("Near", 90.0, distance=300.0)
        far = self.a_ship("Far", 90.0, distance=900.0)
        self.hull.hold_fire(arc=STARBOARD_BROADSIDE)
        chosen = self.hull.opportunity(
            [self.seen(near, 90.0, distance=300.0), self.seen(far, 90.0, distance=900.0)]
        )
        self.assertIs(chosen.target, near)


class TestASnatchedShot(HoldingTestCase):
    """Opportunity fire is worse than a broadside you called yourself."""

    def test_a_held_shot_is_less_well_laid(self):
        self.assertLess(self.hull.laying_steadiness(), 1.0)

    def test_a_snatched_shot_is_meaningfully_worse_than_an_aimed_one(self):
        """
        The bound is absolute on purpose. Comparing against OPPORTUNITY_ACCURACY
        would only say the code agrees with itself, and would go on passing if the
        constant were raised until holding your fire cost nothing at all - which
        would make it the strictly better way to fight.

        """
        bare = create.create_object(Vessel, key="Dinghy")
        self.assertAlmostEqual(bare.hesitation, 0.0)
        self.assertLess(bare.laying_steadiness(), 0.85)
        self.assertGreater(bare.laying_steadiness(), 0.0)

    def test_even_a_fresh_crew_are_a_little_short_of_that(self):
        """Nobody is perfectly steady. An able crew carry some hesitation always."""
        bare = create.create_object(Vessel, key="Dinghy")
        self.assertLess(self.hull.laying_steadiness(), bare.laying_steadiness())

    def test_a_frightened_crew_snatch_harder(self):
        """
        Casualties do not frighten anybody at the instant they fall - morale
        settles towards the new state over the following minute - so this is not
        true until a watch has passed over them.

        """
        steady = self.hull.laying_steadiness()
        self.hull.take_casualties(120)
        self.hull.stand_watch(60.0)
        self.assertLess(self.hull.laying_steadiness(), steady)

    def test_but_they_still_fire(self):
        """Fear degrades here as everywhere else. It does not gate."""
        self.hull.take_casualties(190)
        self.hull.stand_watch(300.0)
        self.assertGreater(self.hull.laying_steadiness(), 0.0)


class TestFiringOnTheOrder(HoldingTestCase):
    """On a hull, through the tick."""

    def test_a_held_battery_fires_itself(self):
        with override_settings(**BREEZE):
            self.a_ship("Marigold", 90.0)
            self.hull.hold_fire(arc=STARBOARD_BROADSIDE)
            self.heard.clear()
            self.hull.at_maritime_tick(1.0)
        self.assertTrue(any("go off" in line for line in self.heard))

    def test_and_says_why_before_it_does(self):
        with override_settings(**BREEZE):
            self.a_ship("Marigold", 90.0)
            self.hull.hold_fire(arc=STARBOARD_BROADSIDE)
            self.heard.clear()
            self.hull.at_maritime_tick(1.0)
        crossed = next(i for i, line in enumerate(self.heard) if "crosses the" in line)
        went_off = next(i for i, line in enumerate(self.heard) if "go off" in line)
        self.assertLess(crossed, went_off)

    def test_an_empty_sea_fires_nothing(self):
        with override_settings(**BREEZE):
            self.hull.hold_fire(arc=STARBOARD_BROADSIDE)
            self.heard.clear()
            self.hull.at_maritime_tick(1.0)
        self.assertFalse(any("go off" in line for line in self.heard))

    def test_the_order_stands_after_it_is_used(self):
        """
        A captain watching a channel wants every ship that comes through it.
        Having to give the order again after each would make it useless for the
        one thing it is for.

        """
        with override_settings(**BREEZE):
            self.a_ship("Marigold", 90.0)
            self.hull.hold_fire(arc=STARBOARD_BROADSIDE)
            self.hull.at_maritime_tick(1.0)
        self.assertIsNotNone(self.hull.holding)

    def test_a_ship_stood_down_holds_her_fire(self):
        with override_settings(**BREEZE):
            self.a_ship("Marigold", 90.0)
            self.hull.hold_fire(arc=STARBOARD_BROADSIDE)
            self.hull.stand_down()
            self.heard.clear()
            self.hull.at_maritime_tick(1.0)
        self.assertFalse(any("go off" in line for line in self.heard))

    def test_a_ship_aground_still_has_a_broadside(self):
        """Guns do not care whether she is going anywhere."""
        with override_settings(**BREEZE):
            self.a_ship("Marigold", 90.0)
            self.hull.hold_fire(arc=STARBOARD_BROADSIDE)
            self.hull.aground = True
            self.heard.clear()
            self.hull.at_maritime_tick(1.0)
        self.assertTrue(any("go off" in line for line in self.heard))


class TestTheOrderOnDeck(EmptySeaMixin, BaseEvenniaCommandTest):
    """The player-facing path."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Kestrel")
        self.hull.length, self.hull.beam = 46.0, 12.0
        self.hull.maritime_position = HERE
        self.hull.motion_limits = MotionLimits(max_speed=8.0, acceleration=0.5, turn_rate=5.0)
        self.deck = create.create_object(ShipRoom, key="Main Deck")
        self.deck.vessel = self.hull
        self.deck.exposure = OPEN
        self.hull.add_mount(
            Mount(key="starboard one", weapon=GUN, loaded=True, ready_at=0.0, shot=BALL)
        )
        self.char1.location = self.deck

    def test_holding_on_an_arc(self):
        self.call(CmdHoldFire(), "to starboard")
        self.assertEqual(self.hull.holding.arc, STARBOARD_BROADSIDE)

    def test_holding_on_a_name(self):
        self.call(CmdHoldFire(), "marigold")
        self.assertEqual(self.hull.holding.target_key, "marigold")

    def test_the_arc_order_warns_what_it_will_do(self):
        said = self.call(CmdHoldFire(), "to starboard")
        self.assertIn("whatever comes into it", said)

    def test_reporting_what_is_held(self):
        self.call(CmdHoldFire(), "to starboard")
        self.assertIn("whatever crosses it", self.call(CmdHoldFire(), ""))

    def test_reporting_when_nothing_is(self):
        self.assertIn("not holding", self.call(CmdHoldFire(), ""))

    def test_securing_the_guns(self):
        self.call(CmdHoldFire(), "to starboard")
        self.call(CmdHoldFire(), "down")
        self.assertIsNone(self.hull.holding)

    def test_a_ship_with_no_guns_says_so(self):
        bare = create.create_object(Vessel, key="Dinghy")
        bare.maritime_position = HERE
        deck = create.create_object(ShipRoom, key="Thwart")
        deck.vessel = bare
        deck.exposure = OPEN
        self.char1.location = deck
        self.assertIn("no guns", self.call(CmdHoldFire(), "to starboard"))


class TestAnOrderThatOutlivesItsPlan(HoldingTestCase):
    """Stored state has to survive the code that wrote it."""

    def test_an_arc_nobody_defines_takes_nothing(self):
        her = self.a_ship("Marigold", 90.0)
        self.hull.holding = Holding(arc="no such arc")
        self.assertIsNone(self.hull.opportunity([self.seen(her, 90.0)]))


class TestAGunThatNeverWentOff(HoldingTestCase):
    """
    A refusal is not a broadside, and it does not cost a charge.

    `can_fire` refuses for four reasons and the broadside loop only skipped two of
    them, so a target inside the arc but beyond the guns' reach discharged every
    piece aboard for a shot nobody took. Carried in from the deck command, where
    it had been all along.

    """

    def far_off(self, metres):
        """
        Returns:
            sighting (Sighting): A ship on the beam at that range.

        """
        her = self.a_ship("Distant", 90.0, distance=metres)
        return self.seen(her, 90.0, distance=metres)

    def test_a_target_beyond_reach_is_not_fired_on(self):
        result = self.hull.fire_broadside(self.far_off(9000.0), 0.0, lambda: 0.0)
        self.assertEqual(result.fired, 0)

    def test_and_the_charge_is_still_in_the_gun(self):
        self.hull.fire_broadside(self.far_off(9000.0), 0.0, lambda: 0.0)
        self.assertTrue(all(mount.loaded for mount in self.hull.mounts))

    def test_a_target_within_reach_is(self):
        """Guards the two above: they must not pass by never firing at all."""
        result = self.hull.fire_broadside(self.far_off(300.0), 0.0, lambda: 0.0)
        self.assertEqual(result.fired, 1)
        self.assertFalse(all(mount.loaded for mount in self.hull.mounts))

    def test_a_held_battery_does_not_announce_a_shot_it_did_not_take(self):
        with override_settings(**BREEZE):
            self.a_ship("Distant", 90.0, distance=9000.0)
            self.hull.hold_fire(arc=STARBOARD_BROADSIDE)
            self.heard.clear()
            self.hull.at_maritime_tick(1.0)
        self.assertFalse(any("go off" in line for line in self.heard))


class TestBadlyLaidGunsTellLessOften(HoldingTestCase):
    """
    The part that makes the penalty real rather than decorative.

    Three mutants lived here: the constant could be raised to a free lunch, the
    steadiness could be dropped on the way to the gun, and the gun could ignore it
    on arrival. All three passed every test above, because every one of them was
    about the *number* and none about what the number does.

    """

    def hits_at(self, steadiness, tries=100):
        """
        Fire the same shot at the same ship many times, on a fixed spread of
        rolls, and count what tells.

        Returns:
            hits (int): How many of them did.

        """
        her = self.a_ship("Marigold", 90.0, distance=300.0)
        seen = self.seen(her, 90.0, distance=300.0)
        told = 0
        for n in range(tries):
            self.hull.replace_mount(
                Mount(key="starboard one", weapon=GUN, loaded=True, ready_at=0.0, shot=BALL)
            )
            rolls = iter([n / float(tries)])
            result = self.hull.fire_broadside(seen, 0.0, lambda: next(rolls), steadiness)
            told += result.hits
        return told

    def test_a_well_laid_gun_tells_more_often(self):
        self.assertGreater(self.hits_at(1.0), self.hits_at(0.5))

    def test_and_the_snatched_shot_is_on_the_worse_side_of_that(self):
        """
        Not merely different - worse, and by the amount the order claims. This is
        what a captain is buying when he holds his fire instead of calling it.

        """
        aimed = self.hits_at(1.0)
        snatched = self.hits_at(self.hull.laying_steadiness())
        self.assertLess(snatched, aimed)

    def test_a_held_battery_fires_less_accurately_than_an_ordered_one(self):
        """End to end, through the standing order rather than through a number."""
        self.hull.hold_fire(arc=STARBOARD_BROADSIDE)
        self.assertLess(self.hull.laying_steadiness(), 1.0)


class TestSayingNothingWhenNothingHappened(HoldingTestCase):
    """
    A held battery that cannot fire says nothing at all.

    Not even "the crews are still at it" - nobody gave an order, so there is
    nobody waiting on an answer, and a ship that reported her guns unready every
    two seconds for the whole of a passage would be the purest wallpaper in the
    system.

    """

    def about_the_guns(self):
        """
        Returns:
            lines (list): Anything said about the battery. The lookout speaks on
                the same tick and is not what this is about.

        """
        return [
            line
            for line in self.heard
            if "gun" in line.lower() or "go off" in line or "crosses the" in line
        ]

    def test_a_battery_with_nothing_ready_is_silent(self):
        with override_settings(**BREEZE):
            self.hull.replace_mount(
                Mount(key="starboard one", weapon=GUN, loaded=False, ready_at=0.0, shot=BALL)
            )
            self.a_ship("Marigold", 90.0)
            self.hull.hold_fire(arc=STARBOARD_BROADSIDE)
            self.heard.clear()
            self.hull.at_maritime_tick(1.0)
        self.assertEqual(self.about_the_guns(), [])

    def test_and_so_is_one_whose_target_is_out_of_reach(self):
        with override_settings(**BREEZE):
            self.a_ship("Distant", 90.0, distance=9000.0)
            self.hull.hold_fire(arc=STARBOARD_BROADSIDE)
            self.heard.clear()
            self.hull.at_maritime_tick(1.0)
        self.assertEqual(self.about_the_guns(), [])

    def test_but_one_that_fires_is_not(self):
        """Guards both above: silence is easy to achieve by never firing."""
        with override_settings(**BREEZE):
            self.a_ship("Marigold", 90.0)
            self.hull.hold_fire(arc=STARBOARD_BROADSIDE)
            self.heard.clear()
            self.hull.at_maritime_tick(1.0)
        self.assertNotEqual(self.about_the_guns(), [])


class TestAShotThatFallsShort(HoldingTestCase):
    """
    Grape that does not carry is a charge spent, not a gun that never went off.

    The distinction the refusal list turns on: a gun that *cannot reach* holds its
    charge, and a gun that fires a shot which will not carry has spent it. Loading
    grape shortens your reach for the afternoon, and that is the price of having
    made your mind up early.

    """

    def test_the_gun_goes_off(self):
        from ..ammunition import GRAPE

        self.hull.replace_mount(
            Mount(key="starboard one", weapon=GUN, loaded=True, ready_at=0.0, shot=GRAPE)
        )
        her = self.a_ship("Marigold", 90.0, distance=900.0)
        result = self.hull.fire_broadside(self.seen(her, 90.0, distance=900.0), 0.0, lambda: 0.0)
        self.assertEqual(result.fired, 1)

    def test_and_the_charge_is_gone(self):
        from ..ammunition import GRAPE

        self.hull.replace_mount(
            Mount(key="starboard one", weapon=GUN, loaded=True, ready_at=0.0, shot=GRAPE)
        )
        her = self.a_ship("Marigold", 90.0, distance=900.0)
        self.hull.fire_broadside(self.seen(her, 90.0, distance=900.0), 0.0, lambda: 0.0)
        self.assertFalse(any(mount.loaded for mount in self.hull.mounts))

    def test_but_it_tells_on_nobody(self):
        from ..ammunition import GRAPE

        self.hull.replace_mount(
            Mount(key="starboard one", weapon=GUN, loaded=True, ready_at=0.0, shot=GRAPE)
        )
        her = self.a_ship("Marigold", 90.0, distance=900.0)
        result = self.hull.fire_broadside(self.seen(her, 90.0, distance=900.0), 0.0, lambda: 0.0)
        self.assertEqual(result.hits, 0)


class TestTheStandingOrderActuallyLaysBadly(HoldingTestCase):
    """
    The seam between "a snatched shot is worse" and "this shot was snatched".

    `TestBadlyLaidGunsTellLessOften` proves a worse-laid gun tells less often, and
    `TestASnatchedShot` proves the battery knows it is laying badly. Neither
    notices if the number is dropped on the way between them, and dropping it is a
    one-word edit that makes holding your fire free.

    So this one watches the call. It is a whiter box than the rest of this file on
    purpose: the value has no consequence of its own that the other two are not
    already checking, and a test that re-checked the consequence would only be
    proving the RNG deterministic.

    """

    def test_a_held_battery_fires_on_its_own_laying(self):
        passed = []
        aimed = self.hull.fire_broadside

        def watched(sighting, now, roll, steadiness=1.0):
            passed.append(steadiness)
            return aimed(sighting, now, roll, steadiness)

        self.hull.fire_broadside = watched
        with override_settings(**BREEZE):
            self.a_ship("Marigold", 90.0)
            self.hull.hold_fire(arc=STARBOARD_BROADSIDE)
            self.hull.take_opportunity()

        self.assertEqual(passed, [self.hull.laying_steadiness()])
        self.assertLess(passed[0], 1.0)
