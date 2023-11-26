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
    def __init__(self, context, resolve_effect=None, if_cancelled=None):
        self.context = context
        self.resolve_effect = resolve_effect
        self.if_cancelled = if_cancelled
        self.cancelled = False
        self.fired = False
        self.tried_to_fire = False
        self.resolved = False
        self.pre_events = [] # Events to happen before this, but only if it succeeds
        # Example: Assassin kills, Liber Ivonis blocking death
        self.queued_pre_events = [] # pre events that have been queued
        self.post_events = [] # Events to happen if this one succeeds
        # Example: Potentially Cardinal looking at ability (distinct from swap)
        self.queued_post_events = [] # post events that have been queued
        self.linked_pre = None # Which Event ran this one as a post_event
        self.linked_post = None # Which Event ran this one as a pre_event
        self.grouping = [self] # Grouped events; e.g., the discard, draw and play of a Quick Play
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
        """Something happened during attempted resolution."""
        self.fired = False
    def cancel(self, source):
        """Cancel an Event due to source."""
        self.cancelled = source
        if self.is_(CARD_PLAY):
            self.context.play_option.cancelled = source
        # Also cancel any queued pre or post events that were waiting to happen
        for event in self.queued_pre_events + self.queued_post_events:
            if not event.resolved:
                event.cancel(FIZZLE)

    def first_run(self, other):
        """A.first_run(B) means run B before A, if A succeeds. B is allowed to cancel A."""
        self.pre_events.append(other)
    def then_run(self, other):
        """A.then_run(B) means run B after A, if A succeeds."""
        self.post_events.append(other)
    def now_queue(self, game, new_event):
        """Fire off a new Event now; this will interrupt, but Game handles that logic."""
        game.queue_event(new_event)
    def group_with(self, others):
        """Group this Event with others. Adds to grouping, not replacement."""
        all_events = list(self.grouping)
        # Kind of preserves ordering
        for event in others:
            for pre_group_ev in event.grouping:
                if pre_group_ev not in all_events:
                    all_events.append(pre_group_ev)
        for event in all_events:
            event.grouping = all_events # Same ref for all; could use that?

    def callback(self, fn, game):
        """Run a callback for a (possibly None) function, accounting for its parameters."""
        if fn:
            # Allow Event callbacks to be of the following forms:
            # f()
            # f(this_event)
            # f(this_event, game)
            if (argc := num_args(fn)) == 2:
                fn(self, game)
            elif argc == 1:
                fn(self)
            else:
                fn()
        
    def resolve(self, game):
        """Run the actual effect of the event, if it wasn't prevented, and fire post events"""
        
        # TODO: ordering of pre / post events
        # Try to find the associated player, and then go in that order
        # If multiple events for a player, ask them the ordering
        # Not sure when this will be relevant though

        # Events should not fire during resolution - but they may be put on the queue
        was_paused = game.pause_events()

        if self.cancelled:
            self.resolved = True
            self.callback(self.if_cancelled, game)
            if not was_paused: game.resume_events()
            # TODO: Cancelled info?
            return
        
        # If there are any pre-events, then queue them all and return
        # We leave this unresolved so that it fires again (if not cancelled)
        # We clear pre_events so we don't keep firing them
        # We also start the queue again to actually play those events
        if self.pre_events:
            # Need to re-queue; this event was removed before resolution
            self.queue(game)
            # Put events in order; this may mean querying players
            for event in game.order_events(self, self.pre_events):
                event.linked_post = self
                self.queued_pre_events.append(event)
                game.queue_event(event)
            self.pre_events = []
            if not was_paused: game.resume_events()
            return # Don't continue; this event will fire again
        
        # No pre events; so now this is considered resolved
        self.resolved = True
        self.callback(self.resolve_effect, game)

        # Resolution marked this as cancelled, which means no post events / info
        if self.cancelled:
            # TODO: cancelled info?
            self.callback(self.if_cancelled, game)
            if not was_paused: game.resume_events()
            return
        
        # Just put all the post events on the stack.
        # This interrupts this event, but it's been marked as resolved, so won't try again.
        for event in game.order_events(self, self.post_events):
            event.linked_pre = self
            self.queued_post_events.append(event)
            game.queue_event(event)
            
        # TODO: cancelled / not cancelled info. Also check if cancelled here again
        for info in self.post_info():
            game.queue_info(info)
            
        # TODO: should this resume before or after info?
        if not was_paused: game.resume_events()
    
    def pre_info(self):
        """Event has just fired."""
        # TODO: Use self.tried_to_fire to tell if this is new or not
        # Make the context do this.
        return self.context.pre_info(self)
    def post_info(self):
        """Event has completed; share with the class."""
        # Make the context do this.
        return self.context.post_info(self)
    def is_(self, type_):
        return self.context.is_(type_)

    # Prevent Event leaking by only giving the context - but should not happen
    def public_info(self, for_):
        log.warn("Public info called for an Event object: " + str(self))
        return public(self.context, for_)
    def private_info(self, for_):
        log.warn("Private info called for an Event object: " + str(self))
        return private(self.context, for_)

    def __str__(self):
        return "Event: {"+ str(self.context) + "}"
    
