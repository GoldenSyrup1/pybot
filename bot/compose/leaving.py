"""A line that says the person is going: the last thing said in a chat.

People end conversations all day, and they do it the way they start one - with a little
filler in front and a reason behind: "anyway i better go, hes crying", "ill let you go,
dinner is burning", "right im off to bed". No knowledge entry owns a goodbye, so before this
the answer was whatever the reason clause matched ("dinner is burning" got *"take it off the
heat"*), or the honest search shrug for a question nobody asked.

Two things are needed for that, and both live here so they cannot drift apart:

* `reads_as_leaving(clean)` - the reading. The leaving has to be the *clause*, not a word in
  it: "i better go" and "im off to bed" are leaves, "i better go to the chemist for a rash"
  is a plan and "should i let my son go on the trip" is a question. A reason after the
  leaving ("got to go, the kids are up") does not change what the line is.
* `pool(clean)` - the wording. A goodbye deserves a goodbye, in the bot's own voice, with a
  little variety so no two in a row are the same.

The arbiter reads the kind (`fallback.reading` returns it) so a topic entry cannot take the
line back on a word of the reason clause.
"""
import re

# The composer's name for this kind of line, read by bot/modules/arbiter.py.
LEAVING = "leaving"

# The time a goodbye is for is part of the goodbye, not a new subject: "see you at 5",
# "talk to you after work", "catch you on monday" are all goings, and on main the time in the
# rest of the clause was the one thing that stopped them being read - "see you tomorrow" was a
# goodbye and "see you at 5" was "Thanks for telling me - I'm here if you want to dig into any
# of that". Only times are allowed here, and no place and no occasion: "see you at the
# hospital tomorrow", "see you at the party" and "see you after the gym" keep their own meaning.
_A_SIGN_OFF = re.compile(
    r"\b(?:(?:catch|see)\s+(?:you|ya|u)\b|(?:talk|speak|chat)(?:ing)?\s+"
    r"(?:to\s+)?(?:you|ya|u)\b|(?:c\s*u|c\s*ya)\b)")
_A_LEAVE_TIME = re.compile(
    r"\b(?:(?:at|around|about)\s+(?:about\s+|around\s+|half\s+)?\d{1,2}(?::\d{2})?\s*"
    r"(?:am|pm|o'?clock)?"
    r"|(?:at|around|about)\s+(?:about\s+|around\s+|half\s+)?(?:one|two|three|four|five|six|seven|"
    r"eight|nine|ten|eleven|twelve)\b"
    r"|at\s+(?:lunch|lunchtime|teatime|breakfast|break)\b"
    r"|after\s+(?:work|school|college|uni|university|lunch|tea|dinner|the\s+school\s+run)\b"
    r"|on\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tues|weds|thurs"
    r"|fri|sat|sun)\b"
    r"|this\s+(?:evening|afternoon|weekend)\b|next\s+week\b|at\s+the\s+weekend\b"
    r"|in\s+the\s+(?:morning|afternoon|evening)\b"
    r"|in\s+(?:a\s+)?(?:bit|while|minute|sec|second|mo|moment)\b)")


# The leave itself: the shapes people actually type. "go" is the verb that matters; "gone" is
# not here, so "my back has gone" and "the milk has gone off" stay where they belong.
#
# The verb of going is the one people type, and it is said with more words than "go": "get off",
# "get going" and a bare "shoot". On main the modal branch only knew "go", "be off", "head
# off", "shoot off", "run", "dash" and "fly", so "better get off" reached the search hedge
# ("a quick search online will get you a solid answer"), "ill get going" reached "Good - that
# sounds like the right next step" and "im gonna head off" the same.
_GOING_VERB = (r"(?:go|get\s+off|get\s+going|be\s+off|be\s+going|head\s+off|shoot|shoot\s+off"
               r"|run|dash|fly)")

_LEAVE = re.compile(
    r"\b(?:"
    r"(?:got|gotta|have|has|need|needs|better|best|must|ought|should)\s+(?:to\s+)?"
    + _GOING_VERB +
    # "im gonna head off", "we are gonna shoot off", "im going to head off": the going said
    # with the words people type. The store rewrites "gonna" to "going to" before this, so the
    # long form is the one that has to be read, and it goes first: the shorter "im going" below
    # would match first and leave "to head off" behind.
    r"|(?:i'?m|im|i\s+am|we'?re|we\s+are|i'?ll|ill)\s+(?:gonna|going\s+to)\s+"
    r"(?:go|be\s+off|head\s+off|shoot(?:\s+off)?|get\s+off)\b"
    r"|(?:i'?m|im|i\s+am|we'?re|we\s+are|i'?ll|ill)\s+"
    r"(?:be\s+)?(?:off|going|head(?:ing)?\s+off|shoot(?:ing)?\s+off|out\s+of\s+here"
    r"|get\s+(?:off|going))\b"
    # How the leave is said when it is the person going away rather than going somewhere: "im
    # away", "ok im out", "im away to my bed". A plan keeps its own reading, so the leftovers
    # after it have to be the run-up or the little words - "im away next week" and "im out of
    # ideas" are not goodbyes.
    r"|(?:i'?m|im|i\s+am|we'?re|we\s+are)\s+(?:away|out)\b"
    r"|(?:off\s+to\s+(?:bed|sleep|work|school|the\s+shop))\b"
    r"|(?:let\s+you\s+go|leave\s+you\s+to\s+it|leave\s+you\s+be|let\s+you\s+get\s+on"
    r"|let\s+you\s+get\s+back|stop\s+bothering\s+you)\b"
    r"|(?:talk|speak|chat)(?:ing)?\s+(?:to\s+you\s+)?(?:later|soon|tomorrow)\b"
    # "talk to you after work", "speak to you on monday": the same sign-off with the time on it.
    r"|(?:talk|speak|chat)(?:ing)?\s+(?:to\s+you\s+)?(?:" + _A_LEAVE_TIME.pattern + r")"
    r"|(?:catch|see)\s+(?:you|ya)\b"
    r"|(?:time\s+(?:for\s+me\s+)?to\s+go)\b"
    # A leave said as the end of the day rather than as the verb: "thats me done for the day",
    # "im done for today", "time i was off", "need my bed", "my beds calling", "time for bed
    # for me". Each of them reached the stock nod or "Thanks for telling me", and none of them is
    # a question about the day.
    r"|(?:that'?s|thats)\s+(?:me\s+)?done\b"
    r"|(?:that'?s|thats)\s+it\s+from\s+me\b"
    r"|(?:i'?m|im|i\s+am)\s+done\s+for\s+(?:the\s+)?(?:day|today|now)\b"
    r"|(?:time\s+(?:i\s+was\s+off|(?:for\s+)?(?:my\s+)?bed))\b"
    r"|(?:need|needs)\s+my\s+bed\b"
    r"|(?:my\s+bed'?s?\s+calling)\b"
    r")")

