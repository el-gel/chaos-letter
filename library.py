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
    cardback = 1

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
                ev.context.death_event.cancel()
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
        if po.targets and po.parameters["number"] is not None:
            for target in po.targets:
                if not target.alive:
                    continue
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
    cardback = 1

class DeepOnes(Investigator):
    name = "Deep Ones"
    type_ = DEEP_ONES
    insane = 1
    def on_play(self, play_event):
        po = play_event.context.play_option
        if po.targets:
            for target in po.targets:
                if not target.alive:
                    continue
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
        if po.targets:
            for target in po.targets:
                # Event doesn't actually do anything, the important bit is the info sent
                seen_card = which_card_query(self.game, target, play_event.context)
                see_context = SeeCardContext(players=(self.controller, target),
                                             card=seen_card,
                                             source=self)
                self.do_event(see_context)
    def sane_play_options(self):
        ret = []
        for player in self.valid_targets():
            ret.append(self.option(targets=(player,), str_fmt="Looking at {po:target}'s hand"))
        if not ret:
            return [(self.option(targets=(), str_fmt="Looking at nothing"), 0)]
        return [(rr,0) for rr in ret]

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
