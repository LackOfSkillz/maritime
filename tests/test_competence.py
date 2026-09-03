"""
Tests that the skill seam actually buys something.

`competence_at` existed from the moment posts did, and for a long while nothing read it -
which made the whole seam a claim rather than a rule. A game pointing
`MARITIME_COMPETENCE_POLICY` at its own skill system got a number back and no consequence.

These are the four consequences. Each is a post doing what that post is *for*: the helmsman
answering, the lookout seeing, the gunner serving, the carpenter mending. Every one of them
is checked against a competent ship as well as an incompetent one, because a rule that
punished everybody equally would be a rule nobody could tell was there.

"""

from django.test import override_settings

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaTest

from ..motion import MotionLimits
from ..position import WorldPosition
from ..rooms import ShipRoom
from ..traffic import traffic
from ..stations import CARPENTER, GUNNERY, HELM, LOOKOUT, WELL_ENOUGH, competence_of
from ..typeclasses import Vessel
from ..vessel import OPEN, VesselCapacity
from ..weapons import Mount, WeaponType
from .base import EmptySeaMixin

HERE = WorldPosition(0.0, 0.0)

#: What a green hand gets out of a job, for a game that has said so.
GREEN = 0.5


def a_green_crew(character, post, vessel):
    """
    A stand-in for a game's own skill system.

    Args:
        character (object or None): Whoever is standing the post.
        post (str): Which post.
        vessel (object): The hull.

    Returns:
        competence (float): Half of what it could be.

    """
    return GREEN


GREEN_POLICY = f"{a_green_crew.__module__}.{a_green_crew.__qualname__}"

GUN = WeaponType(
    key="long nine",
    name="long nine",
    arc=90.0,
    max_range=800.0,
    reload_time=90.0,
    projectile_speed=250.0,
    accuracy=0.6,
    damage=10.0,
)


def a_stranger_at(metres):
    """
    Another hull out on the beam, tall enough to be seen a long way off.

    Args:
        metres (float): How far east of the origin.

    Returns:
        vessel (Vessel): The stranger, noted in the register.

    """
    other = create.create_object(Vessel, key=f"Stranger at {metres:.0f}")
    other.length, other.beam = 24.0, 7.0
    other.air_draft = 30.0
    other.motion_limits = MotionLimits(max_speed=6.0, acceleration=0.5, turn_rate=5.0)
    other.maritime_position = WorldPosition(metres, 0.0)
    other.heading = 180.0
    deck = create.create_object(ShipRoom, key="Her deck")
    deck.vessel = other
    deck.exposure = OPEN
    traffic().note(other, other.maritime_position)
    return other


class CompetenceTestCase(EmptySeaMixin, BaseEvenniaTest):
    """A hull with posts to stand."""

    def setUp(self):
        super().setUp()
        self.hull = create.create_object(Vessel, key="Kestrel")
        self.hull.length, self.hull.beam = 24.0, 7.0
        self.hull.light_draft = 2.0
        self.hull.motion_limits = MotionLimits(max_speed=6.0, acceleration=0.5, turn_rate=8.0)
        self.hull.capacity = VesselCapacity(
            displacement=200_000.0, internal_volume=300.0, stability_moment=100_000.0
        )
        self.hull.maritime_position = HERE
        self.hull.heading = 0.0
        self.deck = create.create_object(ShipRoom, key="Deck")
        self.deck.vessel = self.hull
        self.deck.exposure = OPEN


class TestTheShippedAnswer(CompetenceTestCase):
    """Well enough, always - because a character system is what this must not import."""

    def test_a_post_nobody_stands_is_kept_well_enough(self):
        self.assertAlmostEqual(self.hull.competence_at(HELM), WELL_ENOUGH)

    def test_and_so_is_one_somebody_does(self):
        hand = create.create_object(
            "evennia.objects.objects.DefaultCharacter", key="A hand", location=self.deck
        )
        self.hull.post_to(HELM, hand)
        self.assertAlmostEqual(self.hull.competence_at(HELM), WELL_ENOUGH)

    def test_the_shipped_policy_says_so_for_every_post(self):
        for post in (HELM, LOOKOUT, GUNNERY, CARPENTER):
            self.assertAlmostEqual(competence_of(None, post, self.hull), WELL_ENOUGH)


@override_settings(MARITIME_COMPETENCE_POLICY=GREEN_POLICY)
class TestAGameThatHasItsOwnSkills(CompetenceTestCase):
    """The four consequences. Each is the post doing what that post is for."""

    def test_the_policy_is_taken_up(self):
        self.assertAlmostEqual(self.hull.competence_at(HELM), GREEN)

    def test_a_green_helmsman_is_slower_to_answer(self):
        """
        What a helmsman is for. Her top speed is a fact about her tonnage; how fast she
        comes round is a fact about whoever has the wheel.

        """
        self.assertAlmostEqual(
            self.hull.working_limits.turn_rate, self.hull.motion_limits.turn_rate * GREEN
        )

    def test_but_he_cannot_make_her_slower_through_the_water(self):
        """
        Steering badly does not reduce her displacement. A consequence that leaked into
        everything would be a difficulty slider rather than a helmsman.

        """
        self.assertAlmostEqual(
            self.hull.working_limits.max_speed, self.hull.motion_limits.max_speed
        )

    def test_a_green_gunner_serves_his_guns_slower(self):
        self.hull.add_mount(Mount(key="starboard one", weapon=GUN))
        gun = self.hull.mounts[0]
        self.assertGreater(self.hull.serving_seconds(gun), gun.weapon.reload_time)

    def test_a_green_carpenter_mends_her_slower(self):
        """
        Measured against what the same party would do under a carpenter who knew his
        trade, not against zero - a party of eight is a party of eight either way.

        """
        from ..repairs import DOING_NOTHING_ELSE, party_rate

        self.hull.set_carpenters(8.0)
        able = party_rate(self.hull.carpenters) * DOING_NOTHING_ELSE
        self.assertGreater(able, 0.0, "the fixture never put a party on the work")
        self.assertAlmostEqual(self.hull.repair_rate(quiet=True), able * GREEN)

    def test_a_green_lookout_misses_what_is_faint(self):
        """
        The horizon is geometry and the lookout is attention. He cannot see further than
        the curve of the earth allows; what he loses is the topsail on the skyline.

        """
        far = self.a_stranger(at_metres=25_000.0)
        self.assertNotIn(far, [sighting.target for sighting in self.hull.contacts()])

    def test_but_sees_perfectly_well_what_is_near(self):
        near = self.a_stranger(at_metres=500.0)
        self.assertIn(near, [sighting.target for sighting in self.hull.contacts()])

    def a_stranger(self, at_metres):
        """Another hull, out on the beam and in the register."""
        return a_stranger_at(at_metres)


class TestACompetentShipIsUnaffected(CompetenceTestCase):
    """A rule that punished everybody equally would be a rule nobody could see."""

    def test_her_helm_answers_at_her_own_rate(self):
        self.assertAlmostEqual(
            self.hull.working_limits.turn_rate, self.hull.motion_limits.turn_rate
        )

    def test_her_guns_are_served_at_their_own_rate(self):
        self.hull.add_mount(Mount(key="starboard one", weapon=GUN))
        gun = self.hull.mounts[0]
        self.assertAlmostEqual(self.hull.serving_seconds(gun), gun.weapon.reload_time)

    def test_and_her_lookout_reports_everything_in_sight(self):
        far = a_stranger_at(25_000.0)
        self.assertIn(far, [sighting.target for sighting in self.hull.contacts()])
