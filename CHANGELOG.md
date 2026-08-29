# Changelog

All notable changes to the Maritime contrib.

Entry prefixes follow Evennia's own changelog convention (`Feat:`, `Fix:`, `Docs:`,
`Chore:`) so that entries slot in naturally if this contrib is merged upstream.

## Unreleased

Nothing released yet. The contrib is in Phase 0 - foundations only, no vessel
simulation exists.

### Feat

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
