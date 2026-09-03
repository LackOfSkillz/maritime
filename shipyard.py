"""
Seven hulls a game can build from, and the arithmetic that produced their figures.

    yawl        a ship's boat, or the smallest thing that will keep the sea
    lugger      fast, weatherly, and built for people in a hurry
    cutter      one mast and a great deal of it; the revenue service's own
    schooner    two masts fore-and-aft, and the fastest thing here on a reach
    brig        two masts square-rigged; the workhorse of the age
    barque      three masts, square on two, and a hold to justify them
    frigate     a fifth rate: fast, heavy, and almost no room for cargo

**Every number here is derived, and the derivation is in the code.** A template whose
figures were chosen reads exactly like one whose figures were measured, right up to the
moment somebody asks why a brig carries what she carries. So the tonnages come out of
Builder's Old Measurement, the displacements out of the block coefficient, and the holds out
of the tonnage - and `tests/test_shipyard.py` checks two of them against vessels that
existed.

**Builder's Old Measurement**, the rule England used from about 1650 to 1849:

    tons burthen = ((length - 3/5 beam) x beam x beam/2) / 94      feet throughout

Burthen measures *volume*, not weight: one ton burthen is the space a 252-gallon tun of wine
occupies, about a hundred cubic feet. It says what a hull can hold and not what she can
lift, which is why `cargo.binding_limit` asks which of the two a load has used up.

**The rule wants the length of keel, and these give it the length on deck**, which is longer
by the rake of stem and sternpost. That overstates a square-rigger by about five per cent
and it is left overstating rather than fudged: the brig comes out at 405 tons against
*Cruizer*'s recorded 384, the error is in a known direction, and a correction factor pulled
out of the air to hide it would be worse than the honest five per cent. The frigate, whose
recorded figure comes from a class measured the same way, lands within one per cent.

**Rigs are three polar curves, not seven.** A square-rigger cannot lie closer than about six
points and is at her best with the wind on the quarter; a fore-and-aft rig is the reverse; a
lug sits between and runs better than either. Those are three genuinely different shapes.
Giving each hull her own curve would be seven sets of invented numbers dressed as research.

**Nothing here knows about artwork.** A game that has a picture of a brig hangs it on the
brig; the contrib names rigs because rigs are real, and stops there.
"""

from .motion import MotionLimits
from .oars import OAR_PLANS
from .sailing import FURLED, PolarCurve
from .vessel import OPEN, VesselCapacity

#: Feet in a metre, and cubic feet in a cubic metre. Written out because every figure below
#: crosses between the two, and a rule from 1650 is in feet whatever the rest of this
#: contrib measures in.
FEET_PER_METRE = 3.280839895
CUBIC_FEET_PER_CUBIC_METRE = 35.3146667

#: Cubic feet in one ton burthen - the space a tun of wine takes.
CUBIC_FEET_PER_TON = 100.0

#: Density of sea water, in kilograms per cubic metre. The figure for salt water at the
#: temperatures these hulls sail in; fresh water is 1000 and a hull sits deeper in it.
SEA_WATER = 1025.0

#: What fraction of a wooden hull's loaded displacement is *not* the hull itself.
#:
#: Deadweight: cargo, stores, water, guns, people. A wooden vessel is something over half
#: her loaded displacement light, which leaves about this much. Checked against the example
#: sloop, whose 40-tonne figure was arrived at independently: 99 tonnes loaded times this is
#: 41.6, and the sloop carries 40.
DEADWEIGHT_FRACTION = 0.42


def burthen(length, beam):
    """
    How much a hull measures, by Builder's Old Measurement.

    Args:
        length (float): Length on deck, in metres.
        beam (float): Extreme breadth, in metres.

    Returns:
        tons (float): Tons burthen.

    Notes:
        The rule wants the length of keel and is given the length on deck, which overstates
        a full-bodied hull by around five per cent. See the module docstring: the error is
        in a known direction and is left there.

    """
    long_feet = length * FEET_PER_METRE
    wide_feet = beam * FEET_PER_METRE
    return ((long_feet - 0.6 * wide_feet) * wide_feet * (wide_feet / 2.0)) / 94.0


