import random
import math
import logging
log = logging.getLogger(__name__)

from cl_constants import *
from access_control import *

def still_ask(query_type):
    return query_type in [WHICH_PLAY, NYARLATHOTEP_RETURN, MULTI_PLAY]

class PublicQuery(PublicData):
    pass

class PrivateQuery(PrivateData):
    pass

    
class Query(PublicUser, PrivateUser):
    """Each query has every valid option in the options section
The context is to help the player being asked know what's going on"""
    _PUBLIC_ATTRS = ("context", "options")
    _PUBLIC_CLASS = PublicQuery
    _PRIVATE_ATTRS = ("context", "options")
    _PRIVATE_CLASS = PrivateQuery
    
    def __init__(self, context, options, outcome):
        self.context = context
        self.options = options
        self.outcome = outcome

    def is_(self, type_):
        return self.context.is_(type_)

    def ask(self, player):
        if not still_ask(self.context.type_) and len(self.options) <= 1:
            # Only one choice, so don't ask
            # But do ask for some types of Query, for a facsimile of agency and better play experience
            return self.outcome(self.options[0])
        try:
            privateQ = private(self, player)
            chosen = player.respond_to_query(privateQ)
        except NotImplementedError:
            chosen = None
            log.error("Player hasn't implemented a proper response for " + str(self))
            if self.is_(NYARLATHOTEP_RETURN):
                log.error("Possibly iterated on a NyarlathotepOption")
        except AttributeError:
            chosen = None
            log.error("Player tried to edit the query they were given.")
        if chosen in privateQ.options:
            i = privateQ.options.index(chosen)
            return self.outcome(self.options[i])
        else:
            # I guess we choose for them
            log.error("Player %s didn't pick a valid option" % player.name)
            return self.outcome(random.choice(self.options))

    def __str__(self):
        return str(self.context)


# Specially created option classes, for specific types of Querys

class NyarlathotepOptions:
    """List-like object for more safely enumerating n! options.
Not recommended for Players to enumerate all values.
Will only ever be on its own, not with other options."""
    def __init__(self, iterable):
        if len(set(iterable)) != len(iterable):
            # I can't find a reason this would be needed, as we use uid's not cards
            raise ValueError("Duplicated values in Nyarlathotep not allowed")
        self._items = tuple(iterable)
    def get_int_items(self):
        return self._items
    def index(self, perm):
        if perm not in self:
            raise ValueError(str(perm) + " is not a valid permutation of " + str(self._items))
        avail = list(self._items)
        i = 0
        ret = 0
        while avail:
            p = perm[i]
            j = avail.index(p)
            avail.pop(j)
            ret += j*math.factorial(len(avail))
            i += 1
        return ret
    def __getitem__(self, i):
        avail = list(self._items)
        ret = []
        ii = i
        while avail:
            j = math.floor(ii / math.factorial(len(avail)-1))
            ii -= j*math.factorial(len(avail)-1)
            ret.append(avail.pop(j))
        return tuple(ret)
    def __len__(self):
        return math.factorial(len(self._items))
    def __contains__(self, item):
        """self._items should be all unique, and we don't really care about type"""
        return set(item) == set(self._items) and len(item) == len(self._items)
    def __str__(self):
        return "All combinations of " + str(self._items)
    def __repr__(self):
        return "All combinations of " + repr(self._items)
    def __eq__(self, other):
        if type(other) == type(self):
            return set(other.get_int_items) == set(self._items)
        return False
    def __ne__(self, other):
        return not (self == other)
    def __iter__(self):
        raise NotImplementedError("If you need to iterate through all options, use itertools.permutations on get_int_items")
    def __setitem__(self, i, item):
        """Read only."""
        raise NotImplementedError("Nyarlathotep options are read-only")
