"""
Which interface a session should be looking at.

One question, asked in one place. The alternative is `isinstance(location, ShipRoom)`
scattered through a transport layer, a payload builder and three panels, and the first time
those four disagree the interface will show a helm to somebody swimming.

The answer is about the *character's situation*, not about the client. A telnet player has a
context too; they simply have nothing that draws it.

"""

from .. import switches
from ..ownership import may_command
from ..vessel import vessel_in

#: Ashore, or anywhere the maritime system has no opinion about. The host game's own
#: interface, whatever that is.
NONE = "none"

#: Aboard, without the authority to give the ship orders. A passenger may look at the
#: weather, the chart and where she is going, because all of that is visible from a deck
#: to anybody standing on it.
PASSENGER = "passenger"

#: Aboard and permitted to give orders, which is the full command interface.
COMMAND = "command"

#: In the water. A very short horizon, no ship to command, and problems of their own.
WATER = "water"

#: Standing on land that belongs to the sea - a quay, a pier, the town behind it.
#:
#: There is no ship to give orders to and no chart to read, but there is somewhere to walk
#: and a ship to walk back to, so the panel can stay up and show the place instead of the
#: water.
#:
#: **Off unless a game turns it on**, and that is the important half. The default when
#: somebody steps off a gangway is that maritime gets out of the way entirely and the host
#: game's own interface comes back - which is what this module says at the top of the
#: resolver and what it should have gone on doing. A contrib that decides to own the
#: screen in a market square has overstepped, however good its map is.
#:
#: A game that *wants* the maritime panel ashore - because its whole world is a coast, or
#: because it has no other interface to return to - sets `MARITIME_ASHORE_PANEL` and gets
#: it. That is a decision about a game, so a game makes it.
#:
#: **The game also says which rooms these are; the contrib does not guess.** A `PortRoom` is
#: obviously one, because it has berths. Everything else - the lanes, the market, the room
#: at the top of the hill - is ashore because the game tagged it so, which is the same
#: bargain every other part of this contrib makes about the world.
ASHORE = "ashore"

#: Every context this resolver can return.
#:
#: There is deliberately no CREW between passenger and command. Nothing in the contrib can
#: currently decide it: command authority is one question with a yes or a no, and a ship's
#: company is a count of hands rather than a list of people who might hold a post. When
#: stations arrive - a gunner, a leadsman, a lookout who is a person rather than a height of
#: eye - there will be something real to resolve, and it belongs here. Publishing the value
#: before then would be a promise the contrib cannot keep.
CONTEXTS = (NONE, PASSENGER, COMMAND, WATER, ASHORE)


#: The tag a game puts on land rooms it wants the maritime panel to stay up in, and the
#: category it lives under.
ASHORE_TAG = "ashore"
ASHORE_CATEGORY = "maritime"

#: Re-exported so that everything asking "which interface" has one module to import from.
#:
#: The values and their persistence live in `switches`, because they are set by a command
#: and read by half the contrib, and because `uncharted` and the per-account choice are set
#: the same way and belong beside them. What lives *here* is what the modes mean for a
#: person standing in a particular room, which is a different question and the only one this
#: module has ever answered.
UI_ON = switches.UI_ON
UI_OFF = switches.UI_OFF
UI_HYBRID = switches.UI_HYBRID
UI_MODES = switches.UI_MODES

ui_mode = switches.ui_mode
set_ui_mode = switches.set_ui_mode
ui_mode_for = switches.ui_mode_for

#: Sentinel for "wherever they actually are", so that `None` can mean the void.
_WHERE_THEY_ARE = object()


def wants_ashore_panel():
    """
    Whether this game keeps the maritime panel up on land.

    Returns:
        wanted (bool): False unless the game asked for it.

    Notes:
        Off by default, deliberately. Stepping ashore should hand the screen back to the
        host game, because that is where a player expects to find whatever else the game
        does - its own map, its own combat, its own everything. A contrib that keeps the
        display after the thing it displays has been left behind is a contrib that has
        decided it is the game.

        A game whose world *is* a coast turns it on and gets a land map instead of a blank
        space. Both answers are right for somebody; only one of them is right by default.

    """
    from .. import config

    return bool(config.get_setting("ASHORE_PANEL", False))


