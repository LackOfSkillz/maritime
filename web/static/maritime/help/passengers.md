# Passengers

[Back to the handbook](index.md)

Cargo does not care when it arrives and does not complain, which is why a trade in cargo
alone makes a quiet game.

**A passenger is the same tonnage with an opinion.** He is bound for a named place, he paid
before he sailed, and if she does not go there he wants his money back.

> **No command yet.** See [what has no command yet](no-command-yet.md).

## Selling a passage

```python
from evennia.contrib.full_systems.maritime import Coin

hull.book_passage(traveller, bound_for="Careenage", fare=Coin.of(gold=2))
hull.room_for_passengers()   # how many more she could take
hull.passenger_list()        # (("Mister Vale", "Careenage"), ...)
```

A passenger is **whoever the game says is one** — an object and a destination, and nothing
more. A game with NPC travellers and a game where the passengers are other players use the
same machinery.

The manifest comes back as *names*, not objects. A manifest is a document, and a document
does not hold references to things that can be deleted.

## How many she can take

Derived from her internal volume, like her boats are derived from her length — so a builder
who draws a bigger ship gets more berths without remembering to, and cannot give a launch a
hundred of them. About a third of her can be given over to people; the rest is her hold, her
stores, and the working of the ship.

## Landing them

```python
landed = hull.land_passengers("Careenage")
landed.landed   # who went ashore
```

By *name*, not by position — because "has she arrived?" is a question about a game's world
(a port, a berth, a beach) and this contrib does not get to decide how near is near enough.
Passengers bound somewhere else stay aboard.

## Giving the money back

```python
hull.refund_passage(traveller)
```

**This is what makes a passenger different from cargo.** She did not go where she said she
would, and he is entitled to what he paid — which means a captain who took a prize instead of
a passage has been paid for the prize and not for the passage, and can work out for himself
whether that was worth it.

A ship that cannot pay **refuses** rather than going into debt, and he stays aboard, still
owed. Debt is a game's question and this has no view on it.

## Keeping a timetable

A run that repeats has to **close**. If she does not get back to where she started in the
time the schedule allows, the second cycle begins late and every sailing after it begins
later — which is the failure a timetable exists to avoid, so it is the one worth checking
before she sails rather than three voyages in:

```python
from evennia.contrib.full_systems.maritime import passengers

check = passengers.can_be_kept(route, speed=2.0, allowed=86400.0)
check.needed   # how long the passage actually takes
check.slack    # negative means she cannot do it
check.closes   # whether the run gets her back to the start
```

If the last mark is not the first, the check pays for the passage home as well.

---

Next: **[Trade](trade.md)**.
