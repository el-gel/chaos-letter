from collections import defaultdict
import random
import logging
log = logging.getLogger(__name__)

from events import *
from players import *
from queries import *
from info import *
from context import *
from utils import *
from query_utils import *
from event_utils import *
from cards import *
from cl_constants import *

DEFAULT_CONFIG = {
    HEARTS_TO_WIN: 2,
    INSANE_HEARTS_TO_WIN: 3,
    DECK_STACKING: (),
    }


class PublicGameInfo:
    """Try to only allow Player objects access to relevant information"""
    def __init__(self):
        pass


class Game:
    """Handles running a game, firing Events around etc."""
    def __init__(self, config=None):
        self._settings = {}
        self.update_config(config)
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
        self.round_count = 0

    # Setup and configuration.
        
    def setup(self, deck, players, pull_aside=None, config=None):
        """Setup the Game configuration before starting to run anything."""
        if len(players) > 2*len(deck):
            # 2x to handle priming, may need to have better checking
            raise ValueError("Too many players")
        # Do configuration stuff
        self.update_config(config)
        # Set up an 'original' deck, which is then used by reset_deck
        self.all_cards = list(deck)
        for card in self.all_cards:
            card.put_in_game(self)
        # TODO: make a pull_aside that pulls cards out of the deck until one of each cardback
        if pull_aside:
            self.pull_aside = pull_aside
        # Only add players when everything is ready; they may try to check things early
        for player in players:
            self.add_player(player)

    def update_config(self, config):
        """Update the config dict with config, also setting any defaults."""
        config = config if config else {}
        self._settings.update(config)
        for key, value in DEFAULT_CONFIG.items():
            if key not in self._settings:
                self._settings[key] = value

    def setting(self, name, default=None):
        return self._settings[name] if name in self._settings else default

    # Player handling.
            
    def add_player(self, player, order_i=None, draw=False):
        """Add a player to the game, optionally draw them a card, and fire all past info history into them."""
        # This does this via an Event to make sure the Info is sent
        if order_i is None:
            order_i = len(self.players)
        def do_add(ev):
            self.players.append(player)
            self.player_order.insert(order_i, player)
        self.show_history_to_player(player)
        # When priming, this is called on the primed Player
        Event(JoinContext(player, PRIME if player.prime_count else NEW),
              resolve_effect=do_add).queue(self)
        if draw:
            trigger_draw(self, player, JOINED)
    
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
        """Add a prime player to the game, using prime() from players.py."""
        # Add them just after the player they primed from
        prime_player = prime(player)
        self.add_player(prime_player, self.players.index(player), draw=True)

    def de_prime_players(self):
        """Remove all primed players from the game. Run before start of round."""
        # Each Player keeps a reference for reuse later, so don't need to save anything
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
            raise Exception("Can't leave the game while a round is running.")
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
        player.reset()

    def show_history_to_player(self, player, all_=False):
        """Show the round's Info history to a Player, or the entire game history if all_."""
        for info in (self.all_info_history if all_ else self.round_info_history):
            info.send_to(player)

    # Info about players, including iterables.

    def player_by_uid(self, uid):
        """Get the Player object for a specific UID."""
        for player in self.players:
            if uid == player.uid:
                return player
        return None

    def living_players(self):
        """Get a list of living Players. No order guarantee."""
        return [player for player in self.players if player.alive]

    def targetable_players(self, not_including=None):
        """List of living and unprotected Players. Optionally provide a Player or Players to ignore."""
        ni = not_including if isinstance(not_including, (list, tuple)) else (not_including,)
        return [player for player in self.living_players() if not player.protected and player not in ni]

    def play_order(self, players=None, start_after=None, start_with=None):
        """List of players in play order. If players is not given, defaults to living players.

start_after and start_with: only one can be used. Default is after current player."""
        if players is None:
            players = self.living_players()
        if start_after:
            if start_with:
                raise ValueError("Can't set start_after and start_with at the same time.")
            i = self.player_order.index(start_after) + self.turn_order
        elif start_with:
            i = self.player_order.index(start_with)
        else:
            if self.current_player:
                i = self.player_order.index(self.current_player) + self.turn_order
            else:
                # Don't have a current player yet (pre-game?) so just say it's 0
                log.info("No starting player yet; guessing at the play order.")
                i = 0
        ret = []
        for j in range(len(self.player_order)):
            next_player = self.player_order[(i+(j*self.turn_order))%len(self.player_order)]
            if next_player in players:
                ret.append(next_player)
        return ret

    def turns_til(self, player):
        """How many turns til this player would get to play? Return -1 if they won't (e.g. dead)."""
        if not self.current_player:
            # No idea who would go first
            return -1
        i = 0
        cur = self.player_order.index(self.current_player)
        while i <= len(self.player_order):
            if self.player_order[(cur+(i*self.turn_order))%len(self.player_order)] == player:
                return i
            i += 1
        return -1

    def priority_order(self, event, players=None):
        """Get the priority order of living players (or a passed in list) responding to an event.

This order is:
1) Players targeted, in turn order (if event is a play event/targeting thing).
2) All other players starting after targeter (if relevant - otherwise after current player)."""
        if players is None:
            players = self.living_players()
        if len(players) <= 1:
            return players
        ret = []
        if event.is_(CARD_PLAY):
            # Find targets (ignoring current player), then put them in play order
            targs = event.context.play_option.targets
            ret.extend([player for player in targs if player != self.current_player
                        and player in players])
            ret.sort(key=self.turns_til)
        # TODO: other event types may have different priority orderings
        # Now add all players in play order
        for player in self.play_order():
            if player in ret or player not in players:
                continue
            ret.append(player)
        return ret

    # Deck handling.

    def shuffle(self):
        """Shuffle the deck in place."""
        random.shuffle(self.deck)

    def shuffle_in(self, card):
        """Shuffle a card into the deck."""
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
        """Return the deck and all cards within it to a default state."""
        for card in self.all_cards:
            # I haven't cleared state from cards yet, like I want to
            # So have to actually touch the cards here
            card.reset()
        self.deck = list(self.all_cards)
        self.shuffle()
        self.aside = self.pull_aside(self.deck)

    def stack_deck(self, order):
        """Stack the top of the deck to match order as a list of type_'s. Used for tests."""
        log.info("Stacking the deck with " + liststr(order))
        top = []
        for type_ in order:
            for test in self.deck:
                if test in top:
                    continue
                if test.is_(type_):
                    top.append(test)
                    break
            else:
                log.warning("Deck stacking could not find enough " + type_ + "s.")
        for found in top:
            self.deck.remove(found)
        # Top of deck is last element, so reverse
        self.deck = self.deck + top[-1::-1]

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
        """Set a round winner and reward with a scoring token."""
        # Give heart or insane token depending on status
        if player.how_insane():
            self.give_insane_win(player, source)
        else:
            self.give_heart(player, source)
        self.round_winner = player

    def win_game(self, player, source):
        # End the round as well
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

        # Return False if we want premature ending
        # Currently redundant with run_game logic, but could be used for e.g. end of lunch
        return True
    
    def run_game(self):
        """Keep running games until we have a winner."""
        # TODO: Consider multiple winners. E.g. bishop, jester etc. Cthulu should override them all too.
        while self.run_round():
            # Do win calculations; for now, play one round then get the most tokens
            if self.winner:
                # Someone won due to Cthulu
                break
            # TODO: currently takes first player that's won
            # Consider multiple winners; go to a tie break, with another game if all tied?
            for player in self.players:
                if player.hearts >= self.setting(HEARTS_TO_WIN):
                    self.win_game(player, WON_HEARTS)
                    break
                if player.insane_hearts >= self.setting(INSANE_HEARTS_TO_WIN):
                    self.win_game(player, WON_INSANE_HEARTS)
                    break
            if self.winner:
                break
        log.info("Winner is: " + str(self.winner))
    
    def play_turn(self, player):
        """Play a turn for a player. Returns False if the round is over."""
        # Substeps return False if the round ends or the player is now dead
        # This returns False if the round has ended
        # After each step, check if the round's ended (returned False)
        # Could be fancy and do all() with lazy evaluation
        # Don't do anything if they're dead
        if not player.alive or not self.active:
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
        """Set up ready for a round to run, then mark the Game as running."""
        # Clear out the round info history
        self.clear_round_info()
        # Reset players and game state before telling them the round has started (so all state is clean at the RoundStart event)
        self.active = False # In case we've leaked from somewhere
        self.turn_order = 1
        self.round_winner = None
        self.reset_players()
        self.reset_deck()
        if len(self.setting(DECK_STACKING)) > self.round_count:
            self.stack_deck(self.setting(DECK_STACKING)[self.round_count])
        self.round_count += 1
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
        """Check if only one Player is alive. Return True otherwise (so the round continues)."""
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
                # TODO: Cancel everything on the event queue too
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
        force_ops = {UNFORCED:[], FORCED:[], ALL_FORCED:[]}
        for card in player.hand:
            for option, force in card.play_options():
                force_ops[force].append(option)
        log.debug("force_ops: " + str(force_ops))
        if force_ops[ALL_FORCED]:
            # Must play each of these cards. Special Query for this
            mult_query = multi_play_query(force_ops[ALL_FORCED])
            self.run_query(player, mult_query)
        elif force_ops[FORCED]:
            # Must play one of these cards
            self.run_query(player, which_play_query(force_ops[FORCED]))
        else:
            # Nothing's forcing
            self.run_query(player, which_play_query(force_ops[UNFORCED]))
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

    def order_events(self, main_event, ordering_events):
        """Order multiple events that are supposed to happen at once, related to a main event.

Ordering process:
1) Find the related player for each event to order (that will be context.player, if around)
2) If there are multiple for a specific player, then ask them which order they should run in
3) Then put these all in priority order (determined by main event). Events without a related player go first

Since addition of grouped events, the fundamental unit is a group, not an Event.
Players don't decide order within groups, just order of groups.
Order within a group is decided by original ordering_events order."""
        # TODO: Pretty inefficient. Nb, must always optimise for minimum queries to players.
        log.debug("Due to:   " + str(main_event))
        log.debug("Ordering: " + liststr(ordering_events))
        event_groups_by_uid = defaultdict(list)
        event_groups_seen = []
        players = []
        for event in ordering_events:
            if event.grouping in event_groups_seen:
                continue
            player = getattr(event.context, "player", None)
            event_groups_by_uid[player.uid].append(event.grouping)
            event_groups_seen.append(event.grouping)
            if player and player not in players:
                players.append(player)
        player_order = self.priority_order(main_event, players)
        event_order = []
        # Now have the ordering of Players, so ask each Player what order their events should happen in
        for player in player_order:
            group_order = event_group_ordering_query(player, event_groups_by_uid[player.uid])
            # That was the order of the groups; for each group, add all its events (in original order)
            for group in group_order:
                for event in ordering_events:
                    if event in group:
                        event_order.append(event)
        # Events without a player just get added on; assumption is they don't matter
        # TODO: consider making current player decide
        event_order.extend([event for event in ordering_events if event not in event_order])
        return event_order

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
        """Pause running through the event queue. clear_event_queue will no longer do anything.

Returns whether the queue was already paused; should only do the next resume if it wasn't."""
        was_paused = self.events_paused
        self.events_paused = True
        return was_paused

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
        # When the last event is fired and not interrupted, remove it then resolve it
        while self.event_queue:
            latest = self.event_queue[-1]
            if latest.fired or latest.cancelled:
                # Remove from queue first. If an exception happens during resolution, this leaves
                # the Event unresolved, but not being retried - we drop the exception out at the point of firing
                # and the event queue can in theory continue
                # Don't rely on this for control flow, since the Event may not fire when queued
                self.event_queue.remove(latest)
                latest.resolve(self)
            else:
                self.fire_event(latest)
        # Here is a good place to check if the round is over
        if self.active:
            self.check_one_left()

    def fire_event(self, event):
        """Fire a specific Event, showing it to all cards in play.

Returns True if the Event got through uninterrupted."""
        self.firing_interrupted = False
        event.fire(self)
        if not self.active:
            # Can't respond if the game's not active
            return True
        for player in self.priority_order(event):
            # Cards in the player's hand or discard are what can respond
            # Player itself doesn't see things, unless Querys come in
            # The cards have the business logic on them, in see_event
            # If a card can be optionally used as a quick play, it returns
            # the PlayOptions from see_event
            # Then the player is asked which one they want to use, if any
            all_responses = []
            for card in player.discard + player.hand:
                quick_responses = card.see_event(event)
                if quick_responses:
                    all_responses.extend(quick_responses)
            pick = ask_quick_play_query(player, event.context, all_responses)
            if pick != NO:
                # This is a PlayOption which should be set as quick play appropriately
                pick.trigger()
            if self.firing_interrupted:
                event.interrupt()
                return False
        return True
