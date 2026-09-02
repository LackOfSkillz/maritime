# Ship combat roadmap — read from the source, improved on

Structure and algorithms taken; no tables, numbers or names travel. Every item below says
what the source does, what we do instead, and why ours is better than the naval systems in
the big commercial MUDs.

## Where the competition actually is

The established naval MUDs model a ship as **hull points plus sail points on a room grid**,
with weapons on cooldowns and repairs that top the numbers back up. That is a perfectly
good game. What it cannot express is *where* you were hit, *what* that broke, and what the
ship can still do — because there is only one number per system and no geometry underneath
it.

We already have the two things that make the difference and they are already built:
**continuous coordinates** and **real relative geometry** (bearing, aspect, arcs, closure).
Nothing below invents a combat grid. Every mechanic here reads geometry we already compute,
which is why this can be better rather than merely different.

---

## B. DAMAGE TRACKS  *(next item — foundation for everything after)*

**Source:** hull, rigging, oars, weapons and crew are separate tracks, and critical results
are qualitative — a mast down, a hole below the waterline — rather than a number going down.

**Ours:** the same separation, plus the tracks feed back into the *existing* simulation
rather than into an abstract "combat effectiveness":

- rigging damage reduces effective sail area → her polar curve already does the rest
- oar damage removes positions → `rowed_speed` already reads positions
- crew damage routes through `take_casualties()` → morale, exhaustion, striking and
  mutiny all respond with no new wiring
- weapon damage removes guns from a battery → the arcs already know which bear
- hull damage is the only one that sinks her

**Why better:** a ship that is fast and toothless, or intact and unsteerable, or whole and
unwilling, are three different ships. One pool cannot say that, and every one of those
states is reachable here.

**Consumes `hesitation`**, which morale already computes and nothing yet reads.

---

## C. AMMUNITION AS INTENT  *(the tactical core — do this with damage tracks)*

**Source:** ammunition determines what you can hit. Ball for the hull, chain for the
rigging, grape for the crew — with range restrictions that put grape and crew-shooting at
knife range. And the design note that makes the whole system sing: *pirates shoot for the
rigging to slow a ship so they can catch and board her; shooting for the hull is how you
sink one, and sinking her is the last thing a pirate wants.*

**Ours:** the same triangle, because it is the best idea in the book:

    ball    → hull      I intend to sink you
    chain   → rigging   I intend to catch you
    grape   → crew      I intend to board you

**Why better:** choosing ammunition *is* choosing your intent, and it ties straight into
capture being harder and more valuable than sinking. It also gives the pirate/merchant
career split real mechanical teeth rather than being a label.

**Also from this section:** a broadside fired at one target resolves as a single heavier
attack rather than several small ones — so concentrating fire is rewarded, and the arcs
that decide which guns bear are already built.

---

## D. POINT OF IMPACT AND RAKING  *(emergent, not special-cased)*

**Source:** where you hit matters more than anything else — a strike on the beam is worth
far more than one on the bow, and the modifiers are large.

**Ours:** we do not need an impact table, because we have real relative bearing. The angle
between her heading and the line of fire *is* the point of impact, continuously. Which
means **raking fire — crossing an enemy's bow or stern so a shot travels the length of her
— falls out of the geometry for free** rather than being a special rule.

**Why better:** in a hex system raking is a table entry. Here it is a thing you achieve by
sailing well, and a thing you can be caught by if you let someone across your stern. That
is the single most famous manoeuvre in the age of sail and no MUD models it.

---

## E. RAMMING AND SHEERING

**Source, ramming:** resolved on movement when one ship tries to occupy another's space and
ends the rammer's move. Severity capped by the sizes of both ships and by bow fitting (plain
hull, spur, or ram). **The rammer takes damage too**, heavily modified by impact angle —
bow-to-bow is bad for both, a strike on the beam is devastating for the target.

**Source, sheering:** running down an enemy's side to shear off her oars. Requires the
target to be under oars and your bow to have passed through her side; **the target
counter-attacks**, weaker. How much of her side you ran down changes the severity.

**Ours:** both read the geometry and the closure speed we already compute, so impact energy
is real rather than tabulated, and the bow fitting is a hull property alongside length and
beam. Sheering is naturally oar-specific because `oar_plan` already says whether she has
looms out to break.

**Why better:** ramming that hurts the rammer, scaled by real closing speed and real angle,
is a decision with a cost. Nobody else models sheering at all.

