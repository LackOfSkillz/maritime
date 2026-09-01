# Ordering a passage, and not being wrecked on the way

    ports                          what she could be told to make for, and why not
    make for <harbour>             lay the course, hand it to the master, go alongside
    kedge                          haul her off the ground by her own cable

Plus a clickable harbour on the chart, which sends `make for <harbour>` as ordinary typed
text — so nothing the browser can do is unavailable to a telnet player.

## Can she get there?

Two questions, and it needs both to be yes.

**Is there a course over the marks?** That is `routes`' position and it is the load-bearing
one: a network is *authored*, so what a ship can reach is a thing a world states rather than
a thing an algorithm finds. A pond at the head of a valley is water; a lake behind a bar is
water; the flooded quarry is water. None of them is somewhere a ship can go, and no amount
of sounding the ground will say so.

**Is there water on the legs no mark covers?** Two of them, and both were missed first time:

- the run *in*, from the last mark to the quay
- the run *out*, from wherever she is floating to the first mark

The legs between marks are somebody's statement about where the water runs, checked when
they were laid. These two are nobody's statement about anything — she could be anywhere, and
a quay is at the end of a pier — so they are sounded.

It found a real one immediately. A vessel lying east of an island chain was given a course
whose first mark was west of it; the master steered the direct line at six metres a second
and put her on a spit two hundred metres away, on a course the game itself had planned.
Every leg of the network was clear. The leg onto it was not.

### The pond

The fairway mark off Careenage stands about a mile from the pond in the hills. By distance
alone that made it "the mark serving the pond", and the pond came out reachable with a course
laid across a hillside. Distance to a mark is not a channel — so the leg is sounded, and a
leg with a bank across it does not serve the harbour behind it whatever the tape measure
says.

That is not a pathfinder and must not become one. It is one straight line, the line the ship
will actually sail, checked against the water she actually draws.

### One question, asked one way

There is exactly one test for whether a ship can be somewhere, and it is the one the tick
uses to ground her: `check_swept_grounding`, which asks the seabed **and** the game's
authored hazards.

Sounding `terrain_z_at` alone is a different question with a different answer, and on the
coast this was built against the difference is total: the islands are hazards twelve metres
high standing over terrain that samples at −20 m. A leg straight through an island read as
sixty feet of clear water.

Three separate bugs came out of that one disagreement in an afternoon — a ship that floated
off a rock and grounded again every tick, a network whose marks were laid inside the islands
they served, and a sailing master who sounded ahead and saw nothing.

## Grounding, and the guardrails on it

Grounding should be a bad afternoon. It was a lost ship, every time, and there was no way
out of it at all.

### It can end

A rising tide lifts a hull that is merely held. `refloats_on_tide` had existed since
grounding was written — exported, documented, covered by tests — and **nothing in a running
game had ever called it**. A vessel was found sitting in 19.86 m of water, drawing 2 m,
reporting herself hard on the ground, with a sailing master who had the con and could not
move her. Her record read `touched, sand, −14.0 m, 0.93 m/s`: the softest grounding the
model has, and it was permanent.

She floats off only if the *same* test that grounded her now says she is clear. Using a bare
sounding under her middle instead made a ship on the edge of a rock float, ground, float and
ground for ever, announcing both.

### It can be undone by hand

`kedge` runs an anchor out astern on a warp and walks the capstan round — the thing that was
actually done. Each heave hauls her part of the way to the nearest water she would float in;
a soft bottom lets her slide and rock holds her, so the same labour moves her half as far. A
hull that has been *opened* cannot be kedged at all: she is not held by the ground, she is
sitting on it because the sea is inside her.

The anchor is laid in water she could lie in, not the first water that floats her, and on a
hawser's length rather than three times her own — both learned by watching her come off and
drift straight back on.

### It happens less

| Guardrail | |
| --- | --- |
| The leadsman casts **ahead** | He warned on the water under her middle, which is water she has already crossed. At six metres a second the call came about a second before she struck, and on an authored rock it never came at all. |
| The master sounds ahead | 90 seconds of running, 200 m floor. He will not carry her onto ground he can see. |
| ...and falls off rather than stalling | Up to 60° either side, nearest first. Declining to steer at ground is what any helmsman does; working a way *through* a bank is pilotage he is not given, and past a right angle he would be choosing a different voyage. So he stops and says so. |
| A passage can't be ordered over land | See above. |
| He weighs, and he anchors | Given the con and somewhere to go he brings the anchor home himself. When no heading is clear he lets go rather than merely stopping — a ship stopped in a tideway off a lee shore is still going somewhere, and one did: two fathoms, set down at eight tenths of a knot, on the beach twenty minutes later. |
| He carries two metres of spare water | He sounds ninety seconds ahead, and the tide moves about two metres in that direction over an afternoon. He grounded once by looking at one state of tide and arriving at another. |
| ...except on the last leg | A quay is shallow on purpose. The final approach has already been checked against the berth's own advertised depth, and going in slowly is what `approach_speed` is for. |

### And the marks hold still

`offing_from` walks seaward until there is twelve metres under it — and how deep the water
is depends on the tide, so siting the marks against "now" moved them between one build and
the next. Careenage Roads was laid at two points a quarter of a kilometre apart within an
hour.

A network is a set of claims about where the safe water runs. If the claims move, a course
plotted at high water leads somewhere else at low, and the legs `tests/test_approaches.py`
sounds are not the legs a ship sails. Marks are sited against **chart datum**, which is what
a real chart sounds against and for exactly this reason.

### It hurts less

`HOLING_SPEED` was 1.5 m/s — under three knots. Every grounding at any speed anybody
actually sails at was a holing, and a hull that touched a rock while ghosting along under a
reefed topsail was lost.

There are two thresholds now, because taking the ground gently, being hard on and waiting
for the tide, and being opened on a reef are three different afternoons:

| | |
| --- | --- |
| `TOUCHING_SPEED` = 2.0 m/s (~4 kn) | Below it she has *taken the ground* — a thing ships did on purpose every time they were careened or beached to load at low water. |
| `HOLING_SPEED` = 4.0 m/s (~8 kn) | Above it, **on foul ground only**, she is opened. Sand and mud never hole a hull at any speed. |

## Installing it

`ports`, `make for` and `kedge` are in `HelmCmdSet` with the rest of the helm, so a game
that has ships already has these. They want a deck under them, like every other order.

The clickable harbours need nothing installed: they ride on the chart payload a graphical
client already receives.
