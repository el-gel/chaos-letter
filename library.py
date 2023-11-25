import logging
log = logging.getLogger(__name__)

from cards import *
from events import Event
from event_utils import *
from cl_constants import *
from utils import *
from query_utils import *
from info import *
from players import *

# Specific cards.

class Handmaid(Card):
    name = "Handmaid"
    type_ = HANDMAID
    value = 4
    play_str_fmts = ("{c} played for protection.",)
    def on_play(self, play_event):
        self.holder.protected = True
    def see_turn_start_event(self, ev):
        # The turn_played is incremented after the turn actually starts
        if ev.context.player == self.holder and self.holder.turns_played == self.turn_played \
            and self.played_as.mode != INSANE: # For Liber Ivonis etc.
            def unprotect(ev):
                ev.context.player.protected = False
            self.do_after(ev, ProtectionLossContext(ev.context.player, self),
                              resolve_effect=unprotect)

class ElderSign(Handmaid):
    name = "Elder Sign"
    type_ = ELDER_SIGN
    cardback = LOVECRAFT

class LiberIvonis(ElderSign):
    name = "Liber Ivonis"
    type_ = LIBER_IVONIS
    insane = 1
    ins_play_str_fmts = ("{c} played for IMMORTALITY.",)
    def on_play(self, play_event):
        po = play_event.context.play_option
        if po.mode == INSANE:
            # Does nothing on play, actually triggers from discard
            return
        super().on_play(play_event)
    def see_death_event(self, death_event):
        ctx = death_event.context
        if death_event.cancelled:
            return # Don't need to do anything
        if self.played_as and self.played_as.mode == INSANE and \
           self.controller == ctx.player:
            def cancel_death(ev):
                # Linked event will be the death
                if ev.linked_post.cancelled:
                    # Already was stopped; cancel this one too
                    ev.cancel(FIZZLE)
                    return
                ev.linked_post.cancel(self)
            death_event.first_run(Event(CancelDeathContext(ctx.player, source=self,
                                                           death_event=death_event,
                                                           death_ctx=ctx),
                                        resolve_effect=cancel_death))
    def insane_play_options(self):
        return self.sane_ops_as_insane()


class Guard(Card):
    name = "Guard"
    type_ = GUARD
    value = 1
    play_str_fmts = ("{c} targeting nobody.",
                     "Does {po:target} have a {po:number}?")
    def on_play(self, play_event):
        po = play_event.context.play_option
        # May not have been able to target anyone. Maybe we get multiple targets later.
        for target in living(po.targets):
            hit = False
            for card in target.hand:
                if card.value == po.parameters["number"]:
                    hit = True
                    break
            if hit:
                trigger_death(self.game, target, source=po, card=self)
    def sane_play_options(self):
        ret = []
        for player in self.valid_targets():
            for i in GUARD_CHOICES:
                ret.append(self.option(targets=(player,), parameters={"number":i}))
        if not ret:
            # No targets; so just target no-one and be sad
            ret.append(self.option(targets=()))
        return unforced(ret)

class Investigator(Guard):
    name = "Investigator"
    type_ = INVESTIGATOR
    cardback = LOVECRAFT

class DeepOnes(Investigator):
    name = "Deep Ones"
    type_ = DEEP_ONES
    insane = 1
    play_str_fmts = ("{c} targeting nobody.",
                     "Does {po:target} have a {po:number}?")
    ins_play_str_fmts = ("{c} (insanely) targeting nobody.",
                         "Does {po:target} have a 1? Or a {po:number}?")
    def on_play(self, play_event):
        po = play_event.context.play_option
        for target in living(po.targets):
            hit = False
            if po.mode == INSANE:
                for card in target.hand:
                    if card.value == 1:
                        hit = True
                        break
            if hit:
                trigger_death(self.game, target, source=po, card=self)
            elif po.parameters["number"] is not None:
                for card in target.hand:
                    if card.value == po.parameters["number"]:
                        hit = True
                        break
                if hit:
                    trigger_death(self.game, target, source=po, card=self)
    def insane_play_options(self):
        return self.sane_ops_as_insane()


