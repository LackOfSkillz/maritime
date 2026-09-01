"""
Tests for the hulls a game can build, and for laying them up.

The arithmetic gets the most attention here, and deliberately. A template whose figures
were chosen reads exactly like one whose figures were derived, so the derivations are
checked against vessels that existed and against each other rather than against themselves.

"""

from evennia.utils import create
from evennia.utils.test_resources import BaseEvenniaCommandTest, BaseEvenniaTestCase

from .. import ordinary, shipyard
from ..commands.shipyard import (
    CmdMaritimeBuild,
    CmdMaritimeLayUp,
    CmdMaritimePlayerBuild,
    CmdMaritimeSummon,
    MaritimeShipyardCmdSet,
    a_berth_for,
    dock_here,
    named,
    players_may_build,
    set_players_may_build,
)
from ..motion import MotionLimits
from ..ports import Berth
from ..position import WorldPosition
from ..rooms import PortRoom, ShipRoom
from ..typeclasses import Vessel
from .base import EmptySeaMixin

#: Where the test quay lies, and which way it runs.
QUAY = WorldPosition(0.0, 0.0)
EAST = 90.0


def a_berth(**kwargs):
    """
    Args:
        **kwargs: Overrides.

    Returns:
        berth (Berth): One that takes anything up to a schooner.

    """
    settings = {
        "key": "north quay",
        "position": QUAY,
        "heading": EAST,
        "max_length": 30.0,
        "max_beam": 8.0,
        "max_draft": 4.0,
    }
    settings.update(kwargs)
    return Berth(**settings)


class TestBuildersOldMeasurement(BaseEvenniaTestCase):
    """
    The tonnage rule, against hulls whose figures were recorded.

    Notes:
        Two checks and not one. A formula tested only against itself is a formula that
        cannot be wrong, and these are the two vessels in the module docstring - one where
        the rule lands almost exactly and one where it is known to run high.

    """

    def test_a_leda_class_frigate_comes_out_within_one_per_cent(self):
        # 150 ft gun deck by 39 ft 11 in, recorded at 1,065 tons burthen.
        ours = shipyard.burthen(45.7, 12.2)
        self.assertLess(abs(ours / 1065.0 - 1.0), 0.01, f"{ours:.0f} tons against 1,065")

    def test_a_cruizer_class_brig_runs_high_by_about_five_per_cent(self):
        # 100 ft by 30 ft 6 in, recorded at 384 tons. The rule wants the length of keel
        # and is given the length on deck, which is longer; the error is in a known
        # direction and is documented rather than fudged away.
        ours = shipyard.burthen(30.5, 9.3)
        over = ours / 384.0 - 1.0
        self.assertGreater(over, 0.0)
        self.assertLess(over, 0.08, f"{ours:.0f} tons against 384")

    def test_tonnage_grows_faster_than_length(self):
        # Beam squared is in the formula, which is why a hull twice as long and twice as
        # broad measures eight times as much rather than four.
        self.assertAlmostEqual(
            shipyard.burthen(40.0, 12.0) / shipyard.burthen(20.0, 6.0), 8.0, places=6
        )

    def test_a_hull_narrower_than_it_is_long_measures_something(self):
        self.assertGreater(shipyard.burthen(10.0, 3.2), 0.0)


class TestDisplacement(BaseEvenniaTestCase):
    """Weight, and how much of it is not the ship."""

    def test_a_box_of_seawater_weighs_what_it_should(self):
        # Block coefficient 1.0 is the enclosing box, so this is the density and nothing
        # else - which is the one figure here that has a right answer.
        self.assertAlmostEqual(shipyard.displaces(2.0, 1.0, 0.5, 1.0), 1025.0, places=6)

    def test_the_deadweight_fraction_reproduces_the_example_sloop(self):
        # 18.0 by 5.4 drawing 2.2 at a block coefficient of 0.45. `example/craft.py`
        # arrived at 40 tonnes of deadweight independently, by a different route.
        ours = shipyard.deadweight(18.0, 5.4, 2.2, 0.45)
        self.assertLess(abs(ours / 40000.0 - 1.0), 0.06, f"{ours / 1000:.1f} t against 40")

    def test_a_finer_hull_of_the_same_size_weighs_less(self):
        fine = shipyard.displaces(27.0, 7.3, 3.4, 0.42)
        full = shipyard.displaces(27.0, 7.3, 3.4, 0.58)
        self.assertLess(fine, full)


