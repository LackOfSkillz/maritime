# Maritime

Contribution by Gary Mix, 2026

A maritime simulation system for Evennia. Vessels occupy continuous world coordinates
rather than moving between ocean rooms — they gather way, come round, sail with the wind
on their own polar curves, make leeway, anchor, run aground, get set off course by a
current, and sight each other across a horizon that depends on how high the lookout is
standing. They carry characters in ordinary
Evennia rooms while under way. The sea has a bottom, the bottom has depth, and the tide
moves the surface over it. Genre-neutral, and usable with core Evennia alone.

## Status

**Early development.** Working and tested: the foundations, the spatial model and a tiled
seabed, vessels and their interiors, the simulation service, sailing, currents, grounding, observation, ports,
dead reckoning and fixes, charts, routes and the sailing master, weather and sea state,
tactical geometry, weapons, the projected ocean for anyone in the water, cargo, oars
and boarding. Not
built: crew and authority, damage, the strategic layer, and the service economy.
Nothing here is API-stable.

The first vertical slice runs end to end: walk aboard at one quay, cast off, make sail,
sail continuous water, sound your way through a channel past a rock ledge, come alongside
at another quay and walk ashore — without traversing a single ocean room.

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
  On the starboard beam              5.3 leagues   a sail
```

The water is moving too, so where she points and where she goes are different questions:

```text
> current
The current sets 1-8-0, drift 0.8 knots.
She heads 0-9-0 and makes good 0-9-7 at 6.6 knots.
```

Arriving is walking down a real gangway, not a teleport:

```text
> dock
You call out, "Take her alongside!"
The mate answers, "Alongside, aye sir."
Lines go ashore fore and aft. She is made fast at fishmarket steps, starboard side to.
The gangway comes down onto the quay.

> ashore
Harbour B - Fishmarket Steps
Steps run down from a fishmarket to a stub of quay, slick underfoot and smelling of it.
Exits: gangway
```

And the lead is cast the way a lead line is actually read:

```text
> sound
Elias orders a cast of the lead.
The leadsman calls, "By the deep six!" That is 4.9 fathoms under her keel.
```

Go over the side and the sea is a place too, without a single ocean room having been built
for it in advance — one is lent to your square of water, and taken back when you leave:

```text
> look
You are in the open sea, lifting and falling on a low swell.
A strong breeze comes out of the north-west, and takes the tops off the water.
A vessel under sail lies to the east, 1.3 leagues off.
```

She can be seen because her masts stand above the curve. From her deck, looking back,
there is nothing on the water at all.

Cargo is two capacities, not one, and which of them stops you depends on what you are
carrying. The same hull, twice:

```text
> stow 400 salt
You call out, "Get 400 tons of salt aboard."
The mate answers, "Aye sir - rig the yard tackle."
260 tons of salt go down into the lower hold.
140 tons of salt stay on the quay - the holds are full, though she would carry the
weight of something denser.

> manifest
Kestrel - manifest
  salt                   260.0 tons     260.0 m3
                         260.0 tons     260.0 m3 stowed

  Draught    3.89 m   freeboard 0.11 m
  Capacity   she has cubed out - the holds are full
  She is loaded past her marks. She is not fit to go to sea.
```

The same holds, filled with something light, are a completely different ship:

```text
> stow 400 wool
61 tons of baled wool go down into the lower hold.
339 tons of baled wool stay on the quay - the holds are full, though she would carry the
weight of something denser.

> manifest
  baled wool              61.6 tons     260.0 m3

  Draught    2.45 m   freeboard 1.55 m
```

And the draught is not a number on a sheet. Over a shelf with 2.4 metres of water on it,
loaded she is 1.5 metres into the ground and light she crosses with 40 centimetres to
spare — the same water, and the cargo is the whole difference.

## The example world

`example` builds it. One mainland, six islands, three boats:

```text
Pond Shore  --  Water Meadow  --  River Head
                                      |
                                (row down the river)
                                      |
                Stone Quay  --  Harbour Town  --  Ferry Steps

Stone Quay  ==  Gullstone  ==  Blackrock  ==  Thornholm  ==  Cradle Isle
            ==  Farne  ==  Outer Skerry
