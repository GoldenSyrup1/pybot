"""A fact that belongs to one particular place, said honestly.

Whether a pub has a car park, whether a hotel takes dogs, whether a leisure centre has a pool: the
bot cannot know any of it. The line it used to give was the generic search hedge ("A quick search
online will get you a solid answer"), which is the worst reply for this shape, because the answer
exists and is one tap away on the place's own page. The bot already answers opening hours that way
("I can't check today's opening hours, sorry. The venue's own page or its map listing shows them"),
and a place's own facilities are the same kind of fact: it belongs to that place, it changes, and
nobody but them can confirm it.

`bot/compose/fallback.py` asks this first thing in `_live`, so it only ever replaces a hedge or a
shrug. The ask has to be put to a place, and it has to name a thing that belongs to one.
"""
import re

# A fact about one particular place - whether it has a car park, takes dogs, does takeaway,
# has a pool - is not the sort of thing the bot can hold: it belongs to that place and it
# changes. What the bot said instead was the generic search hedge ("A quick search online will
# get you a solid answer"), which is the worst line for it, because the answer exists and is one
# tap away on the place's own page. So it gets the same treatment as the live notes above: the
# honest limit, and where the answer actually is.
#
# The ask is a yes/no put to a place, and it has to name what is being asked about. A "do they
# have" with no thing in it is a different question ("do they have a dog" about a friend's
# house), and it keeps whatever answer it had.
PLACE_ASKS = re.compile(
    r"(?:\b(?:do|does|did)\s+(?:they|it)\s+(?:have|got|do|offer|allow|take|sell|serve|provide|"
    r"accept|permit|charge)\b"
    # "does the leisure centre have a pool", "do the rooms take dogs": the place is named in
    # the subject, so the verb is two or three words further along. The subject has to open on
    # a determiner, which is what keeps "does he have a car park pass" out of it, and the thing
    # asked about still has to be one of the place words below.
    r"|\b(?:do|does|did)\s+(?:the|this|that|these|those|a|an|my|our|your)\s+"
    r"(?:[a-z'-]+\s+){0,2}(?:have|got|do|offer|allow|take|sell|serve|provide|accept|permit|"
    r"charge)\b"
    r"|\b(?:is|are)\s+there\s+(?:a|any)\b"
    r"|\bcan\s+i\s+(?:bring|take|park|book|pay|use|get)\b"
    # "are the kids allowed in the beer garden": the ask is a permission put to a place, but
    # "are the kids allowed out" is a question about the children and names no place, so the
    # thing below still has to be one of the place words.
    r"|\b(?:are|is|were|was)\s+(?:the\s+|our\s+|your\s+)?"
    r"(?:dogs?|kids?|children|child|pets?)\s+(?:allowed|welcome|permitted)\b)", re.I)
# The lines that are a question about a place however they are put: nobody asks whether a dog
# is welcome at their own house.
PLACE_ASKS_OF_ITS_OWN = re.compile(
    # "are dogs allowed", "kids welcome", "dog friendly". The line has to open on it: "were the
    # kids ok" is a question about how the children are, and it keeps its own answer.
    r"(?:^(?:oh |and |so |are |is )?(?:dogs?|kids?|children|child)\s+"
    r"(?:allowed|welcome|ok|okay)\b"
    r"|\bdog[\s-]?friendly\b"
    r"|\b(?:is|are)\s+(?:it|they)\s+(?:good|ok|okay|suitable|fine)\s+for\b)", re.I)
