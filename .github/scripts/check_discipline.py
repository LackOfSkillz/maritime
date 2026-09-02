#!/usr/bin/env python3
"""
Mechanical enforcement of the project rules in CLAUDE.md.

Black and flake8 already cover formatting and general lint. This script covers the
rules specific to this contrib, which no off-the-shelf tool knows about:

    1. No source file over the line ceiling (CLAUDE.md section 6).
    2. Core Evennia and the standard library only - no third-party imports
       (CLAUDE.md section 9).
    3. CHANGELOG.md exists with a place to record unreleased work
       (CLAUDE.md section 8).
    4. README.md keeps the exact shape Evennia's documentation generator parses
       (CLAUDE.md section 3).
    5. The domain layer returns structured results and never emits prose
       (CLAUDE.md section 8, and Law 11 in docs/architecture.md).
    6. No module imports this package by its absolute path, and no string literal
       spells it out either, so the contrib works both inside the Evennia tree and
       as a standalone drop-in (CLAUDE.md section 2).

Run from the repository root:

    python .github/scripts/check_discipline.py

Exits non-zero if any rule is violated, listing every failure rather than stopping
at the first one.

"""

import ast
import sys
from pathlib import Path

# --- configuration ---------------------------------------------------------

MAX_FILE_LINES = 1000

# Directories that are never part of the shipped contrib.
EXCLUDED_DIRS = {".git", ".github", "__pycache__", "_reference", "area-design", ".venv"}

# Import roots always available to a contrib, because Evennia itself depends on
# them - installing Evennia installs these. Taken from the `dependencies` list in
# Evennia's pyproject.toml, so importing one adds no burden on the user.
#
# Deliberately absent: anything from Evennia's `[extra]` optional group (scipy,
# boto3, gitpython...). Those are permitted for contribs and several ship using
# them, but each one is a package the user must additionally install. See
# CLAUDE.md section 11 - adding one is a decision, not a convenience.
ALLOWED_IMPORT_ROOTS = {
    # the engine and its stack
    "evennia",
    "twisted",
    "django",
    "zope",
    "autobahn",
    # core runtime dependencies
    "yaml",  # pyyaml
    "pytz",
    "tzdata",
    "inflect",
    "inflection",
    "lunr",
    "simpleeval",
    "uritemplate",
    "rest_framework",  # djangorestframework
    "django_filters",  # django-filter
    "sekizai",  # django-sekizai
    # test helpers, also core dependencies
    "mock",
    "model_mommy",
    "anything",
    "parameterized",
}

#: Third-party modules the *optional* graphical enhancement may use, and nothing else may.
#:
#: The contrib itself has no dependencies and that is a promise, not a present state. What
#: these buy is shaded relief on the chart, which a game opts into by installing them; a
#: game that does not gets the same interface it always had.
#:
#: **Allowed only behind a guard.** An import of one of these outside a `try` block is a
#: hard dependency wearing an optional label, and the promise would be broken by the next
#: person who wrote `import numpy` at the top of a module without meaning anything by it.
#: The check below enforces that rather than trusting it, because the failure is silent -
#: everything works on the machine of whoever added it.
OPTIONAL_IMPORT_ROOTS = {
    "numpy",  # shaded relief: gradients and colour ramps over the sounded grid
    "scipy",  # shaded relief: generalising the soundings before lighting them
    "PIL",  # shaded relief: encoding the result as a PNG
}

# Packages permitted to talk to players directly. Everywhere else, emitting prose
# is a layering violation: the domain returns structured results and a separate
# renderer turns them into text.
#
# `transport` is named rather than the whole `client` package it lives in, and the
# narrowness is the point. It is a second speaking layer - the structured one, to
# `messaging`'s prose - and it is the only file in that package allowed to reach a
# session. The context resolver, the payload types and the snapshot builder beside
# it stay under this rule, which is what keeps a payload something you can build in
# a test without a connection to send it down.
MESSAGING_PACKAGES = {"messaging", "commands", "cmdsets", "typeclasses", "transport"}

REPO_ROOT = Path(__file__).resolve().parents[2]


# --- helpers ---------------------------------------------------------------


def iter_source_files():
    """
    Yield every Python file that forms part of the shipped contrib.

    Returns:
        generator: Paths relative to the repository root.

    """
    for path in sorted(REPO_ROOT.rglob("*.py")):
        if EXCLUDED_DIRS.intersection(path.relative_to(REPO_ROOT).parts):
            continue
        yield path


def relative(path):
    """
    Render a path relative to the repo root, for readable output.

    Args:
        path (Path): Absolute path to render.

    Returns:
        text (str): Repo-relative path using forward slashes.

    """
    return path.relative_to(REPO_ROOT).as_posix()


# --- checks ----------------------------------------------------------------


