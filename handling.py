"""
How long her people take to do what they are told.

Everything else in this package answers what a ship *can* do. This answers how long she
takes to start doing it, which is a different question and the one that makes crew quality
visible on an ordinary passage rather than only in action.

An order at sea is not a state change. Somebody has to go aloft, lay out along a yard, and
cast off or make up a gasket, and there are only so many of them. Until that work is done
she carries what she carried - so a captain who leaves it late is still under a full press
when the squall arrives, and that is a decision he made rather than a die he rolled.

**The plan changes when the work is finished, not gradually.** Canvas does come in by
degrees in life, but a sail plan here is a discrete thing, and pretending otherwise would
mean inventing intermediate plans nobody ordered. The honest version of the same drama is
that she carries the old plan - with the old risk - for the whole time it takes, which is
exactly what makes shortening down early worth doing.

`hesitation` is read here for the second time. Morale computed it, gunnery spends it on the
guns, and this spends it on the rigging: frightened people are slower at everything, and a
crew who will not go aloft smartly are a crew whose captain has a problem long before
anybody fires at him.

"""

from dataclasses import dataclass

from .sailing import sail_plan

#: Hand-seconds of work to shift her entire suit of canvas, per metre of length
#: overall. Calibrated against the drill of the age rather than guessed: a
#: well-manned frigate shortening down from a full press to fighting sail is a few
#: minutes' work, and handing everything she has is the better part of a watch's
#: worth of it.
WORK_PER_METRE = 1200.0

#: How much slower a wholly shaken crew are at it, on the same terms as
#: `HESITATION_ON_SERVING`. Higher than the gun deck's figure: a gun crew work
#: behind bulwarks and a topman does not, and the last place fear tells is a
#: hundred feet up in a blow.
HESITATION_ON_HANDLING = 0.8

#: What it costs to change your mind with the hands already aloft. Work half done
#: is work partly wasted - gaskets cast off that must be made up again, people sent
#: to the wrong yard - and a captain who orders three things in a minute gets a
#: slower answer than one who orders the right thing once.
CHANGED_MIND = 0.35


@dataclass(frozen=True)
class Handling:
    """
    Work in progress aloft.

    Attributes:
        plan_key (str): The plan they are setting.
        was_key (str): What she carried when the order was given.
        finish_at (float): When it will be done, on the simulation clock.

    Notes:
        Keys rather than plans, matching how `sail_plan_key` is already stored. A
        pickled dataclass on a database attribute outlives the code that wrote it,
        and a plan whose fields change underneath a saved copy would come back as a
        ship carrying canvas nobody defines any more.

    """

    plan_key: str
    was_key: str
    finish_at: float

    @property
    def plan(self):
        """
        Returns:
            plan (SailPlan or None): What they are setting.

        """
        return sail_plan(self.plan_key)

    @property
    def was(self):
        """
        Returns:
            plan (SailPlan or None): What she carried when it was ordered.

        """
        return sail_plan(self.was_key)


def handling_work(from_plan, to_plan, length):
    """
    How much work a change of canvas is.

    Args:
        from_plan (SailPlan): What she carries.
        to_plan (SailPlan): What is wanted.
        length (float): Her length overall, in metres.

    Returns:
        work (float): Hand-seconds of work.

    Notes:
        Scaled by how much canvas is actually being moved, so shaking out a reef is
        less work than handing every sail she has. It does not matter which way: a
        sail is as much trouble to set as it is to hand, and making the two differ
        would be a claim about rigging rather than about people.

    """
    moved = abs(to_plan.area - from_plan.area)
    return max(0.0, length) * WORK_PER_METRE * moved


def handling_time(work, hands, hesitation=0.0, penalty=HESITATION_ON_HANDLING):
    """
    How long that work will take these people.

    Args:
        work (float): Hand-seconds of work, from `handling_work`.
        hands (float): Effective hands available to do it.
        hesitation (float, optional): How much of what they could do is not being
            done, from `morale`.
        penalty (float, optional): How much slower a wholly shaken crew are.

    Returns:
        seconds (float): How long they will be at it.

    Notes:
        Hands come in already scaled by skill and by what each rating is worth at
        working the ship, so a crack crew of seamen and a party of marines of the
        same number are not the same number of hands. That is the whole reason
        `ShipsCompany.hands` exists, and it is why nothing here asks about quality
        directly.

        Nobody to do it means nobody will: an order given to an empty ship is work
        that never finishes rather than work that finishes instantly.

    """
    if work <= 0.0:
        return 0.0
    if hands <= 0.0:
        return float("inf")
    slower = 1.0 + penalty * max(0.0, min(1.0, hesitation))
    return (work / hands) * slower


