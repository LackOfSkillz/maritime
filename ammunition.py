"""
What a gun is loaded with, and therefore what her captain means to do.

This is the best idea in naval gunnery and the whole reason the damage tracks were worth
building. Choosing shot is not choosing a damage number - it is **declaring an intent**:

    ball     for the hull        I intend to sink you
    chain    for the rigging     I intend to catch you
    grape    for the people      I intend to board you

Three answers to one question, none of them strictly better, and a captain has to decide
before he knows how the fight will go. That is a decision rather than an optimisation, and
it is what makes the difference between a pirate and a privateer legible in what they load.

**Range is the constraint that makes it a real choice.** Ball carries; chain tumbles and
loses its way sooner; grape is a knife-range weapon and useless beyond it. So the shot a
captain wants is often the shot he cannot yet use, and closing to grape range means taking
his enemy's ball the whole way in.

**Nothing here decides how much a hit hurts.** That is `damage`, and it has one dial. These
are multipliers on it, chosen so that no shot is simply the strongest - grape hits people
hardest because people are soft, and would be a poor way to open a plank.

"""

from dataclasses import dataclass

from .damage import HULL, RIGGING

#: The crew are not a damage track - casualties are people, and they live in `crew`. This
#: is the marker that says "send this to the company rather than to a track", and keeping
#: it distinct is what stops shot at the crew quietly becoming shot at the hull.
CREW = "crew"


@dataclass(frozen=True)
class Shot:
    """
    A kind of ammunition.

    Attributes:
        key (str): Identifier.
        name (str): What a gunner calls it.
        aimed_at (str): The damage track it tells on, or `CREW` for the people.
        weight (float): Multiplier on the weapon's damage.
        reach (float): Fraction of the weapon's range at which it is any use.
        accuracy (float): Multiplier on the weapon's accuracy.

    Notes:
        A shot is a set of trade-offs rather than a tier. Each is the best answer to a
        different question, and a game that adds its own - heated shot, langrage, a
        stone from a trebuchet - describes it in exactly these terms.

    """

    key: str
    name: str
    aimed_at: str
    weight: float = 1.0
    reach: float = 1.0
    accuracy: float = 1.0


#: Round shot: solid, heavy, and the only thing that opens a hull. It carries as far as the
#: gun will throw it, which is what makes it the shot you fight at long range whether or not
#: it is the shot you wanted.
BALL = Shot("ball", "round shot", HULL, weight=1.0, reach=1.0, accuracy=1.0)

#: Chain: two balls on a length of chain, tumbling. It cuts rigging and brings spars down,
#: and it is how you catch a ship rather than how you sink one - which is precisely why a
#: pirate loads it. Tumbling costs it range and accuracy both.
CHAIN = Shot("chain", "chain shot", RIGGING, weight=0.9, reach=0.5, accuracy=0.8)

#: Grape: a bag of small shot that opens into a cone. Murderous against people on an open
#: deck, useless against timber, and a knife-range weapon - closing to grape range means
#: taking his ball the whole way in.
GRAPE = Shot("grape", "grape shot", CREW, weight=1.3, reach=0.25, accuracy=1.2)

SHOT_TYPES = (BALL, CHAIN, GRAPE)

#: What a gun holds when nobody has said. Ball, because it is the shot that works at any
#: range - a battery loaded with grape and an enemy two miles off is a battery loaded with
#: nothing, and that is a worse default than being merely unimaginative.
DEFAULT_SHOT = BALL


def shot_named(key):
    """
    Args:
        key (str): What was asked for.

    Returns:
        shot (Shot or None): The ammunition, if it is a kind anybody carries.

    """
    wanted = (key or "").strip().lower()
    if not wanted:
        # An empty string is a prefix of everything, so without this the first kind
        # carried would match and a caller asking for nothing would be handed ball.
        return None
    for shot in SHOT_TYPES:
        if shot.key == wanted or shot.name.lower().startswith(wanted):
            return shot
    return None


def carries(shot, weapon):
    """
    How far this shot is any use from this gun.

    Args:
        shot (Shot): What is loaded.
        weapon (WeaponType): What it is loaded into.

    Returns:
        metres (float): The furthest it is worth firing.

    """
    return weapon.max_range * shot.reach


def in_range(shot, weapon, distance):
    """
    Args:
        shot (Shot): What is loaded.
        weapon (WeaponType): What it is loaded into.
        distance (float): Range to the target, in metres.

    Returns:
        worth_it (bool): True if the shot will reach.

    Notes:
        Separate from the weapon's own range on purpose. A gun that can throw a ball
        two thousand yards throws grape a few hundred, and a captain who has loaded
        grape has shortened his own reach for the afternoon - which is the cost of
        having decided early.

    """
    return distance <= carries(shot, weapon)


def told_by(shot, damage):
    """
    What a hit with this shot is worth.

    Args:
        shot (Shot): What was fired.
        damage (float): What the weapon does when it connects.

    Returns:
        weight (float): What this shot delivers.

    """
    return max(0.0, damage) * shot.weight
