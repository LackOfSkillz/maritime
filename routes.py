"""
Routes: a course laid off between marks, not a path found across the sea.

The ocean is continuous and a vessel moves through it continuously, so there is nothing to
pathfind over - no grid, no tiles, no cells. What a navigator actually does is pick a
handful of places worth going by, and lay a straight leg between each pair:

    Harbour A
      \\
       Fairway Buoy ---- North Cardinal
                              \\
                               Bar Beacon ---- Harbour B

Between two marks she steers a course and holds it. The marks exist because some water is
safe and some is not, and somebody who knew the difference chose where the safe water runs.

**A network is authored, not derived.** The links are a game's statement about which waters
are passable, which is knowledge a chart-maker or a pilot has and an algorithm does not. A
route planner that searched the seabed for a way through would find every gap a hull could
theoretically squeeze, including the ones no sane master would take at night.

**Legs are long and few.** Planning happens once, over perhaps a dozen marks, and the
vessel then sails hundreds of miles of continuous water between two of them. That is the
whole reason this is cheap: the expensive thing would be re-planning per tick, and there is
nothing to re-plan.

"""

import heapq
from dataclasses import dataclass

from .buoyage import BUOY_HEIGHT, SAFE_WATER

# How close counts as having reached a mark, in metres. A buoy is a place you
# pass, not a place you touch, and a vessel that had to hit one exactly would
# circle it forever.
ARRIVAL_RANGE = 200.0


@dataclass(frozen=True)
class Waypoint:
    """
    A mark worth going by.

    Attributes:
        key (str): What it is called.
        position (WorldPosition): Where it is.
        kind (str): What kind of mark it is, from `buoyage.KINDS`. The kind is what
            carries the *meaning* - which side to leave it on, or which way the safe
            water lies - and a mark without one is just a place with a name.
        height (float): How high it stands above the water, in metres. A buoy is a
            low thing and drops below the horizon quickly, which is exactly why
            landfall is made on a light or a beacon rather than on a can.

    Notes:
        `kind` defaults to a safe-water mark, which is the honest default: it says
        "the channel is here" and nothing more, so a world that has not thought about
        buoyage gets marks that make no claims rather than marks that make wrong ones.

    """

    key: str
    position: object
    kind: str = SAFE_WATER
    height: float = BUOY_HEIGHT


@dataclass(frozen=True)
class Route:
    """
    An ordered set of marks, and the legs between them.

    Attributes:
        waypoints (tuple): `Waypoint` objects, in the order to take them.

    """

    waypoints: tuple = ()

    @property
    def distance(self):
        """
        Returns:
            distance (float): The whole route, in metres.

        """
        return sum(
            first.position.horizontal_distance_to(second.position)
            for first, second in zip(self.waypoints, self.waypoints[1:])
        )

    def mark(self, index):
        """
        The mark at a given point in the route.

        Args:
            index (int): How many marks have been left astern.

        Returns:
            waypoint (Waypoint or None): The mark to make for, or None if the
                route has been run.

        """
        if 0 <= index < len(self.waypoints):
            return self.waypoints[index]
        return None

    def advance(self, position, index, arrival=ARRIVAL_RANGE):
        """
        Tick the route on past any marks she has now reached.

        Args:
            position (WorldPosition): Where she is.
            index (int): How many marks she had already left astern.
            arrival (float, optional): How close counts as reached, in metres.

        Returns:
            index (int): How many she has left astern now.

        Notes:
            Progress along a route is state, and this is why. Deriving it from
            position alone - "the first mark she is not near" - looks right until
            she reaches the end, at which point the first mark is the furthest
            away and she is sent back to the beginning. A route is an order of
            places, and which of them are behind her is a fact about the voyage
            rather than about the water.

            Advances past several at once, because a mark can be passed close
            aboard on the way to the next one and a route that stalled on it
            would have her circling a buoy she had already left astern.

        """
        while index < len(self.waypoints):
            mark = self.waypoints[index]
            if position.horizontal_distance_to(mark.position) > arrival:
                break
            index += 1
        return index

    def remaining(self, position, index):
        """
        How far there is still to go.

        Args:
            position (WorldPosition): Where she is.
            index (int): How many marks she has left astern.

        Returns:
            distance (float): Metres, by way of the marks still to come.

        """
        ahead = self.waypoints[index:]
        if not ahead:
            return 0.0
        total = position.horizontal_distance_to(ahead[0].position)
        return total + sum(
            first.position.horizontal_distance_to(second.position)
            for first, second in zip(ahead, ahead[1:])
        )

    def __bool__(self):
        return bool(self.waypoints)

    def __len__(self):
        return len(self.waypoints)


