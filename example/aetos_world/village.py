"""
Careenage, the town at the head of the harbour.

Fifty-odd rooms of ordinary Evennia land, built to show how a walkable place sits inside a
maritime world without either half knowing much about the other. Three rooms of it stand at
real coordinates and have berths; the rest are rooms like rooms anywhere.

**The shape has a reason, because a shape without one reads as designed.** Careenage is long
and thin. It is pinned between the dredged basin on one side and the tidal creek on the
other, and the ground behind it rises into cane, so it grew the only way it could - a single
waterfront street with short lanes climbing off it to a road along the ridge. Nobody laid it
out. You walk along it rather than around it because there is nowhere else to go.

    the Strand      the waterfront, and everything working happens on it
    three piers     570 to 830 metres, because the shore shelves that gently
    the lanes       four of them, climbing inland off the Strand
    Ridge Road      the top of the town, and the road out
    the creek       where a boat coming downriver arrives

**The piers are long because the ground says so.** The beach here shelves so gently that six
metres of water is most of a kilometre out, which is precisely why somebody dredged a basin
and built piers to reach it. A quay on the sand would have nothing alongside it. The lengths in the
prose were measured against the shipped soundings rather than chosen.

**House rules, followed throughout.** Buildings are entered by their own noun and left by
`OUT` - `GO CHANDLERY`, not `GO EAST` - because north is a direction across open ground and
not the act of opening a door. Every description holds only what is permanently true: no
light, no weather, no passers-by, nothing that makes the room lie when it is read at
midnight in a storm. What a place trades in is named on the *street*, not only inside it,
because a sign you can only read once you are already through the door invites nobody.
"""

from ...ports import Berth
from ...position import WorldPosition

#: The town's own name, used in room keys so a game running several worlds can tell them
#: apart at a glance.
TOWN = "Careenage"

#: Where the waterfront stands, in world metres, and which way the shore runs.
#:
#: Found by walking inland from the dredged basin until the ground stood a clear metre above
#: spring high water, rather than by picking a point near the shore. The first attempt put
#: the Strand at eight centimetres above datum - which is not a waterfront, it is a tidal
#: flat, and the whole town would have been ankle-deep twice a day. A town is built above the
#: tide because the people who built it had to live in it.
SHORE = (2745.0, 63.0)
ALONGSHORE_DEG = 315.0
SEAWARD_DEG = 225.0

#: The three berths, as metres seaward of the waterfront and metres along it.
#:
#: **The seaward figures are what the soundings demanded, not what sounded reasonable.** From
#: a waterfront standing safely above the tide, this beach wants 570 metres of pier for three
#: metres of water, 650 for four and 830 for six. Those are long piers, and they are long for
#: a reason that is visible on the chart: the shore shelves so gently that anything shorter
#: would have a ship sitting on the putty. It is also exactly why somebody dredged a basin.
#:
#: An earlier draft guessed 350 and 500 and put the Long Pier four tenths of a metre short of
#: its own advertised depth - which would have been a berth that grounded the vessels it was
#: built for, and nothing would have said so until one sat down on it.
PIERS = (
    {
        "key": "Long Pier",
        "out": 830.0,
        "along": 120.0,
        "draft": 6.0,
        "length": 60.0,
        "beam": 16.0,
        "desc": (
            "Eight hundred metres of piling and plank, built out to where the dredgers "
            "stopped and there is water enough for anything that floats. It is wide enough "
            "for two carts to pass and does not quite manage to be straight. Iron bollards "
            "the size of barrels stand along both edges, and a crane of black timber leans "
            "over the head of it on a stone footing."
        ),
    },
    {
        "key": "Middle Pier",
        "out": 650.0,
        "along": -40.0,
        "draft": 4.0,
        "length": 30.0,
        "beam": 9.0,
        "desc": (
            "Shorter and lower than its neighbour, and busier for it - this is where the "
            "island traders lie, close enough to the Strand that a cargo can be carried "
            "ashore on a shoulder instead of waiting on a cart. The planks are patched in "
            "a dozen colours of timber where they have been replaced one at a time."
        ),
    },
    {
        "key": "The Careening Hard",
        "out": 570.0,
        "along": -220.0,
        "draft": 3.0,
        "length": 24.0,
        "beam": 8.0,
        "desc": (
            "A stone slipway running down into the harbour, with a pair of massive posts "
            "at the head of it and tackle enough to heave a small vessel over on her side. "
            "The stone is green below the tide line and worn into a trough down the middle "
            "where keels have been dragged over it. The whole place smells of tar."
        ),
    },
)

