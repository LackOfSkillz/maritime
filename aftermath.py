"""
The butcher's bill.

While a fight is happening, a casualty is one number: how many are off their feet. That is
the right amount of detail at the time, because nobody aboard is counting. Afterwards it is
the wrong amount, because the four things that number contains have completely different
futures.

    dead        gone, and her complement is smaller for ever
    wounded     down for days, and some of them will not come back
    dazed       knocked about, and on their feet again within the hour
    shirkers    unhurt, and they broke

**The split is a fact about the crew, not about the fight.** A crack company's shaken men are
dazed and back at their guns; a pressed one's are below and not coming up. Same shot, same
number, different ship - which is the sharpest statement the quality axis makes anywhere in
this contrib, and it costs nothing because the axis was already there.

**Shirkers are the part the source stops short of.** It counts them and moves on. Here they
are a decision: a captain can start them back to their duty and be held to have done it, or
he can let it go and be a man short until their nerve returns. Neither is free.

    punish      they are back on their feet now, and the company holds it against you
    let it go   no grievance, and you are short of hands until they come round

The grievance machinery is already built and already watching - `BUTCHERED` has been a
grievance since the morale work - so this closes the loop between a battle and a mutiny
without a line of new wiring.

**We never decide that a player is hurt.** What this publishes is the *fraction*: she took
thirty-eight per cent. A game rolls its own people against that if it wants to, and this
contrib stays out of a character system it does not own.

"""

from dataclasses import dataclass, replace

from .events import Event, bus
from .results import Result

#: The share of a butcher's bill that is dead before anybody looks at them.
KILLED_OUTRIGHT = 0.2

#: The share that is wounded - properly hurt, and down for days.
WOUNDED_SHARE = 0.4

#: What a surgeon can move from the first column to the second, at his best.
#:
#: A third. It is the largest single thing anybody aboard can do for the bill, and it is why
#: a ship with a surgeon is a different proposition from one without.
SURGEON_SAVES = 0.33

#: How long a wound keeps a man off his feet, in seconds.
#:
#: Three days. Long enough that a captain who has been in a hard action is short-handed for
#: the passage home rather than for the next watch, which is the whole difference between a
#: wound and a bruise.
WOUNDED_RECOVER = 3.0 * 24.0 * 3600.0

#: How long it takes a shirker to find his nerve again if nobody makes him.
#:
#: A day. Shorter than a wound, because there is nothing physically wrong with him - and
#: still long enough that letting it go is a real cost rather than a free choice.
NERVE_RETURNS = 24.0 * 3600.0

DEAD = "dead"
WOUNDED = "wounded"
DAZED = "dazed"
SHIRKERS = "shirkers"
KINDS = (DEAD, WOUNDED, DAZED, SHIRKERS)

NO_CASUALTIES = "no_casualties"
NO_SHIRKERS = "no_shirkers"
NOT_COUNTED = "not_counted"


@dataclass(frozen=True, kw_only=True)
class BillCounted(Event):
    """
    A butcher's bill has been made up.

    Attributes:
        vessel (object): The hull.
        fraction (float): What she lost, as a share of her complement.
        dead (int): How many are gone.
        wounded (int): How many are down and will be for days.
        dazed (int): How many were back on their feet at once.
        shirkers (int): How many were unhurt and would not fight.

    Notes:
        The fraction is the field this exists for. A game that models its own people rolls
        them against it; a game that does not can ignore every other field here and still
        know how hard she was hit.

    """

    vessel: object
    fraction: float = 0.0
    dead: int = 0
    wounded: int = 0
    dazed: int = 0
    shirkers: int = 0


