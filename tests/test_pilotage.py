"""
Tests for a pilot taking her in.

The important half of the design is the default: **pilotage is off unless a builder says
otherwise.** A game that has not thought about pilots must not find its ships refused at
every quay, so a berth with nothing said about it takes anybody.

And the ordering: a stranger learns she wants a pilot *before* the approach, while there is
still sea room to wait in - which is the difference between an inconvenience and a grounding.

"""

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest

from ..motion import MotionLimits
from ..ports import (
    ALONGSIDE_SPEED,
    TOO_DEEP,
    TOO_FAR,
    WANTS_A_PILOT,
    Berth,
    can_dock,
)
from ..position import WorldPosition
from ..typeclasses import Vessel

ALONGSIDE = WorldPosition(0.0, 0.0)


def a_berth(**changes):
    """
    Args:
        **changes: Overrides.

    Returns:
        berth (Berth): A quay big enough for the test hull.

    """
    settings = {
        "key": "Long Pier",
        "position": ALONGSIDE,
        "heading": 0.0,
        "max_length": 40.0,
        "max_beam": 12.0,
        "max_draft": 5.0,
    }
    settings.update(changes)
    return Berth(**settings)


def trying_for(berth, piloted=True, draft=2.0):
    """
    Args:
        berth (Berth): The berth she is trying for.
        piloted (bool, optional): Whether she has a pilot aboard.
        draft (float, optional): How deep she sits.

    Returns:
        result (DockingResult): What the quay says.

    """
    return can_dock(ALONGSIDE, 0.0, berth.heading, 24.0, 7.0, draft, berth, piloted=piloted)


class TestTheDefaultIsNoPilotage(BaseEvenniaTest):
    """A game that has not thought about pilots is refused nothing."""

    def test_a_plain_berth_wants_no_pilot(self):
        self.assertFalse(a_berth().pilotage)

    def test_and_takes_a_ship_without_one(self):
        self.assertTrue(trying_for(a_berth(), piloted=False))

    def test_a_ship_with_one_is_welcome_too(self):
        self.assertTrue(trying_for(a_berth(), piloted=True))


class TestAPilotagePort(BaseEvenniaTest):
    """A bar, a tide race, a channel nobody can read from seaward."""

    def test_it_refuses_a_stranger(self):
        self.assertEqual(trying_for(a_berth(pilotage=True), piloted=False).code, WANTS_A_PILOT)

    def test_and_takes_her_with_a_pilot_aboard(self):
        self.assertTrue(trying_for(a_berth(pilotage=True), piloted=True))

    def test_the_refusal_comes_before_the_approach(self):
        """
        A pilot boards outside. Telling her at the quay that she should have picked one up
        an hour ago would be telling her too late to do anything about it.

        """
        far_off = can_dock(
            WorldPosition(5000.0, 0.0),
            0.0,
            0.0,
            24.0,
            7.0,
            2.0,
            a_berth(pilotage=True),
            piloted=False,
        )
        self.assertEqual(far_off.code, WANTS_A_PILOT)
        self.assertNotEqual(far_off.code, TOO_FAR)

    def test_but_after_whether_she_fits_at_all(self):
        """
        There is no point sending a ship for a pilot to take her into a berth she was never
        going to fit.

        """
        result = trying_for(a_berth(pilotage=True), piloted=False, draft=9.0)
        self.assertEqual(result.code, TOO_DEEP)

    def test_a_pilot_does_not_excuse_anything_else(self):
        """
        He knows the water. He does not make her narrower, and he does not stop her way.

        """
        too_fast = can_dock(
            ALONGSIDE,
            ALONGSIDE_SPEED * 5,
            0.0,
            24.0,
            7.0,
            2.0,
            a_berth(pilotage=True),
            piloted=True,
        )
        self.assertFalse(too_fast)
        self.assertNotEqual(too_fast.code, WANTS_A_PILOT)


class TestABerthFromBeforePilotageExisted(BaseEvenniaTest):
    """
    Berths live in the database, so adding a field to one is a migration.

    What makes it a safe migration is that a dataclass default lives on the *class*: an old
    berth restored without the attribute falls through to it. A field added without a default
    would raise on the first `dock` after an upgrade, in a world that worked the day before -
    which is what these two are here to remember.

    """

    def a_berth_without_the_field(self):
        """
        Returns:
            berth (Berth): One whose stored state never had `pilotage` in it.

        Notes:
            Built the way unpickling builds one - state restored straight onto the instance,
            with no `__post_init__` - because that is exactly what an existing world hands
            back after an upgrade.

        """
        old = Berth.__new__(Berth)
        old.__dict__.update(
            {
                "key": "Long Pier",
                "position": ALONGSIDE,
                "heading": 0.0,
                "max_length": 40.0,
                "max_beam": 12.0,
                "max_draft": 5.0,
            }
        )
        return old

    def test_it_is_missing_from_the_restored_state(self):
        self.assertNotIn("pilotage", self.a_berth_without_the_field().__dict__)

    def test_but_the_class_default_answers_for_it(self):
        self.assertFalse(self.a_berth_without_the_field().pilotage)

    def test_and_a_ship_can_still_come_alongside(self):
        self.assertTrue(trying_for(self.a_berth_without_the_field(), piloted=False))


class TestTakingOneAboard(BaseEvenniaTest):
    """A pilot is somebody, not a flag."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Kestrel")
        self.hull.length, self.hull.beam = 24.0, 7.0
        self.hull.motion_limits = MotionLimits(max_speed=6.0, acceleration=0.5, turn_rate=5.0)
        self.hull.maritime_position = ALONGSIDE

    def a_pilot(self):
        return create.create_object("evennia.objects.objects.DefaultCharacter", key="The pilot")

    def test_a_new_hull_has_none(self):
        self.assertIsNone(self.hull.pilot)
        self.assertFalse(self.hull.piloted)

    def test_one_can_come_aboard(self):
        pilot = self.a_pilot()
        self.assertTrue(self.hull.take_a_pilot(pilot))
        self.assertIs(self.hull.pilot, pilot)
        self.assertTrue(self.hull.piloted)

    def test_nobody_is_not_a_pilot(self):
        self.assertFalse(self.hull.take_a_pilot(None))

    def test_he_can_be_put_back_in_his_boat(self):
        pilot = self.a_pilot()
        self.hull.take_a_pilot(pilot)
        self.assertIs(self.hull.discharge_pilot(), pilot)
        self.assertFalse(self.hull.piloted)

    def test_discharging_nobody_is_not_an_error(self):
        self.assertIsNone(self.hull.discharge_pilot())

    def test_a_pilot_who_has_been_deleted_is_no_longer_aboard(self):
        """
        An Evennia attribute holding a deleted object hands back None, and a ship conned by
        nobody-at-all is a ship without a pilot.

        """
        pilot = self.a_pilot()
        self.hull.take_a_pilot(pilot)
        pilot.delete()
        self.assertFalse(self.hull.piloted)
