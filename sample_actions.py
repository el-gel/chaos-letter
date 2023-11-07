import random

from player_actions import *
from cl_constants import *

class RandomActions(PlayerActions):    
    def respond_to_query(self, query):
        return random.choice(query.options)

    def info_event(self, info):
        pass # I don't care!

class LoggingActions(PlayerActions):
    def setup(self):
        self.infos = []
        self.debug = False
        self.other = None
        self.logging = True
    def info_event(self, info):
        self.infos.append(info)
        if self.logging: print("["+str(len(self.infos)-1) + "] To " + self.name + ": " + str(info.context))
        if self.debug and self.logging:
            card = getattr(info.context, "card", None)
            if card:
                print("     Relevant card is: " + repr(card))
            if self.other:
                print("     " + self.other.name + "'s holding: " + repr(self.other.hand))
    def respond_to_query(self, query):
        if self.logging: print("-----" + self.name + " asked: " + str(query.context))
        if self.logging: print("     with options: " + str([str(op) for op in query.options]))
        # For testing, can we select only 4's with guard likes?
        # Also, good to know what's a pain point
        if query.context.type_ == WHICH_PLAY:
            good_ops = []
            ins_ops = []
            LIB = None
            for op in query.options:
                if op.card.type_ in (GUARD, INVESTIGATOR, DEEP_ONES):
                    if not op.targets or op.parameters["number"] in (2,4):
                        good_ops.append(op)
                        if op.mode == INSANE:
                            ins_ops.append(op)
                else:
                    good_ops.append(op)
                    if op.mode == INSANE:
                        if op.card.type_ == LIBER_IVONIS:
                            LIB = op
                        ins_ops.append(op)
            if ins_ops:
                good_ops = ins_ops
            if LIB:
                good_ops = [LIB]
                if self.logging:
                    print("###############################")
                    print("###########IMMORTAL############")
                    print("###############################")
            if self.logging: print("     Only considering: " + str([str(op) for op in good_ops]))
            return random.choice(good_ops)
        return random.choice(query.options)