---

## F. FIRE  *(the best single feature in the book)*

**Source:** fire starts from fire attacks or from accident, and **spreads with an escalating
chance the longer it burns** — reset each time it spreads, so an unfought fire becomes
near-certain to grow, and can start a second fire. Fighting it costs crew, with diminishing
returns. **The ship must stop for the pumps to draw**, because the hoses go over the side.
Sails are handed to stop them catching.

**Ours:** all of it, because it is superb. The stopping rule is the gem — a burning ship
must choose between running and surviving, and that is a genuine dilemma no hit-point model
can produce.

**Why better:** fire that spreads on its own schedule, competes with you for crew, and takes
away your ability to manoeuvre is a *situation*, not a debuff. It also composes with
everything else we have: hands fighting fire are hands not at the guns, not at the oars, and
morale is already watching.

---

## G. FLOODING AND PUMPING

**Source:** bailing and pumping as the in-battle repairs, each slowing the rate at which
hull damage accumulates while they continue.

**Ours:** hull damage below the waterline admits water; pumping and bailing hold it back
while crew are on them. `Buoyancy` already carries a sink rate with nothing to drive it —
this is what drives it.

**Why better:** it makes sinking a process you fight rather than a threshold you cross, and
it competes for the same hands as fire, guns and sail.

---

## H. BOARDING MELEE AT SHIP SCALE

**Source:** a ship assigns **one boarding party or one repelling party per enemy**, drawn
from marines, seamen and oarsmen, committed simultaneously and unavailable for other work.
Party size is capped by **how the hulls touch** — bow-to-bow admits few, side-by-side admits
many, and being properly alongside doubles it. A repelling party may be any size but **only
about twice the boarders can actually reach the fighting**. Force strength sums each person
by type and quality. Four outcomes: boarders beaten, defenders beaten (**ship taken**),
neither (both reinforce), and unopposed (**taken**).

**Ours:** all of this, with contact frontage computed from real hull geometry rather than
read off a table of hex adjacencies — we know both hulls' length, beam, heading and relative
position, so how much of them is actually in contact is a measurement.

**Why better:** the cap on how many defenders can fight is what stops boarding being decided
by headcount, and it is the detail every other implementation misses. Numbers matter, but
frontage decides how much of them you can bring.

**Note — a real gap in what we have:** our `CrewQuality.skill` conflates *working the ship*
with *fighting*. The source separates crew type from quality for exactly this reason: a
crack crew of seamen is not a party of marines. We need a second axis, or complement
composition, before this item.

---

## I. CAPTURE  *(completes ownership from item 1)*

Four conditions, all required, per Gary: grappled and held, **and** struck, **and** her deck
carried, **and** her captain subdued or killed. Ownership and command pass to the owner and
captain of the taking vessel. Player captains resolved through a seam the game overrides.

**Why better:** capture that is genuinely harder than sinking, and worth more, is what makes
the ammunition triangle a real decision instead of flavour.

---

## J. POST-BATTLE CASUALTY RESOLUTION

**Source:** the casualty count resolves *afterwards* into four kinds — dead, wounded who
recover over days, dazed who return at once, and **shirkers who broke and refused to fight**.
The split depends on crew quality: good crews produce dazed, poor crews produce shirkers.
Medical care shifts dead into wounded.

**Ours:** the same four, and then the part the source does not do — **shirkers feed back
into morale and mutiny.** A captain who punishes them harshly earns a grievance; one who
ignores them keeps a crew that knows it broke. Item 2's machinery is already waiting.

**Why better:** it makes the aftermath of a battle a story rather than a repair bill, and it
closes the loop between combat and the morale system we already built.

**Character casualties stay the game's.** We publish the fraction — "she took 38% casualties"
— so a game can roll its own people against it. We never decide that a player is hurt.

---

## K. BATTLE SAILS AND BATTLE REPAIRS

**Battle sails:** reduced canvas trading speed for less rigging to be shot away and hands
freed for the guns. A real trade, and it reads the sail plan we already have.

**Battle repairs, from the source:** a repair rate per day, doubled if she does nothing else;
masts taking days, and a jury-rigged mast permanently slower until a yard replaces it;
weapons needing spares carried or scavenged from a prize; crew replaced only in port or from
a prize's volunteers. In battle only three things are possible: bailing, pumping, replacing
sail.