# A goodbye that carries a day on it is about a time to meet, and what follows it is that day's
# plan, not the reason the person is going now: "see you at 5 tomorrow, i have a meeting" was read
# as a leave with a reason behind it and answered "Go on then - that comes before me. Take care.",
# as though the meeting were what they were leaving for. The goodbye still stands; only the reason
# pool is wrong for it.
_A_DAY_AHEAD = re.compile(
    r"\b(?:tomorrow|tonight|on\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon"
    r"|tues|weds|thurs|fri|sat|sun)\b|next\s+(?:week|weekend|month|monday|tuesday|wednesday"
    r"|thursday|friday|saturday|sunday)|this\s+(?:evening|afternoon|weekend)|in\s+the\s+"
    r"(?:morning|afternoon|evening)|later\b|after\s+(?:work|school|college|uni|university"
    r"|lunch|tea|dinner|the\s+school\s+run)\b)")

# A goodbye said as a wish names leaving nowhere at all: "have a good day", "take care", "have a
# nice weekend", "all the best", "laters". It is the politest way out of a chat and it is still a
# leave, so the pool answers it as one; before this it fell to the honest search shrug ("I'd
# rather not guess - a quick search online will get you a solid answer") or to the stock nod, and
# a person who says "have a good day" is not asking for a search. The wish has to be the whole
# clause, which is what keeps "have a good day at work", "good luck with the interview" and "take
# care of my mum" out: those say something of their own.
_WISH = re.compile(
    r"^(?:ok |okay |right |well |and |so |cheers |thanks |thank you |nice |great |bye )*"
    r"(?:"
    r"(?:i )?hope (?:you )?(?:have )?(?:a |an )?"
    r"(?:really |very |lovely |nice |great |good |safe |smashing |brilliant |restful )*"
    r"(?:day|evening|weekend|week|night|one|time|holiday|christmas|break|rest|trip|journey)\b"
    r"|(?:you )?have (?:a |an )?"
    r"(?:really |very |lovely |nice |great |good |safe |smashing |brilliant |restful )*"
    r"(?:day|evening|weekend|week|night|one|time|holiday|christmas|break|rest|trip|journey)\b"
    # A wish said to the bot about the bot: "get well soon", "feel better soon", "sleep well",
    # "hope your day goes well", "enjoy your lunch", "have fun tonight". Each of these was answered
    # with an intake form ("Got it. Is there anything you'd like a hand with?") or, for the two
    # with an occasion in them, with the honest search shrug - a person wishing the bot a good day
    # was told that a search would turn up better sources.
    # The second person has to be the bot itself. "hope you feel better soon" is about the bot's
    # health; "i hope your mum feels better" is about somebody who is actually ill, and a bot that
    # says "you too" to that is claiming a well mum. "your" therefore takes one of the bot's own
    # occasions and nothing else, so a third person (mum, cat) or a body part ("hope your back
    # feels better") falls through to the entry that answers it.
    r"|(?:i )?hope (?:that )?(?:you\b[^.!?,;]{0,30}?"
    r"|your (?:day|evening|weekend|week|night|lunch|dinner|meal|shift|rest|break|time|one|trip"
    r"|journey|holiday)\b[^.!?,;]{0,30}?)"
    r"(?:well|better|good|great|lovely|nice|fine|okay|smoothly|easily|restful|fun)\b"
    r"|(?:you )?have (?:a )?(?:good )?fun\b"
    r"|(?:you )?enjoy (?:a |an )?(?:good|great|nice|lovely|fun|happy) "
    r"(?:day|evening|weekend|week|night|time|one|trip|journey|holiday|break|shift|lunch|dinner"
    r"|meal|party)\b"
    r"|(?:you )?enjoy (?:your|the) "
    r"(?:day|evening|weekend|night|lunch|dinner|meal|party|trip|holiday|break|shift|rest|"
    r"bath|walk|flight)\b"
    r"|get well soon\b"
    r"|(?:you )?feel better(?: soon)?\b"
    r"|(?:you )?sleep (?:well|tight)\b"
    r"|(?:you )?take care\b"
    r"|all the best\b"
    r"|best wishes\b|best regards\b|(?:kind|warm) regards\b"
    r"|best of luck\b"
    r"|(?:good )?luck\b"
    r"|look after yourself\b"
    r"|laters\b|laterz\b"
    r")")
