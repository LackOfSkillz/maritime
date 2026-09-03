# Trade

[Back to the handbook](index.md)

**Off unless you turn it on.** An economy is the part of a game most likely to already exist,
and a contrib that quietly started pricing salt would be the worst kind of guest.

```python
# settings.py
MARITIME_CARGO_ECONOMY = True
```

With it off, every call below returns a clear refusal (`economy_is_off`) rather than an
error from three frames down — and nothing moves.

> **No command yet.** See [what has no command yet](no-command-yet.md).

## Why this is worth having at all

Because the interesting half was already built. [Cargo](cargo.md) models **both** capacities:

- Heavy cheap cargo — grain, salt, coal, timber — fills her tonnage while the hold stands
  half empty.
- Light valuable cargo fills the volume long before her marks go under.

**The cargoes worth thinking about are the ones that trade the two off**, and no other naval
system can express that, because none of them carry two capacities.

## A port is two lists, not a price list

```python
from evennia.contrib.full_systems.maritime import Market

harrowmouth = Market(key="Harrowmouth", exports=("grain", "hay"), imports=("wine", "iron"))
careenage   = Market(key="Careenage",   exports=("wine", "iron"), imports=("grain", "hay"))
```

A port has a **surplus of what it exports and a shortage of what it imports**, and the price
follows from that — it pays about three fifths for what it has too much of and asks about
seven tenths more for what it is short of.

Two numbers per port instead of one per commodity per port. A builder writes what a place
*is* — a grain coast, a mining port, a city that eats — and the prices fall out. Authoring
prices directly would mean authoring them again every time a commodity was added.

**And the trade routes draw themselves.** Carry what is cheap here to where it is dear; the
map already says where that is. Change what a place exports and you change the whole pattern
of who sails past it, including the [background shipping](the-sea-beyond.md).

## Buying and selling

```python
bought = hull.buy_cargo(harrowmouth, grain, 40.0)
bought.tonnes    # what actually went in
bought.price     # what she was charged for exactly that

hull.sell_cargo(careenage, grain, bought.tonnes)
```

She is charged for **what went in**, not what was asked for — her hold or her marks may stop
her short, and a captain charged for cargo still standing on the quay would be right to
complain. Selling works the same way round: she is paid for what actually came out of her.

## What a thing is worth

The standing worths live in the optional economy module and **not** on `Commodity`, which is
deliberately silent about value — so a game that wants the stowage model without the prices
gets it.

They are authored, and honestly authored, rather than dressed up as a derivation. It is
tempting to say value falls with how densely a thing stows; hay disposes of that idea at
once, being both bulky and worth almost nothing.

## Piracy follows value, not traffic

```python
hull.what_she_carries_is_worth()
```

A raider who hunted *traffic* would spend the game chasing grain coasters, and choosing a
cargo would mean nothing. A raider who hunts *value* goes where the wine and the tobacco are
— so **loading a rich cargo is choosing a dangerous voyage**, and nobody has to tell you so.

That is one decision seen from two sides. The other side is in
[the sea beyond the rail](the-sea-beyond.md).

---

Next: **[What a port sells](services.md)**.
