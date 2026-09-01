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

from .. import seabed
from ..charts import charted_terrain_z_at
from ..position import METRES_PER_FATHOM, WorldPosition

#: How many samples across the visible square.
#:
#: Measured rather than guessed, and raised once - then very nearly raised again by
#: mistake, which is the part worth writing down.
#:
#: At forty-eight the note here read "finer than this buys detail nobody can see on a
#: panel a few hundred pixels wide". That was true of the panel it was written for; a
#: chart a thousand pixels wide showing forty kilometres put eight hundred and fifty
#: metres between samples and drew a coastline as a row of long straight walls.
#:
#: A hundred and ninety-two looked like the obvious next step and is wrong. **A chart is
#: not the seabed - it is the seabed plus a survey error**, and that error varies over
#: patches a few hundred metres across. Sampling closer together than a patch resolves the
#: *error* rather than the shore. Measured on a forty-kilometre sheet over generated
#: ground, coastline traced against about fifty-five kilometres of real coast:
#:
#:      quality   at 96      at 192
#:      1.0       54.2 km    55.7 km      a perfect chart: the extra detail is real
#:      0.9       57.1 km    67.9 km      a fifth of the coast is now survey noise
#:      0.6      107.2 km   171.1 km      three times the real coastline
#:
#: So the useful sampling interval is bounded by how wrong the paper is, not by how
#: detailed the ground is, and the honest ceiling is a spacing no finer than a patch.
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


#: How many fine cells across one seed cell when sampling, at most.
#:
#: Sampling happens in two passes: a seed grid that *finds* the contours, and refinement
#: that draws them well. Only cells carrying a contour are sounded in full, and on a
#: generated world that is about one cell in twenty.
#:
#: A ceiling rather than a setting, because a seed cell wider than the finest structure in
#: the field steps straight over contours - see `_seed_factor`, which works out what is
#: safe here and takes the smaller of the two.
COARSE = 2

#: Not yet asked for, as distinct from asked and unsurveyed. A chart answers `None` off
#: its own edges and that is a real answer, so it cannot double as "no answer yet".
_UNREAD = object()


def traced_levels():
    """
    Returns:
        levels (tuple): Every elevation a sheet is contoured at.

    Notes:
        Sampling refines for exactly these. A caller contouring at some other level would
        get whatever the seed pass happened to leave there, so they are named in one
        place and `sample` takes them as an argument rather than assuming them.

    """
    return (COASTLINE,) + tuple(fathoms(line) for line in FATHOM_LINES)


#: The widest a seed cell may be, in metres.
#:
#: **A seed cell wider than the finest structure in the field steps straight over
#: contours, and no refinement pass can refine what it never saw.**
#:
#: Found by measurement rather than by reasoning, and the first guess was two and a half
#: times too generous. Two hundred and fifty looked principled - it is the patch a survey
#: error covers, and it is the finest wavelength the generator this was measured against
#: puts in its ground - and it drew a coastline nearly four hundred metres from where
#: sounding every point put it. Worst departure of the drawn contour, on generated coast:
#:
#:      seed cell     departure
#:          421 m       (never seeded)
#:          211 m           388 m     too coarse, and looked safe
#:           84 m            29 m
#:           42 m            18 m
#:
#: A hundred is inside the last safe measurement with room to spare. It means this pays
#: at close quarters and does nothing at a wide zoom, which is the opposite of convenient
#: - the wide sheets are the expensive ones. It is kept because halving the cost of the
#: chart a pilot is threading a harbour on is worth having, and because the alternative
#: was to seed everywhere and quietly draw a worse coastline.
SAFE_SEED = 100.0


def _seed_factor(cell, ceiling):
    """
    How coarse the seed pass may safely be, given how far apart the fine samples are.

    Args:
        cell (float): Metres between fine samples.
        ceiling (int): The most the caller will allow.

    Returns:
        factor (int): Fine cells per seed cell. One means sound everything.

    Notes:
        Derived rather than configured, because the safe answer depends on the zoom and
        a captain changes that continuously. A rule keyed to the sheet cannot be wrong
        for a sheet.

    """
    if ceiling < 2 or cell <= 0.0:
        return 1
    return max(1, min(ceiling, int(SAFE_SEED / cell)))


