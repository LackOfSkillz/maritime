"""
The seabed, remembered.

Named for the ground and not for the figures. `cartography.soundings` already means the
depths a chart prints, which is a different thing entirely and a collision worth not having
inside one codebase.

Asking the world what the ground is costs about eighty microseconds and is very nearly the
entire price of a chart: a ten-kilometre sheet is nine thousand of those reads and nine
hundred milliseconds, of which the contouring, the shading and the graticule together are
under fifty. Measured, on a generated world:

    sampling the seabed       825 ms
    tracing the contours       20 ms
    shading the relief         22 ms
    ruling the graticule        3 ms

**And the seabed does not change.** It does not depend on the time, it does not depend on
which chart is being read, and it is the same for every player. Two hundred captains in one
harbour were paying two hundred times over for arithmetic with one answer - and the same
captain asking twice paid twice, which is measurable: the identical patch cost 811 ms and
then 816 ms.

That is what makes this worth doing and also what makes it simple. There is nothing to
invalidate. A cache of something that changes needs a story about when it goes stale; this
one needs a story about how much memory it may have, and nothing else.

**Hits need a lattice.** A sheet used to be sounded around the ship, so two vessels a
hundred metres apart sampled two sets of points that were near each other and equal nowhere.
Snapping the grid to a fixed lattice of the world costs a shift of under one cell - invisible
at any scale a cell is drawn at - and turns "near each other" into "the same points".

What is *not* here: the chart's own error. That is a penny of arithmetic on top - 1.4
microseconds against 82 - and it differs from chart to chart, so caching it would divide the
cache by the number of charts in the game to save under two per cent. The ground is shared;
the lie told about it is not.
"""

from collections import OrderedDict
from weakref import WeakKeyDictionary

from .position import WorldPosition

#: How many soundings to keep before the oldest are dropped.
#:
#: About fifty megabytes at a hundred and sixty bytes an entry, which is a dictionary key,
#: a float, and the overhead of both. Enough for some thirty sheets' worth of distinct
#: ground at chart resolution, which is a busy harbour and its approaches several times
#: over. A game with more memory than sense can raise it.
DEFAULT_LIMIT = 300_000

#: How far off a lattice point a question may be and still be that point, as a fraction of
#: a cell. Small enough that nothing which was not meant to be on the lattice lands on it,
#: loose enough to survive the arithmetic that got it there.
ON_LATTICE = 1e-6

#: Rectangles sounded ahead of time and read from disk - see `bake`. Consulted before the
#: memory cache, because they are complete over their area and cost one index each.
_BAKED = WeakKeyDictionary()

#: Every world that has been asked, and what it said. Weak, so a game that rebuilds its
#: provider - or a test that swaps one in - does not leak the old one's soundings.
_REMEMBERED = WeakKeyDictionary()

#: Kept for the report. Cheap to maintain and the only way to find out whether any of this
#: is working in a running game.
_HITS = [0]
_MISSES = [0]


def snap(value, cell):
    """
    Args:
        value (float): A world coordinate, in metres.
        cell (float): The lattice cell size.

    Returns:
        snapped (float): The lattice point at or below it.

    """
    return math_floor(value / cell) * cell


def math_floor(value):
    """
    Args:
        value (float): Any number.

    Returns:
        floored (int): The largest integer at or below it.

    Notes:
        `int()` truncates towards zero, so it rounds *up* for anything west or south of
        the origin - which would put two lattices either side of it a half-cell out of
        step, and lose every hit across the meridian. Worth its own function for the same
        reason it was worth a bug.

    """
    floored = int(value)
    return floored - 1 if value < floored else floored


def remember_baked(world, baked):
    """
    Put a pre-sounded rectangle in front of the cache.

    Args:
        world (MaritimeMapProvider): Whose ground it describes.
        baked (bake.Baked): The rectangle.

    Returns:
        held (int): How many rectangles this world now has.

    """
    sheets = _BAKED.setdefault(world, [])
    sheets.append(baked)
    return len(sheets)


def baked_for(world, cell):
    """
    Args:
        world (MaritimeMapProvider): The world.
        cell (float): The spacing being read at.

    Returns:
        sheets (tuple): Pre-sounded rectangles at exactly that spacing.

    Notes:
        Exactly that spacing, because a rectangle sounded every two hundred metres has
        nothing to say about a point a hundred metres along - and answering with the
        nearest thing it does know would be the cache lying, which is the one failure
        worth being strict about.

    """
    return tuple(sheet for sheet in _BAKED.get(world, ()) if abs(sheet.cell - cell) < 1e-9)


