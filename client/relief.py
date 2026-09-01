"""
Shaded relief under the chart, when a game has the libraries for it.

**Everything here is optional and the contrib never requires it.** Maritime runs, and its
chart draws, with nothing installed beyond Evennia. What this adds is the thing a printed
chart has and a line drawing does not: the *shape* of the bottom, shaded, so a bank reads
as a bank at a glance rather than as a contour a pilot has to interpret.

A host game that installs `numpy`, `scipy` and `Pillow` gets it. A host game that does not
gets exactly the interface it had, because `available()` answers False and the payload
carries no relief - the client draws what it is sent and never asks for more.

    the contours    what the survey recorded, drawn as lines
    the relief      the same soundings, shaded, so the shape is legible

**It is built from the charted seabed and never from the real one.** That is not a detail:
the whole panel exists on the rule that a graphical client must not make the navigator more
knowledgeable than the character. Relief drawn from the truth would be a picture of the
actual bottom sitting underneath a chart that disagrees with it, which is precisely the
knowledge a bad chart is supposed to deny. It is shaded from the grid the contours came
from - the same numbers, the same errors, the same holes.

**It costs almost nothing.** The grid has already been sounded to draw the contours, and
what happens here is arithmetic over a square of a few thousand numbers plus a small PNG.
The expensive part of a chart is asking the world for depths, and this asks for none.
"""

import base64
import io

try:  # pragma: no cover - depends on what the host game installed
    import numpy
    from PIL import Image
    from scipy import ndimage

    _MISSING = None
except ImportError as missing:  # pragma: no cover - the dependency-free path
    numpy = None
    Image = None
    ndimage = None
    _MISSING = missing

#: How much to blur the soundings before shading them, in grid cells.
#:
#: Generalisation, which is what a cartographer does when drawing at a smaller scale: the
#: shape of a bank matters and the exact wobble of one sounding does not. Small, because
#: this is meant to make the bottom legible rather than to invent a smooth one.
SMOOTHING = 1.2

#: Where the light comes from, as a compass bearing, and how high it stands. North-west and
#: fairly low, which is the convention on printed relief and the one that does not make
#: every reader see the hills as hollows.
LIGHT_BEARING = 315.0
LIGHT_HEIGHT = 45.0

#: How much to exaggerate the slope before shading. A shelf falls a metre or two in a
#: kilometre and would shade as a flat sheet at true scale; charts have always drawn the
#: sea bottom steeper than it is for the same reason.
RELIEF_EXAGGERATION = 60.0

#: The deepest water the ramp distinguishes, in metres. Below this it is all one blue.
DEEPEST = 60.0

#: How the water she cannot swim in is washed, and how strongly.
#:
#: A **safety contour**, which is what an electronic chart calls the line drawn at the
#: depth a particular hull needs, with everything shallower shaded. It is the one thing on
#: a chart that is different for every ship reading it, and it is the whole of "where do I
#: start being careful" in one colour.
#:
#: This adds no knowledge. The soundings already say three fathoms; what the wash says is
#: *three fathoms is not enough for you*, which is arithmetic the reader could have done
#: and, in a hurry, on a lee shore, would not have.
SHOAL_WASH = (206.0, 122.0, 96.0)
SHOAL_STRENGTH = 0.55


def available():
    """
    Returns:
        ready (bool): Whether this game can draw shaded relief.

    Notes:
        Asked rather than assumed at every call site, so the absence of a library is a
        quieter interface rather than a traceback.

    """
    return _MISSING is None


def why_not():
    """
    Returns:
        reason (str or None): What is missing, for a game that expected it to work.

    """
    if _MISSING is None:
        return None
    return (
        f"{_MISSING}. Shaded relief on the chart needs numpy, scipy and Pillow; "
        "maritime works without them and simply draws no relief."
    )


