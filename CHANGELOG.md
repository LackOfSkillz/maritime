# Changelog

All notable changes to the Maritime contrib.

Entry prefixes follow Evennia's own changelog convention (`Feat:`, `Fix:`, `Docs:`,
`Chore:`) so that entries slot in naturally if this contrib is merged upstream.

## Unreleased

Nothing released yet. Foundations, the spatial model, vessels, the simulation
service, sailing, grounding and who owns a ship are in place; ports, navigation,
weather, crew, combat and damage are not.

### Docs

- **Every open decision is answered, and `DECISIONS.md` has nothing outstanding for the
  first time.** Six of them, settled together: how lethal damage should be, what the sea
  does to a person in it, what becomes of an offline player when she sinks, what a cargo is
  worth, what being tender should cost her, and tactical pacing.
- **`docs/damage-model.md`: what phase 17 is going to be, written down before it is built.**
  The shape was worked out by reading the source once and it should not have to be read
  again. Two damage channels of which only attrition is fast; a critical that **opens a
  process and never concludes one**; each track a short ladder of legible steps rather than a
  bar that empties.
- The finding that reorganised the rest: **the crew ladder ends in surrender, not death.** A
  ship whose people are shot to pieces strikes her colours. So grape fills the track that
  ends in her changing hands while ball fills the one that ends in her sinking, and the
  ammunition triangle becomes a choice of *ending* rather than of flavour. It also makes
  capture the cheaper win, which promotes item `I` from a finishing touch to the thing the
  rest leans on - and it means a player who loses a fight is usually alive, ashore and short
  one ship rather than dead.
- **Two rulings turned out to be one.** Piracy follows cargo value rather than traffic, so
  "what is a cargo worth" and "how does a fight pace" are the same decision seen twice: a
  captain picks their own difficulty by choosing what to load and which way to carry it. No
  level scaling anywhere - the sea is fixed and the captain changes.
- **`RESILIENCE_PER_METRE` does not move.** It was set against the guns aiming at a long
  grind with a sudden ending; the source confirms that aim rather than overturning it. What
  changed is the structure it feeds, not the dial.

### Feat

- **Dredged channels, dug by the engine rather than authored.** `dredging` lets a world say
  the one thing it never could: that the sea here is *deeper* than the ground would suggest.
  Everything else a world could declare - hazards, banks, rocks - makes the water shallower,
  and a harbour is the opposite of all of them.

  Nothing is written down. `Dredged` reads the quays out of the game, takes the deepest
  berth each one advertises, sounds sixteen bearings out from it for the nearest sea that
  *stays* deep, and cuts between the two at that depth plus two metres. Put down a room with
  berths and the way in appears with it; deepen a berth later and its channel deepens too.
  The alternative - a list of cuts kept beside the world - is a second description of the
  same harbour, and the two part company the first time anybody moves a pier.

  On the coast this was written for it is the difference between a working harbour and a
  decorative one. Six metres of water was most of a kilometre out and the last of the run in
  crossed two and three metres of sand, so every quay was correctly reported as having no
  safe water into it. Long Pier now advertises 6.00 m against a channel carrying 7.38 m the
  whole way, so a hull loaded to the marks the berth accepts can still get to it.
- The cut runs out to water that *holds* its depth for five hundred metres, not to the first
  deep spot. A channel ending in a hole with a bar beyond it grounds a ship on the way
  **out** - which is the failure nobody tests for, because everyone arrives before they
  leave.
- The sides slope. A vertical wall would put a hull half a metre outside the cut in three
  metres of water where one half a metre inside had eight, and a dredger's spoil will not
  stand up vertically under water in any case.
- **Clickable harbours, and one order that gets her there.** `make for <harbour>` lays the
  course over the marked channels, hands the con to the sailing master, and gives him the
  one standing order he takes: to warp her in when she arrives. `ports` lists what she can
  be told to make for and *why not* for the rest. A harbour on the chart is a symbol you
  click, which sends `make for <harbour>` as ordinary typed text - so nothing the browser
  can do is unavailable to a telnet player.
- Unreachable harbours are still drawn, hollow and dimmed, with the reason in the tooltip.
  Hiding them would leave a captain wondering where the pond went; drawing them as reachable
  would be a lie the command then refuses.
- **Reachability is two questions.** A course over the marks somebody laid - which is what
  keeps a clever search out of a pond by way of water that is technically continuous - and
  water on the two legs no mark covers: the run in from the last mark to the quay, and the
  run out from wherever she is floating to the first mark. Both were missing; the second was
  found when a course the game planned itself put a ship on a spit two hundred metres away.
- **`example/aetos_world/approaches`: a navigation network for the shipped coast.** A mark
  walked seaward off every harbour until there is twelve metres under it and two hundred and
  fifty metres of clearance beyond the foul ground, plus one authored fairway. The fairway
  exists because the direct line from Careenage to Gannet Isle crosses two shoals of 2.7 and
  3.4 metres; its position was found by sounding a grid, and `tests/test_approaches.py`
  re-sounds every leg on every run - including the run in from each mark to each berth,
  which is the leg a ship actually arrives on and the one nobody would have thought to
  check.
- **`kedge`**: run an anchor out astern on a hawser and walk the capstan round, which is the
  thing that was actually done. Each heave hauls her part of the way to the nearest water
  she would float in; a soft bottom lets her slide, rock holds her, and a hull that has been
  opened cannot be kedged at all - she is not held by the ground, she is sitting on it
  because the sea is inside her.
- **The sailing master weighs for a passage and anchors when he cannot sail.** Ordering a
  passage is one decision, so he brings the anchor home himself rather than sitting at
  anchor waiting to be told twice. And when the water shuts in front of her and no heading
  within sixty degrees is clear, he lets go rather than merely stopping - taking the way off
  her and doing nothing else is a slower grounding, which a ship proved by coming to rest in
  two fathoms and being set down onto the beach at eight tenths of a knot with the mate's
  warning still the last thing anybody had heard.
- The margin comes off on the final approach. A quay is in shallow water by definition, so
  a mate carrying two metres of spare water everywhere would not take a ship to her own
  berth - and did not, steering for the pier and refusing to give her way. The last leg has
  already been checked against the berth's own advertised depth, which is somebody's
  statement that she fits.
- **Guardrails on grounding**, which was close to unsurvivable. The leadsman now casts
  *ahead* of the ship rather than under her middle; the sailing master sounds ninety seconds
  ahead and falls off up to sixty degrees rather than carrying her onto ground he can see,
  and stops and says so if the water is foul all round; and `HOLING_SPEED` has gone from
  1.5 m/s to 4.0 with a separate `TOUCHING_SPEED` of 2.0 beneath it. Under three knots
  everything was a holing, so a hull that touched a rock while ghosting under a reefed
  topsail was lost. Taking the ground gently, being hard on and waiting for the tide, and
  being opened on a reef are three different afternoons.

### Add

- **A handbook**, for players and for developers, in `web/static/maritime/help/`. One set of
  markdown files read three ways: in the repository with the links working, as a rendered
  page at `/static/maritime/help.html`, and from the panel's `?` button. `maritime help`
  gives the address to anybody in a plain client, and `maritime help <topic>` opens a page.
- Two copies of a manual is one copy and one lie, so the web page renders the same files the
  repository shows rather than carrying its own. The renderer is small and deliberate: no
  library, so the handbook works with no network, inside a content policy, and with the
  server down.
- The developer half answers the question people actually ask, which is not "how do I run an
  age-of-sail simulation" but **"I have a game, and I want a ferry"** - four worked recipes
  that take two layers and leave the rest out, and a table of what each omitted layer costs.
  Nothing in it throws: absence is a configuration.
- Grouped and ordered the way somebody would learn it. Alphabetical order in a manual is a
  filing decision presented as a teaching one.
- A test holds it to the game: links resolve, the contents is complete, the command's topic
  list and the files agree, and every command it tells somebody to type exists. Writing that
  test found the handbook claiming `rehoist` was a verb - it is not, `strike` is a toggle.
- **`maritime help` has a set of its own**, which goes on the character class so that it
  works everywhere. It went into the runtime switches set first, which quietly broke that
  set's contract - a game can install it and put nothing in front of its players, and an
  all-access command in it is not nothing. Then it went into the helm set, which asserts
  exactly which verbs handle a ship and is the wrong home for a different reason: a manual
  on a deck is one that a lost player, who is usually ashore, cannot reach. Four tests
  between the two sets caught both placements.
- Writing the developer pages against the real modules found three more: `OarPlan` does not
  take `benches`, the current setting is `MARITIME_CURRENT_SET` rather than `_BEARING`, there
  is no `ENCLOSED` exposure, and the integration steps omitted the driver script - without
  which a game gets ships that accept every order and never move.

- **The boarding melee.** One party crosses, one meets them, and four outcomes: the
  boarders thrown back, her deck carried, neither and both sides feed in more, or nobody
  left to meet them and she is taken unopposed.
- **Frontage is measured, not tabulated.** How many can cross is the real length of rail in
  contact - the overlap of the two hulls times the shorter one - and being properly
  alongside doubles it, because every foot of the contact is then somewhere a man can cross
  rather than one point where two hulls happen to meet.
- Only about twice the boarders can reach the fighting, which is what stops a boarding being
  decided by headcount. Three hundred men do not beat forty marines by three hundred to
  forty; they beat them by eighty to forty, and the marines can win that.
- **A property nobody designed, that a test found.** While the defender has men to spare she
  meets whatever crosses with twice its number however wide the contact - so frontage
  changes the size of the fight and not the odds. The moment she cannot field twice what
  comes over, every extra man across is a man she has nobody to meet, and the contact starts
  deciding the outcome. Which is the whole argument for beating her down before boarding
  her, and it fell out of the two caps meeting.
- Marines go across first, then seamen, then whoever is left. A captain sends the people he
  shipped to fight.

### Fix

- **A company crewed the ordinary way could not send a man across.** `man` does not ask for
  divisions and boarding is the one question that needs them, so a fully manned ship
  reported that nobody could board and said nothing about why. A company with no divisions
  now answers with what she is - seamen - rather than with nobody.

- **Grapples are a count, not a yes.** How many irons get across is decided by how much of
  the two hulls are actually alongside, by how fast she is sheering away, and by how many
  hands there are to throw them - each line costs three, so a ship with sixty fit men cannot
  work twenty of them. Any of the three can refuse the boarding on its own.
- What the count then decides: how hard she is to shake off, and how long it takes to get
  free again. More lines hold harder but only by the square root of the count, because
  breaking free has to stay possible - it is what makes being boarded survivable and worth
  trying to survive.
- **Unfouling is harder the more contact there is.** Clearing twelve irons with the two
  hulls grinding together is an undertaking, and a captain who let himself be thoroughly
  lashed has to live with it. Routed through `handling_time`, so being short handed and
  being frightened cost the same here as they cost on every other job aboard.

- **A last broadside into an oncoming rammer.** The ship about to be struck fires everything
  that bears in the moment before impact - not a standing order and nothing to declare,
  because a gun crew watching a bow come at them fire.
- It is not free damage. Every gun that speaks starts its reload, so she meets whatever
  follows the collision with an empty battery. The source makes those guns unavailable for
  the next phase; a continuous simulation gets the same cost by adding no rule at all.
- **And it is a poor bet, which is the point.** A ship driving at you is end-on, the
  narrowest she will ever look, and `aspect_accuracy` already says what that is worth - so
  most of the shots miss. That is not a shortfall to be tuned away: it is why ramming is
  worth attempting, and it fell out of geometry that was already there.

- **Ramming, and it costs the ship doing it.** A hull driven into another is asked to
  survive the same collision she is delivering, which is what makes it a decision rather
  than a free attack. The energy is one half m vee squared off the reduced mass of the two
  hulls and the closing speed along the line between them - so chasing her is a poor way to
  hit her, meeting her is a violent one, and a heavy ship hurts more for no reason except
  that she is heavy. None of that is tabulated.
- Damage is energy *per tonne of the ship receiving it*, which is what makes the same
  collision a third of a brig's hull and the end of a ship's boat. The first version divided
  joules by a constant, and a frigate running down a boat barely scratched her - right
  arithmetic, wrong question.
- **Which face was struck decides what a square blow even is.** A stem is the strongest part
  of a ship and her side the weakest, and the corner between them is her own proportions
  rather than a fixed arc - so a beamy hull presents a wide bow from ahead and a fine one a
  knife edge. The first version measured obliquity from her beam, which made running square
  into her stem - the worst collision there is - read as a graze and refuse to resolve.
- Bow fittings: a plain stem, a spur, or a ram. What a beak *is*, in two numbers: it drives
  more of the blow into her and takes less of it back, because it is structure built forward
  of the hull to be hit instead of the hull.
- **Sheering**: running down an enemy's side to break the looms she has out, with her oars
  breaking against your topsides as they go. How much of her side you ran down decides how
  many, and a ship under sail alone cannot be sheered at all.
- Contact is solved rather than sampled. Stepping along the track and testing each position
  is what grounding does against the seabed, and it is wrong here for a reason grounding
  does not have: a ship is a small object, and a coarse step walks straight past one. The
  stem's track is clipped against the target's hull as an oriented box - exact, constant
  time, and no step size to get wrong.
- Both decks are told, and told different things. A collision has a rammer and a rammed.

### Fix

- **Two rooms in Careenage had two exits of the same name, and one was unreachable.**
  `High Row` had two called `down` - one to each of the two lanes that climb to it - and
  `Netloft Row` had two called `north`. Evennia answers with the first, so the second lane
  could not be walked down at all, by clicking a map or by typing, and nothing anywhere said
  so. Found by walking every room on the map one at a time and checking each step arrived
  where the map said it would.
- The lane builder now names the second and later arrivals at a ridge after the lane they
  descend, so adding a fifth lane to an existing ridge cannot quietly break the fourth.
- **The map no longer draws a line it cannot walk.** Flattening a graph onto a grid leaves
  some pairs a long way apart, and the straight line between them crosses four other streets
  and reads as a bridge through the air. The rooms stay on the map, stay clickable, and
  still route over the whole edge list; only the false line goes.
- Rooms are now laid out next door or nowhere, rather than further along the street when the
  next cell is full. Looking further along was what produced the long lines in the first
  place; suppressing them afterwards only left the room at the far end floating.
- A room placed later can still land in the gap between two earlier ones and cut the road
  that joined them. Rather than hold every gap open against that - which costs other rooms
  their place entirely - the few rooms it happens to are moved afterwards, and any that
  cannot be moved keep their line anyway. **No room is drawn with nothing attached to it**:
  a dot alone in a field reads as a mistake in the map, and no correctness elsewhere makes
  up for it.
- Measured on the fifty-five room waterfront: every line one or two cells, no room
  unattached, and all fifty-four other rooms reached by clicking their dot.
- **A quay never told anybody somebody had walked onto it.** `PortRoom` was the one room
  type in the contrib without `NoticesTheWaterline` - a ship's rooms had it, so walking
  ashore raised the panel and drew a map, and walking on to the quay next door left that map
  behind. It now notices, like everything else at a waterline.
- **Moving between two rooms ashore sent nothing at all.** A street and the quay at the end
  of it are both `ashore`, so the refresh found no change of situation and returned having
  said nothing - while the one thing that had changed was the map, which is a picture of
  where the player is standing. Every click is routed from the dot on that map, so the route
  began where they no longer were: ten rooms along, the walk was sending `north` at a pier
  whose only exit is `shore`.
- **`ShoreRoom`**, for the streets between the quays: an ordinary room that reports arrivals
  and counts as land without also having to be tagged. Requiring both a type and a tag is
  how the island tracks came to be built as land, walked as land and resolved as not-land,
  so stepping up off a pier put the whole panel away.
- The example world had a mixin of its own doing half of this by hand, which is how the
  town's quays became the one kind of room it did not cover. Removed; there is one mechanism
  now.
- The test that guarded this read a mixin's own source for the words `at_object_receive` and
  `send_land`. It passed every day the quays were silent, because the quays did not use that
  mixin. Replaced with one that moves somebody and looks at what was sent.
- **Both example coasts had an island called Outer Skerry**, and both builders adopt a room
  that already answers to the name they wanted. Running the two demos - which the readme
  offers as two commands - therefore merged them: one room with five ways out of it, two
  leading to an island three miles off at another set of coordinates. Nothing reported it;
  the build simply said it had made fewer rooms than last time. The scenery coast's sixth
  island is now `Bare Skerry`, and a test holds the two lists apart.
- The readme said the authored world was 76 rooms and 148 exits. It is 79 and 154, and a
  test now counts what the builder makes and compares it with what the readme claims, so the
  number cannot drift again in silence.


