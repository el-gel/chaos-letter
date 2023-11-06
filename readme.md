# Files:

### game.py:

Runs a game and manages players. Knows the game rules, and may have to handle some edge cases, but does not know the card effects.

### events.py:

Events are actual things happening, and are the main pieces of function. See below.

This file also includes functions for making or triggering specific kinds of Events. If possible, use functions from this file.

### info.py:

Infos are sent to a Player object, which can do whatever it wants with them - the game doesn't care.

### queries.py:

Query and query-making functions.

Querys are sent to a Player object, and do a thing based on the response (usually queueing an Event).

### players.py:

Player logic. The intention is that bots can be written as subclasses of a PlayerActions class (not set up right yet; currently using subclasses of Player).

This PlayerAction class would only see Query and Info events, not the Events.

### context.py:

Context classes, used for distinguishing Events, Infos and Queries.

E.g., a Query event may have a WHICH_CARD context, in which case the Player knows they're picking what card to use.

      Or, the Query may have a USE_NO_U context, in which case the Player knows it's a Yes/No question.

Contexts can be checked by running context.is_(USE_NO_U), or query.is_(USE_NO_U). TODO: Should also be possible from Public/Private objects.

At the moment, this class handles a lot of the string formatting, but in theory, the player bots should be handling displaying data.

Needs a lot of cleaning up / organising, but there's many more contexts left to add.

### cards.py:

The base card logic. Cards are subclasses of the Card class, and define their own behaviour based on seeing Events (not Querys or Infos).

cardback: Cards may have different cardbacks, and this may be different for cards of the same type (e.g., creased Baron).

cardfront: Again, cards may have different cardfronts, which may be different for same type cards (e.g., trans vs cis Baron).

### library.py:

Individual card logic.

The on_play function is used for simple "one event happens" cards, and is the function that happens if the card is successfully played.

Note that there is a split_context call in Card.see_event, which means that e.g. a TURN_START event will trigger the see_turn_start_event method.

Also make sure that cards are accounting for edge cases. E.g., the Priest asks which card to look at, in case of Capitalist.

### access_control.py:

Implements rudimentary readonly classes and the public/private behaviour.

Each object that needs to get shown to a PlayerActions class (the one that bots use) must have a Public and Private object associated.

These are what's passed around in Querys and Infos, so that secret game info is not disclosed.

Every object maintains a different public/private object for each player. This is so that players cannot somehow mess with other players.

