"""
Laying a ship up, and bringing her forward again.

A harbour that only ever fills is a harbour nobody can get into. Every hull ever built
stays on the water for ever, every berth is taken by somebody who logged out three months
ago, and a new player arrives to find nowhere to tie up. That is a housekeeping problem
with a real answer that the age of sail already had a word for.

**In ordinary.** A ship out of commission was laid up in a dockyard - masts and stores
ashore, a skeleton party aboard, and nothing about her that the fleet had to think about
until somebody wanted her again. She was not sold, not broken up, and not sailing. That is
exactly the state wanted here, and it is a state this contrib already has:

    "A vessel with no position has not been launched - she is on the stocks, so
     there is nothing to simulate."                                  - `scripts.py`

So laying up is not a new mode with new rules. It is clearing her position, letting go her
lines and dropping her from the traffic register, after which every part of the system that
walks the water simply does not find her - the simulation does not tick her, a lookout does
not raise her, nothing can run into her, and her berth is free.

**She keeps everything else.** Her cargo is in her holds, her crew are her crew, her damage
is her damage, and her compartments are the same rooms with the same objects in them. Being
laid up is a fact about where she is, not about what she is.

**Who may do it, and when.**

    under way       no. A ship with the way on her is going somewhere and laying her up
                    would be teleporting her out from under whoever ordered it
    anybody aboard  no. She is somebody's floor, and the floor going into storage while
                    they are standing on it is not a thing that should be possible
    not yours       no. `ownership.may_command` decides, which means her captain, or her
                    owner if she has no captain - and a prize taken and made over to her
                    captor is owned, so it is the same question

**Nothing here fires on logout by itself, because Evennia does not offer the hook.** Losing
the last session sets `location` to None and runs nothing this contrib can see - measured,
not assumed, in `docs/logout.md`. A game that wants a fleet laid up when its owner leaves
calls `lay_up_fleet_of` from its own `at_post_unpuppet`, which is four lines and is shown in
`docs/shipyard.md`. A contrib that reached into a host game's character class to do it
without being asked would be a contrib nobody could uninstall.
"""

#: Where the fact is kept on the hull.
#:
#: On the vessel rather than in a register, because a register is a second place for the
#: truth to live and would have to be rebuilt after every reload, migration and restore
#: from backup. The hull carries it, and a hull that comes back at all comes back knowing.
IN_ORDINARY = "in_ordinary"

#: How fast she may be moving and still count as stopped, in metres per second.
#:
#: Not zero. A ship made fast to a quay can carry a hundredth of a knot of numerical drift
#: from the last integration step, and refusing to lay her up over it would leave whoever
#: asked staring at a ship that is plainly alongside and a message saying she is under way.
#: A tenth of a knot is well below anything anybody can steer by.
STOPPED = 0.05


def in_ordinary(vessel):
    """
    Args:
        vessel (Vessel or None): The hull.

    Returns:
        laid_up (bool): Whether she is out of commission.

    """
    if vessel is None:
        return False
    return bool(getattr(getattr(vessel, "db", None), IN_ORDINARY, False))


def under_way(vessel):
    """
    Args:
        vessel (Vessel): The hull.

    Returns:
        going (bool): Whether she is moving, or has been told to.

    Notes:
        Both halves, because either on its own is wrong. A ship stopped dead in the water
        with a course and a speed ordered is *going somewhere* - she is waiting for wind,
        or catching a tide - and laying her up would throw away an order somebody gave.
        A ship under no orders at all still has way on her for some minutes after the last
        one was cancelled.

    """
    if abs(float(getattr(vessel, "speed", 0.0) or 0.0)) > STOPPED:
        return True
    orders = getattr(vessel, "orders", None)
    return bool(orders and float(getattr(orders, "speed", 0.0) or 0.0) > 0.0)


def aboard(vessel):
    """
    Args:
        vessel (Vessel): The hull.

    Returns:
        people (list): Everybody aboard her who is a person, logged in or not.

    Notes:
        **People, and only people.** Cargo, furniture and the ship's cat go into ordinary
        with her, and so do her crew and any other NPC - a crew is part of a ship, not a
        reason she cannot be laid up. What matters is whether laying her up would take the
        floor out from under somebody who will come back to it.

        Being played is asked as `sessions.count()` and not as "has a `sessions`", because
        every `DefaultObject` in Evennia has one of those and asking that way counts a
        crate as a passenger.

        **And somebody who logged out on her deck counts.** Evennia takes an unpuppeted
        character off the grid entirely, so they are in no room's contents - which would
        make them invisible here and let a ship be laid up out from under them. They log
        back in onto the deck of a hull that is nowhere, with her gangway taken away, and
        are stuck. `ships_company` is the vessel's own answer to this and already accounts
        for them; `prelogout_location` is how they are told apart from the cargo.

        This is also what makes the logout rule read the way it was asked for: a captain
        who steps onto the quay and *then* leaves has her laid up, and one who leaves from
        her deck does not.

    """
    found = []
    for thing in vessel.ships_company():
        sessions = getattr(thing, "sessions", None)
        if sessions is not None and sessions.count():
            found.append(thing)
        elif getattr(getattr(thing, "db", None), "prelogout_location", None) is not None:
            found.append(thing)
    return found


def why_not(vessel):
    """
    Args:
        vessel (Vessel): The hull.

    Returns:
        reason (str or None): Why she cannot be laid up, or None if she can.

    Notes:
        A sentence rather than a code, because every caller wants to say it and none of
        them wants to translate it. There are three reasons, there will not be many more,
        and a table of constants for three strings is ceremony.

    """
    if in_ordinary(vessel):
        return f"{vessel.key} is already laid up."
    if under_way(vessel):
        return f"{vessel.key} is under way. Bring her to rest before laying her up."
    still_aboard = aboard(vessel)
    if still_aboard:
        who = ", ".join(sorted(person.key for person in still_aboard))
        return f"There is somebody aboard her: {who}."
    return None