def _shade(depths, known, safe_depth=None):
    """
    Turn a square of charted elevations into a lit, coloured image.

    Args:
        depths (ndarray): Charted elevations, south row first.
        known (ndarray): True where somebody actually surveyed.
        safe_depth (float, optional): Metres of water this hull needs. Anything shallower
            is washed in the caution colour.

    Returns:
        pixels (ndarray): Height by width by four, RGBA.

    Notes:
        Unsurveyed water comes out fully transparent rather than as a colour. A chart
        stops at the edge of what its surveyor covered, and shading past that would be
        the picture claiming coverage the lines below it refuse to claim.

    """
    # Blur before shading. The holes are filled first with the mean of what is known, so
    # the blur does not drag the edge of the paper inwards - then masked out again.
    filled = numpy.where(known, depths, numpy.nanmean(depths[known]) if known.any() else 0.0)
    smooth = ndimage.gaussian_filter(filled, SMOOTHING, mode="nearest")

    east, north = numpy.gradient(smooth * RELIEF_EXAGGERATION)
    bearing = numpy.deg2rad(LIGHT_BEARING)
    height = numpy.deg2rad(LIGHT_HEIGHT)
    slope = numpy.arctan(numpy.hypot(east, north))
    aspect = numpy.arctan2(-east, north)
    lit = numpy.sin(height) * numpy.cos(slope) + numpy.cos(height) * numpy.sin(slope) * (
        numpy.cos(bearing - aspect)
    )
    lit = numpy.clip(lit, 0.0, 1.0)

    # Chart blue by depth, land in a paper buff, then lit.
    deep = numpy.clip(-smooth / DEEPEST, 0.0, 1.0)
    water = numpy.stack([214 - 150 * deep, 232 - 130 * deep, 245 - 80 * deep], axis=-1)
    ground = numpy.stack(
        [
            numpy.full(smooth.shape, 226.0),
            numpy.full(smooth.shape, 214.0),
            numpy.full(smooth.shape, 170.0),
        ],
        axis=-1,
    )
    colour = numpy.where((smooth >= 0.0)[..., None], ground, water)

    # The safety contour: wash whatever she cannot swim in.
    #
    # Faded in over the last metre rather than switched at a line, because a hard edge
    # invites a captain to steer along it, and the depth it is drawn from is a charted
    # one that is wrong by more than a metre in places. A wash that deepens as the water
    # shoals says "getting worse" instead of "safe until exactly here".
    if safe_depth:
        want = float(abs(safe_depth))
        # From the soundings themselves, never from the blurred copy.
        #
        # The blur exists to make the *shape* legible and it is happy to smooth a narrow
        # shoal into the deep water around it - which is exactly the shoal a captain needs
        # warning about. Keyed to the blurred grid, a three-metre patch three cells wide
        # came back reading fifteen metres and was not washed at all. The lighting may
        # generalise; the danger may not.
        under = numpy.clip((want - (-depths)) / max(want * 0.25, 1.0), 0.0, 1.0)
        under = numpy.where(depths >= 0.0, 0.0, under)
        under = numpy.where(known, under, 0.0) * SHOAL_STRENGTH
        wash = numpy.array(SHOAL_WASH)
        colour = colour * (1.0 - under[..., None]) + wash * under[..., None]

    shaded = colour * (0.55 + 0.75 * lit[..., None])
    pixels = numpy.zeros(smooth.shape + (4,), dtype=numpy.uint8)
    pixels[..., :3] = numpy.clip(shaded, 0, 255).astype(numpy.uint8)
    pixels[..., 3] = numpy.where(known, 255, 0).astype(numpy.uint8)
    return pixels


def shaded(grid, safe_depth=None):
    """
    A shaded-relief picture of a sounded grid, as a data URI.

    Args:
        grid (list): Rows of charted elevations, south to north, as `cartography.sample`
            returns them - unsurveyed places being None.
        safe_depth (float, optional): Metres of water the hull reading this needs. Water
            shallower than that is washed in the caution colour - the same chart shades
            differently for a kayak and for a laden brig, which is the point of it.

    Returns:
        image (str or None): A `data:image/png;base64,...` URI, or None if this game has
            no relief libraries, or if nothing on the sheet was surveyed.

    Notes:
        Rows are flipped on the way out. The grid runs south to north because that is how
        a chart is read; an image runs top to bottom because that is how an image is
        drawn, and getting it backwards puts the light on the wrong side of every bank.

    """
    if not available() or not grid:
        return None

    known = numpy.array(
        [[isinstance(v, (int, float)) and not isinstance(v, bool) for v in row] for row in grid]
    )
    if not known.any():
        return None

    depths = numpy.array(
        [
            [
                float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else 0.0
                for v in row
            ]
            for row in grid
        ]
    )

    pixels = _shade(depths, known, safe_depth)
    picture = Image.fromarray(numpy.flipud(pixels), mode="RGBA")
    out = io.BytesIO()
    picture.save(out, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(out.getvalue()).decode("ascii")