class Priest(Card):
    name = "Priest"
    type_ = PRIEST
    value = 2
    play_str_fmts = ("{c} looking at noone.",
                     "Looking at {po:target}'s hand.",
                     "Looking at {po:targets} hands.")
    def on_play(self, play_event):
        po = play_event.context.play_option
        for target in living(po.targets):
            trigger_look(self.game, self.controller, target, source=po, context=play_event.context)
    def sane_play_options(self):
        ret = []
        for player in self.valid_targets():
            ret.append(self.option(targets=(player,)))
        if not ret:
            ret.append(self.option(targets=()))
        return unforced(ret)

class CatsOfUlthar(Priest):
    name = "Cats of Ulthar"
    type_ = CATS
    cardback = LOVECRAFT
    play_str_fmts = ("Meow (at no-one).",
                     "Meow.",
                     "Meow?")

class Baroness(Priest):
    name = "Baroness"
    type_ = BARONESS
    value = 3
    def sane_play_options(self):
        ret = []
        for player1 in self.valid_targets():
            ret.append(self.option(targets=(player1,)))
            for player2 in self.valid_targets():
                if player2 == player1:
                    continue
                ret.append(self.option(targets=(player1,player2)))
        if not ret:
            ret.append(self.option(targets=()))
        return unforced(ret)


class Nope(Card):
    name = "Nope"
    type_ = NOPE
    value = 2
    insane = 1
    cardback = LOVECRAFT
    def on_play(self, play_event):
        po = play_event.context.play_option
        if po.mode == ACTIVE_NOPE:
            po.parameters["cancelling"].card.cancel(self)
    def see_card_play_event(self, ev):
        if self.discarded:
            return
        ctx = ev.context
        if ctx.play_option.can_nope and ctx.card.controller != self.holder and \
           not ev.cancelled:
            if ask_nope_query(self.holder, ctx) == YES:
                nope_option = self.option(mode=ACTIVE_NOPE,
                                          targets=(ctx.card.controller,),
                                          parameters={"cancelling":ctx.play_option},
                                          quick=True)
                self.trigger_quick_play(nope_option)

class Prince(Card):
    name = "Prince"
    type_ = PRINCE
    value = 5
    play_str_fmts = ("How did you manage to {c} no-one?",
                     "Making {po:target} discard.",
                     "Making {po:targets} discard.")
    def on_play(self, play_event):
        po = play_event.context.play_option
        # Should always have a target for a Prince
        for target in po.targets:
            disc_card = ask_which_card(target, play_event.context)
            # Events will fire in reverse order here.
            trigger_draw(self.game, target, source=self)
            trigger_discard(self.game, target, source=po, card=disc_card)
    def sane_play_options(self):
        ret = []
        for player in self.valid_targets(include_me=True):
            ret.append(self.option(targets=(player,),
                                   str_fmt="Making {po:target} discard."))
        return unforced(ret)

class Randolph(Prince):
    name = "Randolph Carter"
    type_ = RANDOLPH
    cardback = LOVECRAFT

class Capitalist(Prince):
    name = "Capitalist"
    type_ = CAPITALIST
    insane = 1
    ins_play_str_fmts = ("Getting an extra card for keeps.",)
    def on_play(self, play_event):
        po = play_event.context.play_option
        if po.mode == INSANE:
            # Draw, but no discard. Player will end up with a second card forever
            trigger_draw(self.game, self.controller, po)
        else:
            super().on_play(play_event)
    def insane_play_options(self):
        # Currently this doesn't target, only gives second card to controller
        return unforced((self.option(targets=(), mode=INSANE),))

class MiGo(Randolph):
    name = "MiGo"
    type_ = MIGO
    insane = 1
    ins_play_str_fmts = ("Not putting anyone's head in a jar.",
                         "Putting {po:target}'s head in a jar.",
                         "Putting {po:targets} heads in jars.")
    def on_play(self, play_event):
        po = play_event.context.play_option
        if po.mode == INSANE:
            # TODO: confirm that the right Info is shown for this card
            for target in po.targets:
                cards_to_take = [card for card in target.hand]
                for card in cards_to_take:
                    target.take(card)
                    self.controller.give(card)
                target.give(BrainCase(game=self.game))
                self.game.make_play(self.controller)
        else:
            super().on_play(play_event)
    def insane_play_options(self):
        # Can't target self with this - but can target no-one
        ret = [self.option(mode=INSANE, targets=(player,))
                 for player in self.valid_targets()]
        if not ret:
            ret.append(self.option(mode=INSANE, targets=()))
        return unforced(ret)

