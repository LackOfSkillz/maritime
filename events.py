"""
Domain events and the bus that delivers them.

Events are how the simulation announces that something happened without knowing, or
caring, who is listening. Messaging renders them into prose, AI reacts to them, quests
and economies watch for them, logging records them, tests assert on them - and the code
that raised the event knows about none of that.

This is the counterpart to `results`. A result is what an operation *returns* to its
caller; an event is what it *broadcasts* to everyone else.

    ```python
    @dataclass(frozen=True, kw_only=True)
    class HullBreached(Event):
        vessel_id: str
        section: str
        area: float

    bus.subscribe(HullBreached, renderer.describe_breach)
    bus.publish(HullBreached(game_time=clock.now(), vessel_id="a", section="bow", area=0.4))
    ```

Concrete event types live with the systems that raise them, not here. This module is
the spine: the base type, and delivery.

"""

from collections import namedtuple
from dataclasses import dataclass

from evennia.utils import logger

# What a publish actually achieved. Reported rather than discarded so a caller - and a
# test - can tell "nobody was listening" from "three listeners ran" from "one blew up".
Delivery = namedtuple("Delivery", ("delivered", "failed"))


@dataclass(frozen=True, kw_only=True)
class Event:
    """
    Something that happened in the simulation.

    Frozen, because an event is a statement about the past. A subscriber that could
    edit one would be rewriting history for every subscriber after it in the chain.

    Attributes:
        game_time (float): When this happened, in game seconds, from the run's
            time provider. Required rather than defaulted: an untimed event cannot
            be ordered against another, which is the one thing a log of events must
            support.

    """

    game_time: float


class EventBus:
    """
    Delivers events to whoever subscribed to them.

    Not a global. The simulation owns an instance and hands it to the pieces that
    need it, so a test can use a fresh bus and never see another test's subscribers.

    """

    def __init__(self):
        self._handlers = {}

    def subscribe(self, event_type, handler):
        """
        Register a handler for an event type and its subtypes.

        Args:
            event_type (type): An `Event` subclass. Subscribing to a base type also
                receives its subtypes, so subscribing to `Event` sees everything -
                which is what a logger or an analytics sink usually wants.
            handler (callable): Called with the event as its only argument.

        Returns:
            unsubscribe (callable): Call it to remove this handler. Taking no
                arguments makes it safe to store and call later without needing to
                remember what was registered.

        Raises:
            TypeError: If `event_type` is not an `Event` subclass, or `handler` is
                not callable. Both mistakes would otherwise fail silently at publish
                time, long after the line that caused them.

        """
        if not (isinstance(event_type, type) and issubclass(event_type, Event)):
            raise TypeError("Can only subscribe to an Event subclass.")
        if not callable(handler):
            raise TypeError("An event handler must be callable.")

        self._handlers.setdefault(event_type, []).append(handler)

        def unsubscribe():
            handlers = self._handlers.get(event_type, [])
            if handler in handlers:
                handlers.remove(handler)

        return unsubscribe

    def publish(self, event):
        """
        Deliver an event to every matching handler.

        Handlers run in subscription order, most-derived event type first, so a
        specific handler sees an event before a catch-all logger does.

        Args:
            event (Event): The event to deliver.

        Returns:
            delivery (Delivery): Counts of handlers that ran and handlers that
                raised.

        Raises:
            TypeError: If `event` is not an `Event`.

        Notes:
            A handler that raises is logged and skipped; it does not prevent the
            remaining handlers from running, and it never propagates back to the
            code that raised the event. A quest script with a bug must not be able
            to stop a vessel from sinking.

        """
        if not isinstance(event, Event):
            raise TypeError("Can only publish an Event.")

        delivered = failed = 0
        for event_type in type(event).__mro__:
            for handler in tuple(self._handlers.get(event_type, ())):
                try:
                    handler(event)
                    delivered += 1
                except Exception:
                    failed += 1
                    logger.log_trace(f"maritime: event handler failed for {type(event).__name__}")
        return Delivery(delivered, failed)

    def subscriber_count(self, event_type=None):
        """
        How many handlers are registered.

        Args:
            event_type (type, optional): Count only this exact type's handlers.
                When omitted, counts every handler on the bus.

        Returns:
            count (int): Number of registered handlers.

        Notes:
            Counts exact registrations, not what a given event would reach - two
            different questions, and conflating them would make this useless for
            checking that an unsubscribe actually took effect.

        """
        if event_type is not None:
            return len(self._handlers.get(event_type, ()))
        return sum(len(handlers) for handlers in self._handlers.values())

    def clear(self):
        """
        Remove every subscriber.

        Returns:
            bus (EventBus): This bus, for chaining.

        """
        self._handlers.clear()
        return self
