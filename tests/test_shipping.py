"""
Tests for who else is out there, and why.

Two claims. **The traffic is explained rather than scattered** - nobody authored a shipping
lane, and changing what a place exports changes who sails past it. And **a raider hunts
value, not traffic**, which is what makes choosing a cargo a choice about danger.

"""

from evennia.utils.test_resources import BaseEvenniaTestCase

from ..economy import WORTH, Market
from ..position import WorldPosition
from ..shipping import (
    KINDS,
    MERCHANT,
    NO_MARKETS,
    NO_TRADE,
    PATROL,
    RAIDER,
    SPEEDS,
    WORTH_NOTICING,
    Anchorage,
    a_fisherman_off,
    a_merchant_on,
    a_patrol_between,
    a_raider_on,
    danger_on,
    encounters,
    populate,
    richest_route,
    routes_worth_sailing,
)
from ..strategic import Fleet, along

HARROWMOUTH = Anchorage(
    key="Harrowmouth",
    position=WorldPosition(0.0, 0.0),
    market=Market(key="Harrowmouth", exports=("grain", "hay"), imports=("wine", "iron")),
)
CAREENAGE = Anchorage(
    key="Careenage",
    position=WorldPosition(60_000.0, 0.0),
    market=Market(key="Careenage", exports=("wine", "iron"), imports=("grain", "hay")),
)
COAST = (HARROWMOUTH, CAREENAGE)


class TestTheLanesDrawThemselves(BaseEvenniaTestCase):
    """A lane is what the ports are."""

    def test_two_places_that_want_each_other_make_routes(self):
        self.assertTrue(routes_worth_sailing(COAST))

    def test_a_place_on_its_own_makes_none(self):
        self.assertEqual(routes_worth_sailing((HARROWMOUTH,)), ())

    def test_places_with_no_markets_make_none(self):
        bare = Anchorage(key="Nowhere", position=WorldPosition(0.0, 0.0))
        self.assertEqual(routes_worth_sailing((bare, bare)), ())

    def test_grain_goes_from_the_coast_to_the_city(self):
        grain = [one for one in routes_worth_sailing(COAST) if one.commodity == "grain"]
        self.assertTrue(grain)
        self.assertIs(grain[0].origin, HARROWMOUTH)
        self.assertIs(grain[0].destination, CAREENAGE)

    def test_and_wine_the_other_way(self):
        wine = [one for one in routes_worth_sailing(COAST) if one.commodity == "wine"]
        self.assertTrue(wine)
        self.assertIs(wine[0].origin, CAREENAGE)
        self.assertIs(wine[0].destination, HARROWMOUTH)

    def test_nothing_is_carried_to_where_it_is_worth_less(self):
        for route in routes_worth_sailing(COAST):
            self.assertGreater(route.margin, 0, route.commodity)

    def test_they_come_back_richest_first(self):
        margins = [route.margin for route in routes_worth_sailing(COAST)]
        self.assertEqual(margins, sorted(margins, reverse=True))

    def test_changing_what_a_place_exports_changes_the_traffic(self):
        """
        The whole point of deriving the lanes. A builder who makes a mining port stops
        seeing grain ships without editing a table of routes.

        """
        before = {route.commodity for route in routes_worth_sailing(COAST)}
        mining = Anchorage(
            key="Harrowmouth",
            position=HARROWMOUTH.position,
            market=Market(key="Harrowmouth", exports=("iron",), imports=("grain",)),
        )
        after = {route.commodity for route in routes_worth_sailing((mining, CAREENAGE))}
        self.assertNotEqual(before, after)

    def test_a_commodity_nobody_prices_carries_nothing(self):
        odd = Anchorage(
            key="Odd",
            position=WorldPosition(0.0, 5000.0),
            market=Market(key="Odd", exports=("moonlight",), imports=("grain",)),
        )
        carried = {route.commodity for route in routes_worth_sailing((odd, CAREENAGE))}
        self.assertNotIn("moonlight", carried)


