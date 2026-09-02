# The interface

[Back to the handbook](index.md)

If you are playing in a web browser and the game has it switched on, going aboard raises a
panel: her name and rig, the instruments, a chart, and the controls that bear.

**It is a keyboard, not a shortcut.** Every control sends the command you could have typed,
through the same handler with the same locks and the same refusals. There is nothing you can
do with the panel that you cannot do by typing, and nothing the panel is allowed to do that
you are not.

Stepping ashore hands the screen back to the game, unless the game has asked to keep the
panel up — in which case the chart is replaced by a map of the town. See
[ashore](ashore.md).

## The chart

What is under her, drawn from the survey rather than from the truth. It is wrong in the
places the paper is wrong.

Drag to pan, scroll to zoom. The harbours she could be told to make for are marked, and
clicking one is the same as typing `make for` — including the part where it refuses if
there is no water in.

## Your own view

    maritime gui on
    maritime gui off

Turns the panel off for your account, if the game allows accounts to choose. Some do not,
and then this command is not there at all.

## For whoever runs the game

These are for administrators and developers, and are not visible to anybody else unless
they have been opened up:

| Command | What it does |
| --- | --- |
| `maritime ui on\|off\|hybrid` | The interface, for the whole game |
| `maritime uncharted on\|off` | Draw the sea as it truly is, ignoring the survey |
| `maritime player gui on\|off` | Whether accounts may choose for themselves |
| `maritime player build on\|off` | Whether players may use the shipyard |
| `maritime build <hull>` | Build a ship, standing at a dock |
| `maritime summon <name>` | Bring a ship of yours forward |
| `maritime lay up <name>` | Put one away |

`maritime uncharted` is the useful one when building: with it on, every chart reads the
world itself, so what you see is what is actually there rather than what somebody surveyed.

---

[Back to the handbook](index.md)