#: The waterfront, north-west to south-east. The Strand is the town's spine and everything
#: else hangs off it.
STRAND = (
    {
        "key": "Netloft Row",
        "desc": (
            "The waterfront runs out here into a litter of hauled-up boats and drying "
            "nets on frames. A low wall of coral block keeps the road out of the water, "
            "and beyond it the mud of the creek mouth begins. The town is all to the "
            "south from here."
        ),
    },
    {
        "key": "Quay Head",
        "desc": (
            "The broadest part of the waterfront, kept clear so that carts can turn. The "
            "Long Pier runs out into the harbour from a gap in the sea wall, and the "
            "harbourmaster's office stands opposite it with a slate outside listing what "
            "lies at which berth."
        ),
    },
    {
        "key": "Fore Street",
        "desc": (
            "A stretch of the waterfront where the buildings stand closest to the water. "
            "The Custom House takes up most of the landward side, a squat stone thing with "
            "barred windows and a scale on a bracket by the door, and there is a queue "
            "outside it more often than not."
        ),
    },
    {
        "key": "Capstan Walk",
        "desc": (
            "Cargo country. The road is half blocked with whatever came off the last "
            "trader - crates, casks, coils of cordage - stacked in rows with chalk marks "
            "on them and a tally-clerk's stool set where it can see the lot. The Middle "
            "Pier goes out from here, and the chandlery faces it across the road."
        ),
    },
    {
        "key": "Fishgut Row",
        "desc": (
            "The paving is scrubbed pale here and slopes to a gutter that runs down to the "
            "harbour. The fish market opens onto the road under a long tiled roof, and a "
            "row of stone slabs stands out front, worn hollow in the middle from a hundred "
            "years of gutting."
        ),
    },
    {
        "key": "The Hard",
        "desc": (
            "The waterfront narrows and turns inland here, pinched between the water and "
            "the first of the cane. The Careening Hard runs down into the harbour on the "
            "seaward side, and the boatyard's fence begins where the road bends inland."
        ),
    },
)

#: The lanes climbing off the Strand. Each is a short spur, and each opens onto something.
LANES = (
    {
        "key": "Cooper's Lane",
        "from": "Quay Head",
        "desc": (
            "A steep lane of packed coral rubble, wide enough for one cart and not two. "
            "The cooperage takes up the whole of one side, open to the lane so that the "
            "work can be seen from it, and the other side is the blank wall of a bond "
            "store with no windows at all."
        ),
    },
    {
        "key": "Ropewalk Lane",
        "from": "Fore Street",
        "desc": (
            "The lane runs alongside the ropewalk, which is a shed so long and so narrow "
            "that it looks like a mistake. Loose fibres of hemp collect against the walls "
            "and in the gutters, and the whole lane smells of tar."
        ),
    },
    {
        "key": "Sailmaker's Lane",
        "from": "Capstan Walk",
        "desc": (
            "A quiet lane with a gutter down the middle of it, climbing between high "
            "walls. The sail loft is above the chandlery here, reached by an outside "
            "stair, and its long windows are set high to catch as much light as the "
            "island will give them."
        ),
    },
    {
        "key": "Canecutter's Lane",
        "from": "The Hard",
        "desc": (
            "The last of the lanes, and the roughest. It climbs out of the town between "
            "the boatyard fence and a bank of red earth, and the cane begins where the "
            "walls give out. Cart ruts are cut deep into it."
        ),
    },
)

