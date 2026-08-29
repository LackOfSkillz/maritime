# Ship's orders

The command vocabulary, drawn from period usage rather than invented. Sources are the
1867 *Sailor's Word-Book* for age-of-sail orders and IMO Standard Marine Communication
Phrases for helm procedure, which is still in use and barely changed.

This is a working list, not a wish list. Roughly twenty orders covers a ship — a player
should be able to sail competently without a glossary, and every entry here earns its
place by doing something the simulation actually models.

**On procedure.** An order is called out, repeated back, and reported when carried out:

```text
> helm 090
You call out, "Helm, steer 0-9-0."
The helmsman answers, "Steering 0-9-0 now, sir."
    ...
The helmsman reports, "Vessel steady on 0-9-0 now, sir."
```

Courses are always spoken digit by digit and in three figures. *Ninety* and *one-nine-zero*
are dangerously easy to confuse across a windy deck; *zero-nine-zero* is not, and that is
why the convention exists rather than being decoration.

**Every order gets an answer. This is a rule, not a flourish.**

The reply is what makes a vessel feel crewed rather than driven. An order that returns a
silent state change is a control panel; an order that is called out, repeated back, and
reported on completion is a ship with people on her. It costs one line of code and it is
the single largest difference between the two.

So: no new order ships without a spoken acknowledgement, and where the result takes time,
a report when it is done. If nobody would answer it aloud, it is probably a query and
belongs under Reports instead.

The acknowledgement also carries information the player needs. "She is carrying more than
she should in this, sir" after setting full sail in a rising wind is a warning delivered in
character, which beats a mechanical notice about a threshold being exceeded.

---

## Steering

| Order | Meaning | Status |
| --- | --- | --- |
| `helm <bearing>` | Steer a compass course | **done** |
| `steady` / `steady as she goes` | Hold the present heading | planned |
| `hard a-port` / `hard a-starboard` | Full rudder, without a course | planned |
| `ease the helm` | Reduce rudder angle | planned |
| `meet her` | Check the swing as she comes round | planned |
| `luff` | Bring her closer to the wind | planned |

`steady as she goes` is worth having early: it is how a conning officer holds whatever
heading a vessel happens to be on, without reading it off first.

## Sail handling

| Order | Meaning | Status |
| --- | --- | --- |
| `sail <plan>` | Set a named plan of canvas | **done** |
| `make sail` | Increase canvas by one step | planned |
| `shorten sail` | Reduce canvas by one step | planned |
| `take in a reef` | Reduce, specifically by reefing | planned |
| `shake out a reef` | The reverse | planned |
| `furl` / `hand sail` | Take in everything; bare poles | planned |
| `let fall` | Drop and set the sails | planned |

`make sail` and `shorten sail` are the ones a player will actually reach for. They step
through the plans, so nobody has to remember whether *reefed* is more or less than
*working* — the ship knows.

## Manoeuvres

| Order | Meaning | Status |
| --- | --- | --- |
| `ready about` | Warn the hands to prepare to tack | planned |
| `about ship` / `tack` | Bring her head through the wind | planned |
| `let go and haul` | The moment of the tack | planned |
| `wear ship` | Turn away through the wind instead | planned |
| `heave to` | Stop by setting sail against helm | planned |

**Tacking is where the wind model becomes gameplay.** A vessel cannot sail into the wind,
so making ground to windward means beating — a zigzag of alternating boards. Tacking
crosses the wind with the bow, which is fast but can fail and leave her *in irons*; wearing
turns away instead, which always works but gives up ground. That trade is the whole
decision, and both outcomes already fall out of the model.

## Ground tackle

| Order | Meaning | Status |
| --- | --- | --- |
| `drop anchor` / `let go the anchor` | Bring up | **done** |
| `weigh anchor` | Break the anchor out and get under way | **done** |
| `veer cable` | Pay out more cable in a blow | planned |

## Reports

| Order | Meaning | Status |
| --- | --- | --- |
| `position` | Latitude, longitude, course and speed | **done** |
| `wind` | Where it is from, and how she lies to it | **done** |
| `sail` | What canvas is set and what she can make of it | **done** |
| `sound` | Depth of water under her | planned |
| `all hands` | Summon the watch below | planned |

## Deliberately not included

`avast`, `belay`, `pipe down`, `sheet home`, `brail up`, `clew up`, `down killock`. All
genuine, none modelled — an order that does nothing is worse than an order that does not
exist, because a player will spend time working out what they did wrong.

They can be added the moment there is something for them to do. `clew up` and `sheet home`
belong with individual sail control; `avast` and `belay` belong with crew tasks that take
time to complete.

---

## Sources

- [*The Sailor's Word-Book*, 1867](https://historyundusted.wordpress.com/2013/10/26/from-the-1867-sailors-word-book-nautical-orders/)
  — period orders as actually called.
- [IMO Standard Marine Communication Phrases](https://captainsmode.com/standard-helm-orders-meaning-execution/)
  — helm orders and the repeat-back, still current.
- [Age of Sail](https://en.wikipedia.org/wiki/Age_of_Sail) — general background on
  handling and manoeuvre.

## A note on other eras

The plan is not to make this list steam- or diesel-aware. Engine order telegraph
commands — *ahead full*, *back one third*, *all stop* — are a different vocabulary
attached to a different propulsion system, and `PropulsionSystem` is already the seam for
that. A game with aircraft carriers supplies its own orders and its own propulsion; this
contrib should not try to be both at once.
