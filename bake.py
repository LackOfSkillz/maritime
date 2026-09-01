"""
The seabed, sounded once and written down.

`seabed` remembers what the ground was for as long as the server runs. This writes it to
disk, so the answer survives a restart and the first captain of the day does not pay for
every sounding the last one already made.

It is worth doing because the ground is *deterministic*. A generated world produces the same
seabed from the same seed for ever, so computing it twice is not caution - it is waste. The
same argument a game engine makes when it ships baked terrain rather than generating it on
every machine at every launch.

**What can be baked, and what cannot.** Measured at eighty-two microseconds a sounding:

    the whole planet at chart detail        11 days      23 GB     out of the question
    the whole planet at five-kilometre      28 minutes   41 MB     the globe's layer
    one inhabited coast at chart detail     27 seconds    1 MB     the one that matters

So nobody bakes a planet at chart detail, and nobody needs to. Fine soundings are wanted
where ships are, and a coast is small; open ocean is wanted coarsely, and coarse is cheap.
The gap between the two is water nobody looks at closely, which is why the gap is allowed
to exist.

**Baked at the scales the chart actually asks for.** A stored grid only helps if its points
are the points somebody wants, and the client's zoom ladder means there are seven of those
and not infinitely many. A grid baked at some other spacing would be a file that is never
read.

**A bake is checked against the world before it is trusted.** A file from a different seed
describes a different planet, and using it would put a coastline where there is open water -
which would look exactly like a bug in the generator. The check is a fingerprint taken by
sounding a fixed scatter of points and hashing what came back, so it costs a few
milliseconds and needs the provider to say nothing about itself.
"""

import hashlib
import os
import struct
from array import array

from . import seabed
from .position import WorldPosition

#: What a bake file starts with, so a truncated or foreign file is refused rather than
#: read as depths.
MAGIC = b"MARSEA01"

#: What the manifest beside the soundings is called.
MANIFEST = "world.json"

#: The header, after the magic: cell, west, south, columns, rows, scale.
HEADER = struct.Struct("<ddd II d")

#: How many bytes of fingerprint follow the header.
FINGERPRINT_BYTES = 16

#: The value meaning "this one was never sounded". The most negative a signed short holds,
#: which is not a depth anywhere.
UNSOUNDED = -32768

#: The finest metres-per-unit worth storing, and the coarsest that will ever be needed.
#:
#: A short holds ±32767, so the scale decides both the precision and the reach: a hundredth
#: of a metre reaches 327 m, a tenth reaches 3.2 km, a whole metre reaches 32 km. **Which
#: one a rectangle gets is decided by the ground in it**, not by anything authored.
#:
#: It was authored, briefly, keyed to the cell size - on the reasoning that coarse grids are
#: for open ocean. That is not reasoning, it is a guess about geography, and it stored whole
#: metres for a shallow coast sounded at a kilometre. A fathom line drawn through
#: metre-quantised ground moves, and the baked chart stopped matching the unbaked one.
FINEST_SCALE = 0.01
COARSEST_SCALE = 1.0

#: How many points to sound when fingerprinting a world. Enough that two different planets
#: cannot agree by chance, few enough to cost nothing.
FINGERPRINT_POINTS = 64


class Baked:
    """
    A rectangle of seabed, sounded at one spacing.

    Notes:
        Held as a flat array of signed shorts rather than a dictionary of floats. A million
        soundings is two megabytes this way and something over a hundred as a dict, and the
        lookup is arithmetic rather than hashing - which matters, because this sits in front
        of the thing a chart does nine thousand times a sheet.

    """

    __slots__ = ("cell", "west", "south", "columns", "rows", "scale", "values", "fingerprint")

    def __init__(self, cell, west, south, columns, rows, scale, values, fingerprint=b""):
        self.cell = float(cell)
        self.west = float(west)
        self.south = float(south)
        self.columns = int(columns)
        self.rows = int(rows)
        self.scale = float(scale)
        self.values = values
        self.fingerprint = fingerprint

    def __len__(self):
        return self.columns * self.rows

    def covers(self, x, y):
        """
        Args:
            x (float): Easting, in metres.
            y (float): Northing, in metres.

        Returns:
            inside (bool): Whether this rectangle holds that point.

        """
        column = round((x - self.west) / self.cell)
        row = round((y - self.south) / self.cell)
        return 0 <= column < self.columns and 0 <= row < self.rows

    def at(self, x, y):
        """
        Args:
            x (float): Easting, in metres. Expected on this grid's lattice.
            y (float): Northing, in metres.

        Returns:
            elevation (float or None): The sounding, or None if this rectangle has nothing
                to say about that point.

        Notes:
            Rounded to the nearest cell and then checked, rather than tested for landing
            exactly on one. The caller arrived here through `k * cell + column * cell`,
            which is not quite `(k + column) * cell` in floating point - and an exact test
            silently rejects most of what it is given. That mistake has already been made
            once, in the memory cache, where it turned a twentyfold saving into a twofold
            one.

        """
        column = round((x - self.west) / self.cell)
        row = round((y - self.south) / self.cell)
        if not (0 <= column < self.columns and 0 <= row < self.rows):
            return None
        stored = self.values[row * self.columns + column]
        if stored == UNSOUNDED:
            return None
        return stored * self.scale


