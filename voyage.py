"""
The sailing master: enough automation to get her from one mark to the next.

A ship under way needs somebody watching the course and the canvas the whole time, and a
player cannot be that person for three hours of a passage. This is the smallest set of
judgements that lets her sail herself between marks:

    steer for the next mark, allowing for the set
    carry what the wind will let her carry
    take the way off her coming up to the last one

**Deliberately not standing orders.** No conditions, no priorities, no evading a hostile or
diverting for shelter or investigating a distress signal. Those need a rules engine with
conflict resolution, and they are their own phase; putting a first version of them in here,
in the mate's judgement, is how a small honest automation quietly becomes an unreviewable
one. What this does is the four things a competent hand does without being told.

**It uses the same orders a player would give.** The sailing master sets a heading and a
sail plan and nothing else - it has no private channel to the hull, cannot exceed what the
rig allows, and is subject to every rule a human captain is. If she cannot lay the mark
because the current is too strong, the automation is as stuck as anyone would be, and says
so rather than cheating.

"""

from .buoyage import Clearance, keep_clear
from .config import time_provider
from .currents import course_to_steer
from .motion import HelmOrders
from .sailing import FURLED, WEATHER_PLANS

# How far off the last mark she starts taking the way off her, in metres. Far
# enough that a hull with real inertia is down to a walk by the time she gets
# there rather than arriving at cruising speed and going straight past.
APPROACH_DISTANCE = 800.0

# The slowest she will be asked to go on an approach, as a fraction of what she
# could make. Below this she loses steerage and stops answering her helm, which
# is a worse problem than arriving briskly.
MINIMUM_APPROACH = 0.15


def course_for_mark(position, mark, speed, current):
    """
    What to steer to make good the course to a mark.

    Args:
        position (WorldPosition): Where she is.
        mark (WorldPosition): Where she is going.
        speed (float): Speed through the water, in metres per second.
        current (CurrentVector): The set and drift she is in.

    Returns:
        heading (float): The compass course to steer, in degrees.

    Notes:
        The whole point of knowing the set. Steering straight at a mark in a
        cross-current walks her steadily downstream of it and she arrives
        somewhere else; the sailing master crabs up into the stream by exactly
        as much as it is setting her down.

        If the water is running harder than she can sail, no heading makes the
        track good and `course_to_steer` says so. Then she steers straight for
        the mark and does her best, which is what a real crew would do and is
        honest about being insufficient - the alternative would be inventing a
        heading that does not work.

    """
    track = position.bearing_to(mark)
    steered = course_to_steer(track, speed, current)
    return track if steered is None else steered


def sail_for_wind(wind, plans=WEATHER_PLANS):
    """
    The most canvas the wind will let her carry.

    Args:
        wind (WindVector): The wind on her.
        plans (iterable, optional): The sail plans available.

    Returns:
        plan (SailPlan): What to set.

    Notes:
        Takes the largest plan still inside its own safe wind, so she shortens
        sail as it freshens and shakes out reefs as it drops. That is one
        judgement, made from one number already on every plan - a mate who did
        nothing else all passage would still be worth their berth.

        Falls back to bare poles when it is blowing harder than anything is rated
        for, which is the correct answer and not a failure to find one.

        Chooses from the *weather* plans rather than from everything she can set.
        Fighting sail stands more wind than working sail, so a mate picking the
        largest plan the weather allows would set it in a fresh breeze and clear her
        for action on a quiet passage with nothing in sight. What a plan is for is
        not written in its sail area.

    """
    carriable = [plan for plan in plans if plan.area > 0.0 and wind.speed <= plan.safe_wind]
    if not carriable:
        return FURLED
    return max(carriable, key=lambda plan: plan.area)


#: How far ahead the sailing master sounds, in seconds of running.
#:
#: A minute and a half. Long enough that a ship doing six metres a second has five hundred
#: metres and most of two minutes to take the way off her, which is comfortable for a hull
#: whose deceleration is measured in tenths of a metre per second squared. Short enough that
#: he is reading the water he is about to cross rather than navigating - the difference
#: between a leadsman and a chart table.
LOOKAHEAD_SECONDS = 90.0

#: How much water the sailing master wants beyond what she draws, in metres.
#:
#: Two metres, on top of the metre `passage.UNDER_KEEL` already asks for. That is not
#: timidity: he is sounding water she will not reach for a minute and a half, and the tide
#: moves about two metres here in that direction over an afternoon. He looked at one state
#: of tide and grounded at another, in three point seven eight metres of water drawing two,
#: with a recorded clearance of minus fifteen centimetres.
#:
#: Deliberately more than the bare passability check. "Could a ship get through here" and
#: "would a prudent mate take her through here" are different questions, and he is asked
#: the second one. A captain who wants the first can take the con.
MASTER_MARGIN = 2.0

