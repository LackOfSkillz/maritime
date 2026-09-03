# The sea beyond the rail

[Back to the handbook](index.md) · [For developers](for-developers.md)

An empty sea is cheap and it is also dull. This is what fills it without paying for it.

## A background ship is a record, not a ship

No typeclass, no room tree, no attributes, no per-vessel script. A key, two dimensions, a
route, a speed, and the moment she sailed:

```python
from evennia.contrib.full_systems.maritime import strategic

record = strategic.StrategicVessel(
    key="Marigold",
    passage=strategic.Passage(route=route, speed=2.0, departed=now),
)
handle = strategic.fleet().enter(record)
```

**She advances by arithmetic, not by simulation.** A vessel nobody has watched for an hour
has not sailed three thousand one-second steps — she has sailed an hour, and where that puts
her is a division:

```python
strategic.fleet().fixes(now)   # the whole background world, in one pass
```

A hull untouched for a week costs exactly what one untouched for a second costs. That is the
property that makes a background world affordable at all, and it is measured in the tests at
a hundred, five hundred and a thousand sail.

## Strategic is not dormant

Conflating them is a bug waiting to happen. A record is a **summary** — it rehydrates an NPC
trader perfectly, because nothing about her is individual. It cannot rehydrate a chest
somebody left in the cabin, a room somebody renamed, or a player asleep in the hold:

```python
made = strategic.summarise(hull)
if not made:
    made.code   # "occupied" - she must go dormant instead, keeping her rooms
```

**Anything in her compartments counts, not just people.** A game that let a player leave a
coil of rope on deck has let them leave something, and this contrib does not get to decide it
was not worth keeping. It refuses rather than truncating, because a summary that quietly
dropped what it could not carry would work perfectly in every test and lose somebody's
belongings the first time it was used in earnest.

## Bringing her back

```python
hull = strategic.materialise(record, now)
```

**Identity is preserved.** She comes back with the name and dimensions she went away with, at
the place the arithmetic says she got to — not at the place she left, and not as a fresh ship
that happens to look like her.

## Who is out there, and why

```python
from evennia.contrib.full_systems.maritime import shipping

coast = (
    shipping.Anchorage(key="Harrowmouth", position=..., market=harrowmouth),
    shipping.Anchorage(key="Careenage",   position=..., market=careenage),
)
shipping.populate(strategic.fleet(), coast, merchants=6, fishermen=4, patrols=1, raiders=1)
```

**Nobody authored a shipping lane.** A lane is what the ports *are*: somewhere with a
surplus, somewhere with a shortage, and a commodity both of them have an opinion about — see
[trade](trade.md). Change what a place exports and the traffic past it changes, which is what
a builder would expect and what a table of authored routes would not do.

| Who | What they do |
| --- | --- |
| Merchants | Load where a thing is cheap and carry it where it is dear |
| Fishermen | Out and home off their own coast, which is what makes a coast feel inhabited |
| Patrols | A beat that closes, because one that did not would be a ship leaving her station |
| Raiders | Work the richest passage there is |

Patrols and raiders are both faster than the trade, which is the whole reason either of them
is worth being afraid of — a merchant who could outrun a raider would never meet one.

Departures are staggered by index rather than rolled, so **the same world built twice is the
same world**. A background fleet that shuffled itself on every restart would make a bug in it
impossible to reproduce.

## Who is in the offing

```python
for seen in shipping.encounters(strategic.fleet(), hull.maritime_position, now):
    seen.record, seen.fix.position, seen.distance
```

**Nothing is materialised here.** This says who is out there and where they have got to.
Turning one into a real hull is `materialise`, and *deciding* to is the game's — because only
a game knows whether its players are in a state to be interrupted by a strange sail.

---

Next: **[What has no command yet](no-command-yet.md)**.
