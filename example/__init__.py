"""
A small working world, so that installing this contrib ends in sailing rather than reading.

Three modules, because they are three things a game replaces separately:

    geography   the ground, the river, the pond and the islands
    craft       a kayak, a canoe and a sloop
    world       the rooms that stand on it, and the command that builds them

Point two settings at this package, reload, and run `example` as a builder:

    ```python
    # in mygame/server/conf/settings.py
    MARITIME_MAP_PROVIDER = "evennia.contrib.full_systems.maritime.example.ExampleSeabed"
    MARITIME_CURRENT_PROVIDER = "evennia.contrib.full_systems.maritime.example.ExampleCurrents"
    MARITIME_WIND_BEARING = 165.0
    MARITIME_WIND_SPEED = 6.0
    ```

Everything in here is ordinary use of the public API. There is no private machinery, so a
game can read `world.py` as the shortest honest answer to "how do I build a ship".

"""

from .craft import (
    CRAFT,
    CRUISING_SPEED,
    EXAMPLE_WIND_BEARING,
    EXAMPLE_WIND_SPEED,
    outfit,
)
from .geography import (
    ISLANDS,
    POND_CENTRE,
    POND_RADIUS,
    RIVER,
    RIVER_DRIFT,
    RIVER_HALF_WIDTH,
    ExampleCurrents,
    ExampleSeabed,
    ExampleTile,
    ExampleTiles,
    distance_to_river,
    harbour_position,
    island_at,
    nearest_island,
    river_set_at,
)
from .commands import CmdMaritimeExample, report
from .world import FERRY_STEPS, MAINLAND, POND_LANDING, STONE_QUAY, build

__all__ = (
    # geography
    "ExampleSeabed",
    "ExampleCurrents",
    "ExampleTile",
    "ExampleTiles",
    "ISLANDS",
    "RIVER",
    "RIVER_DRIFT",
    "RIVER_HALF_WIDTH",
    "POND_CENTRE",
    "POND_RADIUS",
    "distance_to_river",
    "river_set_at",
    "island_at",
    "nearest_island",
    "harbour_position",
    # craft
    "CRAFT",
    "CRUISING_SPEED",
    "EXAMPLE_WIND_BEARING",
    "EXAMPLE_WIND_SPEED",
    "outfit",
    # the world
    "build",
    "CmdMaritimeExample",
    "report",
    "MAINLAND",
    "STONE_QUAY",
    "FERRY_STEPS",
    "POND_LANDING",
)
