"""
The scenario suite: named voyages, run end to end.

Every other test file here checks a piece. These check a *passage* - set sail, stand on,
and see where she ends up - because a system can pass every unit test it has and still be
unable to get a ship from one place to another. The names are the design's own, from
section 20 of the architecture, so that "which of these actually run?" has an answer that
is not somebody's memory.

Each scenario is a voyage rather than an assertion about a function. They tick real time
through real typeclasses and read the result off the ship, which makes them slower than the
rest of the suite and worth every second: three separate bugs this contrib has shipped
would have been caught here rather than by somebody sailing about in the testbed.

Not built, and why:

    flooding, fire, collision            damage, phase 17
    strategic-advance, materialize       phase 11
    passenger-*, service-partial         phases 21 and 23

Those are Gary's, and a scenario that pretended to exercise them would be worse than a gap.

"""

from django.test import override_settings

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest

from ..bathymetry import MaritimeMapProvider, ROCK, SAND
from ..boarding import relative_speed
from ..charts import Chart
from ..clock import ManualTimeProvider
from ..grounding import HOLED
from ..motion import HelmOrders, MotionLimits
from ..navigation import DeadReckoning
from ..position import WorldPosition
from ..ports import Berth
from ..rooms import PortRoom, ShipRoom, rig_gangway
from ..routes import ARRIVAL_RANGE, NavigationNetwork, Waypoint
from ..sailing import FULL, FURLED, PolarCurve, WORKING
from ..tactical import STARBOARD_BROADSIDE
from ..simulation import ACTIVE, MaritimeSimulationService
from ..traffic import traffic
from ..typeclasses import Vessel
from ..vessel import OPEN, VesselCapacity
from ..weapons import Mount, WeaponType, fire
from .base import EmptySeaMixin

#: A steady working breeze from the south, so an easterly course is a beam reach.
BREEZE = {"MARITIME_WIND_BEARING": 180.0, "MARITIME_WIND_SPEED": 8.0}

#: A gale from the same quarter. Same direction on purpose - the only thing that
#: changes between `sailing-basic` and `storm-delay` is how hard it is blowing.
GALE = {"MARITIME_WIND_BEARING": 180.0, "MARITIME_WIND_SPEED": 22.0}


class Shoal(MaritimeMapProvider):
    """Deep water with a sandbank in it, east of x=2000."""

    def terrain_z_at(self, position):
        return -1.0 if position.x >= 2000.0 else -30.0

    def bottom_type_at(self, position):
        return SAND


class Reef(Shoal):
    """The same bank, made of rock."""

    def bottom_type_at(self, position):
        return ROCK


class Ledge(MaritimeMapProvider):
    """
    A rock ledge with open water round its southern end.

    Notes:
        The channel is the point. Standing straight east runs onto it; going south
        round the end does not, and that is what makes a chart worth having.

    """

    def terrain_z_at(self, position):
        on_it = 2000.0 <= position.x <= 2600.0 and abs(position.y) <= 800.0
        return -1.2 if on_it else -30.0

    def bottom_type_at(self, position):
        return ROCK


class ScenarioTestCase(EmptySeaMixin, BaseEvenniaTest):
    """
    A sloop, and a way to sail her.

    Notes:
        Weather is a class attribute rather than an `override_settings`
        decorator, and that is not a style choice. `EmptySeaMixin` enables its
        own flat, still, windless sea inside `setUp`, which runs *after* a class
        decorator has been applied - so a scenario asking for a working breeze by
        decorator got a dead calm and every ship in it sat still. Enabling it
        here, after the empty sea, is the only ordering that works.

    """

    #: What the sky is doing. Applied after the empty sea so it wins.
    weather = {}

    def setUp(self):
        super().setUp()
        if self.weather:
            sky = override_settings(**self.weather)
            sky.enable()
            self.addCleanup(sky.disable)

    def a_sloop(self, key="Kittiwake", position=None, sails=True):
        """
        Returns:
            vessel (Vessel): A working sloop with a deck and a masthead.

        """
        hull = create.create_object(Vessel, key=key)
        hull.length, hull.beam = 18.0, 5.4
        hull.light_draft = 2.2
        hull.air_draft = 20.0
        hull.capacity = VesselCapacity(displacement=40000.0, internal_volume=90.0)
        hull.motion_limits = MotionLimits(max_speed=6.0, acceleration=0.5, turn_rate=6.0)
        hull.maritime_position = position or WorldPosition(0.0, 0.0)
        if sails:
            hull.polar_curve = PolarCurve()
            hull.sail_plan = FURLED

        deck = create.create_object(ShipRoom, key=f"{key} Deck")
        deck.vessel = hull
        deck.exposure = OPEN
        deck.height_of_eye = 2.0

        top = create.create_object(ShipRoom, key=f"{key} Masthead")
        top.vessel = hull
        top.exposure = OPEN
        top.deck_level = 3
        top.height_of_eye = 18.0

        traffic().note(hull, hull.maritime_position)
        return hull

    def sail(self, vessel, seconds, step=15.0):
        """
        Advance a vessel through a stretch of time, a tick at a time.

        Args:
            vessel (Vessel): The hull.
            seconds (float): How long to sail.
            step (float, optional): Tick length.

        Returns:
            ticks (int): How many ticks ran before she stopped or the time ran out.

        Notes:
            Stops early if she goes aground, because a scenario that kept ticking a
            stranded ship would be measuring nothing.

        """
        ticks = 0
        for _ in range(int(seconds / step)):
            vessel.at_maritime_tick(step)
            ticks += 1
            if vessel.aground:
                break
        return ticks


