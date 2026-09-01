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
    var LAND = "maritime_land";
    var SYNC = "maritime_sync";

    /* What this build of the client can draw. Sent so the server does not have to
     * assume; a capability it does not recognise is dropped rather than refused. */
    /* What this client can draw, and therefore what the server will send it.
     *
     * "land" was missing, and the server declines to send a capability a client has
     * not declared - deliberately, because an Evennia client prints a message it has
     * no listener for straight into the player window. So the land map was built,
     * drawn for, and never sent: stepping ashore gave a panel that said "nowhere to
     * map" and stayed that way, with nothing wrong at either end except that they
     * had never been introduced.
     *
     * This list and `payloads.CAPABILITIES` have to agree. They are in two languages
     * in two files and there is no way to check one against the other from here, so
     * `tests/test_client_scripts.py` reads this one as text and compares them. */
    var CAPABILITIES = ["mode", "status", "chart", "land", "contacts", "controls"];

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

        Evennia.emitter.on(LAND, function (args, kwargs) {
            MaritimeState.applyLand(kwargs);
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
