# Maritime

Contribution by Gary Mix, 2026

A maritime simulation system for Evennia. Vessels occupy continuous world coordinates
rather than moving between ocean rooms — they gather way, come round, sail with the wind
on their own polar curves, make leeway, anchor, run aground, get set off course by a
current, and sight each other across a horizon that depends on how high the lookout is
standing. They carry characters in ordinary
Evennia rooms while under way. The sea has a bottom, the bottom has depth, and the tide
moves the surface over it. Genre-neutral, and usable with core Evennia alone.

## Status

**Early development.** Nothing here is API-stable.

Working and tested:

- **The world.** Foundations, the spatial model and a tiled seabed, tides, currents,
  weather and sea state, dredged channels, meridians and parallels, shaded relief.
- **The ship.** Vessels and their interiors, the simulation service, sailing, oars,
  grounding and kedging off it again, cargo and stowage, seven hulls to build from, laying
  her up in ordinary and bringing her forward.
- **Getting about.** Observation, dead reckoning and fixes, charts, buoyage with safe-water
  steering, routes and the sailing master, ordering a passage to a named port, ports and
  berths, discovery of what nobody had seen before.
- **Fighting.** Tactical geometry, weapons, ammunition as intent, point of impact and
  raking, damage tracks, battle sails, wind shadow, opportunity fire, how fast a crew
  answers, ramming and sheering, boarding and grappling.
- **People.** Who owns and commands a ship; her company - quality, morale, exhaustion and
  mutiny, with marines, seamen and oarsmen as distinct divisions.
- **The screen.** An optional graphical interface for web clients, which shows a chart at
  sea and a clickable map of the town ashore, and runtime switches for whoever runs the
  game.

Not built: fire, flooding, the strategic layer, and the service economy.

The first vertical slice runs end to end: walk aboard at one quay, cast off, make sail,
sail continuous water, sound your way through a channel past a rock ledge, come alongside
at another quay and walk ashore — without traversing a single ocean room.

What works today:

```text
> wind
The wind is 17 knots from 0-0-0. She has it on the beam, her best point of sailing.

> sail working
You call out, "Set working sail!"
The mate answers, "Working sail, aye sir."

> helm 090
You call out, "Helm, steer 0-9-0."
The helmsman answers, "Steering 0-9-0 now, sir."
The deck leans as she comes round to starboard.
    ...
The helmsman reports, "Vessel steady on 0-9-0 now, sir."
She runs east, the sea sliding past her rail.

> position
Test Sloop
  Position   0°08.6'S  0°00.5'E
  Heading    0-9-0   ordered 0-9-0
  Speed      6.6 kt   ordered 0.0 kt
```

Standing on the deck, two metres above the water:

```text
> lookout
Nothing in sight. The horizon is 2.9 miles off.
```

Twenty-eight metres up her mast, the same ship at the same instant:

```text
> lookout
The lookout reports:
  On the starboard beam              5.3 leagues   a sail
```

The water is moving too, so where she points and where she goes are different questions:

```text
> current
The current sets 1-8-0, drift 0.8 knots.
She heads 0-9-0 and makes good 0-9-7 at 6.6 knots.
```

Arriving is walking down a real gangway, not a teleport:

```text
> dock
You call out, "Take her alongside!"
The mate answers, "Alongside, aye sir."
Lines go ashore fore and aft. She is made fast at fishmarket steps, starboard side to.
The gangway comes down onto the quay.

> ashore
Harbour B - Fishmarket Steps
Steps run down from a fishmarket to a stub of quay, slick underfoot and smelling of it.
Exits: gangway
```

And the lead is cast the way a lead line is actually read:

```text
> sound
Elias orders a cast of the lead.
The leadsman calls, "By the deep six!" That is 4.9 fathoms under her keel.
```

Go over the side and the sea is a place too, without a single ocean room having been built
for it in advance — one is lent to your square of water, and taken back when you leave:

```text
> look
You are in the open sea, lifting and falling on a low swell.
A strong breeze comes out of the north-west, and takes the tops off the water.
A vessel under sail lies to the east, 1.3 leagues off.
```

She can be seen because her masts stand above the curve. From her deck, looking back,
there is nothing on the water at all.

Cargo is two capacities, not one, and which of them stops you depends on what you are
carrying. The same hull, twice:

```text
> stow 400 salt
You call out, "Get 400 tons of salt aboard."
The mate answers, "Aye sir - rig the yard tackle."
260 tons of salt go down into the lower hold.
140 tons of salt stay on the quay - the holds are full, though she would carry the
weight of something denser.

> manifest
Kestrel - manifest
  salt                   260.0 tons     260.0 m3
                         260.0 tons     260.0 m3 stowed

  Draught    3.89 m   freeboard 0.11 m
  Capacity   she has cubed out - the holds are full
  She is loaded past her marks. She is not fit to go to sea.
```

The same holds, filled with something light, are a completely different ship:

```text
> stow 400 wool
61 tons of baled wool go down into the lower hold.
339 tons of baled wool stay on the quay - the holds are full, though she would carry the
weight of something denser.

> manifest
  baled wool              61.6 tons     260.0 m3

  Draught    2.45 m   freeboard 1.55 m
```

And the draught is not a number on a sheet. Over a shelf with 2.4 metres of water on it,
loaded she is 1.5 metres into the ground and light she crosses with 40 centimetres to
spare — the same water, and the cargo is the whole difference.

## Land in a maritime world

```
build_aetos
```

That builds Careenage and the six islands: 79 rooms, 164 exits, eighteen people behind
counters. It prints the dbref of the room new players should start in, for `START_LOCATION`.

Ashore you get `browse`, `buy`, `market` and `sell` — installed on the shore rooms
themselves, so they exist on land and never on a deck. A street with nobody trading in it
answers "There is nobody selling anything here", which is the honest answer and cheaper than
working out which rooms deserve the verbs. Islands trade by the ton: each wants
one cargo and offers another, and the six of them make a round a captain can run. It is the worked example of the question this contrib gets asked most - how does an
ordinary Evennia area sit inside a world with coordinates in it?

**The answer is one room type.** A `PortRoom` is an ordinary room that also holds a
`WorldPosition` and a berth. Everything landward of it is rooms and exits like anywhere else;
everything seaward is the maritime coordinate system. Nine rooms in the example are
`PortRoom`s and the other eighty are not.

By default, stepping ashore hands the screen back to your game — maritime gets out of the
way, because a harbour interface in a market square is the failure a player actually notices.
A game whose world *is* a coast can keep the panel up instead:

```python
MARITIME_ASHORE_PANEL = True
```

Then the chart is replaced on land by a map of rooms and the ways between them, with
click-to-move. Routes are walked as ordinary movement commands, one at a time — nothing
teleports, so a locked gate stops the walk exactly where it would stop the player.

**Rooms ashore keep the map current by being the right kind of room.** A quay
(`PortRoom`) already does. For the streets between them, use `ShoreRoom` — an ordinary room
that reports arrivals and counts as land:

```python
from evennia.contrib.full_systems.maritime.rooms import ShoreRoom
```

A game with its own room typeclass mixes in `NoticesTheWaterline` instead; the mixin is the
contract and `ShoreRoom` is the convenience. A room that does neither still works — the
player can walk through it — but the panel keeps the last map it was sent, so its dot sits
on a room they have left, and clicking works out a route from there.

