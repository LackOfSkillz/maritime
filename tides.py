"""
A sea that moves, and a tide table to predict it by.

`bathymetry` says depth is the water surface less the terrain beneath it, and that moving
the surface changes every depth in the world without touching any ground. That is the whole
argument for tide being a system rather than decoration - and until now the only surface
this contrib shipped was `FlatTideProvider`, which does not move. Every feature authored to
teach a tide - a bar with three metres over it, a rock that dries - had nothing to teach
with.

**The springs and neaps are not scripted.** They fall out of two waves beating against each
other, which is what they are: the moon pulls the sea round the earth about once every 12
hours 25 minutes, the sun about once every 12 hours exactly, and the pair drift in and out
of step over a fortnight. In step, the ranges add and it is springs. Out of step, they
subtract and it is neaps. Nothing here checks a calendar or a phase of the moon; the
fortnightly cycle is a consequence, and it arrives on its own.

    M2 + S2 in step        big range, springs
    M2 + S2 opposed        small range, neaps
    beat period            14.77 days, which nobody wrote down

That matters for the same reason everything else in this contrib is derived rather than
tabulated. A scripted spring-neap cycle is a number a designer has to keep consistent with
the tide it is supposed to describe; a beat is consistent because it is the same arithmetic.

**A tide table is the point of it, not a garnish.** Knowing the water moves is useless; a
harbour with a bar is a place where you must know *when*. `next_high_water` and its
companions search the same function the water is drawn from, so a table can never disagree
with the sea - which is how it goes wrong in a game that stores predictions.

**It is a model, not an ephemeris.** Real prediction uses dozens of constituents with
amplitudes and phases surveyed port by port. Five gets a sea that behaves: two high waters a
day, a fortnightly cycle, a lunar day that slips against the clock, and a diurnal inequality
if a game wants one. The periods are physical constants; the amplitudes belong to the game.
"""

import math

from .bathymetry import DATUM, FlatTideProvider, MaritimeTideProvider

# --- the constituents -------------------------------------------------------
#
# Periods in mean solar hours. These are properties of the solar system rather than
# choices, and every one of them is the time between successive passages of the body
# whose motion drives it.

#: Principal lunar semidiurnal. The main one nearly everywhere: half a lunar day.
M2_HOURS = 12.4206012

#: Principal solar semidiurnal. Half a solar day, exactly - it is what a clock is for.
S2_HOURS = 12.0

#: Larger lunar elliptic semidiurnal. The moon's orbit is not a circle, so it pulls harder
#: at perigee; this is that, and it is why not every spring tide is the same size.
N2_HOURS = 12.6583475

#: Lunisolar diurnal, and principal lunar diurnal. Once a day rather than twice. Where these
#: are large the two daily high waters differ in height, which is the diurnal inequality.
K1_HOURS = 23.9344697
O1_HOURS = 25.8193417

#: The spring-neap beat, in days. Derived, printed nowhere in the arithmetic, and stated
#: here only so the number can be recognised when it shows up in a game.
#:
#:     1 / (1/12.0 - 1/12.4206012) hours = 354.4 hours = 14.77 days
SPRING_NEAP_DAYS = 14.765

#: How the form factor classifies a tide. `(K1 + O1) / (M2 + S2)`, which is the standard
#: way of saying "how much of this tide happens once a day rather than twice".
FORM_SEMIDIURNAL = 0.25
FORM_MIXED_MAINLY_SEMIDIURNAL = 1.5
FORM_MIXED_MAINLY_DIURNAL = 3.0

#: How finely to hunt for a turn of the tide, in seconds, and how far ahead to look before
#: giving up. Five minutes brackets every high water a five-constituent tide can produce -
#: the shortest period here is twelve hours - and the bracket is then refined properly, so
#: this decides only what is *found*, never how accurately.
HUNT_STEP = 300.0
HUNT_HORIZON = 36.0 * 3600.0

#: How close to the turn the refinement gets, in seconds. A second is far finer than any
#: game needs and costs about forty halvings of nothing.
HUNT_PRECISION = 1.0


