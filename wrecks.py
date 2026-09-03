"""
What is left after she goes down.

A ship that founders should not simply be deleted. She was somewhere, she had things in
her, and both of those outlive her: casks and spars come up and drift away on the same
water everything else drifts on, and the hull goes down to the bottom and *stays there*,
findable by anybody who wrote down where she went.

**A wreck is a place, not an entry in a table.** `floating.sinking_depth` has always known
how deep a thing that has stopped floating has got, and stops it at the seabed rather than
letting it fall for ever. This is what finally asks it: she goes down at her own rate, and
where she comes to rest is where the water was deep when she sank.

**Depth is what makes salvage a decision.** A ship lost in five fathoms off a beach is a
salvage job; the same ship lost in a hundred is a story. Nothing else has to gate it - the
sea does, because the seabed is already modelled and she sank to a real place on it.

**What floats free is what was not stowed to stay.** Not all her cargo: a share of it, the
part that was in cask and on deck rather than struck down and lashed. That share drifts on
the current like everything else afloat, which means somebody who saw her go down and
worked out the set can go and find it.

"""

from dataclasses import dataclass

from .environment import clearance_at
from .floating import sinking_depth
from .results import Result

#: The share of what she carried that breaks free and floats.
#:
#: A sixth. Casks, spars, hatch covers, anything on deck or not struck down hard - and not
#: the rest, because a hold full of salt does not bob to the surface. Enough that a wreck
#: leaves a trail worth following and not so much that sinking her is a way of unloading her.
FLOATS_FREE = 0.17

#: How deep salvage can reach, in metres.
#:
#: Thirty. That is a hard day's work for a diver of the period with a line and no air, and
#: it is the number that turns "where did she sink?" into a question worth asking - a ship
#: lost on a bank is worth going back for and one lost off soundings is gone.
SALVAGE_DEPTH = 30.0

#: What one party recovers in a day, as a share of what is down there.
SALVAGED_PER_DAY = 0.25

NOT_A_WRECK = "not_a_wreck"
TOO_DEEP = "too_deep"
NOTHING_DOWN_THERE = "nothing_down_there"
NOT_THERE = "not_there"


@dataclass(frozen=True, kw_only=True)
class WreckResult(Result):
    """
    Where she lies, and what is left in her.

    Attributes:
        depth (float): How far down she has got, in metres.
        on_the_bottom (bool): Whether she has finished sinking.
        reachable (bool): Whether anybody can work on her.
        aboard (tuple): What is still in her, as parcels.

    """

    depth: float = 0.0
    on_the_bottom: bool = False
    reachable: bool = False
    aboard: tuple = ()


@dataclass(frozen=True, kw_only=True)
class SalvageResult(Result):
    """
    What came up.

    Attributes:
        commodity (str): What was recovered.
        tonnes (float): How much.
        left (float): How much of it is still down there.
        depth (float): How deep they were working.

    """

    commodity: str = ""
    tonnes: float = 0.0
    left: float = 0.0
    depth: float = 0.0


