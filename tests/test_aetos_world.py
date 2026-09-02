"""
Tests for the coast ashore: the town, the islands, the counters and the map.

Content is easy to test badly. Asserting that a room exists proves the builder ran, which
nobody doubted; what is worth pinning is the handful of claims the world would be broken
without, and every one of them is a claim about *coherence* rather than about content:

    every exit leads somewhere     an exit to nothing is a dead end nobody can see
    everywhere is reachable        an orphaned room is content nobody will ever find
    building twice changes nothing a build command that doubles a world is unusable
    piers stand in real water      a quay on dry land is a berth that grounds ships
    islands trade in real goods    a commodity the game lacks is a shop selling nothing
    counters are stocked           an empty shop is a room with a person standing in it

None of those care what the prose says, which is the point: the descriptions can be rewritten
freely and these still hold.
"""

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest, BaseEvenniaTestCase

from ..bathymetry import MaritimeMapProvider
from ..cargo import STANDARD_STOWAGE
from ..client import landmap
from ..discovery import Landmark
from ..example import aetos_world
from ..example.aetos_world import islands, stock, village
from ..position import WorldPosition


class Shelf(MaritimeMapProvider):
    """
    A coast that shelves like the real one, with islands where the manifest says.

    Notes:
        Stands in for the shipped bundle so these tests do not depend on twelve megabytes
        of soundings being present, and run in milliseconds. It shelves gently on purpose -
        that is the property the pier lengths are derived from, and a flat-bottomed stand-in
        would make every pier one step long and prove nothing.
    """

    ISLES = {mark["key"]: n for n, mark in enumerate(islands.ISLANDS)}

    def terrain_z_at(self, position):
        for key, index in self.ISLES.items():
            x = -1900.0
            y = 3800.0 + index * 1390.0
            away = ((position.x - x) ** 2 + (position.y - y) ** 2) ** 0.5
            if away < 400.0:
                return 12.0 - (away / 400.0) * 30.0
        # The mainland, shelving away to the west of the waterfront. Steep enough that
        # the authored pier lengths reach the depths they advertise - the first version of
        # this put every pier on dry land and failed the tests for the stand-in's reasons
        # rather than the world's.
        return (position.x - 2650.0) * 0.015 if position.x > 800.0 else -20.0

    def landmarks_near(self, position, reach):
        return tuple(
            Landmark(key=key, x=-1900.0, y=3800.0 + index * 1390.0, radius=400.0, height=12.0)
            for key, index in self.ISLES.items()
        )


class TestTheTownHangsTogether(BaseEvenniaTestCase):
    """Coherence, which is the only thing worth asserting about a hand-authored place."""

    def setUp(self):
        super().setUp()
        self.world = Shelf()
        self.rooms = village.rooms(self.world)
        self.paths = village.paths()
        self.keys = [room["key"] for room in self.rooms]

    def test_no_two_rooms_share_a_name(self):
        """The builder finds rooms by name, so two alike are one room with two descriptions."""
        self.assertEqual(len(self.keys), len(set(self.keys)))

    def test_every_exit_leads_to_a_room_that_exists(self):
        for start, end, _, _ in self.paths:
            self.assertIn(start, self.keys, f"an exit leaves {start!r}, which is not a room")
            self.assertIn(end, self.keys, f"an exit leads to {end!r}, which is not a room")

    def test_everywhere_can_be_walked_to_from_the_starting_room(self):
        """
        A room nothing connects to is content nobody will ever see, and the builder will
        make it happily for ever.

        """
        joined = {}
        for start, end, _, _ in self.paths:
            joined.setdefault(start, []).append(end)
            joined.setdefault(end, []).append(start)

        seen = {village.STARTING_ROOM}
        stack = [village.STARTING_ROOM]
        while stack:
            for onward in joined.get(stack.pop(), ()):
                if onward not in seen:
                    seen.add(onward)
                    stack.append(onward)
        self.assertEqual(sorted(seen), sorted(self.keys))

    def test_it_is_the_size_it_claims_to_be(self):
        self.assertGreaterEqual(len(self.rooms), 50)

    def test_buildings_are_entered_by_their_noun_and_left_by_out(self):
        """
        The house rule. North is a direction across open ground; it is not the act of
        opening a door, and an exit line reading "north, south and east" gives no hint that
        one of them is a building.

        """
        compass = {"north", "south", "east", "west", "up", "down", "in"}
        insides = {inside["key"] for inside in village.INTERIORS}
        for start, end, out, back in self.paths:
            if end in insides:
                self.assertNotIn(out, compass, f"{end!r} is entered by a compass direction")
                self.assertEqual(back, "out", f"{end!r} is not left by OUT")

    def test_every_room_has_something_to_read(self):
        for room in self.rooms:
            self.assertTrue(room["desc"].strip(), f"{room['key']!r} has no description")
            self.assertGreater(len(room["desc"]), 80, f"{room['key']!r} is barely described")


