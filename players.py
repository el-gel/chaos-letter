import random
import logging
log = logging.getLogger(__name__)

from cl_constants import *
from events import *
from queries import *
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
    def __init__(self, game, name=None, primed_from=None, config=None):
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
        self.config = None # Some function of config
        self.setup()


    def reset(self):
        """Reset for the start of a round. Override the pre_ and post_ reset methods if needed."""
        self.pre_reset()
        self.turns_played = 0
        self.hand = []
        self.discard = []
        self.protected = False
        self.post_reset()

    # TODO: Move these into player actions.

    def setup(self):
        # For extending
        pass

    def pre_reset(self):
        """For things that you may want to do before reset; e.g., grab player state at the end of a round."""
        pass

    def post_reset(self):
        """For things that you may want to do after reset; e.g., resetting tracking state."""
        pass

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
        raise NotImplementedError()

    def info_event(self, info):
        raise NotImplementedError()

    # Name management. TODO: the game object doesn't exist, so making a name unique should be in the Game, not here.

    def generate_name(self):
        # For extending
        return random.choice(RANDOM_NAMES)

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
                                primed_from=player, config=player.config)

# Testing players

class RandomPlayer(Player):
    def respond_to_query(self, query):
        return random.choice(query.options)

    def info_event(self, info):
        pass # I don't care!

class LoggingPlayer(RandomPlayer):
    def setup(self):
        self.infos = []
        self.debug = False
        self.other = None
        self.logging = True
    def info_event(self, info):
        self.infos.append(info)
        if self.logging: print("["+str(len(self.infos)-1) + "] To " + self.name + ": " + str(info.context))
        if self.debug and self.logging:
            card = getattr(info.context, "card", None)
            if card:
                print("     Relevant card is: " + repr(card))
            if self.other:
                print("     " + self.other.name + "'s holding: " + repr(self.other.hand))

class RandomLogger(LoggingPlayer):
    def respond_to_query(self, query):
        if self.logging: print("-----" + self.name + " asked: " + str(query.context))
        if self.logging: print("     with options: " + str([str(op) for op in query.options]))
        # For testing, can we select only 4's with guard likes?
        # Also, good to know what's a pain point
        if query.context.type_ == WHICH_PLAY:
            good_ops = []
            ins_ops = []
            LIB = None
            for op in query.options:
                if op.card.type_ in (GUARD, INVESTIGATOR, DEEP_ONES):
                    if not op.targets or op.parameters["number"] in (2,4):
                        good_ops.append(op)
                        if op.mode == INSANE:
                            ins_ops.append(op)
                else:
                    good_ops.append(op)
                    if op.mode == INSANE:
                        if op.card.type_ == LIBER_IVONIS:
                            LIB = op
                        ins_ops.append(op)
            if ins_ops:
                good_ops = ins_ops
            if LIB:
                good_ops = [LIB]
                if self.logging:
                    print("###############################")
                    print("###########IMMORTAL############")
                    print("###############################")
            if self.logging: print("     Only considering: " + str([str(op) for op in good_ops]))
            return random.choice(good_ops)
        return random.choice(query.options)
