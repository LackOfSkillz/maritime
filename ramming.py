"""
Running one hull into another, and running down her oars.

Two acts that read the same geometry the rest of the tactical code already reads, and turn
it into damage on both ships rather than one.

**The rammer takes it too.** That is the whole reason this is a decision rather than a free
attack. A hull driven into another hull is being asked to survive the same collision it is
delivering, and the only things that change the split are the angle it lands at and what is
fitted to her bow. Bow to bow is bad for both. A blow on the beam is devastating for the
ship that receives it and comparatively cheap for the ship that gives it, which is why
crossing an enemy's course is worth the trouble of getting there.

**Energy, not a table.** `impact_energy` is one half m vee squared, where the mass is her
displacement and the speed is the closing speed along the line between the two hulls, both
of which the simulation already knows. Nothing here is tuned per ship class: a heavy ship
hurts more because she weighs more, and a fast one because the speed is squared. The
constants below convert joules into the damage weights the rest of the game speaks, and are
the only tuning in the file.

**Sheering** is the other half, and is oar work. Running down an enemy's side shears off the
looms she has out, and how much of her side you ran down decides how many. She fights back
while you do it - the oars break against your hull as well as hers - which is weaker than
what she is losing but is not nothing. `oars.OarPlan` already says whether there is anything
out there to break, so a ship under sail alone cannot be sheered and nothing here has to be
told so.

Pure geometry and arithmetic. Nothing in this module knows what an Evennia object is; the
typeclass layer reads these results and applies them.
"""

import math
from dataclasses import dataclass

from .damage import resilience
from .results import Result

#: What is fitted to her bow.
#:
#: `PLAIN` is an ordinary stem: it hurts, because tonnage at speed always does, and it hurts
#: the ship delivering it nearly as much. `SPUR` is a beak built to bite above the waterline
#: and break oars and upperworks. `RAM` is a beak built below it, to open a hull.
PLAIN = "plain"
SPUR = "spur"
RAM = "ram"
FITTINGS = (PLAIN, SPUR, RAM)

#: How much of the impact a fitting drives into the ship struck.
#:
#: A plain stem spreads the blow over the whole width of the bow and much of the energy goes
#: into simply pushing her aside. A ram concentrates it on one point below the waterline,
#: which is what a ram is for.
BITE = {PLAIN: 0.55, SPUR: 0.80, RAM: 1.0}

#: How much of it comes back into the ship delivering it.
#:
#: The inverse relationship is the point, and it is not a game balance decision - it is what
#: a beak is: structure built forward of the hull to take the blow so the hull does not. A
#: plain stem has nothing out there, so the collision arrives at her own timbers.
RECOIL = {PLAIN: 1.0, SPUR: 0.70, RAM: 0.45}

#: Joules per kilogram of the ship receiving it, for one whole damage track.
#:
#: **Energy per tonne, not energy.** The first version divided joules by a constant and
#: called it damage, which is wrong in a way that only shows up at the extremes: a hull's
#: capacity to absorb a collision scales with her mass, and mass goes as the cube of her
#: size while `damage.resilience` goes as the first power of her length. So a frigate
#: running down a ship's boat produced a small absolute energy - the boat is light, and the
#: collision can only contain what the lighter of the two brings to it - and the boat
#: shrugged it off. Dividing by the mass of the ship being hit is what makes the same
#: collision trivial for the frigate and the end of the boat, which is what it is.
#:
#: Set so a two-hundred-ton brig at four knots into another brig's beam takes about a third
#: of her hull: a serious blow, and the end of neither. The one number here chosen rather
#: than derived.
SPECIFIC_ENERGY_PER_TRACK = 2.0

#: The most one blow may take of either ship, as a fraction of a full damage track.
#:
#: **Both sizes cap it, and this is the outer bound.** A collision is violent but it is one
#: event in one place, and a hull is long. Without a ceiling, a large ship at speed into a
#: small one produces an energy figure that would delete her outright, which reads as a bug
#: even when the arithmetic is right.
MOST_ONE_BLOW = 0.55

