"""
What happens when a hull finds the bottom.

Grounding is not a special case bolted onto movement. It is terrain intersecting the
vessel's own envelope, which falls straight out of the elevation model:

    surface     the water, wherever the tide has put it
    keel        the surface less her draft
    ground      the terrain beneath her

    clearance = keel - ground

Negative clearance means the hull is occupying the same space as the seabed, which is the
whole of it. Nothing here needs to know about shoals or reefs as concepts - the terrain
is already the right shape, and a vessel drawing two metres finds the bottom in one and a
half metres of water without anyone having drawn a line on a chart.

**Clearance is a continuous value, not a yes-or-no.** That matters more than the grounding
itself. Knowing you have four metres under the keel and losing a metre every mile is what
lets a navigator make a decision; discovering you have run aground does not. The number is
what soundings report and what a pilot reasons about.

This samples the vessel's centre point. A real implementation samples a hull footprint -
bow, stern, and both quarters - and sweeps that footprint along the track, so a hull cannot
step over a reef narrower than one tick of movement. That refinement waits for the water
column phase; the interface here does not change when it lands.

"""

from dataclasses import dataclass

from .bathymetry import FOUL_GROUND, UNKNOWN
from .results import Result

# Severity of a contact with the ground, in increasing order of regret.
TOUCHED = "touched"
AGROUND = "aground"
HOLED = "holed"

# Clearance in metres below which a vessel is close enough that a leadsman would
# be calling it and an officer should be worrying.
SHOAL_WARNING_CLEARANCE = 3.0

# Speed in metres per second above which finding foul ground opens the hull rather
# than merely stopping her. Slow enough to be a real threshold, fast enough that a
# careful approach is genuinely safer.
HOLING_SPEED = 1.5


@dataclass(frozen=True, kw_only=True)
class GroundingResult(Result):
    """
    What came of a hull meeting the ground.

    Attributes:
        clearance (float): Metres between keel and ground. Negative means she is
            in it.
        bottom (str): What the ground is made of.
        speed (float): Speed at the moment of contact, in metres per second.
        severity (str): `TOUCHED`, `AGROUND` or `HOLED`.

    Notes:
        A successful result means she is clear, with `clearance` reporting by how
        much. A failed one means she found the bottom, and the code says how
        badly.

    """

    clearance: float = 0.0
    bottom: str = UNKNOWN
    speed: float = 0.0
    severity: str = ""


def keel_clearance(position, draft, map_provider, game_time):
    """
    How much water there is under the keel.

    Args:
        position (WorldPosition): Where the vessel is.
        draft (float): How deep she sits, in metres.
        map_provider (MaritimeMapProvider): The world's terrain.
        game_time (float): Game time in seconds, since the tide moves the surface.

    Returns:
        clearance (float): Metres between keel and ground. Negative means the hull
            is in the ground.

    Notes:
        Takes a game time for the same reason depth queries do: the tide decides
        where the surface is, and a clearance measured against the datum is a
        different number from the one that will actually run her aground.

    """
    surface = map_provider.sea_surface_z_at(position, game_time)
    ground = map_provider.terrain_z_at(position)
    return (surface - float(draft)) - ground


def is_shoaling(position, draft, map_provider, game_time, warning=SHOAL_WARNING_CLEARANCE):
    """
    Whether the water is shallow enough to be worth reporting.

    Args:
        position (WorldPosition): Where the vessel is.
        draft (float): How deep she sits, in metres.
        map_provider (MaritimeMapProvider): The world's terrain.
        game_time (float): Game time in seconds.
        warning (float, optional): Clearance in metres below which to warn.

    Returns:
        shoaling (bool): True if she is standing into shallow water.

    Notes:
        The warning is the point. A vessel that grounds without warning is an
        accident; one that grounds after the leadsman has called diminishing
        water is a decision, and only the second is interesting.

    """
    return keel_clearance(position, draft, map_provider, game_time) < warning


def check_grounding(position, draft, speed, map_provider, game_time):
    """
    Test a vessel against the ground beneath her.

    Args:
        position (WorldPosition): Where she is.
        draft (float): How deep she sits, in metres.
        speed (float): How fast she is going, in metres per second.
        map_provider (MaritimeMapProvider): The world's terrain.
        game_time (float): Game time in seconds.

    Returns:
        result (GroundingResult): Successful if she is clear, failed if she is
            not, carrying the clearance either way.

    Notes:
        Severity depends on what she hit and how fast. Mud and sand hold a hull
        and usually give her back on the next tide; reef and rock struck with way
        on open her. That distinction is why bottom type is worth modelling at
        all - otherwise every grounding is the same event.

    """
    clearance = keel_clearance(position, draft, map_provider, game_time)
    bottom = map_provider.bottom_type_at(position)

    if clearance > 0.0:
        return GroundingResult.ok(clearance=clearance, bottom=bottom, speed=speed)

    if bottom in FOUL_GROUND and speed > HOLING_SPEED:
        severity = HOLED
    elif speed > HOLING_SPEED:
        severity = AGROUND
    else:
        severity = TOUCHED

    return GroundingResult.failed(
        severity, clearance=clearance, bottom=bottom, speed=speed, severity=severity
    )


def refloats_on_tide(result):
    """
    Whether a rising tide alone would lift her off.

    Args:
        result (GroundingResult): The grounding that put her there.

    Returns:
        refloats (bool): True if she is merely held and not damaged.

    Notes:
        The classic way off a soft grounding, and it only works because tide and
        terrain share one model - the water rises, the seabed does not, and the
        clearance that was negative becomes positive without anything else
        changing.

    """
    return result.severity != HOLED and result.bottom not in FOUL_GROUND
