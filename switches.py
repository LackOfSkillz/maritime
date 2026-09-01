"""
The switches somebody running the game flips at runtime, and where they are kept.

Five of them, and they have nothing in common except when they are used - which is why they
are here together rather than filed beside the things they affect:

    ui mode         which interface the game presents, for everybody
    uncharted       whether the sea is drawn as surveyed or as it truly is
    player gui      whether an individual may override the interface for themselves
    a person's own  what one account chose, when the game allows choosing
    player build    whether players may build ships, or only staff

**Server-wide, not per-session, and that is the whole point of four of them.** Which
interface a game presents is a decision about what the game *is*, made once by whoever runs
it and looking the same to everybody logged in. A per-player switch would turn it into a
matter of taste, and would also make every bug report begin with working out which mode the
reporter happened to be in. The odd one out is a person's own choice, which exists so that a
game that *wants* to offer the choice can offer it, deliberately, having decided to.

**Kept in `ServerConfig` rather than in settings.** A switch changed at runtime has to
survive a reload without anybody editing Python and restarting a server - which is the whole
reason for having a command instead of a setting. The settings a game ships with are still
what these fall back to, so a game configured in the ordinary way keeps behaving the way it
configured itself and these are only ever overrides.

**Read far more often than written, so they are remembered.** The interface asks what mode
it is in every time anybody moves and on every tick of the panel; a database query for each
of those, on a reactor that has one thread, is a cost paid thousands of times to learn
something that changes about once a month. The cache is cleared by the setters, so the only
way to see a stale value is to write one from another process - and see `_forget` for why
that is the right trade rather than an oversight.
"""

#: What the panel does, for the whole server.
#:
#:     on        always, ashore and inland alike
#:     off       never - the host game's own interface has the screen throughout
#:     hybrid    up aboard a vessel, gone the moment anybody steps off
#:
#: `hybrid` is the shape most games want and the one the contrib defaults to. `on` ignores
#: whether a room was tagged as coastal, because a game that has asked for the panel
#: everywhere has already settled the question the tag exists to answer.
UI_ON = "on"
UI_OFF = "off"
UI_HYBRID = "hybrid"

UI_MODES = (UI_ON, UI_OFF, UI_HYBRID)

#: Where each switch is kept in `ServerConfig`. Prefixed, because a config table is shared
#: with the host game and with every other contrib in it.
UI_KEY = "maritime_ui_mode"
UNCHARTED_KEY = "maritime_uncharted"
PLAYER_GUI_KEY = "maritime_player_gui"
PLAYER_BUILD_KEY = "maritime_player_build"

#: Where one person's own choice is kept, when the game allows them one.
#:
#: On the account rather than on the character, so it follows somebody between the
#: characters they play. A preference about eyesight is not a property of a body.
MY_UI_ATTRIBUTE = "maritime_ui_mode"

#: What has been read since the last write. See the module docstring.
_REMEMBERED = {}


def _held(key):
    """
    Args:
        key (str): One of the config keys above.

    Returns:
        value: Whatever is stored, or None if nothing is.

    Notes:
        Total. A server whose config table cannot be reached - during a migration, in a
        test with no database - gets None and therefore gets the game's own settings, which
        is the same answer it would get on a fresh install. An interface that refused to
        draw because a switch could not be read would be a worse failure than an interface
        drawn in the default mode.

    """
    if key in _REMEMBERED:
        return _REMEMBERED[key]
    try:
        from evennia.server.models import ServerConfig

        value = ServerConfig.objects.conf(key)
    except Exception:
        return None
    _REMEMBERED[key] = value
    return value


def _hold(key, value):
    """
    Args:
        key (str): One of the config keys above.
        value: What to store.

    Notes:
        Written through rather than written back: the cache takes the value that went to
        the database, so a reader immediately afterwards sees what was just set without a
        second query. Clearing instead would be correct too, and would cost that query on
        the very next read - which is the tick after a developer flips a switch and is
        watching the screen to see whether it worked.

    """
    from evennia.server.models import ServerConfig

    ServerConfig.objects.conf(key, value)
    _REMEMBERED[key] = value