class TestThePiersStandInWater(BaseEvenniaTestCase):
    """A quay on dry land is a berth that grounds the ships it was built for."""

    def setUp(self):
        super().setUp()
        self.world = Shelf()

    def test_a_berth_never_advertises_water_it_does_not_have(self):
        """
        Authored, the Long Pier promised six metres and had five point eight-eight - which
        says nothing until a hull sits down on it. The depth is measured now, so this is a
        property rather than a number somebody kept up to date.

        """
        for pier in village.PIERS:
            berth = village.berth_for(pier, self.world)
            under = -self.world.terrain_z_at(berth.position)
            self.assertGreater(under, 0.0, f"{pier['key']} stands on dry ground")
            self.assertLessEqual(
                berth.max_draft, under, f"{pier['key']} offers more water than it has"
            )

    def test_and_leaves_something_under_the_keel(self):
        for pier in village.PIERS:
            berth = village.berth_for(pier, self.world)
            under = -self.world.terrain_z_at(berth.position)
            self.assertGreaterEqual(under - berth.max_draft, village.BERTH_CLEARANCE - 1e-6)

    def test_an_island_pier_reaches_water_deep_enough_to_lie_in(self):
        for island in islands.ISLANDS:
            mark = Landmark(
                key=island["key"],
                x=Shelf.ISLES[island["key"]] * 0.0 - 1900.0,
                y=3800.0 + Shelf.ISLES[island["key"]] * 1390.0,
                radius=400.0,
                height=12.0,
            )
            where = islands.landing_position(mark, self.world)
            self.assertGreaterEqual(
                -self.world.terrain_z_at(where),
                islands.LANDING_DEPTH - 0.5,
                f"{island['key']}'s pier head is in shoal water",
            )


class TestTheIslandsTradeInThingsThatExist(BaseEvenniaTestCase):
    """
    The first draft asked for hardwood, fish, cloth and copper. None is in the stowage
    table, so four islands looked perfectly configured and traded in nothing at all - which
    nobody discovers until a player tries to sell something.
    """

    def test_every_island_wants_and_offers_a_real_commodity(self):
        known = {item.key for item in STANDARD_STOWAGE}
        for island in islands.ISLANDS:
            self.assertIn(island["wants"], known, f"{island['key']} wants a cargo that is not")
            self.assertIn(island["offers"], known, f"{island['key']} offers a cargo that is not")

    def test_and_the_lookup_actually_finds_them(self):
        for island in islands.ISLANDS:
            wants, offers = islands.trade_at(island)
            self.assertIsNotNone(wants, island["key"])
            self.assertIsNotNone(offers, island["key"])

    def test_the_chain_is_a_round_rather_than_a_list(self):
        """
        Somebody's cargo has to be somebody else's want, or a captain can buy and never
        sell. Not every island need connect, but the chain must not be a dead end.

        """
        wanted = {island["wants"] for island in islands.ISLANDS}
        offered = {island["offers"] for island in islands.ISLANDS}
        self.assertTrue(wanted & offered, "nothing any island sells is wanted anywhere")


class TestEveryCounterIsStocked(BaseEvenniaTestCase):
    """An empty shop is a room with a person standing in it."""

    def test_six_to_ten_things_on_every_counter(self):
        for name, spec in stock.VILLAGE_VENDORS.items():
            self.assertGreaterEqual(len(spec["stock"]), 6, f"{name} keeps too little")
            self.assertLessEqual(len(spec["stock"]), 10, f"{name} keeps too much to read")

    def test_the_island_bars_too(self):
        self.assertGreaterEqual(len(stock.BAR_STOCK), 6)
        self.assertLessEqual(len(stock.BAR_STOCK), 10)

    def test_every_line_is_complete_and_costs_something(self):
        for name, spec in stock.VILLAGE_VENDORS.items():
            for line in spec["stock"]:
                self.assertEqual(len(line), 4, f"{name}: {line!r} is malformed")
                thing, price, kind, described = line
                self.assertTrue(thing.strip(), name)
                self.assertGreater(price, 0, f"{name} gives away {thing}")
                self.assertTrue(kind.strip(), f"{thing} has no kind")
                self.assertTrue(described.strip(), f"{thing} is not described")

    def test_a_bar_keeps_something_soft_as_well_as_something_strong(self):
        """
        The distinction the shore-leave factor rests on. A crew let ashore for lemonade is
        still a crew let ashore, and a bar with only rum in it quietly makes that untrue.

        """
        kinds = {line[2] for line in stock.BAR_STOCK}
        self.assertIn("soft", kinds)
        self.assertIn("strong", kinds)

    def test_every_shop_room_named_has_somebody_in_it(self):
        rooms = {room["key"] for room in village.rooms()}
        for name in stock.VILLAGE_VENDORS:
            self.assertIn(name, rooms, f"{name} has a keeper but is not a room")


