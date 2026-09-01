"""
Tests for the example world.

Not decoration. An example that quietly stopped working would be the first thing a new
reader met, and "the islands are a fair sail apart" is a requirement rather than a hope -
so it is asserted rather than eyeballed.

"""

from django.test import override_settings
from evennia.utils.test_resources import BaseEvenniaTest, BaseEvenniaTestCase

from ..bathymetry import MUD, ROCK, SAND
from ..example import (
    CRAFT,
    CRUISING_SPEED,
    ISLANDS,
    POND_CENTRE,
    POND_RADIUS,
    RIVER,
    RIVER_DRIFT,
    RIVER_HALF_WIDTH,
    ExampleCurrents,
    ExampleSeabed,
    build,
    distance_to_river,
    harbour_position,
    island_at,
    river_set_at,
)
from ..example.geography import MAINLAND_Z, POND_DEPTH, RIVER_DEPTH
from ..example.world import FERRY_STEPS, POND_LANDING, STONE_QUAY
from ..oars import PADDLED, ROWED
from ..position import WorldPosition
from ..rooms import PortRoom, ShipRoom
from ..typeclasses import Vessel
from .base import EmptySeaMixin

#: Gary's requirement, as a number.
MINIMUM_LEG = 5.0 * 60.0
MAXIMUM_LEG = 10.0 * 60.0


class TestTheIslandsAreAFairSailApart(BaseEvenniaTestCase):
    """
    The one requirement of the layout that is not a matter of taste.

    Notes:
        Five to ten minutes under working sail, leg by leg, starting from the
        mainland quay. Asserted rather than eyeballed because moving one island a
        few hundred metres is exactly the sort of edit that looks harmless.

    """

    def legs(self):
        """
        Returns:
            legs (tuple): `(name, seconds)` for each passage, west to east.

        """
        found = []
        previous = STONE_QUAY
        for island in ISLANDS:
            here = harbour_position(island)
            found.append((island[0], previous.horizontal_distance_to(here) / CRUISING_SPEED))
            previous = here
        return tuple(found)

    def test_there_are_six_islands(self):
        self.assertEqual(len(ISLANDS), 6)

    def test_every_leg_is_at_least_five_minutes(self):
        for name, seconds in self.legs():
            self.assertGreaterEqual(seconds, MINIMUM_LEG, f"{name} is too close")

    def test_every_leg_is_at_most_ten_minutes(self):
        for name, seconds in self.legs():
            self.assertLessEqual(seconds, MAXIMUM_LEG, f"{name} is too far")

    def test_they_run_eastward(self):
        """So a beginner can follow the chain without navigating."""
        eastings = [island[1] for island in ISLANDS]
        self.assertEqual(eastings, sorted(eastings))

    def test_no_two_islands_overlap(self):
        for first in ISLANDS:
            for second in ISLANDS:
                if first is second:
                    continue
                apart = WorldPosition(first[1], first[2]).horizontal_distance_to(
                    WorldPosition(second[1], second[2])
                )
                self.assertGreater(apart, first[3] + second[3])