def lay_up(vessel):
    """
    Take her out of commission.

    Args:
        vessel (Vessel): The hull.

    Returns:
        reason (str or None): None if she was laid up, or why she was not.

    Notes:
        The order matters. Her lines come off before her position goes, because letting go
        tells the port to release the berth and the port finds her by the berth she is
        recorded in; clearing her position first would leave a berth marked occupied by a
        ship that is nowhere.

    """
    refused = why_not(vessel)
    if refused is not None:
        return refused

    if getattr(vessel, "docked", False):
        vessel.let_go()

    _forget(vessel)

    # Checkpointed *before* her position is cleared, not after. Taking a hull off the
    # water writes through immediately and marks her clean, so anything still only in
    # memory - a heading, a speed - would be dropped on the floor by a checkpoint that
    # came afterwards and found nothing to do.
    vessel.checkpoint()
    vessel.maritime_position = None
    vessel.db.in_ordinary = True
    return None


def bring_forward(vessel, port, berth, gangway=()):
    """
    Put her back on the water, alongside.

    Args:
        vessel (Vessel): The hull.
        port (PortRoom): The quay she is to lie at.
        berth (Berth): The berth.
        gangway (iterable, optional): Exits already rigged between her and the quay.

    Returns:
        vessel (Vessel): The same hull, for chaining.

    Notes:
        Through `make_fast`, which is the same call the `dock` command makes, so a ship
        brought out of ordinary is in every respect a ship that has just docked. A second
        path onto the water is a second set of things to forget.

    """
    vessel.db.in_ordinary = False
    vessel.make_fast(port, berth, gangway)
    _remember(vessel)
    return vessel


def fleet_of(character, laid_up=None):
    """
    The ships this person may give orders to.

    Args:
        character (Object): Whose fleet.
        laid_up (bool, optional): True for only the ones in ordinary, False for only the
            ones on the water, None for all of them.

    Returns:
        hulls (list): Vessels, by name.

    Notes:
        Asked through `ownership.may_command` rather than through `owner`, because that one
        function is where a game says who commands what - and a game that has replaced it
        should find its own answer here too. It also settles capture without a second rule:
        a prize made over to whoever took her is owned by them, and answers to them.

    """
    from .ownership import may_command
    from .typeclasses import Vessel

    found = []
    for hull in Vessel.objects.all():
        if not may_command(character, hull):
            continue
        if laid_up is not None and in_ordinary(hull) != laid_up:
            continue
        found.append(hull)
    found.sort(key=lambda hull: hull.key.lower())
    return found


def lay_up_fleet_of(character):
    """
    Lay up every ship of this person's that can be laid up.

    Args:
        character (Object): Whoever is leaving.

    Returns:
        laid_up (list): The vessels put into ordinary.

    Notes:
        For a game to call from its own `at_post_unpuppet`. Evennia fires nothing this
        contrib can hook, so this is offered rather than installed - see the module
        docstring.

        **Silent about what it could not do.** A ship at sea, a ship with a passenger still
        aboard, a ship under orders: all of them are left exactly as they are and none of
        them is an error. The caller is a logout, there is nobody to tell, and a fleet
        half laid up is the correct outcome rather than a partial failure.

    """
    done = []
    for hull in fleet_of(character, laid_up=False):
        if lay_up(hull) is None:
            done.append(hull)
    return done


def _forget(vessel):
    """
    Drop her from everything that walks the water.

    Args:
        vessel (Vessel): The hull.

    Notes:
        Two registers and not one. The traffic register is what a lookout reads; the
        simulation service is what ticks her. Clearing her position keeps her out of the
        service on the *next* rebuild, which happens at a reload - so a ship laid up and
        not deregistered would go on being integrated until somebody restarted the server,
        and would move about while laid up.

        Both are best-effort. A test with no running script and no register is an ordinary
        situation, and laying a ship up is not worth failing over the absence of something
        that was going to be told she had gone.

    """
    try:
        from .traffic import traffic

        traffic().forget(vessel)
    except Exception:  # noqa: BLE001 - a register that is not there has nothing to forget
        pass

    service = _service()
    if service is not None:
        try:
            service.unregister(vessel)
        except Exception:  # noqa: BLE001 - see above
            pass


def _remember(vessel):
    """
    Args:
        vessel (Vessel): The hull.

    Notes:
        Registered at once rather than left for the next reload, for the same reason
        `make_fast` persists at once: a ship brought forward and then not simulated is a
        ship that will not answer her helm, and the player who just summoned her is
        standing on the quay looking at her.

    """
    service = _service()
    if service is None:
        return
    try:
        from .simulation import ACTIVE

        service.register(vessel, tier=ACTIVE)
    except Exception:  # noqa: BLE001 - nothing running to register with
        pass


def _service():
    """
    Returns:
        service (MaritimeSimulationService or None): The one that is running, if one is.

    """
    try:
        from evennia.utils.search import search_script

        from .scripts import MaritimeDriver

        for script in search_script("maritime_driver"):
            if isinstance(script, MaritimeDriver):
                return script.ndb.service
    except Exception:  # noqa: BLE001 - no script handler, or none running
        return None
    return None


__all__ = (
    "IN_ORDINARY",
    "STOPPED",
    "in_ordinary",
    "under_way",
    "aboard",
    "why_not",
    "lay_up",
    "bring_forward",
    "fleet_of",
    "lay_up_fleet_of",
)