def displaces(length, beam, draft, block):
    """
    What a hull weighs when she is loaded.

    Args:
        length (float): Length on the waterline, in metres.
        beam (float): Extreme breadth, in metres.
        draft (float): Draft loaded, in metres.
        block (float): Block coefficient - how much of the enclosing box the hull
            actually fills. A fine cutter is about 0.45, a full-bodied merchantman 0.6.

    Returns:
        mass (float): Loaded displacement in kilograms.

    """
    return length * beam * draft * block * SEA_WATER


def deadweight(length, beam, draft, block):
    """
    Args:
        length (float): Length on the waterline, in metres.
        beam (float): Extreme breadth, in metres.
        draft (float): Draft loaded, in metres.
        block (float): Block coefficient.

    Returns:
        mass (float): What she can carry, in kilograms, before she suffers for it.

    """
    return displaces(length, beam, draft, block) * DEADWEIGHT_FRACTION


def hold_of(length, beam, usable):
    """
    How much of a hull is hold.

    Args:
        length (float): Length on deck, in metres.
        beam (float): Extreme breadth, in metres.
        usable (float): What fraction of her measured volume is clear of crew space,
            ballast, magazines and stores.

    Returns:
        volume (float): Usable hold, in cubic metres.

    Notes:
        `usable` is where the difference between a smuggler and a frigate lives, and it is
        the one figure here that is judged rather than derived. A lugger is very nearly all
        hold; a fifth rate is powder, shot, water and two hundred and eighty men, and what
        is left over would not pay for the voyage.

    """
    measured = burthen(length, beam) * CUBIC_FEET_PER_TON
    return (measured / CUBIC_FEET_PER_CUBIC_METRE) * usable


#: A square rig's polar curve.
#:
#: Nothing at all inside six points - about sixty-seven degrees - because a square-rigger
#: does not lie closer and pretending otherwise removes the whole reason a fleet works to
#: windward for a week. Best with the wind on the quarter, and very nearly as good running,
#: which is what the rig is for.
SQUARE_RIG = PolarCurve(
    points=(
        (0.0, 0.0),
        (45.0, 0.0),
        (67.5, 0.35),
        (90.0, 0.80),
        (120.0, 1.00),
        (150.0, 1.00),
        (180.0, 0.95),
    )
)

#: A lug rig's polar curve.
#:
#: Points not quite as high as a gaff cutter and runs a great deal better, which is the
#: bargain a lugger strikes and the reason the trade favoured her. The dip-lug is a
#: nuisance to tack and nobody who sailed one for a living cared.
LUG_RIG = PolarCurve(
    points=(
        (0.0, 0.0),
        (30.0, 0.15),
        (45.0, 0.50),
        (60.0, 0.80),
        (90.0, 1.00),
        (120.0, 1.00),
        (150.0, 0.92),
        (180.0, 0.85),
    )
)

#: A gaff fore-and-aft rig, which is the contrib's default curve.
#:
#: Named here so a template can say which rig it carries rather than say nothing and get
#: the default by accident. Three of the seven hulls below are fore-and-aft and it should
#: be legible that they are.
FORE_AND_AFT = PolarCurve()


#: What each hull's `rig` says, and what it does not.
#:
#: How her sails are cut - square, lug, gaff, fore-and-aft - and not what kind of ship she
#: is. "topsail schooner" was in this field first, which put "a topsail-schooner-rigged
#: schooner" into the sentence a player reads when a ship is built. A field that repeats the
#: hull's own name reads as a bug the first time anybody sees it, because it is one.
#:
#: Three of them therefore say the same thing as their curve does, which is the point: the
#: word is what a player is told and the curve is what the wind does, and they should agree.