class TestTheMapAshore(BaseEvenniaTest):
    """
    The map is a walk, so what is worth testing is that the walk is honest: it draws what
    is really joined, it does not stack two rooms on one spot, and it draws the same picture
    twice.
    """

    def setUp(self):
        super().setUp()
        self.hall = create.create_object("evennia.objects.objects.DefaultRoom", key="A Hall")
        self.lane = create.create_object("evennia.objects.objects.DefaultRoom", key="A Lane")
        self.shed = create.create_object("evennia.objects.objects.DefaultRoom", key="A Shed")
        for source, target, key in (
            (self.hall, self.lane, "north"),
            (self.lane, self.hall, "south"),
            (self.lane, self.shed, "shed"),
            (self.shed, self.lane, "out"),
        ):
            create.create_object(
                "evennia.objects.objects.DefaultExit",
                key=key,
                location=source,
                destination=target,
            )
        self.char1.location = self.hall

    def test_it_draws_what_is_joined_and_nothing_else(self):
        sheet = landmap.sheet_for(self.char1)
        self.assertEqual(
            sorted(room["name"] for room in sheet["rooms"]), ["A Hall", "A Lane", "A Shed"]
        )

    def test_no_two_rooms_land_on_one_spot(self):
        """Two rooms drawn on one square is one room lost, silently."""
        sheet = landmap.sheet_for(self.char1)
        spots = [(room["x"], room["y"]) for room in sheet["rooms"]]
        self.assertEqual(len(spots), len(set(spots)))

    def test_north_goes_up(self):
        sheet = landmap.sheet_for(self.char1)
        where = {room["name"]: (room["x"], room["y"]) for room in sheet["rooms"]}
        self.assertGreater(where["A Lane"][1], where["A Hall"][1])

    def test_a_door_puts_its_room_beside_its_parent(self):
        """
        A door does not move you across a town. Drawing `shed` as though it were a compass
        direction would put the inside of a building a street away from its own front.

        """
        sheet = landmap.sheet_for(self.char1)
        where = {room["name"]: (room["x"], room["y"]) for room in sheet["rooms"]}
        lane, shed = where["A Lane"], where["A Shed"]
        self.assertLessEqual(abs(lane[0] - shed[0]) + abs(lane[1] - shed[1]), 2)

    def test_the_same_place_draws_the_same_map_twice(self):
        """
        Exits come back from the database in no guaranteed order, so a map that did not
        sort them would shuffle under the player for no reason they could see.

        """
        self.assertEqual(landmap.sheet_for(self.char1), landmap.sheet_for(self.char1))

    def test_the_player_is_marked_and_is_the_only_one(self):
        sheet = landmap.sheet_for(self.char1)
        here = [room for room in sheet["rooms"] if room["marker"] == landmap.HERE]
        self.assertEqual(len(here), 1)
        self.assertEqual(here[0]["name"], "A Hall")

    def test_somewhere_selling_is_marked_as_such(self):
        seller = create.create_object(
            "evennia.objects.objects.DefaultObject", key="a stallholder", location=self.shed
        )
        seller.db.stock = [["a fish", 2, "food", "It is a fish."]]
        marks = {room["name"]: room["marker"] for room in landmap.sheet_for(self.char1)["rooms"]}
        self.assertEqual(marks["A Shed"], landmap.TRADE)

    def test_a_room_leading_off_the_map_says_so(self):
        """
        Otherwise the edge of the drawing reads as the edge of the world, and a player
        looking at a road that simply stops assumes there is nothing along it.

        """
        beyond = create.create_object("evennia.objects.objects.DefaultRoom", key="Away")
        create.create_object(
            "evennia.objects.objects.DefaultExit",
            key="east",
            location=self.shed,
            destination=beyond,
        )
        sheet = landmap.sheet_for(self.char1, reach=2)
        marks = {room["name"]: room["marker"] for room in sheet["rooms"]}
        self.assertNotIn("Away", marks, "the map drew past its own edge")
        self.assertEqual(marks.get("A Shed"), landmap.WAY_OUT)

    def test_standing_nowhere_maps_nothing_rather_than_failing(self):
        self.char1.location = None
        self.assertEqual(landmap.sheet_for(self.char1)["rooms"], [])


