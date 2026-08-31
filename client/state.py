"""
Turning a situation into something a client may be told.

The layer between the simulation and the wire, and the only place allowed to decide what a
player is entitled to know. Everything below is a deliberate act of *publication*: the
simulation holds a great deal that no interface may show, and the way to keep it that way is
to build payloads from what a character can find out rather than from what a vessel holds.

The rule that matters most here, and the one that will be easiest to break later: a
graphical client must never make the navigator more knowledgeable than the character. When
positions arrive in this module they are reckoned positions, not true ones - and the true
one is not fetched and then dropped, it is never asked for at all. There is no filtering
step to forget.

"""

from ..vessel import vessel_in
from .context import resolve_maritime_ui_context
from .payloads import CAPABILITIES, ChartSheet, Contacts, Mode, Status, Sync


def mode_for(character, room=None):
    """
    Which interface this character should be looking at.

    Args:
        character (Object or None): Whoever is looking.
        room (Object, optional): Resolve as though they were standing here, for
            the moment somebody is part-way through a door.

    Returns:
        mode (Mode): The interface, and the hull it belongs to.

    """
    where = getattr(character, "location", None) if room is None else room
    # No branch for being ashore. There is no vessel in a tavern, so `_identify`
    # already answers None there, and an early return would only have said it twice.
    return Mode(
        mode=resolve_maritime_ui_context(character, where),
        vessel_id=_identify(vessel_in(where)),
    )


def status_for(vessel):
    """
    What her instruments read, as far as anybody aboard may know it.

    Args:
        vessel (Vessel or None): The hull.

    Returns:
        status (Status or None): Her readings, or None if there is no hull.

    Notes:
        Every reading is omitted rather than sent empty when the world cannot
        answer it here. A pond has no tide; a ship off the edge of her chart has no
        sounding, and that absence is a real and dangerous situation which the
        interface must be able to show as absence rather than as zero.

        Heading and course made good are both here and are deliberately different
        numbers. One is where she points and the other where she is going, and the
        gap between them is the whole of what the water is doing to her.

    """
    if vessel is None:
        return None

    motion = {"heading": _rounded(vessel.heading), "speed_through_water": vessel.speed}

    ordered = getattr(vessel.orders, "heading", None)
    if ordered is not None:
        motion["ordered_heading"] = _rounded(ordered)

    track = vessel.made_good()
    if track is not None:
        course, over_ground = track
        motion["course_made_good"] = _rounded(course)
        motion["speed_over_ground"] = over_ground

    return Status(
        vessel=_who_she_is(vessel),
        company=_who_is_aboard(vessel),
        motion=motion,
        environment=_what_the_sea_is_doing(vessel),
        propulsion=_what_drives_her(vessel),
        condition=_what_is_wrong(vessel),
        units=_units(),
    )


def _who_she_is(vessel):
    """
    Returns:
        vessel (dict): Her name and how she is rigged.

    """
    who = {"name": vessel.key}
    length = getattr(vessel, "length", None)
    if length:
        who["length"] = length
    return who


def _who_is_aboard(vessel):
    """
    Returns:
        company (dict): Her people, or nothing if she has no ship's company.

    Notes:
        Morale is published as the band it falls in and never as a percentage. The
        simulation bands it on purpose: a captain is told his people are wavering,
        which is a thing he can act on, rather than that they are at sixty-one per
        cent, which invites him to manage a number. Handing a browser the number
        would undo that decision from the outside.

        A hull with no company at all reports nothing, because a kayak has no crew
        to be steady or otherwise and the paddler is the host game's business.

    """
    company = getattr(vessel, "company", None)
    if company is None:
        return {}

    out = {"complement": company.complement, "fit": company.fit}
    quality = getattr(company, "quality", None)
    if quality is not None:
        out["quality"] = quality.key
    band = getattr(vessel, "morale_band", None)
    if band:
        out["morale"] = band
    return out


def contacts_for(vessel, height_of_eye=None):
    """
    What her lookout can see, as her lookout has it.

    Args:
        vessel (Vessel or None): The hull.
        height_of_eye (float, optional): How high the observer is.

    Returns:
        contacts (Contacts): Everything in sight, nearest first.

    Notes:
        **Bearing and range, never a position.** That is what a lookout reports and
        it is all a chart may draw, because a contact plotted at its true coordinates
        would be a radar return rather than a sighting.

        **Named only when identified.** `Sighting.level` already decides how much an
        observer can honestly say, and this passes that decision straight through. A
        hull nobody has made out is "a sail" here exactly as she is on the deck; the
        interface cannot leak a name the fiction has not granted, because it is never
        given one.

    """
    if vessel is None:
        return Contacts()

    from ..messaging import describe_contact
    from ..observation import IDENTIFIED

    seen = []
    for sighting in vessel.contacts(height_of_eye):
        seen.append(
            {
                "id": f"c{getattr(sighting.target, 'id', len(seen))}",
                "bearing": _rounded(sighting.bearing),
                "relative": sighting.relative,
                "range": sighting.distance,
                "level": sighting.level,
                "label": describe_contact(sighting),
                "identified": sighting.level == IDENTIFIED,
            }
        )
    return Contacts(contacts=tuple(seen))


