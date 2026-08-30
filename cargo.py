"""
Cargo: weight, volume, and which of the two runs out first.

A hold has two capacities and they are not interchangeable. One is the mass the hull can
carry before she is too deep; the other is the space the cargo occupies. Which one binds
depends entirely on what you are carrying, and the whole trade is in that:

    stowage factor    cubic metres one tonne of a thing occupies
    weighs out        the mass ran out first - iron, salt, shot
    cubes out         the space ran out first - wool, hay, empty casks
    broken stowage    the space between irregular packages, which is wasted

Iron ore stows at about 0.4 m³ a tonne and wool at nearly 4. A hull that fills with ore
still has most of her volume empty, and one full of wool is barely down on her marks.
Charging by the tonne for one and by the cubic metre for the other is not a pricing quirk;
it is the only way either trade makes sense.

**Cargo is data, not objects.** Five hundred tonnes of grain is one parcel, not five hundred
Evennia rows. The same argument as shots being events: nothing gains anything from each sack
having an identity, and a ship with a full hold would otherwise cost more to load than to
sail. A game wanting a *particular* crate - one with a body in it - puts an ordinary object
in the hold alongside the parcels, which is what ordinary objects are for.

**Loading has consequences, and they are the point.** Mass sinks her deeper, so a laden ship
grounds in water a light one crosses. It cuts her freeboard, so she is wetter and eventually
unsafe. It slows her. And weight stowed high makes her tender - she has to be loaded from
the bottom up, which is why a hold is a place with a deck level rather than a number on the
hull.

Nothing here prices anything. What a cargo is worth, who is paying and what the contract
says are the game's business - see `DECISIONS.md`.

**The Evennia side of this is `stowage.py`,** which is a departure from how the rest of the
contrib is laid out and a deliberate one. Every other domain module carries its own mixin,
because every other one has exactly one. Cargo has two - a compartment that holds it and a
hull that carries it - and they are as different from each other as `rooms.py` is from
`typeclasses.py`. Keeping all four concerns in one file would have put it past a thousand
lines with nothing but the ceiling as a reason to look at the seam.

"""

import math
from dataclasses import dataclass, field

# Kilograms in a tonne. Cargo is quoted in tonnes because that is how cargo has always
# been quoted; everything the physics touches is in kilograms and metres like the rest
# of the system.
KILOS_PER_TONNE = 1000.0

# Density of seawater in tonnes per cubic metre. Fresh water is 1.0, and a ship moving
# from one to the other rises or settles noticeably - which is a real hazard in a river
# port and is why the two are not averaged into one number here.
SEAWATER_DENSITY = 1.025
FRESHWATER_DENSITY = 1.0

# Fraction of a hull's rectangle that her waterplane actually fills. A barge approaches
# 0.9 and a fine-lined clipper is nearer 0.7; this is a working default for a merchant
# hull, and a game that models specific hulls should pass its own.
WATERPLANE_COEFFICIENT = 0.8

# Fraction of a hold's volume lost to the gaps between irregular packages. Barrels on
# their sides waste more than boxes; bulk grain poured loose wastes almost none. Ten per
# cent is the figure a ship's officer would assume for general cargo without measuring.
DEFAULT_BROKEN_STOWAGE = 0.1

# How tall one deck is, in metres, for working out how high a weight is stowed. Used
# only for the stability moment, where what matters is the difference between the hold
# and the deck above it rather than either exact figure.
DECK_HEIGHT = 2.2

# How deep a merchant hull is from keel to main deck, as a multiple of the draft she
# floats at light. Only a default, and only used where a game has not measured its own
# hulls - but a default is needed, because freeboard is what says she is overloaded.
DEPTH_TO_DRAFT = 2.0

# Freeboard below which she is no longer safely loaded, as a fraction of the freeboard
# she has light. Not a rule of the sea - it is where this system draws the line that a
# load line draws on a real hull, and a game may draw it elsewhere.
MINIMUM_FREEBOARD_FRACTION = 0.3

# How much of her speed a hull loses when loaded to her full deadweight. A laden
# merchantman is slower than the same hull in ballast, and by roughly this much.
FULL_LOAD_SPEED_PENALTY = 0.25

# Slack allowed when comparing two quantities that were each arrived at by adding
# floats together. A ten-millionth of a tonne, and of a cubic metre - both of which are
# quantities of order a hundred here, so this is nine decimal places below anything
# real. Without it, a hold filled to exactly its capacity reports itself not quite full,
# because the tonnage that fits and the volume it occupies are computed by dividing and
# then multiplying by the same number.
TOLERANCE = 1e-7

