# Maritime — Architecture

This document explains how the maritime system is designed and, more importantly, *why*.
It is written for anyone reading or extending the code.

Nothing here is game-specific. Where a decision depends on the host game — how fast its
world clock runs, what happens to an offline character, how death works — the design
exposes a seam rather than picking an answer.

---

## 1. The core idea

A vessel is a simulation entity holding a position in continuous world space. It is not a
collection of rooms that move.

```text
Vessel
├── position, heading, velocity
├── propulsion
├── hull, damage, flooding
├── crew, cargo
└── interior rooms
```

Its cabins, decks and holds are ordinary Evennia rooms. Characters walk around inside them
normally while the vessel is underway. The rooms belong to the vessel; they do not
determine where it is.

The ocean is simulated. Rooms are how characters experience parts of it.

---

## 2. Architectural laws

These are enforcement rules, not aspirations. Code review checks against them.

A fourteenth law governs how the repository itself is built rather than how the simulation
behaves — that this ships as a clean contrib, with no cleanup pass ever owed. It lives in
`CLAUDE.md`, where the discipline it demands is actually checkable, and it is not restated
here.

### Law 1 — One world clock

The maritime system consumes elapsed **game time** from a `TimeProvider` supplied by the
host game. It never invents its own travel-speed multiplier.

A game running its world at 4:1 gets voyages four times faster in real terms than one
running at 1:1, and neither needs a maritime-specific setting to make that happen. Speeds
stay expressed naturally: an eight-knot vessel covers eight nautical miles per *in-world*
hour, whatever that means in wall-clock terms.

### Law 2 — Continuous position is authoritative, and it has three axes

Entities exist at continuous `(x, y, z)` positions, where **z is elevation relative to a
sea-level datum**. Discrete cells, rooms and displayed range bands are projections. They are
never the source of truth.

The third axis is present from the first commit even though surface vessels never leave the
surface. Retrofitting an axis into the authoritative position type touches distance,
bearing, the spatial indexes, the location resolver, collision, grounding and every
serialisation — it is the most expensive change this architecture can absorb. A field and a
constraint now is cheap.

### Law 3 — The ship moves, not its rooms

See section 1.

### Law 4 — Background vessels are not Evennia Objects

A distant NPC vessel is a lightweight domain record: no typeclass, no room tree, no
attributes, no per-vessel script. It becomes a full Evennia object only when detailed
interaction requires it.

Customised or occupied vessels are the exception and go **dormant** instead — see section 6.

### Law 5 — Strategic and active simulation are different algorithms

Distant vessels advance analytically from elapsed game time. Nearby vessels use bounded
fixed-step integration. Never run three thousand one-second physics steps because a distant
vessel has not been updated for an hour.

### Law 6 — One location resolver

No subsystem independently decides where an entity is. Every world-position query goes
through `get_world_position(entity)`.

Ordinary land rooms need no coordinate and legitimately return `NoWorldPosition` — a defined
sentinel, not `None`, so it cannot propagate silently. Ports bridge room-space and
world-space.

### Law 7 — Physical relationships create traversal

Docking and boarding create temporary traversal links between real locations. The system
never teleports a character because two places are conceptually connected.

### Law 8 — The reactor has a budget

Evennia is single-threaded. Maritime background work is bounded, amortised and
starvation-free. Never process an entire fleet in one callback.

### Law 9 — Randomness is injected

Domain code never calls global `random`. Given identical state, inputs, elapsed game time,
step sequence and RNG streams, the domain produces identical results.

This is a testing property, not a promise that a live multiplayer session replays from a
seed.

### Law 10 — Persistence is explicit

Runtime state may live in memory, but important state has explicit checkpoint, reload flush,
shutdown flush and restore rules. Nothing depends on implementation accident.

### Law 11 — The domain returns structured results, never prose

```python
ManeuverResult(success=True, heading_change=7.2, speed_change=-0.4, heel=10.8)
```

Messaging is a separate layer that renders results per observer. A `caller.msg()` inside a
physics or damage calculation is a defect — it is the easiest law to break by accident, and
breaking it makes the messaging layer unreplaceable by a game that wants its own voice.

That layer is `messaging.py`, and it holds two things: what a ship narrates about herself,
and what her crew say when they are given an order. Both go through one class, so a game
replacing its voice replaces all of it — for a while only the first did, and a game could
change what the ship said while the crew went on answering in the contrib's words.

It answers two questions the simulation does not: which change is worth mentioning, and who
hears it. The first is why narration state lives there
rather than on the vessel — deciding whether to speak needs to know what was last said,
which is a property of the conversation and not of the hull. A game points
`MARITIME_NARRATOR` at a `VesselNarrator` subclass and overrides `phrase_for`, which every
line a vessel speaks passes through; it inherits the timing it did not ask to change.

### Law 12 — Services never fabricate physical state

A service executes only while its physical, contractual and temporal preconditions hold.
`execute()` always revalidates. Services may resolve routine transfers atomically, but never
invent an outcome the simulation did not produce.

### Law 13 — Every milestone proves itself

Implementation, unit tests, invariants and a scenario test ship together. Testing is not a
final phase.

---

## 3. Time

```python
class MaritimeTimeProvider:
    def now(self): ...
    def elapsed_game_seconds(self, since): ...
```

The seam exists from the first commit for two reasons, and the second matters more day to
day: **it is the test harness.** A voyage that takes 37 minutes of wall time under a
production clock completes in milliseconds under a manual provider that steps time on
demand. Without this seam, voyage tests are untestable in practice.

| Environment | Provider | Behaviour |
| --- | --- | --- |
| Production | host game's clock | whatever ratio the game runs |
| Unit / scenario | `ManualTimeProvider` | `time.advance(hours=2.5)` |
| Integration | accelerated | fixed high ratio |

**Open question.** World simulation clearly follows game time. Whether *tactical* play —
collision avoidance, boarding approach, manoeuvring for firing arcs — should present at a
reduced ratio is unresolved and deliberately left tunable. Under heavy compression, several
real seconds of typing can be a large amount of closure.

---

## 4. Space

### 4.1 One elevation model for land, sea and seabed

There is no separate "depth map". There is one terrain elevation field that crosses zero.

```text
Z +40     cliff
Z  +1     beach
Z   0     datum
Z  -0.5   reef crown
Z  -3     shoal
Z  -20    coastal shelf
Z -3000   ocean floor
```

The shoreline is where terrain intersects the current water surface.

### 4.2 Tides fall out for free

Sea level is a datum, not a constant.

```text
High water:  surface +1.5, seabed -3.0  ->  4.5 m of water
Low water:   surface -0.8, seabed -3.0  ->  2.2 m of water
```

