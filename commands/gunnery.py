"""
The gun deck: serving her, laying her, and firing.

"""

from ..config import rng_context, time_provider
from ..formatting import format_range
from ..observation import DEFAULT_HEIGHT_OF_EYE, IDENTIFIED
from ..rng import COMBAT
from ..vessel import WEATHER_DECKS
from ..weapons import discharge, fire, serve
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
        self.caller.msg("The battery:")
        for mount in vessel.mounts:
            if not mount.loaded:
                state = "empty"
            elif now < mount.ready_at:
                state = f"being served, {mount.ready_at - now:.0f}s"
            else:
                state = "loaded and ready"
            self.caller.msg(f"  {mount.key:<18}{mount.weapon.name:<16}{mount.arc:<20}{state}")


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
        served = 0
        for mount in vessel.mounts:
            if not mount.loaded:
                vessel.replace_mount(serve(mount, now))
                served += 1

        if not served:
            self.caller.msg("Every gun aboard is already served.")
            return
        self.caller.msg('You call out, "Load!"')
        self.announce(f'{self.caller.key} calls out, "Load!"')
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

        bearing_guns = vessel.guns_bearing(sighting.relative)
        if not bearing_guns:
            self.caller.msg("Not a gun aboard bears on her. Bring her round.")
            return

        her = sighting.target
        _course, her_speed = her.made_good() or (her.heading, her.speed)
        now = time_provider().now()
        roll = rng_context().stream(COMBAT).random

        self.caller.msg('You call out, "Fire!"')
        self.announce(f'{self.caller.key} calls out, "Fire!"')

        hits = 0
        fired = 0
        for mount in bearing_guns:
            shot = fire(
                mount,
                vessel.maritime_position,
                vessel.heading,
                her,
                her.maritime_position,
                her.heading,
                her_speed,
                vessel.sea_here(),
                now,
                roll,
            )
            if shot.code in ("not_loaded", "still_reloading"):
                continue
            fired += 1
            vessel.replace_mount(discharge(mount))
            if shot:
                hits += 1

        if not fired:
            self.aboard(vessel, "Not a gun is ready. The crews are still at it.")
            return

        self.aboard(
            vessel,
            f"{fired} gun{'s' if fired != 1 else ''} go off together, and the smoke "
            f"rolls away to leeward.",
        )
        if hits:
            self.aboard(
                vessel,
                f"{hits} of them tell on {her.key}, {format_range(sighting.distance)} off.",
            )
        else:
            self.aboard(vessel, f"The whole broadside goes wide of {her.key}.")
