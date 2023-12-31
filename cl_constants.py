
class EmptyDeckException(Exception):
    pass

# Types of Query
WHICH_PLAY = "WHICH_PLAY"
MULTI_PLAY = "MULTI_PLAY"
WHO_STARTS = "WHO_STARTS"
WHICH_CARD = "WHICH_CARD"
WHICH_QUICK_PLAY = "WHICH_QUICK_PLAY"
USE_NOPE = "USE_NOPE"
USE_NO_U = "USE_NO_U"
ORDER_EVENTS = "ORDER_EVENTS"
ORDER_EVENT_GROUPS = "ORDER_EVENT_GROUPS"
NYARLATHOTEP_RETURN = "NYARLATHOTEP_RETURN"

# Types of Event
EVENT_TYPES = ("ROUND_START", "ROUND_END", "STARTING", "JOIN",
               "LEAVE", "WIN", "TIE", "SCORED", "ANNHILATION",
               "TURN_START", "TURN_END", "CARD_PLAY", "DEATH",
               "DISCARD", "DRAW", "INSANITY_CHECKS", "INSANITY_CHECK",
               "PROTECTION_LOSS", "CANCEL_DEATH", "SEE_CARD")
for type_ in EVENT_TYPES:
    globals()[type_] = type_

# Non-player, non-card sources / reasons
PLAYED = "PLAYED"
RANDOM = "RANDOM"
JOINED = "JOINED"
QUICK_PLAY = "QUICK_PLAY"
START_OF_TURN = "START_OF_TURN"
OUT_OF_TURN = "OUT_OF_TURN"
BY_CHOICE = "BY_CHOICE"
PRIME = "PRIME"
NEW = "NEW"
DECK_EMPTY = "DECK_EMPTY"
LAST_ALIVE = "LAST_ALIVE"
HIGHEST_CARD = "HIGHEST_CARD"
ONE_LEFT = "ONE_LEFT"
MUTUAL_ANNHILATION = "MUTUAL_ANNHILATION"
WON_HEARTS = "WON_HEARTS"
WON_INSANE_HEARTS = "WON_INSANE_HEARTS"

# Card names
CARD_TYPES = ("ASSASSIN", "JESTSASSIN", "GUARD", "PRIEST", "CARDINAL",
              "SPY", "BARONESS", "BARON", "HANDMAID", "BOUNTY_HUNTER",
              "PRINCE", "CAPITALIST", "COUNT", "NO_U", "INSANE_NO_U",
              "CONSTABLE", "KING", "COUNTESS", "DOWAGER_QUEEN", "PRINCESS",
              "BISHOP", "BRAIN_CASE", "INVESTIGATOR", "DEEP_ONES", "CATS",
              "NOPE", "GOLDEN_MEAD", "YITH", "HOUNDS", "ELDER_SIGN",
              "LIBER_IVONIS", "ARMITAGE", "MIGO", "RANDOLPH", "NYARLATHOTEP",
              "SILVER_KEY", "TRAPEZOID", "NECRONOMICON", "CTHULHU")
for type_ in CARD_TYPES:
    globals()[type_] = type_

# Card modes
ACTIVE_NOPE = "ACTIVE_NOPE"
SHUFFLE = "SHUFFLE"
INSANE = "INSANE"
QUICK = "QUICK"
INSANE_QUICK = "INSANE_QUICK"

FORCED = "FORCED"
UNFORCED = "UNFORCED"
ALL_FORCED = "ALL_FORCED"

# Card backs and fronts
LOVECRAFT = "LOVECRAFT"
BLANK = "BLANK"

# Game settings
GAME_SETTINGS = ("HEARTS_TO_WIN", "INSANE_HEARTS_TO_WIN", "DECK_STACKING")
for setting in GAME_SETTINGS:
    globals()[setting] = setting

# Random other constants
DEFAULT = "DEFAULT"
NOT_SET = "NOT_SET"
NO = "NO"
YES = "YES"
ALL = "ALL"
INSANE_HEART = "INSANE_HEART"
HEART = "HEART"
GUARD_CHOICES = (0,2,3,4,5,6,7,8,9,10)
PLAYER = "PLAYER"
FIZZLE = "FIZZLE"