**She can run into other ships, and it hurts her too.** Ramming is resolved on movement
against the hull she reaches first, from the closing speed and the angle and the two
displacements — so meeting a ship is violent, chasing one is not, and a beam strike is the
one worth manoeuvring for. What is on her bow decides how the cost is split:

```python
vessel.bow_fitting = "ram"      # or "spur", or "plain"
```

Grapples are a count rather than a yes: how many irons get across depends on how much of the
two hulls are alongside, how fast she is sheering away, and how many hands there are to
throw them. More lines hold harder — by the square root of the count, so breaking free stays
possible — and clearing them again takes correspondingly longer.

A beak drives more of the blow into her and takes less of it back, which is what a beak is
for. The ship being run at fires everything that bears in the moment before impact — and
mostly misses, because a bow-on ship is the narrowest target there is, which is why ramming
is worth attempting. Every gun that speaks starts its reload, so she meets what follows with
an empty battery. Running down an oared ship's side shears off the looms she has out, and she breaks them
against your topsides on the way past.

**Every line on the map is one move.** Flattening a graph of rooms onto a grid always leaves
some pairs a long way apart — two ends of a street reached by different routes, a lane that
doubles back — and the straight line between them crosses four other streets and reads as a
bridge through the air. Those lines are not drawn. Nothing true is lost: the rooms are still
on the map, still clickable, and clicking still routes over every exit the room really has.

**The map takes the top half of the panel and the bottom half is yours.** The contrib creates
one empty element and never looks inside it again:

```javascript
document.getElementById("maritime-host").append(yourCharacterSheet);
```

Render a vitals bar, a quest log, a portrait or nothing at all. The half is reserved whether
it is used or not, so a builder can design against room they can actually see, and the panel
does not move the goalposts the moment they render their first element. The element survives
every redraw, so listeners bound to what you put in it stay bound.

## A real coast, shipped

```python
MARITIME_MAP_PROVIDER = "evennia.contrib.full_systems.maritime.baked_world.AetosCoast"
```

That is a game sailing a generated coast — a harbour with moles and a bar, a dredged approach
between two banks, a tidal creek, an isolated pinnacle and a chain of six named islands —
with nothing installed, no seed, and nothing to build.

It works because **the seabed is deterministic and therefore worth writing down**. The coast
was generated once, elsewhere, and sounded into a bundle of about three megabytes: five
sheets from a kilometre-spaced coastal one down to a ten-metre inshore one over the harbour
and the islands. The same bargain a game engine makes when it ships baked terrain rather than
generating it on every machine at every launch.

**Soundings are not a world, though**, and that is the part worth knowing if you build your
own. A grid of elevations gives depth and a coastline and nothing else — no bottom to hold an
anchor or hole a hull, no rock the survey marked, no island with a name to be first to, no
latitude to rule a chart by. Those live in `world.json` beside the soundings, in plain text,
so the interesting half of a world stays readable and only the bulk is binary.

Two honest limits. Zoom in past the finest sheet and the ground is interpolated — smooth
rather than detailed, because there is no generator to ask. Sail past the bundle's edge and
there is open ocean and an unsurveyed chart, because the survey stops where the surveyor
stopped. A game that wants detail everywhere wants a generator, and can bake its own bundle
from one with `bake.bundle`.

## The example world

`example` builds it. One mainland, six islands, three boats:

```text
Pond Shore  --  Water Meadow  --  River Head
                                      |
                                (row down the river)
                                      |
                Stone Quay  --  Harbour Town  --  Ferry Steps

Stone Quay  ==  Gullstone  ==  Blackrock  ==  Thornholm  ==  Cradle Isle
            ==  Farne  ==  Bare Skerry
```

There is deliberately no path from the river head to the harbour. The river is the road,
and rowing down it is how you get there — rowing back up it is a different afternoon.

**Each of the three boats teaches one thing.** The kayak is a pond boat: stop paddling and
the breeze puts you ashore, because nothing else is moving her. The canoe is a river boat:
the same stroke is seven minutes a kilometre downstream and thirty-seven up, and with one
paddler instead of two she will not get up it at all. The sloop is a sea boat, and she
carries two sweeps that do nothing at all until the wind dies.

**Land is ordinary rooms with ordinary exits.** An island is a little graph you walk around
exactly as you would walk around anywhere else; one room of it is a `PortRoom`, which is an
ordinary room that also stands at a world position and offers a berth. That is the entire
join between a 2D room graph and a 3D sea.

Every leg between islands is between five and ten minutes under working sail, and there is
a test that says so — moving an island a few hundred metres is exactly the kind of edit
that looks harmless.

The speed that spacing rests on was *measured*, not assumed. The first layout was built
against a guess of four metres a second; she actually makes 2.2 on that heading, so every
island was nearly twice as far out as it should have been — and the test passed anyway,
because it was checking against the same guess. Sailing one leg is what caught it. The
example's wind is a southerly for the same reason: on an easterly course that puts it
across her beam, and from the west she makes 1.5 and the chain becomes a slog.

## Design

Twenty ideas do most of the work. `docs/architecture.md` has the rest.

**Ships are simulation entities, not moving rooms.** A vessel holds a position; her
cabins and holds are ordinary rooms that name her as their position source. Nobody aboard
stores a coordinate, so moving the hull moves the whole ship's company at once, and a
hundred passengers cost no more than one.

**Continuous coordinates are authoritative, in three axes.** `WorldPosition(x, y, z)`
where z is elevation against a sea-level datum — negative is seabed, positive is dry land.
There is no separate depth map: water depth is the difference between the current surface
and the terrain beneath it, which is what makes tides move every depth in the world
without touching any terrain.

**The host game owns the clock.** Maritime never invents a travel-speed multiplier. It
reads elapsed game time from a provider, so a vessel's eight knots means eight nautical
miles per *in-world* hour whatever `TIME_FACTOR` the game runs at.

**The domain returns data; a separate layer speaks.** Physics and rules are plain Python
returning structured results, and nothing in the simulation knows the word "aground".
`messaging.py` holds every player-facing word the system produces — the ship's own
narration and the crew's replies to orders alike — and decides which change is worth
mentioning and who hears it — on deck you
watch the sea go by, below you feel her heel and hear water on the planking. Point
`MARITIME_NARRATOR` at a `VesselNarrator` subclass, override one method, and every line
the system speaks changes without a line of physics moving.

**The crew do not know where they are.** The engine does. A dead reckoning is advanced by
the course steered and the distance logged — which is all a compass and a log line give you
— so it drifts from the truth by exactly the current and the leeway nobody aboard could see.
Nothing rolls an error: in slack water a reckoning is perfect, and it should be. Take a fix
off a landmark and you learn not just where you are but what has been setting you, which is
the number that lets you steer the next leg properly.

**A heading is not a track.** The water moves as well, and an observer ashore sees the sum
of the two. `speed` is speed *through the water* — what a chip log measures — and the
over-ground course and speed are derived, so a current never has to be subtracted back out
of anything. A current is named for where it goes and a wind for where it comes from; both
are kept, because normalising one to match the other is how a bearing ends up reversed deep
inside a passage calculation.

**Units are display; metres are the truth.** Nothing inside the simulation knows what a
league is. What a player is shown is two settings, not one, because a ship reckoned her run
in leagues and her water in fathoms at the same moment — and every distance scheme falls
back to cables under a mile, because no scheme has a useful word for a tenth of its own
unit and they all borrowed the cable instead. A game in another genre changes one line and
gets kilometres.

