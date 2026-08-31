"""
What a client is allowed to say back.

Evennia routes an incoming `[cmdname, args, kwargs]` to a function of that name found in
`INPUT_FUNC_MODULES`. A game adds this module to that list and the browser can announce
itself; a game that does not is running the protocol in the broadcast-only mode described
in `docs/client.md`, which still works and simply never learns which sessions are graphical.

**Everything arriving here came from a browser and is therefore untrusted.** A determined
player has a JavaScript console and will call these by hand, so nothing may be believed: a
capability list is filtered against what the server actually knows, a protocol version is
coerced to an integer, and a malformed call is dropped rather than raised. The most an
abusive caller achieves is being told what interface they should be looking at, which they
were entitled to know anyway.

Nothing here executes a game action. When controls arrive they will go through the same
authority check a typed command passes, in a separate function that says so.

"""

from .payloads import CAPABILITIES, PROTOCOL_VERSION
from .transport import MAX_REACH, MIN_REACH, hello, redraw_chart


def maritime_hello(session, *args, **kwargs):
    """
    A client announcing that it can draw maritime state.

    Args:
        session (Session): The connection that spoke.
        *args: Ignored. The payload travels as keywords.
        **kwargs: `protocol_version` and `capabilities`, both optional and both
            distrusted.

    Notes:
        Answered with a full snapshot, which is also what makes reconnection
        uninteresting: a client that has just come back says hello exactly as a
        client that has just arrived, and gets the same complete picture. There is
        no separate resynchronisation path to get wrong.

    """
    try:
        version = int(kwargs.get("protocol_version", PROTOCOL_VERSION))
    except (TypeError, ValueError):
        version = PROTOCOL_VERSION

    wanted = kwargs.get("capabilities", CAPABILITIES)
    if isinstance(wanted, str) or not hasattr(wanted, "__iter__"):
        wanted = CAPABILITIES

    hello(session, protocol_version=version, capabilities=tuple(wanted))


def maritime_view(session, *args, **kwargs):
    """
    A client saying how much sea it is showing.

    Args:
        session (Session): The connection that spoke.
        *args: Ignored.
        **kwargs: `reach`, in metres from the ship to the edge of its view.

    Notes:
        The chart is drawn to the reach the client asked for, because a sheet drawn
        to one scale and displayed at another is the mismatch that put a whole
        coastline into the middle fifth of somebody's panel. The client knows how
        much sea it is showing; the server should not have to guess.

        Clamped, and distrusted like everything else arriving from a browser. A
        request for a thousand leagues is a request to contour half the world, and
        the answer to it is a reasonable sheet rather than a hung server.

    """
    try:
        wanted = float(kwargs.get("reach", 0.0))
    except (TypeError, ValueError):
        return

    session.ndb.maritime_reach = max(MIN_REACH, min(MAX_REACH, wanted))
    redraw_chart(session)


def maritime_action(session, *args, **kwargs):
    """
    A control was pressed.

    Args:
        session (Session): The connection that pressed it.
        *args: Ignored.
        **kwargs: `action`, and whatever that control carries.

    Notes:
        Turned into the ordinary command it stands for and executed as though the
        player had typed it - same handler, same locks, same authority check, same
        refusals in the same words. The button is a keyboard.

        Nothing is pre-authorised. A control was offered because she was in a
        position to use it a moment ago; whether she still is gets asked here, by
        the command itself, at the moment it runs.

    """
    from ..vessel import vessel_in
    from .controls import order_for

    character = getattr(session, "puppet", None)
    if character is None:
        return

    vessel = vessel_in(getattr(character, "location", None))
    line = order_for(kwargs.get("action"), kwargs, vessel)
    if line is None:
        return

    character.execute_cmd(line, session=session)