class Constituent:
    """
    One wave in the tide.

    Attributes:
        name (str): Its conventional symbol - `"M2"`, `"S2"` - for tables and diagnostics.
        period_h (float): How long one cycle takes, in hours.
        amplitude_m (float): Half its range, in metres. A constituent's *range* is twice
            this, which is the number tide tables print and the source of an easy factor
            of two.
        phase_deg (float): Where in its cycle it stands at game time zero.

    """

    __slots__ = ("name", "period_h", "amplitude_m", "phase_deg", "_rate", "_phase")

    def __init__(self, name, period_h, amplitude_m, phase_deg=0.0):
        self.name = name
        self.period_h = float(period_h)
        self.amplitude_m = float(amplitude_m)
        self.phase_deg = float(phase_deg)
        # Worked out once. A tide is sampled every time anything asks for a depth, which
        # on a busy sea is thousands of times a tick.
        self._rate = 2.0 * math.pi / (self.period_h * 3600.0)
        self._phase = math.radians(self.phase_deg)

    def height_at(self, seconds):
        """
        Args:
            seconds (float): Game time.

        Returns:
            height (float): This wave's contribution, in metres, above or below mean level.

        """
        return self.amplitude_m * math.cos(self._rate * seconds - self._phase)

    def __repr__(self):
        return (
            f"Constituent({self.name!r}, {self.period_h}, " f"{self.amplitude_m}, {self.phase_deg})"
        )


