# CLAUDE.md — working directions for this repository

This repository is an **Evennia contrib**. It is written to be submitted upstream and used
by developers who know nothing about the game it was written for.

Everything below is binding. When a rule here conflicts with convenience, the rule wins.
When a rule here conflicts with an instruction from Gary, ask.

---

## 1. What this is

`maritime` — a maritime simulation contrib for Evennia. Vessels hold positions in continuous
world coordinates rather than moving between ocean rooms.

The repository root **is** the contrib package. It lives at, and is developed at, its
canonical Evennia path:

```text
evennia/contrib/full_systems/maritime/
```

The folder name is the import path. Users will write
`from evennia.contrib.full_systems.maritime import ...`.

Design rationale lives in `docs/architecture.md`. Read it before adding a system.

### Two homes, not one

This package targets **both** of these, and neither is a consolation prize:

1. An Evennia contrib, merged upstream and living in the Evennia tree.
2. A standalone open-source repository a developer clones and drops into their own game.

Upstream merging is not guaranteed for anyone — accepting a contrib means the Evennia project
takes on maintaining it, and that is a real cost for them to weigh. Whichever way that lands,
the code has to be equally usable, so the second path is a design constraint rather than a
fallback.

Concretely: **never import this package by its absolute path.** Use relative imports
internally (`from .domain import vessel`). An absolute self-import hardcodes home number one
and breaks home number two. CI enforces this.

The same reasoning applies to anything that resolves a module by string — dynamic imports,
settings-style dotted paths, plugin lookups. Derive them from `__package__`, never from a
hardcoded literal.

---

## 2. Package layout (mandated by Evennia)

A contrib must be contained **within a single folder** under one contrib category. Ours is
`full_systems/` — "complete game engines that can be used directly to start creating content
without further additions."

```text
maritime/
├── __init__.py      # import useful resources here for easier importing
├── README.md        # required, and format-sensitive — see §3
├── module1.py
├── module2.py
└── tests/           # or tests.py; Evennia finds them automatically
```

Rules:

- Never add files outside this folder. A contrib that requires changes elsewhere in the
  Evennia tree or to the game directory structure will not be accepted.
- Never commit Evennia core code to this repository. Only our own code, from this directory
  down.
- Use relative imports within the package (`from . import vessel`). Use absolute imports for
  core (`from evennia.utils import ...`).

---

## 3. README.md is load-bearing — do not restructure it

`docs/pylib/contrib_readmes2docs.py` in the Evennia repo **auto-generates this contrib's
public documentation page from `README.md`**. The credit line and the first paragraph are
extracted verbatim onto the contrib overview index.

The required form is exact:

```markdown
# MyContribName

Contribution by <yourname>, <year>

A paragraph (can be multi-line)
summarizing the contrib (required)

Optional other text

## Installation

Detailed installation instructions for using the contrib (required)

## Usage

## Examples
```

Keep the title, the credit line, and a single summary paragraph in that order. Installation
instructions are required, not optional, and must be detailed enough to actually follow.

---

## 4. Testing is not optional and not last

> "Your contribution *must* be covered by unit tests."

- Every milestone ships implementation **and** its tests together. Never defer tests to a
  later pass.
- Test modules must be named `test*.py` (`tests.py`, `test_sailing.py`). Evennia finds them
  wherever they are in the package. Use a `tests/` package once there are many.
- Test classes inherit from `unittest.TestCase` at any distance; test methods start with
  `test_`.

**Use the `Base*` test classes, not the plain ones.** This is a contrib, so its tests are run
as part of the whole Evennia suite via `evennia test evennia` — under *default* settings, not
ours. The `Base*` variants enforce default settings and are the correct choice here:

| Class | Use |
| --- | --- |
| `BaseEvenniaTest` | full object environment, default settings enforced |
| `BaseEvenniaCommandTest` | as above, plus the `.call()` command tester |
| `BaseEvenniaTestCase` | no default objects, just enforced default settings |

All are in `evennia.utils.test_resources`. They define `setUp`/`tearDown` already — if you
override either, call `super()` or you will break the fixture.

Run them with:

```bash
evennia test --settings settings.py evennia.contrib.full_systems.maritime
```

Never claim something works without running the tests and reading the output.

---

## 5. Code style (Evennia Style Guide + PEP 8)

Authoritative settings, taken from Evennia's own linter config:

| Rule | Value |
| --- | --- |
| Formatter | `black`, line length **100** |
| Lint | `flake8`, max line length **100** |
| Indentation | 4 spaces, **never tabs** |
| Line endings | **LF** (enforced by `.gitattributes`) |

Naming:

- `CamelCase` **only** for classes. Nothing else.
- All non-global variables and all function names are `lowercase_with_underscores`.
- Variable names must be **longer than two letters**.
- Only module-level globals are `CAPITAL_LETTERS`.

