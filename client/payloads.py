"""
What goes on the wire.

Plain data with a version on it, and nothing else. These structures know how to describe
themselves and know nothing about vessels, sessions or browsers - which is what lets the
same payload be built by a test, sent to a browser, logged, or handed to a client nobody
here has heard of.

**Every message carries its protocol version.** A contrib that ships an interface has to
assume the interface outlives it: somebody will run a year-old browser against a new server,
or the reverse. A version costs one integer and turns "the panel went blank" into "the panel
said it did not understand version 3".

"""

from dataclasses import dataclass, field

#: The protocol these payloads speak. Raise it when a message changes shape in a way an
#: older client could not read; adding a field nobody is required to look at is not that.
PROTOCOL_VERSION = 1

#: What the server may send. Names are prefixed because they share a namespace with every
#: other system in a host game, and `status` alone would be a poor neighbour.
MODE = "maritime_mode"
STATUS = "maritime_status"
CONTACTS = "maritime_contacts"
CHART = "maritime_chart"
SYNC = "maritime_sync"

#: What a client may send back.
HELLO = "maritime_hello"
VIEW = "maritime_view"

#: Everything a client is allowed to announce it understands. A capability the server does
#: not recognise is ignored rather than refused - an older server meeting a newer client
#: should degrade, not argue.
CAPABILITIES = ("mode", "status", "chart", "contacts", "controls")


@dataclass(frozen=True)
class Payload:
    """
    The shape every message shares.

    Attributes:
        version (int): The protocol this was built for.

    Notes:
        Subclasses add their own fields and name their own `kind`. Nothing here
        serialises to JSON itself; that is the transport's business, and keeping it
        there means these can be asserted against in tests as ordinary objects.

    """

    version: int = PROTOCOL_VERSION

    @property
    def kind(self):
        """
        Returns:
            kind (str): The command name this payload is sent under.

        Raises:
            NotImplementedError: If a subclass forgot to name itself.

        """
        raise NotImplementedError("A payload must say what kind of message it is.")

    def as_message(self):
        """
        Returns:
            message (dict): The keyword arguments to send it with.

        """
        raise NotImplementedError("A payload must say how it goes on the wire.")


@dataclass(frozen=True)
class Mode(Payload):
    """
    Which interface the session should be showing.

    Attributes:
        mode (str): One of `context.CONTEXTS`.
        vessel_id (str or None): Which hull, when aboard one. None ashore or in the
            water.

    Notes:
        The vessel comes along because a client that has been shown two ships in one
        session needs to know when it is looking at a different one, and comparing
        names would break the moment a game let a captain rename his ship.

    """

    mode: str = "none"
    vessel_id: str = None

    @property
    def kind(self):
        return MODE

    def as_message(self):
        return {"version": self.version, "mode": self.mode, "vessel_id": self.vessel_id}


@dataclass(frozen=True)
class Status(Payload):
    """
    What her instruments read.

    Attributes:
        vessel (dict): Who she is - name, and how she is rigged.
        controls (list): What this person may be offered on this hull.
        company (dict): Who is aboard, and how they are bearing it.
        battery (dict): Her guns, if she carries any.
        cargo (dict): What is in her hold, if she has one.
        motion (dict): Where she points and where she is actually going.
        environment (dict): What the sea and sky are doing to her.
        propulsion (dict): What is driving her.
        condition (dict): What is wrong with her.
        units (dict): How this game says distances, depths and speeds.

    Notes:
        Grouped rather than flat because the groups are how a person reads a
        board: everything about her motion together, everything about the weather
        together. A client is free to lay them out differently.

        **A reading absent from a group is a reading that is not true here**, not one
        the server could not be bothered to send. A pond has no tide, a ship off her
        chart has no sounding, and a hull with nothing wrong reports no damage. The
        interface draws what it is given, so absence has to mean something.

        The units come with the numbers. The numbers themselves are always SI -
        metres, metres per second, degrees - so that a client doing arithmetic never
        has to guess, and the units say how this particular game prefers them spoken.

    """

    vessel: dict = field(default_factory=dict)
    controls: list = field(default_factory=list)
    company: dict = field(default_factory=dict)
    battery: dict = field(default_factory=dict)
    cargo: dict = field(default_factory=dict)
    motion: dict = field(default_factory=dict)
    environment: dict = field(default_factory=dict)
    propulsion: dict = field(default_factory=dict)
    condition: dict = field(default_factory=dict)
    units: dict = field(default_factory=dict)

    @property
    def kind(self):
        return STATUS

    def as_message(self):
        return {
            "version": self.version,
            "vessel": dict(self.vessel),
            "controls": list(self.controls),
            "company": dict(self.company),
            "battery": dict(self.battery),
            "cargo": dict(self.cargo),
            "motion": dict(self.motion),
            "environment": dict(self.environment),
            "propulsion": dict(self.propulsion),
            "condition": dict(self.condition),
            "units": dict(self.units),
        }