Same terrain, different navigable water. This is what makes tide a system rather than
flavour — it opens and closes harbour approaches and decides when a bar is passable.

Tide is a provider with a flat default, so a game that does not want tides never configures
one.

### 4.3 Map provider

```python
class MaritimeMapProvider:
    def terrain_z_at(self, position): ...                # authoritative
    def sea_surface_z_at(self, position, game_time): ... # datum + tide
    def water_depth_at(self, position, game_time): ...   # derived
    def bottom_type_at(self, position): ...
    def current_at(self, position, game_time): ...
    def hazards_near(self, position): ...
```

Z is truth; depth is convenience. Depth is still exposed, because the alternative is every
subsystem writing `surface_z - terrain_z` itself and getting the tide argument wrong
somewhere.

**A depth query without a game-time argument is a bug** — it silently asks about the datum
rather than the water actually present.

### 4.4 Vertical envelopes, not vertical physics

Surface vessels are not free 3D bodies. Their horizontal position is simulated; their
vertical position is constrained:

```text
surface_z = sea_surface_z_at(position, now)
keel_z    = surface_z - effective_draft
```

That is all the vertical state a sailing vessel needs, and it is enough for grounding,
tides, squat and hull intersection to fall out of one model.

Entities that *do* own a free Z: divers, sinking objects, settled wrecks, sea creatures.

### 4.5 Spatial indexes come in two scales

One index cannot serve both horizon search and boarding distance.

- **Contact index** — coarse, surface-plane. Lookout and traffic discovery. Horizon geometry
  is a surface concern; this index does not need Z.
- **Proximity index** — fine, Z-aware. Collision, docking, boarding, divers, debris. A diver
  thirty metres beneath a hull is horizontally adjacent and must not be treated as close.

Both generate *candidates* only. Continuous coordinates resolve real geometry.

---

### 4.6 Navigational data is tiled

Terrain, coastline, reefs, shoals, rocks and channels are held per tile, and a vessel
queries only the tiles its movement envelope touches. The alternative — searching every
hazard in the world for every vessel every step — is the shape of an O(n·m) sweep that
looks fine with one ship and a reef and stops being fine with a fleet and a coastline.

A tile is a square of authored seabed: a base elevation, what the ground is made of, and
whatever discrete hazards stand on it. A flat base with things on it rather than a grid of
soundings, because a sounding grid makes a builder fill in a hundred identical numbers to
describe one shelf and *still* cannot say "there is a rock here that dries at low water"
without inventing a resolution fine enough to hold it.

**Tiling did not change what a depth query means.** `TiledMapProvider` is an ordinary
`MaritimeMapProvider`; every existing caller of `terrain_z_at` gets the same kind of answer
from the same interface, which is what the original note above promised.

**What tiles bought is exactness, not only speed.** The swept envelope samples a hull at
seven points on her outline, and something small enough fits between them. How small was
measured rather than argued: two metres of rock, four metres off the centreline of a
six-metre beam, is invisible to all 567 points a sampled pass looks at along an 800-metre
track. An authored hazard has a position and a radius, and is tested against the *whole
corridor she swept*:

```text
hazards_touching(before, after, beam)  ->  the ones the corridor reaches
track_entry(hazard, before, after, r)  ->  where she strikes it
```

She is stopped where she **enters** it, not where she passes closest to it. Closest
approach is on the far side of a rock she has by then sailed through.

> **Invariant:** a hazard inside the water a hull displaces is never missed, however
> small it is and wherever it falls relative to her sample points.

**Unauthored water is not a hole in the world.** A square nobody has drawn falls through to
a base provider — deep open sea by default. A game maps its coastline and its approaches
and leaves the ocean alone, which is how real charts work: the detail is where the danger
is. Tiles load on demand and can be released, so a world of ten thousand keeps resident
only the ones being sailed over.

---

### 4.7 Open water is projected, not built

A ship needs no rooms for the sea because she *is* a place: her compartments are ordinary
rooms that never move, and the hull carries them. Anyone not aboard one — a swimmer, a
diver surfacing, someone on a raft — has no such room, and building rooms for an ocean
nobody is in would be building a world to hold its empty parts.

So the surface is projected. A small pool of rooms is lent out, one to each square of water
that currently has somebody in it, and taken back when they leave. The pool is bounded by
the number of *simultaneously occupied* cells, not by the size of the sea.

**The room is a view, not a location, and everything follows from that.** Evennia's
`wilderness` contrib solves the same problem the other way round: there the room *is* where
you are, so recycling one has to preserve whatever was inside it, and its own docstring
warns that objects left behind end up with `location = None`. Here a swimmer's truth is
their `maritime_position`, held on the swimmer; the room only shows the cell that position
falls in. Releasing a room therefore loses nothing.

That inversion pays three times:

- **Drift is not movement.** A floating thing changes position every tick and changes room
  only on the few ticks it crosses a boundary.
- **A lone drifter never changes room at all.** The room pans to the new cell instead — no
  move, no departure, no arrival. Skipped the moment somebody else is in the room, or
  another room already shows the destination, since two rooms showing one cell would put
  two swimmers in the same water unable to see each other.
- **What you can see is not local.** Contacts are computed from the position, so the answer
  does not depend on which room happens to be lending it.

**The pool is found by tag, not by typeclass.** A typeclass query filters on the dotted path
stored on the row, so moving or renaming the class would silently empty the pool.

> **Invariant:** at most one pool room shows any one cell.

> **Invariant:** a room is released only when nothing but exits remains in it — and even a
> forced release would destroy nothing, because position lives on the swimmer.

---

## 5. Grounding

Grounding is not a special case. It is terrain intersecting the vessel envelope.

```python
clearance = keel_z - terrain_z_at(position)
if clearance <= 0:
    resolve_grounding()
```

The first implementation samples the centre point. The real one samples a hull footprint —
bow, stern, port, starboard — and sweeps along the movement track, so a vessel cannot step
over a reef between ticks.

Clearance is continuous, not binary. It feeds soundings, pilot advice, squat at speed, and
the difference between touching bottom and being hard aground. `effective_draft` accounts
for load, flooding and heel, which is why it is derived rather than stored.

Bottom type decides consequences: mud and sand hold and often release on the next tide; reef
and rock hole the hull. Refloating on a rising tide works only because tide and terrain share
one model.

---

### 5.1 A hull is not a point

A vessel has length, beam, draft and a heading, and those define a footprint. A large ship
can have her bow over a reef while her centre is still in deep water, and testing the centre
alone says she is safe.

Worse, a moving vessel has to test the **swept** footprint between where she was and where
she is proposing to be. Sampling only the endpoints lets a fast hull step clean over a shoal
narrower than one tick of movement — and the faster she goes, the more of the seabed she can
ignore, which is precisely backwards.

