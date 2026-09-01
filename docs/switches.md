# The switches, and who may flip them

Four commands, all in one cmdset, all about which interface the game shows and how much of
the world it shows. Three set the server; the fourth is the one a game can lend to its
players.

    maritime ui [on|off|hybrid]     which interface the game presents, for everybody
    maritime uncharted [on|off]     draw the sea as it truly is, for development
    maritime player gui [on|off]    whether an individual may choose for themselves
    maritime gui [on|off|hybrid|default]   what one player chose, when the game allows it

A fifth switch lives in `switches.py` with these and is documented with the commands that
read it: `maritime player build on|off`, which decides whether players may build ships. See
[`shipyard.md`](shipyard.md).

## Installing them

One line, on your own character cmdset:

```python
from evennia.contrib.full_systems.maritime.commands.interface import (
    MaritimeInterfaceCmdSet,
)


class CharacterCmdSet(default_cmds.CharacterCmdSet):
    def at_cmdset_creation(self):
        super().at_cmdset_creation()
        self.add(MaritimeInterfaceCmdSet)
```

Everything else this contrib offers lives on a `ShipRoom`, so that an order needs a deck
under you. These are the exception and have to be: somebody who has switched the panel off
is by definition somewhere it is not showing, and a command reachable only from a deck they
cannot see is a switch with no way back.

## Who can use them

All four are locked `cmd:perm(Admin)`, which in Evennia's hierarchy means admins,
developers and the superuser — and nobody else. Adding the cmdset to your character class
therefore puts *nothing* in front of your players.

`maritime gui` widens itself to everybody the moment somebody runs `maritime player gui on`,
and narrows again on `maritime player gui off`. It is hidden rather than merely refused,
because a command a player can see in `help` and cannot use is a fair question with no good
answer.

Want them tighter? Each command has one `locks` line; `cmd:perm(Developer)` keeps admins
out.

## What each one does

### `maritime ui`

Says when the maritime panel is shown, for the whole server.

| Mode | Aboard a vessel | Ashore |
| --- | --- | --- |
| `on` | maritime panel | maritime panel |
| `off` | your game's own interface | your game's own interface |
| `hybrid` | maritime panel | your game's own interface |

`hybrid` is the default, and it is the shape most games want: the panel belongs to the sea
and hands the screen back at the gangway. A game whose whole world is a coast, or which has
no other interface to return to, wants `on`.

**One setting for the game, not one per player.** Which interface a game presents is a
decision about what the game *is*. A per-player switch would make it a matter of taste, and
would also make every bug report begin with working out which mode the reporter was in.

It overrides `MARITIME_ASHORE_PANEL`, which is what a game does out of the box, and it
survives a reload.

### `maritime uncharted`

A development switch. With it on, every chart reads the world itself:

- nothing is off the paper — a chart's rectangle stops bounding what can be seen
- no survey error is applied — quality is exactly 1.0, so soundings are the ground
- a ship carrying no chart at all still gets one

That makes the whole world visible for building and testing, which is what it is for.

**Turn it off before anybody plays.** A game running with this on has no navigation in it:
the ordinary business of not knowing what is under you is precisely the thing being
switched away.

It opens the paper, not the lookout. Other ships are still seen when they are seen, and
fog is still fog.

It does not change how far the chart is drawn, either. That is the zoom, it belongs to the
person looking, and it is capped at a hundred kilometres a side as it always was.

### `maritime player gui`

Says whether individual accounts may override the interface for themselves.

Off by default. One interface for one game is the position this contrib argues for — but
it is a position rather than a fact, and a game whose players include somebody who cannot
use a graphical panel at all has a reason the contrib cannot answer from here. So the
decision is offered to whoever runs the game rather than taken away from them.

Turning it off again does **not** erase what anybody chose. It stops those choices being
read, and turning it back on restores them — so a game can be switched back and forth
while testing without quietly wiping a preference a player set months ago.

### `maritime gui`

What one player chose. Same three modes as `maritime ui`, plus `default`, which clears the
choice and puts them back on whatever the game does.

Kept against the account rather than the character, so it follows somebody between the
characters they play.

## Where all this lives

`maritime/switches.py` holds the values and their persistence — all five of them, the
shipyard's included. `maritime/commands/interface.py` holds these four commands, and
`maritime/client/context.py` holds what the modes *mean* for a person standing in a
particular room, which is a different question.

Everything is kept in `ServerConfig` rather than in a settings file, because a switch
changed at runtime has to survive a reload without anybody editing Python and restarting a
server — which is the whole reason for having a command instead of a setting.

The values are cached in the process that reads them, because the interface asks what mode
it is in every time anybody moves and on every tick of the panel, and a database query for
each of those is a cost paid thousands of times to learn something that changes about once
a month. The setters write through the cache, so a switch takes effect at once. A write
from a *different* process — a shell, a script — stays invisible until a reload, which is
true of a great deal else in Evennia.