# What may be left once the wish has been said: "have a good day then, thanks x" is still only a
# goodbye. A word of content in the tail means the clause is doing more than that.
_WISH_ALLOWED = frozenset((
    "then", "now", "too", "both", "all", "and", "you", "thanks", "thank", "cheers", "bye",
    "byebye", "goodbye", "ok", "okay", "right", "well", "so", "x", "xx", "xxx", "mate", "guys",
    "folks", "everyone", "of", "yourself", "it", "to", "for", "the", "a", "have", "nice", "one",
    # The occasion a wish is for is not a new subject: "have a good day at work", "good luck with
    # the interview" and "enjoy your weekend away" are the same goodbye as the bare wish, and
    # before this the detail sent them back to the stock nod or the honest search shrug. Only
    # places and occasions are allowed here, so "take care of my mum" and "have a good look at
    # the boiler" keep their own meaning.
    "at", "with", "in", "on", "work", "school", "class", "shift", "tonight", "tomorrow",
    "today", "soon", "away", "party", "interview", "meeting", "appointment", "exam", "test",
    "flight", "drive", "game", "match", "christmas", "new", "year", "your", "both", "as",
    "well", "everything", "feeling", "day", "night", "weekend", "trip", "journey", "home",
    "break", "lunch", "dinner", "meal", "rest", "sleep", "fun", "safe", "early", "late",
))

# Words a bare leaving is allowed to keep: the breather in front ("ok", "anyway", "right"),
# the pronouns, and the little time words that sit on the end ("now", "then", "soon"). Anything
# else left over means the clause is doing something more than leaving - "i better go and get
# the washing in" is a plan.
_ALLOWED = frozenset((
    "ok", "okay", "right", "well", "anyway", "anyways", "alright", "oh", "so", "yeah", "yes",
    "and", "but", "sorry", "thanks", "thank", "ta", "hi", "hey", "listen", "look", "mm", "mhm",
    "i", "im", "ill", "id", "we", "us", "me", "you", "my", "the", "a", "an", "to", "for", "bit",
    "little", "while", "second", "minute", "sec", "now", "then", "soon", "later", "tonight",
    "today", "tomorrow", "morning", "night", "bed", "sleep", "work", "shop", "it", "home",
    "day", "the", "that", "should", "gonna",
    # The same little words with the apostrophe people actually type. "id better go" was read as
    # a leave and "i'd better go" was not, because the leftover token was "i'd" and the set had
    # only "id": the same goodbye, sent to the search hedge for a missing apostrophe.
    "i'd", "i'll", "i'm", "i've", "we'd", "we'll", "we're", "it's", "that's",
))

# A line that opens like a question is a question: "can i go out tonight", "should i let my
# son go on the trip", "what time should i go". The leave phrase inside it is the subject,
# not the goodbye.
_OPENS_QUESTION = re.compile(
    r"^(?:can|could|should|shall|do|does|did|is|are|was|were|will|would|may|might|must|"
    r"what|when|where|why|how|who|which|whose|if|whether)\b")
# A clause that asks is not a reason for leaving: "got to go, what should i do about it".
# "whats", "hows" and "wheres" are the same asks with the verb swallowed, and they are how people
# type them: "id better go, but first whats the best way to store basil" is a question, and the
# leave in front of it must not swallow the answer.
_ASKS = re.compile(r"\b(?:what|whats|why|whys|how|hows|when|whens|where|wheres|who|whos|"
                   r"which|should|do|does|did|can|could|would|will)\b")
# A clause that asks something is not a leave, wherever in the line it sits: "enjoy your weekend,
# any idea about the tax return" and "have fun tonight, any tips for the party" are a person asking
# a question with a wish in front of it, and answering the wish walks out on the question. The
# openers above catch a clause that starts with an ask; these catch the commonest asks that do not
# hang on a question mark ("any tips for", "is there a", "tell me how"). "if" and "whether" are
# left out on purpose: they are how a leave is softened ("ill let you go, if that is ok").
_ASKS_ANYWHERE = re.compile(
    r"\b(?:any\s+(?:idea|ideas|tips?|advice|suggestions?|chance|thoughts?|clue|pointers?)"
    r"|is\s+there|are\s+there|tell\s+me|do\s+you\s+know|can\s+you|could\s+you"
    r"|what\s+do\s+you|how\s+do\s+i|what\s+should\s+i|wondering\s+if|if\s+you\s+could"
    r"|what\s+about|how\s+about)\b")
_ASKS_OPENER = re.compile(
    r"^(?:can|could|should|shall|do|does|did|is|are|was|were|will|would|may|might|must|"
    r"what|whats|when|where|why|how|hows|who|whos|which|whose)\b")
# "i dont want you to go", "dont go yet" - the line is about staying.
_KEEPS = re.compile(r"\b(?:dont|don't|doesnt|doesn't|didnt|didn't|not|wont|won't|never)\b"
                    r"[^,.;]{0,24}\b(?:go|going|leave|off)\b")
# A full stop between two digits is a clock time, not the end of a clause: "see you at 5.30" is
# one clause, and splitting it left the "30" behind, where it read as the reason the person was
# going and the reply came from REASON_POOL ("Go on then - that comes before me. Take care.").
_SPLIT = re.compile(r"\s*(?:[,;!?]|(?<!\d)\.|\.(?!\d)| - | -- |\bbut\b)\s*")

# A goodbye on its own, or with the reason in front of it ("the kids are up, got to go").
POOL = (
    "Go well, and see you when you're back.",
    "Right, take it easy. Look after yourself.",
    "No worries at all. Mind yourself.",
    "Bye for now — mind how you go.",
    # No "with it" here: this pool is what a bare sign-off gets, and "All the best with it -
    # talk soon" was answering "see you at 8" with a line about a thing nobody had named.
    "All the best — talk soon.",
)
# The leave with a reason behind it: the reason comes first, so the reply goes to the reason
# and then lets them go.
REASON_POOL = (
    "Go on then — that comes before me. Take care.",
    "Fair enough, that matters more. Look after yourself.",
    "Of course. Go and see to it, and mind yourself.",
    "That first, definitely. Come back when you have a minute.",
)