class TestTheHolds(BaseEvenniaTestCase):
    """What each hull can actually stow."""

    def test_a_frigate_measures_more_than_a_barque_and_stows_less(self):
        # The whole point of the `usable` figure: a fifth rate is powder, shot, water and
        # two hundred and eighty men, and a barque is a hold with masts on it.
        frigate = shipyard.figures("frigate")
        barque = shipyard.figures("barque")
        self.assertGreater(frigate["burthen"], barque["burthen"])
        self.assertLess(frigate["hold"], barque["hold"])

    def test_holds_rise_with_the_hulls(self):
        holds = [shipyard.figures(name)["hold"] for name in ("yawl", "lugger", "cutter")]
        self.assertEqual(holds, sorted(holds))


class TestTheBook(BaseEvenniaTestCase):
    """Every hull is complete, and no two are the same ship."""

    def test_there_are_seven(self):
        self.assertEqual(len(shipyard.NAMES), 7)

    def test_every_name_has_a_hull(self):
        for name in shipyard.NAMES:
            self.assertIsNotNone(shipyard.specification(name), name)

    def test_the_book_and_the_names_agree(self):
        self.assertEqual(set(shipyard.NAMES), set(shipyard.HULLS))

    def test_they_are_listed_smallest_first(self):
        lengths = [shipyard.HULLS[name]["length"] for name in shipyard.NAMES]
        self.assertEqual(lengths, sorted(lengths))

    def test_every_hull_has_every_field(self):
        wanted = {
            "rig",
            "length",
            "beam",
            "draft",
            "air_draft",
            "block",
            "usable",
            "windage",
            "berths",
            "oars",
            "curve",
            "limits",
            "desc",
            "decks",
        }
        for name in shipyard.NAMES:
            self.assertEqual(wanted - set(shipyard.HULLS[name]), set(), name)

    def test_every_hull_has_somewhere_to_stand(self):
        for name in shipyard.NAMES:
            self.assertTrue(shipyard.HULLS[name]["decks"], name)

    def test_every_hull_but_the_smallest_has_a_hold(self):
        for name in shipyard.NAMES:
            if name == "yawl":
                continue
            holds = [deck for deck in shipyard.HULLS[name]["decks"] if deck.get("hold")]
            self.assertTrue(holds, f"{name} has nowhere to put cargo")

    def test_no_two_decks_of_one_hull_share_a_name(self):
        for name in shipyard.NAMES:
            keys = [deck["key"] for deck in shipyard.HULLS[name]["decks"]]
            self.assertEqual(len(keys), len(set(keys)), name)

    def test_unknown_rigs_answer_nothing_rather_than_raising(self):
        self.assertIsNone(shipyard.specification("ironclad"))
        self.assertIsNone(shipyard.figures("ironclad"))
        self.assertIsNone(shipyard.capacity_of("ironclad"))


class TestTheRigs(BaseEvenniaTestCase):
    """Three curves, and they are genuinely different shapes."""

    def test_a_square_rigger_cannot_lie_close(self):
        self.assertEqual(shipyard.SQUARE_RIG.efficiency_at(45.0), 0.0)

    def test_a_fore_and_after_can(self):
        self.assertGreater(shipyard.FORE_AND_AFT.efficiency_at(45.0), 0.0)

    def test_a_square_rigger_runs_better_than_a_fore_and_after(self):
        self.assertGreater(
            shipyard.SQUARE_RIG.efficiency_at(170.0),
            shipyard.FORE_AND_AFT.efficiency_at(170.0),
        )

    def test_a_lugger_sits_between_them_going_to_windward(self):
        close = 45.0
        self.assertGreater(
            shipyard.LUG_RIG.efficiency_at(close), shipyard.SQUARE_RIG.efficiency_at(close)
        )
        self.assertLess(
            shipyard.LUG_RIG.efficiency_at(close),
            shipyard.FORE_AND_AFT.efficiency_at(close),
        )

    def test_a_lugger_runs_better_than_a_fore_and_after(self):
        self.assertGreater(
            shipyard.LUG_RIG.efficiency_at(180.0), shipyard.FORE_AND_AFT.efficiency_at(180.0)
        )

    def test_the_square_riggers_carry_the_square_curve(self):
        for name in ("brig", "barque", "frigate"):
            self.assertIs(shipyard.HULLS[name]["curve"], shipyard.SQUARE_RIG, name)