#: How far he will come off his course to find water, in degrees, and in what steps.
#:
#: Sixty degrees, five at a time. Beyond about that he is not avoiding an obstacle any
#: more - a ship steered ninety degrees off her course is going somewhere else - and the
#: honest thing at that point is to stop and say so rather than to wander.
FALL_OFF_LIMIT = 60.0
FALL_OFF_STEP = 5.0

#: And the least he looks, in metres, however slowly she is going.
#:
#: Two hundred. A ship stopped in the water is still being set by the stream and blown by
#: the wind, and a look-ahead that shrank to nothing as she slowed would go blind exactly
#: when she was least able to do anything about what it found.
LOOKAHEAD_METRES = 200.0


def approach_speed(distance, cruising, final=False):
    """
    How fast to be going, this far off the mark.

    Args:
        distance (float): How far to the mark, in metres.
        cruising (float): What she would otherwise make, in metres per second.
        final (bool, optional): True if this is the last mark of the passage.

    Returns:
        speed (float): What to ask for, in metres per second.

    Notes:
        Only the last mark. The ones in between are places to pass, and slowing
        for each of them would turn a passage into a series of stops - a buoy is
        rounded at whatever speed she happens to be doing.

        Never asks for less than a crawl, because a vessel below steerage way
        stops answering her helm, and a ship that cannot steer on her final
        approach is a worse problem than one arriving briskly.

    """
    if not final or distance >= APPROACH_DISTANCE or cruising <= 0.0:
        return cruising
    fraction = max(MINIMUM_APPROACH, distance / APPROACH_DISTANCE)
    return cruising * fraction