Built. A hull is seven points in a rough ship shape — a single bow, quarters at her widest,
a single stern — rather than a rectangle, because a rectangle puts steel where a ship has
none and would ground her on water she is not over. The track is sampled at half her length,
so consecutive footprints overlap and nothing longer than the gap lies between two tests
untouched, and she is stopped at the first thing she touches rather than at the end of the
move — a ship that struck a reef a third of the way through a tick did not travel the other
two thirds.

Demonstrated against the test world's own ledge: a hull making 25 m/s asked to run 750
metres in one tick, straight across 400 metres of rock. The old point test at her
destination reported clear water. The swept test stopped her one metre short of the ledge.

Two limits remain, and both are sampling rather than structure. Something smaller than the
gaps *within* the seven-point outline can still slip between them, and a vessel with no
measured length or beam is tested at her centre alone — which is deliberate, so a game that
has not measured its hulls gets the old behaviour rather than a hull of size zero.

---

## 6. Vessel representation

```text
DORMANT  <->  STRATEGIC  <->  ACTIVE  <->  TACTICAL
```

- **Dormant** — docked or laid up. Rooms and contents persist in the database; the vessel is
  absent from the simulation registry. This is where an occupied or customised vessel rests.
- **Strategic** — distant, unmaterialised, advancing analytically along a route.
- **Active** — materialised, normal sailing, fixed-step physics.
- **Tactical** — materialised, high fidelity: combat, collision threat, boarding, grounding.

Dormant and Strategic are genuinely different, and conflating them is a bug waiting to
happen. A strategic record is a *summary* — it rehydrates an NPC trader faithfully because
nothing about that vessel is individual. It cannot rehydrate placed furniture, container
contents, an altered room tree, or bought upgrades. Vessels carrying individual state
dematerialise by leaving the simulation registry, never by deleting rooms.

Materialisation preserves identity. A vessel never becomes a different vessel because its
representation changed.

### 6.1 Cargo, and the two capacities

A hull has two capacities for cargo and they are not interchangeable:

```text
deadweight    the mass she can carry before she is too deep
hold volume   the space that cargo occupies
```

Which one binds depends entirely on what she is carrying. **Stowage factor** — the cubic
metres one tonne of a thing occupies — is what separates them, and the spread is enormous:
iron stows at about 0.35 and hay at 9. A hull full of iron has most of her volume empty; the
same hull full of hay is barely down on her marks.

That is the whole trade, and it is why both are tracked and why "she is full" is never a
complete answer. A ship that has **weighed out** will take nothing further. One that has
**cubed out** would still carry something denser, which is a decision a shipper can act on.

**Broken stowage** — the space wasted between irregular packages — is charged against
packaged cargo and not against bulk, because bulk has no packages to leave gaps between.

**Cargo is data, not objects.** Five hundred tonnes of grain is one parcel, not five hundred
database rows. The same argument as shots being events: nothing gains anything from each
sack having an identity. A game wanting a *particular* crate puts an ordinary object in the
hold beside the parcels.

**Hold volume is not `VesselCapacity.internal_volume`.** That is the space below deck that
cabins, stores and holds all compete for when she is *built*, and reading it at a quay would
let a ship load cargo into the volume her cabins are standing in. What stops a load is the
hold she actually has.

**Loading has consequences, and they are the point.** Every one lands in a system that
existed before cargo and did not change to receive it:

| effect | reached through |
| --- | --- |
| she grounds where a light ship swims | `draft`, now derived |
| a berth that took her light refuses her loaded | `Berth.takes` |
| she is slower | `working_limits` |
| weight stowed high makes her tender | deck level, already real Z |

> **Invariant:** the working draft is never stored. It is the light draft plus what the
> manifest puts her down by, so it cannot disagree with what is in her holds.

**Weight stowed low is weight doing good.** The stability moment is taken relative to the
main deck rather than the keel, so the sign carries the meaning: ballast and heavy cargo
stowed low come out negative. Stowing from the bottom up is then what the arithmetic
rewards rather than a rule to be remembered — and it is why loading fills from the lowest
hold and discharging works from the highest down.

What being tender then *costs* her, and what a cargo is worth to anybody, are both the
game's to decide. See `DECISIONS.md`.

---

## 7. Simulation and persistence

One scheduler. Never a ticker per cannon, mast, ship or fire.

**A pass is bounded twice, and the two answer different questions.**

```text
batch size    how many entities one pass will look at   (backstop)
time budget   how long one pass will take               (the real limit)
```

A batch count is a guess dressed as a limit: what one vessel costs depends entirely on the
world she is in, and a measured five-fold spread means twenty-five of them is somewhere
between 6.5 ms and 33 ms of held reactor. Only a clock knows which. See
`docs/performance.md` for the numbers.

> **Invariant:** the budget is checked *after* an update, never before. Checking first would
> let one slow vessel starve herself out of the rotation permanently.

> **Invariant:** whatever a pass never reached is wound back onto the rotation. Nothing is
> dropped; it is deferred by one pass rather than by a whole circuit.

**Strategic advancement** is analytical:

```text
elapsed = now - last_update
distance = effective_speed * elapsed
```

One calculation, not twelve thousand one-second iterations.

**Active simulation** uses a fixed step, with catch-up itself bounded so a stalled reactor
cannot produce an enormous synchronous recovery loop.

**Fair scheduling.** Background work runs against a time budget with a *persistent* cursor:

```python
while budget_remaining():
    process(queue.next())
```

The cursor survives the callback and uses stable ids rather than list offsets. Restarting
from index zero each pass silently starves the tail of the fleet — vessels simply stop
advancing, and it presents as a physics bug rather than a scheduling one.

> **Invariant:** every eligible vessel is processed within the configured maximum interval.

**Persistence** happens at checkpoints, on critical events (docking, capture, sinking,
ownership transfer, materialisation transitions) and on reload/shutdown. Never per tick —
attribute writes are the dominant cost in an Evennia game, and a physics loop that writes
every step will bring a server to its knees long before the maths does.

---

## 8. Sailing

Believable sailing, not fluid dynamics.

**Inputs:** wind vector, heading, sail configuration and condition, hull drag, mass, current,
sea state, damage.
**Outputs:** acceleration, velocity, turn capability, leeway, heel.

Rig performance is a **data-driven polar curve** per vessel template — efficiency as a
function of relative wind angle. No universal curve is baked into the engine; a square-rigger
and a fore-and-aft rig have genuinely different shapes.

Propulsion is an interface, so the system is not sail-only:

```python
class PropulsionSystem:
    def calculate_thrust(self, ...): ...
```

Sail, oar, motor, steam, tow — and whatever a given game invents.