#: The seven hulls.
#:
#: Dimensions first, because everything else is worked out from them. `block` and `usable`
#: are the two judged figures; the rest of the fitting-out is what a builder would have to
#: decide anyway.
HULLS = {
    "yawl": {
        "rig": "fore-and-aft",
        "length": 10.0,
        "beam": 3.2,
        "draft": 1.3,
        "air_draft": 12.0,
        "block": 0.40,
        "usable": 0.25,
        "windage": 0.05,
        "berths": 3,
        "oars": OAR_PLANS["skiff"],
        "curve": FORE_AND_AFT,
        "limits": MotionLimits(max_speed=2.8, acceleration=0.7, turn_rate=12.0),
        "desc": (
            "A half-decked boat with two masts, the after one stepped abaft the rudder "
            "head and carrying little more than a steadying sail. She is open from the "
            "mast aft, and there is a pair of oars along the thwarts for calms and "
            "harbours."
        ),
        "decks": (
            {
                "key": "In the yawl",
                "level": 0,
                "exposure": OPEN,
                "eye": 1.6,
                "desc": (
                    "Thwarts, a bailer under the after one, and the tiller across your "
                    "knee. The gunwale is low enough to put a hand over the side without "
                    "leaving your seat."
                ),
            },
        ),
    },
    "lugger": {
        "rig": "lug",
        "length": 17.0,
        "beam": 5.0,
        "draft": 2.1,
        "air_draft": 18.0,
        "block": 0.45,
        "usable": 0.50,
        "windage": 0.04,
        "berths": 12,
        "oars": OAR_PLANS["gig"],
        "curve": LUG_RIG,
        "limits": MotionLimits(max_speed=4.6, acceleration=0.5, turn_rate=7.0),
        "desc": (
            "Three masts raked aft and a hull with no more freeboard than she needs. The "
            "yards are slung well off centre and every one of them has to come down and "
            "go round the mast to tack her, which is a great deal of work and buys a "
            "turn of speed nobody else has."
        ),
        "decks": (
            {
                "key": "Deck",
                "level": 0,
                "exposure": OPEN,
                "eye": 2.2,
                "desc": (
                    "Flush from stem to stern, with the masts coming up through it and "
                    "the halyards belayed at their heels. There is no wheel - a tiller "
                    "comes in over the transom and takes two hands in a sea."
                ),
            },
            {
                "key": "Cabin",
                "level": -1,
                "exposure": "interior",
                "desc": (
                    "Bunks against both sides and a stove between them with its pipe "
                    "through the deck. Headroom for a man who does not stand straight."
                ),
            },
            {
                "key": "Hold",
                "level": -1,
                "exposure": "below_waterline",
                "hold": True,
                "desc": (
                    "Open frames and a plank floor over the ballast, running most of her "
                    "length. She was built round this space and everything else was "
                    "fitted in afterwards."
                ),
            },
        ),
    },
    "cutter": {
        "rig": "gaff",
        "length": 20.0,
        "beam": 6.0,
        "draft": 2.6,
        "air_draft": 25.0,
        "block": 0.45,
        "usable": 0.45,
        "windage": 0.04,
        "berths": 25,
        "oars": OAR_PLANS["cutter"],
        "curve": FORE_AND_AFT,
        "limits": MotionLimits(max_speed=5.1, acceleration=0.4, turn_rate=5.0),
        "desc": (
            "One mast, and an immoderate amount of it. The bowsprit runs out level and "
            "reeves in and out on a traveller, so she can set headsails halfway to the "
            "horizon in light airs and get them all inboard before it blows."
        ),
        "decks": (
            {
                "key": "Deck",
                "level": 0,
                "exposure": OPEN,
                "eye": 2.4,
                "desc": (
                    "The mast comes up a third of the way from the bow with the "
                    "bitts round its heel, and the boom overhangs the transom by "
                    "several feet. Sweeps are lashed along both rails."
                ),
            },
            {
                "key": "Masthead",
                "level": 3,
                "exposure": OPEN,
                "eye": 20.0,
                "desc": (
                    "An arm round the topmast and both feet on the crosstrees. There is "
                    "nothing to hold you here but your own grip, and the horizon is a "
                    "great deal further off than it was on deck."
                ),
            },
            {
                "key": "Cabin",
                "level": -1,
                "exposure": "interior",
                "desc": (
                    "A table that folds against the bulkhead, lockers under the "
                    "settees, and a skylight overhead that leaks in anything worse "
                    "than a shower."
                ),
            },
            {
                "key": "Hold",
                "level": -1,
                "exposure": "below_waterline",
                "hold": True,
                "desc": (
                    "Bare frames, a plank floor and a pump well at its after end. The "
                    "bilge finds its way here from everywhere else aboard."
                ),
            },
        ),
    },
    "schooner": {
        "rig": "fore-and-aft",
        "length": 27.0,
        "beam": 7.3,
        "draft": 3.4,
        "air_draft": 30.0,
        "block": 0.42,
        "usable": 0.50,
        "windage": 0.04,
        "berths": 40,
        "oars": None,
        "curve": FORE_AND_AFT,
        "limits": MotionLimits(max_speed=6.2, acceleration=0.35, turn_rate=4.0),
        "desc": (
            "Two masts raked hard aft, fore-and-aft on both with square topsails on the "
            "fore. The hull is drawn out fine at both ends and has a great deal of "
            "deadrise, which is a way of saying she was built to outrun things."
        ),
        "decks": (
            {
                "key": "Quarterdeck",
                "level": 0,
                "exposure": OPEN,
                "eye": 3.0,
                "desc": (
                    "The wheel, the binnacle abaft it, and the main boom overhead with "
                    "sheet enough to run out over the taffrail. The companion to the "
                    "cabin is under the break forward."
                ),
            },
            {
                "key": "Forecastle",
                "level": 0,
                "exposure": OPEN,
                "eye": 3.0,
                "desc": (
                    "The windlass across the deck, the foremast behind it, and the "
                    "cathead out over each bow. Chain leads aft to the locker through "
                    "a pipe in the deck."
                ),
            },
            {
                "key": "Foretop",
                "level": 3,
                "exposure": OPEN,
                "eye": 22.0,
                "desc": (
                    "A platform no wider than a table, with the topsail yard across it "
                    "and the shrouds coming up through the lubber's hole. Everything "
                    "below looks narrow from here."
                ),
            },
            {
                "key": "Cabin",
                "level": -1,
                "exposure": "interior",
                "desc": (
                    "Panelled to the deck head, with stern windows across the after "
                    "end and a table long enough to spread a chart on."
                ),
            },
            {
                "key": "Hold",
                "level": -1,
                "exposure": "below_waterline",
                "hold": True,
                "desc": (
                    "Ceiling planking over the frames and a limber passage down the "
                    "centre line. Two hatches let into it from the deck above."
                ),
            },
        ),
    },
    "brig": {
        "rig": "square",
        "length": 30.5,
        "beam": 9.3,
        "draft": 3.9,
        "air_draft": 34.0,
        "block": 0.52,
        "usable": 0.50,
        "windage": 0.05,
        "berths": 90,
        "oars": None,
        "curve": SQUARE_RIG,
        "limits": MotionLimits(max_speed=5.4, acceleration=0.25, turn_rate=3.0),
        "desc": (
            "Two masts, square-rigged on both, with a gaff spanker on the main to give "
            "her something to steer by. She is the size the trade settled on: big enough "
            "to be worth loading and small enough for one mate and a dozen hands."
        ),
        "decks": (
            {
                "key": "Quarterdeck",
                "level": 0,
                "exposure": OPEN,
                "eye": 3.4,
                "desc": (
                    "The wheel abaft the mainmast, the binnacle before it, and the "
                    "spanker boom overhead. The rail is pierced for the after guns."
                ),
            },
            {
                "key": "Forecastle",
                "level": 0,
                "exposure": OPEN,
                "eye": 3.6,
                "desc": (
                    "Raised a step above the waist, with the windlass athwartships and "
                    "the galley funnel coming up through it. The bowsprit steeves up "
                    "sharply from the knightheads."
                ),
            },
            {
                "key": "Maintop",
                "level": 3,
                "exposure": OPEN,
                "eye": 24.0,
                "desc": (
                    "A platform at the head of the lower mast, with the topmast rigging "
                    "spreading from its edge. There is room for three men and the "
                    "swivel that mounts on the forward rail."
                ),
            },
            {
                "key": "Great Cabin",
                "level": -1,
                "exposure": "interior",
                "desc": (
                    "The full breadth of the hull, stern windows across the after "
                    "bulkhead, and a deck that slopes with her. Canvas painted in "
                    "squares does for a carpet."
                ),
            },
            {
                "key": "Hold",
                "level": -1,
                "exposure": "below_waterline",
                "hold": True,
                "desc": (
                    "Two decks down, with the ballast under the ceiling planking and "
                    "the mainmast coming through it to the step. Cool, and dark at any "
                    "hour."
                ),
            },
        ),
    },
    "barque": {
        "rig": "square",
        "length": 45.0,
        "beam": 9.5,
        "draft": 5.0,
        "air_draft": 40.0,
        "block": 0.58,
        "usable": 0.60,
        "windage": 0.06,
        "berths": 25,
        "oars": None,
        "curve": SQUARE_RIG,
        "limits": MotionLimits(max_speed=6.2, acceleration=0.18, turn_rate=2.0),
        "desc": (
            "Three masts, square on the fore and main and fore-and-aft on the mizzen. "
            "Dropping the mizzen yards is what makes her a barque and not a ship, and it "
            "is why two dozen hands can work a hull this size when a full rig would want "
            "twice that."
        ),
        "decks": (
            {
                "key": "Poop",
                "level": 0,
                "exposure": OPEN,
                "eye": 4.5,
                "desc": (
                    "The wheel and the binnacle, raised above the main deck with the "
                    "spanker boom overhead and the log reel on the rail aft."
                ),
            },
            {
                "key": "Main Deck",
                "level": 0,
                "exposure": OPEN,
                "eye": 3.4,
                "desc": (
                    "The waist between the two houses, with the fife rails round the "
                    "masts and the pinrails along both bulwarks. Every halyard, brace "
                    "and downhaul aboard comes down to one of them."
                ),
            },
            {
                "key": "Forecastle Head",
                "level": 0,
                "exposure": OPEN,
                "eye": 4.2,
                "desc": (
                    "Over the crew's quarters, with the windlass below and the "
                    "anchors catted either side. The jibboom runs out beyond the "
                    "knightheads."
                ),
            },
            {
                "key": "Maintop",
                "level": 3,
                "exposure": OPEN,
                "eye": 28.0,
                "desc": (
                    "The lower top, with the topmast rigging spreading from it and the "
                    "futtock shrouds leaning outboard below. The deck is a long way "
                    "down and directly beneath you."
                ),
            },
            {
                "key": "Saloon",
                "level": -1,
                "exposure": "interior",
                "desc": (
                    "Panelled, with a long table down the middle and the officers' "
                    "cabins opening off both sides. A skylight overhead and a "
                    "tell-tale compass under it."
                ),
            },
            {
                "key": "Hold",
                "level": -1,
                "exposure": "below_waterline",
                "hold": True,
                "desc": (
                    "One space nearly the length of her, ceiled over the frames, with "
                    "three hatchways letting down into it and the mainmast running "
                    "through to the keelson."
                ),
            },
        ),
    },
    "frigate": {
        "rig": "square",
        "length": 45.7,
        "beam": 12.2,
        "draft": 4.2,
        "air_draft": 46.0,
        "block": 0.52,
        "usable": 0.25,
        "windage": 0.05,
        "berths": 280,
        "oars": None,
        "curve": SQUARE_RIG,
        "limits": MotionLimits(max_speed=6.9, acceleration=0.22, turn_rate=2.5),
        "desc": (
            "A fifth rate: one covered gun deck, a quarterdeck and forecastle above it, "
            "and a battery that would sink anything she cannot outrun. What she has not "
            "got is room - almost everything below the waterline is powder, shot, water "
            "and the men to serve them."
        ),
        "decks": (
            {
                "key": "Quarterdeck",
                "level": 0,
                "exposure": OPEN,
                "eye": 5.0,
                "desc": (
                    "The wheel and its two binnacles, the mizzen coming up through the "
                    "deck forward of them, and the hammock nettings along both rails. "
                    "The break of the deck looks down into the waist."
                ),
            },
            {
                "key": "Forecastle",
                "level": 0,
                "exposure": OPEN,
                "eye": 5.2,
                "desc": (
                    "The belfry, the galley funnel, and the catheads out over each bow "
                    "with the anchors stowed against them."
                ),
            },
            {
                "key": "Gun Deck",
                "level": -1,
                "exposure": "interior",
                "desc": (
                    "The full length of her under one deck head, the guns run out at "
                    "their ports along both sides and the mess tables slung between "
                    "them. Headroom of five feet and a little more."
                ),
            },
            {
                "key": "Maintop",
                "level": 3,
                "exposure": OPEN,
                "eye": 32.0,
                "desc": (
                    "A platform wide enough for a dozen men, railed forward, with the "
                    "topmast rigging spreading from its edge and the swivels mounted "
                    "on the rail."
                ),
            },
            {
                "key": "Great Cabin",
                "level": -1,
                "exposure": "interior",
                "desc": (
                    "Across the whole breadth of the stern, with the quarter galleries "
                    "either side and windows the width of her. Two of the after guns "
                    "stand in it, which no amount of panelling disguises."
                ),
            },
            {
                "key": "Hold",
                "level": -1,
                "exposure": "below_waterline",
                "hold": True,
                "desc": (
                    "Below the orlop, with the water casks stowed in tiers on the "
                    "shingle ballast and the shot lockers against the mainmast. What "
                    "space is left over is not much."
                ),
            },
        ),
    },
}

