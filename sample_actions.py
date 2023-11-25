import random

from player_actions import *
from cl_constants import *

class RandomActions(PlayerActions):    
    def respond_to_query(self, query):
        return random.choice(query.options)

    def info_event(self, info):
        pass # I don't care!


def log_actions(cls):
    class LoggingActions(cls):
        def setup(self):
            super().setup()
            self.infos = []
            self.queries = []
            self.debug = False
            self.logging = True
        # Yes this can be done with the logging module. Improve later.
        def log(self, s):
            if self.logging:
                print(s)
        def dbg(self, s):
            if self.debug:
                self.log(s)
        def log_query_in(self, query):
            self.queries.append(query)
            self.log("--"+self.name[0]+"--" + self.name + " asked: " + str(query.context))
            self.log("     with options: " + recstr(query.options))
        def log_query_out(self, query, resp):
            self.log("      Picking:")
            self.log(recstr(resp))
        def log_info(self, info):
            self.infos.append(info)
            self.log("["+self.name[0]+" "+str(len(self.infos)-1) + "] To " + self.name + ": " + str(info.context))
        def info_event(self, info):
            self.log_info(info)
            if self.debug:
                card = getattr(info.context, "card", None)
                if card:
                    self.log("     Relevant card is: " + repr(card))
            super().info_event(info)
        def respond_to_query(self, query):
            self.log_query_in(query)
            resp = super().respond_to_query(query)
            self.log_query_out(query, resp)
            return resp
    return LoggingActions

@log_actions
class BasicActions(PlayerActions):
    def setup(self):
        self.other = None
    def info_event(self, info):
        if self.debug and self.other:
            self.log("     " + self.other.name + "'s holding: " + repr(self.other.hand))
    def respond_to_query(self, query):
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
            self.log("     Only considering: " + recstr(good_ops))
            return random.choice(good_ops)
        self.log("Picking a random option: ")
        return random.choice(query.options)
