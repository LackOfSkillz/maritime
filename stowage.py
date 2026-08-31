"""
The Evennia side of cargo: a compartment that holds it, and a hull that carries it.

`cargo.py` is the arithmetic - what a stowage factor is, what mass does to a draft, which
capacity runs out first. This is where that meets the database. It is a separate module
because cargo has two Evennia faces rather than the one every other domain module has, and
they are as different from each other as a room is from a ship:

    Stowed   a compartment. Has a volume, holds parcels, knows which deck it is on.
    Laden    a hull. Has a deadweight, aggregates her holds, and sits deeper for it.

**Loading is a negotiation, not a request.** `load` takes what will fit and reports what
would not, because "she took two hundred of the three hundred and she is down on her marks"
is the useful answer at a quay. Refusing the whole consignment over the last ten tonnes
would throw away the two hundred that went aboard, and every caller would have to
re-implement the fitting to avoid it.

**Both capacities are checked, in the two places they live.** The hold enforces its own
volume; the hull enforces her deadweight. Neither can answer for the other - a hold has no
opinion about how deep she is sitting, and a hull does not know which compartment has room -
and the whole trade is in which of the two stops you.

**Draft becomes derived here.** `Vessel.draft` used to be a stored number with a docstring
promising it would one day be worked out from what is aboard. It is now, so grounding, keel
clearance and whether a berth will take her all read the laden figure without one call site
changing. The stored value is the *light* draft, and setting `draft` raises rather than
quietly becoming a second source of truth that the next transfer overwrites.

"""

from .cargo import (
    DEFAULT_BROKEN_STOWAGE,
    DEPTH_TO_DRAFT,
    NEITHER,
    VOLUME,
    Parcel,
    TOLERANCE,
    Stowage,
    binding_limit,
    combine,
    deadweight,
    freeboard,
    laden_draft,
    laden_speed,
    overloaded,
    room_for,
    stowed_moment,
    stowed_volume,
    take_from,
    tender,
    tonnes_per_centimetre,
    total_mass,
    total_tonnes,
)
from .results import Result
from .vessel import VesselCapacity

from dataclasses import dataclass, replace

# Why a transfer did not happen, or did not happen in full.
NO_HOLD = "no_hold"
NOT_ABOARD = "not_aboard"
NOTHING_TO_MOVE = "nothing_to_move"
FULL = "full"
PART_ONLY = "part_only"


@dataclass(frozen=True, kw_only=True)
class TransferResult(Result):
    """
    What actually crossed the rail.

    Attributes:
        parcel (Parcel or None): What moved.
        hold (object or None): Which compartment it moved into or out of. The
            first one used, when a load ran across several.
        refused (float): Tonnes asked for that would not go.
        limit (str): Which capacity refused them - `WEIGHT`, `VOLUME` or `NEITHER`.

    Notes:
        A partial load succeeds and says so, with `PART_ONLY` and the tonnage
        refused. `limit` is the interesting half: being told she is full is not
        useful, and being told she cubed out - so a denser cargo would still go -
        is a decision a shipper can act on.

    """

    parcel: object = None
    hold: object = None
    refused: float = 0.0
    limit: str = NEITHER


