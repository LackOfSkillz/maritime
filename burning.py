"""
Fire aboard.

The best single mechanic in the source, and the reason is that fire is a *situation* rather
than a debuff. It has its own schedule, it competes with you for the one resource a ship
never has enough of, and it takes away the thing you would otherwise use to escape it.

Three rules do all the work:

**It escalates while you ignore it.** A fire that has just caught is a small problem. Every
minute nobody fights it, the chance it spreads goes up - and when it does spread the clock
resets, so a ship that has been burning unattended for a quarter of an hour is not facing one
fire that got worse, she is facing several. An unfought fire is not a slow loss; it is a
compounding one.

**Fighting it costs hands, with diminishing returns.** Every man on a bucket is a man not on
a gun, an oar, or a sheet. Doubling the fire party does not halve the fire, so there is a
point past which sending more people is simply disarming yourself.

**The pumps will not draw unless she stops.** This is the gem. The hoses go over the side,
and a ship with way on drags them. So a burning ship must choose between running and
surviving - and no hit-point model can produce that, because in a hit-point model damage
never asks you to give up your ability to manoeuvre in order to fix it.

To which we add the one the source implies and does not say outright: **canvas aloft is more
fire to catch.** Handing your sails is the other half of the same dilemma, because she cannot
run under bare poles either.

**What fire is not.** It is not a damage track. It is a process that *writes into* the tracks
that already exist - hull, rigging, and the people - which is why it lives in its own module
and why putting it out matters more than any amount of repair.

"""

import math
from dataclasses import dataclass

from .damage import HULL, RIGGING
from .results import Result
from .sailing import rigging_exposed

#: The chance a freshly-lit fire spreads, per minute, with nobody fighting it.
#:
#: Low, because most fires aboard were caught and beaten out. What makes fire dangerous is
#: not this number, it is what happens to it when nobody is free to go.
NEWLY_LIT = 0.02

#: Added to that chance for every further minute it goes unchecked.
#:
#: The whole mechanic. After ten unattended minutes a fire is far more likely to spread than
#: to sit still, and after twenty it is near enough certain - so the cost of being too busy
#: to fight it compounds instead of accumulating.
ESCALATION = 0.03

#: However long it burns, it never quite becomes a certainty. Leaves room for luck to be
#: the reason a ship survived, which is usually the reason a ship survived.
MOST_LIKELY = 0.9

#: Hands wanted to properly fight one seat of fire.
HANDS_PER_SEAT = 15.0

#: The exponent that makes more hands help less. Below one, so the first men to arrive are
#: worth far more than the last - which is why a fire party is a detachment and not the
#: whole watch.
DIMINISHING = 0.6

#: The most way she can carry and still have the pumps draw, in metres a second.
#:
#: A little under a knot. The hoses go over the side to the sea, and a ship moving drags them
#: astern and lifts them clear of the water.
PUMPING_SPEED = 0.5

#: What a fire party can still do with buckets while she runs.
#:
#: Not nothing - a bucket chain is real - but not enough, which is the point. She has to
#: choose.
BUCKETS_ONLY = 0.3

#: Hull damage a single seat of fire does per minute.
BURN_PER_MINUTE = 4.0

#: The share of that which goes into her people rather than into her fabric.
#:
#: Taken out first, and delivered in the units her weapons speak so that it routes through
#: `take_crew_casualties` like every other thing that hurts people - which means morale,
#: exhaustion, striking and mutiny all answer to a fire with no new wiring.
SCORCH_SHARE = 0.15

#: Of what is left, the share that goes into her rigging when there is canvas aloft.
RIGGING_SHARE = 0.5

#: More seats than this and there is nothing left to fight for.
MOST_SEATS = 8

NOT_BURNING = "not_burning"
ALREADY_ALIGHT = "already_alight"
NO_HANDS = "no_hands"


@dataclass(frozen=True, kw_only=True)
class BlazeResult(Result):
    """
    What the fire did in one stretch of time.

    Attributes:
        seats (int): How many separate fires are burning now.
        spread (bool): Whether it took hold somewhere new.
        doused (int): How many seats were put out.
        hull (float): Hull damage done.
        rigging (float): Rigging damage done.
        scorched (int): How many of her people it hurt.
        chance (float): What the spread chance had risen to.
        pumping (bool): Whether the pumps were drawing.
        effect (float): How much good the fire party was doing, 0 to 1.

    """

    seats: int = 0
    spread: bool = False
    doused: int = 0
    hull: float = 0.0
    rigging: float = 0.0
    scorched: int = 0
    chance: float = 0.0
    pumping: bool = False
    effect: float = 0.0


def pumps_draw(speed, limit=PUMPING_SPEED):
    """
    Whether the hoses reach the water.

    Args:
        speed (float): Her speed through the water, in metres a second.
        limit (float, optional): The most way the pumps will tolerate.

    Returns:
        drawing (bool): True if she is quiet enough to pump.

    Notes:
        The rule that makes fire a dilemma rather than a debuff. Everything else here is
        arithmetic; this is the decision.

    """
    return abs(float(speed)) <= limit


