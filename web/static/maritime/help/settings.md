# Every setting

[Back to the handbook](index.md) / [For developers](for-developers.md)

All of them go in `server/conf/settings.py`, all of them are optional, and each one is
independent of the rest. Grouped by what you would be trying to do.

---

## Getting started

Nothing here is required. With none of it you get a flat, still, windless sea two hundred metres deep, which is a legitimate world and a dull one.

| Setting | Default | Meaning |
| --- | --- | --- |
| `MARITIME_ASHORE_PANEL` | `False` | Keep the panel up on land, showing a room map instead of a chart |
| `MARITIME_TIME_PROVIDER` | the game's own clock | Dotted path to a time provider |
| `MARITIME_RNG_SEED` | unset | Pin the master seed to make a run reproducible |

---

## The ground

What is under her, and whether it moves.

| Setting | Default | Meaning |
| --- | --- | --- |
| `MARITIME_MAP_PROVIDER` | flat sea | Dotted path to the game's bathymetry - a `TiledMapProvider` subclass for an authored seabed |
| `MARITIME_DEFAULT_DEPTH` | `200.0` | Depth of the default flat sea, in metres |
| `MARITIME_TIDE_PROVIDER` | a motionless sea | Dotted path to the game's tide - `HarmonicTide` for a real one |
| `MARITIME_SOUNDING_CACHE` | `300000` | How many soundings of the seabed to remember, about 50 MB |
| `MARITIME_WORLD_BUNDLE` | unset | Directory of baked soundings for `BakedMapProvider` |
| `MARITIME_BAKE_DIR` | unset | Where to write and read soundings baked at startup |
| `MARITIME_BAKE_AREA` | unset | `(west, south, east, north)` in metres, to bake at startup |
| `MARITIME_BAKE_SCALES` | unset | Which zoom reaches to pre-sound |

---

## The weather and the water

One provider supplies wind, visibility and sea state together, deliberately: a game where the wind is a gale and the sea is glass is a game with a bug in it.

| Setting | Default | Meaning |
| --- | --- | --- |
| `MARITIME_WEATHER_PROVIDER` | from the settings below | Dotted path to the game's weather |
| `MARITIME_WIND_BEARING` | `0.0` | Bearing the wind blows *from* |
| `MARITIME_WIND_SPEED` | `0.0` | Wind speed in metres per second |
| `MARITIME_SEA_STATE` | follows the wind | Override the sea the wind would raise |
| `MARITIME_VISIBILITY` | 30 miles | How far the air lets you see, in metres |
| `MARITIME_CURRENT_PROVIDER` | slack water | Dotted path, for a tidal stream |
| `MARITIME_CURRENT_SET` | `0.0` | Bearing the water flows *towards* |
| `MARITIME_CURRENT_DRIFT` | `0.0` | How fast it flows, in metres per second |

---

## Where the world is

The world is a plane in metres; these place it on a globe so that `position` reads as latitude and longitude.

| Setting | Default | Meaning |
| --- | --- | --- |
| `MARITIME_ORIGIN_NORTHING` | `0.0` | Places the world's origin on the globe |
| `MARITIME_ORIGIN_EASTING` | `0.0` | As above, for longitude |
| `MARITIME_POSITION_STYLE` | `nautical` | `nautical` or `raw` |
| `MARITIME_NAVIGATION_NETWORK` | no marks | Dotted path to the game's marks and channels |

---

## How things are said

Units, and the voice the ship speaks in.

| Setting | Default | Meaning |
| --- | --- | --- |
| `MARITIME_DISTANCE_UNITS` | `leagues` | `leagues`, `nautical`, `metric` or `raw` |
| `MARITIME_DEPTH_UNITS` | `fathoms` | `fathoms`, `metres` or `raw` |
| `MARITIME_NARRATOR` | the one here | Dotted path to a `VesselNarrator` subclass |
| `MARITIME_WATER_NARRATOR` | the one here | Dotted path to a `WaterNarrator` subclass |

---

## Your game's own rules

The seams where your answers go. See [hooking into it](extending.md).

| Setting | Default | Meaning |
| --- | --- | --- |
| `MARITIME_COMMAND_POLICY` | captain, else owner, else anybody aboard an unowned ship | Dotted path to `(character, vessel) -> bool` |
| `MARITIME_COMMODITIES` | a standard stowage table | The cargoes this game trades in |

---

## Open water and performance

Only relevant once somebody goes over the side, or once you have a fleet.

| Setting | Default | Meaning |
| --- | --- | --- |
| `MARITIME_CELL_SIZE` | `100.0` | How wide a projected square of open water is, in metres |
| `MARITIME_OCEAN_ROOM_TYPECLASS` | `OceanRoom` | Dotted path to the class pool rooms are built from |
| `MARITIME_TICK_BUDGET_MS` | `10.0` | How long one simulation pass may hold the reactor; 0 disables the limit |

---

## One more, which is not ours

```python
WEBSERVER_HOSTNAME = "https://yourgame.example"
```

Not an Evennia setting and not required. If you set it, `maritime help` can give players
a full clickable address for this handbook instead of a path. Without it they are told
the path and where to put it, because guessing a hostname would hand every player on a
live server an address that works only for the person running it.

---

Next: **[Every command](commands.md)**.
