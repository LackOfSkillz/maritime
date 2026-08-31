"""
What the interface offers to do, and what happens when somebody does it.

**A button is a way of typing a command, and nothing else.** Every control here names an
ordinary maritime command that already worked without any of this, and pressing one runs
that command through the same command handler, against the same locks, with the same
authority check a captain shouting it would pass. There is no path from a browser into the
simulation that does not go through the helm.

That is not caution for its own sake. A graphical client that could do things a text player
cannot is a client that has quietly forked the game: the text half stops being playable, and
every rule has to be written twice and will eventually disagree with itself.

**What is offered is advisory; what is done is checked.** The interface may show a berthing
button because she was in position two hundred milliseconds ago. Whether she still is, is
the server's business at the moment the order arrives, and it asks then. Nothing here
pre-authorises anything.

**A determined player has a JavaScript console.** They will call these by hand with whatever
arguments they like, and that has to be uninteresting: the worst it can achieve is typing a
command they could have typed anyway.

"""

#: What the interface may offer, and the command each one is.
#:
#: Named commands rather than free text, so a browser cannot ask for anything that is not
#: on this list. The argument is filled from a small, checked set of shapes; there is no
#: point at which a client's string becomes a command line.
CONTROLS = {
    "port": {"command": "helm", "argument": "{relative}", "group": "helm", "hand": -1.0},
    "starboard": {"command": "helm", "argument": "{relative}", "group": "helm", "hand": 1.0},
    "steady": {"command": "helm", "argument": "{steady}", "group": "helm"},
    "heading": {"command": "helm", "argument": "{bearing}", "group": "helm"},
    "sail": {"command": "sail", "argument": "{plan}", "group": "sails"},
    "anchor": {"command": "drop anchor", "argument": "", "group": "anchor"},
    "weigh": {"command": "weigh anchor", "argument": "", "group": "anchor"},
    "sound": {"command": "sound", "argument": "", "group": "navigation"},
    "scan": {"command": "scan", "argument": "", "group": "lookout"},
    "fix": {"command": "fix", "argument": "", "group": "navigation"},
}

#: How far a helm order may put the wheel over in one press. A browser asking for four
#: hundred degrees is asking for nothing a captain could say.
MAX_ALTERATION = 90.0


def offered(vessel, context):
    """
    Which controls this person may be shown, on this hull.

    Args:
        vessel (Vessel or None): The hull.
        context (str): Their situation, from `context.CONTEXTS`.

    Returns:
        controls (list): The keys of everything worth offering.

    Notes:
        Composed from the hull and from authority together, on the same terms as the
        panels: a kayak has no anchor windlass, and a passenger has no helm. The list
        is advisory - the server checks again when an order actually arrives - but
        offering a control that would only be refused is a poor way to treat somebody.

    """
    from .context import COMMAND

    if vessel is None or context != COMMAND:
        return []

    available = []
    for key, control in CONTROLS.items():
        if control["group"] == "sails" and vessel.sail_plan is None:
            continue
        if control["group"] == "anchor" and not hasattr(vessel, "anchored"):
            continue
        available.append(key)
    return sorted(available)


def order_for(key, detail=None, vessel=None):
    """
    Turn a control press into the command line it stands for.

    Args:
        key (str): Which control was pressed.
        detail (dict, optional): Whatever it carries - degrees, a bearing, a plan.
        vessel (Vessel, optional): The hull, for orders that are relative to how she
            is already heading.

    Returns:
        line (str or None): The command to run, or None if the request made no
            sense.

    Notes:
        Every value is rebuilt rather than passed through. A browser sends a number
        of degrees and gets a bearing back; it never sends text that reaches a
        command line, so there is nothing to escape and nothing to inject.

        **A relative order becomes an absolute one here.** "Ten degrees to port" is
        how a captain speaks, and `helm` takes a bearing - so the wheel-over is added
        to what she is already steering and the result is an ordinary `helm 084`
        that any text player could have typed. Inventing a `helm port 10` syntax to
        match the buttons would have given the graphical client a command the text
        one did not have, which is the one thing it may never do. Found by pressing
        the button and being told to give a bearing.

    """
    # A key has to be something a dictionary can be asked about. A browser is free
    # to send a list or an object where a name belongs, and `dict.get` raises on an
    # unhashable one rather than politely missing - which turned a nonsense press
    # into a traceback. Found by sending nonsense on purpose.
    if not isinstance(key, str):
        return None

    control = CONTROLS.get(key)
    if control is None:
        return None

    detail = detail or {}
    argument = control["argument"]

    if "{relative}" in argument:
        if vessel is None:
            return None
        degrees = _number(detail.get("degrees"), default=10.0)
        if degrees is None:
            return None
        over = max(1.0, min(MAX_ALTERATION, abs(degrees))) * control["hand"]
        ordered = getattr(vessel.orders, "heading", None)
        if ordered is None:
            ordered = vessel.heading
        argument = argument.format(relative=int((ordered + over) % 360.0))
    elif "{steady}" in argument:
        # Steady as she goes: hold the head she is actually lying on, which is not
        # necessarily the one she was last ordered.
        if vessel is None:
            return None
        argument = argument.format(steady=int(vessel.heading % 360.0))
    elif "{bearing}" in argument:
        bearing = _number(detail.get("bearing"))
        if bearing is None:
            return None
        argument = argument.format(bearing=int(bearing % 360.0))
    elif "{plan}" in argument:
        plan = _known_plan(detail.get("plan"))
        if plan is None:
            return None
        argument = argument.format(plan=plan)

    return f"{control['command']} {argument}".strip()


def _number(value, default=None):
    """
    Args:
        value: Whatever arrived from the browser.
        default: What to use when nothing was sent.

    Returns:
        number (float or None): The value as a number, or None if it was not one.

    """
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _known_plan(value):
    """
    Args:
        value: A sail plan name from the browser.

    Returns:
        key (str or None): The plan's key, or None if there is no such plan.

    Notes:
        Matched against the plans that actually exist rather than trusted. This is
        the only control carrying a word rather than a number, and it is the one
        place a client could otherwise have put arbitrary text on a command line.

    """
    from ..sailing import SAIL_PLANS

    if not isinstance(value, str):
        return None
    wanted = value.strip().lower()
    for plan in SAIL_PLANS:
        if plan.key == wanted:
            return plan.key
    return None
