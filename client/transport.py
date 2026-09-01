"""
Getting a payload to a session, and knowing whether to bother.

Evennia's client protocol carries `[cmdname, args, kwargs]` in both directions, and a
client that does not recognise a command name ignores it. That is the whole mechanism, and
it is why a maritime message can be emitted safely into a game where half the players are
on telnet: they will never see it and nothing will break.

**Capability belongs to the session, not the character.** One player may be connected from a
browser and from a terminal at the same time, looking at the same ship. The character is not
graphical; the connection is. Storing this on the character would send chart payloads down a
telnet pipe the moment they opened a browser somewhere else.

**Nothing is sent that has not changed.** A ship's context changes when somebody walks
across a gangway, which is rare, and re-announcing it every tick would be the same wallpaper
`messaging` exists to prevent - with the added cost of a JSON encode per session per step.

"""

from .payloads import CAPABILITIES, PROTOCOL_VERSION
from .state import chart_for, contacts_for, mode_for, status_for, sync_for

#: How much sea a chart may be asked to cover, in metres from the ship to the edge.
#: A browser asking for more than the upper bound is asking the server to contour
#: half the world on its behalf, which is a thing to decline politely.
MIN_REACH = 500.0
MAX_REACH = 100000.0

#: What to draw for a client that has not said what it is showing.
DEFAULT_REACH = 10000.0


def announce(session, payload, capability=None):
    """
    Send one payload to one session, if that session asked for it.

    Args:
        session (Session): Who to tell.
        payload (Payload): What to tell them.
        capability (str, optional): What a client must have declared before this
            kind of message is worth sending it.

    Returns:
        sent (bool): Whether anything was sent.

    Notes:
        Silently declines a session that never said it understood maritime
        messages. That is not an optimisation - a client which has not announced
        itself may be a terminal, and a terminal that receives an unknown command
        name is entitled to print it.

        The same holds one level down, which is what capabilities are *for* and
        what this originally got wrong. A client that declared only "mode" and was
        sent a chart printed several hundred coordinates into the player's message
        window, because an Evennia client shows a command name it has no listener
        for. Seen in a browser, immediately, and it would have happened in any host
        game whose client knew part of this protocol and not the rest.

    """
    if session is None or not understands(session):
        return False
    if capability is not None and capability not in (session.ndb.maritime_capabilities or ()):
        return False
    session.msg(**{payload.kind: ((), payload.as_message())})
    return True


def understands(session):
    """
    Args:
        session (Session): The connection in question.

    Returns:
        graphical (bool): Whether this session has said it can draw maritime state.

    """
    return bool(getattr(session, "ndb", None) and session.ndb.maritime_capabilities)


def hello(session, protocol_version=PROTOCOL_VERSION, capabilities=CAPABILITIES):
    """
    Record what a client says it understands, and answer with a full snapshot.

    Args:
        session (Session): The connection announcing itself.
        protocol_version (int, optional): The version the client speaks.
        capabilities (iterable, optional): What the client says it can draw.

    Returns:
        sent (bool): Whether a snapshot went back.

    Notes:
        Held on `.ndb`, which empties on a reload - correctly. A capability is a fact
        about a live connection, and a browser that has gone away has not got one. The
        client announces itself again when it returns, which is the same handshake
        rather than a special case for reconnection.

        A version this server does not know is accepted rather than refused, and the
        client is told what the server speaks. Refusing would turn a client one
        version ahead into a client with no maritime interface at all, when almost
        everything would have worked.

    """
    if session is None:
        return False

    wanted = tuple(capability for capability in capabilities if capability in CAPABILITIES)
    session.ndb.maritime_capabilities = wanted or ("mode",)
    session.ndb.maritime_protocol = int(protocol_version)

    return refresh(session, force=True)


def refresh(session, force=False, room=None):
    """
    Tell a session what it should be showing, if that has changed.

    Args:
        session (Session): Who to tell.
        force (bool, optional): Send even if nothing has changed, which is what a
            client that has just announced itself needs.
        room (Object, optional): Resolve as though the character were standing
            here, for the moment they are part-way through a door.

    Returns:
        sent (bool): Whether anything was sent.

    """
    if session is None or not understands(session):
        return False

    character = getattr(session, "puppet", None)
    if force:
        session.ndb.maritime_mode = mode_for(character, room)
        return announce(session, sync_for(character, session.ndb.maritime_capabilities, room))

    now = mode_for(character, room)
    if now == session.ndb.maritime_mode:
        return False
    session.ndb.maritime_mode = now
    return announce(session, now)


def refresh_for(character, room=None):
    """
    Tell every session driving this character what it should be showing.

    Args:
        character (Object or None): Whoever has just moved, boarded or gone over.
        room (Object, optional): Resolve as though they were standing here.

    Returns:
        told (int): How many sessions were sent something.

    Notes:
        Every session, because a player may be watching from more than one, and the
        one that did not move is looking at exactly the same ship as the one that
        did.

    """
    if character is None:
        return 0
    sessions = getattr(character, "sessions", None)
    if sessions is None:
        return 0
    return sum(1 for session in sessions.all() if refresh(session, room=room))