These objects get recreated at certain points when they should in theory have been lost track of (e.g., we don't know if the card played was the one just picked up.)

The StaticPublic/PrivateUser classes are actually permanent, and rather than being recreated as a new object get edited. This is used for the Player object, and for bot convenience; it's likely they'll want to just keep a permanent list of all players, rather than needing to ask for the new object after each Info/Query. This might be easier for bots to mess with, so will consider some form of cheat detection after each bot action.

Objects wanting to use this functionality should subclass PublicUser, and set _PUBLIC_ATTRS and _PUBLIC_CLASS (a subclass of PublicData). Same again with Private.

### utils.py:

Useful stuff. E.g., Player logic may want to ask "Is this effect like a Guard?" rather than "Is this an Investigator, Guard or Deep Ones?"

### cl_constants.py:

Quelle surprise.

Considering having a 'register' function so these constants can be defined in context creation rather than duplicated here.

### game_runner.py:

For running a sample game. Sets up a deck and some players and runs the game.


# How Events work:

Essentially, it's Magic: The Gathering's stack.
- When something is supposed to happen, the Game object creates an Event (or a Query that queues an Event based on the response).
    - For instance, an Insanity check happens, or a Player is asked which card to play (and who to target with it).
- The Event goes onto the queue.
- The Game fires the latest Event in the queue (the last one).
    - Firing is letting every card in the game know that the Event is happening, and letting it respond.
    - When a card has to respond (e.g., the Constable is not optional), it does so.
    - When a Player has a choice in the matter, the Player is sent a Query about it. The Player gets a set of options, and the Query will run a callback based on the chosen option (and return the output of that callback).
        - The response can be queuing another Event (e.g., a No-U gets queued on top of the original event). The current Event firing is interrupted (meaning it will be fired again later), and the latest Event is then fired immediately, before resolving the prior one.
        - The response can also be to set a triggered Event, which only happens if the original Event actually works (e.g., the Constable puts a triggered Event on a 'dies' Event, which only happens if they actually do die). This does not interrupt the currently firing Event.
- When the latest Event in the queue has fired, it is resolved.
    - An Event may have been cancelled by this point (e.g. Nope, No-U); in which case we don't wait to fire it again, and resolving does nothing.
    - If not cancelled, then an Event runs its resolve_effect function. This is where the actual stuff happens; e.g., a King swapping hands.
    - An Event is also asked to send off some Info events. TBD whether the Game or Event object is responsible for putting these in the Game's info_queue.
    - Once resolved, an Event is removed from the queue.
- While resolving, it's entirely possible that new Events go on the queue (e.g., after a card play event happens, there may be a 'look at' Event, or 'swwap hands' Event. These are put at the end, and wait to be fired.
- Once the event queue is empty, the Game moves on to the next step in the Player's turn.
- At the beginning and resolution of an Event, it's asked to send Info events to relevant Players (e.g., Alice is trying to play a King on Bob, or Alice swapped a card with Bob).

## Example turn:

### Dead player is skipped
Player Z's turn would start, but they're dead. So skip to the next Player in turn order.

### Turn starts
Player A's turn starts. This puts a turn started Event on the queue; this is seen by Player A's Handmaid, which adds a remove protection Event conditional on the starting of the turn. Nothing else can respond, so the protection is removed by the Handmaid's effect. (The Handmaid does this by using the Card `see_turn_start_event` trigger.)

### Insanity checks

Player A is twice insane.

An 'all insanity checks' Event goes on the queue.

This fires, but nothing can respond to it so it immediately resolves (maybe in future we'll have a card that says "discard this to avoid insanity checks this turn").

For resolution, it will queue two individual insanity check Events. Again, nothing can respond, so the first one resolves.

The top card of the deck is taken away, and the card will be asked to run its 'on_discard' effect. In this case, it's sane, so nothing happens. If nothing was in the deck, then nothing happens.

A discard card Event is put on the stack (in its Context, it says the source of the discard is an Insanity check). The resolution effect of this is to run the card's on_discard method.

This Event is shown to all cards, but nobody can respond so it resolves (maybe in future, we'll have a card that says "when someone discards something to an insanity check, you can take it").

The second insanity check Event resolves.

The top card of the deck is taken away, and the card asked to run its on_discard effect (via a discard card Event resolving). This time, it's insane and notices the Context says Insanity check (or, it's a princess); so it queues a player dies event (w/ Context of Insanity Check).

After this happens, the queue only has the 'player dies' Event on it.

This is shown round all cards, and the Bounty Hunter in someone's discard pile notices. If Player A had been bountied, and not killed to insanity, this would have set a won heart Event conditional on the death going through. Since that's not true, it does nothing.

Player A is immortal, and the immortal card sees the player dies Event and cancels it, by queuing a "cancel death" Event which is tied to the player dies Event.

The queue now has a 'player dies' and 'cancel death' event. The cancel death one fires, and then resolves since nothing responds. It cancels the 'player dies' Event.

The 'player dies' Event now resolves, but does nothing.

### Draw a card

The Event queue is now empty, so we move on to drawing a card. Everyone sees a 'Player A about to draw' Event, and noone can respond.

Then Player A draws a card, which gets put into their hand. Nb; when the draw Event sends Info round, the Info it sends to Player A includes the actual card details, whereas it only shows the cardback to the others.

This draw a card Event has 'regular draw' as the context, and part of the resolution is to end the game if the deck is empty. We do this now rather than at the end of the turn, because of insanity checks and in case we add something like "at the start of their turn, skip it", which would allow a draw from the aside cards. Question: is that something we want?

### Play a card

The Event queue is now empty, so we add a 'play card' Event to it. This is not responded to by anything (this is done rather than having the Game just prompt for play, because the MiGO and Mead use this Event as part of their resolution). TODO: This is currently not how the code works, not sure if this is right or the code is. Will work out when making those two cards.

As a result of this Event resolving, Player A gets sent a Query for which card to play/special event to use (i.e. shuffling an 8 in) and which targets to choose.

To form this Query, the Game asks each of the cards in their hand about what play options they have (We don't yet have a 'play from discard or another player's hand', so only checking those cards).

Each card will return a list of options, along with a callback for what to do when an option is chosen.

The Query will have a Context of "Which card / targets to play?"

Player A responds to the Query with the PlayOption {card=Nyarlathotep, insane=True, targets=everyone else unprotected, parameters=None}.

The Query callbacks will put two Events on the queue:

- A card play Event, with the after_eventbeing the Card's on_play event (passed the aboe PlayOption).

- A card discard Event, with a Context of 'playing this card'.

The discard Event fires first. Nothing can respond, so it resolves; though if the card was like a Princess, its on_discard effect would kill the player. Question; can you Nope an on_discard effect?

Then the play Event fires. This is shown to each player (priority should be to targeted players, then non-targeted players, in turn order from the user. Not currently implemented, it just goes round in join order).

In order, the cards in each Player's hand and discard are given the option to respond.

Player B has a Nope, which sends its Player a Query for "would you like to use it on this?". The Context of this Query is a Nope question context, with the PlayOption as part of it.

They respond with No, so the Query returns doing nothing (if they had responded Yes, then the Query would have created a Nope played card event [like the one above, PlayOption {card=Nope, insane=False, targets=Player A, parameters=Nyarlathotep played Event}]). This Event would have interrupted the firing, so everyone will get a chance to respond again later. Question; if someone Nope's, and then another person no-U's what was Noped, what happens? What if we had a second Nope, and the second was used on the first? Can you no-U a Nope?

Player C has a no-U, and they get asked a similar question. They respond with Yes, and so we have them play it.

This puts a discard Event, a draw Event, and a Card play Event on the queue, which has a 'play no-U' Event as a post resolution effect (like with the Nyarlathotep above). The order is:
- card play
- draw
- discard (firing first)

No-one can respond to the discard and draw Events, and the 'play no-U' Event is fired.

Player B now chooses to respond with their Nope, and again we have a card play, draw, discard Event on the queue.

No-one responds to the Nope Event, and the no-U is cancelled.

The no-U play Event goes to get fired again, but because it is cancelled it's actually skipped - it's told to resolve now.

Then, the Nyarlathotep play Event gets fired again. Player B drew a no-U off the Nope draw, and plays it now.

Again, we have card play / draw / discard Events, which all resolve this time.

The no-U Event resolution cancels the Nyarlathotep play Event, and now puts a new Event on the queue (if there had been choices for the no-U'd effect, it would have sent a Query).

This is a card play Event, but part of the Context (which part?) says that it comes from a no-U.

Everyone gets to respond, but can't.

It resolves, and now does the Nyarlathotep thing:
- It queues an Event to show every other player's card to Player B (the context here says its source is Nyarlathotep, so a Crime Boss sees the Event but doesn't trigger. Capitalist will be sent a Query as part of this).
- This Event will fire an Info package to Player B with all that data.
- It will then send a Query to Player B on how to rearrange them (either within the same Event, or as a new Event that implements .following(); otherwise we lose track of which card the Capitalist gave away).
- This is a special Nyarlathotep Query, due to how big the possibility space is.
- Player B responds, and then every other Player will get a card replaced Event (same as a King swap Event, but with Nyarlathotep as the source - the context has the old card, the new card, and where it came from).

The resolution is now finished.

### End turn

Player A's turn is now over, so we send a turn end Event. This is relevant for the Bounty Hunter.

Then we move to the next player.

# Public, Private, Hidden

All attributes/methods are of three sorts:
- Public: Any Player can ask about this and look at it. E.g., cards in another Player's discard pile, list of all cards that were in the starting deck.
- Private: Only the Player who owns the information can look at it. E.g., cards in hand.
- Hidden: No Player can look at this. E.g., cards in the deck.
None of this information can be modified by the part bots will use; PlayerActions can only interact via responses to Querys, and only see Query and Infos.

### Old thinking
The way I am handling this is that when being sent to a Player, Querys and Infos will create new packets of their information, rather than passing themselves properly.

These packets will be new class objects, derived from the original and only including relevant information.

Players are free to modify these objects as much as they want, it won't change the original.

Need to be careful to not get into loops generating the new objects (e.g. Card links to PlayOption links to Player links to Card).

Options to avoid that problem:
- Constantly updated public/private attributes. Won't work as then Players could modify them for others.
- Each Player gets a public/private version that's constantly updated. Won't work, since if you see a card's private info, you'll be able to track it more than you should be able to.
- The public/private recursion points out what's already been given. Bit awkward, especially with the Context class, and probably won't link things right.
- Make sure that the link graph is acyclic. Requires reworking the class structure.

But how are we handling the fact that some Players will honestly keep a link around? E.g., keeping a single public Player view and constantly looking at that, instead of updating it on every Info event. The fairest method is to have constantly updated public/private info for that player to see, but then need to work out how to hide info that should be hidden.

Maybe I have a public view that's constantly updated, a private view that's also updated, but not including things like what's seen.

### New thinking

Every object has a permanent 'public info' part of it. When Querys and Infos go to Players, this is the part that gets sent.

The public info for Players and the Game are static; these can be stored and checked later.

The public info for Cards is not static. If the card moves from or to a hidden zone, or is in a hidden zone when another card moves to or from, then the public info is regenerated (copied).

The old info is marked as 'invalid', in case another object is still holding a reference (say, a Player's code). Can't enforce them not looking, but can warn about this.

The getter for anything that points to a Card object will go through the main Card object, and that will handle making a new one if it's not invalid.

TODO: Make setters for the main Card object's values, to make it work.

Public objects are considered the same if they are essentially the same, not whether they share the same base Card (there's no way to make that possible without leaking something.)

Public objects have a 'face-up' mode and 'face-down' mode. This will depend on whether the base Card object is in a discard pile or not (another reason discard happens before playing!), and changes what is shown.

Private Player objects are also static, but never shared around. They contain references to mostly-static Private Card objects - the Player knows which is which, and can do equality comparisons with 'is' rather than '==' (__eq__ can't distinguish two Handmaids).

These are also what get passed in to Query's that go to that Player.

These private Card objects are regenerated when changing zones (the same way that Public ones are, except they won't actually change when another card in the zone moves).

However, when they are shown anywhere else (e.g., a show Card effect), they are regenerated as well - so there's no way to track them after the Info event.

Game objects that bots will see, and links between (ignoring links that are hidden):

- Card
    - Links to Player (my_holder) and PlayOption (played_as)
- PlayOption
    - Links to Card (card) and Players (targets). Potentially parameters could be anything, but not sure on that yet.
- Player
    - Links to Card (hand, discard), Players (primed_to / primed_from).   (game is not going to be included).
- Query
    - Context (context), anything (options). Will need to make sure that options are class checked - make a utils 'make public/private' method.
- Info
    - Context (context). May change as I fiddle with this class more.
- Context
    - Anything. Will try to make a generic form of the converter for this.
- Game
    - Players, but this will be passed in to the player bots at the start, rather than through Info.

# TODOs

- Finish the game logic.
- Write the card logic.
- Discuss the weird questions and edge cases with the group.
- Write a usable, interactable Player.
- Write the pre_ and post_info on all the Contexts.
- Refactor everything so the dependencies are acyclic.
- Write help text and instructions for others making PlayerActions.
- Write a game manual / set of rules that matches what actually happens here.
- Take pictures of the real card backs and card fronts, to potentially use in graphical form.
- Sort out circular file import dependencies. utils.py seems main problem.
- A 'dump into interpreter' player action object. Good for debugging.
- Consider a cheating detector that checks whether the data has changed in a Public/Private data class after a player action.
- Make repl_str better.
- json transformation of public/private objects / game state, as a way to pass data to other programs.
- Maybe linting and typing. If I can be bothered facing that. Nb, this will not be consistently enforced after adding, so I'd rather do this later in one big go, when it's time for others to be implementing bots etc. and there's not going to be much development going on.