import logging
log = logging.getLogger(__name__)

from cards import *
from events import *
from cl_constants import *
from utils import *
from queries import *
from info import *
from players import *

# Specific cards.

class Handmaid(Card):
    name = "Handmaid"
    type_ = HANDMAID
    value = 4
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
    def on_play(self, play_event):
        po = play_event.context.play_option
        if po.mode == INSANE:
            # Does nothing on play, actually triggers from discard
            return
        super().on_play(play_event)
    def see_death_event(self, death_event):
        ctx = death_event.context
        if self.played_as and self.played_as.mode == INSANE and \
           self.controller == ctx.player:
            def cancel_death(ev):
                ev.context.death_event.cancel(self)
            self.do_event(
                CancelDeathContext(ctx.player, source=self,
                                   death_event=death_event, death_ctx=ctx),
                resolve_effect=cancel_death)
    def insane_play_options(self):
        return [(self.option(mode=INSANE, str_fmt="To go immortal"), 0)]


class Guard(Card):
    name = "Guard"
    type_ = GUARD
    value = 1
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
                ret.append(self.option(targets=(player,), parameters={"number":i},
                                    str_fmt="Does {po:target} have a {po:number}?"))
        if not ret:
            # No targets; so just target no-one and be sad
            ret.append(self.option(targets=(), str_fmt=self.name + " targeting nobody"))
        return [(rr,0) for rr in ret]

class Investigator(Guard):
    name = "Investigator"
    type_ = INVESTIGATOR
    cardback = LOVECRAFT

class DeepOnes(Investigator):
    name = "Deep Ones"
    type_ = DEEP_ONES
    insane = 1
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
        # Same as sane options, but with mode INSANE
        to_insane = self.sane_play_options()
        for sop, force in to_insane:
            sop.mode = INSANE
            if sop.targets:
                sop.str_fmt = "Does {po:target} have a 1 or a {po:number}?"
        return to_insane


class Priest(Card):
    name = "Priest"
    type_ = PRIEST
    value = 2
    def on_play(self, play_event):
        po = play_event.context.play_option
        for target in living(po.targets):
            # Event doesn't actually do anything, the important bit is the info sent
            seen_card = ask_which_card(target, play_event.context)
            see_context = SeeCardContext(players=(self.controller, target),
                                         card=seen_card,
                                         source=self)
            self.do_event(see_context)
    def sane_play_options(self):
        ret = []
        for player in self.valid_targets():
            ret.append(self.option(targets=(player,),
                                   str_fmt="Looking at {po:target}'s hand"))
        if not ret:
            return [(self.option(targets=(), str_fmt="Looking at nothing."), 0)]
        return [(rr,0) for rr in ret]

class CatsOfUlthar(Priest):
    name = "Cats of Ulthar"
    type_ = CATS
    cardback = LOVECRAFT
    def sane_play_options(self):
        ret = super().sane_play_options()
        for op, force in ret:
            op.str_fmt = "Meow."
        return ret

class Baroness(Priest):
    name = "Baroness"
    type_ = BARONESS
    value = 3
    def sane_play_options(self):
        ret = []
        for player1 in self.valid_targets():
            ret.append(self.option(targets=(player1,),
                                   str_fmt="Looking at {po:target} only."))
            for player2 in self.valid_targets():
                if player2 == player1:
                    continue
                ret.append(self.option(targets=(player1,player2),
                                       str_fmt="Looking at {po:targets}."))
        if not ret:
            return [(self.option(targets=(), str_fmt="Looking at nothing."), 0)]
        return [(rr,0) for rr in ret]


class Nope(Card):
    name = "Nope"
    type_ = NOPE
    value = 2
    insane = 1
    cardback = LOVECRAFT
    def on_play(self, play_event):
        po = play_event.context.play_option
        if po.mode == ACTIVE_NOPE:
            po.parameters["cancelling"].cancel(self)
    def see_card_play_event(self, ev):
        if self.discarded:
            return
        ctx = ev.context
        if ctx.play_option.can_nope and ctx.card.controller != self.holder and \
           not ev.cancelled:
            if ask_nope_query(self.holder, ctx) == YES:
                nope_option = self.option(mode=ACTIVE_NOPE,
                                          targets=(ctx.card.controller,),
                                          parameters={"cancelling":ctx.card},
                                          quick=True)
                self.trigger_quick_play(nope_option)
                                          
    
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
