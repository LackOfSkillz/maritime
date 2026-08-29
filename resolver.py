"""
The one place that answers "where is this, in world space?".

Every subsystem asks `get_world_position(entity)`. Nothing works it out for itself.
That matters because the answer is rarely direct: a character aboard a vessel has no
position of their own, they have a cabin, which belongs to a hull, which is the thing
that actually sits somewhere. Let three subsystems each walk that chain their own way
and they will disagree, usually in the one case nobody tested.

An entity joins world space by declaring one of two things:

    maritime_position          a WorldPosition - "I am here"
    maritime_position_source   another entity  - "ask them"

The second is what carries a vessel's interior. A ship's cabin is not *in* the hull by
Evennia's containment - rooms have no location - so it names the hull as its source, and
everyone standing in it resolves through to wherever the hull has sailed.

Failing both, the entity's ordinary `location` is followed, so a character standing in a
cabin resolves without the character itself knowing anything about ships.

**Most rooms have no world position, and that is correct.** A tavern three streets inland
is not at some coordinate that happens not to matter; it is outside the maritime world
entirely. Asking returns `NoWorldPosition`, a defined sentinel rather than `None`, so the
absence is explicit and cannot be quietly arithmetic'd into a real number.

"""

from .position import WorldPosition


class NoWorldPositionType:
    """
    The absence of a maritime position.

    A singleton, so `is NoWorldPosition` is a valid test. Falsy, so `if not
    position:` reads naturally. Deliberately not `None`: `None` is what an
    unset variable looks like, and conflating "outside the maritime world" with
    "nobody has set this yet" hides real bugs.

    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __bool__(self):
        return False

    def __repr__(self):
        return "NoWorldPosition"


NoWorldPosition = NoWorldPositionType()


def _declared_position(entity):
    """
    The position an entity declares for itself, if any.

    Args:
        entity (any): The entity to inspect.

    Returns:
        position (WorldPosition or None): The declared position, or None if the
            entity does not declare one.

    Notes:
        Anything that is not a `WorldPosition` is ignored rather than trusted. A
        game storing a tuple or a stale string under this name should resolve to
        nothing, not to a crash somewhere far away.

    """
    position = getattr(entity, "maritime_position", None)
    return position if isinstance(position, WorldPosition) else None


def _next_hop(entity):
    """
    The entity to ask next, when this one does not know where it is.

    Args:
        entity (any): The entity to inspect.

    Returns:
        entity (any or None): The next entity in the chain, or None if the chain
            ends here.

    Notes:
        An explicit `maritime_position_source` wins over `location`. A ship's
        cabin sits in no room but belongs to a hull, and that relationship has to
        outrank ordinary containment for anyone aboard to resolve correctly.

    """
    source = getattr(entity, "maritime_position_source", None)
    if source is not None:
        return source
    return getattr(entity, "location", None)


def get_world_position(entity):
    """
    Resolve an entity's position in world space.

    Args:
        entity (any): Anything that might be somewhere - a vessel, a character, a
            room, a drifting barrel.

    Returns:
        position (WorldPosition or NoWorldPositionType): Where the entity is, or
            `NoWorldPosition` if it is outside the maritime world.

    Notes:
        Walks the chain: the entity's own declared position, else its position
        source, else its location, until something answers or the chain ends.

        A containment cycle terminates in `NoWorldPosition` rather than looping.
        Cycles should not happen, but a room whose exit loops back on itself is
        an ordinary building mistake, and hanging the server over it would be a
        poor way to report it.

    """
    seen = set()
    current = entity
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        position = _declared_position(current)
        if position is not None:
            return position
        current = _next_hop(current)
    return NoWorldPosition


def has_world_position(entity):
    """
    Whether an entity is anywhere in world space.

    Args:
        entity (any): The entity to test.

    Returns:
        located (bool): True if the entity resolves to a position.

    Notes:
        For the common case of guarding maritime behaviour, where the position
        itself is not wanted - "is this character at sea at all?".

    """
    return get_world_position(entity) is not NoWorldPosition


def resolve_chain(entity):
    """
    The entities consulted while resolving, in order.

    Args:
        entity (any): The entity to resolve.

    Returns:
        chain (tuple): Every entity visited, starting with `entity` itself and
            ending with whichever one supplied the position, or with the last
            entity examined if none did.

    Notes:
        For diagnosis. When a character resolves somewhere surprising, the useful
        question is which link produced the answer, and reconstructing that by
        hand across a cabin, a hull and a room means guessing.

    """
    seen = set()
    chain = []
    current = entity
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(current)
        if _declared_position(current) is not None:
            break
        current = _next_hop(current)
    return tuple(chain)
