"""
Fire aboard: seeing it, and fighting it.

"""

from ..burning import MOST_SEATS, PUMPING_SPEED, pumps_draw
from .base import MaritimeCommand, ms_to_knots


class CmdFires(MaritimeCommand):
    """
    What is burning, and how the fight is going.

    Usage:
      fires

    Tells you how many separate seats of fire she has, how many hands are on
    them, whether the pumps are drawing, and how close the fire is to taking
    hold somewhere new.
    """

    key = "fires"
    aliases = ("fire report", "blaze")

    def at_helm(self, vessel):
        """Report the fire."""
        if not vessel.alight:
            self.caller.msg("Nothing is alight.")
            return

        seats = vessel.seats_of_fire
        party = vessel.fire_party
        effect = vessel.fire_fighting_effect()
        drawing = pumps_draw(vessel.speed)

        where = "one seat of fire" if seats == 1 else f"{seats} separate seats of fire"
        lines = [f"She has {where} burning."]

        if party:
            lines.append(f"{party:.0f} hands are on it.")
        else:
            lines.append("Nobody is fighting it.")

        if not drawing:
            lines.append(
                f"The pumps will not draw - she has {ms_to_knots(vessel.speed):.1f} knots on "
                f"and the hoses are dragging. Take the way off her to get water on it."
            )
        elif vessel.sail_plan.area > 0.0:
            lines.append("Her canvas is still spread, and there is a deal of it to catch.")

        if not effect:
            lines.append("It is gaining.")
        elif effect < 0.4:
            lines.append("They are barely holding it.")
        elif effect < 0.8:
            lines.append("They are getting the better of it.")
        else:
            lines.append("They have it well in hand.")

        if seats >= MOST_SEATS:
            lines.append("She is alight from end to end.")

        self.caller.msg(" ".join(lines))


class CmdFightFire(MaritimeCommand):
    """
    Put a party on the fire.

    Usage:
      fight fire <hands>
      fight fire off

    Commits hands to fighting the fire. They are hands that are not at the guns,
    the oars, or the sheets, and doubling the party does not halve the fire -
    past a point you are simply disarming yourself.

    Two things matter more than numbers. The pumps take their water over the
    side, so they will not draw while she has way on: a burning ship has to
    choose between running and putting it out. And canvas aloft is more fire to
    catch, so handing your sails helps twice - though she cannot run under bare
    poles either.
    """

    key = "fight fire"
    aliases = ("fire party", "douse fire", "beat it out")

    def at_helm(self, vessel):
        """Send the party, or call them off."""
        if not vessel.alight:
            self.caller.msg("Nothing is alight.")
            return

        wanted = self.args.strip().lower()
        if wanted in ("off", "none", "belay"):
            vessel.fight_fire(0)
            self.caller.msg("The fire party is called off.")
            return

        if not wanted:
            self.caller.msg(
                f"How many hands? She has {vessel.seats_of_fire} alight, and "
                f"{vessel.fire_party:.0f} on it now."
            )
            return

        try:
            hands = float(wanted)
        except ValueError:
            self.caller.msg("Give a number of hands, as 'fight fire 30'.")
            return
        if hands < 0:
            self.caller.msg("A negative fire party is not a thing.")
            return

        result = vessel.fight_fire(hands)
        told = [f"{hands:.0f} hands are on the fire."]
        if not result.pumping:
            told.append(
                f"The pumps will not draw above {ms_to_knots(PUMPING_SPEED):.1f} knots - "
                "they are on buckets until she is stopped."
            )
        if result.effect >= 0.8:
            told.append("That should be enough.")
        elif result.effect < 0.4:
            told.append("It will not be enough.")
        self.caller.msg(" ".join(told))
