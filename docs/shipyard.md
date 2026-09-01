# The shipyard: building ships, laying them up, calling them back

Seven hulls, four commands, and one answer to the question every persistent maritime game
eventually asks — *why is the harbour full of ships nobody has sailed since March?*

    maritime build                      what can be built, and what each hull is
    maritime build <rig> <name>         build one, alongside, ready to sail
    maritime summon <name>              bring a laid-up ship of yours to this dock
    maritime lay up <name>              put one of yours into ordinary and free her berth
    maritime player build on|off        whether players may build at all

## Installing them

One line, on your own character cmdset — on a character rather than a ship, because a ship
is built from dry land by somebody who has not got one yet:

```python
from evennia.contrib.full_systems.maritime.commands.shipyard import (
    MaritimeShipyardCmdSet,
)


class CharacterCmdSet(default_cmds.CharacterCmdSet):
    def at_cmdset_creation(self):
        super().at_cmdset_creation()
        self.add(MaritimeShipyardCmdSet)
```

`maritime summon` and `maritime lay up` are open to everybody, because they only ever act
on ships that already answer to whoever typed them. `maritime build` is staff-only until
`maritime player build on`, and until then it is hidden rather than refused.

## What a dock is

A `PortRoom` with berths in it — the same rooms `dock` and `cast off` already work against.
Nothing new to declare, nothing new to tag.

Building and summoning both want the quay **under your feet**, not one nearby. That is
deliberate: two people standing in the same place should get the same answer, and a bounded
walk outward makes it depend on which way the exits happen to run. Somebody asking in a
market square is told to go to the dock rather than quietly served, because a ship
appearing three streets inland is worse than a refusal.

Laying up needs no dock. The question is about the ship, not about where the person asking
is standing.

## The seven hulls

| Rig | Length | Beam | Draft | Tons bm | Hold | Sleeps |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| yawl | 10.0 m | 3.2 m | 1.3 m | 16 | 11 m³ | 3 |
| lugger | 17.0 m | 5.0 m | 2.1 m | 66 | 93 m³ | 12 |
| cutter | 20.0 m | 6.0 m | 2.6 m | 111 | 141 m³ | 25 |
| schooner | 27.0 m | 7.3 m | 3.4 m | 226 | 321 m³ | 40 |
| brig | 30.5 m | 9.3 m | 3.9 m | 405 | 573 m³ | 90 |
| barque | 45.0 m | 9.5 m | 5.0 m | 666 | 1,132 m³ | 25 |
| frigate | 45.7 m | 12.2 m | 4.2 m | 1,073 | 760 m³ | 280 |

Note the last two rows against each other. The frigate measures more than the barque and
stows barely two thirds as much, because almost everything below her waterline is powder,
shot, water and two hundred and eighty men. The barque is a hold with masts on it and works
with two dozen hands. That difference is the one judged number in the module — `usable` —
and it is the difference between a warship and a freighter.

### Where the numbers come from

Every figure is derived in `shipyard.py`, and the derivations are checked in
`tests/test_shipyard.py` against vessels that existed.

**Tonnage** is Builder's Old Measurement, the rule England used from about 1650 to 1849:

    tons burthen = ((length - 3/5 beam) x beam x beam/2) / 94        feet throughout

Burthen measures *volume*, not weight — one ton burthen is the space a 252-gallon tun of
wine takes, about a hundred cubic feet.

The rule wants the length of **keel** and is given the length **on deck**, which is longer
by the rake of stem and sternpost. That overstates a full-bodied hull by around five per
cent, and it is left overstating rather than fudged:

| Hull | Ours | Recorded | |
| --- | ---: | ---: | --- |
| brig, 100 ft × 30 ft 6 in | 405 | 384 | *Cruizer* class brig-sloop, +5.4% |
| frigate, 150 ft × 39 ft 11 in | 1,073 | 1,065 | *Leda* class fifth rate, +0.8% |

**Displacement** is length × beam × draft × block coefficient × 1025 kg/m³. Deadweight —
what she can carry — is 42% of that, which is what is left of a wooden hull's loaded
displacement once the hull itself is accounted for. Checked against the example sloop in
`example/craft.py`, whose 40-tonne figure was arrived at by a different route: this gives
41.4.

**Holds** are the measured tonnage in cubic metres times `usable`, which runs from 0.25 for
the frigate and the open yawl to 0.60 for the barque.

### Rigs

Three polar curves, not seven. A square-rigger cannot lie closer than about six points and
is at her best with the wind on the quarter; a fore-and-aft rig is the reverse; a lug sits
between and runs better than either. Those are three genuinely different shapes, and giving
each hull its own curve would be seven sets of invented numbers dressed as research.

- **square** — brig, barque, frigate
- **fore-and-aft** — yawl, cutter, schooner
- **lug** — lugger

## In ordinary

A ship out of commission was *laid up in ordinary*: masts and stores ashore, a skeleton
party aboard, and nothing about her the fleet had to think about until somebody wanted her
again. Not sold, not broken up, not sailing.

That is exactly what is wanted here, and it is a state this contrib already had. From
`scripts.py`, long before any of this:

> A vessel with no position has not been launched — she is on the stocks, so there is
> nothing to simulate.

So laying up is not a new mode with new rules. It clears her position, lets go her lines
and drops her from the traffic register, after which every part of the system that walks
the water simply does not find her: the simulation does not tick her, a lookout does not
raise her, nothing can run into her, and her berth is free.

**She keeps everything else** — cargo in her holds, her crew, her damage, and her
compartments with everything in them. Being laid up is a fact about where she is, not about
what she is.

### When it is refused

| | |
| --- | --- |
| under way | A ship with the way on her is going somewhere. So is one at rest with a speed still ordered — she is waiting for wind, or catching a tide. |
| somebody aboard | She is that person's floor, and the floor going into storage while they stand on it should not be possible. |
| not yours | `ownership.may_command` decides: her captain, or her owner if she has no captain. A prize made over to whoever took her is owned by them, so capture needs no second rule. |

## Laying a fleet up on logout

**Evennia fires no hook this contrib can see when somebody logs out.** Losing the last
session sets `location` to `None` and runs nothing — measured rather than assumed, in
[`logout.md`](logout.md).

So a game that wants a player's fleet laid up when they leave calls for it:

```python
from evennia.contrib.full_systems.maritime.ordinary import lay_up_fleet_of


class Character(default_objects.Character):
    def at_post_unpuppet(self, account=None, session=None, **kwargs):
        super().at_post_unpuppet(account=account, session=session, **kwargs)
        if not self.sessions.count():
            lay_up_fleet_of(self)
```

It is offered rather than installed. A contrib that reached into a host game's character
class to do this without being asked would be a contrib nobody could uninstall.

`lay_up_fleet_of` is **silent about what it could not do**. A ship at sea, a ship with a
passenger still aboard, a ship under orders: all are left exactly as they are, and none is
an error. The caller is a logout, there is nobody to tell, and a fleet half laid up is the
correct outcome rather than a partial failure.

## Names must be unique

`maritime build` refuses a name any ship already carries, laid up or not. Two ships called
*Swift* is a harbour where `maritime summon Swift` is a coin toss and where
`@ship owner Swift = someone` may hand over the wrong hull.

The lookup is exact and case-insensitive, deliberately: Evennia's own search matches on a
prefix and would happily return *Swift* when asked for *Swiftsure*.
