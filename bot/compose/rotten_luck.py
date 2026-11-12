"""A thing of theirs that has been damaged, taken or refused is not a day that went well.

"We had a flood", "someone keyed my car", "my son got suspended", "i came off my bike" and "my
visa was refused" all reach the composer's small-day pool on main, which is written for an
ordinary account of an ordinary afternoon ("a takeaway, a haircut, work being alright"):

    we had a flood                -> "Nice one. How did the rest of it go?"
    someone keyed my car          -> "Good to hear. What was the best bit?"
    my son got suspended          -> "Nice one. How did the rest of it go?"
    i came off my bike            -> "Nice one. How did the rest of it go?"

That is the worst thing the bot can say to somebody, and it is not a knowledge gap: nothing needs
looking up to answer it. `bot/compose/badnews.py` reads the hard news - a diagnosis, a death, the
money running out - but a flooded kitchen, a keyed car and a child sent home are a smaller kind
of bad day, and no reader has them, so they fall through to the pleasantry.

What a friend does with one of these is say it is rotten and ask one thing about it, which is
what this file does. Three pools, because the three shapes want different questions: a thing of
theirs that was damaged or taken wants "what needs sorting", a refusal or a punishment that
landed on them wants "what did they say", and coming off a bike wants "are you alright".

This is a last resort and it is written to be one. `bot/modules/greeting.py` asks it at the very
end, and it only takes the turn when the reply the composer chose is one of its glad lines - so
an answer of any kind, from any module, keeps the turn it has. Nothing here invents a fact: the
reply says the day is bad and asks about it.

The words that are ordinary in another line are left out: "a flood of orders", "flooded with
applications", a "fire drill", a code "keyed in", the show somebody "stole". A line that says
one of those is not this.
"""
import re

from . import pick

# A place of theirs that took water, fire or a break-in.
THEIR_PLACE = (r"(?:my|our|the)\s+(?:[a-z']+\s+)?(?:house|flat|place|home|kitchen|bathroom|cellar|basement|loft|"
               r"garage|shed|garden|hall|hallway|landing|roof|bedroom|attic|utility|conservatory)")

# Something of theirs, named or not, that was done to. Two words at most, so a long line about a
# thing that is not theirs does not match by accident.
THEIR_THING = r"(?:my|our)\s+(?:[a-z']+\s+){0,2}"