```

There is deliberately no path from the river head to the harbour. The river is the road,
and rowing down it is how you get there — rowing back up it is a different afternoon.

**Each of the three boats teaches one thing.** The kayak is a pond boat: stop paddling and
the breeze puts you ashore, because nothing else is moving her. The canoe is a river boat:
the same stroke is seven minutes a kilometre downstream and thirty-seven up, and with one
paddler instead of two she will not get up it at all. The sloop is a sea boat, and she
carries two sweeps that do nothing at all until the wind dies.

**Land is ordinary rooms with ordinary exits.** An island is a little graph you walk around
exactly as you would walk around anywhere else; one room of it is a `PortRoom`, which is an
ordinary room that also stands at a world position and offers a berth. That is the entire
join between a 2D room graph and a 3D sea.

Every leg between islands is between five and ten minutes under working sail, and there is
a test that says so — moving an island a few hundred metres is exactly the kind of edit
that looks harmless.

The speed that spacing rests on was *measured*, not assumed. The first layout was built
against a guess of four metres a second; she actually makes 2.2 on that heading, so every
island was nearly twice as far out as it should have been — and the test passed anyway,
because it was checking against the same guess. Sailing one leg is what caught it. The
example's wind is a southerly for the same reason: on an easterly course that puts it
across her beam, and from the west she makes 1.5 and the chain becomes a slog.

## Design

Sixteen ideas do most of the work. `docs/architecture.md` has the rest.

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
`messaging.py` holds every player-facing word the system produces — the ship's own
narration and the crew's replies to orders alike — and decides which change is worth
mentioning and who hears it — on deck you
watch the sea go by, below you feel her heel and hear water on the planking. Point
`MARITIME_NARRATOR` at a `VesselNarrator` subclass, override one method, and every line
the system speaks changes without a line of physics moving.

**The crew do not know where they are.** The engine does. A dead reckoning is advanced by
the course steered and the distance logged — which is all a compass and a log line give you
— so it drifts from the truth by exactly the current and the leeway nobody aboard could see.
Nothing rolls an error: in slack water a reckoning is perfect, and it should be. Take a fix
off a landmark and you learn not just where you are but what has been setting you, which is
the number that lets you steer the next leg properly.

**A heading is not a track.** The water moves as well, and an observer ashore sees the sum
of the two. `speed` is speed *through the water* — what a chip log measures — and the
over-ground course and speed are derived, so a current never has to be subtracted back out
of anything. A current is named for where it goes and a wind for where it comes from; both
are kept, because normalising one to match the other is how a bearing ends up reversed deep
inside a passage calculation.

**Units are display; metres are the truth.** Nothing inside the simulation knows what a
league is. What a player is shown is two settings, not one, because a ship reckoned her run
in leagues and her water in fathoms at the same moment — and every distance scheme falls
back to cables under a mile, because no scheme has a useful word for a tenth of its own
unit and they all borrowed the cable instead. A game in another genre changes one line and
gets kilometres.

**A physical relationship creates a traversal.** Docking does not teleport anybody. Lines
go ashore, a gangway is rigged as two ordinary Evennia exits, and it is deleted when the
lines are let go — so walking ashore is walking, and can be followed, blocked, watched and
locked like any other movement without a docking system having to reimplement any of it.

**Seeing is a height problem, not a range problem.** A hull is hidden by the curve of the
water, so how far you can see depends on how high your eye is — and how far you can see a
*particular* ship depends on how high she is too, because her masthead is over your horizon
looking back. Height of eye comes from the compartment you are standing in, so a masthead
is worth building rather than worth mentioning.

**The seabed is authored a square at a time, and a drawn hazard is exact.** A vessel loads
only the tiles her track crosses, so finding what is on this stretch of bottom does not
mean searching every rock in the world. More than that: a hull is sampled at seven points
on her outline and something small enough fits between them — two metres of rock four
metres off the centreline of a six-metre beam, as it turns out — so an authored hazard is
tested against the whole corridor she swept instead. She is stopped where she *enters* it,
because closest approach is on the far side of a rock she has by then sailed through.

**A pulling boat is the opposite of a sailing one.** A ship is not asked how fast to go —
she goes as fast as the wind on that heading allows. A boat under oars goes as fast as the
people in her are working, so her speed is a rated speed times the stroke times the
*fraction of oars actually manned*: a six-oared gig pulled by two hands is a slow boat with
four oars stowed. Sail wins where a hull has both, because nobody rows a boat that is
sailing — and oars take over in a calm without anybody ordering it. A boat nobody is
driving is not a boat that stays put: the stream carries her and the wind nudges her by her
own windage, which is why a kayak left alone on a pond ends up against the lee shore.

**A hull has two capacities and they are not interchangeable.** Deadweight is the mass she
can carry before she is too deep; hold volume is the space the cargo occupies. Stowage
factor decides which one stops you, and the spread is enormous — iron stows at about a
third of a cubic metre per tonne and hay at nine. So "she is full" is never the whole
answer: a ship that has *weighed out* will take nothing further, and one that has *cubed
out* would still carry something denser.

**Where a room is needed at all, it is a view rather than a place.** Open water gets no
rooms of its own; a small pool is lent out, one to each square of sea that currently has
somebody in it. Because a swimmer's truth is their position and the room only shows the
cell it falls in, releasing one loses nothing — and a lone drifter never changes room at
all, since the room can simply pan to the new water instead.

**Boarding is decided by relative velocity, not by speed.** Two ships running side by side
at ten knots on the same course are motionless with respect to each other and can be lashed
together at leisure; the same two on opposing courses tear the irons out of the rail.
Matching her course and speed *is* the manoeuvre. And the crossing is two ordinary exits —
`board` is not a command, it is the exit's name — so a hostile traversal can be followed,
blocked, watched and locked like any other, and none of that needed designing twice.

**A pass is bounded by a clock, not a count.** What one vessel costs depends entirely on the
world she is in — measured, a five-fold spread — so a fixed batch of twenty-five is
somewhere between 6.5 ms and 33 ms of held reactor and nothing about the number tells you
which. Twisted runs everything in one thread, so that is time in which nobody's command is
processed. The budget is checked after an update rather than before, because checking first
would let one slow vessel starve herself out of the rotation forever.

**One scheduler, bounded and fair.** Not a ticker per vessel: Evennia's `TickerHandler`
keys subscriptions on callback and interval but not arguments, so a fleet subscribing one
method silently overwrites itself and most ships stop moving. A single service processes
what fits in its budget and resumes where it stopped, so a large fleet lengthens the
revisit interval rather than blocking the reactor.

## Installation

Requires Evennia 6.1 or later. There is nothing to `pip install` — the package lives at
`evennia/contrib/full_systems/maritime` like any other contrib.

**1. Point your game at the example world.** In `mygame/server/conf/settings.py`:

```python
MARITIME_MAP_PROVIDER = "evennia.contrib.full_systems.maritime.example.ExampleSeabed"
MARITIME_CURRENT_PROVIDER = "evennia.contrib.full_systems.maritime.example.ExampleCurrents"
MARITIME_WIND_BEARING = 165.0
MARITIME_WIND_SPEED = 6.0
```

Every one of those is optional. With none of them you get a flat, still, windless sea,
which is a legitimate world and a dull one. Replace them with your own classes when you
have a coastline of your own — see [Settings](#settings).

**2. Add the builder command.** In `mygame/commands/default_cmdsets.py`:

```python
from evennia.contrib.full_systems.maritime.example import CmdMaritimeExample

