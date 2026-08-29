"""
Tests for domain events and the event bus.

"""

from dataclasses import FrozenInstanceError, dataclass

from evennia.utils.test_resources import BaseEvenniaTestCase

from ..events import Delivery, Event, EventBus


@dataclass(frozen=True, kw_only=True)
class VesselEvent(Event):
    """An intermediate type, used to test subtype delivery."""

    vessel_id: str = "test-vessel"


@dataclass(frozen=True, kw_only=True)
class HullBreached(VesselEvent):
    """A concrete event standing in for a real one."""

    section: str = "bow"
    area: float = 0.0


@dataclass(frozen=True, kw_only=True)
class WeaponFired(VesselEvent):
    """A second concrete event, for testing that types stay separate."""


class TestEvent(BaseEvenniaTestCase):
    """The base event type."""

    def test_requires_a_game_time(self):
        """
        An untimed event cannot be ordered against another.

        Ordering is the one thing a log of events has to support, so the
        timestamp is required rather than defaulted.

        """
        with self.assertRaises(TypeError):
            Event()

    def test_carries_its_game_time(self):
        self.assertEqual(Event(game_time=1234.5).game_time, 1234.5)

    def test_is_immutable(self):
        """An event is a statement about the past; a handler must not rewrite it."""
        event = Event(game_time=1.0)
        with self.assertRaises(FrozenInstanceError):
            event.game_time = 2.0

    def test_subclass_carries_its_own_fields(self):
        event = HullBreached(game_time=5.0, vessel_id="gull", section="stern", area=0.4)
        self.assertEqual((event.vessel_id, event.section, event.area), ("gull", "stern", 0.4))

    def test_equality_is_by_value(self):
        self.assertEqual(Event(game_time=1.0), Event(game_time=1.0))
        self.assertNotEqual(Event(game_time=1.0), Event(game_time=2.0))


class TestSubscribe(BaseEvenniaTestCase):
    """Registering handlers."""

    def setUp(self):
        super().setUp()
        self.bus = EventBus()
        self.seen = []

    def test_handler_receives_published_event(self):
        self.bus.subscribe(HullBreached, self.seen.append)
        event = HullBreached(game_time=1.0)
        self.bus.publish(event)
        self.assertEqual(self.seen, [event])

    def test_handler_not_called_for_other_types(self):
        self.bus.subscribe(HullBreached, self.seen.append)
        self.bus.publish(WeaponFired(game_time=1.0))
        self.assertEqual(self.seen, [])

    def test_base_type_receives_subtypes(self):
        """Subscribing to Event sees everything - what a logger wants."""
        self.bus.subscribe(Event, self.seen.append)
        self.bus.publish(HullBreached(game_time=1.0))
        self.assertEqual(len(self.seen), 1)

    def test_intermediate_type_receives_subtypes(self):
        self.bus.subscribe(VesselEvent, self.seen.append)
        self.bus.publish(HullBreached(game_time=1.0))
        self.assertEqual(len(self.seen), 1)

    def test_subtype_handler_does_not_receive_base(self):
        """Delivery walks up the hierarchy, never down."""
        self.bus.subscribe(HullBreached, self.seen.append)
        self.bus.publish(VesselEvent(game_time=1.0))
        self.assertEqual(self.seen, [])

    def test_multiple_handlers_all_run(self):
        self.bus.subscribe(HullBreached, self.seen.append)
        self.bus.subscribe(HullBreached, self.seen.append)
        self.bus.publish(HullBreached(game_time=1.0))
        self.assertEqual(len(self.seen), 2)

    def test_handlers_run_in_subscription_order(self):
        self.bus.subscribe(HullBreached, lambda _: self.seen.append("first"))
        self.bus.subscribe(HullBreached, lambda _: self.seen.append("second"))
        self.bus.publish(HullBreached(game_time=1.0))
        self.assertEqual(self.seen, ["first", "second"])

    def test_specific_handlers_run_before_catch_all(self):
        self.bus.subscribe(Event, lambda _: self.seen.append("catch-all"))
        self.bus.subscribe(HullBreached, lambda _: self.seen.append("specific"))
        self.bus.publish(HullBreached(game_time=1.0))
        self.assertEqual(self.seen, ["specific", "catch-all"])

    def test_non_event_type_is_refused(self):
        with self.assertRaises(TypeError):
            self.bus.subscribe(str, self.seen.append)

    def test_non_callable_handler_is_refused(self):
        """Otherwise this fails at publish time, far from the offending line."""
        with self.assertRaises(TypeError):
            self.bus.subscribe(HullBreached, "not callable")


class TestUnsubscribe(BaseEvenniaTestCase):
    """Removing handlers."""

    def setUp(self):
        super().setUp()
        self.bus = EventBus()
        self.seen = []

    def test_unsubscribe_stops_delivery(self):
        cancel = self.bus.subscribe(HullBreached, self.seen.append)
        cancel()
        self.bus.publish(HullBreached(game_time=1.0))
        self.assertEqual(self.seen, [])

    def test_unsubscribe_leaves_other_handlers(self):
        cancel = self.bus.subscribe(HullBreached, lambda _: self.seen.append("gone"))
        self.bus.subscribe(HullBreached, lambda _: self.seen.append("kept"))
        cancel()
        self.bus.publish(HullBreached(game_time=1.0))
        self.assertEqual(self.seen, ["kept"])

    def test_unsubscribe_twice_is_harmless(self):
        cancel = self.bus.subscribe(HullBreached, self.seen.append)
        cancel()
        cancel()
        self.assertEqual(self.bus.subscriber_count(), 0)

    def test_clear_removes_everything(self):
        self.bus.subscribe(HullBreached, self.seen.append)
        self.bus.subscribe(Event, self.seen.append)
        self.bus.clear()
        self.assertEqual(self.bus.subscriber_count(), 0)

    def test_clear_returns_the_bus(self):
        self.assertIs(self.bus.clear(), self.bus)


