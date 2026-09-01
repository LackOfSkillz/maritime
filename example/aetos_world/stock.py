"""
What the people ashore actually sell.

Every counter in the world keeps between six and ten things, which is the number that makes
a shop feel like a shop. Four reads as a demonstration; thirty reads as a catalogue nobody
will page through.

**The stock is where a place says what it is.** A chandler and an apothecary could be
described in identical prose and still be told apart instantly by what is on their shelves,
so the lists do more characterisation than the room descriptions do - and they do it in a
form a player can act on rather than only read.

Each line is `(name, price, kind, description)`:

    name         what a player types, and matched on a leading substring
    price        in coin, and cheap - this is an example, not an economy
    kind         a loose tag: soft, strong, gear, food, cloth, physic, ship
    description  what the thing is when it is bought and looked at

**`kind` is how the world asks questions about a purchase without knowing the catalogue.**
Shore leave cares whether a drink was `soft` or `strong` and nothing else; a quest that
wanted somebody to fetch rope can ask for `ship` without listing every chandler's shelf. A
game adding its own goods keeps that working by reusing the tags.
"""

#: Drinks. Every island bar keeps the same list, because a chain of islands trading with one
#: harbour would - the bottles come off the same schooner. What differs between them is the
#: person behind the counter, which is what people remember anyway.
BAR_STOCK = (
    ("coconut water", 2, "soft", "Cut open in front of you, still cool from the shade."),
    ("lime and soda", 3, "soft", "Sharp enough to cut through a week of salt beef."),
    ("ginger beer", 3, "soft", "Cloudy, fierce, and brewed in somebody's back room."),
    ("small beer", 4, "soft", "Weak enough to drink all day, which is the point of it."),
    ("cane wine", 5, "strong", "Fermented from the pressings and about as rough."),
    ("island rum", 6, "strong", "Dark, and a good deal stronger than it tastes."),
    ("rum punch", 8, "strong", "Fruit, sugar and a great deal of rum, in a hollowed gourd."),
    ("bumbo", 9, "strong", "Rum, water, sugar and nutmeg. A sailor's drink and proud of it."),
    ("flip", 10, "strong", "Beer and rum with an iron heated in it, sweet and appalling."),
)

#: The chandler: everything a ship needs and nothing anybody else would want.
CHANDLERY_STOCK = (
    ("ball of spunyarn", 2, "ship", "Two strands laid up hard, for seizings and service."),
    ("marlinspike", 4, "ship", "A steel spike a hand and a half long, worn bright."),
    ("caulking iron", 5, "ship", "A blunt chisel for driving oakum into a seam."),
    ("hank of oakum", 3, "ship", "Picked hemp, tarred, smelling of every dock in the world."),
    ("single block", 7, "ship", "Elm shell, lignum sheave, greased and ready to reeve."),
    ("coil of ratline", 9, "ship", "Three-strand, tarred, enough to ratline down a shroud."),
    ("hand lead", 12, "ship", "Seven pounds of lead on a marked line, tallowed at the base."),
    ("horn lantern", 14, "ship", "Panes of scraped horn in a tin frame, for a binnacle."),
    ("bolt of canvas", 20, "cloth", "Number six duck, heavy enough for a working sail."),
    ("tar bucket", 6, "ship", "Stockholm tar in a wooden pail, with the brush stood in it."),
)

#: The fish market. Priced by what it takes to catch rather than what it tastes like.
FISH_STOCK = (
    ("salt cod", 3, "food", "A stiff dried slab, good for a year and terrible for a week."),
    ("smoked herring", 3, "food", "Strung through the gills in pairs, the colour of a penny."),
    ("fresh snapper", 6, "food", "Red-scaled and clear-eyed, landed within the hour."),
    ("grouper steak", 7, "food", "Cut thick off a fish that was bigger than the man who took it."),
    ("conch", 4, "food", "Prised out of the shell and beaten flat, which is the only way."),
    ("spiny lobster", 9, "food", "Alive and objecting, with its legs tied."),
    ("turtle meat", 11, "food", "Sold by the pound off the crawl, dark and fine-grained."),
    ("barrel of pickled fish", 18, "food", "A small cask, headed up and ready for a hold."),
)