- **Her position on the chart shipped with the chart, so she never appeared to move.** A
  sheet is drawn centred on her, and sheets are redrawn about once a minute - so the `own`
  that arrived with one put her in the middle of it and nothing changed until the next.
  Watching a passage was watching a still picture with the speed altering beside it. Her
  offset now rides with her *readings*, every tick, measured against the middle of whatever
  sheet that session is holding: the paper is fixed and the pencil moves, which is how a
  chart has always worked. Remembered per session, because two captains at different scales
  - or one who has dragged his chart - are holding sheets centred on different water.
- **`ChartSheet.harbours` was declared, computed, documented, drawn by the client, and left
  out of `as_message`.** The browser had a layer with nothing to draw and there was no error
  anywhere to find. That list of fields is written by hand on purpose - a payload should say
  exactly what it puts on the wire - and it is the one place the class can go quietly wrong.
- **A status message was sent under the wrong name and printed into the player's window.**
  `announce(session, payload, "status")` takes the *capability* as its third argument and
  reads the name off the payload; a new caller passed `"status"` as the name. No client has a
  listener for it, and an Evennia client prints an unknown message name as text - so every
  tick dumped the whole status payload over the top of the game. Two arguments, one of them
  nearly the other's value.
- **`Dredged.rebuild` marked itself done before trying.** The survey ran while Django was
  still starting, the quay table was not readable, and it cached zero channels for ever -
  with the reason swallowed by the same `except` that was there to make startup survivable.
  Every harbour in the game reported no way in, silently. It now retries until it works and
  logs the failure instead of eating it.
- **Sounding a leg cost sixty times what it should.** Checking whether a course had water on
  it was changed from sampling the terrain to handing the whole leg to
  `check_swept_grounding` - which was right about authored hazards and, with no hull length
  to go on, stepped every two metres: two and a half thousand soundings on a five-kilometre
  leg where forty-one had done, on a function called fourteen times for every chart drawn.
  The suite went from twenty-eight minutes to over an hour. It now asks the two questions the
  two right ways: authored hazards *exactly*, through `check_hazards`, and the ground
  *sampled* at a bounded count.
- **A grounded ship could never come off.** `refloats_on_tide` had existed since grounding
  was written - exported, documented, covered by tests - and nothing in a running game had
  ever called it. A vessel was found sitting in 19.86 m of water, drawing 2 m, reporting
  herself hard on the ground, with a sailing master who had the con and could not move her.
  Her record read `touched, sand, -14.0 m, 0.93 m/s`: the softest grounding the model has,
  and it was permanent.
- She floats off only when the *same* test that grounded her says she is clear. A bare
  sounding under her middle instead made a hull on the edge of a rock float, ground, float
  and ground for ever, announcing both - the seabed there is twenty metres down and the rock
  is an authored hazard standing over it.
- **`terrain_z_at` and the authored hazards are two different answers, and only one of them
  is the one the game acts on.** Every "is there water here" question now asks the same
  `check_swept_grounding` the tick asks. That one disagreement produced three bugs in an
  afternoon: the oscillating refloat above, a navigation network whose marks were laid inside
  the islands they served, and a sailing master who sounded ahead and saw nothing.
- **`ChartSheet.harbours` was declared, computed, documented, drawn by the client - and left
  out of `as_message`.** Fourteen harbours worked out on every chart tick and thrown away,
  with no error anywhere to find. That dict is written by hand on purpose, and it is the one
  place this class can go quietly wrong; `tests/test_client_state.py` now checks the
  dataclass and the wire agree.
- The harbour layer cost 656 ms a sheet, re-deriving which mark serves each quay forty
  soundings at a time for all fourteen on every redraw. Which mark serves a quay depends on
  the quay, the marks and her draught and on nothing about where she is floating, so it is
  remembered; the departure mark is found once per sheet rather than fourteen times. Warm
  cost is now 32 ms.
- **The whole browser interface was dead, and had been for three commits.** Wiring the land
  map in, a second handler was written into `Evennia.emitter.on`'s argument list as though it
  were an object literal - `[LAND]: function (...)`. The browser said `SyntaxError: missing )
  after argument list`, refused the entire file, and `MaritimeTransport` never existed, so
  the panel never started at all in any mode.
- And then the chart pane went blank, because `orderPassage` was pasted in front of "the
  first `return {` in the file" and that `return {` belonged to `offsetOf`. The function was
  scoped inside another one, every render threw a `ReferenceError` at the call site, and the
  instrument strip kept working because it is a separate call. `node --check` passed both
  times: a parser checks a file is *a* program, not that it is the one you meant.
- `Vessel.maritime_position` now accepts None, for a hull that is not afloat. It always
  *read* None - `scripts.py` has said since the beginning that a vessel without a position is
  on the stocks - but there was no way to set it, because until now nothing ever took a ship
  back off the water. Written straight through rather than deferred, because the getter falls
  back to the saved value and a deferred None would read back as still lying where she was.
- `make for` no longer sends her round a mark she is lying on. A ship moored to the very mark
  her course started from was told to make for it, which sent her away and then back - a lap
  of a buoy she was already at.
- **The marks were drifting with the tide.** `offing_from` walks seaward until there is
  twelve metres under it, and how deep the water is depends on the tide - so the network
  rebuilt itself differently every few hours. Careenage Roads came out at two positions a
  quarter of a kilometre apart within an hour. A buoy is moored; marks are now sited against
  chart datum, which is what a real chart sounds against and for exactly this reason. A
  course plotted at high water is otherwise a course to somewhere else at low.
- **The sailing master sounded ahead at one state of tide and grounded at another.** He
  looked ninety seconds ahead with one metre of margin against a range of two, and put her
  on a bank in 3.78 m of water drawing 2.00, recorded clearance -0.15 m. He carries a
  further two metres now: "could a ship get through here" and "would a prudent mate take her
  through here" are different questions, and he is asked the second.
- `tests/test_client_scripts.py` runs `node --check` over every client script when node
  happens to be installed, which is not the same as requiring it: nothing fails without node,
  and the skip says exactly what is going unchecked. A companion test feeds it the broken
  file to prove the check can fail.


- **The whole browser interface was dead, and had been for three commits.** Wiring the land
  map in, a second handler was written into `Evennia.emitter.on`'s argument list as though
  it were an object literal - `[LAND]: function (...)`. Brackets balanced, braces balanced,
  every name was declared once, and every existing check on these files passed. The browser
  said `SyntaxError: missing ) after argument list`, refused the entire file, and
  `MaritimeTransport` never existed - so the panel did not lose the land map, it never
  started at all, in any mode.
- `tests/test_client_scripts.py` now runs `node --check` over every client script when node
  happens to be installed, which is not the same as requiring it: nothing fails without
  node, and the skip says exactly what is going unchecked. A companion test feeds it the
  broken file to prove the check can fail. Reading a file as text cannot catch a grammar
  error; only a parser can, and the position that this contrib needs no second toolchain is
  kept by using one when it is there rather than depending on it.

### Feat

- **A shipyard: seven hulls, built at a quay.** `maritime build <rig> <name>` puts a yawl,
  lugger, cutter, schooner, brig, barque or frigate alongside in a free berth with her
  gangway down. Every figure is derived rather than chosen - tonnage by Builder's Old
  Measurement, displacement by block coefficient, hold from the tonnage - and two are
  checked against vessels that existed: the frigate within 1% of a *Leda* class fifth rate,
  the brig 5% over a *Cruizer* class brig-sloop in the direction the rule is known to err.
- Three polar curves rather than seven. A square rig cannot lie inside six points and is
  best on the quarter, a fore-and-aft rig is the reverse, and a lug sits between and runs
  better than either. Seven curves would have been seven sets of invented numbers dressed
  as research.
- **Ships can be laid up *in ordinary*, which is the harbour's housekeeping.**
  `maritime lay up` and `maritime summon` take a ship off the water and bring her back at
  any dock. She keeps her cargo, her crew, her damage and her compartments and gives up her
  berth - so nothing ticks her, nothing raises her and nothing runs into her. Not a new
  mode: a vessel with no position was never simulated, and this is that state named.
- `ordinary.lay_up_fleet_of` for a game to call from its own `at_post_unpuppet`, because
  Evennia fires no logout hook a contrib can see. Silent about the ships it could not lay
  up - at sea, under orders, somebody still aboard - because the caller is a logout and
  there is nobody to tell.
- `Vessel.maritime_position` now takes None, for a hull that is not afloat. It always
  *read* None - `scripts.py` has said since the beginning that a vessel without a position
  is on the stocks - but there was no way to set it, because until now nothing ever took a
  ship back off the water. Written straight through to the database rather than deferred,
  because the getter falls back to the saved value and a deferred None would read back as
  still lying where she was.
- Ship names are unique, checked against every hull in the game whether laid up or not. Two
  ships called *Swift* is a harbour where summoning one is a coin toss.
- **Four runtime switches, so the interface can be changed without editing Python.**
  `maritime ui on|off|hybrid` says when the maritime panel is shown, for the whole server
  and not per player; `maritime uncharted on|off` draws the sea as it truly is for building
  and testing; `maritime player gui on|off` decides whether accounts may choose for
  themselves; `maritime gui` is that choice. All are locked to `perm(Admin)`, all
  persist across a reload in `ServerConfig`, and all four take effect on every screen at
  once rather than at the next tick.
- `maritime gui` is *hidden* from players until a developer lends the choice out, rather
  than visible and refused. A command a player can see in `help` and cannot use is a fair
  question with no good answer.
- **`uncharted` has one seam and no second code path.** Every way the sea is hidden runs
  through the chart being read - off the paper is `covers` saying no, and wrong is the
  survey error - so the switch replaces the paper with the ground and reveals everything
  without drawing the sea any other way. A reveal that drew it by another route would stop
  being a view of what players see.
- **A whole coast ashore, as the worked example of putting 2D Evennia land in a maritime
  world.** `example/aetos_world` builds Careenage - 55 hand-authored rooms at the head of
  the harbour - and four rooms on each of the six islands, with piers, eighteen people
  behind counters and 106 things between them. One builder command, safe to run twice.
- The seam is one room type. Nine rooms are `PortRoom`s holding a position and a berth;
  the other eighty are ordinary rooms that have never heard of the sea, and nothing else had
  to be taught about anything.
- **Piers, because the ground demanded them.** This shore shelves so gently that six metres
  of water is most of a kilometre out, so a quay on the sand would have nothing alongside
  it. Each pier's length is measured against the soundings rather than chosen, and a berth
  advertises the water actually under it less half a metre - so it cannot promise a depth
  it lacks however the world is later rebuilt.
- **Stepping ashore where nobody has been is recorded.** An island pier notices the first
  person off it and credits them, once and permanently, through the discovery ledger. A
  crate landed on the same pier claims nothing.
- **A map ashore, opt-in.** `MARITIME_ASHORE_PANEL` keeps the panel up on land and shows
  rooms and the ways between them instead of a chart, with click-to-move: a breadth-first
  route over the drawn edges, sent as ordinary movement commands one at a time, so a locked
  gate stops the walk exactly where it would stop the player.
- **Off by default, and that is the important half.** The contrib's own rule is that the
  failure a player notices is a maritime interface appearing in a tavern, so stepping off a
  gangway hands the screen back to the host game unless a game asks otherwise. The world
  tags its own rooms as coastal land - a fact about the world - and whether an interface
  does anything about it is the game's decision.
- Four markers and no more, because ashore there are three questions worth answering in
  colour: where am I, where is my ship, and where do I buy things.

- **A real coast now ships with the contrib.** Point `MARITIME_MAP_PROVIDER` at
  `baked_world.AetosCoast` and a game is sailing a generated coast — harbour, moles, bar,
  dredged approach, tidal creek, an isolated pinnacle and six named islands — with nothing
  installed, no seed and nothing to build. About three megabytes of soundings in five
  sheets, from a kilometre-spaced coastal one down to a ten-metre inshore one over the
  harbour and the island chain.
- It works because the seabed is deterministic and therefore worth writing down once. The
  shipped bundle matches the world it came from to 0.01 m inshore and 0.11 m at coastal
  scale, against a survey error the chart itself carries of metres.
- **Soundings are not a world**, which is the mistake the format exists to avoid. Depth and
  a coastline come from the grid; the bottom, the marked rocks, the named islands and the
  latitude come from a manifest in plain text beside it — so the interesting half stays
  readable and reviewable, and only the bulk is binary.
- `bake.bundle` writes one from any provider, asking it the same questions maritime asks, so
  a game can ship its own world the same way.
- Two limits, stated rather than hidden: past the finest sheet the ground is interpolated
  rather than detailed, and past the bundle's edge there is open ocean and an unsurveyed
  chart. The survey stops where the surveyor stopped.

- **The seabed is remembered, and a chart got twenty times cheaper.** Measured first: of the
  902 ms a ten-kilometre sheet took, 825 was asking the world for ground and 45 was every
  other thing a chart does put together — contours, relief and graticule between them.
  Sounding the *identical* patch twice cost 811 ms and then 816, so nothing was being kept.
- The seabed does not change, does not depend on which chart is read, and is the same for
  every player, so there is nothing to invalidate. A cold sheet still costs about 1.3 s; the
  next one costs **60 ms**, and a second ship a few hundred metres away costs 86.
- **Hits need a lattice.** A sheet used to be sounded around its own ship, so two vessels a
  hundred metres apart sampled points that were near each other and equal nowhere. The
  sheet's corner now lands on a lattice of the world — a shift of under one cell, invisible
  at the scale a cell is drawn at, and the difference between two hundred captains in a
  harbour paying two hundred times and paying once.
- Only the corner is snapped. Quantising the *cell* was the first attempt and was wrong: the
  grid then covered more ground than the span it was drawn against, and every contour point
  came out misplaced by up to a tenth of the sheet.
- What is not cached is the chart's own error, which is 1.4 µs against 82 and differs from
  chart to chart. The ground is shared; the lie told about it is not.
- Bounded, and it can say whether it is working. A cache that never hits is
  indistinguishable from no cache except in a profile.

- **Who found it first, and who first set foot on it.** A world nobody has been to is worth
  more than a world everybody has, and the difference is entirely bookkeeping. `discovery`
  keeps a permanent, global record: a place carries the name of the ship that raised it and
  of whoever first got ashore, and anybody who later looks it up is told.
- Two claims, not one, because they are different achievements and frequently different
  people — sighting a headland through a glass at fifteen miles is not getting a boat
  through the surf. A sighting credits the ship's company with the captain named first; a
  landing credits one person, because a boat's crew arrive one at a time.
- **Sighted, not merely near.** Whether a place can be seen is `geographic_range` — height
  of eye against the landmark's own height — so a headland is raised from far further off
  than a sandbank, using the same arithmetic the lookout reports already use. A discovery
  happens exactly when somebody could have called it.
- **From her true position, never her reckoning.** Discovery is a fact about the world and
  not about the chart, so a ship that is hopelessly lost still finds the island she is
  looking at. Where it gets *drawn* is the navigator's problem, and a good one to have.
- A claim is made once and never again — not overwritten, not re-dated, not re-attributed,
  however many ships raise the same headland on the same tick. The guard is in the ledger
  itself rather than only in the caller, because two ships can both be told a place is
  unclaimed before either has written.
- Players only. An achievement shared with eleven hired hands who exist as a number in the
  manifest is not one.
- Nothing at all for a world that names nothing. `landmarks_near` answers empty by default,
  and a featureless shelf has nothing to discover — which is correct rather than a gap. `bathymetry` has always said depth is the surface less the terrain,
  and that moving the surface changes every depth in the world without touching any ground
  — but the only surface the contrib shipped was `FlatTideProvider`, which does not move.
  Every feature authored to teach a tide had nothing to teach with. `tides.HarmonicTide`
  is the tide those features were waiting for.
- **Springs and neaps are not scripted.** They fall out of the lunar and solar waves beating
  against each other, which is what they are. Measured on the demonstration coast: the daily
  range swings between 1.65 m and 4.31 m, biggest and smallest seven days apart — and half
  the beat period is 7.38 days. Nothing in the code checks a calendar or a phase of the moon.
- Configured the way a tide table states one — `HarmonicTide.semidiurnal(spring_range_m=4.0,
  neap_range_m=1.5)` — because a designer knows their harbour's ranges and nobody knows
  their harbour's M2 amplitude. The inversion is exact, so a game gets the two numbers it
  asked for rather than an approximation of them. `mixed` adds the diurnal inequality, where
  the two daily high waters differ and "wait for high water" stops being one instruction.
- **A tide table, searched rather than stored.** `next_high_water`, `next_low_water` and
  `table` hunt the same function the water is drawn from, so a prediction cannot disagree
  with the sea — which is exactly how it goes wrong in a game that caches them.
- Optionally the tidal wave travels, so high water reaches one end of a coast before the
  other. Exact, not approximated: running the tide later up-coast is the same arithmetic as
  running the clock earlier here.
- **`MARITIME_TIDE_PROVIDER`, so a tide can be installed rather than inherited.** Before
  this the only way to have moving water was to write a map provider subclass whose sole
  purpose was to pass a tide to `super().__init__`, so a game wanting its own terrain and a
  stock tide had to write a class to get one. Unset, nothing changes and the sea stays
  still.