def _clauses(clean):
    return [part.strip() for part in _SPLIT.split(clean) if part.strip()]


# A clause that is only a thank-you is not the reason anyone is leaving: "i better go, thanks for
# listening" is a goodbye after a hard chat, not a reason to answer first.
_THANKS_WORDS = frozenset((
    "thanks", "thank", "you", "for", "listening", "listened", "that", "helps", "helped", "so",
    "much", "a", "lot", "the", "chat", "talk", "talking", "it", "all", "help", "again", "was",
    "really", "useful", "advice", "everything", "mate", "and", "i", "appreciate", "means",
))


_RUN_UP = _ALLOWED | _THANKS_WORDS | frozenset(("ok", "okay", "right", "then", "your", "my",
                                                 "our", "much"))


# A sign-off word on its own is the front or the end of a goodbye, not news: "bye, have a good day"
# is the same wish as "have a good day", and reading "bye" as the person's own subject sent it back
# to the sign-off pool. `_SIGN_OFF` above is the reply reading and cannot be reused here.
_SIGN_OFF_WORDS = frozenset((
    "bye", "byebye", "goodbye", "later", "laters", "laterz", "night", "goodnight", "cheers",
    "ok", "okay", "right", "well", "thanks", "thank", "you", "ta", "so", "and", "now", "then",
    "anyway", "anyways", "alright"))


def _is_sign_off(clause):
    """True when a clause is only a sign-off word or two."""
    words = re.findall(r"[a-z']+", clause)
    return bool(words) and all(word in _SIGN_OFF_WORDS for word in words)


def _is_thanks_clause(clause):
    """True when a clause is only a thank-you."""
    words = re.findall(r"[a-z']+", clause)
    return bool(words) and all(word in _THANKS_WORDS for word in words)


# A reason that says someone is unwell is not a reason to say goodbye and nothing else: "i have
# to go, my back is really hurting" is a person telling you what is wrong, and the body is the
# modules' line. The goodbye is read on the next line, if they still go. A reason that is a
# thing to go and see to - dinner burning, the bus, the kids up, a taxi at the door - is the
# leave's own reason and is answered with the leave.
_UNWELL = re.compile(
    r"\b(?:"
    r"sick|ill|poorly|unwell|hurts?|hurting|ached?|aches|aching|pain(?:ful)?|sore|stiff"
    r"|headache|migraines?|toothache|cramps?|cramping|fever|temperature|vomit(?:ing|ed)?"
    r"|throwing\s+up|threw\s+up|nausea|nauseous|dizzy|faint|flu|infection|cough(?:ing)?"
    r"|rash|swollen|swelling|bleed(?:ing)?|blister(?:s|ed)?|stomach|diarr?hoea"
    r")\b")
# A body said the everyday way: "my back is killing me", "my head is banging", "my knee is in
# agony tonight". The mark on its own is figurative - "work is killing me", "the traffic is
# killing me" - so the clause has to name a body part as well before it is a complaint about the
# body. How bad it is said is not the gate: `killing me`, `banging` and `in bits` are the same
# class, and a body named in the reason clause is what makes the reason a symptom turn.
_HURTING = re.compile(r"\b(?:kill(?:s|ing)?(?:\s+(?:me|my))?|agony|agonis(?:ing)?|agoniz(?:ing)?"
                     r"|throbbing|thumping|banging|pounding|hammering|splitting|stinging|burning"
                     r"|on\s+fire|in\s+bits|hurts?|hurting|aching|aches?|sore|stiff|tender"
                     r"|twinge|swollen|killing\s+me)\b")
_BODY = re.compile(r"\b(?:head|heads|throat|ear|ears|eye|eyes|tooth|teeth|back|backs|knee|knees"
                   r"|shoulder|shoulders|arm|arms|leg|legs|foot|feet|ankle|ankles|wrist|wrists"
                   r"|neck|hip|hips|toe|toes|hand|hands|finger|fingers|chest|stomach|belly|skin"
                   r"|jaw|sinus|sinuses|gum|gums|elbow|elbows|shin|shins|thigh|thighs)\b")


def _reads_as_a_body_complaint(clause):
    """True when a clause is a body said in trouble, in any of the ways people say it."""
    return bool(_BODY.search(clause) and _HURTING.search(clause))


def _reads_as_unwell(clause):
    """True when a clause says that someone or their animal is unwell."""
    return bool(_UNWELL.search(clause)) or _reads_as_a_body_complaint(clause)


# A contrast after the leave is the shape of the line, not the reason for going. "im going to bed
# but i cant switch off" is a person telling you what their nights are like, and the leave took
# the line: the sign-off ("Of course. Go and see to it, and mind yourself.") answered a goodbye
# nobody had said. So the tail after the contrast is read on its own, and it is the line when it
# is the person's own trouble - a habit that comes back, an inability, being overwhelmed, feeling
# rotten. It stays the reason (and the leave stays the leave) for anything the world puts in front
# of them: "got to go but my kids are up", "im going to bed but im so tired".
_CONTRAST = re.compile(r"\b(?:but|though|although)\b")
# A habit that comes back is the person's own, and it is the commonest shape in the tail: "i
# keep thinking about work", "i cant switch off", "i still wake at four". The words are the
# ones that say the thing repeats, on the person doing it - "never got to ask" and "its been a
# long day" are not that, and reading them as a trouble turned a goodbye into an answer.
_COMES_BACK = re.compile(
    r"\b(?:keep|keeps|keeping|kept|cant|cannot|can'?t|still|always)\b")