# The things people ask a place about. The first list is a place's own business wherever it
# appears ("do they have a car park" needs no venue named); the second needs a place named in
# the line, because the same words belong to people and homes too ("does she have a dog",
# "is there wifi at my flat").
PLACE_OF_ITS_OWN = (
    "car park", "car parking", "parking", "toilets", "baby change", "takeaway", "take away",
    "beer garden", "play area", "soft play", "high chairs", "highchair", "dress code",
    "step free", "wheelchair access", "wheelchair", "accessible entrance", "table service",
    "cash only", "card only", "booking fee", "cover charge",
)
PLACE_WITH_A_VENUE = (
    "pool", "swimming pool", "dogs", "dog", "kids", "children", "child", "wifi", "wi-fi",
    "vegan", "gluten free", "vegetarian", "bookings", "booking", "tables", "music", "quiz",
    "screens", "garden", "food", "menu", "delivery", "parking", "rooms",
)
# "does it allow dogs", "do they have a pool": the place was named in the last turn, so the
# thing arrives with nothing but a pronoun in front of it. Those words are a place's own
# business when the subject is "it" or "they"; "dog", "kid", "child" and "children" are left out
# on purpose, because "do they have a dog" and "do they have kids" are questions about a house
# or a family far more often than about a venue. They still count when a place is named, through
# PLACE_VENUES and PLACE_WITH_A_VENUE ("do the pub allow kids", "can i take the kids to the pub").
PLACE_ASKS_WITH_NO_SUBJECT = (
    "pool", "swimming pool", "wifi", "wi-fi", "vegan",
    "gluten free", "vegetarian", "bookings", "tables", "menu", "food", "delivery",
    "parking", "rooms",
)
# A dog is on both sides of the fence: "do they have dogs" is a household, and "do they allow
# dogs" is a venue or a landlord. The verb tells them apart, so the animal words count with a
# pronoun only when the ask is a permission put to whoever owns the place.
PLACE_ANIMALS = ("dogs", "dog")
PLACE_PERMISSION = re.compile(
    r"\b(?:allow|allows|allowed|take|takes|taking|taken|permit|permits|permitted|welcome|"
    r"welcomes|welcomed|accept|accepts|accepted|let|lets)\b", re.I)
# "do they let dogs in", "do they welcome pets": a verb the asks above do not read, with a dog
# in it, is the same ask - and only with the animal, because "do they let you bring your own
# food" is a different question and keeps its answer.
PLACE_LETS_ANIMALS = re.compile(
    r"\b(?:do|does|did)\s+(?:they|it)\s+(?:let|lets|welcome|welcomes)\b", re.I)
BARE_PLACE_SUBJECT = re.compile(r"\b(?:do|does|did)\s+(?:they|it)\b|\b(?:is|are)\s+(?:it|they)\b")
PLACE_VENUES = (
    "pub", "restaurant", "cafe", "café", "coffee shop", "bar", "hotel", "b&b", "guest house",
    "campsite", "caravan site", "holiday park", "gym", "leisure centre", "swimming pool",
    "museum", "gallery", "cinema", "theatre", "venue", "shop", "store", "supermarket",
    "garden centre", "station", "salon", "barber", "hairdresser", "garage", "surgery",
    "dentist", "pharmacy", "church", "village hall", "zoo", "farm park", "library", "club",
    "spa", "soft play", "bowling", "snooker hall", "arcade",
)
PLACE_LINES = (
    "I can't check inside a particular place from here, sorry - whether they have that, or let "
    "you do it, is the place's own business. Their own page or their listing on a map app says, "
    "and one phone call settles it.",
    "That one is up to the place itself, and I can't see inside it from here. Their site or "
    "their map listing usually says, and ringing them is the surest answer.",
    "No way for me to know that about one place, sorry. Their own page or listing on a map app "
    "has the answer, and they can confirm it on the phone.",
)


def _bounded(phrase):
    return re.compile(r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])")


def _has(clean, phrases):
    """True when one of these phrases is in the line as whole words."""
    for phrase in phrases:
        if _bounded(phrase).search(clean):
            return True
    return False


def the_line(clean):
    """The honest line for a fact that belongs to one place, or None."""
    of_its_own = bool(PLACE_ASKS_OF_ITS_OWN.search(clean))
    lets_animals = bool(PLACE_LETS_ANIMALS.search(clean) and _has(clean, PLACE_ANIMALS))
    if not (of_its_own or lets_animals or PLACE_ASKS.search(clean)):
        return None
    if not (of_its_own
            or lets_animals
            or _has(clean, PLACE_OF_ITS_OWN)
            or (_has(clean, PLACE_VENUES) and _has(clean, PLACE_WITH_A_VENUE))
            or (BARE_PLACE_SUBJECT.search(clean)
                and _has(clean, PLACE_ASKS_WITH_NO_SUBJECT))
            # "do they allow dogs", "does it take pets": a permission, not a household.
            or (BARE_PLACE_SUBJECT.search(clean)
                and _has(clean, PLACE_ANIMALS) and PLACE_PERMISSION.search(clean))):
        return None
    return PLACE_LINES