**A physical relationship creates a traversal.** Docking does not teleport anybody. Lines
go ashore, a gangway is rigged as two ordinary Evennia exits, and it is deleted when the
lines are let go — so walking ashore is walking, and can be followed, blocked, watched and
locked like any other movement without a docking system having to reimplement any of it.

**Seeing is a height problem, not a range problem.** A hull is hidden by the curve of the
water, so how far you can see depends on how high your eye is — and how far you can see a
*particular* ship depends on how high she is too, because her masthead is over your horizon
looking back. Height of eye comes from the compartment you are standing in, so a masthead
is worth building rather than worth mentioning.

**The seabed is authored a square at a time, and a drawn hazard is exact.** A vessel loads
only the tiles her track crosses, so finding what is on this stretch of bottom does not
mean searching every rock in the world. More than that: a hull is sampled at seven points
on her outline and something small enough fits between them — two metres of rock four
metres off the centreline of a six-metre beam, as it turns out — so an authored hazard is
tested against the whole corridor she swept instead. She is stopped where she *enters* it,
because closest approach is on the far side of a rock she has by then sailed through.

**A pulling boat is the opposite of a sailing one.** A ship is not asked how fast to go —
she goes as fast as the wind on that heading allows. A boat under oars goes as fast as the
people in her are working, so her speed is a rated speed times the stroke times the
*fraction of oars actually manned*: a six-oared gig pulled by two hands is a slow boat with
four oars stowed. Sail wins where a hull has both, because nobody rows a boat that is
sailing — and oars take over in a calm without anybody ordering it. A boat nobody is
driving is not a boat that stays put: the stream carries her and the wind nudges her by her
own windage, which is why a kayak left alone on a pond ends up against the lee shore.

**A hull has two capacities and they are not interchangeable.** Deadweight is the mass she
can carry before she is too deep; hold volume is the space the cargo occupies. Stowage
factor decides which one stops you, and the spread is enormous — iron stows at about a
third of a cubic metre per tonne and hay at nine. So "she is full" is never the whole
answer: a ship that has *weighed out* will take nothing further, and one that has *cubed
out* would still carry something denser.

**Where a room is needed at all, it is a view rather than a place.** Open water gets no
rooms of its own; a small pool is lent out, one to each square of sea that currently has
somebody in it. Because a swimmer's truth is their position and the room only shows the
cell it falls in, releasing one loses nothing — and a lone drifter never changes room at
all, since the room can simply pan to the new water instead.

**Boarding is decided by relative velocity, not by speed.** Two ships running side by side
at ten knots on the same course are motionless with respect to each other and can be lashed
together at leisure; the same two on opposing courses tear the irons out of the rail.
Matching her course and speed *is* the manoeuvre. And the crossing is two ordinary exits —
`board` is not a command, it is the exit's name — so a hostile traversal can be followed,
blocked, watched and locked like any other, and none of that needed designing twice.

**Owner is property; captain is command; admiral is neither.** A merchant who owns four
ships is aboard at most one of them, and a captain who owns nothing still gives the orders on
the deck he stands on — so they are two references, not one controller field. Rank is derived
on every call from how many decks answer to you rather than stored, so it arrives with the
second ship and leaves with the loss of one. Whether a given person may give a given hull an
order is *one function*, `MARITIME_COMMAND_POLICY`, replaceable whole: a game where the mate
may steer but not fire replaces it and is obeyed everywhere without the vessel knowing.

**There is an optional client protocol, and it is a protocol rather than an interface.**
The contrib publishes what a character can see - which situation they are in, and later
their instruments, chart and contacts - and something may draw it. A browser panel is one
consumer; a scriptable terminal client is another. Walking aboard is noticed without a host
game wiring anything, because the rooms on both sides of a gangway belong to this contrib.
Two rules hold it together: the panel is a repeater rather than an oracle, and a graphical
client must never make the navigator more knowledgeable than the character. It ships no
artwork and is finished without any, offering variables a host game can point at pictures of
its own; anything not supplied is simply not drawn. A game with more than one sort of ship
keys those by class, using the template key its own hulls were built from - relayed and
never interpreted, because a taxonomy of ships belongs to the game rather than here. See
`docs/client.md`.

**Orders take time, and how much depends on who is aboard.** A change of canvas is work:
hands aloft, laying out along yards, and only so many of them. A crack frigate's crew
shorten to fighting sail in a bit over two minutes; a pressed crew take better than six,
and a frightened crew longer again. Until it is done she carries what she carried — so a
captain who leaves it until he can see the squall is still under a full press when it
arrives, which is a decision rather than a die roll. It is also what makes a green crew
*feel* green on an ordinary passage instead of merely scoring lower in a fight.

**Fighting sail is a trade, not an upgrade.** Shortening down for action costs speed, and
buys less rigging for chain to cut and more hands at the guns — all of it derived from canvas
area rather than granted to the plan. She still has masts to lose, and her hull is no thicker
for it.

**A ship steals the wind of anyone in her lee.** A cone reaches downwind of every hull,
its length scaled by the canvas she has aloft, and anyone inside it loses drive in
proportion to how deep in it they are. It is the first thing here that makes position
relative to *other ships* matter rather than only position relative to the wind — which is
what the weather gage was actually worth — and it is the fourth side of the fighting-sail
trade, because shortening down shortens your shadow too. Luffing a few degrees to get out
of somebody's lee is a manoeuvre, not a wait. The mate names the ship doing it — a silent
loss of a third of her speed would just send her captain hunting for damage that is not
there.

**Holding your fire is a decision, not a delay.** Run the guns out and leave them, and the
battery speaks the moment something bears. Hold on a named ship and she must be identified
first — safe, and useless in fog. Hold on an arc and the guns take whatever crosses it, in
any weather, including your own consort. The contrib never needs to know what a friend is:
the second order is dangerous by construction, and the captain who gave it knew that.

**Raking falls out of the geometry.** A shot that strikes end-on runs the length of a ship,
and the angle on her bow *is* the point of impact — so crossing an enemy's stern is worth
three times an ordinary broadside without a table anywhere. A hex game needs impact modifiers
for this; here it is a consequence of where you got your ship.

**Ammunition is intent.** Ball for the hull is "I intend to sink you"; chain for the
rigging is "I intend to catch you"; grape for the people is "I intend to board you". None is
strictly better, and range decides what you may even attempt — ball carries, chain tumbles,
grape is a knife-range weapon. Closing to grape range means taking his ball the whole way in.

**Rating is not quality, and a company is made of divisions.** Seamen work her, oarsmen
pull, marines fight and are close to useless at anything else. A crack marine and a crack
seaman are both crack, and only one of them can hand a topsail. Carrying marines is a real
decision with no money in it — people are deadweight, so a fighting complement is freight
she did not carry, and hands that cannot reef.

**Five damage tracks, not one pool.** Hull, rigging, oars, weapons and crew break
separately, because a ship that is fast and toothless, one that is intact and cannot steer,
and one that is whole and unwilling are three different ships. Each feeds the simulation that
already exists — cut rigging means less canvas draws and the polar curve does the rest; crew
losses route through the company, so morale and mutiny answer for free. How lethal all of it
is, is one constant.

