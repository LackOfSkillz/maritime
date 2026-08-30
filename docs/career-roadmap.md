# Roadmap — sea career, ship ratings and stations (after combat)

Gary, in his own words: players earn experience from captaining; you do not start with a
heavy galleon, you start with a kayak and work up through progressively larger ships; a
captain can assign the jobs normally done by ship's NPCs — gunner, lookout, helmsman — and
each of those is a skill of its own; and there are career shapes, so a player can build a
reputation as a pirate captain or as a merchant captain. **It has to hook into any Evennia
game's own skill system**, tested against DireEngine but never bound to it.

## The one decision that decides whether this works

**The contrib must not ship a skill system.** Not a small one, not a default one, not an
optional one. The moment it does, it is competing with whatever the host game already has,
and every game with its own skills has to fight it. That is the same rule that already
keeps economy, character combat and stamina out — and this is the case where it will be
most tempting to break, because a progression system feels like it needs numbers to be
real.

What the contrib ships instead is three things, and none of them is a skill:

1. **Events worth earning from.** A passage made, a prize taken, a cargo delivered, a
   storm ridden out, a grounding survived, a chase won. The contrib already knows when all
   of these happen; it just does not currently say so. These are published, and a game's
   own skill system listens. The `EventBus` and `OwnershipTransferred` pattern from item 1
   is exactly this shape and already works.

2. **Questions, asked through one replaceable seam.** Not "how skilled is this character",
   which is the game's business, but the questions the *ship* needs answered:
       may this character command a vessel of this rating?
       who is at the helm, and how well is she being steered?
       who is serving the guns, and how quickly?
       who has the lookout, and how far can they see?
   One provider a game points a setting at, exactly like `MARITIME_COMMAND_POLICY`. The
   default answers "well enough" to everything, so a game that adopts none of this still
   sails — the same principle as an unowned ship answering to anybody aboard.

3. **A rating for a hull, derived rather than authored.** The kayak-to-galleon ladder is a
   fact about a vessel that the contrib can already work out: her length, beam, rig, sail
   area, oar plan and tonnage are all known. Derive her rating from them the way `rank_of`
   derives ADMIRAL from how many decks answer to you — so a builder who makes a bigger ship
   gets a higher rating without having to remember to say so, and cannot make a galleon
   that claims to be a dinghy.

## Stations

Gunner, lookout, helmsman, and the rest are **posts**, not skills. The contrib already has
the work each post does — gunnery, observation, the helm — it simply assumes it is done
competently by nobody in particular. Making them posts means:

- A captain assigns a character (or leaves it to the ship's people)
- The ship asks the seam how well that post is being kept
- Everything downstream already exists: `hesitation` from morale is exactly the same shape
  of number, so the arithmetic for "this is being done worse than it could be" is built

That is the honest division: **the contrib owns what the post does to the ship; the game
owns how good the person is at it.**

## Careers

Pirate captain and merchant captain are not different mechanics, they are different
*histories* — the same events, counted differently. A game that wants a pirate reputation
counts prizes taken; one that wants a merchant reputation counts cargo delivered. Both are
already events. The contrib should resist inventing a reputation model and simply make sure
that everything worth counting is announced with enough detail to count.

## On the source books

Sea Law has skill sections (using the parent system's skills, navigation skills) and crew
stats, but **these are the least reusable part of it**, because they are bound to one
character system and character systems are precisely what we must not import. The parts
worth reading are the *stations* — what each post contributes to the ship, and what is lost
when nobody is in it — because that is ship-scale and portable. Take the structure of
"a post that is unmanned costs the ship this", not any table of skill bonuses.