# ...and what repeats has to be the person's own head, sleep or body. "i keep forgetting the
# bins" and "i keep losing my keys" repeat too, and they are the errand the person is leaving to
# do: stood down for those, the lookup answered one of them with the study card ("Read a section,
# then close the book and say its three points out loud"), which is worse than any goodbye.
_MIND = re.compile(
    r"\b(?:think|thinks|thinking|thought|thoughts|worry|worried|worrying|fret|fretting|"
    r"overthink|overthinking|sleep|sleeping|asleep|awake|wake|wakes|waking|woke|dream|dreams|"
    r"dreaming|night|nights|head|heads|headache|headaches|migraine|migraines|mind|brain|"
    r"cry|crying|cried|tears|panic|panicking|stress|stressed|anxious|switching|switch)\b")
_OVERWHELM = re.compile(
    r"\b(?:i'?m|i am|i feel|im feeling|feeling|i've been feeling|ive been feeling)\s+"
    r"(?:so |really |a bit |very |totally |completely |proper )?overwhelm(?:ed|ing)\b"
    r"|\b(?:i|we) can'?t (?:keep up|take any ?more|cope any ?more|manage any ?more)\b"
    r"|\b(?:i'?m|i am|im) not coping\b|\bnot coping (?:at all|any ?more|right now)\b"
    r"|\bit'?s more than i can (?:handle|take|cope with|manage|deal with)\b"
    r"|\bmore than i can (?:handle|take|cope with|manage|deal with)\b")
# An adverb between the person and the feeling does not change the feeling: "i still feel rough",
# "i just feel low" and "i really feel awful" are the same line as "i feel rough", so a leave that
# carries one of them behind a "but" has to stand down for it the way "im off but i feel like
# rubbish" already did.
_ADVERB = r"(?:still|just|really|actually|genuinely|very|so|pretty|quite|proper|sort of|kind of)"
_FEELS_ROTTEN = re.compile(
    r"\b(?:i|we)\s+(?:" + _ADVERB + r"\s+)*"
    r"feel(?:ing)?\s+(?:" + _ADVERB + r"\s+)*(?:like\s+)?(?:rubbish|rough|awful|terrible|"
    r"dreadful|poorly|crap|lousy|ill|sick|low|down|knackered|exhausted)\b")


def _a_trouble_behind_a_contrast(clean):
    """True when a contrast sets the person's own trouble against the leaving.

    "im going to bed but i cant switch off", "i should go to bed but i keep waking up", "got to go
    but im overwhelmed" and "im off but i feel like rubbish" are about the second half, and that
    half is the modules' to answer, so none of them is a goodbye. A thank-you, a wish or a
    sign-off after the contrast is still a goodbye ("im off but nice talking to you"), and a
    reason for going ("got to go but my kids are up", "im going to bed but im so tired") is the
    leave's own and stays one.
    """
    if not _CONTRAST.search(clean):
        return False
    tail = " ".join(_CONTRAST.split(clean, 1)[1].split())
    if not tail:
        return False
    if _is_thanks_clause(tail) or _is_sign_off(tail) or _is_wish_clause(tail):
        return False
    if _names_their_own_trouble(tail):
        return True
    return bool(_COMES_BACK.search(tail) and _MIND.search(tail))


def _names_their_own_trouble(text):
    """True when this part of the line is the person's own trouble and not a reason for going.

    One reading for both shapes, because a "but" is only one way of joining the two halves:
    "im off but i feel like rubbish" and "gotta go, i feel awful" are the same line with a comma
    in it, and only the first was read. The sign-off answers the second with "Go on then - that
    comes before me. Take care.", which is about the wrong half.
    """
    return bool(_OVERWHELM.search(text or "") or _FEELS_ROTTEN.search(text or ""))


# A reply that lets the person go, in the words a *reply* uses rather than the words a *line*
# uses: the leave reading above reads what the person said, and this reads what the bot is about
# to say. A goodbye turn belongs to whoever says goodbye with it, and a small-talk reply that
# answers the reason behind the leave - "Nice. Tell me how it goes." to "going to bed, my back
# is killing me" - is not a sign-off however well the line was read.
_SIGN_OFF = re.compile(r"""\b(?:
    take\s+(?:it\s+easy|care)|mind\s+(?:yourself|how\s+you\s+go|out)
    |look\s+after\s+yourself|see\s+(?:you|ya)|bye|good\s+luck|all\s+the\s+best
    |go\s+(?:well|safely|on\s+then|gently)|talk\s+(?:soon|later|tomorrow)|catch\s+you
    |come\s+back|be\s+safe|get\s+home\s+safe|on\s+your\s+way|off\s+you\s+go
    |(?:let|leave)\s+you\s+(?:to\s+it|go)|safe\s+home|enjoy\s+(?:it|yourself|the\s+\w+)
    |have\s+(?:a|an)\s+(?:good|nice|great|lovely)\s+\w+
    |hope\s+(?:it|that|work|the\s+\w+)\s+(?:goes|went|is)\s+well
)\b""", re.X)


def reads_as_a_sign_off(reply):
    """True when a reply lets the person go rather than answering the reason they gave.

    The arbiter asks this of a small-talk candidate on a line that says the person is leaving
    (`bot/modules/arbiter.py`, `_leaving_reply`): the module that read the line as a goodbye keeps
    the turn, and one that read the reason clause keeps nothing.
    """
    return bool(_SIGN_OFF.search(" ".join(str(reply or "").lower().split())))


def _is_wish_clause(clause):
    """True when this clause is a goodbye said as a wish and nothing else."""
    match = _WISH.search(clause)
    if not match:
        return False
    rest = re.findall(r"[a-z']+", clause[match.end():])
    return all(word in _WISH_ALLOWED for word in rest)


