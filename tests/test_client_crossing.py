"""
Tests for crossing between one situation and another.

A gangway, a quay, a ship swapped for a different ship. The moment of the crossing is
where this interface has been wrong most often, because it is the one moment when what
the client is holding and what the server believes it is holding can part company - and
neither side notices, because each is separately consistent.

Kept apart from `test_client_protocol` because that file had grown past the line ceiling
and this is a real seam rather than a convenient one: everything here is about a
transition, and nothing there is.

"""

from ..client import refresh
from ..client.payloads import CHART, STATUS
from .test_client_protocol import ClientTestCase, FakeSession, hello


class TestComingBackAboard(ClientTestCase):
    """
    **A change of mode rebuilds the client's panels, so the server must stop believing
    the client still holds what it was last sent.**

    Seen in play: a captain went ashore, came back to his ship, and the board reported
    "awaiting report" with every reading blank while the chart drew perfectly. The mode
    had switched, the panels had been rebuilt empty, and the next tick compared her
    instruments against what the *old* panels had been holding, found them identical,
    and sent nothing. A ship lying quiet produces the same numbers for hours, so nothing
    was ever going to shift and the board was never going to fill in.

    It is not a teleport bug. Walking back up the gangway does exactly the same thing.

    """

    def a_listening_session(self):
        """A session that has announced itself and can draw everything."""
        session = FakeSession(puppet=self.char1)
        hello(session)
        return session

    def test_the_reading_it_was_holding_is_replaced(self):
        """
        Not merely forgotten. Clearing the cache is what stops the resend being suppressed;
        sending on arrival is what fills the board. Either alone leaves it blank.

        """
        self.aboard()
        session = self.a_listening_session()
        stale = {"a reading": "already on screen"}
        session.ndb.maritime_status = stale

        self.ashore()
        refresh(session)
        self.aboard()
        refresh(session)

        self.assertNotEqual(session.ndb.maritime_status, stale)
        self.assertIn("motion", session.ndb.maritime_status or {})

    def test_and_the_sheet_is_replaced_rather_than_merely_forgotten(self):
        """
        Forgetting it is only half. A board cleared and then left empty until something
        happens to move a number is the same blank screen by another route - so she hands
        over her instruments the moment somebody arrives on her deck, and the stamp that
        comes back is a real one for the sheet just sent.

        """
        self.aboard()
        session = self.a_listening_session()
        stale = ("a sheet", "already on screen")
        session.ndb.maritime_chart_stamp = stale

        self.ashore()
        refresh(session)
        self.aboard()
        session.sent = []
        refresh(session)

        self.assertNotEqual(session.ndb.maritime_chart_stamp, stale)
        self.assertIn(CHART, session.kinds())

    def test_and_her_readings_arrive_with_it(self):
        """
        The whole complaint, from the other end: the mode switched, the panels were
        rebuilt, and nothing filled them in. A ship lying quiet never would.

        """
        self.aboard()
        session = self.a_listening_session()

        self.ashore()
        refresh(session)
        self.aboard()
        session.sent = []
        refresh(session)

        self.assertIn(STATUS, session.kinds())

    def test_going_the_other_way_forgets_them_too(self):
        """Stepping ashore rebuilds the panels just as thoroughly."""
        self.aboard()
        session = self.a_listening_session()
        session.ndb.maritime_status = {"a reading": "already on screen"}

        self.ashore()
        refresh(session)

        self.assertIsNone(session.ndb.maritime_status)

    def test_but_walking_about_aboard_keeps_them(self):
        """
        A mover who has not changed mode still has her panels in front of her, and
        clearing these would redraw the board on every step along a deck - which would
        steal focus from somebody trying to read it.

        """
        self.aboard()
        session = self.a_listening_session()
        held = {"a reading": "already on screen"}
        session.ndb.maritime_status = held

        refresh(session)

        self.assertEqual(session.ndb.maritime_status, held)