def _forget():
    """
    Drop everything remembered, so the next read asks the database again.

    Notes:
        For tests, and for a game that writes these keys itself. Not called on a timer: a
        cache that expired would trade a real cost paid constantly for a stale window
        nobody could predict, which is the worse of the two. The only writer that matters
        is the command in this contrib, and it runs in the same process as every reader.

        A write from a *different* process - a shell, a script, the portal - stays invisible
        until a reload, which is true of a great deal else in Evennia and is worth being
        plain about rather than pretending otherwise.

    """
    _REMEMBERED.clear()


def ui_mode():
    """
    What the panel is doing, for everybody.

    Returns:
        mode (str): One of `UI_MODES`.

    Notes:
        Anything unrecognised reads as the game's own default. A value from an older
        version, a typo written straight into the config table, a game writing something of
        its own - none of those should leave a server with an interface that will not come
        back.

    """
    held = _held(UI_KEY)
    if held in UI_MODES:
        return held
    return default_ui_mode()


def default_ui_mode():
    """
    What the panel does when nobody has said otherwise.

    Returns:
        mode (str): One of `UI_MODES`.

    Notes:
        Read from the game's `MARITIME_ASHORE_PANEL` setting, so a game that configured
        itself in the ordinary way keeps behaving the way it configured itself and the
        runtime switch is only ever an override. Separate from `ui_mode` so the command can
        say what going back to the default would mean.

    """
    from .client.context import wants_ashore_panel

    return UI_ON if wants_ashore_panel() else UI_HYBRID


def set_ui_mode(wanted):
    """
    Say what the panel should do, for the whole server.

    Args:
        wanted (str): One of `UI_MODES`.

    Returns:
        kept (str): What was stored.

    Raises:
        ValueError: If it is not one of the three.

    """
    if wanted not in UI_MODES:
        raise ValueError(f"Unknown maritime UI mode {wanted!r}.")
    _hold(UI_KEY, wanted)
    return wanted


def uncharted():
    """
    Whether the sea is drawn as it truly is rather than as somebody surveyed it.

    Returns:
        open (bool): False unless somebody turned it on.

    Notes:
        Off on any server nobody has touched, which is the only safe default. A game that
        shipped with this on would hand every player a perfect chart of the world and would
        have no navigation left in it.

    """
    return bool(_held(UNCHARTED_KEY))


def set_uncharted(on):
    """
    Args:
        on (bool): True to draw the world, False to draw the paper.

    Returns:
        kept (bool): What was stored.

    """
    kept = bool(on)
    _hold(UNCHARTED_KEY, kept)
    return kept


def players_may_choose():
    """
    Whether an individual account may override the interface for itself.

    Returns:
        allowed (bool): False unless somebody turned it on.

    Notes:
        Off by default, and that is the position this contrib argues for: one interface for
        one game. But it is a position, not a fact, and a game whose players include people
        who cannot use a graphical panel at all has a reason the contrib cannot answer. So
        the choice is offered to whoever runs the game rather than taken away from them.

    """
    return bool(_held(PLAYER_GUI_KEY))


def set_players_may_choose(allowed):
    """
    Args:
        allowed (bool): True to let accounts choose for themselves.

    Returns:
        kept (bool): What was stored.

    Notes:
        Turning it off does not erase what anybody chose. It stops those choices being
        read, and turning it back on restores them - which is what somebody flipping this
        while testing expects, and it means a game can be switched back and forth without
        quietly wiping a preference a player set months ago.

    """
    kept = bool(allowed)
    _hold(PLAYER_GUI_KEY, kept)
    return kept


