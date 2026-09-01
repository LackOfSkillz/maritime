# The maritime client protocol

> The maritime client is a replaceable view and control surface over the maritime
> simulation. The simulation knows nothing about the browser; the browser knows only the
> player-visible state the simulation deliberately publishes.

> A graphical client must never make the navigator more knowledgeable than the character.

Those two sentences decide every question below. Where a design choice is not obviously
right, the one that keeps them true wins.

---

## What this is, and what it is not

The contrib publishes **structured state**. A reference browser panel consumes it. The
panel is optional; the state is not tied to it.

That split is deliberate and it is the same one the rest of this package makes everywhere
else. There is no skill system here, no faction model and no economy, because the moment a
contrib ships an opinion, every game with its own has to argue with it. A user interface is
the largest opinion there is.

Publishing state rather than an interface also means a player on a telnet client with a
scripting layer gets the same data. A browser-only feature would serve half the audience.

**Maritime remains completely playable as text.** Every control corresponds to an ordinary
command that already worked without it. The panel has no powers a captain speaking aloud
does not have.

---

## Discovery findings

Recorded because they were not obvious and two of them shape the plan.

### The contrib would be the first to ship web assets

No contrib in Evennia ships a `static/` or `templates/` directory. There is no precedent to
point at, and reviewers may reasonably have opinions about JavaScript arriving in a
contribs tree.

The response is phasing rather than argument. The protocol is pure Python, useful on its
own, and lives in the package. The browser assets live in one clearly separable directory.
If they are unwelcome upstream they move to a companion distribution without a line of the
protocol changing.

### Integration needs no change to Evennia

Four steps, all of them the host game's own configuration:

1. The game adds the contrib's static directory to `STATICFILES_DIRS`. The default is
   `[GAME_DIR/web/static]` only, and contribs are not Django applications, so their static
   files are not otherwise discovered.
2. The game overrides `webclient/webclient.html`. That template is about twenty-five lines
   and already exposes an empty `{% block scripts %}`, so the override adds a mount point,
   five script tags and one or two stylesheets, and inherits everything else from
   `webclient/base.html`. The second stylesheet, `maritime-layout.css`, is separable: it
   turns the webclient into a full-window bridge while somebody is aboard, and every rule
   in it is scoped to `:root:has(#maritime-root.maritime-on)`, so a game that leaves it out
   keeps the webclient it has always had and one that includes it gets the screen back the
   moment a player steps ashore. The exact markup is in the readme.
3. The game adds `maritime.client.inputfuncs` to `INPUT_FUNC_MODULES`, so a browser can
   announce itself. A game that skips this still gets everything else; it simply never
   learns which of its sessions are graphical.
4. `evennia collectstatic`.

No file inside an installed Evennia is edited. No Python dependency is added.

### The transport already exists and is documented

Evennia's client protocol carries `[cmdname, args, kwargs]` in both directions.

    server to client   session.msg(maritime_status=(args, kwargs))
    client to server   Evennia.msg("maritime_action", args, kwargs)
    client listener    Evennia.emitter.on("maritime_status", handler)

Custom command names are the supported mechanism, not a trick. A client that does not
recognise one ignores it, which is the fallback behaviour a mixed-client game needs.

### The transport is proven, not theoretical

A production Evennia game was examined for its browser client patterns. It registers
through `plugin_handler.add`, receives state on custom command names through
`Evennia.emitter.on`, sends back through `Evennia.msg`, keeps a catch-all listener for
command names it does not know, and watches `connection_open` and `connection_close` to
survive a reconnect.

That is the same mechanism identified above, in service, at scale. Maritime uses it with
`maritime_`-prefixed names and needs to invent nothing.

Worth borrowing as *lessons* rather than as code: the reconnect listeners, the catch-all for
unknown messages, a preferences round-trip so the client's own settings survive, and map
controls for fit, centre, zoom and fullscreen. Worth not borrowing: the shape. That client
is one JavaScript file of about eleven thousand lines, which is the single best argument for
the file split this document specifies.

### The chart is SVG, and that is a deliberate divergence

The client examined draws its map to a canvas. For a room graph that is a reasonable
choice. For a chart it is the wrong one, and maritime uses SVG instead:

  - A contour is a path. A mark is an element with a label. Both are things SVG already is.
  - Every feature has to be selectable, hoverable and tooltipped. On a canvas that means
    writing hit-testing by hand; in SVG it is a click handler.
  - Accessibility is free in SVG and hand-built on a canvas, and a chart that can only be
    read by looking at it fails a reader who cannot.
  - Styling by class means a host can retheme the chart without touching the drawing code.

