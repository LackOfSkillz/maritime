"""
The optional client protocol.

Maritime publishes structured state; a browser may draw it. Nothing in this package is
required to sail, and nothing outside it may depend on a client being connected.

The whole of it rests on two sentences:

    The maritime client is a replaceable view and control surface over the maritime
    simulation. The simulation knows nothing about the browser; the browser knows only the
    player-visible state the simulation deliberately publishes.

    A graphical client must never make the navigator more knowledgeable than the character.

See `docs/client.md` for the reasoning and for how a game wires the browser side up.

    context     which interface a situation calls for
    payloads    what goes on the wire, versioned
    state       turning a situation into something a client may be told
    transport   getting it to a session, and knowing whether to bother

"""

from .context import COMMAND, CONTEXTS, NONE, PASSENGER, WATER, resolve_maritime_ui_context
from .payloads import CAPABILITIES, HELLO, MODE, PROTOCOL_VERSION, SYNC, Mode, Payload, Sync
from .state import mode_for, sync_for
from .transport import announce, hello, refresh, refresh_for, understands

__all__ = (
    "CAPABILITIES",
    "COMMAND",
    "CONTEXTS",
    "HELLO",
    "MODE",
    "Mode",
    "NONE",
    "PASSENGER",
    "PROTOCOL_VERSION",
    "Payload",
    "SYNC",
    "Sync",
    "WATER",
    "announce",
    "hello",
    "mode_for",
    "refresh",
    "refresh_for",
    "resolve_maritime_ui_context",
    "sync_for",
    "understands",
)
