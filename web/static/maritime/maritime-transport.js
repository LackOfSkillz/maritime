/*
 * Talking to the server, and nothing else.
 *
 * Every maritime message enters and leaves through this file. Panels never reach for
 * `Evennia` themselves, so there is one place to look when something is not arriving,
 * and one place to change if the transport ever does.
 *
 * The server is authoritative in both directions. Nothing sent from here is an
 * instruction the browser has decided on; it is a request, revalidated on arrival
 * against the same authority a typed command passes. A determined player has a
 * JavaScript console and will call these by hand, and that must be uninteresting.
 */

window.MaritimeTransport = (function () {
    "use strict";

    var HELLO = "maritime_hello";
    var MODE = "maritime_mode";
    var STATUS = "maritime_status";
    var CONTACTS = "maritime_contacts";
    var CHART = "maritime_chart";
    var SYNC = "maritime_sync";

    /* What this build of the client can draw. Sent so the server does not have to
     * assume; a capability it does not recognise is dropped rather than refused. */
    var CAPABILITIES = ["mode", "status", "chart", "contacts", "controls"];

    var started = false;

    function available() {
        return !!(window.Evennia && window.Evennia.emitter);
    }

    /* Announce this client and ask for a complete picture.
     *
     * Also the whole of reconnection: a client that has just come back says exactly
     * what a client that has just arrived says, and gets the same full snapshot. There
     * is no separate resynchronisation path to get wrong. */
    function announce() {
        if (!available() || typeof Evennia.msg !== "function") {
            return false;
        }
        Evennia.msg(HELLO, [], {
            protocol_version: MaritimeState.PROTOCOL_VERSION,
            capabilities: CAPABILITIES
        });
        return true;
    }

    function start() {
        if (started || !available()) {
            return false;
        }
        started = true;

        Evennia.emitter.on(SYNC, function (args, kwargs) {
            MaritimeState.applySync(kwargs);
        });

        Evennia.emitter.on(MODE, function (args, kwargs) {
            MaritimeState.applyMode(kwargs);
        });

        Evennia.emitter.on(STATUS, function (args, kwargs) {
            MaritimeState.applyStatus(kwargs);
        });

        Evennia.emitter.on(CONTACTS, function (args, kwargs) {
            MaritimeState.applyContacts(kwargs);
        });

        Evennia.emitter.on(CHART, function (args, kwargs) {
            MaritimeState.applyChart(kwargs);
        });

        /* A connection that has just come up is a connection that knows nothing.
         * Announcing again is cheap and is the only thing that makes a reconnect
         * mid-voyage land the player back on their own ship. */
        Evennia.emitter.on("connection_open", function () {
            announce();
        });

        announce();
        return true;
    }

    return {
        HELLO: HELLO,
        MODE: MODE,
        STATUS: STATUS,
        CONTACTS: CONTACTS,
        CHART: CHART,
        SYNC: SYNC,
        CAPABILITIES: CAPABILITIES,
        available: available,
        announce: announce,
        start: start
    };
})();
