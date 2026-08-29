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

That layer is `messaging.py`, and it answers two questions the simulation does not: which
change is worth mentioning, and who hears it. The first is why narration state lives there
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

---

## 7. Simulation and persistence

One scheduler. Never a ticker per cannon, mast, ship or fire.

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

---

## 9. Navigation and observation

The engine knows the exact position. The character does not.

`ActualPosition` and `EstimatedPosition` are tracked separately, with error accruing from
dead reckoning, chart quality, current, visibility and operator skill. This is what allows
being genuinely lost.

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
roles are separate concepts, and authority is evaluated *per capability* rather than held in
a single slot. Modelling it as one current-holder field produces a mate who "has command" and
cannot do most of what command implies.

---

## 11. Ports, schedules and services

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

---

## 13. Boarding

Boarding requires acceptable range, manageable relative speed and a valid attachment. Success
creates temporary traversal links between vessel rooms of compatible exposure — you board
onto a deck, not into a flooded hold.

**Character combat remains the host game's own.** This contrib does not implement a second
humanoid combat system because the fight happens on a ship.

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
