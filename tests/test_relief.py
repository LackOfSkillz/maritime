"""
Tests for the shaded relief, and for the promise that nothing needs it.

Two halves, and the second matters more. The first checks that a game which installed
numpy, scipy and Pillow gets a picture worth having. The second checks that a game which
installed none of them gets the interface it always had - no traceback, no empty box, no
half-drawn anything, just a chart without shading on it.

That second half cannot be exercised here when the libraries *are* present, so it is
tested against the seam rather than the environment: the payload field is optional, the
call answers None rather than raising, and the client is asked to draw only what it was
sent.
"""

import base64
import unittest

from evennia.utils.test_resources import BaseEvenniaTestCase

from ..client import relief
from ..client.payloads import ChartSheet

#: A square of sea with a bank in the middle of it, south row first.
BANK = [
    [-30.0, -30.0, -30.0, -30.0, -30.0],
    [-30.0, -20.0, -18.0, -20.0, -30.0],
    [-30.0, -18.0, -4.0, -18.0, -30.0],
    [-30.0, -20.0, -18.0, -20.0, -30.0],
    [-30.0, -30.0, -30.0, -30.0, -30.0],
]


def a_png(uri):
    """
    Returns:
        raw (bytes): The decoded picture behind a data URI.

    """
    return base64.b64decode(uri.split(",", 1)[1])


class TestTheSeamHoldsWithoutIt(BaseEvenniaTestCase):
    """
    The half that matters. A game with none of the libraries has a working chart.
    """

    def test_the_module_imports_whatever_is_installed(self):
        """
        It is imported unconditionally by the state builder, so failing to import would
        take the whole chart down rather than just the shading.

        """
        self.assertIn(relief.available(), (True, False))

    def test_a_sheet_carries_no_relief_by_default(self):
        self.assertEqual(ChartSheet().relief, "")
        self.assertEqual(ChartSheet().as_message()["relief"], "")

    def test_an_empty_grid_asks_for_nothing(self):
        self.assertIsNone(relief.shaded([]))

    def test_a_wholly_unsurveyed_square_draws_nothing(self):
        """Off the paper there is nothing to shade, and shading it would invent coverage."""
        self.assertIsNone(relief.shaded([[None] * 4 for _ in range(4)]))

    def test_it_says_why_when_it_cannot(self):
        """
        A game that expected shading and is not getting it deserves a sentence rather
        than silence.

        """
        if relief.available():
            self.assertIsNone(relief.why_not())
        else:
            self.assertIn("numpy", relief.why_not())


@unittest.skipUnless(relief.available(), "needs numpy, scipy and Pillow")
class TestWhatItDrawsWhenItCan(BaseEvenniaTestCase):
    """A game that installed the libraries gets a picture of the bottom."""

    def test_it_comes_back_as_a_data_uri(self):
        uri = relief.shaded(BANK)
        self.assertTrue(uri.startswith("data:image/png;base64,"))

    def test_and_it_is_a_png_of_the_right_size(self):
        import io

        from PIL import Image

        picture = Image.open(io.BytesIO(a_png(relief.shaded(BANK))))
        self.assertEqual(picture.size, (len(BANK[0]), len(BANK)))
        self.assertEqual(picture.mode, "RGBA")

    def test_unsurveyed_water_is_transparent_rather_than_a_colour(self):
        """
        A chart stops at the edge of what its surveyor covered. Shading past that would
        have the picture claim coverage the lines refuse to.

        """
        import io

        from PIL import Image

        holed = [row[:] for row in BANK]
        holed[0][0] = None
        picture = Image.open(io.BytesIO(a_png(relief.shaded(holed))))
        # Row 0 is the *south* row, which is the bottom of the image.
        self.assertEqual(picture.getpixel((0, picture.size[1] - 1))[3], 0)
        self.assertEqual(picture.getpixel((2, picture.size[1] - 3))[3], 255)

    def test_north_is_at_the_top(self):
        """
        The grid runs south to north because that is how a chart is read; an image runs
        top to bottom because that is how an image is drawn. Getting the flip wrong puts
        the light on the wrong side of every bank and mirrors the coast.

        """
        import io

        from PIL import Image

        # Land along the north edge only.
        sloping = [[-30.0] * 5 for _ in range(4)] + [[20.0] * 5]
        picture = Image.open(io.BytesIO(a_png(relief.shaded(sloping))))
        top = picture.getpixel((2, 0))
        bottom = picture.getpixel((2, picture.size[1] - 1))
        # Land is drawn in a paper buff, water in blue: the land pixel is the redder one.
        self.assertGreater(top[0] - top[2], bottom[0] - bottom[2])

    def test_land_and_water_do_not_look_alike(self):
        import io

        from PIL import Image

        picture = Image.open(io.BytesIO(a_png(relief.shaded([[-40.0, 20.0], [-40.0, 20.0]]))))
        water = picture.getpixel((0, 0))
        ground = picture.getpixel((1, 0))
        self.assertNotEqual(water[:3], ground[:3])

    def test_a_bank_is_lit_differently_from_the_water_round_it(self):
        """
        The whole point of shading: a bank should read as a shape rather than as a patch
        of a slightly different blue.

        """
        import io

        from PIL import Image

        picture = Image.open(io.BytesIO(a_png(relief.shaded(BANK))))
        crest = picture.getpixel((2, 2))
        flat = picture.getpixel((0, 0))
        self.assertNotEqual(crest[:3], flat[:3])

    def test_it_is_the_same_picture_every_time(self):
        """
        A chart is wrong in the same places every voyage, and its shading has to be as
        steady as its lines - a relief that shimmered between redraws would undo that.

        """
        self.assertEqual(relief.shaded(BANK), relief.shaded(BANK))

    def test_a_grid_with_a_hole_in_it_still_draws(self):
        holed = [row[:] for row in BANK]
        holed[2][2] = None
        self.assertTrue(relief.shaded(holed))


