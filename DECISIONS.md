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