#: The fruit stalls. What grows on this side of the island, and nothing that does not.
FRUIT_STOCK = (
    ("bunch of bananas", 2, "food", "Green at the top of the hand and going over at the bottom."),
    ("papaya", 2, "food", "Heavy for its size, and yielding under a thumb."),
    ("soursop", 3, "food", "Green and spined, and heavier than it has any right to be."),
    ("hand of plantains", 3, "food", "For cooking rather than eating raw, whatever anybody says."),
    ("string of limes", 3, "food", "Thin-skinned, and worth more at sea than they are here."),
    ("pineapple", 4, "food", "Cut with the crown left on, which is how you carry it."),
    ("mangoes", 4, "food", "Four of them in a twist of leaf, at the stage before they run."),
    ("coconuts", 3, "food", "Husked, so they can be stowed without taking up a locker."),
)

#: The provision stalls. This is the list a ship's cook arrives with.
PROVISION_STOCK = (
    ("sack of rice", 6, "food", "A hundredweight, double-sacked against the damp."),
    ("barrel of salt beef", 22, "food", "Packed in brine, and the pieces are not identified."),
    ("salt pork", 18, "food", "Better than the beef, and priced accordingly."),
    ("dried peas", 5, "food", "For pease pudding, which is what happens when the meat runs out."),
    ("sack of flour", 8, "food", "Stone-ground, with the weevils not yet arrived."),
    ("keg of molasses", 9, "food", "Thick, black, and the reason half the fleet sails."),
    ("salt", 4, "food", "Coarse, for the barrels rather than the table."),
    ("cask of water", 5, "food", "Filled from the cistern and headed up in front of you."),
    ("vinegar", 6, "food", "For the between-decks as much as for the food."),
)

#: The slop shop: sea clothes, ready made, in no particular size.
SLOP_STOCK = (
    ("duck trousers", 8, "cloth", "White canvas, cut wide, and stiff until they have been worn."),
    ("checked shirt", 7, "cloth", "Blue and white, of the sort every foremast hand owns."),
    ("guernsey", 12, "cloth", "Oiled wool, knitted close enough to turn a shower."),
    ("tarpaulin hat", 5, "cloth", "Canvas dipped in tar and dried hard over a block."),
    ("oilskin coat", 20, "cloth", "Stiff as a board and entirely waterproof, which is the trade."),
    ("sea boots", 18, "cloth", "Greased leather to the knee, with the soles double-nailed."),
    ("neckerchief", 3, "cloth", "For the sun, for the sweat, and for tying things up."),
    ("sailor's knife", 9, "gear", "A short blunt-tipped blade with a lanyard hole in the handle."),
    ("hammock", 14, "gear", "Number one canvas with the clews already turned in."),
)

#: The apothecary. Nothing here works miracles, and one or two of them work at all.
PHYSIC_STOCK = (
    ("bottle of lime juice", 6, "physic", "Against the scurvy, and it does actually answer."),
    ("quinine bark", 15, "physic", "Bitter enough to gag on, and the only thing for a fever."),
    ("laudanum", 18, "physic", "A small dark bottle with a very carefully written label."),
    ("basilicon ointment", 8, "physic", "For dressing a wound, in a screw-topped pot."),
    ("bandage roll", 3, "physic", "Boiled linen, wound tight, in a paper wrapper."),
    ("ginger root", 4, "physic", "Chewed for the seasickness, on the theory that it helps."),
    ("aloe leaf", 3, "physic", "Split open and laid on a burn, which does help."),
    ("tooth tincture", 7, "physic", "Clove oil and spirit, and the surgeon's alternative."),
)

#: The bakehouse. Mostly ship's bread, because that is what a port eats.
BAKEHOUSE_STOCK = (
    ("ship's biscuit", 3, "food", "Baked four times and hard enough to break a tooth on."),
    ("soft loaf", 2, "food", "Worth having on the day it is made and not after."),
    ("bag of rusks", 4, "food", "Twice-baked and small, for a boat rather than a hold."),
    ("cassava bread", 3, "food", "Flat, pale and faintly sour, and it keeps for ever."),
    ("bun with peel", 2, "food", "Sweet, sticky, and the reason for the queue."),
    ("sack of biscuit", 16, "food", "A hundredweight of the hard kind, for provisioning."),
    ("cornmeal pudding", 3, "food", "Steamed in a cloth and sold by the slice."),
)

#: The rum shop, which is not the tavern - this one sells by the cask to ships.
RUM_STOCK = (
    ("measure of rum", 4, "strong", "Drawn from the cask into whatever you brought."),
    ("bottle of rum", 10, "strong", "Corked and sealed, of the ordinary trade quality."),
    ("bottle of old rum", 22, "strong", "Eleven years kept, and he will tell you so."),
    ("jug of cane wine", 6, "strong", "Rough, cloudy, and drunk mostly by people who made it."),
    ("anker of rum", 40, "strong", "Ten gallons in a small cask, for a ship's spirit room."),
    ("bottle of shrub", 12, "strong", "Rum with citrus and sugar, kept for the passage home."),
    ("nutmegs", 5, "food", "For the bumbo, and worth more by weight than most cargo."),
)