class Wrecked:
    """
    A hull that has gone down, and what can be got out of her.

    Notes:
        The same object she always was. A wreck is not a different kind of thing from a
        ship - she is a ship that has stopped floating, which is exactly what `Buoyancy`
        says about her, and making a separate typeclass for it would mean copying her
        position, her holds and her name somewhere else and then keeping the two in step.

    """

    def at_object_creation(self):
        """Set up this part of a newly created vessel."""
        super().at_object_creation()
        self.db.went_down_at = None

    @property
    def wrecked(self):
        """
        Returns:
            wrecked (bool): Whether she has stopped floating.

        """
        return not self.buoyancy.floats

    def water_here(self, now=None):
        """
        How deep the water is where she lies.

        Args:
            now (float, optional): Game time.

        Returns:
            depth (float): Metres.

        Notes:
            **The clearance under a hull of no draft is the depth of the water.** Asked of
            the same model the soundings and the groundings use, rather than a second one
            written for wrecks - so a wreck on a bank is on the bank the chart shows, and
            the tide is in the answer because it is in that model already.

        """
        here = self.maritime_position
        if here is None:
            return 0.0
        return max(0.0, clearance_at(here, 0.0, self._wreck_now(now)))

    def depth_now(self, now=None):
        """
        How far down she has got.

        Args:
            now (float, optional): Game time. Fetched if not given.

        Returns:
            depth (float): Metres below the surface.

        Notes:
            Worked out from when she sank rather than counted down on a tick, so a wreck
            nobody has looked at for a week is exactly as deep as one that was watched all
            the way down.

        """
        if not self.wrecked or self.db.went_down_at is None:
            return 0.0
        now = self._wreck_now(now)
        return sinking_depth(float(self.db.went_down_at), now, self.buoyancy, self.water_here(now))

    def wreck_report(self, now=None):
        """
        Args:
            now (float, optional): Game time.

        Returns:
            result (WreckResult): Where she lies, or a failure if she is still afloat.

        """
        if not self.wrecked:
            return WreckResult(success=False, code=NOT_A_WRECK)

        now = self._wreck_now(now)
        depth = self.depth_now(now)
        aboard = tuple(
            parcel for hold in self.holds for parcel in hold.stowed if parcel.tonnes > 0.0
        )
        return WreckResult(
            success=True,
            depth=depth,
            on_the_bottom=depth >= self.water_here(now) - 0.01,
            reachable=depth <= SALVAGE_DEPTH,
            aboard=aboard,
        )

    def _wreck_now(self, now=None):
        """
        Args:
            now (float, optional): Game time, if the caller has one.

        Returns:
            now (float): Game time in seconds.

        """
        if now is not None:
            return float(now)

        from . import config

        return config.time_provider().now()

    def go_down(self, now=None):
        """
        Mark the moment she stopped floating, and let what will float free do so.

        Args:
            now (float, optional): Game time.

        Returns:
            adrift (tuple): What came up, as floating objects.

        Notes:
            Called from the foundering, once. A wreck that recorded the time twice would
            reset her own descent and rise back towards the surface, which is a thing
            nobody wants to have to explain.

        """
        if self.db.went_down_at is not None:
            return ()

        self.db.went_down_at = self._wreck_now(now)
        return self.spill_cargo()

    def spill_cargo(self, share=FLOATS_FREE):
        """
        Let a share of what she carried break free and float.

        Args:
            share (float, optional): How much of it comes up.

        Returns:
            adrift (tuple): The floating objects, at her position.

        Notes:
            Taken out of her holds rather than copied out of them, so what floats away is
            no longer down there to be salvaged. Cargo counted twice is cargo somebody
            eventually notices.

        """
        from evennia.utils import create

        from .floating import BARREL_WINDAGE
        from .typeclasses import Flotsam

        here = self.maritime_position
        if here is None:
            return ()

        adrift = []
        for hold in self.holds:
            for parcel in tuple(hold.stowed):
                floated = parcel.tonnes * max(0.0, min(1.0, float(share)))
                if floated <= 0.0:
                    continue
                hold.discharge(parcel.commodity, floated)
                wreckage = create.create_object(
                    Flotsam, key=f"{floated:.1f} tons of {parcel.commodity.name}"
                )
                wreckage.maritime_position = here
                wreckage.windage = BARREL_WINDAGE
                wreckage.db.desc = (
                    "Casks and dunnage from a ship that is not here any more, riding low "
                    "and going wherever the water goes."
                )
                wreckage.db.tonnes = floated
                adrift.append(wreckage)
        return tuple(adrift)

    def salvage(self, commodity, tonnes, now=None):
        """
        Get something up out of her.

        Args:
            commodity (Commodity): What to work on.
            tonnes (float): How much to try for.
            now (float, optional): Game time.

        Returns:
            result (SalvageResult): What came up, or why nothing did.

        Notes:
            **Depth is the whole of the difficulty.** She sank where the water was as deep
            as it was, and that is already modelled - so a ship lost on a bank can be worked
            and one lost off soundings cannot, without a die being rolled or a skill being
            consulted.

        """
        where = self.wreck_report(now)
        if not where:
            return SalvageResult(success=False, code=NOT_A_WRECK)
        if not where.reachable:
            return SalvageResult(success=False, code=TOO_DEEP, depth=where.depth)

        down_there = sum(
            parcel.tonnes
            for hold in self.holds
            for parcel in hold.stowed
            if parcel.commodity.key == commodity.key
        )
        if down_there <= 0.0:
            return SalvageResult(success=False, code=NOTHING_DOWN_THERE, depth=where.depth)

        # Taken hold by hold until the day's work is made up, because what she was carrying
        # is spread through her and a diver going down for six tons does not care which
        # compartment they came out of.
        wanted = min(float(tonnes), down_there)
        got = 0.0
        for hold in self.holds:
            if got >= wanted:
                break
            got += hold.discharge(commodity, wanted - got).tonnes

        return SalvageResult(
            success=got > 0.0,
            code=None if got > 0.0 else NOTHING_DOWN_THERE,
            commodity=commodity.name,
            tonnes=got,
            left=max(0.0, down_there - got),
            depth=where.depth,
        )
