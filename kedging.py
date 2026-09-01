"""
Getting a ship off the ground by her own effort, rather than waiting for the tide.

A grounding that can only end when the water comes back is a grounding a player watches.
Kedging is the thing they *do* about it, and it is the thing that was actually done: a boat
carries an anchor out into deep water astern, drops it, and the hands walk the capstan round
until the ship is dragged off her own keel by her own cable.

    kedge            run out the anchor and heave. Once a watch; she comes off or she does not

**It is work, not a command that undoes a mistake.** Every heave costs the hands, and it
only ever pulls her a little way; a ship hard on with the tide falling is not coming off
this hour whatever anybody does, and one merely touching on a soft bottom probably is. What
decides it is how deep she is in, what she is sitting on, how many hands are fit, and
whether the water is rising or falling under her.

**She goes astern, because that is the way she came.** A ship drives on going forward, so
the water she came from is the water she is certain of - and kedging her ahead over ground
nobody has sounded is how a bad afternoon becomes a lost ship.

**It cannot lift a holed hull.** A ship opened on a reef is not held by the ground; she is
sitting on it because she is full of water. Hauling on a cable does nothing for that, and
saying so is better than offering a lever that never works.
"""

from .grounding import FOUL_GROUND, HOLED

#: How much of a hull's own weight her people can drag her by, per heave.
#:
#: Not a force in newtons - the contrib has no model of ground friction, and inventing one
#: to three decimal places would be a lie with a unit on it. This is the fraction of the
#: distance back to deep water she comes in one turn of work, at full effort, on a good
#: bottom. A tenth: so a soft grounding comes off in a few heaves and a hard one is a whole
#: watch of labour with no promise at the end.
HEAVE_FRACTION = 0.10

#: The least she moves on a heave that works at all, in metres.
#:
#: Two metres. A fraction alone would creep towards zero as she got close, so a ship a
#: metre and a half from floating would kedge for ever in ever smaller steps.
LEAST_HEAVE = 2.0

#: How far astern the anchor can be laid, in metres.
#:
#: Three hundred - a hawser's length, and near enough what a kedge was actually run out on.
#: A ship carried her kedge out in a boat on a warp of a hundred to two hundred fathoms,
#: which is a hundred and eighty to three hundred and sixty metres, and that is what decides
#: how far she can be hauled: not her own size.
#:
#: It was three times her own length, which for a cutter is fifty-four metres. That is far
#: too short to be any use: it will not haul a hull off an island two hundred and fifty
#: metres across, which is exactly the case that found it - she came off, drifted back on,
#: and did it again.
KEDGE_WARP = 300.0

#: Kept because it was published; nothing reads it now.
#:
#: It was how much water a point had to have before the anchor would be laid there, and it
#: turned out to be asking the wrong question. The anchor goes to the best water within a
#: warp, whatever that is - see `deep_water_astern` - and whether she is afloat when she
#: gets there is settled by sounding her afterwards rather than by a threshold set in
#: advance.
KEDGE_MARGIN = 2.0

#: How much of her people have to be fit for a heave to be worth attempting.
#:
#: A third. Below that there is nobody to walk the capstan round, and a ship with a fifth of
#: her company on their feet has larger problems than her keel.
LEAST_HANDS = 0.34

#: What each result is called.
CAME_OFF = "came_off"
MOVED = "moved"
HELD = "held"
HOLED_HULL = "holed"
NO_HANDS = "no_hands"
NOT_AGROUND = "not_aground"

#: What each one means, in the words the deck would use.
MEANS = {
    CAME_OFF: "She lifts, slides astern, and floats.",
    MOVED: "She grinds astern a little, and stops - still aground, but further out.",
    HELD: "The cable comes up bar-taut and she does not stir.",
    HOLED_HULL: (
        "She is opened, not held. No amount of heaving will lift a hull with the sea " "inside it."
    ),
    NO_HANDS: "There are not enough hands fit to walk the capstan round.",
    NOT_AGROUND: "She is afloat. There is nothing to kedge her off.",
}


class Heave:
    """
    What came of one turn of work at the capstan.

    Attributes:
        outcome (str): One of the results above.
        moved (float): How far she came, in metres.
        clearance (float): What she has under her now.

    """

    __slots__ = ("outcome", "moved", "clearance")

    def __init__(self, outcome, moved=0.0, clearance=0.0):
        self.outcome = outcome
        self.moved = moved
        self.clearance = clearance

    def __bool__(self):
        """
        Returns:
            free (bool): Whether she is afloat again.

        """
        return self.outcome == CAME_OFF

    @property
    def said(self):
        """
        Returns:
            sentence (str): What the deck sees.

        """
        return MEANS.get(self.outcome, "Nothing happens.")

    def __repr__(self):
        return f"<Heave {self.outcome} {self.moved:.1f} m>"