class HarmonicTide(MaritimeTideProvider):
    """
    A tide built from waves, the way a real prediction is.

    Notes:
        The sum of a handful of cosines, each turning at its own rate. That is not a
        simplification of tidal theory - it is tidal theory, with a short list where a
        harbour's own survey would have a long one.

        Configure it with `semidiurnal` or `mixed` rather than by hand. A designer knows
        their harbour has four metres at springs and one and a half at neaps, because that
        is what a tide table says; nobody knows their harbour's M2 amplitude.

    """

    def __init__(self, constituents=(), mean_level_m=DATUM, progression=None):
        """
        Args:
            constituents (iterable): The waves to sum.
            mean_level_m (float, optional): The level everything oscillates about. Usually
                the datum; a lake or a flooded region sits above or below it.
            progression (tuple, optional): `(bearing_deg, speed_ms)` - which way the tidal
                wave travels and how fast, so high water reaches one end of a coast before
                the other. None for a tide that turns everywhere at once.

        """
        super().__init__()
        self.constituents = tuple(constituents)
        self.mean_level_m = float(mean_level_m)
        self.progression = progression
        if progression:
            bearing, speed = progression
            if speed <= 0.0:
                raise ValueError(f"A tidal wave must travel somewhere, got {speed!r} m/s.")
            radians = math.radians(bearing)
            # Distance *along* the direction of travel, per metre east and north.
            self._along_e = math.sin(radians) / float(speed)
            self._along_n = math.cos(radians) / float(speed)

    # --- building one -------------------------------------------------------

    @classmethod
    def semidiurnal(cls, spring_range_m, neap_range_m, mean_level_m=DATUM, **kwargs):
        """
        The ordinary tide: two highs and two lows a day, springs every fortnight.

        Args:
            spring_range_m (float): Low water to high water at springs, in metres. The
                number a tide table prints.
            neap_range_m (float): The same at neaps.
            mean_level_m (float, optional): What it oscillates about.

        Returns:
            tide (HarmonicTide): Ready to hand to a map provider.

        Raises:
            ValueError: If neaps are not smaller than springs, which is what the words
                mean - springs are when the ranges add and neaps when they subtract, so a
                neap range larger than the spring one describes no sea that exists.

        Notes:
            Solved rather than fitted. With the solar wave adding to the lunar one at
            springs and opposing it at neaps:

                spring range = 2 * (M2 + S2)
                neap range   = 2 * (M2 - S2)

            which inverts exactly, so a game gets the two numbers it asked for and not an
            approximation of them.

        """
        if neap_range_m > spring_range_m:
            raise ValueError(
                f"Neaps ({neap_range_m} m) cannot exceed springs ({spring_range_m} m) - "
                "springs are when the lunar and solar tides add."
            )
        lunar = (spring_range_m + neap_range_m) / 4.0
        solar = (spring_range_m - neap_range_m) / 4.0
        return cls(
            (
                Constituent("M2", M2_HOURS, lunar),
                Constituent("S2", S2_HOURS, solar),
                # The moon's elliptic term, at its usual share of M2. Small, and the reason
                # one spring tide is bigger than the next rather than every one alike.
                Constituent("N2", N2_HOURS, lunar * 0.19),
            ),
            mean_level_m=mean_level_m,
            **kwargs,
        )

    @classmethod
    def mixed(cls, spring_range_m, neap_range_m, form=0.8, mean_level_m=DATUM, **kwargs):
        """
        A tide whose two daily high waters are not the same height.

        Args:
            spring_range_m (float): As for `semidiurnal`.
            neap_range_m (float): As for `semidiurnal`.
            form (float, optional): The form factor, `(K1 + O1) / (M2 + S2)`. Below 0.25 is
                a plain semidiurnal tide; above 3 the sea rises and falls once a day.
            mean_level_m (float, optional): What it oscillates about.

        Returns:
            tide (HarmonicTide): With diurnal constituents sized to the form factor asked
                for, so `form_factor()` returns what was requested.

        Notes:
            Worth having because it changes the game rather than the scenery. Where the two
            daily highs differ, one of them may not float a hull over the bar and the other
            may - so "wait for high water" stops being a single instruction.

        """
        base = cls.semidiurnal(spring_range_m, neap_range_m, mean_level_m=mean_level_m, **kwargs)
        semidiurnal = sum(
            part.amplitude_m for part in base.constituents if part.name in ("M2", "S2")
        )
        diurnal = float(form) * semidiurnal
        return cls(
            base.constituents
            + (
                Constituent("K1", K1_HOURS, diurnal * 0.62),
                Constituent("O1", O1_HOURS, diurnal * 0.38),
            ),
            mean_level_m=mean_level_m,
            **kwargs,
        )

    # --- what the water is doing --------------------------------------------

    def surface_z_at(self, position, game_time):
        """
        Elevation of the water surface at a point and time.

        Args:
            position (WorldPosition): Where. Used only if this tide progresses along a
                coast; otherwise the sea turns everywhere at once.
            game_time (float): Game time in seconds.

        Returns:
            surface_z (float): Metres relative to the world datum.

        """
        return self.height_at(self._local_time(position, game_time))

    def height_at(self, seconds):
        """
        Args:
            seconds (float): Game time, already adjusted for any progression.

        Returns:
            height (float): The surface elevation, in metres.

        """
        total = self.mean_level_m
        for part in self.constituents:
            total += part.height_at(seconds)
        return total

    def _local_time(self, position, game_time):
        """
        Args:
            position (WorldPosition): Where.
            game_time (float): Game time in seconds.

        Returns:
            seconds (float): The time this place experiences.

        Notes:
            A tidal wave is a wave: it arrives somewhere first. Running the tide earlier at
            the far end is the same thing as running the clock later here, so a progression
            costs two multiplies rather than a second model.

        """
        if not self.progression or position is None:
            return game_time
        return game_time - (position.x * self._along_e + position.y * self._along_n)

    def is_rising(self, position, game_time):
        """
        Args:
            position (WorldPosition): Where.
            game_time (float): Game time in seconds.

        Returns:
            rising (bool): Whether the water is making rather than falling.

        Notes:
            The question a grounded hull asks. She comes off on a making tide and settles
            harder on a falling one, and the difference is the difference between an hour's
            embarrassment and a lost ship.

        """
        seconds = self._local_time(position, game_time)
        return self.height_at(seconds + 60.0) > self.height_at(seconds)

    # --- what it is like ----------------------------------------------------

    def amplitude_of(self, *names):
        """
        Args:
            *names (str): Constituent symbols.

        Returns:
            total (float): Their amplitudes summed, in metres.

        """
        wanted = set(names)
        return sum(part.amplitude_m for part in self.constituents if part.name in wanted)

    def spring_range(self):
        """
        Returns:
            range (float): Low water to high water at springs, in metres.

        Notes:
            The conventional figure, `2 * (M2 + S2)`, which is what a tide table means by
            "springs". The sea will exceed it now and then and that is not an error: the
            elliptic term adds when the moon is near perigee, so the biggest springs of the
            year run higher than the nominal range. A tide whose every spring was identical
            would be the one worth suspecting.

        """
        return 2.0 * self.amplitude_of("M2", "S2")

    def neap_range(self):
        """
        Returns:
            range (float): The same at neaps - the lunar tide less the solar one.

        """
        return 2.0 * abs(self.amplitude_of("M2") - self.amplitude_of("S2"))

    def form_factor(self):
        """
        Returns:
            factor (float): `(K1 + O1) / (M2 + S2)`, the standard classification.

        Notes:
            Below 0.25 the tide is semidiurnal; above 3 it is diurnal; between, mixed. A
            tide with no semidiurnal constituents at all is infinitely diurnal, and answers
            infinity rather than dividing by zero - which is the honest answer and not an
            error, since a purely diurnal tide is a real thing.

        """
        semidiurnal = self.amplitude_of("M2", "S2")
        if semidiurnal <= 0.0:
            return math.inf
        return self.amplitude_of("K1", "O1") / semidiurnal

    def describes(self):
        """
        Returns:
            kind (str): What a pilot book would call this tide.

        """
        factor = self.form_factor()
        if factor < FORM_SEMIDIURNAL:
            return "semidiurnal"
        if factor < FORM_MIXED_MAINLY_SEMIDIURNAL:
            return "mixed, mainly semidiurnal"
        if factor < FORM_MIXED_MAINLY_DIURNAL:
            return "mixed, mainly diurnal"
        return "diurnal"

    # --- the tide table -----------------------------------------------------

    def next_high_water(self, after, position=None):
        """
        Args:
            after (float): Game time to search from, in seconds.
            position (WorldPosition, optional): Where, if the tide progresses.

        Returns:
            turn (tuple or None): `(game_time, height)` of the next high water, or None if
                none was found inside the search horizon - which happens only for a tide
                with no constituents, since a real one turns twice a day.

        """
        return self._next_turn(after, position, rising=True)

    def next_low_water(self, after, position=None):
        """
        Args:
            after (float): Game time to search from, in seconds.
            position (WorldPosition, optional): Where, if the tide progresses.

        Returns:
            turn (tuple or None): `(game_time, height)` of the next low water.

        """
        return self._next_turn(after, position, rising=False)

    def table(self, after, entries=4, position=None):
        """
        The next several turns of the tide, high and low alike.

        Args:
            after (float): Game time to start from, in seconds.
            entries (int, optional): How many turns to predict.
            position (WorldPosition, optional): Where, if the tide progresses.

        Returns:
            turns (tuple): Each `(game_time, height, "high"|"low")`, in order.

        Notes:
            Searched, not stored. A stored prediction is a second source of truth about the
            sea, and the failure mode is a tide table that is subtly wrong - which is worse
            than none, because a captain plans against it.

        """
        turns = []
        when = after
        for _ in range(max(0, int(entries))):
            high = self.next_high_water(when, position)
            low = self.next_low_water(when, position)
            found = [turn for turn in ((high, "high"), (low, "low")) if turn[0]]
            if not found:
                break
            (seconds, height), state = min(found, key=lambda pair: pair[0][0])
            turns.append((seconds, height, state))
            when = seconds + HUNT_STEP
        return tuple(turns)

    def _next_turn(self, after, position, rising):
        """
        Args:
            after (float): Game time to search from.
            position (WorldPosition): Where, if the tide progresses.
            rising (bool): True for a high water, False for a low.

        Returns:
            turn (tuple or None): `(game_time, height)`.

        Notes:
            Bracket, then refine. Walking in five-minute steps finds the interval a turn
            lies in - twelve hours is the shortest period here, so no turn can hide between
            two samples - and the turn itself is then found by closing on the point where
            the water stops moving. The step decides what is found; the refinement decides
            how precisely, and the two are deliberately separate so that making the search
            cheaper cannot quietly make it wrong.

        """
        if not self.constituents:
            return None

        offset = self._local_time(position, 0.0) if position is not None else 0.0

        def height(seconds):
            return self.height_at(seconds + offset)

        sign = 1.0 if rising else -1.0
        previous = height(after)
        walking_up = None
        when = after + HUNT_STEP
        while when <= after + HUNT_HORIZON:
            current = height(when)
            climbing = (current - previous) * sign > 0.0
            if walking_up and not climbing:
                return self._close_on(height, when - 2.0 * HUNT_STEP, when, sign)
            walking_up = climbing
            previous = current
            when += HUNT_STEP
        return None

    @staticmethod
    def _close_on(height, low, high, sign):
        """
        Args:
            height (callable): Water level at a game time.
            low (float): Start of the bracket.
            high (float): End of it.
            sign (float): 1 for a maximum, -1 for a minimum.

        Returns:
            turn (tuple): `(game_time, height)` of the extremum inside the bracket.

        Notes:
            Ternary search. The water has exactly one turning point in the bracket, so
            comparing two interior samples always discards a third of what is left, and it
            needs no derivative - which matters, because the derivative of a sum of cosines
            is easy to write and easy to write with a sign error.

        """
        while high - low > HUNT_PRECISION:
            first = low + (high - low) / 3.0
            second = high - (high - low) / 3.0
            if height(first) * sign < height(second) * sign:
                low = first
            else:
                high = second
        when = (low + high) / 2.0
        return (when, height(when))

    def __repr__(self):
        return (
            f"HarmonicTide({self.describes()}, springs {self.spring_range():.2f} m, "
            f"neaps {self.neap_range():.2f} m)"
        )