def forget_baked(world=None):
    """
    Drop pre-sounded rectangles from memory.

    Args:
        world (MaritimeMapProvider, optional): Just this one. All of them if omitted.

    Returns:
        dropped (int): How many rectangles were let go.

    Notes:
        Separate from `forget`, and deliberately. A bake is expensive and lives on disk;
        dropping it as a side effect of clearing a memory cache would quietly undo a
        server's whole startup, and the symptom would be charts getting slower over time
        for no visible reason.

    """
    if world is not None:
        return len(_BAKED.pop(world, ()))
    dropped = sum(len(sheets) for sheets in _BAKED.values())
    _BAKED.clear()
    return dropped


def reader(world, cell):
    """
    A way of asking this world for ground, that remembers what it said.

    Args:
        world (MaritimeMapProvider): The world to ask.
        cell (float): The lattice being sounded on.

    Returns:
        read (callable): Takes a `WorldPosition` and returns the true seabed elevation.

    Notes:
        Returns a closure rather than taking the world on every call, because the caller
        is a loop over nine thousand points and the lookup of which dictionary to use is
        worth doing once.

        Positions off the lattice are answered honestly and *not* remembered. A caller
        that asks about an arbitrary point gets the right number and no cache entry, which
        is better than either refusing it or filling the cache with points nothing will
        ask for twice.

    """
    remembered = _REMEMBERED.setdefault(world, {})
    known = remembered.get(cell)
    if known is None:
        known = OrderedDict()
        remembered[cell] = known

    limit = _limit()
    ground = world.terrain_z_at
    sheets = baked_for(world, cell)

    def read(position):
        # What was sounded before the server started, if anything was. Complete over its
        # own rectangle and one index to look in, so it is asked first and never written
        # to - there is nothing a bake could learn.
        for sheet in sheets:
            found = sheet.at(position.x, position.y)
            if found is not None:
                _HITS[0] += 1
                return found

        # Rounded to the nearest lattice point, then checked - rather than tested for
        # being exactly on one.
        #
        # A caller that snapped its corner to the lattice is asking about `k * cell +
        # column * cell`, which in floating point is not quite `(k + column) * cell`. An
        # exact test rejected three points in five and the cache held four thousand
        # soundings where it should have held nine, so it looked like a cache and behaved
        # like a two-times speedup instead of a twenty-times one.
        #
        # The tolerance stays tight enough that a genuinely off-lattice question is still
        # answered from the world rather than from the nearest thing lying about.
        column = position.x / cell
        row = position.y / cell
        key = (round(column), round(row))
        if abs(column - key[0]) > ON_LATTICE or abs(row - key[1]) > ON_LATTICE:
            return ground(position)

        found = known.get(key)
        if found is not None:
            _HITS[0] += 1
            known.move_to_end(key)
            return found

        _MISSES[0] += 1
        found = ground(position)
        known[key] = found
        if len(known) > limit:
            known.popitem(last=False)
        return found

    return read


def at(world, x, y, cell):
    """
    One sounding, on the lattice.

    Args:
        world (MaritimeMapProvider): The world to ask.
        x (float): Easting, in metres. Snapped.
        y (float): Northing, in metres. Snapped.
        cell (float): The lattice cell size.

    Returns:
        elevation (float): The true seabed, in metres.

    """
    return reader(world, cell)(WorldPosition(snap(x, cell), snap(y, cell)))


def forget(world=None):
    """
    Drop what is remembered.

    Args:
        world (MaritimeMapProvider, optional): Just this one. All of them if omitted.

    Returns:
        dropped (int): How many soundings were let go.

    Notes:
        For a game that has rebuilt its world under a running server, and for tests, which
        need to prove that a cache is a cache by watching it miss.

    """
    if world is not None:
        levels = _REMEMBERED.pop(world, {})
        return sum(len(level) for level in levels.values())
    dropped = sum(len(level) for levels in _REMEMBERED.values() for level in levels.values())
    _REMEMBERED.clear()
    _HITS[0] = 0
    _MISSES[0] = 0
    return dropped


def statistics():
    """
    Returns:
        report (dict): `held`, `hits`, `misses` and `hit_rate`.

    Notes:
        The only way to find out in a running game whether any of this is doing anything.
        A hit rate that stays near zero means the lattice is not being shared - which is a
        real failure and a silent one, since a cache that never hits is indistinguishable
        from no cache except in the profile.

    """
    held = sum(len(level) for levels in _REMEMBERED.values() for level in levels.values())
    asked = _HITS[0] + _MISSES[0]
    return {
        "held": held,
        "hits": _HITS[0],
        "misses": _MISSES[0],
        "hit_rate": (_HITS[0] / asked) if asked else 0.0,
    }


def _limit():
    """
    Returns:
        limit (int): How many soundings one level may hold.

    """
    from . import config

    try:
        return max(1000, int(config.get_setting("SOUNDING_CACHE", DEFAULT_LIMIT)))
    except (TypeError, ValueError):
        return DEFAULT_LIMIT


__all__ = ("DEFAULT_LIMIT", "snap", "reader", "at", "forget", "statistics")
