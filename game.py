import random
import logging
log = logging.getLogger(__name__)

from events import *
from players import *
from queries import *
from info import *
from context import *
from utils import *
from cards import *
from cl_constants import *


class PublicGameInfo:
    """Try to only allow Player objects access to relevant information"""
    def __init__(self):
        pass


class Game:
    """Handles running a game, firing Events around etc."""
    def __init__(self):
        self.info_queue = []
        self.event_queue = []
        self.events_paused = False
        self.all_info_history = []
        self.round_info_history = []
        self.players = [] # The promise is that this remains stable, barring priming players
        self.player_order = [] # But this may change (Spy, priming)
        # The deck is a list of cards in the order they'll be drawn
        # Shuffling will shuffle the list in place
        # This is to allow players to look at the cardbacks in order
        self.deck = []
        self.all_cards = []
        self.aside = []
        self.active = False # Whether a round is running
        self.pull_aside = lambda deck: [self.draw(), self.draw()]
        self.current_player = None # This is at a specific Player, *not* index (due to Priming and Spy)
        self.turn_order = 1
        self.last_loser = None # This is explicitly not cleared between rounds; if a round ends with no death, take the loser of the prior round
        self.round_winner = None
        self.winner = None

    # Setup and configuration.
        
    def setup(self, deck, players, pull_aside=None):
        if len(players) > 2*len(deck):
            # 2x to handle priming, may need to have better checking
            raise ValueError("Too many players")
        # Set up an 'original' deck, which is then used by reset_deck
        self.all_cards = list(deck)
        for card in self.all_cards:
            card.put_in_game(self)
        # TODO: make a pull_aside thst pulls cards out of the deck until one of each cardback
        if pull_aside:
            self.pull_aside = pull_aside
        # Only add players when everything is ready; they may try to check things early
        for player in players:
            self.add_player(player)

    # Player handling.
            
    def add_player(self, player, order_i=None, draw=False):
        # Add player to player list, optionally draw them a card, and fire all past info history into them
        # No cards are expected to run this, so this is running the Event rather than being run from one
        if order_i is None:
            order_i = len(self.players)
        # Really, nothing should be able to interrupt this, but in case
        def do_add(ev):
            self.players.append(player)
            self.player_order.insert(order_i, player)
        self.show_history_to_player(player)
        Event(JoinContext(player, PRIME if player.prime_count else NEW),
              resolve_effect=do_add).queue(self)
        if draw:
            trigger_draw(self, player, JOINED)
        self.clear_event_queue()
    
    def kill_player(self, player):
        """Kill a player in a round, and prime them if needed."""
        # Check if player played; if not, prime them
        #  if they did, then give their non-prime form to last_loser
        # The death event will handle sending out Info, this is just the function
        # Immediately make them dead, so things like Princess discards don't matter
        player.alive = False
        for card in player.hand:
            trigger_discard(self, player, DEATH, card)
        if player.turns_played:
            if self.last_loser is None:
                # Assign loserness to un-primed form
                self.last_loser = player.unprimed()
        else:
            self.prime_player(player)
    
    def prime_player(self, player):
        # Add a prime player to the game (use prime() from players.py)
        # Add them just after the player they primed from
        prime_player = prime(player)
        self.add_player(prime_player, self.players.index(player), draw=True)

    def de_prime_players(self):
        # Remove all primed players - each Player keeps a reference for reuse later
        # Run just before the start of each round
        primed = [p for p in self.players if p.prime_count]
        oprimed = [p for p in self.player_order if p.prime_count]
        for p in primed:
            self.players.remove(p)
        for p in oprimed:
            self.player_order.remove(p)

    def drop_player(self, player, source=BY_CHOICE):
        """Remove a player from the game entirely; this can only happen between rounds."""
        # TODO: a way to request to leave at the end of the current round. Be sure to remove un-primed version
        if self.active:
            # Maybe replace player with a random actor?
            raise Exception("Can't leave the game when a round is running.")
        def do_drop(ev):
            self.players.remove(player)
            self.player_order.remove(player)
        Event(LeaveContext(player, source),
              resolve_effect=do_drop).queue(self)
        self.clear_event_queue()

    def reset_players(self):
        """Get Players ready at the start of the Game."""
        # De prime players, clear the primes out of there
        self.de_prime_players()
        # No events here; RoundStart event happens only after cleaning
        for player in self.players:
            self.reset_player(player)
            # Also deal with primed players
            while player.primed_to:
                player = player.primed_to
                self.reset_player(player)

    def reset_player(self, player):
        """Reset a specific Player."""
        # Let the Player class handle reset. Allows extending.
        player.reset()

    def show_history_to_player(self, player, all_=False):
        # Show the Info history to the player
        # Only show round history, unless given all_
        for info in (self.all_info_history if all_ else self.round_info_history):
            info.send_to(player)

    def living_players(self):
        """Get a list of living players. No order guarantee."""
        return [player for player in self.players if player.alive]

    def targetable_players(self, not_including=None):
        ni = not_including if isinstance(not_including, (list, tuple)) else (not_including,)
        return [player for player in self.living_players() if not player.protected and player not in ni]

    # Deck handling.

    def shuffle(self):
        random.shuffle(self.deck)

    def shuffle_in(self, card):
        self.deck.append(card)
        self.shuffle()
        for card in self.deck:
            card.invalidate_public()
            card.invalidate_private()

    def draw(self, from_aside=False):
        """Try to remove the top card of the deck, and return it.

If from_aside and the deck is empty, take from the aside cards.
If none of them left either, then I guess give them a braincase?"""
        if self.deck:
            return self.deck.pop()
        if from_aside:
            if self.aside:
                return self.aside.pop()
            # TODO: handle giving when no cards left at all
            raise NotImplementedError()
        raise EmptyDeckException()

    def reset_deck(self):
        for card in self.all_cards:
            # I haven't cleared state from cards yet, like I want to
            # So have to actually touch the cards here
            card.reset()
        self.deck = list(self.all_cards)
        self.shuffle()
        self.aside = self.pull_aside(self.deck)

    # Scoring.

    def give_heart(self, player, source):
        def do_give(ev):
            player.hearts += 1
        Event(ScoredContext(player, source, HEART),
              resolve_effect=do_give).queue(self)
        self.clear_event_queue()

    def give_insane_win(self, player, source):
        def do_give(ev):
            player.insane_hearts += 1
        Event(ScoredContext(player, source, INSANE_HEART),
              resolve_effect=do_give).queue(self)
        self.clear_event_queue()

    def make_round_winner(self, player, source):
        # Give heart or insane token depending on status
        if player.how_insane():
            self.give_insane_win(player, source)
        else:
            self.give_heart(player, source)
        self.round_winner = player

    def win_game(self, source, player):
        # End the round, but also set an overall winner
        self.end_round(source)
        self.winner = player

    # High-level running.
    
    def run_round(self):
        """Run a single round."""
        # Handles resetting and cleanup, as well as picking the start player and initial draw
        self.start_round()
        
        # Just keep doing turns until no longer active
        while self.play_turn(self.current_player):
            cur_i = self.player_order.index(self.current_player)
            # Go to next player in turn order (play_turn will skip dead ones, with no intervening Events)
            self.current_player = self.player_order[(cur_i + self.turn_order) % len(self.player_order)]

        # Reaching here means the round is over; did someone win?
        if self.winner:
            # Someone won the whole thing; Cthulu. Cut here
            return False
        
        # run_game will do the 'who won overall' check, so now only checking for the round
        if self.round_winner:
            # Someone won this round; cut here, but continue rounds
            return True
        
        # Deck out scenario; work out if anyone won, will fire an event if they did
        self.check_round_end_win()
    
    def run_game(self):
        # Keep running games until we have a winner
        # TODO: Consider multiple winners. E.g. bishop, jester etc. Cthulu should override them all too.
        while self.run_round():
            # Do win calculations; for now, play one round then get the most tokens
            self.winner = max(self.players, key=lambda p:p.hearts+p.insane_hearts)
            break
        print("Winner is: " + str(self.winner))
    
    def play_turn(self, player):
        """Play a turn for a player."""
        # Substeps return False if the round ends or the player is now dead
        # This returns False if the round has ended
        # After each step, check if the round's ended (returned False)
        # Could be fancy and do all() with lazy evaluation
        # Don't do anything if they're dead
        if not player.alive:
            return self.active
        if not self.start_turn(player):
            return self.active
        if not self.insanity_checks(player):
            return self.active
        if not self.try_to_draw(player):
            return self.active
        if not self.make_play(player):
            return self.active
        if not self.end_turn(player):
            return self.active
        return self.active

    # Dealing with starting and ending a round; note, may be halfway through something else.

    def start_round(self):
        # Clear out the round info history
        self.clear_round_info()
        # Reset players and game state before telling them the round has started (so all state is clean at the RoundStart event)
        self.active = False # In case we've leaked from somewhere
        self.turn_order = 1
        self.round_winner = None
        self.reset_players()
        self.reset_deck()
        self.inform_start()
        # Ask who should play first - will inform players
        self.ask_for_first_player()
        # Deal out a card to all Players - but the round hasn't started yet, so no responses
        # Q; are you allowed to look at your card before choosing who goes first? I don't think so
        for player in self.players:
            trigger_draw(self, player, JOINED, False)
        self.clear_event_queue()
        # Round has now properly started
        self.active = True

    def inform_start(self):
        """Inform Players of the start of a round."""
        # Show the list of Players playing in this round
        Event(RoundStartContext(self.players)).queue(self)

    def ask_for_first_player(self):
        """Ask the last loser who starts; or pick randomly if there isn't one."""
        if self.last_loser is None:
            # No-one died yet; pick randomly
            starting_player = random.choice(self.players)
            def do_set(ev):
                self.current_player = starting_player
            Event(StartingContext(starting_player, RANDOM),
                  resolve_effect=do_set).queue(self)
        else:
            ask_who_starts(self, self.last_loser)

    def check_one_left(self):
        left = None
        for player in self.players:
            if player.alive:
                if left:
                    # Already found someone
                    return True
                left = player
        trigger_round_win(self, left, LAST_ALIVE)
        return False

    def check_round_end_win(self):
        """Find who won of the surviving players."""
        # Q; how does capitalist work here? For now, just taking the maximum card in hand
        score_dict = {}
        for player in self.living_players():
            score = max([card.value for card in player.hand])
            for card in player.hand + player.discard:
                score = card.round_end_score_edit(score)
            score_dict.setdefault(score, [])
            score_dict[score].append(player)
        found_winner = None
        for score in sorted(score_dict.keys(), reverse=True):
            had_score = score_dict[score]
            if len(had_score) > 1:
                # Annhilating players
                Event(AnnhilationContext(had_score, score)).queue(self)
            elif len(had_score) == 1: # Should always be True; assert instead?
                # I don't like the for: ... break ... else: ... paradigm.
                found_winner = had_score[0]
                break
        # Don't bother running end_round here, that already happened
        if found_winner:
            Event(WinContext(found_winner, HIGHEST_CARD),
                  lambda ev: self.make_round_winner(found_winner, HIGHEST_CARD)).queue(self)
        else:
            # Must be annhilation!
            Event(TieContext(MUTUAL_ANNHILATION)).queue(self)

    def end_round(self, source, winner=None):
        """End the round, optionally setting a winner."""
        # Usually happens once deck is empty or only one player stands
        # Nb; this may happen before or after the win/tie event - it happens before in a deck-out
        
        # If not already ended; to avoid duplicate Events
        if self.active:
            end_source = source
            if source == LAST_ALIVE:
                end_source = ONE_LEFT
            elif source == HIGHEST_CARD:
                end_source = DECK_EMPTY
            def do_end(ev):
                self.active = False
                if winner:
                    self.make_round_winner(winner, end_source)
            Event(RoundEndContext(self.living_players(), end_source),
                  resolve_effect=do_end).queue(self)

    # Sub-steps in a turn.

    def start_turn(self, player):
        """Start the turn for the player."""
        # Doing this all as an Event to make it easier to add 'skip turn' cards
        def do_turn_up(ev):
            player.turns_played += 1
        Event(TurnStartContext(player),
              resolve_effect=do_turn_up).queue(self)
        return self.active and player.alive

    def insanity_checks(self, player):
        """Run insanity checks for the player."""
        # TODO: Cancel later events if player dies.
        def trigger_checks(ev):
            def try_check(ev):
                if not player.alive:
                    # go through the other events and cancel. Only if i > ev.i
                    return
                try:
                    disc_card = self.draw()
                    trigger_discard(self, player, INSANITY_CHECK, disc_card)
                except EmptyDeckException:
                    pass
            # Reversed, since they fire in reverse order
            for i in range(player.how_insane())[-1::-1]:
                self.queue_event(
                    Event(InsanityCheckContext(player, i+1),
                          resolve_effect=try_check))
        Event(InsanityChecksContext(player, player.how_insane()),
              resolve_effect=trigger_checks).queue(self)
        return self.active and player.alive

    def try_to_draw(self, player):
        """Try to draw a card; will raise EmptyDeckException if not possible."""
        try:
            trigger_draw(self, player, START_OF_TURN, False)
        except EmptyDeckException:
            self.end_round(DECK_EMPTY)
        return self.active and player.alive
            
    def make_play(self, player):
        """Ask the player to choose a card to play, then trigger it."""
        force_ops = [[] for i in range(3)]
        for card in player.hand:
            for option, force in card.play_options():
                force_ops[force].append(option)
        if force_ops[2]:
            # Must play each of these cards. Special Query for this
            mult_query = multi_play_query(force_ops[2])
            self.run_query(player, mult_query)
        elif force_ops[1]:
            # Must play one of these cards
            self.run_query(player, which_play_query(force_ops[1]))
        else:
            # Nothing's forcing
            self.run_query(player, which_play_query(force_ops[0]))
        return self.active and player.alive

    def end_turn(self, player):
        """End the player's turn."""
        Event(TurnEndContext(player)).queue(self)
        return self.active and player.alive

    # Query methods.
    
    def run_query(self, player, query):
        if query:
            return query.ask(player)

    # Info methods.

    def queue_info(self, info):
        self.info_queue.append(info)
        self.all_info_history.append(info)
        self.round_info_history.append(info)
        # Probably could just send it, but allowing for pausing/async later
        self.send_all_info()

    def send_all_info(self):
        while self.info_queue:
            info = self.info_queue.pop()
            info.send(self)

    def clear_round_info(self):
        self.round_info_history = []

    # Event methods (and game 'engine').

    def queue_events(self, events, clear=True):
        """Put multiple events in the queue, in order they appear here.

Will clear events *after* queuing; which means the first is last to trigger."""
        for event in events:
            self.queue_event(event, clear=False)
        if clear:
            self.clear_event_queue()
            
    def queue_event(self, event, just_after=None, clear=True):
        """Put an event in the queue; optionally just after another (by uid).

Unless clear is set to False, this will immediately try to clear the event queue too.
Equivalent to calling queue() on an Event object."""
        if just_after:
            try:
                i = [e.uid for e in self.event_queue].index(just_after)
            except ValueError:
                # If not in the queue, put at the front
                i = -1
            self.event_queue.insert(i+1, event)
        else:
            self.event_queue.append(event)
        self.firing_interrupted = True
        if clear:
            self.clear_event_queue()

    def pause_events(self):
        """Pause running through the event queue. clear_event_queue will no longer do anything."""
        self.events_paused = True

    def resume_events(self, clear=True):
        """Resume running the event queue. Unless clear is False, will start clearing immediately."""
        self.events_paused = False
        if clear:
            self.clear_event_queue()
        
    def clear_event_queue(self):
        """Run through the queue until it is empty."""
        if self.events_paused:
            return
        # Fire events from latest first
        # This will do a round the houses, which may cause another Event to be queued
        # If that happens, the firing event will be interrupted, and fired again later
        # When the last event is fired and not interrupted, resolve it and remove it
        while self.event_queue:
            latest = self.event_queue[-1]
            if latest.fired or latest.cancelled:
                # Remove from queue first. If an exception happens during resolution, this leaves
                # the Event unresolved, but not being retried.
                # Don't rely on this, since the Event may not fire when you queue it - the exception may happen only later.
                self.event_queue.remove(latest)
                latest.resolve(self)
            else:
                self.fire_event(latest)
        # Here is a good place to check if the round is over
        if self.active:
            self.check_one_left()

    def fire_event(self, event):
        # TODO: better ordering of priority.
        self.firing_interrupted = False
        event.fire(self)
        if not self.active:
            # Can't respond if the game's not active
            return True
        for player in self.players:
            # Cards in the player's hand or discard are what can respond
            # Player itself doesn't see things, unless Querys come in
            # The cards have the business logic on them, in on_event
            for hand_card in player.hand:
                hand_card.see_event(event)
                if self.firing_interrupted:
                    event.interrupt()
                    return False
            for disc_card in player.discard:
                disc_card.see_event(event)
                if self.firing_interrupted:
                    event.interrupt()
                    return False
        return True
