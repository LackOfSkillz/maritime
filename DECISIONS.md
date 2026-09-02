# Decisions waiting on Gary

Questions that came up while building and are not mine to answer. Each says what is
blocked, what the options look like, and what I did in the meantime so that nothing
stalled.

Nothing here is a bug. These are places where guessing would have produced a plausible
answer that quietly became load-bearing.

**Nothing is outstanding.** The six that stood here were answered together, and are below.

---

# Answered

Kept rather than deleted. What was decided is less useful than what the alternatives were
and why one was picked - the next person to ask "why does capture work like that?" deserves
the argument, not just the outcome.

---

## Tactical pacing

**Was blocking:** how a fight paces, and how a new captain survives learning to fight one.

**Decided:** pacing is geography and cargo. Not difficulty scaling, and not a dial.

A small hull cannot cross open water and survive, so a new captain is confined to safe,
low-paying coastal passages *without anybody telling them they are a beginner*. The ladder
enforces itself through seaworthiness, which is already modelled. The day her hull can cross
open ocean is the day the lucrative water opens.

Risk then follows **what you load**, not what you have achieved. The source is explicit that
pirates ignore grain and hunt spices and precious metals, and it draws its trade routes as
two kinds of line on one map - escorted and unescorted. So a captain picks their own
difficulty by choosing a cargo and a route, and escorted routes are what consorts (item `S`)
are for.

**Why not level scaling:** because a world that grows with the player is a world where
nothing is ever actually safer, and the progression stops meaning anything. Here the sea is
fixed and the captain changes.

For the original question - how fast a fight resolves - a new captain gets time from the
slow attrition channel and from escape being real. **A ship that can run is a ship that can
learn.**

---

## What the sea does to a person in it

**Was blocking:** sinking, man overboard, and what a foundering means for anybody aboard.

**Decided:** we put them in the water and publish the conditions. **The game decides what
that means.**

The same rule that keeps economy, character combat and stamina out of this contrib, and this
is the case where breaking it would be most tempting, because drowning feels like physics
rather than policy. It is not: how much punishment a person absorbs is a character system,
and character systems are the thing we must not import.

What we publish is enough for any game to decide well: water temperature, sea state,
distance to the nearest land, whether they have anything to hold on to, and how long they
have been in. Gary's three bands - cold kills quickly, a rough sea drowns whoever tires
first, calm and warm is survivable but not for two hundred miles - ship as the **worked
example in the handbook**. Guidance a game copies, not mechanics we enforce.

**Prerequisite:** sea temperature does not exist yet. `environment` supplies wind, sea state,
current and visibility, and no temperature. It is small, and nothing above works without it.

---

## What a cargo is worth, and what a contract says

**Was blocking:** phases 21 and 22.

**Decided:** ours, behind `MARITIME_CARGO_ECONOMY`, **off by default**.

This reverses the earlier deferral, and the reversal is right because the interesting half is
already built: `stowage` models *both* capacities, deadweight and volume. That is the whole
game. Heavy cheap cargo - grain, salt, coal, timber, stone - fills her tonnage while the hold
stands half empty; light valuable cargo - spices, silk, dyestuffs, wine - fills the volume
long before the marks go under. **The cargoes worth thinking about are the ones that trade
the two off**, and no other naval system can express that because none of them carry two
capacities.

The pricing model is the source's and it is the correct one: a port has a **surplus of what
it exports and a shortage of what it imports**, and price follows from that rather than from
an authored number per commodity.

One consequence is load-bearing elsewhere: **piracy follows cargo value, not traffic.** That
is what makes the pacing decision above work, so these two are really one decision seen
twice.

Off by default, so a game arriving with its own economy is untouched.

---

## What being tender should cost her

**Was blocking:** phase 24's refits, and repair generally.

**Decided:** damage sets **time in dock** and **the size of the bill**, and the bill is paid
from the ship's ledger rather than by a player.

The source splits repair in two and the split is the mechanic. A carpenter with carried
spares handles routine work indefinitely at sea - seams, cordage, sails, even re-rigging -
so a properly found ship stays out as long as her food and water last. A **yard** is needed
only for major repair and overhaul. So:

    routine    costs crew time, and nothing else
    major      costs money and days alongside

A jury-rigged mast stays slower until a yard sees her. That is a **scar**, not a cooldown,
and it gives a reason to make port that no hit-point system has.

**The ledger this is paid from is a new subsystem**, and it is Gary's design: money lives on
the *vessel*, not the character, because the contrib cannot know what a player is - some
games have no player currency at all - but every ship must pay for repairs, wages and cargo.
Three denominations, because one unit cannot span a day's wage and the price of a ship;
names and ratios configurable. It is a prerequisite for phases 14, 21, 22, 23 and 24, which
is five dependents, so it wants building early.

---

## What becomes of an offline player when she sinks

**Was blocking:** sinking at all.

**Decided:** **the boats, and then the water.**

She carries boats and the seats are limited. When she founders, offline characters take one
automatically; the boat becomes a floating thing and drifts on the current and the wind,
which `floating` already does for a swimmer, a barrel, a raft and a corpse. They log in
adrift and alive, with a story. If there is no seat left they go into the water, and the
ruling above applies.

What makes this better than kindness: **the source destroys ship's boats by name in its
criticals.** So boats can be shot away during the fight, and "did you keep your boats?"
becomes a tactical question with a consequence that outlives the battle. Phase 25 already
lists survivors in the wreck lifecycle; this is where they come from.

**Rejected:** washed ashore (simplest, but wrong in mid-ocean); straight into the water for
somebody who cannot act (harsh, and they cannot swim for themselves); held in limbo until
they log in (elegant on paper, indistinguishable from a bug).

---

## How lethal damage should be

**Was blocking:** nothing - there was a working default. It decides how a fight *feels*.

**Decided:** keep the constant where it is. **Change the shape instead.**

`RESILIENCE_PER_METRE` was set to nine against the guns, aiming at a long grind with a sudden
ending, and at leaving something worth capturing. Reading the source confirms that aim rather
than overturning it, so the dial does not move.

What the source *did* change is the structure the dial feeds, and it is written up properly
in `docs/damage-model.md`. In short: damage arrives on two channels and only attrition is
fast; a critical **opens a process and never concludes one**; each track is a short ladder of
legible steps rather than a bar that empties; and - the finding that matters most - **the
crew ladder ends in surrender, not death.**

That last one makes capture the *cheaper* win and turns the ammunition triangle into a choice
of ending rather than a choice of flavour. It also means a player who loses a fight is
usually alive, ashore and short one ship, which is how this model can be lethal without being
cruel.

**Still true:** the tracks stay as they are however lethal anybody wants it. The point of
five of them is that a ship can be fast and toothless, or intact and unable to steer.

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
