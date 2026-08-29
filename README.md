# Maritime

Contribution by Gary Mix, 2026

A maritime simulation system for Evennia. Vessels occupy continuous world coordinates
rather than moving between ocean rooms — they gather way, come round, sail with the wind
on their own polar curves, make leeway, anchor, run aground, and sight each other across a
horizon that depends on how high the lookout is standing. They carry characters in ordinary
Evennia rooms while under way. The sea has a bottom, the bottom has depth, and the tide
moves the surface over it. Genre-neutral, and usable with core Evennia alone.

## Status

**Early development.** The foundations, spatial model, vessels, simulation, sailing,
grounding and observation are working and tested; ports, charts, weather, crew, combat and
damage are not built yet. Nothing here is API-stable.

What works today:

```text
> wind
The wind is 17 knots from 0-0-0. She has it on the beam, her best point of sailing.

> sail working
You call out, "Set working sail!"
The mate answers, "Working sail, aye sir."

> helm 090
You call out, "Helm, steer 0-9-0."
The helmsman answers, "Steering 0-9-0 now, sir."
The deck leans as she comes round to starboard.
    ...
The helmsman reports, "Vessel steady on 0-9-0 now, sir."
She runs east, the sea sliding past her rail.

> position
Test Sloop
  Position   0°08.6'S  0°00.5'E
  Heading    0-9-0   ordered 0-9-0
  Speed      6.6 kt   ordered 0.0 kt
```

Standing on the deck, two metres above the water:

```text
> lookout
Nothing in sight. The horizon is 2.9 miles off.
```

Twenty-eight metres up her mast, the same ship at the same instant:

```text
> lookout
The lookout reports:
  On the starboard beam               15.9 miles   a sail
```

## Design

Six ideas do most of the work. `docs/architecture.md` has the rest.

**Ships are simulation entities, not moving rooms.** A vessel holds a position; her
cabins and holds are ordinary rooms that name her as their position source. Nobody aboard
stores a coordinate, so moving the hull moves the whole ship's company at once, and a
hundred passengers cost no more than one.

**Continuous coordinates are authoritative, in three axes.** `WorldPosition(x, y, z)`
where z is elevation against a sea-level datum — negative is seabed, positive is dry land.
There is no separate depth map: water depth is the difference between the current surface
and the terrain beneath it, which is what makes tides move every depth in the world
without touching any terrain.

**The host game owns the clock.** Maritime never invents a travel-speed multiplier. It
reads elapsed game time from a provider, so a vessel's eight knots means eight nautical
miles per *in-world* hour whatever `TIME_FACTOR` the game runs at.

**The domain returns data; a separate layer speaks.** Physics and rules are plain Python
returning structured results, and nothing in the simulation knows the word "aground".
`messaging.py` decides which change is worth mentioning and who hears it — on deck you
watch the sea go by, below you feel her heel and hear water on the planking. Point
`MARITIME_NARRATOR` at a `VesselNarrator` subclass, override one method, and every line
the system speaks changes without a line of physics moving.

**Seeing is a height problem, not a range problem.** A hull is hidden by the curve of the
water, so how far you can see depends on how high your eye is — and how far you can see a
*particular* ship depends on how high she is too, because her masthead is over your horizon
looking back. Height of eye comes from the compartment you are standing in, so a masthead
is worth building rather than worth mentioning.

**One scheduler, bounded and fair.** Not a ticker per vessel: Evennia's `TickerHandler`
keys subscriptions on callback and interval but not arguments, so a fleet subscribing one
method silently overwrites itself and most ships stop moving. A single service processes
what fits in its budget and resumes where it stopped, so a large fleet lengthens the
revisit interval rather than blocking the reactor.

## Installation

Not yet installable as a release. To try the current state, place the package at
`evennia/contrib/full_systems/maritime` and add the helm command set to a ship's room:

```python
room.cmdset.add("evennia.contrib.full_systems.maritime.cmdsets.HelmCmdSet", persistent=True)
```

Add the driver script once per game, or nothing will move:

```python
from evennia.utils import create
from evennia.contrib.full_systems.maritime.scripts import MaritimeDriver

create.create_script(MaritimeDriver)
```

Full installation instructions will accompany the first release.

## Settings

All optional. Every one is prefixed `MARITIME_`.

| Setting | Default | Meaning |
| --- | --- | --- |
| `MARITIME_TIME_PROVIDER` | the game's own clock | Dotted path to a time provider |
| `MARITIME_RNG_SEED` | unset | Pin the master seed to make a run reproducible |
| `MARITIME_POSITION_STYLE` | `nautical` | `nautical` or `raw` |
| `MARITIME_ORIGIN_NORTHING` | `0.0` | Places the world's origin on the globe |
| `MARITIME_ORIGIN_EASTING` | `0.0` | As above, for longitude |
| `MARITIME_WIND_BEARING` | `0.0` | Bearing the wind blows *from* |
| `MARITIME_WIND_SPEED` | `0.0` | Wind speed in metres per second |
| `MARITIME_MAP_PROVIDER` | flat sea | Dotted path to the game's bathymetry |
| `MARITIME_NARRATOR` | the one here | Dotted path to a `VesselNarrator` subclass |
| `MARITIME_VISIBILITY` | 30 miles | How far the air lets you see, in metres |
| `MARITIME_DEFAULT_DEPTH` | `200.0` | Depth of the default flat sea, in metres |

