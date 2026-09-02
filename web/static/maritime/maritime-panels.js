/*
 * The instrument strip and the panels beneath the chart.
 *
 * Two rules run through everything here, and both come from the contrib rather than
 * from taste.
 *
 * A reading appears because it is true *here*. There is no water-body type: a pond
 * reports no tide because there is no tide to report, and a tidal river reports both
 * tide and current because both are true. A field the server did not send is a field
 * that is not drawn, rather than one drawn holding a dash.
 *
 * A panel appears because the hull has the thing. A kayak has no crew, no rig and no
 * guns, so she has no crew, sail or battery panel - not a disabled one. This is the
 * same rule the simulation already follows when it refuses to invent a ship's company
 * for a hull that has none.
 */

window.MaritimePanels = (function () {
    "use strict";

    /* The instrument strip, in the order a helmsman reads it. Each names the field it
     * comes from; anything the server has not sent is skipped entirely.
     *
     * Heading and course made good are deliberately separate and deliberately adjacent.
     * They are different quantities - one is where she points, the other where she is
     * actually going - and the gap between them is the whole of what the water is
     * doing to you. Collapsing them into one reading would be the single most
     * misleading thing this interface could do. */
    var READINGS = [
        { field: "heading", label: "HEADING", format: bearing },
        { field: "ordered_heading", label: "ORDERED", format: bearing },
        { field: "speed_through_water", label: "SPEED", format: knots },
        { field: "course_made_good", label: "CMG", format: bearing },
        { field: "speed_over_ground", label: "OVER GROUND", format: knots },
        { field: "wind_from", label: "WIND", format: windFrom },
        { field: "current_set", label: "CURRENT", format: currentSet },
        { field: "charted_depth", label: "DEPTH", format: depth },
        { field: "sail_plan", label: "SAIL PLAN", format: title },
        { field: "sea_state", label: "SEA", format: title },
        { field: "anchor", label: "ANCHOR", format: title },
        { field: "hull", label: "HULL", format: percent }
    ];

    /* Panels, each with the state that has to be present before it is offered. */
    var PANELS = [
        { key: "helm", label: "Helm", needs: null },
        { key: "sails", label: "Sails", needs: "sail_plan" },
        { key: "crew", label: "Crew", needs: "company" },
        { key: "cargo", label: "Cargo", needs: "cargo" },
        { key: "battery", label: "Battery", needs: "battery" },
        { key: "contacts", label: "Contacts", needs: null },
        { key: "navigation", label: "Navigation", needs: null }
    ];

    /* Whatever the payload says the game calls its units. Never guessed: a game that
     * sounds in metres must not be shown fathoms because a browser assumed. */
    var units = { distance: "leagues", depth: "fathoms" };

    var METRES_PER_FATHOM = 1.8288;
    var METRES_PER_SECOND_PER_KNOT = 1852.0 / 3600.0;

    var POINTS = [
        "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"
    ];

    function setUnits(given) {
        if (given) {
            units.distance = given.distance || units.distance;
            units.depth = given.depth || units.depth;
        }
    }

    function bearing(value) {
        if (typeof value !== "number") {
            return String(value);
        }
        var whole = Math.round(value) % 360;
        return (whole < 100 ? (whole < 10 ? "00" : "0") : "") + whole + "°";
    }

    function compass(value) {
        return POINTS[Math.round((value % 360) / 22.5) % 16];
    }

    function knots(value) {
        if (typeof value !== "number") {
            return String(value);
        }
        return (value / METRES_PER_SECOND_PER_KNOT).toFixed(1) + " kn";
    }

    /* Wind is named for where it comes *from* and current for where it sets *to*.
     * Getting those the wrong way round is the oldest mistake in the book and would
     * put a helmsman on the wrong tack, so each is spelled out rather than both
     * being rendered as a bare bearing. */
    function windFrom(value, status) {
        var speed = status && status.environment ? status.environment.wind_speed : null;
        var named = compass(value);
        return typeof speed === "number" ? named + " " + knots(speed) : named;
    }

    function currentSet(value, status) {
        var drift = status && status.environment ? status.environment.current_drift : null;
        var named = compass(value);
        return typeof drift === "number" ? named + " " + knots(drift) : named;
    }

    function depth(value) {
        if (typeof value !== "number") {
            return String(value);
        }
        if (units.depth === "metres") {
            return value.toFixed(1) + " m";
        }
        if (units.depth === "raw") {
            return value.toFixed(1);
        }
        return (value / METRES_PER_FATHOM).toFixed(1) + " fm";
    }

    function title(value) {
        var word = String(value);
        return word.charAt(0).toUpperCase() + word.slice(1);
    }

    /* Soundness as a percentage, the way the target board reads it. The payload
     * sends how sound she is rather than how hurt, so a bar empties as she is
     * beaten about and nobody has to remember which way round it runs. */
    function percent(value) {
        return typeof value === "number" ? Math.round(value * 100) + "%" : String(value);
    }

    function text(value) {
        return String(value);
    }

    function element(tag, className, textContent) {
        var node = document.createElement(tag);
        if (className) {
            node.className = className;
        }
        if (textContent !== undefined && textContent !== null) {
            node.textContent = textContent;
        }
        return node;
    }

    /* A value somebody can read off a dial: a number, a word, or nothing. Anything
     * else is a group of readings rather than a reading.
     *
     * The distinction is load-bearing because a group and a field may share a name -
     * `anchor` holds the anchor's state - and a search that took the first match found
     * the group and rendered it as "[object Object]" on the strip. Seen in a browser,
     * which is the only place it could have been seen. */
    function isReadable(value) {
        var kind = typeof value;
        return kind === "string" || kind === "number" || kind === "boolean";
    }

    /* Pull a reading out of the status payload, wherever the server grouped it.
     * Returns undefined when it is genuinely absent, which is what decides whether the
     * instrument is drawn at all. */
    function reading(status, field) {
        if (!status) {
            return undefined;
        }
        var groups = ["motion", "environment", "propulsion", "anchor", "condition"];
        if (isReadable(status[field])) {
            return status[field];
        }
        for (var i = 0; i < groups.length; i++) {
            var group = status[groups[i]];
            if (group && isReadable(group[field])) {
                return group[field];
            }
        }
        return undefined;
    }

    /* Her name and what she is, at the head of the board. The target design leads
     * with this and it is right to: a captain with two ships needs to know which one
     * he is looking at before he reads a single number off it. */
    function renderIdentity(state) {
        var who = (state.status && state.status.vessel) || {};
        var block = element("div", "maritime-identity");

        /* A slot for a host game's emblem, on the same terms as every other picture
         * here: an unset variable draws nothing and takes no width, so a game with no
         * artwork gets the name where the name has always been. */
        var emblem = element("div", "maritime-artwork maritime-emblem");
        emblem.setAttribute("aria-hidden", "true");
        block.appendChild(emblem);

        var named = element("div", "maritime-named");
        named.appendChild(element("div", "maritime-ship-name", who.name || "—"));
        block.appendChild(named);

        /* Her class leads the description when the game published one, because "cutter"
         * tells a captain more at a glance than "18 metres" does. */
        var described = [];
        if (state.mode && state.mode !== "command") {
            described.push(state.mode);
        }
        if (who.template) {
            described.push(title(who.template));
        }
        if (typeof who.length === "number") {
            described.push(Math.round(who.length) + " metres");
        }
        named.appendChild(
            element("div", "maritime-ship-class", described.join(" · ") || "under command")
        );
        return block;
    }

    function renderStrip(state) {
        var strip = element("div", "maritime-strip");
        strip.setAttribute("role", "group");
        strip.setAttribute("aria-label", "Vessel instruments");
        strip.appendChild(renderIdentity(state));

        var drawn = 0;
        for (var i = 0; i < READINGS.length; i++) {
            var spec = READINGS[i];
            var value = reading(state.status, spec.field);
            if (value === undefined || value === null) {
                continue;
            }
            var cell = element("div", "maritime-reading");
            cell.appendChild(element("span", "maritime-reading-label", spec.label));
            cell.appendChild(
                element("span", "maritime-reading-value", spec.format(value, state.status))
            );
            strip.appendChild(cell);
            drawn += 1;
        }

        if (!drawn) {
            /* Aboard, but the server has not sent instruments yet. Say so plainly
             * rather than drawing ten empty dials, which would look like a ship whose
             * instruments had all failed at once. */
            var waiting = element("div", "maritime-reading");
            waiting.appendChild(element("span", "maritime-reading-label", "VESSEL"));
            waiting.appendChild(
                element("span", "maritime-reading-value maritime-unknown", "awaiting report")
            );
            strip.appendChild(waiting);
        }

        /* The target board ends with the time and the state of the tide. Neither is
         * published - the simulation has a clock and tides, but the payload has never
         * carried either - so the cell is drawn and plainly marked rather than filled
         * with a browser's own idea of what time it is aboard a ship in another
         * world. */
        var clock = element("div", "maritime-reading maritime-placeholder");
        clock.appendChild(element("span", "maritime-reading-label", "TIME & TIDE"));
        clock.appendChild(element("span", "maritime-row-value", "not wired"));
        strip.appendChild(clock);

        return strip;
    }

    /* Whether the hull has the thing a panel is about.
     *
     * A group counts as well as a single reading: her company is a block of several
     * facts rather than one number, and a crew panel that waited for a scalar named
     * "crew" would never appear on any ship. */
    function has(state, what) {
        if (what === null) {
            return true;
        }
        if (reading(state.status, what) !== undefined) {
            return true;
        }
        var group = state.status && state.status[what];
        return !!(group && typeof group === "object" && Object.keys(group).length);
    }

    function offered(state) {
        var out = [];
        for (var i = 0; i < PANELS.length; i++) {
            if (has(state, PANELS[i].needs)) {
                out.push(PANELS[i]);
            }
        }
        return out;
    }

    function renderTabs(state, onSelect) {
        var wrapper = element("div", "maritime-card");
        var tabs = element("div", "maritime-tabs");
        tabs.setAttribute("role", "tablist");

        var available = offered(state);
        var active = state.preferences.panel;
        var names = available.map(function (panel) {
            return panel.key;
        });
        if (names.indexOf(active) === -1) {
            active = names.length ? names[0] : null;
        }

        available.forEach(function (panel) {
            var tab = element("button", "maritime-tab", panel.label);
            tab.type = "button";
            tab.setAttribute("role", "tab");
            tab.setAttribute("aria-selected", panel.key === active ? "true" : "false");
            tab.addEventListener("click", function () {
                onSelect(panel.key);
            });
            tabs.appendChild(tab);
        });

        wrapper.appendChild(tabs);
        return wrapper;
    }

    /* --- panel bodies ------------------------------------------------------ */

    function row(label, value, className) {
        var line = element("div", "maritime-row" + (className ? " " + className : ""));
        line.appendChild(element("span", "maritime-row-label", label));
        line.appendChild(element("span", "maritime-row-value", value));
        return line;
    }

    /* A bar that empties as she is hurt. The payload reports how sound a thing is
     * rather than how broken, so there is never a question about which way it runs. */
    function bar(label, soundness) {
        var percentage = Math.round(soundness * 100);
        var line = element("div", "maritime-bar");
        line.appendChild(element("span", "maritime-row-label", label));

        var track = element("div", "maritime-bar-track");
        var fill = element("div", "maritime-bar-fill");
        fill.style.width = percentage + "%";
        if (soundness < 0.35) {
            fill.className += " maritime-bar-critical";
        } else if (soundness < 0.7) {
            fill.className += " maritime-bar-caution";
        }
        track.appendChild(fill);
        line.appendChild(track);

        /* The figure is written out beside the bar, never colour alone. A reader who
         * cannot tell amber from red still has to be able to read his own ship. */
        line.appendChild(element("span", "maritime-row-value", percentage + "%"));
        return line;
    }

    var TRACK_NAMES = { hull: "Hull", rigging: "Rigging", oars: "Oars", weapons: "Battery" };

    /* A titled box inside a deck of them. */
    function section(heading) {
        var box = element("div", "maritime-section");
        box.appendChild(element("div", "maritime-section-title", heading));
        var body = element("div", "maritime-section-body");
        box.appendChild(body);
        return { box: box, body: body };
    }

    /* A reading nothing is wired to yet, saying so.
     *
     * Marked rather than merely blank, because a placeholder that looks like data is
     * one somebody eventually believes - and a captain acting on an invented ETA is a
     * worse outcome than one told the ETA does not exist yet. */
    function placeholder(label) {
        return row(label, "not wired", "maritime-placeholder");
    }

    /* A bar for a thing the simulation does not track.
     *
     * Drawn empty rather than full, and marked, so the shape of the board is visible
     * without a number being invented for it. An empty bar reads as "no reading"; a
     * full one would read as "in perfect order", which is a claim. */
    function placeholderBar(label) {
        var line = element("div", "maritime-bar maritime-bar-unwired");
        line.appendChild(element("span", "maritime-row-label", label));
        line.appendChild(element("div", "maritime-bar-track"));
        line.appendChild(element("span", "maritime-row-value", "not wired"));
        return line;
    }

    /* What the target board shows that this simulation does not model. Listed here so
     * the difference is a line of data rather than a silence: a hull is damaged as a
     * hull, and there is no separate rudder, sail or flooding track to report. */
    var UNTRACKED = ["Rudder", "Sails", "Flooding"];

    /* The helm deck: her condition, what is in sight, and where she is going, side by
     * side rather than one at a time.
     *
     * The instruments are deliberately absent here. Heading, speed and course are on
     * the strip along the top and reading the same number twice on one screen invites
     * the two to disagree - which they will, the moment one of them is refreshed by a
     * path the other is not. */
    function helmBody(state, into) {
        var deck = element("div", "maritime-deck");

        var condition = section("Vessel status");
        conditionBody(state, condition.body);
        UNTRACKED.forEach(function (name) {
            condition.body.appendChild(placeholderBar(name));
        });

        /* Morale is a band and stays a band.
         *
         * The target board shows it as a percentage and this deliberately does not.
         * The simulation bands it on purpose - a captain is told his people are
         * wavering, which he can act on, rather than handed a number to manage - and
         * the payload has never carried the figure. Drawing a bar here would mean
         * inventing the width of it in a browser, which is worse than the words. */
        var company = (state.status && state.status.company) || {};
        if (company.morale) {
            condition.body.appendChild(row("Crew morale", title(company.morale)));
        }
        // Stamina is the character's, and character systems are the host game's.
        condition.body.appendChild(placeholderBar("Stamina"));

        var driving = (state.status && state.status.propulsion) || {};
        if (driving.sail_plan) {
            condition.body.appendChild(row("Sail plan", title(driving.sail_plan)));
            var who = (state.status && state.status.vessel) || {};
            condition.body.appendChild(sailProfile(driving.sail_plan, who.template));
        }
        deck.appendChild(condition.box);

        var near = section("Nearby contacts");
        contactsBody(state, near.body);
        deck.appendChild(near.box);

        var voyage = section("Current voyage");
        voyageBody(state, voyage.body);
        deck.appendChild(voyage.box);

        into.appendChild(deck);
    }

    /* Where she is going, as far as anything here knows.
     *
     * Her ordered course is real and comes off the helm. A destination, an arrival
     * time and a distance to run are not published by the server at all, so they are
     * shown as unwired rather than computed in a browser out of a heading and some
     * optimism - which is exactly the sort of number that would be wrong in fog and
     * believed anyway. */
    function voyageBody(state, into) {
        var motion = (state.status && state.status.motion) || {};
        into.appendChild(placeholder("Destination"));
        into.appendChild(placeholder("ETA"));
        into.appendChild(placeholder("Distance"));
        if (typeof motion.ordered_heading === "number") {
            into.appendChild(row("Course", bearing(motion.ordered_heading)));
        } else if (typeof motion.heading === "number") {
            into.appendChild(row("Course", bearing(motion.heading)));
        }
        into.appendChild(element("div", "maritime-section-subtitle", "Warnings"));
        into.appendChild(placeholder("Hazards"));
    }

    /* Condition, worst first, and only the tracks the server reported. A ship with
     * nothing wrong says so in a sentence rather than showing four full bars. */
    function conditionBody(state, into) {
        var condition = (state.status && state.status.condition) || {};
        var names = Object.keys(condition);
        if (!names.length) {
            return;
        }
        names.sort(function (first, second) {
            return condition[first] - condition[second];
        });
        names.forEach(function (track) {
            into.appendChild(bar(TRACK_NAMES[track] || title(track), condition[track]));
        });
    }

    /* A place for a host game's sail-plan drawing, if it has one.
     *
     * The element is always built and is always empty: it carries no image, and the
     * stylesheet gives it no height, until a host points --maritime-profile-<plan> at
     * a file of its own. That is the whole of the feature on this side - which plan
     * she is under, said in an attribute, for CSS to answer or ignore.
     *
     * It also says what class of hull she is, when the server published one, so a
     * game with more than one kind of ship can draw a brig differently from a cutter.
     * That value is the host's own template key and means nothing here; it is put in
     * an attribute and left entirely to the host's stylesheet to recognise. A game
     * that publishes no class, or has only one sort of ship, simply does not get the
     * attribute and its unscoped variables apply to everything - which is why adding
     * this changed nothing for anyone already using it.
     *
     * Deliberately added *above* the row that names the plan rather than instead of
     * it. A picture is not a reading, and the words have to survive a player who has
     * no artwork, a slow connection, or a screen reader. */
    function sailProfile(plan, template) {
        var figure = element("div", "maritime-artwork maritime-profile");
        figure.setAttribute("data-sail-plan", plan);
        if (typeof template === "string" && template) {
            figure.setAttribute("data-template", template);
        }
        figure.setAttribute("aria-hidden", "true");
        return figure;
    }

    function sailsBody(state, into) {
        var driving = (state.status && state.status.propulsion) || {};
        if (driving.sail_plan) {
            var who = (state.status && state.status.vessel) || {};
            into.appendChild(sailProfile(driving.sail_plan, who.template));
            into.appendChild(row("Set", title(driving.sail_plan)));
        }
        if (driving.anchor) {
            into.appendChild(row("Anchor", title(driving.anchor)));
        }
        var canvas = sailControls(state);
        if (canvas) {
            into.appendChild(canvas);
        }
        conditionBody(state, into);
    }

    function crewBody(state, into) {
        var company = (state.status && state.status.company) || {};
        if (!company.complement) {
            into.appendChild(element("p", "maritime-empty", "She carries no company."));
            return;
        }
        into.appendChild(row("Complement", String(company.complement)));
        if (typeof company.fit === "number" && company.fit !== company.complement) {
            into.appendChild(row("Still standing", String(company.fit), "maritime-attention"));
        }
        if (company.quality) {
            into.appendChild(row("Quality", title(company.quality)));
        }
        if (company.morale) {
            /* The band, never a number. The simulation bands it on purpose: a captain
             * is told his people are wavering, which he can act on, rather than being
             * handed a percentage to manage. */
            into.appendChild(row("Morale", title(company.morale)));
        }
    }

    function navigationBody(state, into) {
        var sea = (state.status && state.status.environment) || {};
        if (typeof sea.charted_depth === "number") {
            into.appendChild(row("Charted depth", depth(sea.charted_depth)));
        } else {
            into.appendChild(element("p", "maritime-empty", "Off the chart. No soundings."));
        }
        if (typeof sea.wind_from === "number") {
            into.appendChild(row("Wind from", windFrom(sea.wind_from, state.status)));
        }
        if (typeof sea.current_set === "number") {
            into.appendChild(row("Current sets", currentSet(sea.current_set, state.status)));
        }
        if (sea.sea_state) {
            into.appendChild(row("Sea", title(sea.sea_state)));
        }
        var tools = controlsFor(state, [
            { key: "sound", label: "SOUND", title: "Cast the lead" },
            { key: "fix", label: "TAKE A FIX", title: "Fix her position" },
            { key: "scan", label: "SCAN", title: "Sweep the horizon" }
        ]);
        if (tools) {
            into.appendChild(tools);
        }
    }

    /* One unit for a whole list, chosen before a line of it is written.
     *
     * A range column exists to be compared down it, and "2.8 miles" above "1.2
     * leagues" gives that up - the reader has to convert before they can tell which
     * is nearer, which is the one job the column has. The server learned this the
     * hard way in its own reports; the browser had quietly reinvented it.
     *
     * Cables for close work are not a competing unit. That is simply how the
     * distance is spoken at that range. */
    function pickScale(ranges) {
        var scale = "cables";
        for (var i = 0; i < ranges.length; i++) {
            var metres = ranges[i];
            if (typeof metres !== "number") {
                continue;
            }
            if (units.distance === "metric") {
                return "metric";
            }
            if (units.distance === "leagues" && metres >= 5556) {
                scale = "leagues";
            } else if (metres >= 1852 && scale !== "leagues") {
                scale = "miles";
            }
        }
        return scale;
    }

    function range(metres, scale) {
        if (typeof metres !== "number") {
            return String(metres);
        }
        var using = scale || pickScale([metres]);
        if (using === "metric") {
            return (metres / 1000).toFixed(1) + " km";
        }
        if (using === "leagues") {
            return (metres / 5556).toFixed(1) + " leagues";
        }
        if (using === "miles") {
            return (metres / 1852).toFixed(1) + " miles";
        }
        return Math.round(metres / 185.2) + " cables";
    }

    /* Bearing and range, because that is what a lookout calls down. A hull nobody has
     * made out is described as what she looks like and nothing more - the server never
     * sent a name, so there is none here to leak. */
    function contactsBody(state, into) {
        if (!state.contacts || !state.contacts.length) {
            into.appendChild(element("p", "maritime-empty", "Nothing in sight."));
            return;
        }
        var scale = pickScale(
            state.contacts.map(function (contact) {
                return contact.range;
            })
        );
        state.contacts.forEach(function (contact) {
            var line = element("div", "maritime-contact");
            var name = element(
                "span",
                "maritime-contact-name" + (contact.identified ? "" : " maritime-unknown"),
                title(contact.label)
            );
            line.appendChild(name);
            line.appendChild(
                element(
                    "span",
                    "maritime-contact-where",
                    bearing(contact.bearing) + "  ·  " + range(contact.range, scale)
                )
            );
            into.appendChild(line);
        });
    }

    /* A control is a way of typing a command. It sends the name of an action and
     * whatever that action carries; the server rebuilds the command line from its own
     * table, so nothing typed here reaches one. */
    function act(action, detail) {
        if (!window.Evennia || typeof Evennia.msg !== "function") {
            return;
        }
        var payload = detail || {};
        payload.action = action;
        Evennia.msg("maritime_action", [], payload);
    }

    function control(label, action, detail, title) {
        var made = element("button", "maritime-control", label);
        made.type = "button";
        made.title = title || label;
        made.setAttribute("aria-label", title || label);
        made.addEventListener("click", function () {
            act(action, detail);
        });
        return made;
    }

    /* Whether the server offered this control to whoever is looking.
     *
     * Named apart from the panel-side `has` on purpose. Both were called `has`, both
     * took a state and a string, and the later declaration silently replaced the
     * earlier one - so `offered()` spent its time asking whether "company" was in the
     * list of controls, which it never is, and every panel tab vanished. The panel
     * bodies went on rendering from the stored preference, which is exactly why an
     * empty tab strip did not look like a bug. */
    function hasControl(state, key) {
        var offered = (state.status && state.status.controls) || [];
        return offered.indexOf(key) !== -1;
    }

    /* Controls are drawn because the server said this person may have them. It says
     * so again when one is pressed, so this list is a courtesy rather than a
     * permission - a passenger who forges a press is refused by the command, in the
     * same words a passenger who typed it would be. */
    function controlsFor(state, keys) {
        var bar = element("div", "maritime-controls");
        var drawn = 0;
        keys.forEach(function (spec) {
            if (!hasControl(state, spec.key)) {
                return;
            }
            bar.appendChild(control(spec.label, spec.key, spec.detail, spec.title));
            drawn += 1;
        });
        return drawn ? bar : null;
    }

    function helmControls(state) {
        return controlsFor(state, [
            { key: "port", label: "◀ 10°", detail: { degrees: 10 }, title: "Ten degrees to port" },
            { key: "steady", label: "STEADY", title: "Steady as she goes" },
            { key: "starboard", label: "10° ▶", detail: { degrees: 10 }, title: "Ten degrees to starboard" }
        ]);
    }

    function sailControls(state) {
        if (!hasControl(state, "sail")) {
            return null;
        }
        var bar = element("div", "maritime-controls");
        ["furled", "reefed", "working", "full", "battle"].forEach(function (plan) {
            bar.appendChild(
                control(title(plan), "sail", { plan: plan }, "Set " + plan + " sail")
            );
        });
        return bar;
    }

    function batteryBody(state, into) {
        var guns = (state.status && state.status.battery) || {};
        if (!guns.carried) {
            into.appendChild(element("p", "maritime-empty", "She carries no guns."));
            return;
        }
        into.appendChild(row("Carried", String(guns.carried)));
        into.appendChild(row("Ready", String(guns.ready || 0)));
        if (guns.dismounted) {
            into.appendChild(row("Dismounted", String(guns.dismounted), "maritime-attention"));
        }
        if (guns.shot && guns.shot.length) {
            into.appendChild(row("Loaded with", guns.shot.map(title).join(", ")));
        }
    }

    function cargoBody(state, into) {
        var hold = (state.status && state.status.cargo) || {};
        if (!hold.hold && !hold.deadweight) {
            into.appendChild(element("p", "maritime-empty", "She has no hold."));
            return;
        }
        if (typeof hold.mass === "number") {
            into.appendChild(row("Aboard", hold.mass.toFixed(1) + " / " + hold.deadweight + " t"));
        }
        if (typeof hold.draft === "number") {
            into.appendChild(row("Draught", hold.draft.toFixed(2) + " m"));
        }
        if (typeof hold.freeboard === "number") {
            /* Freeboard is the number that decides whether a sea comes aboard, so
             * a low one is worth colouring rather than merely printing. */
            into.appendChild(
                row(
                    "Freeboard",
                    hold.freeboard.toFixed(2) + " m",
                    hold.freeboard < 0.4 ? "maritime-attention" : null
                )
            );
        }
    }

    var BODIES = {
        helm: helmBody,
        battery: batteryBody,
        cargo: cargoBody,
        sails: sailsBody,
        crew: crewBody,
        navigation: navigationBody,
        contacts: contactsBody
    };

    /* The body of whichever panel is selected. */
    function renderPanelBody(state) {
        var card = element("div", "maritime-card");
        var active = state.preferences.panel;
        var label = active;
        for (var i = 0; i < PANELS.length; i++) {
            if (PANELS[i].key === active) {
                label = PANELS[i].label;
            }
        }
        card.appendChild(element("div", "maritime-card-title", label));

        var body = element("div", "maritime-card-body");
        var draw = BODIES[active];
        if (draw) {
            draw(state, body);
        }
        if (!body.childNodes.length) {
            body.appendChild(element("p", "maritime-empty", "Nothing to show here yet."));
        }
        card.appendChild(body);
        return card;
    }

    /* The captain's board.
     *
     * Laid out in rows by the kind of order rather than by how often it is given: the
     * wheel, then the canvas, then everything that is not steering. A hand looking for
     * "hard a-port" in a hurry wants it beside "port", not beside "anchor".
     *
     * `unwired` marks a button whose command this contrib has but whose control has
     * not been written yet. It is drawn and it is plainly dead, because the structure
     * of the board is worth seeing before every square of it works - and a button that
     * silently does nothing is worse than one that says it does nothing.
     */
    var GRID = [
        [
            { key: "port", detail: { degrees: 10 }, label: "Turn port", note: "10°" },
            { key: "starboard", detail: { degrees: 10 }, label: "Turn starboard", note: "10°" },
            { key: "port", detail: { degrees: 45 }, label: "Hard port", note: "45°" },
            { key: "starboard", detail: { degrees: 45 }, label: "Hard starboard", note: "45°" },
            { key: "steady", label: "Steady course" }
        ],
        [
            { key: "sail", detail: { plan: "working" }, label: "Working sail" },
            { key: "sail", detail: { plan: "reefed" }, label: "Reef sails" },
            { key: "sail", detail: { plan: "furled" }, label: "Furl sails" },
            { key: "sail", detail: { plan: "full" }, label: "Full sails" },
            { key: "heading", label: "Shift course", unwired: true }
        ],
        [
            { key: "anchor", label: "Anchor" },
            { key: "dock", label: "Prepare to dock", unwired: true },
            { key: "scan", label: "Scan horizon" },
            { key: "board", label: "Board", unwired: true },
            { key: "fire", label: "Fire weapons", unwired: true, danger: true }
        ]
    ];

    function gridButton(order) {
        var button = element("button", "maritime-order");
        button.type = "button";
        button.appendChild(element("span", "maritime-order-label", order.label));
        if (order.note) {
            button.appendChild(element("span", "maritime-order-note", order.note));
        }
        if (order.danger) {
            button.className += " maritime-order-danger";
        }
        if (order.unwired) {
            button.className += " maritime-order-unwired";
            button.disabled = true;
            button.title = "No control for this yet";
            return button;
        }
        button.title = order.label;
        button.addEventListener("click", function () {
            act(order.key, order.detail);
        });
        return button;
    }

    /* Nothing at all for somebody who may not give orders.
     *
     * Not a greyed-out board: a passenger looking at fifteen disabled buttons is being
     * told the interface thinks they might steer. The server decides who may, and says
     * so by offering no controls, and the honest drawing of that is an absence. */
    function renderControlGrid(state) {
        var offeredHere = (state.status && state.status.controls) || [];
        if (!offeredHere.length) {
            return null;
        }

        var board = element("div", "maritime-board");
        GRID.forEach(function (line) {
            var strip = element("div", "maritime-board-row");
            line.forEach(function (order) {
                if (!order.unwired && !hasControl(state, order.key)) {
                    return;
                }
                strip.appendChild(gridButton(order));
            });
            if (strip.childNodes.length) {
                board.appendChild(strip);
            }
        });
        return board.childNodes.length ? board : null;
    }

    /* ASHORE: who you are and where she lies, and nothing that needs a helm.
     *
     * The full strip is instruments - heading, speed, course made good, sail plan - and on
     * a quay every one of them is either meaningless or a stale reading off a ship at rest.
     * What is worth carrying ashore is which ship is yours, because the point of the map is
     * walking back to her.
     */
    function renderAshoreStrip(state) {
        var strip = element("div", "maritime-strip maritime-strip-ashore");
        var vessel = (state.status && state.status.vessel) || {};

        strip.appendChild(element("div", "maritime-artwork maritime-emblem"));

        var who = element("div", "maritime-strip-who");
        who.appendChild(element("div", "maritime-strip-name", vessel.name || "Ashore"));

        var said = [];
        if (vessel.template) {
            said.push(String(vessel.template).toUpperCase());
        }
        if (typeof vessel.length === "number") {
            said.push(Math.round(vessel.length) + " METRES");
        }
        who.appendChild(element("div", "maritime-strip-note", said.join(" · ")));
        strip.appendChild(who);
        return strip;
    }

    function renderChartPlaceholder() {
        var card = element("div", "maritime-card");
        card.appendChild(element("div", "maritime-card-title", "Chart"));
        var body = element("div", "maritime-card-body");
        body.appendChild(element("p", "maritime-empty", "No chart aboard."));
        card.appendChild(body);
        return card;
    }

    return {
        READINGS: READINGS,
        PANELS: PANELS,
        setUnits: setUnits,
        isReadable: isReadable,
        act: act,
        has: has,
        hasControl: hasControl,
        pickScale: pickScale,
        reading: reading,
        offered: offered,
        renderIdentity: renderIdentity,
        renderStrip: renderStrip,
        renderTabs: renderTabs,
        range: range,
        renderPanelBody: renderPanelBody,
        renderControlGrid: renderControlGrid,
        renderAshoreStrip: renderAshoreStrip,
        renderChartPlaceholder: renderChartPlaceholder
    };
})();
