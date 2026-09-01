"""
The gun deck: serving her, laying her, and firing.

"""

from ..ammunition import DEFAULT_SHOT, SHOT_TYPES, shot_named
from ..config import rng_context, time_provider
from ..damage import serving_time
from ..observation import DEFAULT_HEIGHT_OF_EYE, IDENTIFIED
from ..rng import COMBAT
from ..sailing import hands_aloft
from ..tactical import AFT, FORWARD, PORT_BROADSIDE, STARBOARD_BROADSIDE
from ..vessel import WEATHER_DECKS
from ..weapons import serve
from .base import MaritimeCommand


class CmdGuns(MaritimeCommand):
    """
    Report the battery: what is mounted, and what state each gun is in.

    Usage:
      guns

    """

    key = "guns"
    aliases = ("battery", "gun deck")

    def at_helm(self, vessel):
        """
        Args:
            vessel (Vessel): The hull the caller is aboard.

        """
        if not vessel.mounts:
            self.caller.msg("She carries no guns at all.")
            return

        now = time_provider().now()
        serviceable = set(vessel.serviceable_mounts)
        self.caller.msg("The battery:")
        for mount in vessel.mounts:
            # A dismounted gun is still listed. She had it, and the gap where it
            # used to be is exactly what her captain needs to see.
            if mount not in serviceable:
                state = "|rdismounted|n"
            elif not mount.loaded:
                state = "empty"
            elif now < mount.ready_at:
                state = f"being served, {mount.ready_at - now:.0f}s"
            else:
                state = "loaded and ready"
            self.caller.msg(
                f"  {mount.key:<18}{mount.weapon.name:<16}{mount.arc:<20}"
                f"{mount.shot.name:<12}{state}"
            )


class CmdLoad(MaritimeCommand):
    """
    Serve the guns.

    Usage:
      load

    Loads every empty gun aboard and starts each one's clock. A gun being served
    cannot fire until her crew have finished, which is what makes the first
    broadside worth more than the second.

    """

    key = "load"
    aliases = ("serve", "load guns")

    def at_helm(self, vessel):
        """
        Args:
            vessel (Vessel): The hull the caller is aboard.

        """
        now = time_provider().now()

        # What to load. Naming nothing keeps whatever she had, so a battery goes on
        # firing the same thing until her captain changes his mind - which is how a
        # gun crew actually behaves and saves saying it every time.
        wanted = (self.args or "").strip()
        charge = None
        if wanted:
            charge = shot_named(wanted)
            if charge is None:
                carried = ", ".join(kind.key for kind in SHOT_TYPES)
                self.caller.msg(f"Nobody carries {wanted!r}. She has {carried}.")
                return

        # How long this crew take over it: their own fear, and how much of the
        # battery they are working round. A frightened crew still load - they load
        # slowly, which is a cost rather than a kill switch.
        served = 0
        for mount in vessel.serviceable_mounts:
            if not mount.loaded:
                # Hands on sheets and halyards are hands that are not at the guns,
                # so a ship that has shortened down serves her battery faster. That
                # is the other half of what fighting sail buys, and the reason a ship
                # cleared for action carries less canvas than one on passage.
                seconds = serving_time(
                    mount.weapon.reload_time, vessel.damage, vessel.hesitation
                ) * (1.0 + hands_aloft(vessel.sail_plan))
                vessel.replace_mount(serve(mount, now, seconds, charge))
                served += 1

        if not served:
            if vessel.mounts and not vessel.serviceable_mounts:
                self.caller.msg("There is not a gun aboard fit to be served.")
                return
            self.caller.msg("Every gun aboard is already served.")
            return
        named = charge or DEFAULT_SHOT
        self.caller.msg(f'You call out, "Load with {named.name}!"')
        self.announce(f'{self.caller.key} calls out, "Load with {named.name}!"')
        self.aboard(vessel, f"The gun crews go to work. {served} run out.")


