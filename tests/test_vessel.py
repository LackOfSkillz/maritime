"""
Tests for vessel templates, capacity and deck plans.

"""

from evennia.utils.test_resources import BaseEvenniaTestCase

from ..vessel import (
    BELOW_WATERLINE,
    EXPOSURES,
    INTERIOR,
    MAIN_DECK,
    OPEN,
    DeckLevel,
    DeckPlan,
    VesselCapacity,
    VesselTemplate,
)


def a_sloop(**overrides):
    """Build a small valid template, so tests vary one thing at a time."""
    values = {
        "key": "sloop",
        "name": "Test Sloop",
        "length": 18.0,
        "beam": 5.4,
        "draft": 2.2,
    }
    values.update(overrides)
    return VesselTemplate(**values)


class TestExposures(BaseEvenniaTestCase):
    """Exposure levels."""

    def test_all_distinct(self):
        self.assertEqual(len(set(EXPOSURES)), len(EXPOSURES))

    def test_covers_deck_to_bilge(self):
        self.assertIn(OPEN, EXPOSURES)
        self.assertIn(BELOW_WATERLINE, EXPOSURES)


class TestVesselCapacity(BaseEvenniaTestCase):
    """The shared budget every fitting will draw on."""

    def test_defaults_to_nothing(self):
        capacity = VesselCapacity()
        self.assertEqual(capacity.displacement, 0.0)
        self.assertEqual(capacity.berths, 0)

    def test_carries_its_budgets(self):
        capacity = VesselCapacity(displacement=32000.0, internal_volume=40.0, berths=4)
        self.assertEqual(capacity.displacement, 32000.0)
        self.assertEqual(capacity.internal_volume, 40.0)
        self.assertEqual(capacity.berths, 4)

    def test_is_immutable(self):
        with self.assertRaises(Exception):
            VesselCapacity().displacement = 5.0

    def test_rejects_negative_budget(self):
        with self.assertRaises(ValueError):
            VesselCapacity(displacement=-1.0)

    def test_rejects_negative_berths(self):
        with self.assertRaises(ValueError):
            VesselCapacity(berths=-1)

    def test_rejects_non_finite_budget(self):
        with self.assertRaises(ValueError):
            VesselCapacity(internal_volume=float("inf"))

    def test_zero_is_allowed(self):
        """A raft has no hold; that is not an error."""
        self.assertEqual(VesselCapacity(internal_volume=0.0).internal_volume, 0.0)


class TestDeckLevel(BaseEvenniaTestCase):
    """One deck."""

    def test_main_deck_is_level_zero(self):
        self.assertEqual(MAIN_DECK, 0)

    def test_carries_its_fields(self):
        deck = DeckLevel(level=0, name="Main Deck", slots=3, exposure=OPEN)
        self.assertEqual(
            (deck.level, deck.name, deck.slots, deck.exposure), (0, "Main Deck", 3, OPEN)
        )

    def test_defaults_to_interior(self):
        self.assertEqual(DeckLevel(level=-1, name="Hold", slots=2).exposure, INTERIOR)

    def test_negative_levels_go_below(self):
        self.assertEqual(DeckLevel(level=-2, name="Bilge", slots=1).level, -2)

    def test_rejects_negative_slots(self):
        with self.assertRaises(ValueError):
            DeckLevel(level=0, name="Main Deck", slots=-1)

    def test_rejects_empty_name(self):
        with self.assertRaises(ValueError):
            DeckLevel(level=0, name="", slots=1)

    def test_rejects_unknown_exposure(self):
        """A typo here would silently make a cabin weather-exposed."""
        with self.assertRaises(ValueError):
            DeckLevel(level=0, name="Main Deck", slots=1, exposure="outdoorsy")

    def test_zero_slots_is_allowed(self):
        """A deck you can stand on but not build into."""
        self.assertEqual(DeckLevel(level=1, name="Crow's Nest", slots=0).slots, 0)