class CharacterCmdSet(default_cmds.CharacterCmdSet):
    def at_cmdset_creation(self):
        super().at_cmdset_creation()
        self.add(CmdMaritimeExample())
```

**3. Start the driver.** Once per game, or nothing moves:

```python
from evennia.utils import create
from evennia.contrib.full_systems.maritime.scripts import MaritimeDriver

create.create_script(MaritimeDriver)
```

**4. Reload, and run `example`** as a builder. It creates a mainland with a pond, a river
and a harbour town, six islands strung eastward, and three craft. It is safe to run twice.

Then walk to the Pond Shore, board the kayak, and start paddling.

### Putting the commands on your own ships

The example does this for you. For a ship you build yourself, the helm command set goes on
her compartments — by dotted path, so it survives a reload:

```python
room.cmdset.add("evennia.contrib.full_systems.maritime.cmdsets.HelmCmdSet", persistent=True)
```

On the compartments rather than on the character, so that a helm order needs a deck under
you and cannot be given from a tavern.

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
| `MARITIME_CURRENT_SET` | `0.0` | Bearing the water flows *towards* |
| `MARITIME_CURRENT_DRIFT` | `0.0` | How fast it flows, in metres per second |
| `MARITIME_CURRENT_PROVIDER` | slack water | Dotted path, for a tidal stream |
| `MARITIME_NAVIGATION_NETWORK` | no marks | Dotted path to the game's marks and channels |
| `MARITIME_WEATHER_PROVIDER` | from the settings below | Dotted path to the game's weather |
| `MARITIME_SEA_STATE` | follows the wind | Override the sea the wind would raise |
| `MARITIME_MAP_PROVIDER` | flat sea | Dotted path to the game's bathymetry - a `TiledMapProvider` subclass for an authored seabed |
| `MARITIME_NARRATOR` | the one here | Dotted path to a `VesselNarrator` subclass |
| `MARITIME_WATER_NARRATOR` | the one here | Dotted path to a `WaterNarrator` subclass |
| `MARITIME_COMMODITIES` | a standard stowage table | The cargoes this game trades in |
| `MARITIME_TICK_BUDGET_MS` | `10.0` | How long one simulation pass may hold the reactor; 0 disables the limit |
| `MARITIME_CELL_SIZE` | `100.0` | How wide a projected square of open water is, in metres |
| `MARITIME_OCEAN_ROOM_TYPECLASS` | `OceanRoom` | Dotted path to the class pool rooms are built from |
| `MARITIME_VISIBILITY` | 30 miles | How far the air lets you see, in metres |
| `MARITIME_DISTANCE_UNITS` | `leagues` | `leagues`, `nautical`, `metric` or `raw` |
| `MARITIME_DEPTH_UNITS` | `fathoms` | `fathoms`, `metres` or `raw` |
| `MARITIME_DEFAULT_DEPTH` | `200.0` | Depth of the default flat sea, in metres |

## Usage

Commands are on the ship's rooms, so they work with a deck under you and nowhere else.

| Command | Effect |
| --- | --- |
| `helm <bearing>` | Steer a course. Spoken and answered as at sea |
| `sail <plan>` | `furled`, `storm`, `reefed`, `working`, `full` |
| `wind` | Where the wind is from and how she lies to it |
| `current` | Set and drift, and the course she is making good |
| `weather` | Wind by its force, the sea, and how far you can see |
| `fix` | Fix her position off a landmark, and learn the set |
| `chart` | What the paper says is under her, and how far to trust it |
| `plot <mark>` | Lay a course by way of safe water |
| `follow` / `belay` | Hand the sailing master the con, and take it back |
| `speed <knots>` | Order a speed, for vessels not under sail |
| `allstop` | Take the way off her |
| `drop anchor` / `weigh anchor` | Bring up, and get under way again |
| `dock` / `cast off` | Come alongside a berth, and let go |
| `position` | Latitude, longitude, course and speed |
| `sound` | Water under the keel, and a shoal warning |
| `lookout` | What is in sight from where you are standing |
| `scan` | The whole horizon, quarter by quarter |
| `target <name>` | Range, aspect, closure and which arcs bear |
| `guns` / `load` / `fire <name>` | The battery, serving it, and firing what bears |
| `look <direction>` | One quarter or compass point - `look se`, `look port` |
| `watch <direction>` | A standing watch; told as things come and go |
| `look` | A weather deck also describes the sea outside it |
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

Being lost is the water, not a dice roll:

```python
from evennia.contrib.full_systems.maritime import reckon, take_fix, error_of, WorldPosition