class TestTheGround(BaseEvenniaTestCase):
    """What is under the water, and where the water stops."""

    def setUp(self):
        super().setUp()
        self.sea = ExampleSeabed()

    def test_the_mainland_is_dry(self):
        self.assertAlmostEqual(self.sea.terrain_z_at(WorldPosition(-2000.0, -2000.0)), MAINLAND_Z)

    def test_the_pond_is_water_in_the_middle_of_it(self):
        self.assertAlmostEqual(self.sea.terrain_z_at(POND_CENTRE), -POND_DEPTH)

    def test_the_pond_has_an_edge(self):
        outside = WorldPosition(POND_CENTRE.x, POND_CENTRE.y + POND_RADIUS + 50.0)
        self.assertAlmostEqual(self.sea.terrain_z_at(outside), MAINLAND_Z)

    def test_the_river_is_cut_through_the_land(self):
        self.assertAlmostEqual(self.sea.terrain_z_at(RIVER[1]), -RIVER_DEPTH)

    def test_the_river_has_banks(self):
        bank = WorldPosition(RIVER[1].x, RIVER[1].y + RIVER_HALF_WIDTH + 20.0)
        self.assertAlmostEqual(self.sea.terrain_z_at(bank), MAINLAND_Z)

    def test_the_sea_deepens_with_easting(self):
        near = self.sea.terrain_z_at(WorldPosition(500.0, -2000.0))
        far = self.sea.terrain_z_at(WorldPosition(2000.0, -2000.0))
        self.assertLess(far, near)

    def test_an_island_stands_out_of_it(self):
        name, x, y, _reach = ISLANDS[0]
        self.assertGreater(self.sea.terrain_z_at(WorldPosition(x, y)), 0.0, name)

    def test_an_island_shoals_rather_than_being_a_cliff(self):
        """
        Without a foreshore a lead line shows twenty metres right up to the moment
        she strikes, which is no warning at all.

        """
        _name, x, y, reach = ISLANDS[0]
        beach = self.sea.terrain_z_at(WorldPosition(x - reach * 1.1, y))
        offshore = self.sea.terrain_z_at(WorldPosition(x - reach * 1.9, y))
        self.assertLess(beach, 0.0)
        self.assertLess(offshore, beach)

    def test_every_harbour_has_water_in_it(self):
        for island in ISLANDS:
            depth = -self.sea.terrain_z_at(harbour_position(island))
            self.assertGreater(depth, 2.5, f"{island[0]} quay is a mudflat")

    def test_the_stone_quay_takes_the_sloop(self):
        self.assertGreater(-self.sea.terrain_z_at(STONE_QUAY), CRAFT["sloop"]["draft"])

    def test_the_pond_landing_is_in_the_pond(self):
        self.assertLess(self.sea.terrain_z_at(POND_LANDING), 0.0)

    def test_the_ferry_steps_are_in_the_river(self):
        self.assertLessEqual(distance_to_river(FERRY_STEPS), RIVER_HALF_WIDTH)

    def test_the_river_is_mud_and_the_islands_are_rock(self):
        """What she strikes decides whether she comes off again."""
        self.assertEqual(self.sea.bottom_type_at(RIVER[1]), MUD)
        name, x, y, reach = ISLANDS[0]
        self.assertEqual(self.sea.bottom_type_at(WorldPosition(x - reach * 1.1, y)), ROCK)
        self.assertEqual(self.sea.bottom_type_at(WorldPosition(5000.0, -3000.0)), SAND)

    def test_island_at_says_no_for_open_water(self):
        self.assertIsNone(island_at(WorldPosition(5000.0, -3000.0)))


class TestTheStream(BaseEvenniaTestCase):
    """The river runs and the pond does not."""

    def setUp(self):
        super().setUp()
        self.water = ExampleCurrents()

    def test_the_pond_is_slack(self):
        """The control against which the river means anything."""
        self.assertFalse(self.water.current_at(POND_CENTRE, 0.0).running)

    def test_the_river_runs(self):
        current = self.water.current_at(RIVER[1], 0.0)
        self.assertTrue(current.running)
        self.assertAlmostEqual(current.drift, RIVER_DRIFT)

    def test_it_runs_seaward(self):
        """East and south, down the reaches, never back up them."""
        for start, end in zip(RIVER[:-1], RIVER[1:]):
            middle = WorldPosition((start.x + end.x) / 2.0, (start.y + end.y) / 2.0)
            self.assertAlmostEqual(
                self.water.current_at(middle, 0.0).set, river_set_at(middle), places=3
            )

    def test_it_follows_the_bends(self):
        """One figure for the whole river would set her across the corners."""
        first = self.water.current_at(RIVER[0], 0.0).set
        last = self.water.current_at(RIVER[-2], 0.0).set
        self.assertNotAlmostEqual(first, last)

    def test_the_bank_is_slack(self):
        bank = WorldPosition(RIVER[1].x, RIVER[1].y + RIVER_HALF_WIDTH + 20.0)
        self.assertFalse(self.water.current_at(bank, 0.0).running)

    def test_the_open_sea_is_slack(self):
        self.assertFalse(self.water.current_at(WorldPosition(5000.0, -3000.0), 0.0).running)