@dataclass(frozen=True, kw_only=True)
class ButchersBill(Result):
    """
    What a casualty count turned out to contain.

    Attributes:
        dead (int): Gone, and her complement is smaller.
        wounded (int): Down for days.
        dazed (int): Back on their feet at once.
        shirkers (int): Unhurt, and they broke.
        counted (int): How many the bill was made up from.
        fraction (float): What that was, as a share of her complement.
        saved (int): How many the surgeon moved out of the first column.

    """

    dead: int = 0
    wounded: int = 0
    dazed: int = 0
    shirkers: int = 0
    counted: int = 0
    fraction: float = 0.0
    saved: int = 0

    @property
    def lost_for_good(self):
        """
        Returns:
            lost (int): How many she will never see again.

        """
        return self.dead


def resolve(casualties, quality, surgeon=0.0):
    """
    Sort a casualty count into the four things it contains.

    Args:
        casualties (int): How many were off their feet.
        quality (CrewQuality): What they are made of.
        surgeon (float, optional): How well she is doctored, 0 to 1.

    Returns:
        bill (ButchersBill): The four columns. Failed if there was nobody to count.

    Notes:
        **Steadiness decides dazed against shirkers**, and `base_morale` is already that
        number - what men of this quality will stand before they break. So a crack crew
        turns almost all of its shaken men into dazed and a pressed crew turns most of
        them into shirkers, from a value that was set for a different purpose and happens
        to be exactly right for this one.

        Rounding is done by taking each column off the total in turn rather than by
        rounding four fractions independently, because four independent roundings do not
        add up to the number you started with and a bill that does not balance is a bug
        somebody will find in the field rather than here.

    """
    counted = max(0, int(casualties))
    if not counted:
        return ButchersBill(success=False, code=NO_CASUALTIES)

    dead = int(counted * KILLED_OUTRIGHT)
    saved = int(dead * SURGEON_SAVES * max(0.0, min(1.0, surgeon)))
    dead -= saved

    wounded = int(counted * WOUNDED_SHARE) + saved
    shaken = counted - dead - wounded

    steadiness = max(0.0, min(1.0, getattr(quality, "base_morale", 0.5)))
    dazed = int(shaken * steadiness)
    shirkers = shaken - dazed

    return ButchersBill(
        success=True,
        dead=dead,
        wounded=wounded,
        dazed=dazed,
        shirkers=shirkers,
        counted=counted,
        saved=saved,
    )


