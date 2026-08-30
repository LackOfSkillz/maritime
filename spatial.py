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

**A grid is the other half of this file.** An index answers "what is near this
thing?"; a grid answers "which square of the world is this point in?", and two systems
already need the second - the projected ocean lends one room per occupied cell, and the
map is authored one tile at a time. Both want the same flooring arithmetic at different
scales, so it is written once here rather than twice at either end of the contrib.

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

import math

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


def cell_of(position, size):
    """
    Which cell of a grid a position falls in.

    Args:
        position (WorldPosition): Where it is.
        size (float): How wide a cell is, in metres.

    Returns:
        cell (tuple): `(region, x_index, y_index)`.

    Notes:
        Integer division by flooring, including for negative coordinates -
        truncation would make the two cells either side of zero share an index,
        so the seam at the origin would be a cell twice as wide as every other
        one and nothing would notice until something sailed across it.

        Regions are part of the key, because positions in different regions are
        not comparable and a grid that ignored that would put two unrelated
        worlds in the same square.

    """
    return (
        position.region,
        int(math.floor(position.x / size)),
        int(math.floor(position.y / size)),
    )


def cell_centre(cell, size):
    """
    The middle of a cell, at the datum.

    Args:
        cell (tuple): `(region, x_index, y_index)`.
        size (float): Cell width in metres.

    Returns:
        position (WorldPosition): The centre.

    """
    region, x_index, y_index = cell
    return WorldPosition(
        x=(x_index + 0.5) * size,
        y=(y_index + 0.5) * size,
        z=0.0,
        region=region,
    )


def cell_bounds(cell, size):
    """
    The edges of a cell.

    Args:
        cell (tuple): `(region, x_index, y_index)`.
        size (float): Cell width in metres.

    Returns:
        bounds (tuple): `(west, south, east, north)` in metres.

    """
    _region, x_index, y_index = cell
    return (x_index * size, y_index * size, (x_index + 1) * size, (y_index + 1) * size)


def cells_touching(before, after, size, margin=0.0):
    """
    Every cell a track passes through.

    Args:
        before (WorldPosition): Where the track starts.
        after (WorldPosition): Where it ends.
        size (float): Cell width in metres.
        margin (float, optional): How far either side of the track to include -
            half a beam, when the track is a ship's.

    Returns:
        cells (tuple): The cells, in no particular order.

    Raises:
        ValueError: If the two ends are in different regions, which is not a
            track but two unrelated points.

    Notes:
        The bounding box of the track rather than the cells the line strictly
        crosses. For a track shorter than a cell - which is nearly all of them,
        since a tile is a kilometre and a tick is metres - the two are the same
        answer, and where they differ the box is at most a few extra cells whose
        contents are then tested properly anyway. A DDA walk would be exact,
        slower, and correct about something nothing downstream is asking.

    """
    before._require_same_region(after)
    reach = max(0.0, margin)
    west = min(before.x, after.x) - reach
    east = max(before.x, after.x) + reach
    south = min(before.y, after.y) - reach
    north = max(before.y, after.y) + reach

    first_x = int(math.floor(west / size))
    last_x = int(math.floor(east / size))
    first_y = int(math.floor(south / size))
    last_y = int(math.floor(north / size))

    return tuple(
        (before.region, x_index, y_index)
        for x_index in range(first_x, last_x + 1)
        for y_index in range(first_y, last_y + 1)
    )


def distance_to_track(point, before, after):
    """
    How far a point lies from a track, at its closest.

    Args:
        point (WorldPosition): The thing being measured.
        before (WorldPosition): Where the track starts.
        after (WorldPosition): Where it ends.

    Returns:
        distance (float): Metres, in the horizontal plane.

    Notes:
        The distance to the *segment*, not to the infinite line through it - a
        rock a mile astern is a mile away, not on the track extended backwards.

        This is what makes an authored hazard exact rather than sampled. A hull
        tested at seven points along her length can step over something smaller
        than the gaps between them; a hazard with a radius, measured against the
        whole corridor she swept, cannot be missed however fast she was going.

    """
    return point.horizontal_distance_to(nearest_on_track(point, before, after))


def nearest_on_track(point, before, after):
    """
    The place on a track that passes closest to a point.

    Args:
        point (WorldPosition): The thing being passed.
        before (WorldPosition): Where the track starts.
        after (WorldPosition): Where it ends.

    Returns:
        position (WorldPosition): The point of closest approach, at the datum.

    Notes:
        Clamped to the segment, so a track that has already gone by returns its
        own end rather than a point beyond it.

    """
    before._require_same_region(after)
    run_x, run_y = after.x - before.x, after.y - before.y
    length_squared = run_x * run_x + run_y * run_y
    if length_squared <= 0.0:
        return before

    along = ((point.x - before.x) * run_x + (point.y - before.y) * run_y) / length_squared
    along = max(0.0, min(1.0, along))
    return WorldPosition(
        x=before.x + along * run_x,
        y=before.y + along * run_y,
        z=0.0,
        region=before.region,
    )


def track_entry(point, before, after, radius):
    """
    Where a track first comes within a given distance of a point.

    Args:
        point (WorldPosition): What is being approached.
        before (WorldPosition): Where the track starts.
        after (WorldPosition): Where it ends.
        radius (float): How close counts, in metres.

    Returns:
        position (WorldPosition or None): The first place on the track inside
            that radius, or None if it never gets there.

    Notes:
        The *entry*, not the closest approach, and the difference matters. Stopping
        a ship where she passed nearest a rock puts her on the far side of it,
        which reads as having sailed through the thing that stopped her. She
        strikes it going in.

        Solved as a segment against a circle rather than by walking the track in
        steps, because stepping reintroduces exactly the sampling gap that
        authored hazards exist to close.

    """
    before._require_same_region(after)
    run_x, run_y = after.x - before.x, after.y - before.y
    offset_x, offset_y = before.x - point.x, before.y - point.y

    a = run_x * run_x + run_y * run_y
    if a <= 0.0:
        inside = offset_x * offset_x + offset_y * offset_y <= radius * radius
        return before if inside else None

    b = 2.0 * (offset_x * run_x + offset_y * run_y)
    c = offset_x * offset_x + offset_y * offset_y - radius * radius

    # Already inside it when the step began. She does not enter; she is there.
    if c <= 0.0:
        return before

    discriminant = b * b - 4.0 * a * c
    if discriminant < 0.0:
        return None

    entry = (-b - math.sqrt(discriminant)) / (2.0 * a)
    if entry < 0.0 or entry > 1.0:
        return None
    return WorldPosition(
        x=before.x + entry * run_x,
        y=before.y + entry * run_y,
        z=0.0,
        region=before.region,
    )