- **`RegionalWater`, so a game can have a pond as well as a sea.** A pond is not a bay: it
  sits at whatever height its valley holds it at and does not care what the tide is doing,
  and the only reason that is hard is that a world has one datum and the pond is nowhere
  near it. `WorldPosition` has carried a `region` since the beginning and nothing was using
  it for water; this is what it is for. Each inland water is a full tide provider rather
  than a number, so a lake can have a seiche and a lagoon behind a sill can have a smaller
  tide than the sea outside it. The depth arithmetic is untouched — a pond five metres deep
  comes out five metres deep by the same subtraction that gives a harbour its nine.
- What it bought on the demonstration coast: the harbour bar carries 4.97 m at high water
  and 1.48 m at low, so it is a gate a laden hull waits for. The drying rock dries.
- **The chart is ruled with meridians and parallels.** A navigator reads a position off
  them, and they are also the one honest way a flat sheet can show a round world: the
  meridians converge, visibly, and converge further the wider the view. No projection was
  bent and nothing was faked — the lines are contours of the latitude and longitude fields,
  found with the same marching squares that draws the coastline, so they curve because the
  world does. Costs 2–4 ms of a sheet that already takes hundreds.
- A world with no geography is ruled with nothing. `geographic_at` answers None by default,
  so a seabed defined by an arithmetic ramp draws no graticule rather than inventing a
  latitude — the same shape of promise as the optional relief.
- **An island, a drying rock and a sunken one are now three things rather than one.**
  `dries` meant "above chart datum", so a twelve-metre island reached the client announcing
  that it dried twelve metres. The tide is measured over a full tidal day and a danger is
  classified by what the water actually does to it: `ashore` where the sea never covers it,
  `dries` where it is bare at low water and covered at high, and neither where it never
  shows. On a motionless sea nothing dries, which is correct — nothing moves.
- **Shaded relief on the chart, for a game that wants it.** `numpy`, `scipy` and `Pillow`
  are optional — install them and the chart draws the shape of the bottom, lit, beneath its
  contours; leave them out and it is the line drawing it has always been. Maritime itself
  still has no dependencies, and that is the point: the trade is offered to the game rather
  than taken on its behalf.
- Shaded from the **charted** grid and never the real seabed, so a poor chart's relief is
  as wrong as its soundings and in the same places. Anything else would hand a graphical
  player knowledge the fiction denies a terminal one.
- Costs about 65 ms against the 983 the sounding already took, because the grid it shades
  was computed to draw the contours and no new depth is asked for. Adds some 20 KB to a
  payload that goes out once a minute. Unsurveyed water comes out transparent, so the paper
  still runs out where the survey did.

### Fix

- **Four things ashore were written and never wired**, which is the same failure four times:
  something defined, never called, passing every test about its definition while the world
  behaved as though it did not exist.
  - `browse` and `buy` were in no cmdset, so nothing could reach them and the hundred and
    six goods were unbuyable.
  - `refresh_ashore` was never called, so the land map would have drawn the first room a
    player entered and gone on drawing it while they walked away - click-to-move moving
    them correctly into a map of nowhere they were.
  - `STARTING_ROOM` and `trade_at` were read by nothing but their own tests, so new players
    started wherever the game happened to put them and every island's authored trade was
    decoration.
- All four are now connected, and the tests assert the *call sites* rather than the
  definitions, because it was the call sites that were missing.
- Land rooms carry their own cmdset, so shops work where there is something to buy and
  nowhere else - a `buy` command on the character answers "there is nobody selling anything
  here" in every forest on the map, which is worse than no command at all.
- `sell <tons> <cargo>` lands cargo at an island that wants it and pays for it. It read the
  discharge result as a list of parcels, which reported "nothing came off" for a discharge
  that had worked - it is a `TransferResult` carrying the one parcel that crossed the rail.
- **Dragging the chart was a lie.** A sheet was always drawn around the ship, so sliding it
  moved one fixed square about inside its window: the corner arrived in the middle and there
  was nothing behind it, because nothing outside that square had ever been drawn. Sliding a
  picture is not the same as looking somewhere else, and the request — which carried only a
  reach — had no way of saying which was meant. It now carries a place as well, the sheet is
  drawn there, and the payload says where the ship lies on it so she is not glued to the
  middle of a view she is no longer in.
- Looking away from her is not looking at something she cannot see. The sheet still comes
  from the charts she carries and still stops where their coverage does, so dragging out past
  the survey gives hatching and the word UNSURVEYED.
- **The contrib's own tests assumed a motionless sea**, so installing its new tide broke
  four of them. Three grounding tests asserted a vessel's elevation was zero, which is the
  datum and not the surface; a fourth asserted eighteen metres of clearance under twenty
  metres of water, true only at the top of the hour on a sea that never moves. They were
  right about the behaviour and wrong about the number, and they passed for as long as
  there was no tide to tell them apart.
- Those tests already pinned the seabed to get a known sea. They now pin the tide for the
  same reason. Worth stating plainly: **CI would never have caught this**, because CI runs
  with no tide configured — only a host game that installs one sees it, which is precisely
  the game that would report it as a bug in the contrib.

- **The coastline was being shredded by its own survey error.** A vertical error becomes a
  horizontal one scaled by the slope, and on a coast rising a metre in a kilometre a chart
  of quality 0.85 is out by under 2 m of depth and therefore **±1,745 m of shoreline** —
  against an error that varied over 250 m patches. When the displacement is seven times the
  wavelength it varies over, the drawn coast folds back through itself: it stops being a
  line in the wrong place and becomes a scribble. Measured at a ten-kilometre reach against
  about 24 km of real shore, the old 250 m patch drew 34.6 km in four broken runs; at two
  kilometres it draws 24.5 km in one. The patch is 2 km now.
- Runs too short to be anything a survey found are left off, which is ordinary cartography
  — a cartographer calls it the minimum mappable unit. What arrived below that size was not
  islets but survey error crossing the datum, drawn as a scatter of specks that moved
  whenever the chart was redrawn at another scale. Anything real and smaller belongs to the
  marks layer, where the isolated dangers already live for the same reason.
- The coastline is drawn as a curve through its points rather than as straight runs between
  them. It passes through every point exactly and invents no shoreline; it only stops
  asserting that the coast turns a hard corner wherever somebody happened to sound.

### Fix

- **The charted seabed was a staircase.** Survey error was one value per 250 m patch, so
  the paper stepped at every patch boundary: on a shelf truly falling a fifth of a metre
  every fifty, a chart of quality 0.7 showed **4.55 m cliffs** a quarter of a kilometre
  apart. A lead cast either side of an invisible line disagreed by more than the depth of
  water changing under it. The error is interpolated between patches now, smoothstepped so
  the slope matches at the joins as well as the value — a merely linear blend leaves a
  crease along every boundary, and a crease in a seabed is a ridge nobody put there. The
  intent the docstring always stated, that a survey is wrong about *areas*, is unchanged;
  what has gone is the wall between one area and the next.
- The test guarding that behaviour was asserting the bug. It asked for two readings a
  metre apart to be *identical*, which is the implementation rather than the property —
  the sentence above it said only that the error should not vary between one metre and
  the next. It checks that now, and a second test walks a line and fails on any step.

### Changed

- **A sheet only sounds the cells a contour passes through**, where that can be done
  safely. Most of a chart has no contour in it — counted on generated ground, about one
  cell in twenty carries any traced level — and asking the world for a depth is very
  nearly the whole price of a sheet. A seed pass finds the contours; the rest is filled
  from its own corners, which can neither invent nor hide a crossing because bilinear
  interpolation stays between the values it is given.
- **It turns itself off where it would be wrong**, and that is most of the story. A seed
  cell wider than the finest structure in the field steps over contours, and no
  refinement can refine what it never saw. Measured worst departure of the drawn contour
  from sounding every point: 421 m cells never seed, 211 m cells wandered 388 m, 84 m
  cells 29 m, 42 m cells 18 m. The rule is derived from the sheet rather than configured,
  so a wide zoom is untouched and a close one is about two and a half times cheaper —
  which is the opposite of convenient, since the wide sheets are the expensive ones, and
  is kept because the chart a pilot threads a harbour on is worth halving.
- `GRID` stays at 96, after nearly being raised to 192 on a misreading. **A chart is not
  the seabed, it is the seabed plus a survey error**, and sampling more finely than the
  error varies resolves the error rather than the shore. Coastline traced on a
  forty-kilometre sheet against about 55 km of real coast: a perfect chart gives 54.2 km
  at 96 and 55.7 at 192; a 0.9 chart gives 57.1 and 67.9; a 0.6 chart gives 107.2 and
  171.1. The extra detail at 192 is very largely survey noise drawn as coastline.

### Feat

- **Put the rocks on the chart.** `docs/client.md` has said since the interface was
  specified that the charted layer carries land, soundings, marks *and hazards*. The first
  three arrived and the fourth did not, while grounding went on asking providers for
  hazards the whole time — so a rock a game had authored would hole a hull that sailed over
  it while the chart drew open water above it. That is worse than a rock drawn nowhere,
  because the captain has looked at the paper and is entitled to believe it.
  `charted_dangers(position, reach)` joins `hazards_touching` on the base provider, on the
  same additive terms: a game with no authored hazards answers with nothing and gets the
  chart it had. `TiledMapProvider` reads the tiles the sheet covers and no others, because
  a chart is a few kilometres and a world may be ten thousand tiles.
- Draw them as a chart draws them — a starred symbol with the least depth over it beside
  it, and no figure at all on one that dries, because there is no water to quote. Not as
  buoyage: a buoy is a thing somebody moored and can drag, a rock is a thing somebody found
  and cannot, and a captain looking for a light on a reef is a captain in trouble. They
  cannot come from the soundings either, and that is the point of them — a grid four
  hundred metres across steps over a rock a hundred wide, and whether it steps over *this*
  one depends on where the grid falls, so the danger would appear and vanish as she sailed.
- Give the interface a full-window layout, as an opt-in nobody else pays for. Every rule
  in it is scoped to `:root:has(#maritime-root.maritime-on)`, so a game that never boards
  a vessel sees the webclient it has always had, and a player who steps aboard gets a
  bridge. Additive by construction rather than by discipline: there is no state in which
  the host's own layout is edited and has to be put back.
- **Nothing scrolls the page.** Interior boxes scroll; the page never does. A captain
  looking for the anchor should not have to go and find it, and a bridge you have to
  scroll is a bridge with instruments behind you.
- Lay the deck out in three columns and give the orders a board rather than a row, so the
  wheel, the canvas and everything that is not steering each have a place. A hand looking
  for "hard a-port" in a hurry wants it beside "port", not beside "anchor".
- Say what a reading is *not*. Anything the simulation does not publish - the time and the
  state of the tide, a rudder track, flooding - is drawn in its place and plainly marked
  `not wired`, with bars drawn empty rather than full. A placeholder that looks like data
  is one somebody eventually believes, and a captain acting on an invented ETA is a worse
  outcome than one told the ETA does not exist yet. An empty bar reads as "no reading"; a
  full one would read as "in perfect order", which is a claim.
- Lead her description with her class when the game published one, because "cutter" tells
  a captain more at a glance than "18 metres" does, and give a host game an emblem slot on
  the same terms as every other picture here - an unset variable draws nothing and takes no
  width.

### Fix

- **The chart was contoured thirty times for every one that was sent.** `broadcast_status`
  drew a sheet on every tick and *then* decided whether to send it, so with a two-second
  driver and a revision that turns every sixty seconds, twenty-nine drawings in thirty were
  built and thrown away. The comment above that code said it stopped exactly this from
  happening, which is a fair part of why it lasted. The revision is arithmetic on the clock
  and needs no sheet to compute, so the gate moved ahead of the drawing — and what goes out
  is unchanged, because the first tick of a new revision draws and sends exactly the sheet
  it always did. Invisible against a hand-written seabed at eighteen milliseconds a sheet;
  against a game supplying real bathymetry, where a sheet is the better part of a second, it
  is the difference between 37.7 % of a core per crewed vessel and 1.3 %. Which chart she is
  reading is part of the stamp too, so one bought or unrolled halfway through a minute still
  appears at once rather than waiting for the clock.
- **Draw the chart in screen pixels.** It was drawn in a square of a thousand user units
  scaled to fit, so every stroke and label was specified in units that were some unknown
  fraction of a pixel; widening that square to fill a wide pane made the fraction smaller
  still, and a 1.5-unit range ring came out at about six tenths of a pixel - not a faint
  ring but one the browser can barely draw. Fonts went the same way. One user unit is one
  pixel now, at any zoom, in any shaped box, and the aspect arithmetic is gone with it.
- Stop the chart being letterboxed. A square `viewBox` under a `max-height` left the sheet
  241 pixels tall in a pane with room for 560, and `.maritime-pane > .maritime-card` was
  capping the chart card because it carries both classes.
- Ask the server for the sea the box actually shows, not the sea the captain's scale
  covers. He picks how far the rings reach; the box then shows whatever fits around them,
  and a sheet drawn only to his scale left that water blank - an unsurveyed-looking hole
  that was really the edge of what we thought to ask for.
- Wait for the box to be measured before asking at all. The first draw happens before any
  layout, so a sheet asked for then was the wrong width: it arrived, drew, and was replaced
  moments later by the right one, which is the flash on every page load. There is only ever
  one now, and a `ResizeObserver` watches the box rather than the window - a pane changes
  shape when somebody drags a splitter or opens a panel, and neither is a window resize.
- Replace the compass drawn at a fixed point in the `viewBox`, which stopped being the
  top-left corner the moment the box was not square, with a rose that positions itself and
  carries its own cardinals.
- **The panel tabs had been dead since the interface shipped.** Two functions in
  `maritime-panels.js` were both called `has`; both took a state and a string; the later
  declaration silently replaced the earlier one, so `offered()` spent its life asking
  whether `"company"` was in the list of *controls*, which it never is. Every tab vanished.
  The bodies went on rendering from the stored preference, which is exactly why an empty
  tab strip did not look like a bug. Renamed to `hasControl`.
- Print a chart's worth of soundings rather than a grid's worth. `soundings(every=6)` was a
  count only while the grid never changed size; raising it took the printed scatter from 64
  figures to 256, which arrives as an unreadable block of digits sitting over the ship. It
  is a target count now - about eight each way - worked out from the grid, so the scatter
  stays the same size however finely the seabed was sampled underneath it.
- Sample the seabed twice as finely. At 48 across, a chart a thousand pixels wide showing
  forty kilometres put 850 metres between samples - about twenty-two pixels - and a
  coastline traced through points that far apart is a row of long straight walls. Timed on
  the same seabed at the same span: 48 costs 14 ms, 96 costs 35 ms, 128 costs 61 ms.

### Chore

- Test the browser scripts by reading them, because nothing else here can. This repository
  has no JavaScript test runner and should not gain one - a Python contrib that needs node
  installed to go green is a contrib with a second toolchain - but that left the interface
  untested and one bug has already used the gap. A function redeclared at module scope is
  always a bug here, whatever it is called, and now it fails a test instead of a player.

### Feat

- Publish what class of hull she is, so a game with more than one sort of ship can
  draw a brig differently from a cutter. It is her `template_key` - the identifier
  of the template she was built from, which the host game chose - carried to the
  drawing as `data-template` for a stylesheet to scope the same variables per class.
  Relayed and never interpreted: this contrib does not know what a brig is, and a
  taxonomy of ships would be the host's to own and wrong the moment somebody invented
  a hull nobody here had thought of. It is also the only honest way an interface could
  know, a rig here being a polar curve rather than a name. Her own hull only - a
  contact's class is never published, because what may be told about another ship is
  what the lookout has made out.
- Document `template_key` in the readme, which nothing wrote and nothing explained.
  Hulls are built by the game rather than here, so the field a hull records her class
  in was discoverable only by reading source, and every host would have found it the
  same slow way.

- Provide a fitting for optional artwork without shipping any. A host game points
  `--maritime-profile-<plan>` at pictures of its own and changes nothing else, and
  the sail plan she is under is drawn rather than only named. Absence needs no guard:
  an unset variable falls back to `none`, which draws nothing and occupies no height,
  so a game supplying three plans out of six gets pictures for three and unchanged
  text for the rest, and a game supplying none gets exactly the interface it had. The
  drawing sits above the row naming the plan and never replaces it, because a picture
  is not a reading and the words have to survive a player with no artwork, a slow
  connection or a screen reader.
- Composite artwork with `screen` by default, which is doing real work rather than
  styling: art of this kind generates far more reliably on a black ground than with a
  transparent one, and screen maps black exactly to the backdrop - so an ordinary
  opaque PNG behaves as though it had been cut out, with no alpha channel and no
  tooling in between. A host whose artwork is already cut out sets
  `--maritime-artwork-blend: normal`.

