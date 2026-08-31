"""
Which interface a session should be looking at.

One question, asked in one place. The alternative is `isinstance(location, ShipRoom)`
scattered through a transport layer, a payload builder and three panels, and the first time
those four disagree the interface will show a helm to somebody swimming.

The answer is about the *character's situation*, not about the client. A telnet player has a
context too; they simply have nothing that draws it.

"""

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

#: Every context this resolver can return.
#:
#: There is deliberately no CREW between passenger and command. Nothing in the contrib can
#: currently decide it: command authority is one question with a yes or a no, and a ship's
#: company is a count of hands rather than a list of people who might hold a post. When
#: stations arrive - a gunner, a leadsman, a lookout who is a person rather than a height of
#: eye - there will be something real to resolve, and it belongs here. Publishing the value
#: before then would be a promise the contrib cannot keep.
CONTEXTS = (NONE, PASSENGER, COMMAND, WATER)


#: Sentinel for "wherever they actually are", so that `None` can mean the void.
_WHERE_THEY_ARE = object()


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

    where = getattr(character, "location", None) if room is _WHERE_THEY_ARE else room

    vessel = vessel_in(where)
    if vessel is not None:
        return COMMAND if may_command(character, vessel) else PASSENGER

    if bool(getattr(where, "is_open_water", False)):
        return WATER

    return NONE