NOT_GOOD = tuple(re.compile(pattern) for pattern in (
    # Water or fire in the place they live, however it is said: "we had a burst pipe", "the flat
    # is flooding", "our shed caught fire". "a burst of energy" is not a pipe and "fire drill" is
    # not a fire, so those two carry their own guard below.
    rf"\b(?:we|i|they)\s+(?:just\s+)?had\s+(?:a|an)\s+(?:flood|flooding|leak|burst\s+pipe|"
    r"burst\s+radiator|break[- ]?in|burglary|fire)\b",
    rf"{THEIR_PLACE}[^.!?,]{{0,24}}\b(?:flooded|flooding|is flooding|has flooded|caught fire|"
    r"went on fire|is leaking|was leaking|has water coming in|came through the ceiling)\b",
    # A break-in and a theft: "we got burgled", "my bike got nicked", "someone took my bike".
    r"\b(?:got|been|were|was)\s+(?:burgled|broken into|robbed|vandalised|vandalized|"
    r"smashed up|turned over)\b",
    rf"{THEIR_THING}\b(?:got|was|were|has been|had been|is|are|got\s+)\s*(?:keyed|scratched|"
    r"dented|clamped|towed(?:\s+away)?|smashed|nicked|stolen|vandalised|vandalized|"
    r"broken into|pinched|slashed|punctured|kicked in|wrenched off|snapped off|ripped|torn|"
    r"torched|set (?:on )?fire to)\b",
    r"\b(?:someone|somebody|a kid|the kids|next door|a neighbour|a neighbor|my neighbours?|"
    r"our neighbours?|the neighbours?)\s+"
    r"(?:keyed|scratched|dented|smashed|nicked|pinched|stole|took|vandalised|vandalized)\s+"
    r"(?:my|our)\b",
    # A refusal or a punishment that landed on them or on their child. The thing refused has to
    # be named: "my visa was refused", "my son got suspended", "my application was turned down".
    rf"{THEIR_THING}\b(?:son|daughter|kid|child|boy|girl|lad|lass|teenager|eldest|youngest)\b"
    r"[^.!?,]{0,30}\b(?:suspended|excluded|expelled)\b",
    rf"{THEIR_THING}\b(?:visa|application|claim|mortgage|loan|benefits?|pip|dla|passport|"
    r"offer|request)\b[^.!?,]{0,24}\b(?:refused|rejected|turned down|declined|denied|"
    r"turned me down|turned them down)\b",
    # Coming off something, and a prang in a car.
    r"\bcame off\s+(?:my|his|her|the|a|their)\s+(?:bike|motorbike|moped|scooter|e-scooter|"
    r"cycle|horse|ladder|roof|skateboard|board)\b",
    rf"{THEIR_THING}\b(?:car|van|bike|motorbike)\b[^.!?,]{{0,20}}\b(?:got|was|were)\s+"
    r"(?:clamped|towed(?:\s+away)?|keyed|scratched|dented|scraped)\b",
    r"\bpranged\b|\bscraped the (?:car|van|wing mirror)\b",
    # A part of the place that came down or blew away: "the ceiling came down", "my greenhouse
    # blew away", "the fence blew down", "a tile came off the roof". Nothing here is a good day,
    # and the composer has the small-day pool for it.
    rf"(?:{THEIR_PLACE}|\b(?:ceiling|roof|fence|gate|wall|greenhouse|tree|branch|tiles?|"
    r"guttering|gutter|chimney pot|carport|awning))\b[^.!?,]{0,24}\b(?:came down|collapsed|"
    r"caved in|blew (?:away|down|off|over)|got blown (?:away|down|off))\b",
))

# The same words where the line is not bad news at all: an order book "flooded with
# applications", a fire drill, a code keyed in, a show stolen, and a bike nicked off early.
NOT_GOOD_DESPITE = re.compile(
    r"\bflood(?:ed)?\s+(?:of|with)\b|\bfire\s+(?:drill|alarm|test|work|escape|station|place|"
    r"pits?)\b|\bkeyed\s+in\b|\bstole\s+the\s+(?:show|limelight|scene)\b|"
    r"\bnicked\s+(?:off|out)\b|\brobbed\s+(?:blind|us of)\b|\be?xcluded\s+from\s+the\s+pub\b")

# The composer's glad lines: the small-day pool and the pleasantries about a thing done. One of
# these on a line like the ones above is the bot congratulating somebody on a bad day. The
# question half of the pool is the reliable part, so it is read wherever it sits, and the opener
# is read at the start of the reply.
GLAD_OPENER = re.compile(
    r"^(?:nice one|good to hear|sounds alright|well done|that'?s good|lovely|glad to hear|"
    r"how was it, overall)\b")

# And the other thing a rotten day gets from the composer: nothing. "Got it. Is there anything
# you'd like a hand with?" is the intake form, and "Rotten luck." and "That's a pain." are a
# receipt of the news with no question after it - a friend says one of those and then asks. These
# are read on the same gate, so they are only replaced on a line this file has read as a bad day.
BLANK_OR_THIN = re.compile(
    r"^(?:got it\b|thanks for telling me|i'?m listening|noted:|right\.|okay\.|ok\.|"
    r"rotten luck\.?$|that'?s a pain\.?$|that'?s rough\.?$|fair enough\b|"
    r"ugh, that'?s annoying\.?$|that'?s annoying\.?$)")
