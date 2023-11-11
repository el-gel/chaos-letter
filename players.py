import random
import logging
log = logging.getLogger(__name__)

from cl_constants import *
from access_control import *
from utils import make_name_unique

RANDOM_NAMES = ["Alex", "Beth", "Chris", "David", "Emily", "Fiona", "George"]


class PublicPlayer(StaticPublicData):
    type_ = PLAYER
    def __eq__(self, other):
        if isinstance(other, (Player, PublicPlayer, PrivatePlayer)):
            return self.uid == other.uid
    def __str__(self):
        return self.name

class PrivatePlayer(StaticPrivateData):
    type_ = PLAYER
    def __eq__(self, other):
        if isinstance(other, (Player, PublicPlayer, PrivatePlayer)):
            return self.uid == other.uid
    def __str__(self):
        return self.name



# TODO: a PlayerActions class that implements actual overridden functions
class Player(StaticPublicUser, StaticPrivateUser):
    next_uid = 0
    _PUBLIC_ATTRS = ("uid", "name", "primed_from", "prime_count", "primed_to", "turns_played",
                     "alive", "protected", "hearts", "insane_hearts", "hand", "discard")
    _PUBLIC_CLASS = PublicPlayer
    _PRIVATE_ATTRS = _PUBLIC_ATTRS
    _PRIVATE_CLASS = PrivatePlayer
    type_ = PLAYER
    def __init__(self, game, action_class,
                 name=None, primed_from=None, config=None):
        self.game = game
        self.uid = Player.next_uid
        Player.next_uid += 1
        if name:
            self.name = name
        else:
            self._set_own_name()
        if primed_from:
            self.prime_count = primed_from.prime_count + 1
            self.primed_from = primed_from
            primed_from.primed_to = self
        else:
            self.prime_count = 0
            self.primed_from = None
        self.primed_to = None
        self.turns_played = 0
        self.hand = []
        self.discard = []
        self.alive = True
        self.protected = False
        self.hearts = 0
        self.insane_hearts = 0
        self.reset_public_private()
        # Supposed to be for bot config; not sure where it'll point yet
        # Maybe just let it point to a file to read
        self.action_class = action_class
        self.actions = action_class(private(self, for_=self), config)
        self.config = config # maybe shouldn't allow mutation by action class

    def reset(self):
        """Reset for the start of a round."""
        self.alive = True
        self.turns_played = 0
        self.hand = []
        self.discard = []
        self.protected = False
        self.actions.reset()

    # Public / private info management.

    def public_info(self, for_):
        # If for self, then just give the private info instead
        if for_ == self:
            return super().private_info(for_)
        return super().public_info(for_)

    def private_info(self, for_):
        # If not for self, then give the public info instead
        if for_ != self:
            return super().public_info(for_)
        return super().private_info(for_)

    def reset_public_private(self):
        self._reset_public_info()
        self._reset_private_info()

    # Card movement functions. Triggers appropriate listeners.

    def give(self, card):
        # Disguise what the hand is
        for held in self.hand:
            held.invalidate_public()
        self.hand.append(card)
        # This will invalidate card's public info too
        card.on_enter_zone(self)

    def take(self, card):
        self.hand.remove(card)
        card.on_leave_zone()
        # Disguise what the hand is
        for held in self.hand:
            held.invalidate_public()

    def hand_to_discard(self, card):
        # Does not call on_leave_zone
        self.hand.remove(card)
        self.put_in_discard(card)
        for held in self.hand:
            held.invalidate_public()

    def put_in_discard(self, card):
        self.discard.append(card)
        card.discarded = True
        card.on_enter_zone(self)

    def take_from_discard(self, card):
        self.discard.remove(card)
        card.discarded = False
        card.on_leave_zone()

    # TODO: Move to PlayerActions, or call them. To be overridden.

    def respond_to_query(self, query):
        return self.actions.respond_to_query(query)

    def info_event(self, info):
        return self.actions.info_event(info)

    # Name management. TODO: the game object doesn't exist, so making a name unique should be in the Game, not here.

    def generate_name(self):
        return self.actions.pick_name()

    def _set_own_name(self):
        """Makes sure that the name is unique in the game too"""
        # TODO: Doesn't work, since no players in the game yet
        base_name = self.generate_name()
        self.name = make_name_unique(base_name, self.game)

    # Convenience methods.

    def unprimed(self):
        """Find the unprimed version of myself."""
        if self.prime_count:
            return self.primed_from.unprimed()
        return self

    def how_insane(self):
        return self.prime_count + sum([card.insane for card in self.discard])

    def __eq__(self, other):
        if isinstance(other, (Player, PublicPlayer, PrivatePlayer)):
            return self.uid == other.uid

    def __str__(self):
        return self.name
    

def prime(player):
    # Get the prime form of a player
    if player.primed_to:
        return player.primed_to
    else:
        # Use the same class as before, and same data
        # This will set up the primed_to as well
        return player.__class__(player.game, name=player.name+" Prime",
                                primed_from=player,
                                action_class=player.action_class,
                                config=player.config)