- Draw a chart, contoured out of the ship's own paper rather than authored anywhere.
  A coastline is where the ground crosses datum, so a game that authored a shoal has
  authored the shape of it; marching squares over a sampled grid costs about six
  milliseconds and needs no libraries. It contours the *chart* rather than the sea,
  which buys three things at once: the coast is wrong in the same places every
  voyage, water nobody surveyed comes back as a hole in the paper rather than as
  open sea, and a better chart is visibly better. The true seabed is never fetched
  and so cannot leak.
- Plot her from where she *reckons* she is. A ship whose dead reckoning has drifted
  draws the coast in the wrong place, and the cure is to take a fix - which is the
  whole of navigation, arriving for nothing, because the pipeline never asks for the
  truth.
- Keep the charted and the sighted apart. Land, soundings and buoyage stay on the
  paper in fog, at night and when nobody is looking; other ships exist only while the
  lookout has them. A contact that outlived the sighting would be a radar repeater.
- Mark buoyage by shape as well as colour - a can to port, a cone to starboard, a
  diamond for a danger - and carry each mark's meaning beside its kind. Somebody who
  cannot tell red from green still has to pass a buoy on the correct side.
- Report instruments a captain reads: heading beside course made good, speed through
  the water beside speed over the ground, wind, current, the charted depth, what she
  has set. Each appears only when it is true here, so a pond reports no tide and a
  ship off her chart reports no sounding.
- Offer controls, each of them a way of typing a command that already worked. A press
  runs that command through the same handler, against the same locks, with the same
  authority check a captain shouting it would pass, and nothing a browser sends
  reaches a command line. A passenger is offered no helm - not a disabled one - and
  the board is built per authority, so a captain and a passenger on one deck are sent
  different boards from the same tick.
- Publish morale as a band and never as a number, because the simulation bands it on
  purpose: a captain is told his people are wavering, which he can act on, rather
  than handed a percentage to manage.

### Fix

- A client that understood only part of the protocol was sent all of it, and printed
  several hundred chart coordinates across the player's message window. Capabilities
  were declared and never checked; each payload is now gated on the one it needs.
- A chart drawn to one scale and shown at another put an entire coastline into the
  middle fifth of the panel. The client says how much sea it is showing and the
  server draws to that.
- An action name that was not a name crashed the handler, because `dict.get` raises
  on an unhashable key rather than politely missing.
- Contouring a cell with an unsounded corner. The line now stops where the survey
  does rather than being guessed across it, which is what leaves the hole in the
  paper.

- Publish maritime state to clients that ask for it, as an optional protocol. The
  contrib now says which interface a situation calls for - ashore, aboard as a
  passenger, aboard in command, or in the water - and says it again the moment that
  changes. A browser may draw it. Nothing is required to; the state is not tied to
  any one way of showing it, so a scriptable terminal client gets the same
  messages.
- Notice the crossing without asking a host game to help. Both sides of every
  boundary are rooms this contrib owns - a gangway runs from a quay to a ship's
  compartment, going over the side runs from a compartment to open water - so the
  moment somebody walks aboard is noticed from our own typeclasses. There is no
  integration step for a game to forget and no character typeclass to override.
- Keep capability on the session rather than the character. One player may be
  connected from a browser and a terminal at once, looking at the same ship: the
  character is not graphical, the connection is. A session that never announced
  itself is sent nothing at all, because an unknown message is something a terminal
  is entitled to print at the player.
- Say it only when it changes. Walking from a deck to a hold is two rooms and one
  situation, and reports nothing.
- Version every message, and accept a version from the future rather than refusing
  it. A client one step ahead of its server should lose the part it asked for
  differently, not the whole interface.

- Add holding your fire. A captain may run the guns out and leave them, and the
  battery speaks by itself the moment something bears - which our simulation gets
  almost for nothing, because "hold your fire until she crosses the bow" is an
  order that means something on a clock rather than a turn.
- Make it two orders with different risks, which is the whole decision. Holding on
  a *named* ship is safe and requires her to be identified first, so it does
  nothing in fog, in the dark, or at the edge of vision - exactly where a captain
  most wants his guns held ready. Holding on an *arc* fires at whatever crosses it
  and works in any weather. Nothing here knows what a friend is, and nothing needs
  to: an order to fire on anything crossing to starboard is already an order that
  will take your own consort, and the captain who gave it said so.
- Charge for the snatched shot. Opportunity fire is laid on a bearing rather than
  on a considered solution, so it tells less often - and worse again in a
  frightened crew, `hesitation` degrading rather than gating, as it does at the
  serving and in the rigging.
- Let the order stand after it is used. A captain watching a channel wants every
  ship that comes through it, and making him say so again after each would leave
  the order useless for the one thing it is for. `secure the guns` ends it.

- Make orders take time. An order at sea is not a state change: somebody has to go
  aloft, lay out along a yard and cast off or make up a gasket, and there are only
  so many of them. Until that work is done she carries what she carried - so a
  captain who leaves shortening down until he can see the squall is still under a
  full press when it arrives, and that is a decision he made rather than a die he
  rolled. A crack frigate's crew shorten to fighting sail in a bit over two minutes;
  a pressed crew take better than six, and the same crew badly frightened take
  longer again.
- Read `hesitation` for the second time. Morale computed it, the gun deck spends it
  on serving guns, and this spends it on the rigging - and higher, because a gun
  crew work behind bulwarks and a topman does not. Casualties now cost her twice
  over: fewer hands to do the work, and the ones left are frightened.
- Charge for changing your mind. Work half done is work partly wasted, so a captain
  who orders three things in a minute gets a slower answer than one who orders the
  right thing once.
- Send the watch through the same seam. A mate who could re-rig the ship instantly
  while her captain waited four minutes for the same change would make ordering sail
  yourself strictly worse than saying nothing.
- Tell the deck how long it will be, in the words a bosun would use rather than a
  count of seconds. An order whose end a captain cannot see is not a decision - the
  decision is whether he has time for it, and he can only make that if he knows
  roughly what it costs. `sail` on its own also reports what the hands are still at,
  so nobody re-orders a change already under way and makes it slower.

- Add blanketing: a ship steals the wind of anyone in her lee. A cone reaches
  downwind of every hull, its length scaled by the canvas she has aloft, and anyone
  inside it loses drive in proportion to how deep in it they are - tapering both
  across the cone and along it, because the edge of a blanket is a gradient rather
  than a wall. This is the first thing in the contrib that makes a ship's position
  relative to *other ships* matter rather than only her position relative to the
  wind, which is what the weather gage was actually worth.
- Make the blanket the fourth side of the fighting-sail trade, and the one a captain
  is least likely to have thought about: shortening down shortens your shadow too,
  so clearing for action gives up an advantage you may not have known you had.
- Take the worst single shadow rather than the sum of them. Lying behind two ships
  is not twice as calm as lying behind one - the air is already spoiled, and adding
  shadows would let a squadron becalm a ship entirely. Nobody is becalmed outright
  in any case: the air is disturbed rather than absent, or the weather gage would be
  an execution rather than an advantage.
- Say who is doing it. `shadow()` returns the ship alongside the number and the mate
  names her - "Weatherly has the wind of us, sir" going in, "Our wind again, sir"
  coming out - once each, keyed by *who* rather than by whether, so passing out of
  one ship's lee straight into another's is reported as the new ship instead of
  passing in silence. A ship that silently lost a third of her speed would just send
  her captain hunting for damage that is not there; the answer to "why are we
  slowing" has to name a ship, because the remedy is to steer away from her. The tick
  asks once and uses the answer twice rather than querying the register again to
  narrate what it has just worked out.
- Size the broad-phase search on the longest hull afloat rather than on her own,
  because the shadow a ship is looking for belongs to whoever is casting it. A
  cutter searching one cutter's length downwind would never find the three-decker
  two cables to windward taking her wind, which is the case the gage is most worth
  having.

- Add fighting sail, and make every part of it derived rather than granted. The
  other plans answer how hard it is blowing; this one answers what is about to
  happen. She carries less than working sail and more than reefed - enough to
  manoeuvre, because a ship that cannot manoeuvre is a target - and what that buys
  falls out of the canvas: less aloft for chain to cut, and fewer hands needed to
  work it, so they are back at the guns. Slower, harder to dismast, and firing
  faster, and a captain has to judge whether he still wants the speed.
- Keep her off the sailing master's ladder. Fighting sail is rated to stand more
  wind than working sail, so a mate choosing the largest plan the weather allows
  reached for her in a fresh breeze - clearing the ship for action on a quiet passage
  with nothing in sight. The weather plans are now their own list: what a plan is
  *for* is not written in its sail area, and a captain still orders her whenever he
  likes. He simply never gets her by accident.
- Two things that keep it from being a free upgrade: a furled ship still has masts,
  yards and standing rigging and so cannot be made immune by handing her sails, and
  shortening down does nothing at all for her hull - a ball goes through the same
  planking however much canvas is set.

- Add raking, which turns out to cost nothing. A shot that strikes end-on runs the
  length of a ship instead of stopping at a plank, and the angle on her bow *is* the
  point of impact - a quantity the system has computed since observation was built.
  In a hex game this needs a table of impact modifiers; here it falls out of where
  you managed to get your ship, so it is something a captain achieves by sailing
  well and something he can be caught by if he lets somebody across his stern.
- Make a stern rake worse than a bow rake, structurally rather than arbitrarily: a
  bow is solid timber and knees built to meet the sea, and a stern is windows, cabin
  and the weakest framing in the ship.
- Taper it rather than stepping. A shot fine on her bow is nearly a rake and worth
  nearly as much, and a threshold would make two degrees the difference between a
  scratch and a catastrophe. It falls away quickly, so the position has to be
  earned - and because `aspect_accuracy` already made an end-on target harder to
  hit, raking is a real trade: the hardest shot to land and the worst one to take.
- Name it when it happens. A captain works an hour for a rake and it is over in
  seconds; if it went past as an unusually large number nobody would know what they
  had just done.

- Add ammunition, and make it intent rather than a damage number. Ball for the hull
  means "I intend to sink you"; chain for the rigging means "I intend to catch you";
  grape for the people means "I intend to board you". Three answers to one question,
  none strictly better, and the choice is made before anybody knows how the fight
  will go - which is what makes the difference between a pirate and a privateer
  legible in what they load.
- Let range make it a decision instead of an optimisation. Ball carries as far as
  the gun will throw it, chain tumbles and loses half of that, and grape is a
  knife-range weapon - so the shot a captain wants is often the shot he cannot yet
  use, and closing to grape range means taking his enemy's ball the whole way in. A
  gun that cannot reach says so rather than missing quietly.
- Send each hit to the track its shot was aimed at, and route grape through the
  ship's company so morale, striking and mutiny answer for free. A gun remembers
  what it was last loaded with, so a battery keeps firing the same thing until her
  captain changes his mind.

- Split fighting from seamanship, which fixes a gap that had already shipped.
  `ShipsCompany.strength` read `quality.skill` - how well they work the ship - so a
  crack crew of seamen came out the equal of a party of marines. Exactly backwards:
  the marines cannot reef a topsail and will still carry a deck. Quality now carries
  both axes, and they spread differently on purpose - seamanship is a trade that
  takes years, and standing up in a fight is much less a matter of training.
- Add ratings and divisions. Seamen work her, oarsmen pull, marines fight and are
  close to useless at anything else, and a company can be composed of all three.
  Rating is what they were shipped to do; quality is how good they are at it, and
  keeping them separate is what lets a crack marine and a crack seaman both be crack
  and be worth entirely different things.
- Make a company weigh something. People are deadweight - `deadweight` has said
  "cargo, stores and people" since it was written - so shipping marines is a decision
  with no money in it at all. Substituting them for seamen costs nothing in the hold
  and costs her the hands to work her; adding them costs the hold directly. Casualties
  do not give the space back, because a hold that grew after a battle would be
  grotesque.

- Add damage tracks. Hull, rigging, oars, weapons and crew break separately rather
  than draining one pool, because a ship that is fast and toothless, one that is
  intact and cannot steer, and one that is whole and unwilling are three different
  ships and a single number cannot say which you are looking at.
- Feed each track into the simulation that already exists rather than into an
  invented combat statistic: cut rigging means less canvas draws and her polar curve
  does the rest; shot-away sweeps cannot be pulled by anybody, however many hands she
  has; a wrecked battery bears fewer guns, and the arcs already knew which. Hull
  damage is the only one that sinks her - a ship with her masts gone and every gun
  dismounted is a wreck to look at and will still float home.
- Route crew damage through the ship's company, so morale, exhaustion, striking and
  mutiny all answer without a line of new wiring. That join is why the crew work was
  done before this one.
- Make damage a fraction rather than a count of hits, because hulls here have
  continuous sizes and "five points" means nothing until you ask how big the target
  is. `share_of` decides it once: the same broadside is a bad afternoon for a
  first-rate and the end of a cutter.
- Set the scale of the whole system against the guns rather than guessing it.
  `WeaponType.damage` has defaulted to ten since it was written, with a docstring
  saying it was meaningless until the damage phase gave it a scale; this is that
  scale, and it works out at about sixteen hits to reduce a sloop and fifty-odd for
  a first-rate. Ships of the age were reduced over an hour of firing rather than in
  a broadside, and it keeps capture worth attempting - if gunnery killed quickly
  there would be nothing left to take. One constant, in `DECISIONS.md`, and every
  other number derives from it.
- Report what broke rather than that something did. A mast over the side and a hole
  below the waterline are events; they are derived from the tracks so they cannot
  disagree with them, and each is announced once rather than on every later hit.
- Consume `hesitation` at last. It has been computed since the crew went in and read
  by nothing, which made it a claim rather than a rule - a frightened crew now serve
  their guns slower, and never stop, because a battery that fell silent would make
  morale a kill switch rather than a cost.
- Consume `ShotResult.damage` at last, for the same reason. Gunfire now tells on the
  ship that takes it.

- Add buoyage. A mark now carries a *meaning* rather than only a name and a
  position - safe water, lateral port and starboard hand, the four cardinals, an
  isolated danger mark - because the meaning is the entire reason a helmsman knows
  which side to leave one on. Lateral marks reverse when outbound, which is the part
  everybody gets wrong: it marks the same edge of the same channel either way and it
  is the vessel that turned round.
- Make the two buoyage rules *checkable*, which is the point of them.
  `unreachable_berths` answers "which docks have no marked approach" and
  `unmarked_dangers` answers "which charted rocks has nobody warned of", and the
  example world asserts both in its own tests. A rule like "every approach is
  buoyed" holds on the day it is written and quietly stops holding the first time
  somebody adds an island; a paragraph in the docs will not catch that and a red
  test will. It caught its own author immediately - the example world had six island
  harbours and not one buoyed approach.
- Keep "in charted waters" load-bearing. An unmarked rock in surveyed water is
  somebody's negligence; an unmarked rock in unsurveyed water is just the sea, and
  keeping that distinction is what makes a chart worth having and standing into
  unknown water worth fearing. `Chart.covers` already knew which was which.
- Sight marks like anything else. They run through the same horizon arithmetic as
  hulls, so a low can drops below the horizon long before a beacon does, and the
  lookout reports them apart from the shipping - a sail on the horizon is a
  question, a buoy on the horizon is an answer.
- Give the sailing master a berth to keep. He steers round what the marks warn of,
  says so out loud, and lets the mark decide which way round - a cardinal sends her
  the way it names even when the cheaper-looking way round is the one with the rock
  in it. The alteration shrinks with range, so an early one is small.
- Lay marks in the example world: an offing every approach runs from, and a fairway
  buoy off each of the six island harbours.

- Add the ship's company, crew quality, morale and mutiny. A company is a number
  on the hull rather than a crowd of objects, because a galley's two hundred
  oarsmen as two hundred Evennia objects counted every tick would be absurd.
  Quality is two claims rather than one - how well they work her, and how much
  they will take before they stop - which are genuinely separate: a pressed crew
  who cannot reef may still be too frightened to run, and a crack crew will still
  not stand at any price.
- Make morale a standing condition rather than a check. A crew is not asked "do
  you break?" at moments of crisis; they hold a state that is ground down by what
  happens and comes back slowly. It falls faster than it rises, which is why a
  captain who spends his people cannot stop and have them back. The curve is
  exponential in elapsed time, so a tick running twice as often does not tire a
  crew twice as fast - the simulation must not change when the server gets busy.
- Add the two collapses, told apart by whose fault it is. Striking is what a crew
  does when the enemy has beaten them; mutiny is what they do when the captain
  has, and every grievance is something command did. Casualties count as a
  grievance only while she has *not* struck - the same crew cut to pieces in a
  fight their captain ended have been unlucky, and the difference is whether he
  would stop.
- Gate both twice. A bad reading is necessary and nowhere near sufficient:
  striking also needs casualties past a floor that scales with quality, so better
  crews must be hurt more before the question is even asked, and mutiny needs
  agreement rather than a complaint. An injected roll adds variance and cannot
  open a gate that is shut.
