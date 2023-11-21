import logging
log = logging.getLogger(__name__)

from cl_constants import *
from context import *
from events import *
from query_utils import *

# Death reasons:
# PlayOption of another Card
# INSANITY_CHECK
# *Not* annhilation.
# Want to keep source and card, for e.g. Princess killed, but due to a different card.
def trigger_death(game, player, source=None, card=None):
    if not player.alive:
        # Don't try to kill someone who's already dead
        return
    if source:
        ctx = DeathContext(player, source, card)
    elif card:
        # Assume that the holder of the card caused it, if not told
        ctx = DeathContext(player, card.my_holder, card)
    else:
        raise ValueError("Triggering death must have a source or card involved.")
    Event(ctx, resolve_effect=lambda ev: game.kill_player(player)).queue(game)

# Sources:
# INSANITY_CHECK
# DEATH
# PlayOption of the card getting played
def get_discard_event(player, source, card):
    def do_discard(ev):
        if source == INSANITY_CHECK:
            player.put_in_discard(card)
        else:
            player.hand_to_discard(card)
        card.on_discard(ev)
    return Event(DiscardContext(player, source, card),
                 resolve_effect=do_discard)
    
def trigger_discard(game, player, source, card):
    get_discard_event(player, source, card).queue(game)

def get_draw_event(game, player, source, take_from_aside=True):
    def do_draw(ev):
        # Can raise an EmptyDeckException. If that happens, end the round now
        try:
            card = game.draw(take_from_aside)
        except EmptyDeckException:
            ev.cancel(DECK_EMPTY)
            game.end_round(DECK_EMPTY)
            return
        ev.context.card = card
        player.give(card)
        card.on_draw(ev)
    return Event(DrawContext(player, source),
                 resolve_effect=do_draw)

def trigger_draw(game, player, source, take_from_aside=True):
    get_draw_event(game, player, source, take_from_aside).queue(game)

def trigger_round_win(game, player, source):
    def do_win(ev):
        game.end_round(source, winner=player)
    Event(WinContext(player, source),
          resolve_effect=do_win).queue(game)

def trigger_look(game, looker, lookee, source=None, context=None, whole_hand=False):
    """Show lookee's card to looker, due to source.

source is e.g. END_OF_GAME, or the play_option that triggered.
context is the context of the card play event relevant.
If source isn't provided, will take context.play_option for source."""
    if whole_hand:
        cards = lookee.hand
    else:
        cards = (ask_which_card(lookee, context),)
    for card in cards:
        # Event doesn't do anything, but the Info sent out shows the card to looker
        Event(SeeCardContext(players=(looker, lookee),
                             card=card,
                             source=source if source else context.play_option
                             )).queue(game)

def trigger_shuffle(game, card, source):
    """Shuffle a card into the deck, taking it from their player if necessary."""
    def do_shuffle(ev):
        card.take_from_holder()
        game.shuffle_in(card)
    Event(ShuffleContext(card=card,
                         source=source),
          resolve_effect=do_shuffle).queue(game)
    

def get_play_event(play_option, resolve_effect):
    """Get, but don't trigger, a play event."""
    ctx = CardPlayContext(play_option)
    if getattr(play_option, "str_fmt", False):
        ctx.str_fmt = play_option.str_fmt
    return Event(ctx, resolve_effect=resolve_effect)

