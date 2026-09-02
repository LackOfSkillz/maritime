# Your own coast

[Back to the handbook](index.md) · [For developers](for-developers.md)

The default sea is flat, still, windless and two hundred metres deep everywhere. That is a
legitimate world — a ferry needs nothing more — and a dull one. This is how to replace each
part of it, one at a time.

**Every provider is optional and independent.** Supplying a seabed does not oblige you to
supply weather. Call sites do not change when you add one.

---

## The seabed

One method. Everything else — depth, clearance, whether she grounds — is derived from it
plus the tide, so a game cannot produce a depth that disagrees with its own ground.

```python
# world/sea.py
from evennia.contrib.full_systems.maritime.bathymetry import MaritimeMapProvider


class MyCoast(MaritimeMapProvider):
    """Deep water, with a bank running north and south at x = 400."""

    def terrain_z_at(self, position):
        """
        Args:
            position (WorldPosition): Where to sound.

        Returns:
            z (float): Height of the ground, negative below the surface.

        """
        if 380.0 < position.x < 420.0:
            return -1.5
        return -60.0
```

```python
MARITIME_MAP_PROVIDER = "world.sea.MyCoast"
```

That is a working coast. She will now ground on that bank, the leadsman will call the water
shoaling before she reaches it, and the sailing master will refuse to take her over it.

**What the bottom is made of** decides whether a grounding is survivable — sand and mud give
her back on the tide, rock does not:

```python
    def bottom_type_at(self, position):
        from evennia.contrib.full_systems.maritime.bathymetry import ROCK, SAND
        return ROCK if abs(position.x - 400.0) < 5.0 else SAND
```

**Landmarks** are what `fix` takes bearings on and what a lookout raises:

```python
    def landmarks_near(self, position, reach):
        ...
```

### An authored seabed

For anything bigger than a test, subclass `TiledMapProvider` instead and author the ground
as tiles with hazards on them. A hazard has a radius and is tested against the whole
corridor a hull sweeps, rather than sampled — so a ship cannot step over a rock between two
ticks.

---

## The weather

```python
from evennia.contrib.full_systems.maritime.weather import WeatherProvider


class MyWeather(WeatherProvider):
    def weather_at(self, position, game_time):
        """
        Returns:
            weather (Weather): Wind, visibility and sea state together.

        """
        ...
```

One provider supplies all three, deliberately: a game where the wind is a gale and the sea
is glass is a game with a bug in it, and separating them is how that bug happens.

**Or do not.** Without a provider you get one wind everywhere, from settings:

```python
MARITIME_WIND_BEARING = 165.0    # the bearing it blows *from*
MARITIME_WIND_SPEED = 6.0        # metres per second
```

The sea follows the wind unless you override it with `MARITIME_SEA_STATE`.

---

## Currents

Settings for a single stream:

```python
MARITIME_CURRENT_SET = 90.0      # the bearing the water flows *towards*
MARITIME_CURRENT_DRIFT = 0.5     # metres per second
```

Or `MARITIME_CURRENT_PROVIDER` for a tidal stream that changes with place and time.

The current is one of the two things the reckoning cannot see — the other is leeway — and
it is what makes `fix` worth doing.

---

## Tides

```python
MARITIME_TIDE_PROVIDER = "evennia.contrib.full_systems.maritime.tides.HarmonicTide"
```

Without one the sea does not move, and a ship aground stays aground until she is kedged off.
With one, the chart datum and the actual water are different numbers, which is the whole
point of a lead line.

---

## Marks and channels

```python
MARITIME_NAVIGATION_NETWORK = "world.sea.MyMarks"
```

What `plot` lays a course over and what `make for` follows. Without it, `plot` has nothing
to route by and the sailing master will only steer straight lines.

---

## Where the world's origin is

The world is a plane in metres. These place it on a globe so that `position` reads as
latitude and longitude:

```python
MARITIME_ORIGIN_NORTHING = 0.0
MARITIME_ORIGIN_EASTING = 0.0
```

Longitude deliberately does not narrow towards the poles. A cosine correction would make the
displayed position disagree with the distance actually sailed, and a navigator who cannot
trust the numbers has nothing.

---

Next: **[Your own ships](your-own-ships.md)**.