**A heading is not a track.** The water is moving too, and what an observer ashore sees is
the sum of the two. `currents.py` carries set and drift, the course and speed made good, and
the navigator's triangle that answers what to steer to make a wanted track good — which
genuinely has no answer when the stream is stronger than the vessel, and says so rather than
returning a heading that quietly does not work.

**A current is named for where it goes; a wind for where it comes from.** A northerly wind
blows *from* the north, a north-setting current flows *towards* it. Both conventions are
kept, because normalising one to match the other is how a bearing ends up reversed deep
inside a passage calculation, and because those are the words.

**Speed is speed through the water.** A chip log measures the water going past the hull, so
a vessel set three knots sideways still logs what her sails are making. Keeping `speed`
through-water and deriving the over-ground figures means the current never has to be
subtracted back out of anything — and it makes the difference between the two reportable,
which is the whole of navigation.

Set and drift come from a provider, so a tidal stream that reverses twice a day replaces a
steady set without any call site changing. A game that wants one steady stream sets
`MARITIME_CURRENT_SET` and `MARITIME_CURRENT_DRIFT` and writes no code.

### 8.1 Oars, paddles, and the arms behind them

A sailing vessel is not asked how fast to go — she goes as fast as the wind on that
heading allows. A pulling boat is the exact opposite: she goes as fast as the people in her
are willing to work, and stops when they stop.

```text
speed through water = rated_speed  x  stroke effort  x  fraction of oars manned
```

Three factors, and the third is the interesting one. **A six-oared gig pulled by two hands
is not a six-oared gig**; she is a slow boat with four oars stowed. Making the crew count
matter is the point of counting them, and it is what makes finding a second pair of hands
worth doing before a long pull.

**A rated speed, not a force.** Turning strokes into newtons and newtons into knots needs a
drag model for every hull, and every number in it would be invented. A rated speed is one
figure a builder can look up, argue with, and set.

**Easy oars and hold water are different orders.** Both produce no speed. Easy oars means
stop pulling and let her run on; hold water means put the blades in and stop her — so it
comes back as sharper deceleration rather than as a smaller number. That is the one thing a
pulling boat can do that a ship under sail cannot.

**Sail wins where both are available.** A cutter carries a lug sail and twelve oars, and
which drives her depends on the wind: nobody rows a boat that is sailing, and a hull doing
both would be getting her speed twice.

**One model, two vocabularies.** A kayak is a boat with one position and a double blade;
the arithmetic does not care and the words very much do, so the oar plan carries which
vocabulary applies and the messaging layer reads it. Nobody ends up telling a lone kayaker
to give way together.

> **Invariant:** rowing is speed *through the water*, like every other speed here. Rowing
> up a stream and down it are the same work and different voyages, and nothing subtracts a
> current from anything to say so.

**A boat nobody is driving still goes somewhere.** Sails furled and blades out of the water
is not the same as being moored. The stream carries her and the wind pushes her, in
proportion to how much of her stands out of the water — the same windage a drifting cask
has, from the same function. Skipped under canvas, where the wind is already driving her.

> **Invariant:** "nothing happened this tick" is decided *after* the water and the air have
> been applied, never from her propulsion alone.

Nothing here tires. What a racing stroke costs a crew is a statement about how harsh a game
is and collides with whatever stamina the host game already has — see `DECISIONS.md`.

---

## 9. Navigation and observation

The engine knows the exact position. The character does not.

`ActualPosition` and `EstimatedPosition` are tracked separately, with error accruing from
dead reckoning, chart quality, current, visibility and operator skill. This is what allows
being genuinely lost.

Built, in `navigation.py`, and the error is not rolled. `speed` here is already speed
through the water — exactly what a log measures — so advancing a dead reckoning by heading
and logged speed *is* the historical procedure, and it diverges from the truth by precisely
the current and the leeway, which the simulation was computing anyway. Being lost is a
consequence of the water moving, not a mechanic laid on top to make navigation interesting.
A ship in slack water is never lost, and should not be.

Taking a fix returns what the reckoning had missed: the vector from the DR position to the
truth, over the time run, is the set and drift she has been carrying. That is real practice,
and it closes a loop — sail, fix, learn the set, and feed it to `course_to_steer` to allow
for it on the next leg.

**Units are display, and there are two of them.** Metres are the unit everywhere inside
the simulation and always will be. What a player is shown is set by
`MARITIME_DISTANCE_UNITS` — leagues, nautical, metric or raw — and separately by
`MARITIME_DEPTH_UNITS`, because a ship reckoned her run in leagues and her water in
fathoms at the same moment, and tying the two together would force one of them to be
wrong. Every distance scheme falls back to cables under a mile: no scheme has a useful
word for a tenth of its own unit, and every one of them borrowed the cable instead.

Soundings are called, not printed. `leadsman_call` reads a depth to the quarter fathom and
gives it the way a hand lead is read — *"By the mark seven"* where the line carries leather
or rag, *"By the deep six"* where it carries nothing, *"A quarter less eight"* for three
quarters over because it is shorter and harder to mishear than the alternative, and *"No
bottom with this line"* past twenty fathoms. The distinction is not decoration: it is the
difference between a depth a leadsman felt and one he counted.

Built, in `charts.py`. A chart covers a rectangle of sea, was made by somebody at a moment,
and is wrong — but **wrong in the same places every time**, because the error is a
deterministic function of the chart's seed and the position rather than fresh noise per
reading. That distinction is the whole feature: noise regenerated on every glance would be
unlearnable, and a navigator could never come to distrust one particular approach. Age
degrades a survey but never to nothing, because the coast stays where it was.

Being *off* the chart is its own state, and reads very differently from having bad
soundings.

Routes, in `routes.py`, are laid over marks a game has authored rather than pathfound across
the seabed. Which waters are passable is knowledge a pilot has and an algorithm does not — a
planner that searched the ground would find every gap a hull could theoretically fit
through, including the ones no master would take at night. Dijkstra over the authored links,
weighted by real distance, planned once and then sailed continuously.

**Progress along a route is state, not geometry.** Deriving it from position — "the first
mark she is not near" — looks right until she reaches the end, at which point the first mark
is the furthest away and she is sent back to the beginning. Tests caught exactly that.

Charts are *knowledge of* the world, not the world. A chart's soundings are surveyed values
against the datum; applying the tide is the navigator's job, and a bad chart is a real
hazard.

Detection depends on range, observer and target height, size, weather, light and sea state.
**Observer height matters** — which is what gives a masthead lookout a reason to exist.
Surface observation is a horizon problem; detecting what is *below* is a different and much
shorter-ranged sense.

Built, in `observation.py`: a horizon of `2.07·√h` nautical miles, a geographic range that
is the *sum* of two horizons, and a detection limit that is the lesser of that and what the
air allows. Height of eye comes from the compartment the observer is standing in, so
building a masthead buys range rather than flavour — proven against a live pair of hulls,
where the same ship at the same instant saw nothing from her deck and a sail 15.9 miles off
from her crosstrees.