def hands_worth(hands, seats, per_seat=HANDS_PER_SEAT, falloff=DIMINISHING):
    """
    How much good a fire party of this size is doing.

    Args:
        hands (float): How many are on it.
        seats (int): How many separate fires they are fighting.
        per_seat (float, optional): Hands wanted for one seat.
        falloff (float, optional): The exponent that makes more help less.

    Returns:
        effect (float): From 0 to 1.

    Notes:
        Diminishing rather than linear, so the first men to arrive are worth several of
        the last. A captain who sends everybody has put out the fire and lost the fight,
        which is a trade worth being able to make badly.

    """
    hands = max(0.0, float(hands))
    wanted = per_seat * max(1, int(seats))
    if wanted <= 0.0:
        return 1.0
    return min(1.0, (hands / wanted) ** falloff)


def fighting_effect(hands, seats, speed, exposure=1.0):
    """
    What the fire party actually achieves, given how she is being sailed.

    Args:
        hands (float): How many are on it.
        seats (int): How many separate fires.
        speed (float): Her speed through the water, in metres a second.
        exposure (float, optional): How much of her rigging is spread, from
            `sailing.rigging_exposed`.

    Returns:
        effect (float): From 0 to 1.

    Notes:
        Two multipliers on the party's own worth, and both are choices somebody made:
        whether she is stopped, so the pumps draw, and whether her canvas is handed, so
        there is less alight to fight. A captain who will do neither has a fire party
        working at a fraction of itself.

    """
    effect = hands_worth(hands, seats)
    if not pumps_draw(speed):
        effect *= BUCKETS_ONLY
    # Canvas aloft is both more to burn and more to be busy with. At bare poles the
    # exposure term is at its floor and the party works at its best.
    return effect * (1.0 - 0.5 * max(0.0, min(1.0, exposure)))


def spread_chance(unchecked, effect=0.0, exposure=1.0):
    """
    The chance the fire takes hold somewhere new.

    Args:
        unchecked (float): Seconds since it last spread or was fought back.
        effect (float, optional): What the fire party is achieving, 0 to 1.
        exposure (float, optional): How much of her rigging is spread.

    Returns:
        chance (float): From 0 to `MOST_LIKELY`.

    Notes:
        **The clock is the mechanic.** It rises without limit until it is capped, and it
        resets when the fire spreads - so an unfought fire is not one problem getting
        worse but a growing number of separate ones, each with its own clock.

    """
    minutes = max(0.0, float(unchecked)) / 60.0
    chance = (NEWLY_LIT + ESCALATION * minutes) * max(0.0, min(1.0, exposure))
    chance *= 1.0 - max(0.0, min(1.0, effect))
    return max(0.0, min(MOST_LIKELY, chance))


def douse_chance(effect, elapsed):
    """
    The chance a fire party puts one seat out.

    Args:
        effect (float): What they are achieving, 0 to 1.
        elapsed (float): Seconds of work.

    Returns:
        chance (float): From 0 to 1.

    Notes:
        Exponential in the time spent, so a party that is achieving something will get
        there eventually and one achieving nothing never will, however long it stands
        about. It also means the answer does not depend on how often the scheduler ran.

    """
    effect = max(0.0, min(1.0, float(effect)))
    if not effect:
        return 0.0
    minutes = max(0.0, float(elapsed)) / 60.0
    return 1.0 - math.exp(-effect * minutes)


def burn_damage(seats, elapsed, per_minute=BURN_PER_MINUTE):
    """
    What the fire consumes in this stretch of time.

    Args:
        seats (int): How many separate fires.
        elapsed (float): Seconds.
        per_minute (float, optional): Damage one seat does in a minute.

    Returns:
        damage (float): Total, before it is split between hull and rigging.

    """
    return max(0, int(seats)) * per_minute * (max(0.0, float(elapsed)) / 60.0)


