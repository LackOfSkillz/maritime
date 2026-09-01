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

from .. import seabed
from ..position import WorldPosition
from ..vessel import vessel_in
from .context import COMMAND, PASSENGER, resolve_maritime_ui_context
from .payloads import CAPABILITIES, ChartSheet, Contacts, Mode, Status, Sync
from .controls import offered as controls_offered


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


def status_for(vessel, commanding=True):
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
    # A hull that has been destroyed under a session comes back as None from
    # Evennia, and one being taken apart mid-tick may answer partially. Neither is
    # worth an interface falling over, and the honest answer to "what do her
    # instruments read" for a ship that is gone is nothing at all.
    if vessel is None or getattr(vessel, "maritime_position", None) is None:
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
        controls=controls_offered(vessel, COMMAND if commanding else PASSENGER),
        vessel=_who_she_is(vessel),
        company=_who_is_aboard(vessel),
        battery=_what_she_carries_in_guns(vessel),
        cargo=_what_she_carries_below(vessel),
        motion=motion,
        environment=_what_the_sea_is_doing(vessel),
        propulsion=_what_drives_her(vessel),
        condition=_what_is_wrong(vessel),
        units=_units(),
    )


def _who_she_is(vessel):
    """
    Returns:
        vessel (dict): Her name, her length, and what class of hull she is.

    Notes:
        The class is her `template_key` - the identifier of the `VesselTemplate`
        she was built from, which the host game chose and this contrib never
        interprets. It is published because an interface may reasonably want to
        draw a brig differently from a cutter, and there is no other honest way
        for it to know: a rig here is a polar curve rather than a name, and
        deliberately so.

        Relayed rather than understood. Whatever a game writes in that field
        arrives at its own stylesheet unchanged, so this contrib never acquires a
        taxonomy of ships - which would be the host's to own and would be wrong
        the moment somebody invented a hull nobody here had thought of.

        Her own hull only. A *contact's* class is never published, because what
        may be told about another ship is what the lookout has made out, and that
        is governed by her sighting rather than by what would be convenient to
        draw.

    """
    who = {"name": vessel.key}
    length = getattr(vessel, "length", None)
    if length:
        who["length"] = length

    # Nested rather than guarded: a hull with no attribute store hands back None, and
    # asking None for a template key hands back None again. The `is not None` check
    # that was here first could not change the answer either way.
    template = getattr(getattr(vessel, "db", None), "template_key", None)
    if template:
        who["template"] = template
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


#: How long one drawing of the paper stands before it is worth drawing again.
#:
#: A chart is not an instrument. The coastline does not move, the soundings do not
#: change, and a minute of a coasting vessel's progress is a hundred metres or so -
#: comfortably inside the four hundred between printed depths. Her own position is
#: drawn by the client from the status message, which does arrive every tick.
CHART_REVISION_SECONDS = 60.0