#: The upper town, along the ridge. This is where a place stops being a working waterfront
#: and starts being somewhere people live.
RIDGE = (
    {
        "key": "High Row",
        "desc": (
            "The road along the top of the town, level for once after all that climbing. "
            "From the seaward side there is nothing between here and the harbour but "
            "roofs. The mission stands on the inland side behind a low wall."
        ),
    },
    {
        "key": "The Cross",
        "desc": (
            "The widest part of the ridge, where the road opens into the market square. "
            "A stone cistern stands at the centre with a bucket chained to it, and the "
            "ground around it is worn to hard bare earth by the traffic of a market day."
        ),
    },
    {
        "key": "Beacon Road",
        "desc": (
            "The road runs on east here and turns into the track that leaves town. The "
            "last buildings are on the seaward side only; inland is cane to the top of "
            "the rise. A milestone stands at the corner with its figures worn away."
        ),
    },
    {
        "key": "Market Square",
        "desc": (
            "An open square of hard-packed earth with a ring of stone benches round its "
            "edge and a great tree in the middle, its roots lifting the paving in slabs. "
            "Stalls stand along two sides on permanent frames of lashed timber. The "
            "tavern is on the third side and the mission's wall makes the fourth."
        ),
    },
    {
        "key": "The Fruit Stalls",
        "desc": (
            "The north side of the square, under a roof of thatch on posts. The stalls "
            "are permanent - scrubbed boards on trestles, each with its owner's mark burnt "
            "into the end - and the ground beneath them is soft with a century of trodden "
            "peel."
        ),
    },
    {
        "key": "The Provision Stalls",
        "desc": (
            "Salt meat, hard bread, dried beans and rice, in sacks and barrels under a "
            "shared awning. This is where a ship's cook comes with a list, and the prices "
            "are chalked on a board at the end so that nobody has to ask."
        ),
    },
)

#: The upper lanes, where people live rather than work. Deliberately plainer than the
#: waterfront: a town is mostly houses, and a place where every room is a landmark is a
#: theme park rather than somewhere anybody lives.
UPPER = (
    {
        "key": "Mizzen Row",
        "desc": (
            "A row of small houses with deep verandas, each raised a course or two of "
            "block off the ground. The road is unpaved and edged with whitewashed stones, "
            "and every house has a water butt at its corner under the roof's downpipe."
        ),
    },
    {
        "key": "Gullcry Steps",
        "desc": (
            "The houses run out here into garden plots fenced with cane, growing peppers "
            "and pumpkins and a few stands of banana. A footpath continues where the road "
            "gives up."
        ),
    },
    {
        "key": "The Gut",
        "desc": (
            "A narrow alley between two blocks, barely a shoulder's width, running through "
            "from Palm Row to the ridge. The walls on both sides are blank and the ground "
            "underfoot is a single worn channel of rock."
        ),
    },
    {
        "key": "The Burying Ground",
        "desc": (
            "A walled enclosure on the seaward slope, the stones set in rows facing the "
            "water. Many of the markers carry a ship's name under the person's, and a good "
            "number carry no date of death at all - only the year she was last spoken."
        ),
    },
    {
        "key": "The Signal Path",
        "desc": (
            "A steep zigzag of steps cut into the hillside above the town, with a handrail "
            "of tarred rope on iron stanchions. It exists to get one person to the top "
            "quickly and is no use for anything else."
        ),
    },
    {
        "key": "The Signal Station",
        "desc": (
            "The highest point above the town: a stone hut and a mast with a yard across "
            "it, rigged with halliards for hoisting shapes and flags. A locker beside the "
            "door holds the balls and cones, and a board inside lists what each hoist "
            "means. The whole approach lies open from here."
        ),
    },
)

#: The road out of town, and the working ground behind the waterfront.
OUTSKIRTS = (
    {
        "key": "Dunnage Lane",
        "desc": (
            "A back lane serving the rear doors of the waterfront stores, wide enough for "
            "a cart and stacked along both sides with dunnage and empty crates. Every door "
            "along it is numbered in painted figures a foot high."
        ),
    },
    {
        "key": "Bollard Steps",
        "desc": (
            "A flight of stone steps going down into the harbour between two warehouses, "
            "with an iron ring at the head and another halfway down. Small boats come "
            "alongside here to land people rather than cargo. The lower steps are green."
        ),
    },
    {
        "key": "Fisherman's Beach",
        "desc": (
            "A shelf of coarse sand north of the town where the small boats are drawn up "
            "clear of the water, each on its own set of rollers. Racks of split timber "
            "stand above the tide line for drying nets on."
        ),
    },
    {
        "key": "The Turtle Crawl",
        "desc": (
            "A pen of stakes driven into the shallows and fenced with cane, big enough to "
            "hold a dozen turtles alive until they are wanted. A plank walkway runs out to "
            "it from the beach on trestles."
        ),
    },
    {
        "key": "Millway",
        "desc": (
            "The road out of town, climbing between banks of red earth cut deep by the "
            "carts. Cane stands taller than a rider on both sides, and the road is only "
            "wide enough for one vehicle, with passing places cut at intervals."
        ),
    },
    {
        "key": "The Elbow",
        "desc": (
            "The road turns sharply here around a shoulder of rock too hard to cut "
            "through. A stone trough stands at the inside of the bend, fed by a pipe from "
            "somewhere up the hill, for watering animals on the climb."
        ),
    },
    {
        "key": "Boiling House Lane",
        "desc": (
            "A spur off the main road running to the sugar mill, rutted and dusted white "
            "with spilled lime. The mill stands at the end of it with its roof visible "
            "over the cane, and the road is built wide because the carts that use it are."
        ),
    },
    {
        "key": "Anchor Court",
        "desc": (
            "A dead end off Fore Street, three sides of blank wall around a square of "
            "broken paving with a standpipe in the middle of it. An anchor too badly "
            "sprung to be worth repairing stands upended in the corner, which is where "
            "the court got its name and how everybody finds it."
        ),
    },
    {
        "key": "Windlass Steps",
        "desc": (
            "A flight of stone steps cutting straight up the hill between the backs of "
            "two rows of houses, too narrow and too steep for anything on wheels. It "
            "saves a quarter of a mile and costs a set of lungs, and everybody in a hurry "
            "uses it anyway."
        ),
    },
)

