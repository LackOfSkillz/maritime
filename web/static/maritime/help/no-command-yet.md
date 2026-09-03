# What has no command yet

[Back to the handbook](index.md) · [Every command](commands.md)

Twenty-two command modules cover sailing, fighting, mooring, pumping, repairing and building
a hull. Several of the newer systems are **model and seam only** — the decisions are made,
the results carry their own refusal codes, and there is nothing yet to type.

This page is here so the gap is stated rather than discovered.

| System | The call | Read about it |
| --- | --- | --- |
| Standing orders | `leave_order`, `cancel_order`, `order_in_force` | [Standing orders](standing-orders.md) |
| Passengers | `book_passage`, `land_passengers`, `refund_passage` | [Passengers](passengers.md) |
| Trade | `buy_cargo`, `sell_cargo` | [Trade](trade.md) |
| Stores | `take_on_stores`, `days_of_stores`, `short_allowance` | [Services](services.md) |
| Pilots | `take_a_pilot`, `discharge_pilot` | [Services](services.md) |
| Tows | `take_in_tow`, `slip_the_tow` | [Services](services.md) |
| Refits and value | `take_in_hand`, `what_she_is_worth`, `sell` | [Services](services.md) |
| Salvage | `wreck_report`, `salvage` | [Wrecks](wrecks.md) |
| Posts | `post_to`, `relieve`, `succeed_command` | [Posts](posts.md) |
| The background world | `populate`, `encounters`, `materialise` | [The sea beyond](the-sea-beyond.md) |

## Writing one takes about a dozen lines

Every call above returns a `Result`: truthy on success, with a `code` naming the refusal when
it fails. That is the whole of what a command has to translate.

```python
from evennia.contrib.full_systems.maritime.commands.base import MaritimeCommand

REFUSALS = {
    "no_room": "She has no berth left.",
    "already_aboard": "He is aboard already.",
}


class CmdBook(MaritimeCommand):
    """
    Sell somebody a passage.

    Usage:
      book <person> for <port>
    """

    key = "book"

    def at_helm(self, vessel):
        """Take his money and put him on the list."""
        person, _, port = self.args.partition(" for ")
        traveller = self.caller.search(person.strip())
        if traveller is None:
            return

        booked = vessel.book_passage(traveller, port.strip())
        if not booked:
            self.caller.msg(REFUSALS.get(booked.code, "She cannot take him."))
            return
        self.caller.msg(f"{traveller.key} is booked for {port.strip()}.")
```

`MaritimeCommand` finds the vessel under the caller and checks they may command her before
`at_helm` runs, so a command never has to do either.

Then put it in a cmdset:

```python
from evennia.commands.cmdset import CmdSet


class MyShipCmdSet(CmdSet):
    key = "my_ship"

    def at_cmdset_creation(self):
        self.add(CmdBook())
```

And add *the set* to your ship's rooms as a **class or a dotted path — never an instance**:

```python
room.cmdset.add("world.ships.MyShipCmdSet", persistent=True)
```

Evennia stores a cmdset as the path it was created from, so `MyShipCmdSet` and
`"world.ships.MyShipCmdSet"` both survive. `MyShipCmdSet()` — the parentheses are the whole
of it — works perfectly until the next reload and then quietly vanishes, taking every command
in it. The symptom looks like the commands were never installed at all.

## Before you name one

Two mixins with the same public name **do not raise** — one silently displaces the other, and
the same is true of two commands sharing an alias. Both have caught real bugs here:
`Trades.sell` would have sold the ship out from under a captain who meant to land forty tons
of salt.

Check [every command](commands.md) for the name you want first. The repository has guards for
both kinds of collision in its own test suite.

A live example from the table above: **`buy` is already taken.** It is the shop counter
ashore, and a trade command that claimed it would displace the one players already use. Some
of these want a two-word key - `book passage`, `take in tow`, `store ship` - which reads
better anyway, because that is how the order would actually be given.

---

Next: **[Posts](posts.md)**.