def _worth_refining(corners, levels):
    """
    Whether a seed cell can contain a contour, and so has to be looked at closely.

    Args:
        corners (tuple): The four charted elevations around the cell.
        levels (tuple): The elevations being traced.

    Returns:
        worth (bool): Whether to sound inside it.

    Notes:
        **A cell whose corners all lie on one side of every level cannot contain a
        crossing of one**, and that is provable rather than probable: what fills such a
        cell is bilinear interpolation, which stays between the values it is given. The
        contour drawn through a filled cell is therefore exactly the contour a uniform
        grid would have drawn there, which is none.

        What it does not claim is that the true seabed has no contour there. It may. The
        seed pass samples a continuous world and steps over things, exactly as the old
        uniform grid did at its own spacing - which is why `COARSE` is a judgement and
        not a free win.

        An unsurveyed corner always refines. Off the edge of the paper there is nothing
        to interpolate between, and filling there would be the chart inventing coverage.

    """
    for value in corners:
        if not surveyed(value):
            return True
    low = min(corners)
    high = max(corners)
    for level in levels:
        if low <= level <= high:
            return True
    return False


def _fill(grid, first_row, last_row, first_column, last_column, corners):
    """
    Fill a contour-free seed cell by interpolation rather than by sounding it.

    Notes:
        Only where nothing has been read. Seed cells share their edges with their
        neighbours, and a neighbour that was refined has already put real soundings along
        that edge; overwriting those with interpolated ones would lose good numbers to
        save nothing at all.

    """
    south_west, south_east, north_west, north_east = corners
    down = float(last_row - first_row)
    across = float(last_column - first_column)
    for row in range(first_row, last_row + 1):
        northward = (row - first_row) / down
        west_side = south_west + (north_west - south_west) * northward
        east_side = south_east + (north_east - south_east) * northward
        line = grid[row]
        for column in range(first_column, last_column + 1):
            if line[column] is not _UNREAD:
                continue
            eastward = (column - first_column) / across
            line[column] = west_side + (east_side - west_side) * eastward