#: Everything reached from the creek side. This is the road a boat coming downriver walks
#: into town on, and it is deliberately at the far end from the piers.
CREEK = (
    {
        "key": "The Creek Landing",
        "desc": (
            "A shelving hard of rammed coral at the creek mouth, with a row of rings set "
            "into it for painters. Small craft are drawn up above the tide mark in a line, "
            "bottom-up, and a footpath goes up the bank into the town. The creek runs away "
            "inland from here between banks of mangrove."
        ),
    },
    {
        "key": "Mangrove Walk",
        "desc": (
            "A footpath between the creek and the backs of the northern houses, raised on "
            "a bank of dumped ballast stone to keep it out of the water. The mangroves "
            "come right up to the far side of it."
        ),
    },
    {
        "key": "The Boatyard",
        "desc": (
            "An open yard behind a fence of split cane, with two building slips running "
            "down toward the water and a shed at the back full of timber in stacks. A "
            "half-planked hull stands on the nearer slip, ribs bare, and there is sawdust "
            "trodden into everything."
        ),
    },
)

#: Interiors. Each is entered from a street room by the noun in its own name, and left by
#: `OUT`, which is the house rule and also how a door works.
INTERIORS = (
    {
        "key": "The Harbourmaster's Office",
        "from": "Quay Head",
        "noun": "office",
        "desc": (
            "One room with a high desk, a wall of pigeonholes stuffed with papers, and a "
            "chart of the approaches pinned up so long that it has gone the colour of "
            "tea. A slate by the door lists the berths and what is lying at them."
        ),
    },
    {
        "key": "The Custom House",
        "from": "Fore Street",
        "noun": "custom house",
        "desc": (
            "A stone room built to be difficult to rob: barred windows, one door, and a "
            "strongbox let into the floor under a flagstone that everybody knows about. A "
            "long counter divides it, with the public on one side and the ledgers on the "
            "other."
        ),
    },
    {
        "key": "The Chandlery",
        "from": "Capstan Walk",
        "noun": "chandlery",
        "desc": (
            "Everything a ship needs and nothing anybody else would want, stacked to the "
            "ceiling on shelves reached by a ladder on a rail. Blocks, cordage, canvas, "
            "lamp oil, nails by the keg, and a smell of tar and hemp that gets into "
            "clothes."
        ),
    },
    {
        "key": "The Fish Market",
        "from": "Fishgut Row",
        "noun": "market",
        "desc": (
            "A long shed open at both ends, floored in stone and sloped to drain. Slabs "
            "run down both sides under a roof high enough to keep the heat off, and there "
            "is a well at the far end with a rope worn into a groove over its rim."
        ),
    },
    {
        "key": "The Cooperage",
        "from": "Cooper's Lane",
        "noun": "cooperage",
        "desc": (
            "Staves in bundles, hoops in stacks by size, and three fire pits down the "
            "middle of the floor for raising the barrels. Finished casks stand along the "
            "back wall in a row, each with the cooper's mark burnt into the head."
        ),
    },
    {
        "key": "The Ropewalk",
        "from": "Ropewalk Lane",
        "noun": "ropewalk",
        "desc": (
            "A shed a hundred and fifty metres long and four wide, because that is what "
            "making rope requires. The spinning gear stands at this end and the far end "
            "is lost in the dimness. Hemp hangs in hanks from pegs along the whole length "
            "of one wall."
        ),
    },
    {
        "key": "The Sail Loft",
        "from": "Sailmaker's Lane",
        "noun": "loft",
        "desc": (
            "One enormous room with a floor of pale scrubbed planking, empty of furniture "
            "so that a sail can be spread flat on it. Bolts of canvas stand on end against "
            "the walls, and the long windows are set high on both sides."
        ),
    },
    {
        "key": "The Smithy",
        "from": "High Row",
        "noun": "smithy",
        "desc": (
            "Open on one side to let the heat out, with a hearth and a great leather "
            "bellows at the back and an anvil set on a section of tree trunk sunk into the "
            "floor. Ironwork for ships hangs on the walls in sizes: rudder pintles, "
            "chainplate, hooks and rings."
        ),
    },
    {
        "key": "The Mission",
        "from": "High Row",
        "noun": "mission",
        "desc": (
            "A plain whitewashed room with benches and no ornament except the ship models "
            "hanging from the beams, a dozen of them, each given by a crew that came home. "
            "The floor is stone and the door stands open."
        ),
    },
    {
        "key": "The Bond Store",
        "from": "Cooper's Lane",
        "noun": "store",
        "desc": (
            "A stone room with one door and no window, where cargo sits under seal until "
            "the duty on it is paid. Casks are stacked three high in numbered bays, each "
            "with a customs mark chalked on the head, and there is a second lock on the "
            "inside of the door as well as the outside."
        ),
    },
    {
        "key": "The Sugar Store",
        "from": "Fore Street",
        "noun": "sugar store",
        "desc": (
            "A great open shed with its floor raised on brick piers to keep the damp out "
            "of the hogsheads. They stand in ranks the length of it, and the boards "
            "underfoot are dark and slightly tacky where a century of molasses has soaked "
            "in."
        ),
    },
    {
        "key": "The Slop Shop",
        "from": "Fishgut Row",
        "noun": "slop shop",
        "desc": (
            "Sea clothes, ready made and sold off the shelf: duck trousers, tarred hats, "
            "guernseys, oilskins stiff as boards. Everything hangs from the beams on pegs "
            "so it can be seen at a glance, and none of it is any particular size."
        ),
    },
    {
        "key": "The Rum Shop",
        "from": "Market Square",
        "noun": "rum shop",
        "desc": (
            "One room with a counter across the doorway rather than inside it, so the "
            "trade is served standing in the square. Casks are racked behind on cradles, "
            "each chalked with what it holds and where it came from."
        ),
    },
    {
        "key": "The Bakehouse",
        "from": "The Cross",
        "noun": "bakehouse",
        "desc": (
            "A brick oven the size of a small room takes up one whole wall, with peels as "
            "long as oars leaning beside it. Racks of shelves stand along the other walls "
            "for ship's bread to dry on, which is what most of the output here is for."
        ),
    },
    {
        "key": "The Apothecary",
        "from": "Beacon Road",
        "noun": "apothecary",
        "desc": (
            "A narrow room lined floor to ceiling with drawers, each labelled in a small "
            "neat hand. A counter runs across the back with a set of scales on it under a "
            "glass cover, and bunches of dried plants hang from a rail below the ceiling."
        ),
    },
    {
        "key": "The Watch House",
        "from": "Market Square",
        "noun": "watch house",
        "desc": (
            "A single room with a bench, a table, and a rack of staves by the door. A "
            "barred cell takes up the back third of it behind a grille, furnished with a "
            "plank bed and nothing else at all."
        ),
    },
    {
        "key": "The Sugar Mill",
        "from": "Boiling House Lane",
        "noun": "mill",
        "desc": (
            "A stone tower with a boiling house attached, the rollers standing idle in the "
            "middle of the floor between their timber frames. The coppers are set in a row "
            "over a single long furnace, largest first, and the whole building smells of "
            "burnt sugar."
        ),
    },
    {
        "key": "The Wrecker's Arms",
        "from": "Market Square",
        "noun": "tavern",
        "desc": (
            "A long low room with a floor of beaten earth and a counter down one side made "
            "from a ship's plank, curve and all. Tables stand under the shuttered windows, "
            "and the beam over the counter is carved with the names of vessels that never "
            "came back - which is where the house got its name, and the joke is older than "
            "anybody drinking here."
        ),
    },
)