class TestOutfitting(EmptySeaMixin, BaseEvenniaCommandTest):
    """A hull built from the book is a hull that works."""

    def built(self, name="cutter", key="Test Hull"):
        """
        Args:
            name (str): Which rig.
            key (str): What to call her.

        Returns:
            vessel (Vessel): Outfitted, with her compartments.

        """
        hull = shipyard.outfit(create.create_object(Vessel, key=key), name)
        shipyard.compartments(hull, name)
        return hull

    def test_she_gets_her_dimensions(self):
        hull = self.built("brig")
        self.assertAlmostEqual(hull.length, 30.5)
        self.assertAlmostEqual(hull.beam, 9.3)

    def test_she_gets_her_rig(self):
        self.assertEqual(self.built("brig").polar_curve.points, shipyard.SQUARE_RIG.points)

    def test_she_gets_her_capacity(self):
        hull = self.built("schooner")
        worked = shipyard.figures("schooner")
        self.assertAlmostEqual(hull.capacity.internal_volume, worked["hold"], places=6)
        self.assertEqual(hull.capacity.berths, worked["berths"])

    def test_she_starts_with_her_sails_furled(self):
        from ..sailing import FURLED

        self.assertEqual(self.built("cutter").sail_plan, FURLED)

    def test_she_gets_her_sweeps_if_she_carries_any(self):
        self.assertIsNotNone(self.built("cutter").oar_plan)

    def test_a_barque_carries_none(self):
        # Not asserted as None: a hull with no `oar_plan` set may answer with a default,
        # and what matters is that nobody rows a forty-five-metre barque.
        self.assertIsNone(shipyard.HULLS["barque"]["oars"])

    def test_her_compartments_are_hers(self):
        hull = self.built("frigate")
        rooms = hull.ship_rooms
        self.assertEqual(len(rooms), len(shipyard.HULLS["frigate"]["decks"]))
        for room in rooms:
            self.assertIs(room.vessel, hull)

    def test_her_compartments_carry_her_name(self):
        # So that a harbour of forty ships does not contain forty rooms called "Hold".
        hull = self.built("brig", key="Rattler")
        for room in hull.ship_rooms:
            self.assertTrue(room.key.startswith("Rattler - "), room.key)

    def test_her_holds_add_up_to_her_hold(self):
        hull = self.built("barque")
        stowage = sum(room.hold_capacity for room in hull.ship_rooms if room.hold_capacity)
        self.assertAlmostEqual(stowage, shipyard.figures("barque")["hold"], places=6)

    def test_she_has_a_weather_deck_to_land_a_gangway_on(self):
        from ..commands.shipyard import landing_deck

        for name in shipyard.NAMES:
            hull = self.built(name, key=f"Test {name}")
            self.assertIsNotNone(landing_deck(hull), name)

    def test_the_rig_description_is_not_written_onto_her(self):
        # What a hull *is* belongs to the rig; what one ship looks like belongs to
        # whoever built her.
        self.assertIsNone(self.built("cutter").db.desc)


class ShipyardTestCase(EmptySeaMixin, BaseEvenniaCommandTest):
    """A quay with one berth, and nobody's ships in it."""

    def setUp(self):
        super().setUp()
        self.port = create.create_object(PortRoom, key="North Quay")
        self.port.maritime_position = QUAY
        self.port.add_berth(a_berth())
        self.char1.location = self.port
        set_players_may_build(False)

    def tearDown(self):
        from .. import switches

        switches._forget()
        super().tearDown()


