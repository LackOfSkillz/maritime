"""
Tests that read the browser scripts as text, because nothing else here can.

The client is five JavaScript files and this repository has no JavaScript test runner. That
is a deliberate position - a Python contrib that needs node installed to go green is a
contrib with a second toolchain, and Evennia would be right to object - but it leaves the
interface untested, and one bug has already used the gap.

**Two functions in one file were both called `has`.** Both took a state and a string, both
were declared at module scope in the same closure, and the later declaration silently
replaced the earlier one. `offered()` then spent its life asking whether `"company"` was in
the list of *controls*, which it never is, so every panel tab vanished. The bodies went on
rendering from the stored preference, which is exactly why an empty tab strip did not look
like a bug, and it shipped that way for three commits.

No test could have caught that by exercising the interface, because there is nothing to
exercise it with. A test that *reads* it can, and the class of bug is worth guarding
generally rather than the one instance: a redeclaration at module scope is always a bug in
this codebase, whatever it happens to be called.

Every function declaration in every client script sits at exactly four spaces - one file,
one closure, one scope - so the check is unambiguous rather than a guess at nesting.
"""

import re
import unittest
from pathlib import Path

#: Where the browser scripts live, relative to the contrib root.
CLIENT_SCRIPTS = Path(__file__).resolve().parent.parent / "web" / "static" / "maritime"

#: A function declared at module scope: exactly one level of indentation inside the file's
#: closure. Anything more deeply indented is a nested helper and may legitimately share a
#: name with one in a different function.
DECLARATION = re.compile(r"^    function ([A-Za-z_$][\w$]*)\s*\(", re.MULTILINE)

#: The module closure itself, matched at the start of a line so that a callback written
#: inline - `setTimeout(function () {` - is not mistaken for a second one. It was, first
#: time, and the test failed on a file that had nothing wrong with it.
MODULE = re.compile(r"^window\.[\w$]+ = \(function \(\)", re.MULTILINE)


def scripts():
    return sorted(CLIENT_SCRIPTS.glob("*.js"))


class TestTheClientScriptsAreThere(unittest.TestCase):
    def test_the_scripts_exist_and_are_not_empty(self):
        found = scripts()
        self.assertTrue(found, f"no client scripts under {CLIENT_SCRIPTS}")
        for path in found:
            self.assertGreater(len(path.read_text(encoding="utf-8")), 200, path.name)

    def test_every_script_is_one_closure(self):
        """
        The check below assumes one module scope per file. If a script ever grew a second
        top-level closure, module scope would stop being "four spaces" and the guard would
        quietly stop guarding.

        """
        for path in scripts():
            source = path.read_text(encoding="utf-8")
            self.assertEqual(
                len(MODULE.findall(source)),
                1,
                f"{path.name} is no longer a single closure, so the scope check is wrong",
            )


class TestNothingIsDeclaredTwice(unittest.TestCase):
    """
    The guard the tab strip needed and did not have.

    A duplicate at module scope is never intentional here. JavaScript accepts it silently,
    keeps the last one, and the symptom appears somewhere else entirely.
    """

    def test_no_function_is_declared_twice_in_the_same_script(self):
        for path in scripts():
            names = DECLARATION.findall(path.read_text(encoding="utf-8"))
            seen, repeated = set(), []
            for name in names:
                if name in seen:
                    repeated.append(name)
                seen.add(name)
            self.assertEqual(
                repeated,
                [],
                f"{path.name} declares {repeated} more than once at module scope; "
                f"JavaScript keeps the last one and the first silently stops existing",
            )

    def test_the_check_can_actually_see_a_duplicate(self):
        """
        A guard that cannot fail is not a guard. This is the shape of the bug that got
        through, run against the matcher rather than against a file.

        """
        source = (
            "window.Thing = (function () {\n"
            "    function has(state, key) {\n        return true;\n    }\n"
            "    function has(state, key) {\n        return false;\n    }\n"
            "})();\n"
        )
        self.assertEqual(DECLARATION.findall(source), ["has", "has"])

    def test_the_check_does_not_object_to_nested_helpers(self):
        """Two functions may each contain a helper of the same name. That is not a bug."""
        source = (
            "window.Thing = (function () {\n"
            "    function outer() {\n"
            "        function step() {}\n        return step;\n    }\n"
            "    function other() {\n"
            "        function step() {}\n        return step;\n    }\n"
            "})();\n"
        )
        self.assertEqual(DECLARATION.findall(source), ["outer", "other"])

    def test_the_functions_the_panels_depend_on_are_still_named_apart(self):
        """
        Stated by name, because these two are the pair that collided and the names are
        close enough to collide again: one asks what the *server offered*, the other what
        the *payload contains*.

        """
        source = (CLIENT_SCRIPTS / "maritime-panels.js").read_text(encoding="utf-8")
        names = DECLARATION.findall(source)
        self.assertIn("hasControl", names)
        self.assertIn("has", names)


if __name__ == "__main__":
    unittest.main()
