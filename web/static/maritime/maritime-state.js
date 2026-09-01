/*
 * What the client believes, and nothing about how it looks.
 *
 * One object, changed in one place. The alternative is state living in whichever DOM
 * node happened to render it, and the first time two panels disagree about which ship
 * you are on, there is nowhere to look.
 *
 * Nothing here is authoritative. Every field arrives from the server, and the browser's
 * job is to remember the last thing it was told - not to work anything out. When a
 * value is missing it stays missing; the client never fills a gap with a guess, because
 * a guessed depth reads exactly like a sounded one.
 */

window.MaritimeState = (function () {
    "use strict";

    var PROTOCOL_VERSION = 1;

    /* Preferences are the player's own and may be remembered locally. Nothing about
     * the ship may: a position in localStorage is a position that outlives the voyage
     * and comes back wrong. */
    var PREFERENCES_KEY = "maritime.preferences";

    var state = {
        protocolVersion: PROTOCOL_VERSION,
        serverVersion: null,
        capabilities: [],

        mode: "none",
        vesselId: null,

        status: null,
        chart: null,
        land: null,
        contacts: [],

        selectedContactId: null,

        preferences: {
            panel: "helm",
            followVessel: true,
            zoom: 1
        }
    };

    var listeners = [];

    /* Announce a change once, after it has been made. Callers get the whole state
     * rather than a diff, because a renderer that has to reconstruct the picture from
     * a sequence of diffs is a renderer that will eventually miss one. */
    function changed() {
        for (var i = 0; i < listeners.length; i++) {
            try {
                listeners[i](state);
            } catch (err) {
                /* One broken panel must not stop the others being drawn. */
                if (window.console) {
                    console.error("maritime: a listener failed", err);
                }
            }
        }
    }

    function onChange(listener) {
        listeners.push(listener);
    }

    function get() {
        return state;
    }

    /* --- applying what the server said ------------------------------------- */

    /* Everything arriving from the server goes through here first.
     *
     * A payload from a newer server may carry fields this build has never heard of,
     * and one from an older server may be missing fields this build expects. Neither
     * may throw: a client that falls over on an unfamiliar message is a client that
     * breaks every time the server is upgraded before it is. Unknown fields are kept
     * and ignored; missing ones stay missing and are simply not drawn. */
    function usable(payload) {
        if (!payload || typeof payload !== "object") {
            return null;
        }
        var version = payload.version;
        if (typeof version === "number" && version > PROTOCOL_VERSION && window.console) {
            console.warn(
                "maritime: server speaks protocol " + version + ", this client speaks " +
                PROTOCOL_VERSION + " - showing what is recognised"
            );
        }
        return payload;
    }

    function applyMode(payload) {
        payload = usable(payload);
        if (!payload) {
            return;
        }
        state.serverVersion = payload.version || null;
        state.mode = payload.mode || "none";
        state.vesselId = payload.vessel_id || null;

        /* Leaving the maritime world clears everything the ship was. Keeping a stale
         * chart around would mean a player who stepped ashore and back aboard a
         * different ship briefly sees the wrong one. */
        if (state.mode === "none") {
            state.status = null;
            state.chart = null;
            state.contacts = [];
            state.selectedContactId = null;
        }
        changed();
    }

    function applyStatus(payload) {
        payload = usable(payload);
        if (!payload) {
            return;
        }
        state.status = payload;
        if (payload.units && window.MaritimePanels) {
            MaritimePanels.setUnits(payload.units);
        }
        changed();
    }

    function applyContacts(payload) {
        payload = usable(payload);
        if (!payload) {
            return;
        }
        /* Replaced wholesale, never merged. A contact list is what the lookout has
         * right now; merging would keep ships on the board after they were lost, and
         * a mark that outlives the sighting is a radar return. */
        state.contacts = Array.isArray(payload.contacts) ? payload.contacts : [];
        changed();
    }

    function applyChart(payload) {
        payload = usable(payload);
        if (!payload) {
            return;
        }
        state.chart = payload;
        changed();
    }

    /* The map ashore. Kept beside the chart rather than replacing it, so walking back
     * aboard shows the sea again without waiting for a fresh sheet to be drawn. */
    function applyLand(payload) {
        payload = usable(payload);
        if (!payload) {
            return;
        }
        state.land = payload;
        changed();
    }

    function applySync(payload) {
        if (!payload) {
            return;
        }
        state.serverVersion = payload.version || null;
        state.capabilities = Array.isArray(payload.capabilities) ? payload.capabilities : [];
        applyMode(payload.mode);
        if (payload.status) {
            applyStatus(payload.status);
        }
    }

    /* --- preferences --------------------------------------------------------- */

    function loadPreferences() {
        try {
            var saved = window.localStorage.getItem(PREFERENCES_KEY);
            if (saved) {
                var parsed = JSON.parse(saved);
                for (var key in parsed) {
                    if (Object.prototype.hasOwnProperty.call(state.preferences, key)) {
                        state.preferences[key] = parsed[key];
                    }
                }
            }
        } catch (err) {
            /* A browser with storage disabled, or a corrupt value somebody edited by
             * hand. Defaults are perfectly good. */
        }
        return state.preferences;
    }

    function setPreference(key, value) {
        if (!Object.prototype.hasOwnProperty.call(state.preferences, key)) {
            return;
        }
        state.preferences[key] = value;
        try {
            window.localStorage.setItem(PREFERENCES_KEY, JSON.stringify(state.preferences));
        } catch (err) {
            /* Not being able to remember a preference is not worth telling anybody. */
        }
        changed();
    }

    /* Whether the interface should be showing at all. One question, asked here, so
     * that "aboard" means the same thing to the shell and to every panel. */
    /* Which contact the player has picked out. Held here rather than in the chart so
     * that a list and a chart showing the same sea agree about it. */
    function select(contactId) {
        state.selectedContactId = state.selectedContactId === contactId ? null : contactId;
        changed();
    }

    function isMaritime() {
        return state.mode !== "none";
    }

    return {
        PROTOCOL_VERSION: PROTOCOL_VERSION,
        usable: usable,
        get: get,
        onChange: onChange,
        applyMode: applyMode,
        applyStatus: applyStatus,
        applyContacts: applyContacts,
        applyChart: applyChart,
        applyLand: applyLand,
        applySync: applySync,
        loadPreferences: loadPreferences,
        select: select,
        setPreference: setPreference,
        isMaritime: isMaritime
    };
})();