Import order:

1. Python builtins and standard library
2. Twisted modules
3. Django modules
4. Evennia library modules (`evennia`)
5. Evennia contrib modules (`evennia.contrib`)

Docstrings — every module, class, function and method. Google style, as used throughout
Evennia core:

```python
def is_iterable(obj):
    """
    Checks if an object behaves iterably.

    Args:
        obj (any): Entity to check for iterability.

    Returns:
        is_iterable (bool): If `obj` is iterable or not.

    Notes:
        Strings are *not* accepted as iterable.

    """
```

Modules start with a docstring explaining what the module is and why it exists.

---

## 6. No god files

**Hard guideline: no source file over 1000 lines.**

If a file is approaching the limit, that is a signal the design is wrong, not that the limit
is wrong. Split it along a real seam — a separate concern, not an arbitrary cut point.

**Exceeding 1000 lines requires Gary's explicit approval, in advance.** Do not commit a file
over the limit and explain afterwards. Ask, give the reason, and wait for a decision.

This applies to source modules. Data files and generated content are judged case by case, but
still ask.

---

## 7. Evennia engine rules

These are drawn from Evennia's own docs and are the ones most likely to be broken by someone
who knows Python but not Evennia. Several are silent failures rather than errors.

### Typeclass names are globally unique

> "The typeclass' name must be *unique* across the entire server namespace. There must never
> be two same-named classes defined anywhere."

Before naming a typeclass, grep the Evennia tree for a class of that name. A collision is a
server-wide error, not a local one. Also note a typeclass is only discoverable if its module
is imported from somewhere.

### Never use a ticker to catch changes

> "You should *never* use a ticker to catch *changes*."

Polling every second to notice something that changed is wasted work 99% of the time, and
worse if it means walking objects in the database. Prefer:

- systems that **report their own** state changes (hooks, signals),
- values computed **on demand**, when something actually examines them.

A vessel under way genuinely changes every tick, so simulating it is justified. Derived
state — visibility, contacts, effective speed — is not, and should be computed when asked
for. This is the same split as persist-vs-derive in `docs/architecture.md`.

### TickerHandler subscriptions collide silently

Tickers are identified by callable + interval + `persistent` flag + `idstring` — **not** by
their arguments. Two subscriptions to the same callback and interval with different arguments
will overwrite each other unless each supplies a distinct `idstring`. Everything passed to a
ticker is pickled, with the same restrictions as Attributes.

### Attribute reads are cheap; writes and nested mutation are not

Evennia caches Attributes aggressively — reading a cached Attribute is about as fast as a
normal Python property. The costs are elsewhere:

- **Writing** repeatedly (many times per second) is the real expense.
- A `dict` or `list` off `.db` comes back as a `_SaverDict`/`_SaverList`, and **every nested
  mutation commits**. Take one snapshot, mutate it in plain Python, write it back once.
- Deeply nested structures are slower to store, because Evennia must walk the whole structure
  to find database objects to convert. Keep stored shapes flat.

This is why the simulation keeps hot state in memory and checkpoints, rather than writing
through per step.

### Use a Script, not a homeless Object

> "If you ever consider creating an Object with a `None`-location just to store some game
> data, you should really be using a Script instead."

Once a Script exists, starting, stopping and pausing it is cheap.

### Optimise only after measuring

Evennia's own guidance quotes Knuth: don't optimise until you have identified a real need,
and remember optimisation usually costs readability. Working first, measured second, faster
third.

For load testing use the **Dummyrunner** (`evennia/server/profiling`) — never against a
production database. `cProfile` output lands in `server/logs/server.prof`. When timing
anything involving database writes, drop `timeit`'s repeat count to ~100–1000; the default of
a million will not finish.

---

## 8. Documentation is part of the work, not a write-up afterwards

This contrib will be read far more often than it is written — by reviewers, by developers
deciding whether to adopt it, and by us in a year. Document meticulously.

**Every module** opens with a docstring saying what it is and *why it exists*. Every class,
function and method has one. Where a decision looks arbitrary, record the reason: the next
reader cannot tell a deliberate choice from an accident without being told.

Three tiers, each with a different job:

Four tiers, each with a different job:

| Where | Audience | Job |
| --- | --- | --- |
| `README.md` | someone deciding whether to use it | what it is, how to install, how to start |
| `CHANGELOG.md` | someone tracking what moved | what changed, and when |
| `docs/architecture.md` | someone extending it | how it is built and why it is built that way |
| Docstrings | someone reading the code | what this does, its arguments, its return, its traps |

Rules that are easy to break:

- **Document the constraint, not just the behaviour.** "Returns keel clearance in metres" is
  half a docstring. "Negative means aground" is the other half.
