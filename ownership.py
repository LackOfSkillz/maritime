"""
Who owns her, who commands her, and who answers to whom.

Two roles, and they are not the same thing:

    owner     property. Who she belongs to, whether or not they have ever seen the sea.
    captain   command. Who gives the orders, and who may hand them to somebody else.

**Keeping them apart is the whole point.** A merchant who owns four ships is aboard at
most one of them; the other three are commanded by people who own nothing. Collapsing the
two into a single "controller" field produces an owner who must be present to sail her and
a captain who cannot be dismissed, and neither is a ship.

**A captain can pass command.** That is what makes the role a role rather than a label -
he can hand her to his mate for the night watch, or to a prize crew, and take her back.

**Hold more than one ship and you are an admiral.** Not a rank anybody grants: a derived
fact about how many decks answer to you, so it arrives the moment a second ship does and
leaves the moment one is lost or sold. What an admiral may *do* with a fleet - signal it,
order it, fight it as a unit - is not decided here.

**Who may command is one function, replaceable whole.** The default is deliberately small:
the captain, or the owner if nobody has been appointed, or anybody at all aboard a ship
that belongs to nobody. A game wanting per-capability authority - the mate may steer but
not fire, the purser may neither - points `MARITIME_COMMAND_POLICY` at its own function and
this one is never called again. That seam matters more than the default does.

**An unowned ship answers to anybody aboard her.** Not an oversight. A game that has not
adopted ownership at all must still be able to sail, and a boat drawn up on a beach with
nobody's name on her is anybody's to work.

"""

from dataclasses import dataclass

from .events import Event, bus

# Why a ship changed hands. Recorded on the event, because "sold" and "taken by
# force" are the same transfer and completely different stories, and a game
# listening will want to tell them apart.
SOLD = "sold"
GRANTED = "granted"
CAPTURED = "captured"
INHERITED = "inherited"
TRANSFER_REASONS = (SOLD, GRANTED, CAPTURED, INHERITED)

# What somebody is, given how many decks answer to them. Derived, never assigned.
UNRANKED = "unranked"
CAPTAIN = "captain"
ADMIRAL = "admiral"

# How many ships it takes to be an admiral. Two, because the word means somebody
# who commands ships rather than a ship - and a game that disagrees can say so.
ADMIRAL_THRESHOLD = 2


@dataclass(frozen=True, kw_only=True)
class OwnershipTransferred(Event):
    """
    A ship changed hands.

    Attributes:
        vessel (object): The hull.
        former_owner (object or None): Who held her, if anybody.
        owner (object or None): Who holds her now.
        reason (str): One of `TRANSFER_REASONS`.

    Notes:
        Carries both ends, because a listener almost always needs the one that is
        no longer there - a fleet roster to update, a debt to settle, somebody to
        tell.

    """

    vessel: object
    former_owner: object = None
    owner: object = None
    reason: str = GRANTED


@dataclass(frozen=True, kw_only=True)
class CommandPassed(Event):
    """
    A ship has a new captain.

    Attributes:
        vessel (object): The hull.
        former_captain (object or None): Who had her.
        captain (object or None): Who has her now.

    """

    vessel: object
    former_captain: object = None
    captain: object = None


def fleet_of(character):
    """
    Every ship a character owns.

    Args:
        character (Object): Whose ships to list.

    Returns:
        fleet (tuple): The vessels, in the order they were acquired.

    Notes:
        Kept on the character as well as on the ship, and maintained by the
        setter on both sides - exactly as a compartment names its hull and the
        hull keeps its list. The alternative is querying every vessel in the
        world by an attribute holding an object reference, which is neither
        indexed nor reliable across the several shapes such a value can be
        stored in.

        A sunk ship has to be filtered out because the roster outlives her.
        Evennia unpacks a reference to a deleted object as None - measured, on
        its own and inside a list, in the same process that deleted it - so None
        is the whole of what a dead reference looks like and there is nothing
        further to check for.

    """
    if character is None:
        return ()
    return tuple(vessel for vessel in (character.db.maritime_fleet or ()) if vessel is not None)


def is_admiral(character, threshold=ADMIRAL_THRESHOLD):
    """
    Whether enough decks answer to somebody to call them one.

    Args:
        character (Object): Who to ask about.
        threshold (int, optional): How many ships it takes.

    Returns:
        admiral (bool): True if they hold at least that many.

    """
    return len(fleet_of(character)) >= threshold


def rank_of(character, threshold=ADMIRAL_THRESHOLD):
    """
    What to call somebody, given what answers to them.

    Args:
        character (Object): Who to ask about.
        threshold (int, optional): How many ships makes an admiral.

    Returns:
        rank (str): `ADMIRAL`, `CAPTAIN` or `UNRANKED`.

    Notes:
        Derived on every call rather than stored. A stored rank is a fact that
        can disagree with the world, and this one changes every time a ship is
        bought, sold, taken or sunk - which is exactly the sort of thing nobody
        remembers to keep in step.

        Owning ships and commanding one are different routes to being called
        something. A man with no ship of his own who has been given command of
        somebody else's is a captain, and rightly.

    """
    if is_admiral(character, threshold):
        return ADMIRAL
    if fleet_of(character) or (character is not None and character.db.maritime_command):
        return CAPTAIN
    return UNRANKED


