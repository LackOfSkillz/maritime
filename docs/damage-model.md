# The damage model

What phase 17 is going to be, written down before it is built, because the shape of it was
worked out by reading the source carefully once and it should not have to be read again.

Nothing here is copied. The source's tables are its own; what follows is the *structure*
underneath them, which is the part worth having, restated in our terms and with our
geometry doing the work its hexes used to do.

---

## Damage arrives on two channels, and only one of them is fast

**Attrition** accumulates. It is the bulk of gunnery, it is predictable, and it is never by
itself decisive. This is what gives a captain time to decide something.

**Criticals** are rare, qualitative and specific: a mast down, a gun dismounted, the
steering smashed, a hole at the waterline, an ember in the rigging.

The rule that makes the whole thing work:

> **A critical opens a process. It never concludes one.**

The worst hull result the source has is a great hole below the waterline plus a heavy
ongoing leak. It is not a sinking. It is a sinking *in progress*, and the crew get to fight
it. Sinking is only ever the end of a process somebody lost, and never the outcome of a
single roll. Everything in `F` (fire) and `G` (flooding) is downstream of this one sentence.

## Each track is a ladder, and the rungs are legible

A track is not a bar that empties. It is a short flight of steps, and **each step announces
itself as a different kind of trouble**. Roughly:

    hull        ~10 steps    stores soaked -> a leak that accelerates -> speed lost -> she founders
    crew         ~4 steps    fire most guns -> fire half -> fire none -> SHE STRIKES
    rigging      ~5 steps    sail power falls in fifths until there is none
    oars         ~4 steps    oared power falls in quarters until there is none
    exhaustion   ~5 steps    no effect, no effect, no ramming speed, no battle speed, stopped

Two things matter far more than the step counts:

**The hull ladder is long, and the leak accelerates as you descend it.** Nine rungs of
visible, survivable trouble before the tenth. A ship being reduced can watch it happening.
That is the whole answer to "one shot and she is flotsam" - the answer is structural, not a
tuning constant.

**The crew ladder ends in surrender, not death.** This is the single most important thing in
the source's damage model and it is easy to miss. A ship whose people are shot to pieces
*strikes her colours*; she does not sink and her crew are not annihilated. Which means:

- The normal outcome of losing a fight is **being taken**, not being killed
- Grape fills the crew track fastest, so **the ammunition triangle is a choice of ending**:
  ball takes ten rungs to sink her, grape takes four to make her yours
- Capture is the *cheaper* win, which is what makes item `I` load-bearing rather than a
  finishing touch

A player who loses a battle is therefore usually alive, ashore, and short one ship. That is
a setback with a story in it, and it is why this model can be lethal without being cruel.

**Effects are cumulative.** Nothing resets on the way down.

## Criticals: one table, six severities, applied as an offset

The source does not keep a table per severity. It keeps *one* table per damage type and
shifts where you land on it by a number attached to the severity. Least severe shifts you
far down into the harmless end; most severe shifts you up into the ruinous one.

So severity is a single integer, and the qualitative results are authored once. That is
cheap to build and cheap to balance, and we should do the same.

**The low end of every table is nothing happening** - a shot that whistles through the
rigging and startles the captain. Most criticals are narration. That distribution is what
keeps the model from being lethal, far more than any damage constant does.

## The details worth keeping

- **A hit at the waterline produces a rate, not a quantity.** Damage per turn, continuing.
  That rate *is* flooding, and pumping is what opposes it. `Buoyancy` already carries a sink
  rate with nothing driving it; this is what drives it.
- **Fire needs something to light.** The source only rolls for fire if there is fire aboard
  to begin with - incendiary weapons, firearms, or *the galley fire*. An ordinary cooking
  fire is why an ordinary shot can start a blaze, which is a lovely reason and free to model.
- **An explosion needs a magazine.** A ship carrying no powder cannot blow up, and the
  chance rises steeply with severity for one that does.
- **Rigging comes down in proportions, not in units.** A quarter of her rigging, a half, all
  of it. Masts are lost as fractions of sail power, which is exactly what our polar curve
  wants as input.
- **Battle sails reduce critical severity by one degree** as well as halving rigging damage,
  at the cost of half her speed. We modelled the speed and the halving; we did not model the
  severity reduction, and it is the better half of the trade.
- **Ship's boats are destroyable objects**, named in the criticals. This matters beyond
  flavour: boats are how people survive a foundering, so shooting them away has a
  consequence that outlives the battle. See the offline-player ruling in `DECISIONS.md`.
- **Losing the helm is not damage.** Several results simply take away steering for a turn or
  two - she runs on her present course whether you like it or not. A ship intact and
  uncontrollable is a state worth being able to reach.

## What we do differently, and why it is better

The source reads contact and arcs off hex adjacency. We have continuous coordinates and real
relative geometry, so every place it consults a table we take a measurement:

- Point of impact is the actual angle between her heading and the line of fire, so **raking
  falls out for free** rather than being a table entry
- Boarding frontage is computed from two hulls' length, beam, heading and position, rather
  than from how many hexsides touch
- Damage scales per tonne of the ship receiving it, so a broadside is decisive against a boat
  and an irritation to a first-rate, with no size table

The ladders, the two channels, the surrender ending and the offset-severity trick are the
parts worth taking. The geometry is ours and is better.
