"""
Where the shot struck her, and what came in through the hole.

Damage has been a number per track since phase 17 opened, and that was right for what it
answered: how much canvas she can still draw, how many guns will still serve. It cannot
answer the question a gun captain in this period actually asked, which was not *how much*
but *where* - because a hole in the bulwark is splinters and a hole three feet lower is a
ship going down.

**A hole is under water when it is lower than she is deep.** That is the whole of the
model, and it needs nothing new: `draft` already knows how deep she sits and already grows
with what is in her. So a laden ship drowns from a hole a light one shrugs off, and - the
part worth having - *a ship already making water settles onto her own wounds*. Holes that
were a foot clear go under, the inflow rises, and she settles further. Nobody wrote that
spiral; it falls out of measuring the hole against a draft that moves.

**Firing on the downroll is therefore a real decision.** Aim at her waterline and a hit is
worth several higher up, but the sea is moving her and a shot meant for the waterline goes
into the sea or into the bulwark. This module publishes where a hole is; what a gunner can
do about it belongs with the guns.

**Sections are three, not thirty.** Bow, waist and quarter - because those are the parts a
ship is steered, fought and floated by, and because a section is only worth having if
losing it means something distinct. A model with a hole in frame twenty-seven is a model
nobody can narrate.

"""

import math
from dataclasses import dataclass

from .events import Event, bus
from .results import Result

#: The three parts of her, forward to aft.
BOW = "bow"
WAIST = "waist"
QUARTER = "quarter"
SECTIONS = (BOW, WAIST, QUARTER)

#: How much of her length each section is.
#:
#: The waist is half of her because that is where she is widest, where her hold is, and
#: what most of a broadside meets. Bow and quarter take a quarter each.
SECTION_SHARES = {BOW: 0.25, WAIST: 0.5, QUARTER: 0.25}

#: What a ragged hole in a plank lets through, against a clean orifice.
#:
#: Six tenths. A shot hole is splintered and part-blocked by its own wreckage, which is why
#: the figure is not one - and it is the standard coefficient for a sharp-edged opening,
#: which a hole in a two-inch plank very nearly is.
DISCHARGE = 0.6

#: Metres per second per second.
GRAVITY = 9.81

#: How much of a hole a plug stops.
#:
#: Most, and never all. A carpenter drives a shot plug and a wad of oakum into a hole with
#: the sea coming through it, and what he gets is a weep instead of a jet.
PLUGGED = 0.85

NOT_A_SECTION = "not_a_section"
NO_SUCH_BREACH = "no_such_breach"
ALREADY_PLUGGED = "already_plugged"


@dataclass(frozen=True, kw_only=True)
class HullBreached(Event):
    """
    She has been holed.

    Attributes:
        vessel (object): The hull.
        section (str): Where.
        area (float): How big, in square metres.
        height (float): How far above her keel.
        under_water (bool): Whether the sea is coming in through it as she sits.

    Notes:
        Carries `under_water` as it was at the moment of the hit, which is a fact about
        *then* - she may settle onto it later, and a game that wants to know whether she is
        drowning now asks her rather than remembering this.

    """

    vessel: object
    section: str = ""
    area: float = 0.0
    height: float = 0.0
    under_water: bool = False


@dataclass(frozen=True)
class Breach:
    """
    A hole in her, somewhere.

    Attributes:
        section (str): Which of `SECTIONS` it is in.
        area (float): How big it is, in square metres.
        height (float): How far above her keel, in metres.
        plugged (bool): Whether the carpenter has got to it.

    Notes:
        Height is measured from the keel rather than from the waterline, and that is the
        decision the whole module turns on. A waterline is a thing that moves - she settles
        as she loads and settles further as she fills - so a hole recorded relative to it
        would silently rise as she sank, which is precisely backwards.

    """

    section: str
    area: float
    height: float
    plugged: bool = False


@dataclass(frozen=True, kw_only=True)
class BreachResult(Result):
    """
    What was done to a hole, or what the holes are doing to her.

    Attributes:
        breach (Breach): The one in question, if there is one.
        holes (tuple): All of them.
        under (int): How many are under water as she sits.
        inflow (float): Share of her buoyancy per minute coming in.

    """

    breach: Breach = None
    holes: tuple = ()
    under: int = 0
    inflow: float = 0.0


def section_struck(relative_bearing):
    """
    Which part of her a shot from this bearing goes into.

    Args:
        relative_bearing (float): Degrees from her head, 0 dead ahead.

    Returns:
        section (str): One of `SECTIONS`.

    Notes:
        Derived from the geometry that already exists rather than rolled. A ship raked from
        right astern is hit in the quarter, one crossed ahead in the bow, and one engaged
        broadside in the waist - which is both what happens and why crossing the T was worth
        the manoeuvring.

    """
    off = abs(float(relative_bearing)) % 360.0
    if off > 180.0:
        off = 360.0 - off
    if off <= 45.0:
        return BOW
    if off >= 135.0:
        return QUARTER
    return WAIST


def under_water(breach, draft):
    """
    Whether the sea is coming in through this one.

    Args:
        breach (Breach): The hole.
        draft (float): How deep she is sitting, in metres.

    Returns:
        under (bool): True if it is below the surface.

    """
    return float(breach.height) < float(draft)


