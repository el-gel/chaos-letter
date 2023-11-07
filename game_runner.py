import logging
import sys
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
log = logging.getLogger(__name__)

from utils import *
from library import *
from players import *
from sample_actions import *

from game import *

deckdict = {Handmaid: 1,
            LiberIvonis: 10,
            Guard: 10,
            DeepOnes: 1,
            Priest: 10,
            Prince: 10,
            Nope: 10,
            Princess: 5}
deck = []
for cardclass, num in deckdict.items():
    deck += [cardclass() for i in range(num)]
for i in range(len(deck)):
    deck[i].name += " ("+str(i)+")"
    
g = Game()
p1 = Player(g, "Alice", action_class=LoggingActions)
p2 = Player(g, "Brian", action_class=LoggingActions)
if p2.name == p1.name:
    p2.name = "Harry"
#p2.debug = True
#p2.other = public(p1, p2)
#p2.logging = False
g.setup(deck, [p1,p2])
g.run_round()


wc = WinContext(p1, LAST_ALIVE)
pi = public(wc, for_=p1)
