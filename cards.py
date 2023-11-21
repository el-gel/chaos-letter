import logging
log = logging.getLogger(__name__)

from events import *
from event_utils import *
from cl_constants import *
from access_control import *
from utils import *
from info import *
from players import *

# Cards should store their own triggers and events, so the Game doesn't need to handle each one
# There should be events which always happen and events with choices
# Cards should store their own targeting options
# Events may want to happen after the current events are resolving (constable)
# We should be able to handle the event of "at end of game"
# Events should be able to trigger from discard
# Events should be able to trigger from being targeted

# Play options should be able to be forced
# Forcing has three levels:
# - UNFORCED (not forced)
# - FORCED (forced, but if multiple then have choice)
# - ALL_FORCED (forced, and must play all at once)

# Things that cause events:
# - this card is played (standard)
# - this card is discarded (princess)
# - another event happens
# -- someone else plays something (reverse, nope)
# -- targeted with a guard (assassin)
# -- targeted with a looking effect (crime boss)
# -- player wins (jester)
# -- player dies (constable, immortal tome)
# -- end of game (count)

# Make InsaneCard as a subclass, with a discard event of "if from insanity check, die"
# Actually, just make that a normal card thing, with a check of 'if this is insane'

# TODO: Do I want to have a public 'face-up' option, rather than revealing the private info for discarded/played cards?
# Cannot subclass this (else class reveals hidden info)
class PublicCard(PublicData):
    def set_data(self, backer, for_):
        self._RO = tuple(backer._PUBLIC_ATTRS)
        for ro_val in self._RO:
            if ro_val in backer._PUBLIC_FACEUP_ATTRS:
                setattr(self, ro_val,
                    public(getattr(backer, ro_val), for_) if backer.faceup else None)
            else:
                setattr(self, ro_val,
                    public(getattr(backer, ro_val), for_))

    def __str__(self):
        if self.faceup:
            return self.name
        else:
            return str(self.cardback)


class PrivateCard(PrivateData):
    def __str__(self):
        return self.name
    
    
# Base Card object, overwritten by subclass cards

