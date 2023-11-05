import logging
log = logging.getLogger(__name__)

from cl_constants import *

from access_control import *
from utils import *

# Different possible Info contexts
# YOU contexts give private info too
# TODO: This is not how I'm doing things anymore, but keeping for reference.
#       Move to context.py.
INFO_DEFAULT = 100
INFO_JOINED = 101
INFO_DIED = 102 # Include source of?
INFO_ROUND_OVER = 103
INFO_SCORED_HEART = 104 # Include source of?
INFO_SCORED_INSANE = 105 # Include source of?
INFO_WON = 106
INFO_DREW = 107
INFO_YOU_DREW = 108
INFO_DISCARDED = 109 # Include source of discard?
INFO_JESTERED = 110
INFO_SWAPPED = 111
INFO_YOU_SWAPPED = 112
INFO_SAW = 113
INFO_YOU_SAW = 114
INFO_PROTECTED = 115
INFO_BOUNTIED = 116
INFO_TAKEN = 117 # Card taken away, not discarded (e.g. Migo)

class PublicInfo(PublicData):
    def __str__(self):
        return str(self.context)

class PrivateInfo(PrivateData):
    def __str__(self):
        return str(self.context)

class Info(PublicUser, PrivateUser):
    """An event that has actually happened. These are shown to Players.

targets can be ALL, or a specific set of Players
All Info will still have a public part, just restricted. E.g., X sees 'X drew a Baron', Y sees 'X drew a card'"""
    next_uid = 0
    _PUBLIC_ATTRS = ("uid", "context")
    _PUBLIC_CLASS = PublicInfo
    _PRIVATE_ATTRS = ("uid", "context")
    _PRIVATE_CLASS = PrivateInfo
    
    def __init__(self, context):
        # Trying to make this not need declaring on each subclass
        self.context = context
        self.sent_to = set()
        self.uid = Info.next_uid
        Info.next_uid += 1
    def send(self, game, override=False):
        privates = self.context.private_for()
        if privates is None:
            privates = ()
        elif privates == ALL:
            privates = game.players
        for player in game.players:
            if not override and player.uid in self.sent_to:
                continue
            if player in privates:
                player.info_event(private(self, player))
            else:
                player.info_event(public(self, player))
            self.sent_to.add(player.uid)
    def send_to(self, player, override=False):
        if not override and player.uid in self.sent_to:
            return
        privates = self.context.private_for()
        if privates is None:
            player.info_event(public(self, player))
        elif privates == ALL:
            player.info_event(private(self, player))
        elif player in privates:
            player.info_event(private(self, player))
        else:
            player.info_event(public(self, player))
        self.sent_to.add(player.uid)
    def before(self, other):
        # Relies on uids monotonically increasing - consider timestamps
        return self.uid < other.uid
    def __str__(self):
        # TODO: make this a substitution thing so it's not needed for subclasses
        return str(self.context)
    def __repr__(self):
        return repr(self.context)
    def is_(self, type_):
        return self.context.is_(type_)
