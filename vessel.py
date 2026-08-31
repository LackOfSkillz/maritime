"""
Vessel definitions: hulls as data, not as classes.

A ship class is a `VesselTemplate` - a record of dimensions, capacity and deck plan.
Changing a sloop's beam should be editing a number, never writing a subclass, so no
`Sloop` class exists anywhere in this contrib.

Three ideas hold the fit-out honest, and all three are here from the start even though
nothing consumes them yet:

    VesselCapacity   what the hull can carry before it suffers for it
    DeckPlan         how many compartments will physically fit, and where
    Exposure         how sheltered a compartment is from weather and water

That is deliberate. Capacity and deck slots are what make later customisation a set of
trade-offs rather than a shopping list, and adding them after templates exist means
rewriting every template and every component that was written against the old shape.
Declaring them now costs a few fields.

Deck levels are integers relative to the main deck, so they map straight onto elevation:
0 is the main deck, negative goes down into the hull, positive goes up into the rigging.
That is what lets flooding fill from the lowest compartment upward without a separate
model of which room is under which.

"""

import math
from dataclasses import dataclass, field

# How exposed a compartment is. Weather, boarding and flooding all read this: you board
# onto an open deck, weather reaches a semi-exposed one, and water finds the lowest
# space below the waterline first.
OPEN = "open"
SEMI_EXPOSED = "semi_exposed"
INTERIOR = "interior"
BELOW_WATERLINE = "below_waterline"

EXPOSURES = (OPEN, SEMI_EXPOSED, INTERIOR, BELOW_WATERLINE)

# Exposures open to the sky: where someone can watch the sea go by, feel the
# weather, and be seen doing it. Below deck you feel the motion but you do not
# watch the water, which is what makes an open deck worth standing on.
WEATHER_DECKS = (OPEN, SEMI_EXPOSED)

# Deck level of the main deck. Everything else is relative to it.
MAIN_DECK = 0


def _require_positive(value, name):
    """
    Validate a dimension that must be greater than zero.

    Args:
        value (float): The value to check.
        name (str): Field name, for the error message.

    Returns:
        value (float): The value, as a float.

    Raises:
        ValueError: If the value is not finite and positive.

    """
    number = float(value)
    if not math.isfinite(number) or number <= 0.0:
        raise ValueError(f"{name} must be a positive, finite number, got {value!r}.")
    return number


def _require_non_negative(value, name):
    """
    Validate a budget that may be zero but never negative.

    Args:
        value (float): The value to check.
        name (str): Field name, for the error message.

    Returns:
        value (float): The value, as a float.

    Raises:
        ValueError: If the value is negative or not finite.

    """
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise ValueError(f"{name} must be a non-negative, finite number, got {value!r}.")
    return number


@dataclass(frozen=True)
class VesselCapacity:
    """
    What a hull can carry before it starts to suffer for it.

    Nothing consumes these yet. They exist now because every later fitting -
    armour, guns, cabins, stores - has to draw on a shared budget for
    customisation to be a set of trade-offs rather than a list of upgrades, and
    adding the budget after templates exist means rewriting all of them.

    Attributes:
        displacement (float): Mass in kilograms the hull carries before draft and
            stability begin to degrade.
        internal_volume (float): Usable space below deck, in cubic metres.
        deck_area (float): Topside footprint in square metres, which is what guns
            and deck fittings compete for.
        stability_moment (float): Tolerance for high or off-centre weight. Higher
            hulls carry more aloft before they become tender.
        berths (int): How many people can actually sleep aboard, as distinct from
            how many can stand on deck.

    """

    displacement: float = 0.0
    internal_volume: float = 0.0
    deck_area: float = 0.0
    stability_moment: float = 0.0
    berths: int = 0

    def __post_init__(self):
        """Reject negative or non-finite budgets."""
        for name in ("displacement", "internal_volume", "deck_area", "stability_moment"):
            _require_non_negative(getattr(self, name), f"VesselCapacity.{name}")
        if int(self.berths) < 0:
            raise ValueError(f"VesselCapacity.berths cannot be negative, got {self.berths!r}.")


@dataclass(frozen=True)
class DeckLevel:
    """
    One deck of a hull, and how much will fit on it.

    Attributes:
        level (int): Height relative to the main deck. 0 is the main deck,
            negative descends into the hull, positive climbs into the rigging.
            Ordering by this value orders the ship vertically, which is what
            flooding needs to fill from the bottom up.
        name (str): What the deck is called, for building and description.
        slots (int): How many compartments physically fit here. This is the limit
            that stops a sloop being fitted out like a mansion.
        exposure (str): Default exposure for compartments on this deck. A single
            compartment may differ - a helm station is more exposed than the cabin
            beside it - so this is a default rather than a rule.

    """

    level: int
    name: str
    slots: int
    exposure: str = INTERIOR

    def __post_init__(self):
        """Reject impossible decks."""
        if self.slots < 0:
            raise ValueError(f"DeckLevel.slots cannot be negative, got {self.slots!r}.")
        if not self.name:
            raise ValueError("DeckLevel.name cannot be empty.")
        if self.exposure not in EXPOSURES:
            raise ValueError(
                f"DeckLevel.exposure must be one of {EXPOSURES}, got {self.exposure!r}."
            )