class TestPublish(BaseEvenniaTestCase):
    """Delivery reporting and failure isolation."""

    def setUp(self):
        super().setUp()
        self.bus = EventBus()
        self.seen = []

    def test_reports_delivery_counts(self):
        self.bus.subscribe(HullBreached, self.seen.append)
        self.bus.subscribe(HullBreached, self.seen.append)
        self.assertEqual(self.bus.publish(HullBreached(game_time=1.0)), Delivery(2, 0))

    def test_publish_with_no_subscribers_is_fine(self):
        self.assertEqual(self.bus.publish(HullBreached(game_time=1.0)), Delivery(0, 0))

    def test_failing_handler_does_not_stop_the_others(self):
        """
        A buggy subscriber must not be able to halt the simulation.

        A quest script with a mistake in it cannot be allowed to stop a vessel
        from sinking.

        """

        def explode(_event):
            raise RuntimeError("subscriber bug")

        self.bus.subscribe(HullBreached, explode)
        self.bus.subscribe(HullBreached, self.seen.append)
        result = self.bus.publish(HullBreached(game_time=1.0))
        self.assertEqual(len(self.seen), 1)
        self.assertEqual(result, Delivery(1, 1))

    def test_failure_does_not_propagate_to_the_publisher(self):
        def explode(_event):
            raise RuntimeError("subscriber bug")

        self.bus.subscribe(HullBreached, explode)
        self.bus.publish(HullBreached(game_time=1.0))  # must not raise

    def test_handler_subscribed_during_publish_misses_the_current_event(self):
        """
        Delivery iterates a snapshot, not the live handler list.

        A handler registered in response to an event must not also receive that
        same event - it subscribed after the fact. Iterating the live list would
        deliver to it anyway, and appending mid-iteration does not raise in
        CPython, so nothing would flag it.

        """

        def add_another(_event):
            self.bus.subscribe(HullBreached, lambda _: self.seen.append("late"))

        self.bus.subscribe(HullBreached, add_another)
        self.bus.publish(HullBreached(game_time=1.0))
        self.assertEqual(self.seen, [], "a handler added mid-publish received the event")

    def test_late_subscriber_receives_the_next_event(self):
        """It missed the event it was created during, not every event after."""

        def add_another(_event):
            self.bus.subscribe(HullBreached, lambda _: self.seen.append("late"))

        cancel = self.bus.subscribe(HullBreached, add_another)
        self.bus.publish(HullBreached(game_time=1.0))
        cancel()
        self.bus.publish(HullBreached(game_time=2.0))
        self.assertEqual(self.seen, ["late"])

    def test_handler_unsubscribing_during_publish_does_not_skip_others(self):
        """
        Removing from the live list mid-iteration would shift the remaining
        handlers down and silently skip one.

        """
        cancels = []

        def remove_self(_event):
            cancels[0]()

        cancels.append(self.bus.subscribe(HullBreached, remove_self))
        self.bus.subscribe(HullBreached, lambda _: self.seen.append("kept"))
        self.bus.publish(HullBreached(game_time=1.0))
        self.assertEqual(self.seen, ["kept"])

    def test_publishing_a_non_event_is_refused(self):
        with self.assertRaises(TypeError):
            self.bus.publish("not an event")


class TestSubscriberCount(BaseEvenniaTestCase):
    """Introspection."""

    def setUp(self):
        super().setUp()
        self.bus = EventBus()

    def test_starts_empty(self):
        self.assertEqual(self.bus.subscriber_count(), 0)

    def test_counts_all_handlers(self):
        self.bus.subscribe(HullBreached, lambda _: None)
        self.bus.subscribe(WeaponFired, lambda _: None)
        self.assertEqual(self.bus.subscriber_count(), 2)

    def test_counts_one_type(self):
        self.bus.subscribe(HullBreached, lambda _: None)
        self.bus.subscribe(WeaponFired, lambda _: None)
        self.assertEqual(self.bus.subscriber_count(HullBreached), 1)

    def test_counts_exact_registrations_not_reach(self):
        """
        Counting exact registrations, not what an event would reach.

        Two different questions; conflating them would make this useless for
        checking that an unsubscribe took effect.

        """
        self.bus.subscribe(Event, lambda _: None)
        self.assertEqual(self.bus.subscriber_count(HullBreached), 0)


class TestBusIsolation(BaseEvenniaTestCase):
    """Buses do not share state."""

    def test_separate_buses_do_not_share_subscribers(self):
        first, second = EventBus(), EventBus()
        seen = []
        first.subscribe(HullBreached, seen.append)
        second.publish(HullBreached(game_time=1.0))
        self.assertEqual(seen, [])
