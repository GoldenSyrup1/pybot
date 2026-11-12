"""An invitation to the bot is a person asking for company, and nothing in the composer heard it.

"do you fancy a walk" is not a question about anything in the world: it is one person asking
another along. Every reading in `bot/compose/fallback.py` hears it as a question anyway, so it
reached the search hedge ("that's beyond what I know well, sorry") or, said the other way, the
intake form ("Got it. Is there anything you'd like a hand with?"). Neither is what a person hears
when they invite someone out, and neither is what a friend says back.

A friend who cannot come does not do either. They say no to the coming - plainly, without
apologising for existing and without pretending they could - and they say yes to the thing: where
would you go, what is on, who is going. So the refusal comes first and the next question is about
the thing invited to, which is what `TOGETHER_AT` picks the pool by.

Only a line spoken to the bot is an invitation. "i want to go for a pint" is their own plan and
"we went for a walk" is their news, so the shape has to be addressed ("do you fancy", "shall we")
or start at the verb with nothing in front of it ("fancy a brew", "want to grab a coffee").

`bot/modules/invitation.py` is the turn: it asks this reading and proposes the line, at a
PRIORITY below the knowledge base, so a thing the answers do know keeps its answer ("shall we get
a takeaway" still gets the fish and chips, "you up for a curry on friday" the quick curry).
"""
import re

from . import pick as compose_pick

# An invitation to the bot itself. "do you fancy a walk" is not a question about anything in the
# world - it is a person asking for company - and every reading below hears it as one: it reached
# the search hedge ("that's beyond what I know well") or the intake form ("Got it. Is there
# anything you'd like a hand with?"). A friend who cannot come does not do either. They say no to
# the coming, plainly and without apologising for existing, and they say yes to the thing: where
# would you go, what is on, who is going. The invitation is the whole line, so the answer is the
# next question about it.
#
# Only a line spoken to the bot counts. "i want to go for a pint" is their own plan and "we went
# for a walk" is their news, so the shape has to be addressed (do you / would you / fancy / shall
# we) or start at the verb with nothing in front of it ("fancy a brew", "want to grab a coffee").
INVITED = re.compile(
    r"\b(?:do|would|will|can)\s+you\s+(?:want|fancy|feel\s+like|be\s+up\s+for|come|join)\b"
    r"|\b(?:do|would|will)\s+you\s+(?:like\s+to\s+)?(?:come|join)\b"
    r"|\bfancy\b|\bup\s+for\b|\bwanna\b|\bshall\s+we\b|\bwe\s+could\b"
    r"|\bwant\s+to\s+(?:go|get|grab|have|see|watch|come|join)\b"
    r"|\bcare\s+to\s+(?:come|join)\b")
# The verb has to be the first thing in the line for these two: "want to go for a pint" is an
# invitation, "i want to go for a pint" is a want of theirs, and "we want to go" is a plan.
INVITED_AT_THE_START = re.compile(r"^(?:fancy|wanna|up\s+for|shall\s+we|we\s+could|want\s+to)\b")
NOT_THEIRS = re.compile(r"^(?:i|we|he|she|they|my|our|her|his|their)\b")
# A question about what the bot can tell them is not an invitation: "do you want to know how to
# fix a bike" is asking for a fact, and the invitation shape only differs from it by a verb.
NOT_WANTED = re.compile(
    r"\b(?:know|knew|learn|ask|asked|tell|say|hear|check|explain|guess|help|try)\b"
    r"|\b(?:see|check|find\s+out)\s+if\b|\bwhether\b|\bhow\s+to\b")
# Not every line with an invite word in it is asking the bot along. "Do you want me to ring
# them" is an offer to do something for the bot, "do you want a hand with that" offers help,
# "do you want anything from the shop" is a shopping list and "do you fancy her" is asking
# about somebody else. None of them invites anybody anywhere, so none of them gets a refusal.
NOT_AN_INVITE = re.compile(
    r"\b(?:anything|something|a\s+hand|a\s+lift|a\s+receipt|a\s+piece|me\s+come|"
    r"her|him|them|die|dying|kill)\b"
    r"|\b(?:want|like|need|fancy)\s+(?:me|us)\s+to\b")

# The thing invited to, so the question that comes back is about that thing: a drink is a place
# and a time, a film is what is on, a walk is where it goes.
TOGETHER_AT = (
    ("drink", re.compile(
        r"\b(?:coffee|cuppa|brew|pint|beer|wine|drink|juice|tea\s+out|pub|bar|cafe|"
        r"coffee\s+shop)\b")),
    ("meal", re.compile(
        r"\b(?:lunch|dinner|brunch|breakfast|takeaway|take\s+away|curry|pizza|chinese|indian|"
        r"bite|meal|restaurant|nando'?s|kebab)\b")),
    ("walk", re.compile(
        r"\b(?:walk|stroll|hike|wander|run|jog|cycle|bike\s+ride|swim|gym|park\s+run)\b")),
    ("screen", re.compile(
        r"\b(?:film|movie|show|play|gig|concert|match|telly|cinema|theatre|festival)\b")),
    ("shopping", re.compile(
        r"\b(?:shopping|shops|market|city\s+centre|high\s+street|boot\s+sale)\b")),
    ("out", re.compile(
        r"\b(?:day\s+out|weekend\s+away|trip|beach|countryside|seaside|coast|museum|"
        r"stately\s+home|picnic)\b")),
)
TOGETHER_REPLIES = {
    "drink": (
        "I can't come along, but that sounds like a good idea. Where do you go for it?",
        "Wish I could join you. Somewhere near you, or the place you always go?",
    ),
    "meal": (
        "I can't make it, but that sounds good. Is it a treat, or an ordinary weeknight?",
        "Wish I could be there. Somewhere new, or the place you always end up in?",
    ),
    "walk": (
        "I can't come with you, but that sounds like a good idea. Is there a route you like, or "
        "somewhere new to try?",
        "Wish I could join you. It clears the head more than people expect - where do you go?",
    ),
    "screen": (
        "I can't come along, but that is a good shout. What is on?",
        "Wish I could be there. Something you have been meaning to see, or picking on the night?",
    ),
    "shopping": (
        "I can't come along, but that sounds like a good afternoon. Is it a browse, or are you "
        "after something in particular?",
        "Wish I could be there. Do you know what you want, or will it find you?",
    ),
    "out": (
        "I can't come along, but that sounds like a good day out. Where are you thinking?",
        "Wish I could be there. Have you been before, or would it be the first time?",
    ),
}


def _the_invitation(clean):
    """Which pool answers an invitation to the bot, or None when the line is not one."""
    text = " ".join(str(clean or "").lower().split())
    if not text or not INVITED.search(text):
        return None
    if not INVITED_AT_THE_START.match(text) and NOT_THEIRS.match(text):
        return None
    if NOT_WANTED.search(text) or NOT_AN_INVITE.search(text):
        return None
    for kind, pattern in TOGETHER_AT:
        if pattern.search(text):
            return TOGETHER_REPLIES[kind]
    # Nothing the pools know: "do you fancy" on its own, "want to go somewhere". The refusal
    # with no thing in it is the shape that gets everything else wrong ("do you want a lift
    # home", "do you want a receipt"), so a line with no thing is left to the rest of the bot.
    return None


def reply_for(text, memory):
    """The line an invitation to the bot gets, or None when the line is not one."""
    clean = " ".join(str(text or "").lower().split())
    pool = _the_invitation(clean)
    if not pool:
        return None
    return compose_pick(pool, memory, clean)