class Card(PublicUser, PrivateUser):
    next_uid = 0
    _PUBLIC_FACEUP_ATTRS = ("name", "type_", "value", "insane", "cardfront", "played_as",
                           "turn_played")
    _PUBLIC_ATTRS = _PUBLIC_FACEUP_ATTRS + ("cardback", "holder", "discarded", "faceup",
                                            "controller")
    _PUBLIC_CLASS = PublicCard
    _PRIVATE_ATTRS = ("name", "type_", "value", "insane", "cardback", "cardfront")
    _PRIVATE_CLASS = PrivateCard

    # Overwriting attributes
    name = "DEFAULT"
    type_ = DEFAULT
    value = -1
    insane = 0 # Allow for this being > 1. E.g. "this card counts as triply insane"
    cardback = DEFAULT
    cardfront = BLANK
    # Formatting for play options, indexed by number of targets
    # .option() uses this if not given str_fmt, and will use the number of targets to choose which
    # If more targets than length, then will use the last in the list
    # Blank list for don't change from the default behaviour
    play_str_fmts = ()#("Defaulting on no-one.", "Defaulting on single {po:target}.",
                     #"Defaulting on two {po:targets}.", "Defaulting on more than three {po:targets}.")
    # Same, but for insane plays. Also used by sane_ops_as_insane
    ins_play_str_fmts = ()#("Insanely defaulting on no-one.", "Insanely defaulting on one or more {po:targets}.")
    
    def __init__(self, cardback=None, cardfront=None, game=None):
        # The only potential distinguishing features between different cards is the back and front images
        self.cardback = self.__class__.cardback if cardback is None else cardback
        self.cardfront = self.__class__.cardfront if cardfront is None else cardfront
        self.game = game
        self.uid = Card.next_uid
        Card.next_uid += 1
        self.reset()

    def reset(self):
        # I want this to be unnecessary, but currently cards aren't stateless
        self.holder = None
        self.controller = None # Used for the player that's getting the effect, e.g. a reverser
        self.played_as = None # PlayOption to track how it was used; e.g. as Jester or Assassin. Managed by card logic, not Game
        self.played_events = () # Track the events this card caused on play. Internal use for e.g. cancelling
        self.turn_played = -1 # -1 for not played, 0 is 'played, but before they got a real turn' e.g. Nope
        self.discarded = False
        self.to_invalidate = [] # Tracking copies of PublicInfo we've passed out
        self._reset_public_info()
        self._reset_private_info()

    def put_in_game(self, game):
        self.game = game

    # Public and private info management.

    def invalidate_public(self, for_=ALL):
        """Invalidate the public info object for this card.

Used when we need to 'forget' which card this is.
E.g., if someone was keeping track of public card objects, they'd know whether a played card was the just drawn one.
So when a card leaves or enters a zone with multiple face down cards, they're all invalidated.
The holder's Player info is also invalidated, which will trigger recreating relevant cards.
(Otherwise, we'd need a closure around in order to keep the Public player info up to date)."""
        super().invalidate_public(for_)
        # We want the public Player info to be immediately fixed up. This will make new public info for this card.
        if self.holder:
            self.holder.invalidate_public()

    def invalidate_private(self, for_=ALL):
        """Like invalidate_public, but for private info."""
        super().invalidate_private(for_)
        if self.holder:
            self.holder.invalidate_private()
        
    # Creating targeting options.
    
    def play_options(self):
        """Returns a list of (PlayOption, forcing_level) tuples."""
        return (self.insane_play_options() if self.holder.how_insane() else []) + self.sane_play_options()
    
    def sane_play_options(self):
        """Returns a list of (PlayOption, forcing_level) tuples. Should be overridden."""
        return [(self.option(), UNFORCED)]
    
    def insane_play_options(self):
        """Returns a list of (PlayOption, forcing_level) tuples. Should be overridden for insane cards."""
        return []

    def sane_ops_as_insane(self, str_fmt=None):
        """Returns the sane play options, but all with INSANE mode and optionally changed str_fmt."""
        to_insane = self.sane_play_options()
        for sop, force in to_insane:
            sop.mode = INSANE
            if str_fmt:
                sop.str_fmt = str_fmt
            elif new_ins_str := self.str_fmt_for_targets(INSANE, sop.targets):
                sop.str_fmt = new_ins_str
        return to_insane

    def reverse_play_options(self, play_option, reverser):
        """Returns a list of PlayOptions that are valid reverses for it. Empty list if not reversible."""
        # Default is [] if no targets or multiple, else the same option but with holder as target
        # This doesn't work for multiple targets well, but that may be a small enough list to do manually
        if reverser == play_option.controller:
            return [] # Can't reverse own thing
        if len(play_option.targets) == 1:
            return [play_option.copy(targets=(self.holder,))]
        return []

    def valid_targets(self, include_me=False):
        """All possible targets in the game."""
        return self.game.targetable_players(not_including=None if include_me else self.controller)
    
    def option(self, mode=None, targets=(), parameters=None, quick=False, can_nope=True, str_fmt=None):
        """Makes a PlayOption with these parameters."""
        po = PlayOption(self, mode=mode, targets=targets,
                        parameters=parameters, quick=quick,
                        can_nope=can_nope)
        if str_fmt or (str_fmt := self.str_fmt_for_targets(mode, targets)):
            po.str_fmt = str_fmt
        return po

    def str_fmt_for_targets(self, mode, targets):
        """The most appropriate str_fmt, from play_str_fmts or ins_play_str_fmts."""
        if mode == INSANE and self.ins_play_str_fmts:
            str_i = min(len(self.ins_play_str_fmts)-1, len(targets))
            return self.ins_play_str_fmts[str_i]
        elif self.play_str_fmts:
            str_i = min(len(self.play_str_fmts)-1, len(targets))
            return self.play_str_fmts[str_i]
        return ""

    # TODO: option_for_each, which would take a list of modes, targets, parameters etc and return the right list of tuples
    # Need to decide how this is most useful; for each valid target? Provided list of target tuples? Provided list of targets and number in each option tuple?
    # Sensible defaults? Detection of list of targets vs list of target tuples? Forcing value? How to do for each parameter option?
    # Purpose of this function is to make library card code simpler

    # Make events happen.
    
    def trigger_play_events(self, play_option):
        """Puts events into the game and also sets how this was played. Does not usually need to be overridden."""
        self.played_as = play_option
        self.turn_played = self.holder.turns_played
        self.played_events = self.play_events(play_option)
        # Ordered so the discard happens first
        all_events = self.played_events + [get_discard_event(self.holder, play_option, self)]
        # Group together, for ordering purposes
        all_events[0].group_with(all_events)
        self.game.queue_events(all_events)

    def trigger_quick_play(self, play_option):
        """Puts events into the game for a quick play. Doesn't usually need overriding."""
        self.played_as = play_option
        self.turn_played = self.holder.turns_played
        self.played_events = self.play_events(play_option)
        # Ordered to discard, draw, then do play events
        all_events = self.played_events + [get_draw_event(self.game, self.holder, QUICK_PLAY),
                                           get_discard_event(self.holder, play_option, self)]
        # Group events together, for ordering purposes
        all_events[0].group_with(all_events)
        self.game.queue_events(all_events)
        
    def play_events(self, play_option):
        """This stub is 'run on_play'. Linked, out of turn, or multiple effect cards need to override this method."""
        return [get_play_event(play_option, resolve_effect=lambda ev: self.on_play(ev))]

    def cancel(self, source):
        """Cancel all events this card produced."""
        for ev in self.played_events:
            ev.cancel(source)

    # Trigger methods
    # on_XXX methods are run as resolution effects and get passed the event during resolution.
    # see_event is called when another event is trying to fire, and gets passed the event that's firing.

    def on_play(self, play_event):
        """Used with simple 'one thing' cards. More complex cards should override play_events."""
        raise NotImplementedError()

    def on_quick_play(self, play_event):
        """Used  with simple 'one thing' quick plays. Override quick_play_events for more complex cards."""
        raise NotImplementedError()
    
    def on_draw(self, draw_event):
        # Here in case we add some new card that cares about being drawn
        pass
        
    def on_discard(self, discard_event):
        # Default insanity check thing
        reason = discard_event.context.source
        if self.insane and reason == INSANITY_CHECK:
            trigger_death(self.game, discard_event.context.player, source=INSANITY_CHECK, card=self)

    # 'enter' for gaining a holder, 'leave' for losing them.
    def on_enter_zone(self, player):
        """Triggered by Player.give and Player.put_in_discard."""
        self.holder = player
        self.controller = player
        self.invalidate_private()
        self.invalidate_public()

    def on_leave_zone(self):
        """Triggered by Player.take and Player.take_from_discard. Guaranteed to happen before on_enter_zone if changing players."""
        self.reset()
        self.invalidate_private()
        self.invalidate_public()

    def see_event(self, event):
        # For cards that do something when something happens; e.g. Constable heart, or no-U.
        # Default behaviour is to use a context splitter to make sub-overriding better.
        split_context(event.context, self, "see_{t}_event", event)

    def see_other_event(self, other_event):
        # Required for the context splitter to work.
        pass

    def round_end_score_edit(self, in_):
        """Mostly just for Counts."""
        # Make sure to check if card's actually discarded, if relevant.
        return in_

    # Convenience methods.

    def give_to(self, player):
        """Give this card to a player."""
        player.give(self)

    def take_from_holder(self):
        """Take this card away from its holder, if they exist."""
        if self.holder:
            if self.discarded:
                self.holder.take_from_discard(self)
            else:
                self.holder.take(self)

    def swap_to(self, other):
        """If this card is held by someone, take this card from them. Then, give it to another."""
        self.take_from_holder()
        self.give_to(other)

    def do_event(self, context, resolve_effect=None):
        """Run an Event with this context and effect."""
        Event(context, resolve_effect).queue(self.game)

    def do_after(self, event, context, resolve_effect=None):
        """Do a new Event conditional on event happening."""
        event.then_run(Event(context, resolve_effect))

    @property
    def faceup(self):
        # Possibly there's a 'not discarded, but faceup' thing. Like a card that makes someone play with a revealed hand.
        return self.discarded
        
    def like(self, other):
        return like(self, other)
    def sane_like(self, other):
        return sane_like(self, other)
    def insane_like(self, other):
        return insane_like(self, other)
    def is_(self, type_):
        return self.type_ == type_
    def __str__(self):
        return self.name