def sample(chart, world, now, west, south, span, steps=GRID, coarse=COARSE, levels=None):
    """
    A square of charted elevations, sounded where it matters.

    Args:
        chart (Chart): The paper being read.
        world (MaritimeMapProvider): The ground beneath it.
        now (float): Game time, because charts age.
        west (float): Left edge, in metres.
        south (float): Bottom edge, in metres.
        span (float): How wide and tall the square is, in metres.
        steps (int, optional): Samples along each side.
        coarse (int, optional): Fine cells across one seed cell. One disables the seed
            pass and sounds every point, which is what this used to do.
        levels (tuple, optional): The elevations that will be contoured. Defaults to
            every level a sheet traces.

    Returns:
        grid (list): Rows of elevations, south to north.

    Notes:
        **Most of this square has no contour in it, and sounding all of it was the whole
        cost.** Counted on a generated world at a hundred and ninety-two across, one cell
        in twenty carries any of the traced levels and the other nineteen were sounded to
        produce nothing. Asking the world for a depth is very nearly the entire price of
        a sheet - eighty microseconds against a handful for the arithmetic around it - so
        not asking is worth a great deal more than asking faster.

        A seed grid finds the contours and only the cells carrying one are sounded in
        full. The rest are filled from their own corners, which can neither invent nor
        hide a crossing.

        The figures a chart actually prints are sounded exactly, whatever cell they land
        in. There are a few dozen of them, and a printed depth is a number a captain acts
        on rather than a line he reads a shape from.

        Measured on a forty-kilometre sheet over generated ground: a hundred and
        ninety-two across costs 2,684 ms sounded uniformly and 521 ms this way - less
        than the ninety-six grid it replaces, at twice the resolution.

    """
    if levels is None:
        levels = traced_levels()

    cell = span / float(steps - 1)

    # Asked through something that remembers what the ground was. The seabed does not
    # change, does not depend on which chart is being read and is the same for everybody,
    # so it is worth remembering - and it is very nearly the whole cost of a sheet.
    #
    # Hits need the points to coincide, which is the caller's business rather than this
    # function's: `chart_for` puts the sheet's corner on the lattice. Quantising the cell
    # *here* was the first attempt and was wrong - the grid then covered more ground than
    # the span it was drawn against, and every contour point came out misplaced by up to
    # a tenth of the sheet.
    ground = seabed.reader(world, cell)

    coarse = _seed_factor(cell, coarse)
    grid = [[_UNREAD] * steps for _ in range(steps)]

    def read(row, column):
        value = grid[row][column]
        if value is _UNREAD:
            value = charted_terrain_z_at(
                chart,
                WorldPosition(west + column * cell, south + row * cell),
                now,
                world,
                seabed=ground,
            )
            grid[row][column] = value
        return value

    if coarse < 2:
        for row in range(steps):
            for column in range(steps):
                read(row, column)
        return grid

    # The printed figures first, so no depth a captain reads was ever interpolated.
    printed = max(1, int(round(steps / float(PRINTED))))
    for row in range(0, steps, printed):
        for column in range(0, steps, printed):
            read(row, column)

    edges = list(range(0, steps - 1, coarse))
    if edges[-1] != steps - 1:
        edges.append(steps - 1)

    for first_row, last_row in zip(edges, edges[1:]):
        for first_column, last_column in zip(edges, edges[1:]):
            corners = (
                read(first_row, first_column),
                read(first_row, last_column),
                read(last_row, first_column),
                read(last_row, last_column),
            )
            if _worth_refining(corners, levels):
                for row in range(first_row, last_row + 1):
                    for column in range(first_column, last_column + 1):
                        read(row, column)
            else:
                _fill(grid, first_row, last_row, first_column, last_column, corners)
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


#: The shortest run of coastline worth drawing, as a multiple of the sample spacing.
#:
#: **A chart has a smallest thing it draws, and everything below it is left off.** That is
#: not a shortcut - a cartographer does the same, and calls it the minimum mappable unit:
#: an islet too small to draw at the sheet's scale is either omitted or given a symbol,
#: never rendered as a shape a pilot could mistake for something he could see.
#:
#: What arrives here below that size is not islets. It is survey error crossing the datum:
#: a poor chart is wrong by metres over patches of a few hundred, and where the true bottom
#: lies within that of the waterline, the error alone opens and closes little pools. Drawn,
#: they are a scatter of specks around the coast that no survey ever recorded, and they
#: move whenever the chart is redrawn at another scale.
#:
#: Three cells is a run that has actually gone somewhere. Anything real and smaller than
#: that belongs to the marks layer, which is where the isolated dangers already live for
#: precisely the same reason.
LEAST_RUN = 3.0


def worth_drawing(runs, span, steps=GRID, least=LEAST_RUN):
    """
    Drop the runs too short to be anything a survey found.

    Args:
        runs (list): Polylines, as joined.
        span (float): How wide the sheet is, in metres.
        steps (int, optional): Samples along each side.
        least (float, optional): Shortest run kept, in sample spacings.

    Returns:
        kept (list): The runs long enough to draw.

    Notes:
        Measured along the run rather than across its extent, so a long thin spit
        survives and a compact speck does not - which is the right way round, because a
        spit is a thing you can run onto and a speck is a thing you cannot see.

    """
    floor = least * (span / float(steps - 1))
    kept = []
    for run in runs:
        length = 0.0
        for (first_east, first_north), (next_east, next_north) in zip(run, run[1:]):
            length += math.hypot(next_east - first_east, next_north - first_north)
        if length >= floor:
            kept.append(run)
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


#: Degree spacings a chart is ruled at, coarsest first. The ones a printed chart uses:
#: whole degrees, then halves, then tenths, then hundredths - never an arbitrary fraction,
#: because a navigator reads a position off these and round numbers are the point of them.
GRATICULE_STEPS = (10.0, 5.0, 2.0, 1.0, 0.5, 0.2, 0.1, 0.05, 0.02, 0.01)

