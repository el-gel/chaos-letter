import logging
import sys
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
log = logging.getLogger(__name__)

from game import *

from utils import *
from library import *
from players import *
from sample_actions import *

deckdict = {Handmaid: 1,
            LiberIvonis: 8,
            Guard: 10,
            DeepOnes: 1,
            Priest: 10,
            Prince: 10,
            Nope: 10,
            Princess: 5,
            Capitalist: 10,
            MiGo: 10,
            Cthulhu: 10}

stacks = (
    (LIBER_IVONIS, LIBER_IVONIS, LIBER_IVONIS, LIBER_IVONIS, # Force immortality
     GUARD, LIBER_IVONIS, GUARD,LIBER_IVONIS),
    )

deck = []
for cardclass, num in deckdict.items():
    deck += [cardclass() for i in range(num)]
for i in range(len(deck)):
    deck[i].name += " ("+str(i)+")"
    
g = Game()
p1 = Player(g, action_class=LoggingActions, name="Alice")
p2 = Player(g, action_class=LoggingActions, name="Brian")
#p2.actions.debug = True
#p2.actions.other = public(p1, p2)
p2.actions.logging = False
g.setup(deck, [p1,p2], config={HEARTS_TO_WIN: 1, INSANE_HEARTS_TO_WIN: 1,
                               DECK_STACKING: stacks})
g.run_game()


wc = WinContext(p1, LAST_ALIVE)
pi = public(wc, for_=p1)