One trap worth recording. The default visibility was first set to the conventional ten
nautical miles, which sits *inside* a thirty-metre masthead's horizon of eleven and a
third — so the air would have bound before the curve ever did, and going aloft would have
bought nothing. A sensible-looking default silently deleting the feature it constrains is
the ordinary way this kind of model dies. Clear-weather visibility is therefore set beyond
any reachable horizon, and weather makes it bind later, on purpose.

Detection levels are `CONTACT → VESSEL → CLASSIFIED → IDENTIFIED`, and what a lookout is
told is bounded by the level rather than by what the target is. The engine knows her name
at every range; saying it would make closing to identify pointless.

Contacts progress `UNKNOWN -> CONTACT -> VESSEL -> CLASSIFIED -> IDENTIFIED`, carrying
bearing, estimated range and confidence rather than truth.

**A mark carries a meaning, not just a position.** A buoy with a name and a coordinate tells
a navigator nothing. Real buoyage works because every mark says where the safe water is
*relative to itself*, and that is what lets a helmsman know which side to leave it on:
safe-water marks are passed either side, laterals mark the edges of a channel, cardinals say
"the safe water is on this side of me", and an isolated danger mark sits on the thing itself
with navigable water all round.

**Direction of buoyage is authored, not derived.** Lateral marks are meaningless until
somebody says which way is "in", and no algorithm can work that out about a harbour. A mark
read outbound reverses — it marks the same edge of the same channel either way, and it is the
vessel that turned round.

**Marks are sighted like anything else.** They go through the same horizon arithmetic as
hulls, so a low can drops out of sight long before a beacon does — which is exactly why
landfall was made on lights and steeples rather than on buoys. They are reported *apart from*
shipping, because a sail on the horizon is a question and a buoy on the horizon is an answer.

**The helmsman gives marked dangers a berth by default.** "Berth" here is the sea-room sense,
the one in *give it a wide berth* — the clearance already had a name. The mark decides which
way round, which is the whole reason kinds carry meaning: a cardinal sends her the way it
names even when the cheaper-looking way round is the one with the rock in it. The alteration
shrinks with range, so an early one is small.

**The player is never overruled, only defaulted.** `keep_clear` recommends; it does not seize
the helm. The sailing master acts on it because the con was handed to him, and `belay` takes
it back. Standing into danger has to remain possible — a blockade runner cutting inside a reef
at night is a decision, and a simulation that forbids it is worse than one that lets her
strike.

---

## 10. Crew and authority

Stations accept a player, an NPC or automation through one semantic order API:

```python
ShipOrder(station="helm", action="set_heading", parameters={"heading": 72})
```

Three levels of operation — direct control, orders to crew, and plotted voyage — sit on the
same mechanics. **Solo operation is a baseline case, not an edge case**; a system that only
works with six players online is a system most players never see.

**Ownership is not authority.** Registered owner, current master, command authority and crew
roles are separate concepts. Modelling them as one current-holder field produces an owner who
must be aboard to sail her and a captain who cannot be dismissed, and neither is a ship.

This section used to say authority is evaluated *per capability* rather than held in a slot,
and what shipped holds two: `owner` and `captain`. That is not a retreat from the principle,
it is where the principle actually lives. Two slots are the two facts about a ship the world
needs to agree on — who she belongs to, and whose orders she takes — and a game asking either
question wants an answer, not a permission calculation. **Per-capability authority is the
policy, not the storage.** `MARITIME_COMMAND_POLICY` names one function that decides whether a
character may give a hull an order, and every order in the contrib routes through it. A game
where the mate may steer but not fire replaces that function and is obeyed everywhere without
the vessel knowing it happened.

The default policy is deliberately small: her captain, or her owner if nobody has been
appointed, or **anybody aboard a ship that belongs to nobody**. That last case is not an
oversight. A game that has not adopted ownership at all must still be able to sail, and a boat
drawn up on a beach with nobody's name on her is anybody's to work.

**Rank is derived, never granted.** Hold more than one ship and you are an admiral; lose one
and you are not. A stored rank is a fact that can disagree with the world, and this one changes
every time a ship is bought, sold, taken or sunk — exactly the sort nobody remembers to keep in
step. What an admiral may *do* with a fleet is the game's to decide.

**Ownership moves by event, not by money.** `transfer_ownership` records *why* she changed
hands — sold, granted, captured, inherited — and publishes it. What a ship is worth and who can
afford her is the host game's economy, and a contrib that shipped a price would be arguing
with it.

---

**A company is a number, not a crowd of objects.** A frigate carries three hundred people
and a galley two hundred oarsmen. Creating those as individuals to be counted every tick
would be absurd; named characters aboard remain the host game's, and this counts the rest,
because the rest is what makes her work.

**Crew quality is two claims.** How well they work her, and how much they will take before
they stop. Genuinely separate — a pressed crew who cannot reef in a squall may still be too
frightened of the alternative to run, and a crack crew who can do anything will still not
stand at any price. One "veteran" number loses the more interesting of the two.

**Morale is a standing condition, not a check.** A crew is not asked "do you break?" at
moments of crisis and found steady or wanting; they hold a state that is ground down by
what happens and comes back slowly when it stops. **It falls faster than it rises**, and
that asymmetry is why a captain who spends his people cannot simply stop and have them
back. The curve is exponential in elapsed time, so a tick that runs twice as often does not
tire a crew twice as fast — the simulation must not change when the server gets busy.

**Two collapses, told apart by whose fault it is.** *Striking* is what a crew does when the
enemy has beaten them. *Mutiny* is what they do when the captain has, and every grievance is
something command did — drove them past exhaustion, spent them past bearing and would not
strike, or is not aboard at all. Casualties count as a grievance only while she has *not*
struck: the same crew cut to pieces in a fight their captain ended have been unlucky, and
the difference is whether he would stop. Modelling both as one "morale failure" loses the
only part anybody cares about.

**Both collapses need two gates.** A bad reading is necessary and nowhere near sufficient.
Striking also needs casualties past a floor that scales with quality, so a better crew must
be hurt more before the question is even asked; mutiny also needs agreement, which is more
than one grievance. A roll may be injected for variance and cannot open a gate that is shut
— a die that overrides the systems beneath it is a die that hollows them out.

**Exhaustion is a ship-level state.** How spent the company is, not how tired any person is.
That is the only honest place for it: what a stroke costs a *character* collides with
whatever stamina the host game already has. At ship scale there is nothing to collide with —
she pulls slower and her people are closer to breaking, and both of those are hers.

---

