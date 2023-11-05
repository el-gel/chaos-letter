import logging
import sys
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
log = logging.getLogger(__name__)

from utils import *
from library import *
from players import *

from game import *

hdeck = [Handmaid() for i in range(1)] + [LiberIvonis() for i in range(10)]
gdeck = [Guard() for j in range(10)] + [DeepOnes() for k in range(1)]
pdeck = [Priest() for i in range(10)]
g = Game()
p1 = RandomLogger(g)
p2 = RandomLogger(g)
#p2.debug = True
#p2.other = public(p1, p2)
p2.logging = False
g.setup(hdeck+gdeck+pdeck, [p1,p2])
g.run_round()


wc = WinContext(p1, LAST_ALIVE)
pi = public(wc, for_=p1)