def deep_water_astern(vessel, world, now, reach=None):
    """
    The best water astern of her within one lay of the anchor.

    Args:
        vessel (Vessel): The hull.
        world (MaritimeMapProvider): The ground.
        now (float): Game time.
        reach (float, optional): How far astern to look, in metres.

    Returns:
        found (tuple): `(position, distance, clearance)` - the deepest point within a
            warp, or `(None, 0.0, 0.0)` if nothing astern is better than where she lies.

    Notes:
        Astern, because that is the way she came and therefore the only water on this coast
        anybody can be sure of.

        **The deepest water within a warp, not the first water she would float in.** Those
        are different, and the difference is the whole mechanism: a ship driven up a
        shelving beach has no floating water within three hundred metres of her, and a
        version of this that only looked for floating water reported her held for ever and
        the command became a dead end. What actually happened was that a ship kedged
        *repeatedly* - out to the anchor, lay it again, out again - creeping seaward down
        the slope a warp at a time. So this finds the best water she can reach on this lay,
        `heave` hauls her towards it, and she comes off when she is genuinely afloat, which
        may be the fourth or the fourteenth time.

        Nothing better than where she lies is a real answer and means the same thing it
        would to a bosun: the ground falls away the other way, and no amount of heaving
        astern is going to help.

    """
    from .grounding import check_swept_grounding

    astern = (vessel.heading + 180.0) % 360.0
    here = vessel.maritime_position
    far = reach if reach is not None else KEDGE_WARP
    step = max(LEAST_HEAVE, vessel.length / 4.0)

    def water_at(position):
        """
        Args:
            position (WorldPosition): Where to sound.

        Returns:
            clearance (float): What she would have under her there.

        """
        found = check_swept_grounding(
            position,
            position,
            vessel.heading,
            vessel.draft,
            0.0,
            vessel.length,
            vessel.beam,
            world,
            now,
        )
        return found.clearance

    best, span, deepest = None, 0.0, water_at(here)
    out = step
    while out <= far:
        there = here.moved(astern, out)
        under = water_at(there)
        if under > deepest:
            best, span, deepest = there, out, under
        out += step
    return best, span, deepest


def heave(vessel, now=None, effort=1.0):
    """
    One turn of work at the capstan.

    Args:
        vessel (Vessel): The hull.
        now (float, optional): Game time. Read from the clock if omitted.
        effort (float, optional): How much of their strength they have in it, 0 to 1.

    Returns:
        result (Heave): What happened, and how far she came.

    Notes:
        **She is dragged towards water, not teleported to it.** Each heave moves her a
        fraction of the way to the nearest place she would float, so a ship a few metres
        from deep water comes off quickly and one driven a hundred metres up a bank does
        not come off at all today. That is the honest shape of the thing.

        The bottom matters. Sand and mud let a hull slide; rock and coral hold her, and the
        same work moves her half as far - which is the same distinction that decides whether
        a grounding is a wasted tide or a lost ship.

        Every path through here is a real answer, including the ones that do nothing.
        Kedging that always worked would make grounding free, and grounding that nothing
        could undo is what this exists to fix.

    """
    from . import config

    if not vessel.aground:
        return Heave(NOT_AGROUND)

    record = vessel.db.grounding or {}
    if record.get("severity") == HOLED:
        return Heave(HOLED_HULL)

    company = vessel.company
    if company is not None and company.complement > 0:
        # What is left of her, which the company already knows how to say. Working it out
        # here from `fit` and `complement` would be a second answer to a question that has
        # one, and the two would drift the first time either changed.
        standing = 1.0 - company.casualty_fraction
        if standing < LEAST_HANDS:
            return Heave(NO_HANDS)
        effort = effort * standing

    world = vessel.map_here()
    here = vessel.maritime_position
    if world is None or here is None:
        return Heave(HELD)
    if now is None:
        now = config.time_provider().now()

    water, distance, clearance = deep_water_astern(vessel, world, now)
    if water is None:
        return Heave(HELD)

    # A bottom that holds gives up half as much for the same work.
    hold = 0.5 if record.get("bottom") in FOUL_GROUND else 1.0
    came = max(LEAST_HEAVE, distance * HEAVE_FRACTION) * hold * max(0.0, min(1.0, effort))
    if came <= 0.0:
        return Heave(HELD)

    if came >= distance:
        # All the way to the anchor. Whether that has floated her is a separate question -
        # on a long shelving beach it very often has not, and saying she is off when she is
        # merely further out would be the same lie the first version told.
        vessel.maritime_position = water
        vessel.checkpoint()
        return _settled(vessel, water, world, now, distance, clearance)

    astern = (vessel.heading + 180.0) % 360.0
    dragged = here.moved(astern, came)
    vessel.maritime_position = dragged
    vessel.checkpoint()
    return _settled(vessel, dragged, world, now, came, clearance)


def _settled(vessel, where, world, now, came, hoped):
    """
    Say whether the heave floated her, having already moved her.

    Args:
        vessel (Vessel): The hull.
        where (WorldPosition): Where she has been hauled to.
        world (MaritimeMapProvider): The ground.
        now (float): Game time.
        came (float): How far she moved.
        hoped (float): What was expected under her there.

    Returns:
        result (Heave): What the deck sees.

    Notes:
        Asked with the same test that grounded her, and asked *after* the move rather than
        predicted before it - a hull only just held needs very little, and one on a beach
        needs several warps. The answer decides whether she is still aground, which is the
        one piece of state everything else reads.

    """
    from .grounding import check_swept_grounding

    standing = check_swept_grounding(
        where,
        where,
        vessel.heading,
        vessel.draft,
        0.0,
        vessel.length,
        vessel.beam,
        world,
        now,
    )
    if standing:
        vessel.aground = False
        vessel.db.grounding = None
        vessel.checkpoint()
        return Heave(CAME_OFF, moved=came, clearance=standing.clearance)
    return Heave(MOVED, moved=came, clearance=hoped)


__all__ = (
    "HEAVE_FRACTION",
    "LEAST_HEAVE",
    "KEDGE_WARP",
    "KEDGE_MARGIN",
    "LEAST_HANDS",
    "CAME_OFF",
    "MOVED",
    "HELD",
    "HOLED_HULL",
    "NO_HANDS",
    "NOT_AGROUND",
    "MEANS",
    "Heave",
    "deep_water_astern",
    "heave",
)