def fingerprint(world):
    """
    A short signature of what this world's ground looks like.

    Args:
        world (MaritimeMapProvider): The world to sign.

    Returns:
        signature (bytes): Sixteen bytes.

    Notes:
        Sounded rather than declared. A provider could be asked for a seed, but not every
        provider has one and a game is free to change its terrain without changing it -
        so the honest signature is the ground itself, sampled.

        The scatter is fixed and irregular. A regular grid would agree between two worlds
        that happen to share a shelf; these points are spread far enough apart that two
        planets agreeing on all of them are the same planet.

    """
    digest = hashlib.md5()
    for step in range(FINGERPRINT_POINTS):
        # An irregular but fixed scatter, from a cheap integer hash rather than a random
        # number generator, so it is the same on every machine and in every process.
        x = ((step * 2_654_435_761) % 4_000_000) - 2_000_000
        y = ((step * 1_597_334_677) % 4_000_000) - 2_000_000
        ground = world.terrain_z_at(WorldPosition(float(x), float(y)))
        digest.update(struct.pack("<d", round(float(ground), 3)))
    return digest.digest()


def sound(world, west, south, cell, columns, rows, scale=None, watching=None):
    """
    Sound a rectangle of seabed.

    Args:
        world (MaritimeMapProvider): The world to ask.
        west (float): Left edge, in metres. Snapped to the cell.
        south (float): Bottom edge, in metres. Snapped to the cell.
        cell (float): Spacing, in metres.
        columns (int): How many points across.
        rows (int): How many points up.
        scale (float, optional): Ignored. The scale is chosen from the ground itself -
            see `scale_for`.
        watching (callable, optional): Called with `(done, total)` now and then, so a
            server baking for two minutes can say so rather than appearing to have hung.

    Returns:
        baked (Baked): The rectangle.

    """
    west = seabed.snap(west, cell)
    south = seabed.snap(south, cell)
    ground = world.terrain_z_at
    total = columns * rows

    # Sounded into floats first, so the scale can be chosen from what is actually there.
    # Four bytes a point while this runs; a million points is four megabytes for as long
    # as it takes to quantise them.
    metres = array("f", bytes(4 * columns * rows))
    done = 0
    for row in range(rows):
        northing = south + row * cell
        base = row * columns
        for column in range(columns):
            metres[base + column] = ground(WorldPosition(west + column * cell, northing))
        done += columns
        if watching is not None and row % 32 == 0:
            watching(done, total)
    if watching is not None:
        watching(total, total)

    scale = scale_for(metres)
    values = array("h", bytes(2 * columns * rows))
    for index, deep in enumerate(metres):
        values[index] = int(round(deep / scale))

    return Baked(cell, west, south, columns, rows, scale, values, fingerprint(world))


def scale_for(metres):
    """
    The finest metres-per-unit that holds this ground in a signed short.

    Args:
        metres (iterable): Elevations, in metres.

    Returns:
        scale (float): Metres per stored unit.

    Notes:
        Chosen from the data rather than authored, so a shallow coast is stored to the
        centimetre and an abyssal plain to the metre, and neither has to be predicted by
        whoever set up the bake. The failure this replaces was quiet: whole-metre storage
        for a shelf moved every fathom line a little, and the baked chart no longer matched
        the unbaked one.

    """
    deepest = 0.0
    for value in metres:
        if value > deepest:
            deepest = value
        elif -value > deepest:
            deepest = -value
    if deepest <= 0.0:
        return FINEST_SCALE
    needed = deepest / 32000.0
    scale = FINEST_SCALE
    while scale < needed and scale < COARSEST_SCALE:
        scale *= 10.0
    return min(scale, COARSEST_SCALE)