# How people type a goodbye: the leave, then the shorthand sign-off, with nothing between them.
# "gotta go work ttyl" is a whole goodbye and the leftovers are `ttyl`, which is not in `_ALLOWED`
# and never will be (nothing else in a line keeps it), so the clause was not a leave at all and a
# work row took the turn: "gotta go work ttyl" got three slides and a memory line. The sign-off
# words are the ones `_SIGN_OFF` already reads on their own, and the shorthand is the same thing
# typed short. Nothing else is let through: a clause with a noun of its own left over is still the
# plan it says it is.
_LEAVE_SHORTHAND = frozenset(("ttyl", "talklater", "gtg", "g2g", "cya", "l8r", "l8tr", "n8",
                              "xx", "xxx"))


def _is_leave_clause(clause):
    """True when this clause is a leave and nothing else."""
    if _is_wish_clause(clause):
        return True
    if not _LEAVE.search(clause):
        return False
    # Going away somewhere later is a plan, not a goodbye: "im away next week", "im out tonight"
    # and "im away for the weekend in june" say when, and the person is still here talking.
    if _AWAY_OUT.search(clause) and _AWAY_PLAN.search(clause):
        return False
    rest = _LEAVE.sub(" ", clause)
    downs = _ALLOWED | _SIGN_OFF_WORDS | _LEAVE_SHORTHAND
    if all(word in downs for word in re.findall(r"[a-z']+", rest)):
        return True
    # A time is part of a sign-off, not of every leave: "see you at 5" and "talk to you after
    # work" are goodbyes, and "i have to go to work tomorrow at 6", "im going on monday" and
    # "we are going on friday" are plans the person is still here to talk about. The sign-off is
    # what the time belongs to, so the time is only taken off a clause that has one.
    if not _A_SIGN_OFF.search(clause):
        return False
    trimmed = _A_LEAVE_TIME.sub(" ", rest)
    return trimmed != rest and all(word in downs for word in re.findall(r"[a-z']+", trimmed))


def reads_as_leaving(clean, words=None):
    """True when the person is saying goodbye, with or without a reason around it.

    The leave has to be a whole clause: the first clause with the reason after it
    ("ill let you go, dinner is burning"), the last clause with the reason before it ("the
    kids are up, got to go"), or the whole line. A question keeps its answer, and a leave
    anyone is being talked out of ("dont go") is not a leave.
    """
    return _reads_as_leaving(clean, words)


def reads_as_a_leave_with_a_body_in_it(clean, words=None):
    """True when a goodbye stops being one only because the reason names a body in trouble.

    "right, im off to bed, my tooth is agony" is a goodbye whose reason is a symptom, so the
    body is the turn and this module stands out of the way (see `reads_as_leaving`). That is
    right while something answers the body. When nothing does, the person is left with their
    own line said back to them, which is worse than the goodbye: the fallback asks this before
    it files the line, and says the goodbye instead.
    """
    return not reads_as_leaving(clean, words) and _reads_as_leaving(clean, words, unwell_blocks=False)


def reads_as_a_leave_with_a_trouble_in_it(clean, words=None):
    """True when a goodbye stops being one only because a contrast sets a trouble against it.

    "im off but i feel rough" is not a goodbye while something answers the feeling, and the
    reading stands down for it (see `_a_trouble_behind_a_contrast`). The turn then belongs to the
    modules that answer a trouble - but a tail nobody answers leaves the person with the fallback's
    intake form ("Got it. Is there anything you'd like a hand with?"), which is a worse reply than
    letting them go. This is the same shape as `reads_as_a_leave_with_a_body_in_it`: the fallback
    asks it before it files the line, and says the goodbye when nothing else would.
    """
    return (not reads_as_leaving(clean, words)
            and _reads_as_leaving(clean, words, trouble_blocks=False))


def _reads_as_leaving(clean, words=None, unwell_blocks=True, trouble_blocks=True):
    """`reads_as_leaving`, with the body reason and the trouble behind a contrast blockers or not."""
    clean = " ".join(str(clean or "").lower().split())
    if not clean or "?" in clean:
        return False
    if _OPENS_QUESTION.match(clean) or _KEEPS.search(clean):
        return False
    if trouble_blocks and _a_trouble_behind_a_contrast(clean):
        return False
    clauses = _clauses(clean)
    if not clauses:
        return False
    if len(clauses) == 1:
        return _is_leave_clause(clauses[0])
    if any(_asks_something(clause) for clause in clauses):
        # A leave with a question in it is not a leave: the question is the turn, and a sign-off
        # in front of it walks out of a conversation the person is still in.
        return False
    first, last = clauses[0], clauses[-1]
    if _is_leave_clause(first):
        rest = " ".join(clauses[1:])
        # The tail is the reason: a statement, not an ask of its own, and not somebody being
        # unwell - that is the line, and the body it names is what has to be answered. Their own
        # trouble in the reason is the same stand-down as behind a "but": "gotta go, everything is
        # too much for me" signs off over the thing that matters in it.
        return (not _ASKS.search(rest) and not (unwell_blocks and _reads_as_unwell(rest))
                and not (trouble_blocks and _names_their_own_trouble(rest)))
    if _is_leave_clause(last):
        return True
    # The leave can also be in the middle, which is where it lands when a thank-you goes in
    # front of it: "ok thanks, ill let you go, dinner is burning" had the leave in clause two,
    # so neither end read as one and the cooking entry answered the reason. Everything before
    # the leave has to be nothing but the front of a goodbye, and everything after it a reason.
    for index, clause in enumerate(clauses[1:-1], start=1):
        if not _is_leave_clause(clause):
            continue
        before = " ".join(clauses[:index])
        after = " ".join(clauses[index + 1:])
        if _ASKS.search(after) or (unwell_blocks and _reads_as_unwell(after)):
            continue
        if before and not (_is_filler(before) or _is_thanks_clause(before)):
            continue
        return True
    return False


