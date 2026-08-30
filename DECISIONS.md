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

---

## What a cargo is worth, and what a contract says

**Raised by:** phase 22, cargo.
**Blocks:** trade. The physical half is built - what stows how, what fits, what it does to
her draught - and none of it knows a price.

A freight rate is a statement about a whole economy: what a voyage is worth, whether it is
worth more in a war, who is buying, what a shipper does when you arrive late, and whether
the game has a currency at all. Every one of those already exists in whatever game installs
this, or is deliberately absent from it, and a maritime contrib that shipped its own would
either duplicate the game's economy or argue with it.

The same goes for contracts. A cargo contract is a promise with a deadline and a penalty,
which is the same shape as a passenger charter - and phase 21 is explicitly yours.

The options, as far as I can see them:

1. **The contrib never prices anything.** It moves tonnes; the game sells them. Cleanest
   separation, and what stands today.
2. **The contrib defines a contract shape and no values** - a commodity, a quantity, an
   origin, a destination, a deadline - and the game decides what any of it is worth.
3. **The contrib ships a working freight economy** with configurable rates. Convenient for
   a game with no economy of its own, and an argument with every game that has one.

**What I did:** option 1. `Commodity` carries a key, a name, a stowage factor and whether it
is bulk, and deliberately nothing about value, legality, perishability or demand. Those are
the four fields a ship's officer needs to load her, which is the part that is genuinely
maritime.

**What it needs from you:** a direction, and it pairs with phase 21 rather than standing
alone - passengers and cargo are the same contract with different freight.

---

## What being tender should cost her

**Raised by:** phase 22, cargo.
**Blocks:** nothing built. The condition is detected and reported; what follows from it is
open.

Weight stowed high makes a ship roll slowly and far, and in a seaway not always come back.
The system knows when she is in that state - the stability moment is computed from real deck
levels, and the manifest says so in as many words. What it does not do is make it hurt.

The trouble is that every honest answer reaches into two systems at once. A tender ship
should carry less sail, which is `sailing`; she should be more likely to be knocked down in
a gale, which is weather and damage together; and a knockdown is a flooding event, which is
phase 17 and yours.

The options, as far as I can see them:

1. **Reported and no more.** A warning on the manifest, and a master who ignores it gets
   away with it. What stands today.
2. **A sail limit.** A tender ship cannot safely carry her full plan, and the mate refuses
   to set it. Contained, and touches only `sailing`.
3. **A risk in a seaway,** resolved against sea state - which means deciding what a
   knockdown does, and that is damage.

**What I did:** option 1, and the arithmetic is finished so that whichever way this goes it
is already there. `stowed_moment` is signed relative to the main deck, so a stow that is too
high is a positive number rather than a flag somebody has to set.

**What it needs from you:** a direction, and probably alongside damage rather than before it.

---

## What becomes of an offline player when she sinks

**Raised by:** the LOGOUT-001 spike.
**Blocks:** nothing built. It blocks phase 17, which cannot break a hull up without
deciding this.

The spike answered the engine half and it turned out to matter more than expected. Evennia
takes an unpuppeted character off the grid entirely - `location` becomes `None` and the
room is remembered in `prelogout_location`. When that room is deleted, the attribute reads
back as `None` and the character is put in their `home` room the next time they log in,
with no message and nothing anybody can hook.

So there is already a policy, and nobody chose it: **everyone aboard survives, and is
teleported home without being told.** A game that never decides this will ship that.

The options, as far as I can see them:

1. **Keep the engine's default.** Foundering is survivable if you were offline. Cheapest,
   and quietly makes logging out the safest thing you can do in a storm.
2. **Resolve them like anybody else** - put them in the water, in a boat, or drowned, at
   the moment she goes, whether or not they are logged in. Consistent, and it means a
   player can lose a character while asleep.
3. **Hold them.** Do not resolve an offline passenger at all; leave the compartment alive
   until they log in and then tell them what happened. Kindest, and it means a sunk ship's
   rooms cannot be cleaned up on a schedule.
4. **Do not allow logging out at sea** in the first place, the way some games only let you
   quit in an inn.

**What I did:** nothing that presumes an answer, and one thing that makes any of them
possible. `Vessel.ships_company()` and `rooms.absent_from()` find the offline passengers
that `room.contents` cannot see, so whichever policy you pick, the people it applies to can
actually be enumerated. Without that, options 2 and 3 are not implementable and option 1
happens by default.

