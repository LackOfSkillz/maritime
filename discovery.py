"""
Who saw it first, and who first set foot on it.

A world nobody has been to is worth more than a world everybody has, and the difference is
entirely bookkeeping: the ground is the same either way. What makes the far side of an ocean
worth crossing is that the crossing is *recorded* - that a place carries the name of the ship
that found it, permanently, and that anybody who later looks it up is told.

    The Greater Horn
    First sighted by Aetos, with Kestrel and Wren
    First landing by Kestrel

Three separate things live here and they are worth keeping apart:

    landmarks   named places worth being first to     supplied by the game's world
    claims      who was first, and when               permanent, global, one per place
    coverage    which sea a given person has seen     private, and only for drawing fog

**Claims are global and permanent. Coverage is personal.** They answer different questions -
"who found this" versus "may I draw this" - and a system that conflated them would either
tell every player who discovered a place they have never heard of, or forget a discovery
when the discoverer logged out.

**A claim is made once and never again.** That is what makes the write cost a non-issue: a
ship crossing an ocean triggers a handful of writes over a voyage, not one per tick. It is
also what makes the credit worth having.

**Nothing here decides what a landmark is.** The game's world does, through
`MaritimeMapProvider.landmarks_near`. A generator that names its islands gets discovery for
free; one that does not has nothing to discover, which is the correct answer for a game
whose sea is a featureless shelf.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass

from evennia.scripts.scripts import DefaultScript

from .observation import geographic_range

#: What a landmark is, roughly, for the wording of a report and for how far off it shows.
ISLAND = "island"
LANDMASS = "landmass"
HEADLAND = "headland"
ROCK = "rock"
BANK = "bank"
ANCHORAGE = "anchorage"

LANDMARK_KINDS = (ISLAND, LANDMASS, HEADLAND, ROCK, BANK, ANCHORAGE)

#: Kinds a person can stand on, and so be first to stand on. A bank is under water and a
#: rock awash is not somewhere anybody plants a flag; an island is.
UNDERFOOT = (ISLAND, LANDMASS, HEADLAND, ANCHORAGE)

#: Height of eye for a lookout, in metres, when a vessel cannot say what her masthead is.
#:
#: A lookout at deck level on a small craft. Deliberately modest: getting this wrong the
#: generous way would have a sloop discovering a coastline over the horizon.
DEFAULT_HEIGHT_OF_EYE = 3.0

#: What key the ledger is kept under. One per game.
LEDGER_KEY = "maritime_discoveries"


@dataclass(frozen=True)
class Landmark:
    """
    A named place somebody can be the first to find.

    Attributes:
        key (str): Its name, and its identity in the ledger. Two landmarks with one name
            are one landmark, which is why a world must not name two islands alike.
        x (float): Easting of its middle, in metres.
        y (float): Northing of its middle, in metres.
        radius (float): How far it extends, in metres.
        height (float): How high it stands above the water, in metres. Decides how far off
            it can be raised - a headland is seen from a long way and a sandbank is not.
        kind (str): One of the kinds above.

    Notes:
        Plain coordinates rather than a `WorldPosition`, and shaped exactly like a
        `Hazard` for the same reason: a world generator supplying these should not have to
        import maritime to describe its own islands. Anything with these five attributes
        will do.

        Deliberately not a `Danger`. A danger is a thing that will hole a hull and belongs
        on the chart as a warning; a landmark is a thing worth having a name and belongs in
        the ledger as an achievement. Many places are both, and some are only one: an
        uncharted pinnacle is a serious danger and nobody's proud discovery, while a
        sheltered anchorage is a fine thing to find and hurts nothing.

    """

    key: str
    x: float
    y: float
    radius: float = 0.0
    height: float = 0.0
    kind: str = ISLAND


@dataclass
class Claim:
    """
    Who was first, and when.

    Attributes:
        by (tuple): Names of those credited, the captain first.
        at (float): Game time of the claim, in seconds.
        vessel (str): The ship they were aboard, for a sighting. Empty for a landing.

    Notes:
        Names rather than objects. A discovery outlives the character who made it - an
        account closed, a character deleted, a player gone for a year - and a credit that
        evaporated when somebody stopped playing would be no credit at all. It is also what
        keeps the ledger a flat, cheap thing to store rather than a web of references.

    """

    by: tuple = ()
    at: float = 0.0
    vessel: str = ""

    def as_dict(self):
        """
        Returns:
            record (dict): Plain data, for storing on an attribute.

        """
        return {"by": list(self.by), "at": self.at, "vessel": self.vessel}

    @classmethod
    def from_dict(cls, record):
        """
        Args:
            record (dict): What `as_dict` produced.

        Returns:
            claim (Claim or None): The claim, or None for anything unreadable.

        Notes:
            Tested against `Mapping` rather than `dict`, which is not pedantry. Evennia
            hands a stored dictionary back as a `_SaverDict` - a `MutableMapping` that is
            *not* a `dict` subclass - so an `isinstance(record, dict)` guard rejects every
            claim the moment it has been through the database. Written, it was fine;
            read back, every discovery on the ledger reported nobody had found it.

        """
        if not isinstance(record, Mapping):
            return None
        return cls(
            by=tuple(record.get("by") or ()),
            at=float(record.get("at") or 0.0),
            vessel=str(record.get("vessel") or ""),
        )


@dataclass
class Discovery:
    """
    Everything the ledger knows about one place.

    Attributes:
        key (str): The landmark's name.
        sighted (Claim or None): Who first raised it from seaward.
        landed (Claim or None): Who first set foot on it.

    Notes:
        Two claims rather than one, because they are genuinely different achievements and
        frequently different people. Sighting a headland through a glass at fifteen miles
        is not the same as getting a boat through the surf, and a game that credited only
        the first would make the second pointless.

    """

    key: str
    sighted: Claim = None
    landed: Claim = None

    def credit(self):
        """
        Returns:
            lines (tuple): How a place introduces itself, one line per claim. Empty for a
                place nobody has been to - which is the point of it being empty.

        """
        out = []
        if self.sighted:
            out.append(f"First sighted by {_named(self.sighted.by)}")
        if self.landed:
            out.append(f"First landing by {_named(self.landed.by)}")
        return tuple(out)


def _named(names):
    """
    Args:
        names (iterable): Who to credit, the one with the best claim first.

    Returns:
        text (str): Them, listed the way a person would say it.

    Notes:
        The captain is named first and the rest follow, because a discovery is a ship's and
        a ship has somebody answerable for her. Everybody aboard is named though - a lookout
        who raised the land is exactly the person who should be in the record, and a system
        that credited only the captain would be a system nobody crews for.

    """
    people = [str(name) for name in names if name]
    if not people:
        return "persons unknown"
    if len(people) == 1:
        return people[0]
    if len(people) == 2:
        return f"{people[0]} and {people[1]}"
    return f"{people[0]}, with {', '.join(people[1:-1])} and {people[-1]}"


def ledger():
    """
    The game's record of who found what.

    Returns:
        ledger (DiscoveryLedger): The one ledger, created on first use.

    Notes:
        Found by key rather than held in a module global, so a reload does not orphan it and
        a test can delete it and start clean. Created on demand because a game that never
        names a landmark should not carry a script it never writes to.

    """
    from evennia.utils.create import create_script
    from evennia.utils.search import search_script

    found = [
        script
        for script in search_script(LEDGER_KEY)
        if script.is_typeclass(DiscoveryLedger, exact=False)
    ]
    if found:
        return found[0]
    return create_script(DiscoveryLedger, key=LEDGER_KEY)


def sight(vessel, game_time, landmarks=None):
    """
    Claim whatever this vessel can see and nobody has claimed.

    Args:
        vessel (Vessel): The hull doing the looking.
        game_time (float): When, in seconds.
        landmarks (iterable, optional): What is out there. Asked of the world if omitted.

    Returns:
        found (tuple): The `Discovery` records made by this look. Empty on almost every
            call, which is the normal case and the reason this is cheap.

    Notes:
        **Sighted, not merely near.** Whether a place can be seen is `geographic_range` -
        the observer's height of eye against the landmark's own height - so a forty-metre
        headland is raised from far further off than a sandbank, and a lookout up the mast
        sees further than one on deck. That is the same arithmetic the lookout reports use,
        so a discovery happens exactly when somebody could have called it.

        **True position, not reckoned.** Discovery is a fact about the world and not about
        the chart: a ship that is lost still finds the island she is looking at. The
        reckoning decides where it gets *drawn*, and being wrong about that is the
        navigator's problem and a good one to have.

        Nothing at all for a world with no landmarks, and nothing for a place already
        claimed - which is almost every place, almost every tick.

    """
    here = getattr(vessel, "maritime_position", None)
    if here is None:
        return ()

    if landmarks is None:
        landmarks = _landmarks_near(vessel, here)
    if not landmarks:
        return ()

    eye = _height_of_eye(vessel)
    company = crew_of(vessel)
    if not company:
        return ()

    book = ledger()
    made = []
    for landmark in landmarks:
        if book.sighted(landmark.key):
            continue
        away = math.hypot(landmark.x - here.x, landmark.y - here.y)
        if away > geographic_range(eye, max(landmark.height, 0.0)):
            continue
        made.append(
            book.record_sighting(landmark.key, company, game_time, getattr(vessel, "key", ""))
        )
    return tuple(made)


def set_foot(character, landmark, game_time):
    """
    Claim a landing for whoever is standing on it.

    Args:
        character (Object): Who stepped ashore.
        landmark (Landmark or str): What they stepped onto.
        game_time (float): When, in seconds.

    Returns:
        made (Discovery or None): The record, or None if somebody had already landed here.

    Notes:
        A landing is one person's. A boat's crew who row ashore together arrive one at a
        time and somebody is out first, which is how it has always been reported - and
        crediting a whole boat would make the moment worth nothing to anybody in it.

    """
    key = getattr(landmark, "key", landmark)
    kind = getattr(landmark, "kind", ISLAND)
    if kind not in UNDERFOOT:
        return None
    name = getattr(character, "key", None)
    if not name:
        return None
    book = ledger()
    if book.landed(key):
        return None
    return book.record_landing(key, (name,), game_time)


def credit_for(key):
    """
    Args:
        key (str): A landmark's name.

    Returns:
        lines (tuple): How that place introduces itself. Empty where nobody has been.

    """
    found = ledger().discovery(key)
    return found.credit() if found else ()


def crew_of(vessel):
    """
    Everybody aboard who could be credited, the captain first.

    Args:
        vessel (Vessel): The hull.

    Returns:
        names (tuple): Their names.

    Notes:
        Players only. A discovery is an achievement, and an achievement shared with eleven
        hired hands who exist as a number in the manifest is not one - the ledger would fill
        with names nobody recognises and the captain's own would be lost in them.

        The captain is named first if she is aboard. A captain ashore does not discover
        anything, whatever the articles say.

    """
    names = []
    captain = getattr(vessel, "captain", None)
    for room in getattr(vessel, "ship_rooms", ()) or ():
        for thing in room.contents:
            if not _is_a_player(thing):
                continue
            if thing not in names:
                names.append(thing)
    names.sort(key=lambda person: (person is not captain, str(person.key)))
    return tuple(str(person.key) for person in names)


def _is_a_player(thing):
    """
    Args:
        thing (Object): Anything in a compartment.

    Returns:
        player (bool): Whether it is somebody a player is or has been.

    Notes:
        Having an account rather than being currently connected. A discovery made on the
        last tick before somebody's connection dropped is still theirs.

    """
    if not hasattr(thing, "account"):
        return False
    if thing.account is not None:
        return True
    return bool(getattr(thing.db, "is_player_character", False))


def _height_of_eye(vessel):
    """
    Args:
        vessel (Vessel): The hull.

    Returns:
        height (float): Where her lookout's eye is, in metres above the water.

    """
    for name in ("masthead_height", "height_of_eye", "air_draft"):
        found = getattr(vessel, name, None)
        if isinstance(found, (int, float)) and found > 0.0:
            return float(found)
    return DEFAULT_HEIGHT_OF_EYE


def _landmarks_near(vessel, here):
    """
    Args:
        vessel (Vessel): The hull.
        here (WorldPosition): Where she truly is.

    Returns:
        landmarks (tuple): What the world says is nearby, or nothing if it does not answer.

    """
    world = getattr(vessel, "map_here", None)
    world = world() if callable(world) else None
    asked = getattr(world, "landmarks_near", None)
    if asked is None:
        return ()
    return tuple(asked(here, geographic_range(_height_of_eye(vessel), 200.0)))


class DiscoveryLedger(DefaultScript):
    """
    The game's permanent record of who found what.

    Notes:
        One row per place, holding at most two claims, written once each and then read for
        ever. That shape is why this can be a single attribute rather than a table: a world
        with ten thousand named places and every one of them found is a few hundred
        kilobytes, and the realistic case is a few hundred rows.

        Read whole, mutated, written back once - never mutated in place. An attribute is
        pickled and committed on assignment, so a dictionary edited through the attribute
        would commit on every touch.

    """

    def at_script_creation(self):
        """Configure a script that does nothing but remember."""
        self.key = LEDGER_KEY
        self.desc = "Who first sighted and first landed on each named place."
        self.persistent = True
        self.interval = 0
        self.db.claims = {}

    # --- reading ------------------------------------------------------------

    def _claims(self):
        """
        Returns:
            claims (dict): The whole ledger, as stored.

        """
        return self.db.claims or {}

    def discovery(self, key):
        """
        Args:
            key (str): A landmark's name.

        Returns:
            found (Discovery or None): What is known about it.

        """
        record = self._claims().get(key)
        if not record:
            return None
        return Discovery(
            key=key,
            sighted=Claim.from_dict(record.get("sighted")),
            landed=Claim.from_dict(record.get("landed")),
        )

    def sighted(self, key):
        """
        Args:
            key (str): A landmark's name.

        Returns:
            claim (Claim or None): Who first raised it.

        """
        return Claim.from_dict(self._claims().get(key, {}).get("sighted"))

    def landed(self, key):
        """
        Args:
            key (str): A landmark's name.

        Returns:
            claim (Claim or None): Who first set foot on it.

        """
        return Claim.from_dict(self._claims().get(key, {}).get("landed"))

    def known(self):
        """
        Returns:
            keys (tuple): Every place anybody has found, in the order found.

        """
        return tuple(self._claims())

    # --- writing ------------------------------------------------------------

    def record_sighting(self, key, names, game_time, vessel=""):
        """
        Args:
            key (str): The landmark's name.
            names (iterable): Who to credit, captain first.
            game_time (float): When.
            vessel (str, optional): The ship they were aboard.

        Returns:
            made (Discovery): The record as it now stands.

        """
        return self._write(key, "sighted", Claim(tuple(names), float(game_time), str(vessel)))

    def record_landing(self, key, names, game_time):
        """
        Args:
            key (str): The landmark's name.
            names (iterable): Who to credit.
            game_time (float): When.

        Returns:
            made (Discovery): The record as it now stands.

        """
        return self._write(key, "landed", Claim(tuple(names), float(game_time)))

    def _write(self, key, which, claim):
        """
        Args:
            key (str): The landmark's name.
            which (str): `"sighted"` or `"landed"`.
            claim (Claim): What to record.

        Returns:
            made (Discovery): The record as it now stands.

        Notes:
            **First claim wins, and a second is refused rather than overwritten.** Two ships
            can raise the same island on the same tick, and without this the later one in
            the loop would quietly take the credit. It is also the guard against a bug
            somewhere upstream rewriting history every tick, which would be invisible in
            play and obvious only once somebody noticed a discovery changing hands.

            Read whole, mutated, written back once. See the class note.

        """
        claims = dict(self._claims())
        row = dict(claims.get(key) or {})
        if row.get(which):
            return self.discovery(key)
        row[which] = claim.as_dict()
        claims[key] = row
        self.db.claims = claims
        return self.discovery(key)


__all__ = (
    "ISLAND",
    "LANDMASS",
    "HEADLAND",
    "ROCK",
    "BANK",
    "ANCHORAGE",
    "LANDMARK_KINDS",
    "UNDERFOOT",
    "Landmark",
    "Claim",
    "Discovery",
    "DiscoveryLedger",
    "ledger",
    "sight",
    "set_foot",
    "credit_for",
    "crew_of",
)
