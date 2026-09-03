# What a port sells

[Back to the handbook](index.md)

Pilots, tows, stores, refits, and a price on a hull.

> **Mostly no commands yet** — `refit` and `maritime build` exist; the rest is machinery a
> game drives. See [what has no command yet](no-command-yet.md).

## Stores, which are how far she can go

**This is the pacing lever, and it is geography rather than a dial.** How far a hull can go
is what she has aboard divided by how many she is feeding — and both of those are things
somebody chose.

```python
hull.take_on_stores(12.0, cost=Coin.of(gold=3))
hull.days_of_stores()      # the number that decides anything
hull.stores_report().short # a week left or less
```

Days, not a percentage. *"Eighteen days of stores and twenty-two days of passage"* is a
decision; *"stores at forty-one per cent"* is a status bar.

A small crew goes further on the same casks. A ship crowded with marines for a boarding
**cannot cross an ocean**, and nobody has to be told — they can count.

Running out costs the company's **morale**, not their lives. Hunger is slow: a day on short
commons is grumbling, a fortnight starving is a different ship. Killing a game's characters
over biscuit would be writing a survival system nobody asked for.

```python
hull.short_allowance = True
```

Half again as long, at a cost in temper. The decision a captain of the period actually made:
his people's mood traded for sea room.

**A ship nobody has victualled does not starve.** Zero stores is a fact about what she has,
not about whether anybody ever gave her any — so a game that installs this does not find
every existing hull losing morale on the first tick. Once she has been stored she is in the
model for good, because a ship that has *eaten* everything aboard genuinely is starving.

## Pilots

A berth may want one. **Off by default**, so a game that has thought about pilots at no quay
is refused at no quay:

```python
Berth(key="The Bar", position=..., pilotage=True)

hull.take_a_pilot(somebody)
hull.piloted
hull.discharge_pilot()
```

The refusal comes **before the approach**, not at the quay — a pilot boards outside, so a
stranger learns she wants one while there is still sea room to wait in. That is the
difference between an inconvenience and a grounding.

He knows the water. He does not make her narrower and he does not take the way off her, so
`dock` still refuses her for everything else it always did.

## Tows

The same manoeuvre as a tug, a prize being brought in, and a dismasted ship being got off a
lee shore — so it is built once.

```python
tug.take_in_tow(prize)
tug.slip_the_tow()
```

**The tow does not steer.** She is *placed* astern of the tug on the tug's heading every
step — a tow that kept her own helm would be two ships arguing over one position, and one
simply set at the tug's own position would be overlapping her hull.

**And she is not free.** What she costs is felt in the speed the tick actually steers the tug
by, and it depends on the tow's *mass* — so her manifest counts, and the way to make a stubborn
prize towable is to start throwing cargo over the side. A squadron towing two captures makes
four knots and is caught by anything.

Slipping is unconditional. A tow is slipped in a hurry — the weather has come on, an enemy is
in sight — and making it a check would be making the wrong thing difficult.

## Buying a hull

```python
from evennia.contrib.full_systems.maritime import shipyard

shipyard.prices()             # every rig, and what it costs
shipyard.figures("cutter")    # her dimensions, her burthen, and her price
```

**Ships were contracted and bought by the ton burthen**, so the price hangs off the one
figure the yard already computes. A builder who draws a bigger ship gets a dearer one without
touching anything, and the seven shipped rigs come out priced in order of size without
anybody deciding what that order is. A square rig costs more than a fore-and-aft one of the
same tonnage: more spars, more standing rigging, and a great deal more of it aloft.

## What she is worth afterwards

```python
worth = hull.what_she_is_worth()
worth.value       # what she would fetch as she lies
worth.new         # what a hull of her tonnage costs new
worth.condition   # what her state leaves her, 0 to 1
```

Computed from the dimensions and the condition she has **now**. A hull that has been
lengthened is worth more without anybody recording the refit; one that has been hammered is
worth less without anybody writing down the action. A mast over the side costs her more than
the damage number alone, because a buyer sees it from the quay before he comes aboard.

She is never worth *nothing*. Past a point she is timber and iron, and timber and iron are
worth carting away — a hull worth nothing would let a game delete somebody's ship as an act
of tidying.

## Refits

```python
from evennia.contrib.full_systems.maritime import refits

refits.cost_of_refit(hull, "copper")
hull.take_in_hand("copper")
```

Priced as a share of a new hull of her tonnage, because coppering a frigate is not the same
job as coppering a yawl.

| Refit | What it does |
| --- | --- |
| `copper` | Her bottom sheathed. She is faster for it |
| `lengthen` | Cut in half and lengthened. Carries more, turns worse |
| `strengthen` | Frames doubled. Slower, and harder to hurt |

**Every fact a refit changes is one something already reads.** Lengthening her shows how much
of this model is derived: she gets longer, and from that alone she carries more, rates higher,
swings another boat and takes longer to come round — because every one of those was computed
from her length and none of them was stored.

A refit that only made a line of text appear would be a cosmetic, and cosmetics are a game's.

## Selling her

```python
hull.sell(buyer)          # or sell(buyer, price=Coin.of(gold=400))
```

The hull moves and the price is reported. **The money does not move here** — this contrib has
no people's pockets in it, only the ship's own purse, which is hers and goes with her. Who
pays whom is a question about a game's economy.

---

Next: **[The sea beyond the rail](the-sea-beyond.md)**.
