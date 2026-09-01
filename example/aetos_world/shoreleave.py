"""
What a run ashore does for a crew, and why it is not part of the contrib.

`morale.Factor` says of itself: *data, not code - a game adds its own, and setting-specific
morale belongs to the setting*. Shore leave is exactly that. Whether a crew is cheered by an
afternoon on a beach depends entirely on what kind of ship and what kind of century a game
is about; a press-ganged frigate's people and a trading schooner's are not the same crew and
should not be moved by the same things.

So this lives in the example world, where a setting is allowed to have opinions, and the
contrib keeps none.

**A drink is not the point; being ashore is.** The bar is where it happens because that is
where people go, but the factor is earned by getting the crew off the ship - which is why it
is granted at the gangway and not at the counter. A captain who buys a round for a crew still
aboard has bought a round.

    ashore              the ship is alongside and the hands are let go
    a drink taken       a small extra, and it wears off
    back aboard         the standing lift goes with them for a while

**It wears off, and that is what makes it a decision.** A crew rested a week ago is a crew
who needs resting again, so a captain who never touches a port is one whose people slowly
sour. Morale settles towards its target over hours; this moves the target, and time does the
rest, which is the machinery `morale.settle` already provides.
"""

from ...morale import Factor

#: Being let ashore at all. The large one, and the one a captain plans a voyage around.
SHORE_LEAVE = Factor("shore_leave", 0.18)

#: A drink taken ashore, on top of it. Deliberately small: a captain cannot buy his way out
#: of a hard commission a glass at a time, and a crew that could be bought that cheaply would
#: make every other morale factor pointless.
A_DRINK_ASHORE = Factor("a_drink_ashore", 0.05)

#: How long the good of it lasts, in game seconds. About three days, so a trading run between
#: ports keeps a crew in reasonable heart and a long ocean passage does not.
LEAVE_LASTS = 3.0 * 24.0 * 3600.0

#: The most a run ashore can lift them, however many rounds are stood. Two factors and no
#: more, or a captain with deep pockets discovers that morale is a shop.
MOST_FROM_ONE_RUN = SHORE_LEAVE.weight + A_DRINK_ASHORE.weight


def granted(vessel, now, drink=False):
    """
    Note that this ship's people have been ashore.

    Args:
        vessel (Vessel): The ship whose crew it is.
        now (float): Game time, in seconds.
        drink (bool, optional): Whether something was taken as well as the air.

    Returns:
        held (tuple): The factors now standing, with when each was earned.

    Notes:
        Recorded against the ship rather than the person, because a crew is a body and shore
        leave is something a ship's company has or has not had. One hand ashore is one hand
        ashore; the watch below being let go is shore leave.

        Read whole, mutated, written back once - an attribute is pickled and committed on
        assignment, and a list edited through one commits on every touch.

    """
    held = dict(vessel.db.shore_leave or {})
    held[SHORE_LEAVE.key] = float(now)
    if drink:
        held[A_DRINK_ASHORE.key] = float(now)
    vessel.db.shore_leave = held
    return factors(vessel, now)


def factors(vessel, now):
    """
    What a run ashore is still worth to this crew.

    Args:
        vessel (Vessel): The ship.
        now (float): Game time, in seconds.

    Returns:
        held (tuple): `morale.Factor` entries still in force.

    Notes:
        Expiry is worked out on reading rather than swept up on a timer. There is no tick to
        get wrong, nothing to clean up after a crash, and a ship nobody has looked at for a
        month costs nothing at all - the answer is simply that the leave has run out, which
        it has.

    """
    held = vessel.db.shore_leave or {}
    standing = []
    for factor in (SHORE_LEAVE, A_DRINK_ASHORE):
        when = held.get(factor.key)
        if when is not None and now - float(when) < LEAVE_LASTS:
            standing.append(factor)
    return tuple(standing)


def wearing_off(vessel, now):
    """
    Args:
        vessel (Vessel): The ship.
        now (float): Game time, in seconds.

    Returns:
        share (float): How much of the leave is left, one down to nothing.

    Notes:
        For a narrator that wants to say the hands are getting restless before they get
        surly. Nothing uses it yet; it is here because the alternative is a game asking the
        question and being told only yes or no.

    """
    when = (vessel.db.shore_leave or {}).get(SHORE_LEAVE.key)
    if when is None:
        return 0.0
    left = LEAVE_LASTS - (now - float(when))
    return max(0.0, min(1.0, left / LEAVE_LASTS))


__all__ = (
    "SHORE_LEAVE",
    "A_DRINK_ASHORE",
    "LEAVE_LASTS",
    "MOST_FROM_ONE_RUN",
    "granted",
    "factors",
    "wearing_off",
)
