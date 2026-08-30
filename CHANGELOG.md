# Changelog

All notable changes to the Maritime contrib.

Entry prefixes follow Evennia's own changelog convention (`Feat:`, `Fix:`, `Docs:`,
`Chore:`) so that entries slot in naturally if this contrib is merged upstream.

## Unreleased

Nothing released yet. Foundations, the spatial model, vessels, the simulation
service, sailing and grounding are in place; ports, navigation, weather, crew,
combat and damage are not.

### Feat

- Add charts, which are knowledge of the sea rather than the sea. A chart covers
  a rectangle, was made by somebody at a moment, and is wrong - but wrong in the
  *same places every time*, because the error is a deterministic function of its
  seed and the position rather than fresh noise per reading. Noise regenerated on
  every glance would be unlearnable; this way a bad patch is a place on the paper
  and a pilot who has caught it out once knows to sound there.
- Charted soundings are given at the datum, never at the present tide. Applying
  the state of the tide is the navigator's job, and doing it for them would
  remove the commonest way a careful sailor still goes aground.
- Being off the chart is its own state. A vessel outside her coverage has no
  soundings at all, which reads very differently from having bad ones.
- Add routes: marks a game has authored, and Dijkstra over the safe water between
  them, weighted by real distance. Which channels are passable is knowledge a
  pilot has and an algorithm does not - a planner that searched the seabed would
  find every gap a hull could theoretically fit through, including the ones no
  master would take at night.
- Add `chart` and `plot`, and `MARITIME_NAVIGATION_NETWORK` for a game to lay its
  own marks. Phase 9 is complete.

- Add `scan`, which sweeps the whole horizon quarter by quarter and names the
  empty quarters as well as the full ones. A lookout who only mentions what he
  can see leaves you unable to tell "nothing there" from "nobody looked".
- `look <direction>` reports one quarter or compass point - `look fore`, `look
  port`, `look se`. Ship-relative directions turn with her and compass
  directions do not, which is the difference between watching the port bow and
  watching the headland.
- Add `watch <direction>`, a standing watch that tells you when something lifts
  over the horizon that way and when it sinks again, instead of looking every few
  minutes. Kept from where you are standing, so one set at the masthead sees
  further than one set on deck.
- Directions can be typed the way people type them: `se`, `south east`,
  `south-east` and `southeast` are one direction, and `stbd`, `astern` and
  `larboard` all resolve.
- Contact reports now carry both bearings, the range and what she is - bounded by
  what the range allows, so a hull at the edge of vision stays "a sail" even
  though the engine knows her name. An empty sector says how far it can see,
  because "nothing in sight" is unbounded otherwise.

- A weather deck now describes the sea outside it. The room's own description
  says what is nailed down; appended to it is what is happening - how she is
  moving, the wind by its Beaufort force, whether the water is setting, and what
  the lookout can see. Static rooms, moving world, which is what lets a ship be
  ordinary Evennia rooms and still feel like she is at sea.
- Nothing is invented for it: her motion, the wind, the current and her contacts
  were all already being computed, and this is the one place they are put into a
  sentence.
- The view uses the height of eye of the compartment you are standing in, so the
  same look from the deck and from the masthead can honestly disagree about
  whether there is anything out there. Demonstrated live at 29.8 km: "Nothing
  breaks the horizon" on deck, "A sail stands on the port beam" aloft.
- Add the Beaufort scale. The arithmetic is in `sailing.py` and the names are in
  `messaging.py`, because what a force 7 is *called* is prose - "near gale" and
  "the sky gone the colour of a bruise" are the same measurement.

- Grounding now tests a hull's footprint along her whole track instead of one
  point where she ends up. This was the largest known gap between the
  architecture doc and the code, recorded in both for several phases: a fast
  vessel could step clean over a reef narrower than one tick of her movement,
  and the faster she went the more of the seabed she was entitled to ignore -
  precisely backwards, since speed is what makes grounding expensive.
- A hull is seven points in a rough ship shape rather than a rectangle, because
  a rectangle puts steel where a ship has none. Her bow can ground while her
  centre is still in deep water, which is what a large ship actually does.
- She is stopped at the first thing she touches rather than at the end of the
  move. A ship that struck a reef a third of the way through a tick did not
  travel the other two thirds.
- Demonstrated live: a hull making 25 m/s asked to run 750 metres across 400
  metres of rock. The old point test at her destination reported clear water; the
  swept test stopped her one metre short of the ledge.

