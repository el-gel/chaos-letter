import re
import logging
log = logging.getLogger(__name__)

from cl_constants import *

from access_control import *
from info import *
from utils import *

def chas(ctx, attr):
    return attr in ctx.__dict__ or attr in ctx.__class__.__dict__

def cgd(ctx, attr, default=NOT_SET):
    return default if not chas(ctx, attr) else ctx.__dict__[attr]

def repl_str(rstr, ctx):
    ret = rstr
    if "{t}" in ret:
        ret = ret.replace("{t}", str(ctx.type_))
    if "{p}" in ret:
        ret = ret.replace("{p}", str(cgd(ctx, "player")))
    if "{ps}" in ret:
        # TODO: nicer replacement, e.g. Alex, Beth and Charlie
        # Make a utils 'list to English list'
        ret = ret.replace("{ps}", liststr(ctx.players) if chas(ctx, "players") else NOT_SET)
    if "{c}" in ret:
        ret = ret.replace("{c}", str(cgd(ctx, "card")))
    if "{cs}" in ret:
        ret = ret.replace("{cs}", liststr(ctx.cards) if chas(ctx, "cards") else NOT_SET)
    if "{pcs}" in ret:
        if chas(ctx, "players") and chas(ctx, "cards"):
            ret = ret.replace("{pcs}",
                  str([(str(ctx.players[i]) if ctx.players[i] else NOT_SET,
                       str(ctx.cards[i]) if ctx.cards[i] else NOT_SET)
                     for i in range(max(len(ctx.players),len(ctx.cards)))]))
        else:
            ret = ret.replace("{pcs}", NOT_SET)
    if "{s}" in ret:
        ret = ret.replace("{s}", str(cgd(ctx, "source")))
    if "{po}" in ret:
        ret = ret.replace("{po}", str(cgd(ctx, "play_option")))
    if "{pos}" in ret:
        ret = ret.replace("{pos}", liststr(cgd(ctx, "play_options", ())))
    if "{ops}" in ret:
        ret = ret.replace("{ops}", liststr(cgd(ctx, "options", ())))
    if "{n}" in ret:
        ret = ret.replace("{n}", str(cgd(ctx, "number")))
    if "{nth}" in ret:
        if chas(ctx, "number"):
            n_str = str(ctx.number)
            th_str = ["th", "st", "nd", "rd", "th", "th", "th", "th", "th", "th"][int(n_str[-1])]
            ret = ret.replace("{nth}", n_str + th_str)
        else:
            ret = ret.replace("{nth}", NOT_SET)
    while match := re.search(r"\{po\:(.*?)\}", ret):
        param = match.group(1)
        if chas(ctx,"play_option"):
            if param == "target":
                ret = ret.replace(match.group(0), str(ctx.play_option.targets[0]))
            elif param == "targets":
                ret = ret.replace(match.group(0), liststr(ctx.play_option.targets))
            elif param == "mode":
                ret = ret.replace(match.group(0), str(ctx.play_option.mode))
            else:
                ret = ret.replace(match.group(0),
                    str(ctx.play_option.parameters.get(param, NOT_SET + " ["+param+"]")))
        else:
            ret = ret.replace(match.group(0), NOT_SET)
    while match := re.search(r"\{ps\:(\d*)\}", ret):
        param = int(match.group(1))
        if chas(ctx, "players") and len(ctx.players) > param:
            ret = ret.replace(match.group(0), str(ctx.players[param]))
        else:
            ret = ret.replace(match.group(0), NOT_SET)
    return ret


CTX_ATTRS = ["type_", "player", "card", "source", "play_option",
             "number", "str_fmt", "players", "cards", "play_options"]

class PublicContext(PublicData):
    def set_data(self, ctx, for_):
        # Unlike the normal PublicData, does not set things to None if missing
        self._RO = tuple(ctx._PUBLIC_ATTRS)
        for attr in self._RO:
            if (attr in ctx.__dict__ or attr in ctx.__class__.__dict__) \
               and attr != "str_fmt":
                setattr(self, attr, public(getattr(ctx, attr), for_))
        # Also we have a distinction between internal, public and private string formatting
        self.str_fmt = ctx.pub_str_fmt if ctx.pub_str_fmt else ctx.str_fmt
    def __str__(self):
        return repl_str(self.str_fmt, self)