def broadcast_status(vessel):
    """
    Send her instruments to every graphical session aboard her.

    Args:
        vessel (Vessel): The hull.

    Returns:
        told (int): How many sessions were sent something.

    Notes:
        Called from the simulation tick, so the cheap questions come first: a ship
        with nobody graphical aboard costs a walk of her compartments and no more,
        and a ship whose readings have not moved costs a comparison.

        Compared against what was last sent rather than sent unconditionally. A
        vessel lying at anchor produces the same numbers for hours, and a board that
        redrew itself every few seconds would steal focus from a player trying to
        read it.

    """
    listening = _graphical_sessions_aboard(vessel)
    if not listening:
        return 0

    # One board per authority, not one per ship. A passenger and her captain are
    # looking at the same weather and very different sets of controls, and sending
    # one of them the other's would either offer a passenger the helm or take it
    # away from the master. Two readings at most, so the common case still builds
    # the expensive part once.
    from .context import COMMAND, resolve_maritime_ui_context

    boards = {}
    told = 0
    for session in listening:
        context = resolve_maritime_ui_context(getattr(session, "puppet", None))
        commanding = context == COMMAND
        if commanding not in boards:
            boards[commanding] = status_for(vessel, commanding=commanding)
        status = boards[commanding]
        if status is None:
            continue

        message = status.as_message()
        if message == session.ndb.maritime_status:
            continue
        session.ndb.maritime_status = message
        if announce(session, status, "status"):
            told += 1

    # What the lookout has, on the same step. Sent unconditionally rather than
    # compared, because a contact list changes on almost every tick a ship is under
    # way and comparing two lists costs more than sending the shorter one.
    seen = contacts_for(vessel)
    for session in listening:
        announce(session, seen, "contacts")

    # The paper changes far more slowly than the ship does, and drawing it is the
    # expensive part of this whole layer by a wide margin.
    #
    # **The revision is worked out before anything is drawn, and that is the point.**
    # This built a sheet on every tick and then decided whether to send it, so a chart
    # that goes out once a minute was contoured thirty times for each one that reached
    # a player, and twenty-nine of those drawings were thrown away. Against a
    # hand-written seabed, where a sheet costs eighteen milliseconds, that was invisible
    # waste; against a generated world, where one costs the better part of a second, it
    # is a third of a core burned per crewed vessel to produce nothing.
    #
    # The stamp is the reach and the revision, and both are known without a sheet
    # existing - so a session whose stamp already matches needs nothing drawn for it.
    # What is sent is unchanged: the first tick of a new revision draws and sends
    # exactly the sheet it always did.
    #
    # A sheet per reach rather than one for the ship. Two players may be looking at
    # very different amounts of sea, and drawing one of them the other's scale is what
    # put a coastline into the middle fifth of a panel. Charts are cached by the reach
    # they were drawn to, so the common case - everybody at the same scale - still
    # contours once.
    # Which sheet she is reading goes in the stamp beside the revision. Without it,
    # gating on the revision alone would leave a chart bought, found or unrolled
    # halfway through a minute invisible until the minute turned - the old code
    # noticed at once, because it redrew everything every tick, and losing that would
    # be paying for the saving with a worse interface. Asking which chart covers her
    # is a scan of the few aboard; drawing one is nine thousand soundings.
    from .. import config
    from .state import chart_revision

    revision = chart_revision(config.time_provider().now())
    here = getattr(vessel.chart_here(), "key", None)

    drawn = {}
    for session in listening:
        reach = session.ndb.maritime_reach or DEFAULT_REACH
        stamp = (reach, revision, here)
        if session.ndb.maritime_chart_stamp == stamp:
            continue
        if reach not in drawn:
            drawn[reach] = chart_for(vessel, reach)

        session.ndb.maritime_chart_stamp = stamp
        announce(session, drawn[reach], "chart")
    return told


def redraw_chart(session):
    """
    Send a session the chart again, at whatever reach it is now showing.

    Args:
        session (Session): The connection that has zoomed.

    Returns:
        sent (bool): Whether a sheet went out.

    Notes:
        Answered at once rather than waiting for the next tick, because a captain who
        zooms out and then watches an empty square of sea for five seconds will
        reasonably conclude the chart is broken.

    """
    if session is None or not understands(session):
        return False

    from ..vessel import vessel_in

    character = getattr(session, "puppet", None)
    vessel = vessel_in(getattr(character, "location", None))
    if vessel is None:
        return False

    reach = session.ndb.maritime_reach or DEFAULT_REACH
    sheet = chart_for(vessel, reach)

    # Stamped the same way the broadcast stamps it, or the two disagree for ever and
    # the next tick redraws what this call has already sent.
    session.ndb.maritime_chart_stamp = (
        reach,
        sheet.revision,
        getattr(vessel.chart_here(), "key", None),
    )
    return announce(session, sheet, "chart")


def _graphical_sessions_aboard(vessel):
    """
    Args:
        vessel (Vessel): The hull.

    Returns:
        sessions (list): Every session aboard her that can draw a board.

    Notes:
        Walked rather than cached. A cache would have to be invalidated by somebody
        walking through a door, going overboard, logging in or logging out, and a
        stale one shows a player the instruments of a ship they left.

    """
    found = []
    for room in getattr(vessel, "ship_rooms", ()):
        for thing in getattr(room, "contents", ()):
            sessions = getattr(thing, "sessions", None)
            if sessions is None:
                continue
            for session in sessions.all():
                if understands(session):
                    found.append(session)
    return found
