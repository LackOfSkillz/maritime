/*
 * The map ashore: rooms, the ways between them, and walking there by clicking.
 *
 * A chart is the wrong instrument on land. It draws water, and standing in a market the
 * useful questions are which way the pier is and where things are sold - so when the panel
 * is told the player is ashore it keeps its space and draws this instead.
 *
 * The picture is a graph, not a projection. There are no metres in it: rooms sit where the
 * walk from the player's own room puts them, and the lines are exits. That is the honest
 * shape of the data, and it is also the shape a player already has in their head after
 * walking somewhere twice.
 *
 * DRAWN THE WAY A ZONE MAP IS DRAWN, because that is what it is. The controls, the colours
 * and the interaction are the ones a player already knows from every other map of this
 * kind: fit, centre, zoom, a legend behind an `i`, and full screen. Small tan dots joined
 * by tan lines, the room you are in ringed and bright, and a handful of colours that each
 * mean one thing.
 *
 * IN SVG RATHER THAN CANVAS, which is the one deliberate difference from the map this was
 * modelled on. A canvas has to hit-test clicks against stored positions, redraw to show a
 * hover, and be given a parallel accessibility tree if it is to have one at all; in SVG a
 * room is an element, so the click target, the keyboard focus, the tooltip and the hover
 * state are all free and correct. The picture is identical either way. At the scale of a
 * town - a hundred rooms and change - there is nothing in it for performance.
 *
 * COLOUR IS MEANING. A dot is only worth colouring if the colour answers a question
 * somebody is actually asking, and ashore in a maritime game there are four: where am I,
 * where is my ship, where can I tie up, and where do I buy things. A game with its own
 * points of interest gets those too, through the same tags it already uses.
 *
 * CLICKING WALKS. The route is a breadth-first search over the same edges that were drawn,
 * turned into the directions those edges are named after, and sent one at a time with a
 * pause between. Nothing is teleported: every step is the ordinary movement command a
 * player could have typed, so locks, exits and anything the game does on movement all
 * happen exactly as they would have.
 */
