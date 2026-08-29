"""
Compartments aboard a vessel.

A ship's room is an ordinary Evennia room that holds no position of its own. It names its
vessel, and the world-position resolver walks through to whatever the hull reports - which
is why moving a ship moves her whole company at once and a hundred passengers cost no more
than one.

Split out of `typeclasses.py` because a compartment is not a vessel, and because this is
where deck plans, stations, flooding order and compartment damage all land. `ShipRoom` is
still importable from `typeclasses` - see the note there.

"""

from evennia.objects.objects import DefaultRoom

from .observation import DEFAULT_HEIGHT_OF_EYE
from .vessel import EXPOSURES, INTERIOR, MAIN_DECK


class ShipRoom(DefaultRoom):
    """
    A compartment aboard a vessel.

    Holds no position of its own. It names its vessel, and the world-position
    resolver walks through to whatever the hull reports - which is why a hundred
    people aboard cost nothing extra to move.

    """

    def at_object_creation(self):
        """Set up a newly created compartment."""
        super().at_object_creation()
        self.db.vessel = None
        self.db.deck_level = MAIN_DECK
        self.db.exposure = INTERIOR
        self.db.height_of_eye = DEFAULT_HEIGHT_OF_EYE

    @property
    def maritime_position_source(self):
        """
        The vessel this compartment belongs to.

        Returns:
            vessel (Vessel or None): The hull, which is what actually has a
                position.

        Notes:
            This is the hook the resolver follows. A ship's room is not contained
            by the hull in Evennia's sense, so ordinary location would never lead
            here.

        """
        return self.db.vessel

    @property
    def height_of_eye(self):
        """
        How high an observer standing here has their eye.

        Returns:
            height (float): Metres above the waterline.

        Notes:
            Set per compartment rather than derived from deck level, because the
            thing that makes a masthead worth manning is that it is nothing like
            a deck height above the water. A crosstree thirty metres up sees more
            than three times as far as a man on deck, and no formula over deck
            numbers would produce that.

        """
        height = self.db.height_of_eye
        return DEFAULT_HEIGHT_OF_EYE if height is None else float(height)

    @height_of_eye.setter
    def height_of_eye(self, metres):
        """
        Args:
            metres (float): Height above the waterline.

        """
        self.db.height_of_eye = float(metres)

    @property
    def deck_level(self):
        """
        Which deck this compartment is on.

        Returns:
            level (int): Relative to the main deck. Negative is below.

        """
        level = self.db.deck_level
        return MAIN_DECK if level is None else level

    @deck_level.setter
    def deck_level(self, level):
        """
        Args:
            level (int): The new deck level.

        """
        self.db.deck_level = int(level)

    @property
    def exposure(self):
        """
        How sheltered this compartment is.

        Returns:
            exposure (str): One of the exposure levels.

        """
        return self.db.exposure or INTERIOR

    @exposure.setter
    def exposure(self, exposure):
        """
        Args:
            exposure (str): One of the known exposure levels.

        Raises:
            ValueError: If the value is not a known exposure. An unknown value
                would silently exclude the room from weather and flooding, which
                looks like those systems failing rather than a bad setting.

        """
        if exposure not in EXPOSURES:
            raise ValueError(f"Exposure must be one of {EXPOSURES}, got {exposure!r}.")
        self.db.exposure = exposure

    def __repr__(self):
        return f"<ShipRoom {self.key} deck {self.deck_level}>"