class Stowed:
    """
    A compartment that will take cargo.

    Notes:
        Mixed into `ShipRoom`, so any compartment *could* be a hold and one with
        no capacity simply is not. Better than a separate hold typeclass:
        converting a cabin to cargo space in a refit becomes setting a number
        rather than rebuilding the room, and every compartment already carries the
        deck level that stowing weight low depends on.

    """

    def at_object_creation(self):
        """Set up this part of a newly created compartment."""
        super().at_object_creation()
        self.db.hold_capacity = 0.0
        self.db.cargo = []

    @property
    def hold_capacity(self):
        """
        Returns:
            capacity (float): Cubic metres of cargo space here. Zero means this is
                not a hold.

        """
        return float(self.db.hold_capacity or 0.0)

    @hold_capacity.setter
    def hold_capacity(self, cubic_metres):
        """
        Args:
            cubic_metres (float): How much cargo space this compartment has.

        Raises:
            ValueError: If negative.

        """
        cubic_metres = float(cubic_metres)
        if cubic_metres < 0.0:
            raise ValueError(f"hold_capacity cannot be negative, got {cubic_metres!r}.")
        if self.db.hold_capacity != cubic_metres:
            self.db.hold_capacity = cubic_metres

    @property
    def is_hold(self):
        """
        Returns:
            is_hold (bool): Whether anything can be stowed here.

        """
        return self.hold_capacity > 0.0

    @property
    def stowed(self):
        """
        Returns:
            parcels (tuple): What is in here, one entry per commodity.

        """
        return tuple(self.db.cargo or ())

    def stowed_volume(self, broken_stowage=DEFAULT_BROKEN_STOWAGE):
        """
        Args:
            broken_stowage (float, optional): Fraction lost between packages.

        Returns:
            volume (float): Cubic metres taken up.

        """
        return stowed_volume(self.stowed, broken_stowage)

    def space_left(self, broken_stowage=DEFAULT_BROKEN_STOWAGE):
        """
        Args:
            broken_stowage (float, optional): Fraction lost between packages.

        Returns:
            volume (float): Cubic metres still free, never negative.

        """
        return max(0.0, self.hold_capacity - self.stowed_volume(broken_stowage))

    def room_for(self, commodity, broken_stowage=DEFAULT_BROKEN_STOWAGE):
        """
        How many tonnes of one commodity will fit in here.

        Args:
            commodity (Commodity): What is being offered.
            broken_stowage (float, optional): Fraction lost between packages.

        Returns:
            tonnes (float): What fits by volume alone. Whether the *ship* can
                carry it is a separate question, asked of the hull.

        """
        per_tonne = commodity.stowage_factor
        if not commodity.bulk and broken_stowage < 1.0:
            per_tonne = per_tonne / (1.0 - broken_stowage)
        if per_tonne <= 0.0:
            return 0.0
        return max(0.0, self.space_left(broken_stowage) / per_tonne)

    def stow(self, parcel, broken_stowage=DEFAULT_BROKEN_STOWAGE):
        """
        Put a parcel in here.

        Args:
            parcel (Parcel): What to stow.
            broken_stowage (float, optional): Fraction lost between packages.

        Returns:
            stowed (Parcel): What went in.

        Raises:
            ValueError: If it will not fit, or if this compartment is not a hold.

        Notes:
            Strict, unlike `Laden.load`. This is the primitive that puts a known
            quantity in a known place; working out what will fit across a whole
            ship is the hull's job, and doing it in both places would mean two
            answers to one question.

            Reads the list, folds the new parcel in and writes it back once - see
            Law 10.

        """
        if not self.is_hold:
            raise ValueError(f"{self.key} is not a hold; it has no cargo capacity.")
        after = combine(list(self.stowed) + [parcel])
        if stowed_volume(after, broken_stowage) > self.hold_capacity + TOLERANCE:
            raise ValueError(
                f"{parcel!r} will not fit in {self.key}: only "
                f"{self.space_left(broken_stowage):.1f} cubic metres free."
            )
        self.db.cargo = list(after)
        return parcel

    def discharge(self, commodity, tonnes):
        """
        Take cargo out of here.

        Args:
            commodity (Commodity): What to take.
            tonnes (float): How much.

        Returns:
            taken (Parcel): What actually came out, which may be less than was
                asked for and may be nothing.

        """
        remaining, taken = take_from(self.stowed, commodity, tonnes)
        if taken.tonnes > 0.0:
            self.db.cargo = list(remaining)
        return taken

    def deck_weight(self):
        """
        Returns:
            load (tuple): `(mass, deck_level)` for what is stowed here, which is
                what the stability moment is built from.

        """
        return (total_mass(self.stowed), self.deck_level)


