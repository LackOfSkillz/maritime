"""
The one room type this world adds, and the only reason it needs one.

Named `typeclasses` rather than `rooms` because that is what it holds, and because the
discipline check draws its line there: domain code returns results and a messaging layer
speaks. A room announcing a first landing is a typeclass doing a typeclass's job, and
calling the file something else did not change what it was - it only hid it from the rule.

Everything ashore is an ordinary Evennia room except the island piers, which have a job the
contrib cannot do for them: noticing that somebody has arrived somewhere nobody had been.

**Discovery has to be recorded where the arriving happens.** `discovery.set_foot` will take
a claim from anywhere, but *something* has to call it at the moment a person steps ashore,
and the only thing that knows the moment is the room they stepped into. So the pier is a
room that says so.

**Why the pier and not the beach.** A pier is where a landing physically happens - it is the
structure built for exactly that - and it is the first thing on the island a person can be
standing on. Waiting until the track would credit the wrong moment, and would credit nobody
at all to somebody who rowed in, looked around and left.

    sighted     the ship raised it from seaward, and the whole company is credited
    landed      one person got ashore, and only the first one is

The two are independent and frequently different people, which is why a ship's company can
have sighted an island that none of them has ever set foot on.
"""

from ...discovery import ISLAND, Landmark, set_foot
from ...rooms import PortRoom


class IslandLanding(PortRoom):
    """
    A pier that notices who walks off it first.

    Notes:
        A `PortRoom` in every other respect - it holds a position, it holds berths, ships
        lie alongside it. The addition is one hook.

    """

    def at_object_creation(self):
        """Set up a pier that knows which island it belongs to."""
        super().at_object_creation()
        self.db.landmark = ""
        self.db.landmark_height = 0.0

    def at_object_receive(self, arriving, source, **kwargs):
        """
        Note anybody stepping ashore here.

        Args:
            arriving (Object): Whoever turned up.
            source (Object): Where they came from.

        Notes:
            **Only people, and only the first of them.** The ledger refuses a second claim
            on its own, so this does not have to check - but it does have to avoid claiming
            an island on behalf of a crate somebody landed, which is why it asks whether
            the arrival is somebody a player is.

            Silent when the claim is refused, which is almost always. A message every time
            anybody walked onto a pier would be noise; a message the once is an occasion.

        """
        super().at_object_receive(arriving, source, **kwargs)

        name = self.db.landmark
        if not name or not self._is_a_person(arriving):
            return

        from ... import config

        made = set_foot(
            arriving,
            Landmark(
                key=name,
                x=0.0,
                y=0.0,
                height=float(self.db.landmark_height or 0.0),
                kind=ISLAND,
            ),
            config.time_provider().now(),
        )
        if made is None:
            return

        arriving.msg(
            f"|yNobody has ever set foot on {name} before. It will be remembered "
            "that you were the first.|n"
        )
        self.msg_contents(
            f"{arriving.key} is the first person ever to set foot on {name}.",
            exclude=arriving,
        )

    @staticmethod
    def _is_a_person(thing):
        """
        Args:
            thing (Object): Whatever arrived.

        Returns:
            person (bool): Whether it is somebody rather than something.

        Notes:
            An island claimed by a barrel rolled ashore would be a bug that is very funny
            once and then permanent, because a claim is never given back.

        """
        return getattr(thing, "account", None) is not None or bool(
            getattr(thing.db, "is_player_character", False)
        )


__all__ = ("IslandLanding",)