@dataclass(frozen=True)
class Contacts(Payload):
    """
    What the lookout has, and only that.

    Attributes:
        contacts (tuple): One entry per sighting, nearest first. Each carries a
            bearing, a range and whatever the observer can honestly call it.

    Notes:
        **Volatile by design.** A contact exists here while she is in sight and is
        gone the moment she is not. Nothing about her persists, because a mark that
        outlived the sighting would be a radar repeater and would undo detection in
        exactly the way a true position would undo navigation.

        **Bearing and range, never coordinates.** That is what a lookout calls down
        and it is all a chart may draw from him.

    """

    contacts: tuple = ()

    @property
    def kind(self):
        return CONTACTS

    def as_message(self):
        return {"version": self.version, "contacts": [dict(one) for one in self.contacts]}


@dataclass(frozen=True)
class ChartSheet(Payload):
    """
    What the paper shows, around where she reckons she is.

    Attributes:
        reach (float): How far the sheet extends from her, in metres.
        coastline (list): Polylines of the waterline, as offsets in metres.
        depths (dict): Fathom lines, keyed by the fathom they trace.
        soundings (list): `[east, north, fathoms]` figures to print.
        marks (list): Buoyage on the paper, each with its kind and its meaning.
        route (list): The plotted course, as offsets in metres.
        coverage (dict): The edges of the sheet, so the interface can show where
            surveying stops.
        revision (int): Changes when the drawing does, so an unchanged sheet is
            not sent again.

    Notes:
        **Offsets from the reckoned position, never coordinates.** A chart that has
        drifted from the reckoning draws the coast in the wrong place, which is what
        being lost looks like and what the navigator has to work with. It also means
        a browser is never handed a survey of the world.

    """

    reach: float = 0.0
    coastline: list = field(default_factory=list)
    depths: dict = field(default_factory=dict)
    soundings: list = field(default_factory=list)
    marks: list = field(default_factory=list)
    route: list = field(default_factory=list)
    coverage: dict = field(default_factory=dict)
    revision: int = 0

    @property
    def kind(self):
        return CHART

    def as_message(self):
        return {
            "version": self.version,
            "reach": self.reach,
            "coastline": list(self.coastline),
            "depths": {str(line): paths for line, paths in self.depths.items()},
            "soundings": list(self.soundings),
            "marks": list(self.marks),
            "route": list(self.route),
            "coverage": dict(self.coverage),
            "revision": self.revision,
        }


@dataclass(frozen=True)
class Sync(Payload):
    """
    Everything the client needs to draw itself from nothing.

    Attributes:
        mode (Mode): The interface to show.
        capabilities (tuple): What the server will actually send this session.

    Notes:
        Sent once when a client announces itself and once after a reconnect, because
        a client that has just woken up cannot be assumed to remember anything and
        must not be left rendering a ship the player left an hour ago.

        Deltas are cheaper and come later. A full snapshot is what makes them safe:
        there is always a known state to apply them to.

    """

    mode: Mode = field(default_factory=Mode)
    status: Status = None
    capabilities: tuple = ()

    @property
    def kind(self):
        return SYNC

    def as_message(self):
        return {
            "version": self.version,
            "mode": self.mode.as_message(),
            "status": self.status.as_message() if self.status else None,
            "capabilities": list(self.capabilities),
        }
