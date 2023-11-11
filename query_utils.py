import logging
log = logging.getLogger(__name__)

from cl_constants import *
from queries import *
from events import *
from context import *
from access_control import *
from utils import *

def pass_through(chosen):
    """Used where we just want the chosen option, not to do anything with it."""
    return chosen

def which_play_query(play_options):
    """Get a WhichPlayContext query, asking which card to play."""
    def which_outcome(chosen):
        chosen.trigger()
    return Query(
        context=WhichPlayContext(),
        options=play_options,
        outcome=which_outcome)

def multi_play_query(play_options):
    """Get a MultiPlayContext query.

card_ops is a list of PlayOptions, which must all happen.
Maybe the options should be 'which order do you want to play in?'"""
    def cos_outcome(chosen):
        # Ignore chosen, so we later don't have to expose it all to Player actions
        for play_option in play_options:
            play_option.trigger()
    return Query(
        context=MultiPlayContext(),
        options=(play_options,),
        outcome=cos_outcome)

def ask_who_starts(game, asked):
    """Ask a WhoStartsContext query."""
    def who_outcome(chosen):
        def do_set(ev):
            game.current_player = chosen
        Event(StartingContext(chosen, asked),
              resolve_effect=do_set).queue(game)
    return Query(
        context=WhoStartsContext(),
        options=game.players,
        outcome=who_outcome).ask(asked)

def ask_which_card(asked, context):
    """Ask which card to get involved in something."""
    # If the hand is more than 1, invalidate so cards can't be tracked
    hand_size = len(asked.hand)
    if hand_size > 1:
        for card in asked.hand:
            card.invalidate_private()
            card.invalidate_public()
    return Query(context=WhichCardContext(context),
                 options=asked.hand,
                 outcome=pass_through).ask(asked)

def ask_nope_query(asked, play_context):
    """Ask whether the player wants to Nope a specific play."""
    return Query(context=UseNopeContext(play_context),
                 options=(NO,YES),
                 outcome=pass_through).ask(asked)
