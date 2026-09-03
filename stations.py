"""
Posts, and who is standing them.

Gunner, lookout, helmsman, sailing master, carpenter, surgeon. Every one of these already
happens - the guns are served, the horizon is watched, she is steered - and the contrib has
always assumed each was done competently by nobody in particular. A post is that assumption
made into a decision: somebody is at the helm, and it matters who.

**The contrib owns what a post does to the ship. The game owns how good the person is.**

That division is the whole design, and it is the same one that keeps economy, character
combat and stamina out of here. A skill system is precisely what must not be imported - not
a small one, not a default one, not an optional one, because the moment one ships every game
with its own has to fight it. So this asks a question through one replaceable seam:

    how well is this post being kept?

and the shipped answer is *well enough*. A game that adopts none of this sails exactly as it
did, which is the same courtesy an unowned ship extends by answering to anybody aboard.

**Command succeeds down the posts.** A captain who is killed, taken or simply logs out
leaves a ship that still has to be sailed, and somebody aboard takes her - the sailing
master first, because that is his trade. Nothing here decides that a captain is gone; it
answers what happens when a game says so.

"""

from dataclasses import dataclass

from .events import Event, bus
from .results import Result

#: The posts a ship keeps.
HELM = "helm"
LOOKOUT = "lookout"
GUNNERY = "gunnery"
MASTER = "master"
CARPENTER = "carpenter"
SURGEON = "surgeon"

POSTS = (HELM, LOOKOUT, GUNNERY, MASTER, CARPENTER, SURGEON)

#: What each is for, in the words somebody would use aboard.
CALLED = {
    HELM: "at the helm",
    LOOKOUT: "on lookout",
    GUNNERY: "on the guns",
    MASTER: "sailing master",
    CARPENTER: "ship's carpenter",
    SURGEON: "ship's surgeon",
}

#: Who takes her, in order, when there is no captain.
#:
#: The sailing master first because navigating her is his trade and he is the one man aboard
#: whose job already includes deciding where she goes. Gunnery next, then the carpenter -
#: which is a fair reading of who has authority on a small ship and, more to the point, is
#: a *stated* order rather than whoever the code happened to find first.
SUCCESSION = (MASTER, GUNNERY, CARPENTER, HELM, LOOKOUT, SURGEON)

#: What a post is worth when nobody has said otherwise.
#:
#: One. Not a penalty and not a bonus: a game that does not model competence gets the ship
#: it had before this existed, which is the only honest default for a seam whose whole
#: purpose is to be replaced.
WELL_ENOUGH = 1.0

NO_SUCH_POST = "no_such_post"
NOBODY_THERE = "nobody_there"
ALREADY_THERE = "already_there"
NO_SUCCESSOR = "no_successor"


@dataclass(frozen=True, kw_only=True)
class PostResult(Result):
    """
    Somebody taking or leaving a post.

    Attributes:
        post (str): Which one.
        keeper (object or None): Who has it now.
        relieved (object or None): Who had it before.

    """

    post: str = ""
    keeper: object = None
    relieved: object = None


@dataclass(frozen=True, kw_only=True)
class PostChanged(Event):
    """
    A post changed hands.

    Attributes:
        vessel (object): The hull.
        post (str): Which post.
        keeper (object or None): Who has it now.
        relieved (object or None): Who had it before.

    """

    vessel: object
    post: str = ""
    keeper: object = None
    relieved: object = None


def competence_of(character, post, vessel):
    """
    The shipped answer to "how well is this post being kept?".

    Args:
        character (object or None): Whoever is standing it.
        post (str): Which post.
        vessel (object): The hull.

    Returns:
        competence (float): From 0 to 1, where 1 is as well as it can be done.

    Notes:
        **Well enough, always.** Deciding otherwise would mean reading a skill off a
        character, and character systems are exactly what this contrib must not import - the
        moment it ships one, every game that has its own has to fight it.

        A game that wants a green helmsman to steer worse points `MARITIME_COMPETENCE_POLICY`
        at its own function and answers in its own terms. Everything downstream already
        multiplies by this number, so nothing else has to change.

    """
    return WELL_ENOUGH