class RegionalWater(MaritimeTideProvider):
    """
    One sea, and inland waters that keep their own level.

    Notes:
        A pond is not a bay. It sits at whatever height its valley holds it at, it does not
        rise and fall with the sea, and the only reason it is difficult is that a world has
        one datum and the pond is nowhere near it.

        `WorldPosition` has carried a `region` since the beginning and nothing was using it
        for water. This is what it is for: the sea answers for everywhere by default, and a
        named region answers for itself.

            RegionalWater(
                sea=HarmonicTide.semidiurnal(4.0, 1.5),
                waters={"the pond": FlatTideProvider(surface_z=11.0)},
            )

        Each inland water is a full tide provider rather than a number, so a lake can have a
        seiche, a reservoir can be drawn down over a season, and a tidal lagoon behind a sill
        can have a tide of its own that lags the sea outside it. A float would have made the
        common case one character shorter and the interesting cases impossible.

        **It changes no depth arithmetic.** Depth is still surface less terrain; this only
        answers the surface question differently depending on where it is asked. A pond
        eleven metres up with a floor at eight has three metres in it by exactly the same
        subtraction that gives a harbour its nine.

    """

    def __init__(self, sea=None, waters=None):
        """
        Args:
            sea (MaritimeTideProvider, optional): What answers for everywhere not named.
                Defaults to a motionless surface at the datum.
            waters (dict, optional): Region name to the provider that answers for it.

        """
        super().__init__()
        self.sea = sea or FlatTideProvider()
        self.waters = dict(waters or {})

    def surface_z_at(self, position, game_time):
        """
        Elevation of the water surface at a point and time.

        Args:
            position (WorldPosition): Where. Its region decides which water answers.
            game_time (float): Game time in seconds.

        Returns:
            surface_z (float): Metres relative to the world datum.

        """
        inland = self.waters.get(getattr(position, "region", None))
        if inland is None:
            return self.sea.surface_z_at(position, game_time)
        return inland.surface_z_at(position, game_time)

    def water_for(self, region):
        """
        Args:
            region (str): A region name.

        Returns:
            water (MaritimeTideProvider): Whatever answers for it - the named water if there
                is one, otherwise the sea.

        Notes:
            So a tide table can be asked for about the right body of water. Asking the sea
            for the pond's high water would produce a confident and entirely wrong answer.

        """
        return self.waters.get(region, self.sea)

    def __repr__(self):
        return f"RegionalWater(sea={self.sea!r}, waters={sorted(self.waters)})"


__all__ = (
    "M2_HOURS",
    "S2_HOURS",
    "N2_HOURS",
    "K1_HOURS",
    "O1_HOURS",
    "SPRING_NEAP_DAYS",
    "Constituent",
    "HarmonicTide",
    "RegionalWater",
)