## Usage

Commands are on the ship's rooms, so they work with a deck under you and nowhere else.

| Command | Effect |
| --- | --- |
| `helm <bearing>` | Steer a course. Spoken and answered as at sea |
| `sail <plan>` | `furled`, `storm`, `reefed`, `working`, `full` |
| `wind` | Where the wind is from and how she lies to it |
| `speed <knots>` | Order a speed, for vessels not under sail |
| `allstop` | Take the way off her |
| `drop anchor` / `weigh anchor` | Bring up, and get under way again |
| `position` | Latitude, longitude, course and speed |
| `sound` | Water under the keel, and a shoal warning |
| `lookout` | What is in sight from where you are standing |
| `@maritime` | Raw coordinates and motion state (Builder+) |

## Examples

Sailing is a negotiation, not an order. A vessel makes what the wind on her heading
allows:

```python
from evennia.contrib.full_systems.maritime import WorldPosition
from evennia.contrib.full_systems.maritime.sailing import (
    WindVector, PolarCurve, WORKING, achievable_speed,
)
from evennia.contrib.full_systems.maritime.motion import MotionLimits

hull = MotionLimits(max_speed=10.0, acceleration=1.0, turn_rate=6.0)
wind = WindVector(bearing=0.0, speed=10.0)      # a northerly

achievable_speed(90.0, wind, WORKING, PolarCurve(), hull)   # beam reach - fast
achievable_speed(45.0, wind, WORKING, PolarCurve(), hull)   # close-hauled - slower
achievable_speed(0.0, wind, WORKING, PolarCurve(), hull)    # head to wind - nothing
```

Ship classes are data. There is no `Sloop` class anywhere in this contrib:

```python
from evennia.contrib.full_systems.maritime import (
    VesselTemplate, VesselCapacity, DeckPlan, DeckLevel, OPEN, INTERIOR,
)

SLOOP = VesselTemplate(
    key="test_sloop", name="Test Sloop",
    length=18.0, beam=5.4, draft=2.2,
    capacity=VesselCapacity(displacement=32000.0, berths=4),
    deck_plan=DeckPlan(decks=(
        DeckLevel(level=0, name="Main Deck", slots=2, exposure=OPEN),
        DeckLevel(level=-1, name="Cargo Hold", slots=1, exposure=INTERIOR),
    )),
    crew_minimum=1, crew_ideal=4,
)
```

Every word the system speaks is replaceable, and replacing the words does not mean
reimplementing when to say them:

```python
from evennia.contrib.full_systems.maritime.messaging import VesselNarrator, COMING_ROUND


class Terse(VesselNarrator):
    def phrase_for(self, event, **detail):
        if event == COMING_ROUND:
            return f"Coming round to {detail['side']}.", None
        return super().phrase_for(event, **detail)


# settings.py
MARITIME_NARRATOR = "world.ships.Terse"
```

What a lookout can tell is bounded by the range, not by what the engine knows:

```python
from evennia.contrib.full_systems.maritime import (
    horizon_distance, geographic_range, detection_limit, detection_level,
)

horizon_distance(2.0)                    # a deck:      2.9 nautical miles
horizon_distance(30.0)                   # a masthead: 11.3 nautical miles
geographic_range(2.0, 30.0)              # her mast is over your horizon: 14.3

limit = detection_limit(2.0, 30.0)       # ...unless the air runs out first
detection_level(0.9 * limit, limit)      # 'contact'    - something on the water
detection_level(0.1 * limit, limit)      # 'identified' - you know the ship
```

## Testing

```bash
evennia test --settings settings.py evennia.contrib.full_systems.maritime
```

Roughly 770 tests. `ManualTimeProvider` advances game time on demand, so a voyage that
would take half an hour of wall time runs in milliseconds.

## Limitations

- No ports, docking, charts, weather, crew, cargo, combat or damage yet.
- One global wind and one global visibility. A weather provider replaces both later; call
  sites will not change.
- Ranges reported to players are true ranges. A lookout should be giving an estimate, and
  will once dead reckoning and navigational error land — `Sighting` carries the true
  distance and says so.
- Every vessel scans every tick, against a linear index. Fine for a harbour, and the reason
  the index interface exists separately from what is behind it.
- Grounding samples the vessel centre point only. A hull can step over a reef
  narrower than one tick of movement; swept hull-footprint testing lands with the
  water column phase.
- The world is a plane. Longitude does not narrow towards the poles, deliberately —
  a cosine correction would make the displayed position disagree with the distance
  actually sailed.
- Spatial indexes are a linear scan. The interface is settled; the structure behind it
  lands when there is real traffic to measure it against.
- Narration is addressed to compartments, not to people. A ship can tell the deck one
  thing and the hold another, but cannot yet tell the captain and a deck hand standing
  side by side two different things. The ship's own cry uses her highest weather deck, so
  she calls a sighting the masthead can see even when nobody is up there.

## License

Released under the same BSD 3-Clause license as Evennia. See `LICENSE`.