class Stationed:
    """
    A hull with posts, and people standing them.

    Notes:
        One person to a post and one post to a person. A man at the helm is not also on the
        lookout, and a ship that let him be would be getting two people's work out of one -
        which is the kind of arithmetic that makes a crew a spreadsheet.

    """

    def at_object_creation(self):
        """Set up this part of a newly created vessel."""
        super().at_object_creation()
        self.db.posts = {}

    @property
    def posts(self):
        """
        Returns:
            posts (dict): Post to whoever is standing it, deleted references dropped.

        Notes:
            Filtered on the way out. An Evennia attribute holding a deleted object hands
            back None, and a post held by nobody-at-all is a post nobody is standing.

        """
        held = self.db.posts or {}
        return {post: who for post, who in held.items() if who is not None and who.pk}

    def keeper_of(self, post):
        """
        Args:
            post (str): Which post.

        Returns:
            keeper (object or None): Who is standing it.

        """
        return self.posts.get(post)

    def post_of(self, character):
        """
        Args:
            character (object): Whoever.

        Returns:
            post (str or None): What they are standing, if anything.

        """
        for post, who in self.posts.items():
            if who is character:
                return post
        return None

    def post_to(self, post, character):
        """
        Put somebody on a post.

        Args:
            post (str): Which one.
            character (object): Who takes it.

        Returns:
            result (PostResult): Failed if there is no such post.

        Notes:
            Taking a post gives up whatever else they were standing. A man cannot be at the
            helm and on the lookout, and letting him be would get two people's work out of
            one.

        """
        if post not in POSTS:
            return PostResult(success=False, code=NO_SUCH_POST, post=post)

        held = dict(self.db.posts or {})
        relieved = self.posts.get(post)
        if relieved is character:
            return PostResult(success=False, code=ALREADY_THERE, post=post, keeper=character)

        for other, who in list(held.items()):
            if who is character and other != post:
                del held[other]
        held[post] = character
        self.db.posts = held
        self._say_post_changed(post, character, relieved)
        return PostResult(success=True, post=post, keeper=character, relieved=relieved)

    def relieve(self, post):
        """
        Relieve whoever is standing a post.

        Not `stand_down`: that is the guns' word, meaning secure them, and it had
        it first. Two methods of one name on one hull is not an error - the later
        mixin simply wins, and the older call goes somewhere nobody intended.

        Args:
            post (str): Which one.

        Returns:
            result (PostResult): Failed if nobody was standing it.

        """
        held = dict(self.db.posts or {})
        relieved = self.posts.get(post)
        if relieved is None:
            return PostResult(success=False, code=NOBODY_THERE, post=post)
        held.pop(post, None)
        self.db.posts = held
        self._say_post_changed(post, None, relieved)
        return PostResult(success=True, post=post, keeper=None, relieved=relieved)

    def competence_at(self, post):
        """
        How well a post is being kept.

        Args:
            post (str): Which one.

        Returns:
            competence (float): From 0 to 1.

        Notes:
            The same number whether somebody is standing it or not, unless a game says
            otherwise. A ship's people do these things anyway; a named post is a game
            saying *this* person does it, and only a game knows whether that is better.

        """
        from . import config

        return float(config.competence_policy()(self.keeper_of(post), post, self))

    def succeed_command(self):
        """
        Give her to whoever is next, her captain being gone.

        Returns:
            result (PostResult): Who took her, or a failure if there is nobody to.

        Notes:
            **This does not decide that a captain is gone.** It answers what happens when
            something else says so - he was killed in the melee, taken with the ship, or his
            player closed the window - because deciding a character is out of the fight is
            the one judgement this contrib refuses to make.

            Down `SUCCESSION`, which is written out rather than discovered, so the answer to
            "who has her now?" is a thing somebody decided and not a thing that fell out of
            dictionary ordering.

        """
        for post in SUCCESSION:
            keeper = self.keeper_of(post)
            if keeper is not None and keeper is not self.captain:
                self.pass_command(keeper)
                return PostResult(success=True, post=post, keeper=keeper)
        return PostResult(success=False, code=NO_SUCCESSOR)

    def _say_post_changed(self, post, keeper, relieved):
        """
        Args:
            post (str): Which post.
            keeper (object or None): Who has it now.
            relieved (object or None): Who had it.

        """
        from . import config

        bus().publish(
            PostChanged(
                game_time=config.time_provider().now(),
                vessel=self,
                post=post,
                keeper=keeper,
                relieved=relieved,
            )
        )
