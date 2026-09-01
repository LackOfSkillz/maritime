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

    /* How much further out to fit than the furthest contact, so there is sea around
     * her rather than a rim. */
    var FIT_MARGIN = 1.6;

    /* Where the chart opens when there is nothing in sight to frame: a couple of
     * kilometres, which is the water a coasting vessel is about to be in. */
    var DEFAULT_SCALE = 2;

    /* The chart's box, in screen pixels, with the ship at the origin.
     *
     * ONE USER UNIT IS ONE PIXEL, which is the whole point of measuring it. The drawing
     * used to live in a square of a thousand units scaled to fit, and every stroke and
     * label was therefore specified in units that were some unknown fraction of a
     * pixel. Widening that square to fill a wide pane made the fraction smaller still:
     * a 1.5-unit range ring came out at about six tenths of a pixel, which is not a
     * faint ring but a ring the browser can barely draw. Fonts went the same way.
     *
     * Drawing in pixels means a 2-pixel stroke is two pixels and a 16-pixel sounding is
     * sixteen, at any zoom, in any shaped box - and it removes the aspect arithmetic
     * entirely, because a wider box simply has a wider viewBox.
     *
     * A square to start with, replaced the moment anything is measured. */
    var box = { width: 1000, height: 1000 };

    /* How much of the half-height the outer range ring takes, leaving margin for its
     * own label. */
    var RING_INSET = 0.92;

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

    /* Whether the box has been measured yet.
     *
     * The first draw happens before any layout, so the aspect is still the opening
     * guess and a sheet asked for now would be the wrong width. It arrived, drew, and
     * was replaced moments later by the right one - which is the flash: two different
     * charts, a beat apart, for one page load. Requests wait until the shape is known,
     * and then there is only ever one. */
    var measured = typeof window.ResizeObserver !== "function";

    function askForSheet() {
        if (!measured) {
            return;
        }
        if (askTimer) {
            window.clearTimeout(askTimer);
        }
        askTimer = window.setTimeout(function () {
            askTimer = null;
            if (window.Evennia && typeof Evennia.msg === "function") {
                /* Where it is looking as well as how far.
                 *
                 * The pan is in pixels on a sheet already drawn; turned back into metres
                 * it says how far off her position the captain has slid the chart, which
                 * is what the server needs in order to draw somewhere else. Without it,
                 * dragging moved one fixed square about inside its window and the corner
                 * arrived in the middle with nothing behind it. */
                var scale = pixelsPerMetre();
                asked.panX = view.panX;
                asked.panY = view.panY;
                Evennia.msg("maritime_view", [], {
                    reach: sheetReach(),
                    east: scale ? -view.panX / scale : 0,
                    north: scale ? view.panY / scale : 0
                });
            }
        }, 250);
    }

    /* The pan that was in force when the last request went out.
     *
     * When the sheet comes back it is already drawn around the point that pan pointed at,
     * so keeping the pan as well would count the drag twice and the chart would leap away
     * at every request. Subtracting what was asked for - rather than zeroing - keeps
     * whatever dragging happened while the round trip was in flight, which is most of it
     * when somebody is sweeping the chart along a coast. */
    var asked = { panX: 0, panY: 0 };

    var lastSheet = null;

    function settlePan(sheet) {
        /* Only when a *new* sheet has arrived. The chart is redrawn for contacts, for
         * status, for a resize - and settling on any of those would subtract a pan that
         * no sheet had yet answered, walking the view sideways every few seconds. */
        if (sheet === lastSheet) {
            return false;
        }
        lastSheet = sheet;
        view.panX -= asked.panX;
        view.panY -= asked.panY;
        asked.panX = 0;
        asked.panY = 0;
        return true;
    }

    function reach() {
        return SCALES[Math.max(0, Math.min(SCALES.length - 1, view.scaleIndex))];
    }

    /* Pixels to the metre.
     *
     * Set by the captain's chosen scale against the *shorter* edge, so the reach ring
     * fits whatever shape the box is and a wider pane shows more sea rather than a
     * bigger ship. */
    function pixelsPerMetre() {
        return (Math.min(box.width, box.height) / 2) * RING_INSET / reach();
    }

    /* How much sea the server has to draw to fill this box, which is not the scale the
     * captain chose. He picks how far the rings reach; the box then shows whatever else
     * fits around them, and a sheet drawn only to his scale would leave that water
     * blank - an unsurveyed-looking hole that is really just the edge of what we
     * thought to ask for. Computed from the box rather than estimated from its shape. */
    function sheetReach() {
        return Math.round(Math.max(box.width, box.height) / 2 / pixelsPerMetre());
    }

    /* The window onto the drawing: the box itself, with the ship at the origin. */
    function viewBox() {
        return (
            (-box.width / 2 - view.panX) + " " +
            (-box.height / 2 - view.panY) + " " +
            box.width + " " + box.height
        );
    }

    /* Watch the box rather than the window: a pane can change shape because the player
     * dragged a splitter, opened a panel, or rotated a phone, and only one of those is
     * a window resize. */
    function watchShape(svg, redraw) {
        if (typeof window.ResizeObserver !== "function") {
            return;
        }
        var observer = new window.ResizeObserver(function (entries) {
            var shape = entries[0] && entries[0].contentRect;
            if (!shape || !shape.width || !shape.height) {
                return;
            }
            // A hair of tolerance, or a sub-pixel reflow redraws the chart forever.
            if (measured && Math.abs(box.width - shape.width) < 1
                && Math.abs(box.height - shape.height) < 1) {
                return;
            }
            box = { width: shape.width, height: shape.height };
            measured = true;
            svg.setAttribute("viewBox", viewBox());
            askForSheet();
            if (typeof redraw === "function") {
                redraw();
            }
        });
        observer.observe(svg);
    }

    /* Where a thing lies from the ship, in metres north and east, given what the
     * lookout reported. Bearings are true, so north is up until somebody asks for
     * head-up. */
    function offsetOf(bearingDegrees, metres) {
        var radians = (bearingDegrees * Math.PI) / 180;
        return { east: Math.sin(radians) * metres, north: Math.cos(radians) * metres };
    }

    /* Metres from the ship, to pixels from the centre of the box. North is up, so the
     * y axis runs the other way from the chart's. */
    /* Metres from the ship into pixels on the drawing.
     *
     * The pan is deliberately *not* here. It lives in the viewBox, so dragging moves the
     * window over a drawing that never changes - which means a drag is one attribute
     * write instead of rebuilding every path, and everything moves together including
     * the relief picture, which is not placed through this function at all. */
    function toChart(offset) {
        var scale = pixelsPerMetre();
        return { x: offset.east * scale, y: -offset.north * scale };
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
            var radius = span * fraction * pixelsPerMetre();
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
    function drawOwnVessel(into, heading, own) {
        /* Where she lies *on this sheet*, which is the middle of it only until somebody
         * drags the chart. Drawn at her offset rather than at the centre, or a captain
         * looking up the coast would see his own ship gliding along with the view. */
        var at = own && own.length === 2 ? { east: own[0], north: own[1] } : { east: 0, north: 0 };
        var centre = toChart(at);
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
     * reckons she is, so this is the only place the chart turns knowledge into pixels.
     *
     * DRAWN AS A CURVE THROUGH THE POINTS, NOT AS A ROAD BETWEEN THEM.
     *
     * The points come off a grid, so a straight-segment path turns every one of them into
     * a corner and the coastline reads as a staircase - worst at a wide zoom, where a cell
     * is hundreds of metres and there are few enough points to count.
     *
     * This is Catmull-Rom, written out as the cubic Bezier that SVG takes. It passes
     * through every point exactly: it is not a smoothing, it averages nothing, and it
     * invents no shoreline. What it stops doing is asserting that the coast turns a hard
     * corner at each place somebody happened to sound - which is the honest reading, since
     * the survey found those points and never claimed the water between them ran straight.
     *
     * A chart drawn by hand looks like this because a hand does not draw corners it has no
     * evidence for either. */
    function pathOf(line) {
        var points = [];
        for (var i = 0; i < line.length; i++) {
            points.push(toChart({ east: line[i][0], north: line[i][1] }));
        }
        if (points.length < 3) {
            return points
                .map(function (at, index) {
                    return (index ? "L" : "M") + at.x.toFixed(1) + " " + at.y.toFixed(1);
                })
                .join(" ");
        }

        /* A closed run - an island, or a patch of shoal - takes its neighbours round the
         * loop, so the curve meets itself without a kink where the ends join. */
        var first = points[0];
        var last = points[points.length - 1];
        var closed = Math.abs(first.x - last.x) < 0.5 && Math.abs(first.y - last.y) < 0.5;

        function nth(index) {
            if (closed) {
                var span = points.length - 1;
                return points[((index % span) + span) % span];
            }
            return points[Math.max(0, Math.min(points.length - 1, index))];
        }

        var parts = ["M" + first.x.toFixed(1) + " " + first.y.toFixed(1)];
        for (var n = 0; n < points.length - 1; n++) {
            var before = nth(n - 1);
            var here = nth(n);
            var next = nth(n + 1);
            var after = nth(n + 2);
            /* A sixth of the span to the neighbours: the uniform Catmull-Rom tangent,
             * taut enough not to overshoot into the land it is drawing round. */
            var firstX = here.x + (next.x - before.x) / 6;
            var firstY = here.y + (next.y - before.y) / 6;
            var secondX = next.x - (after.x - here.x) / 6;
            var secondY = next.y - (after.y - here.y) / 6;
            parts.push(
                "C" + firstX.toFixed(1) + " " + firstY.toFixed(1) +
                " " + secondX.toFixed(1) + " " + secondY.toFixed(1) +
                " " + next.x.toFixed(1) + " " + next.y.toFixed(1)
            );
        }
        return parts.join(" ");
    }

    /* The shape of the bottom, shaded, when the game has the libraries to draw it.
     *
     * Optional at every layer: a payload with no relief in it draws none, which is the
     * interface every game had before this and the one a game without numpy still has.
     *
     * Placed by the same offsets as everything else on the sheet, under the contours
     * rather than over them - the lines are what was surveyed and stay legible on top.
     * The browser scales the picture, which is wanted: it is a shading of a few thousand
     * soundings and smoothing it is truer to what it represents than showing its pixels.
     *
     * Not clickable, not focusable, no title. It is the paper, not a thing on it. */
    function drawRelief(into, sheet) {
        if (!sheet || !sheet.relief) {
            return;
        }
        /* The *sheet's* reach, not the captain's scale. He picks how far the rings
         * reach; the server draws whatever fills the box around them, and sizing the
         * picture by his scale would stretch it over the wrong square of sea - visibly
         * so at any zoom where the two differ, which is most of them. */
        var side = (Number(sheet.reach) || reach()) * 2 * pixelsPerMetre();
        var picture = node("image", {
            x: -side / 2,
            y: -side / 2,
            width: side,
            height: side,
            preserveAspectRatio: "none",
            class: "maritime-chart-relief"
        });
        picture.setAttributeNS(
            "http://www.w3.org/1999/xlink", "xlink:href", sheet.relief
        );
        picture.setAttribute("href", sheet.relief);
        into.appendChild(picture);
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

        /* Where the survey stops.
         *
         * Off the chart is a state, not a failure, and a navigator wants to see the edge
         * coming rather than discover it by finding no soundings under him.
         *
         * The water beyond it is *hatched and named*, not left blank. Blank reads as
         * "there is nothing there", and there is a great deal there - it is simply that
         * nobody aboard has a survey of it. The distinction is the whole difference
         * between the edge of the world and the edge of the paper.
         *
         * Drawn as four bands around the sheet rather than as a hole in one shape,
         * because SVG has no even-odd fill that survives a viewBox this large without
         * artefacts, and four rectangles are easier to be sure about. */
        if (sheet.coverage && typeof sheet.coverage.west === "number") {
            var topLeft = toChart({ east: sheet.coverage.west, north: sheet.coverage.north });
            var bottomRight = toChart({ east: sheet.coverage.east, north: sheet.coverage.south });
            var far = Math.max(box.width, box.height) * 3;

            [
                { x: -far, y: -far, width: far * 2, height: far + topLeft.y },
                { x: -far, y: bottomRight.y, width: far * 2, height: far },
                { x: -far, y: topLeft.y, width: far + topLeft.x, height: bottomRight.y - topLeft.y },
                { x: bottomRight.x, y: topLeft.y, width: far, height: bottomRight.y - topLeft.y }
            ].forEach(function (band) {
                if (band.width <= 0 || band.height <= 0) {
                    return;
                }
                layers.overlay.appendChild(
                    node("rect", {
                        x: band.x, y: band.y,
                        width: band.width, height: band.height,
                        fill: "url(#maritime-unsurveyed)",
                        class: "maritime-chart-unsurveyed"
                    })
                );
            });

            layers.overlay.appendChild(
                node("rect", {
                    x: topLeft.x,
                    y: topLeft.y,
                    width: Math.max(0, bottomRight.x - topLeft.x),
                    height: Math.max(0, bottomRight.y - topLeft.y),
                    class: "maritime-chart-coverage"
                })
            );

            /* Named, once, where there is room for the words. A hatch a player has not
             * met before is a texture; a hatch with UNSURVEYED written in it is a fact. */
            labelTheUnsurveyed(layers.overlay, topLeft, bottomRight);
        }
    }

    /* The meridians and parallels the sheet is ruled with.
     *
     * Two jobs, and the second is the reason this exists.
     *
     * The first is the ordinary one: a navigator reads a position off a graticule, and a
     * chart without one is a picture rather than a chart.
     *
     * The second is curvature. This is a flat sheet on a round world, and the honest way
     * to show that is not to bend the picture - it is to draw the lines that actually
     * *are* bent and let the reader see them do it. Meridians converge towards the pole,
     * so at a close scale they stand parallel to within a few metres and at a wide one
     * they visibly lean together. The player zooms out and the world stops being square.
     *
     * The lines are computed on the server, from the projection, and drawn here exactly
     * as sent. The client does no geography: the curve arrives already curved.
     *
     * Nothing at all for a world with no geography. A seabed defined by an arithmetic
     * ramp has no latitude, the payload carries no graticule, and the chart is ruled with
     * nothing rather than with invented degrees. */
    function drawGraticule(into, sheet) {
        if (!sheet || !sheet.graticule || !sheet.graticule.length) {
            return;
        }
        var left = -box.width / 2 - view.panX;
        var bottom = box.height / 2 - view.panY;

        sheet.graticule.forEach(function (ruled) {
            if (!ruled.line || ruled.line.length < 2) {
                return;
            }
            into.appendChild(
                node("path", {
                    d: pathOf(ruled.line),
                    class: "maritime-chart-graticule maritime-chart-graticule-" + ruled.kind
                })
            );

            /* Labelled in the margin it runs out of, the way a printed chart does:
             * parallels read up the left-hand edge, meridians along the bottom. Placing
             * the figure at the end of the run rather than at a fixed spot keeps it with
             * its own line when the sheet is dragged, and off the middle of the chart
             * where the soundings are. */
            var wanted = ruled.kind === "parallel" ? left : bottom;
            var best = null;
            var nearest = Infinity;
            for (var i = 0; i < ruled.line.length; i++) {
                var at = toChart({ east: ruled.line[i][0], north: ruled.line[i][1] });
                var away = ruled.kind === "parallel"
                    ? Math.abs(at.x - wanted)
                    : Math.abs(at.y - wanted);
                if (away < nearest) {
                    nearest = away;
                    best = at;
                }
            }
            if (!best) {
                return;
            }
            var figure = node("text", {
                x: ruled.kind === "parallel" ? best.x + 6 : best.x,
                y: ruled.kind === "parallel" ? best.y - 4 : best.y - 6,
                class: "maritime-chart-graticule-label",
                "text-anchor": ruled.kind === "parallel" ? "start" : "middle"
            });
            figure.textContent = ruled.label;
            into.appendChild(figure);
        });
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

    /* Rocks, wrecks and shoals the survey found, drawn as the chart draws them.
     *
     * Deliberately unlike a buoy. A buoy is a thing somebody moored and it can drag; a
     * rock is a thing somebody found and it cannot. Real charts use a starred symbol
     * for an isolated danger and print the least depth over it, so this does the same,
     * and one that dries gets the same shape with the figure omitted - there is no
     * depth over it to print.
     *
     * They are here rather than in the soundings because sampling cannot find them. A
     * grid four hundred metres across steps straight over a rock a hundred wide, and
     * whether it steps over this one depends on where the grid falls, so the danger
     * would appear and vanish as she sailed. */
    function drawDangers(into, dangers) {
        (Array.isArray(dangers) ? dangers : []).forEach(function (danger) {
            if (!danger || typeof danger.east !== "number") {
                return;
            }
            var span = reach();
            if (Math.abs(danger.east) > span * 1.05 || Math.abs(danger.north) > span * 1.05) {
                return;
            }

            var at = toChart({ east: danger.east, north: danger.north });
            var group = node("g", {
                class:
                    "maritime-chart-danger" +
                    (danger.dries ? " maritime-danger-dries" : "") +
                    (danger.ashore ? " maritime-danger-ashore" : ""),
                tabindex: "0",
                role: "button"
            });

            /* A star: four strokes through the point, which is the symbol a chart uses
             * and which reads at any size without needing a fill. */
            [[0, -7, 0, 7], [-7, 0, 7, 0], [-5, -5, 5, 5], [-5, 5, 5, -5]].forEach(
                function (arm) {
                    group.appendChild(
                        node("line", {
                            x1: at.x + arm[0], y1: at.y + arm[1],
                            x2: at.x + arm[2], y2: at.y + arm[3]
                        })
                    );
                }
            );

            /* The least depth over it, which is the number that decides whether she
             * may pass. Omitted where it dries, because there is no water to quote. */
            if (!danger.dries && !danger.ashore && typeof danger.top_z === "number") {
                var figure = node("text", {
                    x: at.x + 9, y: at.y + 4, class: "maritime-danger-depth"
                });
                figure.textContent = fathomsOf(-danger.top_z);
                group.appendChild(figure);
            }

            var told = node("title");
            told.textContent =
                (danger.label || "danger") +
                (danger.ashore
                    ? " - an island, " + Math.abs(danger.top_z).toFixed(0) + " m high"
                    : danger.dries
                    ? " - dries " + Math.abs(danger.top_z).toFixed(1) + " m"
                    : " - " + Math.abs(danger.top_z).toFixed(1) + " m over it") +
                (danger.bottom ? ", " + danger.bottom : "");
            group.appendChild(told);
            into.appendChild(group);
        });
    }

    /* Metres as a chart prints them, which is whatever unit the sheet is drawn in.
     * Metres here, to one decimal under ten and whole numbers above, because a
     * navigator reads "3.4" on a shoal and "27" in the deep. */
    function fathomsOf(metres) {
        if (!isFinite(metres)) {
            return "";
        }
        return metres < 10 ? metres.toFixed(1) : String(Math.round(metres));
    }

    /* Write UNSURVEYED in whichever margin has room for it.
     *
     * One label, not four: the point is to say what the hatching means, and saying it in
     * every direction at once is shouting. The widest margin wins, which is also the one
     * a player is most likely to be looking at when they sail off the paper. */
    function labelTheUnsurveyed(into, topLeft, bottomRight) {
        var edge = box.width / 2;
        var lip = box.height / 2;
        var margins = [
            { room: edge - bottomRight.x, x: (bottomRight.x + edge) / 2, y: 0 },
            { room: topLeft.x + edge, x: (topLeft.x - edge) / 2, y: 0 },
            { room: lip - bottomRight.y, x: 0, y: (bottomRight.y + lip) / 2 },
            { room: topLeft.y + lip, x: 0, y: (topLeft.y - lip) / 2 }
        ];
        margins.sort(function (a, b) { return b.room - a.room; });
        if (margins[0].room < 70) {
            return;
        }
        var said = node("text", {
            x: margins[0].x,
            y: margins[0].y,
            class: "maritime-chart-unsurveyed-label",
            "text-anchor": "middle"
        });
        said.textContent = "UNSURVEYED";
        into.appendChild(said);
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
                asked.panX = 0;
                asked.panY = 0;
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
        /* Room around the furthest thing in sight rather than a scale that just
         * contains it. Fitted exactly, the outermost contact sits on the rim with no
         * sea beyond her, which reads as the edge of the world instead of the edge of
         * the lookout's report - and leaves nowhere to see her stand into. */
        var wanted = furthest * FIT_MARGIN;
        view.scaleIndex = SCALES.length - 1;
        for (var i = 0; i < SCALES.length; i++) {
            if (SCALES[i] >= wanted) {
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
            /* MOVE THE WINDOW, DO NOT REBUILD THE DRAWING.
             *
             * This called `redraw()`, which rebuilds the whole interface and hands back a
             * brand new `<svg>`. The element the drag started on was thrown away on the
             * first pointermove, and the replacement had never seen a pointerdown - so a
             * drag moved the chart once, by a few pixels, and then stopped dead. It read
             * as "you cannot drag the map".
             *
             * The pan lives in the viewBox, so panning is one attribute on the element
             * already under the finger. Nothing is re-rendered and nothing is replaced.
             *
             * The drawing is in screen pixels, so the distance the finger moved is the
             * distance the chart moves, with no conversion at all. */
            view.held = true;
            view.panX += event.clientX - lastX;
            view.panY += event.clientY - lastY;
            lastX = event.clientX;
            lastY = event.clientY;
            svg.setAttribute("viewBox", viewBox());
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
            viewBox: viewBox(),
            preserveAspectRatio: "xMidYMid slice",
            class: "maritime-chart",
            role: "img",
            "aria-label": "Chart showing own vessel and contacts in sight"
        });

        /* The hatch that means nobody surveyed this.
         *
         * Defined per sheet rather than once in the page, because the chart is rebuilt
         * wholesale on every zoom and a pattern living in a document the drawing no
         * longer belongs to resolves to nothing - which paints the unsurveyed water
         * solid black, and is exactly what happened the first time this was tried. */
        var defs = node("defs", {});
        var hatch = node("pattern", {
            id: "maritime-unsurveyed",
            width: 9,
            height: 9,
            patternUnits: "userSpaceOnUse",
            patternTransform: "rotate(45)"
        });
        hatch.appendChild(node("rect", { width: 9, height: 9, class: "maritime-hatch-ground" }));
        hatch.appendChild(
            node("line", { x1: 0, y1: 0, x2: 0, y2: 9, class: "maritime-hatch-line" })
        );
        defs.appendChild(hatch);
        svg.appendChild(defs);

        /* The sea, and anything a host has hung behind the plot, live on a box under
         * the drawing rather than inside it.
         *
         * Inside would have been fewer elements, but everything in there is in chart
         * coordinates, and a compass rose that slides off the corner when a player
         * drags the chart is a rose drawn on the sea instead of on the paper. These
         * stay where the paper stays. It also buys a real opacity per layer, which
         * matters when the whole point of a texture is that it is barely there. */
        var plot = document.createElement("div");
        plot.className = "maritime-chart-plot";

        var paper = document.createElement("div");
        paper.className = "maritime-paper";
        plot.appendChild(paper);

        /* One compass, and it carries its own lettering.
         *
         * The cardinals used to be drawn inside the SVG at a fixed corner of a square
         * viewBox. Widening that viewBox left them floating somewhere near the middle,
         * because the corner had moved and the drawing had not - and putting them back
         * would have meant the letters and the engraving behind them agreeing about
         * two coordinate systems, one of which a host can restyle.
         *
         * So the rose is one element that positions itself: the engraving is its
         * background when a game supplies one, the letters are its children either
         * way, and the whole thing sits where CSS puts it. A game with no artwork
         * still gets a compass, which it must - which way is north is not decoration. */
        var rose = document.createElement("div");
        rose.className = "maritime-rose";
        rose.setAttribute("aria-hidden", "true");
        ["N", "E", "S", "W"].forEach(function (point) {
            var letter = document.createElement("span");
            letter.className = "maritime-cardinal maritime-cardinal-" + point.toLowerCase();
            letter.textContent = point;
            rose.appendChild(letter);
        });
        plot.appendChild(rose);

        var layers = {};
        ["relief", "graticule", "depths", "land", "soundings", "rings", "dangers", "marks", "contacts", "own", "overlay"].forEach(function (name) {
            layers[name] = node("g", { class: "maritime-layer-" + name });
            svg.appendChild(layers[name]);
        });

        /* Nothing is drawn until the box has been measured.
         *
         * The first paint happens before any layout, so every distance would be
         * computed against a guessed box and every figure placed accordingly - which
         * is what put a block of soundings in a hundred pixels and a coastline at the
         * wrong scale, twice, on the way to the right one. One empty sea for a frame
         * beats two wrong charts. */
        if (measured) {
            if (settlePan(state.chart)) {
                svg.setAttribute("viewBox", viewBox());
            }
            drawRelief(layers.relief, state.chart);
            drawGraticule(layers.graticule, state.chart);
            drawSheet(layers, state.chart);
            if (state.chart) {
                drawRoute(layers.marks, state.chart.route);
                drawDangers(layers.dangers, state.chart.dangers);
                drawMarks(layers.marks, state.chart.marks);
            }
            drawRings(layers.rings);
        }
        if (measured) {
            drawContacts(layers.contacts, state.contacts, function (id) {
                MaritimeState.select(id);
            }, state.selectedContactId);
        }

        var motion = (state.status && state.status.motion) || {};
        if (measured) {
            drawOwnVessel(layers.own, motion.heading, state.chart && state.chart.own);
        }

        makeDraggable(svg, redraw);
        watchShape(svg, redraw);

        plot.appendChild(svg);
        /* On the chart rather than under it. They act on what is drawn, and a control
         * that acts on a picture belongs against the picture - which also gives the
         * chart back the strip of height the bar was taking from it. */
        plot.appendChild(controls(redraw));
        card.appendChild(plot);
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