#: A wider shoal, for the safety contour.
#:
#: `BANK` is five cells across and the soundings are generalised before they are lit, so a
#: one-cell crest is blurred away to nothing and a wash keyed to its depth finds nothing to
#: wash. That is the blur behaving correctly and a test grid too small to test with.
SHOAL = (
    [[-40.0] * 9 for _ in range(3)]
    + [[-40.0, -40.0, -18.0, -8.0, -3.0, -8.0, -18.0, -40.0, -40.0] for _ in range(3)]
    + [[-40.0] * 9 for _ in range(3)]
)


class TestTheSafetyContour(BaseEvenniaTestCase):
    """
    The one thing on a chart that is different for every ship reading it.

    An electronic chart calls it the safety contour: the line at the depth a particular
    hull needs, with everything shallower shaded. It adds no knowledge - the soundings
    already said three fathoms - but it says *three fathoms is not enough for you*, which
    is arithmetic the reader could have done and, on a lee shore in a hurry, would not.
    """

    def test_a_hull_asks_for_its_draught_and_the_grounding_margin(self):
        """
        One idea, one number. If the wash on the paper and the warning on the instruments
        disagreed about what shoal water is, the interface would be telling a captain two
        different stories at once.

        """
        from ..client.state import _safe_water_for
        from ..grounding import SHOAL_WARNING_CLEARANCE

        class Hull:
            draft = 2.0

        self.assertAlmostEqual(_safe_water_for(Hull()), 2.0 + SHOAL_WARNING_CLEARANCE)

    def test_a_hull_that_draws_nothing_gets_no_contour(self):
        from ..client.state import _safe_water_for

        class Raft:
            draft = 0.0

        self.assertIsNone(_safe_water_for(Raft()))

    def test_the_same_hull_loaded_wants_more_water(self):
        """
        Weight-aware without a line of chart code knowing about cargo: `draft` is derived
        from the light draught and what is in the holds, so the contour follows the
        manifest. A stored draught would be a second source of truth, and the symptom
        would be a laden ship shaded as though she were empty.

        """
        from ..cargo import laden_draft
        from ..client.state import _safe_water_for

        class Hull:
            def __init__(self, tonnes):
                self.draft = laden_draft(2.0, tonnes * 1000.0, 1.8)

        light = _safe_water_for(Hull(0))
        laden = _safe_water_for(Hull(90))
        self.assertGreater(laden, light + 0.4)


@unittest.skipUnless(relief.available(), "needs numpy, scipy and Pillow")
class TestWhatTheSafetyContourDraws(BaseEvenniaTestCase):
    def picture(self, safe):
        import io

        from PIL import Image

        return Image.open(io.BytesIO(a_png(relief.shaded(SHOAL, safe))))

    def test_shoal_water_is_washed_and_deep_water_is_not(self):
        plain = self.picture(None)
        washed = self.picture(12.0)
        crest = (4, 4)
        # The crest carries 3 m of water, well inside a 12 m contour.
        self.assertNotEqual(plain.getpixel(crest)[:3], washed.getpixel(crest)[:3])
        # The 40 m corner is outside it and should be untouched.
        self.assertEqual(plain.getpixel((0, 0))[:3], washed.getpixel((0, 0))[:3])

    def test_a_deeper_hull_is_warned_about_more_water(self):
        """
        The point of it: the same chart shades differently for a kayak and a laden brig.

        Counted over the whole square rather than sampled at one pixel. The first version
        picked a cell it believed was in twenty metres and asserted about it, which is
        asserting about the blur as much as the wash - the soundings are generalised
        before they are lit, so no single pixel holds the depth the grid was given.

        """
        plain = self.picture(None)
        shallow = self.picture(6.0)
        deep = self.picture(25.0)

        def washed(against):
            return sum(
                1
                for x in range(plain.size[0])
                for y in range(plain.size[1])
                if plain.getpixel((x, y))[:3] != against.getpixel((x, y))[:3]
            )

        self.assertGreater(washed(shallow), 0, "a shallow hull was warned about nothing")
        self.assertGreater(
            washed(deep),
            washed(shallow),
            "a deeper hull was not warned about more water than a shallower one",
        )

    def test_land_is_not_washed_as_though_it_were_shoal_water(self):
        """Dry land is already drawn as land; washing it would say nothing and cost the
        one colour that means danger."""
        ashore = [[20.0, 20.0], [20.0, 20.0]]
        import io

        from PIL import Image

        plain = Image.open(io.BytesIO(a_png(relief.shaded(ashore))))
        washed = Image.open(io.BytesIO(a_png(relief.shaded(ashore, 25.0))))
        self.assertEqual(plain.getpixel((0, 0))[:3], washed.getpixel((0, 0))[:3])