# A time the going is for is a plan, not a goodbye: "im away next week", "im out tonight", "im
# away for the weekend in june". The words are the ones a plan is said with and the same line
# said as a goodbye is not ("im away for a bit", "ok im out").
_AWAY_OUT = re.compile(r"\b(?:i'?m|im|i\s+am|we'?re|we\s+are)\s+(?:off|away|out)\b")
_AWAY_PLAN = re.compile(
    r"\b(?:next\s+(?:week|month|year|weekend)|this\s+(?:weekend|evening|afternoon)"
    r"|tonight|tomorrow|on\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
    r"|at\s+the\s+weekend|for\s+the\s+weekend|in\s+(?:june|july|august|september|october"
    r"|november|december|january|february|march|april|may))\b")


# The person going away is a leave even when the leave verb is "off" or "away" and not "go":
# "have a good weekend, i am off camping" is a goodbye, and asking "what's going on?" of somebody
# who has just said they are leaving is the wrong half of it.
_AWAY = re.compile(r"\b(?:i'?m|im|i am|we'?re|were|we are)\s+(?:off|away)\b"
                   r"|\b(?:i'?m|im|i am)\s+(?:heading|setting) off\b")


def _asks_something(clause):
    """True when a clause is itself a question, with or without the question mark.

    Read on its own clause and not on the whole line, because the leave and the ask are usually
    two clauses: the wish is the first and the question is the second, and the question is what
    the person wants answered.
    """
    clause = " ".join(str(clause or "").lower().split())
    if not clause:
        return False
    if "?" in clause:
        return True
    return bool(_ASKS_OPENER.match(clause) or _ASKS_ANYWHERE.search(clause))


def _is_filler(clause):
    """True when a clause is only the run-up to a goodbye: "ok", "right then", "ok thanks".

    A thank-you is the commonest run-up there is, with the little words it carries: "ok thanks
    for all your help, i need to go, the bus is here" is a goodbye and not a thanks.
    """
    words = re.findall(r"[a-z']+", clause)
    return bool(words) and all(word in _RUN_UP for word in words)


# A goodbye given as a wish gets the wish back. The leaving pool is all sign-offs ("Go well, and
# see you when you're back"), and answering "have a good day at work" with a sign-off is the bot
# walking out of a conversation it was wished well in.
WISH_POOL = (
    "Thanks — that's kind. Same to you.",
    "Ta. You too — look after yourself.",
    "Thanks, and the same back to you.",
    "Cheers. Hope it goes well for you too.",
    "Thank you — you too.",
)
# "get well soon" and "feel better" are wishes about the bot's health, and it has not got any to
# wish it better from. "You too" answers a good day, not an illness, so this half says the honest
# thing warmly instead of agreeing with the premise.
WELL_POOL = (
    "Thanks — that's kind of you. I'm well, and I hope you are too.",
    "Nothing wrong with me, but thank you. Look after yourself.",
    "That's kind. I'm fine — and I hope you are too.",
)
# An emergency is not a turn to answer with the bot's own health. "i want to kill myself" then
# "i hope you feel better" got "Nothing wrong with me, but thank you. Look after yourself." - the
# wish is taken and the person is dropped, in the one thread where they most need the door kept
# open. No advice here either: the safety module has just given it, and a second instruction in
# front of it is worse than none. These only keep the door open and hand the turn back.
CRISIS_POOL = (
    "That's kind of you — but you're the one I'm thinking about. How are you doing right now?",
    "Thank you, and I mean it. Never mind me — how is it now?",
    "That's kind. I'm all right, and I'd rather stay with you. What is happening right now?",
)
# The wish back, for a thread where the person is the one who is having a bad time. "I'm well, and
# I hope you are too" answers a wish and contradicts the line above it when the line above said
# they were ill: "i feel awful" / "get well soon" got the bot's own health back at them. A friend
# takes the wish and gives it back to the person who needs it.
KINDER_POOL = (
    "Thanks — and I hope it eases soon.",
    "Ta. Same to you — and I hope you feel better soon.",
    "Thank you — and I hope whatever it is lets up a bit.",
    "Thanks, and I hope you are feeling better soon.",
)
# "sleep well" is a wish about a night, and "hope it goes well for you too" is about an occasion
# with an "it" in it that a bedtime does not have. Splitting the pool by what the wish names is
# what WELL_POOL already does for health.
NIGHT_POOL = (
    "Thanks — and the same to you. Sleep well.",
    "Ta. You too — get a good night.",
    "Thank you. And I hope you sleep well too.",
)
# A wish with the person's own news behind it: "have a good weekend, mine is ruined", "sleep
# well, i wont get any", "enjoy your evening, im working late". The wish is courtesy and the news
# is the turn, so the reply sets the wish aside and asks about the news. The sign-off pools are
# wrong here - they walk out of a conversation the person is still in - and so is answering the
# wish as if nothing else had been said.
OWN_NEWS_POOL = (
    "Never mind me — what's happening with you?",
    "Ah, that matters more than me. Tell me about it.",
    "Then the wish can wait — what's going on?",
    "Forget the wish for a second. How is it going?",
)
_NIGHT = re.compile(r"\b(?:sleep|sleeping|bed|bedtime|night's sleep|goodnight)\b|\bnight\b")
_WELL = re.compile(r"\b(?:get well|feel better|well soon)\b")
# The wish gets the wish back only when it names what is being wished for. "take care", "all the
# best" and "good luck" on their own are the formulas of a sign-off, and the sign-off pool has
# been answering those well: "No worries at all. Mind yourself." is a better line than "Thanks,
# and the same back to you." A named day, night, meal or illness is a wish about something, and
# that something is what comes back.
_WISH_THING = re.compile(
    r"\b(?:day|evening|weekend|week|night|lunch|dinner|meal|party|trip|journey|holiday|break|"
    r"shift|rest|bath|walk|flight|fun|well|better|tomorrow|tonight|today|sleep|tight|bed)\b"
    r"|\bwith (?:the|your|it|that)\b")


