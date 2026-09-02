"""
Evennia typeclasses for vessels and their interiors.

Two objects, and the relationship between them is the whole point:

    Vessel     the thing that is somewhere. Holds the position.
    ShipRoom   a compartment. Holds no position, and points at its vessel.

A third, `Flotsam`, is what is left when neither applies - anything on the water that
nobody is steering.

A ship's cabin is not inside the hull by Evennia's containment - rooms have no location
at all - so a cabin names its vessel as its position source, and everyone standing in it
resolves through to wherever the hull has sailed. Nobody aboard stores a coordinate, so
moving the hull moves the entire ship's company at once, for free, with no bookkeeping.

**Position lives in memory and is checkpointed, not written per change.** Every assignment
to a `.db` attribute is a pickle and a database commit, and a vessel under way updates its
position constantly. Writing through on every change would make sailing the single most
expensive thing a server does. So the live value sits in `.ndb`, a dirty flag tracks
whether it has moved since the last save, and the value is flushed on reload, on shutdown,
and whenever something important happens.

That is Law 10 in practice: persistence is explicit, with defined moments, rather than a
side effect of assignment.

"""

from evennia.objects.objects import DefaultObject

from .boarding import Boarded
from .burning import Burns
from .flooding import MakesWater
from .cables import Springs
from .charts import Charted
from .crew import Crewed
from .damage import HULL, Damaged
from .environment import Situated
from .floating import Floating
from .grounding import check_swept_grounding
from .handling import Handled
from .motion import HelmOrders, MotionLimits, MotionState, advance
from .navigation import Navigator, reckon
from .oars import Oared, braking_limits
from .ramming import Rams
from .observation import Lookout
from .ownership import Owned
from .ports import Berthing
from .position import WorldPosition, normalize_bearing

# ShipRoom lives in rooms.py now, and is imported here for `ship_rooms` below - but
# also re-exported deliberately. Evennia stores a typeclass as a dotted path on the
# row, so every compartment already created in every game that has run this contrib
# has this module's name written into its database. Dropping the name here would not
# fail at startup; it would produce rooms that fail to resolve their typeclass one at
# a time as they are loaded, which is a considerably worse way to find out.
from .rooms import Compartmented, ShipRoom  # noqa: F401
from .routes import Routed
from .sailing import Rigged, leeway_angle, steerage_floor
from .stowage import Laden
from .traffic import traffic
from .voyage import Conned
from .weapons import Armed
from .weather import sea_drag


def _tell_the_boards(vessel):
    """
    Send her instruments to any graphical client aboard, and never raise.

    Args:
        vessel (Vessel): The hull.

    Notes:
        Guarded for the same reason the room hooks are: a ship must not stop sailing
        because an interface could not be drawn. The optional half of this contrib
        may fail in any way it likes and the simulation carries on.

    """
    try:
        from .client.transport import broadcast_status

        broadcast_status(vessel)
    except Exception:  # noqa: BLE001 - a board is never worth a stopped ship
        pass


def _now():
    """
    Returns:
        now (float): The time on the simulation clock.

    Notes:
        Deferred behind a call rather than imported at module level, on the same
        terms as the other `config` uses here: `config` reads settings that a game
        overrides, and binding it at import time would freeze the choice before the
        game had made it.

    """
    from . import config

    return config.time_provider().now()


