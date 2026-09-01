"""
The three boats of the example world, and what makes them different.

A kayak, a canoe and a sloop, chosen because between them they use every kind of
propulsion this contrib has and demonstrate that none of them is a special case:

    kayak    one paddle, no sails. A pond boat.
    canoe    two paddles, no sails. A river boat, and the river decides how hard.
    sloop    sails, and two sweeps for when the wind dies. A sea boat.

**The sloop carries oars on purpose.** Nobody rows a boat that is sailing, so her sweeps
do nothing until she is becalmed - at which point they become the difference between
getting home and drifting. That is one line of configuration and the whole of the argument
for modelling both.

**What they carry was checked against real vessels rather than chosen.** The sloop is very
nearly a ship that existed: eighteen metres by five point four is 59 ft by 17 ft 8 in, and
the US revenue cutter *Massachusetts* of 1791 was 60 ft by 17 ft 8 in on a 7 ft 8 in draft
and measured 70 tons burthen. Builder's Old Measurement - the rule England used from about
1650 to 1849 - puts this hull at 81 tons by formula:

    tons burthen = ((length - 3/5 beam) x beam x beam/2) / 94        length and beam in feet

Burthen is a measure of *volume*, not weight: one ton burthen is the space a 252-gallon tun
of wine takes, about a hundred cubic feet. So it says what she can hold and not what she can
lift, and the two limits are different - which is exactly why `cargo.binding_limit` asks
which of them a load has actually used up.

For the weight, the ordinary naval architecture. A hull of these dimensions at a block
coefficient of 0.45 - fine, as a cutter is - displaces about 99 tonnes loaded; a wooden
vessel is something over half that light, leaving about 42 tonnes of deadweight for cargo,
stores, water and people. The figure here is 40 tonnes, which is inside six per cent of that
and on the right side of it.

The hold follows the same check. Seventy tons burthen is 7,000 cubic feet or 198 cubic
metres *measured*, of which a cutter's usable hold - below deck, clear of crew space, ballast
and stores - is some forty to fifty per cent, or 79 to 99 cubic metres. The figure here is
90. The paddling craft were checked the same way and want no argument: a sea kayak carries a
paddler and gear, and a canoe of five and a half metres carries three or four hundred
kilograms.

Every craft here is an ordinary `Vessel` with one compartment. A kayak with a "Main Deck"
would be silly, so hers is called what a kayak has; the architecture does not care, and
that it does not care is the point. A hull holds a position and its compartments resolve
through to it, whether there are twelve of them or one.

"""

from ..motion import MotionLimits
from ..oars import OAR_PLANS
from ..sailing import FURLED, PolarCurve
from ..vessel import OPEN, VesselCapacity

