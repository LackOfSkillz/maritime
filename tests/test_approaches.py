"""
Tests for the marks laid on the Aetos coast, and for the water under them.

**These sound the ground rather than check the arithmetic.** A navigation network is a set
of claims about where a ship can go, and the only way to be wrong about a claim like that is
for there to be a rock in the way. So every mark is sounded, every leg between two marks is
sounded along its length, and every final leg from a mark to the berth it serves is sounded
too - which is the leg a ship actually arrives on and the one nobody would have thought to
check.

The positions are a mixture of derived and authored, deliberately: the harbour marks are
walked out from the quays they serve, and the fairway is a coordinate somebody chose after
sounding a grid. Both need this test, and the authored one needs it more.
"""

from django.test import override_settings
from evennia.utils.test_resources import BaseEvenniaTestCase

from ..bathymetry import MaritimeMapProvider
from ..example.aetos_world import approaches, islands, village
from ..position import WorldPosition

#: The least water any leg of this network may have on it, in metres.
#:
#: Eight. The deepest hull in `shipyard`'s book is the barque at five metres, and three
#: metres under her keel on a marked channel is not generous - it is the minimum anybody
#: would call a channel. A leg that fails this is not a slightly tight leg; it is a leg with
#: a rock on it.
LEAST_WATER = 8.0

#: How finely to sound a leg.
#:
#: Four hundred steps puts a sounding every ten metres or so on the island legs and every
#: thirty on the long one, which is finer than the shoals that were actually found - two of
#: them, of two point seven and three point four metres, either of which is a wreck.
STEPS = 400

#: The world these marks were laid against, so the test measures the shipped coast rather
#: than whatever a host game happens to have configured.
SHIPPED = "evennia.contrib.full_systems.maritime.baked_world.AetosCoast"


def sound_along(world, first, second, steps=STEPS):
    """
    Args:
        world (MaritimeMapProvider): The ground.
        first (WorldPosition): One end of the leg.
        second (WorldPosition): The other.
        steps (int, optional): How many soundings to take.

    Returns:
        least (float): The shallowest water on the leg, in metres.

    """
    return min(
        -world.terrain_z_at(
            WorldPosition(
                first.x + (second.x - first.x) * step / steps,
                first.y + (second.y - first.y) * step / steps,
            )
        )
        for step in range(steps + 1)
    )


@override_settings(MARITIME_MAP_PROVIDER=SHIPPED)
class ApproachesTestCase(BaseEvenniaTestCase):
    """The shipped coast, and the marks laid on it."""

    def setUp(self):
        super().setUp()
        from .. import config

        self.world = config.map_provider()
        self.laid = dict(approaches.marks_for(self.world))


class TestTheMarksStandInWater(ApproachesTestCase):
    """Every mark is somewhere a ship could actually be."""

    def test_every_harbour_has_one(self):
        wanted = {approaches.roads_of("Careenage")}
        wanted |= {approaches.roads_of(one["key"]) for one in islands.ISLANDS}
        self.assertEqual(wanted - set(self.laid), set())

    def test_the_fairway_is_laid_too(self):
        self.assertIn(approaches.FAIRWAY[0], self.laid)

    def test_every_mark_has_water_under_it(self):
        for key, where in self.laid.items():
            under = -self.world.terrain_z_at(where)
            self.assertGreaterEqual(under, LEAST_WATER, f"{key} stands in {under:.1f} m")

    def test_the_fairway_has_a_great_deal_of_water_under_it(self):
        # It exists to be the deep way round two shoals; a fairway in nine metres would be
        # doing half a job.
        where = self.laid[approaches.FAIRWAY[0]]
        self.assertGreater(-self.world.terrain_z_at(where), 15.0)