#: What the rigs are called, in the order somebody would meet them.
#:
#: A tuple rather than `HULLS.keys()`, so the order a command lists them in is the order
#: they were written and not whatever a dictionary happens to hold. Smallest first, which
#: is how somebody choosing between them would like to read it.
NAMES = ("yawl", "lugger", "cutter", "schooner", "brig", "barque", "frigate")


def specification(name):
    """
    Args:
        name (str): One of `NAMES`, in any case.

    Returns:
        spec (dict or None): The hull, or None if there is no such rig.

    """
    return HULLS.get(str(name or "").strip().lower())


def figures(name):
    """
    The worked-out numbers for a hull, as a command would report them.

    Args:
        name (str): One of `NAMES`.

    Returns:
        worked (dict or None): `burthen`, `displacement`, `deadweight`, `hold`, `berths`,
            and the dimensions, or None if there is no such rig.

    Notes:
        Worked out on each call rather than stored. They are seven multiplications, they
        are derived from figures written down a few lines above them, and a stored copy is
        a second place for them to be wrong.

    """
    spec = specification(name)
    if spec is None:
        return None
    return {
        "rig": spec["rig"],
        "length": spec["length"],
        "beam": spec["beam"],
        "draft": spec["draft"],
        "burthen": burthen(spec["length"], spec["beam"]),
        "displacement": displaces(spec["length"], spec["beam"], spec["draft"], spec["block"]),
        "deadweight": deadweight(spec["length"], spec["beam"], spec["draft"], spec["block"]),
        "hold": hold_of(spec["length"], spec["beam"], spec["usable"]),
        "berths": spec["berths"],
        "compartments": len(spec["decks"]),
        "price": price_of(name),
    }


