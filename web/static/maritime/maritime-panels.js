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
        { key: "navigation", label: "Navigation", needs: null },
        { key: "contacts", label: "Contacts", needs: null },
        { key: "crew", label: "Crew", needs: "company" },
        { key: "cargo", label: "Cargo", needs: "cargo" },
        { key: "battery", label: "Battery", needs: "battery" }
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
        block.appendChild(element("div", "maritime-ship-name", who.name || "—"));

        var described = [];
        if (state.mode && state.mode !== "command") {
            described.push(state.mode);
        }
        if (typeof who.length === "number") {
            described.push(Math.round(who.length) + " metres");
        }
        block.appendChild(
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

    function helmBody(state, into) {
        var motion = (state.status && state.status.motion) || {};
        if (typeof motion.heading === "number") {
            into.appendChild(row("Heading", bearing(motion.heading)));
        }
        if (typeof motion.ordered_heading === "number") {
            into.appendChild(row("Ordered", bearing(motion.ordered_heading)));
        }
        if (typeof motion.course_made_good === "number") {
            into.appendChild(row("Made good", bearing(motion.course_made_good)));
        }
        if (typeof motion.speed_through_water === "number") {
            into.appendChild(row("Through the water", knots(motion.speed_through_water)));
        }
        if (typeof motion.speed_over_ground === "number") {
            into.appendChild(row("Over the ground", knots(motion.speed_over_ground)));
        }
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

    function sailsBody(state, into) {
        var driving = (state.status && state.status.propulsion) || {};
        if (driving.sail_plan) {
            into.appendChild(row("Set", title(driving.sail_plan)));
        }
        if (driving.anchor) {
            into.appendChild(row("Anchor", title(driving.anchor)));
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

    var BODIES = {
        helm: helmBody,
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
        has: has,
        pickScale: pickScale,
        reading: reading,
        offered: offered,
        renderIdentity: renderIdentity,
        renderStrip: renderStrip,
        renderTabs: renderTabs,
        range: range,
        renderPanelBody: renderPanelBody,
        renderChartPlaceholder: renderChartPlaceholder
    };
})();