# --- sailing ---------------------------------------------------------------


class TestSailingBasic(ScenarioTestCase):
    """`sailing-basic`: she makes her course with the wind on her beam."""

    weather = BREEZE

    def test_she_sails(self):
        hull = self.a_sloop()
        hull.sail_plan = WORKING
        hull.orders = HelmOrders(heading=90.0, speed=0.0)
        self.sail(hull, 600.0)

        self.assertGreater(hull.speed, 0.0)
        self.assertGreater(hull.maritime_position.x, 500.0)
        self.assertAlmostEqual(hull.heading, 90.0, places=1)

    def test_furled_she_does_not(self):
        """The wind is the same. The canvas is what changed."""
        hull = self.a_sloop()
        hull.sail_plan = FURLED
        hull.orders = HelmOrders(heading=90.0, speed=0.0)
        self.sail(hull, 600.0)
        self.assertAlmostEqual(hull.speed, 0.0)


class TestSailingUpwind(ScenarioTestCase):
    """`sailing-upwind`: she will not sail into the wind's eye."""

    weather = BREEZE

    def sail_on(self, heading):
        hull = self.a_sloop(key=f"Beat {heading:.0f}")
        hull.sail_plan = WORKING
        hull.heading = heading
        hull.orders = HelmOrders(heading=heading, speed=0.0)
        self.sail(hull, 600.0)
        return hull.speed

    def test_a_beam_reach_is_her_best(self):
        self.assertGreater(self.sail_on(90.0), self.sail_on(200.0))

    def test_close_hauled_is_slower_than_reaching(self):
        self.assertGreater(self.sail_on(90.0), self.sail_on(215.0))

    def test_head_to_wind_she_stops(self):
        """Dead into it, and there is nothing the helm can do about it."""
        self.assertAlmostEqual(self.sail_on(180.0), 0.0, places=2)


class TestCurrentDrift(ScenarioTestCase):
    """`current-drift`: where she points and where she goes are different questions."""

    weather = dict(BREEZE, MARITIME_CURRENT_SET=0.0, MARITIME_CURRENT_DRIFT=1.0)

    def test_she_is_set_off_her_course(self):
        hull = self.a_sloop()
        hull.sail_plan = WORKING
        hull.orders = HelmOrders(heading=90.0, speed=0.0)
        start = hull.maritime_position
        self.sail(hull, 900.0)

        self.assertAlmostEqual(hull.heading, 90.0, places=1)
        self.assertGreater(hull.maritime_position.y, start.y + 100.0)

    def test_and_the_ship_knows_it(self):
        hull = self.a_sloop()
        hull.sail_plan = WORKING
        hull.orders = HelmOrders(heading=90.0, speed=0.0)
        self.sail(hull, 300.0)

        course, _speed = hull.made_good()
        self.assertLess(course, hull.heading)


# --- the ground ------------------------------------------------------------