class Burns:
    """
    A hull that can catch fire, and the people who fight it.

    Notes:
        The fire party is a standing number rather than an order repeated every tick.
        Somebody says how many hands are on it and they stay on it, because that is how a
        captain thinks about it and because a fire nobody had to keep re-ordering people
        to fight would not compete with anything.

    """

    def at_object_creation(self):
        """Set up this part of a newly created vessel."""
        super().at_object_creation()
        self.db.fire_seats = 0
        self.db.fire_unchecked = 0.0
        self.db.fire_party = 0.0

    @property
    def seats_of_fire(self):
        """
        Returns:
            seats (int): How many separate fires are burning.

        """
        return int(self.db.fire_seats or 0)

    @property
    def alight(self):
        """
        Returns:
            alight (bool): Whether anything aboard is burning.

        """
        return self.seats_of_fire > 0

    @property
    def fire_party(self):
        """
        Returns:
            hands (float): How many are fighting it.

        """
        return float(self.db.fire_party or 0.0)

    def catch_fire(self, seats=1):
        """
        Something aboard has taken light.

        Args:
            seats (int, optional): How many separate fires start.

        Returns:
            result (BlazeResult): Successful if anything caught.

        Notes:
            Called by whatever set her alight - an incendiary, a shot into something
            combustible, a lantern adrift in a seaway. This module owns what a fire *does*
            and not what starts one, because the second is a question about the world.

        """
        seats = max(0, int(seats))
        if not seats:
            return BlazeResult(success=False, code=NOT_BURNING, seats=self.seats_of_fire)

        before = self.seats_of_fire
        self.db.fire_seats = min(MOST_SEATS, before + seats)
        if not before:
            # A fresh fire starts its clock now. Inheriting the clock of a fire that was
            # put out an hour ago would have a new one spreading almost at once.
            self.db.fire_unchecked = 0.0
        return BlazeResult(success=True, seats=self.seats_of_fire)

    def fight_fire(self, hands):
        """
        Put a party on it.

        Args:
            hands (float): How many to send. Zero calls them off.

        Returns:
            result (BlazeResult): Failed only if she is not burning.

        Notes:
            The hands are *committed*. What they cost is not paid here - it is paid by
            whatever wanted them for the guns or the sheets and now cannot have them.

        """
        if not self.alight:
            return BlazeResult(success=False, code=NOT_BURNING, seats=0)

        self.db.fire_party = max(0.0, float(hands))
        return BlazeResult(
            success=True,
            seats=self.seats_of_fire,
            effect=self.fire_fighting_effect(),
            pumping=pumps_draw(self.speed),
        )

    def fire_fighting_effect(self):
        """
        Returns:
            effect (float): What her fire party is achieving, 0 to 1.

        """
        if not self.alight:
            return 0.0
        return fighting_effect(
            self.fire_party,
            self.seats_of_fire,
            self.speed,
            rigging_exposed(self.sail_plan),
        )

    def douse(self):
        """
        Put every fire out at once.

        Returns:
            doused (int): How many seats there were.

        Notes:
            Not a command. It exists so that a game can end a fire for a reason this
            contrib does not model - a spell, a squall, a harbour's engine - without
            reaching into attributes.

        """
        seats = self.seats_of_fire
        self.db.fire_seats = 0
        self.db.fire_unchecked = 0.0
        self.db.fire_party = 0.0
        return seats

    def work_fire(self, elapsed, roll=None):
        """
        Let the fire burn for a stretch of time.

        Args:
            elapsed (float): Game seconds.
            roll (callable, optional): Returns a float from 0 to 1. Fetched from the
                damage stream if not given.

        Returns:
            result (BlazeResult or None): What it did, or None if nothing is burning.

        Notes:
            Order matters. She burns first, then the party gets its chance to put a seat
            out, and only if they fail does the fire get its chance to spread. A fire that
            could spread and be doused in the same tick would be resolving two contests
            about the same seconds.

        """
        if not self.alight:
            return None

        if roll is None:
            from . import config
            from .rng import DAMAGE

            roll = config.rng_context().stream(DAMAGE).random

        exposure = rigging_exposed(self.sail_plan)
        effect = self.fire_fighting_effect()
        seats = self.seats_of_fire

        # --- what it consumes -----------------------------------------------
        total = burn_damage(seats, elapsed)
        scorch = total * SCORCH_SHARE
        fabric = total - scorch
        rigging = fabric * RIGGING_SHARE * exposure
        hull = fabric - rigging
        if hull:
            self.take_damage(HULL, hull)
        if rigging:
            self.take_damage(RIGGING, rigging)
        scorched = self.take_crew_casualties(scorch) if scorch else 0

        # --- fought, or spreading -------------------------------------------
        doused = 0
        spread = False
        chance = spread_chance(self.db.fire_unchecked or 0.0, effect, exposure)

        if effect and roll() < douse_chance(effect, elapsed):
            doused = 1
            self.db.fire_seats = max(0, seats - 1)
            # Beating one seat back buys time on the others. It does not put the clock to
            # zero, which would make a large fire indefinitely survivable by dousing one
            # seat over and over.
            self.db.fire_unchecked = max(0.0, float(self.db.fire_unchecked or 0.0) * 0.5)
        elif roll() < chance:
            spread = True
            self.db.fire_seats = min(MOST_SEATS, seats + 1)
            self.db.fire_unchecked = 0.0
        else:
            self.db.fire_unchecked = float(self.db.fire_unchecked or 0.0) + max(0.0, float(elapsed))

        if not self.seats_of_fire:
            self.db.fire_party = 0.0
            self.db.fire_unchecked = 0.0

        return BlazeResult(
            success=True,
            seats=self.seats_of_fire,
            spread=spread,
            doused=doused,
            hull=hull,
            rigging=rigging,
            scorched=scorched,
            chance=chance,
            pumping=pumps_draw(self.speed),
            effect=effect,
        )