class TestEveryLegIsClear(ApproachesTestCase):
    """Nothing this network says is passable has a rock on it."""

    def test_every_channel_has_water_along_its_whole_length(self):
        for first, second in approaches.channels():
            least = sound_along(self.world, self.laid[first], self.laid[second])
            self.assertGreaterEqual(
                least, LEAST_WATER, f"{first} -> {second} shoals to {least:.1f} m"
            )

    def test_the_direct_line_to_gannet_is_the_one_that_fouls(self):
        """
        The reason the fairway exists, measured rather than asserted.

        Notes:
            Without this the fairway is a coordinate with a story attached. With it, the
            story is checked: the straight line really is fouled, so the dog-leg really is
            necessary, and if the ground is ever rebuilt into something where it is not,
            this test says so and the mark can go.

        """
        direct = sound_along(
            self.world,
            self.laid[approaches.roads_of("Careenage")],
            self.laid[approaches.roads_of("Gannet Isle")],
        )
        self.assertLess(direct, LEAST_WATER, f"the direct line now carries {direct:.1f} m")


class TestTheLastLegIsClear(ApproachesTestCase):
    """
    The leg from a mark to the berth it serves.

    Notes:
        The one nobody would think to check, and the one a ship actually arrives on.
        `passage.can_reach` makes the berth the final waypoint precisely so the sailing
        master's slow approach is the approach to the quay - which means this leg is sailed
        under his hand, at night, in whatever weather, on every passage anybody ever orders.

    """

    def test_the_run_in_to_every_island_pier_is_clear(self):
        found = {
            mark.key: mark
            for mark in self.world.landmarks_near(WorldPosition(0.0, 6000.0), 200_000.0)
        }
        for island in islands.ISLANDS:
            landmark = found.get(island["key"])
            if landmark is None:
                continue
            berth = islands.landing_position(landmark, self.world)
            mark = self.laid[approaches.roads_of(island["key"])]
            least = sound_along(self.world, mark, berth, steps=100)
            # Against the berth's own depth rather than the channel figure: an island
            # landing is dug to four metres by design, and demanding eight on the last
            # hundred metres would be demanding the pier be somewhere else.
            self.assertGreaterEqual(
                least, islands.LANDING_DEPTH - 0.5, f"{island['key']} run-in is {least:.1f} m"
            )

    def test_the_run_in_to_every_careenage_pier_is_clear(self):
        mark = self.laid[approaches.roads_of("Careenage")]
        for pier in village.PIERS:
            berth = village.berth_for(pier, self.world)
            least = sound_along(self.world, mark, berth.position)
            self.assertGreaterEqual(
                least,
                berth.max_draft,
                f"the run in to {pier['key']} shoals to {least:.1f} m "
                f"against a berth advertising {berth.max_draft:.1f}",
            )


class TestTheNetworkItself(ApproachesTestCase):
    """What the network answers, once it is built."""

    def network(self):
        """
        Returns:
            network (AetosApproaches): Built against the shipped ground.

        """
        return approaches.AetosApproaches(self.world)

    def test_it_can_lay_a_course_from_the_harbour_to_the_far_island(self):
        route = self.network().plan(
            approaches.roads_of("Careenage"), approaches.roads_of("Outer Skerry")
        )
        self.assertTrue(route)

    def test_that_course_goes_by_way_of_every_island_between(self):
        # Which is what a chain is. A route that skipped the middle would mean somebody had
        # linked the ends together, and the middle islands would stop being worth a call.
        route = self.network().plan(
            approaches.roads_of("Careenage"), approaches.roads_of("Outer Skerry")
        )
        names = [mark.key for mark in route.waypoints]
        for island in islands.ISLANDS:
            self.assertIn(approaches.roads_of(island["key"]), names)

    def test_it_goes_out_by_the_fairway(self):
        route = self.network().plan(
            approaches.roads_of("Careenage"), approaches.roads_of("Gannet Isle")
        )
        self.assertIn(approaches.FAIRWAY[0], [mark.key for mark in route.waypoints])

    def test_a_mark_it_has_never_heard_of_gets_no_route(self):
        # Which is how the pond is answered: it is not that the plan fails, it is that
        # there is nothing to plan to.
        self.assertFalse(self.network().plan(approaches.roads_of("Careenage"), "the pond"))

    def test_every_link_joins_two_marks_it_actually_laid(self):
        laid = {mark.key for mark in self.network().marks()}
        for first, second in approaches.channels():
            self.assertIn(first, laid)
            self.assertIn(second, laid)