def chart_revision(now):
    """
    Which drawing of the paper a moment belongs to.

    Args:
        now (float): Game time in seconds.

    Returns:
        revision (int): The same number for every moment within one revision.

    Notes:
        Shared with the transport on purpose, because the two have to agree exactly.
        The transport decides whether to *draw* a sheet by working out what revision it
        would carry; if that formula ever drifted from the one the sheet is stamped
        with, charts would either be sent on every tick or never sent again.

    """
    return int(now // CHART_REVISION_SECONDS)


def chart_for(vessel, reach=10000.0, centre=(0.0, 0.0)):
    """
    The paper, drawn around where she reckons she is - or wherever he is looking.

    Args:
        vessel (Vessel or None): The hull.
        reach (float, optional): How far to draw, in metres from the middle of the sheet.
        centre (tuple, optional): `(east, north)` metres from her reckoned position to the
            middle of the sheet. Zero draws her in the middle, which is the ordinary case.

    Returns:
        sheet (ChartSheet): What the chart shows, or an empty one if she has none.

    Notes:
        An empty sheet is the right answer for a ship with no chart aboard, and the
        interface shows it as empty rather than as open sea. Sailing without a chart
        is a real situation and should look like one.

    """
    from . import cartography, relief

    if vessel is None:
        return ChartSheet()

    chart = vessel.chart_here()
    here = vessel.reckoned_position or vessel.maritime_position
    if chart is None or here is None:
        return ChartSheet(reach=reach)

    from .. import config

    now = config.time_provider().now()
    world = vessel.map_here()

    # Where the *sheet* is centred, which is only where she is until somebody drags it.
    #
    # Everything below is measured from this rather than from her, because a chart is a
    # patch of sea and she is a mark on it. Conflating the two is what made dragging useless:
    # the sheet was always drawn around the ship, so sliding it moved one fixed square about
    # inside its window and the corner arrived in the middle with nothing behind it.
    east, north = centre
    middle = WorldPosition(here.x + east, here.y + north, here.z, here.region)

    span = reach * 2.0

    # The sheet's corner goes on a lattice of the world, not on the ship.
    #
    # Sounding the seabed is nine tenths of what a chart costs, and the seabed is the same
    # for everybody - but two sheets centred on two ships sample points that are near each
    # other and equal nowhere, so nothing can be shared. Snapping the corner costs a shift
    # of under one cell, invisible at the scale a cell is drawn at, and is the difference
    # between two hundred captains paying two hundred times and paying once.
    #
    # Only the corner. The cell stays exactly what the span and the grid make it, because
    # the contours are traced against that same span - see `cartography.sample`.
    cell = span / float(cartography.GRID - 1)
    west = seabed.snap(middle.x - reach, cell)
    south = seabed.snap(middle.y - reach, cell)

    grid = cartography.sample(chart, world, now, west, south, span)

    coast = cartography.as_offsets(
        cartography.worth_drawing(
            cartography.join(cartography.contour(grid, cartography.COASTLINE, west, south, span)),
            span,
        ),
        middle,
    )

    depths = {}
    for line in cartography.FATHOM_LINES:
        traced = cartography.contour(grid, cartography.fathoms(line), west, south, span)
        if traced:
            kept = cartography.worth_drawing(cartography.join(traced), span)
            if kept:
                depths[line] = cartography.as_offsets(kept, middle)

    return ChartSheet(
        reach=reach,
        own=[round(-east, 1), round(-north, 1)],
        coastline=coast,
        depths=depths,
        marks=_marks_within(middle, reach),
        dangers=_dangers_within(world, middle, reach, now),
        relief=relief.shaded(grid, _safe_water_for(vessel)) or "",
        route=_route_of(vessel, middle),
        soundings=cartography.soundings(grid, west, south, span, middle),
        coverage=cartography.coverage(chart, middle),
        graticule=cartography.graticule(world, middle, reach),
        revision=chart_revision(now),
    )


def _what_she_carries_in_guns(vessel):
    """
    Returns:
        battery (dict): Her guns, or nothing if she carries none.

    Notes:
        A hull with no guns reports no battery, so no battery panel is drawn -
        which is the composition rule, not a special case for unarmed ships. A
        kayak is not a warship with an empty gun deck.

        Reported as counts rather than a list of every piece. A captain wants to
        know how many bear and how many are ready; which particular gun is being
        served is the gun deck's business and is on the `guns` report already.

    """
    mounts = getattr(vessel, "mounts", ())
    if not mounts:
        return {}

    serviceable = set(vessel.serviceable_mounts)
    now = _now()
    ready = sum(1 for mount in serviceable if mount.loaded and now >= mount.ready_at)
    return {
        "carried": len(mounts),
        "serviceable": len(serviceable),
        "ready": ready,
        "dismounted": len(mounts) - len(serviceable),
        "shot": sorted({mount.shot.key for mount in serviceable if mount.shot}),
    }


def _what_she_carries_below(vessel):
    """
    Returns:
        cargo (dict): What is in her hold and what it is doing to her.

    Notes:
        Mass and volume both, because a hull can run out of either and they are
        different problems: a ship full of feathers is out of room with tons to
        spare, and one full of shot is down to her marks with the hold half empty.

        Her draught is here rather than with the other instruments because it is a
        consequence of what she is carrying, and a captain reading it wants the
        reason next to the number.

    """
    hold = getattr(vessel, "hold_volume", 0.0)
    deadweight = getattr(vessel, "deadweight", 0.0)
    if not hold and not deadweight:
        # No hold and nothing she may carry: a boat rather than a ship, and there is
        # no cargo panel to draw for her.
        return {}

    out = {
        "mass": round(getattr(vessel, "cargo_tonnes", 0.0), 1),
        "deadweight": round(deadweight, 1),
        "hold": round(hold, 1),
    }

    draft = getattr(vessel, "draft", None)
    if draft:
        out["draft"] = round(draft, 2)
    freeboard = getattr(vessel, "freeboard", None)
    if freeboard:
        out["freeboard"] = round(freeboard, 2)
    return out


def _now():
    """
    Returns:
        now (float): The time on the simulation clock.

    """
    from .. import config

    return config.time_provider().now()


def _safe_water_for(vessel):
    """
    How much water this hull wants under her, for the chart's safety contour.

    Args:
        vessel (Vessel): The hull reading the chart.

    Returns:
        depth (float or None): Metres, or None for a hull that draws nothing worth
            drawing a contour for.

    Notes:
        Her draught plus the margin grounding already warns at, so the wash on the paper
        and the warning on the instruments agree about what shoal water is. Two numbers
        for one idea is how an interface starts telling a captain two different stories.

    """
    from ..grounding import SHOAL_WARNING_CLEARANCE

    draft = getattr(vessel, "draft", None)
    if not draft:
        return None
    return float(draft) + SHOAL_WARNING_CLEARANCE


def _dangers_within(world, here, reach, now=0.0):
    """
    The rocks on the paper, out to the edge of the sheet.

    Args:
        world (MaritimeMapProvider): The world's terrain.
        here (WorldPosition): Where she reckons she is.
        reach (float): How far the sheet extends, in metres.
        now (float, optional): Game time, used to work out what the tide does here.

    Returns:
        dangers (list): Each as an offset, with what is over it and what it is.

    Notes:
        **The half of the charted layer that was never drawn.** `docs/client.md` has
        said since the interface was designed that the charted layer carries land,
        soundings, marks *and hazards*; the first three arrived and the fourth did
        not. Grounding has been asking providers for hazards all along, so a rock a
        game had authored would hole a hull that sailed over it while the chart drew
        open water above it - which is worse than a rock drawn nowhere, because the
        captain has looked at the paper and is entitled to believe it.

        It cannot come from the soundings. Those are sampled on a grid, and anything
        narrower than the grid is not smoothed away but *missed* - and missed
        differently depending on where the grid falls, so it would appear and vanish
        as she sailed. A symbol is how a chart says "here, exactly", and it is what
        real charts do with an isolated danger for the same reason.

        Offsets, like everything else on the sheet, so a browser is never handed a
        survey of the world.

        Charted rather than sighted: this is what the survey recorded, so it stays on
        the paper in fog and at night exactly as the coastline does.

    """
    if world is None:
        return []

    # Not every provider answers, and none has to. A game with no authored hazards
    # gets an empty list and a chart exactly as it was.
    dangers = getattr(world, "charted_dangers", None)
    if dangers is None:
        return []

    # What the water does here, so a rock can be told from an island.
    #
    # These are three different things on a chart and were one thing in the payload: a
    # twelve-metre island came through flagged as drying, and the client dutifully printed
    # "dries 12.0 m" - which is not a thing any chart has ever said. A feature dries if it
    # is bare at low water and covered at high; above the highest tide it is land, and
    # below the lowest it is a rock that never shows.
    low_water, high_water = _tidal_span(world, here, now)

    # Sorted here rather than trusted from the provider. Shallowest first is a property
    # of the *sheet* - a client taking the first entry is taking the worst news - and
    # making it true at the point the sheet is built means it is true for every provider
    # rather than for the ones that remembered.
    out = []
    for danger in sorted(dangers(here, reach), key=lambda found: -found.top_z):
        out.append(
            {
                "id": danger.key,
                "east": round(danger.x - here.x, 1),
                "north": round(danger.y - here.y, 1),
                "radius": round(danger.radius, 1),
                "top_z": round(danger.top_z, 2),
                "bottom": danger.bottom,
                "label": danger.key,
                "dries": low_water < danger.top_z <= high_water,
                "ashore": danger.top_z > high_water,
            }
        )
    return out


#: How long to watch the tide before deciding what a rock does, in game seconds, and how
#: often to look. A tidal day is a little over twenty-four hours, so a full one catches both
#: high waters and both lows however the game's harmonics are phased.
TIDAL_DAY = 25.0 * 3600.0
TIDE_SAMPLES = 25


def _tidal_span(world, here, now):
    """
    The highest and lowest the water gets, measured rather than declared.

    Args:
        world (MaritimeMapProvider): The world, and through it the tide.
        here (WorldPosition): Where the sheet is centred. The tide is taken once for the
            sheet rather than once per danger - it varies over hundreds of kilometres, not
            over the few that separate two rocks on one chart.
        now (float): Game time in seconds.

    Returns:
        span (tuple): `(lowest, highest)` surface elevation in metres.

    Notes:
        A tide provider says where the water is *now*. Nothing in the interface says how
        far it moves, and a chart needs that: whether a rock covers is a question about the
        range, not about this instant.

        Rather than add a method every game would have to implement, this watches. A full
        tidal day of samples answers the question for a harmonic tide, a story-driven
        flood, or no tide at all, and costs a couple of dozen calls to arithmetic that is
        already cheap. A provider with no tide returns the same number every time and the
        span comes out zero, which is the correct answer for a game that has no tides:
        nothing covers and uncovers, because nothing moves.

    """
    surface = [
        world.sea_surface_z_at(here, now + TIDAL_DAY * step / (TIDE_SAMPLES - 1))
        for step in range(TIDE_SAMPLES)
    ]
    return min(surface), max(surface)


def _marks_within(here, reach):
    """
    The buoyage on the paper, out to the edge of the sheet.

    Args:
        here (WorldPosition): Where she reckons she is.
        reach (float): How far the sheet extends, in metres.

    Returns:
        marks (list): Each mark as an offset, with its kind and what it means.

    Notes:
        Charted rather than sighted, and the distinction is the one the whole panel
        turns on. A buoy is a thing somebody wrote down: it stays on the paper in
        fog, at night, and when nobody is looking at it, exactly as the coastline
        does. Only *ships* come and go with the lookout.

        The meaning travels beside the kind, as the two facts buoyage already
        answers: which way the safe water lies, and whether the mark is there
        because something will sink you. A mark whose significance a player has to
        look up is a mark that will be passed on the wrong side.

    """
    from .. import config
    from ..buoyage import marks_danger, safe_water_from

    network = config.navigation_network()
    if network is None:
        return []

    out = []
    for mark in network.marks():
        if mark.position.region != here.region:
            continue
        east = mark.position.x - here.x
        north = mark.position.y - here.y
        if abs(east) > reach or abs(north) > reach:
            continue
        out.append(
            {
                "id": mark.key,
                "east": round(east, 1),
                "north": round(north, 1),
                "kind": mark.kind,
                "label": mark.key,
                "safe_water": safe_water_from(mark.kind),
                "danger": marks_danger(mark.kind),
            }
        )
    return out


def _route_of(vessel, here):
    """
    The course she is following, if she has one.

    Args:
        vessel (Vessel): The hull.
        here (WorldPosition): Where she reckons she is.

    Returns:
        route (list): `[east, north]` for each mark still to make.

    Notes:
        Offsets from the reckoning like everything else, so a course plotted on a
        chart that has drifted is drawn where the navigator believes it runs. That
        is what he would have pencilled on the paper.

    """
    route = getattr(vessel, "route", None)
    if not route:
        return []
    return [
        [round(mark.position.x - here.x, 1), round(mark.position.y - here.y, 1)]
        for mark in route.waypoints
        if mark.position.region == here.region
    ]


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