class Laden:
    """
    The cargo a hull is carrying, and what it is doing to her.

    Notes:
        The first thing to consume `VesselCapacity`, which has existed since
        vessels did, unused, waiting for something that had to draw on a shared
        budget.

        Owns `draft`, which is why that property is here rather than on `Vessel`.

    """

    def at_object_creation(self):
        """Set up this part of a newly created vessel."""
        super().at_object_creation()
        self.db.draft = 2.0
        self.db.hull_depth = 0.0
        self.db.capacity = VesselCapacity()
        self.db.light_displacement = 0.0
        self.db.broken_stowage = DEFAULT_BROKEN_STOWAGE

    # --- what she is ---------------------------------------------------------

    @property
    def capacity(self):
        """
        Returns:
            capacity (VesselCapacity): What this hull can carry.

        """
        return self.db.capacity or VesselCapacity()

    @capacity.setter
    def capacity(self, capacity):
        """
        Args:
            capacity (VesselCapacity): Her budget.

        Raises:
            TypeError: If given anything else.

        """
        if not isinstance(capacity, VesselCapacity):
            raise TypeError(f"Expected a VesselCapacity, got {type(capacity).__name__}.")
        self.db.capacity = capacity

    @property
    def light_displacement(self):
        """
        Returns:
            mass (float): What the hull itself weighs, in kilograms.

        Notes:
            Zero unless a game says otherwise, in which case the whole
            displacement budget is available for cargo. Both readings are
            coherent; see `cargo.deadweight` for why neither is assumed.

        """
        return float(self.db.light_displacement or 0.0)

    @light_displacement.setter
    def light_displacement(self, kilograms):
        """
        Args:
            kilograms (float): What she weighs empty.

        Raises:
            ValueError: If negative.

        """
        kilograms = float(kilograms)
        if kilograms < 0.0:
            raise ValueError(f"light_displacement cannot be negative, got {kilograms!r}.")
        self.db.light_displacement = kilograms

    @property
    def light_draft(self):
        """
        Returns:
            draft (float): How deep she sits with nothing in her, in metres.

        """
        return float(self.db.draft or 0.0)

    @light_draft.setter
    def light_draft(self, metres):
        """
        Args:
            metres (float): How deep she sits empty.

        Raises:
            ValueError: If negative.

        """
        metres = float(metres)
        if metres < 0.0:
            raise ValueError(f"light_draft cannot be negative, got {metres!r}.")
        self.db.draft = metres

    @property
    def hull_depth(self):
        """
        Returns:
            depth (float): Keel to main deck, in metres.

        Notes:
            Twice the light draft unless a game says otherwise, which is a fair
            working proportion for a merchant hull and gives every vessel already
            afloat a freeboard without anybody having to go back and measure one.

        """
        stored = float(self.db.hull_depth or 0.0)
        return stored if stored > 0.0 else self.light_draft * DEPTH_TO_DRAFT

    @hull_depth.setter
    def hull_depth(self, metres):
        """
        Args:
            metres (float): Keel to main deck. Zero restores the derived figure.

        Raises:
            ValueError: If negative.

        """
        metres = float(metres)
        if metres < 0.0:
            raise ValueError(f"hull_depth cannot be negative, got {metres!r}.")
        self.db.hull_depth = metres

    @property
    def broken_stowage(self):
        """
        Returns:
            fraction (float): Share of hold space lost between packages.

        """
        stored = self.db.broken_stowage
        return DEFAULT_BROKEN_STOWAGE if stored is None else float(stored)

    @broken_stowage.setter
    def broken_stowage(self, fraction):
        """
        Args:
            fraction (float): Share of hold space lost, from 0 to just under 1.

        Raises:
            ValueError: If outside that range. At 1 nothing would ever fit
                anywhere, which is a configuration mistake rather than a very
                awkward cargo.

        """
        fraction = float(fraction)
        if not 0.0 <= fraction < 1.0:
            raise ValueError(f"broken_stowage must be at least 0 and under 1, got {fraction!r}.")
        self.db.broken_stowage = fraction

    # --- what is aboard ------------------------------------------------------

    @property
    def holds(self):
        """
        Returns:
            holds (tuple): Her compartments that take cargo, lowest first.

        Notes:
            Sorted by deck level, so "the first hold with room" is also the lowest
            one with room. Stowing from the bottom up is then what happens by
            default rather than what a careful player remembers to do.

        """
        return tuple(
            sorted(
                (room for room in self.ship_rooms if getattr(room, "is_hold", False)),
                key=lambda room: room.deck_level,
            )
        )

    @property
    def hold_volume(self):
        """
        Returns:
            volume (float): Cubic metres of cargo space she actually has, across
                every hold.

        Notes:
            Not `VesselCapacity.internal_volume`. That is the space below deck
            that cabins, stores and holds all compete for when she is built; this
            is how much of it was actually built as hold, and it is the figure
            that stops a load.

        """
        return sum(hold.hold_capacity for hold in self.holds)

    @property
    def cargo(self):
        """
        Returns:
            parcels (tuple): Everything aboard, folded together by commodity.

        """
        aboard = []
        for hold in self.holds:
            aboard.extend(hold.stowed)
        return combine(aboard)

    @property
    def cargo_tonnes(self):
        """
        Returns:
            tonnes (float): What she is carrying.

        """
        return total_tonnes(self.cargo)

    @property
    def deadweight(self):
        """
        Returns:
            deadweight (float): Kilograms of cargo she can take in all.

        """
        # Her people are deadweight too, and the `deadweight` docstring has always
        # said so - cargo, stores and people out of one budget. Every marine shipped
        # is cargo she did not carry, which is what makes a fighting complement a
        # decision rather than a free upgrade.
        company = self.company
        aboard = company.mass if company is not None else 0.0
        return max(0.0, deadweight(self.capacity, self.light_displacement) - aboard)

    @property
    def tonnes_per_centimetre(self):
        """
        Returns:
            tpc (float): Tonnes that sink her one centimetre.

        """
        return tonnes_per_centimetre(self.length, self.beam)

    @property
    def draft(self):
        """
        How deep she is sitting now.

        Returns:
            draft (float): Metres - light draft, plus what the cargo has added.

        Notes:
            Derived, and deliberately read-only. Everything that already asked a
            vessel for her draft - grounding, keel clearance, whether a berth will
            take her - now gets the laden figure without one call site changing,
            which is what that property was always going to become.

        """
        return laden_draft(self.light_draft, total_mass(self.cargo), self.tonnes_per_centimetre)

    @draft.setter
    def draft(self, metres):
        """
        Raises:
            AttributeError: Always.

        Notes:
            The working draft comes from the light draft and the manifest. A
            stored one would be a second source of truth that the next transfer
            silently overwrites, and the symptom would be a ship that grounds
            where the numbers say she should not.

        """
        raise AttributeError(
            "draft is derived from light_draft and what is in the holds; set light_draft instead."
        )

    @property
    def freeboard(self):
        """
        Returns:
            freeboard (float): Metres of hull above the water.

        """
        return freeboard(self.hull_depth, self.draft)

    @property
    def working_limits(self):
        """
        What she can actually do as she is loaded.

        Returns:
            limits (MotionLimits): Her own limits, with the top speed reduced for
                what is in her.

        Notes:
            Deliberately a second property rather than a laden `motion_limits`.
            Draft could become derived silently because almost nothing wrote it;
            limits are authored on every vessel a game builds, and a getter that
            returned something other than what was set would be a trap rather
            than a convenience.

            Acceleration and turn rate are left alone. A loaded hull is slower to
            gather way and slower to answer her helm as well, but by how much is a
            question about her hull form rather than her tonnage, and inventing a
            second and a third coefficient to look thorough would be inventing
            them.

        """
        limits = self.motion_limits
        return replace(
            limits,
            max_speed=laden_speed(limits.max_speed, total_mass(self.cargo), self.deadweight),
        )

    def stowage(self):
        """
        One reading of how she is loaded.

        Returns:
            stowage (Stowage): Mass, volume, draft, freeboard, which capacity has
                run out, and whether she is overloaded or tender.

        Notes:
            Assembled in one place so that a report cannot show a mass from before
            a transfer beside a draft from after it.

        """
        parcels = self.cargo
        laden = self.draft
        return Stowage(
            parcels=parcels,
            tonnes=total_tonnes(parcels),
            volume=stowed_volume(parcels, self.broken_stowage),
            draft=laden,
            freeboard=freeboard(self.hull_depth, laden),
            limit=binding_limit(parcels, self.deadweight, self.hold_volume, self.broken_stowage),
            overloaded=overloaded(self.hull_depth, self.light_draft, laden),
            tender=tender(
                stowed_moment(hold.deck_weight() for hold in self.holds),
                self.capacity.stability_moment,
            ),
        )

    # --- moving it -----------------------------------------------------------

    def load(self, commodity, tonnes, hold=None):
        """
        Take cargo aboard.

        Args:
            commodity (Commodity): What is being loaded.
            tonnes (float): How much is offered.
            hold (ShipRoom, optional): Where to put it. Defaults to working down
                her holds from the lowest.

        Returns:
            result (TransferResult): What went aboard, where, and what would not.

        Notes:
            The hull's deadweight is worked out once, before anything moves, and
            spent down as parcels go in. Asking again after each hold would let a
            ship that cubed out of her first hold take the same tonnage twice.

        """
        offered = max(0.0, float(tonnes))
        if offered <= 0.0:
            return TransferResult(success=False, code=NOTHING_TO_MOVE)

        candidates = [hold] if hold is not None else list(self.holds)
        candidates = [candidate for candidate in candidates if candidate is not None]
        if not candidates:
            return TransferResult(success=False, code=NO_HOLD)

        allowance = room_for(
            commodity, self.cargo, self.deadweight, self.hold_volume, self.broken_stowage
        )

        moved = 0.0
        used = None
        for candidate in candidates:
            takes = min(
                offered - moved,
                allowance - moved,
                candidate.room_for(commodity, self.broken_stowage),
            )
            if takes <= TOLERANCE:
                continue
            candidate.stow(Parcel(commodity, takes), self.broken_stowage)
            moved += takes
            used = used or candidate
            if moved >= offered - TOLERANCE:
                break

        if moved <= 0.0:
            after = self.stowage()
            return TransferResult(
                success=False,
                code=FULL,
                refused=offered,
                limit=after.limit if after.limit != NEITHER else VOLUME,
            )

        refused = max(0.0, offered - moved)
        return TransferResult(
            success=True,
            code=PART_ONLY if refused > TOLERANCE else "",
            parcel=Parcel(commodity, moved),
            hold=used,
            refused=refused,
            limit=self.stowage().limit if refused > TOLERANCE else NEITHER,
        )

    def discharge(self, commodity, tonnes, hold=None):
        """
        Put cargo ashore.

        Args:
            commodity (Commodity): What is being discharged.
            tonnes (float): How much.
            hold (ShipRoom, optional): Which hold to work. Defaults to all of
                them, highest first.

        Returns:
            result (TransferResult): What came out.

        Notes:
            Highest hold first, the reverse of loading, and what a mate would do
            anyway: taking the weight off the top keeps her stiff throughout
            instead of leaving her tender halfway through the discharge.

        """
        wanted = max(0.0, float(tonnes))
        if wanted <= 0.0:
            return TransferResult(success=False, code=NOTHING_TO_MOVE)

        candidates = [hold] if hold is not None else list(reversed(self.holds))
        moved = 0.0
        used = None
        for candidate in candidates:
            if candidate is None:
                continue
            taken = candidate.discharge(commodity, wanted - moved)
            if taken.tonnes > 0.0:
                moved += taken.tonnes
                used = used or candidate
            if moved >= wanted - TOLERANCE:
                break

        if moved <= 0.0:
            return TransferResult(success=False, code=NOT_ABOARD, refused=wanted)

        refused = max(0.0, wanted - moved)
        return TransferResult(
            success=True,
            code=PART_ONLY if refused > TOLERANCE else "",
            parcel=Parcel(commodity, moved),
            hold=used,
            refused=refused,
        )