**Command has a succession.** Captain, first mate, officer of the watch, authorised crew,
then voyage automation. A captain who logs out must not freeze the ship — a vessel at sea
with nobody at the helm is a hazard to everyone else on the water, and "the owner is offline"
is not a physical state the sea recognises.

---

## 11. Ports, schedules and services

**A berth has dimensions.** A quay is a length of stone with a depth of water alongside it,
and a ship longer than the berth or drawing more than the water there cannot use it. That
is what makes a berth a place rather than a teleport pad with a nautical name, and it is
where the fit-out tradeoff becomes physical: add capacity, gain draft, lose your home berth.

**Coming alongside has preconditions, checked in the order a ship discovers them.** Free,
then fits, then near enough, slow enough, and lying along the quay. There is no point
telling a captain his approach is too fast for a berth his ship was never going to fit.
Arriving at a stone quay with way still on is a collision, not a mooring, so the speed
threshold is walking pace - the last of a real approach was warped, poled or towed.

**The gangway is an ordinary exit.** Two of them, created when the lines go ashore and
deleted when they are let go. Because it is an ordinary exit it can be followed, blocked,
watched and locked like any other, and none of that needed designing - which is Law 7 doing
its job rather than a docking system reimplementing movement.

Docking creates a real traversal relationship, which undocking removes. A berth has a depth;
a deep-draught vessel at low water may have to wait or anchor off.

**Scheduled routes obey physics.** A timetable is a target, not a guarantee — wind, current
and damage make vessels late, and the delay should be visible in the world rather than
hidden. Departure is `max(scheduled_departure, arrival + minimum_port_call)`, and a route
whose worst-case cycle cannot fit its timetable fails validation rather than silently
drifting a full cycle behind.

### The service abstraction

```python
class MaritimeService:
    def can_execute(self, context): ...   # advisory only
    def execute(self, context): ...       # revalidates, always
```

`can_execute()` answers "can this be offered?" and authorises nothing. Between check and
execution a ship can cast off, a tow can part, a pilot can leave. `execute()` re-checks.

Batch results are **per subject**, never one global boolean:

```python
ServiceResult(success_count=49, failure_count=1, outcomes=[...])
```

One malformed record must not block the other forty-nine, and must never prevent a vessel
casting off.

> **Service principle:** ports, crews, shipyards, pilots and tugs may provide contractual
> services that operate on the physical world. A service executes only while its
> preconditions hold. It may resolve routine transfers atomically where simulating every
> intermediate step adds no gameplay — but it may never override or fabricate a simulation
> outcome.

Services coordinate the simulation. They do not bypass it.

---

## 12. Damage, loss and the water column

Vessels are not one hit-point total. Hull sections, rigging, steering, pumps, weapons and
crew stations are damaged separately, and damage feeds back into performance.

Hull sections have an above- and below-waterline aspect, because a breach below the
waterline floods and one above it does not. Since deck level maps to real Z, water fills
from the lowest compartment upward, and a deepening draught submerges breaches that were
previously dry — which is how a manageable leak becomes a sinking.

**Sinking should be hard to reach rather than rare by intervention.** A hidden "you do not
sink" roll would violate Law 12 and hollow out every system beneath it. Instead the ladder is
long and every rung is answerable: breach, ingress against pumping, list, stability loss,
founder. Running deliberately for shallow water is a legitimate escape — it costs the voyage
rather than the vessel, and it exists only because grounding and sinking share one model.

**The water column is a place.** Divers, sinking objects and settled wrecks hold real
positions. Without this the wreck lifecycle dead-ends at a seafloor nothing can reach, and
salvage becomes content that cannot be played.

**Depth harms by rate, not only by value.** Decompression sickness is caused by ascending
faster than dissolved gas can leave the blood, so a diver who panics and swims straight up
from a survivable depth is injured by the ascent and not by the depth. That makes vertical
*velocity* a quantity the water column has to track, alongside position — the one place in
this design where a derivative of position is itself physical state. Worth recording now
because it is cheap to carry from the start and expensive to retrofit into a model that
only ever stored where things are.

```text
Vessel -> Disabled -> Sinking -> Wreck (afloat / aground / settled at depth)
```

**Vessel destruction is two-phase.** Enumerate occupants and contents, resolve each one's
destination, *persist that resolution*, and only then retire rooms. Interleaved, a crash
mid-loop leaves some occupants moved and others sitting in rooms already marked for deletion.

> **Invariant:** ship rooms are never deleted while occupants or contents remain unresolved.

That invariant cannot be enforced by reading `room.contents`, which is the obvious way to
try. Evennia takes an unpuppeted character off the grid entirely, so an offline passenger is
in no room's contents at all — measured in `docs/logout.md`. `Vessel.ships_company()` is the
list that has to be resolved; walking the compartments finds only whoever happened to be
logged in.

---

## 13. Boarding

Boarding requires acceptable range, manageable relative speed and a valid attachment. Success
creates temporary traversal links between vessel rooms of compatible exposure — you board
onto a deck, not into a flooded hold.

**Speed is not the constraint. Relative velocity is**, and that distinction is the whole of
the manoeuvre:

```text
two ships side by side at 10 kt, same course   ->  0 kt relative, lash at leisure
the same two at 4 kt on opposing courses       ->  8 kt relative, irons out of the rail
```

Matching her course and speed *is* boarding her. Modelling it as a speed limit would make a
chase and an ambush the same problem, and they are not.

**Lines part.** A grapnel that held when she was matched does not hold when she sheers off,
so the attachment is re-tested on the tick rather than granted once. A made-up line takes
more strain than a thrown one — but not much more, so a ship that puts her helm hard over
and fills her sails always breaks free. That is what makes being boarded survivable, and
worth trying to survive.

> **Invariant:** a refused boarding rigs nothing. There is never an exit anybody can walk
> through that the grapples did not earn.

> **Invariant:** both hulls know they are fast to each other, and cutting frees both. A
> one-sided attachment is the first symptom of a much worse bug.

**The crossing is two ordinary exits**, made the same way a gangway is. Law 7 has no special
case for a hostile traversal: crossing to a ship you are boarding is *walking*, so it can be
followed, blocked, watched and locked exactly like walking ashore, and none of that needed
designing twice. `board` is not a command — it is the exit's name.

**Character combat remains the host game's own.** This contrib does not implement a second
humanoid combat system because the fight happens on a ship.

**Striking is a fact, not a transfer.** That she has struck her colours is recorded, and
confers nothing. What a captor may then *do* with a prize — who may give her orders, who
owns her, what becomes of the people aboard — is a question about authority, which is phase
14. Colours can be rehoisted, because a prize crew can be overwhelmed and a state that could
only be entered would make that unrepresentable. In `DECISIONS.md`.