def _thread_is_an_emergency(memory):
    """True when the last thing said was an emergency reply, not an ordinary one.

    The safety module records the case it answered (`safety_case`) and the runtime records which
    module answered each turn, so this reads the two facts rather than guessing at words. A minor
    injury is answered by the same module and records no case, so a cut finger keeps the ordinary
    wish back: it is a wish, not a crisis with a plaster on it.
    """
    if not isinstance(memory, dict) or not memory.get("safety_case"):
        return False
    turns = [turn for turn in (memory.get("turns") or []) if isinstance(turn, dict)]
    return bool(turns) and turns[-1].get("module") == "safety"


# The vocabulary of a person having a bad time, read on the *thread* and never on the line: the
# wish is the second turn ("i feel awful" then "get well soon") and this decides whose wish it is.
# It is wider than `_UNWELL` because a leave reading must not be widened by it: "i have to go, i
# feel rough" is still a goodbye, and "work is killing me" is still figure of speech, but neither
# stops the person from being the one who is unwell.
_UNWELL_FEELING = re.compile(
    r"\b(?:awful|terrible|dreadful|rough|rubbish|lousy|miserable|cold|chills?|sniffles"
    r"|sore throat|under the weather|poorly|poor thing)\b")


def _thread_is_unwell(memory):
    """True when the last thing the person said was that they (or their animal) are unwell.

    Read off the memory rather than the line, because the wish is the second turn: "i feel awful"
    then "get well soon" is a wish for the person, and the bot answering with its own health is
    the wrong half of the exchange.
    """
    turns = [turn for turn in ((memory or {}).get("turns") or []) if isinstance(turn, dict)]
    for turn in reversed(turns[-2:]):
        line = str(turn.get("user") or "")
        if _reads_as_unwell(line) or _UNWELL_FEELING.search(line.lower()):
            return True
    return False


def _wish_pool(clean, memory=None):
    """The wish-back lines for a goodbye said as a wish, or the leaving pool's own."""
    line = " ".join(str(clean or "").lower().split())
    if _thread_is_an_emergency(memory):
        return CRISIS_POOL
    if _thread_is_unwell(memory):
        return KINDER_POOL
    if _WELL.search(line):
        return WELL_POOL
    if _NIGHT.search(line):
        return NIGHT_POOL
    return WISH_POOL


def pool(clean, words=None, unwell_blocks=True, memory=None, trouble_blocks=True):
    """The goodbye lines for this leave, or None when the line is not one."""
    if not _reads_as_leaving(clean, words, unwell_blocks, trouble_blocks):
        return None
    clauses = _clauses(" ".join(str(clean or "").lower().split()))
    wishes = [clause for clause in clauses if _is_wish_clause(clause)]
    if wishes and not _WISH_THING.search(" ".join(wishes)):
        wishes = []
    leaving_too = any(_is_leave_clause(clause) and not _is_wish_clause(clause)
                      for clause in clauses)
    # A wish with news in the same line is not the wish coming back: "have a good weekend, mine is
    # ruined" and "get well soon, i feel awful" carry a second clause with its own subject, and
    # the news is the turn. Only a wish and the run-up to it may be in the line for the wish to
    # come back.
    own_news = [clause for clause in clauses
                if not _is_wish_clause(clause) and not _is_leave_clause(clause)
                and not _is_filler(clause) and not _is_thanks_clause(clause)
                and not _is_sign_off(clause)]
    opens_with_a_wish = bool(clauses) and bool(wishes) and _is_wish_clause(clauses[0]) \
        and bool(_WISH_THING.search(clauses[0]))
    going_away = any(_AWAY.search(clause) for clause in own_news)
    if wishes and not leaving_too and not going_away:
        if own_news and opens_with_a_wish:
            # The wish opens the line and the news follows it, so the person is still here and
            # talking: "sleep well, i wont get any", "have a good weekend, mine is ruined". The
            # sign-off pools are wrong for that - "That first, definitely. Come back when you
            # have a minute." was the bot walking out on somebody who cannot sleep - so the wish
            # is set aside and the news is asked about.
            return OWN_NEWS_POOL
        if own_news:
            # The wish is on the end of news that is not a wish ("my mum is in hospital, get well
            # soon"), and that news has an answer of its own somewhere else in the composer.
            return None
        # The whole line is a wish, so the wish comes back. A line that also says the person is
        # going ("have a good day, im off now") keeps the sign-off, because the goodbye there is
        # the fact and the wish is only how it is put.
        return _wish_pool(" ".join(wishes), memory)
    # A reason in the line is answered before the leave is; a thank-you is not a reason. The
    # leave can be any clause, so the reason is everything after the first leave that is one.
    for index, clause in enumerate(clauses):
        if not _is_leave_clause(clause):
            continue
        after = " ".join(clauses[index + 1:])
        # A sign-off on the end is not a reason to go and see to anything ("ok im out, night",
        # "got to go, night then"): the reason pool answers it with "Of course. Go and see to it,
        # and mind yourself", which reads as though there were a job waiting. Only a thanks and a
        # sign-off are set aside; anything else after the leave is the reason.
        if after and not (_is_thanks_clause(after) or _is_sign_off(after)):
            # "see you at 5 tomorrow, i have a meeting": the day on the goodbye makes the meeting
            # the plan for that day, not the reason for going now.
            if _A_DAY_AHEAD.search(clause):
                return POOL
            return REASON_POOL
        return POOL
    return POOL


def lines():
    """Every goodbye this module can say, for the arbiter's "is this the sign-off" test."""
    return (frozenset(POOL) | frozenset(REASON_POOL) | frozenset(WISH_POOL)
            | frozenset(WELL_POOL) | frozenset(KINDER_POOL) | frozenset(NIGHT_POOL)
            | frozenset(CRISIS_POOL) | frozenset(OWN_NEWS_POOL))