- Add dead reckoning, and with it the possibility of being genuinely lost. A
  vessel now carries an estimate of her own position, advanced by the course
  steered and the distance logged and by nothing else - which is what a
  navigator with a compass and a log line actually has.
- The error is not rolled. `speed` is already speed through the water, so a
  reckoning advanced by heading and logged speed diverges from the truth by
  exactly the current and the leeway, both of which the simulation was computing
  anyway. A ship in slack water is never lost and should not be; the sea makes
  you lost.
- Add `fix`, which takes a bearing on a landmark of known position. It reports
  what the reckoning had missed - and the difference between where you thought
  you were and where you are, over the time run, is the set and drift you have
  been carrying. That is the input `course_to_steer` was written for, and the
  loop closes.
- Players are shown `reckoned_position`; the true position stays with the engine
  and with staff tools.

- Add ports, and with them the first true vertical slice. A berth has a position,
  a line to lie along, and dimensions - length, beam and the depth of water
  alongside - so a hull that has been fitted out until she draws another half
  metre may no longer fit her home berth. Coming alongside is checked in the
  order a ship discovers it: berth free, ship fits, near enough, slow enough,
  lying along the quay.
- The gangway is two ordinary Evennia exits, made when the lines go ashore and
  deleted when they are let go. Being ordinary exits they can be followed,
  blocked, watched and locked like any other, which is Law 7 doing its job rather
  than a docking system reimplementing movement.
- Add `PortRoom`, quayside room space that also stands somewhere on the water -
  the one place the two coordinate systems meet. Add `dock` and `cast off`, and
  `Vessel.length` and `Vessel.beam`, which berth fitting needs now and hull
  footprints will need later.
- A vessel now keeps her own list of compartments rather than querying for them.

- Add currents, the last named deliverable outstanding from the sailing phase.
  A vessel is now carried by the water in addition to whatever she makes through
  it, so her heading and her track are different questions and only the second
  one gets her anywhere. `currents.py` carries set and drift, course and speed
  made good, and `course_to_steer` - the navigator's triangle, which genuinely
  has no answer when the stream is stronger than the vessel and returns None
  rather than a heading that quietly does not work.
- A current is named for where it goes and a wind for where it comes from. Both
  conventions are kept. Normalising one to match the other is how a bearing ends
  up reversed deep inside a passage calculation.
- `speed` remains speed *through the water*, which is what a chip log measures,
  and the over-ground figures are derived. The current therefore never has to be
  subtracted back out of anything, and the difference between the two is
  reportable - which is most of what navigation is.
- Add `current`, reporting set, drift, and the course she is making good as
  against the one she is steering. Add `MARITIME_CURRENT_PROVIDER` for a tidal
  stream, and `MARITIME_CURRENT_SET` / `MARITIME_CURRENT_DRIFT` for a game that
  wants one steady set without writing a class.
- Add `environment.py`: wind, current, visibility, clearance and what is in sight,
  as functions of a position rather than methods on a hull. A swimmer, a raft and
  a wreck are subject to the same weather and the same water, and none of them
  are vessels.

- Distances and depths are now reported in units a game chooses, defaulting to
  the ones the subject matter used. `MARITIME_DISTANCE_UNITS` takes `leagues`
  (the default: cables, sea miles, then leagues), `nautical`, `metric` or `raw`;
  `MARITIME_DEPTH_UNITS` takes `fathoms` (the default) or `metres`. The two are
  separate on purpose - a ship reckoned her run in leagues and her water in
  fathoms at the same moment. Metres remain the unit everywhere inside the
  simulation.
- Soundings are called the way a lead line is actually read. `leadsman_call`
  reads a depth to the quarter fathom and gives it as `"By the mark seven!"`
  where the line carries leather or rag, `"By the deep six!"` where it carries
  nothing, `"A quarter less eight!"` for three quarters over, and `"No bottom
  with this line!"` past twenty fathoms. Two fathoms is `"By the mark twain!"`,
  which is where Samuel Clemens got the name. Verified live against a
  game-supplied seabed at four depths.
- `GroundingResult` now carries the depth it measured as well as the clearance.
  They are different questions: a leadsman reports what his line finds and knows
  nothing about the draft of the ship he is standing on.

