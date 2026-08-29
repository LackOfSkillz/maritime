"""
Structured results returned by domain operations.

Every meaningful maritime operation returns a `Result`, never a string and never a
message sent to a player. A separate messaging layer turns these into prose, which is
what lets a game replace the wording entirely - including for different observers of
the same event, where a captain, a deck hand and a lookout each need a different
sentence about one hull breach.

A result says *what happened*, in terms a program can branch on:

    ```python
    result = sailing.trim(vessel, sail_plan)
    if not result:
        renderer.explain_failure(result.code, observer)
    ```

Subclass it to carry the specifics of an operation:

    ```python
    @dataclass(frozen=True, kw_only=True)
    class ManeuverResult(Result):
        heading_change: float = 0.0
        speed_change: float = 0.0
        heel: float = 0.0
    ```

Deliberately absent: any free-form `details` dictionary. A grab-bag field is where
structure goes to die - it starts as convenience and ends as an undocumented protocol
that no renderer can rely on. Declare real fields instead.

"""

from dataclasses import dataclass, replace

# Failure codes shared across operations. Operation-specific codes belong beside the
# operation that raises them, not here; this holds only the genuinely universal ones.
NOT_PERMITTED = "not_permitted"
PRECONDITION_FAILED = "precondition_failed"
INVALID_TARGET = "invalid_target"
UNSUPPORTED = "unsupported"


@dataclass(frozen=True, kw_only=True)
class Result:
    """
    The outcome of a domain operation.

    Frozen, so a result cannot be edited after the fact and passed on as though it
    were something the simulation produced. Keyword-only, so subclasses can add
    fields with defaults without colliding with the base class's field order - the
    usual dataclass inheritance trap.

    Attributes:
        success (bool): Whether the operation did what was asked.
        code (str): Machine-readable outcome. Required on failure, so a caller
            always has something to branch on and a renderer always has something
            to translate. Optional on success, for outcomes worth distinguishing
            (a partial success, an order accepted but deferred).

    """

    success: bool
    code: str = ""

    def __post_init__(self):
        """
        Reject a failure that does not say why.

        A failed result with no code cannot be rendered, logged usefully, or
        branched on - it is indistinguishable from every other failure, which is
        exactly when a caller most needs to tell them apart.

        """
        if not self.success and not self.code:
            raise ValueError("A failed Result must carry a code explaining why.")

    def __bool__(self):
        """
        Truthiness follows success, so `if not result:` reads naturally.

        Returns:
            success (bool): Whether the operation succeeded.

        """
        return self.success

    @classmethod
    def ok(cls, **kwargs):
        """
        Build a successful result.

        Args:
            **kwargs: Any fields declared by this class or a subclass.

        Returns:
            result (Result): A successful result of this class.

        """
        return cls(success=True, **kwargs)

    @classmethod
    def failed(cls, code, **kwargs):
        """
        Build a failed result.

        Args:
            code (str): Machine-readable reason. Required.
            **kwargs: Any fields declared by this class or a subclass.

        Returns:
            result (Result): A failed result of this class.

        """
        return cls(success=False, code=code, **kwargs)

    def with_fields(self, **kwargs):
        """
        A copy of this result with some fields replaced.

        Args:
            **kwargs: Fields to override.

        Returns:
            result (Result): A new result; this one is unchanged.

        Notes:
            Results are frozen, so enriching one as it passes through a layer means
            producing a new value rather than mutating the original. That keeps the
            thing a lower layer returned intact for anyone still holding it.

        """
        return replace(self, **kwargs)
