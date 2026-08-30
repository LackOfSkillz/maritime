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
from .currents import STILL, carried, made_good
from .weather import CALM
from .grounding import keel_clearance
from .observation import detection_limit, scan
from .traffic import MAX_TARGET_HEIGHT, traffic


def weather_at(position, game_time=None):
    """
    Everything the sky is doing at a place.

    Args:
        position (WorldPosition): Where to ask.
        game_time (float, optional): Game time in seconds. Defaults to now.

    Returns:
        weather (Weather): Wind, visibility and sea state together.

    Notes:
        One sampling, because these are not independent. Reading the wind from
        one place and the visibility from another is how a system ends up with a
        gale you can see forever across.

    """
    if game_time is None:
        game_time = config.time_provider().now()
    return config.weather_provider().weather_at(position, game_time)


def wind_at(position, game_time=None):
    """
    The wind at a place.

    Args:
        position (WorldPosition): Where to ask.
        game_time (float, optional): Game time in seconds.

    Returns:
        wind (WindVector): Bearing the wind blows *from*, and its speed.

    """
    return weather_at(position, game_time).wind


def sea_state_at(position, game_time=None):
    """
    What the water is doing at a place.

    Args:
        position (WorldPosition): Where to ask.
        game_time (float, optional): Game time in seconds.

    Returns:
        state (str): One of `SEA_STATES`.

    """
    return weather_at(position, game_time).sea_state


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


def visibility_at(position, game_time=None):
    """
    How far the air lets you see at a place.

    Args:
        position (WorldPosition): Where to ask.
        game_time (float, optional): Game time in seconds.

    Returns:
        visibility (float): Metres.

    """
    return weather_at(position, game_time).visibility


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


class Situated:
    """
    What the world is doing where a vessel happens to be.

    Notes:
        Thin by design. Each of these is one call into this module's functions,
        which take a position and know nothing about hulls - so a swimmer or a
        drifting boat can ask the same questions without being a vessel.

    """

    def map_here(self):
        """
        The world's terrain.

        Returns:
            provider (MaritimeMapProvider): The configured map.

        """
        from . import config

        return config.map_provider()

    def wind_here(self):
        """
        The wind where this vessel is.

        Returns:
            wind (WindVector): The local wind.

        """
        from . import environment

        return environment.wind_at(self.maritime_position)

    def current_here(self):
        """
        The current where this vessel is.

        Returns:
            current (CurrentVector): Set and drift, or slack water if she has not
                been launched.

        """
        from . import config, environment

        position = self.maritime_position
        if position is None:
            return STILL
        return environment.current_at(position, config.time_provider().now())

    def sea_here(self):
        """
        What the water is doing where she is.

        Returns:
            state (str): One of `SEA_STATES`, or a flat calm if she has not been
                launched.

        """
        from . import environment

        position = self.maritime_position
        if position is None:
            return CALM
        return environment.sea_state_at(position)

    def keel_clearance(self):
        """
        How much water she has under her.

        Returns:
            clearance (float or None): Metres between keel and ground, or None if
                she has not been launched.

        """
        from . import config, environment

        position = self.maritime_position
        if position is None:
            return None
        return environment.clearance_at(position, self.draft, config.time_provider().now())

    def made_good(self):
        """
        Where she is actually going, and how fast.

        Returns:
            track (tuple or None): `(course, speed)` over the ground, or None if
                she has not been launched.

        Notes:
            Not the same as heading and speed, and the difference is the whole
            reason currents exist. `speed` is speed through the water - what a
            log line measures - so a vessel set sideways by a stream is making
            good a course she is not pointing at, at a speed she is not sailing.

        """
        from . import config, environment

        position = self.maritime_position
        if position is None:
            return None
        _current, course, made = environment.set_and_drift(
            position, self.heading, self.speed, config.time_provider().now()
        )
        return course, made