class TestWhoIsSailing(BaseEvenniaTestCase):
    """Every one of them is a record and a route."""

    def setUp(self):
        super().setUp()
        self.lanes = routes_worth_sailing(COAST)

    def test_a_merchant_is_on_a_real_passage(self):
        trader = a_merchant_on(self.lanes[0], "a trader")
        self.assertEqual(len(trader.passage.route.waypoints), 2)

    def test_and_carries_what_the_lane_is_for(self):
        lane = self.lanes[0]
        trader = a_merchant_on(lane, "a trader")
        self.assertEqual(trader.cargo[0][0], lane.commodity)

    def test_a_fisherman_goes_out_and_comes_home(self):
        boat = a_fisherman_off(HARROWMOUTH, "a boat")
        marks = boat.passage.route.waypoints
        self.assertEqual(marks[0].position, marks[-1].position)

    def test_and_works_off_her_own_coast(self):
        boat = a_fisherman_off(HARROWMOUTH, "a boat")
        out = boat.passage.route.waypoints[1].position
        self.assertLess(HARROWMOUTH.position.horizontal_distance_to(out), 30_000.0)

    def test_a_patrol_works_a_beat_that_closes(self):
        """
        A beat that did not close would be a ship leaving the station she was put there to
        keep.

        """
        beat = a_patrol_between(COAST, "a patrol")
        marks = beat.passage.route.waypoints
        self.assertEqual(marks[0].position, marks[-1].position)

    def test_one_place_is_not_a_beat(self):
        self.assertIsNone(a_patrol_between((HARROWMOUTH,), "a patrol"))

    def test_a_patrol_is_faster_than_the_trade(self):
        """
        A merchant who could outrun a raider would never meet one, and a patrol that could
        not catch anybody would not be worth having.

        """
        self.assertGreater(SPEEDS[PATROL], SPEEDS[MERCHANT])
        self.assertGreater(SPEEDS[RAIDER], SPEEDS[MERCHANT])

    def test_every_kind_has_a_speed(self):
        self.assertEqual(set(SPEEDS), set(KINDS))


class TestARaiderHuntsValue(BaseEvenniaTestCase):
    """The side of the decision where it costs something."""

    def setUp(self):
        super().setUp()
        self.lanes = routes_worth_sailing(COAST)

    def test_the_richest_route_is_the_one_carrying_the_most(self):
        best = richest_route(self.lanes)
        for route in self.lanes:
            self.assertGreaterEqual(best.margin, route.margin)

    def test_nothing_to_hunt_is_nothing_to_hunt(self):
        self.assertIsNone(richest_route(()))

    def test_a_raider_works_the_route_rather_than_sitting_on_a_harbour_mouth(self):
        """
        A raider parked on a harbour mouth is a blockade, and a blockade is a different
        thing.

        """
        raider = a_raider_on(self.lanes[0], "a raider")
        self.assertGreater(len(raider.passage.route.waypoints), 2)

    def test_the_danger_on_a_route_is_what_is_carried_along_it(self):
        wine = [one for one in self.lanes if one.commodity == "wine"][0]
        hay = [one for one in self.lanes if one.commodity == "hay"][0]
        self.assertGreater(danger_on(wine), danger_on(hay))

    def test_which_is_the_standing_worth_of_the_cargo(self):
        wine = [one for one in self.lanes if one.commodity == "wine"][0]
        self.assertEqual(danger_on(wine), WORTH["wine"])

    def test_a_captain_choosing_a_rich_cargo_has_chosen_a_dangerous_passage(self):
        """
        Nobody tells him. It falls out of the raider going where the money is, which is the
        same place his money is.

        """
        fleet = Fleet()
        populate(fleet, COAST, merchants=0, fishermen=0, patrols=0, raiders=1)
        raider = fleet.get(fleet.records()[0][0])
        hunted = {mark.key for mark in raider.passage.route.waypoints}
        best = richest_route(self.lanes)
        self.assertIn(best.origin.key, hunted)
        self.assertIn(best.destination.key, hunted)