#: Where a new character wakes up. Inland and upstream, on purpose: the tutorial begins on
#: the pond with a paddle, and the town is what a player arrives at rather than starts in.
STARTING_ROOM = "The Creek Landing"


def bearing_offset(bearing_deg, metres):
    """
    Args:
        bearing_deg (float): Degrees true.
        metres (float): How far.

    Returns:
        offset (tuple): `(east, north)` in metres.

    """
    import math

    radians = math.radians(bearing_deg)
    return (math.sin(radians) * metres, math.cos(radians) * metres)


def pier_position(pier):
    """
    Where a pier's head stands, in world metres.

    Args:
        pier (dict): One entry from `PIERS`.

    Returns:
        position (WorldPosition): The berth.

    Notes:
        Measured out from the waterfront rather than typed as a coordinate, so the three
        piers stay in line with each other and with the shore if the town is ever moved.

    """
    out_e, out_n = bearing_offset(SEAWARD_DEG, pier["out"])
    along_e, along_n = bearing_offset(ALONGSHORE_DEG, pier["along"])
    return WorldPosition(SHORE[0] + out_e + along_e, SHORE[1] + out_n + along_n)


#: How much water a berth keeps under a hull beyond her draught, in metres. A berth that
#: advertised exactly what was there would put her on the bottom at low water springs.
BERTH_CLEARANCE = 0.5