#: Below this closing speed, hulls touch rather than collide.
#:
#: Two ships coming alongside are moving relative to one another, and every one of those
#: would otherwise be a ram. Half a knot is about the speed a careful approach ends at.
TOUCHING = 0.26

#: The block coefficient assumed of a hull that does not say.
#:
#: Between a fine cutter at 0.45 and a full merchantman at 0.6. A game that models the
#: difference can say so per hull; one that does not gets a middling ship rather than an
#: error.
ASSUMED_BLOCK = 0.52

#: How square a blow on her stem has to be before it counts as bow to bow.
#:
#: Within twenty degrees of square into her bow, both stems are in it. Nothing is added for
#: it - two ships meeting are closing at the sum of their speeds, and the energy goes as the
#: square of that, so the arithmetic already makes it the worst collision on the board. It
#: is reported because it is worth saying, not because it is a special case.
HEAD_ON = 20.0

#: How oblique a blow may be before it glances off instead of biting.
#:
#: Degrees between the rammer's course and straight into the face she struck. Beyond about
#: seventy-eight she is running along that face rather than into it, which is a scrape down
#: the side - `sheer` - and not a collision.
#:
#: **Measured to the face struck, not to her beam.** The first version asked how far the
#: blow was from square on her side, which made running square into her stem - the worst
#: collision there is - read as a graze and refuse to resolve at all.
GLANCING = 78.0


@dataclass(frozen=True, kw_only=True)
class RamResult(Result):
    """
    What came of driving one hull into another.

    Attributes:
        speed (float): Closing speed along the line of impact, in metres per second.
        energy (float): The energy of the collision, in joules.
        angle (float): How square the blow was, in degrees. Zero is a blow square on
            her side; ninety would be a blow along her length, which does not happen
            because it glances off first.
        struck (str): Which of the target's aspects took it, from `tactical.aspect_name`.
        head_on (bool): Whether both stems were in it.
        weight (float): Damage weight into the ship struck.
        recoil (float): Damage weight back into the ship delivering it.
        fitting (str): What was on the rammer's bow.

    Notes:
        A failed result means no ram happened, and `reason` says which of the three ways:
        they never touched, they touched too gently, or the angle was too fine and it
        glanced. None of those is an error - two of them are what most approaches do.

    """

    speed: float = 0.0
    energy: float = 0.0
    angle: float = 0.0
    struck: str = ""
    head_on: bool = False
    weight: float = 0.0
    recoil: float = 0.0
    fitting: str = PLAIN


@dataclass(frozen=True, kw_only=True)
class SheerResult(Result):
    """
    What came of running down an enemy's side.

    Attributes:
        run (float): How much of her side was run down, as a fraction of her length.
        broken (float): Damage weight into her oars.
        recoil (float): Damage weight back into the rammer's own hull, from her looms
            breaking against it.
        looms (bool): Whether she had oars out at all. False means nothing was sheered
            and the result failed for that reason.

    """

    run: float = 0.0
    broken: float = 0.0
    recoil: float = 0.0
    looms: bool = False


def displacement(length, beam, draft, block=ASSUMED_BLOCK, density=1025.0):
    """
    What a hull weighs, for the purpose of hitting something with her.

    Args:
        length (float): Length on the waterline, in metres.
        beam (float): Extreme breadth, in metres.
        draft (float): How deep she floats, in metres.
        block (float, optional): How much of the enclosing box she fills.
        density (float, optional): Kilograms per cubic metre of the water she is in.

    Returns:
        mass (float): Her displacement, in kilograms.

    Notes:
        The same arithmetic as `shipyard.displaces`, taken separately because that module
        is about designing a hull and this one is about what happens when it arrives
        somewhere at speed. A vessel already afloat carries length, beam and draft; she does
        not necessarily carry the template she was built from.

    """
    return max(0.0, length) * max(0.0, beam) * max(0.0, draft) * block * density