**A mark carries a meaning, and the meaning decides which way round.** A buoy with a name
and a position tells a navigator nothing. Cardinals say which side the safe water is on,
laterals mark the edges of a channel and reverse when you are outbound, an isolated danger
mark sits on the thing itself. The helmsman gives what they warn of a berth — sea-room, in
the sense the phrase *give it a wide berth* already meant — and goes the way the mark names
even when the cheaper-looking way round is the one with the rock in it. He recommends; he
never seizes the helm, because standing into danger has to stay a decision a player can make.

**Morale is a standing condition, and it falls faster than it rises.** A crew is not
asked "do you break?" at moments of crisis and found steady or wanting - they hold a state
ground down by what happens and recovered slowly. The asymmetry is why a captain who spends
his people cannot stop and have them back. Two collapses come out of it, told apart by whose
fault it is: *striking* is what a crew does when the enemy has beaten them, *mutiny* is what
they do when the captain has. Both need two gates, and an injected roll can add variance but
cannot open a gate that is shut.

**A pass is bounded by a clock, not a count.** What one vessel costs depends entirely on the
world she is in — measured, a five-fold spread — so a fixed batch of twenty-five is
somewhere between 6.5 ms and 33 ms of held reactor and nothing about the number tells you
which. Twisted runs everything in one thread, so that is time in which nobody's command is
processed. The budget is checked after an update rather than before, because checking first
would let one slow vessel starve herself out of the rotation forever.

**One scheduler, bounded and fair.** Not a ticker per vessel: Evennia's `TickerHandler`
keys subscriptions on callback and interval but not arguments, so a fleet subscribing one
method silently overwrites itself and most ships stop moving. A single service processes
what fits in its budget and resumes where it stopped, so a large fleet lengthens the
revisit interval rather than blocking the reactor.

## Installation

Requires Evennia 6.1 or later. There is nothing to `pip install` — the package lives at
`evennia/contrib/full_systems/maritime` like any other contrib.

**1. Point your game at the example world.** In `mygame/server/conf/settings.py`:

```python
MARITIME_MAP_PROVIDER = "evennia.contrib.full_systems.maritime.example.ExampleSeabed"
MARITIME_CURRENT_PROVIDER = "evennia.contrib.full_systems.maritime.example.ExampleCurrents"
MARITIME_WIND_BEARING = 165.0
MARITIME_WIND_SPEED = 6.0
```