def berth_for(pier, world=None):
    """
    Args:
        pier (dict): One entry from `PIERS`.
        world (MaritimeMapProvider, optional): The ground. Given one, the berth advertises
            what is actually under it rather than what was authored.

    Returns:
        berth (Berth): Where a hull lies, and what will fit.

    Notes:
        **The depth is measured, not asserted.** Authored, the Long Pier promised six metres
        and had five point eight-eight - a berth that would have grounded the vessels it was
        built for, saying nothing until one of them sat down on it. The failure is quiet
        because a berth is a promise about water nobody checks.

        So where the world is available the advertised draught is whatever is really there,
        less a little, and the authored figure becomes a ceiling rather than a claim. A pier
        can then never offer water it does not have, however the ground is later rebuilt.

    """
    position = pier_position(pier)
    draft = float(pier["draft"])
    if world is not None:
        under = -world.terrain_z_at(position)
        draft = min(draft, max(0.0, under - BERTH_CLEARANCE))
    return Berth(
        key=pier["key"].lower().replace(" ", "_").replace("'", ""),
        position=position,
        heading=ALONGSHORE_DEG,
        max_length=pier["length"],
        max_beam=pier["beam"],
        max_draft=draft,
    )


def rooms(world=None):
    """
    Every room in the town.

    Args:
        world (MaritimeMapProvider, optional): The ground, so berths advertise real water.

    Returns:
        specs (list): Room specifications; the ones with a berth become `PortRoom`.

    """
    out = []
    for pier in PIERS:
        out.append({"key": pier["key"], "desc": pier["desc"], "berth": berth_for(pier, world)})
    out.extend(dict(spec) for spec in STRAND)
    out.extend({"key": lane["key"], "desc": lane["desc"]} for lane in LANES)
    out.extend(dict(spec) for spec in RIDGE)
    out.extend(dict(spec) for spec in UPPER)
    out.extend(dict(spec) for spec in OUTSKIRTS)
    out.extend(dict(spec) for spec in CREEK)
    out.extend({"key": inside["key"], "desc": inside["desc"]} for inside in INTERIORS)
    return out