#: The tavern. Food as much as drink, because it is where people eat.
TAVERN_STOCK = (
    ("mug of small beer", 2, "soft", "Cloudy and weak and served without being asked for."),
    ("cup of coffee", 3, "soft", "Boiled rather than brewed, and strong enough to stand a spoon."),
    ("rum punch", 8, "strong", "The house measure, which is not the same as anybody else's."),
    ("flip", 10, "strong", "Beer and rum with a hot iron plunged into it."),
    ("pepperpot", 6, "food", "A stew that has been on the fire longer than most of the customers."),
    (
        "fish and plantain",
        5,
        "food",
        "Fried together in the same pan, which is the correct method.",
    ),
    ("bowl of callaloo", 4, "food", "Greens cooked down with crab and a great deal of pepper."),
    ("bed for the night", 12, "gear", "A mattress in the upper room, shared, and no questions."),
)

#: The cooper, the smith and the sailmaker sell work as much as goods.
COOPER_STOCK = (
    ("small cask", 8, "ship", "Tight-headed, five gallons, and it will hold spirit."),
    ("water barrel", 14, "ship", "Bound with six hoops, charred inside to sweeten it."),
    ("hogshead", 26, "ship", "The big one, for sugar, and it takes two men to roll."),
    ("bundle of staves", 6, "ship", "Seasoned oak, cut to length and not yet raised."),
    ("iron hoops", 5, "ship", "A set of six, graded, for a cask of the ordinary size."),
    ("bung and spile", 2, "ship", "A stopper and the spike to make the hole for it."),
    ("cooper's adze", 16, "gear", "Curved, heavy, and worth more than it looks."),
)

SMITHY_STOCK = (
    ("boat nails", 3, "ship", "A pound of them, square-cut, in a twist of paper."),
    ("rudder pintle", 18, "ship", "Forged in one piece, and the gudgeon to match is extra."),
    ("iron hook", 6, "ship", "For a cargo sling, with the point turned in so it will not catch."),
    ("grapnel", 22, "ship", "Four arms, folding, on a ring - for a boat rather than a ship."),
    ("chain plate", 15, "ship", "Flat iron, drilled, for taking a shroud down to the hull."),
    ("hatchet", 9, "gear", "Short-handled, for a boat's kit, with an edge already on it."),
    ("fire steel", 3, "gear", "A curl of hardened steel, sold with a flint."),
    ("bar of iron", 11, "ship", "Stock, for whatever the smith is told to make of it."),
)

SAILMAKER_STOCK = (
    ("sail needles", 3, "ship", "A paper of six, triangular in section, and very sharp."),
    ("sailmaker's palm", 7, "gear", "Leather, with an iron eye set in it to drive the needle."),
    ("beeswax", 2, "ship", "A block of it, for running the twine through."),
    ("ball of twine", 4, "ship", "Waxed, for roping and for seaming."),
    ("bolt rope", 12, "ship", "Soft-laid, for sewing round the edge of a sail."),
    ("set of cringles", 9, "ship", "Iron thimbles, worked round, ready to be stitched in."),
    ("storm trysail", 45, "ship", "Small, heavy and hideous, and it will save a ship."),
    ("awning", 24, "cloth", "Light duck with roping and eyes, for lying in harbour."),
)


