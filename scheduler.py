"""
Fair, budgeted round-robin scheduling.

Evennia runs on a single reactor thread. Anything slow blocks the entire game, and the
symptom is not sluggishness - it is commands queueing silently and then arriving all at
once. So maritime background work is never "process the whole fleet every minute". It is
"process as much as fits in the budget, then continue from where you stopped".

The cursor is the part that matters. Restarting from the beginning of the list each pass
looks fair and is not: under load the budget always runs out somewhere in the middle, and
everything past that point is never reached at all. Those vessels simply stop advancing,
which presents as a physics bug rather than a scheduling one and is miserable to trace.

    Round-robin, cursor kept:     every vessel reached within one full sweep
    Restart from zero each pass:  the tail silently starves

Hence the starvation guarantee this module exists to provide: with a budget of at least
one item per pass, every registered item is reached within `len(queue)` passes, no matter
how the queue changes underneath.

"""


class FairQueue:
    """
    A round-robin queue that remembers where it left off.

    Not a priority queue - everything here is equal, and the only question is who
    has waited longest. Items may be added and removed at any time without
    disturbing the rotation for anyone else.

    """

    def __init__(self, items=()):
        """
        Args:
            items (iterable, optional): Initial items, in order.

        """
        self._order = []
        self._cursor = 0
        for item in items:
            self.add(item)

    def add(self, item):
        """
        Register an item, if it is not already present.

        Args:
            item (any): The item to schedule. Must be hashable and comparable by
                identity or equality.

        Returns:
            added (bool): True if it was newly added.

        Notes:
            Appends rather than inserting at the cursor. A newly registered vessel
            waits its turn like everything else, which keeps a burst of new
            arrivals from repeatedly displacing whoever was next.

        """
        if item in self._order:
            return False
        self._order.append(item)
        return True

    def remove(self, item):
        """
        Unregister an item.

        Args:
            item (any): The item to drop.

        Returns:
            removed (bool): True if it had been present.

        Notes:
            Adjusts the cursor when the removed item sat before it. Without that,
            removing an early item shifts everything down by one and the queue
            silently skips whoever moved into the vacated slot.

        """
        try:
            index = self._order.index(item)
        except ValueError:
            return False
        self._order.pop(index)
        if index < self._cursor:
            self._cursor -= 1
        if self._cursor >= len(self._order):
            self._cursor = 0
        return True

    def next_batch(self, limit):
        """
        Take the next items in rotation, advancing the cursor past them.

        Args:
            limit (int): How many to take. Fewer are returned if the queue is
                smaller.

        Returns:
            batch (tuple): The items to process now, in rotation order.

        Raises:
            ValueError: If `limit` is negative.

        Notes:
            Never returns the same item twice in one batch, even when `limit`
            exceeds the queue length. Processing a vessel twice in one pass while
            another waits would defeat the point of the rotation.

        """
        if limit < 0:
            raise ValueError(f"Batch limit cannot be negative, got {limit!r}.")
        if not self._order or limit == 0:
            return ()

        count = min(limit, len(self._order))
        batch = []
        for offset in range(count):
            batch.append(self._order[(self._cursor + offset) % len(self._order)])
        self._cursor = (self._cursor + count) % len(self._order)
        return tuple(batch)

    def rewind(self, count):
        """
        Put back items that were taken but never looked at.

        Args:
            count (int): How many to return to the front of the rotation.

        Returns:
            returned (int): How many were actually put back.

        Raises:
            ValueError: If `count` is negative.

        Notes:
            `next_batch` advances the cursor over the whole batch, which is right
            when the whole batch gets processed and wrong the moment something
            stops the loop early. Without this, a pass that ran out of time would
            skip its untouched tail entirely and those entities would wait a full
            rotation for another turn - which is precisely the unfairness the
            cursor exists to prevent.

        """
        if count < 0:
            raise ValueError(f"Rewind count cannot be negative, got {count!r}.")
        if not self._order or count == 0:
            return 0
        count = min(count, len(self._order))
        self._cursor = (self._cursor - count) % len(self._order)
        return count

    def peek(self):
        """
        The item that would come next, without advancing.

        Returns:
            item (any or None): The next item, or None if the queue is empty.

        """
        if not self._order:
            return None
        return self._order[self._cursor]

    def clear(self):
        """
        Drop everything and reset the cursor.

        Returns:
            queue (FairQueue): This queue, for chaining.

        """
        self._order.clear()
        self._cursor = 0
        return self

    @property
    def passes_for_full_sweep(self):
        """
        Passes needed to reach every item, at one item per pass.

        Returns:
            passes (int): Equal to the queue length.

        Notes:
            The starvation bound. At a batch size of `n` the figure is
            `ceil(len / n)`; this reports the worst case, which is what a
            scheduling interval has to be checked against.

        """
        return len(self._order)

    def __len__(self):
        return len(self._order)

    def __contains__(self, item):
        return item in self._order

    def __iter__(self):
        """Iterate in registration order, not rotation order, and without advancing."""
        return iter(tuple(self._order))

    def __repr__(self):
        return f"FairQueue({len(self._order)} items, cursor at {self._cursor})"