def write(path, baked):
    """
    Args:
        path (str): Where to write.
        baked (Baked): What to write.

    Returns:
        written (int): Bytes written.

    Notes:
        Written to a neighbouring name and moved into place, so a bake interrupted by a
        power cut leaves the old file rather than half a new one. A truncated bake would
        be read as a rectangle of very shoal water, which is the worst possible failure:
        every ship in the region aground on nothing.

    """
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    partial = path + ".part"
    with open(partial, "wb") as out:
        out.write(MAGIC)
        out.write(
            HEADER.pack(baked.cell, baked.west, baked.south, baked.columns, baked.rows, baked.scale)
        )
        out.write(baked.fingerprint.ljust(FINGERPRINT_BYTES, b"\0")[:FINGERPRINT_BYTES])
        out.write(baked.values.tobytes())
    os.replace(partial, path)
    return os.path.getsize(path)


def read(path):
    """
    Args:
        path (str): A file `write` produced.

    Returns:
        baked (Baked or None): What it holds, or None if it is not one of ours, is
            truncated, or is otherwise not to be trusted.

    Notes:
        Refuses rather than raises. A bad bake file is a thing a game should start without,
        having said so - not a thing that stops it starting.

    """
    try:
        with open(path, "rb") as source:
            if source.read(len(MAGIC)) != MAGIC:
                return None
            head = source.read(HEADER.size)
            if len(head) != HEADER.size:
                return None
            cell, west, south, columns, rows, scale = HEADER.unpack(head)
            signature = source.read(FINGERPRINT_BYTES)
            values = array("h")
            values.frombytes(source.read(2 * columns * rows))
    except (OSError, ValueError, struct.error):
        return None

    if len(values) != columns * rows:
        return None
    return Baked(cell, west, south, columns, rows, scale, values, signature)


def load(directory, world, on_report=None):
    """
    Read every bake in a directory that belongs to this world.

    Args:
        directory (str): Where the bakes live.
        world (MaritimeMapProvider): The world they should describe.
        on_report (callable, optional): Called with a line of plain text for each file.

    Returns:
        loaded (tuple): The `Baked` rectangles now in use.

    Notes:
        **Checked against the world, and skipped rather than trusted.** A file from another
        seed describes another planet, and reading it would put a coastline where there is
        open water - which looks exactly like a bug in the generator and is very hard to
        recognise as a stale file.

    """
    if not directory or not os.path.isdir(directory):
        return ()

    signature = fingerprint(world)
    loaded = []
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".seabed"):
            continue
        path = os.path.join(directory, name)
        baked = read(path)
        if baked is None:
            _say(on_report, f"maritime: ignoring {name}, which is not a readable bake")
            continue
        if baked.fingerprint != signature:
            _say(on_report, f"maritime: ignoring {name}, which was baked from another world")
            continue
        seabed.remember_baked(world, baked)
        loaded.append(baked)
        _say(on_report, f"maritime: loaded {name}, {len(baked):,} soundings at {baked.cell:.0f} m")
    return tuple(loaded)