# Which limit stopped the loading.
WEIGHT = "weight"
VOLUME = "volume"
NEITHER = "neither"


@dataclass(frozen=True)
class Commodity:
    """
    A kind of cargo, described by how it stows rather than by what it is.

    Attributes:
        key (str): Identifier, e.g. `"wool"`.
        name (str): What it is called on the quay.
        stowage_factor (float): Cubic metres one tonne of it occupies.
        bulk (bool): True for something poured or shovelled loose - grain, coal,
            salt. Bulk cargo wastes no space between packages, because there are
            no packages.

    Notes:
        Deliberately says nothing about value, legality, perishability or who
        wants it. Those are a game's statements about its own world; this is the
        part a ship's officer has to know to load her.

    """

    key: str
    name: str
    stowage_factor: float
    bulk: bool = False

    def __post_init__(self):
        """
        Raises:
            ValueError: If the key is empty, or the stowage factor is not
                positive. A cargo occupying no space would let a hull carry an
                unbounded amount of it, which is a duplication bug rather than a
                remarkable cargo.

        """
        if not self.key:
            raise ValueError("Commodity.key cannot be empty.")
        if not math.isfinite(self.stowage_factor) or self.stowage_factor <= 0.0:
            raise ValueError(
                f"Commodity.stowage_factor must be positive, got {self.stowage_factor!r}."
            )


@dataclass(frozen=True)
class Parcel:
    """
    A quantity of one commodity.

    Attributes:
        commodity (Commodity): What it is.
        tonnes (float): How much of it, by mass.

    Notes:
        Frozen, like every other reading in this system. Loading and discharging
        produce new parcels rather than editing one in place, so a manifest taken
        before a transfer still says what was true then.

    """

    commodity: Commodity
    tonnes: float

    def __post_init__(self):
        """
        Raises:
            ValueError: If the quantity is negative or not finite. Negative cargo
                would let a hold be emptied past empty and come out lighter than
                the ship.

        """
        if not math.isfinite(self.tonnes) or self.tonnes < 0.0:
            raise ValueError(f"Parcel.tonnes must be finite and non-negative, got {self.tonnes!r}.")

    @property
    def mass(self):
        """
        Returns:
            mass (float): Kilograms, for the physics.

        """
        return self.tonnes * KILOS_PER_TONNE

    @property
    def volume(self):
        """
        Returns:
            volume (float): Cubic metres of hold it fills, before broken stowage.

        """
        return self.tonnes * self.commodity.stowage_factor

    def __repr__(self):
        return f"<Parcel: {self.tonnes:g}t {self.commodity.key}>"


#: Stowage factors for common cargoes, in cubic metres per tonne.
#:
#: Reference data rather than content, in the same spirit as the Beaufort scale and the
#: marks on a lead line: these are the figures a ship's officer would have known, not an
#: invented economy. A game is free to ignore the lot and declare its own commodities -
#: nothing in the system reads this except the default for `MARITIME_COMMODITIES`.
#:
#: The spread is the point. Iron stows at a third of a cubic metre and hay at nine, so a
#: hull carrying one is limited by an entirely different thing than the same hull
#: carrying the other.
STANDARD_STOWAGE = (
    Commodity("iron", "pig iron", 0.35),
    Commodity("shot", "round shot", 0.4),
    Commodity("coal", "coal", 1.2, bulk=True),
    Commodity("salt", "salt", 1.0, bulk=True),
    Commodity("grain", "grain", 1.4, bulk=True),
    Commodity("sugar", "sugar", 1.5),
    Commodity("wine", "wine in cask", 1.6),
    Commodity("timber", "sawn timber", 2.2),
    Commodity("hides", "salted hides", 2.5),
    Commodity("tobacco", "tobacco", 3.0),
    Commodity("wool", "baled wool", 3.8),
    Commodity("hay", "hay", 9.0),
)


def commodity_named(text, commodities=STANDARD_STOWAGE):
    """
    Find a commodity by key or by name.

    Args:
        text (str): What was typed - `"wool"`, `"baled wool"`, `"Pig Iron"`.
        commodities (iterable, optional): What to search.

    Returns:
        commodity (Commodity or None): The match, or None.

    Notes:
        Matches the key exactly, then the name exactly, then any name containing
        it - so `wool` finds baled wool and `pig` finds pig iron. Case is ignored
        throughout, because nobody types a manifest with capitals.

    """
    wanted = (text or "").strip().lower()
    if not wanted:
        return None
    for commodity in commodities:
        if commodity.key.lower() == wanted:
            return commodity
    for commodity in commodities:
        if commodity.name.lower() == wanted:
            return commodity
    for commodity in commodities:
        if wanted in commodity.name.lower():
            return commodity
    return None


