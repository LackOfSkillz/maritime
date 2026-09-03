"""
Tests for sailing in company.

The claim worth testing hardest is the one the whole item rests on: **a station is relative
to the ship you keep it on, not to the compass.** Everything else is arithmetic; that is the
difference between a squadron and a crowd.

"""

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest

from ..consorts import (
    LEAST_STATION,
    MOST_STATION,
    NOT_IN_COMPANY,
    SAME_VESSEL,
    TOO_CLOSE,
    TOO_FAR,
    off_station,
    squadron,
    station_point,
)
from ..motion import MotionLimits
from ..position import WorldPosition
from ..rooms import ShipRoom
from ..typeclasses import Vessel
from ..vessel import OPEN
from .base import EmptySeaMixin

HERE = WorldPosition(0.0, 0.0)


class TestWhereAStationIs(BaseEvenniaTest):
    """The arithmetic, with no ships attached."""

    def test_dead_astern_of_a_ship_heading_north(self):
        where = station_point(HERE, 0.0, 180.0, 100.0)
        self.assertAlmostEqual(where.y, -100.0, places=3)
        self.assertAlmostEqual(where.x, 0.0, places=3)

    def test_and_dead_astern_of_one_heading_east(self):
        """
        The same order, a different ship's heading, a different piece of water. If these
        two came out the same the station would be on the compass and the whole item would
        be pointless.

        """
        where = station_point(HERE, 90.0, 180.0, 100.0)
        self.assertAlmostEqual(where.x, -100.0, places=3)
        self.assertAlmostEqual(where.y, 0.0, places=3)

    def test_on_her_starboard_beam(self):
        where = station_point(HERE, 0.0, 90.0, 100.0)
        self.assertAlmostEqual(where.x, 100.0, places=3)

    def test_the_station_turns_with_her(self):
        """What station-keeping *is*: she wears, and the station goes round with her."""
        before = station_point(HERE, 0.0, 90.0, 100.0)
        after = station_point(HERE, 180.0, 90.0, 100.0)
        self.assertNotAlmostEqual(before.x, after.x, places=1)

    def test_being_nowhere_is_no_distance(self):
        self.assertEqual(off_station(None, HERE), 0.0)


class CompanyTestCase(EmptySeaMixin, BaseEvenniaTest):
    """Two hulls, one following the other."""

    def setUp(self):
        super().setUp()
        self.leader = self.a_ship("Petrel", WorldPosition(0.0, 0.0))
        self.follower = self.a_ship("Kestrel", WorldPosition(0.0, -200.0))

    def a_ship(self, key, position):
        hull = create.create_object(Vessel, key=key)
        hull.length, hull.beam = 18.0, 5.4
        hull.motion_limits = MotionLimits(max_speed=6.0, acceleration=0.5, turn_rate=5.0)
        hull.maritime_position = position
        hull.heading = 0.0
        deck = create.create_object(ShipRoom, key=f"{key} Deck")
        deck.vessel = hull
        deck.exposure = OPEN
        return hull


class TestTakingStation(CompanyTestCase):
    """Ordering it, and refusing to."""

    def test_she_starts_on_her_own(self):
        self.assertFalse(self.follower.in_company)
        self.assertIsNone(self.follower.consort)

    def test_she_can_be_ordered_into_company(self):
        self.assertTrue(self.follower.keep_station(self.leader, 180.0, 200.0))
        self.assertIs(self.follower.consort, self.leader)

    def test_she_cannot_keep_station_on_herself(self):
        self.assertEqual(self.follower.keep_station(self.follower, 180.0, 200.0).code, SAME_VESSEL)

    def test_nor_on_nobody(self):
        self.assertFalse(self.follower.keep_station(None, 180.0, 200.0))

    def test_a_station_out_of_signalling_range_is_refused(self):
        result = self.follower.keep_station(self.leader, 180.0, MOST_STATION + 1.0)
        self.assertEqual(result.code, TOO_FAR)

    def test_and_one_close_enough_to_be_a_collision(self):
        result = self.follower.keep_station(self.leader, 180.0, LEAST_STATION - 1.0)
        self.assertEqual(result.code, TOO_CLOSE)

    def test_taking_station_gives_up_the_passage(self):
        """
        She cannot steer for a mark and for a moving ship at once, and a mate holding both
        would take whichever he was asked about last.

        """
        self.follower.under_con = True
        self.follower.keep_station(self.leader, 180.0, 200.0)
        self.assertFalse(self.follower.under_con)

    def test_she_can_part_company(self):
        self.follower.keep_station(self.leader, 180.0, 200.0)
        self.assertTrue(self.follower.part_company())
        self.assertFalse(self.follower.in_company)

    def test_parting_from_nobody(self):
        self.assertFalse(self.follower.part_company())


