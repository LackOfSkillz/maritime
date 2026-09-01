"""
Drawing a chart out of what somebody surveyed.

A coastline is not authored anywhere in this contrib. The world answers how high the
ground is at a point, and a coastline is simply the line where that answer crosses the
datum - so the chart is *contoured* rather than drawn, and a game that authored a shoal
has authored the shape of it without doing any more work.

**It contours the chart, not the sea.** `charted_terrain_z_at` is asked, never the map
provider, and that one choice buys three things at once:

    the coastline is wrong in the same places every voyage, because a chart's error is
        a deterministic function of its seed and the place

    water nobody has surveyed comes back as a hole in the paper rather than as empty
        sea, because a chart covers where its surveyor went and nowhere else

    a better chart is visibly better

It also means the true seabed is never fetched, so it cannot leak. There is no filtering
step here to forget.

The method is marching squares: sample a grid, and for every cell work out where the
level crosses its edges. It needs no libraries, it is a hundred lines, and it produces
polylines that an SVG path can take directly.

"""

import math

from ..charts import charted_terrain_z_at
from ..position import METRES_PER_FATHOM, WorldPosition

#: How many samples across the visible square.
#:
#: Measured rather than guessed, and raised once the panel outgrew the assumption it
#: was first chosen under. At forty-eight the note here read "finer than this buys
#: detail nobody can see on a panel a few hundred pixels wide", which was true of the
#: panel it was written for. A chart a thousand pixels wide showing forty kilometres
#: put eight hundred and fifty metres between samples - about twenty-two pixels - and
#: a coastline traced through points that far apart is a row of long straight walls.
#:
#: Timed on the same seabed at the same span: 48 costs 14ms, 96 costs 35ms, 128 costs
#: 61ms. Ninety-six halves the distance between samples for twenty-one milliseconds on
#: a redraw that is debounced and only happens when somebody zooms, drags or resizes.
GRID = 96

#: Contour levels, as elevation relative to chart datum. Zero is the waterline; the
#: rest are the fathom lines a pilot actually cares about, because the difference
#: between two fathoms and five is the difference between anchoring and grounding.
COASTLINE = 0.0
FATHOM_LINES = (2.0, 5.0, 10.0)


def surveyed(value):
    """
    Args:
        value: Whatever the chart answered for a place.

    Returns:
        known (bool): Whether anybody actually sounded it.

    Notes:
        Off the sheet a chart answers nothing, and nothing is not a depth. Every
        loop below has to ask, because a contour drawn through unsurveyed water
        would be the chart inventing a coastline - the one thing a chart panel must
        never do.

    """
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def sample(chart, world, now, west, south, span, steps=GRID):
    """
    A square of charted elevations.

    Args:
        chart (Chart): The paper being read.
        world (MaritimeMapProvider): The ground beneath it.
        now (float): Game time, because charts age.
        west (float): Left edge, in metres.
        south (float): Bottom edge, in metres.
        span (float): How wide and tall the square is, in metres.
        steps (int, optional): Samples along each side.

    Returns:
        grid (list): Rows of elevations, south to north.

    """
    cell = span / float(steps - 1)
    grid = []
    for row in range(steps):
        y = south + row * cell
        line = []
        for column in range(steps):
            x = west + column * cell
            line.append(charted_terrain_z_at(chart, WorldPosition(x, y), now, world))
        grid.append(line)
    return grid


def _crossing(first, second, level):
    """
    Where along an edge the level falls.

    Args:
        first (float): Value at one end.
        second (float): Value at the other.
        level (float): The level being traced.

    Returns:
        fraction (float): How far along, from 0 to 1.

    Notes:
        Interpolated rather than taken at the midpoint, which is what stops a
        contoured coastline looking like a staircase at any useful zoom.

    """
    if second == first:
        return 0.5
    return (level - first) / (second - first)


