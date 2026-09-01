"""
The people ashore, and the smallest thing that can sell you a drink.

**This is deliberately the least shop that will do.** Maritime has no opinion about trade
between characters and should not grow one: an economy is the host game's business, and every
game that has one has a different one. What is here exists so the example world can
demonstrate the two things that *are* maritime's business - that a crew let ashore feels
better for it, and that cargo comes off a ship and goes somewhere - without pretending to be
a shop system.

A game with a real economy replaces `Vendor` with its own and loses nothing, because nothing
else in this world knows what a vendor is.

    ask <person> about <thing>     what they have and what it costs
    buy <thing> from <person>      hand over coin, get the thing

**Coin is a number on the character.** Not a currency system, not an item, not a ledger -
one attribute, because the alternative is inventing an economy in an example. A game that has
money uses its own and overrides `charge`.
"""

from evennia.objects.objects import DefaultCharacter
from evennia.utils import create

#: What a character's purse is kept under, so a game can find and replace it.
PURSE = "coin"

#: What a new character has to spend, so the example is walkable without a quest to earn it.
STARTING_COIN = 40


class Vendor(DefaultCharacter):
    """
    Somebody who stands in one place and sells a short list of things.

    Notes:
        A character rather than an object, so she can be looked at, talked to and stood
        beside like anybody else - and so a game replacing her with a real NPC has nothing
        to unpick.

        Her stock is a list of `(name, price, kind, description)`. Nothing is tracked and
        nothing runs out: an island bar does not run out of rum in a demonstration, and a
        shop that did would need restocking, which needs an economy.

    """

    def at_object_creation(self):
        """Set up somebody with a counter and a list."""
        super().at_object_creation()
        self.db.stock = []
        self.db.greeting = ""
        self.locks.add("call:false()")

    @property
    def stock(self):
        """
        Returns:
            stock (tuple): What is for sale, as `(name, price, kind, description)`.

        """
        return tuple(tuple(line) for line in (self.db.stock or ()))

    def sells(self, name):
        """
        Args:
            name (str): What somebody asked for, in any case.

        Returns:
            line (tuple or None): The stock entry, or None if she has no such thing.

        Notes:
            Matched loosely, on a leading substring, because a player who types `buy rum`
            should not have to know it is called a measure of dark rum.

        """
        wanted = (name or "").strip().lower()
        if not wanted:
            return None
        for line in self.stock:
            if line[0].lower().startswith(wanted) or wanted in line[0].lower():
                return line
        return None

    def at_object_receive(self, moved, source, **kwargs):
        """
        Args:
            moved (Object): What arrived.
            source (Object): Where from.

        Notes:
            Vendors do not accumulate. Anything handed to one is passed back, so a player
            cannot lose a sextant by giving it to a barman, and so the example does not
            quietly become an inventory sink.

        """
        super().at_object_receive(moved, source, **kwargs)
        if moved.location is self:
            moved.move_to(self.location, quiet=True, move_hooks=False)


def purse_of(character):
    """
    Args:
        character (Object): Whose purse.

    Returns:
        coin (int): What they have.

    """
    held = character.db.coin
    if held is None:
        character.db.coin = STARTING_COIN
        return STARTING_COIN
    return int(held)


def charge(character, price):
    """
    Take coin from somebody.

    Args:
        character (Object): Who is paying.
        price (int): How much.

    Returns:
        paid (bool): Whether they could afford it.

    Notes:
        The seam a game with real money overrides. Everything else here talks to this and
        nothing else talks to `db.coin`, so replacing it replaces the economy.

    """
    held = purse_of(character)
    if held < price:
        return False
    character.db.coin = held - int(price)
    return True


def make(key, description, stock, greeting, home):
    """
    Put a vendor somewhere.

    Args:
        key (str): Their name.
        description (str): What they look like.
        stock (iterable): `(name, price, kind, description)` lines.
        greeting (str): What they say when somebody arrives.
        home (Object): The room they stand in.

    Returns:
        found (tuple): `(vendor, made_now)` - the person, and whether this call created
            them rather than finding them already there.

    Notes:
        Idempotent like everything else in the builder: run twice and there is still one
        barman, because a build command that doubles its own world is a build command
        nobody dares run twice.

        **It reports whether it made anything, and that is not decoration.** Returning only
        the vendor made every caller's tally a lie: a second build correctly created nobody
        and cheerfully announced six new people, because a found vendor and a fresh one are
        both truthy. The build was right and the report was wrong, which is the harder of
        the two to notice - a diagnostic nothing checks is a diagnostic that drifts.

    """
    for standing in home.contents:
        if standing.key == key and standing.is_typeclass(Vendor, exact=False):
            return (standing, False)

    vendor = create.create_object(Vendor, key=key, location=home, home=home)
    vendor.db.desc = description
    vendor.db.stock = [list(line) for line in stock]
    vendor.db.greeting = greeting
    return (vendor, True)


__all__ = ("PURSE", "STARTING_COIN", "Vendor", "purse_of", "charge", "make")