#: What a ton burthen costs, in the smallest coin.
#:
#: **Ships were contracted and bought by the ton burthen**, which is why the price hangs off
#: the one figure this module already computes rather than off a table somebody has to keep
#: in step with the hulls. A builder who draws a bigger ship gets a dearer one without
#: touching anything, and a rig that is added later is priced the moment it exists.
#:
#: Sized against the example world's starting purse so the demo loop - buy a hull, provision
#: her, load a cargo, make a passage - is reachable. Somebody arriving to see what this
#: contrib does should be stopped by the sea, not by pocket money.
PER_TON_BURTHEN = 1400

#: What each rig costs against a plain fore-and-aft hull of the same burthen.
#:
#: A square rig is dearer than she looks: more spars, more standing rigging, more blocks,
#: and a great deal more of all of it aloft. A lug sits just above a bare fore-and-aft rig -
#: which is what made it the working rig of small craft that could not afford the other - and
#: a gaff rig above that again, for the boom, the gaff and the throat and peak halyards that
#: come with it.
#:
#: **Every rig the yard builds is in here, and nothing else is.** A missing one would be
#: priced as the cheapest by a default and look right; a spare one would sit there looking
#: correct for ever. Both are pinned by tests, because the first of them was found by one.
RIG_COST = {"fore-and-aft": 1.0, "lug": 1.15, "gaff": 1.2, "square": 1.45}


