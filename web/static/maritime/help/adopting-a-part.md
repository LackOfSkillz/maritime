# Taking only part of it

[Back to the handbook](index.md) · [For developers](for-developers.md)

The common case is not "I want an age-of-sail simulation". It is **"I have a game, and I
want boats in it"** — a ferry across a river, a packet between two islands, a fishing boat
that goes out and comes back.

All of that works without touching the guns, the crew, the weather, the charts or the
damage model. This page is four worked recipes.

---

## 1. A ferry between two fixed points

The smallest useful thing. Two quays, one vessel, and a crossing that takes real time and
can be stood on.

**What you need:** positions, vessels, ports. Nothing else.

```python
# world/ferry.py
from evennia.utils import create
from evennia.contrib.full_systems.maritime import PortRoom, ShipRoom, Vessel, WorldPosition
from evennia.contrib.full_systems.maritime.vessel import OPEN
from evennia.contrib.full_systems.maritime.motion import HelmOrders, MotionLimits
from evennia.contrib.full_systems.maritime.ports import Berth


def build_ferry():
    """A ferry, two slips, and a deck to stand on."""
    north = create.create_object(PortRoom, key="North Slip")
    north.maritime_position = WorldPosition(0.0, 600.0)
    north.add_berth(Berth(key="north", position=north.maritime_position,
                          heading=180.0, max_length=25.0, max_beam=8.0, max_draft=2.0))

    south = create.create_object(PortRoom, key="South Slip")
    south.maritime_position = WorldPosition(0.0, 0.0)
    south.add_berth(Berth(key="south", position=south.maritime_position,
                          heading=0.0, max_length=25.0, max_beam=8.0, max_draft=2.0))

    boat = create.create_object(Vessel, key="the ferry")
    boat.length, boat.beam = 18.0, 6.0
    boat.light_draft = 1.4
    boat.motion_limits = MotionLimits(max_speed=4.0, acceleration=0.6, turn_rate=20.0)
    boat.maritime_position = south.maritime_position

    deck = create.create_object(ShipRoom, key="Ferry Deck")
    deck.vessel = boat
    deck.exposure = OPEN
    return boat, north, south
```

**Driving her.** A ferry does not need a player at the helm. Set her orders and she goes:

```python
boat.orders = HelmOrders(heading=0.0, speed=3.0)
```

She is now under way, crossing at three metres a second, and anybody standing on her deck
crosses with her. Give her `dock` when she arrives, or run her from a script that turns her
round at each end.

**What you do *not* need:** no wind provider, no seabed (she floats on the default flat
one), no crew, no sails, no charts. Passengers walk aboard down a gangway and walk off at
the other end, and the crossing is a real thing that takes real minutes.

**Commands to give the deck**, if you want passengers to be able to look about:

```python
from evennia.contrib.full_systems.maritime.commands import CmdPosition, CmdLookout

class FerryDeckCmdSet(CmdSet):
    key = "ferry_deck"

    def at_cmdset_creation(self):
        self.add(CmdPosition())
        self.add(CmdLookout())
```

---

## 2. A ferry a player drives

Add the helm, and nothing else.

```python
from evennia.commands.cmdset import CmdSet
from evennia.contrib.full_systems.maritime.commands import (
    CmdAllStop, CmdCastOff, CmdDock, CmdHelm, CmdPosition, CmdSpeed,
)


class SmallCraftCmdSet(CmdSet):
    """Enough to drive a boat and tie her up. No guns, no sails, no crew."""

    key = "small_craft"

    def at_cmdset_creation(self):
        self.add(CmdHelm())
        self.add(CmdSpeed())
        self.add(CmdAllStop())
        self.add(CmdDock())
        self.add(CmdCastOff())
        self.add(CmdPosition())
```

Put that on the ferry's deck room instead of `HelmCmdSet`. Every command in the contrib is
importable on its own for exactly this reason.

---

## 3. A rowing boat on a river

Add oars; still no sails and no weather.

```python
from evennia.contrib.full_systems.maritime.commands import (
    CmdEasyOars, CmdGiveWay, CmdHoldWater, CmdOars, CmdStretchOut,
)
from evennia.contrib.full_systems.maritime.oars import OAR_PLANS
```

There are ready-made plans, which is usually all you want:

```python
boat.oar_plan = OAR_PLANS["gig"]      # paddle, canoe, skiff, gig, cutter
boat.man(6)
```

Or describe your own. `positions` is how many oars she is fitted for and `rated_speed` is
what each one is worth:

```python
from evennia.contrib.full_systems.maritime.oars import ROWED, OarPlan

boat.oar_plan = OarPlan(positions=8, rated_speed=2.0, style=ROWED, name="eight oars")
```

Now she is pulled rather than driven, `give way` and `hold water` mean something, and the
crew get tired if you push them. You still have no wind, no charts and no guns.

Currents work here without a provider, if you want the river to carry her:

```python
MARITIME_CURRENT_SET = 180.0     # the bearing the water flows *towards*
MARITIME_CURRENT_DRIFT = 0.8     # metres per second
```

---

## 4. Sailing, but no fighting

Everything up to and including passage, with the combat left out.

```python
from evennia.contrib.full_systems.maritime.commands import (
    CmdBelay, CmdChart, CmdCurrent, CmdFix, CmdFollow, CmdMakeFor, CmdPlot,
    CmdPorts, CmdSail, CmdSound, CmdWeather, CmdWind,
)
```

Add those to the small-craft set above and you have a trading game: she sails, she
navigates, she can be told to make for a port and will get there. No guns are defined, so
nothing can be fired; no damage arrives, so nothing sinks.

---

## What each thing costs you if you leave it out

| Left out | What stops happening | What still works |
| --- | --- | --- |
| Map provider | No terrain, no shoals | Everything else, on a flat sea |
| Wind provider | One wind everywhere | Sailing, at that wind |
| Sail plan | She makes no way under canvas | Oars, engines, being towed |
| Oar plan | She cannot be pulled | Sail, and everything else |
| Crew | Nobody to tire or frighten | Everything; work is instant |
| Guns | Nothing to fire | Everything else |
| Berths on a room | She cannot dock there | Sailing past it |
| Cargo | No holds, no trim effects | Everything else |

**Nothing in that table throws.** Leaving a layer out is a configuration, not a mistake, and
that is what makes it safe to adopt a part of this and get on with your game.

---

Next: **[Your own coast](your-own-world.md)**, when the flat sea stops being enough.