def may_command(character, vessel):
    """
    Whether this person may give this ship orders.

    Args:
        character (Object): Who is trying.
        vessel (Vessel): The hull.

    Returns:
        permitted (bool): True if the orders should be obeyed.

    Notes:
        The default policy, and deliberately a small one. Her captain may command
        her; so may her owner when no captain has been appointed; and a ship
        nobody owns answers to anybody aboard her.

        That last case is not an oversight. A game that has not adopted ownership
        must still be able to sail, and every example and test in this contrib
        builds ships that belong to nobody.

        A game wanting more - the mate may steer but not fire, a passenger may do
        neither - replaces this wholesale through `MARITIME_COMMAND_POLICY` rather
        than extending it. Authority is the kind of rule that grows teeth, and one
        function a game owns entirely is a better seam than a chain of hooks.

    """
    if vessel is None:
        return False

    captain = vessel.captain
    if captain is not None:
        return character is captain

    owner = vessel.owner
    if owner is not None:
        return character is owner

    return True


class Owned:
    """
    The Evennia-side face of this module.

    Notes:
        Holds two references and maintains the other half of each. Everything
        interesting - who may do what, what a fleet entitles you to, what a
        capture is worth - is either a policy a game replaces or a question this
        deliberately does not answer.

    """

    def at_object_creation(self):
        """Set up this part of a newly created vessel."""
        super().at_object_creation()
        self.db.owner = None
        self.db.captain = None

    # --- property -----------------------------------------------------------

    @property
    def owner(self):
        """
        Returns:
            owner (Object or None): Who she belongs to.

        """
        return self.db.owner

    @owner.setter
    def owner(self, character):
        """
        Args:
            character (Object or None): The new owner, or None to disown her.

        Notes:
            Maintains the fleet on both sides and publishes the transfer. Use
            `transfer_ownership` to say *why* she changed hands; this is the bare
            assignment, and it reports `GRANTED`.

        """
        self.transfer_ownership(character, reason=GRANTED)

    def transfer_ownership(self, character, reason=GRANTED):
        """
        Hand her to somebody, and say why.

        Args:
            character (Object or None): The new owner, or None.
            reason (str): One of `TRANSFER_REASONS`.

        Returns:
            transferred (bool): True if she actually changed hands.

        Raises:
            ValueError: If the reason is not one anybody records.

        Notes:
            No money changes hands here, and none ever will. What a ship is worth
            and who can afford her is the host game's economy, and a contrib that
            shipped a price would be arguing with it - see `DECISIONS.md`. This
            moves the property and announces it; a game wires its own purchase to
            the event.

        """
        if reason not in TRANSFER_REASONS:
            raise ValueError(f"Unknown transfer reason {reason!r}; expected {TRANSFER_REASONS}.")

        former = self.owner
        if former is character:
            return False

        if former is not None:
            _leave_fleet(former, self)
        self.db.owner = character
        if character is not None:
            _join_fleet(character, self)

        bus().publish(
            OwnershipTransferred(
                game_time=_now(),
                vessel=self,
                former_owner=former,
                owner=character,
                reason=reason,
            )
        )
        return True

    # --- command ------------------------------------------------------------

    @property
    def captain(self):
        """
        Returns:
            captain (Object or None): Who commands her.

        """
        return self.db.captain

    @captain.setter
    def captain(self, character):
        """
        Args:
            character (Object or None): The new captain, or None to leave her
                without one.

        """
        self.pass_command(character)

    def pass_command(self, character):
        """
        Give her to somebody else to command.

        Args:
            character (Object or None): The new captain, or None to relinquish.

        Returns:
            passed (bool): True if command actually moved.

        Notes:
            What makes captain a role rather than a label. He can hand her to his
            mate for the night watch or to a prize crew, and take her back.

            One ship per captain, both ways: a character given a second ship
            gives up the first, because a man cannot be on two decks. An admiral
            with a fleet commands one of them and appoints captains to the rest,
            which is the distinction the two roles exist to draw.

        """
        former = self.captain
        if former is character:
            return False

        if former is not None:
            former.db.maritime_command = None
        if character is not None:
            previous = character.db.maritime_command
            if previous is not None and previous is not self:
                previous.db.captain = None
            character.db.maritime_command = self
        self.db.captain = character

        bus().publish(
            CommandPassed(game_time=_now(), vessel=self, former_captain=former, captain=character)
        )
        return True

    def may_be_commanded_by(self, character):
        """
        Whether this person may give her orders.

        Args:
            character (Object): Who is trying.

        Returns:
            permitted (bool): What the configured policy says.

        Notes:
            Asks the policy rather than deciding, so a game that replaced it is
            obeyed everywhere without this class knowing it happened.

        """
        from . import config

        return config.command_policy()(character, self)

    # --- the people ---------------------------------------------------------

    @property
    def owner_rank(self):
        """
        Returns:
            rank (str): What her owner is, given the rest of their fleet.

        """
        return rank_of(self.owner)

    def __repr__(self):
        owner = self.owner.key if self.owner else "nobody"
        captain = self.captain.key if self.captain else "nobody"
        return f"<{self.key}: owned by {owner}, commanded by {captain}>"


def _join_fleet(character, vessel):
    """
    Args:
        character (Object): The new owner.
        vessel (Vessel): The ship joining their fleet.

    Notes:
        Reads the list, appends and writes it back once - Law 10. Mutating the
        stored list in place would commit on every touch.

    """
    fleet = [held for held in (character.db.maritime_fleet or ()) if held is not None]
    if vessel not in fleet:
        fleet.append(vessel)
    character.db.maritime_fleet = fleet


def _leave_fleet(character, vessel):
    """
    Args:
        character (Object): The former owner.
        vessel (Vessel): The ship leaving their fleet.

    """
    fleet = [
        held
        for held in (character.db.maritime_fleet or ())
        if held is not None and held is not vessel
    ]
    character.db.maritime_fleet = fleet


def _now():
    """
    Returns:
        now (float): Game time, for stamping an event.

    Notes:
        An event without a time cannot be ordered against another, which is the
        one thing a log of events has to support - so this is fetched rather than
        defaulted even though ownership itself does not care what time it is.

    """
    from . import config

    return config.time_provider().now()