class TestGroundingShoal(ScenarioTestCase):
    """`grounding-shoal`: sand holds her."""

    weather = dict(BREEZE, MARITIME_MAP_PROVIDER=f"{__name__}.Shoal")

    def test_she_runs_onto_it(self):
        hull = self.a_sloop(position=WorldPosition(1500.0, 0.0))
        hull.sail_plan = FULL
        hull.orders = HelmOrders(heading=90.0, speed=0.0)
        self.sail(hull, 1800.0)

        self.assertTrue(hull.aground)
        self.assertGreaterEqual(hull.maritime_position.x, 1900.0)

    def test_and_stays_there(self):
        hull = self.a_sloop(position=WorldPosition(1900.0, 0.0))
        hull.sail_plan = FULL
        hull.orders = HelmOrders(heading=90.0, speed=0.0)
        self.sail(hull, 900.0)
        stranded = hull.maritime_position
        self.sail(hull, 900.0)
        self.assertAlmostEqual(hull.maritime_position.x, stranded.x, places=3)


class TestGroundingReef(ScenarioTestCase):
    """`grounding-reef`: the same bank, made of rock, opens her."""

    weather = dict(BREEZE, MARITIME_MAP_PROVIDER=f"{__name__}.Reef")

    def test_rock_at_speed_holes_her(self):
        hull = self.a_sloop(position=WorldPosition(1500.0, 0.0))
        hull.sail_plan = FULL
        hull.orders = HelmOrders(heading=90.0, speed=0.0)
        self.sail(hull, 1800.0)

        self.assertTrue(hull.aground)
        self.assertEqual(hull.grounding["severity"], HOLED)

    def test_the_record_says_what_she_struck(self):
        """
        `aground` is a boolean. What she is on and how hard she hit it is the part
        phase 17 will need, and the tick was computing it and throwing it away.

        """
        hull = self.a_sloop(position=WorldPosition(1500.0, 0.0))
        hull.sail_plan = FULL
        hull.orders = HelmOrders(heading=90.0, speed=0.0)
        self.sail(hull, 1800.0)

        self.assertEqual(hull.grounding["bottom"], ROCK)
        self.assertLessEqual(hull.grounding["clearance"], 0.0)
        self.assertGreater(hull.grounding["speed"], 0.0)

    def test_getting_her_off_clears_the_record(self):
        """A ship afloat is not a ship with a grounding on her."""
        hull = self.a_sloop(position=WorldPosition(1500.0, 0.0))
        hull.sail_plan = FULL
        hull.orders = HelmOrders(heading=90.0, speed=0.0)
        self.sail(hull, 1800.0)
        self.assertIsNotNone(hull.grounding)

        hull.aground = False
        self.assertIsNone(hull.grounding)

    def test_the_bottom_is_what_decides_it(self):
        """Identical geometry, identical speed. Only the ground changed."""
        with override_settings(MARITIME_MAP_PROVIDER=f"{__name__}.Shoal"):
            soft = self.a_sloop(key="Soft", position=WorldPosition(1500.0, 0.0))
            soft.sail_plan = FULL
            soft.orders = HelmOrders(heading=90.0, speed=0.0)
            self.sail(soft, 1800.0)
            self.assertNotEqual(soft.grounding["severity"], HOLED)


class TestSafeChannel(ScenarioTestCase):
    """`safe-channel`: the way round is clear where the way through is not."""

    weather = dict(BREEZE, MARITIME_MAP_PROVIDER=f"{__name__}.Ledge")

    def test_standing_straight_at_it_grounds_her(self):
        hull = self.a_sloop(position=WorldPosition(1200.0, 0.0))
        hull.sail_plan = WORKING
        hull.orders = HelmOrders(heading=90.0, speed=0.0)
        self.sail(hull, 3600.0)
        self.assertTrue(hull.aground)

    def test_going_south_round_the_end_does_not(self):
        """The same ledge, the same ship, a different decision."""
        hull = self.a_sloop(position=WorldPosition(1200.0, -1200.0))
        hull.sail_plan = WORKING
        hull.orders = HelmOrders(heading=90.0, speed=0.0)
        self.sail(hull, 3600.0)
        self.assertFalse(hull.aground)
        self.assertGreater(hull.maritime_position.x, 2600.0)


# --- ports -----------------------------------------------------------------