def contour(grid, level, west, south, span):
    """
    Trace one level through a sampled square.

    Args:
        grid (list): Rows of elevations, as `sample` returns.
        level (float): The elevation to trace.
        west (float): Left edge of the square, in metres.
        south (float): Bottom edge, in metres.
        span (float): Width and height, in metres.

    Returns:
        segments (list): `((x1, y1), (x2, y2))` pairs in world metres.

    Notes:
        Marching squares. Each cell of four samples is above or below the level at
        each corner, which gives sixteen cases, of which fourteen produce a line.
        The two saddles are drawn as two separate lines - the ambiguous case, and
        splitting it is the conventional and harmless answer.

    """
    steps = len(grid)
    cell = span / float(steps - 1)
    segments = []

    for row in range(steps - 1):
        for column in range(steps - 1):
            bottom_left = grid[row][column]
            bottom_right = grid[row][column + 1]
            top_right = grid[row + 1][column + 1]
            top_left = grid[row + 1][column]

            # A cell with an unsounded corner is not contoured. The line has to
            # stop at the edge of what somebody surveyed, which is what leaves a
            # hole in the paper rather than a guess across it.
            if not (
                surveyed(bottom_left)
                and surveyed(bottom_right)
                and surveyed(top_right)
                and surveyed(top_left)
            ):
                continue

            case = 0
            if bottom_left > level:
                case |= 1
            if bottom_right > level:
                case |= 2
            if top_right > level:
                case |= 4
            if top_left > level:
                case |= 8
            # Wholly on one side of the level, so there is no line through it.
            #
            # Only the zero matters: fifteen falls through every branch below and
            # appends nothing anyway, so removing it changes no behaviour and no
            # test can catch it. It is named because a reader counting the sixteen
            # cases should be able to see where both of the empty ones went.
            if case in (0, 15):
                continue

            x0 = west + column * cell
            y0 = south + row * cell

            def on_bottom():
                return (x0 + cell * _crossing(bottom_left, bottom_right, level), y0)

            def on_right():
                return (x0 + cell, y0 + cell * _crossing(bottom_right, top_right, level))

            def on_top():
                return (x0 + cell * _crossing(top_left, top_right, level), y0 + cell)

            def on_left():
                return (x0, y0 + cell * _crossing(bottom_left, top_left, level))

            if case in (1, 14):
                segments.append((on_left(), on_bottom()))
            elif case in (2, 13):
                segments.append((on_bottom(), on_right()))
            elif case in (3, 12):
                segments.append((on_left(), on_right()))
            elif case in (4, 11):
                segments.append((on_right(), on_top()))
            elif case in (6, 9):
                segments.append((on_bottom(), on_top()))
            elif case in (7, 8):
                segments.append((on_left(), on_top()))
            elif case == 5:
                segments.append((on_left(), on_bottom()))
                segments.append((on_right(), on_top()))
            elif case == 10:
                segments.append((on_left(), on_top()))
                segments.append((on_bottom(), on_right()))
    return segments


def join(segments, tolerance=1.0):
    """
    Thread loose segments into polylines.

    Args:
        segments (list): Pairs of points, as `contour` returns.
        tolerance (float, optional): How close two ends must be to count as the
            same point, in metres.

    Returns:
        polylines (list): Lists of points, each a continuous run.

    Notes:
        Marching squares emits a cell at a time and in no order. Drawn as they come
        that is thousands of two-point paths; threaded, a coastline is a handful of
        long ones, which is the difference between a chart a browser can pan
        smoothly and one it cannot.

        Endpoints are indexed so that growing a line is a lookup rather than a
        search. The first version rescanned every segment for every step, which is
        quadratic and was slow enough on a real coastline to be worth not shipping.

    """

    def key(point):
        return (round(point[0] / tolerance), round(point[1] / tolerance))

    at_end = {}
    for index, (start, finish) in enumerate(segments):
        at_end.setdefault(key(start), []).append(index)
        at_end.setdefault(key(finish), []).append(index)

    spent = set()
    lines = []

    def grow(line):
        """Extend a line from its last point until nothing joins on."""
        while True:
            here = key(line[-1])
            following = None
            for index in at_end.get(here, ()):
                if index in spent:
                    continue
                start, finish = segments[index]
                if key(start) == here:
                    following = (index, finish)
                elif key(finish) == here:
                    following = (index, start)
                if following is not None:
                    break
            if following is None:
                return
            index, point = following
            spent.add(index)
            line.append(point)

    for index, (start, finish) in enumerate(segments):
        if index in spent:
            continue
        spent.add(index)
        line = [start, finish]
        grow(line)
        line.reverse()
        grow(line)
        lines.append(line)
    return lines


def simplify(line, tolerance=25.0):
    """
    Drop points a chart does not need.

    Args:
        line (list): A polyline of world points.
        tolerance (float, optional): How far a point may sit from the line between
            its neighbours before it is worth keeping, in metres.

    Returns:
        line (list): The same shape with fewer points in it.

    Notes:
        Marching squares puts a vertex on every cell edge it crosses, and most of
        them sit on a straight run where they say nothing. A coastline drawn at a
        few leagues to the panel does not need a point every four hundred metres,
        and sending them all made the payload enormous - which was how a chart
        ended up printed across somebody's message window.

        Perpendicular distance rather than the full Douglas-Peucker recursion. It is
        a few lines instead of thirty and the difference is invisible at any scale a
        chart panel is read at.

    """
    if len(line) < 3:
        return line

    kept = [line[0]]
    for index in range(1, len(line) - 1):
        ax, ay = kept[-1]
        bx, by = line[index]
        cx, cy = line[index + 1]

        run = math.hypot(cx - ax, cy - ay)
        if run <= 0.0:
            continue
        away = abs((cx - ax) * (ay - by) - (ax - bx) * (cy - ay)) / run
        if away >= tolerance:
            kept.append(line[index])
    kept.append(line[-1])
    return kept