#: Files allowed past the ceiling, with the reason. Each is a deliberate,
#: approved decision rather than an oversight, and the rule is unchanged for
#: everything else: a file approaching the limit means the design wants splitting
#: along a real seam.
LENGTH_EXEMPT = {
    "messaging.py": (
        "prose. Every line a vessel or her crew says lives here, and prose has no "
        "branching, no state and nothing to get wrong - so its length costs nothing "
        "and splitting it would scatter one voice across several files."
    ),
}


def check_file_length(failures):
    """
    No source file may exceed the line ceiling, unless it is exempt.

    A file approaching the limit means the design wants splitting along a real
    seam. Raising the limit instead requires explicit approval, in advance, and
    exemptions are listed by name with their reason so that nobody has to guess
    whether one was a decision or a slip.

    Args:
        failures (list): Accumulator for failure messages.

    """
    for path in iter_source_files():
        count = len(path.read_text(encoding="utf-8").splitlines())
        if path.name in LENGTH_EXEMPT:
            continue
        if count > MAX_FILE_LINES:
            failures.append(
                f"{relative(path)}: {count} lines, over the {MAX_FILE_LINES} ceiling. "
                "Split it, or get approval in advance."
            )


def _import_roots(tree):
    """
    Collect the top-level package name of every absolute import in a module.

    Relative imports are skipped: they are internal to the contrib and always fine.

    Args:
        tree (ast.Module): Parsed module.

    Returns:
        roots (set): Top-level module names imported absolutely.

    """
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                # Relative import - internal to the package.
                continue
            if node.module:
                roots.add(node.module.split(".")[0])
    return roots


def _unguarded_roots(tree):
    """
    Args:
        tree (ast.Module): A parsed source file.

    Returns:
        roots (set): Modules imported anywhere *except* inside a `try` body.

    Notes:
        Asked this way round on purpose. The first version collected what *was* guarded
        and let a root pass if it appeared in a try anywhere in the file - so a module
        that imported numpy properly at the top and then again, bare, further down was
        reported clean. It was tested by adding exactly that and watching it pass.

        What matters is that *no* unguarded import exists, so that is what is counted.

    """
    unguarded = set()

    def walk(node):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.Import, ast.ImportFrom)):
                unguarded.update(_import_roots(ast.Module(body=[child], type_ignores=[])))
            elif isinstance(child, ast.Try):
                # The body is the guarded part; everything else in the statement is not.
                for branch in child.handlers + child.orelse + child.finalbody:
                    walk(ast.Module(body=[branch], type_ignores=[]))
            else:
                walk(child)

    walk(tree)
    return unguarded


def check_dependencies(failures):
    """
    Only the standard library and core Evennia may be imported.

    A third-party dependency makes the contrib harder to drop into a game and has
    to be discussed and documented before it is introduced - never added silently.

    Args:
        failures (list): Accumulator for failure messages.

    """
    stdlib = sys.stdlib_module_names
    for path in iter_source_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as err:
            failures.append(f"{relative(path)}: could not parse - {err}")
            continue
        unguarded = _unguarded_roots(tree)
        for root in sorted(_import_roots(tree)):
            if root in stdlib or root in ALLOWED_IMPORT_ROOTS:
                continue
            if root in OPTIONAL_IMPORT_ROOTS:
                if root not in unguarded or path.name.startswith("test_"):
                    continue
                failures.append(
                    f"{relative(path)}: imports '{root}' without a guard. It is optional, "
                    "so it has to be imported inside a try block with a working fallback - "
                    "otherwise the contrib quietly requires it."
                )
                continue
            failures.append(
                f"{relative(path)}: imports third-party module '{root}'. "
                "Core Evennia and the standard library only."
            )


def check_no_prose_in_domain(failures):
    """
    The domain layer must not emit player-facing text.

    Domain code returns structured results; a separate messaging layer renders
    them. A `.msg(` call inside a physics or damage calculation is what makes the
    messaging layer unreplaceable by a game that wants its own voice.

    Args:
        failures (list): Accumulator for failure messages.

    """
    for path in iter_source_files():
        relative_path = path.relative_to(REPO_ROOT)
        # Match a directory (commands/helm.py) or a module (commands.py). Only
        # matching directories would flag a single-module messaging layer, which
        # is the shape a small contrib actually has.
        parts = set(relative_path.parts) | {relative_path.stem}
        if parts.intersection(MESSAGING_PACKAGES):
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if ".msg(" in stripped:
                failures.append(
                    f"{relative(path)}:{lineno}: emits prose outside the messaging layer. "
                    "Return a structured result instead."
                )