class Handled:
    """
    A vessel whose orders take time.

    Notes:
        Mixed into `Vessel`. Nothing here knows what a sail plan is worth or how it
        drives her - only how long her people take to make the change, and that
        until they have, she carries what she carried.

    """

    @property
    def handling(self):
        """
        Returns:
            handling (Handling or None): What the hands are working at, if anything.

        """
        return self.db.handling

    @handling.setter
    def handling(self, work):
        """
        Args:
            work (Handling or None): What they are at, or None when the deck is
                clear.

        """
        self.db.handling = work

    @property
    def working_aloft(self):
        """
        Returns:
            working (bool): Whether there are people aloft on an order.

        """
        return self.handling is not None

    def hands_to_work_her(self):
        """
        How many effective hands are available to handle sail.

        Returns:
            hands (float or None): Effective hands, or None if she has no ship's
                company at all.

        Notes:
            None rather than zero, and the difference matters. A vessel with no
            company is not undermanned - she is a boat somebody climbed into, worked
            by the host game's people, who are not ours to model. A kayak whose
            paddler took four minutes to shorten sail would be this contrib
            inventing a crew for a hull that has none.

        """
        company = self.company
        if company is None:
            return None
        return company.hands

    def time_to_set(self, plan):
        """
        How long she would be at it.

        Args:
            plan (SailPlan): What is wanted.

        Returns:
            seconds (float): How long the change would take. Zero if she carries it
                already, or if there is no company to wait for.

        """
        hands = self.hands_to_work_her()
        if hands is None:
            return 0.0

        work = handling_work(self.sail_plan, plan, self.length)

        # Changing your mind is not free. The work already done towards the last
        # order is partly wasted, and the people doing it have to be told twice.
        if self.working_aloft:
            work *= 1.0 + CHANGED_MIND

        return handling_time(work, hands, self.hesitation)

    def order_sail(self, plan, now):
        """
        Send the hands to make a change of canvas.

        Args:
            plan (SailPlan): What is wanted.
            now (float): The time the order was given.

        Returns:
            seconds (float): How long they will be at it. Zero if it is already
                done, in which case she is carrying the ordered plan on return.

        Notes:
            Returns the time rather than announcing it. `messaging` speaks; this
            says what happened and how long it will take.

        """
        if plan.key == self.sail_plan.key:
            # Already carrying it. Not an error and not work - a captain may well
            # order what she already has, and doing so is how he belays a change
            # that is still in hand.
            #
            # The path below reaches the same state, so this guard is here for Law
            # 10 rather than for behaviour: it avoids writing `sail_plan_key` back
            # as the value it already holds, and every such assignment is a pickle
            # and a commit. Removing it fails no test, and that is not a gap in the
            # tests - there is nothing observable to write one against.
            self.handling = None
            return 0.0

        seconds = self.time_to_set(plan)
        if seconds <= 0.0:
            self.handling = None
            self.sail_plan = plan
            return 0.0

        self.handling = Handling(
            plan_key=plan.key, was_key=self.sail_plan.key, finish_at=now + seconds
        )
        return seconds

    def finish_handling(self, now):
        """
        Apply a change of canvas whose time has come.

        Args:
            now (float): The time on the simulation clock.

        Returns:
            plan (SailPlan or None): What has just been set, or None if there was
                nothing to finish or they are still at it.

        Notes:
            Called every tick, and does nothing on almost all of them. Returning the
            plan rather than announcing it keeps the decision of what to say where
            the words are.

        """
        work = self.handling
        if work is None or now < work.finish_at:
            return None

        plan = work.plan
        self.handling = None
        if plan is None:
            # The plan was removed from the game while the hands were aloft. She
            # keeps what she has rather than losing her canvas to a config change.
            return None

        self.sail_plan = plan
        return plan