class TestWalkingSeaward(ApproachesTestCase):
    """`offing_from`, which is where every harbour mark comes from."""

    def test_it_finds_deep_water_off_the_long_pier(self):
        head = village.pier_position(village.PIERS[0])
        where = approaches.offing_from(head, self.world)
        self.assertGreaterEqual(-self.world.terrain_z_at(where), approaches.OFFING_DEPTH)

    def test_it_stays_inside_the_range_a_mark_can_serve_from(self):
        # A mark further from its harbour than `passage.APPROACH_RANGE` serves no harbour,
        # so a search allowed to run further could only ever return an answer that does not
        # work - and would do it silently.
        from ..passage import APPROACH_RANGE

        self.assertLessEqual(approaches.OFFING_SEARCH_M, APPROACH_RANGE)

    def test_every_harbour_mark_is_near_enough_to_serve_its_harbour(self):
        from ..passage import APPROACH_RANGE

        head = village.pier_position(village.PIERS[0])
        off = self.laid[approaches.roads_of("Careenage")]
        self.assertLessEqual(head.horizontal_distance_to(off), APPROACH_RANGE)

    def test_it_keeps_the_deepest_it_found_rather_than_the_far_edge(self):
        """
        The fallback, on ground that has nothing deep enough anywhere.

        Notes:
            Marching to the end of the walk was the first version, and it put a mark in
            whatever happened to be at the far edge - six metres on the coast that caught
            it, and a beach on a coast that shelved the other way.

        """
        where = approaches.offing_from(WorldPosition(0.0, 0.0), _Sloping(), bearing=270.0)
        # The deepest point on a westward walk over ground that falls to 5 m at 1 km and
        # rises again after: 1 km out, not 4 km out.
        self.assertAlmostEqual(where.x, -1000.0, delta=approaches.OFFING_STEP_M)


class _Sloping(MaritimeMapProvider):
    """
    Ground with a hollow in it a kilometre west, and nothing deep enough anywhere.

    Notes:
        A real provider rather than a bare object with one method, because the walk asks
        about hazards and the tide as well as the seabed now - which is the whole point of
        it - and a stub that answered only `terrain_z_at` would be testing a version of the
        code that no longer exists.

    """

    def terrain_z_at(self, position):
        out = -position.x
        if out <= 0.0:
            return -1.0
        return -(5.0 - abs(out - 1000.0) / 1000.0)


class TestTheMarksDoNotMoveWithTheTide(ApproachesTestCase):
    """
    A buoy is moored. It does not shift with the water over it.

    Notes:
        Sited against the clock, `offing_from` walked further at low water than at high -
        because it stops at a depth, and the depth is what the tide changes. Careenage Roads
        came out at two positions a quarter of a kilometre apart within an hour.

        That is not cosmetic. A network is a set of claims about where the safe water runs;
        if the claims move, a course plotted at high water leads somewhere else at low, and
        the legs this file sounds are not the legs a ship sails.

    """

    def test_the_marks_are_sited_against_the_datum(self):
        self.assertEqual(approaches.config_now(), approaches.DATUM)

    def test_laying_them_twice_lays_them_in_the_same_place(self):
        again = dict(approaches.marks_for(self.world))
        self.assertEqual(set(again), set(self.laid))
        for key, where in again.items():
            self.assertEqual(where, self.laid[key], f"{key} moved")

    def test_they_are_the_same_at_any_hour_of_the_tide(self):
        """
        Measured across a whole tidal cycle rather than asserted.

        Notes:
            The clock is not consulted at all now, so this passes trivially - which is the
            point. It fails the moment somebody puts `time_provider().now()` back, which is
            the natural thing to write and was written once already.

        """
        from .. import config

        moved = []
        for hour in range(0, 13):
            with self.settings(MARITIME_TIME_SCALE=1.0):
                laid = dict(approaches.marks_for(self.world))
            for key, where in laid.items():
                if where != self.laid[key]:
                    moved.append((hour, key))
        self.assertEqual(moved, [], f"marks moved with the clock: {moved[:4]}")
        self.assertIsNotNone(config)