def chart_for(vessel, reach=10000.0):
    """
    The paper, drawn around where she reckons she is.

    Args:
        vessel (Vessel or None): The hull.
        reach (float, optional): How far to draw, in metres from her.

    Returns:
        sheet (ChartSheet): What the chart shows, or an empty one if she has none.

    Notes:
        An empty sheet is the right answer for a ship with no chart aboard, and the
        interface shows it as empty rather than as open sea. Sailing without a chart
        is a real situation and should look like one.

    """
    from . import cartography

    if vessel is None:
        return ChartSheet()

    chart = vessel.chart_here()
    here = vessel.reckoned_position or vessel.maritime_position
    if chart is None or here is None:
        return ChartSheet(reach=reach)

    from .. import config

    now = config.time_provider().now()
    world = vessel.map_here()
    span = reach * 2.0
    west, south = here.x - reach, here.y - reach

    grid = cartography.sample(chart, world, now, west, south, span)

    coast = cartography.as_offsets(
        cartography.join(cartography.contour(grid, cartography.COASTLINE, west, south, span)),
        here,
    )

    depths = {}
    for line in cartography.FATHOM_LINES:
        traced = cartography.contour(grid, cartography.fathoms(line), west, south, span)
        if traced:
            depths[line] = cartography.as_offsets(cartography.join(traced), here)

    return ChartSheet(
        reach=reach,
        coastline=coast,
        depths=depths,
        soundings=cartography.soundings(grid, west, south, span, here),
        coverage=cartography.coverage(chart, here),
        revision=int(now // 60),
    )


def _what_the_sea_is_doing(vessel):
    """
    Returns:
        environment (dict): Only the readings this water can actually answer.

    """
    out = {}

    wind = vessel.wind_here()
    if wind is not None and wind.speed > 0.0:
        out["wind_from"] = _rounded(wind.bearing)
        out["wind_speed"] = wind.speed

    current = vessel.current_here()
    drift = getattr(current, "drift", 0.0) if current is not None else 0.0
    if drift > 0.0:
        out["current_set"] = _rounded(current.set)
        out["current_drift"] = drift

    # Charted, never true. A sounding read off the paper is what a navigator has,
    # and off the chart there is no sounding at all - which is the single most
    # important thing an interface can decline to invent.
    depth = vessel.charted_depth()
    if depth is not None:
        out["charted_depth"] = depth

    sea = vessel.sea_here()
    if sea:
        out["sea_state"] = sea
    return out


def _what_drives_her(vessel):
    """
    Returns:
        propulsion (dict): What she has set, and whether she is held.

    """
    out = {}
    plan = getattr(vessel, "sail_plan", None)
    if plan is not None:
        out["sail_plan"] = plan.name
    if getattr(vessel, "anchored", False):
        out["anchor"] = "down"
    elif plan is not None:
        out["anchor"] = "up"
    return out


def _what_is_wrong(vessel):
    """
    Returns:
        condition (dict): How sound each track is, from 0 to 1. Higher is better,
            so that a client can draw them as bars that empty as she is hurt.

    """
    damage = getattr(vessel, "damage", None)
    if damage is None:
        return {}

    # The hull is always reported, sound or not. It is the track that sinks her, it
    # is the one a captain glances at, and a board that only showed it once she was
    # holed would be telling him at the worst possible moment.
    out = {"hull": 1.0 - min(1.0, max(0.0, getattr(damage, "hull", 0.0)))}

    # The rest are news rather than furniture. Three bars sitting at full is
    # wallpaper; a bar appearing means something has just been shot away.
    for track in ("rigging", "oars", "weapons"):
        hurt = getattr(damage, track, 0.0)
        if hurt > 0.0:
            out[track] = 1.0 - min(1.0, hurt)
    return out


def _units():
    """
    Returns:
        units (dict): How this game prefers distances and depths spoken.

    Notes:
        The numbers themselves are always SI, so a client doing arithmetic never
        has to guess. This says only how to say them.

    """
    from .. import config
    from ..formatting import FATHOMS, LEAGUES

    return {
        "distance": config.get_setting("DISTANCE_UNITS", LEAGUES),
        "depth": config.get_setting("DEPTH_UNITS", FATHOMS),
    }


def _rounded(bearing):
    """
    Args:
        bearing (float): Degrees.

    Returns:
        degrees (float): The same, wrapped into a compass.

    """
    return float(bearing) % 360.0


def sync_for(character, capabilities=CAPABILITIES, room=None):
    """
    Everything a client needs to draw itself from nothing.

    Args:
        character (Object or None): Whoever is looking.
        capabilities (iterable, optional): What this session will be sent.
        room (Object, optional): Resolve as though they were standing here.

    Returns:
        sync (Sync): A complete snapshot.

    Notes:
        Currently that is the mode alone. Instruments, chart and contacts arrive in
        later phases and join here rather than being sent separately, so that a
        client applying a snapshot never has to reason about which parts of it
        arrived and which did not.

    """
    mode = mode_for(character, room)
    where = getattr(character, "location", None) if room is None else room
    return Sync(
        mode=mode,
        status=status_for(vessel_in(where)),
        capabilities=tuple(capabilities),
    )


def _identify(vessel):
    """
    Args:
        vessel (Vessel or None): The hull, if there is one.

    Returns:
        identifier (str or None): A stable handle for it.

    Notes:
        The database id rather than the name, because a client that has been shown
        two ships needs to tell them apart and a game may well let a captain rename
        his. Prefixed so it reads as an opaque handle rather than as a number a
        client might be tempted to do arithmetic on, and so it can never be
        mistaken for something to pass back as an instruction.

    """
    if vessel is None:
        return None
    identifier = getattr(vessel, "id", None)
    return None if identifier is None else f"v{identifier}"
