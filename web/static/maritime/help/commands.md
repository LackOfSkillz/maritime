# Every command

[Back to the handbook](index.md) · [For developers](for-developers.md)

Grouped by what you are trying to do, because that is how anybody looks for one. Alphabetical
order is a filing decision, and this is a manual.

Unless a row says otherwise, a command needs a deck under you: they are installed on the
ship's rooms, so they exist where a ship is and nowhere else.

---

## Steering her

| Command | Effect |
| --- | --- |
| `helm <bearing>` | Steer a course, `000` to `359`. Spoken, and answered |
| `speed <knots>` | Order a speed. For craft not under sail |
| `allstop` | Take the way off her |

## Canvas and oars

| Command | Effect |
| --- | --- |
| `sail <plan>` | `furled`, `storm`, `reefed`, `battle`, `working`, `full` |
| `oars` | What her looms are doing, and how many hands are on them |
| `give way` | The working stroke |
| `stretch out` | Everything they have. It costs them |
| `easy` | A gentle stroke; steerage way and no more |
| `hold water` | Oars in the water, to stop her |
| `paddle` | For craft that are paddled rather than rowed |

## Mooring and the ground

| Command | Effect |
| --- | --- |
| `dock` | Come alongside a berth |
| `cast off` | Let go, and take the gangway away |
| `drop anchor` | Bring up |
| `weigh anchor` | Get the anchor off the ground |
| `kedge` | Run an anchor out astern and haul her off a grounding |

## Where you are

| Command | Effect |
| --- | --- |
| `position` | Latitude, longitude, course and speed, by her reckoning |
| `fix` | Fix off a landmark, and learn the set since the last one |
| `sound` | Water under the keel, and a shoal warning |
| `chart` | What the paper says is under her, and how far to trust it |
| `plot <mark>` | Lay a course by way of safe water |

## The weather

| Command | Effect |
| --- | --- |
| `wind` | Where it is from, how hard, and how she lies to it |
| `current` | Set and drift, and the course she is making good |
| `weather` | Wind by force, the sea, and how far you can see |

## Being taken somewhere

| Command | Effect |
| --- | --- |
| `ports` | What harbours she can be told to make for, and why not the rest |
| `make for <harbour>` | The whole passage: course, sailing master, alongside at the end |
| `follow` | Hand the sailing master the con |
| `belay` | Take it back |

## Keeping a lookout

| Command | Effect |
| --- | --- |
| `lookout` | What is in sight from where you are standing |
| `scan` | The whole horizon, quarter by quarter |
| `look <direction>` | One quarter or compass point — `look se`, `look port` |
| `watch <direction>` | A standing watch; told as things come and go |
| `target <name>` | Range, aspect, closure, and which arcs bear |

## The guns

| Command | Effect |
| --- | --- |
| `guns` | The battery, and the state of each gun |
| `load <shot>` | Serve them with `ball`, `chain` or `grape` |
| `fire <name>` | Everything that bears, at her |
| `hold fire <name\|arc>` | Run out and wait; they speak when she bears |

## Boarding

| Command | Effect |
| --- | --- |
| `grapple <name>` | Throw the irons |
| `grapples` | What is holding, and how many |
| `cut grapples` | Clear them. Takes longer the more are fast |
| `strike` | Haul your colours down — or, typed again, put them back up |

## Her people and her hold

| Command | Effect |
| --- | --- |
| `crew` | Her company, how they are bearing it, and what they hold against you |
| `stow` | Load cargo |
| `discharge` | Put it ashore |
| `manifest` | What she is carrying, and what room is left |

## Ashore

Installed on the shore rooms rather than on a deck.

| Command | Effect |
| --- | --- |
| `browse` | Who is selling here, and what they have |
| `buy <thing> [from <who>]` | Buy it |
| `sell` | Sell cargo to a counter that wants it |
| `market` | What this place wants and what it offers |

## The handbook

| Command | Effect |
| --- | --- |
| `maritime help` | A link to this handbook. Works anywhere |
| `maritime help <topic>` | Opens it at that page |

## For whoever runs the game

Locked to Admin and above, except where a switch has opened one up. None of these need a
deck.

| Command | Effect |
| --- | --- |
| `maritime ui on\|off\|hybrid` | The graphical panel, for the whole game |
| `maritime uncharted on\|off` | Draw the sea as it truly is, ignoring the survey |
| `maritime player gui on\|off` | Whether accounts may choose the panel for themselves |
| `maritime gui on\|off` | Your own panel, when accounts are allowed to choose |
| `maritime player build on\|off` | Whether players may use the shipyard |
| `maritime build <hull>` | Build a ship, standing at a dock |
| `maritime summon <name>` | Bring a ship of yours forward from ordinary |
| `maritime lay up <name>` | Put one away |

## For builders

| Command | Effect |
| --- | --- |
| `@maritime` | Raw coordinates and motion state (Builder+) |
| `@ship` | Build ships, and set owner and captain (Builder+) |
| `build_aetos` | Build the shipped example coast (Builder+) |

---

## Putting them on your own ships

Two ready-made sets:

```python
from evennia.contrib.full_systems.maritime import HelmCmdSet, ShipwrightCmdSet
```

`HelmCmdSet` is everything in the first eleven groups above, and goes on a ship's rooms.
`ShipwrightCmdSet` is `@ship`, and goes on your character or account cmdset because a world
is built from dry land.

**Or take the ones you want.** Every command is importable on its own — see
[taking only part of it](adopting-a-part.md), which is the page to read if a ferry is all
you are after.

---

Next: **[Every setting](settings.md)**.