The cost is that a very large coastline is a great many path points, which is answered by
culling to the viewport rather than by changing technology.

### The graticule, and how a flat sheet admits the world is round

A chart is a plane and the world is not. The panel does not try to hide that, and it does not
try to draw its way out of it either - what it does is rule the sheet with the meridians and
parallels that genuinely lie on the ground, and let the reader watch them converge.

They are not plotted. A parallel is the line along which latitude equals a round number,
which is exactly what a contour tracer finds, so the graticule is the same marching squares
that draws the coastline run over a grid of degrees instead of a grid of depths. Nothing
approximates the projection; the projection produces the lines. Close in they stand square
and the chart is honest to draw itself flat. At two hundred kilometres they lean by
kilometres, and the world stops looking like a square tile.

It costs the navigator nothing he does not have. Latitude comes from an observation and
longitude from a reckoning; that is his job, and a chart with degrees in the margin is the
ordinary tool for doing it.

Like the relief, it degrades rather than demands. `MaritimeMapProvider.geographic_at`
answers None by default, so a seabed defined by an arithmetic ramp - which is not *anywhere*
- draws no graticule at all rather than inventing a latitude for a game that never named
one. A world that knows where it is overrides the method and gets ruled lines for free.

### An island is not a drying rock

Three states, and they were one flag. `dries` used to mean "above chart datum", so an island
twelve metres high reached the client saying that it dried twelve metres - which is not a
sentence any chart has ever contained.

The tide is watched over a full tidal day and each danger classified by what the water
actually does to it:

    ashore      the sea never covers it        an islet, a mole, a headland
    dries       bare at low water, covered at high    the rock a tide table is for
    neither     it never shows                  a pinnacle, a bar, a wreck

A game with no tide gets nothing drying, and that is right rather than a gap: on a
motionless sea nothing covers and uncovers, because nothing moves. The classification is
measured rather than declared, so it holds for a harmonic tide, a story-driven flood, or
none at all, without a tide provider having to implement anything new.

### Shaded relief is offered, never required

The contrib has no dependencies and that is a design guarantee. One thing sits outside it,
deliberately and visibly: the chart's shaded relief needs `numpy`, `scipy` and `Pillow`, and
a game that installs them gets the shape of the bottom lit beneath its contours while a game
that does not gets exactly the interface it always had.

That shape - offer the trade to the developer rather than take it on their behalf - is the
only reason a dependency is acceptable here at all. It is enforced rather than trusted: CI
fails on an unguarded import of any of the three, because a hard dependency wearing an
optional label is the failure nobody notices, working perfectly on the machine of whoever
added it.

It is shaded from the **charted** grid, never the real seabed. The relief of a poor chart is
as wrong as its soundings and in the same places, which it has to be - the rule below about
the panel being a repeater and not an oracle applies to a picture exactly as it does to a
number.

### Theming composes

The client examined already themes with CSS custom properties. Maritime publishing its own
`--maritime-*` palette therefore sits inside a host's shell without inheriting it, and a
host that wants the chart to match its own colours overrides the variables rather than
editing anything here.

Artwork composes the same way and on the same terms. This contrib ships no images and the
interface is finished without any; what it provides is the fitting they screw into, so a
host game points `--maritime-profile-<plan>` at files of its own and touches nothing else.
Absence needs no guard, which is the reason it is done with variables at all: an unset
custom property falls back to `none`, `background-image: none` draws nothing, and every
artwork block has zero height until `--maritime-artwork-height` switches the lot on. A
missing asset is therefore not an error to handle or a broken image to hide - it is simply
not drawn, and a host that supplies three sail plans out of six gets pictures for three and
unchanged text for the other three.

The blend mode is load-bearing rather than decorative. Art of this kind generates far more
reliably on a black ground than with a transparent one, and `screen` maps black exactly to
the backdrop - so an ordinary opaque PNG composites as though it had been cut out, with no
alpha channel and no tooling in between. A host whose artwork *is* cut out sets
`--maritime-artwork-blend: normal`.

A game with more than one sort of ship keys its artwork by class. The payload carries her
`template_key` - the identifier of the `VesselTemplate` she was built from, which the host
game chose - and the drawing carries it as `data-template`, so a stylesheet can scope the
same variables per class:

    .maritime-profile[data-template="brig"] {
        --maritime-profile-full: url("/static/art/brig/full.png");
    }