- Add exhaustion as a ship-level state, and let it cost her. A spent crew pull at
  half speed - still pulling, because a boat rowed by exhausted men is slow rather
  than stopped - and being driven past bearing becomes a grievance, which is what
  makes a chase a decision rather than a free action.
- Let a ship see her own conditions. Being aground, being boarded, having nobody
  aft giving orders: a game should not have to remember to tell a ship she is on
  the putty. What she cannot see - that these are her countrymen, that the enemy
  has a reputation - is what a game hands in, and factors are data so it can.
- Add `crew`, which reports her company and, if there is anything, what they hold
  against you. That last part is the one worth reading: a morale number says his
  people are unhappy, and this says what about.

- Add ownership and command. `owner` is property and `captain` is command, and they
  are two references rather than one controller field because a merchant who owns
  four ships is aboard at most one of them, and a captain who owns nothing still
  gives the orders on the deck he stands on. A captain can `pass_command` - to his
  mate for the night watch, to a prize crew - which is what makes the role a role
  rather than a label. One ship per captain, both ways: a man cannot be on two decks.
- Derive ADMIRAL rather than granting it. Hold more than one ship and you are one;
  lose one and you are not. A stored rank is a fact that can disagree with the world,
  and this one changes every time a ship is bought, sold, taken or sunk. What an
  admiral may *do* with a fleet is the game's to decide.
- Add `MARITIME_COMMAND_POLICY`, one function deciding whether a character may give a
  hull an order, replaceable whole rather than extended by hooks. Every order in the
  contrib routes through it, so a game where the mate may steer but not fire replaces
  it once and is obeyed everywhere. The default is deliberately small: her captain, or
  her owner if nobody has been appointed, or anybody aboard a ship that belongs to
  nobody - because a game that has not adopted ownership must still be able to sail.
- Refuse an order by naming who *may* give it. "You cannot do that" is the least useful
  refusal there is; the player wants to know who to find.
- Add `transfer_ownership`, which records *why* she changed hands and publishes it. No
  money changes hands and none ever will - what a ship is worth is the host game's
  economy, and a contrib that shipped a price would be arguing with it.
- Add `@ship`, the builder's command for making hulls and saying who they belong to.
  Subcommands rather than a menu, because a menu cannot be scripted and a world is
  usually built by a batch file at three in the morning. It ships in its own
  `ShipwrightCmdSet`, because it is the one maritime command that must work with no
  deck under you - every other one needs a deck by design, and this one is used from
  dry land.

- Add the scenario suite the design has listed since the beginning. Sixteen named
  voyages in `tests/test_scenarios.py`, each one a passage rather than an
  assertion about a function - set sail, stand on, and see where she ends up.
  Section 20's ticks used to mean "built and unit-tested"; they now mean "there is
  a voyage that runs it end to end", which is a stronger claim.
- Keep the grounding the tick already computed. `aground` is a boolean and the
  interesting question is not whether she is on the ground but what she is on and
  how hard she hit it - mud on a rising tide is an afternoon and rock at six knots
  is a different ship. The tick worked that out and threw it away; `Vessel.grounding`
  now holds it, which phase 17 will need badly.
- Add `charted-approach`, which the design's list did not have and should have.
  That a chart is wrong in *fixed* places rather than randomly is the one part of
  navigation where correct behaviour looks like a bug.

### Fix

- A gun that could not reach fired anyway. `can_fire` refuses for four reasons and
  the broadside loop skipped two of them, so a target inside the arc but beyond the
  guns' range discharged every piece aboard for a shot nobody took - and reported a
  broadside. A shot that *falls short* is deliberately not among the refusals: that
  gun did go off, and the charge is the price of having loaded grape.
- A ship aground, docked or anchored never finished a change of sail. The tick gave
  up on a held vessel before it reached the hands. Whether she is going anywhere has
  nothing to do with whether her people can work, and a ship hard on the ground is
  one whose captain very much wants his canvas off her.

- Reports mixed their units. Seen live in one sweep: a horizon "2.9 miles off",
  then contacts at "2.7 miles" and "1.5 leagues" in the same list - three ranges,
  two units, and no way to tell at a glance which was nearest, which is the one job
  a range column has. `format_range` chooses per value, so a report now chooses once
  and passes it down: the all-round sweep, a sector report, what a swimmer can see,
  and the passage report, whose two ranges sit in a single sentence precisely so
  they can be compared. Cables for close work stay as they were; they are how the
  distance is actually spoken at that range, not a second unit competing with the
  first.
- A ship whose name carried its own article was given a second one - "the the
  Kittiwake", live, in that same sweep. A game is entitled to name a hull that way,
  and it is not the narrator's business to say it twice.

- A ship with no company at all was hesitating. She reported a morale of one half -
  the default a quality carries - which put her in the shaken band and served her
  guns fifteen per cent slower for no reason whatever. There is nobody aboard to be
  frightened; a boat nobody crewed is worked by whoever climbed into her, and they
  are the host game's people rather than ours to unnerve. Found by loading a gun on
  a live ship and noticing the reload ran six seconds long.
- `shot_named("")` handed back round shot, because an empty string is a prefix of
  every name. Harmless where it was called from and wrong for anybody else.

- The company setter dropped the divisions. A company could be composed with marines
  aboard, assigned to a hull, read back, and come out an undivided crew of seamen -
  silently undoing the entire point of composing one. Every pure-domain test passed;
  only assigning a mixed company to a real ship and then asking her strength caught it.

- Casualties did not weigh on morale. They gated whether striking could be *asked
  about*, so a company could be cut to pieces and feel exactly the same watch to
  watch. Losses are now a factor in the standing condition, and deliberately a
  proportional one rather than a threshold: a crew do not feel nothing at
  forty-nine per cent and everything at fifty. The gate that decides whether
  surrender is a question is the separate mechanism, and that one does have a
  threshold. Found by writing the test that asserts casualties reach morale with no
  new wiring, which was the whole argument for building the crew before the damage.
- A shot heavy enough for two hulls killed more people than were aboard. `share_of`
  is unclamped by design, because a track clamps on the way in - but multiplying
  that raw fraction by the complement let five hundred points of damage kill a
  hundred and eighty-five of a sixty-hand crew.

- A report could not compare its own ranges. Seen live: "The horizon, all round -
  2.9 miles off", then contacts at "2.7 miles" and "1.5 leagues" in the same list.
  Three ranges, two units, and no way to tell which was furthest without doing
  arithmetic - which is the one job a range column has. `format_range` picked its
  unit per value, so a single report crossed a threshold partway down and changed
  vocabulary. A report now chooses once, from its furthest range, with `pick_scale`.
  Cables are deliberately still allowed alongside: a cable beside a league is two
  scales of measurement, the way feet sit beside miles, and reads correctly. Miles
  beside leagues is one scale said two ways, and that is the confusing pairing.

- The mate announced the same alteration every tick. Clearing a mark takes many of
  them, and he said "Giving the south cardinal a berth, sir" on each one - which is
  exactly the wallpaper `messaging` exists to prevent, by its own docstring: a ship
  reports that she is coming round, not that she is still turning, every two
  seconds. Found by sailing her; every unit test was happy.
  Fixing it turned up something structural. Steering to clear a danger settles at
  *exactly* the berth, so the alteration switches off, she swings back towards her
  course and raises the same mark again - which makes "am I turning?" a flickering
  thing to narrate from. `Clearance` now answers two questions: `mark` is what
  forced this turn, `watching` is the danger she is keeping clear of from raising it
  to passing it. The narration keys off the steady one.

- An empty sea was not empty. `EmptySeaMixin` blanked the weather, the current and
  the seabed and left the host game's navigation marks in place, so tests that
  believed they were sailing on blank water had the testbed's buoys on the horizon -
  which is how a test named "an empty sea reports the horizon" ended up looking at a
  fairway buoy.

- `@ship list` was unbounded. Sixty-two unit tests passed over it because each built
  two ships; a testbed with a hundred and sixty-eight in it scrolled a builder's screen
  off the top. It now takes an optional name to narrow by, shows a screenful, and says
  how many it held back - a list that silently stopped short would be worse than no
  list at all.
- `CmdShipwright` was in no cmdset, so it worked perfectly in every test and did not
  exist in the game. Found by typing it at a running server, which is the only way it
  could have been found.

### Chore

- Split `tests/test_scenarios.py` along a real seam when it passed the thousand-line
  ceiling. `scenario_base` is *how to sail a scenario* - a sloop, a stretch of time
  and three authored seabeds - and `test_scenarios` is *the voyages*. They change for
  different reasons, which is the test of whether a seam is real rather than a
  convenient place to cut.
  Worth recording what the split broke: the seabeds are named in settings as dotted
  paths built from `__name__`, so moving the classes left five grounding scenarios
  pointing at a module that no longer had them - and flake8 had called those imports
  unused, because they were used by *string* rather than by name. The paths are now
  derived from the module that actually holds them.

- Drop the `.pk` half of every deleted-object guard in `ownership.py`. A mutant
  survived - replacing the owner property's guard with a bare read changed nothing -
  and the reason turned out to be worth knowing: Evennia unpacks a reference to a
  deleted object as None, on its own and inside a list, in the same process that
  deleted it. The `.pk` half was guarding a state that cannot be stored. Code that
  no mutation can kill is not insurance, it is a claim nobody is checking.

### Docs

- Add `docs/combat-roadmap.md` and `docs/career-roadmap.md`: what ship combat needs
  next and why, and what a sea career would need, each item saying what it is
  informed by and what we do differently. Written down rather than carried in
  somebody's head, because the ordering constraints between them are the whole
  design - damage tracks have to exist before anything that writes into them.
- Set down buoyage and safe-water steering in architecture section 9, and add both
  buoyage invariants to section 21.

- Answer "what pulling an oar costs" in `DECISIONS.md`, with a fourth option none
  of the three listed there: exhaustion at *ship* scale. That dissolves the
  original difficulty rather than picking a side of it - the worry was colliding
  with whatever stamina the host game has, and at ship scale there is nothing to
  collide with.
- Set down the crew and morale model in architecture section 10.

- Correct architecture section 10, which said authority is evaluated per capability
  rather than held in a single slot - and what shipped holds two. That is not a
  retreat from the principle, it is where the principle actually lives: two slots
  are the two facts about a ship the world needs to agree on, and per-capability
  authority is the *policy*, not the storage. The section now says so rather than
  describing a design that is not the one in the tree.
- Answer "what a captor may do with a prize" in `DECISIONS.md` and start an
  **Answered** section to hold it. Ownership and command pass to the owner and the
  captain of the vessel that took her. Capture must be harder than sinking, which is
  the point that makes the rest work - a capture is worth more than a wreck, so if it
  were the easier road nobody would ever fight to sink anything. The alternatives are
  kept rather than deleted; the next person to ask why capture works like that
  deserves the argument, not just the outcome.

### Fix

- **The sailing master never stopped.** He handed back the con at the last mark
  and left her under working canvas with her last helm orders, so she sailed
  twelve kilometres past it and kept going. Ordering no speed stops a boat under
  oars and does nothing at all to one under sail - the canvas simply drives her
  again on the next tick. He now furls before handing back the con, which is what
  "takes the way off her at the end" was always supposed to mean. Every unit test
  in the suite passed over this; the route-following scenario caught it on its
  first run.
- The dead reckoning has a third source of error and the documentation claimed
  there were two. The log is read at the end of a step, so the reckoning
  over-counts while she is working up - about thirty metres for a sloop from rest.
  That is a realistic sampling artefact rather than a bug: a navigator reading four
  knots off the log and multiplying by the hour makes exactly the same mistake. It
  is now named in `reckon` rather than claimed away, and the scenario that asserts
  a perfect reckoning takes both the sails and the acceleration out first.

- Add boarding: grapples, the crossing they make, and the lines that part.
- **Speed is not the constraint - relative velocity is,** and that is the whole of
  the manoeuvre. Two ships running side by side at ten knots on the same course are
  motionless with respect to each other and can be lashed together at leisure; the
  same two at four knots on opposing courses close at eight and tear the irons out
  of the rail. Matching her course and speed *is* boarding her, and a speed limit
  would have made a chase and an ambush the same problem.
- Lines are re-tested on the tick rather than granted once. A made-up line takes
  more strain than a thrown one - but not much more, so a ship that puts her helm
  hard over and fills her sails always breaks free. That is what makes being
  boarded survivable and worth trying to survive.
- The crossing is two ordinary exits, made the same way a gangway is. Law 7 has no
  special case for a hostile traversal: crossing to a ship you are boarding is
  walking, so it can be followed, blocked, watched and locked exactly like walking
  ashore. `board` is not a command - it is the exit's name.
- You board onto a deck, never into a hold. The crossing lands on the highest
  weather deck, because that is where the rail is; a boarding party materialising
  in a sealed magazine would be a routing accident presented as a tactic.
- A refused boarding rigs nothing, so there is never an exit anybody can walk
  through that the grapples did not earn. Both hulls know they are fast to each
  other and cutting frees both - a one-sided attachment is the first symptom of a
  much worse bug.
- Add `grapple`, `cut grapples`, `strike` and `grapples`. Grappling needs an
  identified contact, exactly as gunnery does: you cannot throw an iron onto a
  shape you have not made out.
- Striking is a fact and confers nothing. Colours can be rehoisted, because a
  prize crew can be overwhelmed and a state that could only be entered would make
  that unrepresentable. What a captor may *do* with a prize is a question about
  authority, which is phase 14 - recorded in `DECISIONS.md`.
- No character combat, and none coming. The fight that follows is the host game's
  own; a maritime contrib shipping a second would be arguing with it.

- Measure what a vessel tick costs and give the simulation pass a wall-clock
  budget, which closes the reactor-budget open question. Written up in
  `docs/performance.md`, with the behaviour it justified asserted in
  `tests/test_budget.py`.
- **A fixed batch of 25 turned out to cost between 6.5 ms and 33 ms** depending
  on the world - a five-fold spread between the cheapest vessel and the dearest -
  and nothing about the number 25 tells you which. Twisted runs everything in one
  thread, so 33 ms is 33 ms in which no command is processed and no login
  completes. A count cannot protect against that because it does not know what a
  vessel costs; only a clock does.
- `MARITIME_TICK_BUDGET_MS`, defaulting to 10 ms. The batch count stays as a
  backstop, because a budget alone would let one pathological entity be visited
  alone forever.
- The budget is checked *after* an update, never before. Checking first would let
  one slow vessel starve herself out of the rotation permanently, which is a
  livelock rather than a limit.
- Add `FairQueue.rewind`. `next_batch` advances the cursor over the whole batch,
  which is right when the whole batch is processed and wrong the moment a budget
  stops the loop early - the untouched tail would be skipped and wait a full
  rotation, which is exactly the unfairness the cursor exists to prevent. A test
  caught it.

### Fix

- **`monotonic` cannot see a ten-millisecond budget.** The first implementation
  used `time.monotonic()`, which on Windows ticks at about 15.6 ms - coarser than
  the limit it was enforcing, so the budget would never once have fired. The
  benchmark's first run made it plain: four of six cases read exactly 0.00 ms and
  the rest exactly 16.00. `perf_counter` is the right clock for short intervals
  and is now used by both the service and the benchmark.
- **The tile cache was being thrown away on every call.** `config.map_provider()`
  built a fresh provider each time, on the documented grounds that providers hold
  no state worth sharing. That was true when it was written and stopped being true
  the moment tiles landed - a `TiledMapProvider` caches the squares it has loaded,
  and rebuilding it discarded that cache every time anything asked the depth of
  anything. It surfaced as an anomaly rather than a slowdown: a tiled world
  costing *more* per vessel with one ship on it than with twenty, which is not a
  thing that can be true. Measured directly, five ticks of one vessel: three tile
  loads kept against six rebuilt, and for a vessel at anchor it is the difference
  between one load ever and one per tick forever.
- The map provider is now kept, keyed on the settings that made it, so a settings
  change still yields a new one and a test using `override_settings` is never
  handed the old one. `config.forget_map_provider()` drops it on purpose. Every
  other provider is still built per call - they hold nothing.

- Add the example world, and with it real installation instructions. The README
  has said "full installation instructions will accompany the first release"
  since the beginning, which for a contrib whose acceptance bar is skeptical
  maintainers was the largest hole in the repository. Four numbered steps now,
  ending in `example` and a kayak.
- One mainland with a pond, a river and a harbour town; six islands strung
  eastward; a kayak, a canoe and a sloop. Between them the three craft use every
  kind of propulsion here and demonstrate that none of them is a special case.
- **Land is ordinary rooms with ordinary exits.** An island is a little graph you
  walk around exactly as you would walk around anywhere else, and one room of it
  is a `PortRoom` - an ordinary room that also stands at a world position and
  offers a berth. That is the entire join between a 2D room graph and a 3D sea,
  and it needed no new machinery: bringing a boat alongside rigs a gangway as two
  real exits, and letting go deletes them.