def impact_speed(speed, heading, bearing, target_speed=0.0, target_heading=0.0):
    """
    How fast the two hulls are actually coming together.

    Args:
        speed (float): The rammer's speed through the water, in metres per second.
        heading (float): Her heading, in degrees.
        bearing (float): The bearing from her to the ship she is striking, in degrees.
        target_speed (float, optional): The target's speed, in metres per second.
        target_heading (float, optional): The target's heading, in degrees.

    Returns:
        closing (float): Metres per second of closure along the line between them.
            Negative means they are drawing apart, which cannot ram anybody.

    Notes:
        Both ships' motion resolved onto the line joining them, which is the only component
        that does any damage. A ship overtaken from astern by one making a knot more than
        she is takes a one-knot collision however fast the pair of them are going over the
        ground, and this is why.

        Chasing her is therefore a poor way to ram her, and meeting her is a violent one -
        both of which fall out of the arithmetic rather than being written down anywhere.

    """
    mine = speed * math.cos(math.radians(bearing - heading))
    hers = target_speed * math.cos(math.radians(bearing - target_heading))
    return mine - hers


BOW = "bow"
STERN = "stern"
SIDE = "side"

#: How much of a blow a face of the hull can turn aside.
#:
#: **A stem is the strongest part of a ship and her side is the weakest**, which is the
#: whole reason a beam strike is the one worth manoeuvring for. A stern is weaker than a
#: bow - it is where the great cabin and the rudder are and there is no structure to spare -
#: but it is still an end, and an end is built to meet the sea.
FACE_STRENGTH = {BOW: 0.5, STERN: 0.7, SIDE: 1.0}


def face_struck(bearing, target_heading, target_length, target_beam):
    """
    Which part of her the blow lands on, and which way that part faces.

    Args:
        bearing (float): The bearing from the rammer to the target, in degrees.
        target_heading (float): Which way the target is pointing, in degrees.
        target_length (float): Her length, in metres.
        target_beam (float): Her breadth, in metres.

    Returns:
        struck (tuple): `(face, outward)` - one of `BOW`, `STERN` or `SIDE`, and the
            compass bearing the struck face looks along.

    Notes:
        Decided by her own proportions rather than by a fixed arc. The corner between her
        bow and her side is where her stem gives way to her topsides, and on a hull thirty
        metres long and eight wide that is about sixteen degrees either side of dead ahead -
        so a bow strike is a narrow thing and a side strike is most of the circle, which is
        how a ship is actually shaped. A beamy hull presents a wider bow and a finer one a
        narrower, and neither needs a table.

    """
    off = (bearing + 180.0 - target_heading + 180.0) % 360.0 - 180.0
    corner = math.degrees(math.atan2(max(0.0, target_beam) / 2.0, max(1e-9, target_length) / 2.0))
    if abs(off) <= corner:
        return (BOW, target_heading)
    if abs(off) >= 180.0 - corner:
        return (STERN, target_heading + 180.0)
    return (SIDE, target_heading + (90.0 if off > 0.0 else -90.0))


def obliquity(heading, outward):
    """
    How square the rammer's course is to the face she struck.

    Args:
        heading (float): The rammer's heading, in degrees.
        outward (float): The bearing the struck face looks along, in degrees.

    Returns:
        angle (float): Degrees between her course and straight into that face. Zero is
            square on; ninety is parallel to it, and does not bite at all.

    Notes:
        **This is what a glancing blow actually is** - not "near her bow", which was the
        first version and which made a head-on collision read as a graze. Running square
        into her stem is as square a blow as running square into her side; what makes a
        blow glance is the course being *along* the surface it meets rather than into it.

    """
    return abs((heading - (outward + 180.0) + 180.0) % 360.0 - 180.0)


def _turned_aside(angle):
    """
    Args:
        angle (float): Degrees off square, from `obliquity`.

    Returns:
        share (float): How much of the energy actually goes into her, 0 to 1.

    Notes:
        A cosine, so a square blow delivers everything and a fine one delivers almost
        nothing. This is the geometry doing the work that a table of bonuses does
        elsewhere, and it is why the angle of approach is worth the trouble.

    """
    return max(0.0, math.cos(math.radians(min(90.0, max(0.0, angle)))))


