/*
 * Putting the interface up, and taking it down again.
 *
 * The composition layer: it owns the root element, decides when there should be one,
 * and asks the panels to draw themselves. It holds no ship state and speaks to no
 * server.
 *
 * **Additive unless asked.** The interface adds a container; it does not move,
 * resize or restyle anything the host game had. A player's own layout is not ours to
 * touch, and a client whose panes were shuffled by a contrib is a client whose author
 * will remove the contrib.
 *
 * **Mounting is idempotent.** Being told "command" three times must not build the DOM
 * three times, and being told the same mode twice must not steal focus from somebody
 * halfway through typing.
 */

window.MaritimeUI = (function () {
    "use strict";

    var ROOT_ID = "maritime-root";

    var root = null;
    var mounted = false;
    var lastDrawn = null;

    /* Where to put ourselves.
     *
     * A host game that has decided where this belongs provides the element and we use
     * it. A stock client has not, so one is made and parked at the top of the page -
     * enough to see the thing work without anybody editing a template first. */
    function findMount() {
        var provided = document.getElementById(ROOT_ID);
        if (provided) {
            return provided;
        }
        var made = document.createElement("div");
        made.id = ROOT_ID;
        made.setAttribute("data-maritime-owned", "true");
        document.body.insertBefore(made, document.body.firstChild);
        return made;
    }

    function mount(element) {
        if (mounted) {
            return root;
        }
        root = element || findMount();
        root.setAttribute("role", "region");
        root.setAttribute("aria-label", "Maritime interface");
        mounted = true;
        return root;
    }

    function unmount() {
        if (!mounted || !root) {
            return;
        }
        root.innerHTML = "";
        root.classList.remove("maritime-on");
        /* Only remove the container if we made it. An element the host game supplied
         * is theirs, and taking it out of their document would be exactly the kind of
         * rearranging this file exists not to do. */
        if (root.getAttribute("data-maritime-owned") === "true" && root.parentNode) {
            root.parentNode.removeChild(root);
            root = null;
        }
        mounted = false;
        lastDrawn = null;
    }

    /* A cheap signature of everything currently drawable. Redrawing only when it
     * changes is what keeps a tab a player selected from being rebuilt underneath
     * them every time a heading ticks over. */
    function signature(state) {
        return [
            state.mode,
            state.vesselId,
            state.land ? JSON.stringify(state.land) : "",
            state.preferences.panel,
            state.status ? JSON.stringify(state.status) : "",
            state.contacts ? state.contacts.length : 0,
            state.contacts ? JSON.stringify(state.contacts) : "",
            state.selectedContactId,
            state.chart ? state.chart.revision : ""
        ].join("|");
    }

    function render(state) {
        if (!MaritimeState.isMaritime()) {
            if (mounted) {
                unmount();
            }
            return;
        }

        mount();
        var now = signature(state);
        if (now === lastDrawn) {
            return;
        }
        lastDrawn = now;

        root.innerHTML = "";
        root.classList.add("maritime-on");

        root.appendChild(MaritimePanels.renderStrip(state));

        var pane = document.createElement("div");
        pane.className = "maritime-pane";
        /* Ashore there is no chart to draw and no sense in drawing one: the panel shows
         * the place instead. Aboard it goes back to the sea, and the two never share a
         * pane because they are not two views of one thing. */
        if (state.mode === "ashore" && window.MaritimeLandMap) {
            pane.appendChild(MaritimeLandMap.render(state, function () {
                lastDrawn = null;
                render(MaritimeState.get());
            }));
        } else if (window.MaritimeChart) {
            pane.appendChild(MaritimeChart.render(state, function () {
                /* A pan or a zoom changes nothing the server knows, so the redraw is
                 * forced rather than waiting for state to change. */
                lastDrawn = null;
                render(MaritimeState.get());
            }));
        } else {
            pane.appendChild(MaritimePanels.renderChartPlaceholder());
        }
        pane.appendChild(
            MaritimePanels.renderTabs(state, function (panel) {
                MaritimeState.setPreference("panel", panel);
            })
        );
        pane.appendChild(MaritimePanels.renderPanelBody(state));

        /* The board sits under everything rather than inside a panel, because the
         * orders on it are the ones a captain gives while looking at the chart - and
         * an order that needs a tab found first is an order given late. */
        var board = MaritimePanels.renderControlGrid(state);
        if (board) {
            pane.appendChild(board);
        }
        root.appendChild(pane);
    }

    function setMode(mode) {
        MaritimeState.applyMode({ mode: mode, version: MaritimeState.PROTOCOL_VERSION });
    }

    function start() {
        MaritimeState.loadPreferences();
        MaritimeState.onChange(render);
        MaritimeTransport.start();
        render(MaritimeState.get());
    }

    return {
        ROOT_ID: ROOT_ID,
        mount: mount,
        unmount: unmount,
        render: render,
        setMode: setMode,
        start: start,
        isMounted: function () {
            return mounted;
        }
    };
})();

/* Register with the webclient if it is there, and simply run if it is not - the panel
 * is useful in a plain page during development, and refusing to start without a plugin
 * host would make it untestable outside a running game. */
(function () {
    "use strict";

    function begin() {
        try {
            MaritimeUI.start();
        } catch (err) {
            /* Nothing here may take the terminal down with it. A player whose chart
             * failed is a player sailing by text, which is the whole point of the
             * protocol being optional. */
            if (window.console) {
                console.error("maritime: interface failed to start", err);
            }
        }
    }

    if (window.plugin_handler && typeof plugin_handler.add === "function") {
        plugin_handler.add("maritime", { init: begin });
    } else if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", begin);
    } else {
        begin();
    }
})();