@dataclass(frozen=True)
class DeckPlan:
    """
    Every deck a hull has, and the compartments each will hold.

    The plan is what makes hull size mean something. Fitting out is bounded by
    physical space, so moving up to a larger hull is the real progression rather
    than stacking fittings onto a small one.

    Attributes:
        decks (tuple): The `DeckLevel` entries, in no particular order. Use
            `ordered()` when vertical sequence matters.

    """

    decks: tuple = ()

    def __post_init__(self):
        """Reject duplicate deck levels."""
        levels = [deck.level for deck in self.decks]
        if len(set(levels)) != len(levels):
            raise ValueError(f"DeckPlan has duplicate deck levels: {sorted(levels)}.")

    def ordered(self):
        """
        Decks from the lowest upward.

        Returns:
            decks (tuple): `DeckLevel` entries sorted by level, ascending.

        Notes:
            Lowest first because that is the order flooding cares about, and it
            is the only ordering anything has needed so far.

        """
        return tuple(sorted(self.decks, key=lambda deck: deck.level))

    def level(self, level):
        """
        Find a deck by its level.

        Args:
            level (int): The deck level to look up.

        Returns:
            deck (DeckLevel or None): The deck, or None if the hull has none there.

        """
        for deck in self.decks:
            if deck.level == level:
                return deck
        return None

    @property
    def total_slots(self):
        """
        Total compartments this hull can hold.

        Returns:
            slots (int): Sum of every deck's slots.

        """
        return sum(deck.slots for deck in self.decks)


@dataclass(frozen=True)
class VesselTemplate:
    """
    A ship class, expressed as data.

    No subclass exists for a sloop or a brig. Changing a hull means changing
    numbers, which is what lets a game define its own vessels without importing
    anything from this contrib but the template itself.

    Attributes:
        key (str): Identifier for this class, e.g. `"sloop"`.
        name (str): Display name, e.g. `"Test Sloop"`.
        length (float): Overall length in metres.
        beam (float): Maximum width in metres.
        draft (float): How deep the hull sits when unloaded, in metres. The
            loaded figure is derived later from cargo, flooding and heel, which is
            why this one is the light draft rather than the working one.
        capacity (VesselCapacity): What the hull can carry.
        deck_plan (DeckPlan): The decks and their compartments.
        crew_minimum (int): Fewest hands that can work her at all.
        crew_ideal (int): Hands at which she is fully worked.

    """

    key: str
    name: str
    length: float
    beam: float
    draft: float
    capacity: VesselCapacity = field(default_factory=VesselCapacity)
    deck_plan: DeckPlan = field(default_factory=DeckPlan)
    crew_minimum: int = 1
    crew_ideal: int = 1

    def __post_init__(self):
        """Reject impossible hulls."""
        if not self.key:
            raise ValueError("VesselTemplate.key cannot be empty.")
        for name in ("length", "beam", "draft"):
            _require_positive(getattr(self, name), f"VesselTemplate.{name}")
        if self.beam > self.length:
            raise ValueError(
                f"VesselTemplate.beam ({self.beam}) cannot exceed length ({self.length})."
            )
        if self.crew_minimum < 0 or self.crew_ideal < 0:
            raise ValueError("Crew counts cannot be negative.")
        if self.crew_ideal < self.crew_minimum:
            raise ValueError(
                f"crew_ideal ({self.crew_ideal}) cannot be below "
                f"crew_minimum ({self.crew_minimum})."
            )


def vessel_in(room):
    """
    The vessel a room belongs to, if any.

    Args:
        room (Object or None): A compartment, a stretch of water, a tavern.

    Returns:
        vessel (Vessel or None): The hull it is part of.

    Notes:
        The one definition of what "aboard" means. It walks the same chain the
        position resolver walks, so a room is part of a ship exactly when the
        position system says it is, rather than because somebody checked its
        typeclass in one place and its tags in another.

        Asked of a *room* rather than of a person, because the interesting question
        is sometimes about a room nobody is standing in yet - the far side of a
        gangway, at the moment somebody steps onto it.

        The import is deferred because `typeclasses` reaches back into this module
        and a top-level import would close the circle.

    """
    from .typeclasses import Vessel

    source = getattr(room, "maritime_position_source", None)
    return source if isinstance(source, Vessel) else None