def head_over(breach, draft):
    """
    How much water stands above a hole.

    Args:
        breach (Breach): The hole.
        draft (float): How deep she is sitting, in metres.

    Returns:
        head (float): Metres. Zero if it is clear of the water.

    """
    return max(0.0, float(draft) - float(breach.height))


def inflow_through(breach, draft, discharge=DISCHARGE):
    """
    How much water a single hole admits.

    Args:
        breach (Breach): The hole.
        draft (float): How deep she is sitting, in metres.
        discharge (float, optional): What a ragged hole lets through.

    Returns:
        inflow (float): Cubic metres a second.

    Notes:
        **The square root of the head**, which is Torricelli and is not an approximation
        chosen for convenience - it is what a hole in a tank does. What it buys the game is
        the right shape: a hole twice as deep admits only half again as much, so the
        difference between a hole at the waterline and one well under her is real without
        being absurd.

    """
    head = head_over(breach, draft)
    if head <= 0.0 or breach.area <= 0.0:
        return 0.0
    through = float(discharge) * float(breach.area) * math.sqrt(2.0 * GRAVITY * head)
    return through * (1.0 - PLUGGED) if breach.plugged else through


def buoyancy_share(cubic_metres_a_second, displacement):
    """
    What an inflow is worth as a share of her buoyancy.

    Args:
        cubic_metres_a_second (float): What is coming in.
        displacement (float): Her displacement in kilograms.

    Returns:
        share (float): Share of her buoyancy per minute.

    Notes:
        Converted here rather than at each call site so that the one place the two unit
        systems meet is a function with a name. Flooding counts in shares of buoyancy per
        minute; a hole in a plank counts in cubic metres a second; getting between them
        wrong is the kind of bug that reads as plausible for a long time.

    """
    if displacement <= 0.0:
        return 0.0
    from .cargo import SEAWATER_DENSITY

    hull_volume = float(displacement) / (SEAWATER_DENSITY * 1000.0)
    return (float(cubic_metres_a_second) * 60.0) / hull_volume if hull_volume > 0.0 else 0.0


class Sectioned:
    """
    A hull that can be holed in a particular place.

    Notes:
        Sits alongside `Damaged` rather than replacing it. The tracks answer what she can
        still *do*; the breaches answer whether she is still going to be here, and a game
        that wants only the first can ignore this entirely - a hull with no holes in her
        behaves exactly as she did before this module existed.

    """

    def at_object_creation(self):
        """Set up this part of a newly created vessel."""
        super().at_object_creation()
        self.db.breaches = []

    @property
    def breaches(self):
        """
        Returns:
            holes (tuple): Every hole in her.

        """
        return tuple(self.db.breaches or ())

    def hole(self, section, area, height):
        """
        Put a hole in her.

        Args:
            section (str): One of `SECTIONS`.
            area (float): How big, in square metres.
            height (float): How far above her keel, in metres.

        Returns:
            result (BreachResult): The hole, and what she is making now.

        """
        if section not in SECTIONS:
            return BreachResult(success=False, code=NOT_A_SECTION)

        made = Breach(section=section, area=max(0.0, float(area)), height=float(height))
        holes = list(self.db.breaches or ())
        holes.append(made)
        self.db.breaches = holes

        self._announce_breach(made)
        return BreachResult(
            success=True,
            breach=made,
            holes=self.breaches,
            under=len(self.holed_below()),
            inflow=self.breach_inflow(),
        )

    def holed_below(self):
        """
        Returns:
            holes (tuple): The ones the sea is coming in through, as she sits.

        Notes:
            Recomputed on every asking rather than stored, because the answer changes
            without anybody touching the holes: she loads, she makes water, she settles, and
            a hole that was clear this morning is under this afternoon.

        """
        draft = self.draft
        return tuple(hole for hole in self.breaches if under_water(hole, draft))

    def breach_inflow(self):
        """
        Returns:
            inflow (float): Share of her buoyancy per minute coming in through her holes.

        """
        draft = self.draft
        through = sum(inflow_through(hole, draft) for hole in self.breaches)
        return buoyancy_share(through, self.capacity.displacement)

    def plug(self, breach):
        """
        Get a shot plug into a hole.

        Args:
            breach (Breach): Which one.

        Returns:
            result (BreachResult): What is left of it.

        Notes:
            The carpenter's job, and the one worth doing first is not the biggest hole - it
            is the deepest, because the head over it is what drives the inflow. Nothing here
            chooses for him.

        """
        holes = list(self.breaches)
        if breach not in holes:
            return BreachResult(success=False, code=NO_SUCH_BREACH)
        if breach.plugged:
            return BreachResult(success=False, code=ALREADY_PLUGGED, breach=breach)

        stopped = Breach(
            section=breach.section, area=breach.area, height=breach.height, plugged=True
        )
        holes[holes.index(breach)] = stopped
        self.db.breaches = holes
        return BreachResult(
            success=True,
            breach=stopped,
            holes=self.breaches,
            under=len(self.holed_below()),
            inflow=self.breach_inflow(),
        )

    def _announce_breach(self, breach):
        """
        Say that she has been holed.

        Args:
            breach (Breach): The new hole.

        """
        bus().publish(
            HullBreached(
                game_time=self._breach_now(),
                vessel=self,
                section=breach.section,
                area=breach.area,
                height=breach.height,
                under_water=under_water(breach, self.draft),
            )
        )

    def _breach_now(self):
        """
        Returns:
            now (float): Game time in seconds.

        """
        from . import config

        return config.time_provider().now()
