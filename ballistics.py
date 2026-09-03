"""
What happens between the muzzle and the target.

Split out of `weapons` when that file reached the thousand-line ceiling, and the seam was
already there to cut along: everything here takes numbers and returns numbers. A distance,
a sea state, an aspect - no mounts, no vessels, no database. That is what makes these the
easiest functions in the contrib to test and the ones a game is most likely to want to
replace.

**The shot is not instant, and everything follows from that.** You fire where she will be,
and the solution is wrong the moment she alters course. A model where the ball arrives the
instant it leaves would make manoeuvring in action pointless, because there would be nothing
to manoeuvre out of the way of.

**Four things decide whether it hits**, and they multiply rather than adding: how far off she
is, how much the sea is moving the platform, what aspect she presents, and how good the
weapon is to begin with. Multiplying is what makes them compound - a long shot in a seaway at
a bow-on target is *very* unlikely, which is exactly right, where adding penalties would have
left it merely difficult.

"""

import math

from .weather import SEA_STATES

# How much of its accuracy a weapon keeps at the far edge of its range. Guns do
# not stop working at maximum range, they stop hitting anything - and a cliff
# edge would make range bands a formality rather than a decision.
LONG_RANGE_ACCURACY = 0.15

# How much accuracy a heavy sea takes, at the worst of it. A rolling deck is the
# single largest thing between a gun and its target, and gunners have always
# known to fire on the roll.
MAX_SEA_PENALTY = 0.7

#: How much of the sea's penalty a cable takes out, for a ship lying to her anchor.
#:
#: Not all of it. An anchored ship still rises to a swell - she is not on land - but she
#: is not rolling to her own way through the water, she lies head to wind and tide rather
#: than across it, and the gun crews are working a deck that moves predictably. It is why
#: anchored batteries outshot ships under way, and why laying yourself where your broadside
#: bears and *staying* there was worth the hours it took.
ANCHORED_STEADINESS = 0.5

# How much smaller a bow-on target is than a beam-on one. A hull end-on presents
# her width; broadside she presents her length, which for most vessels is three
# or four times as much.
END_ON_FRACTION = 0.35


def time_of_flight(distance, projectile_speed):
    """
    How long the shot is in the air.

    Args:
        distance (float): Range in metres.
        projectile_speed (float): How fast it flies, in metres per second.

    Returns:
        seconds (float): Game seconds of flight.

    """
    if projectile_speed <= 0.0:
        return 0.0
    return distance / projectile_speed


def aim_point(target_position, target_heading, target_speed, flight_time):
    """
    Where to lay the gun, given that she will not wait.

    Args:
        target_position (WorldPosition): Where she is now.
        target_heading (float): Her heading, in degrees.
        target_speed (float): Her speed over the ground, in metres per second.
        flight_time (float): How long the shot will be in the air.

    Returns:
        position (WorldPosition): Where to aim.

    Notes:
        Aiming off, which is the whole of gunnery against a moving target. It
        assumes she holds her course for the flight, and that assumption is
        wrong the instant she alters - which is exactly why altering course under
        fire is worth doing, and why this is a solution rather than a guarantee.

    """
    if target_speed <= 0.0 or flight_time <= 0.0:
        return target_position
    return target_position.moved(target_heading, target_speed * flight_time)


def range_accuracy(distance, max_range):
    """
    How much of a weapon's accuracy survives the range.

    Args:
        distance (float): Range in metres.
        max_range (float): The weapon's reach.

    Returns:
        fraction (float): From `LONG_RANGE_ACCURACY` to 1.

    Notes:
        Falls away smoothly rather than at a cliff. Guns do not stop working at
        maximum range, they stop hitting - and a hard edge would turn range bands
        into a formality instead of a decision about when to open fire.

    """
    if max_range <= 0.0:
        return 0.0
    reach = min(1.0, max(0.0, distance / max_range))
    return 1.0 - (1.0 - LONG_RANGE_ACCURACY) * reach


def sea_accuracy(sea_state, steady=False):
    """
    How much of it survives the motion of the deck.

    Args:
        sea_state (str): One of `SEA_STATES`.
        steady (bool, optional): Whether she is firing from a steady platform - lying to
            her anchor rather than under way.

    Returns:
        fraction (float): From 1 in a calm down to `1 - MAX_SEA_PENALTY`, and less of a
            fall than that from a steady platform.

    Notes:
        The largest single thing between a gun and its target. Gunners have
        always fired on the roll for this reason, which is a refinement this does
        not model - here the sea simply makes shooting harder, which is the part
        that changes decisions.

    """
    if sea_state not in SEA_STATES:
        return 1.0
    worst = max(1, len(SEA_STATES) - 1)
    penalty = MAX_SEA_PENALTY * (SEA_STATES.index(sea_state) / worst)
    if steady:
        # Scales the penalty rather than adding a bonus, so a flat calm is worth exactly
        # the same at anchor as under way. A cable cannot make a still sea stiller, and a
        # model that paid out for anchoring in a calm would be paying for nothing.
        penalty *= 1.0 - ANCHORED_STEADINESS
    return 1.0 - penalty


def aspect_accuracy(angle):
    """
    How big a target she is, at this aspect.

    Args:
        angle (float): Her aspect, from `tactical.aspect`.

    Returns:
        fraction (float): From `END_ON_FRACTION` bow-on to 1 beam-on.

    Notes:
        A hull end-on presents her width; broadside she presents her length,
        which for most vessels is three or four times as much. It is why a ship
        under fire turns towards the guns, and why crossing a T is worth
        manoeuvring for from both sides of the exchange.

    """
    broadside = abs(math.sin(math.radians(angle)))
    return END_ON_FRACTION + (1.0 - END_ON_FRACTION) * broadside


def hit_chance(weapon, distance, sea_state, target_aspect, steady=False):
    """
    The chance this shot connects.

    Args:
        weapon (WeaponType): What is firing.
        distance (float): Range in metres.
        sea_state (str): The sea she is shooting from.
        target_aspect (float): The target's aspect, in degrees.
        steady (bool, optional): Whether she is firing from a steady platform.

    Returns:
        chance (float): From 0 to 1.

    Notes:
        Four independent factors multiplied: the weapon, the range, the sea and
        the size of what she is showing you. Each is separately arguable and
        separately tunable, which is the point of not rolling them into one
        number nobody can reason about.

    """
    return max(
        0.0,
        min(
            1.0,
            weapon.accuracy
            * range_accuracy(distance, weapon.max_range)
            * sea_accuracy(sea_state, steady)
            * aspect_accuracy(target_aspect),
        ),
    )
