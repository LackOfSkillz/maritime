"""
Tests for the seam nobody looks at: what a hull's mixins call things.

A `Vessel` is assembled from twenty-odd mixins, and Python resolves a name clash between
two of them silently - the one earlier in the bases wins and the other's method is simply
never called again. Nothing raises. Nothing is logged. The older feature stops working.

That has happened three times in one day, twice in command aliases and once here:
`stand_down` meant *secure the guns* long before a posts mixin arrived meaning *relieve
somebody*, and adding the second quietly took the first away.

The alias collisions are guarded in `test_scripts`. This is the same guard for the other
surface.

"""

import inspect

from evennia.utils.test_resources import BaseEvenniaTest

from ..typeclasses import Vessel

#: Hooks two mixins are *supposed* to share, because they cooperate through `super()`.
#:
#: Each of these is called up the chain, so every mixin defining one gets its turn. That is
#: the pattern, not a clash - and listing them by name is what lets everything else be one.
COOPERATIVE = {
    "at_object_creation",
    "at_object_receive",
    "at_object_leave",
    "at_init",
    "at_post_move",
    "at_pre_move",
    "return_appearance",
    "basetype_setup",
}


def maritime_mixins():
    """
    Returns:
        mixins (list): Every class in the hull's ancestry that this contrib wrote.

    Notes:
        Ours only. Evennia's own classes override each other on purpose and are not this
        test's business.

    """
    here = Vessel.__module__.rsplit(".", 1)[0]
    return [
        base
        for base in Vessel.__mro__
        if base is not Vessel and getattr(base, "__module__", "").startswith(here)
    ]


def defined_by(cls):
    """
    Args:
        cls (type): A mixin.

    Returns:
        names (set): What it defines itself, ignoring anything inherited.

    """
    return {
        name
        for name, value in vars(cls).items()
        if not name.startswith("_")
        and name not in COOPERATIVE
        and (inspect.isfunction(value) or isinstance(value, property))
    }


class TestNoTwoMixinsCallSomethingTheSameThing(BaseEvenniaTest):
    """
    **A clash between two mixins is not an error. It is a silent replacement.**

    Whichever comes first in the bases wins, the other's method is never reached again, and
    the only sign is that something which used to work has stopped.

    """

    def test_the_hull_is_built_from_our_mixins(self):
        """A guard on a list that turned out to be empty would pass for ever."""
        self.assertGreater(len(maritime_mixins()), 10)

    def test_every_name_belongs_to_one_of_them(self):
        seen = {}
        clashes = []
        for mixin in maritime_mixins():
            for name in defined_by(mixin):
                if name in seen:
                    clashes.append(f"'{name}' is defined by both {seen[name]} and {mixin.__name__}")
                else:
                    seen[name] = mixin.__name__
        self.assertEqual(
            clashes,
            [],
            "Two mixins answer to one name; the later one silently replaces the earlier:\n  "
            + "\n  ".join(clashes),
        )

    def test_stand_down_still_belongs_to_the_guns(self):
        """
        The clash that prompted this. `stand_down` secures the battery; relieving somebody
        at a post is `relieve`.

        """
        owner = next(mixin.__name__ for mixin in maritime_mixins() if "stand_down" in vars(mixin))
        self.assertEqual(owner, "Armed")
