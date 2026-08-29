#!/usr/bin/env python3
"""
Mechanical enforcement of the project rules in CLAUDE.md.

Black and flake8 already cover formatting and general lint. This script covers the
rules specific to this contrib, which no off-the-shelf tool knows about:

    1. No source file over the line ceiling (CLAUDE.md section 6).
    2. Core Evennia and the standard library only - no third-party imports
       (CLAUDE.md section 9).
    3. README.md keeps the exact shape Evennia's documentation generator parses
       (CLAUDE.md section 3).
    4. The domain layer returns structured results and never emits prose
       (CLAUDE.md section 8, and Law 11 in docs/architecture.md).

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
EXCLUDED_DIRS = {".git", ".github", "__pycache__", "_reference", ".venv"}

# Import roots that are legitimately available to a contrib.
ALLOWED_IMPORT_ROOTS = {"evennia", "twisted", "django"}

# Packages permitted to talk to players directly. Everywhere else, emitting prose
# is a layering violation: the domain returns structured results and a separate
# renderer turns them into text.
MESSAGING_PACKAGES = {"messaging", "commands", "cmdsets", "typeclasses"}

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


def check_file_length(failures):
    """
    No source file may exceed the line ceiling.

    A file approaching the limit means the design wants splitting along a real
    seam. Raising the limit instead requires explicit approval, in advance.

    Args:
        failures (list): Accumulator for failure messages.

    """
    for path in iter_source_files():
        count = len(path.read_text(encoding="utf-8").splitlines())
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
        for root in sorted(_import_roots(tree)):
            if root in stdlib or root in ALLOWED_IMPORT_ROOTS:
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
        parts = set(path.relative_to(REPO_ROOT).parts)
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
