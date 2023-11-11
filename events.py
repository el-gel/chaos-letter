import logging
log = logging.getLogger(__name__)

from cl_constants import *
from utils import *

# Big question; do I use a subclass for each Info/Event, or one big class?
# How about for Querys?
# Use subclasses, with class-wide context attributes
# Use subclasses for context, not Info?

# Different events that can happen
# Need to consider whether to mark as counterable or not
# Each Event will have something it actual does if it happens
# Cards will define their own events
# Events will be distinguishable based on context

#EVENT_DEFAULT
#EVENT_JOIN
#EVENT_DIE
#EVENT_CARD_PLAY

class Event:
    """An event that is about to happen and can be interacted with.
These are not shown to Players; only internal use."""
    next_uid = 0
    def __init__(self, context, resolve_effect=None):
        self.context = context
        self.resolve_effect = resolve_effect
        self.cancelled = False
        self.fired = False
        self.tried_to_fire = False
        self.resolved = False
        self.post_events = [] # Events to happen if this one succeeds
        self.uid = Event.next_uid
        Event.next_uid += 1
        
    def queue(self, game):
        game.queue_event(self)
    def fire(self, game):
        """Formally let everyone know this exists and allow responses."""
        # TODO: Consider moving this game dependency out
        for info in self.pre_info():
            game.queue_info(info)
        self.fired = True
        self.tried_to_fire = True
        #print(str(self.context))
        # Game object will handle getting players and Cards to respond.
    def interrupt(self):
        self.fired = False
    def cancel(self, source):
        # TODO: Consider adding a cause here
        self.cancelled = source
        if self.is_(CARD_PLAY):
            self.context.play_option.cancelled = source
            
    def then_run(self, other):
        """A.then_run(B) means run B after A, if A succeeds."""
        self.post_events.append(other)
    def now_queue(self, game, new_event):
        """Fire off a new Event now; this will interrupt, but Game handles that logic."""
        game.queue_event(new_event)
        
    def resolve(self, game):
        """Run the actual effect of the event, if it wasn't prevented, and fire post events"""
        self.resolved = True
        if self.cancelled:
            # TODO: Cancelled info?
            return
        # Events should not fire during resolution - but they may be put on the queue
        game.pause_events()
        if self.resolve_effect:
            # Allow Event callbacks to be of the following forms:
            # f()
            # f(this_event)
            # f(this_event, game)
            if (argc := num_args(self.resolve_effect)) == 2:
                self.resolve_effect(self, game)
            elif argc == 1:
                self.resolve_effect(self)
            else:
                self.resolve_effect()
        for event in self.post_events:
            game.queue_event(event.following(self))
        for info in self.post_info():
            game.queue_info(info)
        # TODO: should this resume before or after info?
        game.resume_events()
        
    def following(self, previous_event):
        """Used to track information across Events; e.g. Cardinal and which card a Capitalist picked"""
        # Perform any required data extraction (e.g., self.context.card = previous_event.context.card)
        # Then return self
        return self
    
    def pre_info(self):
        """Event has just fired."""
        # Use self.tried_to_fire to tell if this is new or not
        # Make the context do this.
        return self.context.pre_info(self)
    def post_info(self):
        """Event has completed; share with the class."""
        # Make the context do this.
        return self.context.post_info(self)
    def is_(self, type_):
        return self.context.is_(type_)
    