GLAD_ANYWHERE = re.compile(
    r"\b(?:how did the rest of it go|what was the best bit|anything good in it|"
    r"are you pleased with it|is it what you were after|how did that feel)")

# The bad thing is already over: "my bike got nicked and i got it back", "the flat flooded but
# its dried out now", "i came off my bike but im fine". The pools below ask what needs sorting,
# and a person who has just said it is sorted is not asking that. A search engine has nothing to
# add either, so the turn keeps whatever the composer had and this module stands aside.
RESOLVED = re.compile(
    r"\b(?:but|and|although|though)\s+(?:\w+\s+){0,3}?(?:sorted|sorted out|fixed|resolved|"
    r"dried out|paid out|refunded|replaced|recovered|got it back|got them back|got them|"
    r"back at school|back to normal|back home|all fine|all ok|ok now|okay now|fine now|"
    r"im fine|i'?m fine|was fine|no harm|nobody hurt|no one hurt|nothing was taken|"
    r"only a scratch|turned out (?:fine|ok)|got it on appeal|won the appeal|"
    r"appeal worked|only took (?:a|the|my|our|one)\b)\b")

# A thing of theirs damaged, taken or refused: the question is what needs doing about it.
DAMAGED_OR_TAKEN = (
    "Rotten luck. What needs sorting first?",
    "That's a rotten one. How bad is it?",
    "Ugh, that's the last thing you needed. Is it sorted, or still going on?",
    "That's a mess to land on you. What's the damage?",
)
# A refusal or a punishment that came from somebody else: the question is what they said.
# A refusal is the arm where the next line is often a question of its own, and there is a card
# waiting behind it: "my visa was refused" / "what do i do now" answers with the passport pages.
# A reply that ends on a question hands that next line to the composer's question-back pool
# instead ("I can be specific if you tell me this much: what did they say?"), and the card is
# lost, so this pool asks nothing. An invitation there is no better: "tell me what it said when
# you're ready" comes back as a step ("Take your time with the next bit, and take it from
# there"). These lines state the sympathy and leave the next turn free.
A_BLOW_FROM_SOMEONE = (
    "That's a blow. Sorry to hear it.",
    "Ugh, that's harsh. That's a rotten thing to have land on you.",
    "That's a rotten thing to land on you.",
)
# Coming off a bike: the person comes before the thing.
A_FALL = (
    "That's a shock. Are you alright?",
    "Ouch. Are you hurt?",
    "That would rattle anyone. Are you alright?",
)

# Somebody else came off the bike: "my brother came off his bike yesterday" is not a report about
# the person in front of the bot, and "Are you alright?" asks the wrong one. "They" is what a
# friend says about a brother or a sister, and it needs no gender from the line.
A_FALL_ELSE = (
    "That's a shock. Are they alright?",
    "That's a bad one. How are they doing?",
    "That's a shock to hear. Is everyone alright?",
)
_SOMEONE_ELSE = re.compile(r"\b(?:my|our|his|her|their)\s+(?:brother|sister|son|daughter|mum|mom|"
                           r"dad|husband|wife|partner|mate|friend|neighbour|neighbor|nephew|"
                           r"niece|grandad|granddad|grandma|gran|nan|colleague|boss|cousin|little "
                           r"(?:boy|girl|lad|one))\b|\b(?:he|she|they)\s+(?:came off|fell)\b")
_FALL = re.compile(r"\bcame off|\bpranged\b|\bscraped the (?:car|van|wing mirror)\b|\bclamped\b|"
                   r"\btowed\b")
_FROM_SOMEONE = re.compile(r"\b(?:suspended|excluded|expelled|refused|rejected|turned down|"
                           r"declined|denied)\b")


