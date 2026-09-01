"""
A world served from disk, with no generator behind it.

The point of this is that a game can clone the contrib and be sailing a real coast - a
proper one, with a harbour and a bar and an island chain - without installing a terrain
generator, without a seed, and without waiting for anything to be computed. The seabed was
sounded once by somebody else and written down.

**Soundings are not a world.** That is the thing worth stating first, because it is the
mistake this format exists to avoid. A grid of elevations gives depth and a coastline and
nothing else: no bottom to hold an anchor or hole a hull, no rock the survey marked, no
island with a name to be first to, no latitude. All of those come from a manifest beside the
soundings, in plain text, so the interesting half of a world stays readable and reviewable
while only the bulk is binary.

    <bundle>/world.json      the manifest - anchor, dangers, landmarks, bottom
    <bundle>/1053m.seabed    soundings, coarse
    <bundle>/211m.seabed     soundings, finer

**Finer than the finest level is interpolated, and that is the honest cost.** A generator
answers at any scale because it computes; this answers between its points by interpolating,
so a chart zoomed past the finest baked level draws smooth ground rather than real detail.
That is the trade a shipped world makes, it is why the coarse levels are the ones worth
shipping, and it is why a game that wants detail everywhere wants a generator instead.
"""

import json
import math
import os

from .bathymetry import SAND, MaritimeMapProvider
from .discovery import Landmark
from .position import WorldPosition
from .tiles import Hazard

#: What the manifest is called inside a bundle.
MANIFEST = "world.json"

#: Radius used to turn metres into degrees, in metres. The same figure the rest of the
#: contrib measures the horizon with.
EARTH_RADIUS_M = 6_371_000.0

#: What the ground is where the bundle has nothing to say. Deep enough that a hull sails
#: over it without grounding, so the edge of a bundle is open ocean rather than a wall.
OFF_THE_BUNDLE_M = -2_000.0


class BakedMapProvider(MaritimeMapProvider):
    """
    Terrain read from a bundle of soundings.

    Notes:
        Ordinary in every way that matters: it is a `MaritimeMapProvider`, so charts,
        grounding, tides and the client all treat it exactly as they treat a generated
        world. What it does not do is compute anything.

    """

    #: Where to read from. A subclass names its own bundle; the setting is for a game
    #: pointing at one of its own.
    bundle = None

    def __init__(self, bundle=None, tide_provider=None):
        """
        Args:
            bundle (str, optional): Directory holding the manifest and soundings.
            tide_provider (MaritimeTideProvider, optional): What moves the water.

        """
        super().__init__(tide_provider=tide_provider)
        self.bundle = bundle or self.bundle or _configured_bundle()
        self.levels = ()
        self.manifest = {}
        self._dangers = ()
        self._landmarks = ()
        if self.bundle:
            self._open(self.bundle)

    # --- opening ------------------------------------------------------------

    def _open(self, bundle):
        """
        Args:
            bundle (str): Directory to read.

        Notes:
            Soundings finest first, so a lookup takes the best answer available and stops.

        """
        from . import bake

        found = []
        for name in sorted(os.listdir(bundle)):
            if not name.endswith(".seabed"):
                continue
            sheet = bake.read(os.path.join(bundle, name))
            if sheet is not None:
                found.append(sheet)
        self.levels = tuple(sorted(found, key=lambda sheet: sheet.cell))

        path = os.path.join(bundle, MANIFEST)
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as source:
                self.manifest = json.load(source)
        self._dangers = tuple(_danger(record) for record in self.manifest.get("dangers", ()))
        self._landmarks = tuple(
            _landmark(record) for record in self.manifest.get("landmarks", ())
        )

    # --- the ground ---------------------------------------------------------

    def terrain_z_at(self, position):
        """
        Ground elevation at a point.

        Args:
            position (WorldPosition): Where to sample.

        Returns:
            terrain_z (float): Elevation in metres relative to datum.

        Notes:
            From the finest level that covers the point, interpolated between its four
            surrounding soundings. On a lattice point that is the sounding itself, exactly,
            so a chart drawn at a baked scale is the chart the generator drew.

            Off every level it is open ocean rather than a wall. A bundle has an edge, and a
            ship that sails over it should find deep water and an unsurveyed chart, not a
            cliff.

        """
        for sheet in self.levels:
            found = _bilinear(sheet, position.x, position.y)
            if found is not None:
                return found
        return OFF_THE_BUNDLE_M

    def bottom_type_at(self, position):
        """
        Args:
            position (WorldPosition): Where to sample.

        Returns:
            bottom (str): What the seabed is made of.

        Notes:
            From the nearest recorded danger if the point is on one - a rock is rock - and
            otherwise the bundle's own default. Composition across the open seabed is not
            carried: it is a whole second layer of data to buy a difference that only shows
            when a hull touches, and where a hull touches is nearly always something the
            survey marked.

        """
        for danger in self._dangers:
            if math.hypot(danger.x - position.x, danger.y - position.y) <= danger.radius:
                return danger.bottom
        return self.manifest.get("bottom", SAND)

    # --- what the survey recorded -------------------------------------------

    def charted_dangers(self, position, reach):
        """
        Args:
            position (WorldPosition): Where the sheet is centred.
            reach (float): How far it extends, in metres.

        Returns:
            dangers (tuple): What a survey recorded near there, shallowest first.

        """
        near = [
            danger
            for danger in self._dangers
            if abs(danger.x - position.x) <= reach and abs(danger.y - position.y) <= reach
        ]
        near.sort(key=lambda danger: -danger.top_z)
        return tuple(near)

    def hazards_touching(self, before, after, width=0.0):
        """
        Args:
            before (WorldPosition): Where the step started.
            after (WorldPosition): Where it would end.
            width (float, optional): Her beam, in metres.

        Returns:
            hazards (tuple): What she would touch, shallowest first.

        Notes:
            The same list the chart draws from, measured against the corridor she swept.
            A hull is sampled at a handful of points on her outline and something small
            enough fits between them; this is what stops a marked rock being missed by
            arithmetic.

        """
        from .spatial import distance_to_track

        touched = [
            danger
            for danger in self._dangers
            if distance_to_track(WorldPosition(danger.x, danger.y), before, after)
            <= danger.radius + width / 2.0
        ]
        touched.sort(key=lambda danger: -danger.top_z)
        return tuple(touched)

    def landmarks_near(self, position, reach):
        """
        Args:
            position (WorldPosition): Where to look from.
            reach (float): How far, in metres.

        Returns:
            landmarks (tuple): Named places somebody could be the first to find.

        """
        return tuple(
            mark
            for mark in self._landmarks
            if abs(mark.x - position.x) <= reach and abs(mark.y - position.y) <= reach
        )

    def geographic_at(self, position):
        """
        Args:
            position (WorldPosition): Where to ask.

        Returns:
            place (tuple or None): `(latitude, longitude)`, or None if the bundle does not
                say where in the world it is.

        Notes:
            From an anchor in the manifest, on a tangent plane at that anchor. Good to a
            few metres over the couple of hundred kilometres a bundle covers, which is well
            inside what the chart itself claims, and enough for meridians that converge
            correctly - which is the whole reason the graticule wanted this.

        """
        anchor = self.manifest.get("anchor")
        if not anchor:
            return None
        latitude = anchor[0] + math.degrees(position.y / EARTH_RADIUS_M)
        spread = max(math.cos(math.radians(latitude)), 1e-6)
        return (latitude, anchor[1] + math.degrees(position.x / (EARTH_RADIUS_M * spread)))

    def __repr__(self):
        return (
            f"BakedMapProvider({os.path.basename(self.bundle or '')!r}, "
            f"{len(self.levels)} levels, {len(self._dangers)} dangers)"
        )