class TestHoldingIt(CompanyTestCase):
    """Where she is against where she should be."""

    def test_a_ship_not_in_company_has_no_station(self):
        self.assertEqual(self.follower.station().code, NOT_IN_COMPANY)

    def test_two_cables_astern_is_two_cables_astern(self):
        self.follower.keep_station(self.leader, 180.0, 200.0)
        where = self.follower.station()
        self.assertTrue(where.on_station)
        self.assertAlmostEqual(where.off_by, 0.0, places=3)

    def test_off_to_one_side_is_off_station(self):
        self.follower.keep_station(self.leader, 180.0, 200.0)
        self.follower.maritime_position = WorldPosition(150.0, -200.0)
        self.assertFalse(self.follower.station().on_station)

    def test_the_station_moves_when_the_consort_turns(self):
        """
        She was exactly on station. The leader wears onto the opposite course and the same
        water is now ahead of her instead of astern, so the same ship in the same place is
        out of position without having moved.

        """
        self.follower.keep_station(self.leader, 180.0, 200.0)
        self.assertTrue(self.follower.station().on_station)
        self.leader.heading = 180.0
        self.assertFalse(self.follower.station().on_station)

    def test_falling_behind_is_told_apart_from_wandering(self):
        """
        Different failures wanting different answers: one is crowd on sail, the other is
        alter course. A single 'off station' number cannot say which.

        """
        self.follower.keep_station(self.leader, 180.0, 200.0)
        self.follower.maritime_position = WorldPosition(0.0, -600.0)
        self.assertTrue(self.follower.station().astern)

    def test_a_consort_with_no_position_is_lost(self):
        self.follower.keep_station(self.leader, 180.0, 200.0)
        self.leader.maritime_position = None
        self.assertFalse(self.follower.station())


class TestWorkingTheStation(CompanyTestCase):
    """What she does about it on the tick."""

    def test_a_ship_on_her_own_does_nothing(self):
        self.assertFalse(self.follower.work_station())

    def test_on_station_she_matches_her_consort(self):
        self.leader.heading = 45.0
        self.leader.ndb.speed = 3.0
        self.follower.keep_station(self.leader, 180.0, 200.0)
        self.follower.maritime_position = station_point(
            self.leader.maritime_position, 45.0, 180.0, 200.0
        )
        self.assertTrue(self.follower.work_station())
        self.assertAlmostEqual(self.follower.orders.heading, 45.0, places=3)

    def test_off_station_she_steers_for_it(self):
        self.follower.keep_station(self.leader, 180.0, 200.0)
        self.follower.maritime_position = WorldPosition(400.0, -200.0)
        self.follower.work_station()
        # Her station is west of her, so she must be steering somewhere westerly.
        self.assertGreater(self.follower.orders.heading, 180.0)
        self.assertLess(self.follower.orders.heading, 360.0)

    def test_losing_her_consort_ends_the_company(self):
        self.follower.keep_station(self.leader, 180.0, 200.0)
        self.leader.maritime_position = None
        self.follower.work_station()
        self.assertFalse(self.follower.in_company)

    def test_a_ship_made_fast_keeps_no_station(self):
        self.follower.keep_station(self.leader, 180.0, 200.0)
        self.follower.anchored = True
        self.assertFalse(self.follower.work_station())


class TestASquadron(CompanyTestCase):
    """A chain, because the ship ahead is the one you can see."""

    def test_nobody_astern_is_no_squadron(self):
        self.assertEqual(squadron(self.leader), ())

    def test_one_astern(self):
        self.follower.keep_station(self.leader, 180.0, 200.0)
        self.assertEqual(squadron(self.leader), (self.follower,))

    def test_and_one_astern_of_her(self):
        third = self.a_ship("Gannet", WorldPosition(0.0, -400.0))
        self.follower.keep_station(self.leader, 180.0, 200.0)
        third.keep_station(self.follower, 180.0, 200.0)
        self.assertEqual(squadron(self.leader), (self.follower, third))

    def test_a_ring_of_ships_does_not_hang(self):
        """
        Two ships each keeping station on the other has no head, and walking it would not
        stop. Nobody would order it; the code still has to survive it.

        """
        self.follower.keep_station(self.leader, 180.0, 200.0)
        self.leader.keep_station(self.follower, 180.0, 200.0)
        self.assertIn(self.follower, squadron(self.leader))
