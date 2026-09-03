# Posts, and who is good at them

[Back to the handbook](index.md)

Gunner, lookout, helmsman and the rest are **posts, not skills.** The work each post does
already existed — gunnery, observation, the helm — it was simply assumed to be done
competently by nobody in particular.

> **No command yet.** See [what has no command yet](no-command-yet.md).

## The six

| Post | What competence at it costs or saves |
| --- | --- |
| `helm` | How fast she answers |
| `lookout` | Whether a faint sail on the skyline is picked out |
| `gunnery` | How fast the battery is served |
| `carpenter` | How much the repair party gets done in a day |
| `master` | *Nothing yet* |
| `surgeon` | *Nothing yet* |

**Four of the six bite.** The master and the surgeon are real posts — they can be filled,
they are in the order of succession, and `competence_at` answers for them — but nothing
downstream reads that answer yet. Saying so is better than a table that implies otherwise:
a seam that looks wired and is not is exactly the state this whole page was built to get out
of.

```python
hull.post_to("helm", somebody)
hull.keeper_of("helm")
hull.relieve("helm")
```

One person to a post and one post to a person. A man at the helm is not also on the lookout,
and a ship that let him be would be getting two people's work out of one.

## Succession

```python
hull.succeed_command()
```

Her captain being gone, she goes to whoever is next down a published order — master, gunner,
carpenter, helm, lookout, surgeon. **This does not decide that a captain is gone.** It answers
what happens when he is, which is a different question and one a game owns.

## The seam: what the contrib owns, and what your game owns

> **This contrib owns what a post does to the ship. Your game owns how good the person
> standing it is.**

That is the whole division, and it exists because character systems are precisely what this
must not import. The moment it shipped one, every game with its own would have to fight it.

The shipped answer is **well enough, always**:

```python
hull.competence_at("helm")   # 1.0
```

So a game that adopts none of this sails exactly as it did before.

## Turning it on

Point the seam at your own function and answer in your own terms:

```python
# settings.py
MARITIME_COMPETENCE_POLICY = "world.seamanship.how_well"
```

```python
def how_well(character, post, vessel):
    """
    Returns:
        competence (float): 0 to 1, where 1 is as well as it can be done.
    """
    if character is None:
        return 0.6            # her people manage without a named hand
    return character.skills.get(post, 0.5)
```

## What it actually buys

Four consequences, each the post doing what that post is *for*:

- **A green helmsman is slower to answer.** Her top speed is a fact about her tonnage; how
  fast she comes round is a fact about whoever has the wheel. He cannot make her slower
  through the water — a consequence that leaked into everything would be a difficulty slider
  rather than a helmsman.
- **A dull lookout misses what is faint.** Note what this is *not*: his horizon is unchanged,
  because the horizon is geometry and no lookout sees over the curve of the earth. What he
  loses is the topsail on the skyline he has not picked out yet. He sees what is near
  perfectly well.
- **A green gunner serves his guns slower**, alongside everything else that slows a battery:
  their own fear, the wreckage they are working round, and the hands aloft instead of at the
  guns.
- **A good carpenter gets more out of the same party.** A party of eight is a party of eight
  either way; what he changes is what they finish in a day.

---

Next: **[Cargo](cargo.md)**.
