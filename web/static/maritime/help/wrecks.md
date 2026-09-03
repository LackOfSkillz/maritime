# Wrecks and salvage

[Back to the handbook](index.md)

A ship that founders is not deleted. She was somewhere, she had things in her, and both of
those outlive her.

> **No command yet.** This is machinery a game drives; there is nothing to type. See
> [what has no command yet](no-command-yet.md) for the full list and for how to put a
> command on any of it in about a dozen lines.

## She is a place, not an entry in a table

She stops floating, sinks at her own rate, and comes to rest on the seabed the chart already
knows about — *where the water was deep when she sank*. Where she lies is worked out from the
moment she went down rather than counted on a tick, so a wreck nobody has looked at for a week
is exactly as deep as one that was watched all the way down.

```python
report = hull.wreck_report()
report.depth          # how far down she has got, in metres
report.on_the_bottom  # whether she has finished sinking
report.reachable      # whether anybody can work on her
report.aboard         # what is still in her
```

## Depth is the whole of the difficulty

A ship lost in five fathoms off a beach is a salvage job. The same ship lost in a hundred is
a story. Nothing else gates it — no roll, no skill — because the seabed is already modelled
and she sank to a real place on it.

```python
from evennia.contrib.full_systems.maritime import wrecks

got = hull.salvage(salt, tonnes=6.0)
if got:
    print(f"{got.tonnes:.1f} tons up, {got.left:.1f} still down there")
else:
    got.code   # "too_deep", "nothing_down_there", "not_a_wreck"
```

Reach is `wrecks.SALVAGE_DEPTH` — thirty metres, which is a hard day's work for a diver with
a line and no air. It is the number that turns *where did she sink?* into a question worth
asking.

## What floats free

About a sixth of what she carried breaks loose as she goes: casks, spars, hatch covers,
anything on deck or not struck down hard. Not a hold full of salt — that does not bob to the
surface.

What comes up drifts on the same current everything else afloat drifts on, so somebody who
saw her go down and worked out the set can go and find it. And it is taken *out* of her holds
rather than copied out of them, so what floated away is no longer down there to be salvaged.

## Towing a prize in

A tow is the same manoeuvre as a tug, a prize being brought home, and a dismasted ship being
got off a lee shore — so it is built once. See [what a port sells](services.md).

---

Next: **[Standing orders](standing-orders.md)**.