While that fight resolves, the vessels keep drifting, fires keep spreading and flooding keeps
rising. That coupling is deliberate, and it is the main reason tactical pacing is still an
open question.

---

## 14. What the host game decides

The contrib deliberately does not answer these. Each is a seam.

| Decision | Why it is the game's |
| --- | --- |
| World-time ratio | Supplied by the game's own clock |
| Tactical pacing | Depends on the game's command latency and combat feel |
| Offline character policy | Must match the game's death and disconnect rules |
| Tidal range | Depends on authored harbour geometry |
| Skills, combat, economy, progression | Reached through adapters, never imported |
| Prose and message routing | The domain emits results; the game renders them |
| Units shown to players | Metres are internal; leagues, miles or kilometres are taste |

---

## 15. Scope

This is a maritime system. The elevation datum makes flight *representable*, and that is
precisely why the boundary is stated: aerial vehicles, flight physics, projecting land areas
into shared coordinates, and cross-domain visibility are **not** part of this contrib.

Core types are named `WorldPosition` and `WorldLocationResolver` rather than `Maritime*`
because water is the first consumer of this coordinate space, not the only conceivable one,
and neutral vocabulary costs a rename today rather than a refactor later. That is the *only*
concession made to a hypothetical second consumer.

What is explicitly not done: generalising the spatial indexes, movement integration or
physics. A surface-horizon index and a 3D index for free-flying entities are different data
structures, and guessing at the query patterns of a system that does not exist is how
premature abstraction happens. Generalise after implementation proves the seam, not before.

---

## 16. Domain events

The simulation emits events; messaging, AI, quests, economy, logging, reputation and tests
consume them. The list is long on purpose — an event that nothing listens to costs nothing,
and one that does not exist has to be retrofitted through every caller that needed it.

```text
VesselCreated      VesselLaunched     VesselDeparted     VesselArrived
VesselDetected     VesselDocked       VesselGrounded     VesselCollided
WeaponFired        ProjectileHit      HullBreached       FloodingStarted
FireStarted        BoardingStarted    PersonOverboard    VesselCaptured
VesselSunk         WreckCreated       ServiceExecuted    ServiceFailed
```

The event primitives exist (`events.py`); the vessel lifecycle does not emit them yet.

---

## 17. Public API

The long-term stable surface stays narrow. Outside systems reach the simulation through it
and never mutate internal state directly.

```python
maritime.create_vessel()      maritime.get_vessel()
maritime.get_world_position() maritime.issue_order()
maritime.plot_course()        maritime.get_contacts()
maritime.dock()               maritime.undock()
maritime.apply_damage()       maritime.begin_boarding()
```

Nothing here is API-stable yet, and the package exports considerably more than this while
the shape is still being found.

---

## 18. Roadmap

Phases from the north-star specification, with what is actually true of the code. Status is
`done`, `partial` or `—`, and `partial` always says what is missing, because a phase marked
complete while a named deliverable is absent is how a plan stops being a plan.

| # | Phase | Status | Notes |
| --- | --- | --- | --- |
| 0 | Foundation | done | Package, clock, `TimeProvider`, RNG streams, results, events, config, test harness |
| 1 | Coordinates and navigational surface | done | `WorldPosition`, distance, bearing, terrain Z, derived depth, map provider, resolver |
| 2 | Hazard geometry and spatial foundation | done | Indexes, hull footprint, swept envelope, and a tiled seabed whose authored hazards are tested against the whole corridor rather than sampled |
| 3 | Vessel foundation | done | `Vessel`, `VesselTemplate`, `ShipRoom`, creation, persistence |
| 4 | Simulation service | done | Scheduler, fair cursor, dirty tracking, checkpoint, flush, restore, and a measured millisecond budget with the tail wound back on overrun |
| 5 | Basic safe movement | done | Movement, helm, swept grounding against a hull footprint, reload survival |
| 6 | Sailing | done | Wind, relative wind, polar curve, sail plans, leeway, anchoring, set and drift, course and speed made good |
| 7 | Ports | done | Sized berths, approach preconditions, gangway as a real exit, `dock` and `cast off` |
| 8 | Observation | done | Horizon, height of eye, contacts, `lookout`, and a deck that describes the sea outside it |
| 9 | Navigation | done | Dead reckoning, estimated position, error that is the water she could not see, fixes off landmarks, charts that are wrong in fixed places, and routes laid over authored marks |
| 10 | Minimal crew automation | done | The sailing master steers for the next mark allowing for the set, carries what the wind permits, and takes the way off her at the end |
| 11 | Strategic representation | — | Strategic records, analytical travel, materialisation, benchmarks at 100/500/1000 |
| 12 | Weather and sea state | done | One provider supplies wind, visibility and sea state together; the sea follows the wind by default and slows her |
| 13 | Sparse ocean projection | done | A pooled room per occupied cell, rooms as views rather than locations, a lone drifter panning its own room, drift by current and windage, and a second narrator for the water |
| 14 | Crew and authority | — | Roles, staffing, skill hooks, command succession |
| 15 | Tactical geometry | partial | Range, bearing, aspect, closure, arcs and `target` are built. The pacing decision is recorded in `DECISIONS.md` and is Gary's |
| 16 | Weapons | done | Generic mounts, reload clocks, time of flight, aiming off, and a hit chance built from range, sea and aspect. Damage is phase 17 and is not touched |
| 17 | Damage | — | Hull sections, breaches, flooding, fire, repair, sinking, occupant transition |
| 18 | Boarding and capture | partial | Grapples, relative velocity, lines that part on the tick, the crossing as two ordinary exits, and striking as a recorded fact. Control transfer is authority and is recorded in `DECISIONS.md` |
| 19 | Strategic maritime world | — | Merchants, patrols, pirates, fishing, strategic encounters |
| 20 | Standing orders | — | Conditions, priorities, conflict resolution, replanning |
| 21 | Passenger services | — | Timetables, cycle validation, fares, contracts, manifest, purser, disembarkation |
| 22 | Cargo economy | partial | Commodities, stowage factors, holds, both capacities, loading and discharge, and the four consequences of load. Contracts, prices and trade are the game's and are recorded in `DECISIONS.md` |
| 23 | Service expansion | — | Pilots, tugs, provisioning, repairs, shipyards |
| 24 | Ownership and customisation | — | Purchase, sale, upgrades, refits, interiors, cosmetics, player homes |
| 25 | Wrecks and salvage | — | Wreck lifecycle, drift, survivors, floating cargo, tow, salvage |

**Two deliberate departures from the plan's order.**

Observation was built before ports. The spatial indexes had been written in Phase 2 and had
never had a caller, and observation was what needed them; ports need authored harbour
geometry that the test world does not yet have. Building the phase the code was ready for
beat building the one with a dependency outstanding.