class Princess(Card):
    name = "Princess"
    type_ = PRINCESS
    value = 8
    play_str_fmts = ("Committing die with {c}.",)
    def trigger_play_events(self, play_option):
        # Actually have to override this for SHUFFLE mode, since the card doesn't get played/discarded.
        if play_option.mode == SHUFFLE:
            # Don't set the play option for this card, or turn_played. Don't discard or play.
            trigger_shuffle(self.game, self, play_option)
        else:
            super().trigger_play_events(play_option)
    def on_play(self, play_event):
        pass
    def on_discard(self, discard_event):
        # Always die. 
        trigger_death(self.game, discard_event.context.player,
                      source=discard_event.context.source, card=self)
    def sane_play_options(self):
        # Princess can't be nope'd - not that it would have stopped the death
        ret = [self.option(can_nope=False)]
        if all([card.value == 8 for card in self.holder.hand]):
            ret.append(self.option(mode=SHUFFLE, can_nope=False,
                                   str_fmt="Shuffling unsuspiciously."))
        return unforced(ret)

class Necronomicon(Princess):
    name = "Necronomicon"
    type_ = NECRONOMICON
    cardback = LOVECRAFT

class BrainCase(Princess):
    name = "MiGo Brain Case"
    type_ = BRAIN_CASE
    cardback = LOVECRAFT
    value = 0
    insane = 1

class Cthulhu(Necronomicon):
    name = "Cthulhu"
    type_ = CTHULHU
    insane = 1
    ins_play_str_fmts = ("CTHULHU FHTAGN",)
    def cthulhu_active(self):
        # Check insaneness is >= 2, ignoring this card if in the discard pile
        # If we change our mind on primeness counting for Cthulu, this is where to change it
        return (self.controller.how_insane() - (self.insane if self in self.controller.discard else 0)) >= 2
    # Cthulu says "if discarded on your turn (not for insanity check), win if twice insane already, else lose"
    # However, it can still be noped.
    # To do this, the insane play effect is "win the game",
    #   the discard effect is "die if not discarded on their turn or not insane enough
    #                          die if discarded on turn due to insanity check
    #                          win if discarded on turn, but not played
    #                          nothing if discarded on turn due to play (the play effect will do the win)"
    # This does mean that you can un-nopeably win by princeing self, rather than playing cthulu.
    # If people disagree, then the way to fix is to make the discard event create a 'cthulu wins' event
    #   and then the Nope looks for this as well. There is then no play effect, only the discard.
    def on_play(self, play_event):
        po = play_event.context.play_option
        if po.mode == INSANE:
            if self.cthulhu_active():
                self.game.win_game(self.controller, self)
    def on_discard(self, discard_event):
        # Die if discarded on not your turn, or not insane enough, or it's an insanity check
        reason = discard_event.context.source
        player = discard_event.context.player
        if reason == INSANITY_CHECK or self.game.current_player != player or \
           not self.cthulhu_active():
            trigger_death(self.game, player,source=reason, card=self)
        elif self.played_as is None: # This card wasn't played, but it is our turn
            self.game.win_game(self.controller, self)
        # This card was played for the discard, and it's active. on_play will win for us
    def insane_play_options(self):
        if self.cthulhu_active():
            return unforced((self.option(mode=INSANE),))
        else:
            return []

class Count(Card):
    name = "Count"
    type_ = COUNT
    value = 5
    def round_end_score_edit(self, in_):
        if self.discarded:
            return in_ + 1
        else:
            return in_

class NoU(Count):
    name = "No U"
    type_ = NO_U
    # TODO


##ASSASSIN
##JESTSASSIN
##GUARD
##PRIEST
##CARDINAL
##SPY
##BARONESS
##BARON
##HANDMAID
##BOUNTY_HUNTER
##PRINCE
##CAPITALIST
##REVERSE
##INSANE_REVERSE
##CONSTABLE/CRIME_BOSS
##KING
##COUNTESS
##DOWAGER_QUEEN
##PRINCESS
##PRINCESS_PRIME (actually just a different cardfront)
##BISHOP
##
##BRAIN_CASE
##INVESTIGATOR
##DEEP_ONES
##CATS_OF_ULTHAR
##NOPE
##GOLDEN_MEAD
##YITH
##HOUNDS
##ELDER_SIGN
##IMMORTAL_TOME
##ARMITAGE
##MIGO
##RANDOLPH
##NYARLATHOTEP
##SILVER_KEY
##TRAPEZOID
##NECRONOMICON
##CTHULU