class TestTheWholeTownDrawsWithNothingStranded(BaseEvenniaTest):
    """
    **A dot on its own in a field reads as a mistake in the map.**

    The client draws only lines a player could walk in one go: anything longer crosses four
    other streets and reads as a bridge through the air, so it is suppressed. That rule is
    safe only if the layout puts every room within one move of something. A room it strands
    is one the client is not allowed to draw a line to, and it appears as a dot in open
    ground - clickable, walkable, and looking broken.

    Asserted against the whole built town rather than a hand-made grid, because a grid never
    runs out of room and so never fails. What actually strands a room is a real street plan:
    lanes arriving at one ridge from two directions, shops entered by their own noun, and a
    dead end whose only neighbour is already surrounded on every side.
    """

    def setUp(self):
        super().setUp()
        aetos_world.build(world=Shelf())
        self.char1.location = aetos_world.starting_room()

    def drawn_sheet(self):
        """
        Returns:
            sheet (dict): The town as the client would receive it.

        """
        sheet = landmap.sheet_for(self.char1)
        self.assertGreaterEqual(len(sheet["rooms"]), 50, "the map did not draw the town")
        return sheet

    def test_no_room_is_drawn_with_nothing_joined_to_it(self):
        sheet = self.drawn_sheet()
        at = {room["id"]: room for room in sheet["rooms"]}
        near = set()
        for edge in sheet["edges"]:
            first, second = at.get(edge["from"]), at.get(edge["to"])
            if not first or not second:
                continue
            if max(abs(first["x"] - second["x"]), abs(first["y"] - second["y"])) <= landmap.STREET:
                near.add(edge["from"])
                near.add(edge["to"])

        stranded = sorted(room["name"] for room in sheet["rooms"] if room["id"] not in near)
        self.assertEqual(
            stranded, [], "these rooms are drawn with no line the client is allowed to draw"
        )

    def test_no_two_rooms_land_on_one_spot(self):
        """Two rooms drawn on one square is one room lost, and nothing anywhere says so."""
        spots = [(room["x"], room["y"]) for room in self.drawn_sheet()["rooms"]]
        self.assertEqual(len(spots), len(set(spots)))


class TestTheReadmeCountsTheWorldItActuallyBuilds(BaseEvenniaTestCase):
    """
    **The readme is the public documentation page**, generated from this file, and the size
    of the world is the first concrete thing it tells anybody. A number that drifts as the
    town grows is a number a reader cannot trust, and there is nothing in a build log to
    catch it - the builder reports what it made and the readme reports what it used to.

    Counted from the authored data rather than by building, so it costs nothing and answers
    the same question: two exits per join, one room per spec.
    """

    def setUp(self):
        super().setUp()
        world = Shelf()
        self.rooms = len(village.rooms(world))
        self.joins = len(village.paths())
        marks = {mark.key: mark for mark in world.landmarks_near(WorldPosition(0.0, 0.0, 0.0), 1e9)}
        for island in islands.ISLANDS:
            mark = marks.get(island["key"])
            if mark is None:
                continue
            self.rooms += len(islands.rooms_for(island, mark, world))
            self.joins += len(islands.paths_for(island))

    def claimed(self):
        """
        Returns:
            said (tuple): The `(rooms, exits)` the readme states.

        """
        import re
        from pathlib import Path

        readme = Path(__file__).resolve().parent.parent / "README.md"
        found = re.search(
            r"builds Careenage and the six islands: (\d+) rooms, (\d+) exits",
            readme.read_text(encoding="utf-8"),
        )
        self.assertIsNotNone(found, "the readme no longer states the size of the world")
        return int(found.group(1)), int(found.group(2))

    def test_the_room_count_is_the_one_it_builds(self):
        self.assertEqual(self.claimed()[0], self.rooms)

    def test_the_exit_count_is_the_one_it_builds(self):
        """Two per join: a way there and a way back. A one-way street would be a bug."""
        self.assertEqual(self.claimed()[1], self.joins * 2)