- **Record why, especially for anything non-obvious.** A reader who does not know the reason
  will eventually delete it as redundant.
- **Documentation ships with the change**, in the same commit. Not a later pass.
- **Update docs when behaviour changes.** A stale docstring is worse than none — it is
  actively believed.
- **Keep examples generic** — `Test Sloop`, `Harbor A`, `Harbor B`. Never real game lore.

### The changelog

**Every change that a user or reviewer could notice gets a `CHANGELOG.md` entry, written
in the same commit as the change.** Not batched up later — by then the reason is gone and
what remains is a list of file names.

Entries live under `## Unreleased` until a release, grouped `Feat` / `Fix` / `Docs` /
`Chore`. Those prefixes match Evennia's own changelog convention, so entries slot in
naturally if this contrib is merged upstream.

Write for someone who was not here. "Fixed the check" is useless; "core Evennia
dependencies such as PyYAML were rejected by the dependency check, so `import yaml`
failed the build" tells them what broke and whether it affects them.

Internal churn — reformatting, a typo in a comment, a test rename — needs no entry. If in
doubt, ask whether a reader would want to know. Usually they would.

### Commit and push messages

A commit message explains **what changed and why**, for a stranger reading the log,
because a stranger will.

- One logical change per commit. Committing often is fine and pushing every commit is not
  required — but **when you push, the messages must fully account for everything in it.**
  Nothing arrives on the remote undescribed.
- Say why, not only what. The diff already shows what.
- Record decisions and their reasons, so the log stays useful when the code has moved on.
- If a change came out of a bug, name the bug — the next person to hit it will search for
  those words.
- No AI-authorship tells, no churn commits, no "fix fix fix" chains.

Before pushing, re-read the commits going out and check each one is described. If a commit
message no longer matches what it contains, amend it rather than pushing something
misleading.

---

## 9. The tutorial zone is a deliverable

The contrib ships a small, runnable demonstration world. It is not optional polish, and it is
not written last.

Its purpose is threefold, and the third is why it matters most:

1. **It teaches.** A developer evaluating this should be able to sail a vessel from one
   harbour to another within minutes of installing, without reading the architecture doc.
2. **It demonstrates.** Features that cannot be shown in the tutorial zone are features
   nobody will discover.
3. **It is an integration test.** The tutorial zone exercises the real system end to end.
   If it breaks, something genuinely broke — which makes it the most honest test in the
   suite.

Requirements:

- Minimal and genre-neutral. Two harbours, one vessel, one wind, one current, one hazard.
  Enough to prove the system, not enough to impose a setting.
- Generic names throughout. No lore from any particular game.
- Installable and runnable from the README's instructions alone, with no prior knowledge.
- Kept working. A broken tutorial zone is a failing build, not a cosmetic issue.

---

## 10. General engineering standards

These are not stylistic preferences. Treat violations as defects.

- **No dead code.** No commented-out blocks, no unreachable branches, no TODO graveyards, no
  half-wired features left "for later."
- **No speculative abstraction.** Do not build an interface for a consumer that does not
  exist. Generalize only after implementation proves the seam. One caller is not a pattern.
- **No game-specific vocabulary in the code.** No lore, no proper nouns from any particular
  game, no assumptions about skills, combat, economy or progression systems. Reach those
  through adapters if they are needed at all.
- **Documentation examples use generic names** — `Test Sloop`, `Harbor A`, `Harbor B`.
- **Every public function has a reason to exist and a test that proves it.**
- **The domain layer returns structured results, never prose.** A `caller.msg()` inside a
  physics or damage calculation is a defect. Messaging is a separate, replaceable layer.

---

## 11. Dependencies

Evennia **permits** third-party dependencies. This project **declines** them. Those are two
different statements and it matters that they are not confused.

### What Evennia allows

> "The contribution should preferably work in isolation from other contribs (only make use of
> core Evennia) so it can easily be dropped into use. If it does depend on other contribs or
> third-party modules, these must be clearly documented and part of the installation
> instructions."

There is a formal mechanism. Evennia's `pyproject.toml` carries an optional group installed
with `pip install evennia[extra]`, and several shipped contribs use it:

```text
"scipy == 1.17.0",        # xyzroom contrib
"boto3 >= 1.4.4",         # AWS storage contrib
"gitpython >= 3.1.27",    # Git contrib
```

So a dependency is available, with precedent, if genuinely needed.

### Free to use — already core dependencies

Installing Evennia installs these, so importing one costs the user nothing:

```text
django  twisted  zope  autobahn  pytz  tzdata
yaml (pyyaml)  inflect  inflection  lunr  simpleeval  uritemplate
rest_framework  django_filters  sekizai
mock  model_mommy  anything  parameterized     (test helpers)
```

`yaml` and `simpleeval` in particular are worth remembering — data-driven vessel templates
need no new dependency.

