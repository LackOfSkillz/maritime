"""
Tests for fair, budgeted round-robin scheduling.

"""

from evennia.utils.test_resources import BaseEvenniaTestCase

from ..scheduler import FairQueue


class TestRegistration(BaseEvenniaTestCase):
    """Adding and removing."""

    def test_starts_empty(self):
        self.assertEqual(len(FairQueue()), 0)

    def test_accepts_initial_items(self):
        self.assertEqual(len(FairQueue(["a", "b", "c"])), 3)

    def test_add_registers(self):
        queue = FairQueue()
        self.assertTrue(queue.add("a"))
        self.assertIn("a", queue)

    def test_add_is_idempotent(self):
        queue = FairQueue(["a"])
        self.assertFalse(queue.add("a"))
        self.assertEqual(len(queue), 1)

    def test_remove_drops(self):
        queue = FairQueue(["a", "b"])
        self.assertTrue(queue.remove("a"))
        self.assertNotIn("a", queue)

    def test_removing_absent_is_not_an_error(self):
        self.assertFalse(FairQueue().remove("ghost"))

    def test_clear_empties(self):
        self.assertEqual(len(FairQueue(["a", "b"]).clear()), 0)

    def test_iterates_in_registration_order(self):
        self.assertEqual(list(FairQueue(["a", "b", "c"])), ["a", "b", "c"])

    def test_repr_reports_size_and_cursor(self):
        self.assertIn("3", repr(FairQueue(["a", "b", "c"])))


class TestRotation(BaseEvenniaTestCase):
    """The cursor advances and wraps."""

    def setUp(self):
        super().setUp()
        self.queue = FairQueue(["a", "b", "c", "d"])

    def test_first_batch_starts_at_the_beginning(self):
        self.assertEqual(self.queue.next_batch(2), ("a", "b"))

    def test_second_batch_continues(self):
        """
        The whole point. Restarting from zero would return ('a','b') again and
        'c' and 'd' would never run.

        """
        self.queue.next_batch(2)
        self.assertEqual(self.queue.next_batch(2), ("c", "d"))

    def test_wraps_around(self):
        self.queue.next_batch(3)
        self.assertEqual(self.queue.next_batch(2), ("d", "a"))

    def test_peek_does_not_advance(self):
        self.assertEqual(self.queue.peek(), "a")
        self.assertEqual(self.queue.peek(), "a")

    def test_peek_follows_the_cursor(self):
        self.queue.next_batch(2)
        self.assertEqual(self.queue.peek(), "c")

    def test_peek_on_empty_is_none(self):
        self.assertIsNone(FairQueue().peek())

    def test_empty_queue_yields_nothing(self):
        self.assertEqual(FairQueue().next_batch(5), ())

    def test_zero_limit_yields_nothing(self):
        self.assertEqual(self.queue.next_batch(0), ())

    def test_zero_limit_does_not_advance(self):
        self.queue.next_batch(0)
        self.assertEqual(self.queue.peek(), "a")

    def test_negative_limit_is_refused(self):
        with self.assertRaises(ValueError):
            self.queue.next_batch(-1)

    def test_batch_larger_than_queue_returns_each_once(self):
        """
        Processing one vessel twice in a pass while another waits would defeat
        the rotation entirely.

        """
        batch = self.queue.next_batch(100)
        self.assertEqual(len(batch), 4)
        self.assertEqual(len(set(batch)), 4)


class TestStarvationGuarantee(BaseEvenniaTestCase):
    """Nothing waits forever."""

    def test_every_item_reached_within_one_sweep(self):
        """
        The property this module exists to provide.

        Under a budget smaller than the fleet, everything must still come round.

        """
        queue = FairQueue(list(range(50)))
        seen = set()
        for _ in range(queue.passes_for_full_sweep):
            seen.update(queue.next_batch(1))
        self.assertEqual(seen, set(range(50)))

    def test_sweep_bound_matches_length(self):
        self.assertEqual(FairQueue(list(range(17))).passes_for_full_sweep, 17)

    def test_no_item_is_reached_twice_before_all_are_reached(self):
        queue = FairQueue(list(range(10)))
        order = []
        for _ in range(10):
            order.extend(queue.next_batch(1))
        self.assertEqual(len(set(order)), 10)

    def test_large_fleet_small_budget_still_completes(self):
        queue = FairQueue(list(range(1000)))
        seen = set()
        for _ in range(100):
            seen.update(queue.next_batch(10))
        self.assertEqual(len(seen), 1000)


