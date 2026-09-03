"""
Tests for the script that drives the simulation.

"""

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest

from ..clock import ManualTimeProvider
from ..cmdsets import HelmCmdSet
from ..motion import HelmOrders, MotionLimits
from ..position import WorldPosition
from ..scripts import CHECKPOINT_EVERY, MaritimeDriver
from ..simulation import ACTIVE, DORMANT
from ..typeclasses import Vessel
from .base import EmptySeaMixin


class DriverTestCase(EmptySeaMixin, BaseEvenniaTest):
    """A driver and a vessel to drive."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Test Sloop")
        self.hull.maritime_position = WorldPosition(0.0, 0.0)
        self.hull.motion_limits = MotionLimits(max_speed=10.0, acceleration=1.0, turn_rate=6.0)
        self.hull.orders = HelmOrders(heading=90.0, speed=10.0)
        # autostart=False: Evennia runs a repeating script on creation, and the
        # live timer would race every manual at_repeat() in these tests.
        self.driver = create.create_script(MaritimeDriver, autostart=False)
        # A hand-driven clock, so a pass can cover real game time without the
        # test waiting for it. This is what the time seam is for.
        self.clock = ManualTimeProvider()
        self.driver.ndb.time_provider = self.clock
        self.driver.at_start()

    def run_passes(self, count, seconds=10.0):
        """Advance game time and run that many simulation passes."""
        for _ in range(count):
            self.clock.advance(seconds=seconds)
            self.driver.at_repeat()

    def tearDown(self):
        self.driver.delete()
        super().tearDown()


class TestDriverSetup(DriverTestCase):
    """Creation and configuration."""

    def test_repeats(self):
        self.assertGreater(self.driver.interval, 0)

    def test_is_persistent(self):
        """It must survive a reload, or the world stops the first time you save."""
        self.assertTrue(self.driver.persistent)

    def test_builds_a_service(self):
        self.assertIsNotNone(self.driver.service)

    def test_registers_launched_vessels(self):
        self.assertIn(self.hull, self.driver.service)

    def test_ignores_vessels_on_the_stocks(self):
        """
        A vessel with no position has not been launched. Registering her means
        waking her every pass to discover she is still not afloat.

        """
        create.create_object(Vessel, key="On The Stocks")
        self.driver.at_start()
        keys = [vessel.key for vessel in self.driver.service.registered()]
        self.assertNotIn("On The Stocks", keys)


class TestDriverRuns(DriverTestCase):
    """Passes actually move ships."""

    def test_a_pass_moves_her(self):
        self.run_passes(20)
        self.assertNotEqual(self.hull.maritime_position, WorldPosition(0.0, 0.0))

    def test_counts_its_passes(self):
        self.run_passes(1)
        self.assertEqual(self.driver.db.passes, 1)

    def test_rebuilds_the_service_if_it_is_missing(self):
        """After a reload the in-memory service is gone; the next pass restores it."""
        self.driver.ndb.service = None
        self.driver.at_repeat()
        self.assertIsNotNone(self.driver.service)

    def test_a_failing_pass_does_not_stop_the_script(self):
        """
        An exception escaping a repeating script stops it, which would freeze
        every vessel in the game until somebody noticed.

        """

        def explode():
            raise RuntimeError("simulation broke")

        self.driver.ndb.service.tick = explode
        self.driver.at_repeat()  # must not raise

    def test_checkpoints_periodically(self):
        self.run_passes(CHECKPOINT_EVERY)
        self.assertIsNotNone(self.hull.db.maritime_position)

    def test_does_not_checkpoint_every_pass(self):
        """Writing every vessel to disk every couple of seconds is the thing to avoid."""
        self.run_passes(1)
        self.assertIsNone(self.hull.db.maritime_position)


class TestDriverLifecycle(DriverTestCase):
    """Shutdown and reload."""

    def test_shutdown_flushes(self):
        self.run_passes(5)
        self.driver.at_server_shutdown()
        self.assertNotEqual(self.hull.db.maritime_position, WorldPosition(0.0, 0.0))

    def test_reload_flushes(self):
        self.run_passes(5)
        self.driver.at_server_reload()
        self.assertNotEqual(self.hull.db.maritime_position, WorldPosition(0.0, 0.0))

    def test_flushing_without_a_service_is_safe(self):
        self.driver.ndb.service = None
        self.driver.at_server_shutdown()  # must not raise


class TestDriverConvenience(DriverTestCase):
    """Adding and laying up."""

    def test_add_vessel_registers(self):
        another = create.create_object(Vessel, key="Second Sloop")
        another.maritime_position = WorldPosition(5.0, 5.0)
        self.assertTrue(self.driver.add_vessel(another))

    def test_lay_up_makes_her_dormant(self):
        self.driver.lay_up(self.hull)
        self.assertEqual(self.driver.service.tier_of(self.hull), DORMANT)

    def test_a_laid_up_vessel_stops_moving(self):
        self.driver.lay_up(self.hull)
        self.run_passes(20)
        self.assertEqual(self.hull.maritime_position, WorldPosition(0.0, 0.0))

    def test_a_laid_up_vessel_is_still_known(self):
        """Dormant, not removed - she is still checkpointed, just not advanced."""
        self.driver.lay_up(self.hull)
        self.assertIn(self.hull, self.driver.service)

    def test_add_vessel_accepts_a_tier(self):
        another = create.create_object(Vessel, key="Distant Trader")
        another.maritime_position = WorldPosition(9999.0, 9999.0)
        self.driver.add_vessel(another, tier=ACTIVE)
        self.assertEqual(self.driver.service.tier_of(another), ACTIVE)


class TestHelmCmdSet(EmptySeaMixin, BaseEvenniaTest):
    """The command set itself."""

    def test_has_the_helm_commands(self):
        cmdset = HelmCmdSet()
        cmdset.at_cmdset_creation()
        keys = {command.key for command in cmdset.commands}
        self.assertEqual(
            keys,
            {
                "helm",
                "crew",
                "guns",
                "load",
                "fire",
                "hold fire",
                "speed",
                "allstop",
                "position",
                "sail",
                "wind",
                "weather",
                "current",
                "sound",
                "scan",
                "target",
                "lookout",
                "drop anchor",
                "weigh anchor",
                "spring",
                "fires",
                "fight fire",
                "pumps",
                "man pumps",
                "fother",
                "keep station",
                "part company",
                "station",
                "repairs",
                "set repairs",
                "refit",
                "butchers bill",
                "start them",
                "let it go",
                "cut cable",
                "dock",
                "kedge",
                "ports",
                "make for",
                "fix",
                "chart",
                "plot",
                "follow",
                "belay",
                "look",
                "watch",
                "cast off",
                "stow",
                "discharge",
                "manifest",
                "give way",
                "paddle",
                "stretch out",
                "easy",
                "hold water",
                "oars",
                "grapple",
                "cut grapples",
                "strike",
                "grapples",
                "@maritime",
            },
        )

    def test_the_staff_view_is_locked(self):
        """Raw coordinates are not for players."""
        from ..commands import CmdMaritimeStatus

        self.assertIn("Builder", CmdMaritimeStatus.locks)

    def test_is_addable_by_path(self):
        """
        Evennia stores a cmdset as the path it came from, so a set built on the
        fly vanishes at the next reload and takes every command with it.

        """
        room = create.create_object("evennia.objects.objects.DefaultRoom", key="Deck")
        room.cmdset.add(f"{__package__.rsplit(chr(46), 1)[0]}.cmdsets.HelmCmdSet")
        self.assertTrue(room.cmdset.has("maritime_helm"))


class TestNoTwoCommandsAnswerToOneName(EmptySeaMixin, BaseEvenniaTest):
    """
    **An alias collision does not raise. One command simply displaces the other.**

    `butchers bill` was given `muster` as an alias, which `crew` already had. Nothing
    complained, no exception was thrown, and `crew` disappeared out of the helm set
    entirely - a working command gone, and only a contract test asserting exactly which
    verbs the set holds noticed it had happened.

    A guard for the whole class rather than for that one pair, because the next collision
    will be between two commands nobody is thinking about together.

    """

    def classes(self):
        """
        Returns:
            classes (tuple): `(name, class)` for every set this contrib ships.

        """
        from ..cmdsets import HelmCmdSet, ShipwrightCmdSet
        from ..commands.handbook import MaritimeHandbookCmdSet
        from ..commands.interface import MaritimeInterfaceCmdSet
        from ..commands.passage import PassageCmdSet
        from ..commands.shipyard import MaritimeShipyardCmdSet

        return tuple(
            (cls.__name__, cls)
            for cls in (
                HelmCmdSet,
                ShipwrightCmdSet,
                MaritimeHandbookCmdSet,
                MaritimeInterfaceCmdSet,
                PassageCmdSet,
                MaritimeShipyardCmdSet,
            )
        )

    def test_every_name_in_every_set_is_its_own(self):
        """
        Checked against what each set *adds*, not against what it ends up holding.

        By the time the set is built the collision has already been resolved - one
        command displaced the other and the survivor answers to both names - so reading
        the finished set finds nothing wrong. That is exactly why the bug was invisible.
        The commands are therefore collected as they go in.

        """
        from evennia.commands.cmdset import CmdSet as BaseCmdSet

        for name, cls in self.classes():
            added = []
            original = BaseCmdSet.add

            def record(self, command, **kwargs):
                added.append(command)
                return original(self, command, **kwargs)

            BaseCmdSet.add = record
            try:
                cls().at_cmdset_creation()
            finally:
                BaseCmdSet.add = original

            seen = {}
            for command in added:
                key = getattr(command, "key", None)
                if key is None:
                    continue
                for spoken in (key, *getattr(command, "aliases", ())):
                    spoken = str(spoken).lower()
                    if spoken in seen and seen[spoken] != key:
                        self.fail(
                            f"{name}: '{spoken}' answers for both '{seen[spoken]}' and "
                            f"'{key}'. Nothing raises - one simply displaces the other."
                        )
                    seen[spoken] = key

    def test_muster_is_the_crews_own(self):
        """The pair that found it, kept as the worked example."""
        from ..cmdsets import HelmCmdSet

        made = HelmCmdSet()
        made.at_cmdset_creation()
        answers = {
            spoken.lower(): command.key
            for command in made.commands
            for spoken in (command.key, *command.aliases)
        }
        self.assertEqual(answers.get("muster"), "crew")
        self.assertIn("crew", {command.key for command in made.commands})