class NavigationNetwork:
    """
    The marks a game has laid, and which of them join up.

    Notes:
        Authored rather than derived. Which waters are passable is knowledge a
        pilot has and an algorithm does not - a planner that searched the seabed
        would find every gap a hull could theoretically fit through, including
        the ones no master would take at night with a following sea.

    """

    def __init__(self):
        self._waypoints = {}
        self._links = {}

    def add(self, waypoint):
        """
        Add a mark.

        Args:
            waypoint (Waypoint): The mark.

        Returns:
            network (NavigationNetwork): This network, for chaining.

        Raises:
            ValueError: If a mark of that name is already laid.

        """
        if waypoint.key in self._waypoints:
            raise ValueError(f"There is already a mark called {waypoint.key!r}.")
        self._waypoints[waypoint.key] = waypoint
        self._links.setdefault(waypoint.key, set())
        return self

    def link(self, first, second):
        """
        Record that there is safe water between two marks.

        Args:
            first (str): One mark's name.
            second (str): The other's.

        Returns:
            network (NavigationNetwork): This network, for chaining.

        Raises:
            KeyError: If either mark is not laid.

        Notes:
            Both ways. A channel that is passable one way and not the other is a
            real thing - a tidal gate, a one-way traffic scheme - and it wants
            its own representation rather than a half-built link that looks like
            an oversight.

        """
        for key in (first, second):
            if key not in self._waypoints:
                raise KeyError(f"No mark called {key!r}.")
        self._links[first].add(second)
        self._links[second].add(first)
        return self

    def marks(self):
        """
        Returns:
            marks (tuple): Every mark in the network, in the order they were laid.

        """
        return tuple(self._waypoints.values())

    def waypoint(self, key):
        """
        Args:
            key (str): A mark's name.

        Returns:
            waypoint (Waypoint or None): The mark, if it is laid.

        """
        return self._waypoints.get(key)

    def nearest(self, position):
        """
        The mark closest to a place.

        Args:
            position (WorldPosition): Where she is.

        Returns:
            waypoint (Waypoint or None): The nearest mark in the same region.

        """
        candidates = [
            waypoint
            for waypoint in self._waypoints.values()
            if waypoint.position.region == position.region
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda mark: position.horizontal_distance_to(mark.position))

    def plan(self, start, end):
        """
        The shortest way from one mark to another.

        Args:
            start (str): The mark to start from.
            end (str): The mark to reach.

        Returns:
            route (Route): The marks to take in order. Empty if there is no way
                through.

        Notes:
            Dijkstra over the authored links, weighted by real distance. Short
            enough to be obvious and fast enough to be free at this scale - a
            game has tens of marks, not thousands, and the expensive thing would
            be re-planning every tick rather than planning once.

            No route is a real answer. Two harbours with no safe water between
            them are two harbours you cannot sail between, and returning an empty
            route says so rather than inventing a leg across a headland.

        """
        if start not in self._waypoints or end not in self._waypoints:
            return Route()
        if start == end:
            return Route((self._waypoints[start],))

        best = {start: 0.0}
        came_from = {}
        queue = [(0.0, start)]
        seen = set()

        while queue:
            cost, here = heapq.heappop(queue)
            if here in seen:
                continue
            seen.add(here)
            if here == end:
                break
            for neighbour in self._links[here]:
                if neighbour in seen:
                    continue
                step = self._waypoints[here].position.horizontal_distance_to(
                    self._waypoints[neighbour].position
                )
                through = cost + step
                if through < best.get(neighbour, float("inf")):
                    best[neighbour] = through
                    came_from[neighbour] = here
                    heapq.heappush(queue, (through, neighbour))

        if end not in best:
            return Route()

        order = [end]
        while order[-1] != start:
            order.append(came_from[order[-1]])
        order.reverse()
        return Route(tuple(self._waypoints[key] for key in order))

    def __len__(self):
        return len(self._waypoints)

    def __repr__(self):
        return f"NavigationNetwork({len(self._waypoints)} marks)"


class Routed:
    """
    The course a vessel is following, if any.

    Notes:
        The Evennia-side face of `routes`. A route is a plan rather than a
        constraint - she carries one, and something has to choose to steer it.
        Phase 10's crew automation is what will.

    """

    def at_object_creation(self):
        """Set up this part of a newly created vessel."""
        super().at_object_creation()
        self.db.route = None
        self.db.route_index = 0

    @property
    def route(self):
        """
        Returns:
            route (Route or None): The course she is following.

        """
        return self.db.route

    @route.setter
    def route(self, route):
        """
        Args:
            route (Route or None): The course to follow.

        """
        self.db.route = route or None
        self.db.route_index = 0

    @property
    def route_index(self):
        """
        Returns:
            index (int): How many marks of her route she has left astern.

        """
        return int(self.db.route_index or 0)

    @route_index.setter
    def route_index(self, index):
        """
        Args:
            index (int): How many marks are behind her.

        """
        self.db.route_index = int(index)

    def marks_in_sight(self, height_of_eye=None):
        """
        Which of this world's marks can be seen from her.

        Args:
            height_of_eye (float, optional): How high the observer's eye is, in
                metres. Defaults to her own lookout's.

        Returns:
            sightings (tuple): `Sighting` objects, nearest first.

        Notes:
            Marks are reported apart from vessels rather than mixed in with them,
            because they are a different kind of news. A sail on the horizon is a
            question; a buoy on the horizon is an answer.

            They go through the same horizon arithmetic as everything else, so a
            low can drops out of sight long before a beacon does - which is the
            reason landfall was made on lights and steeples rather than on buoys.

        """
        from . import config, environment

        network = config.navigation_network()
        if network is None:
            return ()
        position = self.maritime_position
        if position is None:
            return ()
        if height_of_eye is None:
            height_of_eye = self.height_of_eye

        candidates = tuple(
            (mark, mark.position, mark.height)
            for mark in network.marks()
            if mark.position is not None and mark.position.region == position.region
        )
        return environment.contacts_from(position, self.heading, height_of_eye, candidates)

    def next_mark(self):
        """
        The mark she is making for.

        Returns:
            waypoint (Waypoint or None): The next one, or None if she has no
                route or has run it.

        Notes:
            Ticks her progress on as a side effect, because arriving at a mark is
            something that happens by sailing past it rather than by anybody
            deciding it has happened.

        """
        position = self.maritime_position
        if position is None or not self.route:
            return None
        self.route_index = self.route.advance(position, self.route_index)
        return self.route.mark(self.route_index)

    def passage_remaining(self):
        """
        How far she still has to run.

        Returns:
            distance (float or None): Metres by way of the marks still to come,
                or None if she has no route.

        """
        position = self.maritime_position
        if position is None or not self.route:
            return None
        return self.route.remaining(position, self.route_index)