#: The craft, as data. Each is what a builder would have to decide anyway: how big she
#: is, how deep she sits, how much of the wind she catches when nobody is driving her,
#: what she is pulled by, and what her one compartment is called.
CRAFT = {
    "kayak": {
        "key": "a kayak",
        "desc": (
            "A slim hull barely wider than a person, with a double blade laid across "
            "the deck. She sits so low that the water is at your elbow."
        ),
        "length": 4.6,
        "beam": 0.7,
        "draft": 0.15,
        "windage": 0.05,
        "oars": OAR_PLANS["paddle"],
        "limits": MotionLimits(max_speed=3.0, acceleration=0.8, turn_rate=40.0),
        "compartment": "In the kayak",
        "compartment_desc": (
            "You are sitting almost in the water, knees under the deck and the blade "
            "across your lap. Every ripple is at eye level."
        ),
        "capacity": VesselCapacity(displacement=120.0, berths=1),
    },
    "canoe": {
        "key": "a canoe",
        "desc": (
            "An open boat with two thwarts and a paddle shipped under each. There is "
            "room for a little cargo between them, and none to spare."
        ),
        "length": 5.5,
        "beam": 1.0,
        "draft": 0.25,
        "windage": 0.06,
        "oars": OAR_PLANS["canoe"],
        "limits": MotionLimits(max_speed=3.0, acceleration=0.6, turn_rate=30.0),
        "compartment": "In the canoe",
        "compartment_desc": (
            "Two thwarts, a coil of line and a bailer. The gunwale is a hand's breadth "
            "above the water and the bank slides past close enough to touch."
        ),
        "capacity": VesselCapacity(displacement=400.0, berths=2),
    },
    "sloop": {
        "key": "the Kittiwake",
        "desc": (
            "A working sloop, black-hulled and tarred, with a single mast and a boom "
            "that will take your head off if you are slow. Two sweeps are lashed along "
            "the rail for when the wind fails."
        ),
        "length": 18.0,
        "beam": 5.4,
        "draft": 2.2,
        "air_draft": 20.0,
        "windage": 0.04,
        "oars": OAR_PLANS["skiff"],
        "limits": MotionLimits(max_speed=5.0, acceleration=0.4, turn_rate=4.0),
        "capacity": VesselCapacity(
            displacement=40000.0, internal_volume=90.0, stability_moment=120000.0, berths=6
        ),
        "sails": True,
        "decks": (
            (
                "Main Deck",
                0,
                OPEN,
                2.0,
                0.0,
                "Tarred planking, a tiller you could steer with your hip, and the mast "
                "coming up through the deck a step forward of it. The boom is overhead.",
            ),
            (
                "Masthead",
                3,
                OPEN,
                18.0,
                0.0,
                "Twenty feet up, with an arm round the mast and the whole coast laid out "
                "flat below you. The horizon is a great deal further from here.",
            ),
            (
                "Cabin",
                -1,
                "interior",
                0.0,
                0.0,
                "Two bunks, a locker and a smell of tar and old rope. You can stand up in "
                "it if you are not tall.",
            ),
            (
                "Hold",
                -1,
                "below_waterline",
                0.0,
                60.0,
                "Bare frames and a bilge that needs pumping. Sixty cubic metres of nothing, "
                "waiting for something worth carrying.",
            ),
        ),
    },
}

#: What the sloop actually makes under working sail in the example's breeze, on the
#: heading the island chain runs along. Used to space the islands and to check they
#: stayed a fair sail apart.
#:
#: **Measured, not assumed.** The first version of this file guessed four metres a
#: second, which is nearly twice what she does, and the test that checked the island
#: spacing passed because it was checking against the same guess. Sailing her the
#: length of one leg is what caught it.
#:
#: It is also why the example's wind is a southerly: on this course that puts it
#: across her beam, which is her best point of sailing. From the west she makes 1.5
#: and the same chain becomes a slog.
CRUISING_SPEED = 2.2

#: The wind this figure was measured in - direction it blows *from*, and speed.
#: A game changing `MARITIME_WIND_BEARING` should expect the passages to change with it.
EXAMPLE_WIND_BEARING = 165.0
EXAMPLE_WIND_SPEED = 6.0


def outfit(vessel, spec):
    """
    Give a hull everything her specification says she has.

    Args:
        vessel (Vessel): A freshly created hull.
        spec (dict): One entry from `CRAFT`.

    Returns:
        vessel (Vessel): The same hull, for chaining.

    Notes:
        Deliberately a function over data rather than a method or a subclass. A
        game's boats are its own, and the shortest honest answer to "how do I make
        one" is a dictionary and eight assignments - not a class hierarchy that has
        to be read before it can be copied.

    """
    vessel.db.desc = spec["desc"]
    vessel.length = spec["length"]
    vessel.beam = spec["beam"]
    vessel.light_draft = spec["draft"]
    vessel.windage = spec["windage"]
    vessel.motion_limits = spec["limits"]
    vessel.capacity = spec["capacity"]
    vessel.oar_plan = spec["oars"]

    if spec.get("air_draft"):
        vessel.air_draft = spec["air_draft"]
    if spec.get("sails"):
        vessel.polar_curve = PolarCurve()
        vessel.sail_plan = FURLED
    return vessel
