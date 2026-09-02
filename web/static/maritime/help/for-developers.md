# For developers

[Back to the handbook](index.md)

**You do not have to take all of this.** That is the first and most important thing to know
about integrating it.

The contrib is built as a stack of layers, and each one is useful without the ones above it.
A game that wants a ferry between two islands takes the bottom two and stops. A game that
wants a full age-of-sail simulation takes the lot. Nothing in between is a compromise you
have to apologise for — the layers were separated on purpose.

## The layers, bottom up

| Layer | What it gives you | What it needs |
| --- | --- | --- |
| **Position** | A world with coordinates, depth and terrain under it | Nothing |
| **Vessels** | Hulls that exist somewhere, with rooms inside them | Position |
| **Movement** | Helm, speed, and a ship that takes time to turn | Vessels |
| **Ports** | Quays, berths, a gangway you walk down | Vessels |
| **Sailing** | Wind, canvas, and speed you negotiate for | Movement |
| **Passage** | "Make for Careenage" and a sailing master who does it | Ports, Movement |
| **Observation** | Horizon, lookout, contacts | Position |
| **Crew** | A company, morale, exhaustion, hands to do work | Vessels |
| **Combat** | Guns, damage, ramming, boarding | Crew, Observation |
| **Cargo** | Holds, stowage, two capacities, trim | Vessels |

You can stop after any row. The rows above a missing one simply do not happen; nothing
throws, and nothing reports a half-configured world as an error.

## Which page you want

- **[Putting it in an existing game](integrating.md)** — the four steps, none of which
  touch a file outside your own game directory
- **[Taking only part of it](adopting-a-part.md)** — the ferry, the fishing boat, the river
  crossing, and how to leave the rest out
- **[Your own coast](your-own-world.md)** — seabed, weather, currents and tides, and how to
  supply them
- **[Your own ships](your-own-ships.md)** — hulls, rigs, and building them
- **[Rooms and typeclasses](rooms-and-typeclasses.md)** — what to mix into your own rooms,
  and what happens if you do not
- **[Every setting](settings.md)**
- **[Every command](commands.md)**
- **[Hooking into it](extending.md)** — narration, events, and the decisions left to you

## Three rules the whole thing follows

**Nothing outside this folder is edited.** Integration is four steps in your own settings
and cmdsets. If a page here ever tells you to edit a file inside Evennia, it is a bug in
the page.

**Absence is not an error.** A hull with no measured length, a ship with no crew, a world
with no weather provider — every one of those is a legitimate state that produces
sensible behaviour rather than an exception. That is what makes partial adoption possible.

**Your game's decisions stay yours.** What a ship is worth, what a cargo sells for, what
being cold in the water does to a person, who may give orders to a captured ship — the
contrib does not have opinions about any of these, because they collide with whatever your
game already has. See [hooking into it](extending.md).

---

Next: **[Putting it in an existing game](integrating.md)**.