**Why better:** "jury-rigged and slower until a proper yard sees her" is a scar, not a
cooldown. It gives a reason to make port that no hit-point system has.

---

## L. GRAPPLING, DEEPENED

**Source:** grapples are a *count*, not a boolean — how many lines you get across depends on
contact geometry and crew quality, each costs a hand, and unfouling is harder the more
contact there is.

**Ours:** we already grapple on relative velocity, which is better physics. Add the count:
lines made up as a number, so holding her is a matter of how many and cutting free is a
matter of how fast.

---

## Suggested order

    B  damage tracks          foundation; everything else writes into it
    C  ammunition as intent   the tactical core, needs B
    D  point of impact        falls out of geometry once C exists
    K1 battle sails           small, and makes C a decision
    E  ramming and sheering   needs B and D
    L  grappling deepened     small, precedes H
    H  boarding melee         needs the fighting-strength axis added first
    I  capture                completes H and item 1
    F  fire                   large, independent, can slot anywhere after B
    G  flooding and pumping   pairs with F, competes for the same hands
    J  post-battle casualties closes the loop into morale
    K2 battle repairs         last; it is what you do after everything above

---

# Second pass — the optional rules, which are where the good stuff was hiding

## M. BLOCKED WIND — stealing another ship's air  *(the best find of the second pass)*

**Source:** a sailing ship directly downwind of another has her wind blocked and loses
speed; less so under battle sails.

**Ours:** we can do this enormously better than a hex rule. Continuous coordinates mean a
**wind shadow** is a real cone extending downwind of a vessel, its width and length scaled
by how much canvas she has aloft. Any vessel inside it loses drive in proportion to how
deep in it she is.

**Why better:** it makes position relative to *other ships* matter, not just relative to the
wind — which is the thing every real sailing tactician fights over and no MUD models. It
turns "get to windward of him" into a genuine objective, it is why the weather gage was
worth dying for, and it composes for free with the sail plans and polar curves we already
have. Under battle sails you blanket less, which makes item K1 a three-way trade instead of
a two-way one.

## N. OPPORTUNITY FIRE — hold your fire until she bears

**Source:** a captain may declare guns held ready and fire them the moment a target presents
itself, rather than on his own turn. Declared and unused, they fire late at a penalty. The
failure modes are glorious: gun crews confused and unable to fire at all, or at worst **the
battery fires at the first friendly that enters its arc**.

**Ours:** far more natural for us than for the source, because our simulation is continuous
— "hold your fire until she crosses the bow" is an order that means something on a clock.
The arcs already exist and already know what bears.

**Why better:** it converts gunnery from "press fire when the cooldown ends" into a decision
about *when*, and the friendly-fire failure gives a poorly-handled battery real teeth.

## O. SPRINGING ON A CABLE — anchored gunnery

**Source:** a ship anchored at bow or stern can **pivot around her anchor**, and anchored
ships shoot better because the platform is steady. Cutting the cable to get under way in a
hurry means no anchor until she rigs a spare.

**Ours:** all three. We already have anchoring; this adds the ability to lay a ship where
her broadside bears on a channel and hold her there, which is how shore batteries and
harbour defence actually worked.

**Why better:** a stationary ship is currently a defenceless one. This makes anchoring a
*tactic* — and cutting your cable a decision with a consequence that outlives the fight.

## P. HOW FAST A CREW ANSWERS  *(ties straight into item 2)*

**Source:** routine ship handling is trivial for good crews and genuinely hard for poor
ones, modified by leadership, quality, urgency, and how long they have been trying.
Separately, a captain changing his mind mid-manoeuvre may find the crew fumble it, and a bad
enough fumble throws the whole ship into confusion.

**Ours:** orders take *time*, and how much time depends on crew quality and morale.
`hesitation` is already exactly this number and already unread. A crack crew shortens sail
before the squall hits; a green one is still at it when the squall arrives.

**Why better:** it makes crew quality visible every single watch rather than only in battle,
and it is the mechanism that makes a green crew *feel* green instead of merely scoring lower.

## Q. DEFENSIVE FIRE INTO A RAMMER

**Source:** the ship being rammed may fire everything that bears immediately before impact,
at a penalty, and those guns are then unavailable next phase.

**Ours:** the same. A last broadside into an oncoming rammer at point-blank range, paid for
with your next one.

**Ordering:** this was listed before item E and cannot be built before it - there is no
rammer to fire into until ramming exists. It also wants most of what N built: a battery that
fires on something crossing, at a penalty, without being told to each time. Swapped with E
in the order below.