class Conned:
    """
    Whether the sailing master has the con, and what he does with it.

    Notes:
        The Evennia-side face of this module. He sets a heading and a sail plan
        through exactly the same properties a player would, so he cannot exceed
        the rig, cannot ignore the weather, and is bound by every rule a human
        captain is.

    """

    def at_object_creation(self):
        """Set up this part of a newly created vessel."""
        super().at_object_creation()
        self.db.under_con = False

    @property
    def under_con(self):
        """
        Returns:
            conned (bool): True if the sailing master is working her.

        """
        return bool(self.db.under_con)

    @under_con.setter
    def under_con(self, value):
        """
        Args:
            value (bool): Whether to hand him the con.

        """
        self.db.under_con = bool(value)

    def work_her(self):
        """
        Steer for the next mark and carry what the wind allows.

        Returns:
            worked (bool): True if he did anything.

        Notes:
            Called from the tick, before movement, so his orders take effect on
            the same step a player's would. He gives up the con when the passage
            is run rather than holding it and doing nothing, because a mate who
            has finished should say so.

        """
        if not self.under_con:
            return False

        # He has no private channel to the hull. Made fast, anchored or aground, he is as
        # stuck as anybody - and this has to be asked here as well as in the tick, because
        # he now brings her up himself when the water shuts in front of her. Without it he
        # would let go the anchor and then go on giving helm orders to a ship riding to it.
        if self.held_by():
            return False

        mark = self.next_mark()
        if mark is None:
            # Furl before handing back the con. Ordering no speed stops a boat
            # under oars and does nothing at all to one under canvas - the sails
            # simply drive her again on the next tick - so a mate who reported the
            # passage made and left her running was leaving her unattended at four
            # knots. She sailed twelve kilometres past her last mark before a
            # scenario noticed.
            if self.sail_plan.area > 0.0:
                self.sail_plan = FURLED
            self.orders = HelmOrders(heading=self.heading, speed=0.0)
            self.under_con = False

            # The one standing order he takes. Everything else he does is steering,
            # carrying sail and taking the way off her; going alongside is a decision, and
            # he makes it only because somebody told him to before the passage began - see
            # `passage.make_for`. Carried out *after* the con is given back, so that a
            # berth he cannot take leaves her lying off under the captain's hand rather
            # than under a mate who has already reported the passage made.
            from .passage import take_her_alongside

            berth = take_her_alongside(self)
            self.narrator.passage_made()

            # Announced as well as narrated. The narrator tells the people aboard; this
            # tells the game, which is what a career counts.
            from .career import passage_made

            passage_made(self, sailed=self.stream_the_log())
            if berth is not None:
                self.narrator.gone_alongside(berth)
            return False

        wind = self.wind_here()
        plan = sail_for_wind(wind)
        if plan.key != self.sail_plan.key and not self.working_aloft:
            # Through the same seam a captain's order goes through, so the watch is
            # no faster at it than the hands are. A mate who could re-rig the ship
            # instantly while the captain waited four minutes would make ordering
            # sail yourself strictly worse than saying nothing.
            seconds = self.order_sail(plan, time_provider().now())
            if seconds > 0.0:
                self.narrator.hands_aloft(plan, seconds)
            else:
                self.narrator.trimmed(plan)

        position = self.maritime_position
        heading = course_for_mark(position, mark.position, self.speed, self.current_here())

        final = self.route and mark is self.route.waypoints[-1]
        wanted = approach_speed(
            position.horizontal_distance_to(mark.position),
            self.working_limits.max_speed,
            final=bool(final),
        )
        # Give marked dangers their berth. He is steering anyway, so the alteration
        # costs the player nothing they did not already delegate - and a mate who
        # sailed a plotted course straight over a cardinal would not be a mate.
        clearance = self.clear_of_marks(heading)
        if clearance.mark is not None:
            heading = clearance.heading
        # Told every tick, including the ticks with nothing to report, so the
        # narrator can tell "still clearing the same mark" from "a new one" and say
        # it once rather than every two seconds.
        self.narrator.giving_a_berth(clearance.watching, clearance.altered)

        # **He does not sail her onto ground he can see.**
        #
        # Everything above is about where she is going; this is the one thing that
        # overrides it. A master who runs the ship on because the course said so is not a
        # master, and a game that puts a player aground on a passage it planned itself has
        # no defence at all - which is exactly what happened, at six metres a second, two
        # hundred metres from a spit that was on no chart because nobody had surveyed it.
        # No margin on the last leg: see `water_ahead`. A berth is shallow on purpose.
        spare = 0.0 if final else None
        if not self.water_ahead(heading, wanted, margin=spare):
            # He falls off, which is not pilotage. Working a way through a bank to a place
            # on the far side of it is a judgement he is explicitly not given; declining to
            # steer at ground and taking the nearest heading that is clear is what any
            # helmsman does without being told, and stopping dead instead leaves a ship
            # holding station off a rock for ever - which was the first version, and is a
            # different way of being stuck.
            fallen = self.fall_off(heading, wanted, margin=spare)
            if fallen is None:
                # **He lets go, rather than merely stopping.**
                #
                # Taking the way off her and doing nothing else was the first version, and
                # it is not seamanship - it is a slower grounding. A ship stopped in a
                # tideway off a lee shore is still going somewhere, and this one did: she
                # came to rest in two fathoms, the stream set her down at eight tenths of a
                # knot, and twenty minutes later she was on the beach with the mate's
                # warning still the last thing anybody had been told.
                #
                # An anchor is what holds a ship that cannot sail. He brings her up where
                # the water is, and there she stays until the captain has a better idea.
                self.narrator.shoal_ahead()
                self.orders = HelmOrders(heading=self.heading, speed=0.0)
                self.bring_up_short()
                return True
            self.narrator.falling_off(heading, fallen)
            heading = fallen

        # Told every tick, including the ticks with nothing to report, so the warning is
        # forgotten the moment the water opens and the next bank is announced properly.
        self.narrator.shoal_ahead(clear=True)

        self.orders = HelmOrders(heading=heading, speed=wanted)
        return True

    def bring_up_short(self):
        """
        Let go the anchor because there is nowhere to sail to.

        Returns:
            brought_up (bool): Whether she was anchored by this.

        Notes:
            Only once she has lost her way. Letting go with speed on her is how cables part
            and anchors are left on the bottom, which the `anchor` command already refuses
            for the same reason - so he waits, exactly as a captain would, and the tick
            after next brings her up.

            He keeps the con. The passage is not abandoned: the water may serve on the next
            tide, and a mate who threw the order away because he had to anchor once would
            have to be given it again every time. `belay` is how a captain takes it back.

        """
        from .commands.base import MAX_ANCHORING_SPEED

        if self.anchored or abs(self.speed) > MAX_ANCHORING_SPEED:
            return False
        self.anchored = True
        self.narrator.brought_up_short()
        return True

    def weigh_for_passage(self):
        """
        Bring the anchor home, because a passage was ordered.

        Returns:
            weighed (bool): Whether she was got under way.

        Notes:
            Through the ship's own property rather than through the command, so the capstan
            turns for exactly the same reason and with exactly the same effect as when a
            captain calls for it. A mate with a private way of weighing anchor is a mate who
            can weigh one that is fouled.

            Announced, and it has to be. Somebody who clicked a harbour on a chart and found
            his ship under way with no word said would reasonably wonder what else had been
            decided for him.

        """
        if not self.anchored:
            return False
        self.anchored = False
        self.narrator.weighed_for_passage()
        return True

    def water_ahead(self, heading, speed, seconds=None, margin=None):
        """
        Whether there is water on the course she is about to be given.

        Args:
            heading (float): The course, in degrees.
            speed (float): What she is about to be asked for, in metres per second.
            seconds (float, optional): How far ahead to look, in seconds of running.
            margin (float, optional): How much water he wants beyond her draught. Defaults
                to `MASTER_MARGIN`; zero on the last leg, where the berth is a place
                somebody has already said she fits.

        Returns:
            clear (bool): True if she can hold this course for the look-ahead.

        Notes:
            **A lead, not a chart.** He sounds the water he is about to sail over and no
            further, which is what the man in the chains can actually tell him. The
            distance is how far she runs in `LOOKAHEAD_SECONDS` at the speed she is being
            given, with a floor under it so that a ship barely moving still looks far
            enough ahead to stop.

            **The margin comes off on the final approach.** A quay is in shallow water by
            definition - that is what a quay is - so a mate carrying two metres of spare
            water everywhere will not take a ship to her own berth, which is what happened:
            he steered for the pier and refused to give her way, for ever. The last leg has
            already been checked by `passage.can_reach` against the berth's own advertised
            depth, which is somebody's statement that she fits. Beyond that it is his job to
            go in slowly, and `approach_speed` is where he does.

            True when there is no world to sound. A game with no ground has no banks, and
            refusing to sail because nothing could be measured would be the wrong failure.

        """
        world = self.map_here()
        here = self.maritime_position
        if world is None or here is None:
            return True

        from .passage import water_along

        look = max(
            LOOKAHEAD_METRES,
            abs(float(speed)) * (LOOKAHEAD_SECONDS if seconds is None else seconds),
        )
        wanted = MASTER_MARGIN if margin is None else float(margin)
        return water_along(here, here.moved(heading, look), self.draft + wanted, world)

    def water_before_her(self, speed, seconds=None):
        """
        The least water on the stretch she is about to cross.

        Args:
            speed (float): How fast she is going, in metres per second.
            seconds (float, optional): How far ahead to look, in seconds of running.

        Returns:
            found (GroundingResult or None): The shallowest contact on the corridor ahead,
                or None if there is nothing to sound with.

        Notes:
            The same look-ahead the sailing master uses, deliberately - so a captain
            steering by hand is warned of exactly what would have stopped his mate, and the
            two never disagree about where the water goes.

        """
        from .grounding import check_swept_grounding
        from .voyage import LOOKAHEAD_METRES, LOOKAHEAD_SECONDS

        world = self.map_here()
        here = self.maritime_position
        if world is None or here is None:
            return None

        look = max(
            LOOKAHEAD_METRES,
            abs(float(speed)) * (LOOKAHEAD_SECONDS if seconds is None else seconds),
        )
        return check_swept_grounding(
            here,
            here.moved(self.heading, look),
            self.heading,
            self.draft,
            0.0,
            self.length,
            self.beam,
            world,
            time_provider().now(),
        )

    # --- persistence --------------------------------------------------------

    def fall_off(self, heading, speed, margin=None):
        """
        The nearest heading either side of this one with water on it.

        Args:
            heading (float): The course he would have steered.
            speed (float): What she is being asked for, in metres per second.
            margin (float, optional): How much water he wants beyond her draught.

        Returns:
            course (float or None): A clear heading, or None if the water is foul all
                round the arc he is allowed to look through.

        Notes:
            Tried in pairs, nearest first, so the answer is the smallest alteration that
            works and she does not swing forty degrees to avoid something ten would have
            cleared. Both sides at each step, because which way is better depends on where
            the deep water is and he has no way of knowing without looking.

            Bounded to `FALL_OFF_LIMIT`. A mate who would put the ship on any heading at
            all to keep moving is a mate who will sail her away from where she is going,
            and past a right angle he is no longer avoiding an obstacle - he is choosing a
            different voyage.

        """
        step = FALL_OFF_STEP
        while step <= FALL_OFF_LIMIT:
            for side in (1.0, -1.0):
                tried = (heading + side * step) % 360.0
                if self.water_ahead(tried, speed, margin=margin):
                    return tried
            step += FALL_OFF_STEP
        return None

    def clear_of_marks(self, heading, berth=None):
        """
        What this course looks like against the marks she can see.

        Args:
            heading (float): The course in question, in degrees.
            berth (float, optional): Sea-room to keep, in metres.

        Returns:
            clearance (Clearance): The course that clears, and what forced it.

        Notes:
            Answers the question for anybody who asks - the sailing master, who acts
            on it, and a warning to a player, who is told and then does as they
            please. That difference is the whole of the policy: the helmsman does the
            sensible thing unasked, and the ordered thing when asked.

        """
        position = self.maritime_position
        if position is None:
            return Clearance(heading=heading)
        marks = [sighting.target for sighting in self.marks_in_sight()]
        if berth is None:
            return keep_clear(position, heading, marks)
        return keep_clear(position, heading, marks, berth=berth)
