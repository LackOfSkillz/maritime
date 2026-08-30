"""
Working a boat under oars.

The orders a coxswain gives, as the verbs they are. `give way` is not a synonym for
`speed 3` - a pulling boat has no throttle, and asking her for three knots when the crew
can make two is a question she has no way to answer. What she has is a stroke, and how fast
that drives her depends on how many hands are on the looms.

`easy` and `hold water` both order no speed, and they are different orders. Easy oars means
stop pulling and let her run on; hold water means put the blades in and stop her. The
second is the one thing a pulling boat can do that a ship under sail cannot.

"""

from ..messaging import STROKE_ORDER
from ..oars import (
    EASY_OARS,
    GIVE_WAY,
    HOLD_WATER,
    PADDLE,
    PADDLED,
    STRETCH_OUT,
    STROKES,
)
from .base import MaritimeCommand


class StrokeCommand(MaritimeCommand):
    """
    Base for the orders that change how hard she is being pulled.

    Notes:
        One class and four verbs rather than one verb with an argument, because
        these are what a coxswain says and `stroke give_way` is not. The argument
        form exists as well, on `oars`, for anyone driving this from a script.

    """

    #: Which stroke this order calls for. Set by each subclass.
    stroke = None

    def at_helm(self, vessel):
        """Pass the order, if there is anybody to pass it to."""
        if vessel.oar_plan is None:
            self.caller.msg("She has no oars aboard.")
            return
        if vessel.held_by() == "docked":
            self.caller.msg("She is made fast alongside. Let go before you pull anywhere.")
            return
        vessel.stroke = self.stroke
        self.order(vessel, STROKE_ORDER, stroke=self.stroke, plan=vessel.oar_plan)


class CmdGiveWay(StrokeCommand):
    """
    Set the working stroke.

    Usage:
      give way

    The stroke a boat's crew can hold for an hour. Everything else is either
    slower or not sustainable.
    """

    key = "give way"
    aliases = ("give way together", "row")
    stroke = GIVE_WAY


class CmdPaddleStroke(StrokeCommand):
    """
    Pull gently.

    Usage:
      paddle

    Steerage way and no more, for working alongside or holding station.
    """

    key = "paddle"
    aliases = ("paddle ahead",)
    stroke = PADDLE


class CmdStretchOut(StrokeCommand):
    """
    Pull for everything she has.

    Usage:
      stretch out

    Racing pace. Nothing here decides how long a crew can hold it, which is a
    question about the game rather than about the boat.
    """

    key = "stretch out"
    aliases = ("stretch",)
    stroke = STRETCH_OUT


class CmdEasyOars(StrokeCommand):
    """
    Stop pulling and let her run on.

    Usage:
      easy

    Not the same as holding water. She keeps her way and loses it the way any
    hull does.
    """

    key = "easy"
    aliases = ("easy oars", "easy all")
    stroke = EASY_OARS


class CmdHoldWater(StrokeCommand):
    """
    Put the blades in and stop her.

    Usage:
      hold water

    The one thing a pulling boat can do that a ship under sail cannot: take her
    own way off in a couple of lengths.
    """

    key = "hold water"
    aliases = ("hold",)
    stroke = HOLD_WATER


class CmdOars(MaritimeCommand):
    """
    Report what she is being pulled by, or change the stroke.

    Usage:
      oars
      oars <stroke>

    Says what she is fitted with, how many of those positions are filled, what
    that is making through the water, and what she is making over the ground -
    which in a river is a different number and the interesting one.
    """

    key = "oars"
    aliases = ("paddles",)

    def at_helm(self, vessel):
        """Report her, or take the order."""
        if vessel.oar_plan is None:
            self.caller.msg("She has no oars aboard.")
            return

        wanted = (self.args or "").strip().lower().replace(" ", "_")
        if wanted:
            if wanted not in STROKES:
                self.caller.msg(f"No such order. Try one of: {', '.join(STROKES)}.")
                return
            vessel.stroke = wanted
            self.order(vessel, STROKE_ORDER, stroke=wanted, plan=vessel.oar_plan)
            return

        self.caller.msg(chr(10).join(vessel.narrator.oar_report(vessel)))


def crew_word(plan):
    """
    Args:
        plan (OarPlan): What she is fitted with.

    Returns:
        word (str): What the people pulling her are called.

    """
    return "paddlers" if plan.style == PADDLED else "rowers"
