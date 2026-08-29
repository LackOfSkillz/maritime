"""
Tests for world-position resolution.

"""

from evennia.utils.test_resources import BaseEvenniaTestCase

from ..position import WorldPosition
from ..resolver import (
    NoWorldPosition,
    NoWorldPositionType,
    get_world_position,
    has_world_position,
    resolve_chain,
)


class Thing:
    """
    A stand-in for anything that might be somewhere.

    Vessels and ship rooms do not exist yet, so these model the shapes the
    resolver has to handle: something that knows where it is, something that
    names another entity to ask, and something that is simply contained.

    """

    def __init__(self, name, position=None, source=None, location=None):
        self.name = name
        if position is not None:
            self.maritime_position = position
        if source is not None:
            self.maritime_position_source = source
        self.location = location

    def __repr__(self):
        return f"<{self.name}>"


class TestNoWorldPosition(BaseEvenniaTestCase):
    """The sentinel for 'outside the maritime world'."""

    def test_is_falsy(self):
        self.assertFalse(NoWorldPosition)

    def test_is_a_singleton(self):
        self.assertIs(NoWorldPositionType(), NoWorldPosition)

    def test_is_not_none(self):
        """
        None means 'nobody set this'. This means 'deliberately nowhere'.

        Conflating the two hides the case where a position was expected and
        never arrived.

        """
        self.assertIsNotNone(NoWorldPosition)

    def test_has_a_readable_repr(self):
        self.assertEqual(repr(NoWorldPosition), "NoWorldPosition")

    def test_does_not_pretend_to_have_coordinates(self):
        with self.assertRaises(AttributeError):
            NoWorldPosition.x


class TestDirectPosition(BaseEvenniaTestCase):
    """An entity that knows where it is."""

    def test_returns_its_own_position(self):
        here = WorldPosition(10.0, 20.0)
        self.assertEqual(get_world_position(Thing("buoy", position=here)), here)

    def test_own_position_wins_over_a_source(self):
        """A diver in the water is where they are, not where the hull is."""
        hull = Thing("hull", position=WorldPosition(0.0, 0.0))
        diver = Thing("diver", position=WorldPosition(5.0, 5.0, -30.0), source=hull)
        self.assertEqual(get_world_position(diver).z, -30.0)

    def test_non_position_values_are_ignored(self):
        """A tuple or a stale string must resolve to nothing, not to a crash."""
        thing = Thing("odd")
        thing.maritime_position = (1, 2)
        self.assertIs(get_world_position(thing), NoWorldPosition)


class TestChainResolution(BaseEvenniaTestCase):
    """Walking to whatever actually knows."""

    def setUp(self):
        super().setUp()
        self.at_sea = WorldPosition(18422.0, 9912.0)
        self.hull = Thing("hull", position=self.at_sea)
        self.cabin = Thing("cabin", source=self.hull)
        self.sailor = Thing("sailor", location=self.cabin)

    def test_character_resolves_through_cabin_to_hull(self):
        """The case the resolver exists for."""
        self.assertEqual(get_world_position(self.sailor), self.at_sea)

    def test_cabin_resolves_to_the_hull(self):
        self.assertEqual(get_world_position(self.cabin), self.at_sea)

    def test_moving_the_hull_moves_everyone_aboard(self):
        """Nobody aboard stores a position; they all follow the hull."""
        self.hull.maritime_position = WorldPosition(20000.0, 10000.0)
        self.assertEqual(get_world_position(self.sailor).x, 20000.0)

    def test_source_outranks_location(self):
        """
        A cabin belongs to a hull even while sitting in a room.

        Ordinary containment must not win, or a docked vessel's interior would
        resolve to the harbour room instead of the hull.

        """
        harbour = Thing("harbour", position=WorldPosition(1.0, 1.0))
        cabin = Thing("cabin", source=self.hull, location=harbour)
        self.assertEqual(get_world_position(cabin), self.at_sea)

    def test_follows_plain_containment(self):
        dock = Thing("dock", position=WorldPosition(500.0, 500.0))
        visitor = Thing("visitor", location=dock)
        self.assertEqual(get_world_position(visitor).x, 500.0)

    def test_follows_a_long_chain(self):
        deep = Thing("box", location=Thing("crate", location=self.cabin))
        self.assertEqual(get_world_position(deep), self.at_sea)


class TestOutsideTheMaritimeWorld(BaseEvenniaTestCase):
    """Most of a game is not at sea."""

    def test_inland_room_has_no_position(self):
        """
        A tavern three streets inland is not at a coordinate that happens not
        to matter. It is outside the maritime world entirely.

        """
        self.assertIs(get_world_position(Thing("tavern")), NoWorldPosition)

    def test_character_inland_has_no_position(self):
        drinker = Thing("drinker", location=Thing("tavern"))
        self.assertIs(get_world_position(drinker), NoWorldPosition)

    def test_none_resolves_to_no_position(self):
        self.assertIs(get_world_position(None), NoWorldPosition)

    def test_arbitrary_object_resolves_to_no_position(self):
        self.assertIs(get_world_position(object()), NoWorldPosition)


class TestCycles(BaseEvenniaTestCase):
    """Containment loops terminate."""

    def test_two_entity_cycle_terminates(self):
        first = Thing("first")
        second = Thing("second", location=first)
        first.location = second
        self.assertIs(get_world_position(first), NoWorldPosition)

    def test_self_reference_terminates(self):
        lonely = Thing("lonely")
        lonely.location = lonely
        self.assertIs(get_world_position(lonely), NoWorldPosition)

    def test_cycle_with_a_position_still_resolves(self):
        """A loop further along must not hide a position found before it."""
        anchored = Thing("anchored", position=WorldPosition(3.0, 4.0))
        loop_a = Thing("a")
        loop_b = Thing("b", location=loop_a)
        loop_a.location = loop_b
        rider = Thing("rider", location=anchored)
        self.assertEqual(get_world_position(rider).x, 3.0)


class TestHasWorldPosition(BaseEvenniaTestCase):
    """The guard form."""

    def test_true_when_located(self):
        self.assertTrue(has_world_position(Thing("buoy", position=WorldPosition(0.0, 0.0))))

    def test_false_when_not(self):
        self.assertFalse(has_world_position(Thing("tavern")))

    def test_true_through_a_chain(self):
        hull = Thing("hull", position=WorldPosition(0.0, 0.0))
        sailor = Thing("sailor", location=Thing("cabin", source=hull))
        self.assertTrue(has_world_position(sailor))


class TestResolveChain(BaseEvenniaTestCase):
    """Diagnosis."""

    def setUp(self):
        super().setUp()
        self.hull = Thing("hull", position=WorldPosition(1.0, 2.0))
        self.cabin = Thing("cabin", source=self.hull)
        self.sailor = Thing("sailor", location=self.cabin)

    def test_reports_every_link(self):
        self.assertEqual(resolve_chain(self.sailor), (self.sailor, self.cabin, self.hull))

    def test_stops_at_whatever_supplied_the_position(self):
        self.assertIs(resolve_chain(self.sailor)[-1], self.hull)

    def test_starts_with_the_entity_itself(self):
        self.assertIs(resolve_chain(self.sailor)[0], self.sailor)

    def test_unlocated_chain_ends_at_the_last_link(self):
        tavern = Thing("tavern")
        drinker = Thing("drinker", location=tavern)
        self.assertEqual(resolve_chain(drinker), (drinker, tavern))

    def test_terminates_on_a_cycle(self):
        first = Thing("first")
        second = Thing("second", location=first)
        first.location = second
        self.assertEqual(len(resolve_chain(first)), 2)
