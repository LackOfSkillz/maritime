"""
Noticing that somebody has crossed into or out of the maritime world.

The interface is supposed to appear when a player walks aboard and go when they walk ashore,
with no reload and nothing for the player to do. That needs somebody to notice the crossing.

**Both sides of every crossing are rooms this contrib owns.** A gangway runs between a quay
and a `ShipRoom`; going over the side runs between a `ShipRoom` and an `OceanRoom`; being
recovered runs the other way. So the crossing is noticed from our own typeclasses, and a
host game does not have to override its character typeclass or remember to call anything.
That is the difference between a feature a game installs and a feature a game integrates.

The land side needs nothing. Somebody walking between two rooms ashore was showing no
maritime interface and still is.

**Taking control of a character is a crossing too**, and the easiest one to miss. A player
who logs in while already aboard has not moved, so no room hook fires, and without this they
would sit on their own quarterdeck looking at no interface until they happened to walk
through a door. Evennia announces puppeting with a signal, which a contrib can listen to
without a host game wiring anything - so this stays true to the promise the rest of the file
makes.

"""

from evennia.server.signals import SIGNAL_OBJECT_POST_PUPPET

from . import transport


class NoticesTheWaterline:
    """
    A room that tells a mover's sessions when their situation has changed.

    Notes:
        Mixed into the room typeclasses on both sides of a crossing. It fires on
        arrival and on departure because the two answer different halves: arriving
        aboard is what raises the interface, and leaving the last maritime room is
        what puts it away.

        Deliberately cheap and deliberately quiet. `refresh` compares the resolved
        context against what the session was last told and sends nothing when they
        agree, so walking from a deck into a hold - two rooms, one situation - costs
        a comparison and no traffic.

        Nothing here may raise. A player must never fail to walk through a door
        because an interface could not be told about it, so both hooks are guarded:
        the worst outcome of a broken client layer is a stale panel.

    """

    def at_object_receive(self, moved, source_location, **kwargs):
        """
        Args:
            moved (Object): Whoever arrived.
            source_location (Object or None): Where they came from.

        """
        super().at_object_receive(moved, source_location, **kwargs)
        notice(moved)

    def at_object_leave(self, moved, destination, **kwargs):
        """
        Args:
            moved (Object): Whoever is going.
            destination (Object or None): Where to.

        Notes:
            Fired before the move completes, so the mover is still standing here and
            would resolve to the situation they are leaving. The *destination* is
            asked instead, which is the only way to tell "stepping onto the quay"
            from "stepping down into the hold" at the moment the question arises.

            Nothing is mutated to ask it. The resolver takes the room as an
            argument, because moving somebody to find out where they would be is
            how a player ends up somewhere they never went.

        """
        super().at_object_leave(moved, destination, **kwargs)
        notice(moved, room=destination)


def notice(moved, room=None):
    """
    Tell a mover's sessions their situation may have changed, and never raise.

    Args:
        moved (Object): Whoever moved.
        room (Object, optional): Resolve them as standing here instead.

    Notes:
        Public because not every crossing arrives through a room hook. The ocean
        projection moves swimmers with `move_hooks=False`, deliberately - it
        reassigns its pool rooms constantly and does not want the churn - so going
        over the side and being pulled out again call this directly. Those two are
        the transitions that mean something; drifting from one cell of water to the
        next is still the same situation and has nothing to announce.

    """
    try:
        transport.refresh_for(moved, room=room)
    except Exception:  # noqa: BLE001 - an interface is never worth a failed move
        pass


def _puppeted(sender, session=None, **kwargs):
    """
    A session has taken control of a character.

    Args:
        sender (Object): The character now being puppeted.
        session (Session, optional): The connection that took it.

    Notes:
        The commonest crossing of all, and one no room hook can see: logging in
        aboard your own ship is arriving in the maritime world without having moved
        an inch. Found by connecting to a testbed while standing on a deck and
        watching nothing happen.

        Told through the session rather than the character where one is given. A
        player with two connections who puppets from one has changed the situation
        of that connection only.

    """
    try:
        if session is not None:
            transport.refresh(session, force=True)
        else:
            transport.refresh_for(sender)
    except Exception:  # noqa: BLE001 - an interface is never worth a failed login
        pass


SIGNAL_OBJECT_POST_PUPPET.connect(_puppeted, dispatch_uid="maritime_client_puppet")