dr = take_fix(WorldPosition(0.0, 0.0), now=0.0)
dr = reckon(dr, heading=90.0, speed=5.0, elapsed=600.0)   # course steered, distance logged

dr.position            # (3000, 0) - where she reckons she is
dr.uncertainty         # what the navigator would admit to
error_of(dr, true)     # what she is actually out by: the current, exactly
```

A berth is a place with dimensions, and that is what makes it a decision:

```python
from evennia.contrib.full_systems.maritime import Berth, WorldPosition, can_dock

berth = Berth(
    key="fishmarket steps", position=WorldPosition(3800.0, -800.0), heading=90.0,
    max_length=24.0, max_beam=8.0, max_draft=4.0,
)

can_dock(WorldPosition(3790.0, -800.0), 0.2, 270.0, 18.0, 5.4, 2.2, berth)   # alongside
can_dock(WorldPosition(3790.0, -800.0), 4.0, 270.0, 18.0, 5.4, 2.2, berth)   # 'too_fast'
can_dock(WorldPosition(3790.0, -800.0), 0.2, 270.0, 18.0, 5.4, 5.0, berth)   # 'too_deep'
```

You do not steer where you are going — you steer to counteract what the water is doing:

```python
from evennia.contrib.full_systems.maritime import (
    CurrentVector, made_good, course_to_steer,
)

stream = CurrentVector(set=0.0, drift=2.0)     # two metres a second, setting north

made_good(90.0, 5.0, stream)                   # heading east: a track north of east,
                                               # and faster than she is sailing
course_to_steer(90.0, 5.0, stream)             # what to steer to actually make east good
course_to_steer(90.0, 1.0, stream)             # None - she cannot outrun the stream
```

Soundings are called, not printed:

```python
from evennia.contrib.full_systems.maritime import leadsman_call, METRES_PER_FATHOM