# Not every day that goes wrong has a thing damaged in it. The other shapes reach the same glad
# line because none of them is a question and none of them names a thing the bot could look up:
#
#     ive tried two cables                          -> "How was it, overall?"
#     i waited two hours at the clinic               -> "Got it. Is there anything you'd like a hand with?"
#     my dad passed comment on my cooking            -> "Got it. Is there anything you'd like a hand with?"
#     but i thought id already paid                  -> "How was it, overall?"
#
# An attempt that failed, a wait that went on, a remark that stung and a bill that says otherwise
# are all a person telling the bot where they are stuck, and every one of them is answered with a
# pleasantry about a day that went well. Each wants one question about the thing itself, which is
# what the pools below ask.
A_THING_THAT_DID_NOT_WORK = (
    "That's annoying. What does it do when you try it?",
    "Ugh, one of those. Where are you up to with it now?",
    "That's a pain. What have you got in front of you at the moment?",
    "Rotten. Does it do the same thing every time?",
)
A_WAIT_THAT_WENT_ON = (
    "That's a long time to sit there. Did you get seen in the end?",
    "Ugh, two hours of that. Was it worth staying for?",
    "That's a lot of waiting. Did anyone tell you what was going on?",
)
A_REMARK_THAT_STUNG = (
    "That would sting. What did they say?",
    "Ugh, that's not a kind thing to say. How did you take it?",
    "That's the sort of thing that sits with you. Did you say anything back?",
)
A_BILL_THAT_SAYS_OTHERWISE = (
    "That's worth checking before you pay again. What does the bill say?",
    "Ugh. What does their paperwork say you owe?",
    "That's easily done on their side. Have you got the receipt?",
)
# An attempt that failed, in the person's own words: "ive tried two cables", "i tried everything",
# "none of it worked", "still nothing", "no luck". A report of a fix that worked is not one of
# these ("i dried it with a hairdryer" keeps the glad line), so the line has to say the attempt
# did not settle it.
_TRIED_AND_IT_DID_NOT = re.compile(
    r"\b(?:ive|i'?ve|we'?ve|weve|i|we)\s+(?:already\s+)?(?:tried|attempted)\b"
    r"|\btried\s+(?:everything|it all|all of it|that|this|it|both|two|three|\w+\s+\w+(?:es|s))\b"
    r"|\bnothing\s+(?:works|worked|has worked|i try|i do)\b"
    r"|\b(?:didn'?t|doesn'?t|won'?t|wont|not)\s+work(?:ed)?\b"
    r"|\bno\s+luck\b|\bstill\s+(?:nothing|not|no|the same|doing it|happening)\b"
    r"|\bkeeps?\s+(?:doing|going|coming back|happening)\b"
    r"|\bgave up on it\b")
# A wait the person sat through: "i waited two hours", "we were queueing for ages".
_A_WAIT = re.compile(
    r"\b(?:i|we|he|she|they)\s+(?:was|were|have been|had been)?\s*wait(?:ed|ing)?\b"
    r"|\bqueue(?:d|ds|ing|s)?\b|\bin\s+the\s+queue\b|\bsat\s+in\s+(?:a|the)\s+waiting\b")
_A_LONG_WAIT = re.compile(r"\b(?:hours?|hrs?|ages|half an hour|an hour|two hours|all morning|"
                          r"all afternoon|\d+\s*(?:hours?|hrs?))\b")
# Somebody had a go at them about something of theirs: "my dad passed comment on my cooking",
# "she moaned at me about the garden", "he went on at me". The remark, not a punishment that
# landed (that is a refusal above), so the question is what was said.
_A_REMARK = re.compile(
    r"\bpassed\s+(?:a\s+)?(?:comment|remark|comments|remarks)\b"
    r"|\b(?:had|having)\s+(?:a\s+)?go\s+at\s+me\b"
    r"|\b(?:moaned|went on|nagged|lectured)\s+(?:at|to)\s+me\b"
    r"|\bsaid\s+something\s+(?:about|on)\s+my\b"
    r"|\bmade\s+a\s+(?:comment|remark|face)\s+about\b")
