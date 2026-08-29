# Changelog

All notable changes to the Maritime contrib.

Entry prefixes follow Evennia's own changelog convention (`Feat:`, `Fix:`, `Docs:`,
`Chore:`) so that entries slot in naturally if this contrib is merged upstream.

## Unreleased

Nothing released yet. Foundations and the spatial model are in place; no vessel
simulation exists yet.

### Feat

- Wire motion into the vessel and add helm commands: `helm`, `speed`, `allstop`
  and `position`. A vessel under way is advanced by the simulation service, and
  movement never touches the database - it updates in memory and is checkpointed,
  as position changes many times a minute. Commands take and report knots while
  the domain works in metres per second throughout, so display units stay out of
  the physics and a game preferring other units changes one file.
- Add the vessel motion model. Orders are targets, not instructions: the helm asks
  for a heading and the hull swings towards it at whatever her rudder and speed
  allow, which is most of what makes handling a ship feel unlike driving a cursor.
  Turn rate scales with speed, so a vessel dead in the water cannot steer at all
  and losing way is a real problem rather than an inconvenience. Motion integrates
  in fixed sub-steps, so a turning vessel carves an arc instead of pivoting on the
  spot and running the distance on her new heading - and the track comes out the
  same whether the scheduler ran once or sixty times, so a laggy server does not
  quietly put ships somewhere else. Adds `bearing_difference`, which turns the
  short way round: naive subtraction sends a vessel almost all the way round the
  compass to make a twenty-degree alteration across north.
- Add the simulation service and its fair scheduler. One service drives everything
  rather than a ticker per vessel - partly for cost, partly because Evennia's
  TickerHandler keys subscriptions on callback, interval and idstring but not on
  arguments, so a fleet subscribing one method at one interval silently overwrites
  itself and most ships just stop moving. Work is tiered (dormant, strategic,
  active, tactical) and each pass is bounded, resuming from where it stopped, so a
  large fleet lengthens the revisit interval instead of blocking the reactor. The
  rotation keeps its cursor across passes: restarting from zero looks fair but
  starves everything past the budget. Catch-up is capped, so a server down for a
  week does not hand a vessel a week of movement in one step. A failing update or
  checkpoint is logged and skipped rather than stopping the fleet.
- Add the `Vessel` and `ShipRoom` typeclasses. A compartment holds no position; it
  names its vessel, and the resolver walks through to whatever the hull reports, so
  moving a ship moves everyone aboard at once with no bookkeeping. Position lives
  in memory and is checkpointed on reload, on shutdown and on demand rather than
  written on every change: each `.db` assignment is a pickle and a commit, and a
  vessel under way updates constantly. An unchanged vessel skips the write
  entirely, so a fleet at anchor costs nothing to checkpoint.
- Add vessel templates, capacity and deck plans. A ship class is data, not a
  subclass - changing a sloop's beam is editing a number, so no `Sloop` class
  exists anywhere in the contrib and a game can define its own hulls importing
  only `VesselTemplate`. Deck levels are integers relative to the main deck, so
  they map straight onto elevation and flooding can fill from the lowest
  compartment upward without a separate model of which room is under which.
  `VesselCapacity` and deck slots are declared now although nothing consumes them
  yet: they are what make later fit-out a set of trade-offs rather than a shopping
  list, and adding them after templates exist means rewriting every template.
- Add `ContactIndex` and `ProximityIndex`. Two indexes rather than one, because
  the difference is geometry and not tuning: horizon range is a surface question,
  so contacts ignore elevation, while boarding is not, so proximity measures true
  distance and a diver thirty metres beneath a hull is correctly nowhere near it.
  Both produce candidates, never answers - whether a hull can actually be seen
  depends on weather, light and height of eye, none of which an index knows.
  Entities in other regions are never candidates, since regions are separate
  coordinate spaces. Currently a linear scan: with no vessels yet there is nothing
  to index, and picking a structure now would mean guessing at query patterns that
  do not exist. The interface is what matters, and the structure behind it is
  replaceable without a caller noticing.
- Add the world-position resolver. Every subsystem asks `get_world_position()`
  rather than working the answer out itself, because the answer is rarely direct:
  a character aboard a vessel has a cabin, which belongs to a hull, which is the
  thing that actually sits somewhere. An entity joins world space by declaring
  either a `maritime_position` or a `maritime_position_source` to ask instead;
  otherwise ordinary `location` is followed. A declared source outranks location,
  so a docked vessel's interior resolves to the hull and not the harbour room.
  Anything outside the maritime world returns `NoWorldPosition`, a falsy singleton
  rather than `None`, so absence cannot be quietly treated as a coordinate.