def ram(
    speed,
    heading,
    bearing,
    length,
    beam,
    draft,
    target_length,
    target_beam,
    target_draft,
    target_speed=0.0,
    target_heading=0.0,
    fitting=PLAIN,
    block=ASSUMED_BLOCK,
    target_block=ASSUMED_BLOCK,
):
    """
    Drive one hull into another and find out what it cost them both.

    Args:
        speed (float): The rammer's speed, in metres per second.
        heading (float): Her heading, in degrees.
        bearing (float): The bearing from her to the target, in degrees.
        length (float): Her length, in metres.
        beam (float): Her breadth, in metres.
        draft (float): Her draft, in metres.
        target_length (float): The target's length, in metres.
        target_beam (float): The target's breadth, in metres.
        target_draft (float): The target's draft, in metres.
        target_speed (float, optional): The target's speed, in metres per second.
        target_heading (float, optional): The target's heading, in degrees.
        fitting (str, optional): What is on the rammer's bow, from `FITTINGS`.
        block (float, optional): The rammer's block coefficient.
        target_block (float, optional): The target's block coefficient.

    Returns:
        result (RamResult): What happened, successful only if a ram actually landed.

    Notes:
        **Severity is capped by both hulls.** A ship cannot deliver more of a blow than she
        has the weight to deliver, and cannot receive more than the collision contained -
        so the weight is bounded by `MOST_ONE_BLOW` of a full track on each side
        independently. A frigate running down a ship's boat destroys the boat and barely
        marks her own stem, and both of those come out of the same expression.

    """
    if fitting not in FITTINGS:
        raise ValueError(f"Unknown bow fitting {fitting!r}; expected one of {FITTINGS}.")

    closing = impact_speed(speed, heading, bearing, target_speed, target_heading)
    if closing <= TOUCHING:
        return RamResult(
            success=False,
            code="too_gently",
            speed=max(0.0, closing),
            fitting=fitting,
        )

    face, outward = face_struck(bearing, target_heading, target_length, target_beam)
    angle = obliquity(heading, outward)
    if angle >= GLANCING:
        return RamResult(
            success=False,
            code="glanced",
            speed=closing,
            angle=angle,
            struck=face,
            fitting=fitting,
        )

    # **Reduced mass, which is what a collision actually has to spend.**
    #
    # Two hulls meeting can only put into it what the pair of them bring, and for very
    # unequal ships that is almost entirely the lighter one - a boat cannot hole a ship of
    # the line by being rowed at her hard, however determined the rowing. The reduced mass
    # says so without a special case: for equal ships it is half of one of them, and for a
    # frigate and a boat it is very nearly the boat.
    mine = displacement(length, beam, draft, block)
    hers = displacement(target_length, target_beam, target_draft, target_block)
    if mine <= 0.0 or hers <= 0.0:
        return RamResult(
            success=False,
            code="no_hull",
            speed=closing,
            angle=angle,
            struck=face,
            fitting=fitting,
        )
    energy = 0.5 * (mine * hers / (mine + hers)) * closing * closing

    square = _turned_aside(angle)

    # Each ship is hurt by what the collision costs *her*, per tonne of her. The same
    # energy is a third of a brig's hull and several times over the end of a ship's boat,
    # and both of those come out of this one expression.
    #
    # She takes it on whichever face was struck; the rammer always takes it on her own
    # stem, because that is the part doing the striking.
    hurt = (energy / hers) / SPECIFIC_ENERGY_PER_TRACK * BITE[fitting] * square
    hurt *= FACE_STRENGTH[face]
    back = (energy / mine) / SPECIFIC_ENERGY_PER_TRACK * RECOIL[fitting] * square
    back *= FACE_STRENGTH[BOW]

    return RamResult(
        success=True,
        speed=closing,
        energy=energy,
        angle=angle,
        struck=face,
        head_on=face == BOW and angle <= HEAD_ON,
        weight=_capped(hurt * resilience(target_length), target_length),
        recoil=_capped(back * resilience(length), length),
        fitting=fitting,
    )