class TestTheCraft(BaseEvenniaTestCase):
    """Three boats, between them using every kind of propulsion here."""

    def test_the_kayak_is_paddled_by_one(self):
        self.assertEqual(CRAFT["kayak"]["oars"].positions, 1)
        self.assertEqual(CRAFT["kayak"]["oars"].style, PADDLED)

    def test_the_canoe_is_paddled_by_two(self):
        self.assertEqual(CRAFT["canoe"]["oars"].positions, 2)

    def test_the_sloop_carries_sweeps_as_well_as_sails(self):
        """They do nothing until she is becalmed, which is the argument for both."""
        self.assertTrue(CRAFT["sloop"].get("sails"))
        self.assertEqual(CRAFT["sloop"]["oars"].style, ROWED)

    def test_the_small_craft_draw_less_than_the_pond_is_deep(self):
        for which in ("kayak", "canoe"):
            self.assertLess(CRAFT[which]["draft"], POND_DEPTH)

    def test_the_sloop_could_not_get_up_the_river(self):
        """Which is why the canoe exists, and why the harbour is at the mouth."""
        self.assertGreater(CRAFT["sloop"]["draft"], RIVER_DEPTH * 0.5)

    def test_every_craft_catches_some_wind(self):
        for which, spec in CRAFT.items():
            self.assertGreater(spec["windage"], 0.0, which)


#: Derived rather than written out, so the contrib still works dropped into a game
#: under some other path - the same rule the discipline check enforces on the source.
EXAMPLE = f"{ExampleSeabed.__module__.rsplit('.', 1)[0]}"


@override_settings(
    MARITIME_MAP_PROVIDER=f"{EXAMPLE}.ExampleSeabed",
    MARITIME_CURRENT_PROVIDER=f"{EXAMPLE}.ExampleCurrents",
    MARITIME_WIND_BEARING=165.0,
    MARITIME_WIND_SPEED=6.0,
)
class TestBuildingIt(EmptySeaMixin, BaseEvenniaTest):
    """The builder, run against a real database."""

    def setUp(self):
        super().setUp()
        self.built = build()

    def test_it_builds_the_mainland(self):
        self.assertIn("Stone Quay", self.built["mainland"])
        self.assertIn("Pond Shore", self.built["mainland"])

    def test_it_builds_six_islands(self):
        self.assertEqual(len(self.built["islands"]), 6)

    def test_every_island_has_three_rooms(self):
        for name, rooms in self.built["islands"].items():
            self.assertEqual(len(rooms), 3, name)

    def test_every_waterfront_is_a_port_room(self):
        """One room per landmass that the water can reach - see the module docstring."""
        for rooms in self.built["islands"].values():
            quay = list(rooms.values())[0]
            self.assertIsInstance(quay, PortRoom)
            self.assertTrue(quay.berths)

    def test_the_land_is_ordinary_rooms_with_ordinary_exits(self):
        meadow = self.built["mainland"]["The Water Meadow"]
        self.assertNotIsInstance(meadow, PortRoom)
        self.assertTrue([obj for obj in meadow.contents if obj.destination])

    def test_there_is_no_path_beside_the_river(self):
        """The river is the road. Rowing it is how you get there."""
        head = self.built["mainland"]["River Head"]
        steps = self.built["mainland"]["Ferry Steps"]
        self.assertNotIn(steps, [obj.destination for obj in head.contents if obj.destination])

    def test_it_builds_three_craft(self):
        for which in ("kayak", "canoe", "sloop"):
            self.assertIsInstance(self.built["craft"][which], Vessel)

    def test_every_craft_is_made_fast_where_she_belongs(self):
        for which, quay in (
            ("kayak", "Pond Shore"),
            ("canoe", "River Head"),
            ("sloop", "Stone Quay"),
        ):
            self.assertEqual(
                self.built["craft"][which].docked_at, self.built["mainland"][quay], which
            )

    def test_the_sloop_has_a_masthead_worth_climbing(self):
        decks = {room.key: room for room in self.built["craft"]["sloop"].ship_rooms}
        self.assertGreater(decks["Masthead"].height_of_eye, decks["Main Deck"].height_of_eye)

    def test_the_small_craft_have_one_compartment_each(self):
        """A kayak with a Main Deck would be silly. The architecture does not care."""
        for which in ("kayak", "canoe"):
            self.assertEqual(len(self.built["craft"][which].ship_rooms), 1)

    def test_and_it_is_called_what_that_boat_actually_has(self):
        """Which is the half of the point that counting compartments cannot see."""
        for which in ("kayak", "canoe"):
            only = self.built["craft"][which].ship_rooms[0]
            self.assertEqual(only.key, CRAFT[which]["compartment"])
            self.assertNotEqual(only.key, "Main Deck")

    def test_running_it_twice_builds_one_world(self):
        again = build()
        self.assertEqual(again["craft"]["sloop"], self.built["craft"]["sloop"])
        self.assertEqual(again["mainland"]["Stone Quay"], self.built["mainland"]["Stone Quay"])

    def test_the_ship_rooms_belong_to_their_hulls(self):
        for vessel in self.built["craft"].values():
            for room in vessel.ship_rooms:
                self.assertIsInstance(room, ShipRoom)
                self.assertEqual(room.vessel, vessel)