class TestFindingTheDock(ShipyardTestCase):
    """A quay under your feet, and not one three streets away."""

    def test_a_port_room_with_berths_is_a_dock(self):
        self.assertIs(dock_here(self.char1), self.port)

    def test_an_ordinary_room_is_not(self):
        self.char1.location = self.room1
        self.assertIsNone(dock_here(self.char1))

    def test_a_port_room_with_no_berths_is_not(self):
        bare = create.create_object(PortRoom, key="Slipway")
        self.char1.location = bare
        self.assertIsNone(dock_here(self.char1))

    def test_nowhere_at_all_is_not(self):
        self.char1.location = None
        self.assertIsNone(dock_here(self.char1))

    def test_it_does_not_walk_to_the_next_room(self):
        # Deliberate. Two people standing in the same place should get the same answer,
        # and a bounded walk makes it depend on which way the exits happen to run.
        create.create_object(
            "evennia.objects.objects.DefaultExit",
            key="quay",
            location=self.room1,
            destination=self.port,
        )
        self.char1.location = self.room1
        self.assertIsNone(dock_here(self.char1))


class TestFindingABerth(ShipyardTestCase):
    """Which berth she can have, and why she cannot have one."""

    def test_an_empty_berth_that_fits(self):
        berth, why = a_berth_for(self.port, 20.0, 6.0, 2.6)
        self.assertIsNotNone(berth)
        self.assertIsNone(why)

    def test_a_frigate_will_not_fit_a_schooner_berth(self):
        berth, why = a_berth_for(self.port, 45.7, 12.2, 4.2)
        self.assertIsNone(berth)
        self.assertTrue(why)

    def test_it_says_which_dimension_refused_her(self):
        _berth, why = a_berth_for(self.port, 20.0, 6.0, 9.9)
        self.assertIn("draws too much", why.lower())

    def test_it_says_it_in_the_words_dock_uses(self):
        # One wording for one refusal. Two sets of sentences for the same three codes is
        # how a game ends up telling a player two different things about one berth.
        from ..commands.mooring import BERTH_REFUSALS
        from ..ports import TOO_DEEP

        _berth, why = a_berth_for(self.port, 20.0, 6.0, 9.9)
        self.assertTrue(BERTH_REFUSALS[TOO_DEEP].startswith(why))

    def test_a_taken_berth_is_not_offered(self):
        hull = shipyard.outfit(create.create_object(Vessel, key="First"), "cutter")
        shipyard.compartments(hull, "cutter")
        hull.make_fast(self.port, self.port.berths[0])
        berth, why = a_berth_for(self.port, 20.0, 6.0, 2.6)
        self.assertIsNone(berth)
        self.assertIn("taken", why)


class TestBuildCommand(ShipyardTestCase):
    """`maritime build`."""

    def test_it_lists_the_hulls(self):
        said = self.call(CmdMaritimeBuild(), "", None)
        for name in shipyard.NAMES:
            self.assertIn(name, said)

    def test_it_builds_one_alongside(self):
        self.call(CmdMaritimeBuild(), "cutter Kittiwake", "Kittiwake is built and lying in")
        hull = named("Kittiwake")
        self.assertIsNotNone(hull)
        self.assertTrue(hull.docked)

    def test_the_ship_it_builds_has_her_figures(self):
        self.call(CmdMaritimeBuild(), "cutter Kittiwake", None)
        self.assertAlmostEqual(named("Kittiwake").length, 20.0)

    def test_her_gangway_is_down(self):
        self.call(CmdMaritimeBuild(), "cutter Kittiwake", None)
        self.assertTrue(named("Kittiwake").db.gangway)

    def test_it_refuses_a_name_already_taken(self):
        self.call(CmdMaritimeBuild(), "cutter Kittiwake", None)
        self.port.db.moored = []
        self.call(CmdMaritimeBuild(), "yawl Kittiwake", "There is a ship called")

    def test_the_name_check_ignores_case(self):
        self.call(CmdMaritimeBuild(), "cutter Kittiwake", None)
        self.port.db.moored = []
        self.call(CmdMaritimeBuild(), "yawl kittiwake", "There is a ship called")

    def test_it_refuses_an_unknown_rig(self):
        self.call(CmdMaritimeBuild(), "ironclad Warrior", "There is no 'ironclad'")

    def test_it_wants_a_name(self):
        self.call(CmdMaritimeBuild(), "cutter", "Build her as what")

    def test_it_sends_you_to_the_dock(self):
        self.char1.location = self.room1
        self.call(CmdMaritimeBuild(), "cutter Kittiwake", "Ships are built and laid up")
        self.assertIsNone(named("Kittiwake"))

    def test_it_refuses_a_hull_the_berth_will_not_take(self):
        self.call(CmdMaritimeBuild(), "frigate Amphitrite", "She cannot lie here")
        self.assertIsNone(named("Amphitrite"))

    def test_it_is_hidden_from_players_by_default(self):
        self.assertFalse(CmdMaritimeBuild().access(self.char2, "cmd"))

    def test_it_opens_to_players_when_the_game_says_so(self):
        set_players_may_build(True)
        self.assertTrue(CmdMaritimeBuild().access(self.char2, "cmd"))

    def test_it_takes_the_session_the_parser_passes(self):
        # See the matching test in test_switches: a missing `session` keyword here raises
        # out of the command parser rather than out of this command.
        self.assertFalse(CmdMaritimeBuild().access(self.char2, "cmd", session=None))
        set_players_may_build(True)
        self.assertTrue(CmdMaritimeBuild().access(self.char2, "cmd", session=None))

    def test_staff_can_build_either_way(self):
        self.char1.permissions.add("Admin")
        self.assertTrue(CmdMaritimeBuild().access(self.char1, "cmd"))


