# Decisions waiting on Gary

Questions that came up while building and are not mine to answer. Each says what is
blocked, what the options look like, and what I did in the meantime so that nothing
stalled.

Nothing here is a bug. These are places where guessing would have produced a plausible
answer that quietly became load-bearing.

---

## Tactical pacing

**Raised by:** phase 15, tactical geometry.
**Blocks:** nothing built yet. It blocks phase 15's *evaluation*, which the roadmap calls
"the tactical-pacing decision point".

The specification declines, deliberately, to lock close-quarters play to the host game's
world-time ratio, and lists it as an open question. At 4:1, a player may not have the
reaction time for close manoeuvring, collision avoidance, a boarding approach, or laying a
gun on a ship that is crossing.

The options, as far as I can see them:

1. **Tactical time stays world time.** Simplest and most consistent — one clock, Law 1
   untouched. A four-to-one game gets fights that happen four times faster than they read.
2. **Tactical time slows towards real time when vessels are close.** Reads well and is what
   most naval games do. It means two clocks, and something has to decide when to switch —
   which is a rule, and rules about time leak into everything.
3. **Configurable per game, with no position taken here.** What stands today.

**What I did:** nothing that presumes an answer. `tactical.py` holds geometry only — range,
bearing, aspect, closure, arcs — and takes no time argument at all, so it is incapable of
having an opinion about pacing. Whichever way this goes, none of that changes.

**What it needs from you:** a decision, and ideally after playing one close-quarters
situation once weapons land and it can actually be felt rather than reasoned about.

---

## What the sea does to a person in it

**Raised by:** phase 13, the projected ocean.
**Blocks:** nothing built. It blocks the question of what being in the water *costs*.

The projection puts a swimmer somewhere and drifts them. It says nothing about how long
they last, and that is the whole of the question: exhaustion, cold, whether a wound
matters more in the water, whether a raft or a spar helps, and what happens at the end of
it. Every one of those is a statement about how harsh the game is, and none of them is
mine to make.

It is also the one place where the contrib would reach into the host game's own systems.
Stamina, health and death already exist in whatever game installs this, and a maritime
contrib that shipped its own drowning rules would either duplicate them or fight them.

The options, as far as I can see them:

1. **The contrib does nothing.** A swimmer floats indefinitely; the game kills them if it
   wants to. Cleanest separation, and the game has to write everything.
2. **The contrib exposes hooks and no rules** — time in the water, sea state, whether they
   are holding onto something - and the game decides what those cost.
3. **The contrib ships a default with the numbers configurable.** Convenient, and it makes
   an opinion about lethality the default for every game that installs it.

**What I did:** option 1, for now, and deliberately - `Floating` carries a position, a
windage and a buoyancy, and nothing that decays. `Buoyancy` does carry a sink rate as well
as a flag, because something that has stopped floating is still somewhere and phase 25
needs that, but nothing yet decides when floating stops.

**What it needs from you:** a direction, and probably not until damage lands, since going
into the water will mostly be something that happens to you rather than something you do.
