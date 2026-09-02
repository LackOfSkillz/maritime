# Rooms and typeclasses

[Back to the handbook](index.md) / [For developers](for-developers.md)

Four room types, and what happens if you use none of them.

| Class | What it is | When you need it |
| --- | --- | --- |
| `ShipRoom` | A room inside a hull. Moves with her | Always, for anything you stand on |
| `PortRoom` | A quay: a room that also holds a position and berths | To dock anywhere |
| `ShoreRoom` | An ordinary room on land that keeps a map current | Ashore, with the panel on |
| `OceanRoom` | A pooled room for open water | Only if somebody goes overboard |

```python
from evennia.contrib.full_systems.maritime import PortRoom, ShipRoom
from evennia.contrib.full_systems.maritime.rooms import ShoreRoom
```

## Exposure

A `ShipRoom` has an exposure, and it decides what the room can see and what the weather does
to it:

```python
from evennia.contrib.full_systems.maritime.vessel import (
    BELOW_WATERLINE, INTERIOR, OPEN, SEMI_EXPOSED,
)

deck.exposure = OPEN              # a weather deck: sees out, gets rained on
waist.exposure = SEMI_EXPOSED     # under a break: still a weather deck
cabin.exposure = INTERIOR         # inside: sees nothing
hold.exposure = BELOW_WATERLINE   # below: sees nothing, and floods first
```

`OPEN` and `SEMI_EXPOSED` are the weather decks. That distinction is what decides where a
lookout can stand and where a boarding party arrives.

You board onto the highest weather deck, never into a hold. A boarding party materialising
in a sealed magazine would be a routing accident presented as a tactic.

## Mixins, if you have your own room class

The room types above are conveniences. What does the work is a set of mixins, and a game
that already has its own room class should mix those in rather than adopt ours:

```python
from evennia.contrib.full_systems.maritime.client.boundary import NoticesTheWaterline


class MyStreet(NoticesTheWaterline, MyGameRoom):
    maritime_ashore = True
```

`NoticesTheWaterline` tells an arriving player's sessions where they now are. Without it the
panel keeps the last map it was sent, so its dot sits on a room the player has left - and
since every click on the map is routed from that dot, the walk it works out begins somewhere
they are not.

`maritime_ashore = True` says the room counts as land, so the panel stays up in it. The
alternative is tagging the room, which works and is easy to forget:

```python
from evennia.contrib.full_systems.maritime.client.context import (
    ASHORE_CATEGORY, ASHORE_TAG,
)

room.tags.add(ASHORE_TAG, category=ASHORE_CATEGORY)
```

A room with berths counts as land without being told either way. It is the quay, and a quay
is the seam.

## What happens if you use none of them

Everything still works at sea. Ashore, the panel keeps whatever map it last had - which is
only visible at all if `MARITIME_ASHORE_PANEL` is on, and that is off by default precisely
so a game which has not thought about land is not handed a broken map of it.

---

Next: **[Every setting](settings.md)**.