- Add observation. Detection at sea is a height problem before it is a range
  problem: a hull is hidden by the curve of the water, so how far you can see is
  decided by how high your eye is, and how far you can see *a particular thing*
  by how high that thing is as well. `observation.py` implements the horizon
  (`2.07·√h` nautical miles, the figure a navigator uses, refraction already
  folded in), geographic range as the sum of two horizons, and a detection limit
  that is the lesser of that and what the air allows.
- Height of eye comes from the compartment an observer is standing in, so a
  masthead is worth building rather than worth mentioning. Proved live: one ship,
  one instant, nothing in sight from her deck and a sail 15.9 miles off from her
  crosstrees.
- Add `traffic.py`, the register of who is on the water. The first thing here
  that is not about a single vessel, and the first user of the spatial indexes,
  which had been written and never called.
- Add `lookout`, which reports what can be seen from where you stand - where to
  look, how far off, and only as much as the range allows. Contacts run
  `CONTACT → VESSEL → CLASSIFIED → IDENTIFIED`; the engine knows her name at any
  range and does not say it, because otherwise closing to identify is pointless.
- Sightings are cried as they happen: a new sail, one lost below the horizon, and
  one close enough to tell something new about. A ship at anchor or aground still
  keeps a watch.
- Add `format_range`, which reports distance in cables under a mile and miles
  above it, because ranges at sea are estimates and "three cables" reads as one
  where "555 metres" does not.

- Split the speaking layer out of the `Vessel` typeclass into `messaging.py`, and
  make it a configured seam. Law 11 said the domain returns data and a separate
  layer renders it; the prose was in fact welded into the typeclass, so the
  README's claim that a game could replace every word without touching the
  simulation was not true. It is now: `MARITIME_NARRATOR` points at a
  `VesselNarrator` subclass, every line a vessel speaks passes through one
  `phrase_for` method, and a game that overrides only the words still inherits
  the transition logic that decides when to say them.
- Deciding *when* to speak now lives with the narrator rather than the hull,
  because it needs to know what was last said - a property of the conversation,
  not of the ship.

- Add grounding. A hull finds the bottom when terrain intersects her envelope -
  keel clearance is the water surface less her draft, less the ground beneath -
  so shoals and reefs need no special representation beyond the terrain already
  having the right shape. Clearance is a continuous value, not a yes-or-no,
  because knowing you have four metres and losing one a mile is what lets a
  navigator decide; discovering you have grounded does not. Bottom type decides
  what it costs: sand holds her and the tide usually gives her back, rock struck
  with way on opens her. Adds `sound`, a shoal warning from the leadsman, and
  `MARITIME_MAP_PROVIDER` so a game supplies its own seabed.
- A surface vessel's elevation is now set by the water rather than integrated, so
  she cannot be sailed to the seabed by assigning a negative z. That was
  previously possible and silently meaningless.
- Add sailing. Wind, a data-driven polar curve, sail plans and leeway, so speed
  stops being something you order and becomes something you negotiate: a vessel
  makes what the wind on her heading allows, which head to wind is nothing at all.
  Wind is named for where it blows *from*, as every chart and sailor names it.
  Leeway sets her off her heading, worst close-hauled - which is why dead
  reckoning goes wrong to windward. Adds `sail`, `wind`, `drop anchor` and
  `weigh anchor`, with period orders and crew replies.
- Add position formatting, so players read a position rather than coordinates.
  Latitude and longitude in degrees and decimal minutes, which works out cleanly
  because a nautical mile *is* one minute of latitude by definition - northing
  divided by 1852 needs no fudge factor. Longitude keeps the same scale rather
  than narrowing towards the poles: this world is a plane, and a cosine
  correction would make the displayed position disagree with the distance
  actually sailed. Kept in the messaging layer rather than on `WorldPosition`,
  since a fantasy game may reckon in leagues and a sci-fi one will not use
  latitude at all. `MARITIME_ORIGIN_NORTHING` and `MARITIME_ORIGIN_EASTING` place
  the world's origin on the globe; `MARITIME_POSITION_STYLE` chooses the
  presentation. Raw coordinates move to a new staff-only `@maritime` command.
- Add the driver script, the helm command set, and reporting to the ship's
  company. `MaritimeDriver` is one repeating script for the whole game that ticks
  the service and checkpoints periodically - without it everything below is
  inert. Orders are called out loud and answered using real helm procedure:
  courses are spoken digit by digit ("Helm, steer 0-9-0"), the helm repeats the
  order back, and reports again when the vessel is steady on it. Ambient
  reporting describes *transitions* rather than conditions, so a turn is
  announced once and on completion instead of every tick, and what reaches a
  person depends on their compartment's exposure - on deck you watch the sea go
  by, below you feel her heel and hear water on the planking.