## R. COMPLEMENT COMPOSITION — and why it needs no money

**Source:** marines, seamen and oarsmen are separate groups with separate fighting values,
and quality applies to each independently. A ship's overall quality is the blend.

**Ours:** the same three groups, which fixes the gap already noted — `CrewQuality.skill`
currently conflates working the ship with fighting.

**The economic point, and the important part:** Gary wants complement to be a *choice with a
cost*. It already is, without any money at all, because **people are deadweight**. Forty
marines occupy tonnage and volume and eat provisions, and the contrib already models
deadweight, hold volume and stowage. A merchantman that ships marines *carries less cargo* —
a hard physical trade the contrib owns completely.

Money stays the host game's. What we publish is the physical fact; what a game does about
wages is its own business. That way the trade-off bites even in a game with no economy at
all, and a game with one has something real to price.

## S. CONSORTS — sailing in company

Gary's escort idea. The authentic terms are already there: ships **in company**, a **consort**,
and **keeping station** on another vessel.

**Ours:** a vessel can be ordered to keep station on another — a bearing and a distance she
holds. The sailing master already steers to a mark; this steers to a *moving* one. Nothing
in the source covers it; it comes from the requirement.

**Why better:** convoys, escorts and a squadron that manoeuvres together, all out of one
order. And it composes with the wind shadow above, because station-keeping to leeward of
your consort is a genuine mistake you can make.

---

## Revised order

    B   damage tracks                DONE
    R   complement composition       DONE
    C   ammunition as intent         DONE
    D   point of impact and raking   DONE
    K1  battle sails                 DONE
    M   blocked wind / wind shadow   DONE
    P   how fast a crew answers      DONE
    N   opportunity fire             DONE
    E   ramming and sheering         DONE
    Q   defensive fire               DONE
    L   grappling as a count         DONE
    H   boarding melee               DONE
    I   capture                      DONE
    O   springing on a cable         DONE
    F   fire                         DONE
    G   flooding and pumping         DONE
    S   consorts and station-keeping independent
    J   post-battle casualties       DONE
    K2  battle repairs               last

---

# Smaller things noticed in play

## Range units are mixed inside one report  *(DONE)*

Seen live:

    The horizon, all round - 2.9 miles off:
      Ahead           a vessel under sail, two points off the port bow, 2.7 miles
      To starboard    a vessel, sails furled, broad on the starboard bow, 1.5 leagues

Three ranges, two units, and no way to compare them at a glance - which is the one job a
range column has. `format_range` picks its unit from the magnitude, so a single report
crosses a threshold partway down and changes vocabulary mid-list.

**Wanted:** one unit per report, and leagues where the setting says leagues. Cables for
close work are fine and authentic - a lead line and a boat's length are not measured in
leagues - but "2.9 miles" and "1.5 leagues" must not appear in the same list.

Small, self-contained, and touches `formatting.format_range` plus whoever chooses the
unit for a whole report rather than per line.

---

# Optional, not scheduled  *(TBD - Gary's call)*

Two ideas worth keeping, neither committed to and neither in the order above. Recorded
here with their reasoning so the thinking survives if we take them up.

## T1. A MARITIME INTERFACE  *(TBD)*

**The idea:** a player crossing from an ordinary Evennia room into the maritime coordinate
system gets a maritime interface, and gets their usual one back on stepping ashore.

**The reframe worth arguing about:** the contrib should ship *the protocol, not the
interface*. Everything else here is a seam rather than an implementation - the command
policy, the map provider, the deliberate refusal to ship a skill system - and a UI is the
least seam-like thing there is. Publish ship state as structured OOB/GMCP and Mudlet gets
it too, where a webclient-only feature serves half the audience. It also keeps a JS bundle
out of a directory reviewers will expect to be Python.

So: the contrib publishes a state payload, and a reference panel ships as an optional extra
a game installs deliberately.

**The payload is only what the ship already knows:** heading and ordered heading, speed,
sail plan, wind bearing and relative angle, depth under the keel, the four damage tracks,
morale band, and contacts. Emitted on transition and on meaningful change - the same
"which change is worth mentioning" discipline `messaging` already implements, which is the
same problem solved once already.