# A bill or a charge that says otherwise: "but i thought id already paid", "they say i owe for
# last month", "i was told it was free".
_A_DISPUTED_CHARGE = re.compile(
    r"\bbut\s+i\s+(?:thought|was\s+told|understood|believed)\b[^.!?]{0,44}"
    r"\b(?:paid|pay|included|free|covered|booked|settled|refund(?:ed)?)\b"
    r"|\b(?:they|it)\s+says?\s+i\s+owe\b|\bcharged\s+me\s+again\b"
    r"|\bi\s+was\s+told\s+it\s+was\s+(?:free|included)\b")


# A line that opens as an ask is an ask, whether or not it carries a question mark: "what if i
# tried again", "does it still work", "should i give up on it" all wear one of the shapes below
# and all have an answer of their own.
_AN_ASK_OPENING = re.compile(
    r"^(?:what|how|why|when|where|which|who|whose|is|are|was|were|do|does|did|can|could|should"
    r"|would|will|shall|am|may|might|any\s+chance|isnt|arent|doesnt|dont|didnt)\b")


def reads_as_stuck_with_it(clean):
    """True when the line reports an attempt that failed, a wait, a remark that stung or a bill.

    Whole shapes only, and never an ask: "what if i tried again" and "how long should i wait"
    are questions with an answer of their own, and they are answered where they are read.
    """
    if not clean or "?" in clean or NOT_GOOD_DESPITE.search(clean):
        return False
    if _AN_ASK_OPENING.match(clean):
        return False
    if _A_DISPUTED_CHARGE.search(clean):
        return True
    if _A_REMARK.search(clean):
        return True
    if _TRIED_AND_IT_DID_NOT.search(clean):
        return True
    return bool(_A_WAIT.search(clean) and _A_LONG_WAIT.search(clean))


def reads_as_not_good(clean):
    """True when the line is a thing of theirs that has been damaged, taken, refused or fallen."""
    if not clean or NOT_GOOD_DESPITE.search(clean):
        return False
    return any(pattern.search(clean) for pattern in NOT_GOOD)


def reads_as_glad(reply):
    """True when the reply congratulates the news, or is a receipt of it with nothing after."""
    if not reply:
        return False
    line = reply.strip().lower()
    return bool(GLAD_OPENER.match(line) or GLAD_ANYWHERE.search(line)
                or BLANK_OR_THIN.match(line))


def answer_for(text, memory=None, reply=None):
    """A rotten thing answered as rotten, or None.

    Called with the reply the composer chose, because the whole point is that no other module
    wanted the turn: a line that has an answer of its own keeps it.
    """
    if not reads_as_glad(reply):
        return None
    memory = memory or {}
    clean = ((memory.get("understood") or {}).get("clean") or text or "").lower()
    clean = " ".join(clean.split())
    if RESOLVED.search(clean):
        return None
    if reads_as_stuck_with_it(clean):
        # The attempt that failed, the wait, the remark that stung and the bill that says
        # otherwise are not a thing that was damaged: each has its own question, and none of
        # them is a day that went well.
        if _A_DISPUTED_CHARGE.search(clean):
            pool = A_BILL_THAT_SAYS_OTHERWISE
        elif _A_REMARK.search(clean):
            pool = A_REMARK_THAT_STUNG
        elif _A_WAIT.search(clean) and _A_LONG_WAIT.search(clean):
            pool = A_WAIT_THAT_WENT_ON
        else:
            pool = A_THING_THAT_DID_NOT_WORK
        return pick(list(pool), memory, clean)
    if not reads_as_not_good(clean):
        return None
    if _FALL.search(clean):
        pool = A_FALL_ELSE if _SOMEONE_ELSE.search(clean) else A_FALL
    elif _FROM_SOMEONE.search(clean):
        pool = A_BLOW_FROM_SOMEONE
    else:
        pool = DAMAGED_OR_TAKEN
    return pick(list(pool), memory, clean)
