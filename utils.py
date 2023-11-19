import logging
log = logging.getLogger(__name__)

from cl_constants import *
#import game
#from context import *
#import cards
#from events import *
#from queries import *
#from info import *

def like(card_a, card_b):
    # GUARD ~= INVESTIGATOR
    # NO-U ~= INSANE NO-U
    # PRINCE ~= LOVECRAFT 5 (but not like MiGO; use sane_like there)
    # PRINCESS ~= NECRONOMICON (but not like Cthulu; use sane_like there)
    pass

def sane_like(card_a, card_b):
    # PRINCESS ~= CTHULU
    # PRINCE ~= MIGO
    pass

def insane_like(card_type):
    # Only one here is insane no-U and sane no-U
    # Also all cards that are sane only
    # Currently this is the same as like()
    return like(card_type)
    

def liststr(obj):
    return str([recstr(item) for item in obj])

def dictstr(obj):
    return str({key:recstr(val) for key,val in obj.items()})

def recstr(obj):
    """Recursive string of an object; Python doesn't turn internal parts to strings."""
    if isinstance(obj, (list, tuple)):
        return liststr(obj)
    elif isinstance(obj, dict):
        return dictstr(obj)
    else:
        return str(obj)

def living(players):
    return [player for player in players if player.alive]


def num_args(f):
    """How many arguments the function takes. Used to allow simpler Event callbacks."""
    return f.__code__.co_argcount



def make_name_unique(base_name, game):
    cur_names = [p.name for p in game.players]
    if base_name in cur_names:
        num = 2
        while True:
            if base_name + "_" + str(num) in cur_names:
                num += 1
            else:
                break
        return base_name + "_" + str(num)
    else:
        return base_name


def split_context(ctx, obj, call_str, *args, **kwargs):
    """Call specific methods of obj depending on context type. Uses lowercased type names.

obj: Object with relevant methods.
call_str: String with {t} representing relevant methods.
Will use {t} as 'other' if no method exists.
Check EVENT_TYPES for valid options."""
    desired = call_str.replace("{t}", ctx.type_.lower())
    other = call_str.replace("{t}", "other")
    return getattr(obj, desired, getattr(obj, other)).__call__(*args, **kwargs)
