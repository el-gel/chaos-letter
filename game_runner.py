import logging
import sys
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
log = logging.getLogger(__name__)

from game import *

from utils import *
from library import *
from players import *
from sample_actions import *


def deck_from_dict(d, numbered=True):
    deck = []
    for cardclass, num in d.items():
        deck += [cardclass() for i in range(num)]
    if numbered:
        for i in range(len(deck)):
            deck[i].name += " ("+str(i)+")"
    return deck
    

def two_immortals():
    deck = deck_from_dict({
        Handmaid: 1,
        LiberIvonis: 8,
        Guard: 10,
        DeepOnes: 1,
        Priest: 20,
        Prince: 10,
        Nope: 10,
        NoU: 20,
        Princess: 1,
        Capitalist: 1,
        MiGo: 10,
        Cthulhu: 1})

    stacking = (
        (LIBER_IVONIS, LIBER_IVONIS, LIBER_IVONIS, LIBER_IVONIS, # Force immortality
         GUARD, LIBER_IVONIS, GUARD, LIBER_IVONIS),
        )
    g = Game()
    p1 = Player(g, action_class=InteractiveActions, name="Alice")
    p2 = Player(g, action_class=BasicActions, name="Brian")
    #p2.actions.debug = True
    #p2.actions.other = public(p1, p2)
    p2.actions.logging = False
    g.setup(deck, [p1,p2], config={HEARTS_TO_WIN: 1, INSANE_HEARTS_TO_WIN: 1,
                                   DECK_STACKING: stacking})
    g.run_game()


two_immortals()