def total_tonnes(parcels):
    """
    Args:
        parcels (iterable): The parcels.

    Returns:
        tonnes (float): Their combined mass.

    """
    return sum(parcel.tonnes for parcel in parcels)


def total_mass(parcels):
    """
    Args:
        parcels (iterable): The parcels.

    Returns:
        mass (float): Their combined mass in kilograms.

    """
    return total_tonnes(parcels) * KILOS_PER_TONNE


def stowed_volume(parcels, broken_stowage=DEFAULT_BROKEN_STOWAGE):
    """
    How much hold a set of parcels actually takes up.

    Args:
        parcels (iterable): The parcels.
        broken_stowage (float, optional): Fraction of space lost between packages.

    Returns:
        volume (float): Cubic metres.

    Notes:
        Broken stowage is charged against packaged cargo and not against bulk,
        because bulk has no packages to leave gaps between. Applying one figure
        to both would make a hold of loose grain mysteriously waste a tenth of
        itself, and a ship's officer would notice.

    """
    loss = max(0.0, min(1.0, broken_stowage))
    return sum(
        parcel.volume if parcel.commodity.bulk else parcel.volume / (1.0 - loss)
        for parcel in parcels
    )


def combine(parcels):
    """
    Fold parcels of the same commodity together.

    Args:
        parcels (iterable): The parcels.

    Returns:
        parcels (tuple): One parcel per commodity, in the order first seen.

    Notes:
        A hold that took three consignments of salt holds salt, not three salts.
        Order is kept rather than sorted so that a manifest reads in the order she
        was loaded, which is also the order she will be discharged.

    """
    totals = {}
    for parcel in parcels:
        key = parcel.commodity.key
        if key in totals:
            totals[key] = Parcel(parcel.commodity, totals[key].tonnes + parcel.tonnes)
        else:
            totals[key] = parcel
    return tuple(parcel for parcel in totals.values() if parcel.tonnes > 0.0)


def take_from(parcels, commodity, tonnes):
    """
    Remove a quantity of one commodity.

    Args:
        parcels (iterable): What is stowed.
        commodity (Commodity): What to take out.
        tonnes (float): How much.

    Returns:
        result (tuple): `(remaining, taken)` - the parcels left, and the parcel
            actually removed.

    Notes:
        Takes what is there rather than what was asked for. Discharging more than
        is aboard is an ordinary mistake at a quay, and answering it with an
        exception would make every caller check the manifest first - which is the
        same lookup done twice.

    """
    stowed = combine(parcels)
    available = sum(p.tonnes for p in stowed if p.commodity.key == commodity.key)
    moved = max(0.0, min(float(tonnes), available))
    remaining = tuple(
        Parcel(p.commodity, p.tonnes - moved) if p.commodity.key == commodity.key else p
        for p in stowed
    )
    return tuple(p for p in remaining if p.tonnes > 0.0), Parcel(commodity, moved)


# --- what the hull can take -------------------------------------------------


def deadweight(capacity, light_displacement=0.0):
    """
    The mass a hull may carry.

    Args:
        capacity (VesselCapacity): Her budget.
        light_displacement (float, optional): What she weighs empty, in kilograms.

    Returns:
        deadweight (float): Kilograms of cargo, stores and people she can take.

    Notes:
        Deadweight is the difference between what she displaces loaded and what
        she weighs light - so a game that models her own weight subtracts it here,
        and one that does not gets the whole displacement budget for cargo. Both
        are coherent; silently assuming one would make the other wrong.

    """
    return max(0.0, float(capacity.displacement) - max(0.0, float(light_displacement)))


