# Your own ships

[Back to the handbook](index.md) / [For developers](for-developers.md)

A vessel is an ordinary Evennia object with a position, some dimensions, and rooms inside
her. Everything else is optional.

## The least you need

```python
from evennia.utils import create
from evennia.contrib.full_systems.maritime import ShipRoom, Vessel, WorldPosition
from evennia.contrib.full_systems.maritime.motion import MotionLimits
from evennia.contrib.full_systems.maritime.vessel import OPEN

boat = create.create_object(Vessel, key="Kittiwake")
boat.length, boat.beam = 18.0, 5.4
boat.light_draft = 2.2
boat.motion_limits = MotionLimits(max_speed=6.0, acceleration=0.5, turn_rate=6.0)
boat.maritime_position = WorldPosition(0.0, 0.0)

deck = create.create_object(ShipRoom, key="Main Deck")
deck.vessel = boat
deck.exposure = OPEN
deck.height_of_eye = 2.0
```

**Her dimensions are not decoration.** Length and beam decide her footprint against the
ground, how much of her another hull can lie alongside, and how big a target she is. A hull
with no measured length is tested at her centre alone, which is a legitimate state and a
forgiving one.

`height_of_eye` decides how far a lookout standing in that room can see. A masthead room
with a greater height sees further, and that is the whole of the rule.

## Under sail

```python
from evennia.contrib.full_systems.maritime.sailing import FURLED, PolarCurve

boat.polar_curve = PolarCurve()
boat.sail_plan = FURLED
```

A polar curve is what she makes at each angle to the wind. Without one she makes no way
under canvas, which is correct for a barge.

## Hulls to build from

Seven, with their figures worked from real rules rather than invented - yawl, lugger,
cutter, schooner, brig, barque and frigate:

```python
from evennia.contrib.full_systems.maritime.shipyard import HULLS
```

`maritime build <hull>` is the in-game way, standing at a dock.

## Guns

```python
from evennia.contrib.full_systems.maritime.tactical import STARBOARD_BROADSIDE
from evennia.contrib.full_systems.maritime.weapons import Mount, WeaponType

nine = WeaponType(key="nine pounder", name="nine pounder", arc=STARBOARD_BROADSIDE,
                  max_range=800.0, reload_time=90.0, projectile_speed=250.0,
                  accuracy=0.6, damage=10.0)
boat.add_mount(Mount(key="starboard one", weapon=nine, loaded=True))
```

An arc is which way a gun points. Nothing fires unless something is in its arc, so a ship
with only broadside guns genuinely cannot answer something dead astern.

## Her people

```python
from evennia.contrib.full_systems.maritime.crew import ABLE

boat.man(60, ABLE)
```

Or by division, when it matters who is aboard - which is boarding, and almost nothing else:

```python
from evennia.contrib.full_systems.maritime.crew import (
    CRACK, MARINES, ORDINARY, SEAMEN, Division, ShipsCompany,
)

boat.company = ShipsCompany.of([
    Division(rating=SEAMEN, complement=80, fit=80, quality=ORDINARY),
    Division(rating=MARINES, complement=20, fit=20, quality=CRACK),
])
```

A ship with no company works fine: nobody tires, nobody is frightened, and every job takes
no time at all.

---

Next: **[Rooms and typeclasses](rooms-and-typeclasses.md)**.