class TestPlayerBuildCommand(ShipyardTestCase):
    """`maritime player build`."""

    def test_it_reports_the_default(self):
        self.call(CmdMaritimePlayerBuild(), "", "Only staff may build")

    def test_it_opens_building_up(self):
        self.call(CmdMaritimePlayerBuild(), "on", "Players may now build")
        self.assertTrue(players_may_build())

    def test_it_closes_building_again(self):
        set_players_may_build(True)
        self.call(CmdMaritimePlayerBuild(), "off", "Players may no longer build")
        self.assertFalse(players_may_build())

    def test_it_says_nothing_already_built_is_lost(self):
        set_players_may_build(True)
        said = self.call(CmdMaritimePlayerBuild(), "off", None)
        self.assertIn("stays built", said)

    def test_it_refuses_nonsense(self):
        self.call(CmdMaritimePlayerBuild(), "sometimes", "Say maritime player build on")

    def test_it_is_locked_to_staff(self):
        self.assertIn("perm(Admin)", CmdMaritimePlayerBuild.locks)


class OrdinaryTestCase(ShipyardTestCase):
    """A ship of the caller's, lying at the quay."""

    def setUp(self):
        super().setUp()
        self.hull = shipyard.outfit(create.create_object(Vessel, key="Kittiwake"), "cutter")
        shipyard.compartments(self.hull, "cutter")
        self.hull.motion_limits = MotionLimits(max_speed=5.0, acceleration=0.4, turn_rate=4.0)
        self.hull.owner = self.char1
        self.hull.make_fast(self.port, self.port.berths[0])
        self.hull.speed = 0.0


