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
from .position import WorldPosition
from .results import Result
from .spatial import track_entry

# Severity of a contact with the ground, in increasing order of regret.
TOUCHED = "touched"
AGROUND = "aground"
HOLED = "holed"

# Clearance in metres below which a vessel is close enough that a leadsman would
# be calling it and an officer should be worrying.
SHOAL_WARNING_CLEARANCE = 3.0

# Speed in metres per second above which a contact is more than a touch.
#
# Two metres a second is about four knots. Below it she has *taken the ground* - which is
# a thing ships did on purpose, every time they were careened, beached to work on the
# bottom, or laid on a hard to load a cargo at low water. It is not an accident and it
# should not read as one.
TOUCHING_SPEED = 2.0

# And the speed above which foul ground opens the hull rather than merely stopping her.
#
# Four metres a second, or about eight knots - a ship with real way on. This was one and a
# half, which is under three knots, and it was much too low: it meant every grounding at
# any speed anybody actually sails at was a holing, and a hull that touched a rock while
# ghosting along under a reefed topsail was lost. A grounding should be a bad afternoon;
# only a reckless one should be the end of the ship.
#
# Only foul ground holes her at all, at any speed - see `severity_of`. Sand and mud hold a
# hull and give her back on the tide, which is why bottom type is worth modelling.
HOLING_SPEED = 4.0


@dataclass(frozen=True, kw_only=True)
class GroundingResult(Result):
    """
    What came of a hull meeting the ground.

    Attributes:
        clearance (float): Metres between keel and ground. Negative means she is
            in it.
        depth (float): Metres of water from surface to ground. What a lead line
            finds, and not the same question as clearance - the leadsman knows
            nothing about the draft of the ship he is standing on.
        bottom (str): What the ground is made of.
        speed (float): Speed at the moment of contact, in metres per second.
        severity (str): `TOUCHED`, `AGROUND` or `HOLED`.
        position (WorldPosition or None): Where along her track this was found.
            Set by the swept test, which stops her where she struck rather than
            where she was heading.

    Notes:
        A successful result means she is clear, with `clearance` reporting by how
        much. A failed one means she found the bottom, and the code says how
        badly.

    """

    clearance: float = 0.0
    depth: float = 0.0
    bottom: str = UNKNOWN
    speed: float = 0.0
    severity: str = ""
    position: object = None


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


def severity_of(speed, bottom):
    """
    How bad a contact with this ground at this speed is.

    Args:
        speed (float): How fast she was going, in metres per second.
        bottom (str): What she found.

    Returns:
        severity (str): `TOUCHED`, `AGROUND` or `HOLED`.

    Notes:
        Mud and sand hold a hull and usually give her back on the next tide; reef
        and rock struck with way on open her. That distinction is why bottom type
        is worth modelling at all - otherwise every grounding is the same event.

        **Two thresholds, not one.** They were the same number, so the speed that turned a
        touch into a grounding was also the speed that turned a grounding into a wreck -
        which made every contact above three knots catastrophic and every one below it
        trivial, with nothing in between. Taking the ground gently, being hard on and
        waiting for the tide, and being opened on a reef are three different afternoons.

        Extracted so that terrain and authored hazards answer the same way. Two
        copies of this would drift, and the symptom would be a rock that holes
        her when she is sampled onto it and merely holds her when she is caught
        by the corridor test.

    """
    if bottom in FOUL_GROUND and speed > HOLING_SPEED:
        return HOLED
    if speed > TOUCHING_SPEED:
        return AGROUND
    return TOUCHED


