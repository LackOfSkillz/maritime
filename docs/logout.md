# LOGOUT-001: what happens when a passenger disconnects

A spike, not a design. The question was listed as open because guessing at it would have
been cheap now and expensive later, and because passenger persistence, flooding and vessel
destruction all depend on the answers. Everything below was measured against Evennia 6.1
rather than reasoned about, and every claim is pinned in `tests/test_logout.py` so that a
change in the engine shows up as a failing test rather than as a missing passenger.

---

## The short version

| Question | Answer |
| --- | --- |
| Does an unpuppeted character stay in its room? | **No.** It is taken off the grid entirely — `location` becomes `None`. |
| Is it in the room's `contents`? | **No.** Not in any room's contents. |
| Does reconnect restore location? | **Yes**, from `db.prelogout_location`, else `home`. |
| What if that room is gone? | The attribute reads back as `None` and they go **home, silently**. |
| And with no home either? | They stay at `location = None` and the account is told so. |
| Which hooks fire on logout? | **None.** |
| Which fire on login? | `at_object_receive` on the room, called explicitly. |

---

## What Evennia actually does

`DefaultCharacter.at_post_unpuppet` runs when the *last* session controlling a character
goes away — an ordinary logout, going OOC, or being dropped link-dead. A character with
another session still attached is left where it is.

```python
if not self.sessions.count():
    if self.location:
        # ... announce "X has left the game" to the room ...
        self.db.prelogout_location = self.location
        self.location = None
```

Two things matter here and neither is obvious from the outside.

**The character leaves the world, not just the session.** `location = None` puts them
nowhere at all. They are not in the cabin, not on the ship, not in the sea. Asking this
contrib's resolver where they are returns `NoWorldPosition`, which is the correct answer
and a surprising one if you expected a sleeping body in a bunk.

**No move hooks fire.** Evennia's `location` setter updates the foreign key, saves, and
fixes the contents cache — that is all. It is not `move_to`, so `at_object_leave` never
runs. On the way back in, `at_pre_puppet` calls `at_object_receive` explicitly:

```python
if self.location is None:
    location = self.db.prelogout_location if self.db.prelogout_location else self.home
    if location:
        self.location = location
        self.location.at_object_receive(self, None)
```

So a room hears people arrive and never hears them leave. **Anything that counts who is
aboard from move hooks will over-count by exactly the number of players who logged out
there.**

---

## What this means for a ship

### The good news, and it is genuinely good

A passenger who logs out in a cabin off one coast and back in a week later is put back in
the same cabin — which by then is wherever the ship has sailed. Nothing stored a coordinate
for them, and nothing had to.

That falls out of the architecture for free. Because a `ShipRoom` holds no position and
resolves through to its hull, a *stale room reference is not a stale position*. Had ships
been moving rooms, or had passengers carried coordinates, this would have needed a
reconciliation pass on every login, and the failure mode would have been players
materialising in open water where their ship used to be.

Measured: logged out at x=1000, ship sailed to x=5000, logged in — resolved position 5000.

### The bad news, and it is worse than it looks

**`room.contents` is not the list of people aboard.** An offline passenger is in no room's
contents at all. Every obvious way of asking "who is on this ship" misses them:

```python
[obj for room in vessel.ship_rooms for obj in room.contents]   # misses every offline player
```

The architecture already carries an invariant about this:

> Ship rooms are never deleted while occupants or contents remain unresolved.

That invariant is **unenforceable by looking at contents**, which is exactly how somebody
would try to enforce it. This spike is why `absent_from(room)` and `Vessel.ships_company()`
now exist: they find the stowed-away characters by querying for off-grid objects whose
`prelogout_location` names the room.

**A deleted room sends everyone home, silently.** When the room row is gone, the
`prelogout_location` attribute reads back as `None`, so `at_pre_puppet` falls through to
`home`. A vessel that founders and is broken up therefore teleports every offline passenger
to their home room, with no message, no event, and nothing to hook.

That is a *policy*, arrived at by accident. It is recorded in `DECISIONS.md` as the offline
loss question, now with the engine's actual behaviour attached instead of a guess.

**No home is a stuck character.** With neither a remembered room nor a home, the character
stays at `location = None` and the account gets a red message. Worth knowing that the engine
does not invent a destination.

---

## What this contrib does about it

Nothing that presumes a policy. Two helpers, both of which only answer questions:

- `rooms.absent_from(room)` — characters whose last location was this room.
- `rooms.everyone_in(room)` — its contents plus those, exits excluded.
- `Vessel.ships_company()` — the same across every compartment, which is the list that has
  to be resolved before a hull is ever broken up.

`absent_from` is an indexed query for off-grid objects followed by a check in Python. The
set of logged-out characters is small, and filtering on the attribute *value* would mean
matching Evennia's own packing of an object reference — an implementation detail rather
than a promise.

---

## What is still open

Not answered here, because it is not an engine question:

- **What should happen** to an offline passenger aboard a vessel that founders. Drowned,
  saved, put ashore, held in limbo until they log in? The engine's default is "sent home
  without being told", and no game should end up with that by not choosing.
- **Whether logging out at sea should be allowed at all**, or should beach a character in
  a safe-harbour sense the way some games handle it.

Both are in `DECISIONS.md`.