def paths():
    """
    Every exit, in both directions.

    Returns:
        paths (tuple): `(from, to, out, back)`.

    Notes:
        Both directions are written out rather than left to be inferred. An importer that
        invents the missing half is being kind, and the kindness hides the mistake.

        Streets join by compass; buildings join by their noun. That is the difference
        between walking along a road and going through a door, and the exit line should say
        which is which without anybody having to guess.

    """
    joined = []

    # The Strand, north to south.
    for nearer, further in zip(STRAND, STRAND[1:]):
        joined.append((nearer["key"], further["key"], "south", "north"))

    # The piers run seaward off the Strand, and are named rather than compassed - a pier is
    # a structure you walk out onto.
    joined.append(("Quay Head", "Long Pier", "pier", "shore"))
    joined.append(("Capstan Walk", "Middle Pier", "pier", "shore"))
    joined.append(("The Hard", "The Careening Hard", "hard", "shore"))

    # The lanes climb inland off the Strand and come out on the ridge.
    #
    # **Two of them come out on High Row**, and naming both ends `up` and `down` gave that
    # one room two exits called `down` - one to each lane. Evennia takes the first, so the
    # second lane could not be walked down at all, by clicking or by typing, and nothing
    # said so. A room cannot have two downs any more than it can have two norths.
    #
    # So the second and later arrivals at a ridge are named for the lane they descend. That
    # is what a person would say anyway - "take the ropewalk down" - and it scales: adding
    # a fifth lane to an existing ridge cannot quietly break the fourth.
    landed = {}
    for lane, ridge in zip(LANES, ("High Row", "High Row", "The Cross", "Beacon Road")):
        joined.append((lane["from"], lane["key"], "up", "down"))
        arrivals = landed.setdefault(ridge, 0)
        landed[ridge] = arrivals + 1
        down = "down" if not arrivals else lane["key"].split("'")[0].split()[0].lower()
        joined.append((lane["key"], ridge, "up", down))

    # Ridge Road, and the square hanging off the middle of it - the centre, not one room
    # along, or the whole upper town leans.
    joined.append(("High Row", "The Cross", "east", "west"))
    joined.append(("The Cross", "Beacon Road", "east", "west"))
    joined.append(("The Cross", "Market Square", "square", "road"))
    joined.append(("Market Square", "The Fruit Stalls", "north", "south"))
    joined.append(("Market Square", "The Provision Stalls", "east", "west"))

    # The creek side, which is where somebody coming downriver arrives.
    joined.append(("The Creek Landing", "Mangrove Walk", "south", "north"))
    joined.append(("Mangrove Walk", "Netloft Row", "south", "north"))
    joined.append(("The Hard", "The Boatyard", "yard", "out"))

    # The upper lanes hang off the *middle* of the ridge rather than one room along it.
    # Checked by mirroring rather than by midpoint: a row with the right midpoint can still
    # be lopsided, and the whole upper town leans if it is.
    joined.append(("Beacon Road", "Mizzen Row", "north", "south"))
    joined.append(("Mizzen Row", "Gullcry Steps", "east", "west"))
    joined.append(("Mizzen Row", "The Gut", "gut", "row"))
    joined.append(("The Gut", "The Cross", "south", "gut"))
    joined.append(("High Row", "The Burying Ground", "west", "east"))
    joined.append(("The Cross", "The Signal Path", "up", "down"))
    joined.append(("The Signal Path", "The Signal Station", "up", "down"))

    # Behind the waterfront, and the road out of town.
    joined.append(("Fore Street", "Dunnage Lane", "east", "west"))
    joined.append(("Dunnage Lane", "Bollard Steps", "steps", "up"))
    # A noun, because Netloft Row already goes north to Mangrove Walk and a row cannot have
    # two norths - which it did, so the beach was unreachable from it however you asked.
    # Stepping off a row onto a beach is a thing you do sideways anyway, not a street you
    # walk along.
    joined.append(("Netloft Row", "Fisherman's Beach", "beach", "row"))
    joined.append(("Fisherman's Beach", "The Turtle Crawl", "crawl", "beach"))
    joined.append(("Beacon Road", "Millway", "east", "west"))
    joined.append(("Millway", "The Elbow", "east", "west"))
    joined.append(("The Elbow", "Boiling House Lane", "north", "south"))

    # Two pieces that keep the town off a grid. A court is a dead end - it goes nowhere,
    # which is exactly why a place that grew has them and a place that was drawn does not.
    # The steps are a short cut that skips the ridge road entirely, so there is more than
    # one way up and they are not the same length.
    joined.append(("Fore Street", "Anchor Court", "court", "out"))
    joined.append(("Capstan Walk", "Windlass Steps", "steps", "down"))
    joined.append(("Windlass Steps", "Mizzen Row", "up", "steps"))

    # Buildings, by their own noun.
    for inside in INTERIORS:
        joined.append((inside["from"], inside["key"], inside["noun"], "out"))

    return tuple(joined)


__all__ = (
    "TOWN",
    "SHORE",
    "PIERS",
    "STRAND",
    "LANES",
    "RIDGE",
    "UPPER",
    "OUTSKIRTS",
    "CREEK",
    "INTERIORS",
    "STARTING_ROOM",
    "pier_position",
    "BERTH_CLEARANCE",
    "berth_for",
    "rooms",
    "paths",
)