def price_of(name, per_ton=PER_TON_BURTHEN):
    """
    What a hull of this rig costs new.

    Args:
        name (str): One of `NAMES`.
        per_ton (int, optional): What a ton burthen costs, in the smallest coin.

    Returns:
        price (Coin or None): What the yard wants, or None if there is no such rig.

    Notes:
        Derived from her burthen and her rig, so the seven hulls are priced in order of size
        without anybody deciding what order that is - and so the yawl and the frigate are
        priced by the same rule rather than by two opinions.

    """
    from .ledger import Coin

    spec = specification(name)
    if spec is None:
        return None
    tons = burthen(spec["length"], spec["beam"])
    # Subscripted rather than fetched with a default, deliberately. A `get` here priced a
    # gaff cutter as a bare fore-and-aft hull and looked entirely correct doing it - the
    # kind of silent fallback that survives review and is found by a completeness test.
    rigging = RIG_COST[spec["rig"]]
    return Coin(smallest=int(round(tons * float(per_ton) * rigging)))


def prices():
    """
    Returns:
        prices (dict): Every rig by name, and what it costs.

    Notes:
        What a menu reads. The menu itself is a game's - see `docs/shipyard.md` - but what
        each hull is worth is a fact about the hull, so it lives here beside her dimensions.

    """
    return {name: price_of(name) for name in NAMES}