# TODO: Should these be static?
class PublicPlayOption(PublicData):
    def __str__(self):
        ret = str(self.card)
        ret += " played as " + str(self.mode)
        ret += " targeting " + liststr(self.targets)
        ret += " with " + dictstr(self.parameters) if self.parameters else ""
        return ret
            

class PrivatePlayOption(PrivateData):
    def __str__(self):
        ret = str(self.card)
        ret += " played as " + str(self.mode)
        ret += " targeting " + liststr(self.targets)
        ret += " with " + dictstr(self.parameters) if self.parameters else ""
        return ret


class PlayOption(PublicUser, PrivateUser):
    _PUBLIC_ATTRS = ("card", "mode", "targets", "parameters", "cancelled", "quick", "can_nope")
    _PUBLIC_CLASS = PublicPlayOption
    _PRIVATE_ATTRS = ("card", "mode", "targets", "parameters", "cancelled", "quick", "can_nope")
    _PRIVATE_CLASS = PrivatePlayOption
    def __init__(self, card, mode=None, targets=(), parameters=None, quick=False, can_nope=False, controller=None):
        self.card = card
        self.mode = mode if mode else card.name # E.g. Jester/Assassin. Default is fine for single mode cards
        self.targets = targets
        self.parameters = parameters if parameters else {} # E.g. Guard choice
        self.cancelled = False
        self.quick = quick
        self.can_nope = can_nope
        self.controller = controller if controller else card.controller
        self._reset_public_info()
        self._reset_private_info()

    def trigger(self):
        if self.quick:
            self.card.trigger_quick_play(self)
        else:
            self.card.trigger_play_events(self)

    def copy(self, card=None, mode=None, targets=None, parameters=None, quick=None, can_nope=None):
        card = self.card if card is None else card
        card = self.mode if mode is None else mode
        card = tuple(self.targets) if targets is None else targets
        card = dict(self.parameters) if parameters is None else parameters
        card = self.quick if quick is None else quick
        card = self.can_nope if can_nope is None else can_nope
        return PlayOption(card, mode=mode, targets=targets, parameters=parameters,
                          quick=quick, can_nope=can_nope)
        
    @property
    def target(self):
        """Get first target only."""
        if self.targets:
            return self.targets[0]
        return None