Every one of those is optional. With none of them you get a flat, still, windless sea,
which is a legitimate world and a dull one. Replace them with your own classes when you
have a coastline of your own — see [Settings](#settings).

**2. Add the builder command.** In `mygame/commands/default_cmdsets.py`:

```python
from evennia.contrib.full_systems.maritime.example import CmdMaritimeExample

class CharacterCmdSet(default_cmds.CharacterCmdSet):
    def at_cmdset_creation(self):
        super().at_cmdset_creation()
        self.add(CmdMaritimeExample())
```

**3. Start the driver.** Once per game, or nothing moves:

```python
from evennia.utils import create
from evennia.contrib.full_systems.maritime.scripts import MaritimeDriver

create.create_script(MaritimeDriver)
```

**4. Reload, and run `example`** as a builder. It creates a mainland with a pond, a river
and a harbour town, six islands strung eastward, and three craft. It is safe to run twice.

Then walk to the Pond Shore, board the kayak, and start paddling.

### The graphical interface, which is optional

Everything above works in a plain telnet client and always will. A browser can be given a
chart, instruments and an order board as well, and nothing here is required to play.

The assets live in `web/static/maritime/`. Evennia collects a contrib's static files for
you; what a game supplies is the markup that loads them, in its own
`web/templates/webclient/webclient.html`. Django resolves that file ahead of the one shipped
with the webclient, so nothing inside an installed Evennia is edited:

```html
{# Where the interface mounts. Without it, it makes its own container at the top #}
{# of the page, which works and looks like an afterthought. #}
<div id="maritime-root"></div>

<link rel="stylesheet" href="{% static 'maritime/maritime.css' %}">
<link rel="stylesheet" href="{% static 'maritime/maritime-layout.css' %}">

<script src="{% static 'maritime/maritime-state.js' %}"></script>
<script src="{% static 'maritime/maritime-transport.js' %}"></script>
<script src="{% static 'maritime/maritime-chart.js' %}"></script>
<script src="{% static 'maritime/maritime-panels.js' %}"></script>
<script src="{% static 'maritime/maritime-ui.js' %}"></script>
```

**`maritime-layout.css` is separable on purpose.** It turns the webclient into a full-window
bridge while somebody is aboard a vessel, and every rule in it is scoped to
`:root:has(#maritime-root.maritime-on)` — so a game that leaves it out keeps the webclient
it has always had, and a game that includes it hands the screen back the moment a player
steps ashore. There is no state in which your own layout has been edited and has to be put
back. Take `maritime.css` and leave this one out if you would rather place the panels
yourself.

Nothing above is needed for a terminal player, and a session that never asks for the
interface is never sent it.

### A sea that moves

Depth is the water surface less the terrain beneath it, so moving the surface changes every
depth in the world without touching any ground. That is what makes tide a system rather than
decoration — and it is why a harbour bar is a gate rather than a wall, and why a ship on the
putty comes off on the flood.

```python
# In settings.py
MARITIME_TIDE_PROVIDER = "world.tides.HarbourTide"
```

```python
# In world/tides.py
from evennia.contrib.full_systems.maritime.tides import HarmonicTide

class HarbourTide(HarmonicTide):
    def __init__(self):
        built = HarmonicTide.semidiurnal(spring_range_m=4.0, neap_range_m=1.5)
        super().__init__(built.constituents)
```

Configure it the way a tide table states one, in ranges, because that is what a designer
knows about their harbour. Nobody knows their harbour's M2 amplitude.

**The fortnightly cycle is not something you set.** Springs and neaps are the lunar and solar
tides beating against each other — in step the ranges add, out of step they subtract — so the
cycle emerges from two periods that differ by twenty-five minutes. Measured on the example
coast, the daily range swings between 1.65 m and 4.31 m, with the biggest and smallest seven
days apart; half the beat period is 7.38 days. Nothing checks a calendar.

A tide table comes with it, and it is searched rather than stored:

```python
for when, height, state in tide.table(now, entries=4):
    print(f"{state} water {(when - now) / 3600:.1f} h from now, {height:+.2f} m")
```

Because those predictions hunt the same function the water is drawn from, a table cannot
disagree with the sea. `HarmonicTide.mixed` adds the diurnal inequality if a game wants the
two daily high waters to differ, and a `progression` makes the tidal wave travel, so high
water reaches one end of a long coast before the other.

#### Inland water, which keeps its own level

A pond is not a bay. It stands where its valley holds it, twenty metres above the sea if
that is where the valley is, and it does not rise and fall with the tide. `WorldPosition`
has always carried a `region`; `RegionalWater` is what uses it:

```python
from evennia.contrib.full_systems.maritime.bathymetry import FlatTideProvider
from evennia.contrib.full_systems.maritime.tides import HarmonicTide, RegionalWater

class AllTheWater(RegionalWater):
    def __init__(self):
        super().__init__(
            sea=HarmonicTide.semidiurnal(4.0, 1.5),
            waters={"the pond": FlatTideProvider(surface_z=23.0)},
        )
```

Ask about a position in region `"the pond"` and the water stands at 23 m; ask about the very
same spot as sea and it is a hillside. Region is a property of the question, not of the
ground, which is exactly what lets a pond sit above a sea that is directly beneath it.

Each inland water is a full provider rather than a number, so a lake can have a seiche, a
reservoir can be drawn down over a season, and a tidal lagoon behind a sill can have a tide
of its own that is smaller than the sea's. None of it changes the depth arithmetic: depth is
still the surface less the ground, so a pond five metres deep comes out five metres deep by
the same subtraction that gives a harbour its nine.

Unset the setting and nothing moves, exactly as before.

### Meridians and parallels, which show the world is round

The chart is ruled with a graticule: round degrees of latitude and longitude, labelled in
the margin the way a printed chart labels them. A navigator reads his position off them,
which is reason enough — but they earn their place twice, because they are the only honest
way a flat sheet can show a curved world. The meridians converge, and the further out the
view, the more visibly they do it.

They are not drawn as an approximation. A parallel is the line where latitude equals a round
number, so the same contour tracer that draws the coastline draws the graticule, over a grid
of degrees instead of a grid of depths. The lines curve because the projection curves them.

A world that does not know where it is gets none. `geographic_at` returns None by default,
and a seabed defined by an arithmetic ramp draws no graticule rather than inventing a
latitude:

```python
class MyWorld(MaritimeMapProvider):
    def geographic_at(self, position):
        return (self.latitude_of(position), self.longitude_of(position))
```

### Shaded relief, which is optional twice over

**Maritime itself has no dependencies and never will.** The simulation, the commands, the
charts and the browser interface all work with nothing installed beyond Evennia, and that
is a promise rather than a current state of affairs.

A game that would rather have a better-looking chart than a shorter install can have one:

```bash
pip install numpy scipy pillow
```

With those present the chart draws **shaded relief** beneath its contours — the shape of
the bottom, lit, so a bank reads as a bank at a glance instead of as a ring a pilot has to
interpret. Without them the chart is the line drawing it has always been. Nothing is
configured, nothing degrades, and no code path differs beyond one `available()` check: the
payload simply carries no picture and the browser draws what it was sent.

Three things worth knowing before you take the trade:

- **It is shaded from the charted seabed, never the real one.** A poor chart's relief is
  as wrong as its soundings, and in the same places. Anything else would hand a graphical
  player knowledge the fiction denies a terminal one, which is the rule the whole interface
  is built on.
- **It is nearly free.** The soundings were already taken to draw the contours; shading
  them costs about 65 ms against the 983 the sounding took, and adds some 20 KB to a
  payload that goes out once a minute.
- **It stops where the survey stopped.** Unsurveyed water is transparent, not blue, so the
  paper still visibly runs out at the edge of what somebody covered.

### Putting the commands on your own ships

The example does this for you. For a ship you build yourself, the helm command set goes on
her compartments — by dotted path, so it survives a reload:

```python
room.cmdset.add("evennia.contrib.full_systems.maritime.cmdsets.HelmCmdSet", persistent=True)
```

On the compartments rather than on the character, so that a helm order needs a deck under
you and cannot be given from a tavern.

### Switching the interface at runtime

Four commands decide which interface the game shows, and how much of the world it shows.
They go on your character cmdset, because a switch reachable only from a deck you cannot
see is a switch with no way back:

```python
from evennia.contrib.full_systems.maritime.commands.interface import (
    MaritimeInterfaceCmdSet,
)


class CharacterCmdSet(default_cmds.CharacterCmdSet):
    def at_cmdset_creation(self):
        super().at_cmdset_creation()
        self.add(MaritimeInterfaceCmdSet)
```

| Command | Effect |
| --- | --- |
| `maritime ui on\|off\|hybrid` | When the panel is shown, for the whole server |
| `maritime uncharted on\|off` | Draw the sea as it truly is, for building and testing |
| `maritime player gui on\|off` | Whether players may choose the interface for themselves |
| `maritime gui ...` | What one player chose, when the game allows it |

All four are locked to `perm(Admin)` — admins, developers and the superuser — so installing
the set puts nothing in front of your players. `maritime gui` opens to everybody only while
`maritime player gui` is on, and is hidden rather than refused before then.

`maritime ui` overrides `MARITIME_ASHORE_PANEL` at runtime and survives a reload, which is
the whole reason it is a command rather than a second setting. `maritime uncharted` is for
building: with it on, every chart reads the world itself — nothing off the paper, no survey
error, and a chart even for a ship carrying none. **A game left in that state has no
navigation in it**, so turn it off before anybody plays.

See `docs/switches.md`.

### The builder's command

`@ship` is the one maritime command that must work with *no* deck under you — a world is
built from dry land, usually from a batch file — so it lives in its own set, which goes on
your character cmdset rather than on a room:

```python
from evennia.contrib.full_systems.maritime import ShipwrightCmdSet


class CharacterCmdSet(default_cmds.CharacterCmdSet):
    def at_cmdset_creation(self):
        super().at_cmdset_creation()
        self.add(ShipwrightCmdSet)
```

The command locks itself to Builders; the cmdset does not, so a game wanting it somewhere
narrower can say so without editing the contrib.

### The shipyard, and keeping the harbour clear

Seven hulls a player can build from at a quay, and an answer to the question every
persistent maritime game eventually asks - why is the harbour full of ships nobody has
sailed since March?

```python
from evennia.contrib.full_systems.maritime.commands.shipyard import (
    MaritimeShipyardCmdSet,
)


class CharacterCmdSet(default_cmds.CharacterCmdSet):
    def at_cmdset_creation(self):
        super().at_cmdset_creation()
        self.add(MaritimeShipyardCmdSet)
```

| Command | Effect |
| --- | --- |
| `maritime build` | The book of hulls: size, tonnage, hold and berths |
| `maritime build <rig> <name>` | Build one alongside, gangway down. Staff, or anybody once opened |
| `maritime summon <name>` | Bring a laid-up ship of yours round to this dock |
| `maritime lay up <name>` | Put one of yours into ordinary and free her berth |
| `maritime player build on\|off` | Whether players may build at all (Admin+) |

The hulls are yawl, lugger, cutter, schooner, brig, barque and frigate, and every figure
they carry is derived rather than chosen - tonnage by Builder's Old Measurement,
displacement by block coefficient, holds from the tonnage. Two of them are checked against
vessels that existed: the frigate lands within one per cent of a *Leda* class fifth rate and
the brig five per cent over a *Cruizer* class brig-sloop, in the direction the rule is known
to err.

**A ship laid up is *in ordinary*, not deleted.** She keeps her cargo, her crew, her damage
and her compartments, and gives up her berth and her place on the water - so the simulation
stops ticking her, a lookout stops raising her, and nothing can run into her. That is not a
new mode: a vessel with no position has never been simulated, and this is that state with a
name on it.

Evennia fires no hook this contrib can see when somebody logs out, so laying a fleet up on
logout is offered rather than installed - four lines in your own `at_post_unpuppet`. See
`docs/shipyard.md`.

### Ordering a passage, and surviving a grounding

`make for <harbour>` is `plot`, `follow` and `dock` in one order - which is how a decision
of that size is actually made, and what a chart with harbours drawn on it invites somebody
to click. Clicking a harbour sends exactly that command as typed text, so nothing the
browser can do is unavailable to a terminal player.

Whether she can get there is two questions: is there a course over the marks somebody laid,
and is there water on the two legs no mark covers - the run in from the last mark to the
quay, and the run out from wherever she is floating to the first mark. A pond with a quay in
it is water, and no course can be laid to it, because reachability is a thing a world states
rather than a thing an algorithm finds.

Grounding has guardrails. The leadsman casts ahead of the ship rather than under her middle;
the sailing master sounds ninety seconds ahead and falls off rather than carrying her onto
ground he can see; a tide lifts a hull that is merely held; and `kedge` hauls her off by her
own cable when it does not. Only foul ground struck at eight knots or more opens a hull.

See `docs/passage.md`.

## Settings

All optional. Every one is prefixed `MARITIME_`.

| Setting | Default | Meaning |
| --- | --- | --- |
| `MARITIME_TIME_PROVIDER` | the game's own clock | Dotted path to a time provider |
| `MARITIME_RNG_SEED` | unset | Pin the master seed to make a run reproducible |
| `MARITIME_POSITION_STYLE` | `nautical` | `nautical` or `raw` |
| `MARITIME_ORIGIN_NORTHING` | `0.0` | Places the world's origin on the globe |
| `MARITIME_ORIGIN_EASTING` | `0.0` | As above, for longitude |
| `MARITIME_WIND_BEARING` | `0.0` | Bearing the wind blows *from* |
| `MARITIME_WIND_SPEED` | `0.0` | Wind speed in metres per second |
| `MARITIME_CURRENT_SET` | `0.0` | Bearing the water flows *towards* |
| `MARITIME_CURRENT_DRIFT` | `0.0` | How fast it flows, in metres per second |
| `MARITIME_CURRENT_PROVIDER` | slack water | Dotted path, for a tidal stream |
| `MARITIME_NAVIGATION_NETWORK` | no marks | Dotted path to the game's marks and channels |
| `MARITIME_WEATHER_PROVIDER` | from the settings below | Dotted path to the game's weather |
| `MARITIME_SEA_STATE` | follows the wind | Override the sea the wind would raise |
| `MARITIME_MAP_PROVIDER` | flat sea | Dotted path to the game's bathymetry - a `TiledMapProvider` subclass for an authored seabed |
| `MARITIME_TIDE_PROVIDER` | a motionless sea | Dotted path to the game's tide - `HarmonicTide` for a real one |
| `MARITIME_SOUNDING_CACHE` | `300000` | How many soundings of the seabed to remember, about 50 MB |
| `MARITIME_WORLD_BUNDLE` | unset | Directory of baked soundings for `BakedMapProvider` |
| `MARITIME_ASHORE_PANEL` | `False` | Keep the panel up on land, showing a room map instead of a chart |
| `MARITIME_BAKE_DIR` | unset | Where to write and read soundings baked at startup |
| `MARITIME_BAKE_AREA` | unset | `(west, south, east, north)` in metres, to bake at startup |
| `MARITIME_BAKE_SCALES` | unset | Which zoom reaches to pre-sound |
| `MARITIME_COMMAND_POLICY` | captain, else owner, else anybody aboard an unowned ship | Dotted path to `(character, vessel) -> bool` |
| `MARITIME_NARRATOR` | the one here | Dotted path to a `VesselNarrator` subclass |
| `MARITIME_WATER_NARRATOR` | the one here | Dotted path to a `WaterNarrator` subclass |
| `MARITIME_COMMODITIES` | a standard stowage table | The cargoes this game trades in |
| `MARITIME_TICK_BUDGET_MS` | `10.0` | How long one simulation pass may hold the reactor; 0 disables the limit |
| `MARITIME_CELL_SIZE` | `100.0` | How wide a projected square of open water is, in metres |
| `MARITIME_OCEAN_ROOM_TYPECLASS` | `OceanRoom` | Dotted path to the class pool rooms are built from |
| `MARITIME_VISIBILITY` | 30 miles | How far the air lets you see, in metres |
| `MARITIME_DISTANCE_UNITS` | `leagues` | `leagues`, `nautical`, `metric` or `raw` |
| `MARITIME_DEPTH_UNITS` | `fathoms` | `fathoms`, `metres` or `raw` |
| `MARITIME_DEFAULT_DEPTH` | `200.0` | Depth of the default flat sea, in metres |

## Usage

Commands are on the ship's rooms, so they work with a deck under you and nowhere else — with
two deliberate exceptions. The shopkeeping verbs ashore (`browse`, `buy`, `market`, `sell`)
live on the shore rooms, and the runtime switches are on the account.

| Command | Effect |
| --- | --- |
| `helm <bearing>` | Steer a course. Spoken and answered as at sea |
| `sail <plan>` | `furled`, `storm`, `reefed`, `battle`, `working`, `full` |
| `wind` | Where the wind is from and how she lies to it |
| `current` | Set and drift, and the course she is making good |
| `weather` | Wind by its force, the sea, and how far you can see |
| `fix` | Fix her position off a landmark, and learn the set |
| `chart` | What the paper says is under her, and how far to trust it |
| `plot <mark>` | Lay a course by way of safe water |
| `ports` | What harbours she could be told to make for, and why not |
| `make for <harbour>` | The whole passage: course, sailing master, and alongside at the end |
| `kedge` | Run an anchor out astern and haul her off the ground |
| `follow` / `belay` | Hand the sailing master the con, and take it back |
| `speed <knots>` | Order a speed, for vessels not under sail |
| `allstop` | Take the way off her |
| `drop anchor` / `weigh anchor` | Bring up, and get under way again |
| `dock` / `cast off` | Come alongside a berth, and let go |
| `position` | Latitude, longitude, course and speed |
| `sound` | Water under the keel, and a shoal warning |
| `lookout` | What is in sight from where you are standing |
| `scan` | The whole horizon, quarter by quarter |
| `target <name>` | Range, aspect, closure and which arcs bear |
| `guns` / `load [shot]` / `fire <name>` | The battery, serving it with ball, chain or grape, and firing what bears |
| `hold fire <name>` | Lay a gun and wait; it speaks the moment she bears |
| `oars` | What her looms are doing, and how many hands are on them |
| `give way` / `stretch out` / `easy` / `hold water` | Rowing: a working stroke, everything they have, gently, and stop her |
| `paddle` | For craft that are paddled rather than rowed |
| `grapple <name>` / `grapples` / `cut grapples` | Throw lines to hold her alongside, see what is holding, and let go |
| `strike` | Haul your colours down |
| `stow` / `discharge` / `manifest` | Load cargo, put it ashore, and read what she is carrying |
| `look <direction>` | One quarter or compass point - `look se`, `look port` |
| `watch <direction>` | A standing watch; told as things come and go |
| `look` | A weather deck also describes the sea outside it |
| `crew` | Her company, how they are bearing it, and what they hold against you |
| `lookout` | What is in sight — shipping, and the marks, reported apart |
| `@maritime` | Raw coordinates and motion state (Builder+) |
| `@ship` | Build ships, and set owner and captain (Builder+) |
| `maritime ui` / `maritime uncharted` / `maritime player gui` | Runtime switches (Admin+) |
| `maritime gui` | Your own interface, if the game allows it |
| `maritime build` / `maritime player build` | The shipyard, at a quay (Admin+ unless opened) |
| `maritime summon` / `maritime lay up` | Call a ship of yours back, or put her in ordinary |

## Examples

Sailing is a negotiation, not an order. A vessel makes what the wind on her heading
allows:

```python
from evennia.contrib.full_systems.maritime import WorldPosition
from evennia.contrib.full_systems.maritime.sailing import (
    WindVector, PolarCurve, WORKING, achievable_speed,
)
from evennia.contrib.full_systems.maritime.motion import MotionLimits

hull = MotionLimits(max_speed=10.0, acceleration=1.0, turn_rate=6.0)
wind = WindVector(bearing=0.0, speed=10.0)      # a northerly

achievable_speed(90.0, wind, WORKING, PolarCurve(), hull)   # beam reach - fast
achievable_speed(45.0, wind, WORKING, PolarCurve(), hull)   # close-hauled - slower
achievable_speed(0.0, wind, WORKING, PolarCurve(), hull)    # head to wind - nothing
```

Ship classes are data. There is no `Sloop` class anywhere in this contrib:

```python
from evennia.contrib.full_systems.maritime import (
    VesselTemplate, VesselCapacity, DeckPlan, DeckLevel, OPEN, INTERIOR,
)

SLOOP = VesselTemplate(
    key="test_sloop", name="Test Sloop",
    length=18.0, beam=5.4, draft=2.2,
    capacity=VesselCapacity(displacement=32000.0, berths=4),
    deck_plan=DeckPlan(decks=(
        DeckLevel(level=0, name="Main Deck", slots=2, exposure=OPEN),
        DeckLevel(level=-1, name="Cargo Hold", slots=1, exposure=INTERIOR),
    )),
    crew_minimum=1, crew_ideal=4,
)
```

Nothing here builds hulls from a template - that is the game's own business, and the
template is data it owns. When it does, it should record which class the hull came from:

```python
ship.db.template_key = SLOOP.key
```

Nothing in this contrib writes that field and only the optional client reads it, to say
what sort of ship an interface is looking at. It is worth setting anyway. It is the one
place a hull remembers what she was built as, and neither of the alternatives works: a rig
here is a polar curve rather than a name, and two ships of a length can be quite different
vessels.

Every word the system speaks is replaceable, and replacing the words does not mean
reimplementing when to say them:

```python
from evennia.contrib.full_systems.maritime.messaging import VesselNarrator, COMING_ROUND


class Terse(VesselNarrator):
    def phrase_for(self, event, **detail):
        if event == COMING_ROUND:
            return f"Coming round to {detail['side']}.", None
        return super().phrase_for(event, **detail)


# settings.py
MARITIME_NARRATOR = "world.ships.Terse"
```

What a lookout can tell is bounded by the range, not by what the engine knows:

```python
from evennia.contrib.full_systems.maritime import (
    horizon_distance, geographic_range, detection_limit, detection_level,
)

horizon_distance(2.0)                    # a deck:      2.9 nautical miles
horizon_distance(30.0)                   # a masthead: 11.3 nautical miles
geographic_range(2.0, 30.0)              # her mast is over your horizon: 14.3

limit = detection_limit(2.0, 30.0)       # ...unless the air runs out first
detection_level(0.9 * limit, limit)      # 'contact'    - something on the water
detection_level(0.1 * limit, limit)      # 'identified' - you know the ship
```

Being lost is the water, not a dice roll:

```python
from evennia.contrib.full_systems.maritime import reckon, take_fix, error_of, WorldPosition

dr = take_fix(WorldPosition(0.0, 0.0), now=0.0)
dr = reckon(dr, heading=90.0, speed=5.0, elapsed=600.0)   # course steered, distance logged

dr.position            # (3000, 0) - where she reckons she is
dr.uncertainty         # what the navigator would admit to
error_of(dr, true)     # what she is actually out by: the current, exactly
```

A berth is a place with dimensions, and that is what makes it a decision:

```python
from evennia.contrib.full_systems.maritime import Berth, WorldPosition, can_dock

berth = Berth(
    key="fishmarket steps", position=WorldPosition(3800.0, -800.0), heading=90.0,
    max_length=24.0, max_beam=8.0, max_draft=4.0,
)

can_dock(WorldPosition(3790.0, -800.0), 0.2, 270.0, 18.0, 5.4, 2.2, berth)   # alongside
can_dock(WorldPosition(3790.0, -800.0), 4.0, 270.0, 18.0, 5.4, 2.2, berth)   # 'too_fast'
can_dock(WorldPosition(3790.0, -800.0), 0.2, 270.0, 18.0, 5.4, 5.0, berth)   # 'too_deep'
```

You do not steer where you are going — you steer to counteract what the water is doing:

```python
from evennia.contrib.full_systems.maritime import (
    CurrentVector, made_good, course_to_steer,
)

stream = CurrentVector(set=0.0, drift=2.0)     # two metres a second, setting north

made_good(90.0, 5.0, stream)                   # heading east: a track north of east,
                                               # and faster than she is sailing
course_to_steer(90.0, 5.0, stream)             # what to steer to actually make east good
course_to_steer(90.0, 1.0, stream)             # None - she cannot outrun the stream
```

Soundings are called, not printed:

```python
from evennia.contrib.full_systems.maritime import leadsman_call, METRES_PER_FATHOM

leadsman_call(7.00 * METRES_PER_FATHOM)   # 'By the mark seven!'   - the line is marked here
leadsman_call(6.00 * METRES_PER_FATHOM)   # 'By the deep six!'     - and not here
leadsman_call(7.75 * METRES_PER_FATHOM)   # 'A quarter less eight!'
leadsman_call(2.00 * METRES_PER_FATHOM)   # 'By the mark twain!'
```

## The handbook

A manual for players and for developers, in
[`web/static/maritime/help/`](web/static/maritime/help/index.md).

**One set of files, three doors.** They are ordinary markdown, so they are readable in this
repository with the links working between them; they are served as static content, so
`/static/maritime/help.html` renders them with a contents down the side; and the panel has a
`?` in its top right corner that opens that page. A player in a plain telnet client types
`maritime help` and is given the address.

Two copies of a manual is one copy and one lie — the second is always the stale one and
nothing tells you which — so there is one set of words and the renderer is forty lines.

It is in two halves. The first is for anybody aboard a ship: the helm, sailing, oars,
navigation, soundings, harbours, the lookout, the guns, ramming, boarding, her people, cargo,
ashore, and the interface. The second is for anybody building with it — the layers and which
ones you actually need, the four integration steps, **four worked recipes for taking only
part of it**, your own coast, your own ships, rooms and typeclasses, the seams your game's own
decisions go in, and a full reference of every command and every setting grouped by what you
are trying to do.

A test holds the handbook to the game: every link between pages resolves, every page can get
back to the contents, the contents lists every page, the command's own topic list and the
files on disk are the same set, and **every command the handbook tells somebody to type is a
command that exists**.

## Testing

```bash
evennia test --settings settings.py evennia.contrib.full_systems.maritime
```

**3417 tests**, of which forty-six are **scenarios** rather than unit tests — named voyages
in `tests/test_scenarios.py` that set sail, stand on, and check where she ends up. They are
the slowest part of the suite and worth it twice over: writing them found a sailing master
who handed back the con at his last mark and then sailed twelve kilometres past it, and they
later caught a gale leg beating a breeze leg by exactly eighteen metres — half of one sloop
plus half of another, because the second leg was now running into the first one lying
stopped at the end of her run. Every unit test in the repository passed over both.

`ManualTimeProvider` advances game time on demand, so a voyage that would take half an hour
of wall time runs in milliseconds.

## Limitations

- An anchored ship can be sprung round on her cable to lay her broadside where she wants
  it, and shoots better for lying still. Cutting the cable frees her at once and costs her
  the anchor until a spare is rigged, which is hours.
- **Everything worth doing is clickable, and every click sends a command a player could
  have typed** — an exit, a shopkeeper, a ware on her counter, the Yes and No of a
  purchase. Nothing the graphical client can do is unavailable to a telnet player.
- **A ship's purse pays for what her people buy ashore**, and nothing is ever written to a
  character. What a person carries is the host game's business.
- Careenage is laid out **coordinates first**: every room has a position, and every street
  exit is derived from the difference between two of them rather than typed. There is
  nowhere left to write a direction the geometry will not support.
- **Fire is a situation rather than a debuff.** It escalates on its own clock while you
  ignore it — and resets that clock each time it spreads, so a ship left burning faces
  several fires rather than one that got worse. Fighting it costs hands with diminishing
  returns, and **the pumps will not draw unless she stops**, because the hoses go over the
  side. A burning ship chooses between running and surviving, which is a dilemma no
  hit-point model can produce.
- **Flooding is the mirror of fire, deliberately.** Fire wants her stopped so the hoses
  will draw; water wants her stopped because way through the sea forces more of it in. So
  a ship both alight and filling has one crew, two jobs, and a single decision about her
  speed that cannot satisfy both. Sinking is a process you fight — pumps, and a sail
  fothered under the hull — rather than a threshold you cross.
- **The butcher's bill sorts casualties into four futures** — dead, wounded who are days
  from their duty, dazed who are up within the hour, and men who were not hurt at all and
  broke. How it splits is a fact about the crew rather than about the fight: same shot,
  same number, different ship.
- The men who broke are a decision. Start them back to their duty and you have the hands
  now and a grievance later; say nothing and you are short of them for a day. The grievance
  goes through the same door as every other thing a crew holds against its captain, so a
  battle can end in a mutiny without a line of new wiring.
- We never decide that a player is hurt. The event carries the *fraction* — she took thirty-
  eight per cent — and a game rolls its own people against it.
- What becomes of the people when she founders is not built. The event says how many were
  aboard; the ruling that they take to the boats is in `DECISIONS.md` and the boats are
  their own item.
- A ship has no price either, and ownership carries no money. `transfer_ownership` moves
  the property and publishes why — sold, granted, captured, inherited — and a game wires its
  own purchase to that event. What a ship is worth is the host game's economy.
- Capture wants four conditions and takes none of them on trust: held alongside, struck
  to *that* hull, her deck carried in the exchange just fought, and her captain beaten.
  Ownership moves to the captor's owner. Command is **vacated rather than handed across** —
  a prize waits for a prize master, because one ship per captain is a rule this contrib
  keeps and handing him the prize would make him abandon the ship he won her with.
- Whether a *player* captain is beaten is not ours to say. `MARITIME_SUBDUED_POLICY` is
  the seam; the default settles NPC captains at ship scale so NPC ships can be taken, and
  answers no for anybody with an account. A capture that does not happen is a fight that
  continues, and that is the safe direction to be wrong in.
- A ship with way still ordered on will grind into the ship she has rammed again on the next
  tick, and again after that. That is arguably what she would do, and it is not a decision
  anybody made. Nothing yet tells the helm that the way ahead is now occupied.
- Boarding melee is not built, so a fight that ends alongside ends there.
- Cargo has no price. Contracts, freight rates, who is buying and what a voyage is worth
  are the game's own economy, and shipping an opinion about them would collide with
  whatever it already has. Recorded in `DECISIONS.md`.
- Crews tire, people do not. Exhaustion is a number on the hull, never on a character -
  what a stroke costs a *person* collides with whatever stamina the host game already has,
  and at ship scale there is nothing to collide with. A game with no notion of tiredness
  loses nothing: she pulls slower and her people are closer to breaking. Recorded in
  `DECISIONS.md`.
- Morale has no effect on gunnery or sail handling yet. `hesitation` says how much of what
  her people could do is not being done, and nothing consumes it until damage arrives.
- Being tender is reported and costs her nothing. What top-heavy loading should actually
  do to a ship reaches into sailing and damage at once, and both of those decisions are
  the game's.
- Nothing yet puts a player in the water. The projection can hold them, drift them and
  describe the sea to them, but going over the side is something damage and boarding do,
  and neither is built.
- Being in the water costs nothing. There is no exhaustion, no cold and no drowning,
  because those are statements about how harsh a game is and would collide with the
  health and stamina the host game already has. Recorded in `DECISIONS.md`.
- The water column is not built. `Buoyancy` carries a sink rate so that a wreck has
  somewhere to go, but nothing yet decides when something stops floating, and nothing
  can be dived on.
- A port is a quay with berths. Anchorages, pilots, tugs, cargo handling and repair
  facilities are all later phases.
- The default weather is one wind, one visibility and one sea everywhere. A game supplies
  a provider for anything better; call sites do not change.
- Sea state slows a vessel and is described from the deck. Its effect on stability, gunnery,
  swimming and small craft arrives with the phases that own those.
- One global current, like the wind. A provider replaces it with a tidal stream later;
  call sites will not change.
- Ranges and bearings in a sighting are true, not estimated. The vessel's *position* is now
  reckoned rather than known, but a lookout's range to a contact is still exact.
- Every vessel scans every tick, against a linear index. Fine for a harbour, and the reason
  the index interface exists separately from what is behind it. Measured at roughly a
  millisecond a vessel with fifty sail in company - see `docs/performance.md`.
- The performance figures were taken on a development machine. The ratios are what the
  design rests on; a game expecting a large fleet should re-run the benchmark on the box it
  will actually run on.
- A hull is sampled at seven points on her outline, not swept as a continuous shape, so
  *unauthored terrain* small enough to fit between those points can still pass between
  them. A hazard a game has actually drawn cannot: it has a radius and is tested against
  the whole corridor she swept. A vessel with no measured length or beam is tested at her
  centre alone.
- The world is a plane. Longitude does not narrow towards the poles, deliberately —
  a cosine correction would make the displayed position disagree with the distance
  actually sailed.
- Spatial indexes are a linear scan. The interface is settled; the structure behind it
  lands when there is real traffic to measure it against.
- Two lashed hulls do not move as one. Each is simulated separately and the lines part if
  their motion diverges far enough, which is the honest half; a coupled two-body model is
  not built.
- Nothing decides what happens to an offline passenger aboard a vessel that founders.
  Evennia's default is that they survive and are teleported home without being told, which
  is a policy nobody chose; `Vessel.ships_company()` exists so that any other policy is
  implementable, and the question is in `DECISIONS.md`. The engine behaviour behind it is
  written up in `docs/logout.md`.
- Narration is addressed to compartments, not to people. A ship can tell the deck one
  thing and the hold another, but cannot yet tell the captain and a deck hand standing
  side by side two different things. The ship's own cry uses her highest weather deck, so
  she calls a sighting the masthead can see even when nobody is up there.

## License

Released under the same BSD 3-Clause license as Evennia. See `LICENSE`.
