/*
 * The chart.
 *
 * SVG rather than a canvas, deliberately. A contour is a path and a mark is a labelled
 * element, which is what SVG already is; hit-testing, hovering and tooltips come free
 * where a canvas would need every one written by hand; a screen reader can be told what
 * is on it; and a host game can restyle the whole thing with CSS classes without
 * touching a line of drawing code. The cost is that a large coastline is a great many
 * points, which is answered by culling to the viewport rather than by changing
 * technology.
 *
 * **The chart plots what the ship knows, not what is true.** Her own mark sits at the
 * reckoned position, so a chart that has drifted from the reckoning shows her in the
 * wrong place - which is correct, and is the whole of navigation. Contacts are plotted
 * from the bearing and range the lookout called, because that is what a navigator has
 * to plot with; a contact drawn at its true coordinates would be a radar return.
 *
 * The browser computes screen geometry and nothing else. Every number it draws came
 * from the server.
 */

window.MaritimeChart = (function () {
    "use strict";

    var NS = "http://www.w3.org/2000/svg";

    /* How much sea to show, in metres from the ship to the edge. Zoom moves between
     * these rather than by a free factor, so a captain gets predictable scales he can
     * learn instead of whatever a scroll wheel landed on. */
    var SCALES = [500, 1000, 2000, 5000, 10000, 20000, 50000];

    /* Where the chart opens when there is nothing in sight to frame: a couple of
     * kilometres, which is the water a coasting vessel is about to be in. */
    var DEFAULT_SCALE = 2;

    var view = {
        scaleIndex: DEFAULT_SCALE,
        panX: 0,
        panY: 0,

        /* Whether the player has taken the chart in hand. Until they do it scales
         * itself to whatever is in sight, which is what a navigator would do and
         * means the first look is never an empty square of sea with everything the
         * lookout is shouting about just outside it. The moment somebody zooms or
         * drags, it stays exactly where they put it. */
        held: false
    };

    function node(name, attributes) {
        var made = document.createElementNS(NS, name);
        for (var key in attributes) {
            if (Object.prototype.hasOwnProperty.call(attributes, key)) {
                made.setAttribute(key, attributes[key]);
            }
        }
        return made;
    }

    /* Tell the server how much sea we are showing, so it draws a sheet to match.
     * Debounced: a wheel produces a burst of zoom steps and contouring each one
     * would ask the server to trace a coastline five times for one gesture. */
    var askTimer = null;

    function askForSheet() {
        if (askTimer) {
            window.clearTimeout(askTimer);
        }
        askTimer = window.setTimeout(function () {
            askTimer = null;
            if (window.Evennia && typeof Evennia.msg === "function") {
                Evennia.msg("maritime_view", [], { reach: reach() });
            }
        }, 250);
    }

    function reach() {
        return SCALES[Math.max(0, Math.min(SCALES.length - 1, view.scaleIndex))];
    }

    /* Where a thing lies from the ship, in metres north and east, given what the
     * lookout reported. Bearings are true, so north is up until somebody asks for
     * head-up. */
    function offsetOf(bearingDegrees, metres) {
        var radians = (bearingDegrees * Math.PI) / 180;
        return { east: Math.sin(radians) * metres, north: Math.cos(radians) * metres };
    }

    /* Metres to the drawing's own units. The viewBox is a square of side 1000 with the
     * ship at its centre, so the chart scales to whatever box it is given without any
     * of this arithmetic knowing how many pixels wide that is. */
    function toChart(offset) {
        var span = reach();
        return {
            x: 500 + (offset.east / span) * 480 + view.panX,
            y: 500 - (offset.north / span) * 480 + view.panY
        };
    }

    function ringLabel(metres) {
        if (metres >= 5556) {
            return (metres / 5556).toFixed(1) + " lg";
        }
        if (metres >= 1852) {
            return (metres / 1852).toFixed(1) + " mi";
        }
        return Math.round(metres / 185.2) + " cbl";
    }

    /* Range rings, so a distance on the chart can be read rather than guessed. Two
     * rings and their labels: more than that is clutter on a small panel. */
    function drawRings(into) {
        var span = reach();
        [0.5, 1.0].forEach(function (fraction) {
            var radius = 480 * fraction;
            var centre = toChart({ east: 0, north: 0 });
            into.appendChild(
                node("circle", {
                    cx: centre.x,
                    cy: centre.y,
                    r: radius,
                    class: "maritime-chart-ring"
                })
            );
            var label = node("text", {
                x: centre.x + 4,
                y: centre.y - radius + 14,
                class: "maritime-chart-ring-label"
            });
            label.textContent = ringLabel(span * fraction);
            into.appendChild(label);
        });
    }

    /* Her own mark: a hull shape pointing the way she is heading, so the chart answers
     * "which way am I facing" without anybody reading a number off the strip. */
    function drawOwnVessel(into, heading) {
        var centre = toChart({ east: 0, north: 0 });
        var ship = node("g", {
            class: "maritime-chart-own",
            transform:
                "translate(" + centre.x + "," + centre.y + ") rotate(" + (heading || 0) + ")"
        });
        ship.appendChild(
            node("path", { d: "M 0 -13 L 6 6 L 0 3 L -6 6 Z", class: "maritime-chart-hull" })
        );
        var title = node("title");
        title.textContent = "Own vessel, heading " + Math.round(heading || 0) + " degrees";
        ship.appendChild(title);
        into.appendChild(ship);
    }

    /* A contact, at the bearing and range the lookout gave. Anything not identified is
     * drawn hollow and named only by what it looks like - the payload never carried a
     * name, so there is none here to show. */
    function drawContacts(into, contacts, onSelect, selectedId) {
        (Array.isArray(contacts) ? contacts : []).forEach(function (contact) {
            if (!contact || typeof contact.bearing !== "number" || typeof contact.range !== "number") {
                return;
            }
            var span = reach();
            if (contact.range > span * 1.05) {
                return;
            }
            var at = toChart(offsetOf(contact.bearing, contact.range));
            var group = node("g", {
                class:
                    "maritime-chart-contact" +
                    (contact.identified ? " maritime-known" : " maritime-unknown") +
                    (contact.id === selectedId ? " maritime-selected" : ""),
                tabindex: "0",
                role: "button"
            });
            group.appendChild(node("circle", { cx: at.x, cy: at.y, r: 5 }));

            var title = node("title");
            title.textContent =
                contact.label + ", bearing " + Math.round(contact.bearing) + " degrees";
            group.appendChild(title);

            group.addEventListener("click", function () {
                onSelect(contact.id);
            });
            group.addEventListener("keydown", function (event) {
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelect(contact.id);
                }
            });
            into.appendChild(group);
        });
    }

    /* A run of offsets into a path. Offsets are metres east and north of where she
     * reckons she is, so this is the only place the chart turns knowledge into
     * pixels. */
    function pathOf(line) {
        var parts = [];
        for (var i = 0; i < line.length; i++) {
            var at = toChart({ east: line[i][0], north: line[i][1] });
            parts.push((i ? "L" : "M") + at.x.toFixed(1) + " " + at.y.toFixed(1));
        }
        return parts.join(" ");
    }

    /* The paper: fathom lines, then the waterline, then the printed soundings.
     *
     * Land is not filled. A coastline traced from a chart is a line somebody
     * surveyed, and flooding one side of it with a colour would claim knowledge of
     * everything inside that nobody has. The line is what was measured; the line is
     * what is drawn. */
    function drawSheet(layers, sheet) {
        if (!sheet) {
            return;
        }

        Object.keys(sheet.depths || {}).forEach(function (fathom) {
            var lines = sheet.depths[fathom];
            if (!Array.isArray(lines)) {
                return;
            }
            lines.forEach(function (line) {
                layers.depths.appendChild(
                    node("path", {
                        d: pathOf(line),
                        class: "maritime-chart-depth maritime-depth-" + String(fathom).replace(".", "-")
                    })
                );
            });
        });

        (Array.isArray(sheet.coastline) ? sheet.coastline : []).forEach(function (line) {
            layers.land.appendChild(node("path", { d: pathOf(line), class: "maritime-chart-coast" }));
        });

        var span = reach();
        (Array.isArray(sheet.soundings) ? sheet.soundings : []).forEach(function (sounding) {
            if (!Array.isArray(sounding) || sounding.length < 3) {
                return;
            }
            if (Math.abs(sounding[0]) > span || Math.abs(sounding[1]) > span) {
                return;
            }
            var at = toChart({ east: sounding[0], north: sounding[1] });
            var figure = node("text", {
                x: at.x,
                y: at.y,
                class: "maritime-chart-sounding",
                "text-anchor": "middle"
            });
            figure.textContent = sounding[2].toFixed(0);
            layers.soundings.appendChild(figure);
        });

        /* Where the survey stops. Off the chart is a state, not a failure, and a
         * navigator wants to see the edge coming rather than discover it by finding
         * no soundings under him. */
        if (sheet.coverage && typeof sheet.coverage.west === "number") {
            var topLeft = toChart({ east: sheet.coverage.west, north: sheet.coverage.north });
            var bottomRight = toChart({ east: sheet.coverage.east, north: sheet.coverage.south });
            layers.overlay.appendChild(
                node("rect", {
                    x: topLeft.x,
                    y: topLeft.y,
                    width: Math.max(0, bottomRight.x - topLeft.x),
                    height: Math.max(0, bottomRight.y - topLeft.y),
                    class: "maritime-chart-coverage"
                })
            );
        }
    }

    /* The plotted course, drawn under everything else so marks and contacts sit on
     * top of it rather than being hidden by it. */
    function drawRoute(into, route) {
        if (!route || route.length < 2) {
            return;
        }
        var parts = [];
        for (var i = 0; i < route.length; i++) {
            var at = toChart({ east: route[i][0], north: route[i][1] });
            parts.push((i ? "L" : "M") + at.x.toFixed(1) + " " + at.y.toFixed(1));
        }
        into.appendChild(node("path", { d: parts.join(" "), class: "maritime-chart-route" }));
    }

    /* Buoyage.
     *
     * Charted, so it stays on the paper in fog, at night and when nobody is looking
     * - the same as the coastline. Only ships come and go with the lookout.
     *
     * Shaped by what each mark means rather than only coloured by it: a can, a cone,
     * a diamond for a danger. A player who cannot tell red from green still has to be
     * able to pass a buoy on the correct side, and that is not a small matter. */
    function drawMarks(into, marks) {
        (Array.isArray(marks) ? marks : []).forEach(function (mark) {
            if (!mark || typeof mark.east !== "number" || typeof mark.kind !== "string") {
                return;
            }
            var span = reach();
            if (Math.abs(mark.east) > span * 1.05 || Math.abs(mark.north) > span * 1.05) {
                return;
            }
            var at = toChart({ east: mark.east, north: mark.north });
            var group = node("g", {
                class: "maritime-chart-mark maritime-mark-" + mark.kind.replace(/ /g, "-"),
                tabindex: "0",
                role: "button"
            });

            if (mark.danger) {
                group.appendChild(
                    node("path", {
                        d:
                            "M " + at.x + " " + (at.y - 7) +
                            " L " + (at.x + 6) + " " + at.y +
                            " L " + at.x + " " + (at.y + 7) +
                            " L " + (at.x - 6) + " " + at.y + " Z"
                    })
                );
            } else if (mark.kind === "port hand") {
                group.appendChild(
                    node("rect", { x: at.x - 5, y: at.y - 5, width: 10, height: 10 })
                );
            } else if (mark.kind === "starboard hand") {
                group.appendChild(
                    node("path", {
                        d: "M " + at.x + " " + (at.y - 7) + " L " + (at.x + 6) + " " +
                            (at.y + 5) + " L " + (at.x - 6) + " " + (at.y + 5) + " Z"
                    })
                );
            } else {
                group.appendChild(node("circle", { cx: at.x, cy: at.y, r: 5 }));
            }

            var told = node("title");
            told.textContent =
                mark.label +
                " - " +
                mark.kind +
                (mark.safe_water ? ", safe water to the " + compassOf(mark.safe_water) : "") +
                (mark.danger ? ", foul ground" : "");
            group.appendChild(told);
            into.appendChild(group);
        });
    }

    /* Buoyage answers a bearing for where the safe water lies; a player wants a
     * point of the compass. */
    function compassOf(bearing) {
        if (typeof bearing !== "number") {
            return String(bearing);
        }
        var points = [
            "north", "north-east", "east", "south-east",
            "south", "south-west", "west", "north-west"
        ];
        return points[Math.round((bearing % 360) / 45) % 8];
    }

    function drawCompass(into) {
        var mark = node("g", { class: "maritime-chart-compass" });
        mark.appendChild(node("path", { d: "M 30 46 L 24 30 L 30 34 L 36 30 Z" }));
        var north = node("text", { x: 30, y: 62, "text-anchor": "middle" });
        north.textContent = "N";
        mark.appendChild(north);
        into.appendChild(mark);
    }

    /* --- controls ----------------------------------------------------------- */

    function button(label, title, onClick) {
        var made = document.createElement("button");
        made.type = "button";
        made.className = "maritime-chart-button";
        made.textContent = label;
        made.title = title;
        made.setAttribute("aria-label", title);
        made.addEventListener("click", onClick);
        return made;
    }

    function controls(redraw) {
        var bar = document.createElement("div");
        bar.className = "maritime-chart-controls";
        bar.appendChild(
            button("−", "Show more sea", function () {
                view.scaleIndex = Math.min(SCALES.length - 1, view.scaleIndex + 1);
                view.held = true;
                askForSheet();
                redraw();
            })
        );
        bar.appendChild(
            button("+", "Show less sea", function () {
                view.scaleIndex = Math.max(0, view.scaleIndex - 1);
                view.held = true;
                askForSheet();
                redraw();
            })
        );
        bar.appendChild(
            button("CENTRE", "Put her back in the middle", function () {
                view.panX = 0;
                view.panY = 0;
                view.held = false;
                askForSheet();
                redraw();
            })
        );
        bar.appendChild(
            button("FIT", "Show everything in sight", function () {
                fitToContacts();
                view.held = false;
                askForSheet();
                redraw();
            })
        );
        return bar;
    }

    /* Pick the smallest scale that still holds every contact. A chart that has to be
     * zoomed out by hand before anything appears on it is a chart nobody uses. */
    function fitToContacts() {
        var furthest = 0;
        var contacts = MaritimeState.get().contacts || [];

        /* Fitted to what the lookout can see, and to nothing else.
         *
         * An earlier version also fitted to the sheet the server had drawn, which
         * looked sensible and was a loop: the sheet is drawn to whatever reach the
         * view asked for, so the view fitted to its own last answer and stuck at it
         * for ever. The client decides how much sea to show; the server draws to
         * that. Only one of them may lead. */
        contacts.forEach(function (contact) {
            if (typeof contact.range === "number" && contact.range > furthest) {
                furthest = contact.range;
            }
        });
        view.panX = 0;
        view.panY = 0;
        var before = view.scaleIndex;

        if (!furthest) {
            /* Nothing in sight. A coasting vessel wants the water she is about to be
             * in, not the horizon, so this opens close rather than wide. */
            view.scaleIndex = DEFAULT_SCALE;
            if (view.scaleIndex !== before) {
                askForSheet();
            }
            return;
        }
        view.scaleIndex = SCALES.length - 1;
        for (var i = 0; i < SCALES.length; i++) {
            if (SCALES[i] >= furthest) {
                view.scaleIndex = i;
                break;
            }
        }
        if (view.scaleIndex !== before) {
            askForSheet();
        }
    }

    /* --- dragging ------------------------------------------------------------ */

    function makeDraggable(svg, redraw) {
        var dragging = false;
        var lastX = 0;
        var lastY = 0;

        svg.addEventListener("pointerdown", function (event) {
            dragging = true;
            lastX = event.clientX;
            lastY = event.clientY;
            svg.setPointerCapture(event.pointerId);
        });
        svg.addEventListener("pointermove", function (event) {
            if (!dragging) {
                return;
            }
            var box = svg.getBoundingClientRect();
            /* Screen pixels into the drawing's own units, so a drag moves the chart by
             * the distance the finger moved however large the panel is. */
            view.held = true;
            view.panX += ((event.clientX - lastX) / box.width) * 1000;
            view.panY += ((event.clientY - lastY) / box.height) * 1000;
            lastX = event.clientX;
            lastY = event.clientY;
            redraw();
        });
        ["pointerup", "pointercancel", "pointerleave"].forEach(function (name) {
            svg.addEventListener(name, function () {
                dragging = false;
            });
        });
        svg.addEventListener(
            "wheel",
            function (event) {
                event.preventDefault();
                view.held = true;
                view.scaleIndex = Math.max(
                    0,
                    Math.min(SCALES.length - 1, view.scaleIndex + (event.deltaY > 0 ? 1 : -1))
                );
                redraw();
            },
            { passive: false }
        );
    }

    /* --- the whole thing ----------------------------------------------------- */

    function render(state, redraw) {
        if (!view.held) {
            fitToContacts();
        }

        var card = document.createElement("div");
        card.className = "maritime-card maritime-chart-card";

        var title = document.createElement("div");
        title.className = "maritime-card-title";
        title.textContent = "Chart · " + ringLabel(reach()) + " to the edge";
        card.appendChild(title);

        var svg = node("svg", {
            viewBox: "0 0 1000 1000",
            class: "maritime-chart",
            role: "img",
            "aria-label": "Chart showing own vessel and contacts in sight"
        });

        svg.appendChild(node("rect", { x: 0, y: 0, width: 1000, height: 1000, class: "maritime-chart-sea" }));

        var layers = {};
        ["depths", "land", "soundings", "rings", "marks", "contacts", "own", "overlay"].forEach(function (name) {
            layers[name] = node("g", { class: "maritime-layer-" + name });
            svg.appendChild(layers[name]);
        });

        drawSheet(layers, state.chart);
        if (state.chart) {
            drawRoute(layers.marks, state.chart.route);
            drawMarks(layers.marks, state.chart.marks);
        }
        drawRings(layers.rings);
        drawContacts(layers.contacts, state.contacts, function (id) {
            MaritimeState.select(id);
        }, state.selectedContactId);

        var motion = (state.status && state.status.motion) || {};
        drawOwnVessel(layers.own, motion.heading);
        drawCompass(layers.overlay);

        makeDraggable(svg, redraw);

        card.appendChild(svg);
        card.appendChild(controls(redraw));
        return card;
    }

    return {
        SCALES: SCALES,
        view: view,
        offsetOf: offsetOf,
        toChart: toChart,
        reach: reach,
        ringLabel: ringLabel,
        askForSheet: askForSheet,
        compassOf: compassOf,
        fitToContacts: fitToContacts,
        render: render
    };
})();
