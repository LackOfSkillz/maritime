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

Three steps, all of them the host game's own configuration:

1. The game adds the contrib's static directory to `STATICFILES_DIRS`. The default is
   `[GAME_DIR/web/static]` only, and contribs are not Django applications, so their static
   files are not otherwise discovered.
2. The game overrides `webclient/webclient.html`. That template is about twenty-five lines
   and already exposes an empty `{% block scripts %}`, so the override adds script tags and
   a mount point and inherits everything else from `webclient/base.html`.
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
