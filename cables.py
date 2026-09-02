"""
Springing on a cable, and cutting it.

A ship at anchor is currently a ship that can be shot at. She lies where the ground put her,
her broadside points wherever her head happens to lie, and everything the gunnery model knows
about arcs works against her. That is wrong twice over: it makes anchoring a mistake, and it
leaves out the way harbours were actually defended.

**A spring is a line from the capstan to the anchor cable.** Haul on it and the ship comes
round about her own anchor, without way, without wind, and without answering her helm. It is
how a ship laid her broadside across a channel and kept it there, and it is why a squadron
anchored in line was a serious thing to sail past rather than a row of sitting targets.

Three things come with it, and the third is the one with teeth:

    spring on the cable    lay your broadside where you want it, slowly
    a steady platform      an anchored gun is a better gun, because the deck is still
    cut the cable          under way this minute, and no anchor until you rig a spare

**The mechanism was already here.** `motion.advance` takes a `turn_floor` - "degrees per
second of turning available regardless of speed - a backed sail, a sweep, a warp, a tug" -
which is a spring described without naming it. So this does not add a way to turn; it adds a
reason, and supplies the number.

**Cutting is the interesting decision.** A ship that has to get under way *now* - a fireship
driving down on her, a lee shore making up - can be free of the ground in the time it takes
to swing an axe. She then has no anchor. She cannot bring up, cannot ride out a blow, cannot
hold herself off anything, and getting a spare over the bows is hours of work with hands she
may not have. That consequence outlives the fight, which is what makes it a decision rather
than a button.

"""

import math
from dataclasses import dataclass

from .results import Result

#: Degrees a minute a hull of `REFERENCE_LENGTH` comes round on a spring.
#:
#: Capstan work, not steering. Ninety degrees in a quarter of an hour for a middling ship,
#: which is slow enough that laying yourself across a channel is something you do *before*
#: anybody appears and not after.
SPRING_RATE = 6.0

#: The hull the rate above is quoted for, in metres.
#:
#: Longer ships come round more slowly for the same reason they do everything more slowly:
#: there is more of them to move and the water has more of it to resist.
REFERENCE_LENGTH = 30.0

#: How long it takes to get a spare anchor over the bows, in seconds.
#:
#: Most of a working day. A bower anchor is the heaviest single thing aboard, it lives in the
#: hold when it is not on the bottom, and putting one over the side is a job for the whole
#: watch with tackles. Anybody who cuts should understand they have spent the anchor.
RIGGING_A_SPARE = 6.0 * 3600.0

#: The fraction of her company that has to be fit to rig one at all.
LEAST_HANDS = 0.4

NOT_ANCHORED = "not_anchored"
NO_ANCHOR = "no_anchor"
ANCHOR_ABOARD = "anchor_aboard"
STILL_RIGGING = "still_rigging"
NO_HANDS = "no_hands"
NOT_SPRUNG = "not_sprung"


@dataclass(frozen=True, kw_only=True)
class SpringResult(Result):
    """
    What came of hauling on a spring.

    Attributes:
        heading (float): Where her head lies now, in degrees.
        wanted (float): Where it is being hauled to.
        came_round (float): Degrees of it she made this time.
        remaining (float): Degrees still to come.
        seconds_more (float): How much longer at this rate.

    """

    heading: float = 0.0
    wanted: float = 0.0
    came_round: float = 0.0
    remaining: float = 0.0
    seconds_more: float = 0.0


@dataclass(frozen=True, kw_only=True)
class CableResult(Result):
    """
    What came of cutting a cable, or of rigging a spare.

    Attributes:
        ready_at (float): Game time when she has an anchor again, if she is rigging one.
        seconds_more (float): How long that is from now.

    """

    ready_at: float = 0.0
    seconds_more: float = 0.0