class TestDockUndock(ScenarioTestCase):
    """`dock-undock`: alongside, ashore, aboard, and away again."""

    def setUp(self):
        super().setUp()
        self.quay = create.create_object(PortRoom, key="Stone Quay")
        self.quay.maritime_position = WorldPosition(1000.0, 0.0)
        self.berth = Berth(
            key="stone quay",
            position=WorldPosition(1000.0, 0.0),
            heading=0.0,
            max_length=30.0,
            max_beam=9.0,
            max_draft=6.0,
        )
        self.quay.add_berth(self.berth)

    def test_the_whole_of_it(self):
        hull = self.a_sloop(position=WorldPosition(1000.0, 0.0))
        deck = hull.ship_rooms[0]

        hull.make_fast(self.quay, self.berth)
        self.assertTrue(hull.docked)

        exits = rig_gangway(deck, self.quay)
        hull.db.gangway = list(exits)

        # A gangway is walking. Nobody is teleported.
        self.char1.location = deck
        self.char1.move_to(self.quay, quiet=True, move_hooks=False)
        self.assertEqual(self.char1.location, self.quay)
        self.char1.move_to(deck, quiet=True, move_hooks=False)
        self.assertEqual(self.char1.location, deck)

        hull.let_go()
        self.assertFalse(hull.docked)
        self.assertEqual([obj for obj in deck.contents if obj.destination], [])

    def test_she_will_not_shift_while_made_fast(self):
        hull = self.a_sloop(position=WorldPosition(1000.0, 0.0))
        hull.make_fast(self.quay, self.berth)
        hull.orders = HelmOrders(heading=90.0, speed=5.0)
        self.sail(hull, 600.0)
        self.assertAlmostEqual(hull.maritime_position.x, 1000.0, places=3)


# --- persistence -----------------------------------------------------------


class TestReloadUnderway(ScenarioTestCase):
    """`reload-underway`: a server restart does not lose a voyage."""

    weather = BREEZE

    def test_her_position_survives(self):
        hull = self.a_sloop()
        hull.sail_plan = WORKING
        hull.orders = HelmOrders(heading=90.0, speed=0.0)
        self.sail(hull, 600.0)

        underway = hull.maritime_position
        hull.at_server_reload()

        # Everything live is gone; only what was written down remains.
        hull.ndb.maritime_position = None
        hull.ndb.heading = None
        hull.ndb.speed = None

        self.assertAlmostEqual(hull.maritime_position.x, underway.x, places=3)
        self.assertAlmostEqual(hull.maritime_position.y, underway.y, places=3)

    def test_and_so_does_her_heading(self):
        hull = self.a_sloop()
        hull.sail_plan = WORKING
        hull.orders = HelmOrders(heading=135.0, speed=0.0)
        self.sail(hull, 600.0)
        steered = hull.heading
        hull.at_server_shutdown()
        hull.ndb.heading = None
        self.assertAlmostEqual(hull.heading, steered, places=3)


# --- navigation ------------------------------------------------------------


class TestRouteFollowing(ScenarioTestCase):
    """`route-following`: the sailing master takes her round the marks."""

    weather = BREEZE

    def setUp(self):
        super().setUp()
        self.marks = NavigationNetwork()
        for key, x, y in (
            ("start", 0.0, 0.0),
            ("fairway", 900.0, -300.0),
            ("south cardinal", 1800.0, -600.0),
        ):
            self.marks.add(Waypoint(key, WorldPosition(x, y)))
        self.marks.link("start", "fairway")
        self.marks.link("fairway", "south cardinal")

    def test_and_she_stops_when_the_passage_is_made(self):
        """
        Handing back the con without handing the sails is not arriving. She sailed
        twelve kilometres past her last mark before this scenario existed.

        """
        hull = self.a_sloop()
        hull.sail_plan = WORKING
        hull.route = self.marks.plan("start", "south cardinal")
        hull.route_index = 0
        hull.under_con = True

        self.sail(hull, 3600.0, step=20.0)
        self.assertFalse(hull.under_con)
        self.assertAlmostEqual(hull.speed, 0.0, places=2)

    def test_she_sails_the_marks_unattended(self):
        hull = self.a_sloop()
        hull.sail_plan = WORKING
        hull.route = self.marks.plan("start", "south cardinal")
        hull.route_index = 0
        hull.under_con = True

        # How close she got, not where she coasted to. The claim is that she
        # visited the marks; where she ends up after furling is a different
        # question and a less interesting one.
        last = self.marks.waypoint("south cardinal").position
        closest = hull.maritime_position.horizontal_distance_to(last)
        for _ in range(180):
            hull.at_maritime_tick(20.0)
            closest = min(closest, hull.maritime_position.horizontal_distance_to(last))
            if not hull.under_con:
                break

        self.assertLess(closest, ARRIVAL_RANGE)

    def test_a_route_is_a_plan_not_a_rail(self):
        """She sails towards the mark; she is not moved onto it."""
        hull = self.a_sloop()
        hull.sail_plan = WORKING
        hull.route = self.marks.plan("start", "south cardinal")
        hull.route_index = 0
        hull.under_con = True
        hull.at_maritime_tick(20.0)
        self.assertLess(
            hull.maritime_position.horizontal_distance_to(WorldPosition(0.0, 0.0)), 200.0
        )


