"""
The one command that builds the example world, and the words it says.

Named `commands` in the plural to match the rest of the contrib, and because that is
where player-facing prose is allowed to live - the domain-purity check is spelled
against the package name, and it was right to stop me putting a report in the builder.

Deliberately not in the helm command set. That set lives on a ship's compartments, and
you have to be standing somewhere before there is a ship to stand on - so this goes on a
builder's own command set instead, which is also where a world-building command belongs.

"""

from evennia.commands.command import Command

from .world import build


class CmdMaritimeExample(Command):
    """
    Build the maritime example world.

    Usage:
      example

    Creates the mainland - a pond, a river and a harbour town - six islands strung
    eastward, and three craft: a kayak on the pond, a canoe at the river head and a
    sloop at the stone quay.

    Safe to run again. Everything is found by name first, so a second run returns
    what is already there rather than building a second world beside it.
    """

    key = "example"
    aliases = ("maritime example", "buildmaritime")
    locks = "cmd:perm(Builder)"
    help_category = "Building"

    def func(self):
        """Build it, and say what to try first."""
        self.caller.msg(report(build()))


def report(built):
    """
    Args:
        built (dict): What `build` returned.

    Returns:
        text (str): What was made, and what to do with it.

    Notes:
        Here rather than in `world` because a builder that talks is a builder that
        cannot be called from a script without shouting at somebody. It also keeps
        the domain-purity rule intact, which is what pointed this out.

    """
    mainland, islands, craft = built["mainland"], built["islands"], built["craft"]
    lines = ["|wThe example world is ready.|n", ""]
    lines.append(f"  Mainland   {len(mainland)} rooms, from the pond to the sea")
    lines.append(f"  Islands    {len(islands)}, strung eastward from Stone Quay")
    lines.append(f"  Craft      {', '.join(boat.key for boat in craft.values())}")
    lines.append("")
    lines.append("|wStart at the Pond Shore.|n Board the kayak and try:")
    lines.append("  |wgive way|n   |weasy|n   |whold water|n   |woars|n")
    lines.append("  Then stop paddling and wait. The breeze will put you ashore.")
    lines.append("")
    lines.append("|wThen the river,|n from River Head. Take the canoe down to Ferry Steps -")
    lines.append("  there is no path, the river is the road. Try rowing back up it.")
    lines.append("")
    lines.append("|wThen the sea.|n The Kittiwake lies at Stone Quay:")
    lines.append("  |wcast off|n   |wsail working|n   |whelm 090|n   |wlookout|n   |wsound|n")
    lines.append("  Six islands east, each a fair sail from the last. |wdock|n when you get there.")
    return "\n".join(lines)