**The interface is composed from the hull, not chosen from a list.** A kayak, a ship's
boat, a cutter and a frigate are not four skins of one dashboard - they are four different
sets of questions that have answers. Every one of those questions is already asked
somewhere:

    no ship's company            no crew panel        `company is None`
    one paddling position        no helm, no orders   `oar_plan.positions == 1`, PADDLED
    no rig                       no sail panel        `sail_plan.area` never rises
    no guns aboard               no battery panel     `mounts` is empty
    nothing that will stow       no cargo panel       hold volume of nothing

This is the rule `Handled.hands_to_work_her` already follows when it refuses to invent a
crew for a hull that has none, and the reason a dinghy answers her helm at once. The panel
must refuse on the same terms. A kayaker looking at a crew morale gauge and an anchor
windlass would be reading somebody else's ship.

**The same goes for the water.** A pond has no tide, a lake has no swell worth reporting, a
river's current is the single most important number on the strip, and only at sea does the
horizon or the state of the tide mean much. The temptation is an enum - pond, lake, river,
ocean - and it should be resisted, for the same reason there is no skill system here: the
moment the contrib classifies water, every game with its own idea of water has to argue
with it.

Instead the strip is composed of readings the world can honestly answer *here*. No tide
model, no tide field. No current, no current field. Flat water reports no sea state. On a
pond the strip collapses to almost nothing on its own, with nobody having declared it a
pond - and a tidal river shows tide *and* current because both are genuinely true there,
which an enum would have made a special case.

*Open:* whether a game may pass an optional hint to force a presentation it prefers. That
would be a seam with a derived default, not a taxonomy.

**Two layers, and they must not be confused.** The chart divides cleanly in two, and the
division is what keeps it from becoming a radar screen:

    charted    persistent    from `charts`      land, soundings, marks, hazards
    sighted    volatile      from `contacts()`  other ships

Charted things stay on the paper whether or not anybody is looking at them, because somebody
wrote them down. **Sighted things exist only while the lookout has them** - a contact appears
when she is reported and goes when she is lost, and nothing about her persists. A ship that
stayed on the chart after the lookout lost her would be a radar repeater, and would quietly
undo detection in the same way a true-position marker would quietly undo navigation.

*Open:* whether a lost contact leaves a fading last-known bearing, which is what a navigator
would actually plot. The default is that she simply goes.

**And the chart is generated, not drawn.** Sample `charted_terrain_z_at` over the visible
window and contour it - coastline where it crosses datum, depth areas at fathom bands. That
is a hundred lines of marching squares and no dependencies. Contouring the *chart* rather
than the sea gives three things for nothing: the coastline is wrong in the same places every
voyage, water nobody has surveyed renders as a hole in the paper rather than as empty sea,
and a better chart is visibly better. It also satisfies the rule below structurally rather
than by discipline, because the true seabed is never asked for and so can never leak.

*Open:* whether a game may supply a hand-authored coastline to render instead of a contoured
one. Some games have drawn a world map and will want the chart to match it. That is a
provider seam rather than a rewrite.

**The rule to hold hardest:** the panel is a repeater, not an oracle. It shows exactly what
`contacts()` returns at that height of eye, so an unidentified hull is a bearing-only blip.
Honest, dramatic, and structurally incapable of leaking what the fiction has not granted.

**Two hazards found while looking:**

  - GoldenLayout's config global is overwritten by the player's saved layout in
    localStorage. Swapping the interface and swapping back would stomp arrangements people
    made on purpose. Additive instead: open a pane on entering, close it on leaving, never
    touch their layout.
  - A player can be on our deck inside a game with its own HUD. We do not own the screen.

**A design concept exists:** `ideas/maritime-interface-mockup.png`, with notes in
`ideas/README.md`. It settles the layout question - additive, a status strip and a
right-hand column around the game's own output pane, so nothing has to stomp a player's
saved arrangement. It also shows an unidentified contact sitting in the list as
"Unknown Sail", which is `Sighting.level` doing exactly the job the repeater rule asks
of it.

It assumes several things that are the host game's rather than ours - gold, experience,
stamina, a rank, and morale as a bare percentage where ours is banded on purpose. The
payload must not carry any of them.

**Open:** whether the reference panel lives in this repo at all or in a companion one,
and whether its buttons send ordinary commands - in which case the panel is a keyboard
and needs no new server surface - or a control channel of their own, which would need
every one of them to pass the same authority check `MARITIME_COMMAND_POLICY` already
performs.