class TestNavigationError(ScenarioTestCase):
    """
    `navigation-error`: the reckoning drifts from the truth by exactly what nobody
    aboard could see.
    """

    weather = dict(BREEZE, MARITIME_CURRENT_SET=0.0, MARITIME_CURRENT_DRIFT=1.0)

    def test_the_reckoning_falls_behind_the_ship(self):
        hull = self.a_sloop()
        hull.sail_plan = WORKING
        hull.orders = HelmOrders(heading=90.0, speed=0.0)
        hull.dead_reckoning = DeadReckoning(position=hull.maritime_position)

        self.sail(hull, 1800.0)

        reckoned = hull.dead_reckoning.position
        truth = hull.maritime_position
        self.assertGreater(reckoned.horizontal_distance_to(truth), 100.0)

    def test_and_the_error_is_the_current(self):
        """Northward set, so the truth is north of the reckoning and nowhere else."""
        hull = self.a_sloop()
        hull.sail_plan = WORKING
        hull.orders = HelmOrders(heading=90.0, speed=0.0)
        hull.dead_reckoning = DeadReckoning(position=hull.maritime_position)
        self.sail(hull, 1800.0)

        self.assertGreater(hull.maritime_position.y, hull.dead_reckoning.position.y)

    def test_in_slack_water_and_under_bare_poles_it_is_perfect(self):
        """
        Nothing rolls an error. There is no error to roll.

        Two things had to be taken out of this to make the claim true, and both
        are real. Under canvas there is leeway, which the reckoning cannot see
        either - so the sails come off her. And the reckoning is started once she
        is at a steady speed, because the log is read at the end of a step and
        over-counts while she is still working up: a navigator reading four knots
        and multiplying by the hour makes the same mistake.

        With neither, and no stream, the reckoning and the ship agree to the
        centimetre.

        """
        with override_settings(MARITIME_CURRENT_DRIFT=0.0, MARITIME_WIND_SPEED=0.0):
            hull = self.a_sloop(key="Slack")
            hull.sail_plan = FURLED
            hull.orders = HelmOrders(heading=90.0, speed=4.0)
            self.sail(hull, 300.0)

            hull.dead_reckoning = DeadReckoning(position=hull.maritime_position)
            settled = hull.maritime_position
            self.sail(hull, 1800.0)

            self.assertGreater(hull.maritime_position.x, settled.x + 1000.0)
            self.assertLess(
                hull.dead_reckoning.position.horizontal_distance_to(hull.maritime_position),
                0.5,
            )


# --- weather ---------------------------------------------------------------


class TestStormDelay(ScenarioTestCase):
    """
    `storm-delay`: the same passage takes longer in a gale.

    Notes:
        The interesting part is that it is not simply slower. A sloop under working
        canvas in a gale is fighting a heavy sea, and the sea is what takes her way.

    """

    def run_leg(self, sky, key):
        with override_settings(**sky):
            hull = self.a_sloop(key=key)
            hull.sail_plan = WORKING
            hull.orders = HelmOrders(heading=90.0, speed=0.0)
            self.sail(hull, 900.0)
            return hull.maritime_position.x

    def test_a_gale_costs_her_ground(self):
        self.assertLess(self.run_leg(GALE, "Gale"), self.run_leg(BREEZE, "Breeze"))

    def test_the_sea_is_what_does_it(self):
        with override_settings(**GALE):
            hull = self.a_sloop(key="Blown")
            self.assertNotEqual(hull.sea_here(), "calm")


# --- observation -----------------------------------------------------------