def _capped(weight, length):
    """
    Args:
        weight (float): Damage weight before the ceiling.
        length (float): The length of the hull receiving it, in metres.

    Returns:
        weight (float): What she actually takes.

    Notes:
        Expressed in damage weight rather than as a fraction, because that is what the
        typeclass layer passes to `take_damage` - which divides by her resilience itself.
        Converting here and back there would round twice for no gain.

    """
    return min(weight, MOST_ONE_BLOW * resilience(length))


def sheer(run, target_length, looms, counter=0.35):
    """
    Run down her side and break the oars she has out.

    Args:
        run (float): How much of her side was run down, as a fraction of her length.
            One is stem to stern.
        target_length (float): Her length, in metres.
        looms (bool): Whether she has oars out to break.
        counter (float, optional): How much of the damage comes back, as a share.

    Returns:
        result (SheerResult): What was broken, and what it cost. Failed if she had
            nothing out.

    Notes:
        **Only oars.** A sheer is not a collision - the hulls are alongside and moving the
        same way - so nothing here touches a hull track. What it takes away is her ability
        to move herself, which against a galley is worse than a hole.

        The counter is her looms breaking against the rammer's side as they go. Weaker,
        because they break rather than bite, and into the rammer's *hull* rather than her
        oars: it is a hundred lengths of timber hitting her topsides, not an attack.

    """
    if not looms:
        return SheerResult(success=False, code="no_oars", run=max(0.0, run))

    swept = min(1.0, max(0.0, run))
    broken = swept * MOST_ONE_BLOW * resilience(target_length)
    return SheerResult(
        success=True,
        run=swept,
        broken=broken,
        recoil=broken * counter,
        looms=True,
    )


def side_run_down(before, after, target_position, target_heading, target_length):
    """
    How much of a ship's side another ship ran down.

    Args:
        before (WorldPosition): Where the rammer started her step.
        after (WorldPosition): Where she ended it.
        target_position (WorldPosition): The target's centre.
        target_heading (float): Which way the target is pointing, in degrees.
        target_length (float): Her length, in metres.

    Returns:
        run (float): The fraction of her length that was run down, 0 to 1.

    Notes:
        Both ends of the rammer's step projected onto the target's fore-and-aft line, and
        the overlap between that span and the ship measured. A ship that crosses the whole
        of her side in one tick takes the lot; one that only reached her quarter before the
        tick ended takes what she reached.

        Direction does not matter. Running down her side from aft forward breaks the same
        oars as running down it from forward aft, and which way round it was is a detail
        for the narration rather than the arithmetic.

    """
    if target_length <= 0.0:
        return 0.0

    half = target_length / 2.0
    span = sorted(
        (
            _along(target_position, target_heading, before),
            _along(target_position, target_heading, after),
        )
    )
    overlap = min(span[1], half) - max(span[0], -half)
    return max(0.0, overlap) / target_length


def _along(origin, heading, point):
    """
    Args:
        origin (WorldPosition): The centre of the ship being measured against.
        heading (float): Her heading, in degrees.
        point (WorldPosition): The point to place.

    Returns:
        along (float): Metres forward of her centre, negative aft.

    """
    distance = origin.horizontal_distance_to(point)
    if distance <= 0.0:
        return 0.0
    return distance * math.cos(math.radians(origin.bearing_to(point) - heading))


def struck_by(position, heading, length, beam, point):
    """
    Whether a point falls inside a hull.

    Args:
        position (WorldPosition): The hull's centre.
        heading (float): Which way she is pointing, in degrees.
        length (float): Her length, in metres.
        beam (float): Her breadth, in metres.
        point (WorldPosition): The point in question - a bow, usually.

    Returns:
        inside (bool): Whether the point is within her.

    Notes:
        An oriented box rather than the seven-point outline `grounding` uses, because the
        question is the other way round. Grounding asks whether any part of a hull is over
        a piece of seabed and wants the hull's shape; this asks whether one particular
        point - the stem of the ship doing the ramming - is inside another hull, and for
        that a box in her own frame is both simpler and stricter at the corners, where a
        real hull has nothing anyway.

    """
    if length <= 0.0 or beam <= 0.0:
        return False

    distance = position.horizontal_distance_to(point)
    if distance <= 0.0:
        return True

    off = math.radians(position.bearing_to(point) - heading)
    return (
        abs(distance * math.cos(off)) <= length / 2.0
        and abs(distance * math.sin(off)) <= beam / 2.0
    )