class TestDeckPlan(BaseEvenniaTestCase):
    """The whole hull's decks."""

    def setUp(self):
        super().setUp()
        self.plan = DeckPlan(
            decks=(
                DeckLevel(level=0, name="Main Deck", slots=2, exposure=OPEN),
                DeckLevel(level=-2, name="Bilge", slots=1, exposure=BELOW_WATERLINE),
                DeckLevel(level=-1, name="Hold", slots=2),
            )
        )

    def test_empty_plan_is_allowed(self):
        self.assertEqual(DeckPlan().total_slots, 0)

    def test_total_slots_sums_every_deck(self):
        self.assertEqual(self.plan.total_slots, 5)

    def test_ordered_runs_lowest_first(self):
        """Lowest first, because that is the order flooding fills."""
        self.assertEqual([deck.level for deck in self.plan.ordered()], [-2, -1, 0])

    def test_level_finds_a_deck(self):
        self.assertEqual(self.plan.level(-1).name, "Hold")

    def test_level_returns_none_when_absent(self):
        self.assertIsNone(self.plan.level(5))

    def test_rejects_duplicate_levels(self):
        """
        Two decks at one level would make "which room is below which"
        ambiguous, and flooding order depends on that answer.

        """
        with self.assertRaises(ValueError):
            DeckPlan(
                decks=(
                    DeckLevel(level=0, name="Main Deck", slots=1),
                    DeckLevel(level=0, name="Other Deck", slots=1),
                )
            )


class TestVesselTemplate(BaseEvenniaTestCase):
    """Ship classes as data."""

    def test_carries_its_dimensions(self):
        sloop = a_sloop()
        self.assertEqual((sloop.length, sloop.beam, sloop.draft), (18.0, 5.4, 2.2))

    def test_defaults_to_empty_capacity_and_plan(self):
        sloop = a_sloop()
        self.assertEqual(sloop.capacity.displacement, 0.0)
        self.assertEqual(sloop.deck_plan.total_slots, 0)

    def test_is_immutable(self):
        with self.assertRaises(Exception):
            a_sloop().length = 30.0

    def test_rejects_empty_key(self):
        with self.assertRaises(ValueError):
            a_sloop(key="")

    def test_rejects_zero_length(self):
        with self.assertRaises(ValueError):
            a_sloop(length=0.0)

    def test_rejects_negative_draft(self):
        with self.assertRaises(ValueError):
            a_sloop(draft=-1.0)

    def test_rejects_non_finite_dimension(self):
        with self.assertRaises(ValueError):
            a_sloop(beam=float("nan"))

    def test_rejects_beam_wider_than_length(self):
        """Not a hull. Almost always a transposed pair of numbers."""
        with self.assertRaises(ValueError):
            a_sloop(length=5.0, beam=18.0)

    def test_rejects_ideal_crew_below_minimum(self):
        with self.assertRaises(ValueError):
            a_sloop(crew_minimum=4, crew_ideal=1)

    def test_equal_crew_bounds_are_allowed(self):
        self.assertEqual(a_sloop(crew_minimum=2, crew_ideal=2).crew_ideal, 2)

    def test_two_templates_differ_only_by_data(self):
        """
        Changing a hull is changing numbers, never writing a subclass.

        This is what lets a game define its own vessels while importing nothing
        from this contrib but the template itself.

        """
        brig = a_sloop(key="brig", name="Test Brig", length=30.0, beam=8.0)
        self.assertIs(type(brig), type(a_sloop()))
        self.assertNotEqual(brig.length, a_sloop().length)


class TestSloopTemplate(BaseEvenniaTestCase):
    """A worked example, matching the plan's starter vessel."""

    def setUp(self):
        super().setUp()
        self.sloop = VesselTemplate(
            key="test_sloop",
            name="Test Sloop",
            length=18.0,
            beam=5.4,
            draft=2.2,
            capacity=VesselCapacity(
                displacement=32000.0, internal_volume=45.0, deck_area=60.0, berths=4
            ),
            deck_plan=DeckPlan(
                decks=(
                    DeckLevel(level=0, name="Main Deck", slots=2, exposure=OPEN),
                    DeckLevel(level=-1, name="Cargo Hold", slots=1, exposure=INTERIOR),
                )
            ),
            crew_minimum=1,
            crew_ideal=4,
        )

    def test_is_workable_single_handed(self):
        self.assertEqual(self.sloop.crew_minimum, 1)

    def test_has_three_compartments(self):
        """Main Deck, Cabin, Cargo Hold - the plan's starter layout."""
        self.assertEqual(self.sloop.deck_plan.total_slots, 3)

    def test_hold_sits_below_the_main_deck(self):
        levels = [deck.level for deck in self.sloop.deck_plan.ordered()]
        self.assertEqual(levels, [-1, 0])

    def test_main_deck_is_weather_exposed(self):
        self.assertEqual(self.sloop.deck_plan.level(MAIN_DECK).exposure, OPEN)

    def test_hold_is_not(self):
        self.assertEqual(self.sloop.deck_plan.level(-1).exposure, INTERIOR)