leadsman_call(7.00 * METRES_PER_FATHOM)   # 'By the mark seven!'   - the line is marked here
leadsman_call(6.00 * METRES_PER_FATHOM)   # 'By the deep six!'     - and not here
leadsman_call(7.75 * METRES_PER_FATHOM)   # 'A quarter less eight!'
leadsman_call(2.00 * METRES_PER_FATHOM)   # 'By the mark twain!'
```

## Testing

```bash
evennia test --settings settings.py evennia.contrib.full_systems.maritime
```

Roughly 1760 tests. `ManualTimeProvider` advances game time on demand, so a voyage that
would take half an hour of wall time runs in milliseconds.

## Limitations

- No crew or damage yet. Guns fire and hit; what a hit *does* to a hull is the damage
  phase, and `ShotResult` is deliberately something nothing consumes.
- Cargo has no price. Contracts, freight rates, who is buying and what a voyage is worth
  are the game's own economy, and shipping an opinion about them would collide with
  whatever it already has. Recorded in `DECISIONS.md`.
- Nothing tires. A crew can hold a racing stroke across an ocean, because what that costs
  them collides with whatever stamina the host game already has. `rowed_speed` takes the
  crew count as an argument rather than reading it off the boat, so a game that wants a
  tiring crew supplies a smaller number and everything downstream follows. In
  `DECISIONS.md`.
- Being tender is reported and costs her nothing. What top-heavy loading should actually
  do to a ship reaches into sailing and damage at once, and both of those decisions are
  the game's.
- Nothing yet puts a player in the water. The projection can hold them, drift them and
  describe the sea to them, but going over the side is something damage and boarding do,
  and neither is built.
- Being in the water costs nothing. There is no exhaustion, no cold and no drowning,
  because those are statements about how harsh a game is and would collide with the
  health and stamina the host game already has. Recorded in `DECISIONS.md`.
- The water column is not built. `Buoyancy` carries a sink rate so that a wreck has
  somewhere to go, but nothing yet decides when something stops floating, and nothing
  can be dived on.
- A port is a quay with berths. Anchorages, pilots, tugs, cargo handling and repair
  facilities are all later phases.
- The default weather is one wind, one visibility and one sea everywhere. A game supplies
  a provider for anything better; call sites do not change.
- Sea state slows a vessel and is described from the deck. Its effect on stability, gunnery,
  swimming and small craft arrives with the phases that own those.
- One global current, like the wind. A provider replaces it with a tidal stream later;
  call sites will not change.
- Ranges and bearings in a sighting are true, not estimated. The vessel's *position* is now
  reckoned rather than known, but a lookout's range to a contact is still exact.
- Every vessel scans every tick, against a linear index. Fine for a harbour, and the reason
  the index interface exists separately from what is behind it. Measured at roughly a
  millisecond a vessel with fifty sail in company - see `docs/performance.md`.
- The performance figures were taken on a development machine. The ratios are what the
  design rests on; a game expecting a large fleet should re-run the benchmark on the box it
  will actually run on.
- A hull is sampled at seven points on her outline, not swept as a continuous shape, so
  *unauthored terrain* small enough to fit between those points can still pass between
  them. A hazard a game has actually drawn cannot: it has a radius and is tested against
  the whole corridor she swept. A vessel with no measured length or beam is tested at her
  centre alone.
- The world is a plane. Longitude does not narrow towards the poles, deliberately —
  a cosine correction would make the displayed position disagree with the distance
  actually sailed.
- Spatial indexes are a linear scan. The interface is settled; the structure behind it
  lands when there is real traffic to measure it against.
- Capture confers nothing. A ship can be boarded and can strike, and what a captor may
  then do with her - who may give her orders, who owns her - is a question about authority,
  which is phase 14. In `DECISIONS.md`.
- Two lashed hulls do not move as one. Each is simulated separately and the lines part if
  their motion diverges far enough, which is the honest half; a coupled two-body model is
  not built.
- Nothing decides what happens to an offline passenger aboard a vessel that founders.
  Evennia's default is that they survive and are teleported home without being told, which
  is a policy nobody chose; `Vessel.ships_company()` exists so that any other policy is
  implementable, and the question is in `DECISIONS.md`. The engine behaviour behind it is
  written up in `docs/logout.md`.
- Narration is addressed to compartments, not to people. A ship can tell the deck one
  thing and the hold another, but cannot yet tell the captain and a deck hand standing
  side by side two different things. The ship's own cry uses her highest weather deck, so
  she calls a sighting the masthead can see even when nobody is up there.

## License

Released under the same BSD 3-Clause license as Evennia. See `LICENSE`.