def as_offsets(polylines, origin, places=0):
    """
    Move polylines into metres from the ship, ready to send.

    Args:
        polylines (list): Lists of world points.
        origin (WorldPosition): Where she reckons she is.
        places (int, optional): Decimal places to keep. Whole metres by default:
            a coastline is a surveyor's opinion, and reporting it to the centimetre
            would be precision the chart never had.

    Returns:
        lines (list): Lists of `[east, north]` pairs.

    Notes:
        Offsets rather than coordinates, and from the *reckoned* position. A chart
        that has drifted from the reckoning therefore draws the coast in the wrong
        place, which is exactly what being lost looks like and exactly what the
        navigator has to work with. Sending absolute positions would also hand a
        browser a survey of the world it was never entitled to.

    """
    out = []
    for line in polylines:
        thinned = simplify(line)
        if len(thinned) < 2:
            continue
        out.append([[round(x - origin.x, places), round(y - origin.y, places)] for x, y in thinned])
    return out


#: Roughly how many depths to print across the sheet, each way.
#:
#: A count rather than a sampling interval, because legibility depends on how many
#: figures land on the paper and not on how finely the seabed was sampled underneath
#: them. Printing one grid point in six was the same thing only while the grid never
#: changed size: raising it from forty-eight to ninety-six quietly took the printed
#: scatter from sixty-four figures to two hundred and fifty-six, which arrives as an
#: unreadable block of digits sitting over the ship.
PRINTED = 8


def soundings(grid, west, south, span, origin, every=None):
    """
    A scatter of charted depths, as a chart prints them.

    Args:
        grid (list): Rows of elevations.
        west (float): Left edge, in metres.
        south (float): Bottom edge, in metres.
        span (float): Width and height, in metres.
        origin (WorldPosition): Where she reckons she is.
        every (int, optional): Print one sample in this many, each way. Worked out
            from the grid by default, so the scatter stays the same size however
            finely the seabed was sampled underneath it.

    Returns:
        soundings (list): `[east, north, fathoms]` for each printed depth.

    Notes:
        Thinned on purpose. A chart prints a legible scatter of figures rather than
        every sounding ever taken, and a grid of two thousand numbers is unreadable
        at any size.

        Land is skipped rather than printed as a negative depth, because a chart
        does not sound a hillside.

    """
    steps = len(grid)
    if every is None:
        every = max(1, int(round(steps / float(PRINTED))))
    cell = span / float(steps - 1)
    out = []
    for row in range(0, steps, every):
        for column in range(0, steps, every):
            elevation = grid[row][column]
            if not surveyed(elevation) or elevation >= 0.0:
                continue
            out.append(
                [
                    round(west + column * cell - origin.x, 1),
                    round(south + row * cell - origin.y, 1),
                    round(-elevation / METRES_PER_FATHOM, 1),
                ]
            )
    return out


def coverage(chart, origin):
    """
    The edge of the paper, if it falls within reach.

    Args:
        chart (Chart): The chart being drawn.
        origin (WorldPosition): Where she reckons she is.

    Returns:
        bounds (dict): The sheet's corners, as offsets in metres.

    Notes:
        Sent so the interface can show where surveying stops. Off the chart is a
        state rather than a failure, and a navigator needs to see the edge coming
        rather than discover it by finding no soundings.

    """
    return {
        "west": round(chart.west - origin.x, 1),
        "east": round(chart.east - origin.x, 1),
        "south": round(chart.south - origin.y, 1),
        "north": round(chart.north - origin.y, 1),
    }


def fathoms(level):
    """
    Args:
        level (float): Fathoms below datum.

    Returns:
        elevation (float): The same as an elevation, for contouring.

    """
    return -abs(level) * METRES_PER_FATHOM


def bearing_of(east, north):
    """
    Args:
        east (float): Metres east.
        north (float): Metres north.

    Returns:
        bearing (float): True bearing, in degrees.

    """
    return math.degrees(math.atan2(east, north)) % 360.0