class PrivateContext(PrivateData):
    def set_data(self, ctx, for_):
        # As with Public, does not set to None
        self._RO = tuple(ctx._PRIVATE_ATTRS)
        for attr in self._RO:
            if (attr in ctx.__dict__ or attr in ctx.__class__.__dict__) \
               and attr != "str_fmt":
                setattr(self, attr, private(getattr(ctx, attr), for_))
        self.str_fmt = ctx.pri_str_fmt if ctx.pri_str_fmt else ctx.str_fmt
    def __str__(self):
        return repl_str(self.str_fmt, self)


class Context(PublicUser, PrivateUser):
    _PUBLIC_ATTRS = tuple(CTX_ATTRS)
    _PUBLIC_CLASS = PublicContext
    _PRIVATE_ATTRS = tuple(CTX_ATTRS)
    _PRIVATE_CLASS = PrivateContext
    
    type_ = DEFAULT
    str_fmt = "{t}"
    pub_str_fmt = None
    pri_str_fmt = None
    def __init__(self, *args, **kwargs):
        pass

    def pre_info(self, event):
        """Give pre_info for its Event firing."""
        return []

    def post_info(self, event):
        """Give post_info for its Event completing."""
        return [Info(self)]

    def private_for(self):
        """Who gets Private Info from this. Can be overridden."""
        if "player" in self.__dict__:
            return (self.player,)
        elif "players" in self.__dict__:
            return self.players
        else:
            return ()

    def is_(self, type_):
        return self.type_ == type_

    def __str__(self):
        return repl_str(self.str_fmt, self)
        

# Query contexts

class WhichPlayContext(Context):
    type_ = WHICH_PLAY
    str_fmt = "Asked what card/option to play."

class MultiPlayContext(Context):
    type_ = MULTI_PLAY
    str_fmt = "Forced to play."

class WhoStartsContext(Context):
    type_ = WHO_STARTS
    str_fmt = "Asked who starts."

class WhichCardContext(Context):
    type_ = WHICH_CARD
    str_fmt = "Asked which card to be involved in {s}."
    def __init__(self, source):
        self.source = source

class UseNopeContext(Context):
    type_ = USE_NOPE
    str_fmt = "Asked whether to nope {po}."
    def __init__(self, play_context):
        self.play_context = play_context
        self.play_option = play_context.play_option


class OrderEventsContext(Context):
    type_ = ORDER_EVENTS
    # TODO: {contexts}
    str_fmt = "Asked how to order these events."
    def __init__(self, contexts):
        self.contexts = contexts

# Event and Info contexts

class JoinContext(Context):
    """source can be PRIME or NEW"""
    type_ = JOIN
    str_fmt = "{p} joined as a {s} player."
    def __init__(self, player, source):
        self.player = player
        self.source = source

class LeaveContext(Context):
    type_= LEAVE
    str_fmt = "{p} left the game."
    def __init__(self, player, source):
        self.player = player
        self.source = source

class RoundStartContext(Context):
    type_ = ROUND_START
    str_fmt = "Started the round, with {ps} playing."
    def __init__(self, players):
        self.players = players

class RoundEndContext(Context):
    """source is DECK_EMPTY, ONE_LEFT, or a card that caused it"""
    type_ = ROUND_END
    str_fmt = "Round ended due to {s}: {ps} made it to the end!"
    def __init__(self, players, source):
        self.players = players
        # Consider putting cards in here, as it's public info
        self.source = source

class StartingContext(Context):
    """source is either the player who picked, or RANDOM"""
    type_ = STARTING
    str_fmt = "{p} starts the round."
    def __init__(self, player, source):
        self.player = player
        self.source = source

class WinContext(Context):
    """source is LAST_ALIVE, HIGHEST_CARD, or a card"""
    type_ = WIN
    str_fmt = "{p} won, due to {s}!"
    def __init__(self, player, source):
        self.player = player
        self.source= source