- There is deliberately no path from the river head to the harbour. The river is
  the road; rowing down it is how you get there and rowing back up it is a
  different afternoon.
- Every leg between islands falls between five and ten minutes under working sail,
  and a test says so rather than a comment. Moving an island a few hundred metres
  is exactly the sort of edit that looks harmless.
- Terrain is computed rather than tabulated. This world is twelve kilometres by
  six, which is nine hundred tiles nobody would want to edit, so `ExampleTile`
  overrides `terrain_z_at` and works the ground out at each point from a handful
  of authored shapes - the seam `Tile` documents, used the way it was meant to be.
- Islands have a foreshore. Without one an island is a cliff: twenty-four metres
  of water one step and dry sand the next, so a lead line would show nothing at
  all until she struck. The harbours sit on that foreshore, which is why they come
  out at five or six metres rather than twenty-five - a small harbour is shallow,
  and that is a constraint worth having.
- The river runs per reach rather than as one figure, so the stream follows the
  bends and a canoe rounding one is set towards the outside of it.
- The pond is slack on purpose. It is the control against which the river means
  anything; a boat that behaved the same on both would be demonstrating nothing.

- Add human propulsion: oars and paddles. A sailing vessel is not asked how fast
  to go - she goes as fast as the wind on that heading allows. A pulling boat is
  the exact opposite, and that difference is the whole module.
- Speed is a rated speed times the stroke times the fraction of oars actually
  manned. **A six-oared gig pulled by two hands is not a six-oared gig**; she is a
  slow boat with four oars stowed, and making the crew count matter is the point
  of counting them.
- A rated speed rather than a force. Turning strokes into newtons and newtons into
  knots needs a drag model for every hull and every number in it would be
  invented; a rated speed is one figure a builder can look up and argue with.
- `easy oars` and `hold water` both order no speed and are different orders. Easy
  oars means stop pulling and let her run on; hold water means put the blades in
  and stop her, so it comes back as sharper deceleration rather than a smaller
  number. It is the one thing a pulling boat can do that a ship under sail cannot.
- Sail wins where a hull has both. A cutter carries a lug sail and twelve oars,
  and which drives her depends on the wind - nobody rows a boat that is sailing,
  and a hull doing both would be getting her speed twice. Oars take over in a calm
  without anybody ordering it.
- One model and two vocabularies. A kayak is a boat with one position and a double
  blade; the plan carries which vocabulary applies and the messaging layer reads
  it, so nobody tells a lone kayaker to give way together - and the paddled column
  has no crew reply in it at all, because a kayaker talks to nobody.
- Rowing is speed *through the water*, like everything else here, so rowing up a
  stream and down it are the same work and different voyages with nothing
  subtracting a current from anything. `pull_for` answers the question a crew
  actually asks before setting out, including "we will never get up this river at
  that stroke", which is a real answer worth having before an hour of trying.
- Add `give way`, `paddle`, `stretch out`, `easy`, `hold water` and `oars`. The
  verbs a coxswain says, rather than one verb with an argument - though `oars
  <stroke>` exists too, for anyone driving this from a script.
- A boat nobody is driving still goes somewhere. Sails furled and blades out of
  the water is not the same as being moored: the stream carries her, and so does
  the wind, in proportion to how much of her stands out of it. That is the same
  windage a drifting cask has, from the same function, and it is why a kayak left
  alone on a pond fetches up on the lee shore rather than staying where it was
  let go. Skipped under canvas, where the wind is already driving her and leeway
  says how much of that goes sideways - counting it twice would be counting the
  same air twice.

### Fix

- **A vessel stopped in a tideway was not carried by it.** The tick decided
  "she did not move" from her propulsion alone and returned before the stream was
  ever applied, so a ship lying with no way on in a two-knot current stayed
  exactly where she was. The early return now comes after the water and the air,
  which is the only point at which it is fair to say nothing happened. Found while
  giving an idle boat her windage, which had the same problem for the same reason
  - and it had been there since currents landed.
- `METRES_PER_SECOND_PER_KNOT` was defined in two command modules and about to be
  needed in a third. Moved to `formatting`, once, along with a `format_speed` the
  messaging layer needed and had no way to get - a speed formatted one way for a
  report and another for a ship's own narration would be a tell. `commands/mooring`
  was also redefining `FIX_RANGE` and `MAX_ANCHORING_SPEED` alongside it.

- Run the LOGOUT-001 spike and write it up in `docs/logout.md`, with every claim
  pinned in `tests/test_logout.py` so that a change in Evennia shows up as a
  failing test rather than as a missing passenger. It was listed as an open
  question because guessing would have been cheap now and expensive later; it
  turned out to matter more than expected.
- **`room.contents` is not the list of people aboard.** Evennia takes an
  unpuppeted character off the grid entirely - `location` becomes `None` and the
  room is remembered in `prelogout_location` - so an offline passenger is in no
  room's contents at all. Every obvious way of asking who is on this ship misses
  them, including the one the architecture's own destruction invariant invites.
- Add `rooms.absent_from`, `rooms.everyone_in` and `Vessel.ships_company()`, which
  find them. Without these, the invariant about resolving everyone aboard before a
  hull is broken up is unenforceable by the means anybody would reach for.
- **No hook fires when a character logs out.** `at_post_unpuppet` sets
  `location = None` directly, and Evennia's location setter fires no move hooks at
  all - it updates the foreign key and returns. `at_object_receive` is then called
  explicitly on the way back in. A room hears people arrive and never hears them
  leave, so anything counting occupants from move hooks over-counts by exactly the
  number of players who logged out there.
- The good half, and it is genuinely good: a passenger restored to a remembered
  cabin arrives wherever the ship has since sailed. Nothing stored a coordinate
  for them and nothing had to, because a compartment holds no position. Measured -
  logged out at x=1000, ship sailed to x=5000, logged in at 5000. Had ships been
  moving rooms this would have needed a reconciliation pass on every login.
- A deleted room sends offline passengers home, silently. That is a policy arrived
  at by accident, and it is now in `DECISIONS.md` with the engine's actual
  behaviour attached rather than a guess.

- Add map tiles, which completes phase 2. The seabed is authored a square at a
  time: a base elevation, what the ground is made of, and whatever discrete
  hazards stand on it. A vessel loads only the tiles her track crosses, which is
  the difference between an O(n x m) sweep over every hazard in the world and one
  over the few on this stretch of bottom.
- A flat base with things standing on it, rather than a grid of soundings. A
  sounding grid is the obvious model and the wrong one for authoring: it makes a
  builder fill in a hundred identical numbers to describe one shelf, and still
  cannot say "there is a rock here that dries at low water" without inventing a
  resolution fine enough to hold it.
- **What tiles bought is exactness, not only speed.** The swept envelope samples a
  hull at seven points on her outline, and something small enough fits between
  them. An authored hazard has a position and a radius and is tested against the
  whole corridor she swept, so a rock inside the water she displaces cannot be
  missed. That was a named limitation in the README and is now gone for anything
  a game has actually drawn.
- How small "small enough" is got measured rather than argued. The first draft of
  that claim said the gap widened with speed, which is wrong - the sweep steps by
  half her length whatever she is doing - and the first rock chosen to demonstrate
  it turned out to be caught by sampling after all. The test that stands walks the
  sampled pass itself: two metres of rock, four metres off the centreline of a
  six-metre beam, invisible to all 567 points it looks at, and stopped by the
  corridor.
- She is stopped where she *enters* a hazard rather than where she passes closest
  to it, which needed a segment-against-circle solution rather than a walk along
  the track - stepping would have reintroduced exactly the sampling gap hazards
  exist to close. Closest approach is on the far side of a rock she has by then
  sailed through, which is a strange thing to show a player.
- `hazards_touching` is on `MaritimeMapProvider` itself and answers with nothing
  by default, so grounding asks every provider unconditionally instead of
  guessing whether this one can answer.
- Unauthored water is not a hole in the world. A square nobody has drawn falls
  through to a base provider - deep open sea by default - so a game maps its
  coastline and its approaches and leaves the ocean alone, which is how real
  charts work: the detail is where the danger is.
- Tiles load on demand and can be released, and a *miss* is cached as well as a
  hit. Open ocean is the commonest answer there is, and a cache that only
  remembered tiles would ask the source about the same empty square on every tick
  of a long passage.
- A hazard answers for its own material. Touching sand is an inconvenience and
  touching rock holes her, so a reef head standing on a sandy shelf cannot be
  reported as sand.

### Changed

- The grid arithmetic moved from `floating` to `spatial`, and grew. `cell_of` was
  in `floating` only because the ocean projection needed it first; map tiles want
  the same flooring at a different scale, and a second copy would have been two
  places for one seam at the origin to be wrong. `spatial` now also holds
  `cell_centre`, `cell_bounds`, `cells_touching`, `distance_to_track`,
  `nearest_on_track` and `track_entry`, which are one coherent group: the grid,
  and the geometry over it.
- `severity_of` extracted from `check_grounding`, so terrain and authored hazards
  decide severity the same way. Two copies would drift, and the symptom would be a
  rock that holes her when she is sampled onto it and merely holds her when the
  corridor test catches her.

- Add cargo. A hold has two capacities that are not interchangeable - the mass she
  can carry before she is too deep, and the space the cargo occupies - and which
  one binds depends entirely on what you are carrying. Iron stows at about a third
  of a cubic metre per tonne and hay at nine, so a hull full of one still has most
  of her volume empty and a hull full of the other is barely down on her marks.
  That is the whole trade, and both figures are tracked because either can be the
  one that stops you.
- `weighs out` and `cubes out` are reported as different answers, because they
  are: a ship that has weighed out will take nothing further, while one that has
  cubed out would still carry something denser. Telling a shipper only that she is
  "full" throws away the half of the answer they can act on.
- Broken stowage - the space wasted between irregular packages - is charged
  against packaged cargo and not against bulk, because bulk has no packages to
  leave gaps between. A hold of loose grain that mysteriously wasted a tenth of
  itself is something a ship's officer would notice.
- Cargo is data, not objects. Five hundred tonnes of grain is one parcel rather
  than five hundred database rows, on the same argument that made shots events. A
  game wanting a *particular* crate puts an ordinary object in the hold beside the
  parcels.
- `Vessel.draft` is derived at last. It carried a docstring promising that cargo
  would one day make it a worked figure rather than a stored one; it is now light
  draft plus what the manifest puts her down by, so grounding, keel clearance and
  whether a berth will take her all read the laden number without one call site
  changing. Setting it raises and points at `light_draft`, because a stored
  working draft would be a second source of truth the next transfer overwrites.
- Loading has four consequences and every one of them lands in a system that was
  built before cargo and did not have to change to receive it: she grounds where a
  light ship swims, a berth that took her light refuses her loaded, she is slower,
  and weight stowed high makes her tender.
- `working_limits` is a second property rather than a laden `motion_limits`.
  Draft could become derived silently because almost nothing wrote it; limits are
  authored on every vessel a game builds, and a getter returning something other
  than what was set would be a trap.
- Holds are ordinary compartments with a capacity, so any room aboard could be
  one and a room with no capacity simply is not. Converting a cabin to cargo space
  in a refit is then setting a number rather than rebuilding the room - and every
  compartment already carries the deck level that stowing weight low depends on.
- Loading fills from the lowest hold up and discharging works from the highest
  down, which is what a mate would do anyway: it keeps her stiff at both ends of
  the operation rather than leaving her tender halfway through.
- The first consumer of `VesselCapacity`, which has existed since vessels did,
  unused, waiting for something that had to draw on a shared budget.
- Add `stow`, `discharge` and `manifest`. Cargo only moves alongside - a hold
  filled in mid-ocean would make the whole of docking optional - and the
  precondition is the same `held_by` the rest of the system already uses.
- Add a standard stowage table: twelve real cargoes with their real stowage
  factors, in the same spirit as the Beaufort scale and the marks on a lead line.
  Reference data rather than content, and a game that has its own economy points
  `MARITIME_COMMODITIES` at it and never loads this.
- `cargo.py` holds the arithmetic and `stowage.py` the two Evennia faces. A
  departure from how the rest of the contrib is laid out, and a deliberate one:
  every other domain module has exactly one mixin, and cargo has two that are as
  different from each other as a room is from a ship.

### Changed

- **`Vessel.draft` is read-only.** It is now the working figure - light draft plus
  what the manifest puts her down by - and assigning to it raises an
  `AttributeError` naming `light_draft` instead. A silent setter behind a derived
  getter would mean `v.draft = 2.0` followed by `v.draft` returning 2.3, which is
  a worse trap than a loud break. Every reader is unaffected and gets the laden
  figure for free; six tests across grounding, ports, currents and the swept
  envelope were the only writers, and the full suite found them at once.

- Add the projected ocean. Open water is somewhere a player can be, without
  building rooms for a sea nobody is in: a small pool of rooms, each lent to
  whichever square of water currently has somebody in it and taken back when they
  leave. The pool is bounded by the number of *occupied* cells, so one drifter
  crossing twenty cells still needs exactly one room.
- The room is a view, not a location, and that inversion is the whole design.
  Evennia's `wilderness` was read closely first; there the room *is* where you
  are, so recycling has to preserve its contents, and its own docstring warns
  that objects left behind end up with `location = None`. Here the truth is the
  swimmer's position, held on the swimmer, so releasing a room loses nothing -
  place them again and the same water comes back.
- A lone drifter never changes room at all: the room pans to the new cell
  instead. No move, no departure, no arrival, no write to a location. Skipped the
  moment somebody else is in the room, or another room already shows the
  destination, because two rooms showing one cell would put two swimmers in the
  same water unable to see each other.
- The pool is found by tag rather than by typeclass. A typeclass query filters on
  the dotted path stored on the row, so moving or renaming the class would
  silently empty the pool - which is a bug this contrib has had once already, in
  another module.
- Add floating things: swimmers, rafts, casks, wreckage. The current carries
  everything in it equally because it is the water; the wind moves what stands
  out of that water, in proportion to how much does. Windage is the only
  difference between a raft and a man, and it is why a search for someone who
  went over with a lifebuoy widens in a predictable direction.
- Drift reads the same current and the same wind a vessel in that water reads, so
  a barrel dropped over the side stays with the ship that dropped it until the
  wind separates them.
- Add `Flotsam`, which is `Floating` and `Situated` and nothing else. A game
  wanting floating *characters* mixes `Floating` into its own character class
  instead.
- Add `WaterNarrator`, replaceable through `MARITIME_WATER_NARRATOR`. Being in
  the sea has a different voice from being on a ship, so it is a second narrator
  rather than a method on the first. Bearings are compass points, not relative
  ones: a body in the water has no head for a bearing to be relative to.
- The depth is reported only when the bottom is close enough to stand on. A
  swimmer in deep water has taken no sounding, and telling them how deep it is
  would hand out a number nobody has.
- The horizon from the water is not symmetrical, and the code was right where the
  first draft of the tests was wrong. Height beats the curve, so a ship's masts
  are in sight four miles off; what is lost from down there is everything low - a
  boat, a raft, another swimmer. The cruelty is the other direction: she carries
  no height to be seen by, and from that deck there is nothing on the water at
  all.
- Buoyancy carries a sink rate as well as a flag, because something that has
  stopped floating is still somewhere, going down through a water column that is
  a real place. Collapsing that to a boolean would delete every wreck before
  anybody could dive on it.

### Fix

- A ship seen from the water was announced as "The kittiwake". `str.capitalize`
  lowercases everything after the first character, which is harmless on a
  generated phrase and wrong the moment the phrase contains a name. Replaced with
  `open_sentence`, which raises the first letter and leaves the rest alone. No
  test caught it and one look at the water did, which is the argument for looking.

- Add weapons. A mount is a range, a reload, a projectile speed, an arc and an
  accuracy - nothing here is a cannon, and a game fills those in for guns,
  ballistae, harpoons or something that spits lightning. The rules are the same
  because the geometry is.
- Shots take time to fly, so guns are laid where she will be rather than where
  she is. That assumption is wrong the instant she alters course, which is
  exactly why altering course under fire is worth doing.
- Hit chance is four independent factors multiplied: the weapon, the range, the
  sea and how much of herself she is showing. Each is separately arguable and
  separately tunable, which is the point of not rolling them into one number
  nobody can reason about. A bow-on target is about a third the size of a
  beam-on one, which is why a ship under fire turns towards the guns.
- Shots are events, not objects. A broadside is eight solutions and eight
  results, not eight database rows tracked across the world for four seconds.
- The RNG arrives as an argument rather than being reached for, so a fight
  replays identically from a seed and a test can hand in a fixed roll.
- Add `guns`, `load` and `fire <name>`. Firing needs an identified target: you
  cannot lay a solution on a shape you have not made out.
- Damage is deliberately untouched. A hit says where and how hard and stops;
  hull sections, breaches and flooding are phase 17 and carry decisions that are
  Gary's.