def check_hazards(before, after, draft, speed, beam, map_provider, game_time):
    """
    Test the authored hazards along a track, exactly rather than by sampling.

    Args:
        before (WorldPosition): Where she started the step.
        after (WorldPosition): Where she is proposing to end it.
        draft (float): How deep she sits, in metres.
        speed (float): How fast she is going, in metres per second.
        beam (float): Her beam, in metres.
        map_provider (MaritimeMapProvider): The world's terrain.
        game_time (float): Game time in seconds.

    Returns:
        result (GroundingResult or None): The first hazard she cannot clear, or
            None if the track is free of them.

    Notes:
        She is stopped where she *enters* the hazard rather than where she passes
        closest to it. Closest approach is on the far side of a rock she has by
        then sailed through, which is a strange thing to show a player.

        Providers with no authored hazards return nothing from
        `hazards_touching`, so this costs an empty loop and is worth running
        unconditionally.

    """
    half_beam = max(0.0, beam) / 2.0
    for hazard in map_provider.hazards_touching(before, after, beam):
        centre = WorldPosition(x=hazard.x, y=hazard.y, z=0.0, region=hazard.region)
        struck = track_entry(centre, before, after, hazard.radius + half_beam)
        if struck is None:
            continue
        surface = map_provider.sea_surface_z_at(struck, game_time)
        clearance = (surface - float(draft)) - hazard.top_z
        if clearance > 0.0:
            continue
        severity = severity_of(speed, hazard.bottom)
        return GroundingResult.failed(
            severity,
            clearance=clearance,
            depth=clearance + float(draft),
            bottom=hazard.bottom,
            speed=speed,
            severity=severity,
            position=struck,
        )
    return None


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
    depth = clearance + float(draft)
    bottom = map_provider.bottom_type_at(position)

    if clearance > 0.0:
        return GroundingResult.ok(clearance=clearance, depth=depth, bottom=bottom, speed=speed)

    severity = severity_of(speed, bottom)
    return GroundingResult.failed(
        severity,
        clearance=clearance,
        depth=depth,
        bottom=bottom,
        speed=speed,
        severity=severity,
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
    return held_not_holed(result.severity, result.bottom)


def held_not_holed(severity, bottom):
    """
    Whether a grounding was the kind a tide can undo.

    Args:
        severity (str): One of the severities in this module.
        bottom (str): What she is sitting on.

    Returns:
        soft (bool): True if she is merely held.

    Notes:
        Split out of `refloats_on_tide` so the same question can be asked of a grounding
        that was recorded rather than one that has just happened. A vessel keeps the two
        facts on her - see `Vessel.floats_off` - and reconstructing a whole result object
        from them only to ask one predicate of it would be ceremony, while writing the
        predicate out a second time is how the two answers come to disagree.

    """
    return severity != HOLED and bottom not in FOUL_GROUND


# Sample points on a hull, as fractions of half-length along her and half-beam
# across her. A pointed bow and a single stern point rather than a rectangle's
# four corners, because a rectangle puts steel where a ship has none and would
# ground her on water she is not actually over.
HULL_OUTLINE = (
    (0.0, 0.0),  # amidships
    (1.0, 0.0),  # bow
    (0.6, 1.0),  # starboard bow
    (0.6, -1.0),  # port bow
    (-0.6, 1.0),  # starboard quarter
    (-0.6, -1.0),  # port quarter
    (-1.0, 0.0),  # stern
)

# How far apart to test along a track, as a fraction of the vessel's length.
# Below one, consecutive footprints overlap, so nothing longer than the gap can
# pass between two samples untested.
SWEEP_OVERLAP = 0.5

# Shortest step to take along a track, in metres, whatever the hull's length.
# Stops an unmeasured or very small vessel asking for an unbounded number of
# samples across a long run.
MIN_SWEEP_STEP = 2.0


def hull_points(position, heading, length, beam):
    """
    The points on a hull worth testing against the ground.

    Args:
        position (WorldPosition): Where her centre is.
        heading (float): Which way she is pointing, in degrees.
        length (float): Her length, in metres.
        beam (float): Her beam, in metres.

    Returns:
        points (tuple): `WorldPosition` objects, amidships first.

    Notes:
        A hull is not a point, and testing her centre alone says a ship is safe
        while her bow is over a reef. Seven points in a rough ship shape - a
        single bow, quarters at the widest part, a single stern.

        A vessel with no dimensions returns her centre only. That is deliberate:
        a game that has not measured its hulls gets the old behaviour rather than
        a hull of size zero or an error.

    """
    if length <= 0.0 or beam <= 0.0:
        return (position,)

    half_length, half_beam = length / 2.0, beam / 2.0
    points = []
    for along, across in HULL_OUTLINE:
        forward = position.moved(heading, along * half_length)
        points.append(forward.moved(heading + 90.0, across * half_beam))
    return tuple(points)


def sweep_positions(before, after, length):
    """
    Centre positions to test along a track.

    Args:
        before (WorldPosition): Where she started the step.
        after (WorldPosition): Where she is proposing to end it.
        length (float): Her length, in metres.

    Returns:
        positions (tuple): Centres from just after the start through to the end.

    Notes:
        The reason this exists at all: a vessel tested only where she ends up can
        step clean over a shoal narrower than one tick of her movement, and the
        faster she goes the more of the seabed she is entitled to ignore - which
        is precisely backwards, since speed is what makes grounding expensive.

        Steps overlap by construction, so nothing longer than half her length can
        lie between two consecutive tests untouched. Something smaller than the
        gaps *within* the outline can still slip between her sample points; that
        is a real limit of sampling a shape with seven points rather than a flaw
        in the sweep.

    """
    travelled = before.horizontal_distance_to(after)
    step = max(length * SWEEP_OVERLAP, MIN_SWEEP_STEP)
    if travelled <= step:
        return (after,)

    bearing = before.bearing_to(after)
    count = int(travelled / step)
    positions = [before.moved(bearing, step * index) for index in range(1, count + 1)]
    positions.append(after)
    return tuple(positions)


def check_swept_grounding(
    before, after, heading, draft, speed, length, beam, map_provider, game_time
):
    """
    Test a hull along her whole track, not only where she ends up.

    Args:
        before (WorldPosition): Where she started the step.
        after (WorldPosition): Where propulsion and the water would put her.
        heading (float): Which way she is pointing, in degrees.
        draft (float): How deep she sits, in metres.
        speed (float): How fast she is going, in metres per second.
        length (float): Her length, in metres.
        beam (float): Her beam, in metres.
        map_provider (MaritimeMapProvider): The world's terrain.
        game_time (float): Game time in seconds.

    Returns:
        result (GroundingResult): Successful if she is clear the whole way, and
            failed at the first contact if she is not. `position` is where she
            actually got to.

    Notes:
        Stops her at the first thing she touches rather than at the end of the
        step. A ship that struck a reef a third of the way through a tick did not
        also travel the other two thirds, and putting her at the far end of the
        move before declaring her aground would leave her sitting somewhere she
        never reached.

        The clearance reported is the least found anywhere on the hull, so a
        vessel whose bow is in three metres and whose stern is in twelve reports
        three - which is the number that decides anything.

    """
    # The authored hazards first, and exactly. Anything a game has drawn as a
    # rock is tested against the whole corridor she swept, so it cannot fall into
    # the gaps between her seven outline points.
    struck = check_hazards(before, after, draft, speed, beam, map_provider, game_time)
    if struck is not None:
        return struck

    thinnest = None
    for centre in sweep_positions(before, after, length):
        for point in hull_points(centre, heading, length, beam):
            contact = check_grounding(point, draft, speed, map_provider, game_time)
            if not contact:
                return GroundingResult.failed(
                    contact.severity,
                    clearance=contact.clearance,
                    depth=contact.depth,
                    bottom=contact.bottom,
                    speed=speed,
                    severity=contact.severity,
                    position=centre,
                )
            if thinnest is None or contact.clearance < thinnest.clearance:
                thinnest = contact

    # Clear the whole way, so she is where she was going. The clearance reported
    # is the least found anywhere along it - that is the number a shoal warning
    # is about - but the *position* is the end of the run and never the shallow
    # spot she passed over, or a ship would be dragged back to the thinnest water
    # she crossed.
    if thinnest is None:
        return GroundingResult.ok(position=after)
    return GroundingResult.ok(
        clearance=thinnest.clearance,
        depth=thinnest.depth,
        bottom=thinnest.bottom,
        speed=speed,
        position=after,
    )