class TieContext(Context):
    """source is MUTUAL_ANNHILATION or ALL_8"""
    type_ = TIE
    str_fmt = "It was a tie, due to {s}."
    def __init__(self, source):
        self.source = source

class ScoredContext(Context):
    """earned is HEART or INSANE_HEART, source is a LAST_ALIVE, HIGHEST_CARD or a card"""
    type_ = SCORED
    str_fmt = "{p} earned a token, due to {s}."
    def __init__(self, player, source, earned):
        self.player = player
        self.source = source
        self.earned = earned

class AnnhilationContext(Context):
    type_ = ANNHILATION
    str_fmt = "{ps} annhilated at the end of the round: they each had an effective {n}."
    def __init__(self, players, number):
        self.players = players
        self.number = number

class CardPlayContext(Context):
    type_ = CARD_PLAY
    str_fmt = "{p} goes to play {c} as {po:mode} targeting {po:targets}."
    def __init__(self, play_option):
        # Pretty sure the player will always be this
        self.player = play_option.card.controller
        self.card = play_option.card
        self.play_option = play_option

class DeathContext(Context):
    type_ = DEATH
    str_fmt = "{p} dies due to {s}."
    def __init__(self, player, source, card=None):
        self.source = source
        self.player = player
        self.card = card
        # TODO: How to describe when a player loses with their own baron?
        # I would have said the source is the other player
        # But maybe it should be a PlayOption instead

class DiscardContext(Context):
    """source can be PLAYED, INSANITY_CHECK, or a card. card is the card discarded."""
    type_ = DISCARD
    str_fmt = "{p} discards {c} due to {s}."
    def __init__(self, player, source, card):
        self.player = player
        self.card = card
        self.source = source

class DrawContext(Context):
    """source can be JOINED, START_OF_TURN, OUT_OF_TURN (e.g. no-U) or a card (e.g. Capitalist)."""
    type_ = DRAW
    str_fmt = "{p} draws {c} for {s}."
    pub_str_fmt = "{p} draws for {s} (cardback: {c})"
    def __init__(self, player, source, card=None):
        self.player = player
        self.source = source
        # May not know the card until after the draw actually happens
        self.card = card

class InsanityChecksContext(Context):
    # For the start of all insanity checks, not individual ones
    type_ = INSANITY_CHECKS
    str_fmt = "{p} starts insanity checks ({n} to do)."
    def __init__(self, player, number):
        self.player = player
        self.number = number

class InsanityCheckContext(Context):
    # For individual insanity check
    type_ = INSANITY_CHECK
    str_fmt = "{p} does their {nth} insanity check."
    def __init__(self, player, number):
        self.player = player
        self.number = number

class TurnStartContext(Context):
    type_ = TURN_START
    str_fmt = "{p} starts their {nth} turn."
    def __init__(self, player):
        self.player = player
        self.number = player.turns_played + 1

class TurnEndContext(Context):
    type_ = TURN_END
    str_fmt = "{p} ends their turn."
    def __init__(self, player):
        self.player = player

class ProtectionLossContext(Context):
    type_ = PROTECTION_LOSS
    str_fmt = "{p}'s protection from {s} wore off."
    def __init__(self, player, source):
        self.player = player
        self.source = source

class CancelDeathContext(Context):
    type_ = CANCEL_DEATH
    str_fmt = "But {p} did not die, due to {s}."
    def __init__(self, player, source, death_event, death_ctx):
        self.player = player
        self.source = source
        self.death_event = death_event # Need to know death_event for cancelling
        self.death_ctx = death_ctx # And death_source for public/private

class SeeCardContext(Context):
    type_ = SEE_CARD
    str_fmt = "Showing {ps:1}'s {c} to {ps:0} (due to {s})."
    def __init__(self, players, card, source):
        self.players = players
        self.card = card
        self.source = source

class ShuffleContext(Context):
    type_ = SHUFFLE
    str_fmt = "Shuffled {c} into the deck."
    def __init__(self, card, source):
        self.card = card
        self.source = source