#: Where each counter is, who keeps it, and what they say when somebody walks in.
#:
#: Keyed by the room's own name, so adding a shop means adding a room and a line here and
#: nothing else. A room that names no vendor simply has nobody in it, which is the right
#: default for a bond store.
VILLAGE_VENDORS = {
    "The Chandlery": {
        "key": "Bram",
        "desc": (
            "A heavy, unhurried man with a pencil behind his ear and tar worked so far "
            "into his hands that it no longer comes out. He knows where everything is and "
            "will not let you find it yourself."
        ),
        "greeting": "'Tell me what she needs,' says Bram, 'not what you think it's called.'",
        "stock": CHANDLERY_STOCK,
    },
    "The Fish Market": {
        "key": "Sella",
        "desc": (
            "Forearms like a rower's and a knife she never seems to put down. She works "
            "while she talks and the talking does not slow the work."
        ),
        "greeting": "Sella does not look up. 'Say what you want, I'm listening.'",
        "stock": FISH_STOCK,
    },
    "The Fruit Stalls": {
        "key": "Odette",
        "desc": (
            "An old woman on a stool behind a stall she has kept for fifty years, with a "
            "hat against the sun and a fan she uses on the flies more than herself."
        ),
        "greeting": "'Taste it first,' says Odette, holding something out. 'Go on.'",
        "stock": FRUIT_STOCK,
    },
    "The Provision Stalls": {
        "key": "Kabu",
        "desc": (
            "Broad and deliberate, in an apron gone stiff with salt. He weighs everything "
            "twice - once for you and once for himself - and rounds in your favour."
        ),
        "greeting": "'Provisioning?' says Kabu. 'How many, and how long for?'",
        "stock": PROVISION_STOCK,
    },
    "The Slop Shop": {
        "key": "Merrit",
        "desc": (
            "A small sharp woman with pins in her cuff, who sizes a customer by eye on the "
            "way through the door and is not often wrong."
        ),
        "greeting": "Merrit looks you over. 'Nothing here will fit. It never does.'",
        "stock": SLOP_STOCK,
    },
    "The Apothecary": {
        "key": "Doctor Aleyn",
        "desc": (
            "Thin, precise, and dressed better than anybody else on the ridge. He is not a "
            "physician and corrects anybody who calls him one, but he is what the town has."
        ),
        "greeting": "'Describe it,' says Aleyn, 'in your own words, and take your time.'",
        "stock": PHYSIC_STOCK,
    },
    "The Bakehouse": {
        "key": "Nan Poll",
        "desc": (
            "Floured to the elbow and permanently too warm, working with her sleeves pushed "
            "up and her hair tied out of the way. She has been awake since two."
        ),
        "greeting": "'Soft or hard?' says Nan Poll. 'Soft's for today, hard's for the voyage.'",
        "stock": BAKEHOUSE_STOCK,
    },
    "The Rum Shop": {
        "key": "Cutter",
        "desc": (
            "A lean man with a ledger he guards more carefully than the casks, serving "
            "through the hatch without ever quite coming out from behind it."
        ),
        "greeting": "'By the measure or by the cask?' says Cutter. 'There's a difference.'",
        "stock": RUM_STOCK,
    },
    "The Wrecker's Arms": {
        "key": "Ma Ravel",
        "desc": (
            "She keeps the house from a chair by the end of the counter and gets up for "
            "almost nothing. Everyone in the room is aware of exactly where she is."
        ),
        "greeting": "'Sit where you like,' says Ma Ravel, 'except that table. That's spoken for.'",
        "stock": TAVERN_STOCK,
    },
    "The Cooperage": {
        "key": "Hask",
        "desc": (
            "Deaf in one ear from forty years of hammering hoops, and talks accordingly. "
            "His forearms are the argument for his prices."
        ),
        "greeting": "'WHAT SIZE,' says Hask, at a volume that carries into the lane.",
        "stock": COOPER_STOCK,
    },
    "The Smithy": {
        "key": "Enna",
        "desc": (
            "Short, scarred across both forearms, and entirely unbothered by the heat. She "
            "finishes the piece she is on before she looks up, every time."
        ),
        "greeting": "Enna sets down the hammer. 'Right. What's broken?'",
        "stock": SMITHY_STOCK,
    },
    "The Sail Loft": {
        "key": "Vance",
        "desc": (
            "He works kneeling on the floor with the canvas spread round him, and stands up "
            "in stages. There is a palm on his hand that he has not taken off in years."
        ),
        "greeting": "'Mind the canvas,' says Vance, without heat. 'Walk round, not across.'",
        "stock": SAILMAKER_STOCK,
    },
}


def village_vendor_for(room_key):
    """
    Args:
        room_key (str): A room's name.

    Returns:
        spec (dict or None): Who keeps that counter, or None if nobody does.

    """
    return VILLAGE_VENDORS.get(room_key)


__all__ = (
    "BAR_STOCK",
    "CHANDLERY_STOCK",
    "FISH_STOCK",
    "FRUIT_STOCK",
    "PROVISION_STOCK",
    "SLOP_STOCK",
    "PHYSIC_STOCK",
    "BAKEHOUSE_STOCK",
    "RUM_STOCK",
    "TAVERN_STOCK",
    "COOPER_STOCK",
    "SMITHY_STOCK",
    "SAILMAKER_STOCK",
    "VILLAGE_VENDORS",
    "village_vendor_for",
)