class TestFillingTheSea(BaseEvenniaTestCase):
    """A hundred of them cost what one costs to advance."""

    def setUp(self):
        super().setUp()
        self.fleet = Fleet()

    def test_nowhere_to_sail_from_is_a_failure(self):
        self.assertEqual(populate(self.fleet, ()).code, NO_MARKETS)

    def test_nor_can_merchants_sail_where_there_is_no_trade(self):
        bare = Anchorage(key="Nowhere", position=WorldPosition(0.0, 0.0))
        self.assertEqual(populate(self.fleet, (bare,)).code, NO_TRADE)

    def test_a_coast_gets_a_sea_full_of_ships(self):
        result = populate(self.fleet, COAST)
        self.assertTrue(result)
        self.assertGreater(len(self.fleet), 0)

    def test_and_one_of_each_kind(self):
        result = populate(self.fleet, COAST)
        for kind in KINDS:
            self.assertTrue(result.put_out[kind], kind)

    def test_as_many_as_were_asked_for(self):
        populate(self.fleet, COAST, merchants=3, fishermen=2, patrols=1, raiders=1)
        self.assertEqual(len(self.fleet), 7)

    def test_they_are_all_somewhere(self):
        populate(self.fleet, COAST)
        for fix in self.fleet.fixes(now=1000.0).values():
            self.assertIsNotNone(fix.position)

    def test_and_they_get_somewhere_else(self):
        populate(self.fleet, COAST)
        early = self.fleet.fixes(now=100.0)
        later = self.fleet.fixes(now=10_000.0)
        moved = [handle for handle in early if early[handle].position != later[handle].position]
        self.assertTrue(moved)

    def test_the_same_world_built_twice_is_the_same_world(self):
        """
        Departures are staggered by index rather than rolled. A background fleet that
        shuffled itself on every restart would make a bug in it impossible to reproduce.

        """
        second = Fleet()
        populate(self.fleet, COAST)
        populate(second, COAST)
        mine = [record.passage.departed for _, record in self.fleet.records()]
        theirs = [record.passage.departed for _, record in second.records()]
        self.assertEqual(mine, theirs)

    def test_a_fleet_of_a_thousand_is_still_one_pass(self):
        populate(self.fleet, COAST, merchants=500, fishermen=500, patrols=0, raiders=0)
        self.assertEqual(len(self.fleet.fixes(now=5000.0)), 1000)


class TestWhoIsInTheOffing(BaseEvenniaTestCase):
    """Says who is out there. Materialising anybody is the game's."""

    def setUp(self):
        super().setUp()
        self.fleet = Fleet()
        populate(self.fleet, COAST)

    def test_nowhere_sees_nobody(self):
        self.assertEqual(encounters(self.fleet, None, now=0.0), ())

    def test_somebody_is_off_the_harbour_at_the_start(self):
        near = encounters(self.fleet, HARROWMOUTH.position, now=0.0)
        self.assertTrue(near)

    def test_an_empty_stretch_of_sea_has_nobody_in_it(self):
        empty = WorldPosition(0.0, 900_000.0)
        self.assertEqual(encounters(self.fleet, empty, now=0.0), ())

    def test_they_come_back_nearest_first(self):
        near = encounters(self.fleet, HARROWMOUTH.position, now=3000.0)
        ranges = [seen.distance for seen in near]
        self.assertEqual(ranges, sorted(ranges))

    def test_nobody_further_off_than_asked_for(self):
        near = encounters(self.fleet, HARROWMOUTH.position, now=3000.0, within=5000.0)
        for seen in near:
            self.assertLessEqual(seen.distance, 5000.0)

    def test_looking_further_finds_more(self):
        close = encounters(self.fleet, HARROWMOUTH.position, now=3000.0, within=5000.0)
        wide = encounters(self.fleet, HARROWMOUTH.position, now=3000.0, within=WORTH_NOTICING)
        self.assertGreaterEqual(len(wide), len(close))

    def test_an_encounter_carries_who_she_is_and_where(self):
        seen = encounters(self.fleet, HARROWMOUTH.position, now=0.0)[0]
        self.assertIsNotNone(seen.record)
        self.assertIsNotNone(seen.fix.position)

    def test_and_the_fix_is_the_one_the_fleet_would_give(self):
        seen = encounters(self.fleet, HARROWMOUTH.position, now=2000.0)[0]
        self.assertEqual(seen.fix.position, along(seen.record.passage, now=2000.0).position)

    def test_nothing_was_materialised(self):
        """
        Only a game knows whether its players are in a state to be interrupted by a strange
        sail, so this reports and stops.

        """
        from evennia.objects.models import ObjectDB

        before = ObjectDB.objects.count()
        encounters(self.fleet, HARROWMOUTH.position, now=0.0)
        self.assertEqual(ObjectDB.objects.count(), before)