- Add terrain elevation, tides and derived water depth. There is no depth map -
  one terrain field crosses zero, and depth is the difference between the current
  water surface and the ground beneath it, computed rather than stored. Sea level
  is a datum, not a constant, so moving the surface changes every depth in the
  world without touching terrain: a bank can dry out at low water and flood as the
  tide rises. Depth queries require a game time, since a depth without one asks
  about the datum rather than the water actually present. `FlatTideProvider` and
  `FlatSeaMapProvider` give a game vessels before it needs bathymetry.
- Add `WorldPosition`: continuous three-axis coordinates, where z is elevation
  relative to the sea-level datum. One field covers land, sea surface and seabed,
  so tides, grounding and shorelines derive from a single model rather than three.
  Bearings are compass bearings - north is 0, east is 90, increasing clockwise -
  which is deliberately not the convention `math.atan2` uses. Horizontal and true
  distance are separate methods, because a diver forty metres below a hull is
  nearly zero metres away for navigation and forty for proximity. A region is a
  coordinate space rather than a label: a lake and an ocean may both have a point
  at (0, 0), so operations across regions raise instead of returning a
  meaningless number. Non-finite coordinates are refused at construction.
- Add settings resolution. Games configure maritime from their own `settings.py`
  using `MARITIME_`-prefixed names, never by editing contrib source.
  `MARITIME_TIME_PROVIDER` takes a dotted path so a game can substitute its own
  clock, and `MARITIME_RNG_SEED` pins the master seed for a reproducible run.
  A configured class that is the wrong type fails at load with a message naming
  the setting, rather than surfacing later as a missing attribute. Defaults are
  derived from `__package__`, so they resolve wherever the package actually lives.
- Add domain events and `EventBus`. The simulation announces what happened without
  knowing who listens; messaging, AI, quests, economy, logging and tests subscribe.
  Subscribing to a base event type also receives its subtypes, so a logger can take
  everything with one registration. A handler that raises is logged and skipped
  rather than propagating - a quest script with a bug must not be able to stop a
  vessel from sinking. Delivery iterates a snapshot, so a handler subscribed while
  an event is being delivered does not receive that same event.
- Add `Result`, the structured return value for every domain operation. Frozen and
  keyword-only; a failed result must carry a machine-readable code, so a caller
  always has something to branch on and a renderer always has something to
  translate. Deliberately has no free-form details dictionary.
- Add `RNGContext` and named random streams (`navigation`, `combat`, `damage`,
  `weather`, `ai`). A run replays exactly from its seed, and streams are
  independent so draining one does not shift another. Stream seeds derive from
  SHA-256 rather than the builtin `hash()`, which is salted per process and would
  lose reproducibility across a server restart.
- Add the maritime clock: `MaritimeTimeProvider` interface, `GameTimeProvider`
  reading the host game's own clock via `evennia.utils.gametime`, and
  `ManualTimeProvider` advancing only when told to. Maritime never scales time
  itself, so a vessel's speed means the same thing at any `TIME_FACTOR`.

### Docs

- Add `CHANGELOG.md` and record the changelog and commit-message discipline in
  `CLAUDE.md`.
- Add `docs/architecture.md`: the architectural laws, the shared elevation datum
  for land, sea and seabed, vessel representation tiers, fair scheduling, the
  sailing model and the service abstraction. Written game-agnostic - where a
  decision belongs to the host game, it names the seam rather than choosing.
- Add `CLAUDE.md` recording Evennia's contrib guidelines as binding working rules,
  including package layout, the format-sensitive README, testing requirements,
  code style taken from Evennia's own linter config, the core-Evennia-only
  dependency policy, and a 1000-line ceiling per source file.
- Record engine behaviour that Python fluency alone does not protect against:
  typeclass names are unique server-wide, tickers must never poll for changes,
  ticker subscriptions collide without distinct idstrings, and attribute reads
  are cheap while writes and nested mutation are not.
- Document the dual target - merged upstream, or used standalone - and make the
  tutorial zone a deliverable rather than optional polish.

### Chore

- Add CI running `black`, `flake8`, project discipline checks, and the unit tests
  on Python 3.12 and 3.13 with the contrib installed at its canonical import path.
- Add `check_discipline.py` enforcing the rules no general tool knows about: the
  file-size ceiling, the dependency policy, README shape, domain purity (no
  player-facing prose outside the messaging layer), and location independence
  (no absolute self-imports, so the contrib also works standalone).
- Ignore credential and environment files. They belong in the game directory, not
  in this public repository.
- Scaffold the contrib package at `evennia/contrib/full_systems/maritime` with the
  structure the contrib guidelines require. Licensed BSD 3-Clause to match Evennia.
  Line endings normalised to LF so commits made on Windows do not read as
  whole-file rewrites upstream.

### Fix

- Correct the dependency rule and a false positive in its check. Evennia's own core
  dependencies (PyYAML, simpleeval, inflect, the test helpers) ship with Evennia, so
  importing them costs the user nothing - but `import yaml` was failing the build.
