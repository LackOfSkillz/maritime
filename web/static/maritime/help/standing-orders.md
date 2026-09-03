# Standing orders

[Back to the handbook](index.md)

A captain cannot be at the rail for every hour of a passage, and a mate who only steers for
the next mark will sail a burning ship into an enemy squadron because nobody told him not to.

A standing order is the word you leave behind: **if this, then that.**

> **No command yet.** See [what has no command yet](no-command-yet.md).

## Leaving word

```python
hull.leave_order("squall", when="blowing_hard", then="shorten_sail", priority=5)
hull.leave_order("leak",   when="making_water", then="man_the_pumps", priority=9)
```

Four plain values: a name, a condition, an action, and a priority. **Named rather than
written** — the tempting design stores a function on the order, and it does not survive: an
Evennia attribute is a pickle, and the order that worked all session is gone after a reload.

An order naming a condition or an action nobody knows is **refused**, not stored. An order
that never fires and never says why is worse than no order at all.

## What she can be told to watch for

| Condition | True when |
| --- | --- |
| `making_water` | She has a tenth of her buoyancy in water |
| `on_fire` | She is alight |
| `aground` | She is on the ground |
| `blowing_hard` | It is blowing about a near gale where she is |
| `shoal_water` | There is little enough under her keel to want an order |
| `stranger_in_sight` | Anything at all is in sight |

`stranger_in_sight` is *anything*, not an enemy. Who is an enemy is a question about a game's
world, and this contrib does not have one — a game that knows registers its own and ranks it
above this.

## What she can be told to do

| Action | Effect |
| --- | --- |
| `shorten_sail` | Reef down |
| `make_sail` | Set working canvas |
| `heave_to` | Furl, and take the way off her |
| `clear_for_action` | Fighting sail |
| `man_the_pumps` | A quarter of her company to the pumps |

## One order acts, and the rest are named

Two orders that both want the helm cannot both have it. The **highest priority whose
condition holds** is the one in force, ties going to the order left first — and every other
order that also held is *reported as overridden*:

```python
standing = hull.order_in_force()
standing.order        # the one that acted
standing.overridden   # the ones that wanted to and lost
```

A captain who finds his ship hove to instead of reefed needs to be told which order did it.
An order losing silently is the single worst thing this could do.

## An order lets go of her again

The condition is re-read every tick rather than latched. A ship that shortened down for a
squall **makes sail again when it passes**, without anybody remembering to say so — and a
latched order would have left her reefed for the rest of the voyage because it blew hard once.

## Registering your own

Both registries merge a game's own over the shipped ones, so you can add a condition and
also *replace* one:

```python
# settings.py
MARITIME_ORDER_CONDITIONS = {"enemy_in_sight": my_module.enemy_in_sight}
MARITIME_ORDER_ACTIONS = {"beat_to_quarters": my_module.beat_to_quarters}
```

Anything shipped is answerable out of state this contrib already owns. Anything that spends
money, sends a message or decides who is a friend is yours.

---

Next: **[Passengers](passengers.md)**.
