# Hooking into it

[Back to the handbook](index.md) / [For developers](for-developers.md)

The places this deliberately stops, and how to carry on from there.

## What it refuses to decide

Each of these collides with whatever your game already has, so it is left to you rather than
answered badly:

| Question | Why it is yours |
| --- | --- |
| What a ship is worth | You have an economy; this does not |
| What a cargo sells for | The same |
| What being in the water costs | You have health and stamina rules |
| What a person's stamina is | Crews tire; people are yours |
| Who may command a captured ship | Authority is your game's shape |
| What becomes of an offline passenger when she founders | A policy nobody should pick for you |

None of them is a gap. Each has a seam where your answer goes.

## Ownership and money

Ownership moves and publishes why - sold, granted, captured, inherited - and your game wires
its purchase to that event. What she cost is between you and your player.

## Who may give orders

```python
MARITIME_COMMAND_POLICY = "world.sea.who_may_command"
```

```python
def who_may_command(character, vessel):
    return character is vessel.captain or character.check_permstring("Admin")
```

The default is: her captain, else her owner, else anybody aboard an unowned ship.

## What she says

Every word a ship speaks goes through a narrator, and replacing it changes the voice of the
whole game without touching a rule:

```python
MARITIME_NARRATOR = "world.sea.MyNarrator"
MARITIME_WATER_NARRATOR = "world.sea.MyWaterNarrator"
```

```python
from evennia.contrib.full_systems.maritime import VesselNarrator


class MyNarrator(VesselNarrator):
    def phrase_for(self, event, **detail):
        if event == "run_aground":
            return ("You have put her on the putty.", "She is aground.")
        return super().phrase_for(event, **detail)
```

Two forms are returned: the full one and a terse one. Which a player gets is theirs to
choose, not yours to guess.

## Cargoes

```python
MARITIME_COMMODITIES = "world.sea.MY_CARGOES"
```

A stowage table: what each thing is, what it weighs and how much room it takes. Replacing it
does not require touching a hold.

## Time and dice

```python
MARITIME_TIME_PROVIDER = "world.sea.MyClock"
MARITIME_RNG_SEED = 12345
```

Pinning the seed makes a fight replay identically, which is how the scenarios in the test
suite work and how you would reproduce a bug report.

---

Next: **[Every command](commands.md)**.
