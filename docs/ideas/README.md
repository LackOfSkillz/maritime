# Ideas

Nothing here is committed to. These are sketches and references kept against the
optional items at the end of `../combat-roadmap.md`, so the thinking survives whether
or not we take them up.

## maritime-interface-mockup.png

A design concept for **T1, a maritime interface** — supplied, not built. Worth keeping
because it settles several questions the roadmap entry left open, and raises a few of
its own.

**What it gets right, against what the contrib already knows:**

- The status strip along the top is almost exactly the payload T1 proposes — heading,
  speed, course made good, wind, current, depth, hull, sail plan, anchor. Every one of
  those is a number a vessel can already answer for, so the strip needs no new
  authority. `made_good()` is the one people forget; it is there.
- A contacts list with **bearing and range per contact** rather than positions on a
  map. That is the honest shape: bearing and range are what a lookout reports, and it
  keeps the panel a repeater rather than an oracle.
- "Unknown Sail" sitting in that list beside named ships is the single most important
  detail in the picture. It is `Sighting.level` doing its job — a contact you have not
  identified is shown as a contact you have not identified, and the interface does not
  quietly know more than the deck does.
- Depth in fathoms, wind and current as separate readings, and a warnings block that
  carries shoal water. All of that already exists.

**What it assumes that is the host game's, not ours:**

- Gold, experience ("You gain 1 seamanship experience"), stamina, and a named rank
  ("Quartermaster"). The contrib must not publish any of those, on the same grounds as
  the refusal to ship a skill system. A reference panel can leave room for a game to
  fill, but the payload must not carry them.
- Crew morale as a bare percentage. Ours is banded on purpose — a captain is told his
  people are *wavering*, not that they are at 61%. If the panel shows a number, it
  should be showing the game's, not ours.
- A chart that draws land, buoyage, soundings and a plotted route at once. We have the
  data for the marks and the route; land and soundings come from the game's map
  provider, so the panel has to degrade gracefully when a game has authored neither.

**What it settles:**

The layout is additive rather than a replacement — a strip and a right-hand column
around the game's own output pane. That is the answer to the localStorage hazard in the
roadmap entry: nothing here requires stomping a player's arrangement.

**What it does not settle:**

Still open — whether the reference panel lives in this repo or a companion one, and
whether the buttons issue ordinary commands (in which case the panel is a keyboard and
needs no new server surface) or a control channel of their own (in which case it does,
and every one of them needs the same authority check `MARITIME_COMMAND_POLICY` already
performs).