def bundle(world, sheets, directory, on_report=None, watching=None):
    """
    Write a whole world - soundings and the manifest that makes them a world.

    Args:
        world (MaritimeMapProvider): The world to record.
        sheets (iterable): `(label, area, cell)` for each rectangle to sound, where area is
            `(west, south, east, north)` in metres.
        directory (str): Where to write the bundle.
        on_report (callable, optional): Called with a line of plain text.
        watching (callable, optional): Called with `(done, total)` while sounding.

    Returns:
        written (tuple): Paths written, the manifest last.

    Notes:
        **Sheets, not one blanket.** A chart of a coast is a small-scale sheet over the
        whole of it and a large-scale one over the harbour, because detail is wanted where
        ships are and nowhere else. Sounding the fine level over a whole region costs ten
        times what sounding it over the inhabited part costs, and buys open ocean nobody
        looks at closely.

        **The manifest is where a world stops being a grid of numbers.** Soundings give
        depth and a coastline and nothing else - no bottom, no marked rock, no island with
        a name, no latitude. Those are asked of the provider here and written as plain
        text, so the interesting half of a world stays readable while only the bulk is
        binary.

    """
    os.makedirs(directory, exist_ok=True)
    written = []
    for label, area, cell in sheets:
        west, south, east, north = (float(edge) for edge in area)
        cell = float(cell)
        columns = int((east - west) / cell) + 1
        rows = int((north - south) / cell) + 1
        _say(on_report, f"maritime: sounding {label}, {columns * rows:,} points at {cell:.0f} m")
        sounded = sound(world, west, south, cell, columns, rows, watching=watching)
        path = os.path.join(directory, f"{int(round(cell))}m-{label}.seabed")
        size = write(path, sounded)
        seabed.remember_baked(world, sounded)
        written.append(path)
        _say(on_report, f"maritime: wrote {os.path.basename(path)}, {size / 1e6:.2f} MB")

    path = os.path.join(directory, MANIFEST)
    _write_manifest(path, world, directory)
    written.append(path)
    _say(on_report, f"maritime: wrote {MANIFEST}")
    return tuple(written)


def _write_manifest(path, world, directory):
    """
    Args:
        path (str): Where to write it.
        world (MaritimeMapProvider): The world to describe.
        directory (str): The bundle, read to find out what is actually in it.

    Notes:
        **The sheet list is read off the directory, not off what this call sounded.** A
        bundle is often built in more than one go - the coarse levels first, a close-quarters
        one later - and a manifest describing only the most recent call quietly forgets the
        rest. That happened: adding one inshore sheet rewrote a manifest that had listed
        five, and nothing complained, because the provider finds its soundings by looking in
        the directory and never reads the list.

        A record nothing depends on is exactly the kind that rots without being noticed,
        which is a reason to derive it rather than a reason to drop it.

        Everything else here is *asked of the provider*, so this works for a generated
        world, a tiled one, or anything else a game supplies. Nothing about how the ground
        was made reaches the file.

    """
    import json

    present = []
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".seabed"):
            continue
        sheet = read(os.path.join(directory, name))
        if sheet is None:
            continue
        present.append(
            {
                "file": name,
                "cell": round(sheet.cell, 4),
                "area": [
                    round(sheet.west, 1),
                    round(sheet.south, 1),
                    round(sheet.west + (sheet.columns - 1) * sheet.cell, 1),
                    round(sheet.south + (sheet.rows - 1) * sheet.cell, 1),
                ],
                "soundings": len(sheet),
                "scale": sheet.scale,
            }
        )

    widest = max((abs(edge) for sheet in present for edge in sheet["area"]), default=100_000.0)
    centre = WorldPosition(0.0, 0.0)

    anchor = None
    asked = getattr(world, "geographic_at", None)
    if asked is not None:
        anchor = asked(centre)

    dangers = []
    for danger in world.charted_dangers(centre, widest):
        dangers.append(
            {
                "key": danger.key,
                "x": round(danger.x, 1),
                "y": round(danger.y, 1),
                "radius": round(danger.radius, 1),
                "top_z": round(danger.top_z, 2),
                "bottom": danger.bottom,
            }
        )

    landmarks = []
    for mark in world.landmarks_near(centre, widest):
        landmarks.append(
            {
                "key": mark.key,
                "x": round(mark.x, 1),
                "y": round(mark.y, 1),
                "radius": round(mark.radius, 1),
                "height": round(mark.height, 1),
                "kind": mark.kind,
            }
        )

    with open(path, "w", encoding="utf-8") as out:
        json.dump(
            {
                "anchor": [round(part, 6) for part in anchor] if anchor else None,
                "bottom": world.bottom_type_at(centre),
                "dangers": dangers,
                "landmarks": landmarks,
                "sheets": present,
            },
            out,
            indent=2,
            sort_keys=True,
        )