def _local(origin, heading, point):
    """
    Args:
        origin (WorldPosition): The centre of the hull being measured against.
        heading (float): Her heading, in degrees.
        point (WorldPosition): The point to place.

    Returns:
        where (tuple): `(along, across)` in metres - forward of her centre and to
            starboard of it, both signed.

    """
    distance = origin.horizontal_distance_to(point)
    if distance <= 0.0:
        return (0.0, 0.0)
    off = math.radians(origin.bearing_to(point) - heading)
    return (distance * math.cos(off), distance * math.sin(off))


def contact_along(
    before,
    after,
    heading,
    length,
    target_position,
    target_heading,
    target_length,
    target_beam,
):
    """
    Where along a step one hull first reaches another.

    Args:
        before (WorldPosition): Where the rammer started.
        after (WorldPosition): Where she proposed to end.
        heading (float): Her heading, in degrees.
        length (float): Her length, in metres.
        target_position (WorldPosition): The target's centre.
        target_heading (float): The target's heading, in degrees.
        target_length (float): The target's length, in metres.
        target_beam (float): The target's breadth, in metres.

    Returns:
        contact (WorldPosition or None): Where her centre was when her stem first
            reached the other ship, or None if her step never did.

    Notes:
        **Solved rather than sampled.** The obvious way to write this is to step along the
        track and test each position, which is what grounding does against the seabed - and
        it is wrong here for a reason grounding does not have: the seabed is everywhere,
        and a ship is a small object that a coarse step walks straight past. Sampling every
        half a rammer's length missed a boat lying across the track entirely, and the
        faster the ship the more ships she was entitled to ignore.

        So the stem's track is treated as what it is - a line segment - and clipped against
        the target's hull as an oriented box, in the target's own frame where the box has
        no rotation. Exact, constant time, and there is no step size to get wrong.

    """
    if target_length <= 0.0 or target_beam <= 0.0:
        return None

    stem_before = before.moved(heading, length / 2.0)
    stem_after = after.moved(heading, length / 2.0)

    first = _local(target_position, target_heading, stem_before)
    last = _local(target_position, target_heading, stem_after)

    entry = _clipped(first, last, target_length / 2.0, target_beam / 2.0)
    if entry is None:
        return None

    # Back from the parametric position on the stem's track to where her *centre* was, which
    # is what the caller has to stop her at.
    travelled = before.horizontal_distance_to(after)
    if travelled <= 0.0:
        return before
    return before.moved(before.bearing_to(after), travelled * entry)


def _clipped(first, last, half_length, half_beam):
    """
    Where a segment first enters an axis-aligned box centred on the origin.

    Args:
        first (tuple): `(along, across)` of the segment's start.
        last (tuple): `(along, across)` of its end.
        half_length (float): Half the box's extent along.
        half_beam (float): Half its extent across.

    Returns:
        entry (float or None): How far along the segment it first enters, 0 to 1, or
            None if it never does.

    Notes:
        Slab clipping: the segment is trimmed against each pair of parallel sides in turn,
        and what survives is the part inside the box. A segment that starts inside returns
        zero, which is the right answer for two hulls that were already overlapping when
        the tick began.

    """
    near, far = 0.0, 1.0
    for start, end, half in (
        (first[0], last[0], half_length),
        (first[1], last[1], half_beam),
    ):
        direction = end - start
        if abs(direction) < 1e-12:
            # Parallel to this pair of sides: either always between them or never.
            if abs(start) > half:
                return None
            continue
        low = (-half - start) / direction
        high = (half - start) / direction
        if low > high:
            low, high = high, low
        near = max(near, low)
        far = min(far, high)
        if near > far:
            return None
    return near