### What this project uses: nothing beyond that

Not out of purity. For three concrete reasons:

1. **Standalone use is a design goal** (section 1). Every extra package is friction for the
   developer dropping this into their own game, and a second install step that can be missed.
2. **Adding to `[extra]` means editing a file outside this folder** — Evennia's
   `pyproject.toml`. Section 2 forbids that, and a contrib requiring changes elsewhere in the
   tree is exactly what the guidelines warn is unlikely to be accepted.
3. **The maths does not need it.** Vectors, trigonometry, interpolation, spatial hashing and
   A* over a coarse node graph are each a few dozen lines of clear Python. `numpy` would
   likely be *slower* here — its advantage is bulk array operations, and its per-call
   overhead is real on three-element vectors accessed one at a time, which is our access
   pattern. `scipy`'s KD-tree is excellent for static point sets and a poor fit for positions
   that change every tick, where grid buckets update in constant time.

So: **study the libraries, hand-roll the small piece we actually need.** That is a
performance and portability decision, not asceticism.

### If that ever stops being true

It might. Say so rather than working around it. The process:

1. Establish the need with a measurement, not an intuition.
2. Get Gary's approval before writing code against it.
3. Add it to Evennia's `[extra]` group with a comment naming this contrib.
4. Make it step one of the README's Installation section.
5. Add its import root to `ALLOWED_IMPORT_ROOTS` in the discipline checker, with the reason.

Never add one silently. CI fails the build on any import root outside the list above.

Also: **no dependency on other contribs.** That constraint has no escape hatch here.

---

## 12. Genre-agnostic by default

> "Try to make your contribution as genre-agnostic as possible and assume your code will be
> applied to a very different game than you had in mind when creating it."

Write for a stranger's game. Where a decision belongs to the host game — world-time ratio,
what happens to an offline character, tidal range, how damage maps to their combat system —
**expose a seam and supply a sensible default**, rather than choosing for them.

---

## 13. Licensing

All contributions are released under the **same license as Evennia** (BSD 3-Clause). See
`LICENSE`.

If any code is adapted from an existing Evennia contrib or another source, add a provenance
header naming the origin and the version or commit studied. Do this when the code is written,
not at submission time, when it is no longer reconstructible.

---

## 14. Git hygiene

- Commit subjects are written for a stranger reading the log, because a stranger will.
- One logical change per commit. No churn commits, no "fix fix fix" chains.
- LF line endings, enforced by `.gitattributes`.
- This repo is nested inside a full Evennia clone during development. The clone is excluded
  from this repo, and this folder is excluded from the clone via its `.git/info/exclude`.
  **Never commit to the Evennia clone**, and never let its files enter this repository.
- Do not push or open a PR unless asked.

---

## 15. Submission process — for reference, not to act on

- A contrib is submitted as a **pull request** to Evennia.
- PRs are reviewed and may go through several iterations. Merging is not guaranteed —
  accepting a contrib means the Evennia project takes on maintaining it.
- If unsure whether an idea is suitable, **ask in Evennia's discussions or chat before
  putting work into it.**

Do not initiate any of this. Gary decides when and whether to submit.

---

## 16. The rules are enforced, not just written down

Most of this document is checked mechanically. A rule that only lives in prose decays; a rule
with a check behind it does not.

`.github/workflows/checks.yml` runs on every push and pull request:

| Job | Enforces |
| --- | --- |
| `black --check --line-length 100` | section 5 formatting |
| `flake8 --max-line-length 100` | section 5 lint |
| `.github/scripts/check_discipline.py` | sections 2, 3, 6, 10, 11 |
| `evennia test` on 3.12 and 3.13 | section 4 |

`check_discipline.py` covers the rules no off-the-shelf tool knows about:

1. **File length** — no source file over 1000 lines (section 6).
2. **Dependencies** — standard library, `evennia`, `twisted`, `django` and relative imports
   only. Any other import root fails the build (section 11).
3. **Domain purity** — a `.msg(` outside `messaging/`, `commands/`, `cmdsets/` or
   `typeclasses/` fails. Domain code returns structured results; it does not speak (section
   10).
4. **README shape** — title, credit line and `## Installation` must be present, because
   Evennia generates the public documentation page from this file (section 3).

Run it locally before committing:

```bash
python .github/scripts/check_discipline.py
```

**When you add a rule to this document, add its check.** If a rule cannot be checked, say so
explicitly where it is stated, so nobody assumes CI is covering it.

`black` is pinned in CI. Its formatting changes between releases, and an unpinned formatter
turns an unrelated upstream release into a red build on an untouched branch.

---

## 17. Before you claim you are done

Run the tests. Run the discipline checks. Read the output. Confirm the change is inside this
folder and nothing leaked into the Evennia clone.

Evidence before assertions, every time.