- Add tactical geometry: range, bearing, relative bearing, aspect, relative
  heading, closure, time to close, range bands and weapon arcs. Arithmetic on
  what the simulation already holds; nothing here decides anything or resolves
  anything.
- Aspect is the one that is not symmetric and the one that matters. A ship broad
  on your beam who is bow-on is coming for you; the same ship at the same bearing
  showing her stern is leaving, and nothing else separates those two situations.
  Demonstrated live at an identical bearing of 0-0-0: bow-on and closing at 16.7
  knots, then stern-on and opening at 1.9.
- Range bands are configurable, because what counts as long range depends
  entirely on what a game arms its ships with, and hard-coding it would put a
  weapons decision inside a geometry module.
- `crossing_the_t` falls straight out of holding bearing and aspect separately -
  she is abeam of you and you are ahead of her - which is the clearest
  demonstration that they are different questions.
- Add `target <name>`, which needs an identified contact: you cannot lay a
  solution on a shape you have not made out.
- Tactical *pacing* is deliberately not decided. It is an open question in the
  specification, it belongs to the game, and `tactical.py` takes no time argument
  at all so it is incapable of having an opinion. Recorded in `DECISIONS.md`.

- Add the sailing master: the smallest automation that gets her from one mark to
  the next. He steers for the mark allowing for the set, carries the most canvas
  the wind permits, takes the way off her coming up to the last mark, and hands
  the con back when the passage is made. Four judgements, which is what a
  competent hand does without being told.
- Deliberately not standing orders. No evading, no diverting for shelter, no
  conditions or priorities - those need a rules engine with conflict resolution
  and are their own phase. A first version of them smuggled into the mate's
  judgement is how a small honest automation becomes an unreviewable one.
- He works her through the same properties a player uses, so he cannot exceed the
  rig, cannot ignore the weather, and is as stuck as anybody when she is anchored
  or aground. He has no private channel to the hull.
- `course_for_mark` is the first caller `course_to_steer` has had since it was
  written two phases ago, which is the point of building the seam first.
- Add `follow` and `belay`. Proved live: she sailed all five marks of a plotted
  course round the rock ledge unattended, shortening sail as the wind asked, and
  reported the passage made.

- Add weather. Wind, visibility and sea state now arrive together from one
  provider sampled at a place and a moment, rather than being read separately
  from three settings wherever somebody happened to need them. They are not
  independent - a gale brings a high sea and takes your visibility with it - and
  a system that lets them drift apart will produce a flat calm you cannot see
  across.
- Sea state follows the wind by default, on the WMO scale, but a provider can set
  it against the wind. Waves need fetch and time to build and go on running after
  the wind drops, so a calm morning with a heavy leftover swell has to be
  expressible.
- A heavy sea takes some of her way. Deliberately gently: the danger is meant to
  come from the lee shore and the flooding, not from an arithmetic wall that
  makes heavy weather unplayable rather than dangerous.
- A weather deck describes the sea it is in, and a calm is not remarked on -
  the absence of waves is not news, and repeating it is how ambient text becomes
  wallpaper. Add `weather`, reporting all three together.
- `MARITIME_WIND_BEARING`, `MARITIME_WIND_SPEED` and `MARITIME_VISIBILITY` still
  work exactly as before, through the default provider. Those settings were the
  whole of weather until now, and a game that set them should not have to learn
  about providers to keep what it had.

- Add charts, which are knowledge of the sea rather than the sea. A chart covers
  a rectangle, was made by somebody at a moment, and is wrong - but wrong in the
  *same places every time*, because the error is a deterministic function of its
  seed and the position rather than fresh noise per reading. Noise regenerated on
  every glance would be unlearnable; this way a bad patch is a place on the paper
  and a pilot who has caught it out once knows to sound there.
- Charted soundings are given at the datum, never at the present tide. Applying
  the state of the tide is the navigator's job, and doing it for them would
  remove the commonest way a careful sailor still goes aground.
- Being off the chart is its own state. A vessel outside her coverage has no
  soundings at all, which reads very differently from having bad ones.
- Add routes: marks a game has authored, and Dijkstra over the safe water between
  them, weighted by real distance. Which channels are passable is knowledge a
  pilot has and an algorithm does not - a planner that searched the seabed would
  find every gap a hull could theoretically fit through, including the ones no
  master would take at night.
- Add `chart` and `plot`, and `MARITIME_NAVIGATION_NETWORK` for a game to lay its
  own marks. Phase 9 is complete.

- Add `scan`, which sweeps the whole horizon quarter by quarter and names the
  empty quarters as well as the full ones. A lookout who only mentions what he
  can see leaves you unable to tell "nothing there" from "nobody looked".
- `look <direction>` reports one quarter or compass point - `look fore`, `look
  port`, `look se`. Ship-relative directions turn with her and compass
  directions do not, which is the difference between watching the port bow and
  watching the headland.
- Add `watch <direction>`, a standing watch that tells you when something lifts
  over the horizon that way and when it sinks again, instead of looking every few
  minutes. Kept from where you are standing, so one set at the masthead sees
  further than one set on deck.
- Directions can be typed the way people type them: `se`, `south east`,
  `south-east` and `southeast` are one direction, and `stbd`, `astern` and
  `larboard` all resolve.
- Contact reports now carry both bearings, the range and what she is - bounded by
  what the range allows, so a hull at the edge of vision stays "a sail" even
  though the engine knows her name. An empty sector says how far it can see,
  because "nothing in sight" is unbounded otherwise.

- A weather deck now describes the sea outside it. The room's own description
  says what is nailed down; appended to it is what is happening - how she is
  moving, the wind by its Beaufort force, whether the water is setting, and what
  the lookout can see. Static rooms, moving world, which is what lets a ship be
  ordinary Evennia rooms and still feel like she is at sea.
- Nothing is invented for it: her motion, the wind, the current and her contacts
  were all already being computed, and this is the one place they are put into a
  sentence.
- The view uses the height of eye of the compartment you are standing in, so the
  same look from the deck and from the masthead can honestly disagree about
  whether there is anything out there. Demonstrated live at 29.8 km: "Nothing
  breaks the horizon" on deck, "A sail stands on the port beam" aloft.
- Add the Beaufort scale. The arithmetic is in `sailing.py` and the names are in
  `messaging.py`, because what a force 7 is *called* is prose - "near gale" and
  "the sky gone the colour of a bruise" are the same measurement.

- Grounding now tests a hull's footprint along her whole track instead of one
  point where she ends up. This was the largest known gap between the
  architecture doc and the code, recorded in both for several phases: a fast
  vessel could step clean over a reef narrower than one tick of her movement,
  and the faster she went the more of the seabed she was entitled to ignore -
  precisely backwards, since speed is what makes grounding expensive.
- A hull is seven points in a rough ship shape rather than a rectangle, because
  a rectangle puts steel where a ship has none. Her bow can ground while her
  centre is still in deep water, which is what a large ship actually does.
- She is stopped at the first thing she touches rather than at the end of the
  move. A ship that struck a reef a third of the way through a tick did not
  travel the other two thirds.
- Demonstrated live: a hull making 25 m/s asked to run 750 metres across 400
  metres of rock. The old point test at her destination reported clear water; the
  swept test stopped her one metre short of the ledge.

- Add dead reckoning, and with it the possibility of being genuinely lost. A
  vessel now carries an estimate of her own position, advanced by the course
  steered and the distance logged and by nothing else - which is what a
  navigator with a compass and a log line actually has.
- The error is not rolled. `speed` is already speed through the water, so a
  reckoning advanced by heading and logged speed diverges from the truth by
  exactly the current and the leeway, both of which the simulation was computing
  anyway. A ship in slack water is never lost and should not be; the sea makes
  you lost.
- Add `fix`, which takes a bearing on a landmark of known position. It reports
  what the reckoning had missed - and the difference between where you thought
  you were and where you are, over the time run, is the set and drift you have
  been carrying. That is the input `course_to_steer` was written for, and the
  loop closes.
- Players are shown `reckoned_position`; the true position stays with the engine
  and with staff tools.

- Add ports, and with them the first true vertical slice. A berth has a position,
  a line to lie along, and dimensions - length, beam and the depth of water
  alongside - so a hull that has been fitted out until she draws another half
  metre may no longer fit her home berth. Coming alongside is checked in the
  order a ship discovers it: berth free, ship fits, near enough, slow enough,
  lying along the quay.
- The gangway is two ordinary Evennia exits, made when the lines go ashore and
  deleted when they are let go. Being ordinary exits they can be followed,
  blocked, watched and locked like any other, which is Law 7 doing its job rather
  than a docking system reimplementing movement.
- Add `PortRoom`, quayside room space that also stands somewhere on the water -
  the one place the two coordinate systems meet. Add `dock` and `cast off`, and
  `Vessel.length` and `Vessel.beam`, which berth fitting needs now and hull
  footprints will need later.
- A vessel now keeps her own list of compartments rather than querying for them.

- Add currents, the last named deliverable outstanding from the sailing phase.
  A vessel is now carried by the water in addition to whatever she makes through
  it, so her heading and her track are different questions and only the second
  one gets her anywhere. `currents.py` carries set and drift, course and speed
  made good, and `course_to_steer` - the navigator's triangle, which genuinely
  has no answer when the stream is stronger than the vessel and returns None
  rather than a heading that quietly does not work.
- A current is named for where it goes and a wind for where it comes from. Both
  conventions are kept. Normalising one to match the other is how a bearing ends
  up reversed deep inside a passage calculation.
- `speed` remains speed *through the water*, which is what a chip log measures,
  and the over-ground figures are derived. The current therefore never has to be
  subtracted back out of anything, and the difference between the two is
  reportable - which is most of what navigation is.
- Add `current`, reporting set, drift, and the course she is making good as
  against the one she is steering. Add `MARITIME_CURRENT_PROVIDER` for a tidal
  stream, and `MARITIME_CURRENT_SET` / `MARITIME_CURRENT_DRIFT` for a game that
  wants one steady set without writing a class.
- Add `environment.py`: wind, current, visibility, clearance and what is in sight,
  as functions of a position rather than methods on a hull. A swimmer, a raft and
  a wreck are subject to the same weather and the same water, and none of them
  are vessels.

- Distances and depths are now reported in units a game chooses, defaulting to
  the ones the subject matter used. `MARITIME_DISTANCE_UNITS` takes `leagues`
  (the default: cables, sea miles, then leagues), `nautical`, `metric` or `raw`;
  `MARITIME_DEPTH_UNITS` takes `fathoms` (the default) or `metres`. The two are
  separate on purpose - a ship reckoned her run in leagues and her water in
  fathoms at the same moment. Metres remain the unit everywhere inside the
  simulation.
- Soundings are called the way a lead line is actually read. `leadsman_call`
  reads a depth to the quarter fathom and gives it as `"By the mark seven!"`
  where the line carries leather or rag, `"By the deep six!"` where it carries
  nothing, `"A quarter less eight!"` for three quarters over, and `"No bottom
  with this line!"` past twenty fathoms. Two fathoms is `"By the mark twain!"`,
  which is where Samuel Clemens got the name. Verified live against a
  game-supplied seabed at four depths.
- `GroundingResult` now carries the depth it measured as well as the clearance.
  They are different questions: a leadsman reports what his line finds and knows
  nothing about the draft of the ship he is standing on.

- Add observation. Detection at sea is a height problem before it is a range
  problem: a hull is hidden by the curve of the water, so how far you can see is
  decided by how high your eye is, and how far you can see *a particular thing*
  by how high that thing is as well. `observation.py` implements the horizon
  (`2.07·√h` nautical miles, the figure a navigator uses, refraction already
  folded in), geographic range as the sum of two horizons, and a detection limit
  that is the lesser of that and what the air allows.
- Height of eye comes from the compartment an observer is standing in, so a
  masthead is worth building rather than worth mentioning. Proved live: one ship,
  one instant, nothing in sight from her deck and a sail 15.9 miles off from her
  crosstrees.
- Add `traffic.py`, the register of who is on the water. The first thing here
  that is not about a single vessel, and the first user of the spatial indexes,
  which had been written and never called.
- Add `lookout`, which reports what can be seen from where you stand - where to
  look, how far off, and only as much as the range allows. Contacts run
  `CONTACT → VESSEL → CLASSIFIED → IDENTIFIED`; the engine knows her name at any
  range and does not say it, because otherwise closing to identify is pointless.
- Sightings are cried as they happen: a new sail, one lost below the horizon, and
  one close enough to tell something new about. A ship at anchor or aground still
  keeps a watch.
- Add `format_range`, which reports distance in cables under a mile and miles
  above it, because ranges at sea are estimates and "three cables" reads as one
  where "555 metres" does not.

- Split the speaking layer out of the `Vessel` typeclass into `messaging.py`, and
  make it a configured seam. Law 11 said the domain returns data and a separate
  layer renders it; the prose was in fact welded into the typeclass, so the
  README's claim that a game could replace every word without touching the
  simulation was not true. It is now: `MARITIME_NARRATOR` points at a
  `VesselNarrator` subclass, every line a vessel speaks passes through one
  `phrase_for` method, and a game that overrides only the words still inherits
  the transition logic that decides when to say them.
- Deciding *when* to speak now lives with the narrator rather than the hull,
  because it needs to know what was last said - a property of the conversation,
  not of the ship.

- Add grounding. A hull finds the bottom when terrain intersects her envelope -
  keel clearance is the water surface less her draft, less the ground beneath -
  so shoals and reefs need no special representation beyond the terrain already
  having the right shape. Clearance is a continuous value, not a yes-or-no,
  because knowing you have four metres and losing one a mile is what lets a
  navigator decide; discovering you have grounded does not. Bottom type decides
  what it costs: sand holds her and the tide usually gives her back, rock struck
  with way on opens her. Adds `sound`, a shoal warning from the leadsman, and
  `MARITIME_MAP_PROVIDER` so a game supplies its own seabed.
- A surface vessel's elevation is now set by the water rather than integrated, so
  she cannot be sailed to the seabed by assigning a negative z. That was
  previously possible and silently meaningless.
- Add sailing. Wind, a data-driven polar curve, sail plans and leeway, so speed
  stops being something you order and becomes something you negotiate: a vessel
  makes what the wind on her heading allows, which head to wind is nothing at all.
  Wind is named for where it blows *from*, as every chart and sailor names it.
  Leeway sets her off her heading, worst close-hauled - which is why dead
  reckoning goes wrong to windward. Adds `sail`, `wind`, `drop anchor` and
  `weigh anchor`, with period orders and crew replies.
- Add position formatting, so players read a position rather than coordinates.
  Latitude and longitude in degrees and decimal minutes, which works out cleanly
  because a nautical mile *is* one minute of latitude by definition - northing
  divided by 1852 needs no fudge factor. Longitude keeps the same scale rather
  than narrowing towards the poles: this world is a plane, and a cosine
  correction would make the displayed position disagree with the distance
  actually sailed. Kept in the messaging layer rather than on `WorldPosition`,
  since a fantasy game may reckon in leagues and a sci-fi one will not use
  latitude at all. `MARITIME_ORIGIN_NORTHING` and `MARITIME_ORIGIN_EASTING` place
  the world's origin on the globe; `MARITIME_POSITION_STYLE` chooses the
  presentation. Raw coordinates move to a new staff-only `@maritime` command.
- Add the driver script, the helm command set, and reporting to the ship's
  company. `MaritimeDriver` is one repeating script for the whole game that ticks
  the service and checkpoints periodically - without it everything below is
  inert. Orders are called out loud and answered using real helm procedure:
  courses are spoken digit by digit ("Helm, steer 0-9-0"), the helm repeats the
  order back, and reports again when the vessel is steady on it. Ambient
  reporting describes *transitions* rather than conditions, so a turn is
  announced once and on completion instead of every tick, and what reaches a
  person depends on their compartment's exposure - on deck you watch the sea go
  by, below you feel her heel and hear water on the planking.

### Fix

- Progress along a route is carried rather than derived from position. Taking
  "the first mark she is not near" looks right until she reaches the end, at
  which point the first mark is the furthest away and she is sent back to the
  beginning of the passage. Found by the tests before it ever ran.

- A vessel could not find her own compartments after `ShipRoom` moved module.
  Evennia stores a typeclass as a dotted path and the manager filters on that
  *string*, so `ShipRoom.objects.all()` returned nothing for every room created
  before the move - while the rooms themselves loaded perfectly. A ship with
  compartments behaved exactly like a ship with none: no lookout height, no
  messaging, no gangway. The re-export kept them resolving and could not keep
  them queryable. Vessels now hold their own compartment list, which fixes it,
  removes a full table scan that ran every tick, and does not care what string
  is in the row. `Vessel.reattach_compartments()` rebuilds the list by type for
  anyone upgrading.
- Set a compartment's ship with `room.vessel = hull`, not `room.db.vessel`. The
  link has two sides now and only the property maintains both.