## T2. PROVISIONS, FISHING AND SHORE LEAVE  *(TBD)*

**The idea:** stock the sea with fish, for players and for crew morale - stop and fish when
morale is low, and give shore leave between voyages.

**The trap:** food is the host game's economy. Shipping species, weights and prices is the
same mistake as shipping a skill system, and every game with cooking or fishing would have
to fight us.

**What is ours:** provisions as a physical quantity. Item R already established that people
are deadweight, occupy hold volume and eat, and stowage exists. So the contrib owns how
much a company eats, what is aboard, and what running short does to morale - and owns
nothing about what the food *is*. Fishing becomes an activity converting crew time into
provisions and publishing an event the game hooks, which is exactly the career-roadmap
rule.

**Why it is cheap:** fishing grounds are already in the world. Banks and soundings are
where fish are, historically and actually, so a game that authored a shoal authored a
fishing bank without knowing it. The same shape as raking falling out of the geometry.

**The part that is actually interesting - morale needs a second time constant.** The
current one is tactical: falls in a minute, recovers over fifteen. Right for a battle and
wrong for a six-week passage. Two different quantities:

    nerve         fast, driven by casualties and danger        (what we have)
    contentment   slow, driven by provisions, time at sea,     (new)
                  punishment and shore leave

Contentment sets the level nerve settles toward, so a well-fed crew stands fire better.

**And it gives the failure mode somewhere to go that is not mutiny.** Mutiny is already
what nerve failing looks like. Contentment failing *in port* is DESERTION - and after item
P, losing hands makes her measurably slower to shorten sail for the rest of her life. That
closes a hard loop: neglect the crew, lose people, and the ship is worse at everything
afterwards. It also makes shore leave a decision rather than a button, because time in port
is time not earning and skipping it costs you hands.

Heaving to in order to fish costs steerage way, which is the same shape as fire needing her
stopped for the pumps to draw. Fishing is a situation, not a menu.

**Open:** whether provisions are modelled here at all, and whether desertion - which
destroys something a player owns - is acceptable.

## T3. SURVEY AND DISCOVERY  *(TBD)*

**The idea:** charted land stays on the chart always, because somebody wrote it down - but it
must be possible to find land nobody has written down, and to be the one who writes it.

**Why it is nearly free:** `charts` already models coverage. A chart covers where its
surveyor went and nowhere else, and off the chart is a *state* rather than a failure. So
uncharted water already exists, is already dangerous, and already renders as a hole in the
paper once the chart panel contours charted rather than true depths. Discovery is the act of
filling one in.

**The mechanic worth stealing, and it is not the obvious one.** In the space-exploration
games that do this best, the credit does not go to whoever *saw* a thing first. It goes to
whoever first brought the record home and lodged it. Everything good follows from that one
choice:

  - Survey data is a thing you are *carrying*, not a thing you have achieved
  - It is worth nothing until you make port, so the voyage home is the dangerous half
  - Sink on the way back and the discovery is simply lost, and somebody else will have it
  - Two ships may survey the same coast, and the fast one home gets the name on it

That is also how it actually worked. Hydrographic offices paid for surveys on delivery, and
the reason so many straits and inlets carry a surname is that somebody sailed home with the
paper. We are not borrowing a game mechanic so much as arriving at the same one from the
same pressures.

**What is ours and what is not.** The contrib owns the survey: what was covered, how well,
how far it lay from any charted water, whether anybody had lodged it before, and the fact
that a chart records who first surveyed it. The contrib does **not** own what that is worth.
Money is the host game's, exactly as with prizes and cargo. Publish the event with enough
detail to price it - area, quality, distance beyond the charted world, first or not - and let
the game decide what the chart house pays.

**How it composes with what exists:**

  - Sounding while off the chart is what generates survey data, so the lead line finally has
    a second use besides not dying
  - Lodging a survey extends chart coverage, so the hole in the paper visibly fills in - a
    player can watch their own chart grow over a career
  - A ship carrying an unlodged survey has something to lose in a fight, which gives a
    merchant a reason to run that is not cargo
  - It feeds the sea career directly: "a coast surveyed" is exactly the kind of countable
    event that roadmap is built around

**Open:** whether a surveyor may name what they found, and if so who arbitrates the name;
whether a lodged survey is public to every chart in the world or sold chart by chart; and
whether an inaccurate survey can be lodged in good faith and get somebody else killed, which
is tempting and possibly too cruel.