def binding_limit(parcels, carrying_capacity, hold_volume, broken_stowage=DEFAULT_BROKEN_STOWAGE):
    """
    Which capacity a load has used up.

    Args:
        parcels (iterable): What is aboard.
        carrying_capacity (float): Kilograms of cargo she may take in all.
        hold_volume (float): Cubic metres of hold she actually has.
        broken_stowage (float, optional): Fraction lost between packages.

    Returns:
        limit (str): `WEIGHT` if she is down on her marks, `VOLUME` if the holds
            are full, `NEITHER` if she can take more of both.

    Notes:
        Weight first when both are exhausted, because being overloaded is a
        seaworthiness problem and being full is only a commercial one.

        Takes two numbers rather than a `VesselCapacity` on purpose. The volume
        that stops a load is the hold she actually has, which is the sum of her
        cargo compartments - not `VesselCapacity.internal_volume`, which is the
        space below deck that cabins, stores and holds all compete for when she
        is *built*. Reading the build budget here would let a ship load cargo into
        the volume her cabins are standing in.

    """
    if total_mass(parcels) >= max(0.0, float(carrying_capacity)) - TOLERANCE * KILOS_PER_TONNE:
        return WEIGHT
    if stowed_volume(parcels, broken_stowage) >= max(0.0, float(hold_volume)) - TOLERANCE:
        return VOLUME
    return NEITHER


def room_for(
    commodity, parcels, carrying_capacity, hold_volume, broken_stowage=DEFAULT_BROKEN_STOWAGE
):
    """
    How much more of one commodity will actually go aboard.

    Args:
        commodity (Commodity): What is being offered.
        parcels (iterable): What is already stowed.
        carrying_capacity (float): Kilograms of cargo she may take in all.
        hold_volume (float): Cubic metres of hold she actually has.
        broken_stowage (float, optional): Fraction lost between packages.

    Returns:
        tonnes (float): How many more tonnes of it she will take, never negative.

    Notes:
        The smaller of what the mass allows and what the space allows, which is
        the whole question and the reason both are tracked. A quay asking "will
        the rest of this fit?" gets one number rather than two and a comparison
        it has to make itself.

    """
    spare_mass = max(0.0, float(carrying_capacity)) - total_mass(parcels)
    by_weight = spare_mass / KILOS_PER_TONNE

    loss = max(0.0, min(1.0, broken_stowage))
    per_tonne = commodity.stowage_factor
    if not commodity.bulk:
        per_tonne = per_tonne / (1.0 - loss) if loss < 1.0 else math.inf
    spare_volume = max(0.0, float(hold_volume)) - stowed_volume(parcels, broken_stowage)
    by_volume = spare_volume / per_tonne if per_tonne > 0.0 else math.inf

    return max(0.0, min(by_weight, by_volume))


# --- what it does to her ----------------------------------------------------


def tonnes_per_centimetre(
    length, beam, coefficient=WATERPLANE_COEFFICIENT, density=SEAWATER_DENSITY
):
    """
    How much weight sinks her one centimetre.

    Args:
        length (float): Overall length in metres.
        beam (float): Maximum beam in metres.
        coefficient (float, optional): How much of her rectangle the waterplane
            fills.
        density (float, optional): Water density in tonnes per cubic metre.

    Returns:
        tpc (float): Tonnes per centimetre of immersion.

    Notes:
        The standard figure a mate uses to work out what a parcel will cost in
        draft, and it is only ever the waterplane - the slice of hull at the
        surface. What is below it is already in the water and does not matter to
        the next centimetre.

        Fresh water gives a smaller figure, so the same cargo sinks her further in
        a river than in the sea. That is why the density is an argument.

    """
    waterplane = max(0.0, float(length)) * max(0.0, float(beam)) * max(0.0, float(coefficient))
    return waterplane * float(density) / 100.0


def sinkage(mass, tpc):
    """
    How much deeper a mass puts her.

    Args:
        mass (float): Kilograms aboard.
        tpc (float): Tonnes per centimetre of immersion.

    Returns:
        sinkage (float): Metres.

    """
    if tpc <= 0.0:
        return 0.0
    return (max(0.0, mass) / KILOS_PER_TONNE / tpc) / 100.0


def laden_draft(light_draft, mass, tpc):
    """
    How deep she sits with cargo in her.

    Args:
        light_draft (float): How deep she sits empty, in metres.
        mass (float): Kilograms aboard.
        tpc (float): Tonnes per centimetre of immersion.

    Returns:
        draft (float): Metres.

    Notes:
        The figure grounding and berthing should read, and the reason a loaded
        ship has to wait for the tide to cross a bar a light one runs over. It is
        derived rather than stored so that it cannot disagree with what is
        actually in the hold.

    """
    return max(0.0, float(light_draft)) + sinkage(mass, tpc)