- A vessel stopped dead and head to wind could never come round. Backing a
  headsail turns a stationary ship - that is the entire manoeuvre - but the
  recovery was written as a raised turn *rate*, and turn rate is scaled by speed
  because it models a rudder. Multiplied by zero speed it gave zero turn. Docking
  at a north-facing berth in a northerly parked a ship permanently. `advance()`
  now takes a `turn_floor` that is not speed-scaled, which is the honest way to
  represent anything that turns a hull without water over the rudder: a backed
  sail, a sweep, a warp, a tug. Found by sailing the vertical slice; no unit test
  had ever started a vessel at exactly zero.

- Tests now assert the neutral world they describe rather than inheriting the
  dev game's. Twice now a game has configured something - a seabed, then a
  current - and tests that had never mentioned it started quietly measuring it
  instead of the flat, still, empty sea they claim to test. `EmptySeaMixin` now
  neutralises ground, stream and wind alongside clearing the traffic register,
  so the next thing a game configures cannot do it a third time.

- A vessel stemming the tide exactly no longer reports a nonsense course. The two
  velocities cancel to a residual of about 1e-16 rather than to zero, and asking
  `atan2` for the direction of that residual returned a confident, meaningless
  bearing - a ship reported as making good due south while sitting motionless.
  A nanometre a second is not a course.

- A deleted vessel now leaves the traffic register. It is memory rather than a
  foreign key, so nothing removed her when her row went, and a hull that sank and
  was deleted would have stayed visible on the horizon indefinitely. Found by
  test pollution, which is the same defect wearing a different hat.

- Remove two unused imports from the grounding tests. Caught by CI rather than
  locally, because the local check before that push was the discipline script
  alone and not the linters CI also runs. The three commands that make up the
  gate are now written down in `CLAUDE.md` as one gate.

- A vessel that turned too close to the wind was trapped for good: she lost drive,
  losing drive cost her steerage, and without steerage she could not turn back out.
  The trap is authentic - it is what being in irons means - but a hull nothing can
  recover is a broken ship rather than a hard one. A crew with canvas aloft can now
  back a sail to shove her bow round, which is what a real crew does. With sails
  furled she remains genuinely helpless, as she should be.

- `WorldPosition.__str__` now shows millimetres rather than a single decimal.
  Coordinates were always full 64-bit floats and collision, grappling and
  boarding always read them directly, but the display hid that from the one view
  a developer uses to work out why two hulls did or did not touch.

- Wire motion into the vessel and add helm commands: `helm`, `speed`, `allstop`
  and `position`. A vessel under way is advanced by the simulation service, and
  movement never touches the database - it updates in memory and is checkpointed,
  as position changes many times a minute. Commands take and report knots while
  the domain works in metres per second throughout, so display units stay out of
  the physics and a game preferring other units changes one file.
- Add the vessel motion model. Orders are targets, not instructions: the helm asks
  for a heading and the hull swings towards it at whatever her rudder and speed
  allow, which is most of what makes handling a ship feel unlike driving a cursor.
  Turn rate scales with speed, so a vessel dead in the water cannot steer at all
  and losing way is a real problem rather than an inconvenience. Motion integrates
  in fixed sub-steps, so a turning vessel carves an arc instead of pivoting on the
  spot and running the distance on her new heading - and the track comes out the
  same whether the scheduler ran once or sixty times, so a laggy server does not
  quietly put ships somewhere else. Adds `bearing_difference`, which turns the
  short way round: naive subtraction sends a vessel almost all the way round the
  compass to make a twenty-degree alteration across north.
- Add the simulation service and its fair scheduler. One service drives everything
  rather than a ticker per vessel - partly for cost, partly because Evennia's
  TickerHandler keys subscriptions on callback, interval and idstring but not on
  arguments, so a fleet subscribing one method at one interval silently overwrites
  itself and most ships just stop moving. Work is tiered (dormant, strategic,
  active, tactical) and each pass is bounded, resuming from where it stopped, so a
  large fleet lengthens the revisit interval instead of blocking the reactor. The
  rotation keeps its cursor across passes: restarting from zero looks fair but
  starves everything past the budget. Catch-up is capped, so a server down for a
  week does not hand a vessel a week of movement in one step. A failing update or
  checkpoint is logged and skipped rather than stopping the fleet.
- Add the `Vessel` and `ShipRoom` typeclasses. A compartment holds no position; it
  names its vessel, and the resolver walks through to whatever the hull reports, so
  moving a ship moves everyone aboard at once with no bookkeeping. Position lives
  in memory and is checkpointed on reload, on shutdown and on demand rather than
  written on every change: each `.db` assignment is a pickle and a commit, and a
  vessel under way updates constantly. An unchanged vessel skips the write
  entirely, so a fleet at anchor costs nothing to checkpoint.
- Add vessel templates, capacity and deck plans. A ship class is data, not a
  subclass - changing a sloop's beam is editing a number, so no `Sloop` class
  exists anywhere in the contrib and a game can define its own hulls importing
  only `VesselTemplate`. Deck levels are integers relative to the main deck, so
  they map straight onto elevation and flooding can fill from the lowest
  compartment upward without a separate model of which room is under which.
  `VesselCapacity` and deck slots are declared now although nothing consumes them
  yet: they are what make later fit-out a set of trade-offs rather than a shopping
  list, and adding them after templates exist means rewriting every template.
- Add `ContactIndex` and `ProximityIndex`. Two indexes rather than one, because
  the difference is geometry and not tuning: horizon range is a surface question,
  so contacts ignore elevation, while boarding is not, so proximity measures true
  distance and a diver thirty metres beneath a hull is correctly nowhere near it.
  Both produce candidates, never answers - whether a hull can actually be seen
  depends on weather, light and height of eye, none of which an index knows.
  Entities in other regions are never candidates, since regions are separate
  coordinate spaces. Currently a linear scan: with no vessels yet there is nothing
  to index, and picking a structure now would mean guessing at query patterns that
  do not exist. The interface is what matters, and the structure behind it is
  replaceable without a caller noticing.
- Add the world-position resolver. Every subsystem asks `get_world_position()`
  rather than working the answer out itself, because the answer is rarely direct:
  a character aboard a vessel has a cabin, which belongs to a hull, which is the
  thing that actually sits somewhere. An entity joins world space by declaring
  either a `maritime_position` or a `maritime_position_source` to ask instead;
  otherwise ordinary `location` is followed. A declared source outranks location,
  so a docked vessel's interior resolves to the hull and not the harbour room.
  Anything outside the maritime world returns `NoWorldPosition`, a falsy singleton
  rather than `None`, so absence cannot be quietly treated as a coordinate.
- Add terrain elevation, tides and derived water depth. There is no depth map -
  one terrain field crosses zero, and depth is the difference between the current
  water surface and the ground beneath it, computed rather than stored. Sea level
  is a datum, not a constant, so moving the surface changes every depth in the
  world without touching terrain: a bank can dry out at low water and flood as the
  tide rises. Depth queries require a game time, since a depth without one asks
  about the datum rather than the water actually present. `FlatTideProvider` and
  `FlatSeaMapProvider` give a game vessels before it needs bathymetry.
- Add `WorldPosition`: continuous three-axis coordinates, where z is elevation
  relative to the sea-level datum. One field covers land, sea surface and seabed,
  so tides, grounding and shorelines derive from a single model rather than three.
  Bearings are compass bearings - north is 0, east is 90, increasing clockwise -
  which is deliberately not the convention `math.atan2` uses. Horizontal and true
  distance are separate methods, because a diver forty metres below a hull is
  nearly zero metres away for navigation and forty for proximity. A region is a
  coordinate space rather than a label: a lake and an ocean may both have a point
  at (0, 0), so operations across regions raise instead of returning a
  meaningless number. Non-finite coordinates are refused at construction.
- Add settings resolution. Games configure maritime from their own `settings.py`
  using `MARITIME_`-prefixed names, never by editing contrib source.
  `MARITIME_TIME_PROVIDER` takes a dotted path so a game can substitute its own
  clock, and `MARITIME_RNG_SEED` pins the master seed for a reproducible run.
  A configured class that is the wrong type fails at load with a message naming
  the setting, rather than surfacing later as a missing attribute. Defaults are
  derived from `__package__`, so they resolve wherever the package actually lives.
- Add domain events and `EventBus`. The simulation announces what happened without
  knowing who listens; messaging, AI, quests, economy, logging and tests subscribe.
  Subscribing to a base event type also receives its subtypes, so a logger can take
  everything with one registration. A handler that raises is logged and skipped
  rather than propagating - a quest script with a bug must not be able to stop a
  vessel from sinking. Delivery iterates a snapshot, so a handler subscribed while
  an event is being delivered does not receive that same event.
- Add `Result`, the structured return value for every domain operation. Frozen and
  keyword-only; a failed result must carry a machine-readable code, so a caller
  always has something to branch on and a renderer always has something to
  translate. Deliberately has no free-form details dictionary.
- Add `RNGContext` and named random streams (`navigation`, `combat`, `damage`,
  `weather`, `ai`). A run replays exactly from its seed, and streams are
  independent so draining one does not shift another. Stream seeds derive from
  SHA-256 rather than the builtin `hash()`, which is salted per process and would
  lose reproducibility across a server restart.
- Add the maritime clock: `MaritimeTimeProvider` interface, `GameTimeProvider`
  reading the host game's own clock via `evennia.utils.gametime`, and
  `ManualTimeProvider` advancing only when told to. Maritime never scales time
  itself, so a vessel's speed means the same thing at any `TIME_FACTOR`.

### Docs

- Carry the north-star roadmap into `docs/architecture.md`. The doc described the
  design well and said almost nothing about the plan: twenty-six phases, the
  vertical-slice gate, the named scenario suite, the invariant list, the
  performance goals and the open questions were all in the specification and none
  of them were in the repository. Each phase now carries its real status, and
  every `partial` names what is missing - a phase marked complete while a named
  deliverable is absent is how a plan stops being a plan.
- Record what the doc describes and the code does not: navigational tiling, hull
  footprints and swept grounding detection, domain event emission, and the narrow
  public API. Each is marked unbuilt where it is described rather than only in a
  limitations list somebody has to go and find.
- State plainly that currents are not implemented. They are an input to the
  documented sailing model and a method on the documented map provider
  interface, and they are neither - so a passage takes the same time whichever
  way the water is moving, and three of the six first-voyage acceptance tests
  cannot be written. Sailing is marked partial accordingly.
- Note that the fourteenth law, which governs the repository rather than the
  simulation, lives in `CLAUDE.md` where it is actually checkable.

- Add `CHANGELOG.md` and record the changelog and commit-message discipline in
  `CLAUDE.md`.
- Add `docs/architecture.md`: the architectural laws, the shared elevation datum
  for land, sea and seabed, vessel representation tiers, fair scheduling, the
  sailing model and the service abstraction. Written game-agnostic - where a
  decision belongs to the host game, it names the seam rather than choosing.
- Add `CLAUDE.md` recording Evennia's contrib guidelines as binding working rules,
  including package layout, the format-sensitive README, testing requirements,
  code style taken from Evennia's own linter config, the core-Evennia-only
  dependency policy, and a 1000-line ceiling per source file.
- Record engine behaviour that Python fluency alone does not protect against:
  typeclass names are unique server-wide, tickers must never poll for changes,
  ticker subscriptions collide without distinct idstrings, and attribute reads
  are cheap while writes and nested mutation are not.
- Document the dual target - merged upstream, or used standalone - and make the
  tutorial zone a deliverable rather than optional polish.

### Chore

- Add `DECISIONS.md`: questions raised while building that are not mine to
  answer, each with what is blocked, what the options look like, and what was
  done in the meantime so nothing stalled.
- Remove a dead special case from weapon arcs. An omni mount had a shortcut for
  its three-hundred-and-sixty degree width; mutation testing pointed out that
  deleting the shortcut changed no behaviour, because an arc that reaches half a
  circle either side of its centre already covers every bearing there is.

- Split `commands.py` into a `commands/` package, one module per station: helm,
  sail, pilotage, lookout and mooring. That is how the design has always
  described them - contextual command groups exposed by cmdset - and doing it at
  sixteen commands is cheaper than doing it when gunnery and damage control
  arrive. Everything is re-exported, so `from .commands import CmdHelm` is
  unchanged.
- The station modules are named for the job rather than for the domain module
  each leans on. `commands/navigation.py` shadows `maritime.navigation` from
  inside the package, which is exactly how the first attempt at this split broke.
- Exempt `messaging.py` from the line ceiling, by name and with the reason
  recorded in the checker. It holds every word a vessel or her crew says; prose
  has no branching, no state and nothing to get wrong, so its length costs
  nothing and splitting it would scatter one voice across several files. Every
  other file is held to the rule exactly as before.

- Record the two ways mutation testing lies, in `CLAUDE.md`. A mutation that does
  not apply is a no-op that prints OK exactly like a survivor - already guarded.
  The new one: Python validates a `.pyc` against source mtime *and size*, so a
  same-length mutation written and restored inside one second leaves bytecode the
  interpreter goes on serving after the file is back. That produced a test
  failing against code that was correct when read, and could as easily have
  hidden a survivor. The harnesses now clear `__pycache__` on restore.

- Move the crew's spoken orders and replies out of `commands.py` and into
  `messaging.py`, alongside the ship's own narration. `MARITIME_NARRATOR` was
  built as the one place a game replaces the prose, and commands were bypassing
  it entirely with seventy-one hardcoded messages - so overriding it changed
  what the *ship* said and left the crew answering in the contrib's words. Two
  voices in one game, and the second unreachable without forking every command.
  A command now says `self.order(vessel, HELM_ORDER, spoken=spoken)` and knows
  that an order was given and who hears it, never what it sounds like.
- Prose has no branching and no state, so the file holding it can grow to any
  length without costing anything. That is why it is the right place for it, and
  why `messaging.py` is exempt from the reasoning that applies to code.

- Compose `Vessel` from the seams the domain modules already draw: `Navigator`
  in `navigation.py`, `Berthing` in `ports.py`, `Lookout` in `observation.py`,
  `Rigged` in `sailing.py`, `Situated` in `environment.py` and `Compartmented`
  in `rooms.py`. Everything about a concern now sits in the file that owns it,
  including the defaults it sets at creation, and the domain modules still
  import nothing from Evennia. `typeclasses.py` goes from 1039 lines to 507 and
  stops growing with every phase.

- Say "take the way off her" once instead of three times. Docked, aground and
  anchored each stopped the tick with the same four lines, which is three places
  for them to drift apart. `held_by()` names which one has her - they are undone
  by three different acts and the distinction is worth keeping - and
  `take_way_off()` does the stopping.
- Record the amended file-size rule in `CLAUDE.md`: a thousand lines unless
  splitting makes no code sense, with the measurement to check before proposing
  one. `typeclasses.py` is 920 lines carrying 99 lines of logic; the rest is the
  docstrings the style guide requires. A `Vessel` split into a mixin of getters
  and setters would have been worse code with a better number.

- Move `ShipRoom` out of `typeclasses.py` into `rooms.py`. A compartment is not
  a vessel, and this is where deck plans, stations, flooding order and
  compartment damage all land. `typeclasses.py` drops from 825 lines to 718.
- `ShipRoom` is deliberately re-exported from `typeclasses`. Evennia writes a
  typeclass to the row as a dotted path, so every compartment already created in
  every game that has run this contrib carries the old module name in its
  database. Dropping the name would not fail at startup - it would produce rooms
  that fail to resolve their typeclass one at a time as they are loaded, which is
  a considerably worse way to find out. Verified against three live rooms whose
  rows still say `typeclasses.ShipRoom`: they resolve to the class in `rooms`,
  `isinstance` holds, and their attributes and commands are intact.
- Export `Vessel` and `ShipRoom` from the package. The two typeclasses a game
  actually installs were reachable only by module path.

- Move the CI actions to `checkout@v5` and `setup-python@v6`. The v4/v5 pair
  targets Node 20, which the runners now force onto Node 24 with a deprecation
  annotation on every build - a warning that is about to become a failure.

- Add CI running `black`, `flake8`, project discipline checks, and the unit tests
  on Python 3.12 and 3.13 with the contrib installed at its canonical import path.
- Add `check_discipline.py` enforcing the rules no general tool knows about: the
  file-size ceiling, the dependency policy, README shape, domain purity (no
  player-facing prose outside the messaging layer), and location independence
  (no absolute self-imports, so the contrib also works standalone).
- Ignore credential and environment files. They belong in the game directory, not
  in this public repository.
- Scaffold the contrib package at `evennia/contrib/full_systems/maritime` with the
  structure the contrib guidelines require. Licensed BSD 3-Clause to match Evennia.
  Line endings normalised to LF so commits made on Windows do not read as
  whole-file rewrites upstream.

### Fix

- Correct the dependency rule and a false positive in its check. Evennia's own core
  dependencies (PyYAML, simpleeval, inflect, the test helpers) ship with Evennia, so
  importing them costs the user nothing - but `import yaml` was failing the build.