def check_location_independence(failures):
    """
    No module may import this package by its absolute path.

    The contrib has two possible homes: inside the Evennia tree at
    `evennia.contrib.full_systems.maritime`, or dropped into a game standalone
    under some other path. An absolute self-import hardcodes the first and breaks
    the second. Relative imports work in both.

    Checked against the parsed import statements rather than the file text, so
    documentation examples in docstrings are not flagged.

    Args:
        failures (list): Accumulator for failure messages.

    """
    self_path = "evennia.contrib.full_systems.maritime"
    for path in iter_source_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            # Already reported by the dependency check.
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and not node.level and node.module:
                target = node.module
            elif isinstance(node, ast.Import):
                target = " ".join(alias.name for alias in node.names)
            else:
                continue
            if self_path in target:
                failures.append(
                    f"{relative(path)}:{node.lineno}: imports this package by absolute path. "
                    "Use a relative import, so the contrib also works standalone."
                )


def _docstring_nodes(tree):
    """
    Collect the string nodes that are docstrings, so they can be exempted.

    Args:
        tree (ast.Module): Parsed module.

    Returns:
        nodes (set): ids of `ast.Constant` nodes serving as docstrings.

    """
    found = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
            if isinstance(first.value.value, str):
                found.add(id(first.value))
    return found


def check_no_hardcoded_self_path(failures):
    """
    No string literal may spell out this package's absolute import path.

    Dotted-path defaults and dynamic lookups must be derived from `__package__`.
    A literal `evennia.contrib.full_systems.maritime...` resolves only while the
    contrib sits in the Evennia tree and breaks the moment it is dropped into a
    game somewhere else - the standalone case this project explicitly supports.

    Docstrings are exempt: documentation legitimately shows users the in-tree
    import path they will actually type.

    This is a static property, which is why it lives here rather than in a test.
    A test comparing the default against `__package__` passes either way while
    the contrib is in-tree, so it cannot fail in the situation it guards.

    Args:
        failures (list): Accumulator for failure messages.

    """
    self_path = "evennia.contrib.full_systems.maritime"
    for path in iter_source_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        exempt = _docstring_nodes(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            if id(node) in exempt or self_path not in node.value:
                continue
            failures.append(
                f"{relative(path)}:{node.lineno}: hardcodes this package's absolute "
                "path in a string. Derive it from __package__ so the contrib also "
                "works standalone."
            )


def check_changelog(failures):
    """
    A changelog must exist and have somewhere to record unreleased work.

    Checks the file's shape, not whether a given commit updated it - git history
    is not available to this script, and a check that cannot see the diff would
    either pass vacuously or block unrelated work. Keeping entries current is a
    review responsibility (CLAUDE.md section 8); this only guarantees the place
    to put them has not been removed or renamed.

    Args:
        failures (list): Accumulator for failure messages.

    """
    changelog = REPO_ROOT / "CHANGELOG.md"
    if not changelog.exists():
        failures.append("CHANGELOG.md is missing. Every notable change is recorded there.")
        return

    stripped = [line.strip() for line in changelog.read_text(encoding="utf-8").splitlines()]

    if not stripped or not stripped[0].startswith("# "):
        failures.append("CHANGELOG.md: first line must be a title, as '# Changelog'.")

    if not any(line.lower().startswith("## unreleased") for line in stripped):
        failures.append(
            "CHANGELOG.md: needs an '## Unreleased' section for work that has not "
            "shipped yet, or there is nowhere to record a change in progress."
        )


def check_readme(failures):
    """
    README.md must keep the shape Evennia's documentation generator parses.

    Evennia builds this contrib's public documentation page directly from this
    file, lifting the credit line and first paragraph onto the contrib index. A
    restructured README silently degrades that generated page.

    Args:
        failures (list): Accumulator for failure messages.

    """
    readme = REPO_ROOT / "README.md"
    if not readme.exists():
        failures.append("README.md is missing. It is required for every contrib.")
        return

    lines = readme.read_text(encoding="utf-8").splitlines()
    stripped = [line.strip() for line in lines]

    if not stripped or not stripped[0].startswith("# "):
        failures.append("README.md: first line must be the contrib title, as '# Name'.")

    credit = [line for line in stripped[:6] if line.startswith("Contribution by ")]
    if not credit:
        failures.append(
            "README.md: needs a 'Contribution by <name>, <year>' line near the top. "
            "Evennia lifts it onto the contrib index verbatim."
        )

    if "## Installation" not in stripped:
        failures.append("README.md: an '## Installation' section is required, not optional.")


# --- entry point -----------------------------------------------------------


def main():
    """
    Run every check and report all failures.

    Returns:
        code (int): 0 if every rule passes, 1 otherwise.

    """
    failures = []
    checks = (
        ("file length", check_file_length),
        ("dependencies", check_dependencies),
        ("domain purity", check_no_prose_in_domain),
        ("location independence", check_location_independence),
        ("no hardcoded self-path", check_no_hardcoded_self_path),
        ("changelog", check_changelog),
        ("readme format", check_readme),
    )

    for name, check in checks:
        before = len(failures)
        check(failures)
        status = "FAIL" if len(failures) > before else "ok"
        print(f"  [{status:>4}] {name}")

    if failures:
        print(f"\n{len(failures)} problem(s):\n")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("\nAll discipline checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