def spring_rate(length, rate=SPRING_RATE, reference=REFERENCE_LENGTH):
    """
    How fast she comes round on a spring.

    Args:
        length (float): Her length overall, in metres.
        rate (float, optional): Degrees a minute at the reference length.
        reference (float, optional): The length that rate is quoted for.

    Returns:
        rate (float): Degrees a minute.

    Notes:
        Inverse in her length, like everything else here that is really about how much
        ship the hands are moving. A launch comes round while a two-decker is still
        getting the messenger on the capstan.

    """
    return rate * reference / max(float(length), 1.0)


def _shortest_way(heading, wanted):
    """
    Args:
        heading (float): Where her head lies.
        wanted (float): Where it should lie.

    Returns:
        difference (float): Signed degrees, -180 to 180.

    """
    return (float(wanted) - float(heading) + 180.0) % 360.0 - 180.0


def hauled_round(heading, wanted, seconds, length):
    """
    Where her head lies after a spell at the capstan.

    Args:
        heading (float): Where it lies now, in degrees.
        wanted (float): Where it is being hauled to.
        seconds (float): Game seconds of work.
        length (float): Her length overall, in metres.

    Returns:
        heading (float): Where it lies afterwards, normalised to 0-360.

    Notes:
        She takes the short way round, which is the only way a spring can take her: the
        cable is made fast at one point and hauling brings that point towards you. A ship
        being sprung the long way about would be one being warped in a circle around her
        own anchor, and nobody has ever had that much patience or that much cable.

    """
    difference = _shortest_way(heading, wanted)
    if not difference:
        return float(heading) % 360.0

    most = spring_rate(length) * (max(0.0, float(seconds)) / 60.0)
    came = math.copysign(min(most, abs(difference)), difference)
    return (float(heading) + came) % 360.0