def is_ashore(room):
    """
    Whether this room is maritime land.

    Args:
        room (Object or None): Where somebody is standing.

    Returns:
        ashore (bool): Whether the panel should stay up and show the place.

    Notes:
        A room with berths is ashore without being told - it is the quay, and a quay is the
        seam. Everything else is ashore because the game said so, so a tavern forty miles
        inland does not get a harbour interface merely for being a tavern.

        Total, like the resolver it serves: anything unreadable is not ashore, because the
        failure worth avoiding is the interface turning up where it does not belong.

    """
    if room is None:
        return False
    if getattr(room, "berths", None):
        return True
    # A room that says so itself.
    #
    # `ShoreRoom` exists for nothing but being a room ashore, and having declared that in
    # its own type it should not also have to be tagged by whoever builds it. Requiring both
    # is how a room comes to look configured and do nothing: the island tracks were built as
    # land, walked as land, and resolved as not-ashore, so stepping up off a pier put the
    # whole panel away.
    #
    # Read off the object rather than by importing the room module, because this is the
    # client layer and it does not get to depend on typeclasses. Any room may answer it.
    if getattr(room, "maritime_ashore", False):
        return True
    tags = getattr(room, "tags", None)
    if tags is None:
        return False
    try:
        return bool(tags.has(ASHORE_TAG, category=ASHORE_CATEGORY))
    except (TypeError, AttributeError):
        return False


def resolve_maritime_ui_context(character, room=_WHERE_THEY_ARE):
    """
    What sort of maritime situation this character is in.

    Args:
        character (Object or None): Whoever is looking.
        room (Object or None, optional): Resolve as though they were standing here
            instead of where they are. Used when somebody is part-way through a
            door and the interesting question is about the far side of it.

    Returns:
        context (str): One of `CONTEXTS`.

    Notes:
        Deliberately total. Anything this function cannot make sense of is `NONE`,
        because the failure a player would actually notice is a maritime interface
        appearing in a tavern, and the safe answer is always to leave the host
        game's own interface alone.

        Command authority is asked of the *character* while the situation is asked
        of the *room*, which is right: walking to the other end of your own ship
        does not make you her captain, and does not stop you being one.

    """
    # Kept although every lookup below tolerates None on its own, so removing this
    # changes no behaviour and no test can catch it. It is here to state the
    # contract at the top of a public function rather than leave None-safety
    # resting on three separate getattr defaults continuing to agree.
    if character is None:
        return NONE

    # Asked *for this person*, which is the server's mode unless the game has allowed
    # people to choose and this one has. The permission is checked inside `ui_mode_for`
    # rather than here, so there is exactly one place that decides whose answer wins.
    wanted = switches.ui_mode_for(character)
    if wanted == UI_OFF:
        return NONE

    where = getattr(character, "location", None) if room is _WHERE_THEY_ARE else room

    vessel = vessel_in(where)
    if vessel is not None:
        return COMMAND if may_command(character, vessel) else PASSENGER

    if bool(getattr(where, "is_open_water", False)):
        return WATER

    if wanted == UI_ON:
        return ASHORE

    if wanted == UI_HYBRID and wants_ashore_panel() and is_ashore(where):
        return ASHORE

    return NONE


__all__ = (
    "NONE",
    "PASSENGER",
    "COMMAND",
    "WATER",
    "ASHORE",
    "CONTEXTS",
    "ASHORE_TAG",
    "ASHORE_CATEGORY",
    "UI_ON",
    "UI_OFF",
    "UI_HYBRID",
    "UI_MODES",
    "ui_mode",
    "set_ui_mode",
    "ui_mode_for",
    "wants_ashore_panel",
    "is_ashore",
    "resolve_maritime_ui_context",
)
