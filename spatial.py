"""
Spatial indexes: finding what is near something.

Two indexes, because one cannot serve both questions well.

    ContactIndex     coarse, surface-plane. Lookouts, horizon, traffic.
    ProximityIndex   fine, depth-aware. Collision, docking, boarding, divers.

The difference is not tuning, it is geometry. A masthead lookout sees for tens of
kilometres and does not care that a contact is a few metres higher or lower - horizon
range is a surface question. Boarding cares about metres, and a diver thirty metres
beneath a hull is horizontally on top of it while being nowhere near it. Serve both from
one measure and one of them is always wrong.

**Both produce candidates, never answers.** An index says "these are worth examining";
whether a lookout can actually see a hull depends on weather, light, height of eye and
the target's size, none of which an index knows. Treating a candidate list as a result is
how a vessel ends up spotted through a headland.

Implementation note: this is a linear scan, deliberately. Until vessels exist there is
nothing to index, and choosing a structure now would mean guessing at query patterns that
do not exist yet - how many entities, how often they move, how wide the typical radius.
The interface is what matters at this stage; the structure behind it is replaceable
without any caller noticing, which is the whole reason for defining it first.

"""

from .position import WorldPosition


class SpatialIndex:
    """
    Tracks where entities are, and answers "what is near here?".

    Positions are stored rather than resolved on demand. That is a deliberate
    contract: a real index has to store them to be fast at all, so anything moving
    must say so via `move`. Resolving fresh on every query would work today and
    quietly break when the structure behind this changes.

    """

    def __init__(self):
        self._positions = {}

    def _distance(self, first, second):
        """
        Distance between two positions, in whatever sense this index means.

        Args:
            first (WorldPosition): One position.
            second (WorldPosition): The other.

        Returns:
            distance (float): Distance in metres.

        """
        raise NotImplementedError("A spatial index must define how it measures distance.")

    def insert(self, entity, position):
        """
        Add an entity, or update one already present.

        Args:
            entity (any): The thing being tracked. Must be hashable.
            position (WorldPosition): Where it is.

        Returns:
            index (SpatialIndex): This index, for chaining.

        Raises:
            TypeError: If `position` is not a `WorldPosition`. A tuple would work
                today and fail once the structure behind this changes.

        """
        if not isinstance(position, WorldPosition):
            raise TypeError(f"Expected a WorldPosition, got {type(position).__name__}.")
        self._positions[entity] = position
        return self

    def move(self, entity, position):
        """
        Record that a tracked entity has moved.

        Args:
            entity (any): The entity.
            position (WorldPosition): Its new position.

        Returns:
            index (SpatialIndex): This index, for chaining.

        Raises:
            KeyError: If the entity is not in the index.
            TypeError: If `position` is not a `WorldPosition`.

        Notes:
            Refusing to move something absent is deliberate. Silently inserting
            would turn "I forgot to add this vessel" into an index that looks
            correct while missing everything that never moved.

        """
        if entity not in self._positions:
            raise KeyError(f"{entity!r} is not in this index; insert it before moving it.")
        return self.insert(entity, position)

    def remove(self, entity):
        """
        Stop tracking an entity.

        Args:
            entity (any): The entity to drop.

        Returns:
            removed (bool): True if it had been present.

        Notes:
            Removing something absent is not an error - a vessel sinking twice in
            one tick is a real sequence, and the second removal is a no-op rather
            than a crash.

        """
        return self._positions.pop(entity, None) is not None

    def position_of(self, entity):
        """
        The position last recorded for an entity.

        Args:
            entity (any): The entity to look up.

        Returns:
            position (WorldPosition or None): Its position, or None if untracked.

        """
        return self._positions.get(entity)

    def near(self, position, radius):
        """
        Entities within a radius, nearest first.

        Args:
            position (WorldPosition): Centre of the search.
            radius (float): Search radius in metres, measured in this index's own
                sense - surface distance for contacts, true distance for proximity.

        Returns:
            candidates (tuple): Entities within the radius, ordered nearest first.

        Raises:
            ValueError: If `radius` is negative.

        Notes:
            Only entities in the same region are considered. Regions are separate
            coordinate spaces, so a lake and an ocean may hold points with the same
            coordinates without those points being anywhere near each other.

            The result is a candidate set. Whether any of them can actually be
            seen, hit or boarded is for the caller to determine.

        """
        if radius < 0:
            raise ValueError(f"Search radius cannot be negative, got {radius!r}.")
        found = []
        for entity, entity_position in self._positions.items():
            if entity_position.region != position.region:
                continue
            distance = self._distance(position, entity_position)
            if distance <= radius:
                found.append((distance, entity))
        found.sort(key=lambda pair: pair[0])
        return tuple(entity for _distance, entity in found)

    def clear(self):
        """
        Drop every tracked entity.

        Returns:
            index (SpatialIndex): This index, for chaining.

        """
        self._positions.clear()
        return self

    def __len__(self):
        return len(self._positions)

    def __contains__(self, entity):
        return entity in self._positions

    def __repr__(self):
        return f"{type(self).__name__}({len(self._positions)} tracked)"


class ContactIndex(SpatialIndex):
    """
    Surface-plane index, for detection at range.

    Measures across the surface and ignores elevation, because horizon range is a
    surface question: a lookout seeing twelve kilometres does not care whether the
    hull is a metre higher or lower than their own.

    """

    def _distance(self, first, second):
        """
        Surface distance, ignoring elevation.

        Args:
            first (WorldPosition): One position.
            second (WorldPosition): The other.

        Returns:
            distance (float): Horizontal distance in metres.

        """
        return first.horizontal_distance_to(second)


class ProximityIndex(SpatialIndex):
    """
    Depth-aware index, for things that must actually touch.

    Measures true distance through space, because at these ranges depth separates
    what looks adjacent from above. A diver thirty metres beneath a hull is
    directly below it and cannot be boarded from it.

    """

    def _distance(self, first, second):
        """
        True distance, including elevation.

        Args:
            first (WorldPosition): One position.
            second (WorldPosition): The other.

        Returns:
            distance (float): Distance in metres through space.

        """
        return first.distance_to(second)