def players_may_build():
    """
    Whether anybody may build a ship, or only staff.

    Returns:
        allowed (bool): False unless somebody turned it on.

    Notes:
        Off by default. A demo world wants players building ships; a game with an economy
        wants them bought, won or inherited, and would be very surprised by a command that
        makes a frigate out of nothing. The contrib ships the answer that surprises nobody
        and the game says otherwise.

    """
    return bool(_held(PLAYER_BUILD_KEY))


def set_players_may_build(allowed):
    """
    Args:
        allowed (bool): True to let players build ships.

    Returns:
        kept (bool): What was stored.

    Notes:
        Turning it off leaves everything already built exactly where it is. A permission
        that reached back and unbuilt ships would be a permission nobody dared test.

    """
    kept = bool(allowed)
    _hold(PLAYER_BUILD_KEY, kept)
    return kept


def account_of(who):
    """
    Args:
        who (Object or Account or None): A character, or an account directly.

    Returns:
        account (Account or None): Whose preference to read, if there is one.

    Notes:
        A character puppeted by nobody has no account, and an object that is not a
        character has none either. Both are ordinary - a shopkeeper is in a room whose
        contents get looked at - so neither is an error.

        **Asked of the class, not of the shape.** The first version accepted anything with
        a `db` and a `sessions` as an account already, which every `DefaultObject` in
        Evennia satisfies - so a crate handed in came back as its own account and had a
        player's interface preference written onto it. Duck-typing works where the ducks
        differ; here they do not.

    """
    if who is None:
        return None
    from evennia.accounts.models import AccountDB

    if isinstance(who, AccountDB):
        return who
    account = getattr(who, "account", None)
    return account if isinstance(account, AccountDB) else None


def ui_choice(who):
    """
    What this person chose for themselves, whether or not the game is honouring it.

    Args:
        who (Object or Account or None): A character or an account.

    Returns:
        mode (str or None): One of `UI_MODES`, or None if they never chose.

    """
    account = account_of(who)
    if account is None:
        return None
    held = getattr(getattr(account, "db", None), MY_UI_ATTRIBUTE, None)
    return held if held in UI_MODES else None


def set_ui_choice(who, wanted):
    """
    Args:
        who (Object or Account): A character or an account.
        wanted (str or None): One of `UI_MODES`, or None to go back to the server's.

    Returns:
        kept (str or None): What was stored, or None if there was nobody to store it
            against.

    Raises:
        ValueError: If it is not one of the three, and is not None.

    """
    if wanted is not None and wanted not in UI_MODES:
        raise ValueError(f"Unknown maritime UI mode {wanted!r}.")
    account = account_of(who)
    if account is None:
        return None
    setattr(account.db, MY_UI_ATTRIBUTE, wanted)
    return wanted


def ui_mode_for(who):
    """
    What the panel is doing for this particular person.

    Args:
        who (Object or Account or None): A character or an account.

    Returns:
        mode (str): One of `UI_MODES`.

    Notes:
        The server's mode unless the game has allowed people to choose and this person has.
        Asked in that order deliberately: the permission is checked before the preference,
        so turning the permission off silences every existing choice at once rather than
        leaving them to be found one player at a time.

    """
    if players_may_choose():
        mine = ui_choice(who)
        if mine is not None:
            return mine
    return ui_mode()


__all__ = (
    "UI_ON",
    "UI_OFF",
    "UI_HYBRID",
    "UI_MODES",
    "UI_KEY",
    "UNCHARTED_KEY",
    "PLAYER_GUI_KEY",
    "PLAYER_BUILD_KEY",
    "MY_UI_ATTRIBUTE",
    "ui_mode",
    "default_ui_mode",
    "set_ui_mode",
    "uncharted",
    "set_uncharted",
    "players_may_choose",
    "set_players_may_choose",
    "players_may_build",
    "set_players_may_build",
    "account_of",
    "ui_choice",
    "set_ui_choice",
    "ui_mode_for",
)