Grounding was pulled forward into Phase 5, where the plan already put it — movement is not
finished until the seabed can stop it, and shipping "the ship moves" without that would have
meant calling a phase done that could sail through an island.

---

## 19. The first vertical slice

The gate that says the architecture works. Not a feature list — one continuous act:

```text
walk onto the sloop → cast off → make sail → sail continuous water
→ read the seabed rising ahead → ground on the shoal, or hold the channel
→ raise Harbour B → dock → walk ashore
```

No Wilderness, no combat, no pirates, no passenger economy. The player is in ordinary
Evennia rooms throughout, and at no point does open water require `east east north east`.

**Reached.** Walked aboard at Harbour A, cast off, made sail, sailed continuous water,
sounded nine and a quarter fathoms in the channel south of a rock ledge that would have
opened her, came alongside at Harbour B — made fast at fishmarket steps, starboard side
to — and walked ashore. No ocean rooms were traversed, the wind decided the passage, the
current set her off her course, the seabed decided the route, and the player was in
ordinary Evennia rooms throughout.

Two defects surfaced during that passage that no unit test had caught, both recorded below
and both fixed. A slice is worth running for that reason and not for the screenshot.

**First-voyage acceptance**, and the arithmetic the whole clock design exists to make true:
20 nautical miles at 8 knots is 2.5 game hours — 37.5 real minutes in a game running 4:1,
two and a half hours in one running 1:1, and milliseconds under `ManualTimeProvider`. The
contrib states the distance and the speed; the host game's clock decides the rest, which is
Law 1 seen from the acceptance end. The tests must show
a neutral current arriving on time, a favourable one early, an adverse one late, poor sail
later still, the shoal crossing grounding her and the channel not.

Five of the six are written. The last needs a channel, which needs a harbour to lead to.

---

## 20. Scenario suite

Named scenarios, each a runnable integration test rather than a unit test. They live in
`tests/test_scenarios.py` and the names below are the method names, so "which of these
actually run?" has an answer that is not somebody's memory.

```text
sailing-basic ✓        sailing-upwind ✓       current-drift ✓
grounding-shoal ✓      grounding-reef ✓       safe-channel ✓
dock-undock ✓          reload-underway ✓      route-following ✓
scheduler-fairness ✓   strategic-advance      materialize-dematerialize
contact-detection ✓    navigation-error ✓     storm-delay ✓
collision              broadside ✓            flooding
fire                   boarding ✓             capture ✓
passenger-arrival      passenger-diversion    passenger-capture
service-partial-failure                       charted-approach ✓
```

The ticks used to mean "the capability is built and has unit tests". They now mean "there
is a named voyage that runs it end to end", which is a different and stronger claim — and
making it true found two defects that every unit test in the suite had passed over:

- **The sailing master never stopped.** He handed back the con at the last mark and left
  her under working canvas with her last helm orders, so she sailed twelve kilometres past
  it. Ordering no speed stops a boat under oars and does nothing at all to one under sail.
- **The dead reckoning has a third source of error**, besides the current and the leeway
  this document names. The log is read at the end of a step, so the reckoning over-counts
  while she is working up — about thirty metres for a sloop from rest. It is a realistic
  artefact rather than a bug, and it was being claimed away.

`charted-approach` is not on the design's original list and should have been: that a chart
is wrong in *fixed* places rather than randomly is the one part of navigation where correct
behaviour looks like a bug.

The unbuilt ones are unbuilt because their phases are: flooding, fire and collision are
damage; strategic-advance and materialize are phase 11; the passenger and service scenarios
are phases 21 and 23. A scenario that pretended to exercise them would be worse than a gap.

---

## 21. Invariants

Things that must never be true, whatever else changes. Each one is a bug class rather than a
rule of the fiction.

```text
positions are finite; velocity is never NaN
depth derives from surface minus terrain, never from a stored depth field
a sunken vessel cannot sail
a docked vessel cannot translate freely
a destroyed component cannot operate normally
every berth is reachable from open water by way of marks
every charted danger carries a mark that warns of it
flooding is never negative
a boarding link requires two valid vessels
a gangway requires a valid docking relationship
the strategic scheduler cannot starve a vessel
execute() always revalidates its preconditions
passenger discharge never unloads hold cargo
ship rooms are never deleted beneath unresolved occupants
ordinary land rooms need not have maritime coordinates
```

---

## 22. Performance goals

The architecture should plausibly carry hundreds to thousands of strategic vessels, dozens
of active ones, and several simultaneous tactical interactions — without thousands of live
rooms, thousands of tickers, a database write per second, O(n²) vessel comparisons, or a
synchronous full-fleet sweep.

Real limits come from benchmarks, not from this paragraph. Measured so far: 250 vessels at a
batch of 10 gives a full fair sweep in 25 passes with every vessel updated exactly once.

Two known O(n²) shapes are live and deliberate: the spatial indexes are linear scans, and
every vessel scans for contacts every tick. Both are fine at harbour scale and both sit
behind interfaces that do not change when the structures do.

---

## 23. Open questions

Questions raised while building, with what was done in the meantime, live in `DECISIONS.md`
at the repository root. This section is the design's own list; that file is the working one.



Unresolved on purpose. Recording them beats settling them badly.

**The reactor budget is answered** and has moved out of this list — see
`docs/performance.md`. A fixed batch of 25 turned out to cost anywhere between 6.5 ms and
33 ms depending on the world, which is the whole argument for bounding a pass by a clock
rather than by a count. `MARITIME_TICK_BUDGET_MS` defaults to 10 ms. Measuring it also
found two bugs that reading the code would not have: `monotonic` is too coarse on Windows
to see a ten-millisecond budget at all, and the map provider was being rebuilt on every
call, discarding its tile cache each time.

**LOGOUT-001 is answered** and has moved out of this list — see `docs/logout.md`, with the
behaviour pinned in `tests/test_logout.py`. The headline: an unpuppeted character is taken
off the grid entirely, so `room.contents` is *not* the list of people aboard, and no leave
hook fires. Reconnect restores the room, and because a compartment holds no position that
restores the right position for free. A deleted room sends offline passengers home,
silently, which is a policy nobody chose.

**Tactical pacing.** Does close-quarters play stay at the host game's time ratio, or slow?
At 4:1 a player may not have the reaction time for close manoeuvring, collision avoidance or
a boarding approach. World travel stays tied to world time regardless; only tactical pacing
is in question.

**Offline loss policy.** What becomes of an offline player aboard a vessel that founders.
Game policy, not engine behaviour, but the engine has to expose the seam.

**Long-downtime catch-up.** How much strategic time to reconcile after a prolonged outage.
Capped at an hour today, which is a placeholder and not an answer.