### Fix

- Progress along a route is carried rather than derived from position. Taking
  "the first mark she is not near" looks right until she reaches the end, at
  which point the first mark is the furthest away and she is sent back to the
  beginning of the passage. Found by the tests before it ever ran.

- A vessel could not find her own compartments after `ShipRoom` moved module.
  Evennia stores a typeclass as a dotted path and the manager filters on that
  *string*, so `ShipRoom.objects.all()` returned nothing for every room created
  before the move - while the rooms themselves loaded perfectly. A ship with
  compartments behaved exactly like a ship with none: no lookout height, no
  messaging, no gangway. The re-export kept them resolving and could not keep
  them queryable. Vessels now hold their own compartment list, which fixes it,
  removes a full table scan that ran every tick, and does not care what string
  is in the row. `Vessel.reattach_compartments()` rebuilds the list by type for
  anyone upgrading.
- Set a compartment's ship with `room.vessel = hull`, not `room.db.vessel`. The
  link has two sides now and only the property maintains both.
- A vessel stopped dead and head to wind could never come round. Backing a
  headsail turns a stationary ship - that is the entire manoeuvre - but the
  recovery was written as a raised turn *rate*, and turn rate is scaled by speed
  because it models a rudder. Multiplied by zero speed it gave zero turn. Docking
  at a north-facing berth in a northerly parked a ship permanently. `advance()`
  now takes a `turn_floor` that is not speed-scaled, which is the honest way to
  represent anything that turns a hull without water over the rudder: a backed
  sail, a sweep, a warp, a tug. Found by sailing the vertical slice; no unit test
  had ever started a vessel at exactly zero.

- Tests now assert the neutral world they describe rather than inheriting the
  dev game's. Twice now a game has configured something - a seabed, then a
  current - and tests that had never mentioned it started quietly measuring it
  instead of the flat, still, empty sea they claim to test. `EmptySeaMixin` now
  neutralises ground, stream and wind alongside clearing the traffic register,
  so the next thing a game configures cannot do it a third time.

- A vessel stemming the tide exactly no longer reports a nonsense course. The two
  velocities cancel to a residual of about 1e-16 rather than to zero, and asking
  `atan2` for the direction of that residual returned a confident, meaningless
  bearing - a ship reported as making good due south while sitting motionless.
  A nanometre a second is not a course.

- A deleted vessel now leaves the traffic register. It is memory rather than a
  foreign key, so nothing removed her when her row went, and a hull that sank and
  was deleted would have stayed visible on the horizon indefinitely. Found by
  test pollution, which is the same defect wearing a different hat.

- Remove two unused imports from the grounding tests. Caught by CI rather than
  locally, because the local check before that push was the discipline script
  alone and not the linters CI also runs. The three commands that make up the
  gate are now written down in `CLAUDE.md` as one gate.

- A vessel that turned too close to the wind was trapped for good: she lost drive,
  losing drive cost her steerage, and without steerage she could not turn back out.
  The trap is authentic - it is what being in irons means - but a hull nothing can
  recover is a broken ship rather than a hard one. A crew with canvas aloft can now
  back a sail to shove her bow round, which is what a real crew does. With sails
  furled she remains genuinely helpless, as she should be.

- `WorldPosition.__str__` now shows millimetres rather than a single decimal.
  Coordinates were always full 64-bit floats and collision, grappling and
  boarding always read them directly, but the display hid that from the one view
  a developer uses to work out why two hulls did or did not touch.

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

- Carry the north-star roadmap into `docs/architecture.md`. The doc described the
  design well and said almost nothing about the plan: twenty-six phases, the
  vertical-slice gate, the named scenario suite, the invariant list, the
  performance goals and the open questions were all in the specification and none
  of them were in the repository. Each phase now carries its real status, and
  every `partial` names what is missing - a phase marked complete while a named
  deliverable is absent is how a plan stops being a plan.
- Record what the doc describes and the code does not: navigational tiling, hull
  footprints and swept grounding detection, domain event emission, and the narrow
  public API. Each is marked unbuilt where it is described rather than only in a
  limitations list somebody has to go and find.
- State plainly that currents are not implemented. They are an input to the
  documented sailing model and a method on the documented map provider
  interface, and they are neither - so a passage takes the same time whichever
  way the water is moving, and three of the six first-voyage acceptance tests
  cannot be written. Sailing is marked partial accordingly.