class TestLayingUp(OrdinaryTestCase):
    """What `ordinary.lay_up` does and refuses."""

    def test_she_starts_in_commission(self):
        self.assertFalse(ordinary.in_ordinary(self.hull))

    def test_laying_her_up_takes_her_off_the_water(self):
        self.assertIsNone(ordinary.lay_up(self.hull))
        self.assertTrue(ordinary.in_ordinary(self.hull))
        self.assertIsNone(self.hull.maritime_position)

    def test_she_reads_back_off_the_water_and_not_from_the_last_save(self):
        # The getter reads the live position and falls back to the saved one, and
        # `checkpoint` skips a live position of None - so clearing only the live value
        # would leave her reading back as still lying where she was.
        self.hull.checkpoint()
        ordinary.lay_up(self.hull)
        self.assertIsNone(self.hull.db.maritime_position)
        self.assertIsNone(self.hull.maritime_position)

    def test_a_tuple_is_still_refused(self):
        # Widening the setter to take None must not have widened it to take anything.
        with self.assertRaises(TypeError):
            self.hull.maritime_position = (1.0, 2.0)

    def test_it_frees_her_berth(self):
        ordinary.lay_up(self.hull)
        self.assertIsNone(self.port.occupant_of(self.port.berths[0]))

    def test_it_takes_her_gangway_away(self):
        ordinary.lay_up(self.hull)
        self.assertFalse(self.hull.db.gangway)

    def test_it_drops_her_from_the_traffic_register(self):
        from ..traffic import traffic

        traffic().note(self.hull, QUAY)
        ordinary.lay_up(self.hull)
        self.assertNotIn(self.hull, traffic())

    def test_she_keeps_her_compartments(self):
        rooms = list(self.hull.ship_rooms)
        ordinary.lay_up(self.hull)
        self.assertEqual(list(self.hull.ship_rooms), rooms)

    def test_she_keeps_what_is_in_them(self):
        hold = [room for room in self.hull.ship_rooms if room.hold_capacity][0]
        crate = create.create_object(
            "evennia.objects.objects.DefaultObject", key="a crate", location=hold
        )
        ordinary.lay_up(self.hull)
        self.assertIs(crate.location, hold)

    def test_a_ship_under_way_is_refused(self):
        self.hull.speed = 3.0
        refused = ordinary.lay_up(self.hull)
        self.assertIn("under way", refused)
        self.assertFalse(ordinary.in_ordinary(self.hull))

    def test_a_ship_under_orders_is_refused_even_at_rest(self):
        from ..motion import HelmOrders

        self.hull.speed = 0.0
        self.hull.orders = HelmOrders(heading=EAST, speed=4.0)
        self.assertIn("under way", ordinary.lay_up(self.hull))

    def test_a_hundredth_of_a_knot_of_drift_is_not_under_way(self):
        self.hull.speed = 0.004
        self.assertIsNone(ordinary.lay_up(self.hull))

    def test_a_ship_with_somebody_aboard_is_refused(self):
        # `char1` and not `char2`: only char1 is being played in the Evennia test base, and
        # somebody with no session is not somebody who would notice their floor leaving.
        self.assertTrue(self.char1.sessions.count(), "the test base stopped puppeting char1")
        self.char1.location = self.hull.ship_rooms[0]
        refused = ordinary.lay_up(self.hull)
        self.assertIn(self.char1.key, refused)
        self.assertFalse(ordinary.in_ordinary(self.hull))

    def test_a_ship_somebody_logged_out_aboard_is_refused(self):
        # The case that would otherwise strand them. Evennia takes an unpuppeted character
        # off the grid, so they are in no room's contents - and a hull laid up under them
        # comes back nowhere, with her gangway gone.
        self.char2.db.prelogout_location = self.hull.ship_rooms[0]
        self.char2.location = None
        refused = ordinary.lay_up(self.hull)
        self.assertIn(self.char2.key, refused)

    def test_a_crew_of_npcs_is_not_a_reason_to_refuse(self):
        # A crew is part of a ship. Nobody is standing on her floor in the sense that
        # matters: an NPC has no session and no room to come back to but hers.
        create.create_object(
            "evennia.objects.objects.DefaultCharacter",
            key="a hand",
            location=self.hull.ship_rooms[0],
        )
        self.assertIsNone(ordinary.lay_up(self.hull))

    def test_a_crate_aboard_is_not_somebody(self):
        hold = [room for room in self.hull.ship_rooms if room.hold_capacity][0]
        create.create_object("evennia.objects.objects.DefaultObject", key="a crate", location=hold)
        self.assertIsNone(ordinary.lay_up(self.hull))

    def test_laying_her_up_twice_is_refused(self):
        ordinary.lay_up(self.hull)
        self.assertIn("already laid up", ordinary.lay_up(self.hull))


class TestBringingForward(OrdinaryTestCase):
    """And back again."""

    def test_she_comes_back_alongside(self):
        ordinary.lay_up(self.hull)
        ordinary.bring_forward(self.hull, self.port, self.port.berths[0])
        self.assertFalse(ordinary.in_ordinary(self.hull))
        self.assertTrue(self.hull.docked)

    def test_she_comes_back_where_she_was_put(self):
        ordinary.lay_up(self.hull)
        ordinary.bring_forward(self.hull, self.port, self.port.berths[0])
        self.assertEqual(self.hull.maritime_position, self.port.berths[0].position)

    def test_her_berth_is_taken_again(self):
        ordinary.lay_up(self.hull)
        ordinary.bring_forward(self.hull, self.port, self.port.berths[0])
        self.assertIs(self.port.occupant_of(self.port.berths[0]), self.hull)


