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

from .currents import course_to_steer
from .buoyage import Clearance, keep_clear
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
            self.narrator.passage_made()
            return False

        wind = self.wind_here()
        plan = sail_for_wind(wind)
        if plan.key != self.sail_plan.key:
            self.sail_plan = plan
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

        self.orders = HelmOrders(heading=heading, speed=wanted)
        return True

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