class TestContactDetection(ScenarioTestCase):
    """`contact-detection`: height of eye decides what is over the horizon."""

    weather = BREEZE

    def test_the_masthead_sees_what_the_deck_cannot(self):
        """
        A *low* hull, and the distinction matters. A twenty-metre rig is visible
        from a rowing boat at fourteen kilometres because height beats the curve;
        it is the small craft that vanish, and that is the asymmetry worth
        showing.

        """
        ours = self.a_sloop(key="Kestrel")
        far = self.a_sloop(key="Petrel", position=WorldPosition(14000.0, 0.0))
        far.air_draft = 3.0
        traffic().note(far, far.maritime_position)

        self.assertEqual(ours.contacts(height_of_eye=2.0), ())
        self.assertEqual(len(ours.contacts(height_of_eye=18.0)), 1)

    def test_closing_her_brings_her_into_sight_from_the_deck(self):
        ours = self.a_sloop(key="Kestrel")
        near = self.a_sloop(key="Petrel", position=WorldPosition(3000.0, 0.0))
        traffic().note(near, near.maritime_position)
        self.assertEqual(len(ours.contacts(height_of_eye=2.0)), 1)


# --- the scheduler ---------------------------------------------------------


class TestSchedulerFairness(ScenarioTestCase):
    """`scheduler-fairness`: a fleet larger than one pass is all served."""

    def test_everybody_gets_a_turn(self):
        clock = ManualTimeProvider()
        service = MaritimeSimulationService(clock, batch_size=4, budget_ms=0.0)
        fleet = [self.a_sloop(key=f"Hull {index}") for index in range(12)]
        for hull in fleet:
            hull.orders = HelmOrders(heading=90.0, speed=3.0)
            service.register(hull, ACTIVE)

        for _ in range(6):
            clock.advance(10.0)
            service.tick()

        for hull in fleet:
            self.assertGreater(hull.maritime_position.x, 0.0, hull.key)

    def test_nobody_is_served_twice_while_another_waits(self):
        clock = ManualTimeProvider()
        service = MaritimeSimulationService(clock, batch_size=3, budget_ms=0.0)
        fleet = [self.a_sloop(key=f"Hull {index}") for index in range(6)]
        for hull in fleet:
            service.register(hull, ACTIVE)

        clock.advance(10.0)
        first = set(service.tick())
        clock.advance(10.0)
        second = set(service.tick())
        self.assertEqual(first & second, set())


# --- gunnery ---------------------------------------------------------------


class TestBroadside(ScenarioTestCase):
    """`broadside`: guns that bear, fired together, at a ship on the beam."""

    weather = BREEZE

    def setUp(self):
        super().setUp()
        self.gun = WeaponType(
            key="six pounder",
            name="six-pounder",
            arc=STARBOARD_BROADSIDE,
            max_range=600.0,
            reload_time=90.0,
            projectile_speed=300.0,
            accuracy=0.8,
        )

    def test_a_broadside_bears_and_a_stern_chase_does_not(self):
        ours = self.a_sloop(key="Kestrel")
        ours.heading = 0.0
        abeam = self.a_sloop(key="Abeam", position=WorldPosition(300.0, 0.0))
        ahead = self.a_sloop(key="Ahead", position=WorldPosition(0.0, 300.0))
        for hull in (abeam, ahead):
            traffic().note(hull, hull.maritime_position)

        for index in range(4):
            ours.add_mount(Mount(key=f"gun {index}", weapon=self.gun))

        # She heads north; one lies on her starboard beam and one dead ahead.
        on_the_beam = ours.maritime_position.bearing_to(abeam.maritime_position)
        right_ahead = ours.maritime_position.bearing_to(ahead.maritime_position)
        self.assertEqual(len(ours.guns_bearing(on_the_beam - ours.heading)), 4)
        self.assertEqual(len(ours.guns_bearing(right_ahead - ours.heading)), 0)

    def test_the_broadside_is_fired_and_recorded(self):
        ours = self.a_sloop(key="Kestrel")
        ours.heading = 0.0
        target = self.a_sloop(key="Petrel", position=WorldPosition(300.0, 0.0))
        traffic().note(target, target.maritime_position)

        mount = Mount(key="gun 1", weapon=self.gun, loaded=True)
        ours.add_mount(mount)

        shot = fire(
            mount,
            ours.maritime_position,
            ours.heading,
            target,
            target.maritime_position,
            target.heading,
            target.speed,
            "calm",
            0.0,
            # Law 9: the RNG arrives as an argument. A fixed roll of nothing is a
            # certain hit, which is what a scenario about *bearing* wants.
            roll=lambda: 0.0,
        )
        self.assertTrue(shot)
        self.assertEqual(shot.mount, "gun 1")
        self.assertGreater(shot.flight_time, 0.0)


