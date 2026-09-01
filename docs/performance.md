# What a tick costs, and what the reactor can afford

The design listed the reactor budget as an open question: *"the actual millisecond budget
that is safe on a production server. The current batch size is a stand-in for a measurement
nobody has taken."* This is the measurement.

Taken against the testbed's real database with real typeclasses, on a Windows development
machine, with `perf_counter` and twelve passes per figure reported as the median. Absolute
numbers will differ on your hardware; the *ratios* are the point, and they are what the
design decision rests on.

---

## The headline

**A fixed batch of 25 is somewhere between 6.5 ms and 33 ms of reactor time, and nothing
about the number 25 tells you which.**

| world | ms per vessel | a batch of 25 costs |
| --- | --- | --- |
| flat sea, becalmed, nobody about | 0.26 | 6.5 ms |
| flat sea, sailing | 0.44 | 11.0 ms |
| flat sea, sailing, 20 in sight | 0.62 | 15.5 ms |
| tiled seabed, sailing | 1.34 | 33.5 ms |
| tiled seabed, sailing, 20 in sight | 0.83 | 20.8 ms |
| tiled seabed, sailing, 50 in sight | 1.07 | 26.8 ms |

A five-fold spread between the cheapest vessel and the dearest. Twisted runs everything in
one thread, so 33 ms is 33 ms in which no command is processed, no login completes and no
other script runs. A batch count cannot protect against that because it does not know what
a vessel costs — only a clock does.

So the pass is now bounded twice:

```text
batch size    how many entities one pass will look at   (backstop)
time budget   how long one pass will take               (the real limit)
```

`MARITIME_TICK_BUDGET_MS` defaults to **10 ms**. At the measured costs that serves between
7 and 38 vessels a pass, which for any realistic fleet is one or two passes.

Two rules the implementation had to get right:

- **The budget is checked after an update, never before.** Checking first would let one slow
  vessel starve herself out of the rotation permanently — a livelock, not a limit. At least
  one entity always runs.
- **Whatever the pass never reached is wound back onto the rotation.** `next_batch` advances
  the cursor over the whole batch; without `rewind`, a pass stopped early would skip its
  untouched tail and those vessels would wait a full circuit. That is exactly the unfairness
  the cursor exists to prevent, and a test caught it.

---

## Three bugs the measurement found

Neither would have been found by reading the code, which is the argument for measuring.

### `monotonic` cannot see a ten-millisecond budget

The first implementation used `time.monotonic()`. On Windows that ticks at about **15.6 ms**
— coarser than the budget it was meant to enforce, so a 10 ms limit would never once have
fired. The benchmark's first run made it obvious: four of six cases read exactly `0.00 ms`
and the rest read exactly `16.00`.

`time.perf_counter()` is the right clock for short intervals and is what both the service
and the benchmark now use.

### The tile cache was being thrown away every call

`config.map_provider()` built a **fresh provider on every call**, on the documented grounds
that "providers hold no state worth sharing". That was true when it was written and stopped
being true the moment tiles landed: a `TiledMapProvider` caches the squares it has loaded,
and rebuilding it discarded that cache every time anything asked the depth of anything.

It surfaced as an anomaly rather than as a slowdown — a tiled world costing *more* per
vessel with one ship on it than with twenty, which is not a thing that can be true.

Measured directly, five ticks of one vessel under sail:

```text
one provider, kept        3 tile loads
a fresh one per call      6 tile loads
```

Halved here, and the ratio grows with a finer grid or a more expensive tile source. For a
vessel lying at anchor it is the difference between one load ever and one load per tick,
forever.

The map provider is now kept, keyed on the settings that made it, so changing a setting
still yields a new one and a test using `override_settings` is never handed the old one.
`config.forget_map_provider()` drops it on purpose. Every other provider is still built per
call, deliberately — they hold nothing.

### The chart was contoured thirty times for every one that was sent

`broadcast_status` drew a sheet on every tick and *then* decided whether to send it:

```python
drawn[reach] = chart_for(vessel, reach)     # every tick
stamp = (reach, sheet.revision)
if session.ndb.maritime_chart_stamp == stamp:
    continue                                 # only skips the send
```

The driver ticks every two seconds; a chart's revision turns every sixty. So twenty-nine
drawings in thirty were built and discarded. The comment above that code said it stopped
exactly this from happening, which is a fair part of why it lasted.

Against a hand-written seabed it was invisible — a sheet costs about eighteen milliseconds
there, and forty ticks a minute of it is under one per cent of a core. It only became
visible against a **generated** world, where one sheet is the better part of a second.
Measured over five minutes of a voyage, at the default two-second tick:

```text
                        sheets drawn    contouring
before                          150        113.1 s
after                             5          3.8 s

continuous load, per crewed vessel
before                       37.7 % of a core
after                         1.3 %
```

The revision is arithmetic on the clock and needs no sheet to compute, so the gate moved
ahead of the drawing. What is sent is unchanged: the first tick of a new revision draws and
sends exactly the sheet it always did.

Gating on time alone would have introduced a regression — a chart bought or unrolled
halfway through a minute would have stayed invisible until the minute turned, where the old
code noticed at once because it redrew everything anyway. Which chart she is reading is part
of the stamp now, so that stays immediate; asking is a scan of the few charts aboard, while
drawing one is nine thousand soundings.

This is the bug that matters most for a game supplying real bathymetry, and it is the reason
a costly map provider is affordable at all: the expensive question is now asked once a
minute rather than thirty times a minute.

---

## What this does not answer

- **Real hardware.** These are development-machine numbers. A game expecting a large fleet
  should re-run the benchmark on the box it will actually run on; the ratios should hold
  and the absolute figures will not.
- **The strategic tier.** Everything here is `ACTIVE`. Strategic vessels advance
  analytically and should be far cheaper, but that has not been measured because the
  strategic tier is not built.
- **Contention.** Measured with nothing else running. A production server is doing other
  things, and the budget is a share of a reactor rather than the whole of it.
- **Whether 10 ms is the right default for your game.** It is a defensible one, and
  `MARITIME_TICK_BUDGET_MS` exists because the answer depends on what else your server is
  doing.

---

## Running it yourself

The benchmark is not shipped as a test — it measures wall clock, and a timing assertion on
a loaded build machine is a flaky test rather than a useful one. What *is* shipped is
`tests/test_budget.py`, which asserts the behaviour the measurement justified: that a pass
stops, that at least one entity always runs, that the tail is wound back, and that the
provider is kept.