class TestCursorSurvivesChanges(BaseEvenniaTestCase):
    """The fleet changes under the scheduler constantly."""

    def test_adding_does_not_disturb_the_rotation(self):
        queue = FairQueue(["a", "b", "c"])
        queue.next_batch(1)
        queue.add("d")
        self.assertEqual(queue.peek(), "b")

    def test_new_items_wait_their_turn(self):
        """
        A burst of arrivals must not repeatedly displace whoever was next.

        """
        queue = FairQueue(["a", "b"])
        queue.next_batch(1)
        queue.add("new")
        self.assertEqual(queue.next_batch(1), ("b",))

    def test_removing_before_the_cursor_does_not_skip(self):
        """
        Without adjusting the cursor, removing an early item shifts everything
        down and the queue silently skips whoever moved into the free slot.

        """
        queue = FairQueue(["a", "b", "c", "d"])
        queue.next_batch(2)
        self.assertEqual(queue.peek(), "c")
        queue.remove("a")
        self.assertEqual(queue.peek(), "c")

    def test_removing_after_the_cursor_does_not_disturb(self):
        queue = FairQueue(["a", "b", "c"])
        queue.next_batch(1)
        queue.remove("c")
        self.assertEqual(queue.peek(), "b")

    def test_removing_the_cursor_item_moves_on(self):
        queue = FairQueue(["a", "b", "c"])
        queue.next_batch(1)
        queue.remove("b")
        self.assertEqual(queue.peek(), "c")

    def test_removing_the_last_item_wraps_the_cursor(self):
        queue = FairQueue(["a", "b"])
        queue.next_batch(2)
        queue.remove("a")
        self.assertEqual(queue.peek(), "b")

    def test_emptying_and_refilling_is_safe(self):
        queue = FairQueue(["a", "b"])
        queue.next_batch(2)
        queue.remove("a")
        queue.remove("b")
        queue.add("c")
        self.assertEqual(queue.next_batch(1), ("c",))

    def test_churn_never_starves(self):
        """
        Under continuous joining and leaving, whatever stays registered must
        still come round.

        """
        queue = FairQueue(list(range(20)))
        stayers = set(range(20))
        seen = set()
        for step in range(40):
            seen.update(queue.next_batch(2))
            transient = f"transient-{step}"
            queue.add(transient)
            queue.remove(transient)
        self.assertTrue(stayers.issubset(seen))


class TestRewinding(BaseEvenniaTestCase):
    """
    Putting back what was taken and never looked at.

    Notes:
        `next_batch` advances over the whole batch, which is right when the whole
        batch is processed. A pass stopped early by a time budget has not
        processed its tail, and without winding back those entities would wait a
        full rotation - the exact unfairness the cursor exists to prevent.

    """

    def queue(self, count=5):
        found = FairQueue()
        for index in range(count):
            found.add(f"item {index}")
        return found

    def test_it_puts_the_cursor_back(self):
        queue = self.queue()
        queue.next_batch(5)
        queue.rewind(3)
        self.assertEqual(queue.next_batch(3), ("item 2", "item 3", "item 4"))

    def test_rewinding_nothing_moves_nothing(self):
        queue = self.queue()
        first = queue.next_batch(2)
        queue.rewind(0)
        self.assertNotEqual(queue.next_batch(2), first)

    def test_it_wraps_backwards(self):
        queue = self.queue(3)
        queue.next_batch(1)
        queue.rewind(2)
        self.assertEqual(queue.peek(), "item 2")

    def test_it_cannot_rewind_further_than_the_queue(self):
        queue = self.queue(3)
        self.assertEqual(queue.rewind(99), 3)

    def test_an_empty_queue_rewinds_nothing(self):
        self.assertEqual(FairQueue().rewind(3), 0)

    def test_a_negative_rewind_is_refused(self):
        with self.assertRaises(ValueError):
            self.queue().rewind(-1)