**What it needs from you:** a direction, before damage. It also interacts with whether
logging out at sea is allowed at all, which is the same question from the other end.

---

---

# Answered

Kept rather than deleted. What was decided is less useful than what the alternatives were
and why one was picked - the next person to ask "why does capture work like that?" deserves
the argument, not just the outcome.

---

## What a captor may do with a prize

**Was blocking:** capture meaning anything. Two ships could be lashed together, people could
cross, and she could strike - and then nothing changed.

**The options were:** striking as flavour and the game does what it likes with the fact; a
prize master who holds her without owning her; or ownership transferring outright.

**Decided:** ownership transfers, and command with it. A captured ship passes to the owner
and the captain of the vessel that took her - both, and to those two people rather than to a
side, because "side" is a concept this contrib does not have and the host game does.

**And it must be hard.** Harder than sinking her, which is the point that makes the rest of
it work: a capture is worth more than a wreck, so if capture were the easier road nobody
would ever fight to sink anything. Four conditions, all of them:

1. She is grappled and held alongside.
2. She has struck.
3. The boarding party carried her deck.
4. Her captain is subdued or killed.

The fourth is what stops a capture being paperwork. A ship whose captain is still on his
feet has not been taken, however many people are standing on her deck.

**What is built:** the machinery to receive it. `transfer_ownership(character, reason=CAPTURED)`
moves property and announces why, `pass_command` moves command, and the four conditions have
somewhere to be checked. Boarding melee wires them together.

**Still yours:** how a *player* captain is subdued. Resolving that at ship scale would mean
this contrib deciding when a player character is beaten, which is the one thing it must never
do. The default resolves NPC captains at ship scale so NPC ships can be taken at all, and a
game overrides one seam for the case where the captain is somebody with a keyboard.

---

## What goes upstream, and what stays here

**Was blocking:** nothing yet, but it would have at submission time.

Evennia's contrib guidelines want a folder with a README, the code, and tests. This repo
also carries a changelog, a decisions log, `docs/architecture.md` and a `.github/` holding
the discipline checker. None of that is forbidden - but merged into `evennia/evennia`, a
nested `.github/` does nothing at all, because only the repository root's counts. To a
reviewer it reads as clutter shipped by somebody who did not check.

**Decided:** they stay here and are stripped in the branch that becomes the pull request.
This repo is where the work is done and the discipline lives - `check_discipline.py` is one
of the three commands that must pass before anything is pushed, and the changelog is the
record of why every decision went the way it did. Losing either to tidy up for a reviewer
would be trading the thing for the appearance of the thing.

**What the PR branch drops:** `CHANGELOG.md`, `DECISIONS.md`, `docs/`, `.github/`. What it
keeps is what the guidelines ask for: `README.md`, the modules, `tests/`, `LICENSE`.

---

## What pulling an oar costs

**Was blocking:** whether a long pull is a decision or a formality. The system knew
`STRETCH_OUT` was faster than `GIVE_WAY` and nothing about it being harder, so a boat could
be raced across an ocean.

**The options were:** do nothing and let the game tire people; expose a hook and no rule; or
ship a sustainable-stroke rule with configurable numbers.

**Decided:** none of those three, in the end — a fourth that only became visible once crew
quality existed. **Exhaustion is a ship-level state.** Not how tired any person is: how spent
the *company* is, as one number on the hull.

That dissolves the original difficulty rather than choosing a side of it. The worry was that
stamina already exists in whatever game installs this, or is deliberately absent, so a
maritime contrib shipping its own would duplicate or argue with it. At ship scale there is
nothing to duplicate. No character's stamina is touched, no health system is consulted, and
a game with no notion of tiredness at all loses nothing — she simply pulls slower and her
people are closer to breaking, and both of those are facts about the ship.

**What it does:** `spend` tends the company towards the effort being asked rather than
accumulating without limit, so easy oars all day tends towards rested and a racing stroke
gets most of the way to spent in half an hour. A wholly spent crew have lost half their
speed — still pulling, because a boat rowed by exhausted men is slow rather than stopped.
And exhaustion past a threshold becomes a *grievance*, which is the part that makes it a
decision: run your people into the ground in a chase and you may not have a crew afterwards.

**Still yours, and unchanged:** what being in the water does to a person. That one was
always the harder half of the pair, and nothing here touches it.
