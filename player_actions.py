from players import *
from utils import *
from cl_constants import *

# TODO: Public game object for the player to look at

class PlayerActions(object):
    """The class that is overridden by bots.

Is never passed anything that reveals hidden game information; only Public/Private classes."""
    def __init__(self, my_player, config):
        self.my_player = my_player # A PrivatePlayer object
        self.config = None # Not decided yet
        self.setup()

    def setup(self):
        """Better to extend this rather than __init__."""
        pass

    def pick_name(self):
        raise NotImplementedError()

    def reset(self):
        """Runs just after resetting this player for the start of a round."""
        pass

    def respond_to_query(self, query):
        """Return one of the values in query.options, given query.context."""
        raise NotImplementedError()

    def info_event(self, info):
        """Information about something happening."""
        raise NotImplementedError()

    # TODO: Convenience methods.
    @property
    def name(self):
        return self.my_player.name