class CmdFire(MaritimeCommand):
    """
    Fire everything that bears.

    Usage:
      fire <name>

    Every loaded gun whose arc covers her speaks. Each is laid where she will be
    when the shot arrives rather than where she is now, which is why altering
    course under fire is worth doing.

    The target must be near enough to identify. You cannot lay a solution on a
    shape you have not made out.

    """

    key = "fire"
    aliases = ("open fire", "broadside")

    def at_helm(self, vessel):
        """
        Args:
            vessel (Vessel): The hull the caller is aboard.

        """
        wanted = self.args.strip().lower()
        if not wanted:
            self.caller.msg("Fire on what?")
            return

        room = getattr(self.caller, "location", None)
        if getattr(room, "exposure", None) not in WEATHER_DECKS:
            self.caller.msg("You cannot lay a gun from in here.")
            return

        height = getattr(room, "height_of_eye", DEFAULT_HEIGHT_OF_EYE)
        sighting = None
        for seen in vessel.contacts(height):
            if seen.level == IDENTIFIED and wanted in seen.target.key.lower():
                sighting = seen
                break
        if sighting is None:
            self.caller.msg("Nothing of that name is near enough to lay a gun on.")
            return

        if not vessel.guns_bearing(sighting.relative):
            self.caller.msg("Not a gun aboard bears on her. Bring her round.")
            return

        now = time_provider().now()
        roll = rng_context().stream(COMBAT).random

        self.caller.msg('You call out, "Fire!"')
        self.announce(f'{self.caller.key} calls out, "Fire!"')

        vessel.narrator.broadside(vessel.fire_broadside(sighting, now, roll))


class CmdHoldFire(MaritimeCommand):
    """
    Run the guns out and hold them until something bears.

    Usage:
      hold fire <name>
      hold fire to port
      hold fire to starboard
      hold fire forward
      hold fire
      secure the guns

    Named ship or open arc, and the difference is the whole decision.

    Holding on a *named* ship is safe: she has to be identified before the guns
    will speak, so nobody else is fired on by mistake. It also does nothing at all
    in fog, in the dark, or at the edge of vision - which is exactly where you most
    want your guns held ready.

    Holding on an *arc* fires at whatever crosses it, whether or not anybody knows
    what she is. That works in any weather. It will also take the first ship into
    that arc, and the sea does not check whose she is before she gets there.

    A snatched shot is not a laid one, so opportunity fire is less accurate than a
    broadside you called yourself - and worse again in a frightened crew.

    With no argument, reports what the battery is waiting for.

    """

    key = "hold fire"
    # Not "hold" - that is the oar order to hold water, and a captain who meant to
    # stop his boat would have run his guns out instead. Not "stand down" either;
    # `belay` already answers to it, for taking the con back. The first was found
    # live and the second by the test that was written because of the first.
    aliases = ("hold your fire", "secure the guns")

    #: What a captain may say, and the arc he means by it.
    ARCS = {
        "to port": PORT_BROADSIDE,
        "port": PORT_BROADSIDE,
        "to starboard": STARBOARD_BROADSIDE,
        "starboard": STARBOARD_BROADSIDE,
        "forward": FORWARD,
        "ahead": FORWARD,
        "aft": AFT,
        "astern": AFT,
    }

    def at_helm(self, vessel):
        """
        Args:
            vessel (Vessel): The hull the caller is aboard.

        """
        wanted = self.args.strip().lower()

        securing = self.cmdstring.strip().lower() == "secure the guns"
        if securing or wanted in ("down", "off", "none"):
            if vessel.stand_down():
                self.caller.msg('You call out, "Secure the guns!"')
                self.announce(f'{self.caller.key} calls out, "Secure the guns!"')
                self.aboard(vessel, "The crews house their pieces and stand away.")
                return
            self.caller.msg("The battery is not holding for anything.")
            return

        if not wanted:
            self.report(vessel)
            return

        if not vessel.mounts:
            self.caller.msg("She carries no guns at all.")
            return

        arc = self.ARCS.get(wanted)
        if arc is not None:
            vessel.hold_fire(arc=arc)
            self.caller.msg(f'You call out, "Hold your fire, watch {wanted}!"')
            self.announce(f'{self.caller.key} calls out, "Hold your fire, watch {wanted}!"')
            self.aboard(
                vessel,
                "The gun crews stand to their pieces, watching the empty water. "
                "They will fire on whatever comes into it.",
            )
            return

        vessel.hold_fire(target_key=wanted)
        self.caller.msg(f'You call out, "Hold your fire until the {wanted} bears!"')
        self.announce(f'{self.caller.key} calls out, "Hold your fire until the {wanted} bears!"')
        self.aboard(vessel, "The gun crews stand to their pieces.")

    def report(self, vessel):
        """
        Args:
            vessel (Vessel): The hull.

        """
        held = vessel.holding
        if held is None:
            self.caller.msg("The battery is not holding for anything.")
            return
        if held.target_key is not None:
            self.caller.msg(f"The guns are held, waiting on the {held.target_key} to bear.")
            return
        self.caller.msg(
            f"The guns are held, watching the {held.arc} - "
            f"and they will fire on whatever crosses it."
        )
