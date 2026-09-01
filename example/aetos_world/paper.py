"""
The chart of this coast, and getting one aboard.

A ship with no chart draws an empty sheet - rings, a compass rose and her own head, and no
sea at all. That is the right answer to "what does the paper say" when there is no paper,
and it is documented as such; it is also what every vessel in this world was doing, because
nothing had ever put a chart aboard one. The whole charted layer was invisible and looked
like a bug in the drawing.

**One sheet, covering the town and the chain.** Real coverage is ragged and a game that
wants ragged supplies several charts; this coast is small enough that one sheet is the
truth, and pretending otherwise would be detail for its own sake.

**Not a perfect one.** A chart is a *record* of the sea and the whole navigation model turns
on the difference: quality decides how far the drawn coast is from the real one, which is
why a careful sailor still sounds his way in. A demo world that shipped a quality-1.0 chart
would draw the ground exactly and quietly delete the reason `sound` exists.

Quality here is 0.86 - a good chart, a generation old, made by somebody competent. Off by a
metre or two of depth, which on this shelving coast is a hundred metres of shoreline: enough
that a pilot learns where his paper lies, not enough to lose a ship over.
"""

from ...charts import Chart

#: What the sheet is called, and who made it.
#:
#: A chart carries its surveyor's name because that is what a navigator judges it by. "The
#: Aetos survey" is a thing a captain can come to trust or distrust, and "chart" is not.
SHEET = "Chart of the Aetos Coast"
SURVEYOR = "Vessin, master of the Endeavour"

#: What it covers, in metres.
#:
#: The town at the eastern edge, the island chain up the western side, and the fairway
#: between them - with a margin all round so that a ship standing off the chain is still on
#: the paper rather than sailing off the edge of it a mile from her destination.
WEST = -6000.0
EAST = 4500.0
SOUTH = -3000.0
NORTH = 12500.0

#: How good it is, from 0 to 1. See the module docstring: this is the number that decides
#: whether navigation is a skill or a formality.
QUALITY = 0.86

#: What fixes where it is wrong.
#:
#: A constant, so the same chart is wrong in the same places for everybody and stays wrong
#: there between reloads. A survey error that moved would be unlearnable, which is the whole
#: argument in `charts._sounding_error`.
SEED = 20260901


def coast_chart(region="default", surveyed_at=0.0):
    """
    The sheet this world sails on.

    Args:
        region (str, optional): Which coordinate space it covers.
        surveyed_at (float, optional): When it was made, in game seconds.

    Returns:
        chart (Chart): One sheet of the whole coast.

    Notes:
        Surveyed at the beginning of time by default, which is deliberate: `quality_at`
        decays a survey with age, so a chart stamped at zero is an *old* chart and reads a
        little worse every year the game runs. That is the right shape for a world with one
        survey in it, and a game that wants fresh paper stamps it with the present.

    """
    return Chart(
        key=SHEET,
        region=region,
        west=WEST,
        east=EAST,
        south=SOUTH,
        north=NORTH,
        quality=QUALITY,
        surveyed_at=surveyed_at,
        seed=SEED,
        maker=SURVEYOR,
    )


def put_aboard(vessel, region=None):
    """
    Give a hull the chart of the coast she is on, if she has not got it.

    Args:
        vessel (Vessel): The hull.
        region (str, optional): Which coordinate space. Taken from where she is floating
            if omitted.

    Returns:
        given (bool): Whether a chart was added.

    Notes:
        Idempotent, because `add_chart` refuses a duplicate name by raising and a builder
        command that fell over the second time it was run would be a builder command nobody
        ran twice.

        A ship is not born with a chart in this contrib and should not be - a hull is a
        hull. But a ship *bought at a quay* comes with the local sheet, because that is what
        happens: the yard hands you one, and a shipwright who sold a stranger a vessel and
        no way of finding his way out of the harbour would not sell many.

    """
    if any(chart.key == SHEET for chart in vessel.charts):
        return False
    here = vessel.maritime_position
    vessel.add_chart(coast_chart(region or (here.region if here else "default")))
    return True


__all__ = (
    "SHEET",
    "SURVEYOR",
    "WEST",
    "EAST",
    "SOUTH",
    "NORTH",
    "QUALITY",
    "SEED",
    "coast_chart",
    "put_aboard",
)