def bake(world, area, cells, directory, on_report=None, watching=None):
    """
    Sound an area at several spacings and write the lot.

    Args:
        world (MaritimeMapProvider): The world to sound.
        area (tuple): `(west, south, east, north)` in metres.
        cells (iterable): Spacings to bake, in metres.
        directory (str): Where to write.
        on_report (callable, optional): Called with a line of plain text per file.
        watching (callable, optional): Called with `(done, total)` during each rectangle.

    Returns:
        written (tuple): Paths written.

    Notes:
        One file per spacing, named for it, so adding a scale later does not mean baking
        the others again - and so a game that decides one level is too expensive can
        delete it without touching the rest.

    """
    west, south, east, north = (float(edge) for edge in area)
    written = []
    for cell in cells:
        cell = float(cell)
        columns = int((east - west) / cell) + 1
        rows = int((north - south) / cell) + 1
        _say(on_report, f"maritime: sounding {columns * rows:,} points at {cell:.0f} m...")
        baked = sound(world, west, south, cell, columns, rows, watching=watching)
        path = os.path.join(directory, f"{int(round(cell))}m.seabed")
        size = write(path, baked)
        seabed.remember_baked(world, baked)
        written.append(path)
        _say(on_report, f"maritime: wrote {os.path.basename(path)}, {size / 1e6:.1f} MB")
    return tuple(written)


def chart_cells(reaches, steps):
    """
    The spacings a chart will actually ask for.

    Args:
        reaches (iterable): The zoom ladder, as reaches in metres.
        steps (int): Samples along a sheet's side - `cartography.GRID`.

    Returns:
        cells (tuple): Spacings in metres, coarsest first.

    Notes:
        A bake at any other spacing is a file nothing ever reads. The chart's cell is its
        span over its grid, and its span is twice whatever zoom the client asked for, so
        the set is small, known, and worth deriving rather than writing down twice.

    """
    return tuple(sorted({2.0 * float(reach) / (steps - 1) for reach in reaches}, reverse=True))


def warm(world, on_report=None):
    """
    Load the game's bakes, and make them if they are not there yet.

    Args:
        world (MaritimeMapProvider): The world to sound.
        on_report (callable, optional): Called with a line of plain text. Defaults to
            Evennia's log.

    Returns:
        ready (tuple): The `Baked` rectangles now in front of the cache.

    Notes:
        **This blocks, and on the first start it blocks for a while.** That is the whole
        bargain: a coast sounded once at startup is a coast nobody waits for afterwards,
        and the alternative is every captain paying for the same soundings for ever.
        Twisted is single-threaded, so doing it in the background would not help - it
        would spread the same stall across the first hour of play instead of taking it
        before anybody is aboard.

        Later starts read files and cost milliseconds. A game that would rather not wait
        configures no area, and everything falls back to being sounded on demand exactly
        as before.

    """
    if on_report is None:
        on_report = _log

    from . import config

    directory = config.get_setting("BAKE_DIR")
    area = config.get_setting("BAKE_AREA")
    if not directory or not area:
        return ()

    ready = load(directory, world, on_report)
    if ready:
        return ready

    reaches = config.get_setting("BAKE_SCALES") or ()
    if not reaches:
        return ()

    from .client.cartography import GRID

    cells = chart_cells(reaches, GRID)
    _say(on_report, "maritime: no seabed on disk yet - sounding it now, once.")
    bake(world, area, cells, directory, on_report, _progress(on_report))
    return tuple(sheet for cell in cells for sheet in seabed.baked_for(world, cell))


def _progress(on_report):
    """
    Args:
        on_report (callable): Where to say it.

    Returns:
        watching (callable): Takes `(done, total)` and speaks occasionally.

    Notes:
        A server that is going to be quiet for two minutes should say so, or somebody
        will kill it and report that maritime hangs on startup.

    """
    last = [-1]

    def watching(done, total):
        share = int(10 * done / max(1, total))
        if share != last[0]:
            last[0] = share
            _say(on_report, f"maritime: sounded {done:,} of {total:,} ({10 * share}%)")

    return watching


def _log(line):
    """
    Args:
        line (str): What to say.

    """
    from evennia.utils import logger

    logger.log_info(line)


def _say(on_report, line):
    """
    Args:
        on_report (callable or None): Where to say it.
        line (str): What to say.

    """
    if on_report is not None:
        on_report(line)


__all__ = (
    "UNSOUNDED",
    "FINEST_SCALE",
    "COARSEST_SCALE",
    "scale_for",
    "Baked",
    "fingerprint",
    "sound",
    "write",
    "read",
    "load",
    "bake",
    "chart_cells",
    "bundle",
    "MANIFEST",
)