class TestWhoseFleet(OrdinaryTestCase):
    """`fleet_of`, which is the same question ownership already answers."""

    def test_it_finds_a_ship_you_own(self):
        self.assertIn(self.hull, ordinary.fleet_of(self.char1))

    def test_it_does_not_find_somebody_elses(self):
        self.assertNotIn(self.hull, ordinary.fleet_of(self.char2))

    def test_it_can_be_asked_for_only_the_laid_up_ones(self):
        self.assertEqual(ordinary.fleet_of(self.char1, laid_up=True), [])
        ordinary.lay_up(self.hull)
        self.assertEqual(ordinary.fleet_of(self.char1, laid_up=True), [self.hull])

    def test_it_can_be_asked_for_only_the_ones_afloat(self):
        self.assertEqual(ordinary.fleet_of(self.char1, laid_up=False), [self.hull])
        ordinary.lay_up(self.hull)
        self.assertEqual(ordinary.fleet_of(self.char1, laid_up=False), [])

    def test_a_captured_prize_made_over_to_you_is_yours(self):
        # Capture is settled by ownership changing hands, so there is no second rule here
        # to get wrong - which is the whole reason this asks `may_command`.
        self.hull.owner = self.char2
        self.assertIn(self.hull, ordinary.fleet_of(self.char2))
        self.assertNotIn(self.hull, ordinary.fleet_of(self.char1))


class TestLayingUpAWholeFleet(OrdinaryTestCase):
    """What a game calls when somebody logs out."""

    def test_it_lays_up_what_it_can(self):
        self.assertEqual(ordinary.lay_up_fleet_of(self.char1), [self.hull])
        self.assertTrue(ordinary.in_ordinary(self.hull))

    def test_it_leaves_a_ship_under_way_alone_and_says_nothing(self):
        self.hull.speed = 3.0
        self.assertEqual(ordinary.lay_up_fleet_of(self.char1), [])
        self.assertFalse(ordinary.in_ordinary(self.hull))

    def test_it_leaves_a_ship_with_a_passenger_aboard_alone(self):
        self.char2.db.prelogout_location = self.hull.ship_rooms[0]
        self.char2.location = None
        self.assertEqual(ordinary.lay_up_fleet_of(self.char1), [])

    def test_it_touches_nobody_elses_ships(self):
        self.hull.owner = self.char2
        self.assertEqual(ordinary.lay_up_fleet_of(self.char1), [])
        self.assertFalse(ordinary.in_ordinary(self.hull))

    def test_somebody_with_no_ships_is_not_an_error(self):
        self.assertEqual(ordinary.lay_up_fleet_of(self.char2), [])


class TestSummonCommand(OrdinaryTestCase):
    """`maritime summon`."""

    def test_it_brings_her_forward(self):
        ordinary.lay_up(self.hull)
        self.call(CmdMaritimeSummon(), "Kittiwake", "Kittiwake is brought forward")
        self.assertFalse(ordinary.in_ordinary(self.hull))
        self.assertTrue(self.hull.docked)

    def test_her_gangway_comes_down(self):
        ordinary.lay_up(self.hull)
        self.call(CmdMaritimeSummon(), "Kittiwake", None)
        self.assertTrue(self.hull.db.gangway)

    def test_it_lists_what_is_laid_up(self):
        ordinary.lay_up(self.hull)
        said = self.call(CmdMaritimeSummon(), "", None)
        self.assertIn("Kittiwake", said)

    def test_it_says_where_your_ships_are_when_none_are_laid_up(self):
        said = self.call(CmdMaritimeSummon(), "", None)
        self.assertIn("Nothing of yours is laid up", said)

    def test_it_wants_a_dock(self):
        ordinary.lay_up(self.hull)
        self.char1.location = self.room1
        self.call(CmdMaritimeSummon(), "Kittiwake", "Ships are built and laid up")
        self.assertTrue(ordinary.in_ordinary(self.hull))

    def test_it_refuses_somebody_elses_ship(self):
        ordinary.lay_up(self.hull)
        self.hull.owner = self.char2
        self.call(CmdMaritimeSummon(), "Kittiwake", "Kittiwake does not answer to you")
        self.assertTrue(ordinary.in_ordinary(self.hull))

    def test_it_refuses_a_ship_that_is_not_laid_up(self):
        self.call(CmdMaritimeSummon(), "Kittiwake", "Kittiwake is not laid up")

    def test_it_refuses_a_ship_that_does_not_exist(self):
        self.call(CmdMaritimeSummon(), "Marie Celeste", "There is no ship called")

    def test_it_refuses_when_the_berths_are_full(self):
        ordinary.lay_up(self.hull)
        other = shipyard.outfit(create.create_object(Vessel, key="Other"), "cutter")
        shipyard.compartments(other, "cutter")
        other.make_fast(self.port, self.port.berths[0])
        self.call(CmdMaritimeSummon(), "Kittiwake", "She cannot lie here")
        self.assertTrue(ordinary.in_ordinary(self.hull))

    def test_it_is_open_to_everybody(self):
        # It only ever acts on ships that already answer to whoever typed it, so there is
        # nothing here for a lock to protect.
        self.assertEqual(CmdMaritimeSummon.locks, "cmd:all()")