That value is relayed and never interpreted. This contrib does not know what a brig is and
must never acquire a list of the classes it recognises, because a taxonomy of ships belongs
to the host game and would be wrong the moment somebody invented a hull nobody here had
thought of. It is also the only honest way an interface can know: a rig here is a polar
curve rather than a name, deliberately, since baking one curve in would make every vessel
in every game sail like the same boat.

Her own hull only. A *contact's* class is never published, because what may be told about
another ship is what the lookout has made out - governed by her sighting, never by what
would be convenient to draw. A game that sets no class gets no attribute, and its unscoped
variables apply to every ship it has.

One rule constrains all of it: a picture is not a reading. The sail-plan drawing sits above
the row that names the plan and never replaces it, because the words have to survive a
player with no artwork, a slow connection, or a screen reader.

### Dead reckoning is already the whole point

The hardest rule to hold - that the chart must not become a satellite fix - turns out to be
the module's existing design rather than something to impose on it. `navigation` opens:

> The engine knows exactly where a ship is. The people aboard her do not, and the whole of
> navigation is the gap between those two things.

`Navigator.reckoned_position` exists beside `maritime_position`, and the error is not rolled
but accumulated out of current and leeway. So the payload carries the reckoned position and
never asks for the true one. There is no filtering step that could be forgotten, because the
truth is never fetched.

### Charts already model knowledge, coverage and error

`charts` distinguishes the sea from the paper, records coverage boundaries, and is wrong in
the same places every time by construction. That makes the chart panel *derived* rather than
authored, and makes uncharted water render as absence rather than as empty sea.

---

## Rules

**The panel is a repeater, not an oracle.** It shows what `contacts()` returns at that
height of eye, so an unidentified hull is a bearing-only mark. It cannot leak what the
fiction has not granted, because it is never told.

**Two layers, and they must not be confused.**

    charted   persistent   land, soundings, marks, hazards, from `charts`
    sighted   volatile     other vessels, from `contacts()`

Hazards were the last of those to arrive and are the only ones that do not come from the
soundings. They cannot: a chart samples the seabed on a grid, and anything narrower than
the grid is *missed* rather than smoothed - and missed differently depending on where the
grid falls, so the danger would appear and vanish as she sailed. The provider is asked for
them directly, through `charted_dangers`, and a symbol is how a chart says "here, exactly".
Which is what real charts do with an isolated danger, for the same reason.

Charted things stay because somebody wrote them down. Sighted things exist only while the
lookout has them. A contact that outlived the sighting would be a radar repeater and would
undo detection exactly as a true-position marker would undo navigation.

**The interface is composed from the hull.** No ship's company, no crew panel. One paddling
position, no helm. No rig, no sail panel. No guns, no battery. This is the rule
`Handled.hands_to_work_her` already follows when it refuses to invent a crew for a hull that
has none.

**Readings appear because they are true here.** No water-body taxonomy. A pond reports no
tide because there is no tide, not because it was classified. A tidal river reports both
tide and current because both are true, which a taxonomy would have made a special case.

**The server stays authoritative.** The browser computes screen geometry and nothing else.
Every action revalidates on arrival, against the same authority check a typed command
passes, because a determined user will call the functions by hand.

**Never scrape text.** The narration layer and the panel are two consumers of the same
state, not one derived from the other.

**Fail soft.** A missing reading is an absent field, a broken panel is a missing panel, and
neither stops the ship. A player whose JavaScript died is a player sailing by text.

---

## Phases

    MC-1   protocol, capability, context resolver, mode payload, full sync   DONE
    MC-2   shell: mount, unmount, telemetry strip, placeholder panels
    MC-3   live instruments, proving heading and course made good differ
    MC-4   chart viewport: transform, own vessel, pan, zoom, fit, fullscreen
    MC-5   navigational knowledge: contours, route, marks, hazards
    MC-6   contacts, appearing and disappearing with the lookout
    MC-7   controls, each equivalent to a command
    MC-8   role-sensitive presentation
    MC-9   extension points for systems not yet built
    MC-10  hardening: reconnect, resize, malformed payloads, old protocol

MC-1 is entirely Python and testable without a browser, which is why it is first.

---

## Open questions

- Whether the reference panel ships here or separately. Deferred until there is something
  to move.
- Whether a lost contact leaves a fading last-known bearing, which is what a navigator
  would actually plot, or simply goes.
- Whether a game may supply an authored coastline instead of a contoured one. A provider
  seam, not a rewrite.
- Whether a game may hint at a preferred presentation, overriding what is derived.
- Chart orientation on rivers, where north-up is mostly bank and heading-up is the useful
  view.
