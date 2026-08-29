"""
What the world is doing at a place.

Wind, current, ground, water and what can be seen from here. Everything a thing floating at
a position needs to know about its surroundings, and nothing about what that thing is.

These were methods on `Vessel` until currents arrived and made a fourth of them. They are
functions of a position rather than of a hull because a swimmer, a raft, a barrel and a
wreck are all subject to the same weather and the same water, and none of them are vessels.
When floating entities land they call these, unchanged.

Each of these is a seam. Today wind is one global vector, current is one global set and
drift, and visibility is one number, all read from settings; a weather provider replaces all
three later and no caller here or above changes. That is the point of routing them through
one module instead of reading settings wherever a value happens to be needed.

"""

from . import config
from .currents import carried, made_good
from .grounding import keel_clearance
from .observation import detection_limit, scan
from .sailing import WindVector
from .traffic import MAX_TARGET_HEIGHT, traffic


def wind_at(position):
    """
    The wind at a place.

    Args:
        position (WorldPosition): Where to ask. Ignored while the wind is global.

    Returns:
        wind (WindVector): Bearing the wind blows *from*, and its speed.

    """
    return WindVector(
        bearing=float(config.get_setting("WIND_BEARING", 0.0)),
        speed=float(config.get_setting("WIND_SPEED", 0.0)),
    )


def current_at(position, game_time):
    """
    The current at a place and a moment.

    Args:
        position (WorldPosition): Where to ask.
        game_time (float): Game time in seconds.

    Returns:
        current (CurrentVector): Set and drift. Slack water if the game has not
            configured any.

    Notes:
        Takes a time as well as a place for the same reason depth queries do. A
        tidal stream reverses twice a day, so a current sampled without a time is
        a current from an unspecified moment - which is a bug that produces
        plausible numbers.

    """
    return config.current_provider().current_at(position, game_time)


def visibility_at(position):
    """
    How far the air lets you see at a place.

    Args:
        position (WorldPosition): Where to ask. Ignored while visibility is
            global.

    Returns:
        visibility (float): Metres.

    """
    return config.visibility()


def clearance_at(position, draft, game_time):
    """
    How much water there is under a hull of this draft, here.

    Args:
        position (WorldPosition): Where to ask.
        draft (float): How deep it sits, in metres.
        game_time (float): Game time in seconds.

    Returns:
        clearance (float): Metres between keel and ground. Negative means it is
            in the ground.

    """
    return keel_clearance(position, draft, config.map_provider(), game_time)


def set_and_drift(position, heading, speed, game_time):
    """
    What the water here does to something moving through it.

    Args:
        position (WorldPosition): Where it is.
        heading (float): Where it is pointing, in degrees.
        speed (float): Speed through the water, in metres per second.
        game_time (float): Game time in seconds.

    Returns:
        track (tuple): `(current, course_made_good, speed_made_good)`.

    Notes:
        Returns the current alongside the result so a caller reporting a track
        does not have to sample the water twice and risk getting two different
        answers from a stream that turns between the calls.

    """
    current = current_at(position, game_time)
    course, made = made_good(heading, speed, current)
    return current, course, made


def carried_from(position, game_time, seconds):
    """
    Where the water takes something over a stretch of time.

    Args:
        position (WorldPosition): Where it was.
        game_time (float): Game time in seconds.
        seconds (float): Elapsed game seconds.

    Returns:
        position (WorldPosition): Where the current has put it.

    """
    return carried(position, current_at(position, game_time), seconds)


def contacts_from(position, heading, height_of_eye, candidates):
    """
    What can be seen from a place.

    Args:
        position (WorldPosition): Where the observer is.
        heading (float): Which way they are facing, in degrees.
        height_of_eye (float): How high their eye is, in metres.
        candidates (iterable): `(target, target_position, target_height)` triples.

    Returns:
        sightings (tuple): What is in sight, nearest first.

    """
    return scan(position, heading, height_of_eye, candidates, visibility_at(position))


def vessels_within_sight(position, height_of_eye, exclude=None):
    """
    Vessels close enough to be worth testing properly.

    Args:
        position (WorldPosition): Where the observer is.
        height_of_eye (float): How high their eye is, in metres.
        exclude (any, optional): One entity to leave out - normally the observer.

    Returns:
        candidates (tuple): `(vessel, position, air_draft)` triples.

    Notes:
        The broad phase. The radius is the furthest anything at all could be seen
        from this height, and each candidate is then tested against its own
        height - so a low boat and a tall ship at the same range get different
        answers, which is the entire point.

    """
    radius = detection_limit(height_of_eye, MAX_TARGET_HEIGHT, visibility_at(position))
    return tuple(
        (vessel, vessel.maritime_position, vessel.air_draft)
        for vessel in traffic().near(position, radius)
        if vessel is not exclude and vessel.maritime_position is not None
    )