def capacity_of(name):
    """
    Args:
        name (str): One of `NAMES`.

    Returns:
        capacity (VesselCapacity or None): What she can carry.

    Notes:
        `deck_area` is length by beam, which is generous - a hull is not a rectangle - and
        it is left generous because nothing consumes it yet and a figure invented to be
        precise would be a worse lie than one that is obviously an upper bound.

        `stability_moment` is displacement times beam, which is the shape of the real
        thing: righting moment goes with how heavy she is and how wide. The constant in
        front of it is not known and is taken as one, so these are comparable with each
        other and not with anything else.

    """
    spec = specification(name)
    if spec is None:
        return None
    loaded = displaces(spec["length"], spec["beam"], spec["draft"], spec["block"])
    return VesselCapacity(
        displacement=deadweight(spec["length"], spec["beam"], spec["draft"], spec["block"]),
        internal_volume=hold_of(spec["length"], spec["beam"], spec["usable"]),
        deck_area=spec["length"] * spec["beam"],
        stability_moment=loaded * spec["beam"],
        berths=spec["berths"],
    )


def outfit(vessel, name):
    """
    Give a hull everything her rig says she has.

    Args:
        vessel (Vessel): A freshly created hull.
        name (str): One of `NAMES`.

    Returns:
        vessel (Vessel): The same hull, for chaining.

    Raises:
        KeyError: If there is no such rig.

    Notes:
        A function over data rather than seven subclasses. A game's ships are its own, and
        the shortest honest answer to "how do I make a brig" is a dictionary and nine
        assignments - not a hierarchy that has to be read before it can be copied.

        The description is not set here. What a hull *is* belongs to the rig; what one
        particular ship looks like belongs to whoever built her, and writing the rig's
        description onto every vessel of that rig would give a harbour seven descriptions
        between forty ships.

    """
    spec = HULLS[str(name).strip().lower()]
    vessel.length = spec["length"]
    vessel.beam = spec["beam"]
    vessel.light_draft = spec["draft"]
    vessel.air_draft = spec["air_draft"]
    vessel.windage = spec["windage"]
    vessel.motion_limits = spec["limits"]
    vessel.capacity = capacity_of(name)
    vessel.polar_curve = spec["curve"]
    vessel.sail_plan = FURLED
    if spec["oars"]:
        vessel.oar_plan = spec["oars"]
    return vessel


def compartments(vessel, name):
    """
    Build her decks and hang them on her.

    Args:
        vessel (Vessel): The hull.
        name (str): One of `NAMES`.

    Returns:
        rooms (list): The compartments made, in the order they were written.

    Notes:
        Made here rather than in a command so that a game building a fleet from a script
        gets the same ship a player gets from a dock. Two ways to make a brig is two ways
        for a brig to be wrong.

    """
    from evennia.utils import create

    from .rooms import ShipRoom
    from .vessel import BELOW_WATERLINE, INTERIOR

    spec = HULLS[str(name).strip().lower()]
    exposures = {"interior": INTERIOR, "below_waterline": BELOW_WATERLINE}
    hold = hold_of(spec["length"], spec["beam"], spec["usable"])
    holds = [deck for deck in spec["decks"] if deck.get("hold")]

    made = []
    for deck in spec["decks"]:
        room = create.create_object(ShipRoom, key=f"{vessel.key} - {deck['key']}")
        room.vessel = vessel
        room.deck_level = deck.get("level", 0)
        room.exposure = exposures.get(deck["exposure"], deck["exposure"])
        room.db.desc = deck["desc"]
        if deck.get("eye"):
            room.height_of_eye = deck["eye"]
        if deck.get("hold"):
            # Shared out, so that a hull with two holds does not carry twice what her
            # tonnage says. It is her measurement that is being divided up, not each
            # compartment's.
            room.hold_capacity = hold / float(len(holds))
        made.append(room)
    return made


__all__ = (
    "FEET_PER_METRE",
    "CUBIC_FEET_PER_CUBIC_METRE",
    "CUBIC_FEET_PER_TON",
    "SEA_WATER",
    "DEADWEIGHT_FRACTION",
    "SQUARE_RIG",
    "LUG_RIG",
    "FORE_AND_AFT",
    "HULLS",
    "NAMES",
    "burthen",
    "displaces",
    "deadweight",
    "hold_of",
    "specification",
    "figures",
    "capacity_of",
    "outfit",
    "compartments",
)