__all__ = (
    "PLAIN",
    "SPUR",
    "RAM",
    "FITTINGS",
    "BITE",
    "RECOIL",
    "MOST_ONE_BLOW",
    "TOUCHING",
    "GLANCING",
    "HEAD_ON",
    "RamResult",
    "SheerResult",
    "displacement",
    "impact_speed",
    "face_struck",
    "obliquity",
    "FACE_STRENGTH",
    "BOW",
    "STERN",
    "SIDE",
    "ram",
    "sheer",
    "side_run_down",
    "struck_by",
    "contact_along",
)


class Rams:
    """
    The Evennia-side face of running into other ships.

    Notes:
        Holds the one thing a hull needs to carry for this - what is on her bow - and the
        one operation the tick needs: given a step she is proposing to take, find the first
        hull it reaches and work out what the collision costs them both.

        Nothing here decides anything. It reads the geometry, calls the functions above,
        and hands back a result; stopping her, applying the damage and telling anybody
        about it are the caller's, because the caller is the thing that knows whether she
        also ran aground on the same step and which of the two happened first.

    """

    #: How far either side of her track to look for something to hit, in metres.
    #:
    #: Wide enough for the longest hull in the game plus her own length, and no wider. The
    #: broad phase is a radius query on the traffic index and the narrow phase is exact, so
    #: this only has to avoid missing anybody - being generous costs a little arithmetic
    #: and being mean loses collisions.
    LOOKOUT = 400.0

    def at_object_creation(self):
        """Set up this part of a newly created vessel."""
        super().at_object_creation()
        self.db.bow_fitting = PLAIN

    @property
    def bow_fitting(self):
        """
        Returns:
            fitting (str): What is on her bow, from `FITTINGS`.

        Notes:
            A plain stem unless somebody has said otherwise, because most ships are not
            built to ram and a game that has not thought about it should not find its
            merchantmen fitted with beaks.

        """
        stored = self.db.bow_fitting
        return stored if stored in FITTINGS else PLAIN

    @bow_fitting.setter
    def bow_fitting(self, fitting):
        """
        Args:
            fitting (str): One of `FITTINGS`.

        Raises:
            ValueError: If that is not something a bow can have.

        """
        if fitting not in FITTINGS:
            raise ValueError(f"Unknown bow fitting {fitting!r}; expected one of {FITTINGS}.")
        if self.db.bow_fitting != fitting:
            self.db.bow_fitting = fitting

    def first_hull_along(self, before, after, heading, speed):
        """
        The first ship her step runs into.

        Args:
            before (WorldPosition): Where she started the step.
            after (WorldPosition): Where she proposed to end it.
            heading (float): Her heading, in degrees.
            speed (float): Her speed, in metres per second.

        Returns:
            struck (tuple or None): `(vessel, contact, result)` - who she hit, where her
                centre was when she hit them, and what it cost them both. None if her
                step ran into nobody.

        Notes:
            **Nearest first, because she can only hit one of them.** A step that crosses
            two ships hits the near one and stops there; carrying on to the far one would
            be a ship passing through a ship, which is the thing this exists to prevent.

        """
        from .environment import traffic

        best = None
        for other in traffic().near(before, self.LOOKOUT + before.horizontal_distance_to(after)):
            if other is self:
                continue
            where = other.maritime_position
            if where is None or not getattr(other, "length", 0.0):
                continue

            contact = contact_along(
                before,
                after,
                heading,
                self.length,
                where,
                other.heading,
                other.length,
                other.beam,
            )
            if contact is None:
                continue

            reached = before.horizontal_distance_to(contact)
            if best is not None and reached >= best[0]:
                continue

            result = ram(
                speed=speed,
                heading=heading,
                bearing=contact.bearing_to(where),
                length=self.length,
                beam=self.beam,
                draft=self.draft,
                target_length=other.length,
                target_beam=other.beam,
                target_draft=other.draft,
                target_speed=other.speed,
                target_heading=other.heading,
                fitting=self.bow_fitting,
            )
            best = (reached, other, contact, result)

        return None if best is None else (best[1], best[2], best[3])