class CountsTheCost:
    """
    A hull that can make up her butcher's bill after an action.

    Notes:
        Nothing here happens on its own. Making up the bill is something somebody does when
        the firing stops, and a contrib that did it automatically would be deciding when a
        battle was over - which is a judgement, and not one it can make.

    """

    def at_object_creation(self):
        """Set up this part of a newly created vessel."""
        super().at_object_creation()
        self.db.shirkers = 0
        self.db.wounded = 0
        self.db.wounded_until = 0.0
        self.db.nerve_until = 0.0
        self.db.punished = False

    @property
    def shirkers(self):
        """
        Returns:
            shirkers (int): How many are unhurt and will not fight.

        """
        return int(self.db.shirkers or 0)

    @property
    def wounded(self):
        """
        Returns:
            wounded (int): How many are down and will be for days.

        """
        return int(self.db.wounded or 0)

    @property
    def punished_them(self):
        """
        Returns:
            punished (bool): Whether the shirkers were started back to their duty.

        Notes:
            Read by the morale layer. A captain who did it got his hands back and is held
            to have done it, which is the trade the whole decision is about.

        """
        return bool(self.db.punished)

    def count_the_cost(self, surgeon=0.0):
        """
        Make up the butcher's bill.

        Args:
            surgeon (float, optional): How well she is doctored, 0 to 1.

        Returns:
            bill (ButchersBill): The four columns, or a failure if nobody was hurt.

        Notes:
            **The dazed are put back at once and the dead are struck off her complement**,
            so a ship that has counted her cost is a smaller ship afterwards and not merely
            a bruised one. The wounded and the shirkers stay off her books until time or a
            decision brings them back.

        """
        company = self.company
        if company is None:
            return ButchersBill(success=False, code=NOT_COUNTED)

        bill = resolve(company.casualties, company.quality, surgeon)
        if not bill:
            return bill

        now = self._cost_now()
        # The dead leave her complement rather than merely her muster. Everything derived
        # from complement - her strength, what she can crew, what her pumps can do - shrinks
        # with her, because it is all read from the one number.
        #
        # Through `replace` on the aggregate, and the divisions are left as they were. That
        # is the convention `hurt` and `recover` already set: the company's own complement
        # and fit are what everything reads, and the divisions ride alongside as a view for
        # boarding. Being stricter here than those two are would put this module out of step
        # with the module it is amending.
        company = replace(company, complement=max(0, company.complement - bill.dead))
        self.company = company.recover(bill.dazed)

        self.db.wounded = self.wounded + bill.wounded
        self.db.shirkers = self.shirkers + bill.shirkers
        if bill.wounded:
            self.db.wounded_until = now + WOUNDED_RECOVER
        if bill.shirkers:
            self.db.nerve_until = now + NERVE_RETURNS

        fraction = bill.counted / company.complement if company.complement else 1.0
        bus().publish(
            BillCounted(
                game_time=now,
                vessel=self,
                fraction=fraction,
                dead=bill.dead,
                wounded=bill.wounded,
                dazed=bill.dazed,
                shirkers=bill.shirkers,
            )
        )
        return ButchersBill(
            success=True,
            dead=bill.dead,
            wounded=bill.wounded,
            dazed=bill.dazed,
            shirkers=bill.shirkers,
            counted=bill.counted,
            saved=bill.saved,
            fraction=fraction,
        )

    def punish_shirkers(self):
        """
        Start them back to their duty.

        Returns:
            bill (ButchersBill): How many went back, or a failure if there were none.

        Notes:
            **They are on their feet now, and the company holds it against you.** That is
            the entire trade: a captain short of hands in the middle of something gets them
            back immediately and pays for it in a currency that does not come due until
            later. The grievance is read by morale, which already knows what to do with one.

        """
        shirkers = self.shirkers
        if not shirkers:
            return ButchersBill(success=False, code=NO_SHIRKERS)

        company = self.company
        if company is not None:
            self.company = company.recover(shirkers)
        self.db.shirkers = 0
        self.db.nerve_until = 0.0
        self.db.punished = True
        return ButchersBill(success=True, shirkers=shirkers)

    def let_it_go(self):
        """
        Say nothing, and be a man short until their nerve returns.

        Returns:
            bill (ButchersBill): How many are still below.

        Notes:
            The other half of the trade. No grievance, and no hands either - which is the
            honest cost of mercy in the middle of a fight, and a real reason to choose the
            other one.

        """
        shirkers = self.shirkers
        if not shirkers:
            return ButchersBill(success=False, code=NO_SHIRKERS)
        self.db.punished = False
        return ButchersBill(success=True, shirkers=shirkers)

    def stand_watch_over_the_hurt(self, now=None):
        """
        Let time bring back whoever it is going to bring back.

        Args:
            now (float, optional): Game time. Fetched if not given.

        Returns:
            back (int): How many returned to duty.

        Notes:
            Called from the watch, so a ship that has been hurt gets her people back over
            days without anybody ordering it. The wounded and the shirkers come back on
            different clocks because they are down for different reasons.

        """
        now = self._cost_now() if now is None else float(now)
        back = 0

        until = float(self.db.wounded_until or 0.0)
        if self.wounded and until and now >= until:
            back += self.wounded
            self.db.wounded = 0
            self.db.wounded_until = 0.0

        until = float(self.db.nerve_until or 0.0)
        if self.shirkers and until and now >= until:
            back += self.shirkers
            self.db.shirkers = 0
            self.db.nerve_until = 0.0

        if back:
            company = self.company
            if company is not None:
                self.company = company.recover(back)
        return back

    def _cost_now(self):
        """
        Returns:
            now (float): Game time in seconds.

        """
        from . import config

        return config.time_provider().now()
