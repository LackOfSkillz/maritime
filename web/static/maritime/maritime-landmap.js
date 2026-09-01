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
 * COLOUR IS MEANING. Four markers and no more, because ashore there are only three
 * questions worth answering in colour - where am I, where is my ship, and where do I buy
 * things - and a map that colours eleven kinds of room answers none of them. Everything
 * else stays the same quiet tone so the three that matter carry.
 *
 * CLICKING WALKS. The route is a breadth-first search over the same edges that were drawn,
 * turned into the directions those edges are named after, and sent one at a time with a
 * pause between. Nothing is teleported: every step is the ordinary movement command a
 * player could have typed, so locks, exits and anything the game does on movement all
 * happen exactly as they would have.
 */
window.MaritimeLandMap = (function () {
    "use strict";

    /* What each marker is drawn in. The current room takes the strongest colour on the
     * panel because it is the one thing a player looks for first. */
    var MARKERS = {
        here: { fill: "#e2725b", ring: true, size: 6 },
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

    /* How far apart to draw two rooms that are one step apart, in pixels. */
    var SPACING = 34;

    /* How long to wait between steps of a walk, in milliseconds. Long enough that the
     * server's own movement messages arrive in order and a player can read them going by,
     * short enough that crossing a town is not a chore. */
    var STEP_MS = 320;

    var walking = { token: 0, going: false };

    function node(name, attributes) {
        var made = document.createElementNS("http://www.w3.org/2000/svg", name);
        Object.keys(attributes || {}).forEach(function (key) {
            made.setAttribute(key, attributes[key]);
        });
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

    function render(state, onRedraw) {
        var sheet = state.land;
        var card = document.createElement("div");
        card.className = "maritime-card maritime-landmap";

        var head = document.createElement("div");
        head.className = "maritime-card-head";
        head.textContent = sheet && sheet.title ? "ASHORE · " + sheet.title : "ASHORE";
        card.appendChild(head);

        var plot = document.createElement("div");
        plot.className = "maritime-plot";
        card.appendChild(plot);

        if (!sheet || !sheet.rooms || !sheet.rooms.length) {
            plot.textContent = "Nowhere to map.";
            return card;
        }

        var xs = sheet.rooms.map(function (r) { return r.x; });
        var ys = sheet.rooms.map(function (r) { return r.y; });
        var west = Math.min.apply(null, xs);
        var east = Math.max.apply(null, xs);
        var south = Math.min.apply(null, ys);
        var north = Math.max.apply(null, ys);

        var width = (east - west + 2) * SPACING;
        var height = (north - south + 2) * SPACING;
        var svg = node("svg", {
            viewBox: "0 0 " + width + " " + height,
            class: "maritime-landmap-svg",
            role: "img",
            "aria-label": "Map of " + (sheet.title || "here")
        });

        /* North is up, so the northing is flipped: the data counts north as positive and
         * a screen counts down. Getting this backwards mirrors the whole town and is very
         * hard to see unless you know the place. */
        function at(room) {
            return {
                x: (room.x - west + 1) * SPACING,
                y: (north - room.y + 1) * SPACING
            };
        }

        var where = {};
        sheet.rooms.forEach(function (room) {
            where[room.id] = at(room);
        });

        var drawn = {};
        (sheet.edges || []).forEach(function (edge) {
            var a = where[edge.from];
            var b = where[edge.to];
            if (!a || !b) {
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
                    class: "maritime-landmap-way"
                })
            );
        });

        sheet.rooms.forEach(function (room) {
            var spot = where[room.id];
            var look = MARKERS[room.marker] || MARKERS.plain;
            var group = node("g", {
                class: "maritime-landmap-room maritime-room-" + room.marker,
                tabindex: "0",
                role: "button"
            });

            if (look.ring) {
                group.appendChild(
                    node("circle", {
                        cx: spot.x, cy: spot.y, r: look.size + 4,
                        class: "maritime-landmap-ring"
                    })
                );
            }
            group.appendChild(
                node("circle", {
                    cx: spot.x, cy: spot.y, r: look.size, fill: look.fill
                })
            );

            var told = node("title");
            var means = MEANS[room.marker];
            told.textContent = room.name + (means ? " - " + means : "");
            group.appendChild(told);

            if (room.id !== sheet.here) {
                group.addEventListener("click", function () {
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

        plot.appendChild(svg);
        card.appendChild(legend());
        return card;
    }

    /* A legend, because a colour nobody can look up is a colour nobody learns. Four
     * entries and no room for a fifth, which is the same argument as having four markers. */
    function legend() {
        var strip = document.createElement("div");
        strip.className = "maritime-landmap-legend";
        [["here", "here"], ["ship", "ship"], ["berth", "berth"], ["trade", "trade"]].forEach(
            function (pair) {
                var item = document.createElement("span");
                item.className = "maritime-legend-item";
                var dot = document.createElement("i");
                dot.style.background = MARKERS[pair[0]].fill;
                item.appendChild(dot);
                item.appendChild(document.createTextNode(pair[1]));
                strip.appendChild(item);
            }
        );
        return strip;
    }

    return {
        render: render,
        routeTo: routeTo,
        directionsAlong: directionsAlong,
        stopWalking: stopWalking,
        MARKERS: MARKERS
    };
})();