class TestTheAshorePanelIsOffByDefault(BaseEvenniaTest):
    """
    The rule the resolver states at the top of itself: the failure a player notices is a
    maritime interface turning up in a tavern, and the safe answer is to leave the host
    game's own interface alone.
    """

    def setUp(self):
        super().setUp()
        from ..client import context

        self.context = context
        from ..ports import Berth
        from ..rooms import PortRoom

        self.quay = create.create_object(PortRoom, key="A Quay")

        self.quay.maritime_position = WorldPosition(0.0, 0.0)
        self.quay.add_berth(Berth(key="one", position=WorldPosition(0.0, 0.0)))
        self.char1.location = self.quay

    def test_a_game_that_says_nothing_gets_its_own_interface_back(self):
        """
        Pinned off rather than left to the settings in force. A game that has turned the
        panel on - as the demonstration game does - would otherwise make this test assert
        that game's preference instead of the contrib's default, and it would pass or fail
        depending on whose settings file it ran under.

        """
        from django.test import override_settings

        with override_settings(MARITIME_ASHORE_PANEL=False):
            self.assertEqual(
                self.context.resolve_maritime_ui_context(self.char1), self.context.NONE
            )

    def test_a_game_that_asks_for_it_gets_the_land_map(self):
        from django.test import override_settings

        with override_settings(MARITIME_ASHORE_PANEL=True):
            self.assertEqual(
                self.context.resolve_maritime_ui_context(self.char1), self.context.ASHORE
            )

    def test_a_room_with_berths_is_ashore_without_being_told(self):
        self.assertTrue(self.context.is_ashore(self.quay))

    def test_an_ordinary_room_inland_is_not(self):
        """A tavern forty miles from the sea does not get a harbour interface for being a
        tavern."""
        self.assertFalse(self.context.is_ashore(self.room1))


class TestTheWiringIsActuallyConnected(BaseEvenniaTestCase):
    """
    The gap this class exists for: four things were written and none was wired.

    `browse` and `buy` were in no cmdset, so nothing could reach them. Nothing redrew the
    land map when somebody walked, so it drew the first room a player entered and kept
    drawing it while they walked away. `STARTING_ROOM` and `trade_at` were read by nothing
    but their own tests.

    The redrawing is now `refresh`'s own business and is tested in `test_client_protocol`,
    where there are sessions to send to. The function that used to do it here was called by
    nothing at all, which is the same disease as the rest of this list.

    Every one of them looked finished. That is the point - a thing that is defined and never
    called passes every test written about the definition, and the world it was written for
    behaves as though it does not exist. So these tests assert that the *call sites* are
    there, which is the half that was missing.
    """

    def test_the_ashore_commands_are_in_a_cmdset(self):
        from ..example.aetos_world.typeclasses import AshoreCmdSet

        cmdset = AshoreCmdSet()
        cmdset.at_cmdset_creation()
        keys = {command.key for command in cmdset.commands}
        self.assertEqual(keys, {"browse", "buy", "market", "sell"})

    def test_a_shore_room_carries_that_cmdset(self):
        """
        A command in a cmdset nothing installs is a command nobody can type. The rooms
        install it themselves, so a game that builds this world gets working shops without
        having to add anything to its own character cmdset.

        """
        import inspect

        from ..example.aetos_world import typeclasses

        source = inspect.getsource(typeclasses.ShoreStreet)
        self.assertIn("AshoreCmdSet", source)

    def test_land_rooms_are_built_as_shore_rooms(self):
        """
        The builder made plain `DefaultRoom`s, so nothing above applied to a single room in
        the world it built.

        """
        from ..example import aetos_world

        self.assertIn("ShoreStreet", aetos_world.LAND_ROOM)

    def test_the_starting_room_can_be_found_rather_than_only_named(self):
        from ..example import aetos_world

        self.assertTrue(callable(aetos_world.starting_room))

    def test_selling_cargo_reads_the_island_the_pier_belongs_to(self):
        """
        `trade_at` existed and nothing called it, so every island's authored trade was
        decoration. The selling command is what makes it a fact about the world.

        """
        import inspect

        from ..example.aetos_world import commands

        source = inspect.getsource(commands.CmdSellCargo)
        self.assertIn("trade_at", source)

    def test_an_island_pays_more_than_it_charges(self):
        """Otherwise there is no reason to carry anything anywhere."""
        from ..example.aetos_world import commands

        self.assertGreater(commands.PAID_PER_TONNE, commands.CHARGED_PER_TONNE)