window.MaritimeLandMap = (function () {
    "use strict";

    /* What each marker is drawn in.
     *
     * The four maritime ones first, then whatever a game's own points of interest say.
     * The current room takes the strongest colour on the panel because it is the one thing
     * a player looks for first, and it is the only one that also gets a ring - so it is
     * findable without reading a colour at all. */
    var MARKERS = {
        here: { fill: "#df564a", ring: true, size: 6 },
        ship: { fill: "#7ee0a1", ring: false, size: 5 },
        berth: { fill: "#79a4cc", ring: false, size: 5 },
        trade: { fill: "#e8b64c", ring: false, size: 5 },
        way_out: { fill: "#b08fd0", ring: false, size: 4 },
        plain: { fill: "#8a7560", ring: false, size: 3.5 }
    };

    /* What each marker means, for the legend and for a room's tooltip. */
    var MEANS = {
        here: "you are here",
        ship: "a vessel",
        berth: "a berth",
        trade: "somewhere selling",
        way_out: "the way onward",
        plain: ""
    };

    /* What the ways between rooms are drawn in. */
    var WAY_COLOUR = "rgba(195, 164, 104, 0.6)";
    var WAY_WIDTH = 1.5;

    /* How far apart two rooms can be drawn and still have a line between them.
     *
     * **The drawing and the routing do not need the same edges.** Flattening a graph onto
     * a grid always leaves some pairs a long way apart - two ends of a street reached by
     * different routes, a lane that comes back on itself - and the line joining them is an
     * artifact of the layout rather than a fact about the town. Drawn, it is a diagonal
     * across everything and reads as a road that is not there; left out, the rooms are
     * still on the map, still clickable, and still routed to over the *whole* edge list.
     *
     * One street and a half, so a normal street and its diagonal both draw and nothing
     * else does. Twenty lines came off a fifty-five room waterfront this way. */
    var LONGEST_WAY = 3.1;

    /* How far apart to draw two rooms that are one step apart, in pixels, before zoom. */
    var SPACING = 34;

    /* The least ground a fitted map covers, in cells across and down.
     *
     * **So that a dot is the same size on every map.** Fitting the drawing to the panel
     * means a nine-room quay is blown up until each room is a saucer and each lane a
     * rope, while a hundred-room town is drawn properly - two maps of the same place at
     * two scales, which is exactly what a scale is for avoiding. Padding the extent out to
     * a floor and centring the rooms inside it keeps one size of dot everywhere, and costs
     * only some empty ground round a small map, which is honest: there really is nothing
     * there.
     *
     * Sixteen by twelve is about the size of a town worth having a map of. */
    var LEAST_ACROSS = 16;
    var LEAST_DOWN = 12;

    /* How far the zoom goes either way, and what a click of the button is worth. */
    var MIN_ZOOM = 0.4;
    var MAX_ZOOM = 4.0;
    var ZOOM_STEP = 1.25;

    /* How long to wait between steps of a walk, in milliseconds. Long enough that the
     * server's own movement messages arrive in order and a player can read them going by,
     * short enough that crossing a town is not a chore. */
    var STEP_MS = 320;

    var walking = { token: 0, going: false };

    /* The camera, kept out here so it survives a redraw.
     *
     * A map that reset its zoom every time a room's contents changed would be unusable -
     * and the panel redraws on every tick. So the view is held, and `of` records which
     * place it is a view *of*: walking into a different town resets it, because a pan and
     * a zoom are coordinates in a drawing and the drawing has been replaced. Without that
     * the second map on a page came up blank, pointing at somewhere that no longer existed.
     *
     * Zoom is a multiplier on the fitted view rather than a scale in pixels, so 1 always
     * means "the whole place" whatever size the panel is. */
    var camera = { zoom: 1, x: null, y: null, legend: false, full: false, of: null };

    function node(name, attributes) {
        var made = document.createElementNS("http://www.w3.org/2000/svg", name);
        Object.keys(attributes || {}).forEach(function (key) {
            made.setAttribute(key, attributes[key]);
        });
        return made;
    }

    function element(tag, className, text) {
        var made = document.createElement(tag);
        if (className) {
            made.className = className;
        }
        if (text !== undefined) {
            made.textContent = text;
        }
        return made;
    }

    /* THE ROUTE, over the edges that were actually drawn.
     *
     * Breadth-first, so the way found is the way with fewest rooms in it - which is what
     * somebody clicking a distant dot means, and not necessarily the shortest on the
     * ground. A town has short cuts that are steep and long ways round that are flat, and
     * a map cannot tell which a player wanted. Fewest rooms is at least predictable. */
    function routeTo(fromId, toId, edges) {
        if (fromId === toId) {
            return [];
        }
        var queue = [[fromId]];
        var seen = {};
        seen[fromId] = true;

        while (queue.length) {
            var path = queue.shift();
            var last = path[path.length - 1];
            for (var i = 0; i < edges.length; i++) {
                var edge = edges[i];
                if (edge.from !== last || seen[edge.to]) {
                    continue;
                }
                var next = path.concat([edge.to]);
                if (edge.to === toId) {
                    return next;
                }
                seen[edge.to] = true;
                queue.push(next);
            }
        }
        return null;
    }

    function directionsAlong(path, edges) {
        var out = [];
        for (var i = 0; i < path.length - 1; i++) {
            for (var j = 0; j < edges.length; j++) {
                if (edges[j].from === path[i] && edges[j].to === path[i + 1]) {
                    out.push(edges[j].dir);
                    break;
                }
            }
        }
        return out;
    }

    function stopWalking() {
        walking.going = false;
        walking.token += 1;
    }

    /* Sent one at a time, as ordinary commands.
     *
     * Not as one batched instruction, and not by moving the character directly: every step
     * is the command the player could have typed, so a locked gate stops the walk exactly
     * where it would have stopped them. A walk that could pass through a door a player
     * cannot is a map that lies about the world. */
    function walk(directions) {
        if (!directions || !directions.length) {
            return;
        }
        walking.token += 1;
        var mine = walking.token;
        walking.going = true;

        var step = 0;
        function next() {
            if (!walking.going || mine !== walking.token || step >= directions.length) {
                if (mine === walking.token) {
                    walking.going = false;
                }
                return;
            }
            if (window.Evennia && typeof Evennia.msg === "function") {
                Evennia.msg("text", [directions[step]], {});
            }
            step += 1;
            window.setTimeout(next, STEP_MS);
        }
        next();
    }

    /* Where every room sits, in the drawing's own units before any camera is applied.
     *
     * North is up, so the northing is flipped: the data counts north as positive and a
     * screen counts down. Getting this backwards mirrors the whole town and is very hard
     * to see unless you know the place. */
    function layout(sheet) {
        var where = {};
        var xs = sheet.rooms.map(function (r) { return r.x; });
        var ys = sheet.rooms.map(function (r) { return r.y; });
        var west = Math.min.apply(null, xs);
        var east = Math.max.apply(null, xs);
        var south = Math.min.apply(null, ys);
        var north = Math.max.apply(null, ys);

        /* Padded out to the floor, with the rooms centred in what is left. */
        var across = Math.max(east - west + 2, LEAST_ACROSS);
        var down = Math.max(north - south + 2, LEAST_DOWN);
        var spare = {
            x: (across - (east - west + 2)) / 2,
            y: (down - (north - south + 2)) / 2
        };

        sheet.rooms.forEach(function (room) {
            where[room.id] = {
                x: (room.x - west + 1 + spare.x) * SPACING,
                y: (north - room.y + 1 + spare.y) * SPACING
            };
        });
        return {
            at: where,
            width: across * SPACING,
            height: down * SPACING
        };
    }

    /* FIT and CENTRE, which are two different requests and are often confused.
     *
     * Fit shows the whole town. Centre keeps the zoom and puts the room you are standing
     * in in the middle. Somebody who has zoomed in to read a corner wants the second and
     * would be annoyed by the first.
     *
     * **Neither measures the panel.** The first version worked out a scale from
     * `clientWidth`, which is zero on the paint before any layout has happened - so the
     * fit was computed against a box of nothing, clamped to the minimum zoom, and never
     * recomputed because the request had been spent. An SVG already knows how to fit a
     * drawing into whatever space it is given; the viewBox says what to show and
     * `preserveAspectRatio` does the rest. */
    function fitTo(plan) {
        camera.zoom = 1;
        camera.x = plan.width / 2;
        camera.y = plan.height / 2;
    }

    function centreOn(plan, sheet) {
        var here = plan.at[sheet.here];
        if (here) {
            camera.x = here.x;
            camera.y = here.y;
        }
    }

    function viewBox(plan) {
        var width = plan.width / camera.zoom;
        var height = plan.height / camera.zoom;
        return [camera.x - width / 2, camera.y - height / 2, width, height].join(" ");
    }

    /* Which drawing the camera is a view of.
     *
     * The room you are in and how many rooms there are: between them they change whenever
     * the picture does, and not when it merely gains a passer-by. Comparing the whole sheet
     * would reset the view every time somebody walked past. */
    function signature(sheet) {
        return sheet.here + ":" + sheet.rooms.length + ":" + (sheet.title || "");
    }

    /* The buttons, in the order every map of this kind puts them.
     *
     * Named rather than iconographic, because five glyphs nobody has seen before is a
     * puzzle and five words is a control panel. `i` is the exception and is the one
     * convention strong enough to carry it. */
    function controls(sheet, redraw) {
        var bar = element("div", "maritime-landmap-controls");

        function button(label, title, onPress, pressed) {
            var made = element("button", "maritime-map-button", label);
            made.type = "button";
            made.title = title;
            if (pressed) {
                made.classList.add("is-on");
            }
            made.addEventListener("click", function (event) {
                event.preventDefault();
                onPress();
                redraw();
            });
            bar.appendChild(made);
        }

        button("FIT", "Show the whole place", function () { camera.want = "fit"; });
        button("CENTER", "Put your own room in the middle", function () {
            camera.want = "centre";
        });
        button("−", "Zoom out", function () {
            camera.zoom = Math.max(MIN_ZOOM, camera.zoom / ZOOM_STEP);
        });
        button("+", "Zoom in", function () {
            camera.zoom = Math.min(MAX_ZOOM, camera.zoom * ZOOM_STEP);
        });
        button("i", "What the colours mean", function () {
            camera.legend = !camera.legend;
        }, camera.legend);
        button("FULL", "Fill the panel", function () {
            camera.full = !camera.full;
        }, camera.full);
        return bar;
    }

    /* Dragging moves the camera, not the drawing.
     *
     * One number changes and the browser re-renders the same picture through a different
     * window, rather than every element being given new coordinates. It is also why a drag
     * does not disturb a walk in progress. */
    function makeDraggable(svg, plan, redraw) {
        var from = null;

        svg.addEventListener("pointerdown", function (event) {
            from = { x: event.clientX, y: event.clientY, cx: camera.x, cy: camera.y };
            svg.classList.add("is-dragging");
            svg.setPointerCapture(event.pointerId);
        });

        svg.addEventListener("pointermove", function (event) {
            if (!from) {
                return;
            }
            event.preventDefault();
            /* Pixels to drawing units, taken from the box the browser has actually laid
             * out - which by the time anybody can drag is a real number. */
            var wide = svg.clientWidth || plan.width;
            var scale = plan.width / camera.zoom / wide;
            camera.x = from.cx - (event.clientX - from.x) * scale;
            camera.y = from.cy - (event.clientY - from.y) * scale;
            svg.setAttribute("viewBox", viewBox(plan));
        });

        function done(event) {
            if (!from) {
                return;
            }
            from = null;
            svg.classList.remove("is-dragging");
            if (event && event.pointerId !== undefined && svg.hasPointerCapture(event.pointerId)) {
                svg.releasePointerCapture(event.pointerId);
            }
        }
        svg.addEventListener("pointerup", done);
        svg.addEventListener("pointercancel", done);
    }

    function render(state, onRedraw) {
        var sheet = state.land;
        var card = element("div", "maritime-card maritime-landmap");
        if (camera.full) {
            card.classList.add("is-full");
        }

        var head = element("div", "maritime-card-head");
        head.appendChild(element("span", "maritime-landmap-title", "ASHORE"));
        head.appendChild(
            element("span", "maritime-landmap-where", sheet && sheet.title ? sheet.title : "")
        );
        card.appendChild(head);

        function redraw() {
            if (typeof onRedraw === "function") {
                onRedraw();
            }
        }
        head.appendChild(controls(sheet, redraw));

        var plot = element("div", "maritime-plot maritime-landmap-plot");
        card.appendChild(plot);

        if (!sheet || !sheet.rooms || !sheet.rooms.length) {
            plot.textContent = "Nowhere to map.";
            return card;
        }

        var plan = layout(sheet);

        /* A view of somewhere else is no view at all. */
        var of = signature(sheet);
        if (camera.of !== of) {
            camera.of = of;
            fitTo(plan);
        }
        if (camera.want === "fit") {
            fitTo(plan);
        } else if (camera.want === "centre") {
            centreOn(plan, sheet);
        }
        camera.want = null;
        if (camera.x === null || camera.y === null) {
            fitTo(plan);
        }

        var svg = node("svg", {
            viewBox: viewBox(plan),
            preserveAspectRatio: "xMidYMid meet",
            class: "maritime-landmap-svg",
            role: "img",
            "aria-label": "Map of " + (sheet.title || "here")
        });

        var drawn = {};
        (sheet.edges || []).forEach(function (edge) {
            var a = plan.at[edge.from];
            var b = plan.at[edge.to];
            if (!a || !b) {
                return;
            }
            /* A ladder is not a street. The room it reaches is drawn beside its parent and
             * marked; a line between the two would say you can walk along it. */
            if (edge.climbs) {
                return;
            }
            if (Math.max(Math.abs(a.x - b.x), Math.abs(a.y - b.y)) > SPACING * LONGEST_WAY) {
                return;
            }
            var pair = edge.from < edge.to
                ? edge.from + ":" + edge.to
                : edge.to + ":" + edge.from;
            if (drawn[pair]) {
                return;
            }
            drawn[pair] = true;
            svg.appendChild(
                node("line", {
                    x1: a.x, y1: a.y, x2: b.x, y2: b.y,
                    stroke: WAY_COLOUR,
                    "stroke-width": WAY_WIDTH,
                    class: "maritime-landmap-way"
                })
            );
        });

        sheet.rooms.forEach(function (room) {
            var spot = plan.at[room.id];
            var look = MARKERS[room.marker] || MARKERS.plain;
            var group = node("g", {
                class: "maritime-landmap-room maritime-room-" + room.marker,
                tabindex: "0",
                role: "button"
            });

            if (look.ring) {
                group.appendChild(
                    node("circle", {
                        cx: spot.x, cy: spot.y, r: look.size + 5,
                        class: "maritime-landmap-ring"
                    })
                );
            }
            group.appendChild(
                node("circle", {
                    cx: spot.x, cy: spot.y, r: look.size, fill: look.fill
                })
            );

            /* A room with a way up or down out of it, marked rather than drawn. It is a
             * real exit and a player wants to know it is there; it is not a street and
             * drawing it as one is what made a waterfront unreadable. */
            if (room.stairs) {
                group.appendChild(
                    node("path", {
                        d: "M " + (spot.x - 3) + " " + (spot.y - look.size - 3) +
                           " L " + spot.x + " " + (spot.y - look.size - 7) +
                           " L " + (spot.x + 3) + " " + (spot.y - look.size - 3),
                        class: "maritime-landmap-stairs"
                    })
                );
            }

            var told = node("title");
            var means = MEANS[room.marker];
            told.textContent =
                room.name + (means ? " - " + means : "") + (room.stairs ? " (up or down)" : "");
            group.appendChild(told);

            if (room.id !== sheet.here) {
                group.addEventListener("click", function (event) {
                    event.stopPropagation();
                    stopWalking();
                    var path = routeTo(sheet.here, room.id, sheet.edges || []);
                    if (!path) {
                        return;
                    }
                    walk(directionsAlong(path, sheet.edges || []));
                });
            }
            svg.appendChild(group);
        });

        makeDraggable(svg, plan, redraw);
        plot.appendChild(svg);
        if (camera.legend) {
            card.appendChild(legend());
        }
        return card;
    }

    /* A legend, because a colour nobody can look up is a colour nobody learns.
     *
     * Behind the `i` rather than always on. It is read once, when somebody first wonders
     * what the green ones are, and after that it is a strip of the map's height spent
     * saying something the player already knows. */
    function legend() {
        var strip = element("div", "maritime-landmap-legend");
        ["here", "ship", "berth", "trade", "way_out"].forEach(function (kind) {
            var item = element("span", "maritime-legend-item");
            var dot = element("i");
            dot.style.background = MARKERS[kind].fill;
            item.appendChild(dot);
            item.appendChild(document.createTextNode(MEANS[kind]));
            strip.appendChild(item);
        });
        return strip;
    }

    return {
        render: render,
        routeTo: routeTo,
        directionsAlong: directionsAlong,
        stopWalking: stopWalking,
        layout: layout,
        MARKERS: MARKERS,
        MEANS: MEANS
    };
})();