#: About how many ruled lines a sheet wants each way. Enough to read a position off,
#: few enough not to compete with the soundings.
GRATICULE_LINES = 4


def _nice_step(degrees):
    """
    Args:
        degrees (float): How many degrees the sheet spans.

    Returns:
        step (float): The largest round spacing that still gives a few lines.

    """
    for step in GRATICULE_STEPS:
        if degrees / step >= GRATICULE_LINES:
            return step
    return GRATICULE_STEPS[-1]


def graticule(world, origin, reach, steps=17):
    """
    The meridians and parallels a chart is ruled with.

    Args:
        world (MaritimeMapProvider): The world, which may or may not have a geography.
        origin (WorldPosition): Where she reckons she is.
        reach (float): How far the sheet extends, in metres.

    Returns:
        lines (list): Each `{"label": str, "kind": "parallel"|"meridian", "line": [...]}`,
            as offsets in metres.

    Notes:
        **Contoured, not plotted.** A parallel is the line where latitude equals a round
        number, which is exactly what `contour` already finds - so the graticule is the
        same marching squares the coastline uses, run over a grid of degrees instead of a
        grid of depths. Nothing new had to be written to make the lines curve, and they
        curve correctly, because the projection is doing it rather than an approximation
        of the projection.

        That matters for the reason the graticule is here at all. A chart is a flat sheet
        and the world is not; meridians converging on the paper is the one honest way to
        show that, and a navigator can see it happening as he zooms out.

        Nothing at all for a world with no geography. A seabed defined by an arithmetic
        ramp has no latitude, and ruling it with invented ones would be the chart claiming
        to know where in the world a game is when the game has not said.

        Coarse on purpose: seventeen samples a side. These are smooth global fields and
        the lines are ruled rather than surveyed, so there is nothing here to resolve.

    """
    where = getattr(world, "geographic_at", None)
    if where is None:
        return []

    span = reach * 2.0
    west, south = origin.x - reach, origin.y - reach
    cell = span / float(steps - 1)

    latitudes, longitudes = [], []
    for row in range(steps):
        lat_row, lon_row = [], []
        for column in range(steps):
            here = where(WorldPosition(west + column * cell, south + row * cell))
            if here is None:
                return []
            lat_row.append(here[0])
            lon_row.append(here[1])
        latitudes.append(lat_row)
        longitudes.append(lon_row)

    out = []
    for grid, kind in ((latitudes, "parallel"), (longitudes, "meridian")):
        flat = [value for row in grid for value in row]
        low, high = min(flat), max(flat)
        step = _nice_step(high - low)
        first = math.ceil(low / step) * step
        ruled = first
        while ruled <= high:
            for run in join(contour(grid, ruled, west, south, span)):
                out.append(
                    {
                        "kind": kind,
                        "label": _degrees(ruled, kind, step),
                        "line": [[round(x - origin.x, 1), round(y - origin.y, 1)] for x, y in run],
                    }
                )
            ruled += step
    return out


def _degrees(value, kind, step):
    """
    Args:
        value (float): Degrees, signed.
        kind (str): `"parallel"` or `"meridian"`.
        step (float): The spacing this set is ruled at.

    Returns:
        label (str): As a chart prints it - north and south, east and west, never a
            minus sign. A negative latitude is not a thing anybody says aloud.

    Notes:
        The precision comes from the *step*, not from the value. Asked per value, a
        sheet ruled every fifth of a degree prints "21.6" beside "21.62" - each correct
        on its own and ragged as a set, which is the one thing a ruled scale must not
        be. A chart decides the precision once, for the whole set, and prints every
        line to it.

    """
    hand = ("N", "S") if kind == "parallel" else ("E", "W")
    figures = max(0, min(2, -math.floor(math.log10(step))))
    return f"{abs(value):.{figures}f}°{hand[0] if value >= 0 else hand[1]}"


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