# --- boarding --------------------------------------------------------------


class TestBoardingScenario(ScenarioTestCase):
    """`boarding`: matched, lashed, and crossed."""

    weather = BREEZE

    def matched_pair(self):
        ours = self.a_sloop(key="Kestrel")
        theirs = self.a_sloop(key="Petrel", position=WorldPosition(16.0, 0.0))
        for hull in (ours, theirs):
            hull.heading = 90.0
            hull.ndb.speed = 4.0
            traffic().note(hull, hull.maritime_position)
        return ours, theirs

    def test_the_whole_of_it(self):
        ours, theirs = self.matched_pair()
        self.assertAlmostEqual(
            relative_speed(ours.heading, ours.speed, theirs.heading, theirs.speed), 0.0
        )

        self.assertTrue(ours.grapple(theirs))

        # And the crossing is walking, like everything else in this system.
        deck = ours.boarding_deck
        crossing = [obj for obj in deck.contents if obj.destination][0]
        self.char1.location = deck
        self.char1.move_to(crossing.destination, quiet=True, move_hooks=False)
        self.assertEqual(self.char1.location, theirs.boarding_deck)

    def test_she_shakes_them_off_by_sheering_away(self):
        ours, theirs = self.matched_pair()
        ours.grapple(theirs)

        theirs.orders = HelmOrders(heading=180.0, speed=6.0)
        for _ in range(6):
            theirs.at_maritime_tick(10.0)
            ours.at_maritime_tick(10.0)
            if not ours.grappled:
                break

        self.assertFalse(ours.grappled)


class TestCapture(ScenarioTestCase):
    """`capture`: she strikes, and it is recorded and nothing more."""

    weather = BREEZE

    def test_she_strikes_to_the_ship_alongside(self):
        ours = self.a_sloop(key="Kestrel")
        theirs = self.a_sloop(key="Petrel", position=WorldPosition(16.0, 0.0))
        for hull in (ours, theirs):
            hull.heading = 90.0
            traffic().note(hull, hull.maritime_position)

        ours.grapple(theirs)
        self.assertTrue(theirs.strike(ours))
        self.assertEqual(theirs.struck_to, ours)

    def test_and_the_prize_can_take_it_back(self):
        """A prize crew can be overwhelmed. The state has to be leavable."""
        ours = self.a_sloop(key="Kestrel")
        theirs = self.a_sloop(key="Petrel", position=WorldPosition(16.0, 0.0))
        ours.grapple(theirs)
        theirs.strike(ours)
        self.assertTrue(theirs.rehoist())
        self.assertFalse(theirs.struck)

    def test_striking_confers_nothing(self):
        """
        What a captor may do with a prize is authority, which is phase 14 and is
        Gary's. See `DECISIONS.md`.

        """
        ours = self.a_sloop(key="Kestrel")
        theirs = self.a_sloop(key="Petrel", position=WorldPosition(16.0, 0.0))
        ours.grapple(theirs)
        theirs.strike(ours)

        theirs.orders = HelmOrders(heading=90.0, speed=3.0)
        theirs.at_maritime_tick(30.0)
        self.assertGreater(theirs.speed, 0.0)


# --- charts ----------------------------------------------------------------


class TestChartedApproach(ScenarioTestCase):
    """
    A scenario the design did not name, and should have.

    Notes:
        A chart is wrong in fixed places rather than randomly, which is the whole
        reason a careful navigator still goes aground. Worth a scenario because it
        is the one part of navigation where the *right* behaviour looks like a bug.

    """

    weather = dict(BREEZE, MARITIME_MAP_PROVIDER=f"{__name__}.Ledge")

    def test_the_same_chart_is_wrong_in_the_same_place_twice(self):
        hull = self.a_sloop()
        hull.add_chart(
            Chart(
                key="Approaches",
                west=0.0,
                east=4000.0,
                south=-2000.0,
                north=2000.0,
                quality=0.6,
                surveyed_at=0.0,
                seed=91,
                maker="the Harbour Board",
            )
        )
        hull.maritime_position = WorldPosition(1500.0, 200.0)
        first = hull.charted_depth()
        hull.maritime_position = WorldPosition(3000.0, 0.0)
        hull.maritime_position = WorldPosition(1500.0, 200.0)
        self.assertAlmostEqual(first, hull.charted_depth())