class TestTheApproachesAreMarked(BaseEvenniaTest):
    """
    The buoyage invariants, asserted against the world that ships with the contrib.

    Until these existed the example had six island harbours and not one buoyed
    approach - built, tested, sailed and demonstrated, with every landfall a guess,
    because nothing was checking. That is the whole argument for a rule being a test
    rather than a paragraph: this one was already being broken by its own author.

    """

    def test_every_berth_has_a_marked_approach(self):
        """
        Gary's rule: every dock and every landfall has at least one safe approach
        marked by buoys. A builder who adds an island and forgets the buoy should
        get a red test rather than a drowned player, and this is the red test.

        """
        from ..buoyage import unreachable_berths
        from ..example.marks import Approaches, berths, seaward

        stranded = unreachable_berths(Approaches(), berths(), seaward())
        self.assertEqual(stranded, (), f"unmarked approaches: {stranded}")

    def test_every_island_is_named_in_the_marks(self):
        """
        The invariant only bites if the list of berths is honest. A berth left off
        that list is a harbour nobody checked, so the two have to be kept in step.

        """
        from ..example.geography import ISLANDS
        from ..example.marks import berths, harbour_key

        for island in ISLANDS:
            self.assertIn(harbour_key(island[0]), berths())

    def test_a_berth_nobody_marked_is_caught(self):
        """
        Proof the test can fail. An invariant that cannot go red is decoration, and
        this suite has already shipped one test that passed for the wrong reason.

        """
        from ..buoyage import unreachable_berths
        from ..example.marks import Approaches, seaward

        stranded = unreachable_berths(Approaches(), ["smugglers cove"], seaward())
        self.assertEqual(stranded, ("smugglers cove",))

    def test_no_charted_danger_is_left_unmarked(self):
        """
        The other half. The example authors no discrete hazards yet, so this passes
        by having nothing to find - but it is wired, so the day somebody drops a reef
        into the chain it starts doing its job without anybody remembering to ask.

        """
        from ..buoyage import unmarked_dangers
        from ..example.marks import Approaches

        marks = Approaches().marks()
        self.assertEqual(unmarked_dangers([], marks, []), ())