class Vessel(
    Navigator,
    Conned,
    Owned,
    Boarded,
    Burns,
    MakesWater,
    Springs,
    Crewed,
    Handled,
    Damaged,
    Oared,
    Rams,
    Armed,
    Laden,
    Charted,
    Routed,
    Berthing,
    Lookout,
    Rigged,
    Situated,
    Compartmented,
    DefaultObject,
):
    """
    A ship, as an Evennia object.

    This is the shell. The physics and rules live in the domain layer as plain
    Python; what this class adds is persistence, identity in the database, and the
    hooks that let Evennia tell it when the server is going away.

    """

    def _rammed(self, before, after, other, where, blow, world, now):
        """
        Stop her where she struck another ship, and share out what it cost.

        Args:
            before (MotionState): Where she began the step.
            after (MotionState): Where she was heading.
            other (Vessel): Who she hit.
            where (WorldPosition): Where her centre was at the moment of contact.
            blow (RamResult): What the collision came to.
            world (MaritimeMapProvider): The ground, for the water's surface.
            now (float): The game time.

        Returns:
            moved (bool): True, because she did move - up to the other ship.

        Notes:
            **Both hulls take it, and hers is not the smaller share by default.** Which of
            them comes off worse is decided in `ram` by the angle, the fitting and the two
            displacements, and this only delivers the answer.

            The damage goes on the hull track for both. A collision is a structural event:
            it does not cut rigging or dismount guns except by consequence, and consequence
            is `damage.structural`'s business rather than this one's.

        """
        # **Her guns speak first.**
        #
        # The one moment a broadside is certain of its target is the moment before that
        # target arrives, and a crew watching a bow come at them do not wait to be told. It
        # happens here rather than after the damage because a ship reduced by the collision
        # would lay her guns worse for it - and she laid them before it, not after.
        #
        # Free damage, except that it is not: every gun that speaks starts its reload, so
        # she meets whatever follows the collision with an empty battery.
        other.defensive_fire(self)

        floating = where.with_z(world.sea_surface_z_at(where, now))

        self.ndb.maritime_position = floating
        self.ndb.heading = after.heading
        self.ndb.maritime_dirty = True
        self.ndb.speed = 0.0

        if blow:
            self.take_damage(HULL, blow.recoil)
            self.take_crew_casualties(blow.recoil)
            other.take_damage(HULL, blow.weight)
            other.take_crew_casualties(blow.weight)

        self.narrator.collision(other, blow, hers=False)
        other.narrator.collision(self, blow, hers=True)
        return True

    def at_object_creation(self):
        """
        Set up a newly created vessel.

        Notes:
            Only what a hull has regardless of what it does. Each mixin sets its
            own defaults through the same chain, so a concern's state is
            initialised in the file that owns it rather than in one list here
            that everything has to remember to edit.

        """
        super().at_object_creation()
        self.db.template_key = None
        self.db.maritime_position = None
        self.db.heading = 0.0
        self.db.speed = 0.0
        self.db.orders = HelmOrders()
        self.db.motion_limits = MotionLimits()
        self.db.anchored = False
        self.db.aground = False

    # --- position -----------------------------------------------------------

    @property
    def maritime_position(self):
        """
        Where this vessel is.

        Returns:
            position (WorldPosition or None): The live position if the vessel has
                moved since the last checkpoint, otherwise the saved one.

        Notes:
            Reads the in-memory value first. A vessel under way updates this many
            times a minute, and only the checkpoint touches the database.

        """
        live = self.ndb.maritime_position
        return live if live is not None else self.db.maritime_position

    @maritime_position.setter
    def maritime_position(self, position):
        """
        Move the vessel, or take her off the water entirely.

        Args:
            position (WorldPosition or None): The new position, or None for a hull
                that is not afloat - on the stocks, or laid up in ordinary.

        Raises:
            TypeError: If given anything else. A tuple would survive here and fail much
                later inside a distance calculation, with nothing pointing back at the
                assignment.

        Notes:
            **None is written through to the database at once, and the live value with
            it.** Everything else here is deferred to the next checkpoint, because a ship
            under way moves many times a minute and each write is a pickle and a commit.
            None cannot be: the getter reads the live value and falls back to the saved
            one, and `checkpoint` deliberately skips a live position of None - so setting
            only the live value would leave her reading back from the database as still
            lying where she was.

            That asymmetry is the same one `floating` makes, for the same reason, and it
            costs nothing. A hull comes off the water once, not forty times a minute.

        """
        if position is None:
            self.ndb.maritime_position = None
            self.db.maritime_position = None
            self.ndb.maritime_dirty = False
            return
        if not isinstance(position, WorldPosition):
            raise TypeError(f"Expected a WorldPosition or None, got {type(position).__name__}.")
        self.ndb.maritime_position = position
        self.ndb.maritime_dirty = True

    @property
    def heading(self):
        """
        The vessel's heading, as a compass bearing.

        Returns:
            heading (float): Degrees, where north is 0 and east is 90.

        """
        live = self.ndb.heading
        return live if live is not None else (self.db.heading or 0.0)

    @heading.setter
    def heading(self, degrees):
        """
        Args:
            degrees (float): New heading. Wrapped into [0, 360).

        """
        self.ndb.heading = normalize_bearing(float(degrees))
        self.ndb.maritime_dirty = True

    @property
    def speed(self):
        """
        How fast she is actually going.

        Returns:
            speed (float): Metres per second. Not necessarily what was ordered.

        """
        live = self.ndb.speed
        return live if live is not None else (self.db.speed or 0.0)

    @speed.setter
    def speed(self, metres_per_second):
        """
        Args:
            metres_per_second (float): The new speed.

        Raises:
            ValueError: If negative. Ships do not travel astern; order a
                reciprocal heading instead.

        """
        value = float(metres_per_second)
        if value < 0.0:
            raise ValueError(f"Speed cannot be negative, got {value!r}.")
        self.ndb.speed = value
        self.ndb.maritime_dirty = True

    # --- orders -------------------------------------------------------------

    @property
    def orders(self):
        """
        What the helm has been told to do.

        Returns:
            orders (HelmOrders): The standing order. Targets, not instructions -
                the hull works towards them at whatever rate she can manage.

        """
        return self.db.orders or HelmOrders()

    @orders.setter
    def orders(self, orders):
        """
        Args:
            orders (HelmOrders): The new standing order.

        Raises:
            TypeError: If given anything else.

        Notes:
            Written straight to the database rather than held in memory. An order
            is given occasionally by a person, unlike position which changes many
            times a minute, so there is nothing to batch.

        """
        if not isinstance(orders, HelmOrders):
            raise TypeError(f"Expected HelmOrders, got {type(orders).__name__}.")
        self.db.orders = orders

    @property
    def motion_limits(self):
        """
        What this hull is physically capable of.

        Returns:
            limits (MotionLimits): Speed, acceleration and turn rate.

        """
        return self.db.motion_limits or MotionLimits()

    @motion_limits.setter
    def motion_limits(self, limits):
        """
        Args:
            limits (MotionLimits): The hull's capabilities.

        Raises:
            TypeError: If given anything else.

        """
        if not isinstance(limits, MotionLimits):
            raise TypeError(f"Expected MotionLimits, got {type(limits).__name__}.")
        self.db.motion_limits = limits

    @property
    def anchored(self):
        """
        Whether she lies to her anchor.

        Returns:
            anchored (bool): True if brought up.

        """
        return bool(self.db.anchored)

    @anchored.setter
    def anchored(self, value):
        """
        Args:
            value (bool): Whether she is brought up.

        """
        self.db.anchored = bool(value)

    @property
    def grounding(self):
        """
        What happened the last time she found the bottom.

        Returns:
            grounding (dict or None): `severity`, `bottom`, `clearance` and
                `speed` as they were at the moment of contact, or None if she has
                never touched.

        Notes:
            Kept because `aground` is a boolean and the interesting question is
            not whether she is on the ground but what she is on and how hard she
            hit it. Mud on a rising tide is an afternoon; rock at six knots is a
            different ship.

        """
        return self.db.grounding

    @property
    def aground(self):
        """
        Whether the hull is in the ground.

        Returns:
            aground (bool): True if she has found the bottom.

        """
        return bool(self.db.aground)

    @aground.setter
    def aground(self, value):
        """
        Args:
            value (bool): Whether she is aground.

        """
        self.db.aground = bool(value)
        if not value:
            self.db.grounding = None

    @property
    def narrator(self):
        """
        The layer that turns what happens to her into what people hear.

        Returns:
            narrator (VesselNarrator): The configured narrator, bound to this
                hull.

        Notes:
            Built on demand rather than held, so a game that changes
            `MARITIME_NARRATOR` and reloads gets the new one without every
            existing vessel carrying a stale reference.

        """
        from . import config

        return config.narrator_class()(self)

    # --- rig ----------------------------------------------------------------

    # --- simulation ---------------------------------------------------------

    #: What stops a hull answering her helm. Lines ashore, the ground under her,
    #: or her own anchor - canvas and rudder make no difference to any of them,
    #: and each is undone by a different act with its own name.
    HELD_FAST = ("docked", "aground", "anchored")

    def held_by(self):
        """
        What is holding her, if anything.

        Returns:
            reason (str or None): One of `HELD_FAST`, or None if she is free.

        """
        for reason in self.HELD_FAST:
            if getattr(self, reason):
                return reason
        return None

    def take_way_off(self):
        """
        Stop her, if she is still carrying way.

        Returns:
            stopped (bool): True if there was way to take off.

        """
        if not self.speed:
            return False
        self.ndb.speed = 0.0
        self.ndb.maritime_dirty = True
        return True

    def at_maritime_tick(self, elapsed):
        """
        Advance this vessel through a stretch of game time.

        Args:
            elapsed (float): Game seconds since her last update.

        Returns:
            moved (bool): True if she went anywhere.

        Notes:
            Called by the simulation service, never directly. A vessel with no
            position is not under way - she has not been launched - so there is
            nothing to advance.

        """
        position = self.maritime_position
        if position is None:
            return False

        # Kept up to date before anything else, and whether or not she moves. A
        # ship at anchor is still visible, and still has a lookout.
        traffic().note(self, position)
        self.narrator.sightings(self.contacts())

        # Lines made up are re-tested rather than granted once. A ship that puts
        # her helm hard over and fills her sails breaks free, which is what makes
        # being boarded survivable and worth trying to survive.
        parted = self.check_grapples()
        if parted is not None and not parted:
            self.narrator.grapples_parted(parted)

        # Anybody aboard with a board to draw. Before the movement below rather
        # than after, so the readings a player is looking at are the ones her helm
        # is working from this step rather than the last.
        _tell_the_boards(self)

        # Hands who have finished aloft. Above the check below on purpose: whether
        # she is moving has nothing to do with whether her people can work, and a
        # ship hard on the ground is a ship whose captain very much wants his canvas
        # off her. Found by running her aground with an order still outstanding, and
        # watching the hands stay aloft for good.
        set_now = self.finish_handling(_now())
        if set_now is not None:
            self.narrator.sail_set(set_now)

        # A battery that has been told to hold its fire, finding something in its
        # arc. Above the check below because guns do not care whether she is
        # moving - a ship anchored across a channel with her guns held is doing
        # something deliberate, and one aground still has a broadside.
        self.take_opportunity()

        # A rising tide lifts a ship that is merely held.
        #
        # `refloats_on_tide` has been written, exported and covered by tests since
        # grounding arrived, and nothing in a running game has ever called it - so a hull
        # that touched once stayed aground for ever. Found on a vessel sitting in twenty
        # metres of water, reporting herself hard on the ground, with a sailing master who
        # had the con and could not move her.
        #
        # **Above the check for whether she is held, because being aground is one of the
        # things that holds her.** Put below it first, and the tick returned at the guard
        # every time - so the code that lifts her ran only on ships that were not aground.
        # It also has to be above `work_her`, so a ship that floats free on this tick can
        # be worked on this tick rather than losing the top of the tide waiting.
        if self.aground:
            self.float_off()

        # **The sailing master gets her under way himself, anchor and all.**
        #
        # Ordering a passage is one decision - *take her to Longhope* - and a mate who
        # accepted it and then sat at anchor waiting to be told to weigh would not be a
        # mate. He is holding the con because somebody handed him the whole job, so he does
        # the whole job: he brings the anchor home, and everything below sets his sail and
        # his course.
        #
        # Only with the con and only with somewhere to go. A ship lying at anchor with no
        # passage ordered stays at anchor, which is what an anchor is for.
        if self.under_con and self.anchored and self.next_mark() is not None:
            self.weigh_for_passage()

        # **She burns whether she is held fast or not.** A ship alongside a quay with a
        # fire in her hold is the classic way to lose a ship and a pier together, and an
        # anchored one cannot even run from it. So this goes above the early return that
        # everything else about movement lives below.
        if self.alight:
            self.work_fire(elapsed)

        # And she fills wherever she is, for the same reason. The two run side by side
        # because they compete: both want hands, and both want her slowed - fire so the
        # pumps will draw, water because way through it forces more in. One crew, two
        # jobs, and a single decision about her speed that cannot satisfy both.
        self.work_water(elapsed)

        holding = self.held_by()
        if holding:
            self.take_way_off()
            # The one place a ship changes her heading without changing her position. A
            # spring is a line from the capstan to the anchor cable, so it works only on
            # the thing holding her: warping round a quay or a grounding is a different
            # job with different tackle and is not this.
            if holding == "anchored":
                self.work_spring(elapsed)
            return False

        self.work_her()

        # A watch passes over her people whether or not anything happens to them.
        # Before movement, so a crew who have just been driven to a standstill pull
        # the way exhausted men pull on this step rather than the next one.
        self.stand_watch(elapsed)

        before = MotionState(position=position, heading=self.heading, speed=self.speed)

        orders = self.orders
        wind = self.wind_here()
        limits = self.working_limits
        under_sail = self.sail_plan.area > 0.0 and wind.speed > 0.0
        if under_sail:
            # Asked once and used twice: to work out how fast she is going, and to
            # tell the deck why. Querying the register a second time to narrate what
            # has just been computed would double the cost of the commonest step
            # in the simulation.
            shadow = self.shadow()
            orders = HelmOrders(heading=orders.heading, speed=self.sailing_speed(shadow))
            self.narrator.in_the_lee(shadow)
        elif self.under_oars:
            # A pulling boat is the opposite of a sailing one: she is not asked how
            # fast to go, she goes as fast as the people in her are working. Holding
            # water is a braking order rather than a speed, so the limits move too.
            orders = HelmOrders(heading=orders.heading, speed=self.rowing_speed())
            limits = braking_limits(limits, self.stroke)

        # A crew with canvas aloft can back a headsail to shove her bow round, so
        # she is never wholly without steering. This goes in as a turn floor
        # rather than as a raised turn rate: the rate is scaled by speed, being a
        # rudder, and a backed sail is not - which matters precisely when she is
        # stopped dead and pointing the wrong way.
        # A heavy sea takes her way. Applied to the ordered speed rather
        # than to the result, so she is slowed by the water rather than
        # having her acceleration quietly rewritten.
        drag = sea_drag(self.sea_here())
        if drag:
            orders = HelmOrders(heading=orders.heading, speed=orders.speed * (1.0 - drag))

        floor = steerage_floor(wind, self.sail_plan) if under_sail else 0.0
        after = advance(before, orders, limits, elapsed, turn_floor=floor)

        if under_sail and after.speed > 0.0:
            slip = leeway_angle(after.heading, wind, self.sail_plan, after.speed)
            if slip:
                # She points one way and travels another. Correct the track
                # rather than the heading - her head really is where it was.
                travelled = before.position.horizontal_distance_to(after.position)
                after = MotionState(
                    position=before.position.moved(after.heading + slip, travelled),
                    heading=after.heading,
                    speed=after.speed,
                )
        from . import environment

        world = self.map_here()
        now = _now()

        # The water is moving too. She is carried in addition to whatever she is
        # making through it, which is why her speed is untouched here - a log
        # line measures the water going past the hull, not the ground going past
        # the ship.
        carried = environment.carried_from(after.position, now, elapsed)

        # And so is the air. A hull with no sail set is still something standing
        # up out of the water, so the wind pushes her - the same windage a
        # drifting cask has. Under canvas this is skipped: the wind is already
        # driving her, and leeway says how much of that goes sideways.
        if not under_sail:
            carried = self.blown_from(carried, elapsed)

        after = MotionState(
            position=carried,
            heading=after.heading,
            speed=after.speed,
        )

        # Only now is it fair to say nothing happened. Deciding that from her
        # propulsion alone left a ship stopped in a tideway sitting exactly where
        # she was, because the stream had not been applied yet - and the same
        # would have been true of a boat blown across a pond.
        if after == before:
            return False

        # Course steered and distance logged, and nothing else. The gap this
        # opens against the truth is the current and the leeway - which is not a
        # penalty applied to the crew but the two things they cannot see.
        dr = self.dead_reckoning
        if dr is not None:
            self.dead_reckoning = reckon(dr, after.heading, after.speed, elapsed)

        # A surface vessel floats. Her elevation is decided by the water, not by
        # anything she does, so it is set rather than integrated - which is why
        # she cannot be sailed down to the seabed by assigning a negative z.
        floating = after.position.with_z(world.sea_surface_z_at(after.position, now))

        # Her whole hull, along her whole track. Testing one point where she ends
        # up lets a fast ship step over a shoal narrower than one tick of her
        # movement, and lets a wide one sail her bow through a reef.
        contact = check_swept_grounding(
            before.position,
            floating,
            after.heading,
            self.draft,
            after.speed,
            self.length,
            self.beam,
            world,
            now,
        )

        # **And whatever else is floating in the way.**
        #
        # The seabed is not the only thing a hull can find. Tested over the same track and
        # the same tick, and whichever she reached first is what stopped her - a ship that
        # rams and then grounds did the ramming, and one that grounds short of another ship
        # never reached her at all.
        struck = self.first_hull_along(before.position, floating, after.heading, after.speed)
        if struck is not None:
            other, where, blow = struck
            if contact.position is None or before.position.horizontal_distance_to(
                where
            ) < before.position.horizontal_distance_to(contact.position):
                return self._rammed(before, after, other, where, blow, world, now)

        # Where she actually got to, which on a contact is where she struck
        # rather than where she was going.
        reached = (contact.position or floating).with_z(
            world.sea_surface_z_at(contact.position or floating, now)
        )
        after = MotionState(position=reached, heading=after.heading, speed=after.speed)

        self.ndb.maritime_position = reached
        self.ndb.heading = after.heading
        self.ndb.maritime_dirty = True

        if not contact:
            self.ndb.speed = 0.0
            self.aground = True
            # Kept rather than computed and discarded. Whether she is holed or
            # merely held is the difference between a lost ship and a wasted tide,
            # and the tick already knows - it was simply not writing it down.
            self.db.grounding = {
                "severity": contact.severity,
                "bottom": contact.bottom,
                "clearance": contact.clearance,
                "speed": contact.speed,
            }
            self.narrator.grounding(contact)
            return True

        self.ndb.speed = after.speed
        narrator = self.narrator
        narrator.underway(before, after)

        # **The lead goes in ahead of her, which is what a leadsman is for.**
        #
        # This warned on the water under her middle, which is the water she has already
        # crossed - so at six metres a second the call came about a second before she
        # struck, and on an authored rock it never came at all, because the clearance
        # under her centre stayed twenty metres right up until her bow was on it.
        #
        # A man in the chains swings the lead forward so it is on the bottom beneath the
        # bow as she comes up to it. Sounding the corridor she is about to cross is that,
        # and it turns a grounding from an ambush into a decision somebody made.
        narrator.soundings(self.water_before_her(after.speed) or contact)
        return True

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
            _now(),
        )

    # --- persistence --------------------------------------------------------

    def checkpoint(self):
        """
        Write live state to the database, if it has changed.

        Returns:
            saved (bool): True if anything was written.

        Notes:
            Skips the write entirely when nothing has moved. Re-saving an
            unchanged value still costs a pickle and a commit, and a fleet sitting
            at anchor would otherwise pay that on every checkpoint.

        """
        if not self.ndb.maritime_dirty:
            return False
        if self.ndb.maritime_position is not None:
            self.db.maritime_position = self.ndb.maritime_position
        if self.ndb.heading is not None:
            self.db.heading = self.ndb.heading
        if self.ndb.speed is not None:
            self.db.speed = self.ndb.speed
        self.ndb.maritime_dirty = False
        return True

    def float_off(self, now=None):
        """
        Lift her if the tide has made enough water since she grounded.

        Args:
            now (float, optional): Game time. Read from the clock if omitted.

        Returns:
            floated (bool): Whether she came off.

        Notes:
            **Only a grounding a tide can undo.** A hull holed on rock does not float off
            when the water rises; she fills. That is what `held_not_holed` decides, and it
            is asked of what was written down when she struck rather than of what the
            ground looks like now - the bottom she is on has not changed, and re-deriving
            it would be answering a different question.

            **Asked with the same test that grounded her**, hull outline and authored
            hazards and all - not with a bare sounding under her middle. Those two can
            disagree, and where they do the disagreement is vicious: a hull sitting on the
            edge of a charted rock has twenty metres of terrain beneath her centre, so a
            clearance check floats her, the very next tick grounds her again on the rock,
            and she oscillates for ever announcing both. Found exactly that way.

            The mechanism is still the tide: tide and terrain share one model, so the water
            rising turns a negative clearance positive without anything else moving. She
            simply has to be clear of everything, not clear of the seabed.

            Total. A vessel with no world, no position or no record of how she grounded
            stays where she is - none of those is a reason to declare her afloat, and a
            ship wrongly floated is a ship that sails away over a sandbank.

        """
        from .grounding import check_swept_grounding, held_not_holed

        record = self.db.grounding or {}
        if not held_not_holed(record.get("severity"), record.get("bottom")):
            return False

        world = self.map_here()
        here = self.maritime_position
        if world is None or here is None:
            return False

        standing = check_swept_grounding(
            here,
            here,
            self.heading,
            self.draft,
            0.0,
            self.length,
            self.beam,
            world,
            now if now is not None else _now(),
        )
        if not standing:
            return False

        self.aground = False
        self.db.grounding = None
        self.narrator.floated_off()
        return True

    def at_server_reload(self):
        """Flush live state before the server restarts."""
        super().at_server_reload()
        self.checkpoint()

    def at_object_delete(self):
        """
        Take her off the register on the way out.

        Returns:
            proceed (bool): True, always - nothing here can refuse a deletion.

        Notes:
            The register is memory, not a foreign key, so nothing removes her
            from it when her row goes. A hull that sinks and is deleted would
            otherwise stay visible on the horizon indefinitely, which is a
            haunting rather than a feature.

        """
        traffic().forget(self)
        return super().at_object_delete()

    def at_server_shutdown(self):
        """Flush live state before the server stops."""
        super().at_server_shutdown()
        self.checkpoint()

    # --- interior -----------------------------------------------------------

    def __repr__(self):
        return f"<Vessel {self.key} at {self.maritime_position}>"


class Flotsam(Floating, Situated, DefaultObject):
    """
    Anything on the water that nobody is steering.

    Notes:
        A cask, a spar, a hatch cover, a body. The whole of it is the two mixins:
        `Floating` gives it a position the sea moves, `Situated` lets it read the
        water it is in. There is no behaviour of its own to add, which is the
        test that the mixins were drawn in the right places.

        Provided so a game does not have to declare a class to drop a barrel over
        the side. A game that wants floating *characters* mixes `Floating` into
        its own character class instead - inheriting from this one would make
        every swimmer an object rather than a person.

    """