def freeboard(depth, draft):
    """
    How much hull stands out of the water.

    Args:
        depth (float): Hull depth from keel to main deck, in metres.
        draft (float): How deep she is sitting, in metres.

    Returns:
        freeboard (float): Metres of hull above the waterline, never negative.

    Notes:
        What a load line is drawn to protect. A ship with no freeboard does not
        sink because she is heavy - she sinks because the sea comes aboard faster
        than it leaves.

    """
    return max(0.0, float(depth) - float(draft))


def overloaded(depth, light_draft, laden, fraction=MINIMUM_FREEBOARD_FRACTION):
    """
    Whether she has been loaded past what is safe.

    Args:
        depth (float): Hull depth from keel to main deck, in metres.
        light_draft (float): How deep she sits empty, in metres.
        laden (float): How deep she is sitting now, in metres.
        fraction (float, optional): The share of her light freeboard she must keep.

    Returns:
        overloaded (bool): True if she is down past her marks.

    Notes:
        Measured against the freeboard she has light rather than against a fixed
        number of metres, so the same rule works for a lighter and a merchantman
        without either being given a special case.

    """
    light = freeboard(depth, light_draft)
    if light <= 0.0:
        return True
    return freeboard(depth, laden) < light * max(0.0, fraction)


def laden_speed(max_speed, mass, capacity_mass, penalty=FULL_LOAD_SPEED_PENALTY):
    """
    What she will make with that much in her.

    Args:
        max_speed (float): Her best speed light, in metres per second.
        mass (float): Kilograms aboard.
        capacity_mass (float): Kilograms she can carry.
        penalty (float, optional): The share of her speed she loses at full load.

    Returns:
        speed (float): Metres per second.

    Notes:
        Linear in how full she is, which is not the physics - resistance rises
        faster than that - but is honest about being a working approximation and
        is monotonic, which is the property a player actually experiences. A
        curve here would be a more precise answer to a question the rest of the
        system does not ask precisely.

    """
    if capacity_mass <= 0.0:
        return max(0.0, float(max_speed))
    loaded = max(0.0, min(1.0, max(0.0, mass) / capacity_mass))
    return max(0.0, float(max_speed)) * (1.0 - max(0.0, penalty) * loaded)


def stowed_moment(loads, deck_height=DECK_HEIGHT):
    """
    How much a load wants to roll her, by how high it is stowed.

    Args:
        loads (iterable): `(mass, deck_level)` pairs - kilograms, and the deck
            they are on, with 0 as the main deck and negative descending.
        deck_height (float, optional): Metres between decks.

    Returns:
        moment (float): Kilogram-metres above the main deck. Negative is weight
            low in her, which is weight doing good.

    Notes:
        Relative to the main deck rather than to the keel, so that the sign
        carries the meaning: ballast and heavy cargo stowed low come out
        negative, and everything piled on deck comes out positive. Stowing from
        the bottom up is then not a rule to be remembered but the thing the
        arithmetic rewards.

    """
    return sum(max(0.0, mass) * level * float(deck_height) for mass, level in loads)


def tender(moment, stability_moment):
    """
    Whether she has been loaded top-heavy.

    Args:
        moment (float): Kilogram-metres above the main deck.
        stability_moment (float): What this hull tolerates.

    Returns:
        tender (bool): True if she will roll slowly and far - and, in a sea, not
            always come back.

    Notes:
        What being tender then *costs* her is not decided here. It is a statement
        about how harsh a game is, it collides with sailing and damage, and it is
        recorded in `DECISIONS.md` rather than guessed at.

    """
    if stability_moment <= 0.0:
        return False
    return moment > float(stability_moment)


@dataclass(frozen=True)
class Stowage:
    """
    What is aboard and what it is doing to her.

    Attributes:
        parcels (tuple): Everything stowed, one entry per commodity.
        tonnes (float): Total mass.
        volume (float): Hold actually occupied, broken stowage included.
        draft (float): How deep she is sitting.
        freeboard (float): How much hull is out of the water.
        limit (str): Which capacity has run out - `WEIGHT`, `VOLUME` or `NEITHER`.
        overloaded (bool): Whether she is down past her marks.
        tender (bool): Whether the weight is stowed too high.

    Notes:
        One reading taken at one moment, so a report cannot show a mass from
        before a transfer beside a draft from after it. Assembled by
        `Laden.stowage`; nothing computes a field of it on its own.

    """

    parcels: tuple = field(default_factory=tuple)
    tonnes: float = 0.0
    volume: float = 0.0
    draft: float = 0.0
    freeboard: float = 0.0
    limit: str = NEITHER
    overloaded: bool = False
    tender: bool = False