class AetosCoast(BakedMapProvider):
    """
    The coast that ships with the contrib: a harbour, its approaches and six islands.

    Notes:
        Point `MARITIME_MAP_PROVIDER` at this and a game is sailing a real generated coast
        with nothing installed and nothing to build:

            MARITIME_MAP_PROVIDER = (
                "evennia.contrib.full_systems.maritime.baked_world.AetosCoast"
            )

        It was generated once, elsewhere, and sounded into the bundle beside this file -
        five sheets from a thousand-metre coastal one down to a ten-metre inshore one over
        the harbour and the island chain, at some three megabytes altogether. There is no
        generator behind it and no seed; the ground was found by somebody else and written
        down.

        What it is not is infinite. Sail past the bundle's edge and there is open ocean and
        an unsurveyed chart, which is honest - the survey stops where the surveyor stopped.
        A game wanting a whole planet wants a generator.

    """

    def __init__(self, bundle=None, tide_provider=None):
        """
        Args:
            bundle (str, optional): Somewhere else to read from.
            tide_provider (MaritimeTideProvider, optional): What moves the water.

        """
        super().__init__(
            bundle=bundle or os.path.join(os.path.dirname(__file__), "example", "aetos"),
            tide_provider=tide_provider,
        )


def _bilinear(sheet, x, y):
    """
    Args:
        sheet (bake.Baked): A sounded rectangle.
        x (float): Easting, in metres.
        y (float): Northing, in metres.

    Returns:
        elevation (float or None): The ground, or None if this rectangle does not cover it.

    Notes:
        Between the four surrounding soundings, which on a lattice point reduces to that
        sounding exactly - so nothing is smeared where the data is real.

    """
    column = (x - sheet.west) / sheet.cell
    row = (y - sheet.south) / sheet.cell
    west = math.floor(column)
    south = math.floor(row)
    if not (0 <= west < sheet.columns - 1 and 0 <= south < sheet.rows - 1):
        # The far edge is still a valid point, just with nothing beyond it to blend with.
        if 0 <= round(column) < sheet.columns and 0 <= round(row) < sheet.rows:
            return sheet.at(x, y)
        return None

    across = column - west
    up = row - south
    base = south * sheet.columns + west
    lower = sheet.values[base] * (1.0 - across) + sheet.values[base + 1] * across
    upper = (
        sheet.values[base + sheet.columns] * (1.0 - across)
        + sheet.values[base + sheet.columns + 1] * across
    )
    return (lower * (1.0 - up) + upper * up) * sheet.scale


def _danger(record):
    """
    Args:
        record (dict): One entry from the manifest.

    Returns:
        danger (Hazard): What the survey recorded.

    """
    return Hazard(
        key=record["key"],
        x=float(record["x"]),
        y=float(record["y"]),
        radius=float(record.get("radius", 0.0)),
        top_z=float(record.get("top_z", 0.0)),
        bottom=record.get("bottom", SAND),
    )


def _landmark(record):
    """
    Args:
        record (dict): One entry from the manifest.

    Returns:
        landmark (Landmark): A named place.

    """
    return Landmark(
        key=record["key"],
        x=float(record["x"]),
        y=float(record["y"]),
        radius=float(record.get("radius", 0.0)),
        height=float(record.get("height", 0.0)),
        kind=record.get("kind", "island"),
    )


def _configured_bundle():
    """
    Returns:
        bundle (str or None): What `MARITIME_WORLD_BUNDLE` points at.

    """
    from . import config

    return config.get_setting("WORLD_BUNDLE")


__all__ = ("MANIFEST", "OFF_THE_BUNDLE_M", "BakedMapProvider", "AetosCoast")