class Springs:
    """
    A hull that can be hauled round on her own cable, and can cut it.

    Notes:
        Three states rather than two. She has an anchor and it is catted; she has an
        anchor and it is on the ground; or she has none, because she cut it away and the
        spare is not over the bows yet. The third is the one worth modelling - a ship
        without an anchor is a ship with nowhere safe to stop.

    """

    def at_object_creation(self):
        """Set up this part of a newly created vessel."""
        super().at_object_creation()
        self.db.spring_to = None
        self.db.anchor_ready_at = 0.0

    # --- the spring ---------------------------------------------------------

    @property
    def sprung_to(self):
        """
        Returns:
            bearing (float or None): Where her head is being hauled, or None if no spring
                is rigged.

        """
        bearing = self.db.spring_to
        return None if bearing is None else float(bearing)

    def spring(self, bearing):
        """
        Rig a spring and start hauling her head round.

        Args:
            bearing (float): Where her head should lie, in degrees.

        Returns:
            result (SpringResult): Failed if she is not lying to her anchor.

        Notes:
            Ordered once and worked at every tick afterwards, like a course rather than
            like a manoeuvre. Hauling a ship round takes long enough that a command which
            did it all at once would be lying about the one thing that makes a spring
            interesting - that it is slow, and that somebody may arrive while you are
            still at it.

        """
        if not self.anchored:
            return SpringResult(success=False, code=NOT_ANCHORED, heading=self.heading)

        wanted = float(bearing) % 360.0
        self.db.spring_to = wanted
        remaining = abs(_shortest_way(self.heading, wanted))
        rate = spring_rate(self.length)
        return SpringResult(
            success=True,
            heading=self.heading,
            wanted=wanted,
            remaining=remaining,
            seconds_more=(remaining / rate) * 60.0 if rate else 0.0,
        )

    def unrig_spring(self):
        """
        Take the spring off, and leave her lying as she is.

        Returns:
            unrigged (bool): True if one was rigged.

        """
        if self.db.spring_to is None:
            return False
        self.db.spring_to = None
        return True

    def work_spring(self, elapsed):
        """
        Haul on her for a stretch of time.

        Args:
            elapsed (float): Game seconds.

        Returns:
            result (SpringResult): Failed if she is not anchored or has no spring rigged.

        Notes:
            Called from the tick while she is held fast, which is the one place a vessel
            changes heading without changing position. She is not making way and she is
            not answering her helm; she is being pulled round a point.

        """
        wanted = self.sprung_to
        if wanted is None:
            return SpringResult(success=False, code=NOT_SPRUNG, heading=self.heading)
        if not self.anchored:
            return SpringResult(success=False, code=NOT_ANCHORED, heading=self.heading)

        before = self.heading
        after = hauled_round(before, wanted, elapsed, self.length)
        came = abs(_shortest_way(before, after))
        if came:
            self.heading = after
            self.ndb.maritime_dirty = True

        remaining = abs(_shortest_way(after, wanted))
        if remaining < 0.5:
            # Close enough that another spell at the capstan would move her a fraction of
            # a degree. Leaving the spring rigged would have the hands working for ever.
            self.heading = wanted
            self.db.spring_to = None
            remaining = 0.0

        rate = spring_rate(self.length)
        return SpringResult(
            success=True,
            heading=self.heading,
            wanted=wanted,
            came_round=came,
            remaining=remaining,
            seconds_more=(remaining / rate) * 60.0 if rate else 0.0,
        )

    # --- the cable ----------------------------------------------------------

    @property
    def has_anchor(self):
        """
        Returns:
            has (bool): Whether there is an anchor aboard to let go.

        """
        ready = float(self.db.anchor_ready_at or 0.0)
        if not ready:
            return True
        return self._now() >= ready

    @property
    def rigging_a_spare(self):
        """
        Returns:
            seconds (float): How much longer until she has an anchor, or 0.0 if she has
                one now.

        """
        ready = float(self.db.anchor_ready_at or 0.0)
        return max(0.0, ready - self._now()) if ready else 0.0

    def cut_cable(self):
        """
        Cut the cable and be free of the ground at once.

        Returns:
            result (CableResult): Failed if she is not lying to her anchor.

        Notes:
            **The anchor is gone, not stowed.** It is on the bottom with a length of cable
            attached to it, and buoying it to come back for later is a thing a game may
            model if it wants a reason to return to a place. What this records is only
            that she has none aboard.

            She keeps no spring either - there is nothing left to spring on.

        """
        if not self.anchored:
            return CableResult(success=False, code=NOT_ANCHORED)

        self.anchored = False
        self.db.spring_to = None
        # One clock rather than a flag and a clock. Having no anchor is "ready at a time
        # that never comes", so a ship which never rigs a spare simply never gets one -
        # and there is no second piece of state to disagree with the first.
        self.db.anchor_ready_at = float("inf")
        return CableResult(success=True, seconds_more=float("inf"))

    def rig_a_spare(self, now=None):
        """
        Get the spare anchor over the bows.

        Args:
            now (float, optional): Game time. Fetched if not given.

        Returns:
            result (CableResult): Successful once the work is begun, carrying when she
                will have an anchor again.

        Notes:
            Begun rather than done. It is most of a day's work for most of the watch, and
            a ship that cut her cable at noon is not anchoring again before dark - which
            is the whole consequence, and the reason cutting is a decision.

        """
        if self.has_anchor:
            return CableResult(success=False, code=ANCHOR_ABOARD)

        started = self._now() if now is None else float(now)
        pending = self.rigging_a_spare
        if pending and pending != float("inf"):
            return CableResult(
                success=False,
                code=STILL_RIGGING,
                ready_at=float(self.db.anchor_ready_at),
                seconds_more=pending,
            )

        # Asked the way kedging asks it, from casualties rather than from a second count
        # of who is fit - two answers to one question drift the first time either changes.
        company = self.company
        if company is not None and (1.0 - company.casualty_fraction) < LEAST_HANDS:
            return CableResult(success=False, code=NO_HANDS)

        ready = started + RIGGING_A_SPARE
        self.db.anchor_ready_at = ready
        return CableResult(success=True, ready_at=ready, seconds_more=RIGGING_A_SPARE)

    def _now(self):
        """
        Returns:
            now (float): Game time in seconds.

        """
        from . import config

        return config.time_provider().now()
