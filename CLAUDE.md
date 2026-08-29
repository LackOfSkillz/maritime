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
- Tests go in `tests.py`, or a `tests/` package when there are many across modules. Evennia
  discovers them automatically.
- Use `evennia.utils.test_resources` base classes rather than hand-rolling fixtures.

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

## 7. General engineering standards

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

## 8. Dependencies

> "The contribution should preferably work in isolation from other contribs (only make use of
> core Evennia) so it can easily be dropped into use."

- **Core Evennia and the Python standard library only.**
- No third-party packages. No numpy, no scipy, no physics libraries.
- No dependency on other contribs.
- If a dependency ever becomes genuinely unavoidable, it must be discussed first and then
  documented in the installation instructions. Do not add one unilaterally.

---

## 9. Genre-agnostic by default

> "Try to make your contribution as genre-agnostic as possible and assume your code will be
> applied to a very different game than you had in mind when creating it."

Write for a stranger's game. Where a decision belongs to the host game — world-time ratio,
what happens to an offline character, tidal range, how damage maps to their combat system —
**expose a seam and supply a sensible default**, rather than choosing for them.

---

## 10. Licensing

All contributions are released under the **same license as Evennia** (BSD 3-Clause). See
`LICENSE`.

If any code is adapted from an existing Evennia contrib or another source, add a provenance
header naming the origin and the version or commit studied. Do this when the code is written,
not at submission time, when it is no longer reconstructible.

---

## 11. Git hygiene

- Commit subjects are written for a stranger reading the log, because a stranger will.
- One logical change per commit. No churn commits, no "fix fix fix" chains.
- LF line endings, enforced by `.gitattributes`.
- This repo is nested inside a full Evennia clone during development. The clone is excluded
  from this repo, and this folder is excluded from the clone via its `.git/info/exclude`.
  **Never commit to the Evennia clone**, and never let its files enter this repository.
- Do not push or open a PR unless asked.

---

## 12. Submission process — for reference, not to act on

- A contrib is submitted as a **pull request** to Evennia.
- PRs are reviewed and may go through several iterations. Merging is not guaranteed —
  accepting a contrib means the Evennia project takes on maintaining it.
- If unsure whether an idea is suitable, **ask in Evennia's discussions or chat before
  putting work into it.**

Do not initiate any of this. Gary decides when and whether to submit.

---

## 13. Before you claim you are done

Run the tests. Read the output. Check the line count of anything you touched. Confirm the
change is inside this folder and nothing leaked into the Evennia clone.

Evidence before assertions, every time.