class TestLayUpCommand(OrdinaryTestCase):
    """`maritime lay up`."""

    def test_it_lays_her_up(self):
        self.call(CmdMaritimeLayUp(), "Kittiwake", "Kittiwake is laid up")
        self.assertTrue(ordinary.in_ordinary(self.hull))

    def test_it_wants_a_name(self):
        self.call(CmdMaritimeLayUp(), "", "Lay up which ship?")

    def test_it_refuses_somebody_elses(self):
        self.hull.owner = self.char2
        self.call(CmdMaritimeLayUp(), "Kittiwake", "Kittiwake does not answer to you")

    def test_it_passes_on_the_reason_she_cannot_be(self):
        self.hull.speed = 3.0
        self.call(CmdMaritimeLayUp(), "Kittiwake", "Kittiwake is under way")

    def test_it_does_not_need_a_dock(self):
        # Unlike building and summoning. A ship can be laid up from anywhere, because the
        # question is about her and not about where the person asking happens to stand.
        self.char1.location = self.room1
        self.call(CmdMaritimeLayUp(), "Kittiwake", "Kittiwake is laid up")


class TestTheCmdSet(ShipyardTestCase):
    """What a game gets by installing one line."""

    def test_it_holds_all_four(self):
        made = MaritimeShipyardCmdSet()
        made.at_cmdset_creation()
        self.assertEqual(
            {command.key for command in made.commands},
            {
                "maritime build",
                "maritime summon",
                "maritime lay up",
                "maritime player build",
            },
        )

    def test_players_get_summon_and_lay_up_and_nothing_else(self):
        made = MaritimeShipyardCmdSet()
        made.at_cmdset_creation()
        reachable = sorted(one.key for one in made.commands if one.access(self.char2, "cmd"))
        self.assertEqual(reachable, ["maritime lay up", "maritime summon"])

    def test_opening_building_adds_exactly_one(self):
        set_players_may_build(True)
        made = MaritimeShipyardCmdSet()
        made.at_cmdset_creation()
        reachable = sorted(one.key for one in made.commands if one.access(self.char2, "cmd"))
        self.assertEqual(reachable, ["maritime build", "maritime lay up", "maritime summon"])


class TestNamedIsExact(ShipyardTestCase):
    """Finding a ship by name, and only the right one."""

    def setUp(self):
        super().setUp()
        for key in ("Swift", "Swiftsure"):
            hull = create.create_object(Vessel, key=key)
            hull.length, hull.beam, hull.light_draft = 20.0, 6.0, 2.6
            setattr(self, key.lower(), hull)

    def test_it_does_not_match_on_a_prefix(self):
        self.assertIs(named("Swift"), self.swift)

    def test_a_prefix_that_is_nobodys_whole_name_finds_nothing(self):
        # The test above passes even without the exactness check, because Evennia's own
        # search happens to rank an exact match first - so it proves nothing on its own.
        # This one has no exact match to rank, and fails the moment the check is dropped.
        self.swift.delete()
        self.assertIsNone(named("Swift"))
        self.assertIsNone(named("Swifts"))

    def test_it_finds_the_longer_name_too(self):
        self.assertIs(named("Swiftsure"), self.swiftsure)

    def test_it_ignores_case(self):
        self.assertIs(named("SWIFT"), self.swift)

    def test_nothing_is_nothing(self):
        self.assertIsNone(named(""))
        self.assertIsNone(named(None))

    def test_a_room_of_that_name_is_not_a_ship(self):
        create.create_object(ShipRoom, key="Nonesuch")
        self.assertIsNone(named("Nonesuch"))