- Note that the fourteenth law, which governs the repository rather than the
  simulation, lives in `CLAUDE.md` where it is actually checkable.

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

- Split `commands.py` into a `commands/` package, one module per station: helm,
  sail, pilotage, lookout and mooring. That is how the design has always
  described them - contextual command groups exposed by cmdset - and doing it at
  sixteen commands is cheaper than doing it when gunnery and damage control
  arrive. Everything is re-exported, so `from .commands import CmdHelm` is
  unchanged.
- The station modules are named for the job rather than for the domain module
  each leans on. `commands/navigation.py` shadows `maritime.navigation` from
  inside the package, which is exactly how the first attempt at this split broke.
- Exempt `messaging.py` from the line ceiling, by name and with the reason
  recorded in the checker. It holds every word a vessel or her crew says; prose
  has no branching, no state and nothing to get wrong, so its length costs
  nothing and splitting it would scatter one voice across several files. Every
  other file is held to the rule exactly as before.

- Record the two ways mutation testing lies, in `CLAUDE.md`. A mutation that does
  not apply is a no-op that prints OK exactly like a survivor - already guarded.
  The new one: Python validates a `.pyc` against source mtime *and size*, so a
  same-length mutation written and restored inside one second leaves bytecode the
  interpreter goes on serving after the file is back. That produced a test
  failing against code that was correct when read, and could as easily have
  hidden a survivor. The harnesses now clear `__pycache__` on restore.

- Move the crew's spoken orders and replies out of `commands.py` and into
  `messaging.py`, alongside the ship's own narration. `MARITIME_NARRATOR` was
  built as the one place a game replaces the prose, and commands were bypassing
  it entirely with seventy-one hardcoded messages - so overriding it changed
  what the *ship* said and left the crew answering in the contrib's words. Two
  voices in one game, and the second unreachable without forking every command.
  A command now says `self.order(vessel, HELM_ORDER, spoken=spoken)` and knows
  that an order was given and who hears it, never what it sounds like.
- Prose has no branching and no state, so the file holding it can grow to any
  length without costing anything. That is why it is the right place for it, and
  why `messaging.py` is exempt from the reasoning that applies to code.

- Compose `Vessel` from the seams the domain modules already draw: `Navigator`
  in `navigation.py`, `Berthing` in `ports.py`, `Lookout` in `observation.py`,
  `Rigged` in `sailing.py`, `Situated` in `environment.py` and `Compartmented`
  in `rooms.py`. Everything about a concern now sits in the file that owns it,
  including the defaults it sets at creation, and the domain modules still
  import nothing from Evennia. `typeclasses.py` goes from 1039 lines to 507 and
  stops growing with every phase.

- Say "take the way off her" once instead of three times. Docked, aground and
  anchored each stopped the tick with the same four lines, which is three places
  for them to drift apart. `held_by()` names which one has her - they are undone
  by three different acts and the distinction is worth keeping - and
  `take_way_off()` does the stopping.
- Record the amended file-size rule in `CLAUDE.md`: a thousand lines unless
  splitting makes no code sense, with the measurement to check before proposing
  one. `typeclasses.py` is 920 lines carrying 99 lines of logic; the rest is the
  docstrings the style guide requires. A `Vessel` split into a mixin of getters
  and setters would have been worse code with a better number.

- Move `ShipRoom` out of `typeclasses.py` into `rooms.py`. A compartment is not
  a vessel, and this is where deck plans, stations, flooding order and
  compartment damage all land. `typeclasses.py` drops from 825 lines to 718.
- `ShipRoom` is deliberately re-exported from `typeclasses`. Evennia writes a
  typeclass to the row as a dotted path, so every compartment already created in
  every game that has run this contrib carries the old module name in its
  database. Dropping the name would not fail at startup - it would produce rooms
  that fail to resolve their typeclass one at a time as they are loaded, which is
  a considerably worse way to find out. Verified against three live rooms whose
  rows still say `typeclasses.ShipRoom`: they resolve to the class in `rooms`,
  `isinstance` holds, and their attributes and commands are intact.
- Export `Vessel` and `ShipRoom` from the package. The two typeclasses a game
  actually installs were reachable only by module path.

- Move the CI actions to `checkout@v5` and `setup-python@v6`. The v4/v5 pair
  targets Node 20, which the runners now force onto Node 24 with a deprecation
  annotation on every build - a warning that is about to become a failure.

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
